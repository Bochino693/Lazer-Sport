"""As fotos de estúdio dos nossos 3D (LEIA-ME, seção 96; core/fotos_estudio.py, a 0197).

O que estes testes protegem:

  * as fotos estão no repositório, no tamanho de sempre do site (a capa 1600 x 1600, as
    vistas 1600 x 1000 ou 1080 x 1080), opacas, leves (até 250 KB) e são as que o estúdio
    (ferramentas/fotos3d/produtos.py) grava;
  * "a máquina encolheu": o Basquete Home azul e o preto (Quadrinhos) ocupam a MESMA altura na
    capa, e os Astronautas e os Alienígenas do Air Game Kids, a mesma caixa (um enquadramento
    só por máquina);
  * a migração: fora do Render, nada; no Render, cada posição com a NOSSA foto de antes (ou
    vazia) ganha a de estúdio, que sobe com a assinatura no nome -- rodar de novo não sobe
    nada, e a foto refeita sobe de novo; a de antes fica guardada no adesivo, fora da galeria;
    a foto da equipe fica; a capa do adesivo padrão é a capa do produto; a volta põe tudo
    como estava.
"""

import importlib
import json
import sys
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
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from . import fotos_estudio
from .models import Brinquedos, ImagemBrinquedo, VarianteAdesivo, galeria_publica

migracao = importlib.import_module("core.migrations.0197_fotos_de_estudio")

RAIZ = Path(__file__).resolve().parent.parent
AREAS = RAIZ / "ferramentas" / "categorias" / "areas-dos-produtos.json"
G = "imagens_brinquedos/galeria/"


def _produtos_do_estudio():
    """O produtos.py do estúdio (Python puro: lido sem o Blender)."""
    sys.path.insert(0, str(RAIZ / "ferramentas" / "fotos3d"))
    try:
        return importlib.import_module("produtos")
    finally:
        sys.path.pop(0)


class ArquivosTests(SimpleTestCase):
    def test_as_fotos_do_site_estao_no_repositorio_no_tamanho_de_sempre(self):
        estudio = _produtos_do_estudio()
        gravadas = {caminho for _p, _v, _t, caminho in estudio.arquivos_do_site()}
        tamanhos = {}
        for chave, produto in estudio.PRODUTOS.items():
            for variante in produto["variantes"]:
                for tomada, dados in produto["tomadas"].items():
                    if "glb" in variante and not dados.get("so_mestre"):  # (o mestre só, fora do site)
                        tamanhos[f"{variante['pasta']}/{tomada}.webp"] = dados["saida"]
                        for extra in variante.get("extras", {}).get(tomada, ()):
                            tamanhos[extra] = dados["saida"]
                for tomada, caminho in variante.get("fotos", {}).items():
                    tamanhos[caminho] = produto["tomadas"][tomada]["saida"]
        self.assertEqual(set(tamanhos), gravadas)
        for caminho, tamanho in tamanhos.items():
            with self.subTest(caminho), Image.open(RAIZ / caminho) as foto:
                self.assertEqual(foto.format, "WEBP")
                self.assertEqual(foto.size, tamanho)
                if not caminho.endswith("/foto.webp"):  # (o recorte sem fundo, para as artes, é o único transparente)
                    self.assertNotIn("A", foto.getbands())
                self.assertLessEqual((RAIZ / caminho).stat().st_size, 250 * 1024)
        # cada foto que a migração sobe é uma das que o estúdio grava, e o site a serve
        for _produto, _adesivo, fotos in fotos_estudio.ITENS:
            for foto in fotos:
                with self.subTest(foto["arquivo"]):
                    self.assertIn(f"core/static/{foto['arquivo']}", gravadas)
                    self.assertTrue(finders.find(foto["arquivo"]))

    def test_a_maquina_nao_encolhe_de_um_adesivo_para_o_outro(self):
        areas = json.loads(AREAS.read_text(encoding="utf-8"))
        azul, preto = areas["produto_basquete-home"], areas["capa_basquete-street-quadrinhos"]
        # a mesma altura e o mesmo pé na capa (a foto da fábrica entra no tamanho do 3D)
        self.assertAlmostEqual(azul[3] - azul[1], preto[3] - preto[1], delta=0.01)
        self.assertAlmostEqual(azul[3], preto[3], delta=0.01)
        # os dois adesivos do Air Game Kids: a mesma caixa em todas as vistas
        for vista in ("capa_{}", "vista_{}_frente", "vista_{}_lado_direito", "vista_{}_lado_esquerdo",
                      "vista_{}_verso", "vista_{}_tampo"):
            with self.subTest(vista):
                self.assertEqual(areas[vista.format("air-game-kids-astronautas")],
                                 areas[vista.format("air-game-kids-alienigenas")])
        self.assertEqual(areas["produto_air-game-kids"], areas["capa_air-game-kids-astronautas"])
        # a máquina inteira e grande na capa (a folga de ~7,5% no lado que limita)
        for chave in ("capa_basquete-street-quadrinhos", "capa_air-game-kids-alienigenas", "capa_strike-kids"):
            with self.subTest(chave):
                x0, y0, x1, y1 = areas[chave]
                self.assertTrue(x0 >= 0.04 and y0 >= 0.04 and x1 <= 0.96 and y1 <= 0.96, areas[chave])
                self.assertGreater(max(x1 - x0, y1 - y0), 0.82)

    def test_os_nomes(self):
        foto = fotos_estudio.ITENS[0][2][1]  # o Quadrinhos em 3/4 (frente.webp)
        nome = fotos_estudio.nome_no_cadastro(foto)
        self.assertRegex(nome, r"^estudio-basquete-street-quadrinhos-frente-[0-9a-f]{10}\.webp$")
        self.assertTrue(fotos_estudio.e_de_estudio(G + nome.replace(".webp", "_ab12cd.webp"), foto))
        for antes in ("basquete-street-quadrinhos-frente_trxwbl.png", "basquete-street-quadrinhos-frente-v2_mmxory",
                      "basquete-street-quadrinhos-frente"):
            self.assertTrue(fotos_estudio.e_a_de_antes(G + antes, foto), antes)
        for outra in ("basquete-street-quadrinhos-frente_2_mmxory", "foto-da-equipe_x1y2z3", "basquete-street-quadrinhos-verso"):
            self.assertFalse(fotos_estudio.e_a_de_antes(G + outra, foto), outra)
        capa = fotos_estudio.ITENS[1][2][0]  # a capa do catálogo do Basquete Home (o azul)
        self.assertTrue(fotos_estudio.e_a_de_antes(G + "cena-basquete-home-0123456789_abcdef.webp", capa))
        self.assertTrue(fotos_estudio.nome_no_cadastro(capa).startswith("estudio-catalogo-basquete-home-"))


