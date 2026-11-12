"""Todas as capas quadradas (a seção 80 do LEIA-ME).

O cliente: "de novo vc errou no dimensionamento de algumas fotos, elas devem
ser padrão. veja que não quero fotos cortadas menores, deve seguir o mesmo
padrão." O que estes testes protegem:

  * TODA capa que o repositório controla é quadrada, 1600 x 1600 (as capas em
    cena do catálogo e da Black Friday, a capa de cada um dos nossos 3D e a
    de cada adesivo), leve e com a máquina inteira;
  * cada adesivo de um produto com mais de um adesivo tem a capa quadrada em
    cena (a foto DELE, na frente, `papel_na_capa = "cena"`): a primeira da
    galeria dele, a do card que gira por adesivo;
  * o mecanismo (core/capas_quadradas.py, `capas_em_cena --quadradas`, a
    0186): a capa de antes (a imagem da fábrica) continua na galeria; a frente
    trocada no painel fica; rodar de novo não muda nada; --simular não mexe;
    --desfazer volta; um erro não para os outros; o deploy não cai e só roda
    no Render;
  * o aviso do painel: a capa fora do quadrado ganha o aviso, e grava.
"""

import importlib
import json
import tempfile
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock

from django.apps import apps as apps_reais
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from . import capas_catalogo, capas_quadradas
from .cadastro_modelos import CADASTROS
from .models import Brinquedos, ImagemBrinquedo, VarianteAdesivo, galeria_publica

migracao_0186 = importlib.import_module("core.migrations.0186_capas_quadradas_dos_adesivos")

RAIZ = Path(__file__).resolve().parent.parent
FERRAMENTA = RAIZ / "ferramentas" / "categorias"
MODELOS = capas_quadradas.MODELOS
INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def capas_do_repositorio():
    """{nome: arquivo} de TODA capa de card que o repositório controla."""
    capas = {f"catálogo: {nome}": capas_catalogo.arquivo(chave) for chave, _i, nome, _p in capas_catalogo.LISTA}
    capas.update({f"Black Friday: {nome}": capas_catalogo.arquivo(chave) for chave, _i, nome, _p in capas_catalogo.VERMELHAS})
    da_rotina = {item[0]: item[3] for item in capas_quadradas.ITENS if item[3] is not None}
    for chave, dados in CADASTROS.items():
        # a capa do nosso 3D: a da rotina (a quadrada que sobe por cima), senão a frente do cadastro
        frente = next(arquivo for arquivo, tipo, _t in dados["fotos"] if tipo == "perfil")
        capas[f"3D: {dados['nome']}"] = da_rotina.get(chave, dados["pasta"] / frente)
    capas.update({f"adesivo: {capas_quadradas._rotulo(item)}": item[3] for item in capas_quadradas.ITENS if item[3]})
    return capas


