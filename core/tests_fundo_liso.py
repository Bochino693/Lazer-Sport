"""Nenhuma foto de produto num fundo liso (LEIA-ME V10, seção 118; core/fundo_liso.py).

O dono, com o print do catálogo (o Air Game Kids e os basquetes no azul do estúdio da seção 96):
"esses brinquedos com o fundo azul devem ser de ambiente como falei, nada de fundos singulares."

O que estes testes protegem:

  * TODA foto de produto que o repositório controla está num ambiente: as capas do catálogo
    (capas_catalogo/: as do showroom e as da Black Friday), as capas e as vistas dos nossos 3D
    (arena/modelos/<chave>/), as fotos do estúdio da seção 96 (agora no showroom, seção 118) e as
    da Black Friday que sobem (os produtos sem a capa em cena). Ficam de fora, cada uma pelo seu
    motivo: as plantas baixas (o desenho do projeto, não uma foto), os recortes para as artes
    (foto.webp e as cores do Strike Kids: sem fundo de propósito, fora do site) e os recortes do
    cartaz da Black Friday dos produtos com a capa em cena (não sobem: seção 78);
  * a régua: o fundo azul de estúdio (o degradê marinho e royal), o cinza liso e a cor chapada
    reprovam; o showroom, o piso claro com a parede preta e a parede com textura passam;
  * o aviso do painel: a capa do produto ou a frente de um adesivo enviada num fundo liso grava e
    ganha o aviso; a foto de outra posição, não; a branca continua indo para o recorte;
  * a subida no deploy (a 0215): as fotos de estúdio refeitas no showroom sobem no lugar das
    azuis -- a mesma linha, o nome com a assinatura nova --, só no Render; rodar de novo não sobe
    nada; se a subida falha, o deploy segue e o aviso diz o comando.
"""

import importlib
import json
import sys
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.apps import apps as apps_reais
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image, ImageDraw

from . import black_friday, fotos_estudio, fundo_liso
from .models import Brinquedos, ImagemBrinquedo

migracao = importlib.import_module("core.migrations.0215_fotos_de_estudio_no_showroom")

RAIZ = Path(__file__).resolve().parent.parent
SITE = Path(__file__).resolve().parent / "static" / "site"
G = "imagens_brinquedos/galeria/"
INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def _produtos_do_estudio():
    """O produtos.py do estúdio (Python puro: lido sem o Blender)."""
    sys.path.insert(0, str(RAIZ / "ferramentas" / "fotos3d"))
    try:
        return importlib.import_module("produtos")
    finally:
        sys.path.pop(0)


def fora_da_regua(caminho):
    """As que não são foto de produto num lugar, de propósito: a planta baixa e os recortes para as artes."""
    nome = caminho.name
    return nome == "planta.webp" or nome == "foto.webp" or nome.startswith("cor_")


def fotos_de_produto():
    """{rótulo: arquivo} de TODA foto de produto que o repositório controla (o que o site mostra)."""
    fotos = {f"catálogo: {p.stem}": p for p in sorted((SITE / "capas_catalogo").glob("*.webp"))}
    for pasta in sorted(p for p in (SITE / "arena" / "modelos").iterdir() if p.is_dir()):
        for foto in sorted(pasta.glob("*.webp")):
            if not fora_da_regua(foto):
                fotos[f"3D: {pasta.name}/{foto.name}"] = foto
    # a Black Friday: o que sobe dela (os produtos com `cena` sobem a capa do showroom, já na lista acima)
    for dados in black_friday.PRODUTOS:
        if not dados.get("cena"):
            for arquivo in dados["fotos"]:
                fotos[f"Black Friday: {arquivo}"] = SITE / "black_friday" / arquivo
    return fotos


def _png(imagem):
    saida = BytesIO()
    imagem.save(saida, "PNG")
    saida.seek(0)
    return saida


def _maquina(fundo, tamanho=(800, 800)):
    """A "máquina" (um bloco colorido, cheio de detalhe) no meio do `fundo` (uma imagem do tamanho)."""
    imagem = fundo.convert("RGB").resize(tamanho)
    desenho = ImageDraw.Draw(imagem)
    w, h = tamanho
    desenho.rectangle((w * 0.3, h * 0.25, w * 0.7, h * 0.85), fill=(230, 60, 40))
    for i in range(12):
        desenho.rectangle((w * 0.32 + i * w * 0.03, h * 0.3, w * 0.33 + i * w * 0.03, h * 0.8), fill=(250, 210, 30))
    return imagem


