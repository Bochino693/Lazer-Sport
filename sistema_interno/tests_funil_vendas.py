"""Um funil só: pedido e orçamento viram venda; prazo e etiquetas (seção 89).

O pedido do dono: "pedidos vêm do site, orçamento a gente faz aqui manual,
os dois devem virar vendas após a finalização. O tempo de produção a gente
deve poder informar em cada pedido ou orçamento. Também devemos imprimir a
etiqueta (...) a partir de um orçamento ou pedido -- ponha nos dois e na
venda --, setando quantas cópias por máquina nós queremos, usando sempre
as folhas A4."

O que estes testes protegem:

  * O FUNIL. Pedido pago é venda (uma só, confirmada, no valor cobrado);
    andar até "finalizado" não cria a segunda; cancelar tira a venda;
    o pagamento aprovado pelo checkout de verdade cria a venda depois do
    commit; o orçamento continua virando venda no 100%; os dois na mesma
    tela de Vendas e o Financeiro conta cada um uma vez;
  * A MIGRAÇÃO 0194: os pedidos pagos de antes ganham a venda com a data
    do pedido, sem duplicar ao rodar de novo, e desfazer leva só as dela;
  * O PRAZO DE PRODUÇÃO em dias úteis: a previsão do pedido e do
    orçamento, o campo do painel (quem pode, o que recusa), o que o
    cliente lê em Meus pedidos e na proposta, e a venda que o carrega;
  * AS ETIQUETAS: a conta das folhas A4 (3 máquinas x 5 cópias, 4 por
    folha = 4 folhas), a página de impressão, as cópias, quem pode;
  * O ANDAMENTO do pedido no painel e as telas que mostram tudo isso.
"""

import datetime as dt
import json
import re
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Carrinho, ItemPedido, Pedido, Venda

from . import etiquetas_maquinas as etq
from . import financeiro as fin
from .models import Cliente, ItemOrcamento, Orcamento
from .permissoes import atribuir_funcoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
RAIZ = Path(__file__).resolve().parent

#: Uma sexta-feira: a conta dos dias úteis pula o fim de semana e o 20/11.
SEXTA = timezone.make_aware(dt.datetime(2026, 11, 13, 10, 0))


def equipe(nome, *funcoes):
    usuario = User.objects.create_user(username=nome, password="x")
    atribuir_funcoes(usuario, list(funcoes))
    return User.objects.get(pk=usuario.pk)


class BaseFunil(TestCase):

    def setUp(self):
        self.comprador = User.objects.create_user("comprador-funil", password="x")
        perfil = self.comprador.perfil
        perfil.nome_completo = "Marina Souza"
        perfil.telefone = "(11) 98888-7777"
        perfil.save()

    #: O endereço que o pedido ANTIGO, com frete, guardava.
    ENDERECO_ANTIGO = dict(
        rua="Rua das Flores", numero="120", bairro="Centro",
        cidade="São Paulo", estado="SP", cep="01000-000",
    )

    def pedido(self, status="pago", maquinas=(("Air Game Kids", 1),), forma="credito",
               quando=None, antigo_com_frete=False):
        """O pedido do site de hoje: RETIRADA NA FÁBRICA, sem frete e sem endereço.

        O site deixou de cobrar frete (o cliente combina com a transportadora
        dele). `antigo_com_frete` é o pedido de antes disso, que ainda está
        no banco: frete cobrado e endereço de entrega.
        """
        carrinho = Carrinho.objects.create(cliente=self.comprador.perfil, cpf_cnpj="529.982.247-25")
        envio = (
            dict(tipo_envio="frete", valor_frete=Decimal("150.00"), **self.ENDERECO_ANTIGO)
            if antigo_com_frete else dict(tipo_envio="retirada")
        )
        pedido = Pedido.objects.create(
            cliente=self.comprador.perfil, carrinho_origem=carrinho,
            status=status, forma_pagamento=forma,
            total_bruto=Decimal("3000.00"), total_liquido=Decimal("3000.00"),
            **envio,
        )
        for nome, quantidade in maquinas:
            ItemPedido.objects.create(
                pedido=pedido, nome_item=nome, tipo_item="brinquedo",
                preco_unitario=Decimal("100.00"), quantidade=quantidade,
                subtotal=Decimal("100.00") * quantidade,
            )
        if quando is not None:
            Pedido.objects.filter(pk=pedido.pk).update(criacao=quando)
            pedido.refresh_from_db()
        return pedido

    def orcamento(self, status=Orcamento.Status.APROVADO, maquinas=(("Cama elástica 3 m", 1),),
                  responsavel=None, **campos):
        cliente = Cliente.objects.create(nome_cliente="Buffet Alegria", documento="529.982.247-25")
        orcamento = Orcamento.objects.create(
            cliente=cliente, nome_cliente="Buffet Alegria", status=status,
            forma_pagamento="Pix", whatsapp_cliente="(11) 97777-6655",
            responsavel=responsavel, **campos,
        )
        for nome, quantidade in maquinas:
            ItemOrcamento.objects.create(
                orcamento=orcamento, descricao=nome, quantidade=quantidade,
                valor_unitario=Decimal("1000.00"),
            )
        return orcamento


