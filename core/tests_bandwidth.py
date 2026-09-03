from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.middleware import BandwidthEconomyMiddleware


class BandwidthEconomyMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = BandwidthEconomyMiddleware(
            lambda request: HttpResponse("pagina pesada")
        )

    def test_filter_cat_legado_vira_redirecionamento_curto(self):
        request = self.factory.get(
            "/loja/?filter_cat=1,2,3&page=4&lixo=nao-preservar",
            HTTP_HOST="www.lazersport.com.br",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/loja/?page=4")
        self.assertIn("noindex", response["X-Robots-Tag"])

    def test_nao_interfere_no_painel_interno(self):
        request = self.factory.get(
            "/clientes/?filter_cat=1",
            HTTP_HOST="interno.lazersport.com.br",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_catalogo_atual_sem_filtro_legado_continua_normal(self):
        request = self.factory.get(
            "/loja/?categoria=3",
            HTTP_HOST="www.lazersport.com.br",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
