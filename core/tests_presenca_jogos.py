"""A conta de gente online e de quem joga cada jogo (core/presenca_jogos.py).

O que se garante:
* a batida só entra por POST, com corpo pequeno, do próprio site, e com o
  número do aparelho e da aba no formato certo;
* a conta é por aparelho: duas abas do mesmo navegador são uma pessoa, e
  quem joga um jogo conta uma vez nele;
* a aba que não bate há 75 s sai da conta; o "saí" tira na hora;
* jogo inventado não vira linha da conta; robô não entra; quem bate demais
  leva 429; aparelho novo demais num minuto não infla a conta;
* nada vai para o banco, e o portal e as páginas de jogo trazem o script.
"""
import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import arena, presenca_jogos

CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


class Relogio:
    """O relógio da conta, na mão do teste."""

    def __init__(self):
        self.agora = 10_000.0

    def __call__(self):
        return self.agora

    def andar(self, segundos):
        self.agora += segundos


class PresencaTests(TestCase):
    def setUp(self):
        cache.clear()
        presenca_jogos.esquecer()
        self.addCleanup(presenca_jogos.esquecer)
        self.relogio = Relogio()
        trocar = mock.patch.object(presenca_jogos, "_agora", self.relogio)
        trocar.start()
        self.addCleanup(trocar.stop)
        self.url = reverse("jogos_presenca")

    def bater(self, aparelho="a" * 20, aba="aba001", jogo="", saiu=False, ua=CHROME, **extra):
        self.relogio.andar(1)
        corpo = {"aparelho": aparelho, "aba": aba, "jogo": jogo}
        if saiu:
            corpo["saiu"] = True
        return self.client.post(self.url, json.dumps(corpo), content_type="text/plain;charset=UTF-8",
                                HTTP_USER_AGENT=ua, **extra)

    def test_so_post(self):
        self.assertEqual(self.client.get(self.url, HTTP_USER_AGENT=CHROME).status_code, 405)

    def test_a_batida_conta_e_devolve_a_conta(self):
        resposta = self.bater()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Cache-Control"], "no-store")
        dados = resposta.json()
        self.assertEqual(dados["online"], 1)
        self.assertEqual(dados["jogando"], {})
        self.assertEqual(dados["intervalo"], presenca_jogos.INTERVALO)
        self.assertEqual(self.bater(aparelho="b" * 20, jogo="strike-kids").json(),
                         {"online": 2, "jogando": {"strike-kids": 1}, "intervalo": presenca_jogos.INTERVALO})

    def test_duas_abas_do_mesmo_aparelho_sao_uma_pessoa(self):
        self.bater(aba="portal1")
        dados = self.bater(aba="jogo001", jogo="dragon-bowling").json()
        self.assertEqual(dados["online"], 1)
        self.assertEqual(dados["jogando"], {"dragon-bowling": 1})
        # a mesma pessoa com o mesmo jogo em duas abas conta uma vez nele
        dados = self.bater(aba="jogo002", jogo="dragon-bowling").json()
        self.assertEqual(dados["jogando"], {"dragon-bowling": 1})

    def test_o_sai_tira_so_a_aba_e_depois_o_aparelho(self):
        self.bater(aba="portal1")
        self.bater(aba="jogo001", jogo="lazer-shot")
        dados = self.bater(aba="jogo001", saiu=True).json()
        self.assertEqual(dados, {"online": 1, "jogando": {}, "intervalo": presenca_jogos.INTERVALO})
        self.assertEqual(self.bater(aba="portal1", saiu=True).json()["online"], 0)

    def test_quem_para_de_bater_sai_da_conta(self):
        self.bater(aparelho="a" * 20, jogo="hit-music")
        self.relogio.andar(40)
        self.assertEqual(self.bater(aparelho="b" * 20).json()["online"], 2)
        self.relogio.andar(presenca_jogos.VALIDADE)
        dados = self.bater(aparelho="b" * 20).json()
        self.assertEqual(dados["online"], 1)
        self.assertEqual(dados["jogando"], {})
        self.assertEqual(presenca_jogos.resumo(), {"online": 1, "jogando": {}})

    def test_jogo_que_nao_existe_nao_entra_na_conta(self):
        dados = self.bater(jogo="jogo-inventado").json()
        self.assertEqual(dados, {"online": 1, "jogando": {}, "intervalo": presenca_jogos.INTERVALO})
        self.assertEqual(self.bater(aba="aba002", jogo="<script>").json()["jogando"], {})
        # um jogo da casa entra
        self.assertIn("craque-de-botao", arena.JOGOS_POR_SLUG)
        self.assertEqual(self.bater(aba="aba003", jogo="craque-de-botao").json()["jogando"], {"craque-de-botao": 1})

    def test_corpo_grande_ou_invalido(self):
        grande = json.dumps({"aparelho": "a" * 20, "aba": "aba001", "jogo": "x" * 600})
        resposta = self.client.post(self.url, grande, content_type="text/plain", HTTP_USER_AGENT=CHROME)
        self.assertEqual(resposta.status_code, 413)
        resposta = self.client.post(self.url, "{nada", content_type="text/plain", HTTP_USER_AGENT=CHROME)
        self.assertEqual(resposta.status_code, 400)
        resposta = self.client.post(self.url, "[1, 2]", content_type="text/plain", HTTP_USER_AGENT=CHROME)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.bater(aparelho="curto").status_code, 400)
        self.assertEqual(self.bater(aparelho="a" * 20, aba="com espaço").status_code, 400)
        self.assertEqual(presenca_jogos.resumo()["online"], 0)

    def test_robo_nao_entra_na_conta(self):
        for ua in ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                   "curl/8.4.0", "python-requests/2.32", "Mozilla/5.0 HeadlessChrome/120.0", "SomeCrawler/1.0", ""):
            with self.subTest(ua=ua):
                self.assertEqual(self.bater(ua=ua).status_code, 204)
        # robô de IA nem passa pelo escudo dos jogos
        self.assertEqual(self.bater(ua="Mozilla/5.0 (compatible; GPTBot/1.2)").status_code, 403)
        self.assertEqual(presenca_jogos.resumo()["online"], 0)

    def test_de_outro_site_nao(self):
        self.assertEqual(self.bater(HTTP_ORIGIN="https://outro-site.com").status_code, 403)
        self.assertEqual(self.bater(HTTP_ORIGIN="http://testserver").status_code, 200)
        self.assertEqual(self.bater(HTTP_ORIGIN="http://www.testserver").status_code, 200)

    def test_quem_bate_demais_espera(self):
        for _ in range(presenca_jogos.BATIDAS_POR_MINUTO):
            self.assertEqual(self.bater().status_code, 200)
        resposta = self.bater()
        self.assertEqual(resposta.status_code, 429)
        self.assertEqual(resposta.json()["intervalo"], 60)
        # passado o minuto, volta
        self.relogio.andar(60)
        self.assertEqual(self.bater().status_code, 200)

    def test_aba_demais_no_mesmo_aparelho_nao_cresce(self):
        for i in range(presenca_jogos.ABAS_POR_APARELHO + 4):
            self.bater(aba=f"aba{i:03d}")
        self.assertEqual(len(presenca_jogos._aparelhos["a" * 20]["abas"]), presenca_jogos.ABAS_POR_APARELHO)

    def test_aparelho_novo_demais_num_minuto_nao_infla_a_conta(self):
        with mock.patch.object(presenca_jogos, "NOVOS_POR_MINUTO", 3):
            for i in range(6):
                self.bater(aparelho=f"aparelho{i:012d}")
            self.assertEqual(presenca_jogos.resumo()["online"], 3)
            # passado o minuto, entra gente nova de novo (os de antes já venceram)
            self.relogio.andar(presenca_jogos.VALIDADE + 1)
            self.bater(aparelho="aparelho-depois-000")
            self.assertEqual(presenca_jogos.resumo()["online"], 1)

    def test_nada_vai_para_o_banco(self):
        # o jogo da casa nem consulta o catálogo; o cadastrado sai do cache do catálogo
        with self.assertNumQueries(0):
            self.bater(jogo="strike-kids")
            self.bater(saiu=True)
        self.bater(jogo="um-cadastrado")
        with self.assertNumQueries(0):
            self.bater(aba="aba002", jogo="um-cadastrado")


