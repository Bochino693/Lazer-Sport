"""As categorias: as áreas que faltavam, os nomes em Maiúsculas e Minúsculas e as fotos novas.

O que estes testes protegem:

  * `nome_bonito` com os nomes do site no ar: o que está todo em caixa-alta
    vira Maiúsculas e Minúsculas (conectivos em minúsculas, siglas e
    unidades como se escrevem, acentos como estão); o que já tem as duas
    caixas fica como está;
  * a identidade não muda com o nome: a Arena reconhece cada máquina igual
    (o desenho, o jogo da casa, o objeto 3D) e os endereços são os mesmos;
  * a migração 0147: arruma os nomes das categorias, dos produtos, das peças
    e das categorias das peças; cria a Área Ninja com o Brinquedão Ninja;
    não cria a Área Baby sem produto ativo (nem com um desativado) e cria
    com um; põe nos Trampolins e no Espaço Esportivo Kids os produtos deles
    sem tirar ninguém; rodar de novo não muda nada; fora do Render não sobe
    foto; no Render sobe, e se a subida falhar o deploy segue;
  * as fotos: uma para cada categoria do site no ar e para as áreas novas,
    1200 × 900 (o 4:3 do card), leves; cada nome de categoria acha a sua;
  * o comando: sobe as fotos que faltam com a assinatura no nome, não sobe
    de novo o que já está, `--so`, `--simular`, `--refazer`, `--areas` e
    `--nomes`; duas categorias com a mesma foto ficam com arquivos
    diferentes (o campo é único);
  * a home mostra a categoria nova com a foto, e a página dela tem o texto
    da área.
"""

import importlib
import tempfile
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.apps import apps as apps_reais
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image, ImageStat

from . import arena, categorias_capas
from .models import Brinquedos, CategoriaPeca, CategoriasBrinquedos, PecasReposicao
from .nomes import nome_bonito, precisa_arrumar
from .views import CategoriasInfoView

migracao = importlib.import_module("core.migrations.0147_categorias_capas_e_nomes")
migracao_lugares = importlib.import_module("core.migrations.0149_categorias_nos_lugares")

#: Os nomes do site no ar (novembro de 2026) e como eles ficam.
NOMES_DO_SITE = {
    # categorias
    "BOLICHE VIRTUAL": "Boliche Virtual",
    # produtos
    "AIR GAME PREMIUM": "Air Game Premium",
    "AIR GAME HOME": "Air Game Home",
    "AIR GAME KIDS": "Air Game Kids",
    "BASQUETE HOME": "Basquete Home",
    "BASQUETE STREET": "Basquete Street",
    "MUNDO ZUMBI": "Mundo Zumbi",
    "PORSCHE SIMULADOR": "Porsche Simulador",
    "SIMULADOR MARIO KART": "Simulador Mario Kart",
    "PAC MAN": "Pac Man",
    "SHOW DE BOLA": "Show de Bola",
    "HOMEM ARANHA": "Homem Aranha",
    "HOMEM ARANHA KIDS": "Homem Aranha Kids",
    "TOMB RAIDER KIDS": "Tomb Raider Kids",
    "CORRIDA DOS MINIONS": "Corrida dos Minions",
    "PEGA TOUPEIRA": "Pega Toupeira",
    "MATRIX": "Matrix",
    "MATRIX ONE PIECE": "Matrix One Piece",
    "MULTI JOGOS RETRO": "Multi Jogos Retro",
    "MULTI JOGOS": "Multi Jogos",
    "GABINETE GAMES": "Gabinete Games",
    "PINBALL 32 POLEGADAS": "Pinball 32 Polegadas",
    "PINBALL 40 POLEGADAS": "Pinball 40 Polegadas",
    "PEBOLIM ELETRÔNICO": "Pebolim Eletrônico",
    "SONIC DASH": "Sonic Dash",
    "SONIC KIDS": "Sonic Kids",
    "SONIC RACING ALL-STARS": "Sonic Racing All-Stars",
    "SUBWAY SURFERS": "Subway Surfers",
    "FLAPPY BIRD": "Flappy Bird",
    "SPEED TURBO": "Speed Turbo",
    "PANTERA COR DE ROSA KIDS": "Pantera Cor de Rosa Kids",
    "MINIONS KIDS": "Minions Kids",
    "LABAMBA": "Labamba",
    "CARROSSEL SORVETINHO": "Carrossel Sorvetinho",
    "MINI RODA SORVETE": "Mini Roda Sorvete",
    "NERVO TESTE": "Nervo Teste",
    "BRINQUEDÃO MODELO 1": "Brinquedão Modelo 1",
    "LAZER SHOT": "Lazer Shot",
    "SIMULADOR DE CORRIDA TOP RACER": "Simulador de Corrida Top Racer",
    "BOB ESPONJA HAMMER KIDS": "Bob Esponja Hammer Kids",
    # peças de reposição
    "BONECO PARA MESA DE PEBOLIM": "Boneco para Mesa de Pebolim",
    "CABO HDMI": "Cabo HDMI",
    "CABO FLEXÍVEL": "Cabo Flexível",
    "CAIXA DE SOM MULTIMÍDIA KNUP RGB PULSE 2.0": "Caixa de Som Multimídia Knup RGB Pulse 2.0",
    "CONTROLE DE XBOX 360": "Controle de Xbox 360",
    "MANETA AIR GAME": "Maneta Air Game",
    "DISCO AIR GAME": "Disco Air Game",
    "MINI CAIXA DE SOM BLUETHOOT XTRAD POCKET": "Mini Caixa de Som Bluethoot Xtrad Pocket",
}

