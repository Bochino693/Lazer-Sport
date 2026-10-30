"""Ranking dos jogos do simulador e a partida grátis do visitante.

O que estes testes protegem:

  * o visitante joga uma partida de cada jogo: a sessão guarda quais já
    foram e o placar; ao entrar na conta, esse placar vai para o ranking;
  * o cadastrado guarda só o melhor resultado de cada jogo, e conta as
    partidas;
  * o ranking geral dá até 1.000 pontos por jogo (o recorde leva 1.000),
    para placar alto de um jogo não engolir os outros;
  * o nome no ranking nunca é o e-mail;
  * /jogos/partida/ e /jogos/ranking/ não viram "jogo" no endereço.
"""

import json
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import ranking
from .models import ClientePerfil, RecordeJogo


def _cliente(username, email, senha="x", **nome):
    """Cliente com telefone (sem ele o site manda completar o perfil)."""
    usuario = User.objects.create_user(username, email, senha, **nome)
    perfil, _ = ClientePerfil.objects.get_or_create(user=usuario)
    perfil.telefone = "11987654321"
    perfil.save()
    return usuario


def _postar(client, jogo, pontos):
    return client.post(
        reverse("jogos_partida"),
        data=json.dumps({"jogo": jogo, "pontos": pontos}),
        content_type="application/json",
    )


@mock.patch.object(ranking, "INTERVALO_MINIMO", 0)
class PartidaGratisTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_visitante_fica_marcado_e_nada_vai_para_o_banco(self):
        resposta = _postar(self.client, "dragon-bowling", 187)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"logado": False, "jogados": ["dragon-bowling"]})
        self.assertFalse(RecordeJogo.objects.exists())

        pagina = self.client.get(reverse("jogo", args=["dragon-bowling"]))
        self.assertContains(pagina, "data-console-cadastro")
        jogador = pagina.context["jogador"]
        self.assertFalse(jogador["logado"])
        self.assertEqual(jogador["jogados"], ["dragon-bowling"])

    def test_ao_entrar_o_placar_da_partida_gratis_entra_no_ranking(self):
        usuario = _cliente("bia", "bia@exemplo.com", "Senha#12345", first_name="Beatriz", last_name="Souza")
        _postar(self.client, "dragon-bowling", 187)
        self.client.post(reverse("login"), {"username": "bia", "password": "Senha#12345", "next": "/jogos/dragon-bowling/"})
        recorde = RecordeJogo.objects.get(usuario=usuario, jogo="dragon-bowling")
        self.assertEqual(recorde.pontos, 187)

        # na volta ao jogo, o aviso de "salvo no seu nome" aparece uma vez
        pagina = self.client.get(reverse("jogo", args=["dragon-bowling"]))
        self.assertEqual(pagina.context["salvos"], [{"jogo": "dragon-bowling", "titulo": "Dragon Bowling", "pontos": 187, "posicao": 1}])
        self.assertContains(pagina, "data-sim-salvo")
        self.assertEqual(self.client.get(reverse("jogo", args=["dragon-bowling"])).context["salvos"], [])

    def test_jogo_ou_placar_invalido(self):
        self.assertEqual(_postar(self.client, "nao-existe", 10).status_code, 400)
        self.assertEqual(_postar(self.client, "dragon-bowling", -1).status_code, 400)
        self.assertEqual(_postar(self.client, "dragon-bowling", "muito").status_code, 400)
        self.assertEqual(_postar(self.client, "dragon-bowling", ranking.PONTOS_MAXIMOS + 1).status_code, 400)

    def test_cadastro_vindo_do_jogo_volta_para_ele(self):
        self.client.get(reverse("registrar") + "?next=/jogos/hit-music/")
        self.assertEqual(self.client.session.get("conta_fluxo_destino"), "/jogos/hit-music/")

    def test_rotas_de_partida_e_ranking_nao_sao_jogos(self):
        self.assertEqual(reverse("jogos_partida"), "/jogos/partida/")
        self.assertEqual(self.client.get("/jogos/ranking/?jogo=hit-music").status_code, 200)
        self.assertEqual(self.client.get("/jogos/ranking/?jogo=nada").status_code, 404)


@mock.patch.object(ranking, "INTERVALO_MINIMO", 0)
class RecordeERankingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = _cliente("ana@exemplo.com", "ana@exemplo.com", first_name="Ana", last_name="Lima")
        self.rui = _cliente("rui", "rui@exemplo.com")

    def test_guarda_so_o_melhor_e_conta_as_partidas(self):
        self.client.force_login(self.ana)
        for pontos in (120, 300, 90):
            resposta = _postar(self.client, "strike-kids", pontos)
            self.assertTrue(resposta.json()["gravado"])
        recorde = RecordeJogo.objects.get(usuario=self.ana, jogo="strike-kids")
        self.assertEqual((recorde.pontos, recorde.partidas), (300, 3))
        self.assertEqual(resposta.json()["posicao"], {"posicao": 1, "pontos": 300})

    def test_ranking_geral_vale_ate_mil_por_jogo(self):
        # Hit Music conta em centésimos de %: 9.000 não pode engolir o boliche
        RecordeJogo.objects.create(usuario=self.ana, jogo="hit-music", pontos=9000, partidas=1)
        RecordeJogo.objects.create(usuario=self.rui, jogo="hit-music", pontos=4500, partidas=1)
        RecordeJogo.objects.create(usuario=self.rui, jogo="dragon-bowling", pontos=200, partidas=1)
        geral = ranking.ranking_geral()
        self.assertEqual([(linha["usuario"], linha["pontos"]) for linha in geral], [(self.rui.pk, 1500), (self.ana.pk, 1000)])
        jogo = ranking.ranking_do_jogo("hit-music")
        self.assertEqual([linha["pontos"] for linha in jogo], [9000, 4500])

    def test_nome_publico_nunca_e_o_email(self):
        self.assertEqual(ranking.nome_publico(self.ana), "Ana L.")
        sem_nome = User.objects.create_user("carla.dias@exemplo.com", "carla.dias@exemplo.com", "x")
        self.assertNotIn("@", ranking.nome_publico(sem_nome))

    def test_pagina_mostra_o_ranking_do_jogo(self):
        RecordeJogo.objects.create(usuario=self.ana, jogo="lazer-shot", pontos=1520, partidas=2)
        pagina = self.client.get(reverse("jogo", args=["lazer-shot"]))
        self.assertContains(pagina, "data-sim-ranking")
        self.assertContains(pagina, "Ana L.")
        self.assertNotContains(pagina, "ana@exemplo.com")
