"""As máquinas da Black Friday tiradas do fundo vermelho (e do panorâmico): os recortes (LEIA-ME, seção 78).

O cliente, com o print do card do Basquete Kids (a máquina no fundo de neon
vermelho do cartaz da Black Friday): "veja que o fundo não ficou uniforme com
o que preciso, de paisagens e tal ... identifique as máquinas com o fundo
vermelho e ponha elas no padrão". E, com o print do card do Air Rock (a foto
panorâmica cortada em quadrado, a máquina cortada e o logo pela metade):
"valide para não ter fotos assim com zoom pois estraga".

Os produtos que a Black Friday criou (core/black_friday.py) têm a foto
recortada do PRÓPRIO CARTAZ: a máquina no neon vermelho escuro (Basquete Duplo,
Basquete Kids e as três casinhas), ou a foto panorâmica (Air Rock, Kid Play),
que o card quadrado corta. O padrão é a seção 64: a máquina inteira, grande, no
showroom da Lazer & Sport. Este script tira cada máquina do fundo; depois, o
recortar.py (--alta) põe o recorte em maquinas-alta/ e o gerar.cjs faz a foto
no showroom, como as capas do catálogo.

O recortar.py só sabe tirar o fundo BRANCO. Aqui o fundo é o gradiente de neon
vermelho e preto, então são dois jeitos, conforme a máquina:

  * "contorno" (Basquete Duplo, Basquete Kids, Cozinha Infantil, Oficina de
    Engenharia, Salão de Beleza): o contorno da máquina desenhado à mão sobre a
    foto (uns 3 px de erro) dá três zonas: por dentro (o contorno encolhido
    `faixa` px) é a máquina; por fora (crescido `faixa` px) é o fundo; na faixa
    entre elas, cada pixel é medido pela COR: a cor do fundo ali perto e a cor
    da máquina ali perto (as médias de cada zona em volta). Onde as duas são bem
    diferentes, a cor decide o quanto o pixel é máquina (a borda macia de uma
    foto); onde não são (a máquina preta no fundo preto), o contorno decide.
    Por isso a GELADEIRA VERMELHA da Cozinha Infantil, as partes vermelhas dos
    basquetes e o anel de luz vermelho no chão do Basquete Kids não somem nem
    ficam: o contorno diz onde é a máquina, e a cor só acerta a borda;
  * "grabcut" (Air Rock, Kid Play: a mesa preta com o arco de tubos finos, o
    playground com as redes): o GrabCut do OpenCV, com as zonas certas dadas à
    mão (o contorno largo; a máquina certa: os tubos do arco, a placa, as
    laterais, os pés de LED, as cores do playground; o fundo certo: o que se vê
    entre os tubos, o chão, o balão), e depois o mesmo acabamento da borda pela
    cor, numa faixa fina. Onde o chão escuro se mistura com a mesa preta (a
    borda de baixo do Air Rock), a borda é a reta desenhada à mão (`corte`):
    é uma aresta reta da mesa.

Nos dois, a COR DA BORDA é limpa do fundo (o vermelho que vazou no pixel meio
transparente: a cor da máquina = (pixel - (1 - alfa) x fundo) / alfa), sem a
franja vermelha do neon na borda; o que não encosta na máquina some.

O KID PLAY: a foto da arte corta embaixo o canto da frente do piso de grama (o
playground vem inteiro, só o tapete de grama sai pela borda da foto). O canto
que falta é completado com a grama da própria foto (um pedaço liso, sem poste
nem LED, em ladrilhos misturados), na continuação das duas bordas retas do
tapete: a máquina inteira na foto do showroom, sem nada cortado.

Os recortes ficam GUARDADOS no repositório, para fazer artes (o cliente pediu),
e NUNCA aparecem no site: core/static/site/black_friday/recortes/<chave>.webp
(WebP sem perda, com transparência, no tamanho da foto da arte). As fotos de
antes (o cartaz) continuam em core/static/site/black_friday/produto-*.webp.

    python ferramentas/categorias/recortar_vermelho.py               (todos)
    python ferramentas/categorias/recortar_vermelho.py basquete-kids (só este)
    python ferramentas/categorias/recortar.py --alta basquete-kids   (o recorte em alta, para a foto)

Precisa do numpy e, para o Air Rock e o Kid Play, do OpenCV
(pip install numpy opencv-python-headless): só para refazer os recortes; as
fotos e o site não dependem deles.
"""

