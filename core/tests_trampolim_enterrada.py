"""O Trampolim de Enterrada: o objeto 3D feito com o .3ds da fábrica e o cadastro.

O que estes testes protegem:

  * a máquina chamada "Trampolim de Enterrada" leva o .glb para a Arena 3D,
    com as medidas que o próprio arquivo tem (e o .glb, a variante com a
    piscina de espuma e as fotos existem no estático, leves);
  * o nome tem "enterrada", mas é cama elástica: vai para "Trampolins e
    brinquedões", e não para as máquinas de basquete -- antes e depois de
    estar no catálogo; e o passeio da Arena tem o caminho dele;
  * antes de estar no catálogo, o objeto já aparece na arena, com a ficha e
    as fotos 2D; cadastrado, o do catálogo toma o lugar (sem duplicar);
  * o comando e a migração cadastram uma vez só, com as cinco fotos na
    galeria, a frente como foto principal, as medidas do projeto e o objeto
    3D ligado no cadastro -- e a migração nunca derruba o deploy, nem
    cadastra fora do Render (lá, só liga o objeto ao que já está no catálogo).
"""

import importlib
import tempfile
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
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD
from .objetos_3d import ler_glb_do_site

migracao = importlib.import_module("core.migrations.0139_trampolim_enterrada")

NOME = "Trampolim de Enterrada"
GLB = "site/arena/modelos/trampolim-enterrada.glb"


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    storage = FileSystemStorage(location=pasta)
    return (
        mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage),
        mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage),
    )


def _migrar():
    migracao.Migration.operations[0].code(apps_reais, None)


class ObjetoNaArenaTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_liga_pelo_nome_e_os_arquivos_existem(self):
        modelo = arena.modelo_da_maquina(NOME)
        self.assertEqual(modelo["id"], "trampolim-enterrada")
        self.assertEqual(arena.modelo_da_maquina("Trampolim Enterrada Kids")["id"], "trampolim-enterrada")
        self.assertIsNone(arena.modelo_da_maquina("Cama Elástica 3 m"))
        self.assertIsNone(arena.modelo_da_maquina("Basquete Enterrada"))
        # o .glb e a variante da espuma: leves, com as medidas do próprio arquivo
        for caminho in (GLB, "site/arena/modelos/trampolim-enterrada-espuma.glb"):
            achado = finders.find(caminho)
            self.assertTrue(achado, caminho)
            self.assertLess(Path(achado).stat().st_size, 600 * 1024, caminho)
            self.assertEqual(ler_glb_do_site(caminho)["medidas"], list(modelo["medidas"]), caminho)
        for _, arquivo in modelo["fotos"]:
            self.assertTrue(finders.find(modelo["pasta"] + arquivo), arquivo)

    def test_e_cama_elastica_e_nao_basquete(self):
        self.assertEqual(arena.modelo_3d(NOME), "cama_elastica")
        self.assertEqual(arena.modelo_3d("Trampolim Enterrada"), "cama_elastica")
        # o "enterrada" sozinho continua sendo basquete
        self.assertEqual(arena.modelo_3d("Basquete Enterrada"), "basquete")
        self.assertEqual(arena.grupo_da_arena(arena.modelo_3d(NOME), arena.jogo_da_maquina(NOME)), "brinquedoes")

    def test_o_passeio_tem_o_caminho_do_trampolim(self):
        # o caminho (subir a escada, pular nas camas, enterrar) fica no
        # caminhos.js da arena, pelo id do modelo: o id tem de ser o mesmo dos dois lados
        codigo = Path(finders.find("site/arena/caminhos.js")).read_text(encoding="utf-8")
        self.assertIn('CAMINHOS["trampolim-enterrada"]', codigo)

    def test_aparece_na_arena_antes_do_cadastro(self):
        resposta = self.client.get(reverse("arena"))
        dados = {m["nome"]: m for m in resposta.context["arena_dados"]["maquinas"]}
        exposto = dados[NOME]
        self.assertIn(GLB, exposto["modelo"])
        self.assertEqual(exposto["modelo_id"], "trampolim-enterrada")
        self.assertEqual((exposto["grupo"], exposto["reino"]), ("brinquedoes", False))
        self.assertEqual(exposto["medidas_modelo"], [2.98, 6.01, 2.25])
        self.assertEqual(exposto["medidas_texto"], "3,25 m × 6 m × 2 m")
        self.assertIn("trampolim-enterrada/frente.webp", exposto["capa"])
        nomes = [b["nome"] for b in resposta.context["brinquedos_arena"]]
        self.assertIn(NOME, nomes)

    def test_cadastrado_toma_o_lugar_sem_duplicar(self):
        Brinquedos.objects.create(
            nome_brinquedo=NOME, descricao="x", avaliacao=5, voltz="", altura_m=3.25, largura_m=6, profundidade_m=2,
        )
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        mesmos = [m for m in maquinas if m["nome"] == NOME]
        self.assertEqual(len(mesmos), 1)
        self.assertIsInstance(mesmos[0]["id"], int)
        self.assertIn("trampolim-enterrada.glb", mesmos[0]["modelo"])
        self.assertEqual((mesmos[0]["desenho"], mesmos[0]["grupo"]), ("cama_elastica", "brinquedoes"))
        self.assertEqual(mesmos[0]["medidas_modelo"], [2.98, 6.01, 2.25])


