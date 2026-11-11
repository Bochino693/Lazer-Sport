"""O Brinquedão Ninja: o objeto 3D feito com o .3ds da fábrica e as imagens do projeto, e o cadastro.

O que estes testes protegem:

  * a máquina chamada "Brinquedão Ninja" leva o .glb para a Arena 3D, com
    as medidas que estão dentro do .glb (14,3 m com as duas camas
    elásticas), e o arquivo é leve; o .glb e as duas fotos existem;
  * antes de estar no catálogo, o objeto já aparece na arena (na seção dos
    brinquedões, na roda e não num reino), com a imagem do projeto de capa;
    cadastrado, o do catálogo toma o lugar (sem duplicar);
  * o passeio por dentro tem caminho próprio, e todo jeito de andar que ele
    usa (a tirolesa, inclusive) existe na Arena;
  * o comando cadastra uma vez só, com a capa (a cena no galpão, a da 0153)
    de foto principal, a frente e a planta na galeria, as medidas da planta e o objeto 3D ligado; se o brinquedo já
    está no catálogo, só ganha o objeto;
  * a migração liga o objeto em todo lugar, só cadastra no Render e nunca
    derruba o deploy;
  * na home, sem cadastro do objeto, vale o do site pelo nome.
"""

import importlib
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

from . import arena
from .cadastro_modelos import CADASTROS
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD
from .objetos_3d import ler_glb_do_site

migracao = importlib.import_module("core.migrations.0140_brinquedao_ninja")

GLB = "site/arena/modelos/brinquedao-ninja.glb"
MEDIDAS = [3.37, 14.3, 2.42]  # altura, largura, profundidade do .glb


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    storage = FileSystemStorage(location=pasta)
    return (
        mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage),
        mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage),
    )


def _categorias():
    CategoriasBrinquedos.objects.create(nome_categoria="Brinquedões", imagem_categoria="categorias/brinquedoes.png")
    CategoriasBrinquedos.objects.create(nome_categoria="Eletrônicos", imagem_categoria="categorias/eletronicos.png")


class ObjetoNaArenaTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_liga_pelo_nome_e_os_arquivos_existem(self):
        self.assertEqual(arena.modelo_da_maquina("Brinquedão Ninja")["id"], "brinquedao-ninja")
        self.assertEqual(arena.modelo_da_maquina("BRINQUEDAO NINJA 14m")["id"], "brinquedao-ninja")
        # o Modelo 2 continua com o dele, e "Ninja" sozinho não é o brinquedão
        self.assertEqual(arena.modelo_da_maquina("Brinquedão Modelo 2")["id"], "brinquedao-modelo-2")
        self.assertIsNone(arena.modelo_da_maquina("Ninja"))
        modelo = arena.modelo_da_maquina("Brinquedão Ninja")
        self.assertTrue(finders.find(modelo["arquivo"]))
        for _, arquivo in modelo["fotos"]:
            self.assertTrue(finders.find(modelo["pasta"] + arquivo), arquivo)
        for arquivo, _, _ in CADASTROS["brinquedao-ninja"]["fotos"]:
            self.assertTrue((CADASTROS["brinquedao-ninja"]["pasta"] / arquivo).exists(), arquivo)

    def test_medidas_sao_as_do_glb_e_ele_e_leve(self):
        modelo = arena.modelo_da_maquina("Brinquedão Ninja")
        self.assertEqual(list(modelo["medidas"]), MEDIDAS)
        self.assertEqual(ler_glb_do_site(GLB)["medidas"], MEDIDAS)
        # a Arena baixa o objeto inteiro: abaixo de 1 MB, como os outros
        self.assertLess(Path(finders.find(GLB)).stat().st_size, 1024 * 1024)

    def test_aparece_na_arena_antes_do_cadastro(self):
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5, voltz="220v")
        resposta = self.client.get(reverse("arena"))
        dados = {m["nome"]: m for m in resposta.context["arena_dados"]["maquinas"]}
        exposto = dados["Brinquedão Ninja"]
        self.assertIn(GLB, exposto["modelo"])
        self.assertEqual(exposto["modelo_id"], "brinquedao-ninja")
        self.assertEqual(exposto["grupo"], "brinquedoes")
        self.assertFalse(exposto["reino"])  # brinquedão: fica na roda, como o Modelo 2
        self.assertEqual(exposto["medidas_modelo"], MEDIDAS)
        self.assertIn("brinquedao-ninja/frente.webp", exposto["capa"])
        self.assertIn("14 m", exposto["medidas_texto"])
        self.assertIn("Brinquedão Ninja", [b["nome"] for b in resposta.context["brinquedos_arena"]])
        self.assertContains(resposta, f'data-vitrine3d data-modelo="/static/{GLB}')

    def test_cadastrado_toma_o_lugar_sem_duplicar(self):
        Brinquedos.objects.create(nome_brinquedo="Brinquedão Ninja", descricao="x", avaliacao=5, voltz="")
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        mesmos = [m for m in maquinas if m["nome"] == "Brinquedão Ninja"]
        self.assertEqual(len(mesmos), 1)
        self.assertIsInstance(mesmos[0]["id"], int)
        self.assertIn("brinquedao-ninja.glb", mesmos[0]["modelo"])
        self.assertEqual(mesmos[0]["medidas_modelo"], MEDIDAS)


