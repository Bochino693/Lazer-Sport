"""As máquinas da Black Friday no showroom (a seção 78 do LEIA-ME).

O cliente, com o print do card do Basquete Kids (a máquina no fundo de neon
vermelho do cartaz): "identifique as máquinas com o fundo vermelho e ponha
elas no padrão"; e, com o do Air Rock (a panorâmica cortada no card): "valide
para não ter fotos assim com zoom pois estraga". O que estes testes protegem:

  * as fotos novas (core/static/site/capas_catalogo/<chave>.webp): quadradas,
    1600 x 1600, opacas, leves, com a máquina inteira e folga em volta, e a
    BORDA SEM O VERMELHO (medida: a fração de pixels vermelhos no anel de
    fora, que nas fotos de antes passava de 50%);
  * os recortes guardados para as artes (transparentes, sem a franja do neon
    na borda) e que o site não usa em lugar nenhum;
  * a foto da categoria "Casinhas Cenográficas" num lugar de verdade (4:3);
  * o mecanismo (core/capas_catalogo.py, VERMELHAS; o comando capas_em_cena
    --vermelhas; a migração 0180): a cena vira a capa, o recorte do cartaz fica
    guardado mas NUNCA aparece na galeria pública, nos cards, nas fotos que
    giram nem na página; rodar de novo não muda nada; a foto trocada no painel
    fica; o --desfazer volta; o deploy não cai;
  * a Black Friday rodada do zero já cria os produtos com a cena.
"""

import colorsys
import datetime
import importlib
import json
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
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image, ImageChops, ImageFilter

from . import black_friday, capas_catalogo, categorias_capas, fotos_dos_cards
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, Promocoes, galeria_publica

migracao_0180 = importlib.import_module("core.migrations.0180_maquinas_vermelhas_no_showroom")

RAIZ = Path(__file__).resolve().parent.parent
FERRAMENTA = RAIZ / "ferramentas" / "categorias"
CARTAZ = Path(__file__).resolve().parent / "static" / "site" / "black_friday"
RECORTES = CARTAZ / "recortes"
#: As do fundo de neon vermelho (as outras duas eram panorâmicas).
NO_NEON = ("basquete-duplo", "basquete-kids", "cozinha-infantil", "oficina-de-engenharia", "salao-de-beleza")
#: A foto de antes de cada uma (o recorte do cartaz, em core/static/site/black_friday/).
DE_ANTES = {
    "basquete-duplo": "produto-basquete-duplo.webp", "basquete-kids": "produto-basquete-kids.webp",
    "cozinha-infantil": "produto-cozinha-infantil.webp", "oficina-de-engenharia": "produto-oficina-de-engenharia.webp",
    "salao-de-beleza": "produto-salao-de-beleza.webp", "air-rock": "produto-air-rock.webp", "kid-play": "produto-kid-play.webp",
}


def vermelho_na_borda(caminho, anel=0.06):
    """A fração dos pixels VERMELHOS no anel de fora da foto (o tom até 15 graus do vermelho, com cor e luz)."""
    with Image.open(caminho) as foto:
        rgb = foto.convert("RGB")
    rgb.thumbnail((300, 300))
    w, h = rgb.size
    k = max(2, round(min(w, h) * anel))
    px = rgb.load()
    anel_px = [px[x, y] for y in range(h) for x in range(w) if x < k or y < k or x >= w - k or y >= h - k]

    def vermelho(p):
        tom, sat, luz = colorsys.rgb_to_hsv(*(c / 255 for c in p))
        return (tom <= 15 / 360 or tom >= 345 / 360) and sat >= 0.5 and luz >= 0.12

    return sum(1 for p in anel_px if vermelho(p)) / len(anel_px)


def franja_de_neon(caminho):
    """A fração da borda do recorte (o opaco encostado no transparente) que é o neon do fundo (vermelho escuro)."""
    with Image.open(caminho) as foto:
        im = foto.convert("RGBA")
    a = im.getchannel("A")
    borda = ImageChops.multiply(a.point(lambda v: 255 if v > 160 else 0),
                                a.point(lambda v: 255 if v < 40 else 0).filter(ImageFilter.MaxFilter(5)))
    pixels = [p for p, b in zip(im.convert("RGB").getdata(), borda.getdata()) if b]
    neon = sum(1 for r, g, b in pixels if 25 < r < 130 and g < 22 and b < 22)
    return neon / max(1, len(pixels))