#: Os que já estão com as duas caixas: ficam como estão.
JA_BONS = (
    "Brinquedão", "Espaço Esportivo Kids", "Jogos de Mesa", "Mecânicos", "Trampolins",
    "Brinquedão Modelo 2", "Espaço Esportivo Modelo 1", "Strike Kids", "Trampolim de Enterrada",
    "Brinquedão Ninja", "Air Game Kids Alienígenas", "Basquete Street Quadrinhos",
    "Cabo de Fonte para Computador – Energia Segura e Confiável", "JoySticks", "Caixas de Som",
    "Reposição Brinquedos",
)

#: As categorias do site no ar (a home de novembro de 2026).
CATEGORIAS_DO_SITE = (
    "Brinquedão", "Competitivos", "Eletrônicos", "Espaço Esportivo Kids", "Espaço Kids Play", "Esportivos",
    "Famosos", "Fliperama", "Jogos de Mesa", "Kids", "Mecânicos", "Simuladores", "Trampolins", "BOLICHE VIRTUAL",
)


def _brinquedo(nome, **extra):
    dados = {"descricao": "x", "avaliacao": Decimal("5.00"), "voltz": "220V"}
    dados.update(extra)
    return Brinquedos.objects.create(nome_brinquedo=nome, **dados)


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    return mock.patch.object(CategoriasBrinquedos._meta.get_field("imagem_categoria"), "storage", FileSystemStorage(location=pasta))


def _mudo(*_args, **_kwargs):
    return None


