"""O Brinquedão Modelo 4: o objeto 3D feito com o .3ds da fábrica e as imagens do projeto, e o cadastro.

O que estes testes protegem:

  * a máquina chamada "Brinquedão Modelo 4" leva o .glb para a Arena 3D,
    com as medidas que estão dentro do .glb (19,6 m: os dois trechos em "Z"),
    e o arquivo é leve; o .glb e as quatro imagens do projeto existem; o
    Modelo 2 e o Ninja continuam com os deles;
  * antes de estar no catálogo, o objeto já aparece na arena (na seção dos
    brinquedões, na roda e não num reino), com o render em perspectiva de
    capa; cadastrado, o do catálogo toma o lugar (sem duplicar);
  * no "Monte seu projeto" ele é um modelo pronto de Brinquedão;
  * o passeio por dentro tem caminho próprio, e todo jeito de andar que ele
    usa existe na Arena;
  * o comando cadastra uma vez só, com o render de foto principal e as
    outras três imagens na galeria, fora da loja, com o objeto 3D ligado; se
    o brinquedo já está no catálogo, só ganha o objeto;
  * a migração liga o objeto em todo lugar, só cadastra no Render e nunca
    derruba o deploy.
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

from . import arena, projeto3d
from .cadastro_modelos import CADASTROS
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD
from .objetos_3d import ler_glb_do_site

migracao = importlib.import_module("core.migrations.0142_brinquedao_modelo_4")

GLB = "site/arena/modelos/brinquedao-modelo-4.glb"
MEDIDAS = [3.55, 19.62, 5.98]  # altura, largura, profundidade do .glb


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
        self.assertEqual(arena.modelo_da_maquina("Brinquedão Modelo 4")["id"], "brinquedao-modelo-4")
        self.assertEqual(arena.modelo_da_maquina("BRINQUEDAO MODELO 4 (20 m)")["id"], "brinquedao-modelo-4")
        # os outros brinquedões continuam com os deles
        self.assertEqual(arena.modelo_da_maquina("Brinquedão Modelo 2")["id"], "brinquedao-modelo-2")
        self.assertEqual(arena.modelo_da_maquina("Brinquedão Ninja")["id"], "brinquedao-ninja")
        modelo = arena.modelo_da_maquina("Brinquedão Modelo 4")
        self.assertTrue(finders.find(modelo["arquivo"]))
        for _, arquivo in modelo["fotos"]:
            self.assertTrue(finders.find(modelo["pasta"] + arquivo), arquivo)
        for arquivo, _, _ in CADASTROS["brinquedao-modelo-4"]["fotos"]:
            self.assertTrue((CADASTROS["brinquedao-modelo-4"]["pasta"] / arquivo).exists(), arquivo)

    def test_medidas_sao_as_do_glb_e_ele_e_leve(self):
        modelo = arena.modelo_da_maquina("Brinquedão Modelo 4")
        self.assertEqual(list(modelo["medidas"]), MEDIDAS)
        self.assertEqual(ler_glb_do_site(GLB)["medidas"], MEDIDAS)
        # a Arena baixa o objeto inteiro: abaixo de 1 MB, como os outros
        self.assertLess(Path(finders.find(GLB)).stat().st_size, 1024 * 1024)

    def test_aparece_na_arena_antes_do_cadastro(self):
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5, voltz="220v")
        resposta = self.client.get(reverse("arena"))
        dados = {m["nome"]: m for m in resposta.context["arena_dados"]["maquinas"]}
        exposto = dados["Brinquedão Modelo 4"]
        self.assertIn(GLB, exposto["modelo"])
        self.assertEqual(exposto["modelo_id"], "brinquedao-modelo-4")
        self.assertEqual(exposto["grupo"], "brinquedoes")
        self.assertFalse(exposto["reino"])  # brinquedão: fica na roda, como o Ninja
        self.assertEqual(exposto["medidas_modelo"], MEDIDAS)
        self.assertIn("brinquedao-modelo-4/perspectiva.webp", exposto["capa"])
        self.assertIn("19,6 m", exposto["medidas_texto"])
        self.assertIn("Brinquedão Modelo 4", [b["nome"] for b in resposta.context["brinquedos_arena"]])
        self.assertContains(resposta, f'data-vitrine3d data-modelo="/static/{GLB}')

    def test_cadastrado_toma_o_lugar_sem_duplicar(self):
        Brinquedos.objects.create(nome_brinquedo="Brinquedão Modelo 4", descricao="x", avaliacao=5, voltz="")
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        mesmos = [m for m in maquinas if m["nome"] == "Brinquedão Modelo 4"]
        self.assertEqual(len(mesmos), 1)
        self.assertIsInstance(mesmos[0]["id"], int)
        self.assertIn("brinquedao-modelo-4.glb", mesmos[0]["modelo"])
        self.assertEqual(mesmos[0]["medidas_modelo"], MEDIDAS)

    def test_e_um_modelo_pronto_de_brinquedao_no_monte_seu_projeto(self):
        itens = {i["id"]: i for i in projeto3d.catalogo()["itens"]}
        item = itens["modelo-brinquedao-modelo-4"]
        self.assertEqual((item["tipo"], item["area"]), ("grande", "brinquedao"))
        self.assertEqual(item["medidas"], MEDIDAS)
        self.assertIn(GLB, item["modelo"])


class PasseioTests(TestCase):
    """O caminho do passeio fica no arena3d.js (é desenho do objeto, como as animações)."""

    def test_tem_caminho_proprio_e_todo_modo_existe(self):
        js = Path(finders.find("site/arena/arena3d.js")).read_text(encoding="utf-8")
        inicio = js.index('CAMINHOS["brinquedao-modelo-4"] = () => [')
        caminho = js[inicio:js.index("\n];", inicio)]
        tobogan = js[js.index("function toboganDoModelo4()"):]
        tobogan = tobogan[:tobogan.index("\n}\n")]
        modos_usados = set(re.findall(r'\), "([a-z]+)"', caminho + tobogan))
        bloco = js[js.index("const MODOS_DO_PASSEIO = {"):]
        modos = set(re.findall(r"^  ([a-z]+): \{", bloco[:bloco.index("\n};")], re.M))
        # sobe a escada, atravessa o andar de cima pelos rolos e redes e desce o tobogã até a piscina
        self.assertTrue({"subir", "agachado", "tubo", "rede", "escorregar", "cair"} <= modos_usados)
        self.assertEqual(modos_usados - modos, set())
        self.assertIn("...toboganDoModelo4()", caminho)


class CadastroTests(TestCase):
    def test_comando_cadastra_uma_vez_com_as_fotos_e_o_objeto(self):
        _categorias()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_brinquedao_modelo_4", stdout=StringIO())
                call_command("cadastrar_brinquedao_modelo_4", stdout=StringIO())
        brinquedo = Brinquedos.objects.get(nome_brinquedo="Brinquedão Modelo 4")
        self.assertEqual(
            list(brinquedo.imagens_brinquedo.order_by("ordem").values_list("tipo", flat=True)),
            ["perfil", None, None, None],
        )
        self.assertTrue(brinquedo.imagem_brinquedo.name)
        self.assertEqual([c.nome_categoria for c in brinquedo.categorias_brinquedos.all()], ["Brinquedões"])
        self.assertEqual((brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m), (Decimal("3.55"), Decimal("19.6"), 6))
        # "não disponível na loja", como os outros
        self.assertFalse(brinquedo.exibir_na_loja)
        objeto = ObjetoTresD.objects.get()
        self.assertEqual((objeto.brinquedo, objeto.codigo, objeto.medidas), (brinquedo, "brinquedao-modelo-4", MEDIDAS))

    def test_ja_no_catalogo_so_ganha_o_objeto(self):
        do_painel = Brinquedos.objects.create(nome_brinquedo="Brinquedão Modelo 4 - 20 m", descricao="do painel", avaliacao=5, voltz="")
        call_command("cadastrar_modelo_3d", "brinquedao-modelo-4", stdout=StringIO())
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(do_painel.imagens_brinquedo.count(), 0)
        self.assertEqual(do_painel.objeto_3d.codigo, "brinquedao-modelo-4")

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
        self.assertIn("cadastrar_modelo_3d brinquedao-modelo-4", aviso.call_args[0][0])
        self.assertFalse(Brinquedos.objects.exists())
        # no Render, com tudo funcionando: cadastra, com as quatro fotos e o objeto 3D
        _categorias()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True), mock.patch("builtins.print"):
                rodar(apps_reais, None)
        brinquedo = Brinquedos.objects.get(nome_brinquedo="Brinquedão Modelo 4")
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 4)
        self.assertEqual(brinquedo.objeto_3d.codigo, "brinquedao-modelo-4")

    def test_migracao_liga_o_que_ja_esta_no_catalogo_em_todo_lugar(self):
        ja = Brinquedos.objects.create(nome_brinquedo="Brinquedão Modelo 4", descricao="x", avaliacao=5, voltz="")
        migracao.Migration.operations[0].code(apps_reais, None)
        self.assertEqual(ja.objeto_3d.codigo, "brinquedao-modelo-4")
        self.assertEqual(Brinquedos.objects.count(), 1)
