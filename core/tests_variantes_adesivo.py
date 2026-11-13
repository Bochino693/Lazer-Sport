"""O Air Game Kids Alienígenas e o Basquete Home Quadrinhos: as máquinas de sempre com os adesivos novos.

O que estes testes protegem:

  * cada uma leva o SEU .glb para a Arena 3D e para a página do produto, pelo
    nome inteiro: o "Air Game Kids" e o "Basquete Home" de antes (nem o Air
    Game Hockey nem o Basquete Street) não pegam o objeto novo; o .glb tem as medidas que a folha de
    adesivos dá na altura da máquina (0,90 × 0,86 × 1,51 m e 2,70 × 1,00 ×
    2,40 m) e é leve; as fotos existem;
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
    derruba o deploy;
  * a 0146: o "Air Game Hockey Espacial" que a 0145 cadastrou vira o Air Game
    Kids Alienígenas (o nome, a descrição, os campos do Air Game Kids, as
    descrições das fotos e o objeto 3D no .glb novo), em todo lugar; no
    Render, as fotos que o cadastro subiu são refeitas; fora isso, como a
    0145; rodar de novo não faz nada. A chave antiga ainda vale no comando;
  * o que a cliente pediu, conferido com as máquinas de verdade: no basquete,
    a bola das laterais VAZADA (os gomos brancos da folha são furos abertos,
    sem grade), a PRANCHA inclinada que devolve a bola até a chapa de parada
    na frente, com as bolas, sem a caixa preta em cima do teto, e as peças de
    máquina da foto (o moedeiro, o neon, o placar, o Start, a estrutura de
    tubo e os pés); no Air Game, a fita de LED na borda, a régua e a borda
    pretas e o placar.
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
from .cadastro_modelos import APELIDOS, CADASTROS, VARIANTES_DE_ADESIVO
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD, TagsBrinquedos
from .objetos_3d import ler_glb_do_site, ler_json_do_glb, medidas_do_glb

migracao = importlib.import_module("core.migrations.0145_variantes_de_adesivo")
migracao_0146 = importlib.import_module("core.migrations.0146_air_game_kids_alienigenas")

HOCKEY = "air-game-kids-alienigenas"
BASQUETE = "basquete-street-quadrinhos"
#: o id e o nome de antes do hockey (até a 0146)
HOCKEY_ANTES, NOME_ANTES = "air-game-hockey-espacial", "Air Game Hockey Espacial"
#: id -> (nome, nome da máquina de antes, desenho, medidas do .glb: altura, largura, profundidade)
VARIANTES = {
    HOCKEY: ("Air Game Kids Alienígenas", "Air Game Kids", "hockey", [0.9, 0.86, 1.51]),
    BASQUETE: ("Basquete Home Quadrinhos", "Basquete Home", "basquete", [2.7, 1.0, 2.4]),
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
    """O Air Game Kids e o Basquete Home do catálogo (com nomes escritos de outro jeito, como no site)."""
    mesas, esportes, eletronicos = _categoria("Mesas de jogo"), _categoria("Esportes"), _categoria("Eletrônicos")
    hockey = Brinquedos.objects.create(
        nome_brinquedo="AIR GAME KIDS", descricao="A mesa de air hockey infantil.", valor_brinquedo=Decimal("2800.00"),
        avaliacao=Decimal("4.70"), exibir_na_loja=True, voltz="220v",
        altura_m=Decimal("0.90"), largura_m=Decimal("0.86"), profundidade_m=Decimal("1.50"),
    )
    hockey.categorias_brinquedos.set([mesas, eletronicos])
    hockey.tags.set([TagsBrinquedos.objects.create(nome_tags="air hockey kids")])
    basquete = Brinquedos.objects.create(
        nome_brinquedo="Basquete Home", descricao="O basquete de arcade.", valor_brinquedo=Decimal("9000.00"),
        avaliacao=Decimal("4.90"), exibir_na_loja=False, voltz="127v",
        altura_m=Decimal("2.70"), largura_m=Decimal("1.00"), profundidade_m=Decimal("2.40"),
    )
    basquete.categorias_brinquedos.set([esportes])
    return {HOCKEY: hockey, BASQUETE: basquete}


def _air_game_hockey():
    """O Air Game Hockey do catálogo: a mesa grande, que a 0145 copiava (e que não é a base de hoje)."""
    hockey = Brinquedos.objects.create(
        nome_brinquedo="AIR GAME HOCKEY", descricao="A mesa de air hockey.", valor_brinquedo=Decimal("3500.00"),
        avaliacao=Decimal("4.80"), exibir_na_loja=False, voltz="127v",
        altura_m=Decimal("1.00"), largura_m=Decimal("1.10"), profundidade_m=Decimal("2.10"),
    )
    hockey.categorias_brinquedos.set([_categoria("Mesas grandes")])
    hockey.tags.set([TagsBrinquedos.objects.create(nome_tags="air hockey")])
    return hockey


def _da_0145(base_antiga, prefixo=HOCKEY_ANTES):
    """O "Air Game Hockey Espacial" como a 0145 cadastrou: copiando o Air Game Hockey, com o 3D de antes.

    `prefixo` é o começo do nome das fotos: o da chave antiga, as que o
    cadastro subiu; outro, as de alguém, pelo painel.
    """
    velho = Brinquedos.objects.create(
        nome_brinquedo=NOME_ANTES, descricao="O Air Game Hockey Espacial é o Air Game Hockey com o espaço.",
        valor_brinquedo=base_antiga.valor_brinquedo, avaliacao=base_antiga.avaliacao,
        exibir_na_loja=base_antiga.exibir_na_loja, voltz=base_antiga.voltz,
        altura_m=base_antiga.altura_m, largura_m=base_antiga.largura_m, profundidade_m=base_antiga.profundidade_m,
        imagem_brinquedo=f"brinquedos/{prefixo}-frente.webp",
    )
    velho.categorias_brinquedos.set(base_antiga.categorias_brinquedos.all())
    velho.tags.set(base_antiga.tags.all())
    for ordem, (tipo, texto) in enumerate((
        ("perfil", "Air Game Hockey Espacial: a mesa de air hockey com o HOCKEY KIDS"),
        ("lado_esquerdo", "Air Game Hockey Espacial pelo lado esquerdo"),
    ), start=1):
        ImagemBrinquedo.objects.create(brinquedo=velho, tipo=tipo, ordem=ordem, texto_alternativo=texto,
                                       imagem=f"brinquedos/{prefixo}-{ordem}.webp")
    ObjetoTresD.objects.create(brinquedo=velho, arquivo_estatico=_glb(HOCKEY_ANTES), codigo=HOCKEY_ANTES,
                               medidas=[1.0, 0.92, 1.67])
    return velho


def _glb_do_site(chave):
    with open(finders.find(_glb(chave)), "rb") as arquivo:
        return ler_json_do_glb(arquivo)


def _medidas_do_material(dados, material):
    """[altura, largura, profundidade] só das malhas de um material do .glb (o resto sai do JSON)."""
    indice = next(i for i, m in enumerate(dados["materials"]) if m.get("name") == material)
    copia = json.loads(json.dumps(dados))
    for malha in copia["meshes"]:
        malha["primitives"] = [p for p in malha["primitives"] if p.get("material") == indice]
    return medidas_do_glb(copia)


class PecasDeVerdadeTests(TestCase):
    """O que a cliente apontou no 3D, conferido com as máquinas de verdade (as fotos do catálogo)."""

    def test_a_bola_das_laterais_do_basquete_e_vazada(self):
        formas = json.loads((FERRAMENTAS / BASQUETE / "formas.json").read_text(encoding="utf-8"))
        recortes = json.loads((FERRAMENTAS / BASQUETE / "recortes.json").read_text(encoding="utf-8"))["pecas"]
        for lado in ("esquerda", "direita"):
            with self.subTest(lado):
                peca = f"lateral-externa-{lado}"
                furos = formas[peca].get("furos", [])
                self.assertEqual(len(furos), 8)  # os oito gomos brancos da bola
                x0, y0, x1, y1 = recortes[peca]["furos"]["caixa"]
                for furo in furos:
                    self.assertGreaterEqual(len(furo), 6)
                    self.assertTrue(all(x0 <= u <= x1 and y0 <= v <= y1 for u, v in furo))
                # (o balão BASKETBALL, branco, embaixo, não é furo)
                self.assertLess(max(v for f in furos for _, v in f), 0.6)
        materiais = {m["name"] for m in _glb_do_site(BASQUETE)["materials"]}
        self.assertNotIn("rede-de-protecao", materiais)  # os furos ficam abertos, sem grade (pedido da cliente)

    def test_a_prancha_do_basquete_e_a_rampa_que_devolve_a_bola(self):
        dados = _glb_do_site(BASQUETE)
        altura, largura, comprimento = _medidas_do_material(dados, "adesivo-prancha")
        # inclinada: sobe uns 40 cm do console ao fundo da cesta (no chão, deitada, seria 0)
        self.assertGreater(altura, 0.3)
        self.assertLess(altura, 0.6)
        # a pista entre as laterais de MDF de 25 mm (LEIA-ME V10, seção 92): 1,00 m - 2 x 26 mm
        self.assertAlmostEqual(largura, 0.946, delta=0.01)
        self.assertGreater(comprimento, 2.0)
        materiais = {m["name"] for m in dados["materials"]}
        self.assertIn("chapa-de-parada", materiais)  # onde a bola para, ao alcance de quem joga
        self.assertIn("bolas", materiais)

    def test_o_basquete_tem_as_pecas_de_maquina_da_foto(self):
        materiais = {m["name"] for m in _glb_do_site(BASQUETE)["materials"]}
        for nome in ("porta-do-moedeiro", "moedeiro", "neon-roxo", "placar", "botao-start", "estrutura-tubo-preto",
                     "pes-niveladores", "aro", "rede-da-cesta"):
            self.assertIn(nome, materiais)
        # nada de caixa preta: as peças pretas são as chapas, sem a caixa de cima entre o teto e a testeira
        montar = (FERRAMENTAS / BASQUETE / "montar.js").read_text(encoding="utf-8")
        self.assertNotIn("a caixa de cima", montar)

    def test_o_air_game_tem_o_led_a_regua_e_o_placar(self):
        dados = _glb_do_site(HOCKEY)
        materiais = {m["name"]: m for m in dados["materials"]}
        for nome in ("fita-de-led", "placar", "digitos-do-placar", "borda"):
            self.assertIn(nome, materiais)
        # a régua e a borda são pretas, como na mesa
        cor = materiais["borda"]["pbrMetallicRoughness"].get("baseColorFactor", [1, 1, 1, 1])
        self.assertLess(max(cor[:3]), 0.05)
        # a fita de LED corre pela borda das laterais inteiras (o comprimento e a altura da mesa)
        altura, _largura, comprimento = _medidas_do_material(dados, "fita-de-led")
        self.assertGreater(altura, 0.8)
        self.assertGreater(comprimento, 1.45)


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
        # nem o Air Game Hockey (a mesa grande) nem o Basquete Street (a estrutura aberta com a rede);
        # o nome de antes (o da 0145; o do basquete até a seção 72) ainda liga o novo
        self.assertIsNone(arena.modelo_da_maquina("AIR GAME HOCKEY"))
        self.assertIsNone(arena.modelo_da_maquina("Basquete Street"))
        self.assertEqual(arena.modelo_da_maquina("Basquete Street Quadrinhos")["id"], BASQUETE)
        self.assertEqual(arena.modelo_da_maquina(NOME_ANTES)["id"], HOCKEY)
        self.assertFalse(finders.find(_glb(HOCKEY_ANTES)))  # o .glb de antes não existe mais

    def test_o_glb_tem_as_medidas_da_maquina_e_e_leve(self):
        for chave, (nome, _antes, _desenho, medidas) in VARIANTES.items():
            with self.subTest(chave):
                modelo = arena.modelo_da_maquina(nome)
                self.assertEqual(list(modelo["medidas"]), medidas)
                self.assertEqual(ler_glb_do_site(_glb(chave))["medidas"], medidas)
                # a Arena baixa o objeto inteiro: em alta definição (os adesivos em 2048 px), até 4 MB
                self.assertLess(Path(finders.find(_glb(chave))).stat().st_size, 4 * 1024 * 1024)
                for _, arquivo in modelo["fotos"]:
                    self.assertTrue(finders.find(modelo["pasta"] + arquivo), arquivo)
                for arquivo, _, _ in CADASTROS[chave]["fotos"]:
                    self.assertTrue((CADASTROS[chave]["pasta"] / arquivo).exists(), arquivo)
                # as medidas do cadastro (quando não há a máquina de antes) são as do .glb; as
                # do Air Game Kids são as do catálogo (0,86 m de largura: o 3D também, com as laterais de MDF grosso)
                for cadastro, do_glb in zip(CADASTROS[chave]["medidas"], medidas):
                    self.assertAlmostEqual(float(cadastro), do_glb, delta=0.035)
        self.assertEqual(CADASTROS[HOCKEY]["medidas"], ("0.90", "0.86", "1.50"))

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
        self.assertEqual((hockey["tipo"], hockey["desenho"], hockey["medidas"]), ("maquina", "hockey", [0.9, 0.86, 1.51]))
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
        self.assertIn("Copiado de AIR GAME KIDS", saida)
        self.assertIn("Copiado de Basquete Home", saida)
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
                # as posições do cadastro (LEIA-ME 72: a frente em 3/4 e o tampo de cima também são posições)
                self.assertEqual(
                    list(novo.imagens_brinquedo.order_by("ordem").values_list("tipo", flat=True)),
                    [tipo for _arquivo, tipo, _texto in CADASTROS[chave]["fotos"]],
                )
                self.assertEqual([tipo for _arquivo, tipo, _texto in CADASTROS[chave]["fotos"]][:5],
                                 ["perfil", "tres_quartos", "lado_esquerdo", "lado_direito", "verso"])
                # a capa (o card) é a cena da 0153; a frente de antes fica na galeria, sem tipo
                self.assertIn(f"{chave}-capa", novo.imagem_brinquedo.name)
                objeto = novo.objeto_3d
                self.assertEqual((objeto.codigo, objeto.arquivo_estatico), (chave, _glb(chave)))
                self.assertEqual(objeto.medidas, VARIANTES[chave][3])
                # a máquina de antes fica como estava, sem objeto 3D
                self.assertFalse(ObjetoTresD.objects.filter(brinquedo=base).exists())
                self.assertEqual(base.imagens_brinquedo.count(), 0)
        self.assertIn("HOCKEY KIDS", Brinquedos.objects.get(nome_brinquedo="Air Game Kids Alienígenas").descricao)
        self.assertIn("quadrinhos", Brinquedos.objects.get(nome_brinquedo="Basquete Home Quadrinhos").descricao)

    def test_rodar_de_novo_nao_duplica_e_fotos_refaz_a_galeria(self):
        _maquinas_de_antes()
        self._cadastrar()
        self.assertIn("Objeto 3D ligado", self._cadastrar())  # já no catálogo: só confere a ligação
        self._cadastrar("--fotos")
        for nome, _antes, _desenho, _medidas in VARIANTES.values():
            self.assertEqual(Brinquedos.objects.filter(nome_brinquedo=nome).count(), 1)
            self.assertEqual(Brinquedos.objects.get(nome_brinquedo=nome).imagens_brinquedo.count(), 6)
        self.assertEqual(ObjetoTresD.objects.count(), 2)
        self.assertEqual(Brinquedos.objects.count(), 4)

    def test_sem_a_maquina_de_antes_entra_como_os_outros(self):
        _categoria("Eletrônicos")
        _categoria("Brinquedões")
        saida = self._cadastrar("--so", BASQUETE)
        self.assertIn("Basquete Home não está no catálogo", saida)
        novo = Brinquedos.objects.get(nome_brinquedo="Basquete Home Quadrinhos")
        self.assertEqual((novo.altura_m, novo.largura_m, novo.profundidade_m), (Decimal("2.70"), Decimal("1.00"), Decimal("2.40")))
        self.assertEqual([c.nome_categoria for c in novo.categorias_brinquedos.all()], ["Eletrônicos"])
        self.assertEqual((novo.valor_brinquedo, novo.exibir_na_loja, novo.voltz), (None, False, ""))
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo="Air Game Kids Alienígenas").exists())

    def test_a_maquina_de_antes_ativa_vem_antes_da_desativada(self):
        Brinquedos.objects.create(nome_brinquedo="Basquete Home", descricao="velho", avaliacao=3, voltz="110v",
                                  valor_brinquedo=Decimal("1.00"), ativo=False)
        Brinquedos.objects.create(nome_brinquedo="BASQUETE HOME", descricao="o do site", avaliacao=5, voltz="220v",
                                  valor_brinquedo=Decimal("9000.00"))
        self._cadastrar("--so", BASQUETE)
        novo = Brinquedos.objects.get(nome_brinquedo="Basquete Home Quadrinhos")
        self.assertEqual((novo.valor_brinquedo, novo.voltz), (Decimal("9000.00"), "220v"))

    def test_ja_no_catalogo_so_ganha_o_objeto(self):
        # pelo nome de hoje ou pelo de antes (um do painel que a 0145 ligou segue ligado, sem irmão)
        for nome in ("Air Game Kids Alienígenas (mesa)", "Air Game Hockey Espacial (mesa)"):
            with self.subTest(nome):
                Brinquedos.objects.all().delete()
                do_painel = Brinquedos.objects.create(nome_brinquedo=nome, descricao="do painel", avaliacao=5, voltz="220v")
                call_command("cadastrar_variantes_adesivo", "--so", HOCKEY, stdout=StringIO())
                self.assertEqual(Brinquedos.objects.count(), 1)
                self.assertEqual(do_painel.imagens_brinquedo.count(), 0)
                self.assertEqual(do_painel.objeto_3d.codigo, HOCKEY)
                self.assertEqual(Brinquedos.objects.get().nome_brinquedo, nome)

    def test_as_duas_estao_no_cadastrar_modelo_3d(self):
        self.assertEqual(set(VARIANTES_DE_ADESIVO), set(VARIANTES))
        for chave in VARIANTES:
            self.assertEqual(CADASTROS[chave]["objeto_3d"], _glb(chave))
        self.assertEqual(APELIDOS, {HOCKEY_ANTES: HOCKEY})

    def test_a_chave_de_antes_ainda_vale(self):
        _maquinas_de_antes()
        saida = StringIO()
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b:
                call_command("cadastrar_modelo_3d", HOCKEY_ANTES, stdout=saida)
                call_command("cadastrar_variantes_adesivo", "--so", HOCKEY_ANTES, HOCKEY, stdout=saida)
        novo = Brinquedos.objects.get(nome_brinquedo="Air Game Kids Alienígenas")
        self.assertEqual((novo.objeto_3d.codigo, novo.objeto_3d.arquivo_estatico), (HOCKEY, _glb(HOCKEY)))
        self.assertIn(f"{HOCKEY}-capa", novo.imagem_brinquedo.name)
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo=NOME_ANTES).exists())
        self.assertEqual(Brinquedos.objects.count(), 3)

    def test_o_comando_renomeia_o_que_sobrou_com_o_nome_de_antes(self):
        _maquinas_de_antes()
        velho = _da_0145(_air_game_hockey())
        saida = self._cadastrar("--so", HOCKEY)
        self.assertIn(f"Renomeado: {NOME_ANTES} -> Air Game Kids Alienígenas", saida)
        velho.refresh_from_db()
        self.assertEqual(velho.nome_brinquedo, "Air Game Kids Alienígenas")
        self.assertEqual(velho.objeto_3d.codigo, HOCKEY)
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo__startswith="Air Game Kids Alien").count(), 1)


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
            self.assertEqual(novo.imagens_brinquedo.count(), 6)
            self.assertEqual(novo.objeto_3d.codigo, chave)
            self.assertEqual((novo.valor_brinquedo, novo.voltz), (antes[chave].valor_brinquedo, antes[chave].voltz))

    def test_liga_o_que_ja_esta_no_catalogo_em_todo_lugar(self):
        ja = Brinquedos.objects.create(nome_brinquedo="Basquete Home Quadrinhos", descricao="x", avaliacao=5, voltz="")
        self._rodar()
        self.assertEqual(ja.objeto_3d.codigo, BASQUETE)
        self.assertEqual(Brinquedos.objects.count(), 1)


class Migracao0146Tests(TestCase):
    """O "Air Game Hockey Espacial" que a 0145 cadastrou vira o Air Game Kids Alienígenas."""

    NOME = "Air Game Kids Alienígenas"

    def _rodar(self, render=False, pasta=None):
        with mock.patch("builtins.print") as aviso:
            if render:
                a, b = _disco(pasta)
                with a, b, override_settings(IS_RENDER=True):
                    migracao_0146.Migration.operations[0].code(apps_reais, None)
            else:
                migracao_0146.Migration.operations[0].code(apps_reais, None)
        return " ".join(str(chamada[0][0]) for chamada in aviso.call_args_list)

    def test_vem_depois_da_0145(self):
        self.assertEqual(migracao_0146.Migration.dependencies, [("core", "0145_variantes_de_adesivo")])
        self.assertEqual(migracao.Migration.dependencies, [("core", "0144_fotos_do_espaco")])  # a 0145 fica como está

    def test_renomeia_e_copia_o_air_game_kids_em_todo_lugar(self):
        kids = _maquinas_de_antes()[HOCKEY]
        hockey = _air_game_hockey()
        velho = _da_0145(hockey)
        total = Brinquedos.objects.count()
        avisos = self._rodar()
        self.assertIn(f"Renomeado: {NOME_ANTES} -> {self.NOME}", avisos)
        novo = Brinquedos.objects.get(pk=velho.pk)
        self.assertEqual(novo.nome_brinquedo, self.NOME)
        self.assertEqual(novo.descricao, CADASTROS[HOCKEY]["descricao"])
        # os campos são os do Air Game Kids, e não mais os do Air Game Hockey
        for campo in ("valor_brinquedo", "avaliacao", "exibir_na_loja", "voltz", "altura_m", "largura_m", "profundidade_m"):
            self.assertEqual(getattr(novo, campo), getattr(kids, campo), campo)
        self.assertEqual((novo.altura_m, novo.largura_m, novo.profundidade_m),
                         (Decimal("0.90"), Decimal("0.86"), Decimal("1.50")))
        self.assertEqual(set(novo.categorias_brinquedos.all()), set(kids.categorias_brinquedos.all()))
        self.assertEqual(set(novo.tags.all()), set(kids.tags.all()))
        # as fotos ficam (fora do Render não sobe nada), com o nome novo na descrição
        textos = list(novo.imagens_brinquedo.order_by("ordem").values_list("texto_alternativo", flat=True))
        self.assertEqual(textos, [f"{self.NOME}: a mesa de air hockey com o HOCKEY KIDS", f"{self.NOME} pelo lado esquerdo"])
        self.assertIn(f"{HOCKEY_ANTES}-frente", novo.imagem_brinquedo.name)
        # o objeto 3D passa para o .glb e o código novos, com as medidas do .glb novo
        objeto = ObjetoTresD.objects.get(brinquedo=novo)
        self.assertEqual((objeto.codigo, objeto.arquivo_estatico), (HOCKEY, _glb(HOCKEY)))
        self.assertEqual(objeto.medidas, [0.9, 0.86, 1.51])
        self.assertTrue(finders.find(objeto.arquivo_estatico))
        # o Air Game Hockey e o Air Game Kids ficam como estavam, sem 3D; ninguém novo
        self.assertEqual(Brinquedos.objects.count(), total)
        self.assertEqual(ObjetoTresD.objects.count(), 1)
        hockey.refresh_from_db()
        self.assertEqual((hockey.nome_brinquedo, hockey.valor_brinquedo), ("AIR GAME HOCKEY", Decimal("3500.00")))
        self.assertFalse(ObjetoTresD.objects.filter(brinquedo__in=[hockey, kids]).exists())
        # na arena e na página, o objeto novo
        cache.clear()
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        mesmos = [m for m in maquinas if m["nome"] == self.NOME]
        self.assertEqual(len(mesmos), 1)
        self.assertEqual((mesmos[0]["id"], mesmos[0]["modelo_id"]), (novo.pk, HOCKEY))
        self.assertIn(f"{HOCKEY}.glb", mesmos[0]["modelo"])
        self.assertNotIn(NOME_ANTES, [m["nome"] for m in maquinas])
        # rodar de novo não faz nada
        self.assertNotIn("Renomeado", self._rodar())
        self.assertEqual(Brinquedos.objects.get(pk=velho.pk).nome_brinquedo, self.NOME)
        self.assertEqual(Brinquedos.objects.count(), total)

    def test_sem_o_air_game_kids_no_catalogo(self):
        velho = _da_0145(_air_game_hockey())
        avisos = self._rodar()
        self.assertIn("Air Game Kids não está no catálogo", avisos)
        novo = Brinquedos.objects.get(pk=velho.pk)
        self.assertEqual((novo.nome_brinquedo, novo.descricao), (self.NOME, CADASTROS[HOCKEY]["descricao"]))
        self.assertEqual((novo.altura_m, novo.largura_m, novo.profundidade_m),
                         (Decimal("0.90"), Decimal("0.86"), Decimal("1.50")))
        # o resto fica como estava (confira no painel)
        self.assertEqual((novo.valor_brinquedo, novo.voltz), (Decimal("3500.00"), "127v"))
        self.assertEqual(novo.objeto_3d.codigo, HOCKEY)

    def test_no_render_refaz_as_fotos_que_o_cadastro_subiu(self):
        _maquinas_de_antes()
        velho = _da_0145(_air_game_hockey())
        with tempfile.TemporaryDirectory() as pasta:
            self._rodar(render=True, pasta=pasta)
        novo = Brinquedos.objects.get(pk=velho.pk)
        self.assertEqual(novo.nome_brinquedo, self.NOME)
        self.assertIn(f"{HOCKEY}-capa", novo.imagem_brinquedo.name)
        self.assertEqual(
            list(novo.imagens_brinquedo.order_by("ordem").values_list("texto_alternativo", flat=True)),
            [texto for _, _, texto in CADASTROS[HOCKEY]["fotos"]],
        )
        self.assertEqual(novo.objeto_3d.codigo, HOCKEY)
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo=self.NOME).count(), 1)

    def test_no_render_as_fotos_do_painel_ficam(self):
        _maquinas_de_antes()
        velho = _da_0145(_air_game_hockey(), prefixo="foto-da-loja")
        with tempfile.TemporaryDirectory() as pasta:
            self._rodar(render=True, pasta=pasta)
        novo = Brinquedos.objects.get(pk=velho.pk)
        self.assertEqual(novo.imagem_brinquedo.name, "brinquedos/foto-da-loja-frente.webp")
        self.assertEqual(novo.imagens_brinquedo.count(), 2)
        self.assertTrue(all(t.startswith(self.NOME) for t in novo.imagens_brinquedo.values_list("texto_alternativo", flat=True)))

    def test_no_render_com_o_cloudinary_fora_avisa_e_segue(self):
        _maquinas_de_antes()
        velho = _da_0145(_air_game_hockey())
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            avisos = self._rodar(render=True, pasta=pasta)
        self.assertIn(f"cadastrar_variantes_adesivo --so {HOCKEY} --fotos", avisos)
        novo = Brinquedos.objects.get(pk=velho.pk)
        # renomeado e religado; as fotos de antes ficam até o comando refazer
        self.assertEqual((novo.nome_brinquedo, novo.objeto_3d.codigo), (self.NOME, HOCKEY))
        self.assertEqual(novo.imagens_brinquedo.count(), 2)
        self.assertIn(f"{HOCKEY_ANTES}-frente", novo.imagem_brinquedo.name)

    def test_com_o_nome_novo_ja_no_catalogo_nao_duplica_o_nome(self):
        ja = Brinquedos.objects.create(nome_brinquedo=self.NOME, descricao="do painel", avaliacao=5, voltz="220v")
        velho = _da_0145(_air_game_hockey())
        avisos = self._rodar()
        self.assertIn("ficou com o nome", avisos)
        self.assertEqual(Brinquedos.objects.get(pk=velho.pk).nome_brinquedo, NOME_ANTES)
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo=self.NOME).count(), 1)
        # os dois apontam para o .glb que existe (o de antes não existe mais)
        self.assertEqual(ObjetoTresD.objects.get(brinquedo=velho).arquivo_estatico, _glb(HOCKEY))
        self.assertEqual(ObjetoTresD.objects.get(brinquedo=ja).codigo, HOCKEY)

    def test_o_objeto_enviado_pelo_painel_fica(self):
        velho = _da_0145(_air_game_hockey())
        ObjetoTresD.objects.filter(brinquedo=velho).update(arquivo="objetos_3d/da-loja.glb", medidas=[1.2, 1.0, 2.0])
        self._rodar()
        objeto = ObjetoTresD.objects.get(brinquedo=velho)
        self.assertEqual((objeto.codigo, objeto.arquivo.name), (HOCKEY, "objetos_3d/da-loja.glb"))
        self.assertEqual(ObjetoTresD.objects.count(), 1)

    def test_como_a_0145_onde_ela_nao_cadastrou(self):
        # nada no catálogo: fora do Render não cadastra; no Render cadastra (copiando o Air Game Kids)
        kids = _maquinas_de_antes()[HOCKEY]
        self._rodar()
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo=self.NOME).exists())
        with tempfile.TemporaryDirectory() as pasta:
            self._rodar(render=True, pasta=pasta)
        novo = Brinquedos.objects.get(nome_brinquedo=self.NOME)
        self.assertEqual((novo.valor_brinquedo, novo.voltz), (kids.valor_brinquedo, kids.voltz))
        self.assertEqual(novo.imagens_brinquedo.count(), 6)
        self.assertEqual((novo.objeto_3d.codigo, novo.objeto_3d.arquivo_estatico), (HOCKEY, _glb(HOCKEY)))
        # num banco novo, a 0145 (pela chave antiga) já cadastra o novo, e a 0146 não duplica
        with tempfile.TemporaryDirectory() as pasta:
            a, b = _disco(pasta)
            with a, b, override_settings(IS_RENDER=True), mock.patch("builtins.print"):
                migracao.Migration.operations[0].code(apps_reais, None)
            self._rodar(render=True, pasta=pasta)
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo=self.NOME).count(), 1)
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo=NOME_ANTES).exists())


migracao_0148 = importlib.import_module("core.migrations.0148_air_game_kids_sem_tabua")


class SemTabuaTests(TestCase):
    """O Air Game Kids Alienígenas sem a tábua azul embaixo das cabeceiras (a 0148).

    A folha põe um retângulo azul liso embaixo da arte das cabeceiras; essa
    tábua não existe na mesa. O recorte a tira, a cabeceira é só a faixa da
    arte logo abaixo do tampo, e o campo continua na altura de sempre.
    """

    CABECEIRAS = ("lateral-esquerda-2", "lateral-direita-2")

    def test_o_adesivo_da_cabeceira_e_so_a_arte(self):
        from PIL import Image

        pasta = FERRAMENTAS / HOCKEY
        recortes = json.loads((pasta / "recortes.json").read_text(encoding="utf-8"))["pecas"]
        formas = json.loads((pasta / "formas.json").read_text(encoding="utf-8"))
        pecas = json.loads((pasta / "pecas.json").read_text(encoding="utf-8"))
        for peca in self.CABECEIRAS:
            with self.subTest(peca):
                self.assertTrue(recortes[peca].get("sem_faixa_lisa"))
                self.assertGreater(formas[peca].get("faixa_lisa_px", 0), 80)  # a faixa saiu
                with Image.open(pasta / "adesivos" / f"{peca}.png") as imagem:
                    imagem = imagem.convert("RGB")
                    w, h = imagem.size
                    # o pé do adesivo ainda é arte (o chão lunar, de muitas cores), e não o azul liso
                    cores = {tuple(c // 16 for c in imagem.getpixel((x, h - 4))) for x in range(0, w, 3)}
                    self.assertGreater(len(cores), 8)
                # no 3D, a cabeceira é a faixa da arte (~0,40 m), e não do chão ao campo (~0,75 m)
                largura, altura = pecas[peca]["mm"]
                self.assertEqual(largura, pecas["tampo"]["mm"][1])  # entre as laterais: a largura do tampo
                self.assertAlmostEqual(largura, 805, delta=10)  # (a fita de LED da borda conta na altura da mesa)
                self.assertLess(altura, 450)

    def test_vem_depois_da_0147(self):
        self.assertEqual(migracao_0148.Migration.dependencies, [("core", "0147_categorias_capas_e_nomes")])

    def _rodar(self, render, pasta=None):
        with mock.patch("core.categorias_capas.atualizar_capas") as capas, mock.patch("builtins.print") as aviso:
            if render:
                a, b = _disco(pasta)
                with a, b, override_settings(IS_RENDER=True):
                    migracao_0148.Migration.operations[0].code(apps_reais, None)
            else:
                migracao_0148.Migration.operations[0].code(apps_reais, None)
        return capas, " ".join(str(chamada[0][0]) for chamada in aviso.call_args_list)

    def _no_catalogo(self, foto):
        return Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids Alienígenas", descricao="x", avaliacao=5, voltz="220v",
            imagem_brinquedo=f"brinquedos/{foto}",
        )

    def test_fora_do_render_nao_faz_nada(self):
        brinquedo = self._no_catalogo(f"{HOCKEY}-frente.webp")
        capas, _ = self._rodar(render=False)
        capas.assert_not_called()
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, f"brinquedos/{HOCKEY}-frente.webp")
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 0)

    def test_no_render_refaz_as_fotos_do_cadastro_e_as_capas(self):
        brinquedo = self._no_catalogo(f"{HOCKEY}-frente.webp")
        with tempfile.TemporaryDirectory() as pasta:
            capas, _ = self._rodar(render=True, pasta=pasta)
        self.assertEqual(brinquedo.imagens_brinquedo.count(), len(CADASTROS[HOCKEY]["fotos"]))
        capas.assert_called_once()
        self.assertEqual(set(capas.call_args.kwargs["so"]),
                         {"espaco-kids-play", "eletronicos", "jogos-de-mesa", "competitivos", "famosos", "kids"})

    def test_no_render_as_fotos_do_painel_ficam(self):
        brinquedo = self._no_catalogo("foto-da-loja.webp")
        with tempfile.TemporaryDirectory() as pasta:
            capas, _ = self._rodar(render=True, pasta=pasta)
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, "brinquedos/foto-da-loja.webp")
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 0)
        capas.assert_called_once()

    def test_no_render_com_o_cloudinary_fora_avisa_e_segue(self):
        self._no_catalogo(f"{HOCKEY}-frente.webp")
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            _, avisos = self._rodar(render=True, pasta=pasta)
        self.assertIn(f"cadastrar_variantes_adesivo --so {HOCKEY} --fotos", avisos)


migracao_0150 = importlib.import_module("core.migrations.0150_basquete_quadrinhos_fotos")


class BasqueteFotosDeVerdadeTests(TestCase):
    """A 0150: o Basquete Home Quadrinhos que a 0145 cadastrou com as fotos da arte provisória.

    No Render, a galeria que o cadastro subiu vira a do 3D de hoje (a da
    folha de adesivos); a que veio do painel fica. Em todo lugar, o objeto 3D
    é religado ao .glb de hoje.
    """

    NOME = "Basquete Home Quadrinhos"

    def _rodar(self, render=False, pasta=None):
        with mock.patch("builtins.print") as aviso:
            if render:
                a, b = _disco(pasta)
                with a, b, override_settings(IS_RENDER=True):
                    migracao_0150.Migration.operations[0].code(apps_reais, None)
            else:
                migracao_0150.Migration.operations[0].code(apps_reais, None)
        return " ".join(str(chamada[0][0]) for chamada in aviso.call_args_list)

    def _da_0145(self, prefixo=BASQUETE):
        """Como a 0145 deixou: as fotos da versão provisória e o 3D com as medidas dela."""
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo=self.NOME, descricao="x", avaliacao=5, voltz="220v",
            imagem_brinquedo=f"brinquedos/{prefixo}-frente.webp",
        )
        for ordem, tipo in enumerate(("perfil", "lado_esquerdo"), start=1):
            ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo=tipo, ordem=ordem,
                                           texto_alternativo="provisória", imagem=f"brinquedos/{prefixo}-{ordem}.webp")
        ObjetoTresD.objects.create(brinquedo=brinquedo, arquivo_estatico=_glb(BASQUETE), codigo=BASQUETE,
                                   medidas=[1.0, 1.0, 1.0], cores=[])
        return brinquedo

    def test_vem_depois_da_0149(self):
        self.assertEqual(migracao_0150.Migration.dependencies, [("core", "0149_categorias_nos_lugares")])

    def test_fora_do_render_so_religa_o_3d(self):
        brinquedo = self._da_0145()
        self._rodar()
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 2)  # as fotos só mudam no Render
        objeto = ObjetoTresD.objects.get(brinquedo=brinquedo)
        self.assertEqual(objeto.medidas, VARIANTES[BASQUETE][3])  # as medidas do .glb de hoje

    def test_no_render_as_fotos_viram_as_da_arte_de_verdade(self):
        brinquedo = self._da_0145()
        with tempfile.TemporaryDirectory() as pasta:
            self._rodar(render=True, pasta=pasta)
        brinquedo.refresh_from_db()
        self.assertEqual(
            list(brinquedo.imagens_brinquedo.order_by("ordem").values_list("texto_alternativo", flat=True)),
            [texto for _, _, texto in CADASTROS[BASQUETE]["fotos"]],
        )
        self.assertIn(f"{BASQUETE}-capa", brinquedo.imagem_brinquedo.name)
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo=self.NOME).count(), 1)

    def test_no_render_as_fotos_do_painel_ficam(self):
        brinquedo = self._da_0145(prefixo="foto-da-loja")
        with tempfile.TemporaryDirectory() as pasta:
            self._rodar(render=True, pasta=pasta)
        brinquedo.refresh_from_db()
        self.assertEqual(brinquedo.imagem_brinquedo.name, "brinquedos/foto-da-loja-frente.webp")
        self.assertEqual(brinquedo.imagens_brinquedo.count(), 2)

    def test_no_render_com_o_cloudinary_fora_avisa_e_segue(self):
        self._da_0145()
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(FileSystemStorage, "save", side_effect=OSError("sem rede")):
            avisos = self._rodar(render=True, pasta=pasta)
        self.assertIn(f"cadastrar_variantes_adesivo --so {BASQUETE} --fotos", avisos)