class FotosTests(TestCase):
    def test_toda_capa_do_repositorio_e_quadrada_1600(self):
        capas = capas_do_repositorio()
        self.assertGreaterEqual(len(capas), 39 + 7 + 10)
        for nome, arquivo in capas.items():
            with self.subTest(nome), Image.open(arquivo) as foto:
                self.assertEqual(foto.size, (1600, 1600))  # o card é quadrado: nem faixas, nem zoom
                self.assertEqual(foto.format, "WEBP")
                self.assertNotIn("A", foto.getbands())
                self.assertLessEqual(Path(arquivo).stat().st_size, 250 * 1024)
                self.assertTrue(finders.find(str(Path(arquivo).relative_to(RAIZ / "core" / "static"))))

    def test_as_capas_novas_tem_a_maquina_inteira_e_grande(self):
        areas = json.loads((FERRAMENTA / "areas-dos-produtos.json").read_text(encoding="utf-8"))
        for chave in ("air-game-kids-astronautas", "brinquedao-modelo-4", "brinquedao-modelo-5"):
            with self.subTest(chave):
                x0, y0, x1, y1 = areas[f"capa_{chave}"]
                self.assertTrue(x0 >= 0.02 and y0 >= 0.02 and x1 <= 0.98 and y1 <= 0.98, areas[f"capa_{chave}"])
                self.assertGreater(max(x1 - x0, y1 - y0), 0.6)

    def test_cada_adesivo_dos_produtos_com_mais_de_um_tem_a_capa(self):
        rotulos = {capas_quadradas._rotulo(item) for item in capas_quadradas.ITENS}
        for esperado in ("Air Game Kids (Astronautas)", "Air Game Kids (Alienígenas)", "Basquete Home (Quadrinhos)",
                         "Basquete Home", "Air Game Premium", "Brinquedão Modelo 4", "Brinquedão Modelo 5"):
            self.assertIn(esperado, rotulos)
        # todo nosso 3D está na rotina (a capa dele é a quadrada, em cena)
        for chave, dados in CADASTROS.items():
            self.assertTrue(any(item[0] == chave for item in capas_quadradas.ITENS), chave)
        # os 3D de cada adesivo também têm a capa (o Astronautas ganhou a dele)
        for pasta in ("air-game-kids-astronautas", "air-game-kids-alienigenas", "basquete-street-quadrinhos"):
            self.assertTrue((MODELOS / pasta / "capa.webp").exists(), pasta)

    def test_as_cenas_das_capas_novas(self):
        codigo = (FERRAMENTA / "cenas.js").read_text(encoding="utf-8")
        capas = codigo[codigo.index("const CAPAS = {"):]
        capas = capas[:capas.index("\n};\n")]
        for chave, lugar in (("air-game-kids-astronautas", "showroom"), ("brinquedao-modelo-5", "showroom"),
                             ("brinquedao-modelo-4", "showroom")):
            bloco = capas[capas.index(f'"{chave}": {{'):]
            bloco = bloco[:bloco.index("\n  },")]
            self.assertIn(f'lugar: "{lugar}"', bloco)
            self.assertIn(f'glb("{chave}")', bloco)

    def test_o_aviso_do_formato(self):
        def png(largura, altura):
            saida = BytesIO()
            Image.new("RGB", (largura, altura), (40, 90, 160)).save(saida, "PNG")
            saida.seek(0)
            return saida

        self.assertEqual(capas_quadradas.aviso_de_formato(png(1600, 1000)),
                         "A capa do card deve ser quadrada (1:1); esta é 1,6:1.")
        self.assertEqual(capas_quadradas.aviso_de_formato(png(1086, 1448)),
                         "A capa do card deve ser quadrada (1:1); esta é 0,75:1.")
        self.assertEqual(capas_quadradas.aviso_de_formato(png(1600, 1600)), "")
        self.assertEqual(capas_quadradas.aviso_de_formato(png(1000, 900)), "")  # 1,11: quase quadrada
        arquivo = png(1567, 1004)
        self.assertIn("1,56:1", capas_quadradas.aviso_de_formato(arquivo))
        self.assertEqual(arquivo.tell(), 0)  # o arquivo volta ao começo (o painel ainda grava ele)
        self.assertEqual(capas_quadradas.aviso_de_formato(BytesIO(b"nada")), "")


class _ComDisco(TestCase):
    """As fotos num disco temporário."""

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

    def produto(self, nome, frente=None, papel=""):
        """O produto como está no ar: a frente do adesivo padrão (o arquivo do Cloudinary) e a capa igual."""
        brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=Decimal("5.00"),
                                              voltz="", imagem_brinquedo=frente or "")
        if frente:
            ImagemBrinquedo.objects.create(brinquedo=brinquedo, variante=brinquedo.adesivo_padrao, tipo="perfil",
                                           ordem=1, imagem=frente, papel_na_capa=papel)
        brinquedo.refresh_from_db()
        return brinquedo

    def foto(self, brinquedo, variante, tipo, imagem, ordem=2, papel=""):
        return ImagemBrinquedo.objects.create(brinquedo=brinquedo, variante=variante, tipo=tipo, ordem=ordem,
                                              imagem=imagem, papel_na_capa=papel)

    def rodar(self, *argumentos):
        saida = StringIO()
        call_command("capas_em_cena", "--quadradas", *argumentos, stdout=saida)
        return saida.getvalue()

    def estado(self):
        return sorted(ImagemBrinquedo.objects.values_list("brinquedo_id", "variante_id", "tipo", "papel_na_capa", "imagem"),
                      key=str)


