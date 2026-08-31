import json
from pathlib import Path
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.middleware import InternalResponseRecoveryMiddleware
from .resiliencia import pagina_interna_nao_encontrada, resposta_temporaria


class ResilienciaPainelTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_link_antigo_html_volta_ao_painel(self):
        request = self.factory.get("/rota-antiga/")
        resposta = pagina_interna_nao_encontrada(request)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, "/?recuperado=pagina")

    def test_link_antigo_ajax_nao_finge_que_gravou(self):
        request = self.factory.post(
            "/rota-antiga/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        resposta = pagina_interna_nao_encontrada(request)
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(json.loads(resposta.content)["status"], "stale")

    def test_falha_temporaria_ajax_e_repetivel_mas_nao_reenvia(self):
        request = self.factory.get(
            "/clientes/",
            HTTP_X_REQUESTED_WITH="LS-Soft-Navigation",
        )
        request.ls_request_id = "teste123"
        resposta = resposta_temporaria(request)
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta["Retry-After"], "3")
        self.assertEqual(resposta["X-LS-Retryable"], "1")
        self.assertEqual(json.loads(resposta.content)["request_id"], "teste123")

    def test_tela_temporaria_nao_depende_do_contexto_do_banco(self):
        request = self.factory.get("/clientes/")
        resposta = resposta_temporaria(request)
        self.assertEqual(resposta.status_code, 503)
        self.assertContains(resposta, "A conexão oscilou", status_code=503)

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=["interno.testserver", "testserver"],
    )
    def test_url_antiga_real_usa_o_handler_do_subdominio(self):
        resposta = self.client.get(
            "/rota-interna-que-nao-existe/",
            HTTP_HOST="interno.testserver",
        )
        self.assertRedirects(
            resposta,
            "/?recuperado=pagina",
            fetch_redirect_response=False,
        )

    def test_middleware_converte_falha_do_proxy_sem_mascarar_site_publico(self):
        middleware = InternalResponseRecoveryMiddleware(
            lambda _request: HttpResponse(status=502)
        )
        request = self.factory.get("/clientes/")
        request.is_interno = True
        self.assertEqual(middleware(request).status_code, 503)

        request_publico = self.factory.get("/loja/")
        request_publico.is_interno = False
        self.assertEqual(middleware(request_publico).status_code, 502)

    def test_processo_web_e_compativel_com_instancia_pequena_do_render(self):
        raiz = Path(__file__).resolve().parent.parent
        procfile = (raiz / "Procfile").read_text(encoding="utf-8")
        python = (raiz / ".python-version").read_text(encoding="utf-8").strip()

        web = procfile.splitlines()[0]
        self.assertIn("--bind 0.0.0.0:$PORT", web)
        self.assertIn("--workers 1", web)
        self.assertIn("--threads 4", web)
        self.assertIn("--timeout 90", web)
        self.assertNotIn("--preload", web)
        self.assertEqual(python, "3.12")

    def test_health_check_do_render_nao_toca_no_banco(self):
        with patch(
            "django.db.backends.utils.CursorWrapper.execute",
            side_effect=AssertionError("health check tentou consultar o banco"),
        ):
            resposta = self.client.get("/healthz/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, b"ok")
