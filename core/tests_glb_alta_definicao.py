"""Os 3D das máquinas de adesivo em alta definição e no tamanho de verdade (LEIA-ME V10, seção 92).

O chefe do cliente: "o 3D está sem vida, apagado e sem definição" e "olha o
Basquete Home normal e o preto: a máquina diminuiu". O que estes testes protegem:

  * O TAMANHO: cada .glb (lido como o site lê: o JSON de dentro e o min/max
    das posições, com o giro e a escala dos nós) tem a altura, a largura e a
    profundidade do brinquedo NO BANCO (a 2% de diferença, no máximo); os
    adesivos de um produto têm a MESMA medida entre si (a troca de adesivo
    nunca encolhe nem cresce a máquina);
  * A DEFINIÇÃO: os adesivos grandes com 2048 px no lado maior (a arte
    ampliada 4x com nitidez), em sRGB (JPEG), em vinil laminado brilhante
    (KHR_materials_clearcoat), o que acende com emissiveStrength, e o .glb
    leve (até 4 MB);
  * OS NOMES dos materiais (quem importa no Blender acha cada peça pelo nome);
  * os visores com a luz de ambiente, o tom neutro e o enquadramento do
    primeiro 3D na troca de adesivo.
"""

import io
import json
import struct
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from PIL import Image

from .cadastro_modelos import CADASTROS
from .models import Brinquedos, ObjetoTresD, VarianteAdesivo
from .objetos_3d import medidas_do_glb

ESTATICO = Path(__file__).resolve().parent / "static"
MODELOS = "site/arena/modelos/"
TOLERANCIA = 0.02
TAMANHO_MAXIMO = 4 * 1024 * 1024

#: Os produtos e os 3D deles (um por adesivo). As medidas são as que o banco tem
#: no ar: as do cadastro (core/cadastro_modelos.py); o Basquete Home ficou com as
#: do Quadrinhos (a 0166).
PRODUTOS = {
    "Basquete Home": {"medidas": CADASTROS["basquete-street-quadrinhos"]["medidas"],
                      "glbs": {"Quadrinhos": "basquete-street-quadrinhos.glb"}},
    "Air Game Kids": {"medidas": CADASTROS["air-game-kids-alienigenas"]["medidas"],
                      "glbs": {"Astronautas": "air-game-kids-astronautas.glb", "Alienígenas": "air-game-kids-alienigenas.glb"}},
    "Strike Kids": {"medidas": CADASTROS["strike-kids"]["medidas"], "glbs": {"Padrão": "strike-kids.glb"}},
}

#: Os nomes dos materiais que ficam (os de antes, para quem importa no Blender) e os novos.
NOMES = {
    "basquete-street-quadrinhos.glb": {
        "mdf-preto", "estrutura-tubo-preto", "pes-niveladores", "chapa-de-parada", "aro", "suporte-da-cesta",
        "rede-da-cesta", "bolas", "neon-roxo", "placar", "moldura-do-placar", "porta-do-moedeiro", "moedeiro",
        "botao-start", "adesivo-lateral-externa-esquerda", "adesivo-lateral-interna-esquerda",
        "adesivo-lateral-externa-direita", "adesivo-lateral-interna-direita", "adesivo-fundo-cesta",
        "adesivo-teto-interno", "adesivo-testeira-frente", "adesivo-testeira-fundo", "adesivo-testeira-teto",
        "adesivo-testeira-superior-esquerda", "adesivo-testeira-superior-direita", "adesivo-testeira-lateral-esquerda",
        "adesivo-testeira-lateral-direita", "adesivo-prancha", "adesivo-frente",
    },
    "air-game-kids-alienigenas.glb": {
        "pintura-azul", "borda", "boca-do-gol", "soprador", "grade-do-soprador", "rebatedor-vermelho", "rebatedor-verde",
        "disco", "fita-de-led", "placar", "digitos-do-placar", "adesivo-lateral-esquerda", "adesivo-lateral-direita",
        "adesivo-lateral-esquerda-2", "adesivo-lateral-direita-2", "adesivo-tampo",
    },
    "strike-kids.glb": {
        "estrutura_mdf", "lateral_esquerda_arte", "lateral_direita_arte", "lateral_esquerda_dentro", "lateral_direita_dentro", "pista", "frente_arte",
        "painel_tela", "testeira_arte", "monitor", "moldura_monitor", "camera_sensor", "lente", "bolsao_piso", "bolsao_parede", "bolsao_borda", "placa_tela_arte", "bola_0", "bola_1",
        "botao_aro", "botao_vermelho", "neon_vermelho", "neon_azul", "led_pontos", "led_fita",
    },
}
NOMES["air-game-kids-astronautas.glb"] = NOMES["air-game-kids-alienigenas.glb"]
#: Os adesivos grandes de cada .glb, que têm de vir com 2048 px no lado maior.
GRANDES = {
    "basquete-street-quadrinhos.glb": ("adesivo-lateral-externa-esquerda", "adesivo-lateral-externa-direita", "adesivo-prancha"),
    "air-game-kids-alienigenas.glb": ("adesivo-lateral-esquerda", "adesivo-tampo"),
    "air-game-kids-astronautas.glb": ("adesivo-lateral-esquerda", "adesivo-tampo"),
    "strike-kids.glb": ("lateral_esquerda_arte", "lateral_direita_arte", "pista", "monitor"),
}