@override_settings(IS_RENDER=False)
class AirGameKidsTests(_ComDisco):
    """O Air Game Kids como está no ar: o Astronautas com a capa em cena do catálogo; o Alienígenas sem frente."""

    def setUp(self):
        super().setUp()
        self.kids = self.produto("Air Game Kids", "imagens_brinquedos/galeria/cena-air-game-kids-56aeb3d2d5_epknbl",
                                 papel="cena")
        self.astronautas = self.kids.adesivo_padrao
        VarianteAdesivo.objects.filter(pk=self.astronautas.pk).update(nome="Astronautas", slug="astronautas")
        self.foto(self.kids, self.astronautas, "tres_quartos", "imagens_brinquedos/galeria/air-game-kids-astronautas-frente_p8swir")
        self.alien = VarianteAdesivo.objects.create(brinquedo=self.kids, nome="Alienígenas", slug="alienigenas", ordem=2)
        self.foto(self.kids, self.alien, "tres_quartos", "imagens_brinquedos/galeria/air-game-kids-alienigenas-frente_ebhqcl", 3)
        self.foto(self.kids, self.alien, "lado_direito", "imagens_brinquedos/galeria/air-game-kids-alienigenas-lado_direito_ejo4fl", 4)

    def test_cada_adesivo_com_a_capa_quadrada_em_cena(self):
        self.assertIn("poria a capa quadrada como a frente", self.rodar("--simular"))
        self.assertFalse(ImagemBrinquedo.objects.filter(variante=self.alien, papel_na_capa="cena").exists())
        texto = self.rodar()
        self.assertIn("Air Game Kids (Astronautas): já está com a capa quadrada em cena", texto)
        self.assertIn("Air Game Kids (Alienígenas): a capa agora é a quadrada no showroom", texto)
        capa = ImagemBrinquedo.objects.get(variante=self.alien, papel_na_capa="cena")
        self.assertEqual(capa.tipo, "perfil")
        with open(self.pasta / capa.imagem.name, "rb") as subiu:
            self.assertEqual(subiu.read(), (MODELOS / "air-game-kids-alienigenas" / "capa.webp").read_bytes())
        with Image.open(self.pasta / capa.imagem.name) as foto:
            self.assertEqual(foto.size, (1600, 1600))
        # a primeira foto do adesivo na página (e no card que gira por adesivo) é a capa quadrada
        fotos = list(self.kids.imagens_brinquedo.all())
        self.assertEqual(galeria_publica(fotos, self.kids.adesivo_padrao_id, adesivo_id=self.alien.pk)[0].pk, capa.pk)
        self.assertEqual(galeria_publica(fotos, self.kids.adesivo_padrao_id)[0].papel_na_capa, "cena")
        # a capa do produto (a do padrão) não mudou; as vistas continuam na galeria
        self.kids.refresh_from_db()
        self.assertIn("cena-air-game-kids", self.kids.imagem_brinquedo.name)
        self.assertEqual(len(galeria_publica(fotos, self.kids.adesivo_padrao_id, adesivo_id=self.alien.pk)), 3)

    def test_rodar_de_novo_nao_muda_nada_e_o_desfazer_volta(self):
        self.rodar()
        estado = self.estado()
        texto = self.rodar()
        self.assertIn("Air Game Kids (Alienígenas): já está com a capa quadrada em cena", texto)
        self.assertEqual(self.estado(), estado)
        texto = self.rodar("--desfazer")
        self.assertIn("Air Game Kids (Alienígenas): a capa de antes voltou", texto)
        self.assertIn("Air Game Kids (Astronautas): não está com a capa quadrada desta rotina", texto)
        self.assertFalse(ImagemBrinquedo.objects.filter(variante=self.alien, papel_na_capa="cena").exists())
        # a capa em cena do catálogo (a do Astronautas) não é desta rotina: fica
        self.assertTrue(ImagemBrinquedo.objects.filter(variante=self.astronautas, papel_na_capa="cena").exists())

    def test_a_frente_trocada_no_painel_fica(self):
        self.foto(self.kids, self.alien, "perfil", "imagens_brinquedos/galeria/foto-da-equipe_x1y2z3", 1)
        self.assertIn("a frente foi trocada no painel", self.rodar("--so", "Air Game Kids (Alienígenas)"))
        self.assertFalse(ImagemBrinquedo.objects.filter(variante=self.alien, papel_na_capa="cena").exists())