class FotosTests(TestCase):
    def test_a_lista(self):
        self.assertEqual(sorted(item[0] for item in capas_catalogo.VERMELHAS), sorted(DE_ANTES))
        nomes_do_catalogo = {item[2] for item in capas_catalogo.LISTA}
        for chave, _i, nome, prefixo in capas_catalogo.VERMELHAS:
            self.assertNotIn(nome, nomes_do_catalogo)
            self.assertEqual(prefixo, f"black-friday-2026-produto-{chave}-")
            # o nome do arquivo que a Black Friday subiu começa assim (é por ele que o --desfazer acha a foto)
            self.assertTrue(black_friday._nome_do_arquivo(DE_ANTES[chave]).startswith(prefixo))
        # o Brinquedão Modelo 5 fica: a capa dele é a imagem da fábrica (seção 64)
        self.assertNotIn("Brinquedão Modelo 5", {item[2] for item in capas_catalogo.VERMELHAS})

    def test_as_fotos_de_antes_eram_vermelhas_ou_panoramicas(self):
        # a medida que achou as máquinas (o LEIA-ME 78 dá os números): a borda vermelha ou o formato de faixa
        for chave in NO_NEON:
            with self.subTest(chave):
                self.assertGreater(vermelho_na_borda(CARTAZ / DE_ANTES[chave]), 0.5)
        for chave in ("air-rock", "kid-play"):
            with self.subTest(chave), Image.open(CARTAZ / DE_ANTES[chave]) as foto:
                self.assertGreater(foto.width / foto.height, 2)

    def test_cada_foto_nova_e_quadrada_leve_inteira_e_sem_o_vermelho(self):
        areas = json.loads((FERRAMENTA / "areas-dos-produtos.json").read_text(encoding="utf-8"))
        lista = json.loads((FERRAMENTA / "maquinas-dos-produtos.json").read_text(encoding="utf-8"))
        ficha = json.loads((FERRAMENTA / "maquinas" / "maquinas.json").read_text(encoding="utf-8"))
        for chave, i, nome, _prefixo in capas_catalogo.VERMELHAS:
            with self.subTest(chave):
                arquivo = capas_catalogo.arquivo(chave)
                with Image.open(arquivo) as foto:
                    self.assertEqual(foto.format, "WEBP")
                    self.assertEqual(foto.size, (1600, 1600))  # o card é quadrado: nada de zoom
                    self.assertNotIn("A", foto.getbands())
                self.assertLessEqual(arquivo.stat().st_size, 250 * 1024)
                self.assertTrue(finders.find(f"site/capas_catalogo/{chave}.webp"))
                # o fundo é o showroom, e não o neon do cartaz
                self.assertLess(vermelho_na_borda(arquivo), 0.08)
                # a máquina inteira, com folga em volta (a caixa dela, em fração da foto)
                x0, y0, x1, y1 = areas[f"produto_{chave}"]
                self.assertTrue(x0 >= 0.03 and y0 >= 0.03 and x1 <= 0.97 and y1 <= 0.97, areas[f"produto_{chave}"])
                self.assertGreater(max(x1 - x0, y1 - y0), 0.6)  # e grande
                # a máquina é a de verdade (o recorte da foto dela), e nenhuma outra
                self.assertEqual(lista[chave], [nome])
                self.assertEqual((ficha[chave]["id"], ficha[chave]["nome"]), (i, nome))
                self.assertTrue((FERRAMENTA / "maquinas-alta" / f"{chave}.webp").exists())

    def test_cenas_variam_o_canto_do_showroom(self):
        codigo = (FERRAMENTA / "cenas.js").read_text(encoding="utf-8")
        inicio = codigo.index("const CATALOGO = {")
        catalogo = codigo[inicio:codigo.index("\n};\n", inicio)]
        cenarios = []
        for chave, *_ in capas_catalogo.VERMELHAS:
            linha = next(l for l in catalogo.splitlines() if l.strip().startswith(f'"{chave}":'))
            self.assertIn('...v("', linha)
            cenarios.append(linha.split('...v("')[1].split('"')[0])
        self.assertGreaterEqual(len(set(cenarios)), 4)  # a placa, as plantas, o fliperama, a vitrine

    def test_os_recortes_guardados_para_as_artes(self):
        for chave in DE_ANTES:
            with self.subTest(chave):
                arquivo = RECORTES / f"{chave}.webp"
                with Image.open(arquivo) as recorte:
                    self.assertEqual(recorte.mode, "RGBA")  # transparente: pronto para fazer arte
                    alfa = recorte.getchannel("A")
                    self.assertEqual(alfa.getextrema(), (0, 255))
                    w, h = recorte.size
                    self.assertEqual([alfa.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))], [0] * 4)
                # a borda limpa: nada do neon vermelho do fundo grudado na máquina
                self.assertLess(franja_de_neon(FERRAMENTA / "maquinas-alta" / f"{chave}.webp"), 0.12)

    def test_o_site_nao_mostra_os_recortes(self):
        for pasta in (RAIZ / "core" / "templates", RAIZ / "core" / "static" / "site"):
            for arquivo in pasta.rglob("*"):
                if arquivo.suffix in (".html", ".js", ".css"):
                    self.assertNotIn("black_friday/recortes", arquivo.read_text(encoding="utf-8", errors="ignore"), arquivo)

    def test_a_foto_da_categoria_das_casinhas(self):
        self.assertEqual(categorias_capas.chave_da_capa("Casinhas Cenográficas"), "casinhas-cenograficas")
        arquivo = categorias_capas.arquivo_da_capa("casinhas-cenograficas")
        with Image.open(arquivo) as foto:
            self.assertEqual(foto.size, (1600, 1200))  # o 4:3 do card de categoria
        self.assertLessEqual(arquivo.stat().st_size, 250 * 1024)
        # (a faixa vermelha do arco-íris pintado na parede da brinquedoteca conta um pouco: ~14%; a de
        # antes, o neon do cartaz, 76%) e o lugar é claro, e não o fundo escuro do cartaz
        self.assertLess(vermelho_na_borda(arquivo), 0.25)
        self.assertGreater(vermelho_na_borda(capas_catalogo.FOTO_DE_ANTES_DA_CATEGORIA), 0.5)
        with Image.open(arquivo) as foto:
            self.assertGreater(sum(foto.convert("L").resize((40, 30)).getdata()) / 1200, 120)
        # as três casinhas de verdade (os recortes delas), num lugar com crianças
        fotos = json.loads((FERRAMENTA / "maquinas-das-fotos.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(fotos["casinhas-cenograficas"]), ["Cozinha Infantil", "Oficina de Engenharia", "Salão de Beleza"])
        cenas = (FERRAMENTA / "cenas.js").read_text(encoding="utf-8")
        bloco = cenas[cenas.index('"casinhas-cenograficas": {'):]
        bloco = bloco[:bloco.index("\n  },")]
        self.assertIn('lugar: "brinquedoteca"', bloco)
        # as crianças na frente (naFrente: pelo lugar na tela, inteiras na foto)
        self.assertIn("naTela: naFrente([[", bloco)
        self.assertGreaterEqual(bloco.split("naTela: naFrente(")[1].split("\n")[0].count('"'), 6)


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    storage = FileSystemStorage(location=pasta)
    return [
        mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage),
        mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage),
        mock.patch.object(CategoriasBrinquedos._meta.get_field("imagem_categoria"), "storage", storage),
        mock.patch.object(Promocoes._meta.get_field("imagem_promocao"), "storage", storage),
        mock.patch.object(Promocoes._meta.get_field("arte_promocao"), "storage", storage),
    ]