# ======================================================================
# O FUNIL: PEDIDO PAGO É VENDA, UMA SÓ
# ======================================================================
class PedidoViraVendaTests(BaseFunil):

    def test_pedido_pago_vira_uma_venda_confirmada_com_o_valor_cobrado(self):
        pedido = self.pedido()
        acao, venda_id = pedido.acertar_venda()

        venda = Venda.objects.get(pk=venda_id)
        self.assertEqual(acao, "criada")
        self.assertEqual(venda.pedido_id, pedido.pk)
        self.assertTrue(venda.confirmado)
        # O que o Mercado Pago cobrou -- sem frete, que o site não cobra mais.
        self.assertEqual(venda.valor_pago, Decimal("3000.00"))
        self.assertEqual(venda.forma_pagamento, "cartao")
        self.assertEqual(venda.cpf, "52998224725")
        self.assertEqual(venda.origem, "site")
        pedido.refresh_from_db()
        self.assertEqual(pedido.producao_inicio, timezone.localdate())

    def test_o_pedido_antigo_com_frete_vende_o_total_cobrado(self):
        """O frete que o pedido de antes cobrou entra: foi o que o cliente pagou."""
        pedido = self.pedido(antigo_com_frete=True)
        _, venda_id = pedido.acertar_venda()
        self.assertEqual(Venda.objects.get(pk=venda_id).valor_pago, Decimal("3150.00"))

    def test_acertar_de_novo_e_andar_ate_finalizar_nao_duplica(self):
        pedido = self.pedido()
        _, primeira = pedido.acertar_venda()

        self.assertEqual(pedido.acertar_venda(), ("", primeira))
        for passo in ("em_preparacao", "finalizado"):
            with self.subTest(passo=passo):
                self.assertEqual(pedido.mudar_situacao(passo), ("", primeira))
        self.assertEqual(pedido.finalizar().pk, primeira)
        self.assertEqual(Venda.objects.count(), 1)

    def test_a_venda_que_ja_existia_vale(self):
        """O pedido finalizado pelo `finalizar()` antigo já tinha venda."""
        pedido = self.pedido(status="finalizado")
        antiga = Venda.objects.create(pedido=pedido, valor_pago=Decimal("3000.00"), confirmado=True)
        self.assertEqual(pedido.acertar_venda(), ("", antiga.pk))
        self.assertEqual(Venda.objects.count(), 1)

    def test_cancelar_o_pedido_pago_tira_a_venda(self):
        pedido = self.pedido()
        _, venda_id = pedido.acertar_venda()

        self.assertEqual(pedido.mudar_situacao("cancelado"), ("desfeita", venda_id))
        self.assertFalse(Venda.objects.exists())
        # Cancelado é o fim: não anda mais.
        with self.assertRaises(ValueError):
            Pedido.objects.get(pk=pedido.pk).mudar_situacao("pago")

    def test_aguardando_pagamento_nao_e_venda_nem_anda_pelo_painel(self):
        pedido = self.pedido(status="aguardando_pagamento")
        self.assertEqual(pedido.acertar_venda(), ("", None))
        with self.assertRaisesMessage(ValueError, "espera o pagamento"):
            pedido.mudar_situacao("em_preparacao")
        self.assertFalse(Venda.objects.exists())

    def test_a_retirada_nao_tem_saiu_para_entrega(self):
        self.assertEqual(
            self.pedido().proximas_situacoes(),
            ["em_preparacao", "finalizado", "cancelado"],
        )
        # O pedido antigo, com frete, ainda passa pelo "saiu para entrega".
        self.assertEqual(
            self.pedido(antigo_com_frete=True).proximas_situacoes(),
            ["em_preparacao", "saiu_entrega", "finalizado", "cancelado"],
        )

    def test_o_pagamento_aprovado_pelo_checkout_cria_a_venda_depois_do_commit(self):
        """O checkout não muda; o sinal do pedido acerta a venda no commit."""
        from core import checkout

        pedido = self.pedido(status="aguardando_pagamento")
        Pedido.objects.filter(pk=pedido.pk).update(mp_fingerprint="assinatura-x")
        pedido.refresh_from_db()
        pagamento = {
            "id": 9911, "status": "approved", "payment_type_id": "credit_card",
            # no cartão de crédito o cliente paga o total + 12% (LEIA-ME seção 98)
            "transaction_amount": float(checkout.valor_no_cartao(pedido.total_final)),
            "external_reference": checkout.referencia_do_pedido(pedido),
            "metadata": {"cart_fingerprint": "assinatura-x"},
            "installments": 1,
        }

        # O e-mail de confirmação vai numa thread, que o SQLite dos testes
        # não aguenta; ele não é o assunto aqui.
        with mock.patch("core.notificacoes.enviar_confirmacao_de_compra"), \
                self.captureOnCommitCallbacks(execute=True):
            checkout.confirmar_pagamento(pedido, pagamento)

        venda = Venda.objects.get(pedido=pedido)
        self.assertTrue(venda.confirmado)
        # a venda leva o que o cliente pagou de fato: o cartão, com os 12%
        self.assertEqual(venda.valor_pago, checkout.valor_no_cartao(pedido.total_final))
        self.assertEqual(venda.forma_pagamento, "cartao")

    def test_gravar_outro_campo_nao_pergunta_pela_venda(self):
        pedido = self.pedido()
        with self.captureOnCommitCallbacks() as pendentes:
            pedido.impresso = True
            pedido.save(update_fields=["impresso"])
        self.assertEqual(pendentes, [])
        with self.captureOnCommitCallbacks() as pendentes:
            pedido.status = "em_preparacao"
            pedido.save(update_fields=["status"])
        self.assertEqual(len(pendentes), 1)


