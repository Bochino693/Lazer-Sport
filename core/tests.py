import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from .views import gerar_pix, processar_cartao


def carrinho_mock(total="100.00", payment_id=None):
    carrinho = MagicMock()
    carrinho.id = 7
    carrinho.total_final = Decimal(total)
    carrinho.mp_payment_id = payment_id
    carrinho.itens.exists.return_value = True
    return carrinho


def usuario_mock():
    return SimpleNamespace(
        is_authenticated=True,
        email="comprador@example.com",
    )


@override_settings(
    MP_ACCESS_TOKEN="TEST-ACCESS-TOKEN",
    ALLOWED_HOSTS=["testserver"],
)
class MercadoPagoPixTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("core.views.mercadopago.SDK")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_erro_do_gateway_nao_vira_key_error(
        self,
        buscar_carrinho,
        sdk_class,
    ):
        buscar_carrinho.return_value = carrinho_mock()
        sdk_class.return_value.payment.return_value.create.return_value = {
            "status": 400,
            "response": {
                "message": "Bad request",
                "cause": [{"description": "payer.email inválido"}],
            },
        }
        request = self.factory.get("/api/gerar-pix/?carrinho_id=7")
        request.user = usuario_mock()

        response = gerar_pix(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["erro"], "Não foi possível gerar o Pix.")
        self.assertIn("payer.email", body["detalhe"])

    @patch("core.views.mercadopago.SDK")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_pix_valido_salva_payment_id_e_retorna_qr_code(
        self,
        buscar_carrinho,
        sdk_class,
    ):
        carrinho = carrinho_mock()
        buscar_carrinho.return_value = carrinho
        sdk_class.return_value.payment.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": 123456,
                "status": "pending",
                "point_of_interaction": {
                    "transaction_data": {
                        "qr_code_base64": "BASE64",
                        "qr_code": "PIX-COPIA-COLA",
                        "ticket_url": "https://example.test/pix",
                    }
                },
            },
        }
        request = self.factory.get("/api/gerar-pix/?carrinho_id=7")
        request.user = usuario_mock()

        response = gerar_pix(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["payment_id"], 123456)
        self.assertEqual(body["qr_code"], "BASE64")
        self.assertEqual(carrinho.mp_payment_id, "123456")
        carrinho.save.assert_called_once_with(update_fields=["mp_payment_id"])


@override_settings(
    MP_ACCESS_TOKEN="TEST-ACCESS-TOKEN",
    ALLOWED_HOSTS=["testserver"],
)
class MercadoPagoCardTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_abaixo_de_20_mil_rejeita_mais_de_12_parcelas(
        self,
        buscar_carrinho,
    ):
        buscar_carrinho.return_value = carrinho_mock("19999.99")
        request = self.factory.post(
            "/processar_cartao/",
            data=json.dumps({
                "carrinho_id": 7,
                "token": "token",
                "payment_method_id": "visa",
                "installments": 13,
                "payer": {"email": "comprador@example.com"},
            }),
            content_type="application/json",
        )
        request.user = usuario_mock()

        response = processar_cartao(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertIn("12 parcelas", body["mensagem"])

    @patch("core.views.mercadopago.SDK")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_acima_de_20_mil_aceita_18_parcelas(
        self,
        buscar_carrinho,
        sdk_class,
    ):
        carrinho = carrinho_mock("20000.01")
        buscar_carrinho.return_value = carrinho
        sdk_class.return_value.payment.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": 987654,
                "status": "approved",
                "status_detail": "accredited",
            },
        }
        request = self.factory.post(
            "/processar_cartao/",
            data=json.dumps({
                "carrinho_id": 7,
                "token": "card-token",
                "payment_method_id": "visa",
                "issuer_id": "123",
                "installments": 18,
                "payer": {
                    "email": "comprador@example.com",
                    "identification": {
                        "type": "CPF",
                        "number": "19119119100",
                    },
                },
            }),
            content_type="application/json",
        )
        request.user = usuario_mock()

        response = processar_cartao(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["aprovado"])
        self.assertEqual(carrinho.mp_payment_id, "987654")