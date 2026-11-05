"""Brinquedo que contém outros (`ComponenteBrinquedo`, core/composicao.py).

O que se garante:
* brinquedão e espaço esportivo são conjuntos (pela categoria ou pelo nome);
* nada contém a si mesmo nem fecha um ciclo; a quantidade fica entre 1 e 99;
* o objeto 3D do Espaço Esportivo Modelo 1 sugere os dois Gol Flash e os
  dois Swish do catálogo, e a descrição sugere o que ela cita pelo nome;
* a página do conjunto mostra o que ele traz (com a quantidade) e a de
  cada item diz em que conjunto ele também vem -- e muda logo depois de
  ligar (o cache da página é limpo);
* o painel salva o conjunto e recusa o ciclo; a migração liga o espaço.
"""
import importlib
import json

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from . import composicao
from .models import Brinquedos, CategoriasBrinquedos, ComponenteBrinquedo

migracao = importlib.import_module("core.migrations.0132_espaco_esportivo_traz_gol_flash_e_swish")


def brinquedo(nome, categoria=None, descricao=""):
    b = Brinquedos.objects.create(nome_brinquedo=nome, descricao=descricao or "x", avaliacao=5)
    if categoria:
        cat, _ = CategoriasBrinquedos.objects.get_or_create(nome_categoria=categoria, defaults={"imagem_categoria": f"categorias/{categoria}.png"})
        b.categorias_brinquedos.add(cat)
    return b


class RegrasTests(TestCase):
    def setUp(self):
        self.espaco = brinquedo("Espaço Esportivo Modelo 1", "Espaço esportivo",
                                "Quadras, trampolins, dois círculos do Gol Flash e a Piscina de Bolinhas Kids.")
        self.gol = brinquedo("Gol Flash Arena", "Eletrônicos")
        self.swish = brinquedo("Swish Arena", "Eletrônicos")
        self.piscina = brinquedo("Piscina de Bolinhas Kids")
        self.circuito = brinquedo("Circuito Kids")

    def test_quem_e_conjunto(self):
        self.assertTrue(composicao.pode_conter(self.espaco))
        self.assertTrue(composicao.pode_conter(brinquedo("Brinquedão Selva", "Brinquedões")))
        self.assertTrue(composicao.pode_conter(self.circuito))  # pelo nome
        self.assertFalse(composicao.pode_conter(self.gol))

    def test_nao_contem_a_si_mesmo_nem_fecha_ciclo(self):
        with self.assertRaisesMessage(ValueError, "é ele mesmo"):
            composicao.salvar(self.espaco, [(self.espaco.pk, 1)])
        composicao.salvar(self.espaco, [(self.circuito.pk, 1)])
        with self.assertRaisesMessage(ValueError, "ficaria em volta"):
            composicao.salvar(self.circuito, [(self.espaco.pk, 1)])

    def test_salvar_troca_a_lista_e_ajusta_a_quantidade(self):
        composicao.salvar(self.espaco, [(self.gol.pk, 2), (self.swish.pk, 0), (self.gol.pk, 5)])
        itens = list(ComponenteBrinquedo.objects.filter(conjunto=self.espaco).values_list("item__nome_brinquedo", "quantidade"))
        self.assertEqual(itens, [("Gol Flash Arena", 2), ("Swish Arena", 1)])
        composicao.salvar(self.espaco, [(self.piscina.pk, 300)])
        self.assertEqual(list(self.espaco.componentes.values_list("quantidade", flat=True)), [99])

    def test_as_sugestoes_vem_do_objeto_3d_e_da_descricao(self):
        catalogo = list(Brinquedos.objects.values_list("pk", "nome_brinquedo"))
        sugestoes = {s["nome"]: s for s in composicao.sugestoes(self.espaco, catalogo)}
        self.assertEqual(sugestoes["Gol Flash Arena"]["quantidade"], 2)
        self.assertIn("objeto 3D", sugestoes["Gol Flash Arena"]["motivo"])
        self.assertEqual(sugestoes["Swish Arena"]["quantidade"], 2)
        self.assertEqual(sugestoes["Piscina de Bolinhas Kids"]["motivo"], "citado na descrição")
        # o que já está ligado não volta como sugestão
        self.assertNotIn("Gol Flash Arena", {s["nome"] for s in composicao.sugestoes(self.espaco, catalogo, [self.gol.pk])})

    def test_a_migracao_liga_o_espaco_aos_dois_gol_flash_e_aos_dois_swish(self):
        migracao.ligar(apps, None)
        itens = list(self.espaco.componentes.values_list("item__nome_brinquedo", "quantidade"))
        self.assertEqual(itens, [("Gol Flash Arena", 2), ("Swish Arena", 2)])
        # rodar de novo não duplica, e a lista montada à mão fica como está
        composicao.salvar(self.espaco, [(self.piscina.pk, 1)])
        migracao.ligar(apps, None)
        self.assertEqual(list(self.espaco.componentes.values_list("item__nome_brinquedo", flat=True)), ["Piscina de Bolinhas Kids"])