import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent.parent
#: As fotos de antes (o recorte do cartaz da Black Friday) e as artes inteiras.
ORIGEM = RAIZ / "core" / "static" / "site" / "black_friday"
#: Os recortes guardados para fazer artes (transparentes; o site não mostra).
RECORTES = ORIGEM / "recortes"

#: Cada máquina: a foto de origem, o jeito ("contorno" ou "grabcut") e as zonas desenhadas à mão
#: (em pixels da foto de origem). Os pontos foram tirados das fotos ampliadas com a grade e conferidos
#: no recorte sobre um fundo liso (a borda inteira, nada da máquina cortado e nada do fundo junto).
CONTORNOS = {
    "basquete-duplo": {
        "origem": "produto-basquete-duplo.webp",
        "metodo": "contorno",
        "contorno": [[
            (398, 145), (480, 128), (755, 75), (805, 106), (821, 125), (822, 300), (821, 600), (818, 866),
            (723, 1027), (420, 970), (209, 933), (207, 860), (196, 760), (189, 599), (275, 590), (273, 554),
            (286, 507), (298, 497), (301, 300), (304, 247), (330, 228), (357, 216), (398, 207),
        ]],
    },
    "basquete-kids": {
        "origem": "produto-basquete-kids.webp",
        "metodo": "contorno",
        "contorno": [[
            (176, 70), (245, 65), (550, 62), (557, 66), (561, 75), (563, 106), (579, 128), (610, 144), (641, 169),
            (666, 200), (685, 237), (697, 281), (706, 319), (708, 350), (705, 387), (698, 419), (690, 436),
            (684, 441), (777, 502), (780, 508), (779, 600), (778, 700), (775, 780), (775, 822), (650, 838),
            (530, 860), (410, 889), (398, 884), (380, 867), (330, 810), (295, 770), (262, 735), (250, 748),
            (214, 745), (213, 677), (210, 600), (204, 500), (199, 300), (193, 120), (180, 80),
        ]],
        # o anel de luz vermelho do chão, encostado no pé da direita
        "corte": [[(776, 792), (792, 792), (792, 818), (776, 818)]],
    },
    "cozinha-infantil": {
        "origem": "produto-cozinha-infantil.webp",
        "metodo": "contorno",
        "contorno": [[
            (153, 155), (190, 145), (250, 131), (330, 111), (390, 97), (450, 97), (550, 97), (610, 97), (650, 107),
            (750, 135), (830, 158), (844, 163), (843, 190), (832, 205), (830, 230), (830, 540), (845, 545),
            (855, 557), (862, 570), (867, 590), (869, 620), (869, 815), (862, 824), (820, 830), (600, 860),
            (340, 895), (260, 906), (247, 909), (155, 848), (153, 500),
        ]],
    },
    "oficina-de-engenharia": {
        "origem": "produto-oficina-de-engenharia.webp",
        "metodo": "contorno",
        "contorno": [[
            (150, 171), (170, 165), (250, 144), (330, 125), (410, 106), (450, 100), (570, 97), (590, 99), (650, 115),
            (750, 143), (830, 166), (840, 170), (839, 215), (822, 232), (821, 520), (821, 545), (842, 560),
            (852, 587), (853, 620), (853, 812), (845, 815), (811, 812), (780, 807), (700, 819), (540, 840),
            (380, 862), (260, 879), (250, 887), (150, 838), (151, 500),
        ]],
    },
    "salao-de-beleza": {
        "origem": "produto-salao-de-beleza.webp",
        "metodo": "contorno",
        "contorno": [[
            (131, 168), (150, 163), (210, 148), (290, 129), (370, 113), (450, 106), (550, 98), (570, 98), (590, 104),
            (690, 134), (810, 171), (822, 176), (821, 215), (805, 232), (803, 520), (826, 529), (842, 550),
            (850, 580), (852, 610), (852, 812), (845, 815), (804, 803), (780, 802), (700, 813), (580, 832),
            (420, 855), (260, 879), (218, 889), (131, 839), (131, 500),
        ]],
    },
    # a arte 10 inteira (968 x 949): a foto do produto de antes era só a faixa de cima (sem os pés)
    "air-rock": {
        "origem": "arte-10.webp",
        "metodo": "grabcut",
        "contorno": [[
            (32, 470), (120, 452), (212, 440), (214, 458), (365, 222), (395, 212), (700, 212), (716, 226), (820, 425),
            (874, 438), (876, 552), (848, 558), (848, 658), (770, 660), (762, 610), (640, 650), (600, 668),
            (390, 760), (362, 772), (362, 890), (278, 892), (274, 800), (190, 770), (186, 762), (96, 768),
            (92, 680), (50, 672), (32, 600),
        ]],
        # o fundo certo: entre os tubos do arco, embaixo da mesa, o quadro do preço da arte
        "fundo": [
            [(256, 436), (268, 404), (300, 362), (324, 332), (345, 312), (400, 312), (440, 380), (445, 410), (300, 436)],
            [(468, 312), (725, 312), (745, 350), (700, 368), (600, 380), (500, 385), (490, 365)],
            [(400, 790), (560, 730), (600, 760), (600, 900), (400, 900)],
            [(195, 790), (270, 805), (270, 900), (195, 900)],
            [(610, 668), (700, 645), (770, 668), (700, 690)],
            [(200, 445), (222, 430), (240, 400), (274, 360), (322, 300), (355, 260), (366, 240), (360, 215), (200, 215)],
            [(718, 240), (720, 260), (742, 300), (775, 360), (795, 395), (850, 412), (880, 412), (880, 215), (718, 215)],
        ],
        # a máquina certa: as duas laterais, o tampo, a placa do arco e os pés de LED
        "certo": [
            [(80, 520), (280, 600), (280, 740), (80, 660)],
            [(340, 620), (850, 455), (856, 548), (782, 566), (390, 756), (352, 762)],
            [(60, 492), (400, 432), (560, 405), (700, 395), (850, 445), (320, 600)],
            [(402, 240), (688, 240), (680, 284), (442, 290)],
            [(296, 782), (344, 782), (344, 868), (296, 868)],
            [(108, 676), (172, 676), (172, 742), (108, 742)],
            [(782, 572), (826, 572), (826, 632), (782, 632)],
        ],
        # e os tubos do arco (o meio de cada um, medido pelo escuro do tubo, linha a linha)
        "certo_linhas": [
            ([(387, 242), (338, 300), (290, 360), (264, 390), (245, 415), (236, 440), (234, 452)], 4),
            ([(440, 255), (448, 270), (455, 285), (464, 300), (470, 315), (478, 330), (486, 345), (493, 360),
              (500, 375), (508, 390), (515, 405), (525, 420), (535, 440), (545, 465), (552, 490), (556, 510),
              (559, 530), (561, 545)], 4),
            ([(695, 240), (728, 300), (761, 360), (777, 390), (799, 428)], 3),
        ],
        # as bordas de baixo, retas (o chão escuro some com a mesa preta), e embaixo dos pés
        "corte": [
            [(383, 771), (786, 575), (786, 900), (383, 900)],
            [(176, 722), (283, 778), (283, 900), (176, 900)],
            [(30, 668), (89, 668), (89, 900), (30, 900)],
            [(836, 556), (880, 556), (880, 900), (836, 900)],
            [(90, 768), (180, 768), (180, 900), (90, 900)],
            [(283, 872), (384, 872), (384, 900), (283, 900)],
            [(786, 652), (836, 652), (836, 900), (786, 900)],
        ],
    },
    "kid-play": {
        "origem": "produto-kid-play.webp",
        "metodo": "grabcut",
        "contorno": [[
            (104, 10), (540, 8), (548, 70), (1032, 70), (1088, 108), (1168, 158), (1208, 196), (1248, 214),
            (1452, 230), (1482, 246), (1494, 560), (1488, 648), (920, 648), (800, 632), (600, 600), (400, 568),
            (200, 533), (36, 500), (8, 470), (14, 450), (60, 432), (104, 418),
        ]],
        # a parede acima da torre e do meio, os balões da direita
        "fundo": [
            [(400, 4), (545, 4), (545, 19), (400, 15)],
            [(560, 70), (1030, 70), (1030, 74), (560, 74)],
            [(1446, 196), (1500, 196), (1500, 290), (1446, 290)],
            [(1380, 196), (1446, 196), (1446, 233), (1380, 234)],
            [(1436, 230), (1446, 230), (1446, 272), (1436, 272)],
        ],
        # o laranja do tubo, dos tapetes e das plaquinhas (a parede de madeira também é laranja)
        "certo": [
            [(480, 480), (610, 478), (615, 520), (480, 530)],
            [(735, 130), (820, 130), (820, 205), (735, 205)],
        ],
        "certo_linhas": [
            ([(430, 240), (480, 190), (560, 150), (612, 134)], 40),
            ([(468, 300), (500, 332)], 18),
            ([(1010, 262), (1050, 245)], 14),
            ([(1005, 500), (1055, 465)], 14),
        ],
        # o verde da grama e dos LEDs, o branco dos postes, o azul e o amarelo, longe da borda do contorno
        "certo_cor": True,
        # o pé do balão azul, deitado em cima da barra do canto da direita
        "corte": [[(1392, 212), (1442, 212), (1442, 248), (1392, 247)]],
        # o canto da grama que a foto cortou embaixo: o triângulo entre as duas bordas retas do tapete
        "grama": {"baixo": 90, "poligono": [(930, 638), (1441, 724), (1458, 638), (1462, 600), (1440, 600)],
                  "fonte": (1012, 590, 1185, 640)},
        # só na foto do showroom: a borda da frente do tapete, inclinada na foto (a câmera de cima e de
        # lado), fica reta (ver `para_cena`)
        "cisalhar": 0.162,
    },
}


