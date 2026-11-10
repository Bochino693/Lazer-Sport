"""Arena 3D, o simulador Lazer & Sport Jogos e o painel ao vivo da home.

O que estes testes protegem:

  * a página da arena abre inteira sem JavaScript (jogos, máquinas em 3D,
    fotos de todas as máquinas) e cada jogo aponta para arquivos que
    existem -- capa, pôster, script e cada arte que o script carrega;
  * cada jogo tem a sua página no simulador (/jogos/<jogo>/), em foco,
    com o comando dele: arrasto nos boliches, clique no tiro, botões só
    onde a máquina tem botão;
  * os sons de verdade de cada máquina (o `sons` dos jogos, tirados dos
    projetos originais) existem, são MP3 e cabem no peso por jogo;
  * nenhuma arte de terceiros (logos de patrocinador, capas de outras
    músicas) entra na pasta dos jogos -- só as duas capas que o dono
    pediu para o Hit Music (Carmine e Paper Moon, as da própria mesa);
  * as máquinas vêm em seções: as dos jogos da casa primeiro, depois as
    que já fazíamos e os trampolins e brinquedões; nada de 3D montado à
    mão (nem na arena, nem na página do produto);
  * na roda da Arena 3D (e na lista, que é a roda sem WebGL) só entra quem
    tem objeto 3D de verdade (.glb); o resto fica na galeria de fotos, e a
    área sem nenhum objeto some;
  * o painel ao vivo responde com totais e pode ser guardado em cache;
  * a home troca "Nossos Parceiros" pela chamada da arena.
"""

import re
from decimal import Decimal
from pathlib import Path

from unittest import mock

from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase
from django.urls import reverse

from . import arena
from .models import Brinquedos, ObjetoTresD

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


def _com_objeto_3d(brinquedo, arquivo="site/arena/modelos/strike-kids.glb"):
    """Liga um .glb (um que vem com o site) ao brinquedo, como o painel liga."""
    ObjetoTresD.objects.create(brinquedo=brinquedo, arquivo_estatico=arquivo, medidas=[1.8, 1.0, 1.2])
    return brinquedo


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
        for ancora in ('id="arena-3d"', 'id="arena-dados"', "arena3d.js", 'id="monte-seu-espaco"', 'id="p3dDados"', "projeto3d.js"):
            self.assertIn(ancora, html)
        # os jogos foram para o portal (/jogos/): a arena é só o 3D e o "Monte seu espaço"
        self.assertNotIn('id="jogos"', html)
        self.assertNotIn("jogo-cartao", html)

    def test_so_quem_tem_objeto_3d_vai_para_a_roda_e_para_a_lista(self):
        resposta = self.client.get(reverse("arena"))
        html = resposta.content.decode()
        # a roda 3D e a lista (a roda sem WebGL): só os objetos 3D de verdade
        # -- aqui, os do site, que ainda não estão no catálogo
        self.assertEqual(html.count("data-arena-id="), len(arena.MODELOS_3D))
        maquinas = resposta.context["arena_dados"]["maquinas"]
        self.assertEqual(sorted(m["nome"] for m in maquinas), sorted(m["titulo"] for m in arena.MODELOS_3D))
        self.assertTrue(all(m["modelo"] for m in maquinas))
        # as duas sem .glb seguem na galeria de fotos (com o jogo da prévia)
        galeria = {b["nome"]: b for b in resposta.context["brinquedos_arena"]}
        self.assertEqual((galeria["Dragon Bowling Rosa"]["modelo"], galeria["Dragon Bowling Rosa"]["jogo"]), ("", "dragon-bowling"))
        self.assertIn("Air Game Hockey", html.split('id="titulo-maquinas"')[1])
        # a roda 3D (até o "Monte seu espaço", que lista o catálogo inteiro para montar) não leva quem não tem .glb
        roda = html.split('id="arena-3d"')[1].split('id="monte-seu-espaco"')[0]
        # (o nome inteiro: o "Air Game Kids Alienígenas" tem o objeto dele e está na roda)
        self.assertNotIn('"nome": "Air Game Hockey"', roda)
        self.assertNotIn(">Air Game Hockey<", roda)
        self.assertIn('"nome": "Air Game Kids Alien\\u00edgenas"', roda)  # (no JSON, o "\u00ed" vem escapado)
        # o número do topo conta os da roda
        self.assertIn(f"<b>{len(arena.MODELOS_3D)}</b> brinquedos em 3D", html)

    def test_com_objeto_3d_no_cadastro_entra_na_roda(self):
        _com_objeto_3d(Brinquedos.objects.get(nome_brinquedo="Air Game Hockey"))
        resposta = self.client.get(reverse("arena"))
        nomes = [m["nome"] for m in resposta.context["arena_dados"]["maquinas"]]
        self.assertIn("Air Game Hockey", nomes)
        self.assertNotIn("Dragon Bowling Rosa", nomes)

    def test_da_para_ver_a_maquina_de_todos_os_lados(self):
        html = self.client.get(reverse("arena")).content.decode()
        for vista in ("girar", "frente", "direita", "costas", "esquerda", "cima", "baixo"):
            self.assertIn(f'data-arena-vista="{vista}"', html)

    def test_da_para_ir_direto_a_qualquer_brinquedo(self):
        # as setas, o "Ir para" (a lista com busca), o "Ver tudo" e o mapa
        html = self.client.get(reverse("arena")).content.decode()
        for acao in ("esquerda", "direita", "irpara", "visao", "mapa"):
            self.assertIn(f'data-arena-acao="{acao}"', html)
        for parte in ("data-arena-irpara", "data-arena-irpara-busca", "data-arena-irpara-lista"):
            self.assertIn(parte, html)



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
                # o título é o de quem busca para jogar ("Boliche virtual online grátis...")
                from core.paginas_tema import busca_do_jogo
                titulo = busca_do_jogo(jogo["slug"]).get("titulo") or f"{jogo['titulo']}: jogue a prévia"
                self.assertIn(f"<title>{titulo.replace('&', '&amp;')}", html)
                self.assertIn('aria-current="page"', html)
                self.assertIn('id="sim-jogos"', html)
                self.assertIn("intro-jogos.js", html)  # a abertura antes do 3-2-1

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