class _ComDisco(TestCase):
    """As fotos num disco temporário (o Cloudinary dos testes)."""

    def setUp(self):
        cache.clear()
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.disco = FileSystemStorage(location=pasta.name, base_url="/media/")
        for campo in (Brinquedos._meta.get_field("imagem_brinquedo"), ImagemBrinquedo._meta.get_field("imagem")):
            troca = mock.patch.object(campo, "storage", self.disco)
            troca.start()
            self.addCleanup(troca.stop)

    def produto(self, nome, capa):
        brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=Decimal("5.00"),
                                              voltz="", imagem_brinquedo=G + capa)
        ImagemBrinquedo.objects.create(brinquedo=brinquedo, variante=brinquedo.adesivo_padrao, tipo="perfil", ordem=1,
                                       imagem=G + capa, papel_na_capa="cena")
        brinquedo.refresh_from_db()
        return brinquedo

    def foto(self, brinquedo, variante, tipo, nome, ordem=2, papel=""):
        return ImagemBrinquedo.objects.create(brinquedo=brinquedo, variante=variante, tipo=tipo, ordem=ordem,
                                              imagem=G + nome, papel_na_capa=papel)

    def estado(self):
        return sorted(ImagemBrinquedo.objects.values_list("id", "variante_id", "tipo", "papel_na_capa", "imagem"))

    def subidas(self):
        return sorted(p.name for p in self.pasta.rglob("*") if p.is_file())

    def no_render(self):
        with override_settings(IS_RENDER=True):
            migracao.subir(apps_reais, None)