# ---------------------------------------------------------------- as máscaras

def mascara_poligonos(tamanho, poligonos, linhas=(), escala=4):
    """Os polígonos (e as linhas grossas: (pontos, largura)) numa máscara de 0 a 1, macia (desenhada a 4x)."""
    w, h = tamanho
    m = Image.new("L", (w * escala, h * escala), 0)
    d = ImageDraw.Draw(m)
    for p in poligonos:
        d.polygon([(x * escala, y * escala) for x, y in p], fill=255)
    for pontos, largura in linhas:
        d.line([(x * escala, y * escala) for x, y in pontos], fill=255, width=largura * escala, joint="curve")
    return np.asarray(m.resize((w, h), Image.BOX), dtype=np.float32) / 255


def _morfologia(m, px, filtro):
    im = Image.fromarray((m > 0.5).astype(np.uint8) * 255)
    for _ in range(px):
        im = im.filter(filtro(3))
    return np.asarray(im) > 127


def encolher(m, px):
    return _morfologia(m, px, ImageFilter.MinFilter)


def crescer(m, px):
    return _morfologia(m, px, ImageFilter.MaxFilter)


def _caixa(arr, r, eixo):
    """A média numa janela de 2r+1 ao longo de `eixo` (pela soma acumulada; a borda se repete)."""
    pad = [(0, 0)] * arr.ndim
    pad[eixo] = (r + 1, r)
    a = np.pad(arr, pad, mode="edge")
    c = np.cumsum(a, axis=eixo, dtype=np.float64)
    n = arr.shape[eixo]
    fim = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=eixo)
    ini = np.take(c, np.arange(0, n), axis=eixo)
    return ((fim - ini) / (2 * r + 1)).astype(np.float32)


