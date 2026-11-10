"""O Brinquedão Modelo 3: o objeto 3D feito com as três imagens do projeto, e o cadastro.

O que estes testes protegem:

  * a máquina chamada "Brinquedão Modelo 3" leva o .glb para a Arena 3D, com
    as medidas que estão dentro do .glb (o L de 10 m × 5,20 m, 3,75 m de
    altura), e o arquivo é leve; o .glb e as quatro fotos existem; o Modelo 2
    continua com o dele;
  * a planta é o L do projeto: a piscina de bolinhas e o tobogã ficam DENTRO
    da barra, nos últimos 2 m (o espaço que ele ocupa decide o que cabe no
    "Monte seu projeto");
  * antes de estar no catálogo, o objeto já aparece na arena (na seção dos
    brinquedões, na roda e não num reino), com a frente de capa; cadastrado,
    o do catálogo toma o lugar (sem duplicar);
  * no "Monte seu projeto" ele é um modelo pronto de Brinquedão;
  * o passeio por dentro tem caminho próprio (sobe a torre, a rede, o tobogã,
    a piscina), e todo jeito de andar que ele usa existe na Arena;
  * o comando cadastra uma vez só, com a frente de foto principal, os dois
    lados e a planta na galeria, as medidas do projeto e o objeto 3D ligado;
    se o brinquedo já está no catálogo, só ganha o objeto;
  * a migração liga o objeto em todo lugar, só cadastra no Render e nunca
    derruba o deploy;
  * na home, sem cadastro do objeto, vale o do site pelo nome.
"""

import importlib
import math
import re
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

migracao = importlib.import_module("core.migrations.0143_brinquedao_modelo_3")

