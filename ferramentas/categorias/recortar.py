"""As máquinas de verdade das fotos das categorias: a foto do catálogo, recortada do fundo.

O cliente pediu: "não quero nenhuma máquina fake, você tem os itens nas
categorias, é só pegar e posicionar". Nas cenas (cenas.js), cada máquina é
o .glb nosso, quando existe, ou a FOTO DO PRÓPRIO CATÁLOGO, recortada do
fundo e posta em pé no chão (um plano de frente para a câmera, na altura
de verdade). Este script baixa a foto de capa de cada uma (a do site no ar,
no Cloudinary), tira o fundo e grava `maquinas/<chave>.webp`, leve, com
transparência -- a pasta fica no repositório, para refazer as fotos sem rede.

O RECORTE:
  * "pronto": a foto do catálogo já vem recortada (as "removebg" e
    "Photoroom"): só se apara a sobra transparente;
  * "branco": o fundo é branco liso: some o branco que encosta na borda
    (o branco de dentro da máquina fica); "branco+buracos": também o branco
    grande cercado pela máquina (o vão de um arco);
  * uma lista de pontos: o contorno da máquina, desenhado à mão sobre a
    foto (o Boliche Virtual só tem fotos na loja, com o fundo da loja).
A foto vai como é: nada redesenhado, nenhum logo acrescentado.

    python ferramentas/categorias/recortar.py            (todas)
    python ferramentas/categorias/recortar.py mundo-zumbi  (só esta)

`altura` é a do cadastro (altura_m, em metros): a escala da máquina na cena.
"""

import io
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

PASTA = Path(__file__).resolve().parent / "maquinas"
CLOUDINARY = "https://res.cloudinary.com/dgikjmki8/image/upload/c_limit,w_1600,f_png/v1/"
#: O lado maior do arquivo gravado (a máquina ocupa no máximo ~1000 px no render de 2400).
LADO = 900

#: O contorno do Boliche Virtual na foto rosa da galeria (1086 x 1448), à mão.
CONTORNO_BOLICHE = [
    (42, 1305), (5, 1060), (30, 1000), (28, 905), (620, 755), (645, 700), (650, 600), (668, 470),
    (690, 430), (700, 410), (697, 350), (712, 300), (735, 258), (772, 225), (802, 202), (838, 205),
    (858, 230), (885, 228), (897, 255), (885, 300), (888, 345), (880, 392), (905, 390), (930, 420),
    (945, 480), (940, 545), (928, 600), (938, 660), (948, 740), (950, 820), (945, 890), (932, 950),
    (915, 990), (880, 1003), (830, 1000), (790, 1000), (700, 1075), (600, 1110), (500, 1150),
    (300, 1222), (100, 1290),
]

