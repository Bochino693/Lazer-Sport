"""O Air Game Hockey Espacial e o Basquete Street Quadrinhos: as máquinas de sempre com os adesivos novos.

O que estes testes protegem:

  * cada uma leva o SEU .glb para a Arena 3D e para a página do produto, pelo
    nome inteiro: o "Air Game Hockey" e o "Basquete Street" de antes não pegam
    o objeto novo; o .glb tem as medidas que a folha de adesivos dá (1,00 ×
    0,92 × 1,67 m e 2,70 × 1,00 × 2,40 m) e é leve; as fotos existem;
  * cada adesivo é a peça recortada da folha da fábrica: toda peça do
    pecas.json tem o arquivo em adesivos/ (do tamanho que o recorte achou),
    uma caixa no recortes.json e um material com a imagem (JPEG) dentro do
    .glb; as peças recortadas têm o contorno de verdade (formas.json), e não
    sobrou arte provisória;
  * o desenho é o da máquina (mesa de hockey, basquete) e a seção é "As
    máquinas que já fazíamos"; no "Monte seu projeto" é uma máquina, com o
    lugar de quem joga do tipo dela;
  * antes de estar no catálogo, o objeto já aparece na arena; cadastrado, o
    do catálogo toma o lugar (sem duplicar);
  * o comando cadastra COPIANDO a máquina de antes (preço, voltagem, loja,
    avaliação, medidas, categorias e tags), com a descrição da arte nova, as
    cinco fotos e o objeto 3D; sem a máquina de antes, entra como os outros
    modelos (as medidas daqui, a categoria pelo nome, fora da loja); rodar de
    novo não duplica e `--fotos` refaz a galeria;
  * a migração liga o objeto em todo lugar, só cadastra no Render e nunca
    derruba o deploy.
"""

import importlib
import json
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import mock

from django.apps import apps as apps_reais
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import arena, projeto3d
from .cadastro_modelos import CADASTROS, VARIANTES_DE_ADESIVO
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD, TagsBrinquedos
from .objetos_3d import ler_glb_do_site, ler_json_do_glb

migracao = importlib.import_module("core.migrations.0145_variantes_de_adesivo")

HOCKEY = "air-game-hockey-espacial"
BASQUETE = "basquete-street-quadrinhos"
#: id -> (nome, nome da máquina de antes, desenho, medidas do .glb: altura, largura, profundidade)
VARIANTES = {
    HOCKEY: ("Air Game Hockey Espacial", "Air Game Hockey", "hockey", [1.0, 0.92, 1.67]),
    BASQUETE: ("Basquete Street Quadrinhos", "Basquete Street", "basquete", [2.7, 1.0, 2.4]),
}
FERRAMENTAS = Path(settings.BASE_DIR) / "ferramentas" / "modelos3d"


def _glb(chave):
    return f"site/arena/modelos/{chave}.glb"


def _disco(pasta):
    """As fotos vão para uma pasta temporária, e não para o Cloudinary."""
    storage = FileSystemStorage(location=pasta)
    return (
        mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", storage),
        mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", storage),
    )


def _categoria(nome):
    return CategoriasBrinquedos.objects.create(nome_categoria=nome, imagem_categoria=f"categorias/{nome}.png")


def _maquinas_de_antes():
    """O Air Game Hockey e o Basquete Street do catálogo (com nomes escritos de outro jeito, como no site)."""
    mesas, esportes, eletronicos = _categoria("Mesas de jogo"), _categoria("Esportes"), _categoria("Eletrônicos")
    hockey = Brinquedos.objects.create(
        nome_brinquedo="AIR GAME HOCKEY", descricao="A mesa de air hockey.", valor_brinquedo=Decimal("3500.00"),
        avaliacao=Decimal("4.80"), exibir_na_loja=True, voltz="220v",
        altura_m=Decimal("1.00"), largura_m=Decimal("1.10"), profundidade_m=Decimal("2.10"),
    )
    hockey.categorias_brinquedos.set([mesas, eletronicos])
    hockey.tags.set([TagsBrinquedos.objects.create(nome_tags="air hockey")])
    basquete = Brinquedos.objects.create(
        nome_brinquedo="Basquete Street", descricao="O basquete de arcade.", valor_brinquedo=Decimal("9000.00"),
        avaliacao=Decimal("4.90"), exibir_na_loja=False, voltz="127v",
        altura_m=Decimal("2.70"), largura_m=Decimal("1.00"), profundidade_m=Decimal("2.40"),
    )
    basquete.categorias_brinquedos.set([esportes])
    return {HOCKEY: hockey, BASQUETE: basquete}


class ObjetoNaArenaTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_liga_pelo_nome_inteiro(self):
        for chave, (nome, antes, _desenho, _medidas) in VARIANTES.items():
            with self.subTest(chave):
                self.assertEqual(arena.modelo_da_maquina(nome)["id"], chave)
                self.assertEqual(arena.modelo_da_maquina(nome.upper())["id"], chave)
                # a máquina de antes continua sem objeto 3D (o adesivo dela é outro)
                self.assertIsNone(arena.modelo_da_maquina(antes))
                self.assertIsNone(arena.modelo_da_maquina(antes.upper()))

    def test_o_glb_tem_as_medidas_da_maquina_e_e_leve(self):
        for chave, (nome, _antes, _desenho, medidas) in VARIANTES.items():
            with self.subTest(chave):
                modelo = arena.modelo_da_maquina(nome)
                self.assertEqual(list(modelo["medidas"]), medidas)
                self.assertEqual(ler_glb_do_site(_glb(chave))["medidas"], medidas)
                # a Arena baixa o objeto inteiro: abaixo de 800 KB, como os outros
                self.assertLess(Path(finders.find(_glb(chave))).stat().st_size, 800 * 1024)
                for _, arquivo in modelo["fotos"]:
                    self.assertTrue(finders.find(modelo["pasta"] + arquivo), arquivo)
                for arquivo, _, _ in CADASTROS[chave]["fotos"]:
                    self.assertTrue((CADASTROS[chave]["pasta"] / arquivo).exists(), arquivo)
                # as medidas do cadastro (quando não há a máquina de antes) são as do .glb
                self.assertEqual([float(v) for v in CADASTROS[chave]["medidas"]], medidas)

    def test_cada_adesivo_e_uma_imagem_no_glb(self):
        for chave in VARIANTES:
            with self.subTest(chave):
                pasta = FERRAMENTAS / chave
                pecas = json.loads((pasta / "pecas.json").read_text(encoding="utf-8"))
                recortes = json.loads((pasta / "recortes.json").read_text(encoding="utf-8"))
                self.assertEqual(set(recortes["pecas"]), set(pecas))
                with open(finders.find(_glb(chave)), "rb") as arquivo:
                    dados = ler_json_do_glb(arquivo)
                materiais = {m.get("name"): m for m in dados["materials"]}
                for peca, info in pecas.items():
                    self.assertTrue((pasta / info["arquivo"]).exists(), info["arquivo"])
                    self.assertEqual(len(info["mm"]), 2)
                    textura = materiais[f"adesivo-{peca}"]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
                    imagem = dados["images"][dados["textures"][textura]["source"]]
                    self.assertEqual(imagem["mimeType"], "image/jpeg", peca)
                # as peças recortadas levam o contorno (as laterais)
                self.assertTrue(any("contorno" in info for info in pecas.values()))

    def test_toda_peca_sai_da_folha_de_adesivos(self):
        # a arte é a da folha da fábrica, recortada: cada peça tem a imagem do
        # tamanho que o recorte achou, e a peça recortada tem o contorno de
        # verdade (o polígono), que vira o contorno da placa no 3D
        from PIL import Image

        recortadas = {
            HOCKEY: {"lateral-esquerda", "lateral-direita"},
            BASQUETE: {"lateral-externa-esquerda", "lateral-externa-direita", "lateral-interna-esquerda",
                       "lateral-interna-direita", "testeira-frente", "testeira-fundo"},
        }
        for chave in VARIANTES:
            with self.subTest(chave):
                pasta = FERRAMENTAS / chave
                recortes = json.loads((pasta / "recortes.json").read_text(encoding="utf-8"))
                formas = json.loads((pasta / "formas.json").read_text(encoding="utf-8"))
                self.assertTrue((pasta / recortes["folha"]).exists(), recortes["folha"])
                self.assertEqual(set(formas), set(recortes["pecas"]))
                self.assertFalse((pasta / "desenhar_provisorios.py").exists())  # nada de arte provisória
                for peca, forma in formas.items():
                    with Image.open(pasta / "adesivos" / f"{peca}.png") as imagem:
                        self.assertEqual(list(imagem.size), forma["px"], peca)
                    self.assertEqual("contorno" in forma, peca in recortadas[chave], peca)
                    for u, v in forma.get("contorno", ()):
                        self.assertTrue(0 <= u <= 1 and 0 <= v <= 1, peca)
                    if "contorno" in forma:
                        self.assertGreaterEqual(len(forma["contorno"]), 6, peca)
        # a Frente do basquete dobra em três faixas (as linhas da folha)
        frente = json.loads((FERRAMENTAS / BASQUETE / "formas.json").read_text(encoding="utf-8"))["frente"]
        self.assertEqual(len(frente["dobras"]), 2)

    def test_desenho_e_secao_das_maquinas(self):
        for chave, (nome, _antes, desenho, _medidas) in VARIANTES.items():
            with self.subTest(chave):
                self.assertEqual(arena.modelo_3d(nome), desenho)
                self.assertEqual(arena.modelo_da_maquina(nome)["grupo"], "maquinas")

    def test_aparece_na_arena_antes_do_cadastro(self):
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5, voltz="220v")
        resposta = self.client.get(reverse("arena"))
        dados = {m["nome"]: m for m in resposta.context["arena_dados"]["maquinas"]}
        for chave, (nome, _antes, _desenho, medidas) in VARIANTES.items():
            with self.subTest(chave):
                exposto = dados[nome]
                self.assertIn(_glb(chave), exposto["modelo"])
                self.assertEqual(exposto["modelo_id"], chave)
                self.assertEqual((exposto["grupo"], exposto["reino"]), ("maquinas", False))
                self.assertEqual(exposto["medidas_modelo"], medidas)
                self.assertIn(f"{chave}/frente.webp", exposto["capa"])
        # o Air Game Hockey de antes segue sem objeto (fora da roda)
        self.assertNotIn("Air Game Hockey", dados)

    def test_cadastrado_toma_o_lugar_sem_duplicar(self):
        for nome, _antes, _desenho, _medidas in VARIANTES.values():
            Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=5, voltz="220v")
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        for chave, (nome, _antes, desenho, medidas) in VARIANTES.items():
            with self.subTest(chave):
                mesmos = [m for m in maquinas if m["nome"] == nome]
                self.assertEqual(len(mesmos), 1)
                self.assertIsInstance(mesmos[0]["id"], int)
                self.assertIn(f"{chave}.glb", mesmos[0]["modelo"])
                self.assertEqual((mesmos[0]["desenho"], mesmos[0]["grupo"]), (desenho, "maquinas"))
                self.assertEqual(mesmos[0]["medidas_modelo"], medidas)

    def test_a_pagina_do_produto_mostra_o_3d(self):
        for chave, (nome, _antes, _desenho, _medidas) in VARIANTES.items():
            with self.subTest(chave):
                brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=5, voltz="220v")
                resposta = self.client.get(reverse("brinquedo_detalhe", args=[brinquedo.pk]))
                self.assertContains(resposta, f'data-modelo="/static/{_glb(chave)}')

    def test_e_uma_maquina_no_monte_seu_projeto(self):
        itens = {i["id"]: i for i in projeto3d.catalogo()["itens"]}
        hockey = itens[f"modelo-{HOCKEY}"]
        self.assertEqual((hockey["tipo"], hockey["desenho"], hockey["medidas"]), ("maquina", "hockey", [1.0, 0.92, 1.67]))
        self.assertFalse(hockey["parede"])  # a mesa fica solta: joga-se nas duas cabeceiras
        basquete = itens[f"modelo-{BASQUETE}"]
        self.assertEqual((basquete["tipo"], basquete["desenho"], basquete["medidas"]), ("maquina", "basquete", [2.7, 1.0, 2.4]))
        self.assertTrue(basquete["parede"])
        self.assertIn(_glb(BASQUETE), basquete["modelo"])