class BasqueteHomeTests(_ComDisco):
    """O Basquete Home no ar: o Azul (o padrão) com a capa em cena do catálogo; o Quadrinhos com as vistas do 3D."""

    def setUp(self):
        super().setUp()
        self.home = self.produto("Basquete Home", "cena-basquete-home-56aeb3d2d5_epknbl")
        self.azul = self.home.adesivo_padrao
        VarianteAdesivo.objects.filter(pk=self.azul.pk).update(nome="Azul", slug="azul")
        self.da_fabrica = self.foto(self.home, self.azul, "lado_direito", "basquetehome_lado_s1antg", 3)
        self.quadrinhos = VarianteAdesivo.objects.create(brinquedo=self.home, nome="Quadrinhos", slug="quadrinhos", ordem=2)
        q = "basquete-street-quadrinhos-"
        self.foto(self.home, self.quadrinhos, "perfil", "capa-basquete-street-quadrinhos-0123456789_abcdef", 1, "cena")
        self.foto(self.home, self.quadrinhos, "tres_quartos", q + "frente_trxwbl", 4)
        self.foto(self.home, self.quadrinhos, "lado_direito", q + "lado_direito-v2_mmxory", 5)
        self.foto(self.home, self.quadrinhos, None, q + "lado_direito_aaaaaa", 6)  # (a v1, guardada)
        self.foto(self.home, self.quadrinhos, "lado_esquerdo", q + "lado_esquerdo_bbbbbb", 7)
        self.foto(self.home, self.quadrinhos, "verso", q + "verso_cccccc", 8)
        self.foto(self.home, self.quadrinhos, None, q + "jogador_dddddd", 9)

    @override_settings(IS_RENDER=False)
    def test_fora_do_render_nada_muda(self):
        estado = self.estado()
        migracao.subir(apps_reais, None)
        self.assertEqual(self.estado(), estado)
        self.assertEqual(self.subidas(), [])

    def test_no_render_as_fotos_de_estudio_entram_nas_posicoes(self):
        self.no_render()
        fotos = list(ImagemBrinquedo.objects.filter(brinquedo=self.home))
        galeria = galeria_publica(fotos, self.azul.pk, adesivo_id=self.quadrinhos.pk)
        self.assertEqual([f.tipo for f in galeria],
                         ["perfil", "tres_quartos", "lado_direito", "lado_esquerdo", "verso", "de_cima"])
        for foto in galeria:
            self.assertIn("estudio-basquete-street-quadrinhos-", foto.imagem.name)
            self.assertEqual(foto.fundo, "com")
        self.assertEqual(galeria[0].papel_na_capa, "cena")
        # o detalhe de quem joga entrou "de cima"; o arquivo é o do estúdio
        with open(self.pasta / galeria[5].imagem.name, "rb") as subiu:
            self.assertEqual(subiu.read(), (RAIZ / "core/static/site/arena/modelos/basquete-street-quadrinhos/jogador.webp").read_bytes())
        # as de antes ficaram guardadas no adesivo, fora da galeria
        guardadas = ImagemBrinquedo.objects.filter(variante=self.quadrinhos, tipo=None)
        self.assertEqual(guardadas.count(), 7)
        self.assertFalse(guardadas.filter(papel_na_capa="cena").exists())
        # o Azul (o padrão): a capa do produto é a foto da fábrica no estúdio; as fotos da fábrica ficam
        self.home.refresh_from_db()
        capa = galeria_publica(fotos, self.azul.pk)[0]
        self.assertIn("estudio-catalogo-basquete-home-", capa.imagem.name)
        self.assertEqual(self.home.imagem_brinquedo.name, capa.imagem.name)
        self.assertEqual(galeria_publica(fotos, self.azul.pk)[1].pk, self.da_fabrica.pk)

    def test_rodar_de_novo_nao_sobe_nada_e_a_foto_refeita_sobe(self):
        self.no_render()
        estado, subidas = self.estado(), self.subidas()
        self.no_render()
        self.assertEqual(self.estado(), estado)
        self.assertEqual(self.subidas(), subidas)
        # o estúdio refez a vista (outra assinatura): só ela sobe, na mesma linha
        frente = ImagemBrinquedo.objects.get(variante=self.quadrinhos, tipo="tres_quartos")
        with mock.patch.object(fotos_estudio, "assinatura", lambda foto: "f" * 10 if foto["arquivo"].endswith(
                "quadrinhos/frente.webp") else fotos_estudio.hashlib.sha1(fotos_estudio.caminho(foto).read_bytes()).hexdigest()[:10]):
            self.no_render()
        frente.refresh_from_db()
        self.assertIn("estudio-basquete-street-quadrinhos-frente-ffffffffff", frente.imagem.name)
        self.assertEqual(len(self.subidas()), len(subidas) + 1)

    def test_a_volta_poe_tudo_como_estava(self):
        estado = self.estado()
        capa = self.home.imagem_brinquedo.name
        self.no_render()
        migracao.voltar(apps_reais, None)
        depois = self.estado()
        self.assertEqual([linha[1:] for linha in depois], [linha[1:] for linha in estado])
        self.home.refresh_from_db()
        self.assertEqual(self.home.imagem_brinquedo.name, capa)

    def test_a_foto_da_equipe_fica(self):
        ImagemBrinquedo.objects.filter(variante=self.quadrinhos, tipo="verso").update(imagem=G + "foto-da-equipe_x1y2z3")
        saida = StringIO()
        with override_settings(IS_RENDER=True):
            call_command("fotos_de_estudio", "--so", "Basquete Home (Quadrinhos)", stdout=saida)
        self.assertIn("a foto foi trocada no painel (foto-da-equipe_x1y2z3); fica como está", saida.getvalue())
        self.assertEqual(ImagemBrinquedo.objects.get(variante=self.quadrinhos, tipo="verso").imagem.name,
                         G + "foto-da-equipe_x1y2z3")
        # o Azul não foi pedido: ficou como estava
        self.assertFalse(ImagemBrinquedo.objects.filter(variante=self.azul, imagem__contains="estudio-").exists())

    def test_a_subida_que_falha_nao_derruba_o_deploy(self):
        avisos = []
        with override_settings(IS_RENDER=True), \
                mock.patch.object(fotos_estudio, "_subir", side_effect=RuntimeError("Cloudinary fora")):
            fotos_estudio.no_deploy(apps_reais, None, avisar=avisos.append)
        self.assertTrue(any("não foi feito agora" in a and "fotos_de_estudio" in a for a in avisos))
        # nada ficou pela metade: a de antes continua na posição
        self.assertTrue(ImagemBrinquedo.objects.filter(variante=self.quadrinhos, tipo="tres_quartos",
                                                       imagem__contains="quadrinhos-frente_trxwbl").exists())


