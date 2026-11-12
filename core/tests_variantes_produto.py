"""Os adesivos: um objeto só no banco, com as duas artes (LEIA-ME, seção 72).

O cliente: "DEVE MUDAR A ESTRUTURA DOS OBJETOS, DEIXAR SOMENTE UM MAS COM O
OUTRO ADESIVO E SEU RESPECTIVO OBJETO 3D, A ESTRUTURA DEVE SER ASSIM, NÃO DOIS
OBJETOS, ALÉM DO MAIS MUDE O VALOR PARA 6990,00 DO AIR GAME". O que estes
testes protegem:

  * a estrutura: o adesivo (core.models.VarianteAdesivo) é dono das fotos
    (`ImagemBrinquedo.variante`) e do 3D dele; o padrão usa os do produto;
  * a 0169, com o banco como estava (o produto à parte e o `origem`): as
    fotos e o 3D passam para o produto e o adesivo; TODAS as referências
    (orçamento, carrinho, pedido, favorito, clique, promoção e extras,
    combo) vão para o produto; o favorito repetido vira um; o produto à parte
    é APAGADO; o Air Game Kids fica com R$ 6.990,00; rodar de novo não faz
    nada; esquema e dados em arquivos separados (0168 / 0169 / 0170);
  * o endereço antigo vai (301) para o produto;
  * as listas, a página (a galeria com as duas artes, um visor com os dois
    3D), a Arena, a proposta e o carrinho (o adesivo como observação);
  * o card de todo brinquedo com mais de uma foto gira as fotos.
"""

import importlib
import json
import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations import AddField, RemoveField, RunPython
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from . import variantes
from .models import (
    Brinquedos,
    CategoriasBrinquedos,
    ImagemBrinquedo,
    ItemCarrinho,
    ObjetoTresD,
    VarianteAdesivo,
    galeria_publica,
)
from .services import criar_pedido_a_partir_do_carrinho
from .views_arena import dados_publicos_da_arena

migracao_0168 = importlib.import_module("core.migrations.0168_variantes_donas_do_3d_e_das_fotos")
migracao_0169 = importlib.import_module("core.migrations.0169_um_objeto_no_banco")
migracao_0170 = importlib.import_module("core.migrations.0170_variantes_sem_origem")

GLB_ALIEN = "site/arena/modelos/air-game-kids-alienigenas.glb"
GLB_ASTRONAUTAS = "site/arena/modelos/air-game-kids-astronautas.glb"
ANTES = ("core", "0168_variantes_donas_do_3d_e_das_fotos")


def _calado(*_args, **_kwargs):
    return None


def _produto(nome, foto, categoria=None, **campos):
    dados = {
        "descricao": f"{nome}.", "avaliacao": Decimal("4.80"), "voltz": "220V",
        "valor_brinquedo": Decimal("6990.00"), "exibir_na_loja": True,
        "imagem_brinquedo": f"imagens_brinquedos/{foto}.png",
    }
    dados.update(campos)
    brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, **dados)
    ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="perfil", ordem=1,
                                   imagem=f"imagens_brinquedos/{foto}.png", texto_alternativo=f"{nome}: a foto")
    if categoria is not None:
        brinquedo.categorias_brinquedos.add(categoria)
    return brinquedo


class _ComAdesivos(TestCase):
    """O Air Game Kids como fica: um produto, o adesivo Astronautas (o padrão) e o Alienígenas (fotos e 3D dele)."""

    def setUp(self):
        cache.clear()
        self.categoria = CategoriasBrinquedos.objects.create(nome_categoria="Jogos de Mesa", imagem_categoria="categorias/m.png")
        self.base = _produto("Air Game Kids", "astronautas", self.categoria,
                             altura_m=Decimal("0.90"), largura_m=Decimal("0.86"), profundidade_m=Decimal("1.50"))
        ObjetoTresD.objects.create(brinquedo=self.base, arquivo_estatico=GLB_ASTRONAUTAS, codigo="air-game-kids-astronautas")
        VarianteAdesivo.objects.create(brinquedo=self.base, nome="Astronautas", slug="astronautas", ordem=1, padrao=True)
        self.alien = VarianteAdesivo.objects.create(
            brinquedo=self.base, nome="Alienígenas", slug="alienigenas", ordem=2, padrao=False,
            arquivo_estatico_3d=GLB_ALIEN, codigo_3d="air-game-kids-alienigenas", id_antigo=54,
        )
        for ordem, nome in ((5, "alienigenas"), (6, "alienigenas-lado")):
            ImagemBrinquedo.objects.create(brinquedo=self.base, variante=self.alien, tipo=None, ordem=ordem,
                                           imagem=f"imagens_brinquedos/{nome}.png", texto_alternativo="os alienígenas")
        cache.clear()


