"""O Brinquedão Selva: o objeto 3D feito com o .3ds da fábrica e o cadastro.

O que estes testes protegem:

  * a máquina chamada "Brinquedão Selva..." leva o .glb para a Arena 3D,
    com as medidas do objeto (e o arquivo existe no estático);
  * as outras máquinas continuam com o volume feito das fotos;
  * o comando cadastra uma vez só, com as quatro fotos na galeria e a
    frente como foto principal, na zona dos brinquedões.
"""

import tempfile
from io import StringIO
from unittest import mock

from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import arena
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo


class ModeloDaFabricaTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_liga_pelo_nome(self):
        modelo = arena.modelo_da_maquina("Brinquedão Selva 11m")
        self.assertEqual(modelo["id"], "brinquedao-selva-11m")
        self.assertIsNone(arena.modelo_da_maquina("Brinquedão Castelo Kids"))
        self.assertIsNone(arena.modelo_da_maquina("Lazer Shot"))
        for item in arena.MODELOS_3D:
            self.assertTrue(finders.find(item["arquivo"]), item["arquivo"])

    def test_vai_para_a_arena_com_o_objeto(self):
        Brinquedos.objects.create(nome_brinquedo="Brinquedão Selva 11m", descricao="x", avaliacao=5, voltz="")
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5, voltz="220v")
        resposta = self.client.get(reverse("arena"))
        dados = {m["nome"]: m for m in resposta.context["arena_dados"]["maquinas"]}
        selva = dados["Brinquedão Selva 11m"]
        self.assertIn("site/arena/modelos/brinquedao-selva-11m.glb", selva["modelo"])
        self.assertEqual(selva["medidas_modelo"], [3.65, 11.4, 3.62])
        self.assertEqual(selva["grupo"], "brinquedoes")
        self.assertEqual(dados["Air Game Hockey"]["modelo"], "")
        self.assertContains(resposta, 'data-gltf="')


class CadastroDoBrinquedaoTests(TestCase):
    def test_cadastra_uma_vez_com_as_fotos(self):
        CategoriasBrinquedos.objects.create(nome_categoria="Brinquedões", imagem_categoria="categorias/brinquedoes.png")
        CategoriasBrinquedos.objects.create(nome_categoria="Eletrônicos", imagem_categoria="categorias/eletronicos.png")
        with tempfile.TemporaryDirectory() as pasta:
            storage = FileSystemStorage(location=pasta)
            with mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage), \
                    mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage):
                call_command("cadastrar_brinquedao_selva", stdout=StringIO())
                saida = StringIO()
                call_command("cadastrar_brinquedao_selva", stdout=saida)
        self.assertIn("já está cadastrado", saida.getvalue())
        brinquedo = Brinquedos.objects.get(nome_brinquedo="Brinquedão Selva 11m")
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo="Brinquedão Selva 11m").count(), 1)
        self.assertEqual(
            list(brinquedo.imagens_brinquedo.order_by("ordem").values_list("tipo", flat=True)),
            ["perfil", "lado_esquerdo", "lado_direito", None],
        )
        self.assertTrue(brinquedo.imagem_brinquedo.name)
        self.assertEqual([c.nome_categoria for c in brinquedo.categorias_brinquedos.all()], ["Brinquedões"])
        self.assertEqual((brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m), (3.5, 11, 2))
        self.assertFalse(brinquedo.exibir_na_loja)