@override_settings(IS_RENDER=False)
class BrinquedoesTests(_ComDisco):
    def test_modelo_4_a_capa_do_3d_e_a_da_fabrica_na_galeria(self):
        m4 = self.produto("Brinquedão Modelo 4", "imagens_brinquedos/galeria/brinquedao-modelo-4-perspectiva_wjiskf")
        self.foto(m4, m4.adesivo_padrao, None, "imagens_brinquedos/galeria/brinquedao-modelo-4-planta_ab12cd", papel="recorte")
        self.assertIn("a capa agora é a quadrada no showroom (a de antes continua na galeria)", self.rodar("--so", "Brinquedão Modelo 4"))
        m4.refresh_from_db()
        fotos = list(m4.imagens_brinquedo.all())
        galeria = galeria_publica(fotos, m4.adesivo_padrao_id)
        self.assertEqual([(f.tipo, f.papel_na_capa) for f in galeria], [("perfil", "cena"), ("tres_quartos", "")])
        self.assertIn("brinquedao-modelo-4-perspectiva", galeria[1].imagem.name)  # a imagem da fábrica fica
        self.assertIn("capa-brinquedao-modelo-4-", m4.imagem_brinquedo.name)
        self.assertEqual(m4.imagem_catalogo.name, galeria[0].imagem.name)
        # de novo: nada; desfazer: a da fábrica volta a ser a capa
        estado = self.estado()
        self.assertIn("já está com a capa quadrada em cena", self.rodar("--so", "Brinquedão Modelo 4"))
        self.assertEqual(self.estado(), estado)
        self.assertIn("a capa de antes voltou", self.rodar("--so", "Brinquedão Modelo 4", "--desfazer"))
        m4.refresh_from_db()
        frente = ImagemBrinquedo.objects.get(brinquedo=m4, tipo="perfil")
        self.assertIn("brinquedao-modelo-4-perspectiva", frente.imagem.name)
        self.assertEqual(m4.imagem_brinquedo.name, frente.imagem.name)
        self.assertFalse(ImagemBrinquedo.objects.filter(brinquedo=m4, papel_na_capa="cena").exists())

    def test_modelo_5_da_black_friday(self):
        m5 = self.produto("Brinquedão Modelo 5",
                          "imagens_brinquedos/galeria/black-friday-2026-produto-brinquedao-modelo-5-06a744c6_rdzasg")
        self.rodar("--so", "Brinquedão Modelo 5")
        m5.refresh_from_db()
        galeria = galeria_publica(list(m5.imagens_brinquedo.all()), m5.adesivo_padrao_id)
        self.assertEqual([f.tipo for f in galeria], ["perfil", "tres_quartos"])
        self.assertIn("black-friday-2026-produto-brinquedao-modelo-5", galeria[1].imagem.name)
        with open(self.pasta / galeria[0].imagem.name, "rb") as subiu:
            self.assertEqual(subiu.read(), (MODELOS / "brinquedao-modelo-5" / "capa.webp").read_bytes())

    def test_o_3d_de_um_adesivo_so_so_ganha_o_papel(self):
        strike = self.produto("Strike Kids", "imagens_brinquedos/galeria/strike-kids-capa_t12zew")
        texto = self.rodar("--so", "Strike Kids")
        self.assertIn("a capa quadrada da frente agora é a capa em cena", texto)
        frente = ImagemBrinquedo.objects.get(brinquedo=strike, tipo="perfil")
        self.assertEqual(frente.papel_na_capa, "cena")
        self.assertEqual(ImagemBrinquedo.objects.filter(brinquedo=strike).count(), 1)  # nada subiu
        self.assertIn("a capa de antes voltou", self.rodar("--so", "Strike Kids", "--desfazer"))
        frente.refresh_from_db()
        self.assertEqual(frente.papel_na_capa, "")
        self.assertEqual(ImagemBrinquedo.objects.filter(brinquedo=strike).count(), 1)

    def test_a_capa_trocada_no_painel_fica(self):
        m4 = self.produto("Brinquedão Modelo 4", "imagens_brinquedos/da-equipe.png")
        self.assertIn("a frente foi trocada no painel", self.rodar("--so", "Brinquedão Modelo 4"))
        m4.refresh_from_db()
        self.assertEqual(m4.imagem_brinquedo.name, "imagens_brinquedos/da-equipe.png")
        self.assertEqual(ImagemBrinquedo.objects.filter(brinquedo=m4).count(), 1)

    def test_so_conferidos_os_sem_3d(self):
        self.produto("Air Game Premium", "imagens_brinquedos/galeria/cena-air-game-premium-5b0c34607d_hldeap", papel="cena")
        self.produto("Basquete Home", "imagens_brinquedos/basquetehome_s1antg")
        texto = self.rodar("--so", "Air Game Premium", "Basquete Home")
        self.assertIn("Air Game Premium: já está com a capa quadrada em cena", texto)
        self.assertIn("Basquete Home: SEM a capa quadrada em cena", texto)
        self.assertIn("só conferido", self.rodar("--so", "Air Game Premium", "--desfazer"))

    def test_um_erro_nao_para_os_outros_e_avisa_o_comando(self):
        m4 = self.produto("Brinquedão Modelo 4", "imagens_brinquedos/galeria/brinquedao-modelo-4-perspectiva_wjiskf")
        m5 = self.produto("Brinquedão Modelo 5", "imagens_brinquedos/galeria/brinquedao-modelo-5-salao_frente_q1w2e3")
        with mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            texto = self.rodar()
        self.assertIn('capas_em_cena --quadradas --so "Brinquedão Modelo 4"', texto)
        self.assertIn('capas_em_cena --quadradas --so "Brinquedão Modelo 5"', texto)
        for brinquedo in (m4, m5):  # nada pela metade
            self.assertEqual(list(ImagemBrinquedo.objects.filter(brinquedo=brinquedo).values_list("tipo", flat=True)), ["perfil"])

    def test_o_comando_lista_quando_o_nome_nao_existe(self):
        self.assertIn("Os da lista", self.rodar("--so", "Pebolim"))


