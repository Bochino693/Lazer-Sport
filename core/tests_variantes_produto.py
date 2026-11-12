"""Os adesivos: um objeto só no banco, cada adesivo com as posições e o 3D dele (LEIA-ME, seção 72).

O cliente: "DEVE MUDAR A ESTRUTURA DOS OBJETOS, DEIXAR SOMENTE UM MAS COM O
OUTRO ADESIVO E SEU RESPECTIVO OBJETO 3D" e "cada adesivo deve ter fotos das
posições e um objeto 3d, um outro adesivo, mesmas fotos das posições e
referente a ele um objeto 3d, padronize isso para todos", "de forma alguma
use as fotos de fundo branco". O que estes testes protegem:

  * a estrutura de TODO brinquedo: Brinquedo -> adesivos (o padrão sempre,
    `Brinquedos.adesivo_padrao`), cada um com as fotos das posições e o 3D;
  * a galeria, o card (o giro) e a Arena: as posições do adesivo padrão, uma
    por posição, NUNCA a foto sem fundo (a de fundo branco, o recorte);
  * a página do produto: o seletor grande junto da galeria; trocar o adesivo
    troca as fotos e o 3D ali mesmo (e o endereço, o WhatsApp, o carrinho);
  * as migrações: esquema e dados separados (0181 / 0182 / 0183); a 0169 e a
    0182 rodadas duas vezes não mudam nada e nenhum adesivo perde foto ou 3D;
    a volta da 0182 devolve o banco; a 0183 nunca troca a foto de alguém;
  * nada de duas fotos quase iguais no mesmo adesivo, nada de vista sem fundo
    (core.conferir_fotos), no painel e nas vistas tiradas do 3D;
  * o painel: as seis posições e o 3D de cada adesivo, o recorte para baixar.
"""

import importlib
import json
import re
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.apps import apps as registro
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations import (AddConstraint, AddField, AlterField, RemoveConstraint, RemoveField,
                                             RunPython)
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from PIL import Image, ImageDraw

from . import conferir_fotos, variantes
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
migracao_0181 = importlib.import_module("core.migrations.0181_adesivo_padrao_e_posicoes")
migracao_0182 = importlib.import_module("core.migrations.0182_adesivo_padrao_de_todo_brinquedo")
migracao_0183 = importlib.import_module("core.migrations.0183_posicoes_do_3d_dos_adesivos")

GLB_ALIEN = "site/arena/modelos/air-game-kids-alienigenas.glb"
GLB_ASTRONAUTAS = "site/arena/modelos/air-game-kids-astronautas.glb"
ANTES = ("core", "0168_variantes_donas_do_3d_e_das_fotos")
MODELOS = Path(__file__).resolve().parent / "static" / "site" / "arena" / "modelos"


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


def _imagem(nome, desenho="ruido", tamanho=(96, 72)):
    """Uma foto de teste: "ruido" (cada uma diferente), "branco" (fundo branco), "recorte" (transparente)."""
    if desenho == "ruido":
        imagem = Image.merge("RGB", [Image.effect_noise(tamanho, 90) for _ in range(3)])
        formato, tipo = "PNG", "image/png"
    elif desenho == "branco":
        imagem = Image.new("RGB", tamanho, "white")
        ImageDraw.Draw(imagem).rectangle((24, 12, 70, 66), fill=(20, 60, 200))
        formato, tipo = "PNG", "image/png"
    else:
        imagem = Image.new("RGBA", tamanho, (0, 0, 0, 0))
        ImageDraw.Draw(imagem).rectangle((24, 12, 70, 66), fill=(20, 60, 200, 255))
        formato, tipo = "PNG", "image/png"
    arquivo = BytesIO()
    imagem.save(arquivo, formato)
    return SimpleUploadedFile(nome, arquivo.getvalue(), content_type=tipo)


class _ComAdesivos(TestCase):
    """O Air Game Kids como fica: um produto, o adesivo Astronautas (o padrão) e o Alienígenas (fotos e 3D dele).

    O padrão tem a frente e o lado direito, a foto de fundo branco de antes (a
    "original") e um recorte; o Alienígenas, a frente e o lado direito dele.
    """

    def setUp(self):
        cache.clear()
        self.categoria = CategoriasBrinquedos.objects.create(nome_categoria="Jogos de Mesa", imagem_categoria="categorias/m.png")
        self.base = _produto("Air Game Kids", "astronautas", self.categoria,
                             altura_m=Decimal("0.90"), largura_m=Decimal("0.86"), profundidade_m=Decimal("1.50"))
        ObjetoTresD.objects.create(brinquedo=self.base, arquivo_estatico=GLB_ASTRONAUTAS, codigo="air-game-kids-astronautas")
        # todo brinquedo nasce com o adesivo padrão ("Padrão"): aqui ele se chama Astronautas
        self.padrao = self.base.adesivo_padrao
        VarianteAdesivo.objects.filter(pk=self.padrao.pk).update(nome="Astronautas", slug="astronautas")
        self.padrao.refresh_from_db()
        ImagemBrinquedo.objects.create(brinquedo=self.base, variante=self.padrao, tipo="lado_direito", ordem=2,
                                       imagem="imagens_brinquedos/astronautas-lado.png")
        ImagemBrinquedo.objects.create(brinquedo=self.base, variante=self.padrao, tipo=None, ordem=3,
                                       papel_na_capa="original", imagem="imagens_brinquedos/astronautas-branco.png")
        ImagemBrinquedo.objects.create(brinquedo=self.base, variante=self.padrao, tipo=None, ordem=4,
                                       papel_na_capa="recorte", imagem="imagens_brinquedos/astronautas-removebg.png")
        self.alien = VarianteAdesivo.objects.create(
            brinquedo=self.base, nome="Alienígenas", slug="alienigenas", ordem=2, padrao=False,
            arquivo_estatico_3d=GLB_ALIEN, codigo_3d="air-game-kids-alienigenas", id_antigo=54,
        )
        for ordem, (nome, tipo) in enumerate((("alienigenas", "perfil"), ("alienigenas-lado", "lado_direito")), start=5):
            ImagemBrinquedo.objects.create(brinquedo=self.base, variante=self.alien, tipo=tipo, ordem=ordem,
                                           imagem=f"imagens_brinquedos/{nome}.png", texto_alternativo="os alienígenas")
        self.base.refresh_from_db()
        cache.clear()