def ler_glb(nome):
    """(o JSON de dentro, o bloco binário) de um .glb do site."""
    dados = (ESTATICO / MODELOS / nome).read_bytes()
    magica, versao, _total, n_json, tipo = struct.unpack("<4sIIII", dados[:20])
    assert magica == b"glTF" and versao == 2 and tipo == 0x4E4F534A, nome
    gltf = json.loads(dados[20:20 + n_json])
    n_bin, = struct.unpack("<I", dados[20 + n_json:24 + n_json])
    return gltf, dados[28 + n_json:28 + n_json + n_bin]


def medidas(nome):
    """[altura, largura, profundidade] do .glb, em metros: o min/max de cada malha levado pelos nós."""
    return medidas_do_glb(ler_glb(nome)[0])


def perto(a, b, tolerancia=TOLERANCIA):
    return abs(float(a) - float(b)) <= tolerancia * float(b)


def imagem_do_material(gltf, binario, material, chave="baseColorTexture"):
    """A imagem (PIL) da textura de cor (ou da emissiva) de um material."""
    info = (material.get("pbrMetallicRoughness") or {}).get(chave) if chave == "baseColorTexture" else material.get(chave)
    if not info:
        return None, None
    fonte = gltf["textures"][info["index"]]["source"]
    imagem = gltf["images"][fonte]
    vista = gltf["bufferViews"][imagem["bufferView"]]
    inicio = vista.get("byteOffset", 0)
    return imagem.get("mimeType"), Image.open(io.BytesIO(binario[inicio:inicio + vista["byteLength"]]))


class TamanhoDeVerdadeTests(SimpleTestCase):
    def test_cada_glb_tem_as_medidas_do_produto(self):
        for produto, dados in PRODUTOS.items():
            esperado = [Decimal(v) for v in dados["medidas"]]
            for adesivo, nome in dados["glbs"].items():
                with self.subTest(produto=produto, adesivo=adesivo):
                    lido = medidas(nome)
                    self.assertEqual(len(lido), 3)
                    for eixo, (a, b) in zip(("altura", "largura", "profundidade"), zip(lido, esperado)):
                        self.assertTrue(perto(a, b), f"{nome}: {eixo} {a} m, o produto tem {b} m")

    def test_os_adesivos_de_um_produto_tem_a_mesma_medida(self):
        for produto, dados in PRODUTOS.items():
            todas = [medidas(nome) for nome in dados["glbs"].values()]
            for outra in todas[1:]:
                with self.subTest(produto=produto):
                    for a, b in zip(outra, todas[0]):
                        self.assertTrue(perto(a, b, 0.005), f"{produto}: {outra} x {todas[0]}")

    def test_os_dois_adesivos_do_air_game_kids_sao_o_mesmo_movel(self):
        """Saem do mesmo montar.js: as mesmas malhas, do mesmo tamanho, só a arte muda."""
        a, _ = ler_glb("air-game-kids-astronautas.glb")
        b, _ = ler_glb("air-game-kids-alienigenas.glb")
        caixas = lambda g: sorted(  # noqa: E731
            (m.get("name"), tuple(round(v, 4) for v in g["accessors"][p["attributes"]["POSITION"]]["max"]))
            for m in g["meshes"] for p in m["primitives"]
        )
        self.assertEqual(len(a["meshes"]), len(b["meshes"]))
        self.assertEqual([n for n, _ in caixas(a)], [n for n, _ in caixas(b)])

    def test_o_cadastro_e_o_3d_concordam_com_o_codigo_da_arena(self):
        # o que a Arena reserva antes de o arquivo chegar (lido de dentro do .glb) é o tamanho do produto
        from .objetos_3d import ler_glb_do_site

        for produto, dados in PRODUTOS.items():
            for nome in dados["glbs"].values():
                lido = ler_glb_do_site(MODELOS + nome)["medidas"]
                with self.subTest(glb=nome):
                    for a, b in zip(lido, dados["medidas"]):
                        self.assertTrue(perto(a, Decimal(b)), f"{nome}: {lido} x {dados['medidas']}")


