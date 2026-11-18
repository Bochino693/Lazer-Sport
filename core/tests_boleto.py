"""O boleto do checkout (LEIA-ME seção 100): pelo preço do Pix, vence em 3 dias."""

import json
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import boleto as regras
from . import checkout
from .models import Brinquedos, Carrinho, ItemCarrinho, Pedido

CPF = "529.982.247-25"  # um CPF de teste válido (dígitos conferem)
DADOS = {
    "nome": "Bia Souza", "documento": CPF, "cep": "01310-100", "rua": "Av. Paulista",
    "numero": "1000", "bairro": "Bela Vista", "cidade": "São Paulo", "uf": "sp",
}


def resposta_boleto(pagamento_id=555, valor="4990.00", status="pending"):
    return {
        "status": 201,
        "response": {
            "id": pagamento_id, "status": status, "payment_type_id": "ticket",
            "transaction_amount": float(valor),
            "date_of_expiration": "2026-11-17T23:59:59.000-03:00",
            "transaction_details": {
                "external_resource_url": f"https://www.mercadopago.com.br/payments/{pagamento_id}/ticket",
                "digitable_line": "23793381286008200000000000000000000000000000000",
            },
        },
    }


class RegrasDoBoletoTests(SimpleTestCase):
    def test_dados_limpos(self):
        limpos = regras.validar(DADOS)
        self.assertEqual(limpos["documento"], "52998224725")
        self.assertEqual(limpos["cep"], "01310100")
        self.assertEqual(limpos["uf"], "SP")

    def test_o_que_o_banco_recusaria_volta_com_a_frase(self):
        casos = (
            ({"documento": "111.111.111-11"}, "CPF ou o CNPJ"),
            ({"nome": "Bia"}, "nome completo"),
            ({"cep": "123"}, "8 números"),
            ({"uf": "XX"}, "estado"),
            ({"rua": "", "bairro": ""}, "a rua, o bairro"),
        )
        for troca, frase in casos:
            with self.subTest(troca=troca):
                with self.assertRaisesMessage(regras.DadosInvalidos, frase):
                    regras.validar({**DADOS, **troca})

    def test_cnpj_aceita_a_razao_social_de_uma_palavra(self):
        limpos = regras.validar({**DADOS, "documento": "11.222.333/0001-81", "nome": "Brinquedolandia"})
        payer = regras.pagador("x@exemplo.com", limpos)
        self.assertEqual(payer["identification"], {"type": "CNPJ", "number": "11222333000181"})
        self.assertEqual(payer["first_name"], "Brinquedolandia")

    def test_pagador_com_endereco(self):
        payer = regras.pagador("bia@exemplo.com", regras.validar(DADOS))
        self.assertEqual(payer["identification"], {"type": "CPF", "number": "52998224725"})
        self.assertEqual((payer["first_name"], payer["last_name"]), ("Bia", "Souza"))
        self.assertEqual(payer["address"]["federal_unit"], "SP")
        self.assertEqual(payer["address"]["zip_code"], "01310100")

    def test_vence_em_3_dias_no_fim_do_dia_de_brasilia(self):
        agora = datetime(2026, 11, 14, 22, 30, tzinfo=dt_timezone.utc)  # 19:30 em Brasília
        dia = regras.vencimento(agora)
        self.assertEqual(regras.vencimento_mp(dia), "2026-11-17T23:59:59.000-03:00")

    def test_le_a_resposta(self):
        info = regras.dados_da_resposta(resposta_boleto()["response"])
        self.assertTrue(info["url"].endswith("/ticket"))
        self.assertTrue(info["linha"].startswith("2379"))
        self.assertEqual(info["vencimento"].day, 17)