class PaginaDoProdutoTests(TestCase):
    def test_o_conjunto_mostra_o_que_traz_e_o_item_onde_tambem_vem(self):
        espaco = brinquedo("Espaço Esportivo Modelo 1", "Espaço esportivo")
        gol = brinquedo("Gol Flash Arena")
        pagina = self.client.get(reverse("brinquedo_detalhe", args=[espaco.pk]))
        self.assertNotContains(pagina, "O que vem neste espaço")  # ainda nada ligado (e a página fica em cache)
        composicao.salvar(espaco, [(gol.pk, 2)])
        pagina = self.client.get(reverse("brinquedo_detalhe", args=[espaco.pk]))
        self.assertContains(pagina, "O que vem neste espaço")
        self.assertContains(pagina, "<b>2×</b> Gol Flash Arena", html=False)
        self.assertContains(pagina, reverse("brinquedo_detalhe", args=[gol.pk]))
        item = self.client.get(reverse("brinquedo_detalhe", args=[gol.pk]))
        self.assertContains(item, "Também vem em")
        self.assertContains(item, "Espaço Esportivo Modelo 1")


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class PainelTests(TestCase):
    def setUp(self):
        self.espaco = brinquedo("Espaço Esportivo Modelo 1", "Espaço esportivo")
        self.gol = brinquedo("Gol Flash Arena")
        self.client.force_login(User.objects.create_superuser("chefe", "chefe@exemplo.com", "senha-segura"))

    def salvar(self, conjunto, itens):
        return self.client.post("/site/objetos-3d/", {"action": "conjunto_salvar", "brinquedo": conjunto.pk, "itens": json.dumps(itens)},
                                HTTP_HOST="interno.testserver", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_a_tela_mostra_o_conjunto_com_as_sugestoes_e_salva(self):
        tela = self.client.get("/site/objetos-3d/", HTTP_HOST="interno.testserver")
        self.assertContains(tela, 'data-conjunto="%d"' % self.espaco.pk)
        self.assertContains(tela, "sugestão do que vem dentro")
        resposta = self.salvar(self.espaco, [{"id": self.gol.pk, "quantidade": 2}])
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(self.espaco.componentes.get().quantidade, 2)
        tela = self.client.get("/site/objetos-3d/", HTTP_HOST="interno.testserver")
        self.assertContains(tela, "Traz dentro")
        self.assertContains(tela, "Vem em: Espaço Esportivo Modelo 1")

    def test_o_ciclo_e_recusado_com_o_motivo(self):
        circuito = brinquedo("Circuito Kids")
        self.assertEqual(self.salvar(self.espaco, [{"id": circuito.pk}]).status_code, 200)
        resposta = self.salvar(circuito, [{"id": self.espaco.pk}])
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("ficaria em volta", resposta.json()["msg"])