@override_settings(IS_RENDER=False)
class MigracaoTests(_ComDisco):
    def test_so_dados_depois_da_0185(self):
        self.assertEqual(migracao_0186.Migration.dependencies, [("core", "0185_fotos_sem_fundo_fora_do_site")])
        self.assertEqual([type(op).__name__ for op in migracao_0186.Migration.operations], ["RunPython"])

    def test_fora_do_render_nao_faz_nada(self):
        m4 = self.produto("Brinquedão Modelo 4", "imagens_brinquedos/galeria/brinquedao-modelo-4-perspectiva_wjiskf")
        self.assertIsNone(capas_quadradas.no_deploy(apps_reais, None, avisar=lambda *_: None))
        self.assertFalse(ImagemBrinquedo.objects.filter(brinquedo=m4, papel_na_capa="cena").exists())

    def test_no_render_poe_as_capas_limpa_o_cache_e_de_novo_nao_muda_nada(self):
        m4 = self.produto("Brinquedão Modelo 4", "imagens_brinquedos/galeria/brinquedao-modelo-4-perspectiva_wjiskf")
        cache.set("um-card", "antigo")
        with override_settings(IS_RENDER=True):
            feito = capas_quadradas.no_deploy(apps_reais, None, avisar=lambda *_: None)
            self.assertIn("a capa agora é a quadrada", feito["Brinquedão Modelo 4"])
            self.assertIn("não está no catálogo", feito["Air Game Kids (Alienígenas)"])
            self.assertIsNone(cache.get("um-card"))
            estado = self.estado()
            feito = capas_quadradas.no_deploy(apps_reais, None, avisar=lambda *_: None)
        self.assertIn("já está", feito["Brinquedão Modelo 4"])
        self.assertEqual(self.estado(), estado)
        m4.refresh_from_db()
        self.assertIn("capa-brinquedao-modelo-4-", m4.imagem_catalogo.name)

    def test_o_deploy_nao_cai(self):
        avisos = []
        with override_settings(IS_RENDER=True), mock.patch.object(capas_quadradas, "rodar", side_effect=RuntimeError("banco fora")):
            self.assertIsNone(capas_quadradas.no_deploy(apps_reais, None, avisar=avisos.append))
        self.assertIn("python manage.py capas_em_cena --quadradas", " ".join(avisos))


