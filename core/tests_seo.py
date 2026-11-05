"""O site nas buscas: páginas por tema, dados estruturados, mapa do site e cartão.

O que se garante:
* /boliche/, /fliperama/ e /brinquedos-para-shopping/ abrem com H1, título,
  descrição e dados estruturados (trilha, perguntas e lista) que são JSON
  de verdade -- JSON quebrado o Google descarta calado;
* toda página pública tem o cartão de compartilhamento, o robots e os
  dados da empresa; a verificação do Search Console só sai configurada;
* o mapa do site fala www.lazersport.com.br (e não o "example.com" do
  cadastro Sites), traz os temas e deixa de fora o brinquedo inativo;
* os endereços do site antigo redirecionam de vez (301).
"""
import json
import re
from html import escape

from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse

from . import paginas_tema
from .models import Brinquedos


def json_ld(html):
    blocos = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, flags=re.S)
    return [json.loads(b) for b in blocos]


class PaginasPorTemaTests(TestCase):
    def test_cada_tema_abre_com_o_que_o_buscador_le(self):
        for slug, dados in paginas_tema.TEMAS.items():
            with self.subTest(tema=slug):
                resposta = self.client.get(reverse("pagina_tema", args=[slug]))
                self.assertEqual(resposta.status_code, 200)
                html = resposta.content.decode()
                self.assertIn(f"<title>{dados['titulo_seo'].replace('&', '&amp;')}</title>", html)
                self.assertIn(f'<meta name="description" content="{escape(dados["descricao_seo"])}', html)
                self.assertEqual(html.count("<h1"), 1)
                self.assertIn(f"https://www.lazersport.com.br/{slug}/", html)
                tipos = set()
                for bloco in json_ld(html):
                    for no in bloco.get("@graph", [bloco]):
                        tipos.update(no["@type"] if isinstance(no["@type"], list) else [no["@type"]])
                self.assertTrue({"BreadcrumbList", "FAQPage", "ItemList", "Organization", "WebSite"} <= tipos, tipos)

    def test_o_boliche_mostra_as_maquinas_de_boliche_e_o_catalogo(self):
        Brinquedos.objects.create(nome_brinquedo="Boliche Virtual", descricao="Boliche de arcade", avaliacao=5)
        Brinquedos.objects.create(nome_brinquedo="Pula-pula", descricao="cama elástica", avaliacao=5)
        html = self.client.get(reverse("pagina_tema", args=["boliche"])).content.decode()
        self.assertIn("Dragon Bowling", html)
        self.assertIn("Strike Kids", html)
        self.assertIn(reverse("jogo", args=["dragon-bowling"]), html)
        self.assertIn("Boliche Virtual", html)
        self.assertNotIn("Pula-pula", html)
        self.assertIn("wa.me/5511960563135?text=", html)

    def test_os_temas_estao_no_topo_e_no_rodape_de_toda_pagina(self):
        html = self.client.get(reverse("brinquedos")).content.decode()
        for slug in paginas_tema.TEMAS:
            self.assertIn(f'href="{reverse("pagina_tema", args=[slug])}"', html)

    def test_tema_desconhecido_nao_vira_pagina(self):
        self.assertNotEqual(self.client.get("/boliches-baratos/").status_code, 200)


