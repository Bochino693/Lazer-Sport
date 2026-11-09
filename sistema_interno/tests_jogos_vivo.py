"""Ao vivo no portal (/site/jogos/ao-vivo/) e o menu separado em Jogos x Estúdio 3D.

O que se garante: só o superadministrador entra; a tela mostra quem está online e jogando (a
batida do portal), as partidas, o ranking e as contas novas; o JSON da atualização sozinha não leva
o id de ninguém; e, no menu, o bloco Lazer & Sport Games só tem jogos (o 3D mora no Estúdio 3D).
"""
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from core import presenca_jogos
from core.models import PartidasDoJogo, RecordeJogo

HOST = "interno.testserver"


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AoVivoTests(TestCase):
    def setUp(self):
        cache.clear()
        presenca_jogos.esquecer()
        self.addCleanup(presenca_jogos.esquecer)
        self.addCleanup(cache.clear)
        self.super = User.objects.create_superuser("chefe", "chefe@example.com", "senha-segura")

    def abrir(self, **extra):
        self.client.force_login(self.super)
        return self.client.get("/site/jogos/ao-vivo/", extra, HTTP_HOST=HOST)

    def test_so_o_superadministrador(self):
        comum = User.objects.create_user("comum", password="senha-segura", is_staff=True)
        self.client.force_login(comum)
        self.assertNotEqual(self.client.get("/site/jogos/ao-vivo/", HTTP_HOST=HOST).status_code, 200)
        self.assertContains(self.abrir(), "Ao vivo no portal")

    def test_mostra_quem_esta_jogando_as_partidas_e_o_ranking(self):
        # o resumo da presença é refeito no máximo a cada 2 s: o relógio anda entre as batidas e a tela
        relogio = iter([1000.0, 1001.0, 1002.0, 1010.0, 1010.0, 1010.0])
        self.enterContext(mock.patch.object(presenca_jogos, "_agora", side_effect=lambda: next(relogio, 1010.0)))
        presenca_jogos.bater("a" * 16, "aba1", "strike-kids")
        presenca_jogos.bater("b" * 16, "aba1", "strike-kids")
        presenca_jogos.bater("c" * 16, "aba1", "")
        PartidasDoJogo.objects.create(slug="strike-kids", partidas=51)
        PartidasDoJogo.objects.create(slug="nao-existe-mais", partidas=99)  # jogo apagado não entra
        jogadora = User.objects.create_user("ana", first_name="Ana", last_name="Lima")
        RecordeJogo.objects.create(usuario=jogadora, jogo="strike-kids", pontos=450)
        dados = self.abrir(formato="json").json()
        self.assertEqual(dados["online"], 3)
        self.assertEqual(dados["jogando_total"], 2)
        self.assertEqual(dados["jogando"][0]["nome"], "Strike Kids")
        self.assertEqual(dados["partidas_total"], 51)
        self.assertEqual(dados["mais_jogados"][0]["n"], 51)
        self.assertEqual(dados["ranking"][0]["nome"], "Ana L.")
        self.assertNotIn("usuario", dados["ranking"][0])  # nada de id de quem joga
        self.assertEqual(dados["campeoes"][0]["pontos"], 450)
        self.assertGreaterEqual(dados["contas"]["hoje"], 2)
        tela = self.abrir()
        self.assertContains(tela, 'data-vivo-n="online">3<')
        self.assertContains(tela, "Strike Kids")

    def test_sem_ninguem_a_tela_explica(self):
        tela = self.abrir()
        self.assertContains(tela, "Ninguém numa página de jogo neste minuto.")
        self.assertContains(tela, "O ranking começa com a primeira partida de um cadastrado.")

    def test_o_menu_separa_jogos_e_estudio_3d(self):
        html = self.abrir().content.decode()
        jogos = html[html.index("ls-nav-section--games"):html.index("ls-nav-section--estudio")]
        self.assertIn("/site/jogos/ao-vivo/", jogos)
        self.assertNotIn("/site/objetos-3d/", jogos)
        estudio = html[html.index("ls-nav-section--estudio"):]
        self.assertIn("/site/objetos-3d/", estudio)
        self.assertIn("/site/objetos-3d/montar/", estudio)

    def test_a_tela_do_3d_nao_tem_a_marca_dos_jogos(self):
        self.client.force_login(self.super)
        tela = self.client.get("/site/objetos-3d/", HTTP_HOST=HOST)
        self.assertContains(tela, "Estúdio 3D")
        self.assertNotContains(tela, "marca-games")
        self.assertNotContains(tela, "LAZER &amp; SPORT GAMES · 3D")
