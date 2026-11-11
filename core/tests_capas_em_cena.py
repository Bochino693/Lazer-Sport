"""As capas em cena dos nossos produtos em 3D e o card das peças da home (a 0153).

O cliente: "as fotos nas categorias devem ficar full ali, sem as bordas
brancas... projete alguma coisa também para as peças de reposição da
primeira posição, para não ficar brancão também". O que estes testes
protegem:

  * a CAPA de cada produto nosso em 3D (o card de produto e a primeira da
    galeria) é a cena: capa.webp, a primeira foto do cadastro, tipo
    "perfil", quadrada (o card é quadrado), opaca (o card a mostra cheia),
    com cor e leve; a vista que era a capa fica na galeria, sem tipo -- e
    nenhum cadastro repete um tipo (a restrição única brinquedo + tipo);
  * o Brinquedão Modelo 5 tem de capa a foto do salão da fábrica, e o
    Modelo 4 fica como estava;
  * cada capa só tem máquina de verdade: o produto (o .glb nosso) e, ao
    fundo, produtos do catálogo;
  * o card fixo "Peças e acessórios" da home é a foto das peças de verdade
    do catálogo, de ponta a ponta (sem o carrossel de antes);
  * a 0153 refaz, só no Render, a galeria que o cadastro subiu (uma vez), e
    nunca derruba o deploy;
  * a 0154 (o 3D novo do Basquete Street Quadrinhos e do Air Game Kids
    Alienígenas, seção 61): no Render, refaz à força a galeria dos dois que o
    cadastro subiu (mesmo com a capa em cena da 0153) e sobe as fotos das
    categorias que mudaram; em todo lugar, religa o objeto 3D ao .glb de
    hoje; nunca derruba o deploy.
"""

import importlib
import json
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.apps import apps as apps_reais
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image, ImageStat

from . import categorias_capas
from .cadastro_modelos import CADASTROS
from .models import Brinquedos, ImagemBrinquedo, ObjetoTresD, PecasReposicao
from .objetos_3d import ler_glb_do_site

migracao = importlib.import_module("core.migrations.0153_capas_em_cena")
migracao_0154 = importlib.import_module("core.migrations.0154_basquete_e_air_game_reais")

FERRAMENTA = Path(__file__).resolve().parent.parent / "ferramentas" / "categorias"
#: Os produtos com a capa em cena (o Modelo 5 tem a do salão da fábrica).
EM_CENA = tuple(chave for chave in migracao.CHAVES if chave != "brinquedao-modelo-5")


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    storage = FileSystemStorage(location=pasta)
    return (
        mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage),
        mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage),
    )


