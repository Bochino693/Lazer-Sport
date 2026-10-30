"""Arena 3D, o simulador Lazer & Sport Jogos e o painel ao vivo da home.

O que estes testes protegem:

  * a página da arena abre inteira sem JavaScript (jogos, máquinas em 3D,
    fotos de todas as máquinas) e cada jogo aponta para arquivos que
    existem -- capa, pôster, script e cada arte que o script carrega;
  * cada jogo tem a sua página no simulador (/jogos/<jogo>/), em foco,
    com o comando dele: arrasto nos boliches, clique no tiro, botões só
    onde a máquina tem botão;
  * nenhuma arte de terceiros (logos de patrocinador, capas de outras
    músicas) entra na pasta dos jogos -- só as duas capas que o dono
    pediu para o Hit Music (Carmine e Paper Moon, as da própria mesa);
  * as máquinas vêm em seções: as dos jogos da casa primeiro, depois as
    que já fazíamos e os trampolins e brinquedões; nada de 3D montado à
    mão (nem na arena, nem na página do produto);
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

    def test_abre_com_as_tres_secoes(self):
        resposta = self.client.get(reverse("arena"))
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertEqual(html.count("<h1"), 1)
        for ancora in ('id="jogos"', 'id="arena-3d"', 'id="arena-dados"', "arena3d.js"):
            self.assertIn(ancora, html)
        # Todos os jogos chegam como cartão, levando ao simulador.
        for jogo in arena.JOGOS:
            self.assertIn(f'href="{reverse("jogo", args=[jogo["slug"]])}"', html)

    def test_todas_as_maquinas_vao_para_o_3d_e_para_a_lista(self):
        resposta = self.client.get(reverse("arena"))
        html = resposta.content.decode()
        # a lista (a página sem 3D) tem as duas, e o 3D recebe as duas com as fotos
        self.assertEqual(html.count("data-arena-id="), 2)
        self.assertIn("Air Game Hockey", html)
        maquinas = resposta.context["arena_dados"]["maquinas"]
        self.assertEqual(sorted(m["nome"] for m in maquinas), ["Air Game Hockey", "Dragon Bowling Rosa"])

    def test_da_para_ver_a_maquina_de_todos_os_lados(self):
        html = self.client.get(reverse("arena")).content.decode()
        for vista in ("girar", "frente", "direita", "costas", "esquerda", "cima", "baixo"):
            self.assertIn(f'data-arena-vista="{vista}"', html)



class SimuladorTests(TestCase):

    def setUp(self):
        cache.clear()
        _brinquedo("Gol Flash Arena")

    def test_cada_jogo_tem_a_sua_pagina_em_foco(self):
        for jogo in arena.JOGOS:
            with self.subTest(jogo=jogo["slug"]):
                resposta = self.client.get(reverse("jogo", args=[jogo["slug"]]))
                self.assertEqual(resposta.status_code, 200)
                html = resposta.content.decode()
                self.assertEqual(html.count("<h1"), 1)
                self.assertIn(f"<title>{jogo['titulo']}: jogue a prévia", html)
                self.assertIn('aria-current="page"', html)
                self.assertIn('id="sim-jogos"', html)

    def test_pagina_geral_e_jogo_que_nao_existe(self):
        self.assertEqual(self.client.get(reverse("jogos")).status_code, 200)
        self.assertEqual(self.client.get("/jogos/nao-existe/").status_code, 404)

    def test_comandos_seguem_o_jogo(self):
        gol = self.client.get(reverse("jogo", args=["gol-flash-arena"])).content.decode()
        for tecla in ("ArrowLeft", "Space", "ArrowRight"):
            self.assertIn(f'data-console-tecla="{tecla}"', gol)
        # Boliche é arrasto: nenhum botão embaixo da tela.
        boliche = self.client.get(reverse("jogo", args=["strike-kids"])).content.decode()
        self.assertNotIn("data-console-tecla=", boliche)
        self.assertIn("Arraste e solte", boliche)

    def test_jogo_liga_na_maquina_do_catalogo(self):
        html = self.client.get(reverse("jogo", args=["gol-flash-arena"])).content.decode()
        maquina = Brinquedos.objects.get(nome_brinquedo="Gol Flash Arena")
        self.assertIn(reverse("brinquedo_detalhe", args=[maquina.pk]), html)

    def test_todos_os_jogos_tem_comando(self):
        for jogo in arena.JOGOS:
            with self.subTest(jogo=jogo["slug"]):
                controle = arena.CONTROLES[jogo["slug"]]
                self.assertIn(controle["gesto"], arena.ICONES_DO_GESTO)
                self.assertTrue(controle["passos"])
                self.assertTrue(controle["na_maquina"])

    def test_sitemap_tem_os_jogos(self):
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(reverse("jogos"), xml)
        for jogo in arena.JOGOS:
            self.assertIn(reverse("jogo", args=[jogo["slug"]]), xml)


class ArquivosDosJogosTests(TestCase):

    def test_capa_poster_e_script_de_cada_jogo_existem(self):
        for jogo in arena.jogos_do_simulador(arena.JOGOS):
            for campo in ("capa", "poster", "script", "miniatura"):
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
        # Só imagens. As músicas do Hit Music (Carmine e Paper Moon) e as
        # capas delas, tiradas da própria mesa, entraram por decisão do
        # dono; o resto das capas e os logos de terceiros continuam fora.
        pasta = JOGOS_DIR.parent
        liberadas = {JOGOS_DIR / "hit-music" / "capas" / "carmine.webp", JOGOS_DIR / "hit-music" / "capas" / "soul.webp"}
        for arquivo in pasta.rglob("*"):
            if arquivo in liberadas:
                continue
            if arquivo.is_file() and arquivo.suffix.lower() in {".webp", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".avif"}:
                with self.subTest(arquivo=str(arquivo.relative_to(pasta))):
                    self.assertIsNone(TERCEIROS.search(arquivo.name))

    def test_hit_music_tem_as_capas_e_os_videos_da_mesa(self):
        # a capa no seletor e o vídeo da música no painel de cima, como no Godot
        script = (JOGOS_DIR / "hit-music.js").read_text(encoding="utf-8")
        for capa in ("hit-music/capas/carmine.webp", "hit-music/capas/soul.webp",
                     "hit-music/videos/carmine.mp4", "hit-music/videos/soul.mp4"):
            with self.subTest(capa=capa):
                self.assertIn(capa, script)
                self.assertTrue((JOGOS_DIR / capa).is_file())

class SecoesDaArenaTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_cada_maquina_na_sua_secao(self):
        for nome in ("Air Game Hockey", "Dragon Bowling Rosa", "Cama Elástica 3m", "Lazer Shot Arena"):
            _brinquedo(nome)
        resposta = self.client.get(reverse("arena"))
        grupos = {g["id"]: [b["nome"] for b in g["brinquedos"]] for g in resposta.context["grupos_arena"]}
        self.assertEqual(list(grupos), ["jogos", "maquinas", "brinquedoes"])
        self.assertEqual(sorted(grupos["jogos"]), ["Dragon Bowling Rosa", "Lazer Shot Arena"])
        self.assertEqual(grupos["maquinas"], ["Air Game Hockey"])
        self.assertEqual(grupos["brinquedoes"], ["Cama Elástica 3m"])

    def test_area_vazia_nao_aparece(self):
        _brinquedo("Air Game Hockey")
        html = self.client.get(reverse("arena")).content.decode()
        self.assertIn('data-arena-zona="maquinas"', html)
        self.assertNotIn('data-arena-zona="jogos"', html)
        self.assertNotIn('data-arena-zona="brinquedoes"', html)

    def test_jogo_so_pelo_nome_da_maquina(self):
        # basquete e boxe do catálogo são outras máquinas, com outros jogos
        self.assertEqual(arena.jogo_da_maquina("Lazer Shot Arena"), "lazer-shot")
        self.assertEqual(arena.jogo_da_maquina("Dragon Bowling Rosa"), "dragon-bowling")
        self.assertEqual(arena.jogo_da_maquina("Basquete Street"), "")
        self.assertEqual(arena.jogo_da_maquina("Boxe Força Máxima"), "")
        self.assertEqual(arena.jogo_da_maquina("Mundo Zumbi"), "")

    def test_faixas_de_aviso_so_no_lazer_shot(self):
        self.assertEqual([a["id"] for a in arena.avisos_da_maquina("Lazer Shot")], ["camera", "arma"])
        self.assertEqual(arena.avisos_da_maquina("Dragon Bowling Rosa"), [])
        self.assertEqual(arena.avisos_da_maquina("Basquete Street"), [])
        lazer = _brinquedo("Lazer Shot")
        _brinquedo("Air Game Hockey")
        pagina = self.client.get(reverse("brinquedo_detalhe", args=[lazer.pk])).content.decode()
        self.assertIn('aria-label="Contém câmera e Arma personalizada"', pagina)
        catalogo = self.client.get(reverse("brinquedos")).content.decode()
        self.assertEqual(catalogo.count('class="ls-faixas"'), 1)
        dados = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        self.assertEqual({m["nome"]: m["avisos"] for m in dados}, {"Lazer Shot": ["camera", "arma"], "Air Game Hockey": []})

    def test_pagina_do_produto_sem_3d(self):
        boliche = _brinquedo("Dragon Bowling Rosa")
        html = self.client.get(reverse("brinquedo_detalhe", args=[boliche.pk])).content.decode()
        self.assertNotIn('id="ver-em-3d"', html)
        self.assertNotIn("arena3d.js", html)


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
        self.assertIn(f'href="{reverse("jogos")}"', html)
        self.assertIn("data-painel-url", html)


class PrecoSoDaLojaTests(TestCase):
    """Só mostra preço o que está à venda na loja (marcado e com valor)."""

    def setUp(self):
        cache.clear()
        self.na_loja = _brinquedo("Air Game Hockey", valor_brinquedo=Decimal("8900.00"), exibir_na_loja=True)
        self.fora = _brinquedo("Basquete Street", valor_brinquedo=Decimal("12345.00"), exibir_na_loja=False)

    def test_regra_do_modelo(self):
        self.assertTrue(self.na_loja.disponivel_na_loja)
        self.assertFalse(self.fora.disponivel_na_loja)
        self.assertFalse(_brinquedo("Sem preço", exibir_na_loja=True).disponivel_na_loja)

    def test_home_arena_e_vitrine(self):
        home = self.client.get(reverse("home")).content.decode()
        # o card curto da home não traz preço: só marca o que está à venda
        self.assertIn("Disponível para compra", home)
        self.assertNotIn("12.345,00", home)
        self.assertNotIn("12.345,00", self.client.get(reverse("arena")).content.decode())
        dados = {d["nome"]: d for d in (
            arena.dados_do_brinquedo(b, "/") for b in Brinquedos.objects.prefetch_related(
                "categorias_brinquedos", "tags", "imagens_brinquedo")
        )}
        self.assertEqual(dados["Air Game Hockey"]["preco"], "R$ 8.900,00")
        self.assertEqual(dados["Basquete Street"]["preco"], "")
