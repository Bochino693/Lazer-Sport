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
