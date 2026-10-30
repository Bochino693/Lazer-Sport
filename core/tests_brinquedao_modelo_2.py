"""O Brinquedão Modelo 2: o objeto 3D feito com o .3ds da fábrica e o cadastro.

O que estes testes protegem:

  * a máquina chamada "Brinquedão Modelo 2" leva o .glb para a Arena 3D,
    com as medidas do objeto (e o arquivo e as fotos existem no estático);
  * antes de estar no catálogo, o objeto já aparece na arena, com a ficha
    e as fotos 2D; cadastrado, o do catálogo toma o lugar (sem duplicar);
  * o comando e a migração cadastram uma vez só, com as quatro fotos na
    galeria e a frente como foto principal -- e a migração nunca derruba
    o deploy, nem roda fora do Render.
"""

import importlib
import tempfile
from io import StringIO
from unittest import mock

from django.apps import apps as apps_reais
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import arena
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo

migracao = importlib.import_module("core.migrations.0113_brinquedao_modelo_2")


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    storage = FileSystemStorage(location=pasta)
    return (
        mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage),
        mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage),
    )


class ObjetoNaArenaTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_liga_pelo_nome_e_os_arquivos_existem(self):
        self.assertEqual(arena.modelo_da_maquina("Brinquedão Modelo 2")["id"], "brinquedao-modelo-2")
        self.assertIsNone(arena.modelo_da_maquina("Brinquedão Castelo Kids"))
        self.assertIsNone(arena.modelo_da_maquina("Lazer Shot"))
        for modelo in arena.MODELOS_3D:
            self.assertTrue(finders.find(modelo["arquivo"]), modelo["arquivo"])
            for _, arquivo in modelo["fotos"]:
                self.assertTrue(finders.find(modelo["pasta"] + arquivo), arquivo)

    def test_aparece_na_arena_antes_do_cadastro(self):
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5, voltz="220v")
        resposta = self.client.get(reverse("arena"))
        dados = {m["nome"]: m for m in resposta.context["arena_dados"]["maquinas"]}
        exposto = dados["Brinquedão Modelo 2"]
        self.assertIn("site/arena/modelos/brinquedao-modelo-2.glb", exposto["modelo"])
        self.assertEqual(exposto["grupo"], "brinquedoes")
        self.assertEqual(exposto["medidas_modelo"], [3.65, 11.4, 3.62])
        self.assertIn("brinquedao-modelo-2/frente.webp", exposto["capa"])
        self.assertContains(resposta, 'data-arena-zona="brinquedoes"')
        # a galeria de fotos é só do catálogo
        self.assertEqual([b["nome"] for b in resposta.context["brinquedos_arena"]], ["Air Game Hockey"])

    def test_cadastrado_toma_o_lugar_sem_duplicar(self):
        Brinquedos.objects.create(nome_brinquedo="Brinquedão Modelo 2", descricao="x", avaliacao=5, voltz="")
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        mesmos = [m for m in maquinas if m["nome"] == "Brinquedão Modelo 2"]
        self.assertEqual(len(mesmos), 1)
        self.assertIsInstance(mesmos[0]["id"], int)
        self.assertIn("brinquedao-modelo-2.glb", mesmos[0]["modelo"])
        self.assertEqual(mesmos[0]["grupo"], "brinquedoes")


class CadastroTests(TestCase):
    def test_comando_cadastra_uma_vez_com_as_fotos(self):
        CategoriasBrinquedos.objects.create(nome_categoria="Brinquedões", imagem_categoria="categorias/brinquedoes.png")
        CategoriasBrinquedos.objects.create(nome_categoria="Eletrônicos", imagem_categoria="categorias/eletronicos.png")
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_brinquedao_modelo_2", stdout=StringIO())
                saida = StringIO()
                call_command("cadastrar_brinquedao_modelo_2", stdout=saida)
        self.assertIn("já está cadastrado", saida.getvalue())
        brinquedo = Brinquedos.objects.get(nome_brinquedo="Brinquedão Modelo 2")
        self.assertEqual(
            list(brinquedo.imagens_brinquedo.order_by("ordem").values_list("tipo", flat=True)),
            ["perfil", "lado_esquerdo", "lado_direito", None],
        )
        self.assertTrue(brinquedo.imagem_brinquedo.name)
        self.assertEqual([c.nome_categoria for c in brinquedo.categorias_brinquedos.all()], ["Brinquedões"])
        self.assertEqual((brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m), (3.5, 11, 2))
        self.assertFalse(brinquedo.exibir_na_loja)

    def test_migracao_so_no_render_e_sem_derrubar_o_deploy(self):
        # fora do Render (computador, testes) não faz nada
        migracao.cadastrar(apps_reais, None)
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo="Brinquedão Modelo 2").exists())
        # no Render, com o Cloudinary fora do ar: avisa e segue, sem cadastro pela metade
        with override_settings(IS_RENDER=True), \
                mock.patch.object(ImagemBrinquedo._meta.get_field("imagem").storage, "save", side_effect=OSError("sem rede")), \
                mock.patch("builtins.print") as aviso:
            migracao.cadastrar(apps_reais, None)
        self.assertIn("cadastrar_brinquedao_modelo_2", aviso.call_args[0][0])
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo="Brinquedão Modelo 2").exists())
        # no Render, com tudo funcionando: cadastra
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True), mock.patch("builtins.print"):
                migracao.cadastrar(apps_reais, None)
        self.assertEqual(Brinquedos.objects.get(nome_brinquedo="Brinquedão Modelo 2").imagens_brinquedo.count(), 4)