@override_settings(MP_ACCESS_TOKEN="TEST-ACCESS-TOKEN")
class BoletoNoCheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("bia", "bia@exemplo.com", "Senha#12345", first_name="Bia")
        perfil = self.user.perfil
        perfil.telefone = "(11)91234-5678"
        perfil.save(update_fields=["telefone"])
        self.perfil = perfil
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="x", avaliacao=Decimal("5"),
            valor_brinquedo=Decimal("4990.00"), exibir_na_loja=True,
        )
        self.carrinho = Carrinho.objects.create(cliente=perfil, tipo_envio="retirada")
        from django.contrib.contenttypes.models import ContentType

        ItemCarrinho.objects.create(
            carrinho=self.carrinho, content_type=ContentType.objects.get_for_model(Brinquedos),
            object_id=self.brinquedo.pk, quantidade=1,
        )
        self.client.force_login(self.user)

    def gerar(self, **extra):
        return self.client.post(
            reverse("gerar_boleto"), data=json.dumps({**DADOS, "carrinho_id": self.carrinho.pk, **extra}),
            content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    @mock.patch("core.notificacoes.enviar_boleto")
    @mock.patch("core.views.mercadopago.SDK")
    def test_gera_o_boleto_pelo_preco_do_pix(self, sdk_class, _email):
        criar = sdk_class.return_value.payment.return_value.create
        criar.return_value = resposta_boleto()
        r = self.gerar()
        self.assertEqual(r.status_code, 200, r.content[:300])
        dados = r.json()
        self.assertTrue(dados["boleto"])
        self.assertTrue(dados["linha"].startswith("2379"))
        self.assertEqual(dados["valor"], "4990.00")
        enviado = criar.call_args[0][0]
        self.assertEqual(enviado["payment_method_id"], "bolbradesco")
        self.assertEqual(enviado["transaction_amount"], 4990.0)  # o preço do Pix, sem os 12%
        self.assertEqual(enviado["payer"]["address"]["city"], "São Paulo")
        self.assertRegex(enviado["date_of_expiration"], r"T23:59:59\.000-03:00$")
        pedido = Pedido.objects.get(pk=dados["pedido_id"])
        self.assertEqual(pedido.status, "aguardando_pagamento")
        self.assertTrue(pedido.boleto_aberto)
        self.assertEqual(pedido.mp_payment_id, "555")
        self.assertFalse(self.carrinho.itens.exists())  # reservado

    @mock.patch("core.views.mercadopago.SDK")
    def test_dado_errado_nao_reserva_nada(self, sdk_class):
        r = self.gerar(documento="123")
        self.assertEqual(r.status_code, 400)
        self.assertIn("CPF", r.json()["erro"])
        self.assertTrue(self.carrinho.itens.exists())
        sdk_class.return_value.payment.return_value.create.assert_not_called()

    @mock.patch("core.notificacoes.enviar_boleto")
    @mock.patch("core.views.mercadopago.SDK")
    def test_abrir_de_novo_devolve_o_mesmo_boleto(self, sdk_class, _email):
        criar = sdk_class.return_value.payment.return_value.create
        criar.return_value = resposta_boleto()
        primeiro = self.gerar().json()
        segundo = self.gerar().json()
        self.assertEqual(criar.call_count, 1)
        self.assertEqual(primeiro["linha"], segundo["linha"])

    @mock.patch("core.views.mercadopago.SDK")
    def test_recusado_devolve_os_itens_ao_carrinho(self, sdk_class):
        sdk_class.return_value.payment.return_value.create.return_value = {
            "status": 400, "response": {"message": "invalid zip_code"},
        }
        r = self.gerar()
        self.assertEqual(r.status_code, 400)
        self.assertTrue(self.carrinho.itens.exists())

    @mock.patch("core.notificacoes.enviar_boleto")
    @mock.patch("core.views.mercadopago.SDK")
    def test_trocar_para_o_pix_cancela_o_boleto(self, sdk_class, _email):
        pagamento = sdk_class.return_value.payment.return_value
        pagamento.create.return_value = resposta_boleto()
        pedido_id = self.gerar().json()["pedido_id"]

        # o boleto ainda pendente; o cancelamento dá certo; o Pix novo nasce
        pagamento.get.return_value = {"status": 200, "response": resposta_boleto()["response"]}
        pagamento.update.return_value = {"status": 200, "response": {"id": 555, "status": "cancelled"}}
        pagamento.create.return_value = {
            "status": 201,
            "response": {
                "id": 777, "status": "pending", "payment_type_id": "bank_transfer",
                "transaction_amount": 4990.0,
                "point_of_interaction": {"transaction_data": {"qr_code": "000201PIX", "qr_code_base64": ""}},
            },
        }
        r = self.client.get(reverse("gerar_pix"), {"carrinho_id": self.carrinho.pk})
        self.assertEqual(r.status_code, 200, r.content[:300])
        pagamento.update.assert_called_once()
        self.assertEqual(pagamento.update.call_args[0][1], {"status": "cancelled"})
        pedido = Pedido.objects.get(pk=pedido_id)
        self.assertEqual(pedido.mp_payment_id, "777")
        self.assertEqual(pedido.status, "aguardando_pagamento")

    def test_pago_o_pedido_diz_boleto(self):
        pedido, _ = checkout.reservar_pedido(self.carrinho, usuario=self.user)
        pedido.mp_payment_id = "555"
        pedido.save(update_fields=["mp_payment_id"])
        payment = {
            **resposta_boleto(status="approved")["response"],
            "external_reference": checkout.referencia_do_pedido(pedido),
            "metadata": {"cart_fingerprint": pedido.mp_fingerprint},
        }
        with mock.patch("core.notificacoes.enviar_confirmacao_de_compra"), self.captureOnCommitCallbacks(execute=True):
            pago, mudou = checkout.confirmar_pagamento(pedido, payment)
        self.assertTrue(mudou)
        self.assertEqual(pago.forma_pagamento, "boleto")
        self.assertEqual(pago.valor_cobrado, Decimal("4990.00"))
        self.assertEqual(pago.parcelas, 1)
        self.assertEqual(Pedido.FORMA_DA_VENDA["boleto"], "boleto")

    def test_tela_de_pagamento_com_o_boleto_aberto(self):
        pedido, _ = checkout.reservar_pedido(self.carrinho, usuario=self.user)
        Pedido.objects.filter(pk=pedido.pk).update(
            boleto_url="https://www.mercadopago.com.br/payments/555/ticket", boleto_linha="2379 3381",
            boleto_vencimento=timezone.now(),
        )
        html = self.client.get(reverse("pagamento", args=[self.carrinho.pk])).content.decode()
        self.assertIn('id="boleto-panel" class="payment-panel active"', html)
        self.assertIn('id="pix-panel" class="payment-panel"', html)
        self.assertNotIn('id="pix-panel" class="payment-panel active"', html)
        self.assertIn("let boletoAberto = true;", html)
        self.assertIn("2379 3381", html)

    def test_tela_de_pagamento_sem_boleto_tem_o_formulario(self):
        html = self.client.get(reverse("pagamento", args=[self.carrinho.pk])).content.decode()
        self.assertIn('data-method="boleto"', html)
        self.assertIn('id="boleto-form"', html)
        self.assertIn("let boletoAberto = false;", html)
        self.assertIn("Gerar boleto de R$ 4.990,00", html)

    def test_meus_pedidos_mostra_o_boleto_aberto(self):
        pedido, _ = checkout.reservar_pedido(self.carrinho, usuario=self.user)
        Pedido.objects.filter(pk=pedido.pk).update(
            boleto_url="https://www.mercadopago.com.br/payments/555/ticket", boleto_vencimento=timezone.now(),
        )
        html = self.client.get(reverse("meus_pedidos")).content.decode()
        self.assertIn("Boleto gerado", html)
        self.assertIn("Abrir o boleto", html)