class UmFunilSoTests(BaseFunil):

    def test_orcamento_no_100_continua_virando_uma_venda(self):
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(orcamento.total)
        orcamento.registrar_pagamento(orcamento.total)
        orcamento.refresh_from_db()
        self.assertEqual(Venda.objects.filter(pk=orcamento.venda_id).count(), 1)
        self.assertEqual(Venda.objects.count(), 1)

    def test_o_financeiro_conta_cada_venda_uma_vez(self):
        pedido = self.pedido()
        pedido.acertar_venda()
        pedido.mudar_situacao("finalizado")
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(orcamento.total)
        orcamento.registrar_pagamento(orcamento.total)

        serie = fin.montar_series(fin.janela_de_meses(2))
        self.assertEqual(serie[-1]["receita"], Decimal("3000.00") + Decimal("1000.00"))

        # O cancelamento do pedido sai da receita; o orçamento fica.
        Pedido.objects.get(pk=pedido.pk).mudar_situacao("cancelado")
        serie = fin.montar_series(fin.janela_de_meses(2))
        self.assertEqual(serie[-1]["receita"], Decimal("1000.00"))

    def test_as_duas_origens_na_mesma_tela_de_vendas(self):
        pedido = self.pedido()
        pedido.acertar_venda()
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(orcamento.total)
        self.client.force_login(equipe("caixa-funil", "financeiro"))

        resposta = self.client.get("/vendas/inner/", {"filtro": "todas"}, **INTERNO)
        html = resposta.content.decode()
        self.assertEqual(resposta.context["page_obj"].paginator.count, 2)
        self.assertIn('class="ls-venda-origem site"', html)
        self.assertIn('class="ls-venda-origem orcamento"', html)
        self.assertIn(f"Pedido #{pedido.pk}", html)
        self.assertIn(f"Orçamento nº {orcamento.numero_documento}", html)
        self.assertIn("Um funil só", html)


# ======================================================================
# A MIGRAÇÃO 0194: OS PEDIDOS PAGOS DE ANTES
# ======================================================================
class MigracaoDasVendasDoSiteTests(BaseFunil):

    def migracao(self):
        return import_module("core.migrations.0194_vendas_dos_pedidos_pagos")

    def rodar(self, funcao="preencher"):
        getattr(self.migracao(), funcao)(apps, SimpleNamespace(connection=connection))

    def test_preenche_com_a_data_do_pedido_sem_duplicar_e_desfaz_so_as_dela(self):
        agosto = timezone.make_aware(dt.datetime(2026, 8, 14, 15, 30))
        pago = self.pedido(status="pago", quando=agosto, antigo_com_frete=True)
        finalizado = self.pedido(status="finalizado", forma="pix", quando=agosto)
        self.pedido(status="aguardando_pagamento")
        self.pedido(status="cancelado")
        com_venda = self.pedido(status="finalizado")
        antiga = Venda.objects.create(pedido=com_venda, valor_pago=Decimal("10.00"), confirmado=True)

        self.rodar()
        self.rodar()  # de novo: nada muda

        self.assertEqual(Venda.objects.count(), 3)
        venda = Venda.objects.get(pedido=pago)
        self.assertEqual(venda.valor_pago, Decimal("3150.00"))
        self.assertTrue(venda.confirmado)
        self.assertEqual(venda.forma_pagamento, "cartao")
        self.assertEqual(venda.cpf, "52998224725")
        self.assertEqual(venda.criacao, agosto)
        self.assertEqual(Venda.objects.get(pedido=finalizado).forma_pagamento, "pix")
        pago.refresh_from_db()
        self.assertEqual(pago.producao_inicio, dt.date(2026, 8, 14))
        self.assertEqual(Venda.objects.get(pk=antiga.pk).valor_pago, Decimal("10.00"))

        # A receita cai em agosto, e não no mês da migração.
        serie = fin.montar_series(fin.janela_de_meses(6, referencia=dt.date(2026, 9, 20)))
        por_mes = {linha["mes"]: linha["receita"] for linha in serie}
        self.assertEqual(por_mes[dt.date(2026, 8, 1)], Decimal("3150.00") + Decimal("3000.00"))

        self.rodar("desfazer")
        self.assertEqual(list(Venda.objects.values_list("pk", flat=True)), [antiga.pk])
        pago.refresh_from_db()
        self.assertIsNone(pago.producao_inicio)

    def test_e_so_dados_e_o_esquema_e_a_0193(self):
        operacoes = self.migracao().Migration.operations
        self.assertEqual([type(op).__name__ for op in operacoes], ["RunPython"])
        self.assertTrue(operacoes[0].reversible)
        esquema = import_module("core.migrations.0193_prazo_de_producao_do_pedido").Migration
        self.assertEqual([type(op).__name__ for op in esquema.operations], ["AddField", "AddField"])
        orcamento = import_module("sistema_interno.migrations.0062_orcamento_prazo_de_producao").Migration
        self.assertEqual([type(op).__name__ for op in orcamento.operations], ["AddField", "AddField"])