class StrikeKidsTests(_ComDisco):
    """O Strike Kids no ar: a capa do cadastro e as vistas; o 3/4 e o de cima guardados, sem posição."""

    def setUp(self):
        super().setUp()
        self.strike = self.produto("Strike Kids", "strike-kids-capa_t12zew")
        self.padrao = self.strike.adesivo_padrao
        for ordem, (tipo, nome) in enumerate((("lado_direito", "lado_direito"), ("lado_esquerdo", "lado_esquerdo"),
                                              ("verso", "verso"), (None, "tres_quartos_esquerda"), (None, "de_cima"),
                                              (None, "frente")), start=2):
            self.foto(self.strike, self.padrao, tipo, f"strike-kids-{nome}_abc{ordem:03d}", ordem)

    def test_as_posicoes_novas_e_a_volta(self):
        estado = self.estado()
        self.no_render()
        galeria = galeria_publica(list(ImagemBrinquedo.objects.filter(brinquedo=self.strike)), self.padrao.pk)
        self.assertEqual([f.tipo for f in galeria],
                         ["perfil", "tres_quartos", "lado_direito", "lado_esquerdo", "verso", "de_cima"])
        self.assertIn("estudio-strike-kids-tres_quartos_esquerda-", galeria[1].imagem.name)
        self.assertIn("estudio-strike-kids-de_cima-", galeria[5].imagem.name)
        self.strike.refresh_from_db()
        self.assertIn("estudio-strike-kids-capa-", self.strike.imagem_brinquedo.name)
        migracao.voltar(apps_reais, None)
        # as guardadas de antes continuam sem posição (as posições eram novas)
        self.assertEqual([linha[1:] for linha in self.estado()], [linha[1:] for linha in estado])
        self.strike.refresh_from_db()
        self.assertEqual(self.strike.imagem_brinquedo.name, G + "strike-kids-capa_t12zew")


class SemOsProdutosTests(_ComDisco):
    def test_sem_os_produtos_avisa_e_segue(self):
        avisos = []
        with override_settings(IS_RENDER=True):
            feito = fotos_estudio.no_deploy(apps_reais, None, avisar=avisos.append)
        self.assertIn("Strike Kids: não está no catálogo.", avisos)
        self.assertTrue(feito)
        self.assertFalse(ImagemBrinquedo.objects.exists())
