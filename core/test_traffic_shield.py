from django.test import SimpleTestCase

from core.healthcheck import HealthcheckWSGI
from core.traffic_shield import TrafficShieldWSGI


def _environ(path="/", query="", host="www.lazersport.com.br", ua="browser"):
    return {
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "HTTP_HOST": host,
        "HTTP_USER_AGENT": ua,
        "REQUEST_METHOD": "GET",
        "REMOTE_ADDR": "203.0.113.8",
    }


def _call(app, environ):
    result = {}

    def start(status, headers):
        result["status"] = status
        result["headers"] = dict(headers)

    result["body"] = b"".join(app(environ, start))
    return result


class TrafficShieldTests(SimpleTestCase):
    def setUp(self):
        self.calls = 0

        def django(environ, start_response):
            self.calls += 1
            start_response("200 OK", [("Content-Length", "2")])
            return [b"ok"]

        self.shield = TrafficShieldWSGI(django)

    def test_probe_php_nunca_entra_no_django(self):
        response = _call(self.shield, _environ("/wp-content/inputs.php"))
        self.assertTrue(response["status"].startswith("404"))
        self.assertEqual(self.calls, 0)

    def test_filter_cat_encerra_sem_redirecionar(self):
        response = _call(self.shield, _environ("/loja/", "filter_cat=1,2,3"))
        self.assertTrue(response["status"].startswith("410"))
        self.assertNotIn("Location", response["headers"])
        self.assertEqual(self.calls, 0)

    def test_limite_publico_nao_bloqueia_painel(self):
        acquired = [self.shield.public_slots.acquire(blocking=False) for _ in range(4)]
        self.assertTrue(all(acquired))
        try:
            public = _call(self.shield, _environ("/brinquedos/"))
            internal = _call(self.shield, _environ("/", host="interno.lazersport.com.br"))
        finally:
            for _ in acquired:
                self.shield.public_slots.release()
        self.assertTrue(public["status"].startswith("503"))
        self.assertTrue(internal["status"].startswith("200"))

    def test_healthcheck_fica_fora_do_limite(self):
        wrapped = HealthcheckWSGI(self.shield)
        response = _call(wrapped, _environ("/healthz/"))
        self.assertTrue(response["status"].startswith("200"))
        self.assertEqual(response["body"], b"ok")

    def test_bot_recebe_429_depois_da_cota(self):
        self.shield.bot_limit = 4
        env = _environ("/brinquedos/", ua="meta-externalagent/1.1")
        for _ in range(4):
            self.assertTrue(_call(self.shield, env)["status"].startswith("200"))
        self.assertTrue(_call(self.shield, env)["status"].startswith("429"))

    def _ocupar_todas_as_vagas(self):
        acquired = [self.shield.public_slots.acquire(blocking=False) for _ in range(4)]
        self.assertTrue(all(acquired))
        return acquired

    def _liberar(self, acquired):
        for _ in acquired:
            self.shield.public_slots.release()

    def test_estatico_nunca_recebe_503_mesmo_com_as_vagas_tomadas(self):
        """Um CSS cortado é uma página que abre sem estilo: estático não disputa vaga."""
        acquired = self._ocupar_todas_as_vagas()
        try:
            for caminho in (
                "/static/site/ls-base.css",
                "/static/images/logoofi.png",
                "/media/brinquedos/foto.webp",
                "/favicon.ico",
                "/robots.txt",
                "/manifest.webmanifest",
                "/sw.js",
            ):
                resposta = _call(self.shield, _environ(caminho))
                self.assertTrue(resposta["status"].startswith("200"), caminho)
            # a página pesada continua sendo cortada
            self.assertTrue(_call(self.shield, _environ("/brinquedos/"))["status"].startswith("503"))
        finally:
            self._liberar(acquired)
        self.assertEqual(self.calls, 7)

    def test_estatico_nao_devolve_vaga_que_nao_pegou(self):
        """Passar direto não pode 'liberar' uma vaga a mais (o semáforo é limitado)."""
        for _ in range(10):
            _call(self.shield, _environ("/static/site/ls-base.css"))
        acquired = self._ocupar_todas_as_vagas()
        try:
            # a 5ª vaga não existe: o estático não a criou
            self.assertFalse(self.shield.public_slots.acquire(blocking=False))
        finally:
            self._liberar(acquired)

    def test_sonda_disfarcada_de_estatico_continua_barrada(self):
        for caminho in ("/static/.env", "/static/wp-admin/x.css", "/media/shell.php"):
            resposta = _call(self.shield, _environ(caminho))
            self.assertTrue(resposta["status"].startswith("404"), caminho)
        self.assertEqual(self.calls, 0)

    def test_pagina_parecida_com_estatico_ainda_ocupa_vaga(self):
        """Só o prefixo exato é leve: /staticos/ ou /robots.txt/x não passam direto."""
        acquired = self._ocupar_todas_as_vagas()
        try:
            for caminho in ("/staticos/", "/robots.txt/x", "/sw.js/", "/estatico/static/a.css"):
                self.assertTrue(_call(self.shield, _environ(caminho))["status"].startswith("503"), caminho)
        finally:
            self._liberar(acquired)
