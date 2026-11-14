"""Compra normal: pagar fora da tela e voltar depois.

O cliente gera o Pix, sai, paga no app do banco e volta pelo carrinho, pela
tela de pagamento ou por Meus pedidos. O sistema reconhece que aquela compra
foi paga e leva para os pedidos, sem depender de a pessoa ter ficado na tela.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import conferencia_pagamento as conf
from .models import Carrinho, Pedido


def pagar(pedido, payment):
    Pedido.objects.filter(pk=pedido.pk).update(status="pago")
    pedido.refresh_from_db()
    return pedido, True


@override_settings(MP_ACCESS_TOKEN="APP_USR-teste", ALLOWED_HOSTS=["testserver"])
class VoltarDepoisDePagarTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("bia", "bia@exemplo.com", "Senha#12345")
        self.perfil = self.user.perfil
        self.perfil.telefone = "(11)91234-5678"
        self.perfil.save(update_fields=["telefone"])
        self.carrinho = Carrinho.objects.create(cliente=self.perfil)
        self.client.force_login(self.user)

    def reserva(self, status="aguardando_pagamento", mp="123"):
        return Pedido.objects.create(
            cliente=self.perfil,
            carrinho_origem=self.carrinho,
            status=status,
            mp_payment_id=mp,
            total_final=Decimal("10.00"),
        )

    def mp_responde(self, sdk, status):
        sdk.return_value.payment.return_value.get.return_value = {
            "status": 200,
            "response": {"id": 123, "status": status},
        }

    @patch("core.conferencia_pagamento.checkout.confirmar_pagamento", side_effect=pagar)
    @patch("core.conferencia_pagamento.mercadopago.SDK")
    def test_carrinho_vazio_com_pix_pago_leva_para_os_pedidos(self, sdk, _confirmar):
        pedido = self.reserva()
        self.mp_responde(sdk, "approved")

        resposta = self.client.get(reverse("carrinho"))

        self.assertRedirects(resposta, reverse("meus_pedidos") + "#pedidos", fetch_redirect_response=False)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, "pago")

    @patch("core.conferencia_pagamento.mercadopago.SDK")
    def test_pix_ainda_pendente_mostra_o_pagamento_em_andamento(self, sdk):
        pedido = self.reserva()
        self.mp_responde(sdk, "pending")

        resposta = self.client.get(reverse("carrinho"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["pagamento_em_andamento"], pedido)
        self.assertIn("no-store", resposta.headers.get("Cache-Control", ""))

    def test_pago_pelo_webhook_com_a_pessoa_fora_leva_para_os_pedidos_uma_vez(self):
        self.reserva(status="pago")

        primeira = self.client.get(reverse("carrinho"))
        self.assertRedirects(primeira, reverse("meus_pedidos") + "#pedidos", fetch_redirect_response=False)

        # depois de ver os pedidos, o carrinho vazio volta a ser só carrinho
        self.client.get(reverse("meus_pedidos"))
        segunda = self.client.get(reverse("carrinho"))
        self.assertEqual(segunda.status_code, 200)

    def test_compra_antiga_nao_prende_o_carrinho(self):
        pedido = self.reserva(status="pago")
        Pedido.objects.filter(pk=pedido.pk).update(atualizado=timezone.now() - timedelta(hours=5))

        resposta = self.client.get(reverse("carrinho"))

        self.assertEqual(resposta.status_code, 200)

    def test_voltar_para_a_tela_de_pagamento_ja_paga_vai_para_os_pedidos(self):
        self.reserva(status="pago")

        resposta = self.client.get(reverse("pagamento", args=[self.carrinho.id]))

        self.assertRedirects(resposta, reverse("meus_pedidos") + "#pedidos", fetch_redirect_response=False)

    @patch("core.conferencia_pagamento.checkout.confirmar_pagamento", side_effect=pagar)
    @patch("core.conferencia_pagamento.mercadopago.SDK")
    def test_meus_pedidos_acerta_o_pix_pago_fora_da_tela(self, sdk, _confirmar):
        pedido = self.reserva()
        self.mp_responde(sdk, "approved")

        resposta = self.client.get(reverse("meus_pedidos"))

        self.assertEqual(resposta.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, "pago")

    @patch("core.conferencia_pagamento.checkout.expirar_reserva")
    @patch("core.conferencia_pagamento.mercadopago.SDK")
    def test_pix_vencido_devolve_os_itens(self, sdk, expirar):
        self.reserva()
        self.mp_responde(sdk, "cancelled")

        self.client.get(reverse("carrinho"))

        expirar.assert_called_once()


@override_settings(ALLOWED_HOSTS=["testserver"])
class EntregaNoCarrinhoTests(TestCase):
    """A forma de entrega escolhida é a que a tela mostra e a que se cobra."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("caio", "caio@exemplo.com", "Senha#12345")
        perfil = self.user.perfil
        perfil.telefone = "(11)91234-5678"
        perfil.save(update_fields=["telefone"])
        self.carrinho = Carrinho.objects.create(cliente=perfil)
        from django.contrib.contenttypes.models import ContentType
        from .models import Brinquedos, ItemCarrinho
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game", descricao="x", avaliacao=Decimal("5"),
            valor_brinquedo=Decimal("100.00"),
        )
        ItemCarrinho.objects.create(
            carrinho=self.carrinho,
            content_type=ContentType.objects.get_for_model(Brinquedos),
            object_id=brinquedo.pk, quantidade=1,
        )
        self.client.force_login(self.user)

    def test_carrinho_e_sempre_retirada_na_fabrica(self):
        Carrinho.objects.filter(pk=self.carrinho.pk).update(tipo_envio="frete")
        html = self.client.get(reverse("carrinho")).content.decode()
        self.assertIn("Retirada na fábrica", html)
        self.assertIn("frete é por conta do cliente", html)
        self.assertNotIn('id="cepInput"', html)
        self.carrinho.refresh_from_db()
        self.assertEqual(self.carrinho.tipo_envio, "retirada")

    def test_frete_pelo_site_desligado(self):
        r = self.client.post(reverse("calcular_frete"), data='{"cep": "02000000"}',
                             content_type="application/json")
        self.assertEqual(r.status_code, 410)
        r = self.client.post(reverse("atualizar_tipo_envio", args=[self.carrinho.id]),
                             data='{"tipo_envio": "frete"}', content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_reserva_nunca_cobra_frete(self):
        from .checkout import reservar_pedido
        Carrinho.objects.filter(pk=self.carrinho.pk).update(tipo_envio="frete")
        self.carrinho.refresh_from_db()
        pedido, _ = reservar_pedido(self.carrinho, usuario=self.user)
        self.assertEqual(pedido.tipo_envio, "retirada")
        self.assertEqual(pedido.valor_frete or Decimal("0"), Decimal("0"))


class RespostaFalsa:
    def __init__(self, status, dados):
        self.status_code = status
        self._dados = dados

    def json(self):
        return self._dados


@override_settings(MP_ACCESS_TOKEN="APP_USR-teste")
class MinimoDoCartaoTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_menor_valor_entre_credito_e_debito_ativos(self):
        formas = [
            {"id": "visa", "payment_type_id": "credit_card", "status": "active", "min_allowed_amount": 0.5},
            {"id": "debvisa", "payment_type_id": "debit_card", "status": "active", "min_allowed_amount": 1},
            {"id": "pix", "payment_type_id": "bank_transfer", "status": "active", "min_allowed_amount": 0.01},
            {"id": "velho", "payment_type_id": "credit_card", "status": "deactive", "min_allowed_amount": 0.1},
        ]
        with patch.object(conf.requests, "get", return_value=RespostaFalsa(200, formas)) as get:
            self.assertEqual(conf.minimo_do_cartao(), Decimal("0.5"))
            self.assertEqual(conf.minimo_do_cartao(), Decimal("0.5"))
        self.assertEqual(get.call_count, 1)

    def test_sem_resposta_nao_bloqueia_o_cartao(self):
        with patch.object(conf.requests, "get", side_effect=conf.requests.Timeout):
            self.assertIsNone(conf.minimo_do_cartao())


class ParcelamentoSemJurosTests(TestCase):
    """Uma parcela a cada R$ 1.000, até 6x; abaixo de R$ 2.000, à vista."""

    def test_regra_das_parcelas(self):
        from .checkout import parcelas_maximas
        # o total NO CARTÃO (com os 12%): até 10x, parcela mínima de R$ 5 (seção 98)
        casos = {
            "0.01": 1, "4.99": 1, "9.99": 1, "10.00": 2, "30.00": 6,
            "49.99": 9, "50.00": 10, "999.99": 10, "6990.00": 10, "45000.00": 10,
        }
        for total, esperado in casos.items():
            self.assertEqual(parcelas_maximas(Decimal(total)), esperado, total)

    def test_pedido_guarda_as_parcelas_do_cartao(self):
        from .checkout import parcelas_do_pagamento
        parcelas, valor = parcelas_do_pagamento({
            "installments": 3, "transaction_amount": 6990,
            "transaction_details": {"installment_amount": 2330},
        })
        self.assertEqual((parcelas, valor), (3, Decimal("2330.00")))
        parcelas, valor = parcelas_do_pagamento({"transaction_amount": 100})
        self.assertEqual((parcelas, valor), (1, Decimal("100.00")))


@override_settings(ALLOWED_HOSTS=["testserver"])
class CarrinhoSemRecarregarTests(TestCase):
    """Cada ação do carrinho devolve o carrinho conferido para a tela."""

    def setUp(self):
        from django.contrib.contenttypes.models import ContentType
        from .models import Brinquedos, ItemCarrinho
        self.user = User.objects.create_user("lia", "lia@exemplo.com", "Senha#12345")
        perfil = self.user.perfil
        perfil.telefone = "(11)91234-5678"
        perfil.save(update_fields=["telefone"])
        self.carrinho = Carrinho.objects.create(cliente=perfil)
        tipo = ContentType.objects.get_for_model(Brinquedos)
        a = Brinquedos.objects.create(nome_brinquedo="Air Game", descricao="x", avaliacao=Decimal("5"), valor_brinquedo=Decimal("1000.00"))
        b = Brinquedos.objects.create(nome_brinquedo="Pebolim", descricao="x", avaliacao=Decimal("5"), valor_brinquedo=Decimal("250.00"))
        self.item_a = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=tipo, object_id=a.pk, quantidade=1)
        self.item_b = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=tipo, object_id=b.pk, quantidade=2)
        self.client.force_login(self.user)

    def test_quantidade_devolve_os_totais(self):
        r = self.client.post(reverse("alterar_quantidade_item"),
                             data='{"item_id": %d, "delta": 2}' % self.item_a.pk,
                             content_type="application/json").json()
        c = r["carrinho"]
        self.assertEqual(c["itens"][str(self.item_a.pk)]["quantidade"], 3)
        self.assertEqual(c["itens"][str(self.item_a.pk)]["subtotal"], "3000.00")
        self.assertEqual(c["total_liquido"], "3500.00")
        self.assertEqual(c["total_itens"], 5)
        self.assertFalse(c["vazio"])

    def test_remover_e_limpar_devolvem_o_carrinho(self):
        r = self.client.post(reverse("remover_item_carrinho"), {"item_id": self.item_b.pk}).json()
        self.assertNotIn(str(self.item_b.pk), r["carrinho"]["itens"])
        self.assertEqual(r["carrinho"]["total_liquido"], "1000.00")
        r = self.client.post(reverse("limpar_carrinho")).json()
        self.assertTrue(r["carrinho"]["vazio"])
        self.assertEqual(r["carrinho"]["total_itens"], 0)

    def test_tela_nao_recarrega_nas_acoes(self):
        html = self.client.get(reverse("carrinho")).content.decode()
        trecho = html[html.index("CARRINHO SEM RECARREGAR"):html.index("function lsEnviarQtd")]
        self.assertNotIn("location.reload()", trecho.replace("Nada de location.reload()", ""))
        self.assertIn('id="ck-vazio"', html)
        self.assertIn('id="cupom-aplicado"', html)