class PainelTests(_ComDisco):
    """O aviso do painel: a capa fora do quadrado avisa, e grava assim mesmo."""

    URL = "/site/brinquedos/"

    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("capas", "c@exemplo.com", "x"))
        self.brinquedo = self.produto("Pebolim")

    @staticmethod
    def envio(nome, largura, altura):
        imagem = Image.merge("RGB", [Image.effect_noise((largura, altura), 90) for _ in range(3)])
        saida = BytesIO()
        imagem.save(saida, "PNG")
        return SimpleUploadedFile(nome, saida.getvalue(), content_type="image/png")

    def salvar(self, **arquivos):
        dados = {"action": "save", "id": self.brinquedo.pk, "nome_brinquedo": "Pebolim", "descricao": "x", **arquivos}
        resposta = self.client.post(self.URL, dados, **AJAX)
        self.assertLess(resposta.status_code, 400, resposta.content[:300])
        return json.loads(resposta.content)["msg"]

    def test_a_capa_larga_ganha_o_aviso_e_grava(self):
        msg = self.salvar(imagem_perfil=self.envio("larga.png", 160, 100))
        self.assertIn("A capa do card deve ser quadrada (1:1); esta é 1,6:1.", msg)
        self.brinquedo.refresh_from_db()
        self.assertIn("larga", self.brinquedo.imagem_brinquedo.name)  # um aviso, e não um bloqueio
        self.assertNotIn("quadrada", self.salvar(imagem_perfil=self.envio("quadrada.png", 120, 120)))
        self.assertNotIn("quadrada", self.salvar())  # sem foto nova: nada a dizer

    def test_a_frente_do_adesivo_tambem(self):
        padrao = self.brinquedo.adesivo_padrao
        resposta = self.client.post(self.URL, {"action": "adesivo_posicao", "id": self.brinquedo.pk, "adesivo_id": padrao.pk,
                                               "tipo": "perfil", "foto": self.envio("frente-alta.png", 75, 100)}, **AJAX)
        msg = json.loads(resposta.content)["msg"]
        self.assertIn("esta é 0,75:1", msg)
        self.assertTrue(ImagemBrinquedo.objects.filter(variante=padrao, tipo="perfil", imagem__contains="frente-alta").exists())
        # a outra posição não é a capa: sem aviso
        resposta = self.client.post(self.URL, {"action": "adesivo_posicao", "id": self.brinquedo.pk, "adesivo_id": padrao.pk,
                                               "tipo": "verso", "foto": self.envio("verso-largo.png", 160, 100)}, **AJAX)
        self.assertNotIn("quadrada", json.loads(resposta.content)["msg"])
