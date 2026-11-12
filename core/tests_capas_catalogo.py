"""As fotos de produto no showroom da Lazer & Sport (a seção 64 do LEIA-ME).

O que estes testes protegem:

  * as capas em cena do catálogo (core/capas_catalogo.py): cada produto da
    lista tem a foto quadrada (1600 x 1600, o card), opaca, leve, com a
    máquina de verdade (a foto do catálogo, recortada) e nenhuma outra; os de
    fora (o Boliche Virtual, os nossos 3D, os Modelos 4 e 5) não estão na lista;
  * "nenhum pode ficar assim" (o Strike Kids apagado): a área do produto de cada
    foto de produto tem contraste e saturação mínimos, tirados da foto de
    verdade do Boliche Virtual;
  * o comando `capas_em_cena`: --simular não mexe; aplicar põe a cena como capa
    e deixa a de antes na galeria (marcada, visível); rodar de novo não
    duplica; --desfazer volta a de antes; a capa trocada pela equipe no painel
    fica; um erro de subida não para os outros;
  * a 0156 (o campo), a 0157 (as capas, só no Render, sem derrubar o deploy) e a 0158
    (a galeria dos nossos 3D refeita à força e as categorias, só no Render);
  * as vistas da galeria dos nossos 3D no showroom (o mesmo nome e tamanho);
  * o card nunca corta o brinquedo (ls-fotos.js e ls-tema.css).
"""

import importlib
import json
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import mock

from django.apps import apps as apps_reais
from django.contrib.staticfiles import finders
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image, ImageFilter, ImageStat

from . import capas_catalogo, categorias_capas
from .cadastro_modelos import CADASTROS
from .models import Brinquedos, ImagemBrinquedo

migracao_0156 = importlib.import_module("core.migrations.0156_papel_na_capa")
migracao_0157_capas = importlib.import_module("core.migrations.0157_capas_em_cena_do_catalogo")
migracao_0157 = importlib.import_module("core.migrations.0158_fotos_no_showroom")

RAIZ = Path(__file__).resolve().parent.parent
FERRAMENTA = RAIZ / "ferramentas" / "categorias"
MODELOS = Path(__file__).resolve().parent / "static" / "site" / "arena" / "modelos"
#: As vistas da galeria dos nossos 3D refeitas no showroom (as outras são da fábrica, plantas ou fotos).
VISTAS = {
    "air-game-kids-alienigenas": ("frente", "lado_esquerdo", "lado_direito", "verso", "tampo"),
    "basquete-street-quadrinhos": ("frente", "lado_esquerdo", "lado_direito", "verso", "jogador"),
    "brinquedao-modelo-3": ("frente", "lado_esquerdo", "lado_direito"),
    "brinquedao-modelo-5": ("frente", "lado_esquerdo", "lado_direito", "perspectiva_3d"),
    "espaco-esportivo-modelo-1": ("frente", "lado_esquerdo", "lado_direito"),
    "strike-kids": ("frente", "lado_direito", "lado_esquerdo", "verso", "tres_quartos_esquerda", "de_cima"),
    "trampolim-enterrada": ("frente", "lado_esquerdo", "lado_direito", "espuma"),
}

#: A medida da "vida" da foto, na área do produto (a caixa da máscara dele, que o compor.py anota em
#: ferramentas/categorias/areas-dos-produtos.json): o contraste (o desvio da luminância), a saturação
#: média e a nitidez (a média das bordas). Na foto de verdade do Boliche Virtual (o showroom), a área
#: da máquina dá ~76, ~67 e ~28; a capa apagada do Strike Kids (o salão do mural) dava 18,7 de nitidez.
#: Com o brinquedo mais vivo (seção 72: compor.py, `vivo`), os mínimos subiram (eram 45, 55 e 19,5;
#: nas vistas, 40 e 45).
CONTRASTE_MINIMO = 48
SATURACAO_MINIMA = 70
NITIDEZ_MINIMA = 20.5
#: Nas vistas da galeria, o limite é mais baixo e a nitidez não conta: há vista que é, de verdade,
#: uma chapa lisa (as costas verdes do Strike Kids) ou o parque inteiro visto do alto (o Espaço Esportivo).
CONTRASTE_MINIMO_VISTA = 45
SATURACAO_MINIMA_VISTA = 53