class NomeBonitoTests(TestCase):
    def test_os_nomes_do_site_no_ar(self):
        for antes, depois in NOMES_DO_SITE.items():
            with self.subTest(antes):
                self.assertEqual(nome_bonito(antes), depois)

    def test_o_que_ja_tem_as_duas_caixas_fica(self):
        for nome in JA_BONS:
            with self.subTest(nome):
                self.assertFalse(precisa_arrumar(nome))
                self.assertEqual(nome_bonito(nome), nome)

    def test_conectivos_siglas_unidades_e_acentos(self):
        casos = {
            "PEÇAS E ACESSÓRIOS": "Peças e Acessórios",
            "DE VOLTA AO JOGO": "De Volta ao Jogo",  # o conectivo que abre o nome sobe
            "tipo a": "Tipo A",  # e o que fecha também
            "piscina de bolinhas": "Piscina de Bolinhas",  # tudo em minúsculas também é arrumado
            "CABO USB PARA TV LED": "Cabo USB para TV LED",
            "ÓCULOS VR 3D": "Óculos VR 3D",
            "FONTE 12V 5A 110V/220V": "Fonte 12V 5A 110V/220V",
            "PISCINA DE BOLINHAS 3X3": "Piscina de Bolinhas 3x3",
            "CAMA ELÁSTICA 3 X 3": "Cama Elástica 3 x 3",
            'TELA 32" FULL HD': 'Tela 32" Full HD',
            "STREET FIGHTER II": "Street Fighter II",
            "CONTROLE PLAYSTATION E XBOX": "Controle PlayStation e Xbox",
            "MÓDULO WI-FI": "Módulo Wi-Fi",
            "BONECO (PAR)": "Boneco (Par)",
            "CARRINHO F1  TURBO": "Carrinho F1 Turbo",
            "ÁREA BABY": "Área Baby",
        }
        for antes, depois in casos.items():
            with self.subTest(antes):
                self.assertEqual(nome_bonito(antes), depois)

    def test_vazio_e_none(self):
        self.assertIsNone(nome_bonito(None))
        self.assertEqual(nome_bonito(""), "")
        self.assertEqual(nome_bonito("X"), "X")  # uma letra só: não tem o que arrumar
        self.assertEqual(nome_bonito("360"), "360")

    def test_a_arena_reconhece_cada_maquina_igual(self):
        # o desenho 3D, o jogo da casa e o objeto 3D saem do nome: sem caixa, sem acento
        for antes, depois in NOMES_DO_SITE.items():
            with self.subTest(antes):
                self.assertEqual(arena.modelo_3d(antes), arena.modelo_3d(depois))
                self.assertEqual(arena.jogo_da_maquina(antes), arena.jogo_da_maquina(depois))
                self.assertEqual(arena.modelo_da_maquina(antes), arena.modelo_da_maquina(depois))