def _outra_maquina(fundo, tamanho=(800, 800)):
    """Outra "máquina" (redonda, à esquerda): a foto de outra posição não é a mesma foto."""
    imagem = fundo.convert("RGB").resize(tamanho)
    w, h = tamanho
    ImageDraw.Draw(imagem).ellipse((w * 0.12, h * 0.2, w * 0.55, h * 0.9), fill=(40, 200, 90))
    return imagem


def estudio_azul(tamanho=(800, 800)):
    """O fundo infinito da seção 96: o marinho nas bordas e o brilho royal atrás da máquina."""
    mascara = Image.radial_gradient("L").resize(tamanho)
    marinho = Image.new("RGB", tamanho, (4, 10, 38))
    royal = Image.new("RGB", tamanho, (29, 75, 255))
    return _maquina(Image.composite(marinho, royal, mascara), tamanho)


def showroom_sintetico(tamanho=(800, 800)):
    """A parede preta com as placas e o piso claro com o rejunte (o showroom, de mentira)."""
    w, h = tamanho
    imagem = Image.new("RGB", tamanho, (20, 20, 22))
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle((0, h * 0.55, w, h), fill=(200, 194, 186))
    for x in range(0, w, 60):
        desenho.line((x, h * 0.55, x - 80, h), fill=(130, 124, 118), width=2)
    for y in range(int(h * 0.55), h, 40):
        desenho.line((0, y, w, y), fill=(130, 124, 118), width=2)
    for i in range(0, w, 45):
        desenho.line((i, 0, i + 30, h * 0.5), fill=(45, 45, 48), width=3)
    return _maquina(imagem, tamanho)


class FotosDoRepositorioTests(SimpleTestCase):
    def test_nenhuma_foto_de_produto_num_fundo_liso(self):
        fotos = fotos_de_produto()
        for rotulo, arquivo in fotos.items():
            with self.subTest(rotulo):
                cor, textura = fundo_liso.medir(arquivo)
                self.assertFalse(fundo_liso.e_fundo_liso(arquivo),
                                 f"{rotulo}: fundo liso (cor quase única {cor:.2f}, textura {textura:.1f}). "
                                 "A foto do card deve mostrar o brinquedo num ambiente (o showroom).")

    def test_a_lista_tem_todas(self):
        fotos = set(fotos_de_produto().values())
        self.assertGreater(len(fotos), 100)
        # as de estúdio da seção 96 (o que o ferramentas/fotos3d grava no site), menos o recorte sem fundo
        estudio = _produtos_do_estudio()
        for _p, _v, _t, caminho in estudio.arquivos_do_site():
            if not caminho.endswith("/foto.webp"):
                self.assertIn(RAIZ / caminho, fotos, caminho)
        # as capas do catálogo, as da Black Friday no showroom e a capa de cada um dos nossos 3D
        for arquivo in (SITE / "capas_catalogo").glob("*.webp"):
            self.assertIn(arquivo, fotos)
        for capa in (SITE / "arena" / "modelos").glob("*/capa.webp"):
            self.assertIn(capa, fotos)
        self.assertIn(SITE / "black_friday" / "produto-brinquedao-modelo-5.webp", fotos)
        # os de fora são de fora de propósito: a planta e os recortes para as artes
        self.assertNotIn(SITE / "arena" / "modelos" / "strike-kids" / "foto.webp", fotos)
        self.assertNotIn(SITE / "arena" / "modelos" / "strike-kids" / "cor_azul.webp", fotos)
        self.assertNotIn(SITE / "arena" / "modelos" / "trampolim-enterrada" / "planta.webp", fotos)