def vida(foto, caixa=(0.2, 0.15, 0.8, 0.9)):
    """(contraste, saturação, nitidez) da área `caixa` (em fração da foto)."""
    rgb = foto.convert("RGB")
    w, h = rgb.size
    area = rgb.crop((int(w * caixa[0]), int(h * caixa[1]), int(w * caixa[2]), int(h * caixa[3])))
    area = area.resize((300, max(1, round(300 * area.height / area.width))))
    cinza = area.convert("L")
    return (
        ImageStat.Stat(cinza).stddev[0],
        ImageStat.Stat(area.convert("HSV").getchannel("S")).mean[0],
        ImageStat.Stat(cinza.filter(ImageFilter.FIND_EDGES)).mean[0],
    )


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    storage = FileSystemStorage(location=pasta)
    return (
        mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage),
        mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage),
    )


def _do_painel(item, com_galeria=True, outra_foto=False):
    """O produto como a equipe cadastrou: a capa é a foto da lista (no Cloudinary) e, às vezes, mais fotos."""
    chave, _i, nome, public_id = item
    capa = "imagens_brinquedos/outra_foto_x1y2.png" if outra_foto else f"{public_id}.png"
    brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=Decimal("5.00"), voltz="220V",
                                          imagem_brinquedo=capa)
    if com_galeria:
        ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="perfil", ordem=1, imagem=capa, texto_alternativo="a da equipe")
        ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="lado_direito", ordem=2, imagem="imagens_brinquedos/lado.png")
    return brinquedo


