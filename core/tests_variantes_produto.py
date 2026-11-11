"""Os adesivos: um objeto só, com as duas artes (LEIA-ME, seção 72).

O cliente: "vc deve deixar apenas um objeto ... como no boliche", "EU QUERO OS
DOIS OBJETOS 3D, NO MESMO BRINQUEDO", "TUDO DEVE AFUNILAR PARA UM OBJETO SÓ
... TAMBÉM DEVE SER POSSÍVEL MUDAR PARA VER OS ADESIVOS" e "quando o
brinquedo tiver mais que uma, no card ... deve ficar rodando as fotos". O que
estes testes protegem:

  * o `juntar`/`separar` e o `unificar` de core/variantes.py: a ficha da
    outra arte fica desativada (nada é apagado); as fotos dela entram na
    galeria do produto (os mesmos arquivos), as medidas que faltam vêm dela
    (as que ele tem ficam), o Air Game Kids ganha o 3D dos Astronautas; o
    preço não muda; rodar de novo não duplica;
  * as migrações: esquema e dados em arquivos separados (0160/0161,
    0165/0166);
  * o endereço antigo da ficha vai, permanente, para o produto, sem ?adesivo;
  * nas listas o produto aparece uma vez; o card de todo brinquedo com mais
    de uma foto traz as fotos para girar (`data-fotos-card`);
  * na página: sem as fichas que trocavam a página, a galeria com as duas
    artes, um visor 3D com os dois modelos ("Adesivo: A · B");
  * a Arena e o "Ver em 3D" da proposta: o produto uma vez, com os dois 3D;
  * o carrinho guarda o adesivo escolhido (observação), o pedido o leva no
    nome e, se o pagamento não sai, ele volta para o carrinho com o adesivo.
"""

import importlib
from decimal import Decimal
import json

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
    ObjetoTresD,
    VarianteAdesivo,
)
from .services import criar_pedido_a_partir_do_carrinho
from .views_arena import dados_publicos_da_arena