class PresencaNasPaginasTests(TestCase):
    """O portal e as páginas de jogo trazem o script; o resto do site, não."""

    def setUp(self):
        cache.clear()
        presenca_jogos.esquecer()
        self.addCleanup(presenca_jogos.esquecer)
        self.relogio = Relogio()
        trocar = mock.patch.object(presenca_jogos, "_agora", self.relogio)
        trocar.start()
        self.addCleanup(trocar.stop)

    def test_portal_traz_o_script_e_a_conta(self):
        presenca_jogos.bater("x" * 20, "aba001", "strike-kids")
        self.relogio.andar(1)
        presenca_jogos.bater("y" * 20, "aba001", "")
        self.relogio.andar(1)
        resposta = self.client.get(reverse("jogos"), HTTP_USER_AGENT=CHROME)
        self.assertContains(resposta, "site/paginas/presenca-jogos.js")
        self.assertContains(resposta, f'data-presenca-url="{reverse("jogos_presenca")}" data-jogo=""')
        self.assertEqual(resposta.context["presenca"], {"online": 2, "jogando": {"strike-kids": 1}})

    def test_pagina_do_jogo_da_casa_segue_o_endereco(self):
        resposta = self.client.get(reverse("jogo", args=["strike-kids"]), HTTP_USER_AGENT=CHROME)
        self.assertContains(resposta, 'data-jogo="auto"')

    def test_o_jogo_abre_no_quadro_do_launcher(self):
        # o launcher abre o jogo num quadro do próprio site (app-jogos.js); outro site, não
        for url in (reverse("jogo", args=["strike-kids"]) + "?app=1", reverse("jogo", args=["dragon-bowling"])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, HTTP_USER_AGENT=CHROME)["X-Frame-Options"], "SAMEORIGIN")

    def test_um_jogo_cadastrado_nao_pode_ter_o_endereco_da_presenca(self):
        from django.core.exceptions import ValidationError

        from .models import JogoCadastrado

        jogo = JogoCadastrado(nome="Presença", slug="presenca", endereco="https://exemplo.com/jogo/")
        with self.assertRaises(ValidationError) as erro:
            jogo.clean()
        self.assertIn("slug", erro.exception.message_dict)

    def test_a_loja_nao_bate(self):
        resposta = self.client.get(reverse("home"), HTTP_USER_AGENT=CHROME)
        self.assertNotContains(resposta, "presenca-jogos.js")
