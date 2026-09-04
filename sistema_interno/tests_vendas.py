"""Do pagamento ao comprovante assinado.

O que estes testes protegem:

  * cada pagamento vira uma VENDA com data e valor da parcela -- é o que
    permite dizer quanto entrou em cada mês, coisa que `valor_pago`
    (acumulado, sobrescrito) nunca soube responder;
  * o comprovante só existe quando existe dinheiro;
  * o cliente assina uma vez, com documento válido, e o que ele assinou
    fica congelado num hash;
  * a tela de vendas e o financeiro somam as três origens sem contar
    ninguém duas vezes.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Pedido, Venda as VendaDaLoja
from sistema_interno import vendas as servico_vendas
from sistema_interno.models import (
    AceiteVenda,
    Cliente,
    ItemOrcamento,
    Orcamento,
    OrdemServico,
    Venda,
)
from sistema_interno.permissoes import atribuir_funcoes


def _orcamento_com_item(valor="1000.00", **extras):
    orcamento = Orcamento.objects.create(
        nome_cliente="Buffet Alegria",
        validade=timezone.localdate() + timedelta(days=5),
        status=Orcamento.Status.APROVADO,
        forma_pagamento="Pix",
        **extras,
    )
    ItemOrcamento.objects.create(
        orcamento=orcamento,
        descricao="Cama elástica 3m",
        quantidade=1,
        valor_unitario=Decimal(valor),
    )
    return orcamento


class ParcelaViraVendaTests(TestCase):
    """Registrar pagamento e registrar venda são o mesmo ato."""

    def test_o_primeiro_pagamento_cria_a_venda_da_parcela(self):
        orcamento = _orcamento_com_item("1000.00")

        venda = orcamento.registrar_pagamento(Decimal("300.00"))

        self.assertIsNotNone(venda)
        self.assertEqual(venda.valor, Decimal("300.00"))
        self.assertEqual(venda.valor_documento, Decimal("1000.00"))
        self.assertEqual(venda.origem, Venda.Origem.ORCAMENTO)
        self.assertTrue(venda.parcial)

    def test_o_segundo_pagamento_registra_só_a_diferença(self):
        """`valor_pago` é acumulado; a venda é a parcela.

        Sem isso, quitar uma proposta de R$ 1.000 depois de uma entrada de
        R$ 300 registraria R$ 1.000 de novo -- a receita do mês apareceria
        com R$ 1.300 em vez de R$ 700.
        """
        orcamento = _orcamento_com_item("1000.00")
        orcamento.registrar_pagamento(Decimal("300.00"))

        segunda = orcamento.registrar_pagamento(Decimal("1000.00"))

        self.assertEqual(segunda.valor, Decimal("700.00"))
        self.assertEqual(
            servico_vendas.total_registrado(orcamento), Decimal("1000.00")
        )
        self.assertEqual(Venda.objects.count(), 2)

    def test_salvar_o_mesmo_valor_de_novo_nao_duplica_venda(self):
        orcamento = _orcamento_com_item("1000.00")
        orcamento.registrar_pagamento(Decimal("300.00"))

        repetido = orcamento.registrar_pagamento(Decimal("300.00"))

        self.assertIsNone(repetido)
        self.assertEqual(Venda.objects.count(), 1)

    def test_corrigir_para_menos_nao_cria_venda_negativa(self):
        orcamento = _orcamento_com_item("1000.00")
        orcamento.registrar_pagamento(Decimal("300.00"))

        correcao = orcamento.registrar_pagamento(Decimal("100.00"))

        self.assertIsNone(correcao)
        self.assertEqual(Venda.objects.count(), 1)

    def test_a_ordem_de_servico_tambem_registra_venda(self):
        ordem = OrdemServico.objects.create(
            nome_cliente="Escola Aprender", equipamento="Tobogã",
        )

        venda = ordem.registrar_pagamento(Decimal("450.00"))

        self.assertIsNotNone(venda)
        self.assertEqual(venda.origem, Venda.Origem.ORDEM_SERVICO)
        self.assertEqual(venda.ordem_servico_id, ordem.pk)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class DocumentoDeVendaTests(TestCase):
    """A ação do painel emite o comprovante -- e só com dinheiro na conta."""

    URL = "/orcamentos/"

    def setUp(self):
        self.financeiro = User.objects.create_user(
            username="financeiro-venda", password="senha-longa-de-teste",
        )
        # O código da função, não o nome do grupo -- é o que
        # `atribuir_funcoes` entende.
        atribuir_funcoes(self.financeiro, ["financeiro"])
        self.client.force_login(self.financeiro)

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_proposta_sem_pagamento_nao_gera_comprovante(self):
        orcamento = _orcamento_com_item("1000.00")

        resposta = self.post({"action": "documento_venda", "id": orcamento.pk})

        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(Venda.objects.filter(orcamento=orcamento).exists())

    def test_com_pagamento_o_comprovante_sai_com_link(self):
        orcamento = _orcamento_com_item("1000.00")
        orcamento.registrar_pagamento(Decimal("400.00"))

        resposta = self.post({"action": "documento_venda", "id": orcamento.pk})

        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "sucesso")
        self.assertIn("/venda/", corpo["link"])
        self.assertEqual(corpo["valor"], "400,00")

        venda = Venda.objects.get(orcamento=orcamento)
        self.assertTrue(venda.documento_emitido)
        self.assertEqual(venda.situacao, Venda.Situacao.DOCUMENTO_EMITIDO)

    def test_documento_de_proposta_paga_antes_desta_tela_nao_fica_sem_lastro(self):
        """Pagamento gravado sem passar por `registrar_pagamento`.

        É o caso do histórico e o de uma correção feita direto no banco: o
        comprovante ainda assim precisa nascer com uma venda por trás.
        """
        orcamento = _orcamento_com_item("1000.00")
        Orcamento.objects.filter(pk=orcamento.pk).update(
            valor_pago=Decimal("250.00"),
            status_pagamento=Orcamento.StatusPagamento.PARCIAL,
        )

        resposta = self.post({"action": "documento_venda", "id": orcamento.pk})

        self.assertEqual(resposta.status_code, 200, resposta.content)
        venda = Venda.objects.get(orcamento=orcamento)
        self.assertEqual(venda.valor, Decimal("250.00"))


@override_settings(ALLOWED_HOSTS=["testserver"])
class AssinaturaDoClienteTests(TestCase):
    """A página pública do comprovante, do lado de quem pagou."""

    def setUp(self):
        self.orcamento = _orcamento_com_item("1000.00")
        self.venda = self.orcamento.registrar_pagamento(Decimal("400.00"))

    def url(self):
        return f"/venda/{self.venda.token}/"

    def test_documento_nao_emitido_nao_abre(self):
        resposta = self.client.get(self.url())

        self.assertEqual(resposta.status_code, 404)

    def test_emitido_abre_e_mostra_os_valores(self):
        self.venda.emitir_documento()

        resposta = self.client.get(self.url())

        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode()
        self.assertIn("400,00", conteudo)
        self.assertIn("1.000,00", conteudo)

    def test_assinatura_exige_documento_valido(self):
        self.venda.emitir_documento()

        resposta = self.client.post(self.url(), {
            "nome": "Marta Responsável",
            "documento_assinante": "111.111.111-11",
            "consentimento": "1",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(AceiteVenda.objects.exists())

    def test_assinatura_exige_consentimento(self):
        self.venda.emitir_documento()

        resposta = self.client.post(self.url(), {
            "nome": "Marta Responsável",
            "documento_assinante": "529.982.247-25",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(AceiteVenda.objects.exists())

    def test_assinatura_valida_vira_recibo(self):
        self.venda.emitir_documento()

        resposta = self.client.post(self.url(), {
            "nome": "Marta Responsável",
            "documento_assinante": "529.982.247-25",
            "consentimento": "1",
        }, follow=True)

        self.assertEqual(resposta.status_code, 200)
        aceite = AceiteVenda.objects.get()
        self.assertEqual(aceite.assinante_nome, "Marta Responsável")
        self.assertEqual(len(aceite.venda_hash), 64)
        # O documento informado nunca é guardado com pontuação -- e nunca
        # aparece inteiro na tela.
        self.assertNotIn(".", aceite.assinante_documento)
        self.assertNotIn("529.982.247-25", resposta.content.decode())

        self.venda.refresh_from_db()
        self.assertEqual(self.venda.situacao, Venda.Situacao.ASSINADA)

    def test_ninguem_assina_duas_vezes(self):
        self.venda.emitir_documento()
        dados = {
            "nome": "Marta Responsável",
            "documento_assinante": "529.982.247-25",
            "consentimento": "1",
        }
        self.client.post(self.url(), dados)

        self.client.post(self.url(), dict(dados, nome="Outra Pessoa"))

        self.assertEqual(AceiteVenda.objects.count(), 1)
        self.assertEqual(AceiteVenda.objects.get().assinante_nome, "Marta Responsável")

    def test_o_comprovante_de_um_cliente_nao_leva_ao_de_outro(self):
        """O token é a chave: id sequencial abriria a porta do vizinho."""
        self.venda.emitir_documento()
        outra = _orcamento_com_item("2000.00").registrar_pagamento(Decimal("500.00"))
        outra.emitir_documento()

        resposta = self.client.get(f"/venda/{self.venda.pk}/")

        self.assertEqual(resposta.status_code, 404)


class EstatisticaDeVendasTests(TestCase):
    """As três origens somadas uma vez só."""

    def test_o_resumo_junta_orcamento_ordem_e_loja(self):
        _orcamento_com_item("1000.00").registrar_pagamento(Decimal("400.00"))
        OrdemServico.objects.create(
            nome_cliente="Escola", equipamento="Tobogã",
        ).registrar_pagamento(Decimal("150.00"))
        VendaDaLoja.objects.create(
            pedido=Pedido.objects.create(status="finalizado"),
            valor_pago=Decimal("90.00"),
            confirmado=True,
        )

        indicadores = servico_vendas.indicadores()

        self.assertEqual(indicadores["total_recebido"], Decimal("640.00"))
        self.assertEqual(indicadores["quantidade_vendas"], 3)
        por_origem = {
            linha["codigo"]: linha["total"] for linha in indicadores["origens"]
        }
        self.assertEqual(por_origem[Venda.Origem.ORCAMENTO], Decimal("400.00"))
        self.assertEqual(por_origem[Venda.Origem.ORDEM_SERVICO], Decimal("150.00"))
        self.assertEqual(por_origem[Venda.Origem.LOJA], Decimal("90.00"))

    def test_o_financeiro_conta_a_proposta_paga_no_balcao(self):
        """Antes, receita era só a da loja -- o menor dos três caminhos."""
        from sistema_interno import financeiro as fin

        _orcamento_com_item("20000.00").registrar_pagamento(Decimal("5000.00"))

        serie = fin.montar_series(fin.janela_de_meses(2))

        self.assertEqual(serie[-1]["receita"], Decimal("5000.00"))

    def test_o_que_falta_receber_nao_entra_no_recebido(self):
        """Saldo a receber é promessa, e promessa não é caixa."""
        orcamento = _orcamento_com_item("1000.00")
        orcamento.registrar_pagamento(Decimal("400.00"))

        indicadores = servico_vendas.indicadores()
        em_aberto = servico_vendas.em_aberto_por_documento()

        self.assertEqual(indicadores["total_recebido"], Decimal("400.00"))
        self.assertEqual(em_aberto["orcamentos"], Decimal("600.00"))


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class TelaDeVendasTests(TestCase):
    """A tela mostra as três origens, e não só a loja."""

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-vendas", password="senha-longa-de-teste",
            email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def test_a_tela_lista_venda_de_orcamento_e_de_ordem_de_servico(self):
        cliente = Cliente.objects.create(
            nome_cliente="Buffet Alegria", telefone="(11) 97777-6655",
        )
        _orcamento_com_item("1000.00", cliente=cliente).registrar_pagamento(
            Decimal("400.00")
        )
        OrdemServico.objects.create(
            nome_cliente="Escola Aprender", equipamento="Tobogã",
        ).registrar_pagamento(Decimal("150.00"))

        resposta = self.client.get("/vendas/inner/", HTTP_HOST="interno.testserver")

        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode()
        self.assertIn("Buffet Alegria", conteudo)
        self.assertIn("Escola Aprender", conteudo)
        self.assertIn("550,00", conteudo)