#: O peso dos sons de cada máquina (a pasta `sons/` do jogo, baixada quando
#: ele abre). Os efeitos são MP3 mono curtos; o que passar disto é trilha
#: longa ou WAV esquecido, e quem paga é o celular de quem abriu o jogo.
PESO_DOS_SONS = 720 * 1024
PESO_DE_UM_SOM = 400 * 1024


class SonsDosJogosTests(TestCase):
    """Os sons de verdade das máquinas (o `sons` de cada jogo)."""

    def _sons(self):
        return [p for p in JOGOS_DIR.rglob("*") if p.is_file() and "sons" in p.relative_to(JOGOS_DIR).parts]

    def test_cada_som_que_o_script_pede_existe(self):
        existentes = {p.name for p in self._sons()}
        for script in JOGOS_DIR.glob("*.js"):
            texto = script.read_text(encoding="utf-8")
            for caminho in set(re.findall(r'"([\w./-]+\.mp3)"', texto)):
                if "/sons/" not in caminho and "/" in caminho:
                    continue  # as músicas do Hit Music, que ele mesmo toca
                with self.subTest(script=script.name, som=caminho):
                    if "/" in caminho:
                        self.assertTrue((JOGOS_DIR / caminho).is_file(), caminho)
                    else:
                        # montado com o prefixo da pasta (SOM + "strike.mp3")
                        self.assertIn(caminho, existentes)

    def test_sons_sao_mp3_e_cabem_no_peso(self):
        pastas = {}
        for arquivo in self._sons():
            with self.subTest(arquivo=str(arquivo.relative_to(JOGOS_DIR))):
                self.assertEqual(arquivo.suffix, ".mp3")
                self.assertLessEqual(arquivo.stat().st_size, PESO_DE_UM_SOM)
            pasta = arquivo.relative_to(JOGOS_DIR).parts[0]
            pastas[pasta] = pastas.get(pasta, 0) + arquivo.stat().st_size
        self.assertTrue(pastas, "nenhum som de máquina encontrado")
        for pasta, peso in pastas.items():
            with self.subTest(pasta=pasta):
                self.assertLessEqual(peso, PESO_DOS_SONS, f"{pasta}: {peso // 1024} KB de sons")

    def test_cada_maquina_com_projeto_tem_os_seus_sons(self):
        # os jogos que têm o projeto original na casa usam os sons dele
        for script, pasta in (("strike-kids.js", "strike-kids/sons/"), ("dragon-bowling.js", "boliche/dragon/sons/"),
                              ("lazer-shot.js", "lazer-shot/sons/"), ("super-boxing.js", "super-boxing/sons/"),
                              ("basquete.js", "basquete/sons/"), ("gol-flash.js", "gol-flash/sons/")):
            with self.subTest(script=script):
                texto = (JOGOS_DIR / script).read_text(encoding="utf-8")
                self.assertIn(pasta, texto)
                self.assertRegex(texto, r"\bsons: ")

