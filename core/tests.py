import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .catalog_images import (
    adicionar_imagens_atuais_como_primeira,
    numerar_imagens_existentes_das_pecas,
)
from .models import Brinquedos, ImagemBrinquedo, ImagemPeca, PecasReposicao
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


class CatalogImageMigrationTests(TestCase):
    def test_imagem_antiga_vira_foto_um_sem_duplicar(self):
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Brinquedo de teste",
            imagem_brinquedo="imagens_brinquedos/original.jpg",
            descricao="Descrição",
            avaliacao=Decimal("5.00"),
            voltz="220V",
        )

        self.assertEqual(adicionar_imagens_atuais_como_primeira(), 1)
        self.assertEqual(adicionar_imagens_atuais_como_primeira(), 0)

        imagem = ImagemBrinquedo.objects.get(brinquedo=brinquedo)
        self.assertEqual(imagem.ordem, 1)
        self.assertEqual(
            imagem.imagem.name,
            "imagens_brinquedos/original.jpg",
        )
        self.assertEqual(brinquedo.imagem_catalogo.name, imagem.imagem.name)

    def test_peca_prioriza_frente_e_numera_as_demais(self):
        peca = PecasReposicao.objects.create(
            nome="Peça de teste",
            descricao_peca="Descrição",
        )
        detalhe = ImagemPeca.objects.create(
            peca_reposicao=peca,
            imagem="pecas_reposicao/detalhe.jpg",
            posicao=ImagemPeca.PosicaoImagem.DETALHE,
            ordem=1,
        )
        frente = ImagemPeca.objects.create(
            peca_reposicao=peca,
            imagem="pecas_reposicao/frente.jpg",
            posicao=ImagemPeca.PosicaoImagem.FRENTE,
            ordem=2,
        )

        self.assertEqual(numerar_imagens_existentes_das_pecas(), 2)

        detalhe.refresh_from_db()
        frente.refresh_from_db()
        self.assertEqual(frente.ordem, 1)
        self.assertEqual(detalhe.ordem, 2)
        self.assertEqual(peca.imagem_principal.pk, frente.pk)

    def test_telas_de_detalhe_exibem_galerias(self):
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Brinquedo galeria",
            imagem_brinquedo="imagens_brinquedos/principal.jpg",
            descricao="Descrição completa do brinquedo",
            avaliacao=Decimal("4.50"),
            voltz="220V",
        )
        for ordem in (1, 2):
            ImagemBrinquedo.objects.create(
                brinquedo=brinquedo,
                imagem=f"imagens_brinquedos/foto-{ordem}.jpg",
                ordem=ordem,
            )

        resposta_brinquedo = self.client.get(
            reverse("brinquedo_detalhe", args=[brinquedo.id])
        )
        self.assertEqual(resposta_brinquedo.status_code, 200)
        self.assertContains(resposta_brinquedo, 'data-galeria-indice="1"')
        self.assertContains(resposta_brinquedo, "1 / 2")

        peca = PecasReposicao.objects.create(
            nome="Peça galeria",
            descricao_peca="Descrição completa da peça",
            preco_venda=Decimal("129.90"),
        )
        for ordem, posicao in (
            (1, ImagemPeca.PosicaoImagem.FRENTE),
            (2, ImagemPeca.PosicaoImagem.DETALHE),
        ):
            ImagemPeca.objects.create(
                peca_reposicao=peca,
                imagem=f"pecas_reposicao/foto-{ordem}.jpg",
                ordem=ordem,
                posicao=posicao,
            )

        resposta_peca = self.client.get(
            reverse("reposicao_detalhe", args=[peca.id])
        )
        self.assertEqual(resposta_peca.status_code, 200)
        self.assertContains(resposta_peca, 'data-foto-indice="1"')
        self.assertContains(resposta_peca, "Código LS-P")
