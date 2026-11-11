"""A coleta das jogadas (core/jogadas.py): cada Jogar, com data, quem e por onde.

O que estes testes protegem (o caso real: o Super Mario 64 jogado com a conta
de administrador não aparecia em lugar nenhum):

  * quem tem conta -- inclusive a equipe, marcada -- tem a jogada anotada;
  * a mesma pessoa no mesmo jogo em seguida (a página e o emulador, o
    recarregar) é uma jogada só; outro jogo é outra;
  * o visitante liberado é anotado (sem conta, com um número da sessão); o
    que já gastou as jogadas grátis e foi barrado, não;
  * "jogaram hoje com conta" conta os jogos de console (antes só os da casa);
  * o resumo por período (hoje, 7 dias, 30 dias...) e sem a equipe;
  * o painel Ao vivo mostra o período pedido, só para o superadministrador.
"""

import datetime as dt
import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import arena, jogadas
from .models import JogadaRegistrada
from .tests_ranking import _cliente

CASA = arena.JOGOS[0]["slug"]
OUTRO = arena.JOGOS[1]["slug"]


@override_settings(ALLOWED_HOSTS=["*"])
class RegistroTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def abrir(self, slug, **extra):
        corpo = {"jogo": slug, **extra}
        return self.client.post(reverse("jogos_abriu"), data=json.dumps(corpo), content_type="application/json")

    def test_com_conta_anota_e_a_equipe_vai_marcada(self):
        admin = User.objects.create_superuser("chefe", "chefe@exemplo.com", "x")
        self.client.force_login(admin)
        self.assertTrue(self.abrir(CASA, origem="emulador").json()["liberado"])
        jogada = JogadaRegistrada.objects.get()
        self.assertEqual((jogada.jogo, jogada.usuario, jogada.equipe, jogada.origem), (CASA, admin, True, "emulador"))

    def test_a_mesma_jogada_em_seguida_conta_uma_vez_e_outro_jogo_conta(self):
        self.client.force_login(_cliente("ana", "ana@exemplo.com"))
        self.abrir(CASA, origem="pagina")
        self.abrir(CASA, origem="emulador")  # o Jogar do emulador logo depois da página
        self.abrir(OUTRO)
        self.assertEqual(sorted(JogadaRegistrada.objects.values_list("jogo", flat=True)), sorted([CASA, OUTRO]))
        self.assertFalse(JogadaRegistrada.objects.get(jogo=CASA).equipe)

    def test_a_mesma_pessoa_depois_do_intervalo_conta_de_novo(self):
        self.client.force_login(_cliente("bia", "bia@exemplo.com"))
        self.abrir(CASA)
        sessao = self.client.session
        sessao[jogadas.SESSAO] = {CASA: 0}  # a anterior foi há muito tempo
        sessao.save()
        self.abrir(CASA)
        self.assertEqual(JogadaRegistrada.objects.filter(jogo=CASA).count(), 2)

    def test_visitante_liberado_anota_e_o_barrado_nao(self):
        self.abrir(CASA, gastar=True)
        self.abrir(OUTRO, gastar=True)
        visitante = JogadaRegistrada.objects.filter(usuario__isnull=True)
        self.assertEqual(visitante.count(), 2)
        self.assertTrue(all(len(j.visitante) == 16 for j in visitante))
        sessao = self.client.session
        sessao[jogadas.SESSAO] = {}
        sessao.save()
        barrado = self.abrir(arena.JOGOS[2]["slug"], gastar=True).json()
        self.assertFalse(barrado["liberado"])
        self.assertEqual(JogadaRegistrada.objects.count(), 2)


class ResumoTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", "ana@exemplo.com", "x", first_name="Ana")
        self.chefe = User.objects.create_user("chefe", "chefe@exemplo.com", "x", is_staff=True)
        agora = timezone.now()
        for jogo, usuario, dias in [
            ("super-mario-64", self.ana, 0), ("super-mario-64", self.chefe, 0), (CASA, self.ana, 3),
            (CASA, None, 20), ("super-mario-64", self.ana, 100), (CASA, self.ana, 400),
        ]:
            JogadaRegistrada.objects.create(
                jogo=jogo, usuario=usuario, equipe=bool(usuario and usuario.is_staff),
                visitante="" if usuario else "abc123", quando=agora - dt.timedelta(days=dias),
            )

    def test_os_periodos(self):
        contas = {p: jogadas.resumo(p)["jogadas"] for p in jogadas.PERIODOS}
        self.assertEqual(contas, {"hoje": 2, "semana": 3, "mes": 4, "trimestre": 4, "semestre": 5, "ano": 5})

    def test_pessoas_por_jogo_e_sem_a_equipe(self):
        mes = jogadas.resumo("mes")
        self.assertEqual((mes["com_conta"], mes["visitantes"], mes["equipe"]), (2, 1, 1))
        self.assertEqual(mes["por_jogo"], {"super-mario-64": 2, CASA: 2})
        self.assertEqual(mes["quem"][0]["nome"], "Ana")
        sem = jogadas.resumo("mes", com_equipe=False)
        self.assertEqual((sem["jogadas"], sem["com_conta"], sem["equipe"]), (3, 1, 0))

    def test_jogaram_hoje_com_conta_inclui_os_jogos_de_console(self):
        from .portal_jogos import contagens

        self.assertEqual(contagens()["jogadores_hoje"], 2)
        self.assertEqual(jogadas.jogadores_hoje(com_equipe=False), 1)


class PainelAoVivoTests(TestCase):
    INTERNO = {"HTTP_HOST": "interno.testserver"}
    URL = "/site/jogos/ao-vivo/"

    def setUp(self):
        self.admin = User.objects.create_superuser("chefe", "chefe@exemplo.com", "x")
        JogadaRegistrada.objects.create(jogo=CASA, usuario=self.admin, equipe=True)

    def test_o_periodo_e_a_equipe(self):
        self.client.force_login(self.admin)
        url = self.URL
        dados = self.client.get(url, {"formato": "json", "periodo": "mes"}, **self.INTERNO).json()
        self.assertEqual((dados["jogadas"]["periodo"], dados["jogadas"]["jogadas"]), ("mes", 1))
        sem = self.client.get(url, {"formato": "json", "periodo": "mes", "equipe": "0"}, **self.INTERNO).json()
        self.assertEqual(sem["jogadas"]["jogadas"], 0)
        pagina = self.client.get(url, {"periodo": "ano"}, **self.INTERNO)
        self.assertContains(pagina, "Jogadas · Ano")
        self.assertContains(pagina, "Quem jogou com conta")

    def test_so_o_superadministrador(self):
        self.client.force_login(User.objects.create_user("ana", "ana@exemplo.com", "x", is_staff=True))
        resposta = self.client.get(self.URL, {"formato": "json"}, **self.INTERNO)
        self.assertNotEqual(resposta.status_code, 200)
