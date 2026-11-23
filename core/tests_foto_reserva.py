"""A reserva das fotos quando o Cloudinary não entrega (LEIA-ME-V10, seção 128)."""

import json
from pathlib import Path

from django.http import HttpResponse
from django.test import SimpleTestCase, RequestFactory

from core import fotos_reserva
from core.middleware import FotoReservaMiddleware

ESTATICOS = Path(__file__).resolve().parent / "static"


class IndiceDasCopiasTests(SimpleTestCase):
    def test_o_indice_gravado_esta_em_dia_com_as_pastas(self):
        gravado = fotos_reserva.ARQUIVO_INDICE.read_text(encoding="utf-8")
        self.assertEqual(
            gravado, fotos_reserva.texto_do_indice(),
            "Rode `python manage.py fotos_reserva`: a lista das cópias locais ficou para trás.",
        )

    def test_toda_copia_do_indice_existe(self):
        indice = json.loads(fotos_reserva.ARQUIVO_INDICE.read_text(encoding="utf-8"))
        for grupo in indice.values():
            for url in grupo.values():
                self.assertTrue(url.startswith("/static/"), url)
                self.assertTrue((ESTATICOS / url[len("/static/"):]).is_file(), url)

    def test_as_fotos_do_site_que_nasceram_aqui_estao_no_indice(self):
        indice = fotos_reserva.montar_indice()
        # capa do showroom, capa de adesivo (objeto 3D), arte de kit, categoria, Black Friday
        for chave in ("air-game-home", "air-game-kids-alienigenas", "brinquedao-modelo-3", "kit-boliche-virtual"):
            self.assertIn(chave, indice["produtos"])
        self.assertIn("area-ninja", indice["categorias"])
        self.assertIn("arte-01", indice["black_friday"])


class ScriptNaPaginaTests(SimpleTestCase):
    def setUp(self):
        self.requisicao = RequestFactory().get("/")

    def passar(self, resposta):
        return FotoReservaMiddleware(lambda request: resposta)(self.requisicao)

    def test_pagina_com_foto_do_cloudinary_ganha_o_script_antes_do_head_fechar(self):
        html = (
            '<html><head><title>x</title></head><body>'
            '<img src="https://res.cloudinary.com/conta/image/upload/v1/x.jpg"></body></html>'
        )
        resposta = self.passar(HttpResponse(html, content_type="text/html; charset=utf-8"))
        corpo = resposta.content.decode()
        self.assertIn("ls-foto-reserva.js", corpo)
        self.assertIn('data-indice="/static/site/fotos-reserva.json"', corpo)
        self.assertLess(corpo.index("ls-foto-reserva.js"), corpo.index("</head>"))
        self.assertEqual(corpo.count("ls-foto-reserva.js"), 1)

    def test_pagina_sem_foto_do_cloudinary_sai_como_entrou(self):
        html = "<html><head></head><body><p>sem foto</p></body></html>"
        resposta = self.passar(HttpResponse(html, content_type="text/html"))
        self.assertEqual(resposta.content.decode(), html)

    def test_json_e_erro_nao_sao_mexidos(self):
        corpo = '{"foto": "https://res.cloudinary.com/conta/x.jpg"}'
        self.assertEqual(self.passar(HttpResponse(corpo, content_type="application/json")).content.decode(), corpo)
        html = '<html><head></head><body><img src="https://res.cloudinary.com/c/x.jpg"></body></html>'
        self.assertNotIn("ls-foto-reserva.js", self.passar(HttpResponse(html, status=404)).content.decode())

    def test_o_tamanho_declarado_acompanha_o_corpo(self):
        html = '<html><head></head><body><img src="https://res.cloudinary.com/c/x.jpg"></body></html>'
        resposta = HttpResponse(html, content_type="text/html")
        resposta["Content-Length"] = str(len(html))
        resposta = self.passar(resposta)
        self.assertEqual(int(resposta["Content-Length"]), len(resposta.content))

    def test_o_middleware_esta_ligado(self):
        from django.conf import settings

        self.assertIn("core.middleware.FotoReservaMiddleware", settings.MIDDLEWARE)


class ContratoDoScriptTests(SimpleTestCase):
    def setUp(self):
        self.js = (ESTATICOS / "site" / "ls-foto-reserva.js").read_text(encoding="utf-8")

    def test_so_age_no_erro_de_foto_do_cloudinary(self):
        self.assertIn("addEventListener('error'", self.js)
        self.assertIn("}, true);", self.js)  # na captura: o erro de <img> não sobe
        self.assertIn("res.cloudinary.com/", self.js)

    def test_sem_copia_entra_o_quadro_e_nunca_o_icone_quebrado(self):
        self.assertIn("Foto em atualização", self.js)
        self.assertIn("removeAttribute('srcset')", self.js)


class SemConexaoComOCloudinaryTests(SimpleTestCase):
    def test_o_topo_das_paginas_nao_abre_conexao_com_o_cloudinary(self):
        # seção 132: a conexão à toa também fazia o script da reserva entrar em toda página
        base = (Path(__file__).resolve().parent / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertNotIn('href="https://res.cloudinary.com"', base)