class TamanhoNoBancoTests(TestCase):
    """Com o banco como no ar: cada produto com 3D (o do produto e os dos adesivos) bate com as medidas DELE."""

    def setUp(self):
        for nome, dados in PRODUTOS.items():
            altura, largura, fundo = (Decimal(v) for v in dados["medidas"])
            brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, descricao=f"{nome}.", altura_m=altura,
                                                  largura_m=largura, profundidade_m=fundo, voltz="220V",
                                                  avaliacao=Decimal("4.80"), imagem_brinquedo="imagens_brinquedos/x.png")
            adesivos = list(dados["glbs"].items())
            primeiro, glb = adesivos[0]
            if nome != "Basquete Home":  # o Basquete Home: o 3D é só o do adesivo Quadrinhos (o azul não tem)
                ObjetoTresD.objects.create(brinquedo=brinquedo, arquivo_estatico=MODELOS + glb, codigo=glb[:-4])
            padrao = brinquedo.adesivo_padrao
            if nome == "Basquete Home":
                VarianteAdesivo.objects.filter(pk=padrao.pk).update(nome="Azul", slug="azul")
                VarianteAdesivo.objects.create(brinquedo=brinquedo, nome="Quadrinhos", slug="quadrinhos", ordem=2, padrao=False,
                                               arquivo_estatico_3d=MODELOS + glb, codigo_3d=glb[:-4])
                continue
            VarianteAdesivo.objects.filter(pk=padrao.pk).update(nome=primeiro, arquivo_estatico_3d=MODELOS + glb, codigo_3d=glb[:-4])
            for ordem, (adesivo, outro) in enumerate(adesivos[1:], start=2):
                VarianteAdesivo.objects.create(brinquedo=brinquedo, nome=adesivo, slug=adesivo.lower()[:20], ordem=ordem,
                                               padrao=False, arquivo_estatico_3d=MODELOS + outro, codigo_3d=outro[:-4])

    def test_os_3d_de_cada_produto_no_banco(self):
        conferidos = 0
        for brinquedo in Brinquedos.objects.all():
            arquivos = {o.arquivo_estatico for o in ObjetoTresD.objects.filter(brinquedo=brinquedo) if o.arquivo_estatico}
            arquivos |= {v.arquivo_estatico_3d for v in VarianteAdesivo.objects.filter(brinquedo=brinquedo) if v.arquivo_estatico_3d}
            esperado = (brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m)
            lidas = []
            for caminho in sorted(arquivos):
                achado = finders.find(caminho)
                self.assertTrue(achado, caminho)
                with open(achado, "rb") as f:
                    dados = f.read()
                n_json, = struct.unpack("<I", dados[12:16])
                lido = medidas_do_glb(json.loads(dados[20:20 + n_json]))
                lidas.append(lido)
                with self.subTest(brinquedo=brinquedo.nome_brinquedo, glb=caminho):
                    for a, b in zip(lido, esperado):
                        self.assertTrue(perto(a, b), f"{caminho}: {lido} m, o produto tem {esperado}")
                conferidos += 1
            for outra in lidas[1:]:
                self.assertEqual(outra, lidas[0], f"{brinquedo.nome_brinquedo}: os adesivos com medidas diferentes")
        self.assertEqual(conferidos, 4)