class CadastroTests(TestCase):
    def _cadastrar(self, *args):
        saida = StringIO()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_variantes_adesivo", *args, stdout=saida)
        return saida.getvalue()

    def test_copia_a_maquina_de_antes(self):
        antes = _maquinas_de_antes()
        saida = self._cadastrar()
        self.assertIn("Copiado de AIR GAME HOCKEY", saida)
        self.assertIn("Copiado de Basquete Street", saida)
        for chave, (nome, _antes, _desenho, _medidas) in VARIANTES.items():
            with self.subTest(chave):
                base = antes[chave]
                novo = Brinquedos.objects.get(nome_brinquedo=nome)
                for campo in ("valor_brinquedo", "avaliacao", "exibir_na_loja", "voltz", "altura_m", "largura_m", "profundidade_m"):
                    self.assertEqual(getattr(novo, campo), getattr(base, campo), campo)
                self.assertEqual(novo.disponivel_na_loja, base.disponivel_na_loja)
                self.assertEqual(set(novo.categorias_brinquedos.all()), set(base.categorias_brinquedos.all()))
                self.assertEqual(set(novo.tags.all()), set(base.tags.all()))
                self.assertTrue(novo.ativo)
                # a descrição é a da arte nova (e não a da máquina de antes)
                self.assertEqual(novo.descricao, CADASTROS[chave]["descricao"])
                self.assertEqual(
                    list(novo.imagens_brinquedo.order_by("ordem").values_list("tipo", flat=True)),
                    ["perfil", "lado_esquerdo", "lado_direito", "verso", None],
                )
                self.assertIn(f"{chave}-frente", novo.imagem_brinquedo.name)
                objeto = novo.objeto_3d
                self.assertEqual((objeto.codigo, objeto.arquivo_estatico), (chave, _glb(chave)))
                self.assertEqual(objeto.medidas, VARIANTES[chave][3])
                # a máquina de antes fica como estava, sem objeto 3D
                self.assertFalse(ObjetoTresD.objects.filter(brinquedo=base).exists())
                self.assertEqual(base.imagens_brinquedo.count(), 0)
        self.assertIn("HOCKEY KIDS", Brinquedos.objects.get(nome_brinquedo="Air Game Hockey Espacial").descricao)
        self.assertIn("quadrinhos", Brinquedos.objects.get(nome_brinquedo="Basquete Street Quadrinhos").descricao)

    def test_rodar_de_novo_nao_duplica_e_fotos_refaz_a_galeria(self):
        _maquinas_de_antes()
        self._cadastrar()
        self.assertIn("Objeto 3D ligado", self._cadastrar())  # já no catálogo: só confere a ligação
        self._cadastrar("--fotos")
        for nome, _antes, _desenho, _medidas in VARIANTES.values():
            self.assertEqual(Brinquedos.objects.filter(nome_brinquedo=nome).count(), 1)
            self.assertEqual(Brinquedos.objects.get(nome_brinquedo=nome).imagens_brinquedo.count(), 5)
        self.assertEqual(ObjetoTresD.objects.count(), 2)
        self.assertEqual(Brinquedos.objects.count(), 4)

    def test_sem_a_maquina_de_antes_entra_como_os_outros(self):
        _categoria("Eletrônicos")
        _categoria("Brinquedões")
        saida = self._cadastrar("--so", BASQUETE)
        self.assertIn("Basquete Street não está no catálogo", saida)
        novo = Brinquedos.objects.get(nome_brinquedo="Basquete Street Quadrinhos")
        self.assertEqual((novo.altura_m, novo.largura_m, novo.profundidade_m), (Decimal("2.70"), Decimal("1.00"), Decimal("2.40")))
        self.assertEqual([c.nome_categoria for c in novo.categorias_brinquedos.all()], ["Eletrônicos"])
        self.assertEqual((novo.valor_brinquedo, novo.exibir_na_loja, novo.voltz), (None, False, ""))
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo="Air Game Hockey Espacial").exists())

    def test_a_maquina_de_antes_ativa_vem_antes_da_desativada(self):
        Brinquedos.objects.create(nome_brinquedo="Basquete Street", descricao="velho", avaliacao=3, voltz="110v",
                                  valor_brinquedo=Decimal("1.00"), ativo=False)
        Brinquedos.objects.create(nome_brinquedo="BASQUETE STREET", descricao="o do site", avaliacao=5, voltz="220v",
                                  valor_brinquedo=Decimal("9000.00"))
        self._cadastrar("--so", BASQUETE)
        novo = Brinquedos.objects.get(nome_brinquedo="Basquete Street Quadrinhos")
        self.assertEqual((novo.valor_brinquedo, novo.voltz), (Decimal("9000.00"), "220v"))

    def test_ja_no_catalogo_so_ganha_o_objeto(self):
        do_painel = Brinquedos.objects.create(nome_brinquedo="Air Game Hockey Espacial (mesa)", descricao="do painel",
                                              avaliacao=5, voltz="220v")
        call_command("cadastrar_variantes_adesivo", "--so", HOCKEY, stdout=StringIO())
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(do_painel.imagens_brinquedo.count(), 0)
        self.assertEqual(do_painel.objeto_3d.codigo, HOCKEY)

    def test_as_duas_estao_no_cadastrar_modelo_3d(self):
        self.assertEqual(set(VARIANTES_DE_ADESIVO), set(VARIANTES))
        for chave in VARIANTES:
            self.assertEqual(CADASTROS[chave]["objeto_3d"], _glb(chave))