NOME = "Brinquedão Modelo 3"
GLB = "site/arena/modelos/brinquedao-modelo-3.glb"
MEDIDAS = [3.75, 10.0, 5.2]  # altura, largura, profundidade do .glb


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
        self.assertEqual(arena.modelo_da_maquina(NOME)["id"], "brinquedao-modelo-3")
        self.assertEqual(arena.modelo_da_maquina("BRINQUEDAO MODELO 3 em L")["id"], "brinquedao-modelo-3")
        # o Modelo 2 continua com o dele, e o "3" não pega o "30"
        self.assertEqual(arena.modelo_da_maquina("Brinquedão Modelo 2")["id"], "brinquedao-modelo-2")
        self.assertIsNone(arena.modelo_da_maquina("Brinquedão Modelo 30"))
        self.assertEqual(arena.modelo_3d(NOME), "playground")
        modelo = arena.modelo_da_maquina(NOME)
        self.assertTrue(finders.find(modelo["arquivo"]))
        for _, arquivo in modelo["fotos"]:
            self.assertTrue(finders.find(modelo["pasta"] + arquivo), arquivo)
        for arquivo, _, _ in CADASTROS["brinquedao-modelo-3"]["fotos"]:
            self.assertTrue((CADASTROS["brinquedao-modelo-3"]["pasta"] / arquivo).exists(), arquivo)

    def test_medidas_sao_as_do_glb_e_ele_e_leve(self):
        modelo = arena.modelo_da_maquina(NOME)
        self.assertEqual(list(modelo["medidas"]), MEDIDAS)
        self.assertEqual(ler_glb_do_site(GLB)["medidas"], MEDIDAS)
        # a Arena baixa o objeto inteiro: abaixo de 800 KB
        self.assertLess(Path(finders.find(GLB)).stat().st_size, 800 * 1024)

    def test_a_piscina_e_o_tobogan_ficam_dentro_da_barra(self):
        # No objeto (centralizado, a frente em +z): a barra de 10 m × 2 m vai
        # de x = -5 a 5 e de z = -2,6 (o fundo) a -0,6 (a frente dela); a perna
        # é que avança até z = 2,6. A piscina e a espiral ocupam os últimos 2 m
        # da barra (x de 3 a 5), sem nada saindo na frente dela.
        for nome in ("bolinhas", "toboga-azul", "toboga-magenta", "toboga-amarelo", "toboga-laranja"):
            baixo, alto = _caixa_do_no(nome)
            self.assertGreater(alto[0], baixo[0], nome)  # o nó existe e tem malha
            self.assertGreaterEqual(baixo[0], 3.0 - 0.01, nome)
            self.assertLessEqual(alto[0], 5.0 + 0.01, nome)
            self.assertGreaterEqual(baixo[2], -2.6 - 0.01, nome)
            self.assertLessEqual(alto[2], -0.6 + 0.01, nome)
        # a boca do tobogã sai do piso do 2º andar (1,90 m) e o tubo chega à piscina
        baixo, alto = _caixa_do_no("toboga-azul")
        self.assertLess(baixo[1], 0.45)
        self.assertGreater(alto[1], 2.3)

    def test_aparece_na_arena_antes_do_cadastro(self):
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5, voltz="220v")
        resposta = self.client.get(reverse("arena"))
        dados = {m["nome"]: m for m in resposta.context["arena_dados"]["maquinas"]}
        exposto = dados[NOME]
        self.assertIn(GLB, exposto["modelo"])
        self.assertEqual(exposto["modelo_id"], "brinquedao-modelo-3")
        self.assertEqual((exposto["grupo"], exposto["reino"]), ("brinquedoes", False))  # na roda, como o Modelo 2
        self.assertEqual(exposto["medidas_modelo"], MEDIDAS)
        self.assertEqual(exposto["medidas_texto"], "3,75 m × 10 m × 5,20 m")
        self.assertIn("brinquedao-modelo-3/frente.webp", exposto["capa"])
        self.assertIn(NOME, [b["nome"] for b in resposta.context["brinquedos_arena"]])
        self.assertContains(resposta, f'data-vitrine3d data-modelo="/static/{GLB}')

    def test_cadastrado_toma_o_lugar_sem_duplicar(self):
        Brinquedos.objects.create(nome_brinquedo=NOME, descricao="x", avaliacao=5, voltz="")
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        mesmos = [m for m in maquinas if m["nome"] == NOME]
        self.assertEqual(len(mesmos), 1)
        self.assertIsInstance(mesmos[0]["id"], int)
        self.assertIn("brinquedao-modelo-3.glb", mesmos[0]["modelo"])
        self.assertEqual(mesmos[0]["medidas_modelo"], MEDIDAS)

    def test_e_modelo_pronto_de_brinquedao_no_monte_seu_projeto(self):
        itens = {i["id"]: i for i in projeto3d.catalogo()["itens"]}
        item = itens["modelo-brinquedao-modelo-3"]
        self.assertEqual((item["tipo"], item["area"], item["desenho"]), ("grande", "brinquedao", "playground"))
        self.assertEqual(item["medidas"], MEDIDAS)
        self.assertIn(GLB, item["modelo"])
        # cabe no maior brinquedão sob medida (largura × profundidade)
        maior = projeto3d.AREAS["brinquedao"]["max"]
        self.assertLessEqual((item["medidas"][1], item["medidas"][2]), maior)


class PasseioTests(TestCase):
    """O caminho do passeio fica no caminhos.js da arena (é desenho do objeto, como as animações)."""

    def test_tem_caminho_proprio_e_todo_modo_existe(self):
        js = Path(finders.find("site/arena/caminhos.js")).read_text(encoding="utf-8")
        inicio = js.index('CAMINHOS["brinquedao-modelo-3"] = () => [')
        caminho = js[inicio:js.index("\n];", inicio)]
        tobogan = js[js.index("function toboganDoModelo3()"):]
        tobogan = tobogan[:tobogan.index("\n}\n")]
        modos_usados = set(re.findall(r'\), "([a-z]+)"', caminho + tobogan))
        bloco = js[js.index("const MODOS_DO_PASSEIO = {"):]
        modos = set(re.findall(r"^  ([a-z]+): \{", bloco[:bloco.index("\n};")], re.M))
        # sobe a torre, atravessa a passarela de rede, passa pelos sacos, desce o tobogã e cai na piscina
        self.assertTrue({"subir", "rede", "agachado", "escorregar", "cair"} <= modos_usados)
        self.assertEqual(modos_usados - modos, set())
        self.assertIn("...toboganDoModelo3()", caminho)