class CapasTests(TestCase):
    """A capa de cada produto é a cena, e o cadastro continua valendo."""

    def test_a_capa_e_a_primeira_foto_do_cadastro(self):
        for chave in EM_CENA:
            with self.subTest(chave):
                arquivo, tipo, texto = CADASTROS[chave]["fotos"][0]
                self.assertEqual((arquivo, tipo), ("capa.webp", "perfil"))
                self.assertTrue(texto.startswith(CADASTROS[chave]["nome"]))
        # o Modelo 5: a foto do salão da fábrica; o Modelo 4 fica como estava
        self.assertEqual(CADASTROS["brinquedao-modelo-5"]["fotos"][0][:2], ("salao_frente.webp", "perfil"))
        self.assertEqual(CADASTROS["brinquedao-modelo-4"]["fotos"][0][:2], ("perspectiva.webp", "perfil"))

    def test_a_capa_de_antes_fica_na_galeria_sem_tipo(self):
        for chave in EM_CENA:
            with self.subTest(chave):
                fotos = CADASTROS[chave]["fotos"]
                antes = "foto.webp" if chave == "strike-kids" else "frente.webp"
                self.assertEqual([tipo for arquivo, tipo, _ in fotos if arquivo == antes], [None])
        fotos = CADASTROS["brinquedao-modelo-5"]["fotos"]
        self.assertEqual([tipo for arquivo, tipo, _ in fotos if arquivo == "perspectiva.webp"], [None])

    def test_nenhum_cadastro_repete_um_tipo(self):
        # ImagemBrinquedo: um tipo por brinquedo (a restrição única brinquedo + tipo)
        for chave, dados in CADASTROS.items():
            with self.subTest(chave):
                tipos = [tipo for _, tipo, _ in dados["fotos"] if tipo]
                self.assertEqual(len(tipos), len(set(tipos)))
                self.assertEqual(dados["fotos"][0][1], "perfil")
                arquivos = [arquivo for arquivo, _, _ in dados["fotos"]]
                self.assertEqual(len(arquivos), len(set(arquivos)))

    def test_a_capa_e_quadrada_cheia_e_leve(self):
        for chave in EM_CENA:
            arquivo = CADASTROS[chave]["pasta"] / "capa.webp"
            with self.subTest(chave), Image.open(arquivo) as foto:
                self.assertEqual(foto.format, "WEBP")
                # o card de produto é quadrado; a galeria também, no computador
                self.assertEqual(foto.size, (1200, 1200))
                # opaca: o card a mostra cheia, de ponta a ponta (ls-fotos.js, `foto-cheia`)
                self.assertNotIn("A", foto.getbands())
                self.assertLessEqual(arquivo.stat().st_size, 190 * 1024)
                rgb = foto.convert("RGB")
                # "para não ficar brancão": cor, quase nada de branco estourado, nem escura demais
                self.assertGreater(ImageStat.Stat(rgb.convert("HSV").getchannel("S")).mean[0], 50)
                brancos = sum(1 for p in rgb.resize((120, 120)).getdata() if min(p) > 235)
                self.assertLess(brancos / (120 * 120), 0.12)
                self.assertGreater(ImageStat.Stat(rgb.convert("L")).mean[0], 70)
                # o estático do site serve a capa (é dela que o cadastro sobe a foto)
                self.assertTrue(finders.find(f"site/arena/modelos/{chave}/capa.webp"))

    def test_cada_capa_so_tem_maquina_de_verdade(self):
        # a lista de cada capa (o gerar.cjs grava): o produto, o .glb nosso, e ao fundo
        # só produtos do catálogo do site no ar (recortar.py --catalogo)
        lista = json.loads((FERRAMENTA / "maquinas-das-capas.json").read_text(encoding="utf-8"))
        catalogo = json.loads((FERRAMENTA / "maquinas" / "catalogo.json").read_text(encoding="utf-8"))
        self.assertEqual(set(lista), set(EM_CENA))
        for chave, maquinas in lista.items():
            with self.subTest(chave):
                self.assertEqual(maquinas[0], CADASTROS[chave]["nome"] + " (3D)")
                for maquina in maquinas[1:]:
                    self.assertTrue(maquina.endswith(" (ao fundo)"), maquina)
                    self.assertIn(maquina.replace(" (ao fundo)", ""), catalogo, f"{maquina} não é do catálogo")

    def test_a_ferramenta_refaz_so_as_cenas_de_um_glb(self):
        # quando um .glb é refeito: node ferramentas/categorias/gerar.cjs --glb <nome> --compor
        self.assertIn("window.cenasComGlb", (FERRAMENTA / "cenas.js").read_text(encoding="utf-8"))
        gerar = (FERRAMENTA / "gerar.cjs").read_text(encoding="utf-8")
        self.assertIn('"--glb"', gerar)
        self.assertIn("compor.py", gerar)