class MigracaoTests(TestCase):
    def _rodar(self):
        migracao.Migration.operations[0].code(apps_reais, None)

    def test_so_cadastra_no_render_e_nao_derruba_o_deploy(self):
        self.assertEqual(migracao.Migration.dependencies, [("core", "0144_fotos_do_espaco")])
        antes = _maquinas_de_antes()
        # fora do Render (computador, testes) não cadastra nada
        self._rodar()
        self.assertEqual(Brinquedos.objects.count(), 2)
        # no Render, com o Cloudinary fora do ar: avisa e segue, sem cadastro pela metade
        with override_settings(IS_RENDER=True), \
                mock.patch.object(ImagemBrinquedo._meta.get_field("imagem").storage, "save", side_effect=OSError("sem rede")), \
                mock.patch("builtins.print") as aviso:
            self._rodar()
        avisos = " ".join(chamada[0][0] for chamada in aviso.call_args_list)
        for chave in VARIANTES:
            self.assertIn(f"cadastrar_modelo_3d {chave}", avisos)
        self.assertEqual(Brinquedos.objects.count(), 2)
        self.assertFalse(ObjetoTresD.objects.exists())
        # no Render, com tudo funcionando: cadastra copiando a máquina de antes, com as fotos e o objeto 3D
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True), mock.patch("builtins.print"):
                self._rodar()
        for chave, (nome, _antes, _desenho, _medidas) in VARIANTES.items():
            novo = Brinquedos.objects.get(nome_brinquedo=nome)
            self.assertEqual(novo.imagens_brinquedo.count(), 5)
            self.assertEqual(novo.objeto_3d.codigo, chave)
            self.assertEqual((novo.valor_brinquedo, novo.voltz), (antes[chave].valor_brinquedo, antes[chave].voltz))

    def test_liga_o_que_ja_esta_no_catalogo_em_todo_lugar(self):
        ja = Brinquedos.objects.create(nome_brinquedo="Basquete Street Quadrinhos", descricao="x", avaliacao=5, voltz="")
        self._rodar()
        self.assertEqual(ja.objeto_3d.codigo, BASQUETE)
        self.assertEqual(Brinquedos.objects.count(), 1)
