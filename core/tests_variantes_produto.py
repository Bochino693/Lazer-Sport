"""Os adesivos de um produto: um produto, vários adesivos (LEIA-ME, seção 72).

O cliente: "os dois devem se tornar o mesmo objeto, como um adesivo
diferente, ele quem deve ser o diferencial, rodando as duas imagens em todo
objeto também canalizando os dois objetos 3d". O que estes testes protegem:

  * o modelo (core.models.VarianteAdesivo) e o `juntar`/`separar` de
    core/variantes.py: a ficha que vira adesivo fica desativada (nada é
    apagado) e rodar de novo não duplica;
  * as migrações: a 0160 só com o esquema e a 0161 só com os dados (o
    Postgres não aceita os dois juntos); a 0161 junta os dois pares (o
    Basquete Street Quadrinhos antes vira o Basquete Home Quadrinhos) e deixa
    o Basquete Street sozinho;
  * o endereço antigo da ficha vai, permanente, para o produto com ?adesivo=;
  * nas listas (a home, a categoria, /brinquedos/, a loja, a busca e a
    Arena) o produto aparece uma vez, com o selo "2 adesivos" e as capas
    dos dois; a ficha não aparece;
  * na página, as fichas "Adesivo: A · B"; o ?adesivo= troca as fotos e o 3D;
    o adesivo sem 3D leva ao que tem; o adesivo vai na mensagem do orçamento;
  * o carrinho guarda o adesivo, o pedido o leva no nome e, se o pagamento
    não sai, ele volta para o carrinho com o adesivo.
"""

import importlib
from decimal import Decimal
from urllib.parse import quote

from django.apps import apps as apps_de_hoje
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.migrations.operations import AddField, CreateModel, RunPython
from django.test import TestCase
from django.urls import reverse

from . import arena, variantes
from .models import (
    Brinquedos,
    CategoriasBrinquedos,
    ImagemBrinquedo,
    ItemCarrinho,
    VarianteAdesivo,
)
from .services import criar_pedido_a_partir_do_carrinho
from .views_arena import dados_publicos_da_arena

migracao_0160 = importlib.import_module("core.migrations.0160_variantes_de_adesivo")
migracao_0161 = importlib.import_module("core.migrations.0161_juntar_variantes_de_adesivo")

PAR = ("Air Game Kids", ("Astronautas", "astronautas"), [("Air Game Kids Alienígenas", "Alienígenas", "alienigenas")])


def _calado(*_args, **_kwargs):
    return None


def _produto(nome, foto, categoria=None, **campos):
    dados = {
        "descricao": f"{nome}.", "avaliacao": Decimal("4.80"), "voltz": "220V",
        "valor_brinquedo": Decimal("4990.00"), "exibir_na_loja": True,
        "imagem_brinquedo": f"imagens_brinquedos/{foto}.png",
    }
    dados.update(campos)
    brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, **dados)
    ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="perfil", ordem=1,
                                   imagem=f"imagens_brinquedos/{foto}.png", texto_alternativo=f"{nome}: a foto")
    if categoria is not None:
        brinquedo.categorias_brinquedos.add(categoria)
    return brinquedo


class _ComPar(TestCase):
    """O Air Game Kids (os astronautas) com o Air Game Kids Alienígenas virando o adesivo dele."""

    def setUp(self):
        cache.clear()
        self.categoria = CategoriasBrinquedos.objects.create(nome_categoria="Jogos de Mesa", imagem_categoria="categorias/m.png")
        self.base = _produto("Air Game Kids", "astronautas", self.categoria)
        self.ficha = _produto("Air Game Kids Alienígenas", "alienigenas", self.categoria)
        produto, padrao, fichas = PAR
        variantes.juntar(produto, padrao, fichas, Brinquedos, VarianteAdesivo, avisar=_calado)
        self.base.refresh_from_db()
        self.ficha.refresh_from_db()
        cache.clear()