def borrar(arr, sigma):
    """Quase uma gaussiana (três caixas seguidas, nos dois eixos)."""
    r = max(1, round(sigma * 0.85))
    out = arr.astype(np.float32)
    for _ in range(3):
        out = _caixa(_caixa(out, r, 0), r, 1)
    return out


def media_local(cor, onde, sigma):
    """A cor média só de `onde`, espalhada em volta (onde não há vizinho perto, um raio 4x maior)."""
    pesos = onde.astype(np.float32)
    soma, total = borrar(cor * pesos[..., None], sigma), borrar(pesos, sigma)[..., None]
    soma2, total2 = borrar(cor * pesos[..., None], sigma * 4), borrar(pesos, sigma * 4)[..., None]
    return np.where(total > 0.02, soma / np.maximum(total, 1e-6), soma2 / np.maximum(total2, 1e-6))


def ligado(fg, semente):
    """Os pixels de `fg` ligados a `semente` (4 vizinhos)."""
    h, w = fg.shape
    vis = (semente & fg).copy()
    fila = deque(zip(*np.nonzero(vis)))
    while fila:
        y, x = fila.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and fg[yy, xx] and not vis[yy, xx]:
                vis[yy, xx] = True
                fila.append((yy, xx))
    return vis


# ---------------------------------------------------------------- a borda

