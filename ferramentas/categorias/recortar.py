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
    grande cercado pela máquina (o vão de um arco); "branco+furinhos": também
    o branco pequeno cercado (o miolo de um cabo enrolado); "branco-claro": só
    o branco quase puro (a bobina branca dos cabos fica); "escuro": a peça
    escura no branco (some também a sombra cinza-clara em volta); ("figura",
    n, giro): a figura n de uma foto com várias, sozinha e de pé;
  * uma lista de pontos: o contorno da máquina, desenhado à mão sobre a
    foto (o Boliche Virtual só tem fotos na loja, com o fundo da loja).
A foto vai como é: nada redesenhado, nenhum logo acrescentado.

    python ferramentas/categorias/recortar.py              (todas, e o catalogo.json)
    python ferramentas/categorias/recortar.py mundo-zumbi  (só esta)
    python ferramentas/categorias/recortar.py --catalogo   (só o catalogo.json: as categorias de cada produto)
    python ferramentas/categorias/recortar.py --pecas      (as peças de reposição: reposicao/)
    python ferramentas/categorias/recortar.py --alta [chaves] (o recorte em alta: maquinas-alta/)

`altura` é a do cadastro (altura_m, em metros): a escala da máquina na cena.

AS PEÇAS DE REPOSIÇÃO (o card "Peças e acessórios" da home): a foto de cada
peça do catálogo (a página /pecas-reposicao/, a API /api/v1/pecas/), com o
mesmo recorte, em `reposicao/<chave>.webp`, e a ficha em
`reposicao/pecas.json` (o nome e o id no site, a altura de verdade em
metros). Ficam de fora as fotos que são a caixa de outra marca (o controle
e a caixa de som multimídia): a cena não mostra marca de ninguém.
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
#: As capas do catálogo (seção 64): o recorte em alta, do tamanho da foto do site (até 1600 px),
#: em maquinas-alta/ -- a máquina ocupa a foto quase inteira.
PASTA_ALTA = Path(__file__).resolve().parent / "maquinas-alta"
LADO_ALTO = 1600

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
    # (os que faltavam para as capas do catálogo, a seção 64)
    "air-game-home": (2, "Air Game Home", "imagens_brinquedos/airhokey_lpyk86", 0.80, "cinza"),
    "multi-jogos": (16, "Multi Jogos", "imagens_brinquedos/Multi_jogos_Mesa_foocks", 1.52, "branco+buracos"),
    "matrix-one-piece": (36, "Matrix One Piece", "imagens_brinquedos/matrix_oqoacy", 2.30, "pronto"),
    "air-game-kids": (40, "Air Game Kids", "imagens_brinquedos/WhatsApp_Image_2026-07-24_at_16.10.57-removebg-preview_hcfnmt", 0.90, "pronto"),
}


REPOSICAO = Path(__file__).resolve().parent / "reposicao"

#: chave -> (id no site, nome, foto no Cloudinary, altura em m, recorte)
PECAS = {
    "boneco-pebolim": (1, "Boneco para Mesa de Pebolim",
                       "pecas_reposicao/bonecos-pebolim-frente-ee78cafb65abff265417508856803055-1024-1024_nx4yyc", 0.13, "pronto"),
    # os dois bonecos da mesma foto, cada um sozinho e de pé (a foto os mostra inclinados)
    "boneco-pebolim-vermelho": (1, "Boneco para Mesa de Pebolim",
                                "pecas_reposicao/bonecos-pebolim-frente-ee78cafb65abff265417508856803055-1024-1024_nx4yyc",
                                0.12, ("figura", 0, 17)),
    "boneco-pebolim-amarelo": (1, "Boneco para Mesa de Pebolim",
                               "pecas_reposicao/bonecos-pebolim-frente-ee78cafb65abff265417508856803055-1024-1024_nx4yyc",
                               0.12, ("figura", 1, 17)),
    "cabo-flexivel": (7, "Cabo Flexível", "pecas_reposicao/CABOS_kxa6pt", 0.36, "branco-claro"),
    "cabo-hdmi": (5, "Cabo HDMI", "pecas_reposicao/cabo-hdmi_ci5liw", 0.17, "escuro"),
    "disco-air-game": (12, "Disco Air Game", "pecas_reposicao/BOTAO-REBATE-removebg-preview_fun5iv", 0.045, "branco"),
    "maneta-air-game": (11, "Maneta Air Game", "pecas_reposicao/MANETA-removebg-preview_zcqczy", 0.075, "escuro"),
    "mini-caixa-de-som": (8, "Mini Caixa de Som Bluethoot Xtrad Pocket", "pecas_reposicao/caixa_portatil_melhorada_2_mrd6in",
                          0.075, "escuro"),
    "mini-caixa-de-som-frente": (8, "Mini Caixa de Som Bluethoot Xtrad Pocket",
                                 "pecas_reposicao/caixa_portatil_melhorada_1_yqrrr0", 0.1, "escuro"),
}