@override_settings(IS_RENDER=False)
class MigracaoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.trampolins = CategoriasBrinquedos.objects.create(nome_categoria="Trampolins", imagem_categoria="categorias/trampolim_abc")
        self.esportivo = CategoriasBrinquedos.objects.create(nome_categoria="Espaço Esportivo Kids", imagem_categoria="categorias/esp_abc")
        self.brinquedao = CategoriasBrinquedos.objects.create(nome_categoria="Brinquedão", imagem_categoria="categorias/brq_abc")
        self.boliche = CategoriasBrinquedos.objects.create(nome_categoria="BOLICHE VIRTUAL", imagem_categoria="categorias/BOLICHE_abc")
        self.modelo1 = _brinquedo("BRINQUEDÃO MODELO 1")
        self.modelo1.categorias_brinquedos.set([self.brinquedao, self.trampolins])
        self.ninja = _brinquedo("Brinquedão Ninja")
        self.ninja.categorias_brinquedos.set([self.brinquedao])
        self.enterrada = _brinquedo("Trampolim de Enterrada")
        self.espaco = _brinquedo("Espaço Esportivo Modelo 1")
        self.bv = _brinquedo("BOLICHE VIRTUAL")
        self.bv.categorias_brinquedos.set([self.boliche])
        self.desligado = _brinquedo("BABY PARK", ativo=False)
        self.peca = PecasReposicao.objects.create(nome="CABO HDMI", descricao_peca="x")
        self.cat_peca = CategoriaPeca.objects.create(nome_categoria_peca="CAIXAS DE SOM")
        self.boa = CategoriaPeca.objects.create(nome_categoria_peca="JoySticks")

    def rodar(self):
        migracao.migrar(apps_reais, None, avisar=_mudo)

    def test_nomes_viram_maiusculas_e_minusculas(self):
        self.rodar()
        self.boliche.refresh_from_db()
        self.bv.refresh_from_db()
        self.modelo1.refresh_from_db()
        self.assertEqual(self.boliche.nome_categoria, "Boliche Virtual")
        self.assertEqual(self.bv.nome_brinquedo, "Boliche Virtual")
        self.assertEqual(self.modelo1.nome_brinquedo, "Brinquedão Modelo 1")
        self.assertEqual(PecasReposicao.objects.get(pk=self.peca.pk).nome, "Cabo HDMI")
        self.assertEqual(CategoriaPeca.objects.get(pk=self.cat_peca.pk).nome_categoria_peca, "Caixas de Som")
        # o que já tinha as duas caixas fica como estava
        self.assertEqual(CategoriaPeca.objects.get(pk=self.boa.pk).nome_categoria_peca, "JoySticks")
        self.assertEqual(Brinquedos.objects.get(pk=self.ninja.pk).nome_brinquedo, "Brinquedão Ninja")

    def test_enderecos_e_fotos_nao_mudam_com_o_nome(self):
        antes = {
            "categoria": reverse("categoria_detalhe", args=[self.boliche.pk]),
            "brinquedo": reverse("brinquedo_detalhe", args=[self.bv.pk]),
            "imagem": self.boliche.imagem_categoria.name,
        }
        self.rodar()
        self.boliche.refresh_from_db()
        self.assertEqual(reverse("categoria_detalhe", args=[self.boliche.pk]), antes["categoria"])
        self.assertEqual(reverse("brinquedo_detalhe", args=[self.bv.pk]), antes["brinquedo"])
        # fora do Render a foto não muda
        self.assertEqual(self.boliche.imagem_categoria.name, antes["imagem"])
        self.assertEqual(self.client.get(antes["categoria"]).status_code, 200)

    def test_cria_a_area_ninja_com_o_brinquedao_ninja(self):
        self.rodar()
        ninja = CategoriasBrinquedos.objects.get(nome_categoria="Área Ninja")
        self.assertTrue(ninja.ativo)
        self.assertEqual(list(ninja.brinquedos.values_list("nome_brinquedo", flat=True)), ["Brinquedão Ninja"])
        # o Brinquedão Ninja continua no Brinquedão
        self.assertIn(self.brinquedao, self.ninja.categorias_brinquedos.all())
        # sem foto ainda (fora do Render): NULL, e não "" (o campo é único)
        self.assertFalse(ninja.imagem_categoria)
        self.assertIsNone(CategoriasBrinquedos.objects.filter(pk=ninja.pk).values_list("imagem_categoria", flat=True)[0])

    def test_area_baby_so_nasce_com_produto_ativo(self):
        self.rodar()
        self.assertFalse(CategoriasBrinquedos.objects.filter(nome_categoria="Área Baby").exists())
        # o produto desligado não conta
        self.assertFalse(self.desligado.categorias_brinquedos.exists())
        baby = _brinquedo("Área Baby Kids 5 x 4")
        self.rodar()
        # a segunda área sem foto convive com a primeira (as duas com NULL)
        categoria = CategoriasBrinquedos.objects.get(nome_categoria="Área Baby")
        self.assertEqual(list(categoria.brinquedos.all()), [baby])

    def test_produtos_de_area_entram_na_categoria_e_ninguem_sai(self):
        self.rodar()
        self.assertEqual(
            set(self.trampolins.brinquedos.values_list("nome_brinquedo", flat=True)),
            {"Brinquedão Modelo 1", "Trampolim de Enterrada"},
        )
        self.assertEqual(list(self.esportivo.brinquedos.all()), [self.espaco])
        self.assertEqual(set(self.modelo1.categorias_brinquedos.all()), {self.brinquedao, self.trampolins})

    def test_rodar_de_novo_nao_muda_nada(self):
        self.rodar()
        antes = (
            list(CategoriasBrinquedos.objects.order_by("id").values_list("id", "nome_categoria")),
            sorted(Brinquedos.categorias_brinquedos.through.objects.values_list("brinquedos_id", "categoriasbrinquedos_id")),
            list(Brinquedos.objects.order_by("id").values_list("nome_brinquedo", flat=True)),
        )
        self.rodar()
        depois = (
            list(CategoriasBrinquedos.objects.order_by("id").values_list("id", "nome_categoria")),
            sorted(Brinquedos.categorias_brinquedos.through.objects.values_list("brinquedos_id", "categoriasbrinquedos_id")),
            list(Brinquedos.objects.order_by("id").values_list("nome_brinquedo", flat=True)),
        )
        self.assertEqual(antes, depois)

    def test_no_render_sobe_as_fotos(self):
        with tempfile.TemporaryDirectory() as pasta, _disco(pasta), override_settings(IS_RENDER=True):
            self.rodar()
            for categoria in CategoriasBrinquedos.objects.all():
                chave = categorias_capas.chave_da_capa(categoria.nome_categoria)
                with self.subTest(categoria.nome_categoria):
                    self.assertIn(categorias_capas.nome_no_cadastro(chave), categoria.imagem_categoria.name)
                    self.assertTrue(categoria.imagem_categoria.storage.exists(categoria.imagem_categoria.name))

    def test_no_render_a_subida_que_falha_nao_derruba_o_deploy(self):
        avisos = []
        with override_settings(IS_RENDER=True), mock.patch.object(categorias_capas, "atualizar_capas", side_effect=OSError("sem rede")):
            migracao.migrar(apps_reais, None, avisar=avisos.append)
        self.assertIn("atualizar_capas_categorias", avisos[-1])
        # os nomes e as áreas ficaram
        self.assertTrue(CategoriasBrinquedos.objects.filter(nome_categoria="Área Ninja").exists())
        self.assertTrue(CategoriasBrinquedos.objects.filter(nome_categoria="Boliche Virtual").exists())