class ModeloTests(_ComPar):
    def test_juntar_faz_os_adesivos_e_desativa_a_ficha(self):
        lista = list(self.base.variantes_adesivo.all())
        self.assertEqual([(v.nome, v.slug, v.padrao, v.ordem) for v in lista],
                         [("Astronautas", "astronautas", True, 1), ("Alienígenas", "alienigenas", False, 2)])
        self.assertIsNone(lista[0].origem)
        self.assertEqual(lista[0].ficha, self.base)
        self.assertEqual((lista[1].origem, lista[1].ficha), (self.ficha, self.ficha))
        self.assertFalse(self.ficha.ativo)
        self.assertTrue(self.base.ativo)
        # nada foi apagado: a ficha e as fotos dela continuam lá
        self.assertEqual(self.ficha.imagens_brinquedo.count(), 1)

    def test_rodar_de_novo_nao_duplica(self):
        produto, padrao, fichas = PAR
        variantes.juntar(produto, padrao, fichas, Brinquedos, VarianteAdesivo, avisar=_calado)
        self.assertEqual(VarianteAdesivo.objects.count(), 2)

    def test_o_slug_e_unico_no_produto(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            VarianteAdesivo.objects.create(brinquedo=self.base, nome="Outro", slug="alienigenas")

    def test_separar_desfaz(self):
        variantes.separar("Air Game Kids", Brinquedos, VarianteAdesivo, avisar=_calado)
        self.ficha.refresh_from_db()
        self.assertTrue(self.ficha.ativo)
        self.assertEqual(VarianteAdesivo.objects.count(), 0)

    def test_o_preco_do_produto_que_fica_nao_muda(self):
        # o Air Game Kids com R$ 6.990,00 (o painel); a ficha com outro preço: o produto fica com o dele
        self.base.refresh_from_db()
        self.assertEqual(self.base.valor_brinquedo, Decimal("4990.00"))
        VarianteAdesivo.objects.all().delete()
        Brinquedos.objects.filter(pk=self.base.pk).update(valor_brinquedo=Decimal("6990.00"))
        Brinquedos.objects.filter(pk=self.ficha.pk).update(valor_brinquedo=Decimal("1234.00"), ativo=True)
        variantes.juntar(*PAR[:2], PAR[2], Brinquedos, VarianteAdesivo, avisar=_calado)
        self.base.refresh_from_db()
        self.assertEqual(self.base.valor_brinquedo, Decimal("6990.00"))
        # sem preço, o Air Game Kids fica com R$ 6.990,00
        Brinquedos.objects.filter(pk=self.base.pk).update(valor_brinquedo=None)
        variantes.juntar(*PAR[:2], PAR[2], Brinquedos, VarianteAdesivo, avisar=_calado)
        self.base.refresh_from_db()
        self.assertEqual(self.base.valor_brinquedo, Decimal("6990.00"))

    def test_sem_o_produto_nao_faz_nada(self):
        VarianteAdesivo.objects.all().delete()
        self.base.delete()
        self.assertIsNone(variantes.juntar(*PAR[:2], PAR[2], Brinquedos, VarianteAdesivo, avisar=_calado))
        self.assertEqual(VarianteAdesivo.objects.count(), 0)

    def test_um_adesivo_so_nao_vira_fichas(self):
        VarianteAdesivo.objects.filter(padrao=False).update(ativo=False)
        self.assertEqual(variantes.variantes_do_produto(self.base), [])
        self.assertIsNone(variantes.do_card(self.base.pk))


class MigracaoTests(TestCase):
    def test_esquema_e_dados_em_arquivos_separados(self):
        esquema = migracao_0160.Migration.operations
        dados = migracao_0161.Migration.operations
        self.assertTrue(esquema and all(isinstance(op, (AddField, CreateModel)) for op in esquema))
        # e nada nosso depois da 0161 (o coordenador numera as próximas)
        self.assertEqual(len(dados), 2)
        self.assertTrue(dados and all(isinstance(op, RunPython) for op in dados))
        self.assertIn(("core", "0160_variantes_de_adesivo"), migracao_0161.Migration.dependencies)

    def test_a_0161_junta_os_dois_pares_e_o_street_fica_sozinho(self):
        cache.clear()
        base_air = _produto("AIR GAME KIDS", "astronautas")
        ficha_air = _produto("Air Game Kids Alienígenas", "alienigenas")
        base_bq = _produto("Basquete Home", "basquete-home")
        ficha_bq = _produto("Basquete Street Quadrinhos", "basquete-street-quadrinhos-capa")
        ImagemBrinquedo.objects.filter(brinquedo=ficha_bq).update(texto_alternativo="Basquete Street Quadrinhos de frente")
        street = _produto("Basquete Street", "basquete-street")
        for _vez in range(2):  # pode rodar de novo
            variantes.migrar(apps_de_hoje, None, avisar=_calado)
        for brinquedo in (base_air, ficha_air, base_bq, ficha_bq, street):
            brinquedo.refresh_from_db()
        self.assertEqual(ficha_bq.nome_brinquedo, "Basquete Home Quadrinhos")
        self.assertEqual(ficha_bq.imagens_brinquedo.get().texto_alternativo, "Basquete Home Quadrinhos de frente")
        self.assertEqual(list(base_air.variantes_adesivo.values_list("slug", flat=True)), ["astronautas", "alienigenas"])
        self.assertEqual(list(base_bq.variantes_adesivo.values_list("nome", flat=True)), ["Azul", "Quadrinhos"])
        self.assertEqual(base_bq.variantes_adesivo.get(slug="quadrinhos").origem, ficha_bq)
        self.assertEqual((ficha_air.ativo, ficha_bq.ativo), (False, False))
        self.assertEqual((base_air.ativo, base_bq.ativo, street.ativo), (True, True, True))
        self.assertFalse(street.variantes_adesivo.exists())
        self.assertFalse(VarianteAdesivo.objects.filter(origem=street).exists())
        self.assertEqual(VarianteAdesivo.objects.count(), 4)


class RedirecionamentoTests(_ComPar):
    def test_o_endereco_da_ficha_vai_para_o_produto_no_adesivo(self):
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[self.ficha.pk]))
        self.assertEqual(resposta.status_code, 301)
        self.assertEqual(resposta["Location"], f"/brinquedo/{self.base.pk}/?adesivo=alienigenas")

    def test_o_desativado_sem_adesivo_continua_404(self):
        outro = _produto("Pebolim", "pebolim", ativo=False)
        self.assertEqual(self.client.get(reverse("brinquedo_detalhe", args=[outro.pk])).status_code, 404)