class AltaDefinicaoTests(SimpleTestCase):
    def test_leve_e_com_os_nomes_de_sempre(self):
        for nome, esperados in NOMES.items():
            with self.subTest(glb=nome):
                self.assertLessEqual((ESTATICO / MODELOS / nome).stat().st_size, TAMANHO_MAXIMO)
                gltf, _ = ler_glb(nome)
                nomes = {m.get("name") for m in gltf["materials"]}
                self.assertFalse(esperados - nomes, f"{nome}: faltam os materiais {sorted(esperados - nomes)}")

    def test_adesivos_grandes_em_2048_px_e_srgb(self):
        for nome, grandes in GRANDES.items():
            gltf, binario = ler_glb(nome)
            materiais = {m.get("name"): m for m in gltf["materials"]}
            for peca in grandes:
                with self.subTest(glb=nome, peca=peca):
                    chave = "emissiveTexture" if peca == "monitor" else "baseColorTexture"
                    tipo, imagem = imagem_do_material(gltf, binario, materiais[peca], chave)
                    self.assertIsNotNone(imagem, peca)
                    self.assertIn(tipo, ("image/jpeg", "image/png"))
                    self.assertEqual(imagem.mode, "RGB")  # a arte em cor (sRGB), sem canal a mais
                    self.assertGreaterEqual(max(imagem.size), 1900, f"{peca}: {imagem.size}")
                    self.assertLessEqual(max(imagem.size), 2048, f"{peca}: {imagem.size}")

    def test_vinil_brilhante_e_luzes_acesas(self):
        for nome in NOMES:
            gltf, _ = ler_glb(nome)
            usadas = set(gltf.get("extensionsUsed") or [])
            with self.subTest(glb=nome):
                self.assertIn("KHR_materials_clearcoat", usadas)
                self.assertIn("KHR_materials_emissive_strength", usadas)
                for m in gltf["materials"]:
                    if (m.get("pbrMetallicRoughness") or {}).get("baseColorTexture") and m["name"].startswith(("adesivo-", "lateral_", "pista", "frente_arte", "painel_tela", "testeira_arte", "acab_")):
                        self.assertIn("KHR_materials_clearcoat", m.get("extensions") or {}, m["name"])
                acesos = [m["name"] for m in gltf["materials"] if "KHR_materials_emissive_strength" in (m.get("extensions") or {})]
                self.assertTrue(acesos, nome)

    def test_mipmaps_nas_texturas(self):
        for nome in NOMES:
            gltf, _ = ler_glb(nome)
            for amostrador in gltf.get("samplers") or []:
                with self.subTest(glb=nome):
                    # sem minFilter o three.js usa o LinearMipmapLinear; com ele, um que usa mipmap
                    self.assertIn(amostrador.get("minFilter", 9987), (9984, 9985, 9986, 9987))


class VisoresTests(SimpleTestCase):
    def test_luz_de_ambiente_tom_neutro_e_enquadramento_do_primeiro_3d(self):
        realismo = (ESTATICO / "site/arena/realismo3d.js").read_text()
        for trecho in ("PMREMGenerator", "RoomEnvironment.js", "NeutralToneMapping", "SRGBColorSpace", "anisotropy", "setPixelRatio"):
            self.assertIn(trecho, realismo)
        self.assertTrue((ESTATICO / "vendor/three/RoomEnvironment.js").exists())
        for arquivo in ("visor3d.js", "vitrine3d.js", "arena3d.js"):
            texto = (ESTATICO / "site/arena" / arquivo).read_text()
            with self.subTest(arquivo=arquivo):
                self.assertIn("realismo3d.js", texto)
                self.assertIn("prepararObjeto", texto)
        visor = (ESTATICO / "site/arena/visor3d.js").read_text()
        self.assertIn("if (!enquadrado)", visor)  # a troca de adesivo não refaz o enquadramento
        self.assertIn("sombraDeContato", visor)

    def test_fundo_azul_marinho_atras_do_3d(self):
        css = (ESTATICO / "site/paginas/arena.css").read_text()
        trecho = css[css.index(".arena-foto-midia--3d,"):]
        trecho = trecho[:trecho.index("}")]
        self.assertNotIn("#ffffff", trecho)
        self.assertIn("#0a1f42", trecho)
