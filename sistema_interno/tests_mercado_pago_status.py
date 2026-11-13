from unittest import mock

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from . import mercado_pago_status as mp


class RespostaFalsa:
    def __init__(self, status, dados=None):
        self.status_code = status
        self._dados = dados or {}

    def json(self):
        return self._dados


class SituacaoMercadoPagoTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_tipo_e_final_da_chave_sem_expor_o_resto(self):
        self.assertEqual(mp.tipo_da_chave("TEST-123"), "teste")
        self.assertEqual(mp.tipo_da_chave("APP_USR-abc"), "producao")
        self.assertEqual(mp.tipo_da_chave(""), "vazia")
        self.assertEqual(mp.tipo_da_chave("xyz"), "desconhecida")
        self.assertEqual(mp.final_da_chave("APP_USR-1234567890-ab12"), "…ab12")
        self.assertEqual(mp.final_da_chave("curta"), "")

    @override_settings(MP_ACCESS_TOKEN="", MP_PUBLIC_KEY="APP_USR-chave-publica-1")
    def test_falta_chave_e_erro(self):
        s = mp.situacao_mercado_pago(consultar=False)
        self.assertEqual(s["nivel"], "erro")
        self.assertIn("MP_ACCESS_TOKEN", s["titulo"])

    @override_settings(MP_ACCESS_TOKEN="TEST-1111-2222-aaaa", MP_PUBLIC_KEY="TEST-bbbb-cccc-dddd")
    def test_credenciais_de_teste_dao_alerta(self):
        s = mp.situacao_mercado_pago(consultar=False)
        self.assertEqual((s["nivel"], s["modo"]), ("alerta", "TESTE"))

    @override_settings(MP_ACCESS_TOKEN="APP_USR-1111-2222-aaaa", MP_PUBLIC_KEY="TEST-bbbb-cccc-dddd")
    def test_tipos_misturados_avisam(self):
        s = mp.situacao_mercado_pago(consultar=False)
        self.assertEqual(s["modo"], "TESTE")
        self.assertTrue(any("tipos diferentes" in a for a in s["avisos"]))

    @override_settings(MP_ACCESS_TOKEN="APP_USR-1111-2222-aaaa", MP_PUBLIC_KEY="APP_USR-bbbb-cccc-dddd")
    def test_producao_com_conta_aceita(self):
        with mock.patch.object(mp.requests, "get", return_value=RespostaFalsa(200, {"tags": ["normal"], "site_id": "MLB"})) as get:
            s = mp.situacao_mercado_pago()
            mp.situacao_mercado_pago()
        self.assertEqual((s["nivel"], s["modo"]), ("ok", "PRODUÇÃO"))
        self.assertTrue(s["conta_aceita"])
        self.assertEqual(get.call_count, 1, "a conta fica guardada no cache")
        self.assertNotIn("APP_USR-1111", str(s))

    @override_settings(MP_ACCESS_TOKEN="APP_USR-1111-2222-aaaa", MP_PUBLIC_KEY="APP_USR-bbbb-cccc-dddd")
    def test_usuario_de_teste_com_chave_app_usr(self):
        with mock.patch.object(mp.requests, "get", return_value=RespostaFalsa(200, {"tags": ["test_user"], "site_id": "MLB"})):
            s = mp.situacao_mercado_pago()
        self.assertEqual(s["modo"], "TESTE")

    @override_settings(MP_ACCESS_TOKEN="APP_USR-1111-2222-aaaa", MP_PUBLIC_KEY="APP_USR-bbbb-cccc-dddd")
    def test_token_recusado_e_erro(self):
        with mock.patch.object(mp.requests, "get", return_value=RespostaFalsa(401)):
            s = mp.situacao_mercado_pago()
        self.assertEqual(s["nivel"], "erro")
        self.assertTrue(any("recusou" in a for a in s["avisos"]))

    @override_settings(MP_ACCESS_TOKEN="APP_USR-1111-2222-aaaa", MP_PUBLIC_KEY="APP_USR-bbbb-cccc-dddd")
    def test_api_fora_do_ar_nao_derruba_a_tela(self):
        with mock.patch.object(mp.requests, "get", side_effect=requests.Timeout):
            s = mp.situacao_mercado_pago()
        self.assertEqual(s["modo"], "PRODUÇÃO")
        self.assertTrue(any("Não foi possível" in a for a in s["avisos"]))


from django.contrib.auth.models import User
from django.test import TestCase

from .permissoes import atribuir_funcoes


@override_settings(
    ALLOWED_HOSTS=["interno.testserver", "testserver"],
    MP_ACCESS_TOKEN="TEST-1111-2222-aaaa-9876",
    MP_PUBLIC_KEY="TEST-bbbb-cccc-dddd-5432",
)
class CartaoMercadoPagoNoFinanceiroTests(TestCase):
    def test_financeiro_mostra_o_modo_sem_mostrar_a_chave(self):
        cache.clear()
        gestor = User.objects.create_user(username="gestora", password="senha-segura")
        atribuir_funcoes(gestor, ("gestao",))
        self.client.force_login(gestor)
        with mock.patch.object(mp.requests, "get", return_value=RespostaFalsa(200, {"tags": [], "site_id": "MLB"})):
            resposta = self.client.get("/financeiro/", HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Mercado Pago · <strong>TESTE</strong>", html=False)
        self.assertContains(resposta, "termina em …9876")
        self.assertNotContains(resposta, "TEST-1111-2222")
        self.assertNotContains(resposta, "TEST-bbbb")
