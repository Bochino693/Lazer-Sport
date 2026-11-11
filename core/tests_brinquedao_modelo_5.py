"""O Brinquedão Modelo 5: o objeto 3D feito com as quatro imagens do projeto, e o cadastro.

O que estes testes protegem:

  * a máquina chamada "Brinquedão Modelo 5" leva o .glb para a Arena 3D, com
    as medidas que estão dentro do .glb (3,70 m de barra, 2,48 m de fundo com
    a perna e o escorregador, 2 m de altura), e o arquivo é leve; o .glb e as
    oito fotos existem; os outros brinquedões continuam com os deles;
  * a planta é a do projeto: a barra de 3,70 m × 1 m, o escorregador na
    frente da perna, à esquerda, os rolos na frente dos módulos 2 e 3, a
    cunha do 2º módulo e, no 4º, os dois triângulos laranja (o degrau a
    0,64 m e o piso de 1 m);
  * antes de estar no catálogo, o objeto já aparece na arena (na seção dos
    brinquedões e na vaga dos brinquedões da roda), com a perspectiva da
    fábrica de capa; cadastrado, o do catálogo toma o lugar (sem duplicar);
  * no "Monte seu projeto" ele é um modelo pronto de Brinquedão;
  * o passeio por dentro tem caminho próprio (a escada, os sacos, a cunha, o
    escorregador), e todo jeito de andar que ele usa existe na Arena;
  * o comando cadastra uma vez só, fora da loja, com a perspectiva da
    fábrica de foto principal, as vistas do 3D, a planta e as duas do salão
    na galeria, as medidas da planta e o objeto 3D ligado; se o brinquedo já
    está no catálogo, só ganha o objeto;
  * a migração liga o objeto em todo lugar, só cadastra no Render e nunca
    derruba o deploy;
  * na home, sem cadastro do objeto, vale o do site pelo nome.
"""

import importlib
import json
import math
import re
import shutil
import subprocess
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import mock

from django.apps import apps as apps_reais
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import arena, projeto3d
from .cadastro_modelos import CADASTROS
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD
from .objetos_3d import ler_glb_do_site

migracao = importlib.import_module("core.migrations.0151_brinquedao_modelo_5")

NOME = "Brinquedão Modelo 5"
CHAVE = "brinquedao-modelo-5"
GLB = "site/arena/modelos/brinquedao-modelo-5.glb"
MEDIDAS = [2.0, 3.7, 2.48]  # altura, largura, profundidade do .glb
FOTOS = (
    "perspectiva.webp", "frente.webp", "lado_esquerdo.webp", "lado_direito.webp", "perspectiva_3d.webp",
    "planta.webp", "salao_frente.webp", "salao_esquerda.webp",
)


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    storage = FileSystemStorage(location=pasta)
    return (
        mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage),
        mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage),
    )


def _caixa_do_no(nome):
    """A caixa (mínimo, máximo) do nó `nome` do .glb do site, no objeto, em metros.

    Como `medidas_do_glb`, mas só com as malhas debaixo daquele nó (o
    gltfpack põe a malha de cada material num nó filho, com a escala da
    compressão).
    """
    from .objetos_3d import _MAXIMO_DO_TIPO, _matriz_do_no, _multiplicar, ler_json_do_glb

    with open(finders.find(GLB), "rb") as arquivo:
        dados = ler_json_do_glb(arquivo)
    nos, malhas, acessores = dados["nodes"], dados["meshes"], dados["accessors"]
    baixo, alto = [math.inf] * 3, [-math.inf] * 3

    def andar(indice, pai, dentro):
        no = nos[indice]
        matriz = _multiplicar(pai, _matriz_do_no(no))
        dentro = dentro or no.get("name") == nome
        if dentro and "mesh" in no:
            for primitiva in malhas[no["mesh"]]["primitives"]:
                acessor = acessores[primitiva["attributes"]["POSITION"]]
                menor, maior = acessor["min"], acessor["max"]
                if acessor.get("normalized"):
                    teto = _MAXIMO_DO_TIPO[acessor["componentType"]]
                    menor, maior = [max(v / teto, -1.0) for v in menor], [max(v / teto, -1.0) for v in maior]
                for x in (menor[0], maior[0]):
                    for y in (menor[1], maior[1]):
                        for z in (menor[2], maior[2]):
                            for eixo in range(3):
                                v = matriz[eixo] * x + matriz[4 + eixo] * y + matriz[8 + eixo] * z + matriz[12 + eixo]
                                baixo[eixo], alto[eixo] = min(baixo[eixo], v), max(alto[eixo], v)
        for filho in no.get("children") or []:
            andar(filho, matriz, dentro)

    identidade = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    for raiz in dados["scenes"][dados.get("scene", 0)]["nodes"]:
        andar(raiz, identidade, False)
    return baixo, alto