migracao_0160 = importlib.import_module("core.migrations.0160_variantes_de_adesivo")
migracao_0161 = importlib.import_module("core.migrations.0161_juntar_variantes_de_adesivo")
migracao_0165 = importlib.import_module("core.migrations.0165_papel_outra_arte")
migracao_0166 = importlib.import_module("core.migrations.0166_um_objeto_por_produto")
from django.db.migrations.operations import AlterField  # noqa: E402

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
    """O Air Game Kids (os astronautas) com o Air Game Kids Alienígenas juntado a ele, como a 0161 e a 0166 fazem."""

    def setUp(self):
        cache.clear()
        self.categoria = CategoriasBrinquedos.objects.create(nome_categoria="Jogos de Mesa", imagem_categoria="categorias/m.png")
        self.base = _produto("Air Game Kids", "astronautas", self.categoria)
        self.ficha = _produto("Air Game Kids Alienígenas", "alienigenas", self.categoria,
                              altura_m=Decimal("0.90"), largura_m=Decimal("0.86"), profundidade_m=Decimal("1.50"))
        ImagemBrinquedo.objects.create(brinquedo=self.ficha, tipo="lado_esquerdo", ordem=2,
                                       imagem="imagens_brinquedos/alienigenas-lado.png", texto_alternativo="o lado")
        produto, padrao, fichas = PAR
        variantes.juntar(produto, padrao, fichas, Brinquedos, VarianteAdesivo, avisar=_calado)
        self._unificar()
        self.base.refresh_from_db()
        self.ficha.refresh_from_db()
        cache.clear()

    def _unificar(self):
        variantes.unificar(self.base, Brinquedos, ImagemBrinquedo, ObjetoTresD, VarianteAdesivo, avisar=_calado)


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
        self.assertEqual(self.ficha.imagens_brinquedo.count(), 2)

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

    def test_as_fotos_da_outra_arte_entram_na_galeria(self):
        outra = list(self.base.imagens_brinquedo.filter(papel_na_capa="outra_arte").order_by("ordem"))
        self.assertEqual([f.imagem.name for f in outra],
                         ["imagens_brinquedos/alienigenas.png", "imagens_brinquedos/alienigenas-lado.png"])
        self.assertEqual({f.tipo for f in outra}, {None})
        # os mesmos arquivos, depois das dele, na galeria pública (a da página e a do card)
        self.assertEqual([f.imagem.name for f in self.base.imagens_ordenadas],
                         ["imagens_brinquedos/astronautas.png", "imagens_brinquedos/alienigenas.png",
                          "imagens_brinquedos/alienigenas-lado.png"])
        # a ficha continua com as fotos dela
        self.assertEqual(self.ficha.imagens_brinquedo.count(), 2)

    def test_unificar_de_novo_nao_duplica(self):
        antes = ImagemBrinquedo.objects.count()
        self._unificar()
        self._unificar()
        self.assertEqual(ImagemBrinquedo.objects.count(), antes)
        self.assertEqual(ObjetoTresD.objects.filter(brinquedo=self.base).count(), 1)

    def test_as_medidas_que_faltam_vem_da_ficha_e_as_que_ha_ficam(self):
        self.assertEqual((self.base.altura_m, self.base.largura_m, self.base.profundidade_m),
                         (Decimal("0.90"), Decimal("0.86"), Decimal("1.50")))
        Brinquedos.objects.filter(pk=self.base.pk).update(altura_m=Decimal("2.10"), largura_m=None)
        self.base.refresh_from_db()
        self._unificar()
        self.base.refresh_from_db()
        self.assertEqual((self.base.altura_m, self.base.largura_m), (Decimal("2.10"), Decimal("0.86")))

    def test_o_produto_tem_os_dois_3d(self):
        proprio = self.base.objeto_3d
        self.assertEqual((proprio.codigo, proprio.arquivo_estatico),
                         ("air-game-kids-astronautas", "site/arena/modelos/air-game-kids-astronautas.glb"))
        modelos = variantes.modelos_3d(self.base)
        self.assertEqual([m["nome"] for m in modelos], ["Astronautas", "Alienígenas"])
        self.assertIn("air-game-kids-astronautas.glb", modelos[0]["url"])
        self.assertIn("air-game-kids-alienigenas.glb", modelos[1]["url"])
        # produto sem outra arte: lista vazia (o visor fica como sempre)
        self.assertEqual(variantes.modelos_3d(_produto("Pebolim", "pebolim")), [])


class MigracaoTests(TestCase):
    def test_esquema_e_dados_em_arquivos_separados(self):
        self.assertTrue(all(isinstance(op, AlterField) for op in migracao_0165.Migration.operations))
        self.assertTrue(all(isinstance(op, RunPython) for op in migracao_0166.Migration.operations))
        self.assertIn(("core", "0165_papel_outra_arte"), migracao_0166.Migration.dependencies)
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
        # a 0166: o Basquete Home sem medidas fica com as do Quadrinhos; as fotos dele na galeria
        Brinquedos.objects.filter(pk=ficha_bq.pk).update(
            altura_m=Decimal("2.70"), largura_m=Decimal("1.00"), profundidade_m=Decimal("2.40"))
        Brinquedos.objects.filter(pk=base_bq.pk).update(altura_m=None, largura_m=None, profundidade_m=None)
        for _vez in range(2):  # pode rodar de novo
            variantes.unificar_todos(apps_de_hoje, None, avisar=_calado)
        base_bq.refresh_from_db()
        self.assertEqual((base_bq.altura_m, base_bq.largura_m, base_bq.profundidade_m),
                         (Decimal("2.70"), Decimal("1.00"), Decimal("2.40")))
        self.assertEqual(list(base_bq.imagens_brinquedo.filter(papel_na_capa="outra_arte").values_list("imagem", flat=True)),
                         ["imagens_brinquedos/basquete-street-quadrinhos-capa.png"])
        self.assertFalse(street.imagens_brinquedo.filter(papel_na_capa="outra_arte").exists())
        self.assertTrue(ObjetoTresD.objects.filter(brinquedo=base_air, codigo="air-game-kids-astronautas").exists())
        self.assertFalse(ObjetoTresD.objects.filter(brinquedo=base_bq).exists())  # o 3D dele é o do Quadrinhos
        self.assertEqual(base_air.valor_brinquedo, Decimal("4990.00"))