class FotosDoCatalogoTests(TestCase):
    def test_a_lista_e_os_de_fora(self):
        self.assertEqual(len(capas_catalogo.LISTA), 39)
        nomes = {nome for _c, _i, nome, _p in capas_catalogo.LISTA}
        self.assertEqual(len(nomes), 39)
        for fora in ("Boliche Virtual", "Brinquedão Modelo 4", "Brinquedão Modelo 5", "Strike Kids", "Brinquedão Modelo 2"):
            self.assertNotIn(fora, nomes)
            self.assertIn(fora, capas_catalogo.FORA)
        # os nossos 3D ficam de fora todos (a capa deles é a cena do cadastro)
        for dados in CADASTROS.values():
            self.assertNotIn(dados["nome"], nomes)

    def test_cada_foto_e_quadrada_opaca_leve_e_so_tem_a_maquina(self):
        lista = json.loads((FERRAMENTA / "maquinas-dos-produtos.json").read_text(encoding="utf-8"))
        ficha = json.loads((FERRAMENTA / "maquinas" / "maquinas.json").read_text(encoding="utf-8"))
        for chave, i, nome, _public_id in capas_catalogo.LISTA:
            with self.subTest(nome):
                arquivo = capas_catalogo.arquivo(chave)
                with Image.open(arquivo) as foto:
                    self.assertEqual(foto.format, "WEBP")
                    self.assertEqual(foto.size, (1600, 1600))  # o card é quadrado: nada de zoom nem corte
                    self.assertNotIn("A", foto.getbands())
                self.assertLessEqual(arquivo.stat().st_size, 250 * 1024)
                self.assertTrue(finders.find(f"site/capas_catalogo/{chave}.webp"))
                # a máquina é a de verdade (a foto do catálogo, recortada), e nenhuma outra na foto
                self.assertEqual((ficha[chave]["id"], ficha[chave]["nome"]), (i, nome))
                self.assertTrue((FERRAMENTA / "maquinas-alta" / f"{chave}.webp").exists())
                self.assertEqual(lista[chave], [nome])

    def test_nenhuma_foto_de_produto_fica_apagada(self):
        # "veja como ficou apagado o boliche kids, assim não vai vender, nenhum pode ficar assim":
        # as capas do catálogo, as capas dos nossos 3D e as vistas da galeria
        areas = json.loads((FERRAMENTA / "areas-dos-produtos.json").read_text(encoding="utf-8"))
        # (e as da Black Friday tiradas do fundo vermelho, seção 78)
        fotos = {f"produto_{chave}": capas_catalogo.arquivo(chave) for chave, *_ in capas_catalogo.LISTA + capas_catalogo.VERMELHAS}
        fotos.update({f"capa_{chave}": MODELOS / chave / "capa.webp" for chave in CADASTROS if (MODELOS / chave / "capa.webp").exists()})
        fotos.update({f"vista_{chave}_{vista}": MODELOS / chave / f"{vista}.webp" for chave, vistas in VISTAS.items() for vista in vistas})
        self.assertEqual(set(fotos) - set(areas), set())
        for nome, arquivo in fotos.items():
            with self.subTest(nome), Image.open(arquivo) as foto:
                contraste, saturacao, nitidez = vida(foto, areas[nome])
                if nome.startswith("vista_"):
                    self.assertGreaterEqual(contraste, CONTRASTE_MINIMO_VISTA)
                    self.assertGreaterEqual(saturacao, SATURACAO_MINIMA_VISTA)
                    continue
                # as capas (a foto do card): o contraste, a cor e a nitidez da foto de verdade
                self.assertGreaterEqual(contraste, CONTRASTE_MINIMO)
                self.assertGreaterEqual(saturacao, SATURACAO_MINIMA)
                self.assertGreaterEqual(nitidez, NITIDEZ_MINIMA)

    def test_o_padrao_e_o_showroom(self):
        codigo = (FERRAMENTA / "cenas.js").read_text(encoding="utf-8")
        inicio = codigo.index("const CATALOGO = {")
        catalogo = codigo[inicio:codigo.index("\n};\n", inicio)]
        # as 39 de fundo branco e as 7 da Black Friday (o fundo vermelho e as panorâmicas, seção 78)
        self.assertEqual(catalogo.count('...v("'), 39 + len(capas_catalogo.VERMELHAS))
        for cenario in ("logo", "plantas", "fliperama", "vitrine"):
            self.assertGreaterEqual(catalogo.count(f'...v("{cenario}"'), 5)  # variam: não fica igual em todos
        inicio = codigo.index("const CAPAS = {")
        capas = codigo[inicio:codigo.index("\n};\n", inicio)]
        self.assertEqual(capas.count('lugar: "showroom"'), 7)  # o Espaço Esportivo, no galpão
        for peca in ("NeutralToneMapping", "principal", "preenchimento", "recorte", "anisotropy = 16"):
            self.assertIn(peca, codigo)
        lugares = (FERRAMENTA / "lugares.js").read_text(encoding="utf-8")
        self.assertIn("showroom(caixaDos, giro, op = {})", lugares)
        # a placa é o logo oficial da empresa; os adesivos são genéricos (nada de personagem de ninguém)
        self.assertIn("logoofi.png", (FERRAMENTA / "placa.py").read_text(encoding="utf-8"))
        self.assertTrue((FERRAMENTA / "showroom" / "placa-lazer-sport.png").exists())
        showroom = lugares.lower().split("showroom(caixados")[1].split("fliperama(caixados")[0]
        for terceiro in ("pac-man", "pacman", "fantasminha", "mario", "sonic"):
            self.assertNotIn(terceiro, showroom)

    def test_as_vistas_dos_nossos_3d_no_showroom(self):
        for chave, vistas in VISTAS.items():
            for vista in vistas:
                with self.subTest(f"{chave}/{vista}"), Image.open(MODELOS / chave / f"{vista}.webp") as foto:
                    # o mesmo tamanho de antes (o cadastro e a Arena não mudam) e com o lugar (opaca)
                    self.assertEqual(foto.size, (1080, 1080) if chave == "strike-kids" else (1600, 1000))
                    self.assertNotIn("A", foto.getbands())
                    claro = sum(1 for p in foto.convert("RGB").resize((80, 50)).getdata() if min(p) > 238)
                    self.assertLess(claro / 4000, 0.25)  # não é mais o fundo claro de estúdio
                    self.assertLessEqual((MODELOS / chave / f"{vista}.webp").stat().st_size, 200 * 1024)
        # e ficam: a foto sem fundo do Strike Kids (a capa da Arena), as da fábrica e as plantas
        with Image.open(MODELOS / "strike-kids" / "foto.webp") as foto:
            self.assertEqual(foto.mode, "RGBA")

    def test_o_card_enche_a_caixa_bem_enquadrado(self):
        """Sem faixas desfocadas dos lados: a foto de outro formato vira o
        recorte no formato da caixa, feito pelo conteúdo (Cloudinary g_auto)."""
        js = (RAIZ / "core" / "static" / "site" / "ls-fotos.js").read_text(encoding="utf-8")
        css = (RAIZ / "core" / "static" / "site" / "ls-tema.css").read_text(encoding="utf-8")
        self.assertIn("outroFormato", js)
        self.assertIn("foto-enquadrada", js)
        self.assertIn("c_fill,g_auto,ar_", js)
        self.assertNotIn("foto-encaixada", js + css)
        self.assertNotIn("--foto-fundo", js + css)
        bloco = css[css.index(".foto-cheia.foto-enquadrada img {"):]
        self.assertIn("object-fit: cover", bloco[:bloco.index("}")])

    def test_o_card_nunca_da_zoom(self):
        """"valide para não ter fotos assim com zoom pois estraga" (o Air Rock
        panorâmico no card quadrado): o recorte vai só até 1,4 x de diferença
        de formato; a foto muito diferente fica inteira, no meio da caixa,
        com as faixas na cor da beirada dela -- nada de cópia desfocada."""
        js = (RAIZ / "core" / "static" / "site" / "ls-fotos.js").read_text(encoding="utf-8")
        css = (RAIZ / "core" / "static" / "site" / "ls-tema.css").read_text(encoding="utf-8")
        self.assertIn("const ZOOM_MAXIMO = Math.log(1.4);", js)
        self.assertIn("zoomDemais(caixa, formato)", js)
        self.assertIn("recorteLimitado", js)
        # o recorte limitado parte da FOTO: some no máximo ~10% dela (nunca a máquina cortada)
        self.assertIn("const APARA_NO_MAXIMO = 1.12;", js)
        self.assertIn("Math.max(daCaixa, proporcao / APARA_NO_MAXIMO)", js)
        self.assertNotIn("daCaixa * 1.4", js)
        bloco = css[css.index(".foto-cheia.foto-inteira {"):]
        self.assertIn("var(--foto-faixas, var(--foto-borda", bloco[:bloco.index("}")])
        bloco = css[css.index(".foto-cheia.foto-inteira:not(.ls-vitrine-foto) {"):]
        self.assertIn("place-items: center", bloco[:bloco.index("}")])
        self.assertNotIn("blur(", css[css.index(".foto-cheia.foto-inteira {"):css.index(".foto-cheia.foto-enquadrada img {")])