class EstruturaTests(_ComAdesivos):
    def test_um_objeto_com_os_dois_adesivos(self):
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo__startswith="Air Game Kids").count(), 1)
        self.assertEqual([v.nome for v in self.base.variantes_adesivo.all()], ["Astronautas", "Alienígenas"])
        self.assertIn("air-game-kids-alienigenas.glb", self.alien.url_3d)
        self.assertEqual(self.alien.fotos.count(), 2)
        self.assertFalse(hasattr(self.alien, "origem"))

    def test_a_galeria_tem_as_duas_artes(self):
        nomes = [f.imagem.name for f in self.base.imagens_ordenadas]
        self.assertEqual(nomes, ["imagens_brinquedos/astronautas.png", "imagens_brinquedos/alienigenas.png",
                                 "imagens_brinquedos/alienigenas-lado.png"])
        self.assertEqual(self.base.imagem_perfil.name, "imagens_brinquedos/astronautas.png")
        self.assertEqual([f.imagem.name for f in galeria_publica(self.base.imagens_brinquedo.all())], nomes)

    def test_os_dois_3d_do_produto(self):
        modelos = variantes.modelos_3d(self.base)
        self.assertEqual([m["nome"] for m in modelos], ["Astronautas", "Alienígenas"])
        self.assertIn("air-game-kids-astronautas.glb", modelos[0]["url"])
        self.assertIn("air-game-kids-alienigenas.glb", modelos[1]["url"])
        self.assertEqual(variantes.modelos_3d(_produto("Pebolim", "pebolim")), [])
        self.assertEqual(variantes.produtos_com_adesivos(), {self.base.pk})


class MigracoesTests(TestCase):
    def test_esquema_e_dados_em_arquivos_separados(self):
        self.assertTrue(all(isinstance(op, AddField) for op in migracao_0168.Migration.operations))
        self.assertTrue(all(isinstance(op, RunPython) for op in migracao_0169.Migration.operations))
        self.assertTrue(all(isinstance(op, RemoveField) for op in migracao_0170.Migration.operations))
        self.assertIn(("core", "0167_jogadas_registradas"), migracao_0168.Migration.dependencies)
        self.assertIn(ANTES, migracao_0169.Migration.dependencies)
        self.assertIn(("core", "0169_um_objeto_no_banco"), migracao_0170.Migration.dependencies)