@override_settings(ALLOWED_HOSTS=["testserver"])
class UmCarrinhoSoTests(TestCase):
    """Cliente com dois carrinhos (corrida antiga) não pode ficar sem comprar."""

    def setUp(self):
        from django.contrib.contenttypes.models import ContentType
        from .models import Brinquedos, ItemCarrinho, Promocoes
        self.user = User.objects.create_user("rui", "rui@exemplo.com", "Senha#12345")
        self.perfil = self.user.perfil
        self.perfil.telefone = "(11)91234-5678"
        self.perfil.save(update_fields=["telefone"])
        self.tipo = ContentType.objects.get_for_model(Brinquedos)
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="x", avaliacao=Decimal("5"),
            valor_brinquedo=Decimal("6990.00"), exibir_na_loja=True,
        )
        self.primeiro = Carrinho.objects.create(cliente=self.perfil)
        self.segundo = Carrinho.objects.create(cliente=self.perfil)
        ItemCarrinho.objects.create(carrinho=self.primeiro, content_type=self.tipo, object_id=self.brinquedo.pk, quantidade=1)
        ItemCarrinho.objects.create(carrinho=self.segundo, content_type=self.tipo, object_id=self.brinquedo.pk, quantidade=2)
        self.client.force_login(self.user)

    def test_adicionar_com_dois_carrinhos_funciona_e_junta(self):
        r = self.client.post(
            reverse("adicionar_ao_carrinho", args=["brinquedo", self.brinquedo.pk]),
            {"quantidade": "1"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertTrue(r.json()["sucesso"])
        self.assertEqual(Carrinho.objects.filter(cliente=self.perfil).count(), 1)
        item = Carrinho.objects.get(cliente=self.perfil).itens.get()
        self.assertEqual(item.quantidade, 4)

    def test_tela_do_carrinho_com_dois_carrinhos_abre(self):
        self.assertEqual(self.client.get(reverse("carrinho")).status_code, 200)
        self.assertEqual(Carrinho.objects.filter(cliente=self.perfil).count(), 1)

    def test_promocao_com_quantidade_vai_para_o_carrinho(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import Promocoes
        promo = Promocoes.objects.create(
            descricao="Black Friday: teste", preco_promocao=Decimal("4990.00"),
            brinquedos=self.brinquedo, ativo=True,
            valida_ate=timezone.localdate() + timedelta(days=5),
        )
        r = self.client.post(
            reverse("adicionar_ao_carrinho", args=["promocao", promo.pk]),
            {"quantidade": "3"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()["quantidade"], 3)

    def test_erro_inesperado_volta_em_json_com_recado(self):
        with patch("core.views.checkout.carrinho_do_cliente", side_effect=RuntimeError("x")):
            r = self.client.post(
                reverse("adicionar_ao_carrinho", args=["brinquedo", self.brinquedo.pk]),
                {"quantidade": "1"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(r.status_code, 500)
        self.assertIn("WhatsApp", r.json()["erro"])


class CartaoComDozePorCentoTests(TestCase):
    """LEIA-ME seção 98: o Pix paga o preço; o cartão de crédito, o preço + 12%."""

    def _pagamento(self, pedido, tipo, valor, vezes=10):
        from . import checkout
        return {
            "id": "777", "status": "approved", "payment_type_id": tipo, "transaction_amount": float(valor),
            "external_reference": checkout.referencia_do_pedido(pedido),
            "metadata": {"cart_fingerprint": "f"}, "installments": vezes,
            "transaction_details": {"installment_amount": float(valor) / vezes},
        }

    def _pedido(self, *itens):
        from types import SimpleNamespace
        linhas = [SimpleNamespace(subtotal=Decimal(v), sem_juros_no_cartao=s) for v, s in itens]
        total = sum((linha.subtotal for linha in linhas), Decimal("0.00"))
        return SimpleNamespace(id=5, total_final=total, mp_payment_id=None, mp_fingerprint="f",
                               itens=SimpleNamespace(all=lambda: linhas))

    def test_confere_o_cartao_com_os_12_e_o_pix_pelo_preco(self):
        from . import checkout
        pedido = self._pedido(("100.00", 10))  # uma promoção: 10x sem juros
        confere = checkout.pagamento_confere_com_pedido
        self.assertTrue(confere(self._pagamento(pedido, "credit_card", "112.00"), pedido))
        self.assertFalse(confere(self._pagamento(pedido, "credit_card", "100.00"), pedido))
        self.assertTrue(confere(self._pagamento(pedido, "bank_transfer", "100.00"), pedido))
        self.assertFalse(confere(self._pagamento(pedido, "bank_transfer", "112.00"), pedido))

    def test_acima_das_vezes_sem_juros_o_cartao_confere_com_os_juros(self):
        """LEIA-ME seção 99: um brinquedo (6x) em 7x e em 10x paga juros; em 6x, não."""
        from . import checkout
        pedido = self._pedido(("100.00", 6))
        confere = checkout.pagamento_confere_com_pedido
        self.assertTrue(confere(self._pagamento(pedido, "credit_card", "112.00", vezes=6), pedido))
        self.assertTrue(confere(self._pagamento(pedido, "credit_card", "125.79", vezes=7), pedido))
        self.assertTrue(confere(self._pagamento(pedido, "credit_card", "131.23", vezes=10), pedido))
        self.assertFalse(confere(self._pagamento(pedido, "credit_card", "112.00", vezes=10), pedido))

    def test_pedido_misto_cada_item_com_a_sua_regra(self):
        """A promoção (10x) não paga juros em 7x; a peça (6x) do mesmo pedido paga."""
        from . import checkout
        pedido = self._pedido(("1000.00", 10), ("500.00", 6))
        opcoes = {o["parcelas"]: o for o in checkout.opcoes_do_pedido(pedido)}
        self.assertTrue(opcoes[6]["sem_juros"])
        self.assertEqual(opcoes[6]["total"], Decimal("1680.00"))
        self.assertFalse(opcoes[7]["sem_juros"])
        self.assertEqual(opcoes[7]["total"], Decimal("1748.95"))
        self.assertEqual(opcoes[10]["total"], Decimal("1776.16"))
        self.assertEqual(checkout.sem_juros_ate(list(opcoes.values())), 6)

    def test_o_pedido_guarda_o_que_o_cliente_pagou(self):
        from unittest import mock
        from . import checkout
        user = User.objects.create_user("cris", "cris@exemplo.com", "Senha#12345")
        perfil = user.perfil
        pedido = Pedido.objects.create(cliente=perfil, status="aguardando_pagamento", total_bruto=Decimal("4990"))
        Pedido.objects.filter(pk=pedido.pk).update(mp_fingerprint="f")
        pedido.refresh_from_db()
        with mock.patch("core.notificacoes.enviar_confirmacao_de_compra"), self.captureOnCommitCallbacks(execute=True):
            checkout.confirmar_pagamento(pedido, self._pagamento(pedido, "credit_card", checkout.valor_no_cartao(pedido.total_final)))
        pedido.refresh_from_db()
        self.assertEqual(pedido.valor_cobrado, checkout.valor_no_cartao(pedido.total_final))
        self.assertEqual(pedido.total_cobrado, pedido.valor_cobrado)
        self.assertEqual(pedido.parcelas, 10)