class EstruturaTests(_ComAdesivos):
    def test_todo_brinquedo_nasce_com_o_adesivo_padrao(self):
        pebolim = _produto("Pebolim", "pebolim")
        self.assertEqual((pebolim.adesivo_padrao.nome, pebolim.adesivo_padrao.padrao), ("Padrão", True))
        self.assertEqual(list(pebolim.imagens_brinquedo.values_list("variante_id", flat=True)), [pebolim.adesivo_padrao_id])
        # a foto nova sem adesivo é do padrão
        foto = ImagemBrinquedo.objects.create(brinquedo=pebolim, tipo="verso", ordem=2, imagem="imagens_brinquedos/p-verso.png")
        self.assertEqual(foto.variante_id, pebolim.adesivo_padrao_id)

    def test_um_objeto_com_os_dois_adesivos(self):
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo__startswith="Air Game Kids").count(), 1)
        self.assertEqual([v.nome for v in self.base.variantes_adesivo.order_by("ordem")], ["Astronautas", "Alienígenas"])
        self.assertEqual(self.base.adesivo_padrao_id, self.padrao.pk)
        self.assertIn("air-game-kids-alienigenas.glb", self.alien.url_3d)
        self.assertEqual(self.alien.fotos.count(), 2)
        self.assertFalse(hasattr(self.alien, "origem"))

    def test_cada_adesivo_com_as_posicoes_e_o_3d(self):
        adesivos = variantes.adesivos_da_pagina(self.base)
        self.assertEqual([(a["nome"], a["padrao"]) for a in adesivos], [("Astronautas", True), ("Alienígenas", False)])
        astronautas, alien = adesivos
        self.assertEqual([(f.tipo, f.imagem.name) for f in astronautas["fotos"]],
                         [("perfil", "imagens_brinquedos/astronautas.png"), ("lado_direito", "imagens_brinquedos/astronautas-lado.png")])
        self.assertEqual([(f.tipo, f.imagem.name) for f in alien["fotos"]],
                         [("perfil", "imagens_brinquedos/alienigenas.png"), ("lado_direito", "imagens_brinquedos/alienigenas-lado.png")])
        self.assertIn("air-game-kids-astronautas.glb", astronautas["url_3d"])
        self.assertIn("air-game-kids-alienigenas.glb", alien["url_3d"])

    def test_a_galeria_e_a_do_padrao_sem_a_foto_sem_fundo(self):
        nomes = [f.imagem.name for f in self.base.imagens_ordenadas]
        self.assertEqual(nomes, ["imagens_brinquedos/astronautas.png", "imagens_brinquedos/astronautas-lado.png"])
        self.assertEqual(self.base.imagem_perfil.name, "imagens_brinquedos/astronautas.png")
        # a de fundo branco e o recorte ficam guardados no adesivo, fora do site
        guardadas = self.padrao.fotos.filter(papel_na_capa__in=ImagemBrinquedo.PAPEIS_FORA_DO_SITE)
        self.assertEqual(guardadas.count(), 2)
        self.assertTrue(all(f.fora_do_site for f in guardadas))
        com_prefetch = Brinquedos.objects.prefetch_related("imagens_brinquedo").get(pk=self.base.pk)
        self.assertEqual([f.imagem.name for f in com_prefetch.imagens_ordenadas], nomes)
        self.assertEqual([f.imagem.name for f in galeria_publica(self.base.imagens_brinquedo.all(), adesivo_id=self.alien.pk)],
                         ["imagens_brinquedos/alienigenas.png", "imagens_brinquedos/alienigenas-lado.png"])

    def test_uma_foto_por_posicao_em_cada_adesivo(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            ImagemBrinquedo.objects.create(brinquedo=self.base, variante=self.alien, tipo="perfil", ordem=9,
                                           imagem="imagens_brinquedos/outra.png")
        # a mesma posição em outro adesivo do mesmo brinquedo pode
        self.assertEqual(ImagemBrinquedo.objects.filter(brinquedo=self.base, tipo="perfil").count(), 2)

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
        self.assertTrue(all(isinstance(op, (RemoveConstraint, AddField, AlterField, AddConstraint))
                            for op in migracao_0181.Migration.operations))
        self.assertTrue(all(isinstance(op, RunPython) for op in migracao_0182.Migration.operations))
        self.assertTrue(all(isinstance(op, RunPython) for op in migracao_0183.Migration.operations))
        self.assertIn(("core", "0167_jogadas_registradas"), migracao_0168.Migration.dependencies)
        self.assertIn(ANTES, migracao_0169.Migration.dependencies)
        self.assertIn(("core", "0169_um_objeto_no_banco"), migracao_0170.Migration.dependencies)
        self.assertIn(("core", "0180_maquinas_vermelhas_no_showroom"), migracao_0181.Migration.dependencies)
        self.assertIn(("core", "0181_adesivo_padrao_e_posicoes"), migracao_0182.Migration.dependencies)
        self.assertIn(("core", "0182_adesivo_padrao_de_todo_brinquedo"), migracao_0183.Migration.dependencies)
        # a 0182 volta (a 0181 também: só esquema); a 0183 não apaga nada na volta
        self.assertTrue(migracao_0182.Migration.operations[0].reversible)
        self.assertEqual(migracao_0182.Migration.operations[0].reverse_code.__name__, "despadronizar")

    def test_a_subida_so_no_render(self):
        with mock.patch.object(variantes, "subir_posicoes") as subir, self.settings(IS_RENDER=False):
            variantes.subir_posicoes_no_deploy(registro)
        subir.assert_not_called()
        with mock.patch.object(variantes, "subir_posicoes", side_effect=RuntimeError("fora do ar")), \
                self.settings(IS_RENDER=True):
            avisos = []
            variantes.subir_posicoes_no_deploy(registro, avisar=avisos.append)  # o deploy segue
        self.assertIn("posicoes_dos_adesivos", avisos[0])


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
        # (a ficha era a principal e um extra: o produto fica só como o principal, sem repetir nos extras)
        self.assertEqual(list(promo.brinquedos_extras.values_list("pk", flat=True)), [])
        self.assertEqual(list(Combos.objects.get(pk=combo.pk).brinquedos.values_list("pk", flat=True)), [produto.pk])
        # o endereço antigo vai para o produto
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[ficha.pk]))
        self.assertEqual((resposta.status_code, resposta["Location"]), (301, f"/brinquedo/{produto.pk}/"))