class CadastroTests(TestCase):
    def test_comando_cadastra_uma_vez_com_as_fotos_e_o_objeto(self):
        _categorias()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_brinquedao_modelo_3", stdout=StringIO())
                call_command("cadastrar_brinquedao_modelo_3", stdout=StringIO())
        brinquedo = Brinquedos.objects.get(nome_brinquedo=NOME)
        self.assertEqual(
            list(brinquedo.imagens_brinquedo.order_by("ordem").values_list("tipo", flat=True)),
            ["perfil", "lado_esquerdo", "lado_direito", None],
        )
        self.assertTrue(brinquedo.imagem_brinquedo.name)
        self.assertEqual([c.nome_categoria for c in brinquedo.categorias_brinquedos.all()], ["Brinquedões"])
        # as medidas do cadastro são as do projeto
        self.assertEqual((brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m), (Decimal("3.75"), 10, Decimal("5.20")))
        self.assertFalse(brinquedo.exibir_na_loja)
        objeto = ObjetoTresD.objects.get()
        self.assertEqual((objeto.brinquedo, objeto.codigo, objeto.medidas), (brinquedo, "brinquedao-modelo-3", MEDIDAS))

    def test_ja_no_catalogo_so_ganha_o_objeto(self):
        do_painel = Brinquedos.objects.create(nome_brinquedo="Brinquedão Modelo 3 (10 m)", descricao="do painel", avaliacao=5, voltz="")
        call_command("cadastrar_modelo_3d", "brinquedao-modelo-3", stdout=StringIO())
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(do_painel.imagens_brinquedo.count(), 0)
        self.assertEqual(do_painel.objeto_3d.codigo, "brinquedao-modelo-3")

    def test_migracao_so_cadastra_no_render_e_nao_derruba_o_deploy(self):
        rodar = migracao.Migration.operations[0].code
        self.assertEqual(migracao.Migration.dependencies, [("core", "0142_brinquedao_modelo_4")])
        # fora do Render (computador, testes) não cadastra nada
        rodar(apps_reais, None)
        self.assertFalse(Brinquedos.objects.exists())
        # no Render, com o Cloudinary fora do ar: avisa e segue, sem cadastro pela metade
        with override_settings(IS_RENDER=True), \
                mock.patch.object(ImagemBrinquedo._meta.get_field("imagem").storage, "save", side_effect=OSError("sem rede")), \
                mock.patch("builtins.print") as aviso:
            rodar(apps_reais, None)
        self.assertIn("cadastrar_modelo_3d brinquedao-modelo-3", aviso.call_args[0][0])
        self.assertFalse(Brinquedos.objects.exists())
        # no Render, com tudo funcionando: cadastra, com as quatro fotos e o objeto 3D
        _categorias()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True), mock.patch("builtins.print"):
                rodar(apps_reais, None)
        brinquedo = Brinquedos.objects.get(nome_brinquedo=NOME)
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 4)
        self.assertEqual(brinquedo.objeto_3d.codigo, "brinquedao-modelo-3")

    def test_migracao_liga_o_que_ja_esta_no_catalogo_em_todo_lugar(self):
        ja = Brinquedos.objects.create(nome_brinquedo=NOME, descricao="x", avaliacao=5, voltz="")
        migracao.Migration.operations[0].code(apps_reais, None)
        self.assertEqual(ja.objeto_3d.codigo, "brinquedao-modelo-3")
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
