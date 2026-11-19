"""A RÉGUA DO PEDIDO PARA A EQUIPE (LEIA-ME-V10, seção 117).

"Revise todo o sistema e deixe fluido, com as etapas bem definidas e claras
para seguir." Uma régua só, com as seis fases que o cliente vê, e o próximo
passo na voz da equipe:

  * a fase de agora é a primeira que falta, e o próximo passo diz o que
    fazer e com quem está a vez (Comercial, Financeiro, Produção);
  * o botão só aparece para quem pode (o Financeiro registra o pagamento,
    o Comercial passa o contrato);
  * a janela do orçamento pede o HTML pronto e não o recebe de novo quando
    nada mudou; a tela do contrato já nasce com a régua e a troca quando o
    cliente assina.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from . import documento_assinatura as svc
from .etapas_do_pedido import etapas
from .models import ItemOrcamento, Orcamento
from .permissoes import atribuir_funcoes
from .tests_documento_assinatura import BaseDocumento, preencher_dados_do_contrato

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def _usuario(nome, *funcoes):
    user = User.objects.create_user(username=nome, password="x")
    atribuir_funcoes(user, funcoes)
    return user


class _BaseEtapas(TestCase):
    def setUp(self):
        cache.clear()
        preencher_dados_do_contrato()
        self.vendas = _usuario("et-vendas", "vendas")
        self.financeiro = _usuario("et-fin", "financeiro")
        self.producao = _usuario("et-prod", "producao")

    def orcamento(self, **campos):
        padrao = {
            "nome_cliente": "Buffet Régua",
            "status": Orcamento.Status.APROVADO,
            "forma_pagamento": "Pix",
            "responsavel": self.vendas,
        }
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica 3 m", quantidade=2, valor_unitario=Decimal("1500.00"),
        )
        return orcamento

    @staticmethod
    def estados(regua):
        return {etapa.chave: etapa.estado for etapa in regua.lista}


class EtapasDoPedidoTests(_BaseEtapas):

    def test_as_seis_fases_sao_as_do_cliente(self):
        regua = etapas(self.orcamento(status=Orcamento.Status.RASCUNHO), self.vendas)
        self.assertEqual(
            [etapa.nome for etapa in regua.lista],
            ["Proposta", "Aprovação", "Contrato assinado", "Pagamento", "Produção", "Entregue"],
        )
        self.assertEqual([etapa.numero for etapa in regua.lista], [1, 2, 3, 4, 5, 6])

    def test_rascunho_a_vez_e_do_comercial_terminar_a_proposta(self):
        regua = etapas(self.orcamento(status=Orcamento.Status.RASCUNHO), self.vendas)
        self.assertEqual(self.estados(regua)["proposta"], "atual")
        self.assertEqual(regua.lista[0].nota, "Em montagem")
        self.assertEqual(regua.proximo.quem, "Comercial")
        self.assertIn("envie ao cliente", regua.proximo.texto)

    def test_esperando_o_cliente_aprovar(self):
        regua = etapas(self.orcamento(status=Orcamento.Status.AGUARDANDO_RESPOSTA), self.vendas)
        self.assertEqual(self.estados(regua)["proposta"], "feita")
        self.assertEqual(self.estados(regua)["aprovacao"], "atual")
        self.assertEqual(regua.proximo.texto, "Esperando o cliente aprovar.")

    def test_ajustes_pedidos_mostram_o_pedido_do_cliente(self):
        regua = etapas(self.orcamento(
            status=Orcamento.Status.EM_NEGOCIACAO, motivo_negociacao="Trocar a cor para azul",
        ), self.vendas)
        self.assertIn("nova versão", regua.proximo.texto)
        self.assertIn("Trocar a cor para azul", regua.proximo.detalhe)

    def test_aprovado_sem_contrato_o_comercial_gera_e_passa_o_link_de_10_minutos(self):
        orcamento = self.orcamento()
        regua = etapas(orcamento, self.vendas)
        self.assertEqual(self.estados(regua)["aprovacao"], "feita")
        self.assertEqual(self.estados(regua)["termo"], "atual")
        self.assertEqual(regua.lista[2].nota, "Gerar o contrato")
        self.assertEqual(regua.proximo.quem, "Comercial")
        self.assertEqual(regua.proximo.acao, "Gerar o contrato")
        self.assertEqual(regua.proximo.url, f"/orcamentos/{orcamento.pk}/documento/")
        self.assertIn(f"vale {svc.minutos_do_link()} minutos", regua.proximo.detalhe)
        # o Financeiro vê o passo, mas o botão é do Comercial
        regua_fin = etapas(orcamento, self.financeiro)
        self.assertEqual(regua_fin.proximo.texto, regua.proximo.texto)
        self.assertEqual(regua_fin.proximo.acao, "")
        # na tela do contrato, o cartão é a ação: sem botão para a mesma tela
        self.assertEqual(etapas(orcamento, self.vendas, tela="contrato").proximo.url, "")

    def test_assinado_a_vez_e_do_financeiro(self):
        orcamento = self.orcamento()
        documento = svc.gerar(orcamento, self.vendas)
        documento.situacao = documento.Situacao.ASSINADO
        documento.assinado_em = timezone.now()
        documento.save()
        regua = etapas(orcamento, self.financeiro)
        self.assertEqual(self.estados(regua)["termo"], "feita")
        self.assertEqual(self.estados(regua)["pagamento"], "atual")
        self.assertEqual(regua.proximo.quem, "Financeiro")
        self.assertIn("R$ 3.000,00", regua.proximo.texto)
        self.assertEqual(regua.proximo.acao, "Registrar pagamento")
        self.assertEqual(regua.proximo.alvo, "orcamentoPagamentoResumo")
        # o Comercial não registra pagamento: o passo aparece, o botão não
        self.assertEqual(etapas(orcamento, self.vendas).proximo.acao, "")

    def test_pagamento_parcial_diz_quanto_falta(self):
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(Decimal("1000.00"))
        regua = etapas(orcamento, self.financeiro)
        nota = next(e.nota for e in regua.lista if e.chave == "pagamento")
        self.assertIn("33% pago", nota)
        self.assertIn("R$ 2.000,00", nota)

    def test_recusado_para_em_vermelho(self):
        regua = etapas(self.orcamento(status=Orcamento.Status.RECUSADO), self.vendas)
        self.assertEqual(self.estados(regua)["aprovacao"], "parada")
        self.assertFalse(any(e.estado == "atual" for e in regua.lista))
        self.assertEqual(regua.proximo.tom, "alerta")
        self.assertIn("recusou", regua.proximo.texto)

    def test_a_marca_so_muda_quando_a_regua_muda(self):
        orcamento = self.orcamento(status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        primeira = etapas(orcamento, self.vendas).marca
        self.assertEqual(etapas(orcamento, self.vendas).marca, primeira)
        orcamento.status = Orcamento.Status.APROVADO
        orcamento.save()
        self.assertNotEqual(etapas(orcamento, self.vendas).marca, primeira)


class RotaDaReguaTests(_BaseEtapas):
    def test_a_janela_recebe_o_html_pronto_e_nao_de_novo_sem_mudanca(self):
        orcamento = self.orcamento()
        self.client.force_login(self.vendas)
        resposta = self.client.get(f"/orcamentos/{orcamento.pk}/etapas/", **AJAX)
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["feitas"], 2)
        self.assertEqual(corpo["html"].count('<li class="ls-etapa'), 6)
        self.assertIn('aria-current="step"', corpo["html"])
        self.assertIn("Próximo passo · com Comercial", corpo["html"])
        self.assertIn('data-etapa-ir="orcamentoDocumentoAssinatura"', corpo["html"])
        de_novo = self.client.get(f"/orcamentos/{orcamento.pk}/etapas/?marca={corpo['marca']}", **AJAX).json()
        self.assertNotIn("html", de_novo)
        self.assertEqual(de_novo["marca"], corpo["marca"])

    def test_quem_nao_abre_orcamento_nao_abre_a_regua(self):
        orcamento = self.orcamento()
        self.client.force_login(self.producao)
        resposta = self.client.get(f"/orcamentos/{orcamento.pk}/etapas/", **AJAX)
        self.assertNotEqual(resposta.status_code, 200)

    def test_a_janela_do_orcamento_tem_o_lugar_da_regua(self):
        self.client.force_login(self.vendas)
        pagina = self.client.get("/orcamentos/", **INTERNO).content.decode()
        self.assertIn('id="orcamentoEtapas"', pagina)
        self.assertIn('data-url-modelo="/orcamentos/0/etapas/"', pagina)


class ReguaNaTelaDoContratoTests(BaseDocumento):
    def test_a_tela_do_contrato_nasce_com_a_regua_e_ela_anda_quando_o_cliente_assina(self):
        orcamento = self.criar_orcamento(pago=False)
        self.client.force_login(self.vendedor)
        pagina = self.client.get(f"/orcamentos/{orcamento.pk}/documento/", **INTERNO).content.decode()
        self.assertIn("data-doc-etapas", pagina)
        self.assertIn("Contrato assinado", pagina)
        self.assertIn("Gere o contrato e passe para o cliente assinar.", pagina)

        documento = self.gerar(orcamento)
        resposta = self.assinar(self.link(documento))
        self.assertEqual(resposta.status_code, 200, resposta.content[:300])
        estado = self.client.get(
            f"/orcamentos/{orcamento.pk}/documento/estado/?documento={documento.pk}&situacao=aguardando",
            **AJAX,
        ).json()
        self.assertTrue(estado["mudou"])
        self.assertIn("Registre o pagamento", estado["etapas"])
        self.assertIn("Próximo passo · com Financeiro", estado["etapas"])