class ListasTests(_ComPar):
    def _confere(self, html, nome_da_lista):
        with self.subTest(nome_da_lista):
            self.assertIn(f"/brinquedo/{self.base.pk}/", html)
            self.assertNotIn(f"/brinquedo/{self.ficha.pk}/", html)
            self.assertNotIn("Air Game Kids Alienígenas", html)
            # o selo e as duas capas (o card reveza as fotos dos adesivos)
            self.assertIn("2 adesivos", html)
            self.assertIn("data-adesivos-capas=", html)
            self.assertIn("astronautas", html)
            self.assertIn("alienigenas", html)

    def test_o_produto_aparece_uma_vez_com_o_selo(self):
        paginas = {
            "home": reverse("home"),
            "categoria": reverse("categoria_detalhe", args=[self.categoria.pk]),
            "brinquedos": reverse("brinquedos"),
            "loja": reverse("loja"),
            "busca": reverse("search") + "?q=air+game+kids",
        }
        for nome, url in paginas.items():
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, 200, nome)
            self._confere(resposta.content.decode(), nome)

    def test_o_script_que_reveza_as_capas_esta_em_toda_pagina(self):
        self.assertContains(self.client.get(reverse("home")), "site/ls-adesivos.js")

    def test_na_arena_uma_vez_com_o_3d_do_adesivo(self):
        dados = dados_publicos_da_arena()
        nomes = [b["nome"] for b in dados["brinquedos_arena"]]
        self.assertEqual(nomes.count("Air Game Kids"), 1)
        self.assertNotIn("Air Game Kids Alienígenas", nomes)
        item = next(b for b in dados["brinquedos_arena"] if b["nome"] == "Air Game Kids")
        self.assertIn("air-game-kids-alienigenas.glb", item["modelo"])
        self.assertEqual(item["modelo_id"], "air-game-kids-alienigenas")
        self.assertIn("air-game-kids-alienigenas", item["modelos_variantes"])
        # o .glb do adesivo não aparece à parte, como objeto fora do catálogo
        self.assertNotIn("modelo-air-game-kids-alienigenas", [b["id"] for b in dados["brinquedos_arena"]])
        self.assertIn(self.base.pk, [m["id"] for m in dados["arena_dados"]["maquinas"]])
        self.assertNotIn("air-game-kids-alienigenas", [m["modelo_id"] for m in arena.modelos_fora_do_catalogo(
            [{"modelo_id": "", "modelos_variantes": ["air-game-kids-alienigenas"]}])])