def _categorias():
    CategoriasBrinquedos.objects.create(nome_categoria="Brinquedões", imagem_categoria="categorias/brinquedoes.png")
    CategoriasBrinquedos.objects.create(nome_categoria="Eletrônicos", imagem_categoria="categorias/eletronicos.png")


class ObjetoNaArenaTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_liga_pelo_nome_e_os_arquivos_existem(self):
        self.assertEqual(arena.modelo_da_maquina(NOME)["id"], CHAVE)
        self.assertEqual(arena.modelo_da_maquina("BRINQUEDAO MODELO 5 de madeira")["id"], CHAVE)
        # os outros continuam com os deles, e o "5" não pega o "50"
        for outro in ("2", "3", "4"):
            self.assertEqual(arena.modelo_da_maquina(f"Brinquedão Modelo {outro}")["id"], f"brinquedao-modelo-{outro}")
        self.assertIsNone(arena.modelo_da_maquina("Brinquedão Modelo 50"))
        self.assertEqual(arena.modelo_3d(NOME), "playground")
        modelo = arena.modelo_da_maquina(NOME)
        self.assertTrue(finders.find(modelo["arquivo"]))
        for _, arquivo in modelo["fotos"]:
            self.assertTrue(finders.find(modelo["pasta"] + arquivo), arquivo)
        self.assertEqual([f for f, _, _ in CADASTROS[CHAVE]["fotos"]], list(FOTOS))
        for arquivo in FOTOS:
            self.assertTrue((CADASTROS[CHAVE]["pasta"] / arquivo).exists(), arquivo)

    def test_medidas_sao_as_do_glb_e_ele_e_leve(self):
        modelo = arena.modelo_da_maquina(NOME)
        self.assertEqual(list(modelo["medidas"]), MEDIDAS)
        self.assertEqual(ler_glb_do_site(GLB)["medidas"], MEDIDAS)
        # a Arena baixa o objeto inteiro: abaixo de 800 KB
        self.assertLess(Path(finders.find(GLB)).stat().st_size, 800 * 1024)

    def test_a_planta_e_a_do_projeto(self):
        # No objeto (centralizado, a frente em +z): a barra de 3,70 m vai de
        # x = -1,85 a 1,85 e de z = -1,241 (o fundo) a -0,241 (a frente dela);
        # a perna e o escorregador avançam até z = 1,24, na ponta esquerda.
        baixo, alto = _caixa_do_no("tubos-madeira")
        self.assertAlmostEqual(baixo[0], -1.85, delta=0.01)
        self.assertAlmostEqual(alto[0], 1.85, delta=0.01)
        self.assertAlmostEqual(alto[1], 2.0, delta=0.01)
        self.assertAlmostEqual(baixo[2], -1.241, delta=0.01)
        # o escorregador: na largura da perna (0,62 m), da beira do piso (1 m) até o chão, 1,45 m na frente
        baixo, alto = _caixa_do_no("escorregador-amarelo")
        self.assertGreaterEqual(baixo[0], -1.85 - 0.01)
        self.assertLessEqual(alto[0], -1.85 + 0.7)
        self.assertLess(baixo[1], 0.05)
        self.assertGreater(alto[1], 1.0)
        self.assertGreater(alto[2], 1.15)
        # os quatro rolos na frente dos módulos 2 e 3, de 0,2 m até o tubo do piso (1 m)
        for cor in ("rosa", "amarelo", "azul", "laranja"):
            baixo, alto = _caixa_do_no(f"rolo-{cor}")
            self.assertGreaterEqual(baixo[0], 1.0 - 1.85, cor)
            self.assertLessEqual(alto[0], 2.7 - 1.85, cor)
            self.assertAlmostEqual(baixo[1], 0.2, delta=0.01)
            self.assertAlmostEqual(alto[1], 0.966, delta=0.01)
        # a cunha azul no 2º módulo, com ~0,38 m acima do piso de 1,04 m
        baixo, alto = _caixa_do_no("cunha-azul")
        self.assertGreaterEqual(baixo[0], 1.38 - 1.85)
        self.assertLessEqual(alto[0], 1.92 - 1.85)
        self.assertAlmostEqual(alto[1], 1.42, delta=0.02)
        # no 4º módulo, os triângulos laranja: o degrau (0,64 m) e o piso de cima (1,04 m)
        baixo, alto = _caixa_do_no("piso-laranja")
        self.assertAlmostEqual(baixo[0], 2.7 - 1.85, delta=0.01)
        self.assertAlmostEqual(baixo[1], 0.6, delta=0.01)
        self.assertAlmostEqual(alto[1], 1.04, delta=0.01)

    def test_aparece_na_arena_antes_do_cadastro(self):
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5, voltz="220v")
        resposta = self.client.get(reverse("arena"))
        dados = {m["nome"]: m for m in resposta.context["arena_dados"]["maquinas"]}
        exposto = dados[NOME]
        self.assertIn(GLB, exposto["modelo"])
        self.assertEqual(exposto["modelo_id"], CHAVE)
        self.assertEqual((exposto["grupo"], exposto["reino"]), ("brinquedoes", False))  # na roda, como os outros
        self.assertEqual(exposto["categorias"], ["Brinquedões"])
        self.assertEqual(exposto["medidas_modelo"], MEDIDAS)
        self.assertEqual(exposto["medidas_texto"], "2 m × 3,70 m × 2,48 m")
        self.assertIn("brinquedao-modelo-5/perspectiva.webp", exposto["capa"])
        self.assertIn(NOME, [b["nome"] for b in resposta.context["brinquedos_arena"]])
        self.assertContains(resposta, f'data-vitrine3d data-modelo="/static/{GLB}')

    def test_a_roda_poe_na_vaga_dos_brinquedoes(self):
        # roda.js (vagaDe): pelo nome e pela categoria, sem nada escrito para ele
        node = shutil.which("node")
        if not node:
            self.skipTest("Sem node para rodar o JavaScript da arena")
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        dados = next(m for m in maquinas if m["nome"] == NOME)
        roda = Path(finders.find("site/arena/roda.js")).as_uri()
        codigo = f"import({json.dumps(roda)}).then((m) => console.log(m.vagaDe({json.dumps(dados)})))"
        resultado = subprocess.run([node, "--input-type=module", "-e", codigo], capture_output=True, text=True, timeout=60)
        self.assertEqual(resultado.stdout.strip(), "brinquedao", resultado.stderr)

    def test_cadastrado_toma_o_lugar_sem_duplicar(self):
        Brinquedos.objects.create(nome_brinquedo=NOME, descricao="x", avaliacao=5, voltz="")
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        mesmos = [m for m in maquinas if m["nome"] == NOME]
        self.assertEqual(len(mesmos), 1)
        self.assertIsInstance(mesmos[0]["id"], int)
        self.assertIn("brinquedao-modelo-5.glb", mesmos[0]["modelo"])
        self.assertEqual(mesmos[0]["medidas_modelo"], MEDIDAS)

    def test_e_modelo_pronto_de_brinquedao_no_monte_seu_projeto(self):
        itens = {i["id"]: i for i in projeto3d.catalogo()["itens"]}
        item = itens["modelo-brinquedao-modelo-5"]
        self.assertEqual((item["tipo"], item["area"], item["desenho"]), ("grande", "brinquedao", "playground"))
        self.assertEqual(item["medidas"], MEDIDAS)
        self.assertIn(GLB, item["modelo"])
        # cabe no maior brinquedão sob medida (largura × profundidade)
        maior = projeto3d.AREAS["brinquedao"]["max"]
        self.assertLessEqual((item["medidas"][1], item["medidas"][2]), tuple(maior))