#: chave -> (id no site, nome, foto no Cloudinary, altura em m, recorte)
MAQUINAS = {
    "air-game-premium": (1, "Air Game Premium", "imagens_brinquedos/Mesas_de_air_hockey_futuristas_com_LEDs_hr1x4m", 1.90, "branco+buracos"),
    "basquete-home": (3, "Basquete Home", "imagens_brinquedos/basquetehome_s1antg", 2.10, "branco"),
    "mundo-zumbi": (4, "Mundo Zumbi", "imagens_brinquedos/Mundo_Zumbi_cj4fhq", 1.94, "pronto"),
    "porsche-simulador": (5, "Porsche Simulador", "imagens_brinquedos/Simulador_Porche_yrfemm", 1.70, "pronto"),
    "simulador-mario-kart": (6, "Simulador Mario Kart", "imagens_brinquedos/Simulador_Mario_qqjqno", 2.14, "pronto"),
    "pac-man": (7, "Pac Man", "imagens_brinquedos/Pac_Man_c3lp48", 1.10, "pronto"),
    "basquete-street": (8, "Basquete Street", "imagens_brinquedos/Basquete_Street_kclh4g", 2.70, "pronto"),
    "show-de-bola": (9, "Show de Bola", "imagens_brinquedos/Show_de_Bola_rto0vx", 2.40, "pronto"),
    "homem-aranha-kids": (10, "Homem Aranha Kids", "imagens_brinquedos/Homem_Aranha_Kids_tj2kf5", 1.50, "pronto"),
    "tomb-raider-kids": (11, "Tomb Raider Kids", "imagens_brinquedos/Tomb_Raider_Kids_fmvljf", 1.50, "pronto"),
    "corrida-dos-minions": (12, "Corrida dos Minions", "imagens_brinquedos/Minions_egblw6", 2.10, "pronto"),
    "pega-toupeira": (13, "Pega Toupeira", "imagens_brinquedos/pegatop_byx7nr", 1.23, "branco"),
    "matrix": (14, "Matrix", "imagens_brinquedos/Matrix_zze6sm", 0.90, "pronto"),
    "multi-jogos-retro": (15, "Multi Jogos Retro", "imagens_brinquedos/Multi_Jogos_Retro_nmbwkp", 1.86, "pronto"),
    "gabinete-games": (17, "Gabinete Games", "imagens_brinquedos/Gabinete_Games_pcz92j", 1.90, "pronto"),
    "pinball-32": (18, "Pinball 32 Polegadas", "imagens_brinquedos/Pimbal_32_Polegadas_zymhyo", 1.73, "pronto"),
    "pinball-40": (19, "Pinball 40 Polegadas", "imagens_brinquedos/Pimbal_40_polegadas_ezjlz8", 1.75, "pronto"),
    "pebolim-eletronico": (20, "Pebolim Eletrônico", "imagens_brinquedos/pebolim-eletro_am7cub", 2.30, "branco+buracos"),
    "homem-aranha": (21, "Homem Aranha", "imagens_brinquedos/Homem_Aranha_Grande_l7xqsq", 2.10, "pronto"),
    "sonic-dash": (22, "Sonic Dash", "imagens_brinquedos/Sonic_Grande_mvfjbo", 2.10, "pronto"),
    "subway-surfers": (23, "Subway Surfers", "imagens_brinquedos/Subway_Surfers_hbuebk", 2.10, "pronto"),
    "flappy-bird": (24, "Flappy Bird", "imagens_brinquedos/Flapyy_Bird_GRande_r13wlt", 2.10, "pronto"),
    "speed-turbo": (25, "Speed Turbo", "imagens_brinquedos/Speed_Turbo_ojcxu0", 2.10, "pronto"),
    "pantera-kids": (26, "Pantera Cor de Rosa Kids", "imagens_brinquedos/Pantera_Kids_rxjhod", 1.50, "pronto"),
    "sonic-kids": (27, "Sonic Kids", "imagens_brinquedos/Sonic_Kids_pceewo", 1.50, "pronto"),
    "minions-kids": (28, "Minions Kids", "imagens_brinquedos/Minions_Kids_wh35t1", 1.50, "pronto"),
    "labamba": (29, "Labamba", "imagens_brinquedos/Labamba_idv3wd", 2.30, "pronto"),
    "carrossel-sorvetinho": (30, "Carrossel Sorvetinho", "imagens_brinquedos/Carrosel_ra9ann", 1.95, "pronto"),
    "mini-roda-sorvete": (31, "Mini Roda Sorvete", "imagens_brinquedos/Mini_Roda_Gigante_jxmj3r", 2.70, "pronto"),
    "nervo-teste": (32, "Nervo Teste", "imagens_brinquedos/Nervo_Teste_pcgql3", 2.19, "pronto"),
    "brinquedao-modelo-1": (33, "Brinquedão Modelo 1", "imagens_brinquedos/Imagem1-Photoroom_qfd8iy", 2.60, "pronto"),
    "boliche-virtual": (34, "Boliche Virtual", "imagens_brinquedos/galeria/Boliche_Virtual_Rosa_r17hzv", 2.40, CONTORNO_BOLICHE),
    "lazer-shot": (35, "Lazer Shot", "imagens_brinquedos/LAZER-SHOT_cautcu", 2.30, "pronto"),
    "sonic-racing": (37, "Sonic Racing All-Stars", "imagens_brinquedos/SONIC_k6bpj7", 2.10, "branco"),
    "top-racer": (38, "Simulador de Corrida Top Racer", "imagens_brinquedos/ChatGPT_Image_24_de_jul._de_2026__15_31_31-removebg-preview_t3qcnh", 1.50, "pronto"),
    "bob-esponja-kids": (39, "Bob Esponja Hammer Kids", "imagens_brinquedos/WhatsApp_Image_2026-07-24_at_16.01.53-removebg-preview_mdy0ek", 1.47, "pronto"),
}