@override_settings(IS_RENDER=False)
class ComandoTests(TestCase):
    ITEM = next(item for item in capas_catalogo.LISTA if item[2] == "Pega Toupeira")

    def _rodar(self, *argumentos, pasta=None):
        saida = StringIO()
        if pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("capas_em_cena", *argumentos, stdout=saida)
        else:
            call_command("capas_em_cena", *argumentos, stdout=saida)
        return saida.getvalue()

    def test_simular_nao_mexe(self):
        brinquedo = _do_painel(self.ITEM)
        texto = self._rodar("--simular", "--so", str(self.ITEM[1]))
        self.assertIn("poria a capa em cena", texto)
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 2)
        self.assertFalse(ImagemBrinquedo.objects.filter(papel_na_capa="cena").exists())

    def test_aplicar_poe_a_cena_e_a_de_antes_fica_na_galeria(self):
        brinquedo = _do_painel(self.ITEM)
        with tempfile.TemporaryDirectory() as pasta:
            texto = self._rodar("--so", "Pega Toupeira", pasta=pasta)
            self.assertIn("a capa agora é a cena", texto)
            brinquedo.refresh_from_db()
            fotos = list(brinquedo.imagens_brinquedo.order_by("ordem", "id"))
            self.assertEqual([(f.tipo, f.papel_na_capa) for f in fotos],
                             [("perfil", "cena"), (None, "original"), ("lado_direito", "")])
            self.assertIn("cena-pega-toupeira-", brinquedo.imagem_brinquedo.name)
            with open(Path(pasta) / fotos[0].imagem.name, "rb") as subiu:
                self.assertEqual(subiu.read(), capas_catalogo.arquivo("pega-toupeira").read_bytes())
            # o card e a página mostram a cena; a galeria pública mostra também a foto da equipe
            self.assertEqual(brinquedo.imagem_catalogo.name, fotos[0].imagem.name)
            self.assertEqual([f.papel_na_capa for f in brinquedo.imagens_ordenadas], ["cena", "original", ""])
            # de novo: não duplica
            self.assertIn("já está com a capa em cena", self._rodar("--so", "13", pasta=pasta))
            self.assertEqual(brinquedo.imagens_brinquedo.count(), 3)

    def test_desfazer_volta_a_capa_de_antes(self):
        brinquedo = _do_painel(self.ITEM)
        capa_antes = brinquedo.imagem_brinquedo.name
        with tempfile.TemporaryDirectory() as pasta:
            self._rodar("--so", "13", pasta=pasta)
            self.assertIn("a capa de antes voltou", self._rodar("--desfazer", "--so", "13", pasta=pasta))
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, capa_antes)
        fotos = list(brinquedo.imagens_brinquedo.order_by("ordem", "id"))
        self.assertEqual([(f.tipo, f.papel_na_capa) for f in fotos], [("perfil", ""), ("lado_direito", "")])
        self.assertEqual(fotos[0].imagem.name, capa_antes)
        self.assertIn("não está com a capa em cena", self._rodar("--desfazer", "--so", "13"))

    def test_sem_galeria_a_capa_antiga_vira_a_original(self):
        brinquedo = _do_painel(self.ITEM, com_galeria=False)
        with tempfile.TemporaryDirectory() as pasta:
            self._rodar("--so", "13", pasta=pasta)
            fotos = list(brinquedo.imagens_brinquedo.order_by("ordem", "id"))
            self.assertEqual([(f.tipo, f.papel_na_capa) for f in fotos], [("perfil", "cena"), (None, "original")])
            self.assertEqual(fotos[1].imagem.name, f"{self.ITEM[3]}.png")
            self._rodar("--desfazer", "--so", "13", pasta=pasta)
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, f"{self.ITEM[3]}.png")

    def test_a_foto_trocada_no_painel_fica(self):
        brinquedo = _do_painel(self.ITEM, outra_foto=True)
        with tempfile.TemporaryDirectory() as pasta:
            texto = self._rodar("--so", "13", pasta=pasta)
        self.assertIn("trocada no painel", texto)
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, "imagens_brinquedos/outra_foto_x1y2.png")
        self.assertFalse(brinquedo.imagens_brinquedo.filter(papel_na_capa__in=["cena", "original"]).exists())

    def test_um_erro_nao_para_os_outros_e_avisa_o_comando(self):
        toupeira = _do_painel(self.ITEM)
        sonic = _do_painel(next(item for item in capas_catalogo.LISTA if item[2] == "Sonic Kids"))
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            texto = self._rodar("--so", "13", "Sonic Kids", pasta=pasta)
        self.assertIn("python manage.py capas_em_cena --so 13", texto)
        self.assertIn("python manage.py capas_em_cena --so 27", texto)
        for brinquedo in (toupeira, sonic):
            brinquedo.refresh_from_db()  # nada pela metade
            self.assertEqual([f.tipo for f in brinquedo.imagens_brinquedo.order_by("ordem")], ["perfil", "lado_direito"])

    def test_so_um_que_nao_esta_na_lista(self):
        self.assertIn("Os da lista", self._rodar("--so", "Brinquedão Modelo 2"))