class EstruturarTests(TransactionTestCase):
    """A 0169 com o banco como estava: o Air Game Kids Alienígenas à parte (desativado), com referências."""

    def _apps(self, executor, no):
        folhas = [n for n in executor.loader.graph.leaf_nodes() if n[0] != "core"] + [no]
        return executor.loader.project_state(folhas).apps

    def test_a_ficha_a_parte_vira_parte_do_produto_e_some(self):
        executor = MigrationExecutor(connection)
        executor.migrate([ANTES])
        executor.loader.build_graph()
        apps = self._apps(executor, ANTES)
        B = apps.get_model("core", "Brinquedos")
        Img = apps.get_model("core", "ImagemBrinquedo")
        Obj = apps.get_model("core", "ObjetoTresD")
        Var = apps.get_model("core", "VarianteAdesivo")
        U = apps.get_model("auth", "User")
        CT = apps.get_model("contenttypes", "ContentType")

        base = B.objects.create(nome_brinquedo="Air Game Kids", descricao="x", avaliacao=5, voltz="220V",
                                valor_brinquedo=Decimal("4990.00"))
        Img.objects.create(brinquedo=base, tipo="perfil", ordem=1, imagem="imagens_brinquedos/astronautas.png")
        ficha = B.objects.create(nome_brinquedo="Air Game Kids Alienígenas", descricao="x", avaliacao=5, voltz="220V",
                                 valor_brinquedo=Decimal("4990.00"), ativo=False)
        Img.objects.create(brinquedo=ficha, tipo="perfil", ordem=1, imagem="imagens_brinquedos/alien-capa.png")
        Img.objects.create(brinquedo=ficha, tipo="lado_esquerdo", ordem=2, imagem="imagens_brinquedos/alien-lado.png")
        # a cópia da 0166 (a capa da ficha já na galeria do produto)
        Img.objects.create(brinquedo=base, tipo=None, ordem=2, imagem="imagens_brinquedos/alien-capa.png",
                           papel_na_capa="outra_arte")
        Obj.objects.create(brinquedo=ficha, arquivo_estatico=GLB_ALIEN, codigo="air-game-kids-alienigenas",
                           cores=[], medidas=[0.9, 0.83, 1.51])
        Var.objects.create(brinquedo=base, nome="Astronautas", slug="astronautas", ordem=1, padrao=True)
        alien = Var.objects.create(brinquedo=base, nome="Alienígenas", slug="alienigenas", ordem=2, origem=ficha)

        # as referências à ficha: orçamento, carrinho, pedido, favorito (e o repetido), clique, promoção, combo
        usuario = U.objects.create(username="cliente-ficha")
        Orc = apps.get_model("sistema_interno", "Orcamento")
        ItemOrc = apps.get_model("sistema_interno", "ItemOrcamento")
        orc = Orc.objects.create(nome_cliente="Cliente")
        item_orc = ItemOrc.objects.create(orcamento=orc, descricao="Air Game Kids Alienígenas", brinquedo=ficha)
        tipo = CT.objects.get(app_label="core", model="brinquedos")
        Carrinho = apps.get_model("core", "Carrinho")
        ItemC = apps.get_model("core", "ItemCarrinho")
        carrinho = Carrinho.objects.create()
        item_c = ItemC.objects.create(carrinho=carrinho, content_type=tipo, object_id=ficha.pk, quantidade=2)
        Fav = apps.get_model("core", "Favorito")
        tipo_fav = Fav._meta.get_field("tipo").choices[0][0]
        Fav.objects.create(usuario=usuario, brinquedo=base, tipo=tipo_fav)
        Fav.objects.create(usuario=usuario, brinquedo=ficha, tipo=tipo_fav)
        Click = apps.get_model("core", "BrinquedoClick")
        clique = Click.objects.create(brinquedo_clicado=ficha)
        Promo = apps.get_model("core", "Promocoes")
        promo = Promo.objects.create(descricao="Promo", brinquedos=ficha)
        promo.brinquedos_extras.add(ficha)
        Combo = apps.get_model("core", "Combos")
        combo = Combo.objects.create(descricao="Combo", valor_combo=Decimal("100.00"))
        combo.brinquedos.add(ficha)

        # a 0169 (e de novo: nada muda), depois a 0170
        executor = MigrationExecutor(connection)
        executor.migrate([("core", "0169_um_objeto_no_banco")])
        executor.loader.build_graph()
        apps169 = self._apps(executor, ("core", "0169_um_objeto_no_banco"))
        variantes.estruturar(apps169, None, avisar=_calado)
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

        # um objeto só: a ficha sumiu; o adesivo tem o 3D e as fotos; o preço é 6990
        self.assertFalse(Brinquedos.objects.filter(pk=ficha.pk).exists())
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo__startswith="Air Game Kids").count(), 1)
        produto = Brinquedos.objects.get(pk=base.pk)
        self.assertEqual(produto.valor_brinquedo, Decimal("6990.00"))
        adesivo = VarianteAdesivo.objects.get(pk=alien.pk)
        self.assertEqual((adesivo.id_antigo, adesivo.arquivo_estatico_3d, adesivo.codigo_3d),
                         (ficha.pk, GLB_ALIEN, "air-game-kids-alienigenas"))
        self.assertEqual(adesivo.medidas_3d, [0.9, 0.83, 1.51])
        self.assertEqual(sorted(adesivo.fotos.values_list("imagem", flat=True)),
                         ["imagens_brinquedos/alien-capa.png", "imagens_brinquedos/alien-lado.png"])
        self.assertEqual(ImagemBrinquedo.objects.filter(brinquedo=produto).count(), 3)  # sem a cópia repetida
        self.assertFalse(adesivo.fotos.exclude(tipo=None).exists())
        self.assertFalse(ObjetoTresD.objects.filter(brinquedo_id=ficha.pk).exists())
        # as referências vieram para o produto
        from core.models import BrinquedoClick, Combos, Favorito, Promocoes
        from sistema_interno.models import ItemOrcamento

        self.assertEqual(ItemOrcamento.objects.get(pk=item_orc.pk).brinquedo_id, produto.pk)
        linha = ItemCarrinho.objects.get(pk=item_c.pk)
        self.assertEqual((linha.object_id, linha.adesivo, linha.quantidade), (produto.pk, "Alienígenas", 2))
        self.assertEqual(Favorito.objects.filter(usuario_id=usuario.pk).count(), 1)  # o repetido virou um
        self.assertEqual(Favorito.objects.get(usuario_id=usuario.pk).brinquedo_id, produto.pk)
        self.assertEqual(BrinquedoClick.objects.get(pk=clique.pk).brinquedo_clicado_id, produto.pk)
        promo = Promocoes.objects.get(pk=promo.pk)
        self.assertEqual(promo.brinquedos_id, produto.pk)
        self.assertEqual(list(promo.brinquedos_extras.values_list("pk", flat=True)), [produto.pk])
        self.assertEqual(list(Combos.objects.get(pk=combo.pk).brinquedos.values_list("pk", flat=True)), [produto.pk])
        # o endereço antigo vai para o produto
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[ficha.pk]))
        self.assertEqual((resposta.status_code, resposta["Location"]), (301, f"/brinquedo/{produto.pk}/"))


