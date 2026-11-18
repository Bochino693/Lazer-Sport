"""O recorte automático das fotos de peça em fundo branco (LEIA-ME, seção 102).

Fotos sintéticas (nada de foto de cliente): a peça escura num fundo branco, a
caixa branca do produto, o furo do rolo, a sombra cinza e a foto com fundo de
verdade. E o ciclo no cadastro: recorta, guarda a original, não refaz,
desfaz, o sinal só roda onde está ligado.
"""

import tempfile
from io import BytesIO
from unittest import mock

from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase
from PIL import Image, ImageDraw, ImageFilter

from core import recorte_peca
from core.models import ImagemPeca, PecasReposicao


def _jpg(imagem):
    saida = BytesIO()
    imagem.convert("RGB").save(saida, "JPEG", quality=95)
    return saida.getvalue()


def _png(imagem):
    saida = BytesIO()
    imagem.save(saida, "PNG")
    return saida.getvalue()


def _cabo_no_branco():
    """Um anel preto grosso (a volta do cabo) com uma sombra cinza embaixo, no branco."""
    im = Image.new("RGB", (400, 400), (255, 255, 255))
    sombra = Image.new("L", (400, 400), 0)
    ImageDraw.Draw(sombra).ellipse((100, 292, 300, 326), fill=70)
    sombra = sombra.filter(ImageFilter.GaussianBlur(6))
    im.paste((0, 0, 0), mask=sombra.point(lambda v: v // 2))
    d = ImageDraw.Draw(im)
    d.ellipse((80, 70, 320, 310), fill=(20, 20, 20))
    d.ellipse((140, 130, 260, 250), fill=(255, 255, 255))  # o vão da volta: fundo
    return im


def _caixa_branca():
    """A caixa do produto: face branca, contorno cinza, uma janela escura."""
    im = Image.new("RGB", (400, 400), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((70, 60, 330, 340), fill=(250, 250, 250), outline=(160, 160, 160), width=4)
    d.rectangle((110, 160, 290, 300), fill=(30, 30, 35))
    return im


def _alfa(png, xy):
    return Image.open(BytesIO(png)).convert("RGBA").getpixel(xy)[3]


class RecortarTests(TestCase):
    def test_peca_escura_perde_o_fundo_e_o_vao_e_fica_inteira(self):
        png = recorte_peca.recortar(_jpg(_cabo_no_branco()))
        self.assertIsNotNone(png)
        im = Image.open(BytesIO(png)).convert("RGBA")
        w, h = im.size
        self.assertEqual(_alfa(png, (0, 0)), 0, "o canto (fundo) fica transparente")
        # o anel está inteiro: um ponto do anel no meio da altura, à esquerda
        caixa = im.getchannel("A").getbbox()
        self.assertIsNotNone(caixa)
        meio_y = h // 2
        linha = [im.getpixel((x, meio_y))[3] for x in range(w)]
        self.assertGreater(max(linha), 240, "o cabo continua opaco")
        # o vão da volta (o centro) virou fundo também
        self.assertLess(im.getpixel((w // 2, meio_y))[3], 20, "o vão do cabo não fica branco")

    def test_sombra_cinza_vira_sombra_translucida_e_nao_mancha_branca(self):
        png = recorte_peca.recortar(_jpg(_cabo_no_branco()))
        im = Image.open(BytesIO(png)).convert("RGBA")
        claros_opacos = sum(
            1 for r, g, b, a in im.getdata() if a > 200 and min(r, g, b) > 170
        )
        self.assertLess(claros_opacos, 40, "não sobra cinza claro opaco (mancha) em volta do cabo")

    def test_caixa_branca_do_produto_nao_e_comida(self):
        png = recorte_peca.recortar(_jpg(_caixa_branca()))
        self.assertIsNotNone(png)
        im = Image.open(BytesIO(png)).convert("RGBA")
        w, h = im.size
        # a face branca da caixa (acima da janela) continua opaca
        self.assertGreater(im.getpixel((w // 2, int(h * 0.2)))[3], 240)
        self.assertEqual(im.getpixel((0, 0))[3], 0)

    def test_foto_com_fundo_de_verdade_fica_como_esta(self):
        im = Image.new("RGB", (300, 300), (40, 90, 160))
        ImageDraw.Draw(im).rectangle((100, 100, 200, 200), fill=(250, 200, 30))
        self.assertIsNone(recorte_peca.recortar(_jpg(im)))

    def test_png_ja_sem_fundo_so_e_aparado(self):
        im = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((120, 100, 180, 220), fill=(200, 20, 20, 255))
        png = recorte_peca.recortar(_png(im))
        aparada = Image.open(BytesIO(png))
        # aparada em volta da peça (61 x 121 px) e ampliada 2x (a foto é pequena)
        self.assertLess(aparada.width, 160)
        self.assertLess(aparada.height, 290)
        self.assertGreater(aparada.height, aparada.width * 1.6)

    def test_arquivo_que_nao_e_imagem_devolve_none(self):
        self.assertIsNone(recorte_peca.recortar(b"nao sou imagem"))


class CadastroTests(TestCase):
    """A foto no cadastro: num disco temporário (sem Cloudinary)."""

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.disco = FileSystemStorage(location=pasta.name, base_url="/media/")
        for nome in ("imagem", "imagem_original"):
            troca = mock.patch.object(ImagemPeca._meta.get_field(nome), "storage", self.disco)
            troca.start()
            self.addCleanup(troca.stop)
        self.peca = PecasReposicao.objects.create(nome="Cabo de teste", descricao_peca="Cabo.")

    def _foto(self, imagem, nome="cabo.jpg"):
        arquivo = self.disco.save(f"pecas_reposicao/{nome}", BytesIO(_jpg(imagem)))
        return ImagemPeca.objects.create(peca_reposicao=self.peca, imagem=arquivo, ordem=1)

    def test_recorta_guarda_a_original_e_nao_refaz(self):
        foto = self._foto(_cabo_no_branco())
        original = foto.imagem.name
        self.assertEqual(recorte_peca.processar(foto), "recortada")
        foto.refresh_from_db()
        self.assertTrue(foto.imagem.name.endswith(".png"))
        self.assertIn(recorte_peca.MARCA_DO_RECORTE, foto.imagem.name)
        self.assertEqual(foto.imagem_original.name, original)
        self.assertEqual(foto.recorte_de, foto.imagem.name)
        with foto.imagem.open("rb") as arquivo:
            self.assertEqual(_alfa(arquivo.read(), (0, 0)), 0)
        # rodar de novo não refaz (nem baixa)
        with mock.patch.object(recorte_peca, "baixar", side_effect=AssertionError("baixou de novo")):
            self.assertEqual(recorte_peca.processar(foto), "ja_conferida")

    def test_foto_com_fundo_fica_e_fica_marcada_como_conferida(self):
        im = Image.new("RGB", (300, 300), (40, 90, 160))
        foto = self._foto(im, "ambiente.jpg")
        nome = foto.imagem.name
        self.assertEqual(recorte_peca.processar(foto), "sem_recorte")
        foto.refresh_from_db()
        self.assertEqual(foto.imagem.name, nome)
        self.assertFalse(foto.imagem_original)
        self.assertEqual(recorte_peca.processar(foto), "ja_conferida")

    def test_desfazer_devolve_a_foto_da_equipe(self):
        foto = self._foto(_cabo_no_branco())
        original = foto.imagem.name
        recorte_peca.processar(foto)
        foto.refresh_from_db()
        self.assertTrue(recorte_peca.desfazer(foto))
        foto.refresh_from_db()
        self.assertEqual(foto.imagem.name, original)
        self.assertFalse(foto.imagem_original)
        self.assertEqual(recorte_peca.processar(foto), "ja_conferida")

    def test_foto_nova_no_lugar_da_recortada_e_conferida_de_novo(self):
        foto = self._foto(_cabo_no_branco())
        recorte_peca.processar(foto)
        foto.refresh_from_db()
        nova = self.disco.save("pecas_reposicao/nova.jpg", BytesIO(_jpg(_caixa_branca())))
        foto.imagem = nova
        foto.save()
        self.assertTrue(recorte_peca.precisa_conferir(foto))
        self.assertEqual(recorte_peca.processar(foto), "recortada")
        foto.refresh_from_db()
        self.assertEqual(foto.imagem_original.name, nova)

    def test_uma_foto_que_falha_nao_para_as_outras(self):
        ruim = self._foto(_cabo_no_branco(), "ruim.jpg")
        boa = self._foto(_caixa_branca(), "boa.jpg")
        verdadeiro = recorte_peca.baixar

        def baixar(imagem, tempo=25):
            if "ruim" in imagem.name:
                raise OSError("rede fora")
            return verdadeiro(imagem, tempo)

        with mock.patch.object(recorte_peca, "baixar", side_effect=baixar):
            resumo = recorte_peca.processar_todas(ImagemPeca, avisar=None)
        self.assertEqual(resumo["falhou"], 1)
        self.assertEqual(resumo["recortada"], 1)
        ruim.refresh_from_db()
        boa.refresh_from_db()
        self.assertTrue(recorte_peca.precisa_conferir(ruim), "a que falhou fica para a próxima")
        self.assertFalse(recorte_peca.precisa_conferir(boa))

    def test_comando_desfazer_e_refazer(self):
        foto = self._foto(_cabo_no_branco())
        with mock.patch("sys.stdout"):
            call_command("pecas_sem_fundo", stdout=BytesIO_text())
        foto.refresh_from_db()
        self.assertTrue(foto.imagem_original)
        call_command("pecas_sem_fundo", "--desfazer", stdout=BytesIO_text())
        foto.refresh_from_db()
        self.assertFalse(foto.imagem_original)
        call_command("pecas_sem_fundo", "--refazer", "--so", str(self.peca.pk), stdout=BytesIO_text())
        foto.refresh_from_db()
        self.assertTrue(foto.imagem_original)

    def test_sinal_so_roda_quando_ligado(self):
        with mock.patch.object(recorte_peca, "processar_em_segundo_plano") as rodar:
            with self.captureOnCommitCallbacks(execute=True):
                self._foto(_cabo_no_branco(), "desligado.jpg")
            rodar.assert_not_called()
            with self.settings(RECORTE_PECAS_AUTOMATICO=True):
                with self.captureOnCommitCallbacks(execute=True):
                    foto = self._foto(_cabo_no_branco(), "ligado.jpg")
            rodar.assert_called_once_with(foto.pk)

    def test_migracao_nao_faz_nada_fora_do_render(self):
        from importlib import import_module

        migracao = import_module("core.migrations.0205_pecas_sem_fundo_branco")
        with mock.patch.object(recorte_peca, "processar_todas") as todas:
            with self.settings(IS_RENDER=False):
                migracao.recortar(None, None)
            todas.assert_not_called()


def BytesIO_text():
    from io import StringIO

    return StringIO()
