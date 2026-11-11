"""Os adesivos do Air Game Kids dos astronautas, para o mesmo móvel do Alienígenas.

  * as laterais: a lateral da foto do catálogo, desentortada pela perspectiva
    (f7/desentortar.py, o contorno da folha dos alienígenas encaixado na foto
    com 0,7 px de erro); a do outro lado é a mesma arte (as laterais da folha
    da fábrica são iguais) -- vista de fora, o espelho da primeira;
  * as cabeceiras: o fundo espacial da própria foto (a faixa de cima, sem
    personagens) com o logotipo do produto (o círculo "Air Hockey Espacial
    Kids" da lateral);
  * o tampo: o do Alienígenas, com o campo, as linhas e os gols como são,
    e no lugar do chão lunar laranja, o fundo espacial da foto; no meio, o
    logotipo do produto; as marquinhas "HOCKEY KIDS" das pontas saem.
Nada de personagem novo: só pedaços da foto.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

AQUI = Path(__file__).resolve().parent
ALIEN = AQUI.parent / "air-game-kids-alienigenas"
SAIDA = AQUI / "adesivos"
import json  # noqa: E402

formas = json.loads((ALIEN / "formas.json").read_text())


def preencher_fora(img, mascara, passos=40):
    """Estende as cores de dentro para fora da máscara (sem franja branca na borda)."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    m = (np.asarray(mascara) > 127).astype(np.float32)
    soma = a * m[..., None]
    peso = m.copy()
    for _ in range(passos):
        viz = np.zeros_like(soma)
        vp = np.zeros_like(peso)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            viz += np.roll(np.roll(soma, dy, 0), dx, 1)
            vp += np.roll(np.roll(peso, dy, 0), dx, 1)
        novo = (peso == 0) & (vp > 0)
        soma[novo] = viz[novo] / vp[novo][:, None]
        peso[novo] = 1
    return Image.fromarray(np.clip(soma, 0, 255).astype(np.uint8))


# ---- as laterais ----
lateral = Image.open(AQUI / "lateral-desentortada.png").convert("RGB")  # 988 x 592, branco fora do contorno
W, H = lateral.size
mascara = Image.new("L", (W, H), 0)
ImageDraw.Draw(mascara).polygon([(u * W, v * H) for u, v in formas["lateral-esquerda"]["contorno"]], fill=255)
mascara = mascara.filter(ImageFilter.MinFilter(5))  # 2 px para dentro: o branco da borda da foto fica de fora
lateral = preencher_fora(lateral, mascara)
# a outra lateral é a mesma arte (o montar.js lê a mesma imagem nas duas: as laterais da folha são iguais)
lateral.save(SAIDA / "lateral-esquerda.png")

# ---- o fundo espacial: o azul-escuro do espaço da foto e os dois planetas dos cantos (sem personagens) ----
lat = np.asarray(lateral)
azul = tuple(int(v) for v in np.median(lat[445:470, 430:570].reshape(-1, 3), axis=0))
planeta_amarelo = lateral.crop((50, 100, 230, 190))   # o canto de cima, à esquerda
planeta_laranja = lateral.crop((770, 100, 950, 190))  # o canto de cima, à direita
logo_caixa = (382, 152, 618, 388)  # o círculo "Air Hockey Espacial Kids" na lateral desentortada
logo = lateral.crop(logo_caixa)
mlogo = Image.new("L", logo.size, 0)
ImageDraw.Draw(mlogo).ellipse((4, 4, logo.size[0] - 4, logo.size[1] - 4), fill=255)
mlogo = mlogo.filter(ImageFilter.GaussianBlur(2))