class RedirecionamentoTests(_ComAdesivos):
    def test_o_endereco_antigo_vai_para_o_produto(self):
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[54]))
        self.assertEqual(resposta.status_code, 301)
        self.assertEqual(resposta["Location"], f"/brinquedo/{self.base.pk}/")

    def test_o_que_nunca_existiu_continua_404(self):
        self.assertEqual(self.client.get(reverse("brinquedo_detalhe", args=[9999])).status_code, 404)


class ListasTests(_ComAdesivos):
    def test_o_produto_aparece_uma_vez_e_o_card_gira_as_fotos(self):
        paginas = {
            "home": reverse("home"),
            "categoria": reverse("categoria_detalhe", args=[self.categoria.pk]),
            "brinquedos": reverse("brinquedos"),
            "loja": reverse("loja"),
            "busca": reverse("search") + "?q=air+game+kids",
        }
        for nome, url in paginas.items():
            with self.subTest(nome):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 200, nome)
                html = resposta.content.decode()
                self.assertIn(f"/brinquedo/{self.base.pk}/", html)
                self.assertNotIn("Air Game Kids Alienígenas", html)
                self.assertNotIn("?adesivo=", html)
                self.assertIn("data-fotos-card=", html)
                self.assertIn("alienigenas", html)

    def test_todo_brinquedo_com_mais_de_uma_foto_gira(self):
        dois = _produto("Pebolim", "pebolim", self.categoria)
        ImagemBrinquedo.objects.create(brinquedo=dois, tipo="verso", ordem=2, imagem="imagens_brinquedos/pebolim-verso.png")
        _produto("Pula Pula", "pula", self.categoria)
        cache.clear()
        html = self.client.get(reverse("categoria_detalhe", args=[self.categoria.pk])).content.decode()
        marcas = [json.loads(m.replace("&quot;", '"')) for m in re.findall(r'data-fotos-card="([^"]*)"', html)]
        fotos = {tuple(sorted(x.split("/")[-1].split(".")[0] for x in m)) for m in marcas}
        self.assertIn(("pebolim", "pebolim-verso"), fotos)
        self.assertFalse(any("pula" in f for par in fotos for f in par))
        self.assertTrue(all(m[0].endswith(("pebolim.png", "astronautas.png")) or "pebolim" in m[0] or "astronautas" in m[0]
                            for m in marcas))

    def test_o_script_que_gira_as_fotos_esta_em_toda_pagina(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn("site/ls-giro.js", html)

    def test_na_arena_uma_vez_com_os_dois_3d(self):
        dados = dados_publicos_da_arena()
        nomes = [b["nome"] for b in dados["brinquedos_arena"]]
        self.assertEqual(nomes.count("Air Game Kids"), 1)
        item = next(b for b in dados["brinquedos_arena"] if b["nome"] == "Air Game Kids")
        self.assertIn("air-game-kids-astronautas.glb", item["modelo"])
        self.assertEqual([m["nome"] for m in item["adesivos3d"]], ["Astronautas", "Alienígenas"])
        self.assertIn("air-game-kids-alienigenas", item["modelos_variantes"])
        self.assertNotIn("modelo-air-game-kids-alienigenas", [b["id"] for b in dados["brinquedos_arena"]])


class PaginaDoProdutoTests(_ComAdesivos):
    def _pagina(self, extra=""):
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[self.base.pk]) + extra)
        self.assertEqual(resposta.status_code, 200)
        return resposta

    def test_um_objeto_sem_as_fichas_que_trocavam_a_pagina(self):
        html = self._pagina().content.decode()
        self.assertNotIn("produto-adesivos", html)
        self.assertNotIn("?adesivo=", html)

    def test_a_galeria_tem_as_duas_artes(self):
        nomes = [i.imagem.name for i in self._pagina().context["imagens_brinquedo"]]
        self.assertEqual(nomes[0], "imagens_brinquedos/astronautas.png")
        self.assertIn("imagens_brinquedos/alienigenas.png", nomes)

    def test_um_visor_3d_com_os_dois_modelos(self):
        resposta = self._pagina("?adesivo=alienigenas")
        html = resposta.content.decode()
        self.assertEqual(html.count("data-visor3d hidden"), 1)
        self.assertIn("air-game-kids-astronautas.glb", resposta.context["objeto_3d"].url)
        self.assertEqual([m["nome"] for m in resposta.context["adesivos3d"]], ["Astronautas", "Alienígenas"])
        self.assertIn('data-adesivos3d="adesivos3d-dados"', html)
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


