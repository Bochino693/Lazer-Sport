"""O pagamento 100% do orçamento registra a venda (LEIA-ME-V10, seção 81).

O pedido: "após o orçamento atingir aprovado, que você deve gerar a
assinatura, a opção de pagamento deve ser o último estágio, terminando o
pagamento 100% deve registrar como venda."

O que estes testes protegem:

  * quitar 100% cria UMA `core.Venda`, confirmada, com o recebido, o
    CPF/CNPJ do cliente e a forma (quando o texto fala de uma só);
    registrar de novo não duplica; outro valor ainda 100% só ajusta;
  * a correção que tira dos 100% (parcial, zero) desfaz a venda -- é dado
    derivado -- e o histórico do orçamento conta, na linha do pagamento;
  * a ação do painel diz no recado que virou venda, e o servidor continua
    exigindo só a aprovação (o termo sem assinatura é pergunta da tela);
  * `Venda.__str__` sem pedido; a tela de Vendas mostra a venda do
    orçamento com o cliente, o número e o caminho de volta; o relatório
    da gestão não mostra "#None";
  * o Financeiro conta a receita uma vez só, no mês do pagamento;
  * a migração 0061 preenche os orçamentos que já estavam pagos, com a
    data do pagamento, sem duplicar ao rodar de novo, e desfaz;
  * a janela do orçamento leva a régua (Aprovado -> Assinatura ->
    Pagamento -> Venda) e o que ela precisa.
"""

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.models import Pedido, Venda

from . import financeiro as fin
from .models import (
    AtividadeOrcamento,
    Cliente,
    ItemOrcamento,
    Orcamento,
    forma_da_venda,
)
from .permissoes import atribuir_funcoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

CPF = "529.982.247-25"


class BaseVenda(TestCase):
    def setUp(self):
        self.financeiro = User.objects.create_user(username="caixa", password="x")
        atribuir_funcoes(self.financeiro, ["financeiro", "vendas"])
        self.cliente = Cliente.objects.create(nome_cliente="Buffet Alegria", documento=CPF)

    def orcamento(self, *, total="3000.00", status=Orcamento.Status.APROVADO, cliente=True, **campos):
        padrao = {
            "nome_cliente": "Buffet Alegria",
            "status": status,
            "forma_pagamento": "Pix",
            "responsavel": self.financeiro,
        }
        if cliente:
            padrao["cliente"] = self.cliente
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica 3 m",
            quantidade=1, valor_unitario=Decimal(total),
        )
        return orcamento

    def pagar(self, orcamento, valor):
        return self.client.post(
            "/orcamentos/",
            {"action": "pagamento", "id": orcamento.pk, "valor_pago": valor},
            **AJAX,
        )