class PaginaDoProdutoTests(_ComPar):
    def _pagina(self, adesivo=""):
        url = reverse("brinquedo_detalhe", args=[self.base.pk]) + (f"?adesivo={adesivo}" if adesivo else "")
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        return resposta

    def test_as_fichas_dos_adesivos(self):
        html = self._pagina().content.decode()
        self.assertIn("Adesivo:", html)
        self.assertIn('href="?adesivo=astronautas#bread"', html)
        self.assertIn('href="?adesivo=alienigenas#bread"', html)
        self.assertEqual(html.count('aria-current="true"'), 1)

    def test_o_adesivo_troca_as_fotos_e_o_3d(self):
        resposta = self._pagina("alienigenas")
        self.assertEqual(resposta.context["adesivo"]["slug"], "alienigenas")
        self.assertEqual([i.brinquedo_id for i in resposta.context["imagens_brinquedo"]], [self.ficha.pk])
        self.assertIn("air-game-kids-alienigenas.glb", resposta.context["objeto_3d"]["url"])
        self.assertContains(resposta, "data-visor3d-abrir")
        # o pedido leva o adesivo
        self.assertContains(resposta, 'name="adesivo" value="Alienígenas"')
        self.assertIn(quote("Adesivo: Alienígenas"), resposta.context["whatsapp_url"])

    def test_o_adesivo_sem_3d_leva_ao_que_tem(self):
        resposta = self._pagina()
        self.assertEqual(resposta.context["adesivo"]["slug"], "astronautas")
        self.assertEqual([i.brinquedo_id for i in resposta.context["imagens_brinquedo"]], [self.base.pk])
        self.assertFalse(resposta.context["objeto_3d"])
        self.assertContains(resposta, "3D no adesivo Alienígenas")
        self.assertNotContains(resposta, "data-visor3d-abrir")
        self.assertIn(quote("Adesivo: Astronautas"), resposta.context["whatsapp_url"])

    def test_adesivo_que_nao_existe_e_o_padrao(self):
        self.assertEqual(self._pagina("xyz").context["adesivo"]["slug"], "astronautas")

    def test_produto_sem_adesivos_fica_como_era(self):
        outro = _produto("Pebolim", "pebolim")
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[outro.pk]))
        self.assertNotContains(resposta, "produto-adesivos")
        self.assertNotIn("adesivo", resposta.context)


class CarrinhoTests(_ComPar):
    def setUp(self):
        super().setUp()
        self.usuario = User.objects.create_user("cliente-adesivo", password="x")
        perfil = self.usuario.perfil
        perfil.telefone = "11999990000"  # o cadastro completo (sem ele, o site pede antes de comprar)
        perfil.save()
        self.client.force_login(self.usuario)
        self.url = reverse("adicionar_ao_carrinho", args=["brinquedo", self.base.pk])

    def test_o_carrinho_guarda_o_adesivo(self):
        self.client.post(self.url, {"quantidade": 1, "adesivo": "Alienígenas"})
        self.client.post(self.url, {"quantidade": 1, "adesivo": "Alienígenas"})
        self.client.post(self.url, {"quantidade": 1, "adesivo": "Astronautas"})
        # um adesivo que não é do produto não entra
        self.client.post(self.url, {"quantidade": 1, "adesivo": "Dinossauros"})
        linhas = {i.adesivo: i.quantidade for i in ItemCarrinho.objects.all()}
        self.assertEqual(linhas, {"Alienígenas": 2, "Astronautas": 1, "": 1})
        self.assertContains(self.client.get(reverse("carrinho")), "adesivo Alienígenas")

    def test_o_pedido_leva_o_adesivo_e_ele_volta_para_o_carrinho(self):
        self.client.post(self.url, {"quantidade": 1, "adesivo": "Alienígenas"})
        item = ItemCarrinho.objects.get()
        self.assertEqual(item.nome_com_adesivo, "Air Game Kids — adesivo Alienígenas")
        pedido = criar_pedido_a_partir_do_carrinho(item.carrinho)
        self.assertEqual(pedido.itens.get().nome_item, "Air Game Kids — adesivo Alienígenas")
        ItemCarrinho.objects.all().delete()
        pedido.status = "aguardando_pagamento"
        pedido.carrinho_origem = item.carrinho
        pedido.save(update_fields=["status", "carrinho_origem"])
        pedido.devolver_ao_carrinho()
        self.assertEqual(ItemCarrinho.objects.get().adesivo, "Alienígenas")