def acabamento(rgb, geo, faixa, sigma, contraste=(25, 70)):
    """A borda macia pela cor e sem o fundo, numa faixa de `faixa` px dos dois lados da borda de `geo`.

    `geo` (0 a 1) diz onde é a máquina. Por dentro dela (encolhida) é máquina; por fora (crescida),
    fundo; na faixa, o alfa sai da cor: o quanto o pixel está da cor do fundo em volta (B) para a cor
    da máquina em volta (F). Onde F e B quase não se distinguem, vale `geo`. Devolve (cor, alfa).
    """
    dentro = encolher(geo, faixa)
    fora = ~crescer(geo, faixa)
    faixa_m = ~dentro & ~fora
    F = media_local(rgb, dentro, sigma)
    B = media_local(rgb, fora, sigma)
    FB = F - B
    n2 = (FB ** 2).sum(-1)
    proj = np.clip(((rgb - B) * FB).sum(-1) / np.maximum(n2, 1), 0, 1)
    # a borda firme: a peça na sombra (mais escura que a média dela) não fica meio transparente
    t = np.clip((proj - 0.2) / 0.5, 0, 1)
    pela_cor = t * t * (3 - 2 * t)
    c = np.clip((np.sqrt(n2) - contraste[0]) / (contraste[1] - contraste[0]), 0, 1)
    alfa = np.where(dentro, 1.0, np.where(fora, 0.0, c * pela_cor + (1 - c) * geo))
    # só o que está ligado à máquina; os pontinhos soltos da faixa somem
    ok = ligado(alfa > 0.5, dentro)
    alfa = np.where((alfa > 0.5) & ~ok, 0, alfa)
    alfa = np.where(faixa_m & (alfa < 0.5) & ~crescer(ok.astype(np.float32), 2), 0, alfa)
    # a cor sem o fundo (o vermelho do neon que vazou na borda): (C - (1 - a) B) / a, só no pixel meio
    # transparente e na medida dele (o opaco fica com a cor dele)
    a3 = alfa[..., None]
    limpa = np.clip((rgb - (1 - a3) * B) / np.maximum(a3, 0.35), 0, 255)
    peso = np.clip((1 - a3) * 2, 0, 1)
    cor = np.where(faixa_m[..., None] & (a3 > 0), rgb * (1 - peso) + limpa * peso, rgb)
    return cor, alfa