class FotosTests(TestCase):
    def test_cada_categoria_do_site_e_cada_area_tem_a_sua_foto(self):
        nomes = [nome_bonito(n) for n in CATEGORIAS_DO_SITE] + [nome for nome, _, _ in categorias_capas.AREAS]
        for nome in nomes:
            with self.subTest(nome):
                chave = categorias_capas.chave_da_capa(nome)
                self.assertIsNotNone(chave)
                self.assertTrue(categorias_capas.arquivo_da_capa(chave).exists())
        # e as variações do mesmo nome
        self.assertEqual(categorias_capas.chave_da_capa("BOLICHE VIRTUAL"), "boliche-virtual")
        self.assertEqual(categorias_capas.chave_da_capa("Brinquedões"), "brinquedao")
        self.assertEqual(categorias_capas.chave_da_capa("Area ninja"), "area-ninja")
        # "kids" sozinho não pega o "Espaço Kids Play"
        self.assertEqual(categorias_capas.chave_da_capa("Espaço Kids Play"), "espaco-kids-play")
        self.assertIsNone(categorias_capas.chave_da_capa("Infláveis"))

    def test_as_fotos_tem_o_corte_do_card_e_sao_leves(self):
        arquivos = sorted(categorias_capas.PASTA.glob("*.webp"))
        self.assertEqual({a.stem for a in arquivos}, {chave for chave, _ in categorias_capas.CAPAS})
        for arquivo in arquivos:
            with self.subTest(arquivo.name), Image.open(arquivo) as foto:
                self.assertEqual(foto.format, "WEBP")
                self.assertEqual(foto.size, (1200, 900))
                # o card baixa a foto inteira: até ~150 KB
                self.assertLessEqual(arquivo.stat().st_size, 150 * 1024)

    def test_as_fotos_estao_num_lugar_e_nao_no_branco(self):
        # "estão muito brancas, ponha em lugares": a foto tem cor (saturação
        # média), quase nada de branco estourado, e a borda não é um fundo liso
        for arquivo in sorted(categorias_capas.PASTA.glob("*.webp")):
            with self.subTest(arquivo.name), Image.open(arquivo) as foto:
                rgb = foto.convert("RGB")
                saturacao = ImageStat.Stat(rgb.convert("HSV").getchannel("S")).mean[0]
                self.assertGreater(saturacao, 50)
                brancos = sum(1 for p in rgb.resize((120, 90)).getdata() if min(p) > 235)
                self.assertLess(brancos / (120 * 90), 0.12)
                borda = [rgb.getpixel((x, y)) for x in range(0, 1200, 24) for y in (6, 893)]
                borda += [rgb.getpixel((x, y)) for y in range(0, 900, 24) for x in (6, 1193)]
                desvio = ImageStat.Stat(_imagem(borda)).stddev
                self.assertGreater(max(desvio), 12)
                # nem escura demais
                self.assertGreater(ImageStat.Stat(rgb.convert("L")).mean[0], 70)


