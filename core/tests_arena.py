"""Arena 3D, Lazer & Sport Jogos e o painel ao vivo da home.

O que estes testes protegem:

  * a página da arena abre inteira sem JavaScript (jogos, máquinas em 3D,
    fotos de todas as máquinas) e cada jogo aponta para arquivos que
    existem -- capa, pôster, script e cada arte que o script carrega;
  * nenhuma arte de terceiros (capas de música, logos de patrocinador)
    entra na pasta dos jogos;
  * só ganha 3D a máquina que tem objeto de verdade (o gabinete de
    boliche); as outras ficam com as fotos reais, sem gabinete inventado;
  * o painel ao vivo responde com totais e pode ser guardado em cache;
  * a home troca "Nossos Parceiros" pela chamada da arena.
"""

import re
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import arena
from .models import Brinquedos

JOGOS_DIR = Path(finders.find("site/arena/console.js")).parent / "jogos"

#: Pedaços de nome de arquivo que denunciam arte de terceiros: as capas de
#: música do Hit Music e os logos de patrocinador do Gol Flash.
TERCEIROS = re.compile(
    r"naruto|rick|morty|dragon-ball|dragon_ball|demon|fairy|carmine|patinho|"
    r"michelob|corona|stella|^bud\b|ga_logo|^bar\.",
    re.IGNORECASE,
)


def _brinquedo(nome, **extra):
    dados = {
        "nome_brinquedo": nome,
        "descricao": f"{nome}: brinquedo profissional",
        "valor_brinquedo": Decimal("0"),
        "avaliacao": Decimal("4.50"),
        "voltz": "220v",
    }
    dados.update(extra)
    return Brinquedos.objects.create(**dados)


class ArenaPaginaTests(TestCase):

    def setUp(self):
        cache.clear()
        _brinquedo("Dragon Bowling Rosa")
        _brinquedo("Air Game Hockey")

    def test_abre_com_as_tres_secoes_e_o_console(self):
        resposta = self.client.get(reverse("arena"))
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertEqual(html.count("<h1"), 1)
        for ancora in ('id="jogos"', 'id="arena-3d"', 'id="maquinas"', 'id="arena-console"'):
            self.assertIn(ancora, html)
        # Todos os jogos chegam como cartão, mesmo sem JavaScript.
        for jogo in arena.JOGOS:
            self.assertIn(f'data-jogo-abrir="{jogo["slug"]}"', html)

    def test_todas_as_maquinas_aparecem_nas_fotos(self):
        html = self.client.get(reverse("arena")).content.decode()
        self.assertEqual(html.count("data-fotos-cartao"), 2)
        self.assertIn("Air Game Hockey", html)

    def test_jogar_pelo_link_e_o_atalho_jogos(self):
        resposta = self.client.get(reverse("arena") + "?jogar=lazer-shot")
        self.assertEqual(resposta.status_code, 200)
        atalho = self.client.get(reverse("jogos"))
        self.assertEqual(atalho.status_code, 302)
        self.assertEqual(atalho["Location"], "/arena/#jogos")