class PadronizarTests(TestCase):
    """A 0182 (core.variantes.padronizar) num banco como o do ar: rodada DUAS vezes, nenhum adesivo perde nada."""

    def _como_antes_da_0182(self):
        """O Air Game Kids como a 0170 deixou: as fotos do padrão sem adesivo, o 3D só no ObjetoTresD."""
        base = Brinquedos.objects.create(nome_brinquedo="Air Game Kids", descricao="x", avaliacao=5, voltz="220V",
                                         valor_brinquedo=Decimal("6990.00"))
        padrao = base.adesivo_padrao
        VarianteAdesivo.objects.filter(pk=padrao.pk).update(nome="Astronautas", slug="astronautas")
        Brinquedos.objects.filter(pk=base.pk).update(adesivo_padrao=None)
        ObjetoTresD.objects.create(brinquedo=base, arquivo_estatico=GLB_ASTRONAUTAS, codigo="air-game-kids-astronautas",
                                   medidas=[0.9, 0.83, 1.51])
        alien = VarianteAdesivo.objects.create(brinquedo=base, nome="Alienígenas", slug="alienigenas", ordem=2,
                                               arquivo_estatico_3d=GLB_ALIEN, codigo_3d="air-game-kids-alienigenas")
        fotos = [
            (None, "perfil", "cena", "imagens_brinquedos/galeria/cena-air-game-kids-56aeb3d2d5.webp"),
            (None, None, "original", "imagens_brinquedos/WhatsApp-removebg-preview_hcfnmt.png"),
            (None, None, "", "imagens_brinquedos/WhatsApp-removebg-preview_hcfnmt.png"),  # a cópia da original
            (alien, None, "outra_arte", "imagens_brinquedos/galeria/air-game-kids-alienigenas-capa_FWTKYic.webp"),
            (alien, None, "outra_arte", "imagens_brinquedos/galeria/air-game-kids-alienigenas-lado_esquerdo_SjqMzHc.webp"),
            (alien, None, "outra_arte", "imagens_brinquedos/galeria/air-game-kids-alienigenas-lado_direito_1IFiG3d.webp"),
            (alien, None, "outra_arte", "imagens_brinquedos/galeria/air-game-kids-alienigenas-frente_qvkpjbc.webp"),
            (alien, None, "outra_arte", "imagens_brinquedos/galeria/air-game-kids-alienigenas-verso_lNZxZJb.webp"),
            (alien, None, "outra_arte", "imagens_brinquedos/galeria/air-game-kids-alienigenas-tampo_Kbpuu72.webp"),
        ]
        for ordem, (variante, tipo, papel, nome) in enumerate(fotos, start=1):
            foto = ImagemBrinquedo.objects.create(brinquedo=base, variante=variante or padrao, tipo=tipo, ordem=ordem,
                                                  papel_na_capa=papel, imagem=nome)
            if variante is None:
                ImagemBrinquedo.objects.filter(pk=foto.pk).update(variante=None)
        # um brinquedo sem adesivo nenhum (como todos os outros antes da 0182) e uma máquina da Black Friday
        pebolim = Brinquedos.objects.create(nome_brinquedo="Pebolim", descricao="x", avaliacao=5, voltz="220V")
        bf = Brinquedos.objects.create(nome_brinquedo="Basquete Kids", descricao="x", avaliacao=5, voltz="220V")
        for brinquedo in (pebolim, bf):
            ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="perfil", ordem=1, imagem=f"imagens_brinquedos/{brinquedo.pk}.png")
            ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo=None, ordem=2, imagem="imagens_brinquedos/x-removebg-preview.png")
            ImagemBrinquedo.objects.filter(brinquedo=brinquedo).update(variante=None)  # (antes de tirar o adesivo: ele leva as fotos)
            VarianteAdesivo.objects.filter(brinquedo=brinquedo).delete()
        return base, padrao, alien, pebolim, bf

    @staticmethod
    def _retrato():
        fotos = sorted(ImagemBrinquedo.objects.values_list("id", "brinquedo_id", "variante_id", "tipo", "papel_na_capa", "imagem"))
        adesivos = sorted(VarianteAdesivo.objects.values_list("id", "brinquedo_id", "nome", "padrao", "arquivo_3d",
                                                              "arquivo_estatico_3d", "codigo_3d"))
        return fotos, adesivos, sorted(Brinquedos.objects.values_list("id", "adesivo_padrao_id"))

    def test_duas_vezes_com_dois_adesivos_nada_se_perde(self):
        base, padrao, alien, pebolim, bf = self._como_antes_da_0182()
        n_fotos = ImagemBrinquedo.objects.count()
        variantes.padronizar(registro, avisar=_calado)
        primeiro = self._retrato()
        variantes.padronizar(registro, avisar=_calado)
        self.assertEqual(self._retrato(), primeiro)  # de novo: nada muda
        self.assertEqual(ImagemBrinquedo.objects.count(), n_fotos)  # nenhuma foto sumiu

        base.refresh_from_db()
        padrao.refresh_from_db()
        alien.refresh_from_db()
        # o padrão: o adesivo do brinquedo, com as fotos dele e o 3D (o do ObjetoTresD, que fica)
        self.assertEqual(base.adesivo_padrao_id, padrao.pk)
        self.assertEqual((padrao.arquivo_estatico_3d, padrao.codigo_3d, padrao.medidas_3d),
                         (GLB_ASTRONAUTAS, "air-game-kids-astronautas", [0.9, 0.83, 1.51]))
        self.assertTrue(ObjetoTresD.objects.filter(brinquedo=base, ativo=True).exists())
        self.assertEqual(padrao.fotos.count(), 3)
        self.assertEqual(list(padrao.fotos.exclude(tipo=None).values_list("tipo", flat=True)), ["perfil"])
        # a cópia da foto de fundo branco virou recorte para artes (guardada); a original continua original
        self.assertEqual(sorted(padrao.fotos.filter(tipo=None).values_list("papel_na_capa", flat=True)), ["original", "recorte"])
        # o Alienígenas: o 3D dele intacto, as 6 fotos dele, com as posições de volta pelo nome do arquivo
        self.assertEqual((alien.arquivo_estatico_3d, alien.codigo_3d), (GLB_ALIEN, "air-game-kids-alienigenas"))
        posicoes = {f.imagem.name.split("air-game-kids-alienigenas-")[1].rsplit("_", 1)[0]: f.tipo for f in alien.fotos.all()}
        self.assertEqual(posicoes, {"capa": "perfil", "lado_esquerdo": "lado_esquerdo", "lado_direito": "lado_direito",
                                    "frente": "tres_quartos", "verso": "verso", "tampo": "de_cima"})
        # todo brinquedo tem o padrão; o sem adesivo ganhou um "Padrão"
        self.assertEqual(Brinquedos.objects.filter(adesivo_padrao=None).count(), 0)
        pebolim.refresh_from_db()
        self.assertEqual(pebolim.adesivo_padrao.nome, "Padrão")
        self.assertEqual(sorted(pebolim.imagens_brinquedo.values_list("papel_na_capa", flat=True)), ["", "recorte"])
        # a da Black Friday: só a estrutura, nenhuma foto marcada
        bf.refresh_from_db()
        self.assertEqual(bf.adesivo_padrao.nome, "Padrão")
        self.assertEqual(list(bf.imagens_brinquedo.values_list("papel_na_capa", flat=True)), ["", ""])
        self.assertEqual(bf.imagens_brinquedo.filter(variante=bf.adesivo_padrao).count(), 2)

    def test_o_3d_que_o_adesivo_ja_tem_nunca_e_trocado(self):
        base, padrao, alien, _pebolim, _bf = self._como_antes_da_0182()
        VarianteAdesivo.objects.filter(pk=padrao.pk).update(arquivo_estatico_3d="site/arena/modelos/o-meu.glb")
        variantes.padronizar(registro, avisar=_calado)
        variantes.padronizar(registro, avisar=_calado)
        padrao.refresh_from_db()
        self.assertEqual(padrao.arquivo_estatico_3d, "site/arena/modelos/o-meu.glb")

    def test_a_volta_devolve_o_banco_e_a_ida_de_novo_da_o_mesmo(self):
        base, *_resto = self._como_antes_da_0182()
        antes = sorted(ImagemBrinquedo.objects.values_list("id", "variante_id", "tipo", "papel_na_capa"))
        variantes.padronizar(registro, avisar=_calado)
        do_air_game = sorted(ImagemBrinquedo.objects.filter(brinquedo=base).values_list("id", "variante_id", "tipo", "papel_na_capa"))
        variantes.despadronizar(registro)
        self.assertEqual(sorted(ImagemBrinquedo.objects.values_list("id", "variante_id", "tipo", "papel_na_capa")), antes)
        self.assertFalse(VarianteAdesivo.objects.filter(nome="Padrão").exists())  # os criados pela 0182 saem
        self.assertEqual(VarianteAdesivo.objects.filter(brinquedo=base).count(), 2)  # o Astronautas e o Alienígenas ficam
        variantes.padronizar(registro, avisar=_calado)
        self.assertEqual(sorted(ImagemBrinquedo.objects.filter(brinquedo=base).values_list(
            "id", "variante_id", "tipo", "papel_na_capa")), do_air_game)