# ======================================================================
# O 100% VIRA VENDA -- UMA SÓ -- E SAI QUANDO DEIXA DE SER 100%
# ======================================================================
class VendaDoPagamentoTests(BaseVenda):

    def test_pagamento_de_100_registra_uma_venda_confirmada(self):
        orcamento = self.orcamento()
        mudanca = orcamento.registrar_pagamento(Decimal("3000.00"), "Pix no balcão")

        orcamento.refresh_from_db()
        venda = orcamento.venda
        self.assertIsNotNone(venda)
        self.assertEqual(mudanca.acao, "criada")
        self.assertEqual(mudanca.venda_id, venda.pk)
        self.assertEqual(venda.valor_pago, Decimal("3000.00"))
        self.assertTrue(venda.confirmado)
        self.assertEqual(venda.cpf, "52998224725")
        self.assertEqual(venda.forma_pagamento, "pix")
        self.assertIsNone(venda.pedido_id)
        self.assertEqual(venda.orcamento, orcamento)
        self.assertEqual(venda.origem, "orcamento")

    def test_registrar_de_novo_nao_duplica_e_outro_valor_so_ajusta(self):
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(Decimal("3000.00"))
        primeira = Orcamento.objects.get(pk=orcamento.pk).venda_id

        mudanca = orcamento.registrar_pagamento(Decimal("3000.00"))
        self.assertEqual(mudanca.acao, "")
        mudanca = orcamento.registrar_pagamento(Decimal("3100.00"))  # entrou a mais
        self.assertEqual(mudanca.acao, "ajustada")

        self.assertEqual(Venda.objects.count(), 1)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.venda_id, primeira)
        self.assertEqual(orcamento.venda.valor_pago, Decimal("3100.00"))

    def test_a_venda_de_outra_aba_nao_se_repete(self):
        """A instância velha na memória não cria uma segunda venda."""
        orcamento = self.orcamento()
        velha = Orcamento.objects.get(pk=orcamento.pk)
        orcamento.registrar_pagamento(Decimal("3000.00"))
        velha.registrar_pagamento(Decimal("3000.00"))
        self.assertEqual(Venda.objects.count(), 1)

    def test_abaixo_de_100_a_venda_sai(self):
        orcamento = self.orcamento()
        for valor, situacao in (("1000.00", "parcial"), ("0.00", "pendente")):
            with self.subTest(valor=valor):
                orcamento.registrar_pagamento(Decimal("3000.00"))
                venda_id = Orcamento.objects.get(pk=orcamento.pk).venda_id
                mudanca = orcamento.registrar_pagamento(Decimal(valor))
                self.assertEqual((mudanca.acao, mudanca.venda_id), ("desfeita", venda_id))
                orcamento.refresh_from_db()
                self.assertEqual(orcamento.status_pagamento, situacao)
                self.assertIsNone(orcamento.venda_id)
                self.assertFalse(Venda.objects.filter(pk=venda_id).exists())
        self.assertEqual(Venda.objects.count(), 0)

        # Quitou de novo: uma venda nova.
        orcamento.registrar_pagamento(Decimal("3000.00"))
        self.assertEqual(Venda.objects.count(), 1)

    def test_parcial_nao_e_venda(self):
        orcamento = self.orcamento()
        mudanca = orcamento.registrar_pagamento(Decimal("2999.99"))
        self.assertEqual(mudanca.acao, "")
        self.assertFalse(Venda.objects.exists())

    def test_sem_cadastro_vale_o_cpf_de_quem_assinou(self):
        from . import documento_assinatura as svc
        from .tests_documento_assinatura import png_de_assinatura

        orcamento = self.orcamento(cliente=False, forma_pagamento="50% no Pix e 50% no cartão")
        documento = svc.gerar(orcamento, self.financeiro)
        token, _ = svc.emitir_link(documento)
        resposta = self.client.post(
            f"/assinar/{token}/",
            {"nome": "Maria Alegria", "documento": "111.444.777-35", "concordo": "1",
             "assinatura": png_de_assinatura()},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)

        orcamento.registrar_pagamento(Decimal("3000.00"))
        venda = Orcamento.objects.get(pk=orcamento.pk).venda
        self.assertEqual(venda.cpf, "11144477735")
        # Duas formas no texto: escolher seria inventar.
        self.assertIsNone(venda.forma_pagamento)

    def test_a_forma_da_venda_so_sai_quando_o_texto_fala_de_uma(self):
        for texto, esperado in (
            ("Pix", "pix"), ("PIX à vista", "pix"), ("Cartão de crédito em 3x", "cartao"),
            ("Dinheiro na entrega", "dinheiro"), ("Boleto", None), ("", None),
            ("50% Pix e 50% no cartão", None),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(forma_da_venda(texto), esperado)

    def test_excluir_o_orcamento_pago_leva_a_venda_junto(self):
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(Decimal("3000.00"))
        orcamento.refresh_from_db()
        venda_id = orcamento.venda_id
        orcamento.delete()
        self.assertFalse(Venda.objects.filter(pk=venda_id).exists())


# ======================================================================
# A AÇÃO DO PAINEL: O RECADO E O HISTÓRICO
# ======================================================================
class AcaoDePagamentoTests(BaseVenda):

    def test_o_recado_e_o_historico_contam_a_venda(self):
        orcamento = self.orcamento()
        self.client.force_login(self.financeiro)

        resposta = self.pagar(orcamento, "3.000,00")
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        orcamento.refresh_from_db()
        self.assertEqual(corpo["venda"], orcamento.venda_id)
        self.assertEqual(corpo["venda_acao"], "criada")
        self.assertIn(f"registrado como venda #{orcamento.venda_id}", corpo["msg"])
        self.assertIn("100%", corpo["msg"])
        linha = AtividadeOrcamento.objects.filter(
            orcamento=orcamento, tipo=AtividadeOrcamento.Tipo.PAGAMENTO,
        ).latest("id")
        self.assertIn(f"registrado como venda #{orcamento.venda_id}", linha.resumo)

        venda_id = orcamento.venda_id
        resposta = self.pagar(orcamento, "1.000,00")
        corpo = resposta.json()
        self.assertEqual(corpo["venda_acao"], "desfeita")
        self.assertIsNone(corpo["venda"])
        self.assertIn(f"A venda #{venda_id} saiu das vendas", corpo["msg"])
        linha = AtividadeOrcamento.objects.filter(
            orcamento=orcamento, tipo=AtividadeOrcamento.Tipo.PAGAMENTO,
        ).latest("id")
        self.assertIn(f"a venda #{venda_id} saiu", linha.resumo)
        self.assertIn("deixou de ser 100%", linha.resumo)
        self.assertFalse(Venda.objects.exists())

    def test_o_pagamento_sem_o_termo_assinado_passa_no_servidor(self):
        """A pergunta "O contrato ainda não foi assinado" é da tela, não trava."""
        orcamento = self.orcamento()
        self.client.force_login(self.financeiro)
        self.assertEqual(self.pagar(orcamento, "3.000,00").status_code, 200)
        self.assertTrue(Orcamento.objects.get(pk=orcamento.pk).venda_id)

    def test_so_depois_da_aprovacao(self):
        orcamento = self.orcamento(status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.client.force_login(self.financeiro)
        resposta = self.pagar(orcamento, "3.000,00")
        self.assertGreaterEqual(resposta.status_code, 400)
        self.assertFalse(Venda.objects.exists())

    def test_a_janela_leva_a_regua_e_a_pergunta_do_contrato(self):
        orcamento = self.orcamento(respondido_em=timezone.now())
        orcamento.registrar_pagamento(Decimal("3000.00"))
        gestor = User.objects.create_superuser("gestor-venda", "g@example.com", "x")
        self.client.force_login(gestor)
        html = self.client.get("/orcamentos/", **INTERNO).content.decode()

        self.assertIn('id="orcamentoEtapas"', html)
        for etapa in ("aprovado", "assinatura", "pagamento", "venda"):
            self.assertIn(f'data-etapa="{etapa}"', html)
        # O termo vem antes do pagamento na janela também.
        self.assertLess(html.index('id="orcamentoDocumentoAssinatura"'), html.index('id="orcamentoPagamentoResumo"'))
        self.assertIn("O contrato ainda não foi assinado. Registrar o pagamento mesmo assim?", html)
        self.assertIn("LSAviso.confirmar", html)
        self.assertNotIn("window.confirm(", html)

        dados = json.loads(re.search(
            r'<script id="orcamentosDados" type="application/json">(.*?)</script>', html, re.S,
        ).group(1))
        por_id = {d["id"]: d for d in dados}
        orcamento.refresh_from_db()
        self.assertEqual(por_id[orcamento.pk]["venda"], orcamento.venda_id)
        self.assertTrue(por_id[orcamento.pk]["aprovado_em"])
        self.assertEqual(por_id[orcamento.pk]["documento_assinatura"]["situacao"], "gerar")
        self.assertIn(f"venda #{orcamento.venda_id}", html)


# ======================================================================
# ONDE A VENDA APARECE: __str__, VENDAS, RELATÓRIO, FINANCEIRO
# ======================================================================
class VendaNasTelasTests(BaseVenda):

    def test_str_da_venda_sem_pedido(self):
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(Decimal("3000.00"))
        venda = Venda.objects.get()
        self.assertEqual(str(venda), f"Venda do orçamento nº {orcamento.numero_documento}")

        solta = Venda.objects.create(valor_pago=Decimal("10.00"))
        self.assertEqual(str(solta), f"Venda #{solta.pk}")
        self.assertEqual(solta.origem, "site")

        pedido = Pedido.objects.create(status="finalizado", total_liquido=Decimal("50.00"))
        do_site = Venda.objects.create(pedido=pedido, valor_pago=Decimal("50.00"))
        self.assertEqual(str(do_site), f"Venda do Pedido #{pedido.pk}")
        self.assertIsNone(do_site.orcamento_de_origem)

    def test_a_tela_de_vendas_mostra_a_venda_do_orcamento(self):
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(Decimal("3000.00"))
        pedido = Pedido.objects.create(status="finalizado", total_liquido=Decimal("50.00"))
        Venda.objects.create(pedido=pedido, valor_pago=Decimal("50.00"), confirmado=True)
        self.client.force_login(self.financeiro)

        resposta = self.client.get("/vendas/inner/", {"filtro": "confirmadas"}, **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertIn(f"Orçamento nº {orcamento.numero_documento}", html)
        self.assertIn(f"/orcamentos/?q={orcamento.pk}&amp;editar={orcamento.pk}", html)
        self.assertIn('class="ls-venda-origem orcamento"', html)
        self.assertIn('class="ls-venda-origem site"', html)
        self.assertIn(f"Pedido #{pedido.pk}", html)
        self.assertIn("Buffet Alegria", html)
        self.assertIn("3.000,00", html)
        self.assertNotIn("#None", html)
        self.assertEqual(resposta.context["valor_confirmado"], Decimal("3050.00"))
        # A venda do orçamento já nasce confirmada: a bolinha não conta.
        self.assertEqual(
            self.client.get("/vendas/inner/", **INTERNO).context["page_obj"].paginator.count, 0,
        )

    def test_o_relatorio_da_gestao_nao_mostra_none(self):
        """O relatório antigo da gestão (a rota hoje leva ao Financeiro).

        A moldura dele (`base_adm`) depende das rotas do painel; o que a
        venda de orçamento podia quebrar é a lista, o bloco `content` --
        é ele que se desenha aqui, com o contexto da própria view.
        """
        from django.template import Context
        from django.template.loader import get_template
        from django.template.loader_tags import BlockNode

        from core.views import RelatorioVendasView

        orcamento = self.orcamento()
        orcamento.registrar_pagamento(Decimal("3000.00"))
        pedido = Pedido.objects.create(status="finalizado", total_liquido=Decimal("50.00"))
        Venda.objects.create(pedido=pedido, valor_pago=Decimal("50.00"), confirmado=True)

        view = RelatorioVendasView()
        view.request = RequestFactory().get("/adm/relatorios-vendas/")
        view.kwargs = {}
        contexto = view.get_context_data()
        modelo = get_template("gestao/relatoriov_adm.html").template
        bloco = next(
            no for no in modelo.nodelist.get_nodes_by_type(BlockNode) if no.name == "content"
        )
        html = bloco.nodelist.render(Context(contexto))
        self.assertIn(f"nº {orcamento.numero_documento}", html)
        self.assertIn(f"#{pedido.pk}", html)
        self.assertNotIn("#None", html)
        self.assertNotRegex(html, r"<br>#\s*</div>")

    def test_o_financeiro_conta_a_receita_uma_vez_no_mes_do_pagamento(self):
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(Decimal("3000.00"))
        orcamento.registrar_pagamento(Decimal("3000.00"))  # repetido: não soma de novo
        meses = fin.janela_de_meses(3)
        serie = fin.montar_series(meses)
        self.assertEqual(serie[-1]["receita"], Decimal("3000.00"))
        self.assertEqual(fin.indicadores(serie)["ticket_medio"], Decimal("3000.00"))

        # Desfeito, sai da receita.
        orcamento.registrar_pagamento(Decimal("1000.00"))
        self.assertEqual(fin.montar_series(meses)[-1]["receita"], Decimal("0.00"))


# ======================================================================
# A MIGRAÇÃO 0061: OS ORÇAMENTOS QUE JÁ ESTAVAM PAGOS
# ======================================================================
class MigracaoDasVendasTests(BaseVenda):

    def migracao(self):
        return import_module("sistema_interno.migrations.0061_vendas_dos_orcamentos_pagos")

    def rodar(self, funcao="preencher"):
        getattr(self.migracao(), funcao)(apps, SimpleNamespace(connection=connection))

    def pago_antes_desta_versao(self, valor, quando, **campos):
        """Pago como a regra antiga gravava: sem venda nenhuma."""
        orcamento = self.orcamento(**campos)
        Orcamento.objects.filter(pk=orcamento.pk).update(
            status_pagamento=Orcamento.StatusPagamento.PAGO,
            valor_pago=Decimal(valor),
            pago_em=quando,
        )
        return Orcamento.objects.get(pk=orcamento.pk)

    def test_preenche_com_a_data_do_pagamento_sem_duplicar_e_desfaz(self):
        agosto = timezone.make_aware(datetime(2026, 8, 14, 15, 30))
        pago = self.pago_antes_desta_versao("3000.00", agosto)
        sem_valor = self.pago_antes_desta_versao("0.00", agosto, cliente=False, forma_pagamento="Boleto")
        parcial = self.orcamento()
        parcial.registrar_pagamento(Decimal("100.00"))
        do_site = Venda.objects.create(valor_pago=Decimal("50.00"), confirmado=True)
        self.assertFalse(Venda.objects.exclude(pk=do_site.pk).exists())

        self.rodar()
        self.rodar()  # de novo: nada muda

        pago.refresh_from_db()
        sem_valor.refresh_from_db()
        parcial.refresh_from_db()
        self.assertEqual(Venda.objects.count(), 3)
        self.assertIsNone(parcial.venda_id)

        venda = pago.venda
        self.assertEqual(venda.valor_pago, Decimal("3000.00"))
        self.assertTrue(venda.confirmado)
        self.assertEqual(venda.cpf, "52998224725")
        self.assertEqual(venda.forma_pagamento, "pix")
        self.assertEqual(venda.criacao, agosto)
        # Sem o recebido anotado, vale o total; sem cliente, sem CPF.
        self.assertEqual(sem_valor.venda.valor_pago, Decimal("3000.00"))
        self.assertIsNone(sem_valor.venda.cpf)
        self.assertIsNone(sem_valor.venda.forma_pagamento)

        # A receita cai em agosto, e não no mês da migração.
        serie = fin.montar_series(fin.janela_de_meses(6, referencia=agosto.date() + timedelta(days=40)))
        por_mes = {linha["mes"]: linha["receita"] for linha in serie}
        self.assertEqual(por_mes[agosto.date().replace(day=1)], Decimal("6000.00"))

        self.rodar("desfazer")
        self.assertEqual(list(Venda.objects.values_list("pk", flat=True)), [do_site.pk])
        self.assertFalse(Orcamento.objects.filter(venda__isnull=False).exists())

    def test_e_so_dados(self):
        """O esquema é a 0060; misturar os dois estoura no PostgreSQL."""
        operacoes = self.migracao().Migration.operations
        self.assertEqual([type(op).__name__ for op in operacoes], ["RunPython"])
        self.assertTrue(operacoes[0].reversible)
        esquema = import_module("sistema_interno.migrations.0060_orcamento_venda").Migration
        self.assertEqual([type(op).__name__ for op in esquema.operations], ["AddField"])
        self.assertIn(("sistema_interno", "0059_importacao_data_documento"), esquema.dependencies)