def baixar(foto):
    with urllib.request.urlopen(CLOUDINARY + foto, timeout=60) as resposta:
        return Image.open(io.BytesIO(resposta.read())).convert("RGBA")


def sem_fundo_branco(imagem, limite=232, buracos=False):
    """Tira o branco liso que encosta na borda (o de dentro da máquina fica).

    `buracos`: também o branco grande cercado pela máquina (o vão do arco do
    Air Game Premium e do Pebolim Eletrônico, onde se vê a parede do estúdio).
    """
    # "branco" só onde os três canais são claros
    r, g, b = imagem.convert("RGB").split()
    claros = [c.point(lambda v: 255 if v > limite else 0) for c in (r, g, b)]
    fundo = ImageChops.multiply(ImageChops.multiply(claros[0], claros[1]), claros[2])
    w, h = fundo.size
    for x in range(0, w, 4):
        for y in (0, h - 1):
            if fundo.getpixel((x, y)) == 255:
                ImageDraw.floodfill(fundo, (x, y), 128)
    for y in range(0, h, 4):
        for x in (0, w - 1):
            if fundo.getpixel((x, y)) == 255:
                ImageDraw.floodfill(fundo, (x, y), 128)
    if buracos:
        # cada mancha branca que sobrou: se for grande (mais de 1,5% da foto), é fundo
        for y in range(0, h, 6):
            for x in range(0, w, 6):
                if fundo.getpixel((x, y)) == 255:
                    ImageDraw.floodfill(fundo, (x, y), 200)
                    area = fundo.histogram()[200]
                    ImageDraw.floodfill(fundo, (x, y), 128 if area > 0.015 * w * h else 100)
    alfa = fundo.point(lambda v: 0 if v == 128 else 255)
    # a borda do recorte: um tico para dentro e macia
    alfa = alfa.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    imagem.putalpha(alfa)
    return imagem


def pelo_contorno(imagem, pontos):
    alfa = Image.new("L", imagem.size, 0)
    ImageDraw.Draw(alfa).polygon(pontos, fill=255)
    imagem.putalpha(alfa.filter(ImageFilter.GaussianBlur(1.2)))
    return imagem


def recortar(chave):
    _id, nome, foto, altura, recorte = MAQUINAS[chave]
    imagem = baixar(foto)
    if recorte in ("branco", "branco+buracos"):
        imagem = sem_fundo_branco(imagem, buracos=recorte == "branco+buracos")
    elif isinstance(recorte, list):
        imagem = pelo_contorno(imagem, recorte)
    # apara a sobra transparente: a base da máquina fica na borda de baixo (no chão)
    caixa = imagem.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    imagem = imagem.crop(caixa)
    imagem.thumbnail((LADO, LADO), Image.LANCZOS)
    PASTA.mkdir(exist_ok=True)
    saida = PASTA / f"{chave}.webp"
    imagem.save(saida, "WEBP", quality=80, method=6)
    return saida, imagem.size


def ficha():
    """maquinas/maquinas.json: o nome, o id no site e a altura de cada uma (o cenas.js lê)."""
    dados = {chave: {"id": i, "nome": nome, "altura": altura} for chave, (i, nome, _foto, altura, _r) in MAQUINAS.items()}
    (PASTA / "maquinas.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(chaves):
    for chave in chaves or MAQUINAS:
        saida, tamanho = recortar(chave)
        print(f"{chave}: {saida.name} {tamanho[0]}x{tamanho[1]} ({saida.stat().st_size // 1024} KB)")
    ficha()


if __name__ == "__main__":
    main(sys.argv[1:])