class ArquivosDosJogosTests(TestCase):

    def test_capa_poster_e_script_de_cada_jogo_existem(self):
        for jogo in arena.JOGOS:
            for campo in ("capa", "poster", "script"):
                with self.subTest(jogo=jogo["slug"], campo=campo):
                    self.assertIsNotNone(finders.find(jogo[campo]), jogo[campo])

    def test_cada_arte_que_o_script_carrega_existe(self):
        existentes = {p.name for p in JOGOS_DIR.rglob("*") if p.is_file()}
        for script in JOGOS_DIR.glob("*.js"):
            texto = script.read_text(encoding="utf-8")
            for caminho in set(re.findall(r'"([\w./-]+\.(?:webp|png|jpg|svg))"', texto)):
                with self.subTest(script=script.name, arte=caminho):
                    if "/" in caminho:
                        # Relativo ao script, ou à pasta dele (o boliche
                        # resolve a partir de `./boliche/`).
                        bases = [JOGOS_DIR, *(d for d in JOGOS_DIR.iterdir() if d.is_dir())]
                        self.assertTrue(any((b / caminho).is_file() for b in bases), caminho)
                    else:
                        # Montado com o prefixo da pasta (ARTE + "x.webp").
                        self.assertIn(caminho, existentes)

    def test_nenhuma_arte_de_terceiros(self):
        pasta = JOGOS_DIR.parent
        for arquivo in pasta.rglob("*"):
            if arquivo.is_file():
                with self.subTest(arquivo=str(arquivo.relative_to(pasta))):
                    self.assertIsNone(TERCEIROS.search(arquivo.name))

    def test_adesivos_do_strike_kids_completos(self):
        for tema in arena.TEMAS_STRIKE_KIDS:
            chave = tema[0] if isinstance(tema, (tuple, list)) else tema
            for face in (
                "01_letreiro_frente", "02_letreiro_lateral_esquerda", "02_letreiro_lateral_direita",
                "02_letreiro_traseira", "03_torre_frente", "04_torre_lateral_esquerda",
                "04_torre_lateral_direita", "05_torre_traseira", "06_pista_lateral_esquerda",
                "06_pista_lateral_direita", "07_pista_frente", "08_pista_piso",
            ):
                with self.subTest(tema=chave, face=face):
                    self.assertIsNotNone(
                        finders.find(f"site/arena/adesivos/strike-kids/{chave}/{face}.webp")
                    )
        # A tela da TV é a mesma em todos os temas.
        self.assertIsNotNone(finders.find("site/arena/adesivos/strike-kids/tela.webp"))


class SoMaquinaDeVerdadeGanha3DTests(TestCase):

    def test_variantes_so_para_o_boliche(self):
        self.assertIsNone(arena.variantes("Air Game Hockey", "fliperama"))
        dragon = arena.variantes("Dragon Bowling Rosa", "boliche")
        self.assertEqual(dragon["adesivo"], "dragon")
        self.assertEqual(dragon["cor"], "rosa")
        strike = arena.variantes("Strike Kids Boliche", "boliche")
        self.assertTrue(strike["adesivo"].startswith("strike-"))

    def test_vitrine_3d_tem_strike_kids_e_dragon_bowling(self):
        maquinas = arena.maquinas_3d([])
        self.assertEqual([m["id"] for m in maquinas], ["strike-kids", "dragon-bowling"])
        for maquina in maquinas:
            self.assertEqual(maquina["desenho"], "boliche")
            self.assertEqual(maquina["medidas"], list(arena.GABINETE_BOLICHE))
            self.assertTrue(maquina["fotos"])
            self.assertTrue(maquina["variantes"]["adesivos"])

    def test_pagina_do_produto_so_mostra_3d_no_boliche(self):
        boliche = _brinquedo("Dragon Bowling Rosa")
        hockey = _brinquedo("Air Game Hockey")
        com_3d = self.client.get(reverse("brinquedo_detalhe", args=[boliche.pk])).content.decode()
        sem_3d = self.client.get(reverse("brinquedo_detalhe", args=[hockey.pk])).content.decode()
        self.assertIn('id="ver-em-3d"', com_3d)
        self.assertNotIn('id="ver-em-3d"', sem_3d)
        self.assertNotIn("arena3d.js", sem_3d)


class PainelAoVivoTests(TestCase):

    def setUp(self):
        cache.clear()
        _brinquedo("Strike Kids Boliche")

    def test_responde_totais_com_cache_publico(self):
        resposta = self.client.get(reverse("painel_ao_vivo"))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("public", resposta["Cache-Control"])
        dados = resposta.json()
        self.assertEqual(dados["brinquedos"], 1)
        self.assertIn("atualizado_em", dados)
        self.assertIsInstance(dados["novidades"], list)


class HomeComArenaTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_arena_no_lugar_dos_parceiros(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn('id="arena-home"', html)
        self.assertNotIn('id="estabelecimentos"', html)
        self.assertIn(f'href="{reverse("arena")}#', html)
        self.assertIn("data-painel-url", html)