class CabecaDasPaginasTests(TestCase):
    def test_cartao_de_compartilhamento_e_dados_da_empresa(self):
        html = self.client.get(reverse("brinquedos")).content.decode()
        self.assertIn('<meta property="og:image" content="https://www.lazersport.com.br/static/images/compartilhar/', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn("max-image-preview:large", html)
        self.assertNotIn("Lazer & Sports", html)
        empresa = [n for b in json_ld(html) for n in b.get("@graph", []) if n.get("@type") == "Organization"][0]
        self.assertEqual(empresa["address"]["postalCode"], "02679-110")
        self.assertIn("https://www.instagram.com/lazersportbrinquedos", empresa["sameAs"])

    def test_verificacao_do_search_console_so_sai_configurada(self):
        self.assertNotIn("google-site-verification", self.client.get(reverse("brinquedos")).content.decode())
        with override_settings(GOOGLE_SITE_VERIFICATION="codigo-do-google", BING_SITE_VERIFICATION="codigo-do-bing"):
            html = self.client.get(reverse("brinquedos")).content.decode()
        self.assertIn('<meta name="google-site-verification" content="codigo-do-google">', html)
        self.assertIn('<meta name="msvalidate.01" content="codigo-do-bing">', html)

    def test_a_home_descreve_a_fabrica_como_negocio_local(self):
        html = self.client.get(reverse("home")).content.decode()
        negocio = [b for b in json_ld(html) if "LocalBusiness" in (b.get("@type") or [])][0]
        self.assertEqual(negocio["address"]["addressLocality"], "São Paulo")
        self.assertEqual(negocio["telephone"], "+55-11-96056-3135")
        self.assertIn("geo", negocio)

    def test_a_pagina_do_produto_compartilha_a_foto_do_brinquedo(self):
        b = Brinquedos.objects.create(nome_brinquedo="Boliche Virtual", descricao="Boliche de arcade", avaliacao=5)
        html = self.client.get(reverse("brinquedo_detalhe", args=[b.pk])).content.decode()
        self.assertIn('<meta property="og:type" content="product">', html)
        self.assertIn('<meta property="og:title" content="Boliche Virtual | Lazer & Sport Brinquedos">', html)


class MapaDoSiteTests(TestCase):
    def test_o_mapa_fala_o_endereco_publico_e_so_o_que_abre(self):
        Site.objects.update_or_create(pk=1, defaults={"domain": "example.com", "name": "example.com"})
        ativo = Brinquedos.objects.create(nome_brinquedo="Ativo", descricao="x", avaliacao=5)
        inativo = Brinquedos.objects.create(nome_brinquedo="Inativo", descricao="x", avaliacao=5, ativo=False)
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("example.com", xml)
        self.assertIn("<loc>https://www.lazersport.com.br/</loc>", xml)
        for slug in paginas_tema.TEMAS:
            self.assertIn(f"<loc>https://www.lazersport.com.br/{slug}/</loc>", xml)
        self.assertIn("https://www.lazersport.com.br/loja/", xml)
        self.assertIn(reverse("brinquedo_detalhe", args=[ativo.pk]), xml)
        self.assertNotIn(reverse("brinquedo_detalhe", args=[inativo.pk]), xml)


class EnderecosAntigosTests(TestCase):
    def test_os_enderecos_do_wordpress_mudaram_de_vez(self):
        for antigo in ("/categoria-produto/fliperama/", "/fabricante-de-brinquedo/x/", "/produto-tag/boliche/", "/lancamentos/"):
            with self.subTest(antigo=antigo):
                self.assertEqual(self.client.get(antigo).status_code, 301)
        # o curinga (endereço que nunca existiu) continua temporário
        self.assertEqual(self.client.get("/qualquer-coisa-que-nao-existe/").status_code, 302)


class JogosNaBuscaTests(TestCase):
    """Quem busca "boliche virtual" quer jogar: a página do jogo responde isso."""

    def test_o_dragon_bowling_e_boliche_virtual_online_gratis(self):
        html = self.client.get(reverse("jogo", args=["dragon-bowling"])).content.decode()
        self.assertIn("<title>Boliche virtual online grátis: jogue o Dragon Bowling | Lazer &amp; Sport</title>", html)
        self.assertIn("Boliche virtual online grátis: jogue no navegador ou no celular", html)
        self.assertIn(f'href="{reverse("pagina_tema", args=["jogos-de-boliche"])}"', html)
        jogo = [b for b in json_ld(html) if b.get("@type") == "VideoGame"][0]
        self.assertEqual(jogo["name"], "Dragon Bowling")
        self.assertTrue(jogo["isAccessibleForFree"])
        self.assertEqual(jogo["url"], "https://www.lazersport.com.br/jogos/dragon-bowling/")

    def test_todo_jogo_tem_texto_de_busca_e_tema_que_existe(self):
        from . import arena
        for jogo in arena.JOGOS:
            with self.subTest(jogo=jogo["slug"]):
                busca = paginas_tema.busca_do_jogo(jogo["slug"])
                self.assertTrue(busca.get("titulo") and busca.get("descricao") and busca.get("frase"))
                self.assertIn(busca["tema"], paginas_tema.TEMAS)

    def test_jogos_de_boliche_poe_o_jogo_na_frente(self):
        html = self.client.get(reverse("pagina_tema", args=["jogos-de-boliche"])).content.decode()
        self.assertIn("Jogar Dragon Bowling", html)
        self.assertIn("Jogar Strike Kids", html)
        self.assertIn("Quer essa máquina de verdade no seu espaço?", html)

    def test_o_topo_mostra_so_os_destaques_e_o_rodape_todos(self):
        html = self.client.get(reverse("brinquedos")).content.decode()
        topo = html[html.index('class="search-suggestions"'):html.index("CONTEÚDO DINÂMICO")]
        self.assertIn(reverse("pagina_tema", args=["jogos-de-boliche"]), topo)
        self.assertNotIn(reverse("pagina_tema", args=["maquina-de-boxe"]), topo)
        rodape = html[html.index('<footer class="ls-footer">'):]
        for slug in paginas_tema.TEMAS:
            self.assertIn(reverse("pagina_tema", args=[slug]), rodape)


class IndexNowTests(TestCase):
    def test_a_chave_so_aparece_configurada(self):
        self.assertEqual(self.client.get("/abcdef1234567890.txt").status_code, 404)
        with override_settings(INDEXNOW_KEY="abcdef1234567890"):
            resposta = self.client.get("/abcdef1234567890.txt")
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta.content.decode(), "abcdef1234567890")
            self.assertEqual(self.client.get("/outrachave12345.txt").status_code, 404)

    def test_o_aviso_leva_as_paginas_do_sitemap(self):
        from . import indexnow
        enviados = {}

        def enviar(url, corpo):
            enviados.update(url=url, corpo=corpo)
            return 202

        with override_settings(INDEXNOW_KEY="abcdef1234567890"):
            resultado = indexnow.avisar(indexnow.enderecos_do_sitemap(), enviar=enviar)
        self.assertEqual(resultado["status"], 202)
        self.assertEqual(enviados["corpo"]["host"], "www.lazersport.com.br")
        self.assertEqual(enviados["corpo"]["keyLocation"], "https://www.lazersport.com.br/abcdef1234567890.txt")
        self.assertIn("https://www.lazersport.com.br/jogos-de-boliche/", enviados["corpo"]["urlList"])
        self.assertIn("https://www.lazersport.com.br/jogos/dragon-bowling/", enviados["corpo"]["urlList"])

    def test_sem_chave_o_comando_explica(self):
        from django.core.management import CommandError, call_command
        with self.assertRaisesMessage(CommandError, "INDEXNOW_KEY"):
            call_command("avisar_buscadores")