def _como_no_ar(chave, nome, outra_foto=False, lado=True):
    """O produto como a Black Friday o cadastrou no site: a capa é o recorte do cartaz (no Cloudinary)."""
    capa = "imagens_brinquedos/galeria/outra_foto_da_equipe_x1y2" if outra_foto else \
        f"imagens_brinquedos/galeria/black-friday-2026-produto-{chave}-add77476_rat0p3"
    brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=Decimal("5.00"), voltz="220V",
                                          imagem_brinquedo=capa)
    ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="perfil", ordem=1, imagem=capa,
                                   texto_alternativo=f"{nome} da Lazer & Sport")
    if lado:
        # (uma vista que a equipe pôs: os cards giram as fotos de quem tem mais de uma)
        ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="lado_direito", ordem=2, imagem="imagens_brinquedos/lado.png")
    return brinquedo


class _ComDisco(TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.patches = _disco(self.pasta.name)
        for p in self.patches:
            p.start()
        cache.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.pasta.cleanup()
        cache.clear()

    def rodar(self, *argumentos):
        saida = StringIO()
        call_command("capas_em_cena", *argumentos, stdout=saida)
        return saida.getvalue()


@override_settings(IS_RENDER=False)
class ComandoTests(_ComDisco):
    def setUp(self):
        super().setUp()
        self.kids = _como_no_ar("basquete-kids", "Basquete Kids")
        self.vermelha = self.kids.imagem_brinquedo.name

    def _fotos(self, brinquedo):
        return [(f.tipo, f.papel_na_capa, Path(f.imagem.name).name.split("-")[0]) for f in brinquedo.imagens_brinquedo.order_by("ordem", "id")]

    def test_simular_nao_mexe(self):
        texto = self.rodar("--vermelhas", "--simular")
        self.assertIn("Basquete Kids: poria a capa em cena", texto)
        self.assertIn("Air Rock: não está no catálogo", texto)
        self.assertEqual(self.kids.imagens_brinquedo.count(), 2)
        self.assertFalse(ImagemBrinquedo.objects.filter(papel_na_capa="cena").exists())

    def test_a_cena_vira_a_capa_e_o_vermelho_sai_do_site(self):
        texto = self.rodar("--vermelhas")
        self.assertIn("Basquete Kids: a capa agora é a cena no showroom", texto)
        self.kids.refresh_from_db()
        fotos = list(self.kids.imagens_brinquedo.order_by("ordem", "id"))
        self.assertEqual([(f.tipo, f.papel_na_capa) for f in fotos], [("perfil", "cena"), ("lado_direito", ""), (None, "")])
        self.assertIn("cena-basquete-kids-", self.kids.imagem_brinquedo.name)
        with open(Path(self.pasta.name) / fotos[0].imagem.name, "rb") as subiu:
            self.assertEqual(subiu.read(), capas_catalogo.arquivo("basquete-kids").read_bytes())
        # o recorte do cartaz continua cadastrado (nada apagado)...
        self.assertEqual(fotos[2].imagem.name, self.vermelha)
        # ... mas não aparece em lugar nenhum do site: a capa (card, API, quadro do topo), a galeria
        # pública da página, as fotos que giram no card
        self.assertEqual(self.kids.imagem_catalogo.name, fotos[0].imagem.name)
        self.assertNotIn(self.vermelha, [f.imagem.name for f in self.kids.imagens_ordenadas])
        self.assertNotIn(self.vermelha, [f.imagem.name for f in galeria_publica(fotos)])
        fotos_dos_cards.limpar_cache()
        no_card = fotos_dos_cards.do_card(self.kids.pk)
        # (LEIA-ME 72: o card gira por adesivo; o Basquete Kids tem um só, e não gira)
        self.assertIsNone(no_card)
        self.assertFalse(any("black-friday-2026-produto" in item["src"] for item in no_card or []))
        pagina = self.client.get(reverse("brinquedo_detalhe", args=[self.kids.pk]))
        self.assertEqual(pagina.status_code, 200)
        self.assertNotIn("black-friday-2026-produto-basquete-kids", pagina.content.decode())
        self.assertIn("cena-basquete-kids-", pagina.content.decode())

    def test_rodar_de_novo_nao_muda_nada(self):
        self.rodar("--vermelhas")
        antes = self._fotos(self.kids)
        nomes = sorted(f.imagem.name for f in self.kids.imagens_brinquedo.all())
        self.assertIn("Basquete Kids: já está com a capa em cena", self.rodar("--vermelhas"))
        self.assertIn("já está com a capa em cena", self.rodar("--so", "59"))
        self.assertEqual(self._fotos(self.kids), antes)
        self.assertEqual(sorted(f.imagem.name for f in self.kids.imagens_brinquedo.all()), nomes)

    def test_a_foto_trocada_no_painel_fica(self):
        duplo = _como_no_ar("basquete-duplo", "Basquete Duplo", outra_foto=True)
        texto = self.rodar("--vermelhas")
        self.assertIn("Basquete Duplo: a capa foi trocada no painel", texto)
        duplo.refresh_from_db()
        self.assertEqual(duplo.imagem_brinquedo.name, "imagens_brinquedos/galeria/outra_foto_da_equipe_x1y2")
        self.assertFalse(duplo.imagens_brinquedo.filter(papel_na_capa="cena").exists())

    def test_sem_galeria_o_recorte_do_cartaz_fica_guardado(self):
        rock = Brinquedos.objects.create(nome_brinquedo="Air Rock", descricao="x", avaliacao=5,
                                         imagem_brinquedo="imagens_brinquedos/black-friday-2026-produto-air-rock-8cf5a03f_cbfpzb")
        self.rodar("--so", "Air Rock")
        fotos = list(rock.imagens_brinquedo.order_by("ordem", "id"))
        self.assertEqual([(f.tipo, f.papel_na_capa) for f in fotos], [("perfil", "cena"), (None, "")])
        self.assertEqual(rock.imagens_ordenadas[0].papel_na_capa, "cena")
        self.assertEqual(len(rock.imagens_ordenadas), 1)
        self.rodar("--so", "Air Rock", "--desfazer")
        rock.refresh_from_db()
        self.assertTrue(rock.imagem_brinquedo.name.endswith("black-friday-2026-produto-air-rock-8cf5a03f_cbfpzb"))

    def test_desfazer_volta_o_recorte_do_cartaz(self):
        self.rodar("--vermelhas")
        self.assertIn("Basquete Kids: o recorte do cartaz voltou a ser a capa", self.rodar("--vermelhas", "--desfazer"))
        self.kids.refresh_from_db()
        self.assertEqual(self.kids.imagem_brinquedo.name, self.vermelha)
        self.assertEqual(sorted((f.tipo or "", f.papel_na_capa) for f in self.kids.imagens_brinquedo.all()),
                         [("lado_direito", ""), ("perfil", "")])
        self.assertIn("Basquete Kids: não está com a capa em cena", self.rodar("--vermelhas", "--desfazer"))

    def test_um_erro_nao_para_os_outros_e_avisa_o_comando(self):
        rock = _como_no_ar("air-rock", "Air Rock")
        with mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            texto = self.rodar("--vermelhas")
        self.assertIn("python manage.py capas_em_cena --so 59", texto)
        self.assertIn("python manage.py capas_em_cena --so 60", texto)
        for brinquedo in (self.kids, rock):  # nada pela metade
            self.assertEqual([f.tipo for f in brinquedo.imagens_brinquedo.order_by("ordem")], ["perfil", "lado_direito"])


@override_settings(IS_RENDER=False)
class CategoriaTests(_ComDisco):
    def setUp(self):
        super().setUp()
        self.casinhas = CategoriasBrinquedos.objects.create(
            nome_categoria="Casinhas Cenográficas",
            imagem_categoria="categorias/categoria-produto-casinhas-cenograficas-4c506006_vlkuey",
        )

    def test_a_foto_nova_uma_vez_so_e_o_desfazer(self):
        self.assertIn("poria a foto na brinquedoteca", self.rodar("--vermelhas", "--simular"))
        self.assertIn("a foto agora é a das casinhas na brinquedoteca", self.rodar("--vermelhas"))
        self.casinhas.refresh_from_db()
        nome = self.casinhas.imagem_categoria.name
        self.assertIn(categorias_capas.nome_no_cadastro("casinhas-cenograficas"), nome)
        self.assertIn("já está com a foto na brinquedoteca", self.rodar("--vermelhas"))
        self.casinhas.refresh_from_db()
        self.assertEqual(self.casinhas.imagem_categoria.name, nome)
        self.assertIn("a foto de antes voltou", self.rodar("--vermelhas", "--desfazer"))
        self.casinhas.refresh_from_db()
        self.assertIn("categoria-produto-casinhas-cenograficas-", self.casinhas.imagem_categoria.name)
        with open(Path(self.pasta.name) / self.casinhas.imagem_categoria.name, "rb") as voltou:
            self.assertEqual(voltou.read(), capas_catalogo.FOTO_DE_ANTES_DA_CATEGORIA.read_bytes())

    def test_a_foto_trocada_no_painel_fica(self):
        CategoriasBrinquedos.objects.filter(pk=self.casinhas.pk).update(imagem_categoria="categorias/da-equipe_x1")
        self.assertIn("a foto foi trocada no painel", self.rodar("--vermelhas"))
        self.casinhas.refresh_from_db()
        self.assertEqual(self.casinhas.imagem_categoria.name, "categorias/da-equipe_x1")


@override_settings(IS_RENDER=False)
class MigracaoTests(_ComDisco):
    def test_so_dados_e_depois_da_promocao_do_kit(self):
        self.assertEqual([type(op).__name__ for op in migracao_0180.Migration.operations], ["RunPython"])
        self.assertEqual(len(migracao_0180.Migration.dependencies), 1)
        self.assertEqual(migracao_0180.Migration.dependencies[0][0], "core")

    def test_fora_do_render_nao_faz_nada(self):
        kids = _como_no_ar("basquete-kids", "Basquete Kids")
        self.assertIsNone(capas_catalogo.vermelhas_no_deploy(apps_reais, None, avisar=lambda *_: None))
        self.assertFalse(kids.imagens_brinquedo.filter(papel_na_capa="cena").exists())

    def test_no_render_poe_no_showroom_e_rodar_de_novo_nao_muda_nada(self):
        kids = _como_no_ar("basquete-kids", "Basquete Kids")
        kid_play = _como_no_ar("kid-play", "Kid Play", lado=False)
        casinhas = CategoriasBrinquedos.objects.create(
            nome_categoria="Casinhas Cenográficas", imagem_categoria="categorias/categoria-produto-casinhas-cenograficas-4c506006_vlkuey")
        avisos = []
        with override_settings(IS_RENDER=True):
            feito = capas_catalogo.vermelhas_no_deploy(apps_reais, None, avisar=avisos.append)
            self.assertIn("a capa agora é a cena", feito["Basquete Kids"])
            self.assertIn("a capa agora é a cena", feito["Kid Play"])
            self.assertIn("não está no catálogo", feito["Air Rock"])
            self.assertIn("brinquedoteca", feito["Casinhas Cenográficas (categoria)"])
            estado = sorted(ImagemBrinquedo.objects.values_list("brinquedo_id", "tipo", "papel_na_capa", "imagem", "ordem"),
                            key=str)
            casinhas.refresh_from_db()
            foto_da_categoria = casinhas.imagem_categoria.name
            feito = capas_catalogo.vermelhas_no_deploy(apps_reais, None, avisar=avisos.append)
        self.assertTrue(all("já está" in frase or "não está no catálogo" in frase for frase in feito.values()), feito)
        self.assertEqual(sorted(ImagemBrinquedo.objects.values_list("brinquedo_id", "tipo", "papel_na_capa", "imagem", "ordem"),
                                key=str), estado)
        casinhas.refresh_from_db()
        self.assertEqual(casinhas.imagem_categoria.name, foto_da_categoria)
        for brinquedo in (kids, kid_play):
            brinquedo.refresh_from_db()
            self.assertIn("cena-", brinquedo.imagem_catalogo.name)

    def test_a_subida_que_falha_nao_derruba_o_deploy(self):
        _como_no_ar("basquete-kids", "Basquete Kids")
        avisos = []
        with override_settings(IS_RENDER=True), \
                mock.patch.object(capas_catalogo, "rodar", side_effect=RuntimeError("banco fora")):
            self.assertIsNone(capas_catalogo.vermelhas_no_deploy(apps_reais, None, avisar=avisos.append))
        self.assertIn("python manage.py capas_em_cena --vermelhas", " ".join(avisos))
        avisos = []
        with override_settings(IS_RENDER=True), mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            capas_catalogo.vermelhas_no_deploy(apps_reais, None, avisar=avisos.append)
        self.assertIn("python manage.py capas_em_cena --so 59", " ".join(avisos))


class BlackFridayDoZeroTests(_ComDisco):
    def test_os_produtos_ja_nascem_com_a_cena(self):
        for nome in ("Air Game Kids", "Strike Kids", "Nervo Teste", "Boliche Virtual", "Air Game Home", "Matrix"):
            Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", imagem_brinquedo=f"brinquedos/{nome}.jpg",
                                      avaliacao=Decimal("4.8"), voltz="220V")
        black_friday.rodar(Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, Promocoes,
                           hoje=datetime.date(2026, 11, 11), avisar=lambda *_: None)
        for chave, _i, nome, _prefixo in capas_catalogo.VERMELHAS:
            with self.subTest(nome):
                brinquedo = Brinquedos.objects.get(nome_brinquedo=nome)
                fotos = list(brinquedo.imagens_brinquedo.all())
                self.assertEqual([(f.tipo, f.papel_na_capa) for f in fotos], [("perfil", "cena")])
                self.assertIn(f"cena-{chave}-", brinquedo.imagem_brinquedo.name)
                self.assertNotIn("black-friday-2026-produto", brinquedo.imagem_brinquedo.name)
        casinhas = CategoriasBrinquedos.objects.get(nome_categoria="Casinhas Cenográficas")
        self.assertIn(categorias_capas.nome_no_cadastro("casinhas-cenograficas"), casinhas.imagem_categoria.name)
        # o comando reconhece: já está em cena; e o --desfazer não deixa o produto sem capa
        self.assertIn("Basquete Kids: já está com a capa em cena", self.rodar("--vermelhas"))
        self.assertIn("não há o recorte do cartaz guardado", self.rodar("--vermelhas", "--desfazer"))
        self.assertTrue(Brinquedos.objects.get(nome_brinquedo="Basquete Kids").imagens_brinquedo.filter(papel_na_capa="cena").exists())