class ReguaTests(SimpleTestCase):
    """A régua: a cor quase única E pouca textura na moldura."""

    def test_o_fundo_de_estudio_reprova(self):
        self.assertTrue(fundo_liso.e_fundo_liso(estudio_azul()))
        self.assertTrue(fundo_liso.e_fundo_liso(estudio_azul((1600, 1000))))
        self.assertTrue(fundo_liso.e_fundo_liso(_maquina(Image.new("RGB", (900, 900), (128, 128, 130)))))
        self.assertTrue(fundo_liso.e_fundo_liso(_maquina(Image.new("RGB", (900, 900), (180, 20, 30)))))
        cor, textura = fundo_liso.medir(estudio_azul())
        self.assertGreaterEqual(cor, fundo_liso.COR_QUASE_UNICA)
        self.assertLessEqual(textura, fundo_liso.POUCA_TEXTURA)

    def test_o_ambiente_passa(self):
        self.assertFalse(fundo_liso.e_fundo_liso(showroom_sintetico()))
        # a cor quase única com textura (o galpão claro, a parede de tijolos) não é fundo liso
        ruido = Image.merge("RGB", [Image.effect_noise((800, 800), 40).point(lambda v: v // 3 + 40)] * 2
                            + [Image.effect_noise((800, 800), 40).point(lambda v: v // 2 + 120)])
        self.assertFalse(fundo_liso.e_fundo_liso(_maquina(ruido)))
        # a foto de verdade do showroom (a capa do Air Game Home)
        self.assertFalse(fundo_liso.e_fundo_liso(SITE / "capas_catalogo" / "air-game-home.webp"))

    def test_mede_o_caminho_o_arquivo_e_a_imagem(self):
        arquivo = _png(estudio_azul())
        arquivo.read(10)
        self.assertTrue(fundo_liso.e_fundo_liso(arquivo))
        self.assertEqual(arquivo.tell(), 10)  # (o arquivo volta para onde estava)
        transparente = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
        self.assertTrue(fundo_liso.e_fundo_liso(transparente))  # (o recorte: o branco liso)


class AvisoTests(SimpleTestCase):
    def test_o_aviso(self):
        arquivo = _png(estudio_azul())
        self.assertEqual(fundo_liso.aviso_de_fundo(arquivo),
                         "A foto do card deve mostrar o brinquedo num ambiente (o showroom), não num fundo liso.")
        self.assertEqual(arquivo.tell(), 0)  # o painel ainda grava o arquivo
        self.assertEqual(fundo_liso.aviso_de_fundo(_png(showroom_sintetico())), "")
        # a branca não ganha este aviso: ela vira o recorte para as artes, e o painel já diz isso
        self.assertEqual(fundo_liso.aviso_de_fundo(_png(_maquina(Image.new("RGB", (800, 800), "white")))), "")
        self.assertEqual(fundo_liso.aviso_de_fundo(BytesIO(b"nada")), "")


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

    def produto(self, nome, frente=""):
        brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=Decimal("5.00"),
                                              voltz="", imagem_brinquedo=frente)
        if frente:
            ImagemBrinquedo.objects.create(brinquedo=brinquedo, variante=brinquedo.adesivo_padrao, tipo="perfil",
                                           ordem=1, imagem=frente, papel_na_capa="cena")
        brinquedo.refresh_from_db()
        return brinquedo


class PainelTests(_ComDisco):
    """O aviso do painel: a capa ou a frente do adesivo num fundo liso avisa, e grava assim mesmo."""

    URL = "/site/brinquedos/"

    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("fundo", "f@exemplo.com", "x"))
        self.brinquedo = self.produto("Pebolim")

    @staticmethod
    def envio(nome, imagem):
        return SimpleUploadedFile(nome, _png(imagem).getvalue(), content_type="image/png")

    def salvar(self, **arquivos):
        dados = {"action": "save", "id": self.brinquedo.pk, "nome_brinquedo": "Pebolim", "descricao": "x", **arquivos}
        resposta = self.client.post(self.URL, dados, **AJAX)
        self.assertLess(resposta.status_code, 400, resposta.content[:300])
        return json.loads(resposta.content)["msg"]

    def posicao(self, tipo, imagem, nome):
        padrao = self.brinquedo.adesivo_padrao
        resposta = self.client.post(self.URL, {"action": "adesivo_posicao", "id": self.brinquedo.pk, "adesivo_id": padrao.pk,
                                               "tipo": tipo, "foto": self.envio(nome, imagem)}, **AJAX)
        self.assertLess(resposta.status_code, 400, resposta.content[:300])
        return json.loads(resposta.content)["msg"]

    def test_a_capa_num_fundo_liso_ganha_o_aviso_e_grava(self):
        msg = self.salvar(imagem_perfil=self.envio("azul.png", estudio_azul((400, 400))))
        self.assertIn(fundo_liso.AVISO, msg)
        self.brinquedo.refresh_from_db()
        self.assertIn("azul", self.brinquedo.imagem_brinquedo.name)  # um aviso, e não um bloqueio
        self.assertNotIn(fundo_liso.AVISO, self.salvar(imagem_perfil=self.envio("loja.png", showroom_sintetico((400, 400)))))
        self.assertNotIn(fundo_liso.AVISO, self.salvar())  # sem foto nova: nada a dizer

    def test_a_frente_do_adesivo_tambem(self):
        self.assertIn(fundo_liso.AVISO, self.posicao("perfil", estudio_azul((400, 400)), "frente-azul.png"))
        self.assertTrue(ImagemBrinquedo.objects.filter(tipo="perfil", imagem__contains="frente-azul").exists())
        # a outra posição não é a foto do card: sem aviso
        cinza = Image.new("RGB", (400, 400), (120, 120, 124))
        self.assertNotIn(fundo_liso.AVISO, self.posicao("verso", _outra_maquina(cinza, (400, 400)), "verso-cinza.png"))
        self.assertTrue(ImagemBrinquedo.objects.filter(tipo="verso", imagem__contains="verso-cinza").exists())

    def test_o_adesivo_novo_com_a_frente_num_fundo_liso(self):
        resposta = self.client.post(self.URL, {"action": "adesivo_incluir", "id": self.brinquedo.pk, "adesivo_nome": "Azul",
                                               "adesivo_perfil": self.envio("nova-azul.png", estudio_azul((400, 400)))}, **AJAX)
        self.assertLess(resposta.status_code, 400, resposta.content[:300])
        self.assertIn(fundo_liso.AVISO, json.loads(resposta.content)["msg"])


class MigracaoTests(_ComDisco):
    """A 0215: as fotos de estúdio (a azul de antes no ar) trocadas pelas do showroom, só no Render."""

    ANTIGA = G + "estudio-strike-kids-capa-c2abecd83e_gzu290"

    def setUp(self):
        super().setUp()
        self.strike = self.produto("Strike Kids", self.ANTIGA)
        self.capa = ImagemBrinquedo.objects.get(brinquedo=self.strike, tipo="perfil")

    def no_render(self):
        with override_settings(IS_RENDER=True):
            migracao.subir(apps_reais, None)

    def test_a_migracao_so_de_dados_depois_da_ultima(self):
        self.assertEqual([type(op).__name__ for op in migracao.Migration.operations], ["RunPython"])
        self.assertEqual(migracao.Migration.dependencies, [("core", "0214_capas_novas_dos_kits")])

    @override_settings(IS_RENDER=False)
    def test_fora_do_render_nada_muda(self):
        migracao.subir(apps_reais, None)
        self.capa.refresh_from_db()
        self.assertEqual(self.capa.imagem.name, self.ANTIGA)
        self.assertEqual([p for p in self.pasta.rglob("*") if p.is_file()], [])

    def test_no_render_a_foto_do_showroom_entra_no_lugar_da_azul(self):
        foto = next(f for f in fotos_estudio.ITENS if f[0] == "Strike Kids")[2][0]
        # a capa do repositório não é mais a azul que está no ar (c2abecd83e)
        self.assertNotEqual(fotos_estudio.assinatura(foto), "c2abecd83e")
        self.no_render()
        self.capa.refresh_from_db()
        # a MESMA linha (a capa em cena do adesivo padrão), com o nome da foto de hoje
        self.assertIn(Path(fotos_estudio.nome_no_cadastro(foto)).stem, self.capa.imagem.name)
        self.assertEqual(self.capa.papel_na_capa, "cena")
        with open(self.pasta / self.capa.imagem.name, "rb") as subiu:
            self.assertEqual(subiu.read(), (SITE / "arena" / "modelos" / "strike-kids" / "capa.webp").read_bytes())
        self.strike.refresh_from_db()
        self.assertEqual(self.strike.imagem_brinquedo.name, self.capa.imagem.name)  # a capa do produto, no card
        # rodar de novo não sobe nada
        subidas = sorted(p for p in self.pasta.rglob("*") if p.is_file())
        self.no_render()
        self.assertEqual(sorted(p for p in self.pasta.rglob("*") if p.is_file()), subidas)

    def test_a_subida_que_falha_nao_derruba_o_deploy(self):
        avisos = []
        with override_settings(IS_RENDER=True), mock.patch.object(fotos_estudio, "rodar", side_effect=RuntimeError("fora")):
            self.assertIsNone(fotos_estudio.no_deploy(apps_reais, None, avisar=avisos.append))
        self.assertIn("python manage.py fotos_de_estudio", " ".join(avisos))

    def test_os_nomes_cabem_no_campo(self):
        # o ImageField guarda até 100 caracteres: a pasta, o nome com a assinatura e o sufixo do Cloudinary
        campo = ImagemBrinquedo._meta.get_field("imagem")
        for _produto, _adesivo, fotos in fotos_estudio.ITENS:
            for foto in fotos:
                nome = campo.upload_to + Path(fotos_estudio.nome_no_cadastro(foto)).stem + "_abcdef"
                self.assertLessEqual(len(nome), campo.max_length, nome)