class MedidasDoBasqueteTests(TestCase):
    def test_sem_medidas_na_ficha_valem_as_do_3d_dela(self):
        # o Basquete Home e o Quadrinhos sem medidas no cadastro: o Basquete Home fica com as do 3D
        # do Quadrinhos (2,70 x 1,00 x 2,40 m, core/cadastro_modelos.py); as que ele tem, ficam
        base = _produto("Basquete Home", "basquete-home")
        _produto("Basquete Home Quadrinhos", "quadrinhos")
        variantes.juntar("Basquete Home", ("Azul", "azul"), [("Basquete Home Quadrinhos", "Quadrinhos", "quadrinhos")],
                         Brinquedos, VarianteAdesivo, avisar=_calado)
        variantes.unificar(base, Brinquedos, ImagemBrinquedo, ObjetoTresD, VarianteAdesivo, avisar=_calado)
        base.refresh_from_db()
        self.assertEqual((base.altura_m, base.largura_m, base.profundidade_m),
                         (Decimal("2.70"), Decimal("1.00"), Decimal("2.40")))
        Brinquedos.objects.filter(pk=base.pk).update(altura_m=Decimal("2.10"))
        variantes.unificar(base, Brinquedos, ImagemBrinquedo, ObjetoTresD, VarianteAdesivo, avisar=_calado)
        base.refresh_from_db()
        self.assertEqual(base.altura_m, Decimal("2.10"))


class RedirecionamentoTests(_ComPar):
    def test_o_endereco_da_ficha_vai_para_o_produto(self):
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[self.ficha.pk]))
        self.assertEqual(resposta.status_code, 301)
        self.assertEqual(resposta["Location"], f"/brinquedo/{self.base.pk}/")

    def test_o_desativado_sem_adesivo_continua_404(self):
        outro = _produto("Pebolim", "pebolim", ativo=False)
        self.assertEqual(self.client.get(reverse("brinquedo_detalhe", args=[outro.pk])).status_code, 404)