# ======================================================================
# O TEMPO DE PRODUÇÃO
# ======================================================================
class PrazoDeProducaoTests(BaseFunil):

    def test_a_previsao_do_pedido_conta_do_pagamento_em_dias_uteis(self):
        pedido = self.pedido(quando=SEXTA)
        pedido.prazo_producao_dias = 5
        # Sem o dia gravado, conta do dia do pedido (a reserva é o começo
        # do pagamento): sexta 13/11 + 5 úteis, pulando o 20/11 = 23/11.
        self.assertEqual(pedido.previsao_producao, dt.date(2026, 11, 23))
        self.assertEqual(pedido.texto_producao, "Produção: 5 dias úteis — previsão 23/11")

    def test_o_pedido_nao_pago_tem_prazo_mas_nao_previsao(self):
        pedido = self.pedido(status="aguardando_pagamento")
        pedido.prazo_producao_dias = 5
        self.assertIsNone(pedido.previsao_producao)
        self.assertEqual(pedido.texto_producao, "Produção: 5 dias úteis")

    def test_a_previsao_do_orcamento_conta_da_aprovacao(self):
        orcamento = self.orcamento(
            prazo_producao_dias=3, respondido_em=SEXTA,
        )
        self.assertEqual(orcamento.previsao_producao, dt.date(2026, 11, 18))
        self.assertEqual(orcamento.prazo_para_o_cliente, "3 dias úteis — previsão 18/11/2026")

        rascunho = self.orcamento(status=Orcamento.Status.AGUARDANDO_RESPOSTA, prazo_producao_dias=3)
        self.assertIsNone(rascunho.previsao_producao)
        self.assertEqual(rascunho.prazo_para_o_cliente, "3 dias úteis após a aprovação")

    def test_a_aprovacao_registrada_no_painel_marca_o_comeco(self):
        vendedor = equipe("vendedor-funil", "vendas")
        orcamento = self.orcamento(status=Orcamento.Status.AGUARDANDO_RESPOSTA, responsavel=vendedor)
        self.client.force_login(vendedor)
        resposta = self.client.post(
            "/orcamentos/", {"action": "status", "id": orcamento.pk, "status": "aprovado"}, **AJAX,
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.producao_inicio, timezone.localdate())

    def test_a_venda_carrega_o_prazo_da_origem(self):
        pedido = self.pedido(quando=SEXTA)
        _, venda_id = pedido.acertar_venda()
        Pedido.objects.filter(pk=pedido.pk).update(
            prazo_producao_dias=5, producao_inicio=SEXTA.date(),
        )
        venda = Venda.objects.get(pk=venda_id)
        self.assertEqual(venda.prazo_producao_dias, 5)
        self.assertEqual(venda.previsao_producao, dt.date(2026, 11, 23))
        self.assertEqual(venda.texto_producao, "Produção: 5 dias úteis — previsão 23/11")

    def salvar(self, usuario, tipo, pk, prazo):
        self.client.force_login(usuario)
        return self.client.post(f"/producao/prazo/{tipo}/{pk}/", {"prazo": prazo}, **AJAX)

    def test_a_producao_informa_o_prazo_do_pedido_pelo_painel(self):
        producao = equipe("fabrica-funil", "producao")
        pedido = self.pedido(quando=SEXTA)

        resposta = self.salvar(producao, "pedido", pedido.pk, "5")

        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "sucesso")
        self.assertEqual(corpo["prazo"]["dias"], 5)
        self.assertEqual(corpo["prazo"]["previsao"], "23/11/2026")
        self.assertIn("previsão 23/11/2026", corpo["msg"])
        pedido.refresh_from_db()
        self.assertEqual(pedido.prazo_producao_dias, 5)
        self.assertEqual(pedido.producao_inicio, SEXTA.date())
        # Gravar o prazo não mexe na venda (não é mudança de situação).
        self.assertFalse(Venda.objects.exists())

        # Apagar o campo apaga o prazo.
        self.assertEqual(self.salvar(producao, "pedido", pedido.pk, "").json()["prazo"]["dias"], None)

    def test_o_campo_recusa_o_que_nao_e_prazo(self):
        producao = equipe("fabrica-funil-2", "producao")
        pedido = self.pedido()
        for valor in ("abc", "-1", "999"):
            with self.subTest(valor=valor):
                resposta = self.salvar(producao, "pedido", pedido.pk, valor)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json()["status"], "erro")
        cancelado = self.pedido(status="cancelado")
        self.assertEqual(self.salvar(producao, "pedido", cancelado.pk, "5").status_code, 400)

    def test_quem_informa_o_prazo_do_orcamento(self):
        dono = equipe("ambulante-dono", "ambulante")
        outro = equipe("ambulante-outro", "ambulante")
        orcamento = self.orcamento(responsavel=dono)

        self.assertEqual(self.salvar(equipe("fab-orc", "producao"), "orcamento", orcamento.pk, "10").status_code, 200)
        self.assertEqual(self.salvar(equipe("vend-orc", "vendas"), "orcamento", orcamento.pk, "11").status_code, 200)
        self.assertEqual(self.salvar(dono, "orcamento", orcamento.pk, "12").status_code, 200)
        self.assertEqual(self.salvar(outro, "orcamento", orcamento.pk, "13").status_code, 403)
        # Criação e site não é do funil: volta para a tela dela.
        self.assertEqual(self.salvar(equipe("criador", "criacao"), "orcamento", orcamento.pk, "14").status_code, 302)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.prazo_producao_dias, 12)
        # Aprovado sem dia gravado: o começo é marcado quando o prazo entra.
        self.assertEqual(orcamento.producao_inicio, timezone.localdate())

        recusado = self.orcamento(status=Orcamento.Status.RECUSADO)
        self.assertEqual(self.salvar(dono, "orcamento", recusado.pk, "5").status_code, 403)
        self.assertEqual(self.salvar(equipe("vend-rec", "vendas"), "orcamento", recusado.pk, "5").status_code, 400)

    def test_o_pedido_e_da_producao_do_financeiro_e_da_gestao(self):
        pedido = self.pedido()
        self.assertEqual(self.salvar(equipe("so-vendas", "vendas"), "pedido", pedido.pk, "5").status_code, 403)
        self.assertEqual(self.salvar(equipe("fin-ped", "financeiro"), "pedido", pedido.pk, "5").status_code, 200)

    def test_o_cliente_le_o_prazo_em_meus_pedidos(self):
        pedido = self.pedido(quando=SEXTA)
        Pedido.objects.filter(pk=pedido.pk).update(prazo_producao_dias=5)
        self.client.force_login(self.comprador)

        html = self.client.get("/meus-pedidos/").content.decode()

        self.assertIn('class="pd-producao"', html)
        self.assertIn("Produção: 5 dias úteis — previsão 23/11", html)

        # Finalizado, a máquina já chegou: a linha sai.
        Pedido.objects.filter(pk=pedido.pk).update(status="finalizado")
        self.assertNotIn('class="pd-producao"', self.client.get("/meus-pedidos/").content.decode())

    def test_a_proposta_do_cliente_mostra_o_prazo(self):
        orcamento = self.orcamento(
            status=Orcamento.Status.AGUARDANDO_RESPOSTA, prazo_producao_dias=15,
        )
        html = self.client.get(f"/orcamento/{orcamento.token}/").content.decode()
        self.assertIn("comercial-grid entra com-prazo", html)
        self.assertIn("Prazo de produção", html)
        self.assertIn("15 dias úteis após a aprovação", html)

        sem_prazo = self.orcamento(status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        html = self.client.get(f"/orcamento/{sem_prazo.token}/").content.decode()
        self.assertNotIn("Prazo de produção", html)


# ======================================================================
# AS ETIQUETAS POR MÁQUINA, EM FOLHAS A4
# ======================================================================
class ContaDasFolhasTests(TestCase):

    def test_3_maquinas_x_5_copias_com_4_por_folha_dao_4_folhas(self):
        maquinas = [etq.Maquina(pk, f"Máquina {pk}", 1) for pk in (1, 2, 3)]
        copias = {1: 5, 2: 5, 3: 5}
        total = etq.contar(maquinas, copias)

        self.assertEqual(total, 15)
        self.assertEqual(etq.folhas_necessarias(total, etq.POR_FOLHA["a6"]), 4)
        self.assertEqual(etq.folhas_necessarias(total, etq.POR_FOLHA["a5"]), 8)
        self.assertEqual(
            [len(folha) for folha in etq.em_folhas(list(range(total)), 4)], [4, 4, 4, 3],
        )

    def test_a_conta_em_qualquer_tamanho(self):
        for total, por_folha, folhas in ((0, 4, 0), (1, 4, 1), (4, 4, 1), (5, 4, 2), (8, 2, 4), (9, 2, 5)):
            with self.subTest(total=total, por_folha=por_folha):
                self.assertEqual(etq.folhas_necessarias(total, por_folha), folhas)

    def test_as_copias_que_vem_da_tela(self):
        maquinas = [etq.Maquina(7, "Air Game", 2), etq.Maquina(8, "Basquete", 1)]
        self.assertEqual(etq.ler_copias([], maquinas), {7: 1, 8: 1})
        self.assertEqual(etq.ler_copias(["7:3", "8:0"], maquinas), {7: 3, 8: 0})
        # Máquina de outra origem, lixo e exagero.
        self.assertEqual(etq.ler_copias(["99:4", "x:1", "8:500"], maquinas), {8: etq.COPIAS_MAXIMAS})
        # Quantidade x cópias.
        self.assertEqual(etq.contar(maquinas, {7: 3, 8: 1}), 7)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class EtiquetasNaImpressaoTests(BaseFunil):

    def setUp(self):
        super().setUp()
        self.producao = equipe("expedicao-funil", "producao")
        self.client.force_login(self.producao)

    def imprimir(self, tipo, pk, **parametros):
        return self.client.get(f"/etiquetas/maquinas/{tipo}/{pk}/imprimir/", parametros, **INTERNO)

    def test_3_maquinas_x_5_copias_saem_em_4_folhas_a4(self):
        pedido = self.pedido(maquinas=(("Air Game Kids", 1), ("Basquete Street", 1), ("Pebolim", 1)))
        itens = list(pedido.itens.order_by("pk"))

        resposta = self.imprimir(
            "pedido", pedido.pk, tamanho="a6", c=[f"{item.pk}:5" for item in itens],
        )

        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertEqual(resposta.context["total"], 15)
        self.assertEqual(resposta.context["total_folhas"], 4)
        self.assertEqual(len(re.findall(r'<section class="ls-a4-folha ls-folha-etiquetas a6"', html)), 4)
        self.assertEqual(html.count('<article class="ls-etiqueta">'), 15)
        self.assertEqual([len(folha) for folha in resposta.context["folhas"]], [4, 4, 4, 3])
        self.assertIn("Volume</small><strong>5/5", html)
        self.assertIn("Basquete Street", html)
        self.assertIn(f"Pedido #{pedido.pk}", html)
        self.assertIn("Marina Souza", html)          # o destinatário, como na etiqueta de sempre
        self.assertIn("(11) 98888-7777", html)
        # Retirada na fábrica: o aviso no lugar do endereço (o frete é do cliente).
        self.assertIn("Retirada na fábrica · frete por conta do cliente", html)
        self.assertIn("Frágil", html)
        self.assertIn("15 etiquetas", html)
        self.assertIn("4 folhas A4", html)

        meia = self.imprimir("pedido", pedido.pk, tamanho="a5", c=[f"{item.pk}:5" for item in itens])
        self.assertEqual(meia.context["total_folhas"], 8)

    def test_unidades_vezes_copias_e_a_data_de_producao(self):
        pedido = self.pedido(maquinas=(("Air Game Kids", 2),), quando=SEXTA)
        Pedido.objects.filter(pk=pedido.pk).update(prazo_producao_dias=5, producao_inicio=SEXTA.date())
        item = pedido.itens.get()

        resposta = self.imprimir("pedido", pedido.pk, c=f"{item.pk}:3")

        html = resposta.content.decode()
        self.assertEqual(resposta.context["total"], 6)
        self.assertEqual(resposta.context["total_folhas"], 2)   # A6 é o padrão: 4 por folha
        self.assertIn("Unidade 2 de 2", html)
        self.assertIn("3/3", html)
        self.assertIn("Pronto em</small>23/11/2026", html)

    def test_sem_copias_escolhidas_sai_uma_por_unidade_e_a_data_da_impressao(self):
        pedido = self.pedido(maquinas=(("Air Game Kids", 2), ("Pebolim", 1)))
        resposta = self.imprimir("pedido", pedido.pk)
        self.assertEqual(resposta.context["total"], 3)
        self.assertIn("Emitida em</small>" + timezone.localdate().strftime("%d/%m/%Y"),
                      resposta.content.decode())

    def test_o_que_nao_imprime_diz_por_que(self):
        pedido = self.pedido()
        item = pedido.itens.get()
        zero = self.imprimir("pedido", pedido.pk, c=f"{item.pk}:0")
        self.assertEqual(zero.status_code, 400)
        self.assertIn("Nenhuma etiqueta", zero.content.decode())

        grande = self.pedido(maquinas=(("Bola", 50),))
        demais = self.imprimir("pedido", grande.pk, c=f"{grande.itens.get().pk}:20")
        self.assertEqual(demais.status_code, 400)
        self.assertIn("no máximo", demais.content.decode())

        aguardando = self.pedido(status="aguardando_pagamento")
        self.assertEqual(self.imprimir("pedido", aguardando.pk).status_code, 400)

        rascunho = self.orcamento(status=Orcamento.Status.RASCUNHO)
        resposta = self.imprimir("orcamento", rascunho.pk)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("proposta aprovada", resposta.content.decode())

    def test_do_orcamento_aprovado_e_da_venda(self):
        orcamento = self.orcamento(maquinas=(("Cama elástica 3 m", 1), ("Tobogã", 2)))
        resposta = self.imprimir("orcamento", orcamento.pk)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["total"], 3)
        self.assertIn(f"Orçamento nº {orcamento.numero_documento}", resposta.content.decode())

        orcamento.registrar_pagamento(orcamento.total)
        orcamento.refresh_from_db()
        self.client.force_login(equipe("caixa-etiq", "financeiro"))
        da_venda = self.imprimir("venda", orcamento.venda_id)
        self.assertEqual(da_venda.status_code, 200)
        self.assertIn(f"Venda #{orcamento.venda_id}", da_venda.content.decode())

    def test_a_folha_de_copias_le_a_ficha(self):
        pedido = self.pedido(maquinas=(("Air Game Kids", 2), ("Pebolim", 1)))
        resposta = self.client.get(f"/etiquetas/maquinas/pedido/{pedido.pk}/", **AJAX)
        self.assertEqual(resposta.status_code, 200)
        ficha = resposta.json()
        self.assertTrue(ficha["pronta"])
        self.assertEqual([m["quantidade"] for m in ficha["maquinas"]], [2, 1])
        self.assertEqual({t["valor"]: t["por_folha"] for t in ficha["tamanhos"]}, {"a6": 4, "a5": 2})
        self.assertEqual(ficha["imprimir"], f"/etiquetas/maquinas/pedido/{pedido.pk}/imprimir/")
        self.assertTrue(ficha["prazo"]["url"].endswith(f"/producao/prazo/pedido/{pedido.pk}/"))

    def test_quem_imprime(self):
        pedido = self.pedido()
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(orcamento.total)
        orcamento.refresh_from_db()

        # A Produção imprime do pedido e do orçamento, mas a venda é do
        # Financeiro e da Gestão.
        self.assertEqual(self.imprimir("pedido", pedido.pk).status_code, 200)
        self.assertEqual(self.imprimir("orcamento", orcamento.pk).status_code, 200)
        self.assertEqual(
            self.client.get(f"/etiquetas/maquinas/venda/{orcamento.venda_id}/", **AJAX).status_code, 403,
        )
        # Vendas não cuida do pedido do site.
        self.client.force_login(equipe("vend-etiq", "vendas"))
        self.assertEqual(self.client.get(f"/etiquetas/maquinas/pedido/{pedido.pk}/", **AJAX).status_code, 403)
        self.assertEqual(self.imprimir("orcamento", orcamento.pk).status_code, 200)
        # Criação e site: fora do funil.
        self.client.force_login(equipe("criador-etiq", "criacao"))
        self.assertEqual(self.imprimir("pedido", pedido.pk).status_code, 302)
        # Tipo que não existe.
        self.client.force_login(self.producao)
        self.assertEqual(self.imprimir("cliente", pedido.pk).status_code, 404)

    def test_a_folha_a4_e_a4_e_quebra_a_pagina(self):
        """O papel: A4 sem margem de impressora, 8 mm por dentro, uma folha por página."""
        folha = (RAIZ / "static" / "interno" / "etiquetas-a4.css").read_text(encoding="utf-8")
        impressao = folha[folha.index("@media print"):]
        self.assertIn("@page{size:A4;margin:0}", impressao)
        self.assertIn("break-after:page", impressao)
        self.assertIn("page-break-after:always", impressao)
        self.assertIn(".ls-a4 .ls-a4-folha:last-child{break-after:auto", impressao)
        self.assertIn("width:210mm;height:297mm;padding:8mm", folha)
        self.assertIn(".ls-a4 .ls-a4-folha.a6{grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}", folha)
        self.assertIn(".ls-a4 .ls-a4-folha.a5{grid-template-columns:1fr;grid-template-rows:1fr 1fr}", folha)
        # Nenhuma letra do papel abaixo do que o laser imprime.
        for tamanho in re.findall(r"font-size:\.(\d+)rem", folha):
            with self.subTest(tamanho=tamanho):
                self.assertGreaterEqual(int(tamanho.ljust(2, "0")), 62)