@override_settings(IS_RENDER=False)
class MigracoesTests(TestCase):
    def test_a_0156_depois_da_0155_e_so_no_render(self):
        self.assertEqual(migracao_0156.Migration.dependencies, [("core", "0155_imagens_em_alta")])
        # esquema e dados em arquivos separados (Postgres: "pending trigger events")
        self.assertEqual([type(op).__name__ for op in migracao_0156.Migration.operations], ["AddField"])
        self.assertEqual(migracao_0157_capas.Migration.dependencies, [("core", "0156_papel_na_capa")])
        self.assertEqual([type(op).__name__ for op in migracao_0157_capas.Migration.operations], ["RunPython"])
        brinquedo = _do_painel(ComandoTests.ITEM)
        self.assertIsNone(capas_catalogo.subir_no_deploy(apps_reais, None, avisar=lambda *_: None))
        self.assertFalse(brinquedo.imagens_brinquedo.filter(papel_na_capa="cena").exists())
        avisos = []
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True):
                feito = capas_catalogo.subir_no_deploy(apps_reais, None, avisar=avisos.append)
        self.assertIn("a capa agora é a cena", feito["Pega Toupeira"])
        self.assertIn("não está no catálogo", feito["Sonic Kids"])
        self.assertTrue(brinquedo.imagens_brinquedo.filter(papel_na_capa="cena").exists())

    def test_a_0156_nao_derruba_o_deploy(self):
        _do_painel(ComandoTests.ITEM)
        avisos = []
        with mock.patch.object(capas_catalogo, "rodar", side_effect=RuntimeError("banco fora")), \
                override_settings(IS_RENDER=True):
            self.assertIsNone(capas_catalogo.subir_no_deploy(apps_reais, None, avisar=avisos.append))
        self.assertIn("python manage.py capas_em_cena", " ".join(avisos))

    def test_a_0157_refaz_a_forca_os_nossos_3d_e_sobe_as_categorias(self):
        self.assertEqual(migracao_0157.Migration.dependencies, [("core", "0157_capas_em_cena_do_catalogo")])
        dados = CADASTROS["air-game-kids-alienigenas"]
        brinquedo = Brinquedos.objects.create(nome_brinquedo=dados["nome"], descricao="x", avaliacao=5,
                                              imagem_brinquedo="imagens_brinquedos/air-game-kids-alienigenas-capa.webp")
        ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="perfil", ordem=1,
                                       imagem="imagens_brinquedos/air-game-kids-alienigenas-capa-antes.webp")
        avisos = []
        with mock.patch.object(categorias_capas, "subir_fotos_no_deploy") as categorias:
            migracao_0157.refazer(apps_reais, None, avisar=avisos.append)  # fora do Render: nada
            categorias.assert_not_called()
            with tempfile.TemporaryDirectory() as pasta:
                a, b = _disco(pasta)
                with a, b, override_settings(IS_RENDER=True):
                    migracao_0157.refazer(apps_reais, None, avisar=avisos.append)
                fotos = list(brinquedo.imagens_brinquedo.order_by("ordem"))
                self.assertEqual([f.tipo for f in fotos], [tipo for _, tipo, _ in dados["fotos"]])
                with open(Path(pasta) / fotos[0].imagem.name, "rb") as subiu:
                    self.assertEqual(subiu.read(), (dados["pasta"] / "capa.webp").read_bytes())
            categorias.assert_called_once()
        self.assertIn("showroom", " ".join(avisos))

    def test_a_0157_nao_derruba_o_deploy(self):
        dados = CADASTROS["strike-kids"]
        brinquedo = Brinquedos.objects.create(nome_brinquedo=dados["nome"], descricao="x", avaliacao=5,
                                              imagem_brinquedo="imagens_brinquedos/strike-kids-capa.webp")
        avisos = []
        with tempfile.TemporaryDirectory() as pasta, mock.patch.object(categorias_capas, "subir_fotos_no_deploy"), \
                mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True):
                migracao_0157.refazer(apps_reais, None, avisar=avisos.append)
        self.assertIn("python manage.py cadastrar_modelo_3d strike-kids --fotos", " ".join(avisos))
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, "imagens_brinquedos/strike-kids-capa.webp")