class ListasTests(_ComPar):
    def _confere(self, html, nome_da_lista):
        with self.subTest(nome_da_lista):
            self.assertIn(f"/brinquedo/{self.base.pk}/", html)
            self.assertNotIn(f"/brinquedo/{self.ficha.pk}/", html)
            self.assertNotIn("Air Game Kids Alienígenas", html)
            self.assertNotIn("?adesivo=", html)
            # o card gira as fotos (as das duas artes)
            self.assertIn("data-fotos-card=", html)
            self.assertIn("astronautas", html)
            self.assertIn("alienigenas", html)

    def test_o_produto_aparece_uma_vez_e_o_card_gira_as_fotos(self):
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

    def test_todo_brinquedo_com_mais_de_uma_foto_gira(self):
        dois = _produto("Pebolim", "pebolim", self.categoria)
        ImagemBrinquedo.objects.create(brinquedo=dois, tipo="verso", ordem=2, imagem="imagens_brinquedos/pebolim-verso.png")
        um = _produto("Pula Pula", "pula", self.categoria)
        cache.clear()
        html = self.client.get(reverse("categoria_detalhe", args=[self.categoria.pk])).content.decode()
        marcas = [json.loads(m.replace("&quot;", '"')) for m in __import__("re").findall(r'data-fotos-card="([^"]*)"', html)]
        fotos = {tuple(sorted(x.split("/")[-1].split(".")[0] for x in m)) for m in marcas}
        self.assertIn(("pebolim", "pebolim-verso"), fotos)
        self.assertFalse(any("pula" in f for par in fotos for f in par))
        # a capa é a primeira
        self.assertTrue(all("pebolim.png" in m[0] or "astronautas" in m[0] for m in marcas))
        self.assertTrue(um.pk)

    def test_o_script_que_gira_as_fotos_esta_em_toda_pagina(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn("site/ls-giro.js", html)
        self.assertNotIn("ls-adesivos.js", html)

    def test_na_arena_uma_vez_com_os_dois_3d(self):
        dados = dados_publicos_da_arena()
        nomes = [b["nome"] for b in dados["brinquedos_arena"]]
        self.assertEqual(nomes.count("Air Game Kids"), 1)
        self.assertNotIn("Air Game Kids Alienígenas", nomes)
        item = next(b for b in dados["brinquedos_arena"] if b["nome"] == "Air Game Kids")
        self.assertIn("air-game-kids-astronautas.glb", item["modelo"])
        self.assertEqual([m["nome"] for m in item["adesivos3d"]], ["Astronautas", "Alienígenas"])
        self.assertIn("air-game-kids-alienigenas", item["modelos_variantes"])
        # o .glb do adesivo não aparece à parte, como objeto fora do catálogo
        self.assertNotIn("modelo-air-game-kids-alienigenas", [b["id"] for b in dados["brinquedos_arena"]])
        self.assertIn(self.base.pk, [m["id"] for m in dados["arena_dados"]["maquinas"]])


class PaginaDoProdutoTests(_ComPar):
    def _pagina(self, extra=""):
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[self.base.pk]) + extra)
        self.assertEqual(resposta.status_code, 200)
        return resposta

    def test_um_objeto_sem_as_fichas_que_trocavam_a_pagina(self):
        html = self._pagina().content.decode()
        self.assertNotIn("produto-adesivos", html)
        self.assertNotIn("?adesivo=", html)
        self.assertNotIn("3D no adesivo", html)

    def test_a_galeria_tem_as_duas_artes(self):
        resposta = self._pagina()
        nomes = [i.imagem.name for i in resposta.context["imagens_brinquedo"]]
        self.assertEqual(nomes[0], "imagens_brinquedos/astronautas.png")
        self.assertIn("imagens_brinquedos/alienigenas.png", nomes)
        self.assertIn("imagens_brinquedos/alienigenas-lado.png", nomes)

    def test_um_visor_3d_com_os_dois_modelos(self):
        resposta = self._pagina("?adesivo=alienigenas")  # o endereço velho não muda nada
        html = resposta.content.decode()
        self.assertEqual(html.count("data-visor3d hidden"), 1)
        self.assertIn("air-game-kids-astronautas.glb", resposta.context["objeto_3d"].url)
        self.assertEqual([m["nome"] for m in resposta.context["adesivos3d"]], ["Astronautas", "Alienígenas"])
        self.assertIn('id="adesivos3d-dados"', html)
        self.assertIn('data-adesivos3d="adesivos3d-dados"', html)
        self.assertIn("site/arena/adesivos3d.js", html)
        # o adesivo escolhido no 3D vai para o carrinho como observação
        self.assertIn('name="adesivo" value="" data-adesivo-escolhido', html)

    def test_sem_3d_proprio_o_visor_abre_no_do_adesivo(self):
        ObjetoTresD.objects.filter(brinquedo=self.base).delete()
        cache.clear()
        resposta = self._pagina()
        self.assertIn("air-game-kids-alienigenas.glb", resposta.context["objeto_3d"]["url"])
        self.assertEqual([m["nome"] for m in resposta.context["adesivos3d"]], ["Alienígenas"])

    def test_produto_sem_adesivos_fica_como_era(self):
        outro = _produto("Pebolim", "pebolim")
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[outro.pk]))
        self.assertNotContains(resposta, "adesivos3d")
        self.assertEqual(resposta.context["adesivos3d"], [])


class OrcamentoTests(_ComPar):
    def test_o_ver_em_3d_da_proposta_tem_os_dois_3d(self):
        class Item:
            brinquedo_id = self.base.pk
            brinquedo = self.base
        self.assertEqual([m["nome"] for m in variantes.modelos_do_item(Item())], ["Astronautas", "Alienígenas"])

        class ItemDaFicha:  # a proposta antiga, com a ficha: o mesmo produto
            brinquedo_id = self.ficha.pk
            brinquedo = self.ficha
        self.assertEqual([m["nome"] for m in variantes.modelos_do_item(ItemDaFicha())], ["Astronautas", "Alienígenas"])

        class Outro:
            brinquedo_id = 999
            brinquedo = _produto("Pebolim", "pebolim")
        self.assertEqual(variantes.modelos_do_item(Outro()), [])


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