def com_logo(fundo, diametro, centro):
    img = fundo.copy()
    lg = logo.resize((diametro, diametro), Image.LANCZOS)
    mk = mlogo.resize((diametro, diametro), Image.LANCZOS)
    img.paste(lg, (centro[0] - diametro // 2, centro[1] - diametro // 2), mk)
    return img


def pena(tam, borda):
    """A máscara de um retângulo com as bordas macias (o pedaço se funde no azul)."""
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).rectangle((borda, borda, tam[0] - borda, tam[1] - borda), fill=255)
    return m.filter(ImageFilter.GaussianBlur(borda / 2))


def colar(fundo, pedaco, caixa, borda=14):
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    pedaco = pedaco.resize((w, h), Image.LANCZOS)
    fundo.paste(pedaco, caixa[:2], pena((w, h), borda))


# ---- as cabeceiras (271 x 135 na folha; aqui no dobro): o azul do espaço, um planeta de cada lado e o logotipo ----
cw, ch = 542, 270
for nome, (a_, b_) in {"lateral-esquerda-2": (planeta_amarelo, planeta_laranja),
                       "lateral-direita-2": (planeta_laranja, planeta_amarelo)}.items():
    cab = Image.new("RGB", (cw, ch), azul)
    colar(cab, a_, (0, 40, 230, 155))
    colar(cab, b_.transpose(Image.FLIP_TOP_BOTTOM), (312, 115, 542, 230))
    com_logo(cab, 230, (cw // 2, ch // 2)).save(SAIDA / f"{nome}.png")

# ---- o tampo ----
tampo = Image.open(ALIEN / "adesivos/tampo.png").convert("RGB")
tw, th = tampo.size
arr = np.asarray(tampo).astype(np.float32) / 255
mx, mn = arr.max(-1), arr.min(-1)
sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
# o matiz em graus
delta = np.maximum(mx - mn, 1e-6)
hue = np.where(mx == r, ((g - b) / delta) % 6, np.where(mx == g, (b - r) / delta + 2, (r - g) / delta + 4)) * 60
laranja = ((hue <= 58) | (hue >= 340)) & (sat > 0.38) & (mx > 0.35)
# os quatro gols (os círculos vermelhos com a cruz) ficam
gols = Image.new("L", (tw, th), 0)
for gx, gy in ((0.135, 0.265), (0.135, 0.72), (0.865, 0.265), (0.865, 0.72)):
    ImageDraw.Draw(gols).ellipse((gx * tw - 19, gy * th - 19, gx * tw + 19, gy * th + 19), fill=255)
laranja &= ~(np.asarray(gols) > 127)
# só dentro do campo (a moldura azul fica)
campo = np.zeros_like(laranja)
campo[int(th * 0.07):int(th * 0.93), int(tw * 0.08):int(tw * 0.92)] = True
# o miolo (o logotipo dos alienígenas) vira campo branco e recebe o logotipo do produto
miolo = Image.new("L", (tw, th), 0)
cx, cy = tw // 2, int(th * 0.47)
ImageDraw.Draw(miolo).ellipse((cx - 94, cy - 82, cx + 94, cy + 82), fill=255)
miolo = np.asarray(miolo) > 127
troca = laranja & campo & ~miolo
# os cantos do campo: os planetas da foto (o amarelo à esquerda, o laranja à direita), no azul do espaço
fundo = Image.new("RGB", (tw, th), azul)
cw2, ch2 = int(tw * 0.30), int(th * 0.32)
x0, y0, x1, y1 = int(tw * 0.08), int(th * 0.07), int(tw * 0.92), int(th * 0.93)
colar(fundo, planeta_amarelo, (x0, y0, x0 + cw2, y0 + ch2), 8)
colar(fundo, planeta_amarelo.transpose(Image.FLIP_TOP_BOTTOM), (x0, y1 - ch2, x0 + cw2, y1), 8)
colar(fundo, planeta_laranja, (x1 - cw2, y0, x1, y0 + ch2), 8)
colar(fundo, planeta_laranja.transpose(Image.FLIP_TOP_BOTTOM), (x1 - cw2, y1 - ch2, x1, y1), 8)
novo = np.asarray(tampo).copy()
espaco = np.asarray(fundo)
m = Image.fromarray((troca * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
m = np.asarray(m).astype(np.float32)[..., None] / 255
novo = (novo * (1 - m) + espaco * m).astype(np.uint8)
# o miolo branco (como o campo) e o logotipo do produto
branco = np.array([250, 251, 252], np.uint8)
novo[miolo] = branco
tampo_novo = Image.fromarray(novo)
# as linhas azuis do meio do campo voltam por cima do miolo branco (as do tampo de antes)
azulado = (np.asarray(tampo).astype(int)[..., 2] > 120) & (np.asarray(tampo).astype(int)[..., 0] < 60)
# só as colunas das linhas do campo (o azul do logotipo dos alienígenas não volta)
colunas = azulado[int(th * 0.1):int(th * 0.9)].mean(axis=0) > 0.5
colunas = np.convolve(colunas.astype(int), np.ones(3, int), mode="same") > 0
linhas = azulado & miolo & colunas[None, :]
arr2 = np.asarray(tampo_novo).copy()
arr2[linhas] = np.asarray(tampo)[linhas]
tampo_novo = com_logo(Image.fromarray(arr2), 132, (cx, cy))
# as marquinhas "HOCKEY KIDS" das pontas (a marca dos alienígenas) saem: a cor da moldura
d = ImageDraw.Draw(tampo_novo)
moldura = tuple(int(v) for v in np.median(np.asarray(tampo)[2:10, 100:360].reshape(-1, 3), axis=0))
for caixa in ((6, 186, 30, 216), (433, 46, 457, 78)):
    d.rectangle(caixa, fill=moldura)
tampo_novo = tampo_novo.resize((tw * 2, th * 2), Image.LANCZOS)
tampo_novo.save(SAIDA / "tampo.png")

# a prévia das peças
prev = Image.new("RGB", (988 + 20 + 922, 592 + 20 + 270), (240, 240, 245))
prev.paste(lateral, (0, 0))

prev.paste(tampo_novo, (1008, 0))
prev.paste(Image.open(SAIDA / "lateral-esquerda-2.png"), (0, 612))
prev.paste(Image.open(SAIDA / "lateral-direita-2.png"), (562, 612))
prev.save(AQUI / "previa-pecas.png")
print("ok", tampo_novo.size)