class CadastroTests(TestCase):
    def setUp(self):
        CategoriasBrinquedos.objects.create(nome_categoria="Camas Elásticas", imagem_categoria="categorias/camas.png")
        CategoriasBrinquedos.objects.create(nome_categoria="Brinquedões", imagem_categoria="categorias/brinquedoes.png")
        CategoriasBrinquedos.objects.create(nome_categoria="Eletrônicos", imagem_categoria="categorias/eletronicos.png")

    def test_comando_cadastra_uma_vez_com_as_fotos_e_o_objeto(self):
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_trampolim_enterrada", stdout=StringIO())
                saida = StringIO()
                call_command("cadastrar_trampolim_enterrada", stdout=saida)
        self.assertIn("Objeto 3D ligado", saida.getvalue())
        brinquedo = Brinquedos.objects.get(nome_brinquedo=NOME)
        self.assertEqual(
            list(brinquedo.imagens_brinquedo.order_by("ordem").values_list("tipo", flat=True)),
            ["perfil", "lado_esquerdo", "lado_direito", None, None],
        )
        self.assertIn("trampolim-enterrada-frente", brinquedo.imagem_brinquedo.name)
        self.assertEqual([c.nome_categoria for c in brinquedo.categorias_brinquedos.all()], ["Camas Elásticas"])
        self.assertEqual((brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m), (3.25, 6, 2))
        self.assertFalse(brinquedo.exibir_na_loja)
        objeto = ObjetoTresD.objects.get()
        self.assertEqual((objeto.brinquedo, objeto.codigo, objeto.arquivo_estatico), (brinquedo, "trampolim-enterrada", GLB))
        self.assertEqual(objeto.medidas, [2.98, 6.01, 2.25])

    def test_fotos_refaz_a_galeria_sem_duplicar(self):
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_trampolim_enterrada", stdout=StringIO())
                call_command("cadastrar_trampolim_enterrada", "--fotos", stdout=StringIO())
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo=NOME).count(), 1)
        self.assertEqual(Brinquedos.objects.get(nome_brinquedo=NOME).imagens_brinquedo.count(), 5)
        self.assertEqual(ObjetoTresD.objects.count(), 1)

    def test_migracao_so_cadastra_no_render_e_sem_derrubar_o_deploy(self):
        # fora do Render (computador, testes) não cadastra
        _migrar()
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo=NOME).exists())
        # no Render, com o Cloudinary fora do ar: avisa e segue, sem cadastro pela metade
        with override_settings(IS_RENDER=True), \
                mock.patch.object(ImagemBrinquedo._meta.get_field("imagem").storage, "save", side_effect=OSError("sem rede")), \
                mock.patch("builtins.print") as aviso:
            _migrar()
        self.assertIn("cadastrar_modelo_3d trampolim-enterrada", aviso.call_args[0][0])
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo=NOME).exists())
        self.assertFalse(ObjetoTresD.objects.exists())
        # no Render, com tudo funcionando: cadastra, com as fotos e o objeto 3D
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True), mock.patch("builtins.print"):
                _migrar()
        brinquedo = Brinquedos.objects.get(nome_brinquedo=NOME)
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 5)
        self.assertEqual(brinquedo.objeto_3d.codigo, "trampolim-enterrada")

    def test_migracao_liga_o_objeto_ao_que_ja_esta_no_catalogo(self):
        # cadastrado à mão no painel (com as fotos reais): fora do Render
        # também, ele só ganha o objeto 3D, e as fotos dele ficam
        manual = Brinquedos.objects.create(nome_brinquedo="Trampolim de Enterrada Pro", descricao="x", avaliacao=5)
        _migrar()
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(manual.objeto_3d.codigo, "trampolim-enterrada")
        self.assertEqual(manual.imagens_brinquedo.count(), 0)