# ======================================================================
# O ANDAMENTO DO PEDIDO E AS TELAS
# ======================================================================
@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AndamentoETelasTests(BaseFunil):

    def andar(self, usuario, pedido, status):
        self.client.force_login(usuario)
        return self.client.post(f"/pedidos/{pedido.pk}/andamento/", {"status": status}, **AJAX)

    def test_o_financeiro_anda_com_o_pedido_e_a_venda_acompanha(self):
        financeiro = equipe("fin-andamento", "financeiro")
        pedido = self.pedido()

        resposta = self.andar(financeiro, pedido, "em_preparacao")
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo["situacao"], "em_preparacao")
        self.assertEqual(corpo["venda_acao"], "criada")
        self.assertIn("Registrado como venda", corpo["msg"])
        venda_id = corpo["venda"]

        corpo = self.andar(financeiro, pedido, "finalizado").json()
        self.assertEqual((corpo["situacao"], corpo["venda"], corpo["venda_acao"]), ("finalizado", venda_id, ""))

        corpo = self.andar(financeiro, pedido, "cancelado").json()
        self.assertEqual(corpo["venda_acao"], "desfeita")
        self.assertIn("saiu da receita", corpo["msg"])
        self.assertFalse(Venda.objects.exists())
        self.assertEqual(self.andar(financeiro, pedido, "pago").status_code, 400)

    def test_quem_nao_e_do_financeiro_nao_anda(self):
        pedido = self.pedido()
        self.assertEqual(self.andar(equipe("fab-andar", "producao"), pedido, "finalizado").status_code, 302)
        self.assertEqual(Pedido.objects.get(pk=pedido.pk).status, "pago")
        self.assertEqual(self.andar(equipe("ges-andar", "gestao"), pedido, "lixo").status_code, 400)

    def test_a_tela_de_pedidos_tem_o_andamento_o_prazo_e_as_etiquetas(self):
        pedido = self.pedido()
        pedido.acertar_venda()
        aguardando = self.pedido(status="aguardando_pagamento")
        self.client.force_login(equipe("fin-tela", "financeiro"))

        html = self.client.get("/pedidos/inner/", **INTERNO).content.decode()

        self.assertIn(f'data-andamento-url="/pedidos/{pedido.pk}/andamento/"', html)
        self.assertNotIn(f'data-andamento-url="/pedidos/{aguardando.pk}/andamento/"', html)
        self.assertIn(f'data-prazo-url="/producao/prazo/pedido/{pedido.pk}/"', html)
        self.assertIn(f'data-etiquetas-url="/etiquetas/maquinas/pedido/{pedido.pk}/"', html)
        self.assertNotIn(f'data-etiquetas-url="/etiquetas/maquinas/pedido/{aguardando.pk}/"', html)
        self.assertIn(f"Venda #{pedido.venda.pk}", html)
        opcoes = re.search(
            rf'data-andamento-url="/pedidos/{pedido.pk}/andamento/"\s+data-andamento-opcoes="([^"]+)"', html,
        ).group(1).replace("&quot;", '"')
        # Retirada na fábrica: sem "saiu para entrega".
        self.assertEqual(
            [opcao["valor"] for opcao in json.loads(opcoes)],
            ["em_preparacao", "finalizado", "cancelado"],
        )

    def test_a_janela_do_orcamento_leva_o_prazo_e_as_etiquetas(self):
        from .views_gestao import OrcamentosInnerView

        aprovado = self.orcamento(prazo_producao_dias=7)
        dados = OrcamentosInnerView.serializar(aprovado)["producao"]
        self.assertEqual(dados["dias"], 7)
        self.assertEqual(dados["etiquetas"], f"/etiquetas/maquinas/orcamento/{aprovado.pk}/")
        aguardando = self.orcamento(status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.assertEqual(OrcamentosInnerView.serializar(aguardando)["producao"]["etiquetas"], "")
        recusado = self.orcamento(status=Orcamento.Status.RECUSADO)
        self.assertIsNone(OrcamentosInnerView.serializar(recusado)["producao"])

        self.client.force_login(equipe("vend-janela", "vendas"))
        html = self.client.get("/orcamentos/", **INTERNO).content.decode()
        self.assertIn('id="orcamentoProducao"', html)
        self.assertIn(f'data-etiquetas-url="/etiquetas/maquinas/orcamento/{aprovado.pk}/"', html)

    def test_a_fila_da_producao_na_tela_de_etiquetas(self):
        pedido = self.pedido()
        orcamento = self.orcamento()
        self.pedido(status="finalizado")

        self.client.force_login(equipe("fab-fila", "producao"))
        resposta = self.client.get("/etiquetas/", **INTERNO)
        fila = resposta.context["fila_producao"]
        self.assertEqual(
            sorted((linha["tipo"], linha["objeto"].pk) for linha in fila),
            [("orcamento", orcamento.pk), ("pedido", pedido.pk)],
        )
        html = resposta.content.decode()
        self.assertIn("Na produção agora", html)
        self.assertIn(f'data-prazo-url="/producao/prazo/orcamento/{orcamento.pk}/"', html)
        self.assertNotIn("R$", html[html.index("Na produção agora"):html.index("filaProducaoVazia")])

        # Quem não é do funil não vê a fila.
        self.client.force_login(equipe("criador-fila", "criacao", "producao"))
        self.assertTrue(self.client.get("/etiquetas/", **INTERNO).context["fila_producao"])
        self.client.force_login(equipe("so-criacao", "criacao"))
        self.assertEqual(self.client.get("/etiquetas/", **INTERNO).context["fila_producao"], [])

    def test_o_script_do_funil_usa_as_folhas_de_aplicativo(self):
        script = (RAIZ / "static" / "interno" / "producao-etiquetas.js").read_text(encoding="utf-8")
        self.assertIn("LSAviso.confirmar", script)
        self.assertIn("ls-recado-folha", script)
        self.assertIn("showModal", script)
        self.assertNotRegex(script, r"(?<![\w.])(alert|confirm)\(")
        self.assertNotIn("window.confirm", script)
        base = (RAIZ / "templates" / "base_inner.html").read_text(encoding="utf-8")
        self.assertIn("interno/producao-etiquetas.js", base)
