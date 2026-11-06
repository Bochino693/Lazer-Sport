"""O escudo dos jogos (core/escudo_jogos.py): robôs de IA, cópia em massa e o passe."""

import json
import time
from unittest import mock

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse

from . import escudo_jogos as escudo
from .tests_jogos_emulador import EmuladorNoSiteTests

NAVEGADOR = "Mozilla/5.0 (Linux; Android 14; Xiaomi) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"


def resolver(desafio, bits):
    """A conta do navegador (jogo-passe.js), feita aqui."""
    sorteio = desafio.split(".")[1]
    nonce = 0
    while escudo.zeros_do_comeco(sorteio, nonce) < bits:
        nonce += 1
    return str(nonce)


def pedir_passe(client, passe, nonce=None, sinais=None, desafio=None, **extra):
    desafio = desafio or passe["desafio"]
    corpo = {"desafio": desafio, "nonce": resolver(desafio, passe["bits"]) if nonce is None else nonce, "sinais": sinais or {"webdriver": False}}
    return client.post(passe["url"], json.dumps(corpo), content_type="application/json", **extra)


class EscudoTests(TestCase):
    """Com o jogo de disco (disco-teste) dos testes do emulador."""

    config = EmuladorNoSiteTests.config

    def setUp(self):
        EmuladorNoSiteTests.setUp(self)
        cache.clear()
        self.addCleanup(cache.clear)
        self.client.defaults["HTTP_USER_AGENT"] = NAVEGADOR

    def passe(self):
        return self.config(self.client.get(reverse("jogo_emulador", args=["disco-teste"])))["passe"]

    # ------------------------------------------------------------ robôs de IA e programas de cópia
    def test_robo_de_ia_nao_entra_nos_jogos_e_a_loja_continua_aberta(self):
        for ua in ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
                   "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", "CCBot/2.0 (https://commoncrawl.org/faq/)",
                   "Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)"):
            with self.subTest(ua=ua[:30]):
                self.assertEqual(self.client.get(reverse("jogos"), HTTP_USER_AGENT=ua).status_code, 403)
                self.assertEqual(self.client.get("/static/site/arena/jogos/boliche/index.html", HTTP_USER_AGENT=ua).status_code, 403)
                self.assertEqual(self.client.get(reverse("jogo_emulador", args=["disco-teste"]), HTTP_USER_AGENT=ua).status_code, 403)
                self.assertNotEqual(self.client.get("/robots.txt", HTTP_USER_AGENT=ua).status_code, 403)

    def test_buscador_continua_vendo_a_biblioteca(self):
        google = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        resposta = self.client.get(reverse("jogos"), HTTP_USER_AGENT=google)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("noai", resposta["X-Robots-Tag"])

    def test_programa_de_copia_nao_abre_o_reprodutor_nem_pede_passe(self):
        passe = self.passe()
        for ua in ("curl/8.5.0", "python-requests/2.32", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/130.0 Safari/537.36",
                   "Scrapy/2.11 (+https://scrapy.org)", "Wget/1.21"):
            with self.subTest(ua=ua[:20]):
                self.assertEqual(self.client.get(reverse("jogo_emulador", args=["disco-teste"]), HTTP_USER_AGENT=ua).status_code, 403)
                self.assertEqual(pedir_passe(self.client, passe, HTTP_USER_AGENT=ua).status_code, 403)
                # a biblioteca (o que o buscador e a prévia do WhatsApp leem) continua
                self.assertEqual(self.client.get(reverse("jogos"), HTTP_USER_AGENT=ua).status_code, 200)

    # ------------------------------------------------------------ a armadilha
    def test_quem_cai_na_armadilha_fica_fora_dos_jogos(self):
        self.assertContains(self.client.get(reverse("jogos")), 'class="pg-armadilha" href="/jogos/_acervo/"')
        self.assertEqual(self.client.get(escudo.ARMADILHA).status_code, 404)
        self.assertEqual(self.client.get(reverse("jogos")).status_code, 403)
        self.assertEqual(self.client.get(reverse("jogo_emulador", args=["disco-teste"])).status_code, 403)
        # outro navegador no mesmo IP (a rede da operadora) continua jogando
        self.assertEqual(self.client.get(reverse("jogos"), HTTP_USER_AGENT=NAVEGADOR + " outro").status_code, 200)
        # a loja não muda
        self.assertNotEqual(self.client.get("/robots.txt").status_code, 403)

    def test_a_armadilha_nao_marca_pre_carga_nem_buscador(self):
        self.client.get(escudo.ARMADILHA, HTTP_SEC_PURPOSE="prefetch")
        self.assertEqual(self.client.get(reverse("jogos")).status_code, 200)
        google = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        self.client.get(escudo.ARMADILHA, HTTP_USER_AGENT=google)
        self.assertEqual(self.client.get(reverse("jogos"), HTTP_USER_AGENT=google).status_code, 200)

    def test_robots_txt(self):
        texto = self.client.get("/robots.txt").content.decode()
        geral, ia = texto.split("# Os jogos da Lazer & Sport")
        self.assertIn("Disallow: /jogos/_acervo/", geral)
        self.assertIn("Disallow: /jogos/*/emulador/", geral)
        self.assertNotIn("Disallow: /jogos/\n", geral)  # a biblioteca continua nos buscadores
        for robo in ("GPTBot", "ClaudeBot", "CCBot", "Google-Extended", "PerplexityBot"):
            self.assertIn("User-agent: " + robo, ia)
        self.assertIn("Disallow: /jogos/\n", ia)
        self.assertIn("Disallow: /carrinho/", ia)

    # ------------------------------------------------------------ o passe
    def test_a_conta_certa_ganha_de_onde_baixar(self):
        passe = self.passe()
        self.assertEqual(passe["url"], reverse("jogo_passe", args=["disco-teste"]))
        self.assertEqual(passe["bits"], escudo.BITS)
        resposta = pedir_passe(self.client, passe)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Cache-Control"], "no-store")
        nomes = {a["nome"] for a in resposta.json()["arquivos"]}
        self.assertEqual(nomes, {"Jogo (Disc 1).cue", "Track 01.bin", "Track 02.bin"})

    def test_conta_errada_desafio_repetido_ou_mexido_ganha_outro_desafio(self):
        passe = self.passe()
        errada = pedir_passe(self.client, passe, nonce="1")
        # a chance de "1" acertar 16 bits é 1 em 65 mil: se acertar, o teste não diz nada
        if escudo.zeros_do_comeco(passe["desafio"].split(".")[1], 1) < passe["bits"]:
            self.assertEqual(errada.status_code, 409)
            self.assertIn("desafio", errada.json())
        self.assertEqual(pedir_passe(self.client, passe).status_code, 200)
        self.assertEqual(pedir_passe(self.client, passe).status_code, 409)  # a mesma resposta duas vezes
        quando, sorteio, bits, assinatura = self.passe()["desafio"].split(".")
        facil = f"{quando}.{sorteio}.1.{assinatura}"  # baixar a dificuldade quebra a assinatura
        self.assertEqual(pedir_passe(self.client, {**passe, "bits": 1}, desafio=facil).status_code, 409)

    def test_desafio_vencido(self):
        passe = self.passe()
        with mock.patch.object(escudo.time, "time", return_value=time.time() + escudo.VALIDADE + 5):
            resposta = pedir_passe(self.client, passe)
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json()["motivo"], "desafio vencido")

    def test_desafio_de_outro_navegador_nao_vale(self):
        passe = self.passe()
        self.assertEqual(pedir_passe(self.client, passe, HTTP_USER_AGENT=NAVEGADOR + " outro").status_code, 409)

    def test_navegador_controlado_por_programa_e_pedido_de_fora(self):
        passe = self.passe()
        self.assertEqual(pedir_passe(self.client, passe, sinais={"webdriver": True}).status_code, 403)
        self.assertEqual(pedir_passe(self.client, passe, HTTP_SEC_FETCH_SITE="cross-site").status_code, 403)
        self.assertEqual(pedir_passe(self.client, passe, HTTP_ORIGIN="https://copiador.example").status_code, 403)
        self.assertEqual(pedir_passe(self.client, passe, HTTP_SEC_FETCH_SITE="same-origin").status_code, 200)

    def test_quem_abre_jogo_demais_faz_mais_conta_e_depois_espera(self):
        with mock.patch.object(escudo, "_vezes", return_value=10):
            self.assertEqual(self.passe()["bits"], escudo.BITS + 2)
        with mock.patch.object(escudo, "_vezes", return_value=40):
            self.assertEqual(self.passe()["bits"], escudo.BITS + 6)
        passe = self.passe()
        with mock.patch.object(escudo, "_vezes", return_value=escudo.TETO):
            resposta = pedir_passe(self.client, passe)
        self.assertEqual(resposta.status_code, 429)
        self.assertIn("Retry-After", resposta)
        # a contagem de verdade sobe a cada passe
        for _ in range(3):
            self.assertEqual(pedir_passe(self.client, self.passe()).status_code, 200)
        self.assertEqual(escudo._vezes(RequestFactory().get("/", HTTP_USER_AGENT=NAVEGADOR)), 3)

    def test_a_pagina_do_jogo_tambem_nao_leva_o_endereco(self):
        resposta = self.client.get(reverse("jogo", args=["disco-teste"]))
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertNotIn("guardado_Track", html)
        self.assertIn('"passe"', html)
        self.assertIn("jogo-passe.js", html)

    def test_passe_de_jogo_que_nao_existe(self):
        resposta = self.client.post(reverse("jogo_passe", args=["nao-existe"]), "{}", content_type="application/json")
        self.assertEqual(resposta.status_code, 404)

    def test_sem_desafio_o_site_manda_um(self):
        resposta = self.client.post(reverse("jogo_passe", args=["disco-teste"]), "{}", content_type="application/json")
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json()["bits"], escudo.BITS)


class ApkEPasseTests(TestCase):
    def test_o_apk_leva_o_script_do_passe(self):
        # o APK usa config_do_emulador (com o caminho de dentro do app) e não pede passe
        from .jogos_apk_gerar import ARQUIVOS_DO_REPRODUTOR
        from .views_app_jogos import CASCA

        self.assertIn("site/paginas/jogo-passe.js", ARQUIVOS_DO_REPRODUTOR)
        self.assertIn("site/paginas/jogo-passe.js", CASCA)  # e o app sem internet também