class OrcamentoTests(_ComAdesivos):
    def test_o_ver_em_3d_da_proposta_tem_os_dois_3d(self):
        class Item:
            brinquedo_id = self.base.pk
            brinquedo = self.base
        com = variantes.produtos_com_adesivos()
        self.assertEqual([m["nome"] for m in variantes.modelos_do_item(Item(), com)], ["Astronautas", "Alienígenas"])
        self.assertEqual([m["nome"] for m in variantes.modelos_do_item(Item())], ["Astronautas", "Alienígenas"])

        class Outro:
            brinquedo_id = 999
            brinquedo = _produto("Pebolim", "pebolim")
        self.assertEqual(variantes.modelos_do_item(Outro(), com), [])


class CarrinhoTests(_ComAdesivos):
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
        self.client.post(self.url, {"quantidade": 1, "adesivo": "Dinossauros"})  # não é do produto: não entra
        linhas = {i.adesivo: i.quantidade for i in ItemCarrinho.objects.all()}
        self.assertEqual(linhas, {"Alienígenas": 2, "Astronautas": 1, "": 1})
        self.assertContains(self.client.get(reverse("carrinho")), "adesivo Alienígenas")

    def test_o_pedido_leva_o_adesivo_e_ele_volta_para_o_carrinho(self):
        self.client.post(self.url, {"quantidade": 1, "adesivo": "Alienígenas"})
        item = ItemCarrinho.objects.get()
        pedido = criar_pedido_a_partir_do_carrinho(item.carrinho)
        self.assertEqual(pedido.itens.get().nome_item, "Air Game Kids — adesivo Alienígenas")
        ItemCarrinho.objects.all().delete()
        pedido.status = "aguardando_pagamento"
        pedido.carrinho_origem = item.carrinho
        pedido.save(update_fields=["status", "carrinho_origem"])
        pedido.devolver_ao_carrinho()
        self.assertEqual(ItemCarrinho.objects.get().adesivo, "Alienígenas")