def baixar(foto):
    with urllib.request.urlopen(CLOUDINARY + foto, timeout=60) as resposta:
        return Image.open(io.BytesIO(resposta.read())).convert("RGBA")


def sem_fundo_branco(imagem, limite=232, buracos=False, buraco_minimo=0.015):
    """Tira o branco liso que encosta na borda (o de dentro da máquina fica).

    `buracos`: também o branco grande cercado pela máquina (o vão do arco do
    Air Game Premium e do Pebolim Eletrônico, onde se vê a parede do estúdio):
    a mancha com mais de `buraco_minimo` da foto (nas peças, o miolo do cabo
    enrolado e da alça, bem menor).
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
                    ImageDraw.floodfill(fundo, (x, y), 128 if area > buraco_minimo * w * h else 100)
    alfa = fundo.point(lambda v: 0 if v == 128 else 255)
    # (a foto que já vem com parte transparente: o transparente dela continua transparente)
    alfa = ImageChops.multiply(alfa, imagem.getchannel("A"))
    # a borda do recorte: um tico para dentro e macia
    alfa = alfa.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    imagem.putalpha(alfa)
    return imagem


def figura(imagem, qual, giro):
    """A figura `qual` (da esquerda para a direita) de uma foto recortada com várias, de pé (`giro` graus)."""
    alfa = imagem.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    w, h = alfa.size
    manchas = []
    for x in range(0, w, 3):
        for y in range(0, h, 3):
            if alfa.getpixel((x, y)) == 255:
                ImageDraw.floodfill(alfa, (x, y), 100)
                mancha = alfa.point(lambda v: 255 if v == 100 else 0)
                if mancha.histogram()[255] > 0.01 * w * h:
                    manchas.append((x, mancha))
                alfa = alfa.point(lambda v: 0 if v == 100 else v)
    _x, mancha = sorted(manchas, key=lambda m: m[0])[qual]
    sozinha = imagem.copy()
    sozinha.putalpha(ImageChops.multiply(imagem.getchannel("A"), mancha.filter(ImageFilter.MaxFilter(5))))
    return sozinha.rotate(giro, resample=Image.BICUBIC, expand=True)


def pelo_contorno(imagem, pontos):
    alfa = Image.new("L", imagem.size, 0)
    ImageDraw.Draw(alfa).polygon(pontos, fill=255)
    imagem.putalpha(alfa.filter(ImageFilter.GaussianBlur(1.2)))
    return imagem


def recortar(chave, lista=None, pasta=PASTA, lado=LADO, largura_da_foto=1600, qualidade=80):
    _id, nome, foto, altura, recorte = (lista or MAQUINAS)[chave]
    imagem = baixar(foto)
    if recorte in ("branco", "branco+buracos"):
        imagem = sem_fundo_branco(imagem, buracos=recorte == "branco+buracos")
    elif recorte == "branco+furinhos":
        imagem = sem_fundo_branco(imagem, buracos=True, buraco_minimo=0.0008)
    elif recorte == "cinza":
        # a foto com a sombra cinza do estúdio embaixo (o Air Game Home): some até o cinza claro
        imagem = sem_fundo_branco(imagem, limite=165, buracos=True, buraco_minimo=0.0008)
    elif recorte == "escuro":
        # a peça escura no branco: some também a sombra cinza-clara da foto em volta
        imagem = sem_fundo_branco(imagem, limite=200, buracos=True, buraco_minimo=0.0008)
    elif isinstance(recorte, tuple) and recorte[0] == "figura":
        imagem = figura(imagem, recorte[1], recorte[2])
    elif recorte == "branco-claro":
        # o branco quase puro só (a bobina branca dos cabos fica: o sombreado dela é cinza)
        imagem = sem_fundo_branco(imagem, limite=248)
    elif isinstance(recorte, list):
        imagem = pelo_contorno(imagem, recorte)
    # apara a sobra transparente: a base da máquina fica na borda de baixo (no chão)
    caixa = imagem.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    imagem = imagem.crop(caixa)
    imagem.thumbnail((lado, lado), Image.LANCZOS)
    pasta.mkdir(exist_ok=True)
    saida = pasta / f"{chave}.webp"
    imagem.save(saida, "WEBP", quality=qualidade, method=6)
    return saida, imagem.size


SITE = "https://www.lazersport.com.br/api/v1/brinquedos/"


def _json(url):
    with urllib.request.urlopen(url, timeout=60) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def catalogo():
    """maquinas/catalogo.json: cada produto do site no ar e as categorias dele.

    É o que prova que cada foto só tem itens da própria categoria
    (core/tests_categorias_capas.py confere a lista de cada foto contra ele).
    """
    produtos, url = [], SITE
    while url:
        pagina = _json(url)
        produtos += pagina["results"]
        url = pagina["next"]
    dados = {}
    for p in sorted(produtos, key=lambda p: p["id"]):
        detalhe = _json(f"{SITE}{p['id']}/")
        dados[detalhe["nome"]] = {"id": detalhe["id"], "categorias": [c["nome"] for c in detalhe["categorias"]]}
    (PASTA / "catalogo.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return dados


def ficha():
    """maquinas/maquinas.json: o nome, o id no site e a altura de cada uma (o cenas.js lê)."""
    dados = {chave: {"id": i, "nome": nome, "altura": altura} for chave, (i, nome, _foto, altura, _r) in MAQUINAS.items()}
    (PASTA / "maquinas.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


SITE_PECAS = "https://www.lazersport.com.br/api/v1/pecas/"


def catalogo_pecas():
    """reposicao/catalogo.json: cada peça do site no ar (o nome e o id), a prova de que são do catálogo."""
    pecas_do_site, url = [], SITE_PECAS
    while url:
        pagina = _json(url)
        pecas_do_site += pagina["results"]
        url = pagina["next"]
    dados = {p["nome"]: {"id": p["id"]} for p in sorted(pecas_do_site, key=lambda p: p["id"])}
    (REPOSICAO / "catalogo.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return dados


def pecas():
    """reposicao/: o recorte de cada peça e a ficha (reposicao/pecas.json, o cenas.js lê)."""
    catalogo_pecas()
    for chave in PECAS:
        saida, tamanho = recortar(chave, PECAS, REPOSICAO)
        print(f"{chave}: {saida.name} {tamanho[0]}x{tamanho[1]} ({saida.stat().st_size // 1024} KB)")
    dados = {chave: {"id": i, "nome": nome, "altura": altura} for chave, (i, nome, _foto, altura, _r) in PECAS.items()}
    (REPOSICAO / "pecas.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def alta(chaves):
    """maquinas-alta/: o recorte de cada máquina do catálogo no tamanho da foto do site (as capas em cena)."""
    for chave in chaves or MAQUINAS:
        saida, tamanho = recortar(chave, MAQUINAS, PASTA_ALTA, LADO_ALTO, qualidade=90)
        print(f"{chave}: {saida.name} {tamanho[0]}x{tamanho[1]} ({saida.stat().st_size // 1024} KB)")
    ficha()


def main(chaves):
    if chaves[:1] == ["--alta"]:
        alta(chaves[1:])
        return
    if chaves == ["--catalogo"]:
        print(f"{len(catalogo())} produtos em maquinas/catalogo.json")
        return
    if chaves == ["--pecas"]:
        pecas()
        return
    for chave in chaves or MAQUINAS:
        saida, tamanho = recortar(chave)
        print(f"{chave}: {saida.name} {tamanho[0]}x{tamanho[1]} ({saida.stat().st_size // 1024} KB)")
    ficha()
    if not chaves:
        catalogo()


if __name__ == "__main__":
    main(sys.argv[1:])