# ---------------------------------------------------------------- os dois jeitos

def pelo_contorno(rgb, dados):
    h, w, _ = rgb.shape
    geo = mascara_poligonos((w, h), dados["contorno"])
    return acabamento(rgb, geo, faixa=dados.get("faixa", 5), sigma=6)


def pelo_grabcut(rgb, dados):
    import cv2  # (só para refazer o Air Rock e o Kid Play)

    h, w, _ = rgb.shape
    contorno = mascara_poligonos((w, h), dados["contorno"]) > 0.5
    fundo = mascara_poligonos((w, h), dados.get("fundo", ())) > 0.5
    certo = mascara_poligonos((w, h), dados.get("certo", ()), dados.get("certo_linhas", ())) > 0.5
    mapa = np.full((h, w), cv2.GC_BGD, np.uint8)
    mapa[contorno] = cv2.GC_PR_FGD
    if dados.get("certo_cor"):
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
        cores = ((g > r + 25) & (g > b + 10)) | ((mn > 205) & (mx - mn < 40)) | (b > r + 70) | ((r > 200) & (g > 185) & (b < 110))
        mapa[cores & encolher(contorno.astype(np.float32), 14)] = cv2.GC_FGD
    # (o fundo certo vence a cor: o balão verde e azul encostado no poste da direita)
    mapa[fundo] = cv2.GC_BGD
    mapa[certo] = cv2.GC_FGD
    modelo_fundo, modelo_maquina = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    bgr = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
    cv2.setRNGSeed(7)  # (o mesmo recorte a cada vez que roda)
    cv2.grabCut(bgr, mapa, None, modelo_fundo, modelo_maquina, 8, cv2.GC_INIT_WITH_MASK)
    fg = (mapa == cv2.GC_FGD) | (mapa == cv2.GC_PR_FGD)
    # só as manchas grandes (a máquina); os buraquinhos pequenos cercados viram máquina (os vãos grandes ficam)
    n, rotulos, stats, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8), connectivity=8)
    fg = np.isin(rotulos, [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 0.002 * fg.size])
    n, rotulos, stats, _ = cv2.connectedComponentsWithStats((~fg).astype(np.uint8), connectivity=4)
    fg |= np.isin(rotulos, [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] < 0.0004 * fg.size])
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    cor, alfa = acabamento(rgb, fg.astype(np.float32), faixa=2, sigma=4)
    if dados.get("grama"):
        cor, alfa = completar_grama(cor, alfa, dados["grama"])
    return cor, alfa