class SubirPosicoesTests(TestCase):
    """A 0183 (core.variantes.subir_posicoes): as vistas do 3D sobem uma vez, sem trocar a foto de ninguém."""

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.disco = FileSystemStorage(location=pasta.name)
        troca = mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", self.disco)
        troca.start()
        self.addCleanup(troca.stop)
        self.base = _produto("Air Game Kids", "astronautas")
        self.padrao = self.base.adesivo_padrao
        VarianteAdesivo.objects.filter(pk=self.padrao.pk).update(nome="Astronautas", slug="astronautas",
                                                                 arquivo_estatico_3d=GLB_ASTRONAUTAS)
        self.alien = VarianteAdesivo.objects.create(brinquedo=self.base, nome="Alienígenas", slug="alienigenas", ordem=2,
                                                    arquivo_estatico_3d=GLB_ALIEN)
        # a vista de antes no lado esquerdo (era o direito de novo) e a foto que alguém pôs no verso
        self.velha = ImagemBrinquedo.objects.create(
            brinquedo=self.base, variante=self.alien, tipo="lado_esquerdo", ordem=2,
            imagem="imagens_brinquedos/galeria/air-game-kids-alienigenas-lado_esquerdo_SjqMzHc.webp")
        self.minha = ImagemBrinquedo.objects.create(brinquedo=self.base, variante=self.alien, tipo="verso", ordem=3,
                                                    imagem="imagens_brinquedos/galeria/a-minha-foto.jpg")

    def test_duas_vezes_sobe_uma_e_nao_troca_a_foto_de_ninguem(self):
        variantes.subir_posicoes(Brinquedos, VarianteAdesivo, ImagemBrinquedo, avisar=_calado)
        primeiro = sorted(ImagemBrinquedo.objects.values_list("id", "variante_id", "tipo", "imagem"))
        variantes.subir_posicoes(Brinquedos, VarianteAdesivo, ImagemBrinquedo, avisar=_calado)
        self.assertEqual(sorted(ImagemBrinquedo.objects.values_list("id", "variante_id", "tipo", "imagem")), primeiro)
        # os Astronautas: a frente (a foto do catálogo) e as cinco posições do 3D
        self.assertEqual(sorted(self.padrao.fotos.values_list("tipo", flat=True)),
                         ["de_cima", "lado_direito", "lado_esquerdo", "perfil", "tres_quartos", "verso"])
        self.assertEqual(self.padrao.fotos.get(tipo="perfil").imagem.name, "imagens_brinquedos/astronautas.png")
        # o Alienígenas: a vista nova no lado esquerdo; a de antes fica guardada, sem posição
        self.velha.refresh_from_db()
        self.assertIsNone(self.velha.tipo)
        self.assertIn("air-game-kids-alienigenas-lado_esquerdo-v2", self.alien.fotos.get(tipo="lado_esquerdo").imagem.name)
        # a foto que alguém pôs no verso fica
        self.minha.refresh_from_db()
        self.assertEqual(self.minha.tipo, "verso")
        self.assertFalse(self.alien.fotos.filter(imagem__contains="verso-v2").exists())
        # nenhum adesivo perdeu o 3D
        self.padrao.refresh_from_db()
        self.alien.refresh_from_db()
        self.assertEqual((self.padrao.arquivo_estatico_3d, self.alien.arquivo_estatico_3d), (GLB_ASTRONAUTAS, GLB_ALIEN))
        # o comando faz o mesmo (e não sobe nada de novo)
        from django.core.management import call_command

        from io import StringIO

        call_command("posicoes_dos_adesivos", stdout=StringIO())
        self.assertEqual(sorted(ImagemBrinquedo.objects.values_list("id", "variante_id", "tipo", "imagem")), primeiro)