class PasseioTests(TestCase):
    """O caminho do passeio fica no caminhos.js da arena (é desenho do objeto, como as animações)."""

    def test_tem_caminho_proprio_e_todo_modo_existe(self):
        js = Path(finders.find("site/arena/caminhos.js")).read_text(encoding="utf-8")
        inicio = js.index('CAMINHOS["brinquedao-modelo-5"] = () => [')
        caminho = js[inicio:js.index("\n];", inicio)]
        modos_usados = set(re.findall(r'\), "([a-z]+)"', caminho))
        bloco = js[js.index("const MODOS_DO_PASSEIO = {"):]
        modos = set(re.findall(r"^  ([a-z]+): \{", bloco[:bloco.index("\n};")], re.M))
        # sobe a escada da ponta, anda abaixado entre os sacos, passa de gatinhas pela cunha e desce o escorregador
        self.assertTrue({"subir", "agachado", "rastejar", "escorregar"} <= modos_usados)
        self.assertEqual(modos_usados - modos, set())
        # os pontos são escritos nas coordenadas do montar.js: M5 é o deslocamento que o gerar.cjs imprime
        self.assertIn("const M5 = (x, y, z) => [x / 1000 - 1.85, z / 1000, -y / 1000 - 0.241];", js)

    def test_o_passeio_nao_encosta_em_nada(self):
        # core/tests_js/passeio.mjs com a geometria de verdade do .glb: os olhos nunca a menos de 10 cm
        node = shutil.which("node")
        if not node:
            self.skipTest("Sem node para rodar o JavaScript da arena")
        script = Path(__file__).parent / "tests_js" / "passeio.mjs"
        resultado = subprocess.run([node, str(script), CHAVE], capture_output=True, text=True, timeout=300)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)