class PecasDaHomeTests(TestCase):
    """O card fixo "Peças e acessórios": as peças de verdade, de ponta a ponta."""

    ARQUIVO = Path(__file__).resolve().parent / "static" / "site" / "categorias" / "pecas-e-acessorios.webp"

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_a_foto_tem_o_corte_do_card_e_cor(self):
        with Image.open(self.ARQUIVO) as foto:
            self.assertEqual(foto.size, (1200, 900))
            self.assertLessEqual(self.ARQUIVO.stat().st_size, 150 * 1024)
            rgb = foto.convert("RGB")
            self.assertGreater(ImageStat.Stat(rgb.convert("HSV").getchannel("S")).mean[0], 50)
            brancos = sum(1 for p in rgb.resize((120, 90)).getdata() if min(p) > 235)
            self.assertLess(brancos / (120 * 90), 0.12)

    def test_so_tem_pecas_de_verdade_do_catalogo(self):
        # a lista da foto (o gerar.cjs grava) contra as peças do site no ar (recortar.py --pecas)
        lista = json.loads((FERRAMENTA / "maquinas-das-fotos.json").read_text(encoding="utf-8"))["pecas-e-acessorios"]
        catalogo = json.loads((FERRAMENTA / "reposicao" / "catalogo.json").read_text(encoding="utf-8"))
        ficha = json.loads((FERRAMENTA / "reposicao" / "pecas.json").read_text(encoding="utf-8"))
        na_frente = [p for p in lista if not p.endswith("(ao fundo)")]
        self.assertGreaterEqual(len(set(na_frente)), 4)
        for peca in lista:
            with self.subTest(peca):
                self.assertIn(peca.replace(" (ao fundo)", "").replace(" (peça)", ""), catalogo)
        for chave, dados in ficha.items():
            with self.subTest(chave), Image.open(FERRAMENTA / "reposicao" / f"{chave}.webp") as foto:
                self.assertEqual(catalogo[dados["nome"]]["id"], dados["id"])
                self.assertEqual(foto.mode, "RGBA")  # recortada: o fundo é transparente

    def test_o_card_mostra_a_foto_de_ponta_a_ponta(self):
        PecasReposicao.objects.create(nome="Cabo HDMI", descricao_peca="x", preco_venda=Decimal("10.00"))
        html = self.client.get(reverse("home")).content.decode()
        inicio = html.index("categoria-link-featured")
        card = html[inicio:html.index("</a>", inicio)]
        self.assertIn("categoria-media categoria-media--cheia", card)
        self.assertIn("site/categorias/pecas-e-acessorios", card)
        self.assertIn("Peças e acessórios", card)
        # o carrossel de antes (as fotos das peças no fundo branco) saiu
        self.assertNotIn("pecasSlider", html)
        self.assertNotIn("peca-slide", html)