class ConferirFotosTests(TestCase):
    """Nada de foto sem fundo no site, nada de duas fotos quase iguais no mesmo adesivo."""

    def test_sem_fundo_e_quase_igual(self):
        self.assertTrue(conferir_fotos.sem_fundo(_imagem("b.png", "branco")))
        self.assertTrue(conferir_fotos.sem_fundo(_imagem("t.png", "recorte")))
        self.assertFalse(conferir_fotos.sem_fundo(str(MODELOS / "air-game-kids-alienigenas" / "capa.webp")))
        foto = _imagem("a.png")
        espelhada = BytesIO()
        Image.open(foto).transpose(Image.FLIP_LEFT_RIGHT).save(espelhada, "PNG")
        a = conferir_fotos.assinatura(foto)
        self.assertTrue(conferir_fotos.parecidas(a, conferir_fotos.assinatura(BytesIO(espelhada.getvalue()))))
        self.assertFalse(conferir_fotos.parecidas(a, conferir_fotos.assinatura(_imagem("c.png"))))

    def test_as_vistas_de_cada_adesivo_sao_diferentes_e_com_fundo(self):
        for (produto, adesivo), (pasta, fotos) in variantes.POSICOES_DO_3D.items():
            with self.subTest(f"{produto} ({adesivo})"):
                caminhos = [MODELOS / pasta / arquivo for arquivo, *_ in fotos]
                if (MODELOS / pasta / "capa.webp").exists():  # a frente (a capa) também conta
                    caminhos.append(MODELOS / pasta / "capa.webp")
                self.assertTrue(all(c.exists() for c in caminhos), caminhos)
                self.assertFalse([c.name for c in caminhos if conferir_fotos.sem_fundo(str(c))])
                assinaturas = [conferir_fotos.assinatura(str(c)) for c in caminhos]
                self.assertEqual([(caminhos[i].name, caminhos[j].name) for i, j in conferir_fotos.repetidas(assinaturas)], [])

    def test_as_posicoes_dos_nossos_3d_sao_diferentes(self):
        """As vistas que viram posição (o `tipo` em CADASTROS e em POSICOES_DO_3D), por pasta: nenhuma quase igual."""
        from .cadastro_modelos import CADASTROS

        for chave, dados in CADASTROS.items():
            pasta = Path(dados.get("pasta") or MODELOS / chave)
            arquivos = {arquivo for arquivo, tipo, _t in dados.get("fotos", ()) if tipo}
            for (_p, _a), (outra, fotos) in variantes.POSICOES_DO_3D.items():
                if outra == chave:
                    arquivos |= {arquivo for arquivo, *_ in fotos}
            caminhos = sorted(pasta / a for a in arquivos if (pasta / a).exists()
                              and not variantes._vista_sem_fundo(f"{chave}-{a}"))
            with self.subTest(chave):
                assinaturas = [conferir_fotos.assinatura(str(c)) for c in caminhos]
                self.assertEqual([(caminhos[i].name, caminhos[j].name) for i, j in conferir_fotos.repetidas(assinaturas)], [])

    def test_a_lista_das_vistas_sem_fundo_confere_com_os_arquivos(self):
        achadas = {}
        for arquivo in sorted(MODELOS.glob("*/*.webp")):
            if conferir_fotos.sem_fundo(str(arquivo)):
                achadas.setdefault(arquivo.parent.name, set()).add(arquivo.stem)
        # (a do Brinquedão Modelo 5 é da Black Friday: outra frente cuida dela)
        achadas.pop("brinquedao-modelo-5", None)
        self.assertEqual(achadas, {pasta: set(vistas) for pasta, vistas in variantes.VISTAS_SEM_FUNDO.items()})