# as seções vêm do catálogo; os objetos 3D em exposição ficam de fora aqui
@mock.patch.object(arena, "MODELOS_3D", ())
class SecoesDaArenaTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_cada_maquina_na_sua_secao(self):
        for nome in ("Air Game Hockey", "Dragon Bowling Rosa", "Cama Elástica 3m", "Lazer Shot Arena"):
            _com_objeto_3d(_brinquedo(nome))
        _brinquedo("Pebolim Clássico")  # sem objeto 3D: fora da roda
        resposta = self.client.get(reverse("arena"))
        grupos = {g["id"]: [b["nome"] for b in g["brinquedos"]] for g in resposta.context["grupos_arena"]}
        self.assertEqual(list(grupos), ["jogos", "maquinas", "brinquedoes"])
        self.assertEqual(sorted(grupos["jogos"]), ["Dragon Bowling Rosa", "Lazer Shot Arena"])
        self.assertEqual(grupos["maquinas"], ["Air Game Hockey"])
        self.assertEqual(grupos["brinquedoes"], ["Cama Elástica 3m"])

    def test_area_vazia_nao_aparece(self):
        _com_objeto_3d(_brinquedo("Air Game Hockey"))
        # a área dos trampolins só teria a cama sem .glb: some da roda
        _brinquedo("Cama Elástica 3m", altura_m=Decimal("2.4"))
        resposta = self.client.get(reverse("arena"))
        html = resposta.content.decode()
        self.assertIn('data-arena-zona="maquinas"', html)
        self.assertNotIn('data-arena-zona="jogos"', html)
        self.assertNotIn('data-arena-zona="brinquedoes"', html)
        self.assertEqual([z["id"] for z in resposta.context["arena_dados"]["zonas"]], ["maquinas"])
        # e a cama continua na galeria de fotos
        self.assertIn("Cama Elástica 3m", html.split('id="titulo-maquinas"')[1])

    def test_sem_nenhum_objeto_3d_a_roda_avisa_e_a_galeria_fica(self):
        _brinquedo("Air Game Hockey")
        resposta = self.client.get(reverse("arena"))
        self.assertEqual(resposta.context["arena_dados"]["maquinas"], [])
        html = resposta.content.decode()
        self.assertNotIn("data-arena3d", html)
        self.assertIn("Os objetos 3D estão chegando", html)
        self.assertIn("Air Game Hockey", html.split('id="titulo-maquinas"')[1])

    def test_jogo_so_pelo_nome_da_maquina(self):
        # basquete e boxe do catálogo são outras máquinas, com outros jogos
        self.assertEqual(arena.jogo_da_maquina("Lazer Shot Arena"), "lazer-shot")
        self.assertEqual(arena.jogo_da_maquina("Dragon Bowling Rosa"), "dragon-bowling")
        self.assertEqual(arena.jogo_da_maquina("Basquete Street"), "")
        self.assertEqual(arena.jogo_da_maquina("Boxe Força Máxima"), "")
        self.assertEqual(arena.jogo_da_maquina("Mundo Zumbi"), "")

    def test_selos_de_recursos_do_lazer_shot_e_do_strike_kids(self):
        self.assertEqual([a["id"] for a in arena.avisos_da_maquina("Lazer Shot")], ["camera", "arma"])
        self.assertEqual([a["id"] for a in arena.avisos_da_maquina("Strike Kids Boliche")], ["camera", "sensores"])
        self.assertEqual(arena.avisos_da_maquina("Dragon Bowling Rosa"), [])
        self.assertEqual(arena.avisos_da_maquina("Basquete Street"), [])
        lazer = _brinquedo("Lazer Shot")
        _brinquedo("Air Game Hockey")
        _brinquedo("Strike Kids Boliche")
        pagina = self.client.get(reverse("brinquedo_detalhe", args=[lazer.pk])).content.decode()
        self.assertIn('aria-label="Recursos: Contém câmera e Arma personalizada"', pagina)
        # cada selo com o ícone, o nome curto e a explicação
        self.assertIn('data-aviso="camera"', pagina)
        self.assertIn("Tira a foto do jogador para o ranking", pagina)
        catalogo = self.client.get(reverse("brinquedos")).content.decode()
        self.assertEqual(catalogo.count('class="ls-recursos"'), 2)
        # na galeria de fotos da arena tem (o Lazer Shot e o Strike Kids);
        # na ficha da Arena 3D, não
        html = self.client.get(reverse("arena")).content.decode()
        self.assertEqual(html.count('class="ls-recursos"'), 2)
        self.assertIn("5 sensores de precisão", html)
        self.assertNotIn("ls-recursos", html.split('id="arena-3d"')[1].split('id="maquinas"')[0])

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