def _imagem(pixels):
    """Uma imagem de uma linha com estes pixels (para a estatística da borda)."""
    imagem = Image.new("RGB", (len(pixels), 1))
    imagem.putdata(pixels)
    return imagem


@override_settings(IS_RENDER=False)
class MigracaoDosLugaresTests(TestCase):
    """A 0149: as fotos nos lugares sobem no Render, só as que mudaram."""

    def setUp(self):
        self.kids = CategoriasBrinquedos.objects.create(nome_categoria="Kids", imagem_categoria="categorias/kids_antiga")
        # a do Fliperama já está com a foto de hoje (a mesma assinatura): não sobe de novo
        self.fliper = CategoriasBrinquedos.objects.create(
            nome_categoria="Fliperama", imagem_categoria=f"categorias/{categorias_capas.nome_no_cadastro('fliperama')}_abc123",
        )

    def test_depende_da_0148(self):
        self.assertEqual(migracao_lugares.Migration.dependencies, [("core", "0148_air_game_kids_sem_tabua")])

    def test_fora_do_render_nao_faz_nada(self):
        self.assertIsNone(migracao_lugares.subir_fotos_no_deploy(apps_reais, None, avisar=_mudo))
        self.kids.refresh_from_db()
        self.assertEqual(self.kids.imagem_categoria.name, "categorias/kids_antiga")

    def test_no_render_sobe_so_o_que_mudou(self):
        with tempfile.TemporaryDirectory() as pasta, _disco(pasta), override_settings(IS_RENDER=True):
            resultado = migracao_lugares.subir_fotos_no_deploy(apps_reais, None, avisar=_mudo)
        self.assertEqual(resultado["trocadas"], ["Kids"])
        self.assertEqual(resultado["iguais"], ["Fliperama"])
        self.kids.refresh_from_db()
        self.fliper.refresh_from_db()
        self.assertIn(categorias_capas.nome_no_cadastro("kids"), self.kids.imagem_categoria.name)
        self.assertTrue(self.fliper.imagem_categoria.name.endswith("_abc123"))

    def test_no_render_a_subida_que_falha_nao_derruba_o_deploy(self):
        avisos = []
        with override_settings(IS_RENDER=True), mock.patch.object(categorias_capas, "atualizar_capas", side_effect=OSError("sem rede")):
            self.assertIsNone(migracao_lugares.subir_fotos_no_deploy(apps_reais, None, avisar=avisos.append))
        self.assertIn("atualizar_capas_categorias", avisos[-1])
        self.kids.refresh_from_db()
        self.assertEqual(self.kids.imagem_categoria.name, "categorias/kids_antiga")


