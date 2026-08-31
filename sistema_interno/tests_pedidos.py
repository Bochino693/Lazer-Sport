"""O número da bolinha e o conteúdo da tela falam da mesma coisa.

O DEFEITO. A bolinha do menu contava `core.Pedido` -- o pedido que o
cliente faz no site, que é o que a palavra significa para quem usa o
painel. A tela de Pedidos listava `CentralPedidos`, uma tabela interna de
uma época anterior que nunca recebeu uma linha. O menu dizia "6 pedidos",
a pessoa clicava e lia "Nenhum pedido na central".

É o pior tipo de defeito: nada dá erro, nada aparece em log, e a tela em
si está correta -- só não é o mesmo assunto. E como as duas fontes nunca
se cruzavam, nenhum teste percebia. O mesmo valia para Vendas.

Estes testes cruzam as duas: contam pela central de avisos e contam pela
tela, e exigem o mesmo número.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Pedido, Venda

from .avisos import coletar


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class BolinhaETelaContamOMesmoTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-pedidos", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    @staticmethod
    def quantidade_no_aviso(chave):
        return next(
            (
                aviso.quantidade
                for aviso in coletar(User.objects.get(username="gestor-pedidos"))
                if aviso.chave == chave
            ),
            0,
        )

    def abrir(self, rota, **filtros):
        return self.client.get(rota, filtros, HTTP_HOST="interno.testserver")

    # -------------------------------------------------------- pedidos
    def criar_pedidos(self):
        for status in (
            "aguardando_pagamento", "pago", "em_preparacao",
            "saiu_entrega", "finalizado", "cancelado",
        ):
            Pedido.objects.create(status=status, total_liquido=Decimal("100.00"))

    def test_a_tela_de_pedidos_mostra_exatamente_o_que_a_bolinha_conta(self):
        self.criar_pedidos()

        contado = self.quantidade_no_aviso("pedidos")
        resposta = self.abrir("/pedidos/inner/")
        listado = resposta.context["page_obj"].paginator.count

        self.assertEqual(contado, 4, "Quatro dos seis não estão nem finalizados nem cancelados.")
        self.assertEqual(
            listado, contado,
            "A bolinha e a tela precisam contar a mesma fila -- foi a "
            "divergência entre as duas que fez o menu dizer '6 pedidos' "
            "sobre uma tela vazia.",
        )

    def test_o_filtro_em_aberto_e_o_padrao_da_tela(self):
        """Quem abre Pedidos quer ver o que está em aberto, não o histórico."""
        self.criar_pedidos()

        self.assertEqual(self.abrir("/pedidos/inner/").context["filtro_ativo"], "abertos")

    def test_os_outros_filtros_alcancam_o_histórico_inteiro(self):
        self.criar_pedidos()

        self.assertEqual(self.abrir("/pedidos/inner/", filtro="todos").context["page_obj"].paginator.count, 6)
        self.assertEqual(self.abrir("/pedidos/inner/", filtro="finalizados").context["page_obj"].paginator.count, 1)
        self.assertEqual(self.abrir("/pedidos/inner/", filtro="cancelados").context["page_obj"].paginator.count, 1)

    def test_o_pedido_da_loja_aparece_na_tela_com_o_que_importa(self):
        # `total_final` é recalculado por `Pedido.save()` a partir do
        # líquido mais o frete -- escrever nele direto não adianta.
        pedido = Pedido.objects.create(
            status="pago", total_liquido=Decimal("420.00"),
            valor_frete=Decimal("30.00"), cidade="São Paulo", estado="SP",
        )

        resposta = self.abrir("/pedidos/inner/")

        self.assertContains(resposta, f"#{pedido.pk}")
        self.assertContains(resposta, "450,00")
        self.assertContains(resposta, "São Paulo")

    # --------------------------------------------------------- vendas
    def test_a_tela_de_vendas_mostra_o_que_a_bolinha_conta(self):
        for confirmado in (False, False, True):
            Venda.objects.create(
                valor_pago=Decimal("200.00"), confirmado=confirmado,
            )

        contado = self.quantidade_no_aviso("vendas")
        listado = self.abrir(
            "/vendas/inner/", filtro="a_confirmar",
        ).context["page_obj"].paginator.count

        self.assertEqual(contado, 2)
        self.assertEqual(listado, contado)

    def test_vendas_abre_no_que_a_bolinha_conta(self):
        self.assertEqual(
            self.abrir("/vendas/inner/").context["filtro_ativo"], "a_confirmar",
        )

    def test_a_tela_de_vendas_soma_o_que_ja_entrou(self):
        Venda.objects.create(valor_pago=Decimal("200.00"), confirmado=True)
        Venda.objects.create(valor_pago=Decimal("300.50"), confirmado=True)
        Venda.objects.create(valor_pago=Decimal("999.00"), confirmado=False)

        resposta = self.abrir("/vendas/inner/")

        # A faixa de dinheiro soma só o que foi confirmado. A venda de
        # 999 aparece na LISTA (é justamente a que espera confirmação),
        # mas não pode entrar na conta de "já entrou".
        self.assertEqual(resposta.context["valor_confirmado"], Decimal("500.50"))
        self.assertContains(resposta, "500,50")

    def test_nenhuma_das_duas_telas_le_a_central_antiga(self):
        """`CentralPedidos` e `CentralVendas` nunca receberam uma linha.

        Se alguém apontar as telas de volta para elas, o defeito volta
        inteiro -- e volta silencioso.
        """
        from .views import PedidosView, VendasView
        import inspect

        for view in (PedidosView, VendasView):
            with self.subTest(view=view.__name__):
                fonte = inspect.getsource(view)
                self.assertNotIn("CentralPedidos", fonte)
                self.assertNotIn("CentralVendas", fonte)
