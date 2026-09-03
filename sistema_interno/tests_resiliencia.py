import json
from pathlib import Path
from unittest.mock import patch

from django.http import HttpResponse
from django.db import OperationalError
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.middleware import InternalResponseRecoveryMiddleware
from .resiliencia import pagina_interna_nao_encontrada, resposta_temporaria


class ResilienciaPainelTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_link_antigo_html_oferece_volta_sem_redirecionar(self):
        request = self.factory.get("/rota-antiga/")
        resposta = pagina_interna_nao_encontrada(request)
        self.assertContains(resposta, "Voltar ao painel", status_code=404)
        self.assertEqual(resposta["X-LS-Retryable"], "0")

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
        self.assertEqual(resposta.status_code, 404)

    @override_settings(DEBUG=False, SITE_URL="https://www.lazersport.com.br")
    def test_link_publico_preserva_pagina_e_filtros(self):
        request = self.factory.get("/loja/?busca=arduino")
        resposta = pagina_interna_nao_encontrada(request)
        self.assertEqual(resposta.url, "https://www.lazersport.com.br/loja/?busca=arduino")
        self.assertEqual(resposta["Cache-Control"], "no-store")

    def test_post_publico_nao_e_transferido(self):
        resposta = pagina_interna_nao_encontrada(self.factory.post("/loja/"))
        self.assertEqual(resposta.status_code, 404)

    @override_settings(DEBUG=False, SITE_URL="https://www.lazersport.com.br")
    def test_ponte_loja_nao_abre_home(self):
        from .views_site import LinkSitePublicoView
        resposta = LinkSitePublicoView().get(self.factory.get("/abrir-site/loja/"), tipo="loja")
        self.assertEqual(resposta.url, "https://www.lazersport.com.br/loja/")

    def test_erro_aplicacao_nao_vira_falha_transitoria(self):
        from .resiliencia import erro_interno
        request = self.factory.get("/clientes/")
        request.is_interno = True
        resposta = InternalResponseRecoveryMiddleware(erro_interno)(request)
        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(resposta["X-LS-Retryable"], "0")

    def test_contador_pedidos_visivel_inclusive_zero_sem_bloquear_renderizacao(self):
        base = (Path(__file__).parent / "templates/base_inner.html").read_text()
        self.assertIn('data-selo="count_pedidos" data-mostrar-zero="1" title="Pedidos em aberto">…</span>', base)

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

    @patch("core.middleware.close_old_connections")
    def test_conexao_do_banco_quebrada_fecha_e_volta_com_recuperacao(
        self, fechar_conexoes,
    ):
        middleware = InternalResponseRecoveryMiddleware(lambda _request: None)
        request = self.factory.get(
            "/ordens-servico/",
            HTTP_X_REQUESTED_WITH="LS-Soft-Navigation",
        )
        request.is_interno = True
        request.ls_request_id = "banco123"

        resposta = middleware.process_exception(
            request,
            OperationalError("conexão encerrada pelo servidor"),
        )

        fechar_conexoes.assert_called_once_with()
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta["X-LS-Recovery"], "banco-remoto")
        self.assertEqual(json.loads(resposta.content)["request_id"], "banco123")

    def test_processo_web_e_compativel_com_instancia_pequena_do_render(self):
        """Os mesmos limites de antes, agora lidos de onde eles moram.

        Eram onze parâmetros escritos na linha do Procfile. Passaram para
        `gunicorn.conf.py`, que é onde dá para explicar cada número e onde
        a hospedagem pode ajustá-los por variável de ambiente sem publicar
        código. O que este teste protege continua o mesmo: um processo,
        sem duplicar a aplicação em memória, com prazo folgado para a
        partida a frio.
        """
        raiz = Path(__file__).resolve().parent.parent
        procfile = (raiz / "Procfile").read_text(encoding="utf-8")
        python = (raiz / ".python-version").read_text(encoding="utf-8").strip()

        web = procfile.splitlines()[0]
        self.assertIn("gunicorn lazer.wsgi:application", web)
        self.assertIn("-c gunicorn.conf.py", web)
        self.assertNotIn("--preload", web)
        self.assertEqual(python, "3.12")

        conf = {}
        exec(
            compile(
                (raiz / "gunicorn.conf.py").read_text(encoding="utf-8"),
                "gunicorn.conf.py",
                "exec",
            ),
            conf,
        )
        self.assertEqual(conf["worker_class"], "gthread")
        self.assertEqual(conf["workers"], 1)
        self.assertEqual(conf["timeout"], 90)
        self.assertTrue(conf["bind"].startswith("0.0.0.0:"))
        self.assertFalse(conf.get("preload_app", False))

        # Threads sobem sem duplicar a aplicação: é o parâmetro certo para
        # instância pequena com banco remoto lento, porque enquanto uma
        # thread espera o Supabase a outra atende.
        self.assertGreaterEqual(conf["threads"], 4)
        self.assertLessEqual(conf["threads"], 16)

        # RECICLAR O ÚNICO WORKER É DERRUBAR O SITE.
        #
        # Era `--max-requests 600`: a cada 600 requisições o único
        # processo era morto e refeito, e tudo que chegava enquanto o
        # Django subia esperava a partida inteira -- o que estourava o
        # prazo do proxy e voltava como 502 sem explicação.
        self.assertEqual(conf["max_requests"], 0)

    def test_css_e_js_versionados_nao_sao_perguntados_de_novo(self):
        """Sete arquivos, 600 KB, uma pergunta por dia cada um.

        Todo CSS e JS do painel sai por `{% estatico %}`, que põe na URL
        um `?v=` calculado do CONTEÚDO: mudou o arquivo, mudou o
        endereço. Mesmo assim eles vinham com validade de um dia, então
        uma vez por dia o navegador perguntava "mudou?" para cada um --
        sete idas e voltas antes de a tela começar a desenhar, na
        primeira abertura do dia, que é quando a demora mais aparece.

        Ícone e imagem ficam de fora de propósito: eles podem ser
        trocados no lugar, e uma validade de dez anos esconderia a troca.
        """
        from django.conf import settings

        imutavel = settings.WHITENOISE_IMMUTABLE_FILE_TEST

        for url in (
            "/static/interno/interno_modern.css",
            "/static/interno/painel.js",
            "/static/interno/ls-soft-navigation.js",
            "/static/site/ls-page-loader.css",
            "/static/interno/vendor/bootstrap.min.css",
            "/static/interno/vendor/fonts/bootstrap-icons.woff2",
        ):
            self.assertTrue(imutavel("/disco" + url, url), url)

        for url in (
            "/static/interno/app-icone-192.png",
            "/static/images/logoofi.png",
            "/static/app/lazersport.apk",
        ):
            self.assertFalse(imutavel("/disco" + url, url), url)

    def test_o_painel_pede_os_estaticos_sempre_com_versao(self):
        """A validade de dez anos só é segura assim.

        Um `{% static %}` sem `?v=` num CSS ou JS marcado como imutável
        prenderia o navegador na versão velha por dez anos.
        """
        raiz = Path(__file__).resolve().parent
        base = (raiz / "templates" / "base_inner.html").read_text(encoding="utf-8")

        import re

        for pedido in re.findall(r"\{%\s*static\s+'([^']+)'\s*%\}", base):
            self.assertFalse(
                pedido.endswith((".css", ".js")),
                f"{pedido} sai por static sem versão; use estatico",
            )

    def test_health_check_do_render_nao_toca_no_banco(self):
        with patch(
            "django.db.backends.utils.CursorWrapper.execute",
            side_effect=AssertionError("health check tentou consultar o banco"),
        ):
            resposta = self.client.get("/healthz/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, b"ok")