class ComandoTests(TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        disco = _disco(self.pasta.name)
        disco.start()
        self.addCleanup(disco.stop)
        self.kids = CategoriasBrinquedos.objects.create(nome_categoria="Kids", imagem_categoria="categorias/kids_antiga")
        self.fliper = categorias_capas.criar_sem_foto(CategoriasBrinquedos, "Fliperama")
        self.outra = CategoriasBrinquedos.objects.create(nome_categoria="Infláveis", imagem_categoria="categorias/inflaveis")

    def chamar(self, *args):
        saida = StringIO()
        call_command("atualizar_capas_categorias", *args, stdout=saida)
        return saida.getvalue()

    def test_sobe_as_que_faltam_e_nao_sobe_de_novo(self):
        texto = self.chamar()
        self.assertIn("Fotos trocadas: 2", texto)
        for categoria, chave in ((self.kids, "kids"), (self.fliper, "fliperama")):
            categoria.refresh_from_db()
            self.assertIn(categorias_capas.nome_no_cadastro(chave), categoria.imagem_categoria.name)
        # a que não tem foto no repositório fica com a dela
        self.outra.refresh_from_db()
        self.assertEqual(self.outra.imagem_categoria.name, "categorias/inflaveis")
        nome = self.kids.imagem_categoria.name
        self.assertIn("Fotos trocadas: 0; já estavam certas: 2", self.chamar())
        self.kids.refresh_from_db()
        self.assertEqual(self.kids.imagem_categoria.name, nome)

    def test_so_simular_e_refazer(self):
        self.assertIn("Fotos subiriam: 2", self.chamar("--simular"))
        self.kids.refresh_from_db()
        self.assertEqual(self.kids.imagem_categoria.name, "categorias/kids_antiga")
        self.assertIn("Fotos trocadas: 1", self.chamar("--so", "kids"))
        self.fliper.refresh_from_db()
        self.assertFalse(self.fliper.imagem_categoria)
        self.kids.refresh_from_db()
        primeira = self.kids.imagem_categoria.name
        self.chamar("--so", "kids", "--refazer")
        self.kids.refresh_from_db()
        # subiu de novo: outro arquivo, com a mesma assinatura
        self.assertNotEqual(self.kids.imagem_categoria.name, primeira)
        self.assertIn(categorias_capas.nome_no_cadastro("kids"), self.kids.imagem_categoria.name)

    def test_duas_categorias_com_a_mesma_foto_ficam_com_arquivos_diferentes(self):
        outra_kids = categorias_capas.criar_sem_foto(CategoriasBrinquedos, "KIDS")
        self.chamar("--so", "kids")
        self.kids.refresh_from_db()
        outra_kids.refresh_from_db()
        self.assertTrue(self.kids.imagem_categoria.name and outra_kids.imagem_categoria.name)
        self.assertNotEqual(self.kids.imagem_categoria.name, outra_kids.imagem_categoria.name)

    def test_areas_e_nomes(self):
        _brinquedo("BRINQUEDÃO NINJA")
        texto = self.chamar("--areas", "--nomes")
        self.assertIn("Brinquedão Ninja", texto)
        ninja = CategoriasBrinquedos.objects.get(nome_categoria="Área Ninja")
        # nasceu já com a foto
        self.assertIn(categorias_capas.nome_no_cadastro("area-ninja"), ninja.imagem_categoria.name)
        self.assertEqual(list(ninja.brinquedos.values_list("nome_brinquedo", flat=True)), ["Brinquedão Ninja"])


@override_settings(HOME_CACHE_TTL=0)
class VitrineTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ninja = CategoriasBrinquedos.objects.create(nome_categoria="Área Ninja", imagem_categoria="categorias/area-ninja-0123456789")
        _brinquedo("Brinquedão Ninja", imagem_brinquedo="imagens_brinquedos/n.webp").categorias_brinquedos.set([self.ninja])

    def test_home_mostra_a_area_nova_com_a_foto(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn("Área Ninja", html)
        self.assertIn("categorias/area-ninja-0123456789", html)
        self.assertIn("1 brinquedo", html)

    def test_a_pagina_da_area_tem_o_texto_dela(self):
        view = CategoriasInfoView()
        self.assertEqual(view.vitrine_da_categoria(self.ninja)["icone"], "fa-person-running")
        self.assertEqual(view.vitrine_da_categoria(CategoriasBrinquedos(nome_categoria="Área Baby"))["icone"], "fa-baby")
        self.assertEqual(view.vitrine_da_categoria(CategoriasBrinquedos(nome_categoria="Trampolins"))["icone"], "fa-arrows-up-down")
        # o brinquedão continua com o dele
        self.assertEqual(view.vitrine_da_categoria(CategoriasBrinquedos(nome_categoria="Brinquedão"))["icone"], "fa-layer-group")
        resposta = self.client.get(reverse("categoria_detalhe", args=[self.ninja.pk]))
        self.assertContains(resposta, "Circuitos de obstáculos")