@override_settings(IS_RENDER=False)
class MigracaoTests(TestCase):
    """A 0153: no Render, a galeria que o cadastro subiu ganha a capa em cena, uma vez."""

    def _do_cadastro(self, chave, capa="frente"):
        """Como o cadastro deixou (antes da 0153): as fotos dele, com a capa de antes."""
        dados = CADASTROS[chave]
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo=dados["nome"], descricao="x", avaliacao=5, voltz="220v",
            imagem_brinquedo=f"imagens_brinquedos/{chave}-{capa}.webp",
        )
        for ordem, tipo in enumerate(("perfil", "lado_esquerdo"), start=1):
            ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo=tipo, ordem=ordem, texto_alternativo="antes",
                                           imagem=f"imagens_brinquedos/{chave}-{ordem}.webp")
        return brinquedo

    def _rodar(self, pasta=None, render=True):
        avisos = []
        if render:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True):
                migracao.refazer(apps_reais, None, avisar=avisos.append)
        else:
            migracao.refazer(apps_reais, None, avisar=avisos.append)
        return " ".join(avisos)

    def test_vem_depois_da_0152(self):
        self.assertEqual(migracao.Migration.dependencies, [("core", "0152_categorias_maquinas_reais")])
        self.assertIs(migracao.Migration.operations[0].code, migracao.refazer)
        self.assertEqual(set(migracao.CHAVES), set(EM_CENA) | {"brinquedao-modelo-5"})

    def test_fora_do_render_nao_mexe(self):
        brinquedo = self._do_cadastro("brinquedao-ninja")
        self.assertEqual(self._rodar(render=False), "")
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 2)
        self.assertIn("brinquedao-ninja-frente", brinquedo.imagem_brinquedo.name)

    def test_no_render_a_galeria_do_cadastro_ganha_a_capa(self):
        ninja = self._do_cadastro("brinquedao-ninja")
        strike = self._do_cadastro("strike-kids", capa="foto")
        modelo5 = self._do_cadastro("brinquedao-modelo-5", capa="perspectiva")
        with tempfile.TemporaryDirectory() as pasta:
            avisos = self._rodar(pasta)
        for brinquedo, chave in ((ninja, "brinquedao-ninja"), (strike, "strike-kids"), (modelo5, "brinquedao-modelo-5")):
            with self.subTest(chave):
                brinquedo.refresh_from_db()
                capa = Path(CADASTROS[chave]["fotos"][0][0]).stem
                self.assertIn(f"{chave}-{capa}", brinquedo.imagem_brinquedo.name)
                fotos = list(brinquedo.imagens_brinquedo.order_by("ordem"))
                self.assertEqual([f.tipo for f in fotos], [tipo for _, tipo, _ in CADASTROS[chave]["fotos"]])
                self.assertIn(f"{chave}-{capa}", fotos[0].imagem.name)
                self.assertIn(CADASTROS[chave]["nome"], avisos)
        # o produto continua o mesmo (só a galeria muda) e nada é duplicado
        self.assertEqual(Brinquedos.objects.count(), 3)

    def test_uma_vez_so(self):
        ninja = self._do_cadastro("brinquedao-ninja")
        with tempfile.TemporaryDirectory() as pasta:
            self._rodar(pasta)
            with mock.patch.object(FileSystemStorage, "save", side_effect=AssertionError("subiu de novo")):
                self.assertEqual(self._rodar(pasta), "")
        ninja.refresh_from_db()
        self.assertIn("brinquedao-ninja-capa", ninja.imagem_brinquedo.name)

    def test_as_fotos_do_painel_ficam(self):
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Brinquedão Ninja", descricao="x", avaliacao=5, imagem_brinquedo="imagens_brinquedos/minha-foto.webp",
        )
        with tempfile.TemporaryDirectory() as pasta:
            self.assertEqual(self._rodar(pasta), "")
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, "imagens_brinquedos/minha-foto.webp")

    def test_fora_do_catalogo_nao_cadastra(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.assertEqual(self._rodar(pasta), "")
        self.assertFalse(Brinquedos.objects.exists())

    def test_a_subida_falha_e_o_deploy_segue(self):
        ninja = self._do_cadastro("brinquedao-ninja")
        trampolim = self._do_cadastro("trampolim-enterrada")
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            avisos = self._rodar(pasta)
        self.assertIn("python manage.py cadastrar_modelo_3d brinquedao-ninja --fotos", avisos)
        self.assertIn("python manage.py cadastrar_modelo_3d trampolim-enterrada --fotos", avisos)
        # nada pela metade: a galeria de antes fica até o comando refazer
        for brinquedo, chave in ((ninja, "brinquedao-ninja"), (trampolim, "trampolim-enterrada")):
            brinquedo.refresh_from_db()
            self.assertEqual(brinquedo.imagens_brinquedo.count(), 2)
            self.assertIn(f"{chave}-frente", brinquedo.imagem_brinquedo.name)


@override_settings(IS_RENDER=False)
class BasqueteEAirGameReaisTests(TestCase):
    """A 0154: o 3D novo dos dois (seção 61) no site -- as fotos, o objeto e as fotos das categorias."""

    def _do_cadastro(self, chave, capa="capa"):
        """Como a 0153 deixou: as fotos que o cadastro subiu, com a capa em cena (do 3D de antes)."""
        dados = CADASTROS[chave]
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo=dados["nome"], descricao="x", avaliacao=5, voltz="220v",
            imagem_brinquedo=f"imagens_brinquedos/{chave}-{capa}.webp",
        )
        for ordem, (arquivo, tipo, _texto) in enumerate(dados["fotos"], start=1):
            ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo=tipo, ordem=ordem, texto_alternativo="do 3D de antes",
                                           imagem=f"imagens_brinquedos/{chave}-{Path(arquivo).stem}-antes.webp")
        ObjetoTresD.objects.create(brinquedo=brinquedo, arquivo_estatico=dados["objeto_3d"], codigo=chave,
                                   medidas=[1.0, 1.0, 1.0], cores=[])
        return brinquedo

    def _rodar(self, pasta=None, render=True):
        avisos = []
        with mock.patch.object(categorias_capas, "subir_fotos_no_deploy") as categorias, mock.patch("builtins.print"):
            if render:
                a, b = _disco(pasta)
                with a, b, override_settings(IS_RENDER=True):
                    migracao_0154.refazer(apps_reais, None, avisar=avisos.append)
            else:
                migracao_0154.refazer(apps_reais, None, avisar=avisos.append)
        return " ".join(avisos), categorias

    def test_vem_depois_da_0153(self):
        self.assertEqual(migracao_0154.Migration.dependencies, [("core", "0153_capas_em_cena")])
        self.assertIs(migracao_0154.Migration.operations[0].code, migracao_0154.refazer)
        self.assertEqual(set(migracao_0154.CHAVES), {"basquete-street-quadrinhos", "air-game-kids-alienigenas"})

    def test_fora_do_render_so_religa_o_3d(self):
        brinquedos = {chave: self._do_cadastro(chave) for chave in migracao_0154.CHAVES}
        avisos, categorias = self._rodar(render=False)
        self.assertEqual(avisos, "")
        categorias.assert_not_called()
        for chave, brinquedo in brinquedos.items():
            with self.subTest(chave):
                self.assertTrue(all("antes" in f.imagem.name for f in brinquedo.imagens_brinquedo.all()))
                objeto = ObjetoTresD.objects.get(brinquedo=brinquedo)
                # as medidas e as cores do .glb de hoje
                lido = ler_glb_do_site(CADASTROS[chave]["objeto_3d"])
                self.assertEqual((objeto.medidas, objeto.cores), (lido["medidas"], lido["cores"]))

    def test_no_render_refaz_a_forca_mesmo_com_a_capa_da_0153(self):
        brinquedos = {chave: self._do_cadastro(chave) for chave in migracao_0154.CHAVES}
        with tempfile.TemporaryDirectory() as pasta:
            avisos, categorias = self._rodar(pasta)
            for chave, brinquedo in brinquedos.items():
                with self.subTest(chave):
                    brinquedo.refresh_from_db()
                    fotos = list(brinquedo.imagens_brinquedo.order_by("ordem"))
                    dados = CADASTROS[chave]
                    self.assertEqual([f.tipo for f in fotos], [tipo for _, tipo, _ in dados["fotos"]])
                    self.assertEqual([f.texto_alternativo for f in fotos], [texto for _, _, texto in dados["fotos"]])
                    self.assertFalse(any("antes" in f.imagem.name for f in fotos))
                    self.assertIn(f"{chave}-capa", brinquedo.imagem_brinquedo.name)
                    # o arquivo que subiu é a capa de hoje (a do 3D novo)
                    with open(Path(pasta) / brinquedo.imagem_brinquedo.name, "rb") as subiu, \
                            open(dados["pasta"] / "capa.webp", "rb") as de_hoje:
                        self.assertEqual(subiu.read(), de_hoje.read())
                    self.assertIn(dados["nome"], avisos)
        # as fotos das categorias com estes .glb também sobem (só as que mudaram)
        categorias.assert_called_once()
        self.assertEqual(Brinquedos.objects.count(), 2)

    def test_as_fotos_do_painel_ficam(self):
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo=CADASTROS["air-game-kids-alienigenas"]["nome"], descricao="x", avaliacao=5,
            imagem_brinquedo="imagens_brinquedos/foto-da-loja.webp",
        )
        with tempfile.TemporaryDirectory() as pasta:
            self.assertEqual(self._rodar(pasta)[0], "")
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, "imagens_brinquedos/foto-da-loja.webp")
        # o objeto 3D é ligado mesmo assim (o .glb de hoje)
        self.assertEqual(brinquedo.objeto_3d.codigo, "air-game-kids-alienigenas")

    def test_a_subida_falha_e_o_deploy_segue(self):
        basquete = self._do_cadastro("basquete-street-quadrinhos")
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            avisos, categorias = self._rodar(pasta)
        self.assertIn("python manage.py cadastrar_variantes_adesivo --so basquete-street-quadrinhos --fotos", avisos)
        # nada pela metade: a galeria de antes fica até o comando refazer; o 3D e as categorias seguem
        basquete.refresh_from_db()
        self.assertTrue(all("antes" in f.imagem.name for f in basquete.imagens_brinquedo.all()))
        lido = ler_glb_do_site(CADASTROS["basquete-street-quadrinhos"]["objeto_3d"])
        self.assertEqual(basquete.objeto_3d.medidas, lido["medidas"])
        categorias.assert_called_once()

    def test_as_fotos_com_estes_glb_sao_as_que_o_gerar_refaz(self):
        # gerar.cjs --glb basquete-street-quadrinhos --glb air-game-kids-alienigenas refaz as capas
        # dos dois e as fotos das categorias onde eles aparecem -- e só estas sobem na 0154
        lista = json.loads((FERRAMENTA / "maquinas-das-fotos.json").read_text(encoding="utf-8"))
        com_os_dois = {chave for chave, maquinas in lista.items()
                       if {"Basquete Street Quadrinhos (3D)", "Air Game Kids Alienígenas (3D)"} & set(maquinas)}
        self.assertEqual(com_os_dois, {"espaco-kids-play", "eletronicos", "jogos-de-mesa", "competitivos", "famosos",
                                       "esportivos", "kids"})
        capas = json.loads((FERRAMENTA / "maquinas-das-capas.json").read_text(encoding="utf-8"))
        for chave in migracao_0154.CHAVES:
            self.assertEqual(capas[chave][0], CADASTROS[chave]["nome"] + " (3D)")