class RedirecionamentoTests(_ComAdesivos):
    def test_o_endereco_antigo_vai_para_o_produto(self):
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[54]))
        self.assertEqual(resposta.status_code, 301)
        self.assertEqual(resposta["Location"], f"/brinquedo/{self.base.pk}/")

    def test_o_que_nunca_existiu_continua_404(self):
        self.assertEqual(self.client.get(reverse("brinquedo_detalhe", args=[9999])).status_code, 404)


class ListasTests(_ComAdesivos):
    def test_o_produto_aparece_uma_vez_e_o_card_gira_os_adesivos(self):
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
                marcas = re.findall(r'data-fotos-card="([^"]*)"', html)
                cards = [json.loads(m.replace("&quot;", '"')) for m in marcas]
                do_air_game = next(c for c in cards if "astronautas" in c[0]["src"])
                # o card gira POR ADESIVO (o carrossel do cliente): a capa de cada um, o padrão primeiro
                self.assertEqual([(i["src"].split("/")[-1].split(".")[0], i["adesivo"]) for i in do_air_game],
                                 [("astronautas", "Astronautas"), ("alienigenas", "Alienígenas")])
                self.assertNotIn("astronautas-branco", html)
                self.assertNotIn("astronautas-removebg", html)

    def test_um_adesivo_so_nao_gira(self):
        dois = _produto("Pebolim", "pebolim", self.categoria)
        ImagemBrinquedo.objects.create(brinquedo=dois, tipo="verso", ordem=2, imagem="imagens_brinquedos/pebolim-verso.png")
        cache.clear()
        html = self.client.get(reverse("categoria_detalhe", args=[self.categoria.pk])).content.decode()
        marcas = [json.loads(m.replace("&quot;", '"')) for m in re.findall(r'data-fotos-card="([^"]*)"', html)]
        self.assertFalse(any("pebolim" in item["src"] for card in marcas for item in card))
        self.assertTrue(any("alienigenas" in item["src"] for card in marcas for item in card))

    def test_o_script_que_gira_as_fotos_esta_em_toda_pagina(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn("site/ls-giro.js", html)

    def test_na_arena_uma_vez_com_os_dois_3d_e_as_fotos_do_padrao(self):
        dados = dados_publicos_da_arena()
        nomes = [b["nome"] for b in dados["brinquedos_arena"]]
        self.assertEqual(nomes.count("Air Game Kids"), 1)
        item = next(b for b in dados["brinquedos_arena"] if b["nome"] == "Air Game Kids")
        self.assertIn("air-game-kids-astronautas.glb", item["modelo"])
        self.assertEqual([m["nome"] for m in item["adesivos3d"]], ["Astronautas", "Alienígenas"])
        self.assertIn("air-game-kids-alienigenas", item["modelos_variantes"])
        self.assertNotIn("modelo-air-game-kids-alienigenas", [b["id"] for b in dados["brinquedos_arena"]])
        texto = json.dumps(item)
        self.assertIn("astronautas-lado", texto)
        self.assertNotIn("alienigenas-lado", texto)
        self.assertNotIn("astronautas-branco", texto)


class PaginaDoProdutoTests(_ComAdesivos):
    def _pagina(self, extra=""):
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[self.base.pk]) + extra)
        self.assertEqual(resposta.status_code, 200)
        return resposta

    def test_o_seletor_grande_junto_da_galeria(self):
        html = self._pagina().content.decode()
        visual = html[html.index('class="produto-visual"'):html.index('id="produto-informacoes"')]
        self.assertIn("data-adesivos-pagina", visual)  # na coluna da galeria, logo abaixo das miniaturas
        self.assertLess(visual.index("data-galeria-miniaturas"), visual.index("data-adesivos-pagina"))
        self.assertLess(visual.index("data-adesivos-pagina"), visual.index("produto-garantias"))
        self.assertIn('Adesivo: <strong data-adesivo-nome>Astronautas</strong>', visual)
        self.assertEqual(re.findall(r'data-adesivo-slug="([^"]+)"', visual), ["astronautas", "alienigenas"])
        self.assertIn('class="produto-adesivo ativo"', visual)
        self.assertIn('href="?adesivo=alienigenas"', visual)  # sem o script, o link abre a página no adesivo
        self.assertNotIn('class="produto-adesivos"', html[html.index('id="produto-informacoes"'):])

    def test_os_dados_da_troca_tem_as_fotos_e_o_3d_de_cada_adesivo(self):
        resposta = self._pagina()
        html = resposta.content.decode()
        dados = json.loads(re.search(r'id="adesivos-pagina-dados"[^>]*>(.*?)</script>', html, re.S).group(1))
        self.assertEqual([(a["nome"], a["padrao"]) for a in dados], [("Astronautas", True), ("Alienígenas", False)])
        astronautas, alien = dados
        self.assertEqual([f["grande"].split("/")[-1] for f in astronautas["fotos"]], ["astronautas.png", "astronautas-lado.png"])
        self.assertEqual([f["grande"].split("/")[-1] for f in alien["fotos"]], ["alienigenas.png", "alienigenas-lado.png"])
        self.assertIn("air-game-kids-astronautas.glb", astronautas["url_3d"])
        self.assertIn("air-game-kids-alienigenas.glb", alien["url_3d"])
        self.assertIn("Adesivo%3A%20Alien%C3%ADgenas", alien["whatsapp"])
        self.assertIn("adesivo%3Dalienigenas", alien["whatsapp"])
        # nunca a foto sem fundo
        self.assertNotIn("astronautas-branco", html)
        self.assertNotIn("astronautas-removebg", html)

    def test_trocar_o_adesivo_troca_as_fotos_e_o_3d(self):
        resposta = self._pagina("?adesivo=alienigenas")
        self.assertEqual([i.imagem.name for i in resposta.context["imagens_brinquedo"]],
                         ["imagens_brinquedos/alienigenas.png", "imagens_brinquedos/alienigenas-lado.png"])
        self.assertIn("air-game-kids-alienigenas.glb", resposta.context["objeto_3d"]["url"])
        html = resposta.content.decode()
        self.assertIn('Adesivo: <strong data-adesivo-nome>Alienígenas</strong>', html)
        self.assertIn('name="adesivo" value="Alienígenas" data-adesivo-escolhido', html)
        self.assertIn("Adesivo%3A%20Alien%C3%ADgenas", resposta.context["whatsapp_url"])
        # o padrão: as fotos dele
        padrao = self._pagina()
        self.assertEqual([i.imagem.name for i in padrao.context["imagens_brinquedo"]],
                         ["imagens_brinquedos/astronautas.png", "imagens_brinquedos/astronautas-lado.png"])

    def test_a_troca_e_ali_mesmo_com_a_transicao_e_o_3d_junto(self):
        html = self._pagina().content.decode()
        self.assertIn("function escolherAdesivo(slug, origem)", html)
        self.assertIn("trocarFoto(fotos[0].grande, fotos[0].alt, 1)", html)  # a transição da foto da vitrine
        self.assertIn("new CustomEvent('ls:adesivo'", html)
        self.assertNotIn("data-adesivos-navegar", html)
        visor = (MODELOS.parent / "visor3d.js").read_text()
        self.assertIn('document.addEventListener("ls:adesivo", ouvir)', visor)
        self.assertIn("controle.marcar(indice)", visor)
        self.assertNotIn("location.href", visor)
        self.assertIn("caixa.marcar = (i) =>", (MODELOS.parent / "adesivos3d.js").read_text())

    def test_um_visor_3d_com_os_dois_modelos(self):
        resposta = self._pagina()
        html = resposta.content.decode()
        self.assertEqual(html.count("data-visor3d hidden"), 1)
        self.assertIn("air-game-kids-astronautas.glb", resposta.context["objeto_3d"].url)
        self.assertEqual([m["nome"] for m in resposta.context["adesivos3d"]], ["Astronautas", "Alienígenas"])
        self.assertIn('data-adesivos3d="adesivos3d-dados"', html)
        self.assertIn('name="adesivo" value="Astronautas" data-adesivo-escolhido', html)

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
        self.assertNotContains(resposta, 'class="produto-adesivos"')


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
    """O painel (Gestão de Brinquedos): o selo "2 adesivos" e a seção "Adesivos" (as posições e o 3D de cada um)."""

    INTERNO = {"HTTP_HOST": "interno.testserver"}
    AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
    ROTA = "/site/brinquedos/"

    def setUp(self):
        super().setUp()
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

    def _post(self, dados):
        resposta = self.client.post(self.ROTA, dados, **self.AJAX)
        return resposta, json.loads(resposta.content)

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
        astronautas, alien = adesivos
        self.assertEqual(alien["arquivo_3d"], "air-game-kids-alienigenas.glb")
        self.assertEqual(astronautas["arquivo_3d"], "air-game-kids-astronautas.glb")
        # as seis posições de cada adesivo (as vazias para incluir)
        self.assertEqual([p["tipo"] for p in alien["posicoes"]],
                         ["perfil", "tres_quartos", "lado_direito", "lado_esquerdo", "verso", "de_cima"])
        self.assertEqual([bool(p["url"]) for p in alien["posicoes"]], [True, False, True, False, False, False])
        self.assertEqual(len(alien["fotos"]), 2)
        # o recorte para artes (a sem fundo): só aqui, para baixar
        self.assertEqual(sorted(r["arquivo"] for r in astronautas["recortes"]), ["astronautas-branco.png", "astronautas-removebg.png"])
        self.assertEqual(alien["recortes"], [])
        self.assertNotIn("astronautas-branco", json.dumps(astronautas["posicoes"]))

    def test_incluir_e_tirar_um_adesivo(self):
        pebolim = _produto("Pebolim", "pebolim")
        resposta, dados = self._post({
            "action": "adesivo_incluir", "id": pebolim.pk, "adesivo_nome": "Copa",
            "adesivo_padrao_nome": "Clássico", "adesivo_fotos": [_imagem("copa-1.png"), _imagem("copa-2.png")],
        })
        self.assertEqual(dados["status"], "sucesso", dados)
        self.assertEqual([(a["nome"], a["padrao"], len(a["fotos"])) for a in dados["adesivos"]],
                         [("Clássico", True, 1), ("Copa", False, 2)])
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo__startswith="Pebolim").count(), 1)
        copa = VarianteAdesivo.objects.get(brinquedo=pebolim, slug="copa")
        # as fotos mandadas juntas: as primeiras posições livres
        self.assertEqual(sorted(copa.fotos.values_list("tipo", flat=True)), ["perfil", "tres_quartos"])
        # tirar: as fotos saem junto; o padrão fica (todo brinquedo tem um)
        resposta, dados = self._post({"action": "adesivo_tirar", "id": pebolim.pk, "adesivo_id": copa.pk})
        self.assertEqual([a["nome"] for a in dados["adesivos"]], ["Clássico"])
        self.assertEqual(VarianteAdesivo.objects.filter(brinquedo=pebolim).count(), 1)
        self.assertEqual(ImagemBrinquedo.objects.filter(brinquedo=pebolim).count(), 1)
        resposta, _dados = self._post({"action": "adesivo_tirar", "id": self.base.pk, "adesivo_id": self.padrao.pk})
        self.assertEqual(resposta.status_code, 400)

    def test_incluir_e_trocar_a_foto_de_uma_posicao_e_o_3d(self):
        resposta, dados = self._post({"action": "adesivo_posicao", "id": self.base.pk, "adesivo_id": self.alien.pk,
                                      "tipo": "verso", "foto": _imagem("alien-verso.png")})
        self.assertEqual(dados["status"], "sucesso", dados)
        self.assertTrue(self.alien.fotos.filter(tipo="verso").exists())
        # a frente do padrão é a capa do brinquedo
        resposta, dados = self._post({"action": "adesivo_posicao", "id": self.base.pk, "adesivo_id": self.padrao.pk,
                                      "tipo": "perfil", "foto": _imagem("astro-nova.png")})
        self.assertEqual(dados["status"], "sucesso", dados)
        self.base.refresh_from_db()
        self.assertIn("astro-nova", self.base.imagem_brinquedo.name)
        self.assertEqual(self.padrao.fotos.filter(tipo="perfil").count(), 1)

    def test_a_foto_sem_fundo_vira_recorte_para_artes(self):
        for desenho in ("branco", "recorte"):
            with self.subTest(desenho):
                resposta, dados = self._post({"action": "adesivo_posicao", "id": self.base.pk, "adesivo_id": self.alien.pk,
                                              "tipo": "verso", "foto": _imagem(f"alien-{desenho}.png", desenho)})
                self.assertEqual(dados["status"], "sucesso", dados)
                self.assertIn("recorte para artes", dados["msg"])
                self.assertFalse(self.alien.fotos.filter(tipo="verso").exists())
        self.assertEqual(self.alien.fotos.filter(papel_na_capa="recorte", tipo=None).count(), 2)
        alien = next(a for a in dados["adesivos"] if a["nome"] == "Alienígenas")
        self.assertEqual(len(alien["recortes"]), 2)
        cache.clear()
        html = self.client.get(reverse("brinquedo_detalhe", args=[self.base.pk]) + "?adesivo=alienigenas").content.decode()
        self.assertNotIn("alien-branco", html)
        self.assertNotIn("alien-recorte", html)

    def test_a_foto_quase_igual_a_outra_do_adesivo_nao_entra(self):
        foto = _imagem("alien-lado.png")
        resposta, dados = self._post({"action": "adesivo_posicao", "id": self.base.pk, "adesivo_id": self.alien.pk,
                                      "tipo": "lado_esquerdo", "foto": foto})
        self.assertEqual(dados["status"], "sucesso", dados)
        foto.seek(0)
        repetida = SimpleUploadedFile("alien-lado-de-novo.png", foto.read(), content_type="image/png")
        resposta, dados = self._post({"action": "adesivo_posicao", "id": self.base.pk, "adesivo_id": self.alien.pk,
                                      "tipo": "verso", "foto": repetida})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("quase igual", dados["msg"])
        self.assertFalse(self.alien.fotos.filter(tipo="verso").exists())