def completar_grama(cor, alfa, g):
    """O canto do piso de grama que a foto cortou embaixo, numa tela `baixo` px mais alta.

    O triângulo que falta (`poligono`) é coberto com um pedaço de grama lisa da própria foto
    (`fonte`: x0, y0, x1, y1, sem poste nem LED), em ladrilhos que se sobrepõem pela metade e se
    misturam aos poucos (sem emenda), cada um de um lugar diferente do pedaço; só onde a foto não cobre.
    """
    h, w, _ = cor.shape
    novo_h = h + g["baixo"]
    cor2 = np.zeros((novo_h, w, 3), np.float32)
    alfa2 = np.zeros((novo_h, w), np.float32)
    cor2[:h], alfa2[:h] = cor, alfa
    falta = mascara_poligonos((w, novo_h), [g["poligono"]])
    x0, y0, x1, y1 = g["fonte"]
    fonte = cor[y0:y1, x0:x1]
    th, tw = 40, 120
    soma = np.zeros((novo_h, w, 3), np.float32)
    peso = np.zeros((novo_h, w), np.float32)
    janela = np.outer(np.minimum(np.arange(th) + 1, th - np.arange(th)), np.minimum(np.arange(tw) + 1, tw - np.arange(tw))).astype(np.float32)
    sorte = np.random.default_rng(5)
    ys, xs = np.nonzero(falta > 0)
    for ty in range(ys.min() - th // 2, ys.max() + 1, th // 2):
        for tx in range(xs.min() - tw // 2, xs.max() + 1, tw // 2):
            sy = int(sorte.integers(0, fonte.shape[0] - th + 1))
            sx = int(sorte.integers(0, fonte.shape[1] - tw + 1))
            a0, b0, a1, b1 = max(ty, 0), max(tx, 0), min(ty + th, novo_h), min(tx + tw, w)
            if a0 >= a1 or b0 >= b1:
                continue
            pa, pb = a0 - ty, b0 - tx
            jn = janela[pa:pa + a1 - a0, pb:pb + b1 - b0]
            soma[a0:a1, b0:b1] += fonte[sy + pa:sy + pa + a1 - a0, sx + pb:sx + pb + b1 - b0] * jn[..., None]
            peso[a0:a1, b0:b1] += jn
    grama = soma / np.maximum(peso, 1e-6)[..., None]
    m = falta * (1 - alfa2)
    return cor2 * (1 - m[..., None]) + grama * m[..., None], np.maximum(alfa2, falta)


# ---------------------------------------------------------------- o recorte

def recorte(chave):
    """O recorte da máquina `chave` (RGBA, no tamanho da foto de origem, aparado com 8 px de folga)."""
    dados = CONTORNOS[chave]
    rgb = np.asarray(Image.open(ORIGEM / dados["origem"]).convert("RGB"), dtype=np.float32)
    cor, alfa = (pelo_grabcut if dados["metodo"] == "grabcut" else pelo_contorno)(rgb, dados)
    if dados.get("corte"):
        # o que é fundo com certeza (a borda reta de baixo, o anel de luz do chão): macio, desenhado a 4x
        alfa = alfa * (1 - mascara_poligonos((alfa.shape[1], alfa.shape[0]), dados["corte"]))
    imagem = Image.fromarray(np.dstack([np.clip(cor, 0, 255), np.clip(alfa * 255, 0, 255)]).astype(np.uint8), "RGBA")
    x0, y0, x1, y1 = imagem.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return imagem.crop((max(0, x0 - 8), max(0, y0 - 8), min(imagem.width, x1 + 8), min(imagem.height, y1 + 8)))


def para_cena(chave, imagem):
    """O recorte como a foto do showroom precisa: a base no chão de ponta a ponta.

    Na cena, a máquina é a foto de pé no chão (um plano): só encosta no chão o que está na linha de
    baixo da foto. O Kid Play foi fotografado de cima e de lado: a borda da frente do tapete de grama
    desce para a direita (`cisalhar`: tantos px por px), e a ponta da esquerda ficaria no ar. O
    cisalhamento vertical (cada coluna desce o quanto a borda sobe ali) deixa a borda reta, no chão,
    e os postes continuam de pé (as colunas não entortam). O recorte guardado para as artes fica como
    a foto (sem isso).
    """
    k = CONTORNOS[chave].get("cisalhar")
    if not k:
        return imagem
    w, h = imagem.size
    extra = round(k * w)
    # (o PIL leva da saída para a origem: y_origem = y_saida - k (w - x))
    saida = imagem.transform((w, h + extra), Image.AFFINE, (1, 0, 0, k, 1, -k * w), resample=Image.BICUBIC)
    caixa = saida.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return saida.crop(caixa)


def guardar(chave):
    """Grava o recorte para as artes (core/static/site/black_friday/recortes/<chave>.webp) e o devolve."""
    imagem = recorte(chave)
    RECORTES.mkdir(parents=True, exist_ok=True)
    saida = RECORTES / f"{chave}.webp"
    imagem.save(saida, "WEBP", lossless=True, quality=100, method=6, exact=False)
    return saida, imagem


def main(chaves):
    for chave in chaves or CONTORNOS:
        saida, imagem = guardar(chave)
        print(f"{chave}: {saida.relative_to(RAIZ)} {imagem.width}x{imagem.height} ({saida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