class RodaEPasseioJsTests(TestCase):
    """A roda (um de cada categoria, nada colado) e o passeio (nada atravessa os túneis), no node.

    core/tests_js/roda.mjs confere a conta da roda (core/static/site/arena/roda.js) com as máquinas
    de verdade da página; core/tests_js/passeio.mjs confere cada caminho do passeio
    (caminhos.js) com a geometria do .glb de cada objeto.
    """

    def _node(self):
        import shutil

        node = shutil.which("node")
        if not node:
            self.skipTest("Sem node para rodar o JavaScript da arena")
        return node

    def test_um_de_cada_categoria_e_nada_colado(self):
        import json
        import subprocess
        import tempfile

        node = self._node()
        cache.clear()
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as arquivo:
            json.dump(maquinas, arquivo)
        try:
            resultado = subprocess.run([node, str(Path(__file__).parent / "tests_js" / "roda.mjs"), arquivo.name],
                                       capture_output=True, text=True, timeout=120)
        finally:
            Path(arquivo.name).unlink(missing_ok=True)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)

    def test_o_passeio_nao_atravessa_nada(self):
        import subprocess

        node = self._node()
        resultado = subprocess.run([node, str(Path(__file__).parent / "tests_js" / "passeio.mjs")],
                                   capture_output=True, text=True, timeout=300)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)

    def test_a_pagina_traz_os_modulos_da_roda_e_do_passeio(self):
        html = self.client.get(reverse("arena")).content.decode()
        for trecho in ("site/arena/roda.js", "site/arena/caminhos.js", "data-arena-troca", "data-troca-passo"):
            self.assertIn(trecho, html)

    def test_nenhum_raio_por_quadro_e_a_qualidade_adapta(self):
        # o quadro da arena e o do passeio não fazem conta com os triângulos dos
        # objetos (o mouse vai pelas caixas dos estandes, o piso do passeio é o
        # caminho amostrado); a qualidade tem os três degraus e desce sozinha
        js = Path(finders.find("site/arena/arena3d.js")).read_text(encoding="utf-8")
        quadro = js[js.index("  quadro(dt) {\n    this.pinturasNoQuadro = 0;"):]
        quadro = quadro[:quadro.index("\n  }\n")]
        self.assertNotIn("intersect", quadro)
        passeio = js[js.index("class Passeio {"):js.index("class Camera {")]
        quadro_do_passeio = passeio[passeio.index("  quadro(dt) {"):]
        quadro_do_passeio = quadro_do_passeio[:quadro_do_passeio.index("\n  }\n")]
        self.assertNotIn("intersect", quadro_do_passeio)
        self.assertNotIn("this.piso(", quadro_do_passeio)
        self.assertIn("maquinaSobACaixa", js)
        for degrau in ("alta:", "media:", "baixa:"):
            self.assertIn(degrau, js[js.index("const QUALIDADES = {"):])
        self.assertIn("mudarDeDegrau(1)", js)


class ArenaNoNavegadorTests(StaticLiveServerTestCase):
    """A Arena 3D de verdade num Chromium sem tela (core/tests_js/arena_vagas.cjs, com o Playwright).

    Um modelo carregado por categoria, a troca na vaga descarta o de antes e nenhum raio
    por quadro (na arena e no passeio). Sem node, Playwright ou o Chromium dele, pula.
    """

    def test_um_carregado_por_categoria_e_a_troca_descarta(self):
        import os
        import shutil
        import subprocess

        node = shutil.which("node")
        npm = shutil.which("npm")
        if not node:
            self.skipTest("Sem node")
        ambiente = dict(os.environ)
        if npm:
            raiz_global = subprocess.run([npm, "root", "-g"], capture_output=True, text=True).stdout.strip()
            ambiente["NODE_PATH"] = os.pathsep.join(filter(None, [ambiente.get("NODE_PATH", ""), raiz_global]))
        tem = subprocess.run([node, "-e", "require.resolve('playwright')"], capture_output=True, env=ambiente)
        if tem.returncode != 0:
            self.skipTest("Sem o Playwright para abrir a arena num navegador")
        resultado = subprocess.run(
            [node, str(Path(__file__).parent / "tests_js" / "arena_vagas.cjs"), self.live_server_url + reverse("arena")],
            capture_output=True, text=True, timeout=900, env=ambiente,
        )
        if "Executable doesn't exist" in resultado.stdout + resultado.stderr:
            self.skipTest("Sem o Chromium do Playwright")
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
