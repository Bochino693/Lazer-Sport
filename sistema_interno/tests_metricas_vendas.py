"""As métricas de venda unificadas (LEIA-ME-V10, seção 147).

O dono: "tudo deve ir para a mesma métrica" -- o orçamento, a O.S. e o
pedido do site, sem contar a mesma venda duas vezes.

O que estes testes protegem:

  * os três canais: o pedido pago do site, o orçamento pago 100% e a O.S.
    paga ("Serviços"), cada um com quantidade, valor e ticket, e o total;
  * SEM CONTAGEM DUPLA: a O.S. do orçamento que já virou venda fica de
    fora; a O.S. de orçamento que NÃO virou venda conta como serviço;
  * o que não é venda não entra: pedido cancelado ou sem pagamento, O.S.
    com pagamento parcial, cancelada ou trocada por outra versão, orçamento
    com pagamento parcial;
  * o período corta pela data do pagamento;
  * a taxa de assinatura: no site só o pedido com máquina pede contrato; o
    tempo para assinar é a mediana;
  * o tempo entre as fases é a mediana de quem passou pelas duas;
  * a tela é só do Financeiro e da Gestão, abre com o período certo no
    chip, não usa <select> e não consulta o banco uma vez por venda.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.models import Pedido, Venda

from . import documento_assinatura as svc_doc
from . import documento_pedido as dp
from . import documento_servico
from . import metricas_vendas as mv
from .models import DocumentoAssinatura, ItemOrcamento, ItemOrdemServico, Orcamento, OrdemServico
from .tests_documento_assinatura import CPF_DO_CLIENTE
from .tests_documento_pedido import BasePedido
from .tests_lista_montagem import INTERNO, equipe

TELA = "/vendas/metricas/inner/"


class BaseMetricas(BasePedido):
    """Parte de dois pedidos pagos do site (um com máquina, um só de peças) e um em aberto."""

    def setUp(self):
        super().setUp()
        # a venda nasce no pagamento; o valor é o que o teste diz
        for pedido, valor in ((self.pedido_maquina, "5000.00"), (self.pedido_peca, "100.00")):
            Venda.objects.update_or_create(pedido=pedido, defaults={"valor_pago": Decimal(valor), "confirmado": True})

    def orcamento_pago(self, valor="8000.00", pagar=None):
        orcamento = Orcamento.objects.create(
            nome_cliente="Buffet Inventado", status=Orcamento.Status.APROVADO,
            enviado_em=timezone.now() - timedelta(days=6), respondido_em=timezone.now() - timedelta(days=4),
            responsavel=self.dono,
        )
        ItemOrcamento.objects.create(orcamento=orcamento, descricao="Air Game Kids", quantidade=1, valor_unitario=Decimal(valor))
        orcamento.registrar_pagamento(Decimal(pagar if pagar is not None else valor))
        orcamento.refresh_from_db()
        return orcamento

    def ordem_paga(self, valor="300.00", pagar=None, **campos):
        padrao = {
            "nome_cliente": "Parque Inventado", "equipamento": "Cama elástica",
            "status": OrdemServico.Status.AGENDADA, "agendada_para": timezone.now() + timedelta(days=3),
            "responsavel": self.dono,
        }
        padrao.update(campos)
        ordem = OrdemServico.objects.create(**padrao)
        ItemOrdemServico.objects.create(
            ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO, descricao="Conserto", quantidade=1,
            valor_unitario=Decimal(valor),
        )
        ordem.registrar_pagamento(Decimal(pagar if pagar is not None else valor))
        return ordem

    def canal(self, chave, **kw):
        return {c.chave: c for c in mv.apurar("tudo", **kw)["canais"]}[chave]

    @staticmethod
    def assinar(documento, quando=None):
        svc_doc.assinar(documento, nome="Cliente Inventado", cpf_cnpj="52998224725", png=b"\x89PNG", ip="127.0.0.1", navegador="t")
        if quando is not None:
            documento.assinado_em = quando
        documento.save()
        return documento


class CanaisTests(BaseMetricas):
    def test_os_tres_canais_e_o_total(self):
        self.orcamento_pago("8000.00")
        self.ordem_paga("300.00")
        self.ordem_paga("500.00")
        dados = mv.apurar("tudo")
        numeros = {c.chave: (c.quantidade, c.valor, c.ticket) for c in dados["canais"]}
        self.assertEqual(numeros["site"], (2, Decimal("5100.00"), Decimal("2550.00")))
        self.assertEqual(numeros["orcamento"], (1, Decimal("8000.00"), Decimal("8000.00")))
        self.assertEqual(numeros["servicos"], (2, Decimal("800.00"), Decimal("400.00")))
        self.assertEqual((dados["quantidade"], dados["valor"], dados["ticket"]), (5, Decimal("13900.00"), Decimal("2780.00")))
        self.assertEqual([c.parte for c in dados["canais"]], [37, 58, 6])

    def test_a_ordem_do_orcamento_que_ja_virou_venda_nao_conta_de_novo(self):
        orcamento = self.orcamento_pago("8000.00")
        self.ordem_paga("250.00", orcamento=orcamento)        # a instalação da venda do orçamento
        self.assertEqual(self.canal("servicos").quantidade, 0)
        self.assertEqual(self.canal("orcamento").quantidade, 1)
        self.assertEqual(mv.apurar("tudo")["valor"], Decimal("13100.00"))

    def test_a_ordem_de_orcamento_que_nao_virou_venda_conta_como_servico(self):
        orcamento = self.orcamento_pago("8000.00", pagar="1000.00")   # parcial: não é venda
        self.assertIsNone(orcamento.venda_id)
        self.ordem_paga("250.00", orcamento=orcamento)
        self.assertEqual(self.canal("orcamento").quantidade, 0)
        self.assertEqual((self.canal("servicos").quantidade, self.canal("servicos").valor), (1, Decimal("250.00")))

    def test_o_que_nao_e_venda_nao_entra(self):
        self.ordem_paga("300.00", pagar="100.00")                                   # parcial
        self.ordem_paga("300.00", status=OrdemServico.Status.CANCELADA)
        self.ordem_paga("300.00", status=OrdemServico.Status.SUBSTITUIDA)
        self.assertEqual(self.canal("servicos").quantidade, 0)
        # o pedido em aberto não tem venda; o cancelado sai da conta
        self.assertFalse(Venda.objects.filter(pedido=self.pedido_aberto).exists())
        Pedido.objects.filter(pk=self.pedido_peca.pk).update(status="cancelado")
        self.assertEqual((self.canal("site").quantidade, self.canal("site").valor), (1, Decimal("5000.00")))

    def test_venda_sem_origem_fica_de_fora_e_e_avisada(self):
        Venda.objects.create(valor_pago=Decimal("999.00"), confirmado=True)
        dados = mv.apurar("tudo")
        self.assertEqual(dados["sem_origem"], 1)
        self.assertEqual(dados["valor"], Decimal("5100.00"))

    def test_o_periodo_corta_pela_data_do_pagamento(self):
        antiga = self.ordem_paga("300.00")
        OrdemServico.objects.filter(pk=antiga.pk).update(pago_em=timezone.now() - timedelta(days=60))
        self.ordem_paga("500.00")
        Venda.objects.filter(pedido=self.pedido_peca).update(criacao=timezone.now() - timedelta(days=200))

        def numeros(periodo):
            return {c.chave: c.quantidade for c in mv.apurar(periodo)["canais"]}

        self.assertEqual(numeros("30"), {"site": 1, "orcamento": 0, "servicos": 1})
        self.assertEqual(numeros("90"), {"site": 1, "orcamento": 0, "servicos": 2})
        self.assertEqual(numeros("365"), {"site": 2, "orcamento": 0, "servicos": 2})
        self.assertEqual(numeros("tudo"), {"site": 2, "orcamento": 0, "servicos": 2})
        self.assertEqual(mv.ler_periodo("qualquer"), mv.PERIODO_PADRAO)


class AssinaturaTests(BaseMetricas):
    def test_no_site_so_o_pedido_com_maquina_pede_contrato(self):
        site = self.canal("site")
        self.assertEqual((site.pedem_assinatura, site.assinadas, site.taxa_assinatura), (1, 0, 0))
        documento = dp.gerar_do_pedido(self.pedido_maquina, CPF_DO_CLIENTE, self.dono)
        self.assinar(documento, quando=self.pedido_maquina.pago_em + timedelta(hours=5))
        site = self.canal("site")
        self.assertEqual((site.pedem_assinatura, site.assinadas, site.taxa_assinatura), (1, 1, 100))
        self.assertEqual(site.tempo_para_assinar_texto, "5 h")

    def test_orcamento_e_servico_e_a_taxa_geral(self):
        com = self.orcamento_pago("8000.00")
        self.orcamento_pago("2000.00")
        self.assinar(svc_doc.gerar(com, self.dono), quando=com.respondido_em + timedelta(days=3))
        ordem = self.ordem_paga("300.00")
        documento = documento_servico.gerar_da_ordem(ordem, self.dono)
        self.assinar(documento, quando=documento.criacao + timedelta(minutes=20))
        dados = mv.apurar("tudo")
        canais = {c.chave: c for c in dados["canais"]}
        self.assertEqual((canais["orcamento"].pedem_assinatura, canais["orcamento"].assinadas, canais["orcamento"].taxa_assinatura), (2, 1, 50))
        self.assertEqual(canais["orcamento"].tempo_para_assinar_texto, "3 dias")
        self.assertEqual((canais["servicos"].assinadas, canais["servicos"].taxa_assinatura), (1, 100))
        self.assertEqual(canais["servicos"].tempo_para_assinar_texto, "20 min")
        # 1 do site + 2 de orçamento + 1 serviço pedem; 2 assinadas
        self.assertEqual((dados["pedem_assinatura"], dados["assinadas"], dados["taxa_assinatura"]), (4, 2, 50))

    def test_documento_que_so_espera_nao_conta_como_assinado(self):
        svc_doc.gerar(self.orcamento_pago(), self.dono)
        orcamento = self.canal("orcamento")
        self.assertEqual((orcamento.assinadas, orcamento.taxa_assinatura, orcamento.tempo_para_assinar_texto), (0, 0, "—"))

    def test_sem_venda_a_taxa_nao_e_zero_e_sim_vazia(self):
        self.assertIsNone(self.canal("servicos").taxa_assinatura)


class FasesTests(BaseMetricas):
    def test_a_mediana_de_quem_passou_pelas_duas_fases(self):
        agora = timezone.now()
        for dias in (1, 2, 30):                         # a parada (30 dias) não puxa o número
            ordem = self.ordem_paga("100.00")
            OrdemServico.objects.filter(pk=ordem.pk).update(criacao=agora - timedelta(days=dias), pago_em=agora)
        self.ordem_paga("100.00", status=OrdemServico.Status.CONCLUIDA, concluida_em=agora + timedelta(hours=3))
        fases = {f.nome: f for f in mv.apurar("tudo")["fases"]}
        pagamento = fases["Da abertura da O.S. ao pagamento"]
        self.assertEqual(pagamento.base, 4)
        self.assertIn(pagamento.texto, ("36 h", "1 dias", "2 dias"))
        self.assertEqual(fases["Da abertura da O.S. à conclusão"].base, 1)
        # orçamento: enviado há 6 dias, aprovado há 4 -> 2 dias
        self.orcamento_pago()
        fases = {f.nome: f for f in mv.apurar("tudo")["fases"]}
        self.assertEqual(fases["Da proposta enviada à aprovação"].texto, "2 dias")
        self.assertEqual(fases["Do pagamento à entrega"].texto, "—")

    def test_o_texto_do_tempo(self):
        self.assertEqual(mv.texto_do_tempo(None), "—")
        self.assertEqual(mv.texto_do_tempo(timedelta(seconds=20)), "1 min")
        self.assertEqual(mv.texto_do_tempo(timedelta(minutes=45)), "45 min")
        self.assertEqual(mv.texto_do_tempo(timedelta(hours=30)), "30 h")
        self.assertEqual(mv.texto_do_tempo(timedelta(days=9)), "9 dias")


class TelaTests(BaseMetricas):
    def painel(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente

    def test_so_o_financeiro_e_a_gestao_abrem(self):
        for nome, funcao, pode in (("fin", "financeiro", True), ("ges", "gestao", True), ("ven", "vendas", False), ("pro", "producao", False), ("amb", "ambulante", False)):
            resposta = self.painel(equipe(f"metricas-{nome}", funcao)).get(TELA, **INTERNO)
            self.assertEqual(resposta.status_code == 200, pode, f"{funcao}: {resposta.status_code}")
        self.assertNotEqual(Client().get(TELA, **INTERNO).status_code, 200)

    def test_a_tela_mostra_os_canais_o_periodo_e_o_caminho_de_volta(self):
        self.orcamento_pago("8000.00")
        self.ordem_paga("300.00")
        cliente = self.painel(equipe("metricas-tela", "financeiro"))
        resposta = cliente.get(TELA, **INTERNO)
        self.assertEqual(resposta.context["periodo"], "90")
        for canal in ("site", "orcamento", "servicos"):
            self.assertContains(resposta, f'data-mv-canal="{canal}"')
        self.assertContains(resposta, "R$ 13.400,00")
        self.assertContains(resposta, 'data-mv-periodo="90" aria-current="true"')
        self.assertContains(resposta, 'id="voltarParaVendas"')
        self.assertNotContains(resposta, "<select")
        self.assertContains(cliente.get(TELA + "?periodo=tudo", **INTERNO), 'data-mv-periodo="tudo" aria-current="true"')
        # a tela de Vendas leva às métricas
        self.assertContains(cliente.get("/vendas/inner/", **INTERNO), 'id="verMetricasDeVendas"')

    def test_as_consultas_nao_crescem_com_as_vendas(self):
        cliente = self.painel(equipe("metricas-conta", "financeiro"))

        def contar():
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(cliente.get(TELA + "?periodo=tudo", **INTERNO).status_code, 200)
            return len(capturadas)

        self.orcamento_pago()
        self.ordem_paga()
        contar()
        poucas = contar()
        for _ in range(3):
            self.assinar(svc_doc.gerar(self.orcamento_pago(), self.dono))
            ordem = self.ordem_paga()
            self.assinar(documento_servico.gerar_da_ordem(ordem, self.dono))
        from .tests_lista_montagem import QUARTA, no_dia, no_relogio

        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            for _ in range(3):
                pedido = self.pedido()
                Venda.objects.update_or_create(pedido=pedido, defaults={"valor_pago": Decimal("10.00"), "confirmado": True})
        contar()            # a regra da produção (guardada em cache) é relida depois de um pedido novo
        muitas = contar()
        self.assertEqual(muitas, poucas, "as métricas consultam o banco uma vez por venda")

    def test_o_css_da_tela_so_usa_as_variaveis_do_tema(self):
        import re
        from pathlib import Path

        from django.conf import settings

        css = (Path(settings.BASE_DIR) / "sistema_interno/static/interno/metricas_vendas.css").read_text()
        self.assertFalse(re.findall(r"#[0-9a-fA-F]{3,8}\b", css))