class CadastroTests(TestCase):
    def test_comando_cadastra_uma_vez_com_as_fotos_e_o_objeto(self):
        _categorias()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_brinquedao_modelo_5", stdout=StringIO())
                call_command("cadastrar_brinquedao_modelo_5", stdout=StringIO())
        brinquedo = Brinquedos.objects.get(nome_brinquedo=NOME)
        imagens = list(brinquedo.imagens_brinquedo.order_by("ordem"))
        self.assertEqual(
            [i.tipo for i in imagens],
            ["perfil", None, "lado_esquerdo", "lado_direito", None, None, None, None],
        )
        # a principal é a perspectiva da fábrica; depois as vistas do 3D, a planta e as duas do salão
        self.assertTrue(all(i.texto_alternativo.startswith(("Brinquedão Modelo 5", "Planta", "O Brinquedão")) for i in imagens))
        self.assertIn("perspectiva", brinquedo.imagem_brinquedo.name)
        self.assertEqual([c.nome_categoria for c in brinquedo.categorias_brinquedos.all()], ["Brinquedões"])
        # as medidas do cadastro são as da planta
        self.assertEqual((brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m), (2, Decimal("3.70"), 1))
        self.assertFalse(brinquedo.exibir_na_loja)
        self.assertIsNone(brinquedo.valor_brinquedo)
        self.assertIn("3,70 m", brinquedo.descricao)
        objeto = ObjetoTresD.objects.get()
        self.assertEqual((objeto.brinquedo, objeto.codigo, objeto.medidas), (brinquedo, CHAVE, MEDIDAS))

    def test_ja_no_catalogo_so_ganha_o_objeto(self):
        do_painel = Brinquedos.objects.create(nome_brinquedo="Brinquedão Modelo 5 (madeira)", descricao="do painel", avaliacao=5, voltz="")
        call_command("cadastrar_modelo_3d", CHAVE, stdout=StringIO())
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(do_painel.imagens_brinquedo.count(), 0)
        self.assertEqual(do_painel.objeto_3d.codigo, CHAVE)

    def test_migracao_so_cadastra_no_render_e_nao_derruba_o_deploy(self):
        rodar = migracao.Migration.operations[0].code
        self.assertEqual(migracao.Migration.dependencies, [("core", "0150_basquete_quadrinhos_fotos")])
        # fora do Render (computador, testes) não cadastra nada
        rodar(apps_reais, None)
        self.assertFalse(Brinquedos.objects.exists())
        # no Render, com o Cloudinary fora do ar: avisa o comando e segue, sem cadastro pela metade
        with override_settings(IS_RENDER=True), \
                mock.patch.object(ImagemBrinquedo._meta.get_field("imagem").storage, "save", side_effect=OSError("sem rede")), \
                mock.patch("builtins.print") as aviso:
            rodar(apps_reais, None)
        self.assertIn("cadastrar_modelo_3d brinquedao-modelo-5", aviso.call_args[0][0])
        self.assertFalse(Brinquedos.objects.exists())
        # no Render, com tudo funcionando: cadastra, com as oito fotos e o objeto 3D
        _categorias()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True), mock.patch("builtins.print"):
                rodar(apps_reais, None)
        brinquedo = Brinquedos.objects.get(nome_brinquedo=NOME)
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 8)
        self.assertFalse(brinquedo.exibir_na_loja)
        self.assertEqual(brinquedo.objeto_3d.codigo, CHAVE)

    def test_migracao_liga_o_que_ja_esta_no_catalogo_em_todo_lugar(self):
        ja = Brinquedos.objects.create(nome_brinquedo=NOME, descricao="x", avaliacao=5, voltz="")
        migracao.Migration.operations[0].code(apps_reais, None)
        self.assertEqual(ja.objeto_3d.codigo, CHAVE)
        self.assertEqual(Brinquedos.objects.count(), 1)


@override_settings(HOME_CACHE_TTL=600)
class HomeTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_sem_cadastro_do_objeto_vale_o_do_site_pelo_nome(self):
        Brinquedos.objects.create(
            nome_brinquedo=NOME, descricao="Brinquedo de teste", avaliacao=Decimal("4.50"),
            voltz="", imagem_brinquedo="imagens_brinquedos/foto.webp",
        )
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, f'data-modelo3d="/static/{GLB}', count=1)