class PainelTests(_ComAdesivos):
    """O painel (Gestão de Brinquedos): um objeto só, o selo "2 adesivos" e a seção "Adesivos" do cadastro."""

    INTERNO = {"HTTP_HOST": "interno.testserver"}
    AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
    ROTA = "/site/brinquedos/"

    def setUp(self):
        super().setUp()
        import tempfile
        from unittest import mock

        from django.core.files.storage import FileSystemStorage

        self.gestor = User.objects.create_superuser("catalogo-adesivos", "c@exemplo.com", "x")
        self.client.force_login(self.gestor)
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        disco = FileSystemStorage(location=pasta.name)
        for campo in (Brinquedos._meta.get_field("imagem_brinquedo"), ImagemBrinquedo._meta.get_field("imagem"),
                      VarianteAdesivo._meta.get_field("arquivo_3d")):
            troca = mock.patch.object(campo, "storage", disco)
            troca.start()
            self.addCleanup(troca.stop)

    def _foto(self, nome):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        arquivo = BytesIO()
        Image.new("RGB", (4, 3), "red").save(arquivo, "PNG")
        return SimpleUploadedFile(nome, arquivo.getvalue(), content_type="image/png")

    def test_um_objeto_com_o_selo_e_os_adesivos_no_cadastro(self):
        resposta = self.client.get(self.ROTA, **self.INTERNO)
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertEqual(html.count('class="bq-nome">Air Game Kids<'), 1)
        self.assertNotIn("Air Game Kids Alienígenas", html)
        self.assertIn("2 adesivos", html)
        self.assertIn("data-adesivos", html)
        dados = json.loads(re.search(r'id="toysAdminData"[^>]*>(.*?)</script>', html, re.S).group(1))
        adesivos = next(d for d in dados if d["id"] == self.base.pk)["adesivos"]
        self.assertEqual([(a["nome"], a["padrao"]) for a in adesivos], [("Astronautas", True), ("Alienígenas", False)])
        self.assertEqual(adesivos[1]["arquivo_3d"], "air-game-kids-alienigenas.glb")
        self.assertEqual(len(adesivos[1]["fotos"]), 2)

    def test_incluir_e_tirar_um_adesivo(self):
        pebolim = _produto("Pebolim", "pebolim")
        resposta = self.client.post(self.ROTA, {
            "action": "adesivo_incluir", "id": pebolim.pk, "adesivo_nome": "Copa",
            "adesivo_padrao_nome": "Clássico", "adesivo_fotos": [self._foto("copa-1.png"), self._foto("copa-2.png")],
        }, **self.AJAX)
        dados = json.loads(resposta.content)
        self.assertEqual(dados["status"], "sucesso", dados)
        self.assertEqual([(a["nome"], a["padrao"], len(a["fotos"])) for a in dados["adesivos"]],
                         [("Clássico", True, 0), ("Copa", False, 2)])
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo__startswith="Pebolim").count(), 1)
        copa = VarianteAdesivo.objects.get(brinquedo=pebolim, slug="copa")
        self.assertEqual(copa.fotos.count(), 2)
        # tirar: as fotos saem junto; sem outro adesivo, o padrão sai também
        resposta = self.client.post(self.ROTA, {"action": "adesivo_tirar", "id": pebolim.pk, "adesivo_id": copa.pk}, **self.AJAX)
        self.assertEqual(json.loads(resposta.content)["adesivos"], [])
        self.assertFalse(VarianteAdesivo.objects.filter(brinquedo=pebolim).exists())
        self.assertEqual(ImagemBrinquedo.objects.filter(brinquedo=pebolim).count(), 1)
        # o padrão não sai pela seção (é o próprio brinquedo)
        padrao = VarianteAdesivo.objects.get(brinquedo=self.base, padrao=True)
        resposta = self.client.post(self.ROTA, {"action": "adesivo_tirar", "id": self.base.pk, "adesivo_id": padrao.pk}, **self.AJAX)
        self.assertEqual(resposta.status_code, 400)