class PasseioTests(TestCase):
    """O caminho do passeio fica no caminhos.js da arena (é desenho do objeto, como as animações)."""

    def test_tem_caminho_proprio_e_todo_modo_existe(self):
        js = Path(finders.find("site/arena/caminhos.js")).read_text(encoding="utf-8")
        inicio = js.index('"brinquedao-ninja": () => [')
        caminho = js[inicio:js.index("\n  ],", inicio)]
        tobogan = js[js.index("function toboganDoNinja()"):]
        tobogan = tobogan[:tobogan.index("\n}\n")]
        modos_usados = set(re.findall(r'\), "([a-z]+)"', caminho + tobogan))
        bloco = js[js.index("const MODOS_DO_PASSEIO = {"):]
        modos = set(re.findall(r"^  ([a-z]+): \{", bloco[:bloco.index("\n};")], re.M))
        # sobe, atravessa o andar de cima, desce o tobogã, pula nas camas e vai de tirolesa
        self.assertTrue({"subir", "agachado", "tubo", "rede", "escorregar", "pular", "tirolesa", "cair"} <= modos_usados)
        self.assertEqual(modos_usados - modos, set())
        self.assertIn("...toboganDoNinja()", caminho)


class CadastroTests(TestCase):
    def test_comando_cadastra_uma_vez_com_as_fotos_e_o_objeto(self):
        _categorias()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_brinquedao_ninja", stdout=StringIO())
                call_command("cadastrar_brinquedao_ninja", stdout=StringIO())
        brinquedo = Brinquedos.objects.get(nome_brinquedo="Brinquedão Ninja")
        self.assertEqual(
            list(brinquedo.imagens_brinquedo.order_by("ordem").values_list("tipo", flat=True)),
            ["perfil", None, None],
        )
        self.assertIn("brinquedao-ninja-capa", brinquedo.imagem_brinquedo.name)
        self.assertEqual([c.nome_categoria for c in brinquedo.categorias_brinquedos.all()], ["Brinquedões"])
        # as medidas do cadastro são as da planta da fábrica
        self.assertEqual((brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m), (Decimal("3.10"), 14, 2))
        self.assertFalse(brinquedo.exibir_na_loja)
        objeto = ObjetoTresD.objects.get()
        self.assertEqual((objeto.brinquedo, objeto.codigo, objeto.medidas), (brinquedo, "brinquedao-ninja", MEDIDAS))

    def test_ja_no_catalogo_so_ganha_o_objeto(self):
        do_painel = Brinquedos.objects.create(nome_brinquedo="Brinquedão Ninja 14 m", descricao="do painel", avaliacao=5, voltz="")
        call_command("cadastrar_modelo_3d", "brinquedao-ninja", stdout=StringIO())
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(do_painel.imagens_brinquedo.count(), 0)
        self.assertEqual(do_painel.objeto_3d.codigo, "brinquedao-ninja")

    def test_migracao_so_cadastra_no_render_e_nao_derruba_o_deploy(self):
        rodar = migracao.Migration.operations[0].code
        # fora do Render (computador, testes) não cadastra nada
        rodar(apps_reais, None)
        self.assertFalse(Brinquedos.objects.exists())
        # no Render, com o Cloudinary fora do ar: avisa e segue, sem cadastro pela metade
        with override_settings(IS_RENDER=True), \
                mock.patch.object(ImagemBrinquedo._meta.get_field("imagem").storage, "save", side_effect=OSError("sem rede")), \
                mock.patch("builtins.print") as aviso:
            rodar(apps_reais, None)
        self.assertIn("cadastrar_modelo_3d brinquedao-ninja", aviso.call_args[0][0])
        self.assertFalse(Brinquedos.objects.exists())
        # no Render, com tudo funcionando: cadastra, com as duas fotos e o objeto 3D
        _categorias()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True), mock.patch("builtins.print"):
                rodar(apps_reais, None)
        brinquedo = Brinquedos.objects.get(nome_brinquedo="Brinquedão Ninja")
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 3)
        self.assertEqual(brinquedo.objeto_3d.codigo, "brinquedao-ninja")

    def test_migracao_liga_o_que_ja_esta_no_catalogo_em_todo_lugar(self):
        ja = Brinquedos.objects.create(nome_brinquedo="Brinquedão Ninja", descricao="x", avaliacao=5, voltz="")
        migracao.Migration.operations[0].code(apps_reais, None)
        self.assertEqual(ja.objeto_3d.codigo, "brinquedao-ninja")
        self.assertEqual(Brinquedos.objects.count(), 1)


@override_settings(HOME_CACHE_TTL=600)
class HomeTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_sem_cadastro_do_objeto_vale_o_do_site_pelo_nome(self):
        Brinquedos.objects.create(
            nome_brinquedo="Brinquedão Ninja", descricao="Brinquedo de teste", avaliacao=Decimal("4.50"),
            voltz="", imagem_brinquedo="imagens_brinquedos/foto.webp",
        )
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, f'data-modelo3d="/static/{GLB}', count=1)
