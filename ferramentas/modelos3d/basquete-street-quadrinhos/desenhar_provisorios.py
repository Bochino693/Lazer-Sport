"""A arte PROVISÓRIA dos adesivos do Basquete Street Quadrinhos (adesivos/<peça>.png).

    python3 desenhar_provisorios.py            # todas as peças
    python3 desenhar_provisorios.py prancha    # só esta

Enquanto a folha de adesivos da fábrica não chega, cada peça ganha uma arte
no tema dela, no tamanho do pecas.json (a medida da face no 3D): quadrinhos
em fundo preto, com as faixas arredondadas amarelas, laranja, vermelhas e
rosa, os pontinhos de retícula, os balões "POW!", "BOOM!" e "WOW!", o
letreiro BASKETBALL, duas crianças jogando (desenho simples, de pictograma),
a bola grande nas laterais de fora e a quadra com as linhas vermelhas na
prancha. Quando a folha chegar, o recortar_adesivos.py troca estes arquivos
pelas peças de verdade.
"""

import math
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parent))

from PIL import Image, ImageChops, ImageDraw  # noqa: E402

from adesivos_comum import Tela, capsula, ler_pecas, poligono_estrela, semente, texto  # noqa: E402

PRETO = "#0d0d10"
AMARELO = "#ffd21f"
LARANJA = "#ff8a1f"
VERMELHO = "#e8262c"
ROSA = "#ff4fa3"
BRANCO = "#ffffff"
CORES = (AMARELO, LARANJA, VERMELHO, ROSA)


def faixas(tela, sorte, angulo, largura, passo, area=None, cores=CORES, contorno=True):
    """As faixas arredondadas, em diagonal, de ponta a ponta (algumas cortadas pela borda)."""
    x0, y0, x1, y1 = area or (0, 0, *tela.mm)
    a = math.radians(angulo)
    ux, uy = math.cos(a), math.sin(a)  # ao longo
    nx, ny = -uy, ux  # de lado
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    meia = math.hypot(x1 - x0, y1 - y0) / 2
    d = tela.d
    k = -meia
    i = sorte.randrange(len(cores))
    while k < meia:
        comprimento = sorte.uniform(0.35, 0.8) * meia
        centro = sorte.uniform(-meia * 0.6, meia * 0.6)
        px, py = cx + nx * k + ux * centro, cy + ny * k + uy * centro
        pts = capsula(*tela.px(px - ux * comprimento, py - uy * comprimento), *tela.px(px + ux * comprimento, py + uy * comprimento),
                      tela.px(largura))
        d.polygon(pts, fill=cores[i % len(cores)], outline=PRETO if contorno else None, width=round(tela.px(largura * 0.06)))
        i += sorte.randrange(1, len(cores))
        k += passo * sorte.uniform(0.85, 1.25)


def reticula(tela, area, cor, passo, raio_max, direcao=(1, 0)):
    """Os pontinhos de retícula (os quadrinhos antigos), maiores para um lado."""
    x0, y0, x1, y1 = area
    camada = tela.camada()
    d = ImageDraw.Draw(camada)
    dx, dy = direcao
    linha = 0
    y = y0
    while y <= y1:
        x = x0 + (passo / 2 if linha % 2 else 0)
        while x <= x1:
            t = ((x - x0) / max(1, x1 - x0)) * dx + ((y - y0) / max(1, y1 - y0)) * dy
            r = raio_max * max(0.08, min(1, t if dx + dy > 0 else 1 + t))
            d.ellipse([*tela.px(x - r, y - r), *tela.px(x + r, y + r)], fill=cor)
            x += passo
        y += passo * 0.87
        linha += 1
    tela.colar(camada)


def explosao(tela, cx, cy, r, frase, sorte, cor=AMARELO, borda=VERMELHO, letra=VERMELHO, pontas=14, achatar=1.0, giro=-8,
             altura_texto=None):
    """O balão de explosão dos quadrinhos ("POW!", "BOOM!"): a estrela irregular dupla e a frase."""
    d = tela.d
    for raio, preenche in ((r * 1.12, borda), (r, cor)):
        pts = poligono_estrela(cx, cy, raio, raio * 0.66, pontas, giro=sorte.uniform(0, 1), sorte=sorte)
        pts = [(cx + (x - cx), cy + (y - cy) * achatar) for x, y in pts]
        d.polygon([tela.px(*p) for p in pts], fill=preenche, outline=PRETO, width=round(tela.px(r * 0.035)))
    if frase:
        texto(tela, (cx, cy), frase, altura_texto or r * 0.5, letra, PRETO, r * 0.05, giro=giro, sombra=PRETO,
              deslocamento_mm=(r * 0.035, r * 0.035), italica=True, largura_max_mm=r * 1.45)


def letreiro(tela, cx, cy, altura, giro=0, largura_max=None):
    """O letreiro BASKETBALL: laranja com o contorno preto, a borda branca e a sombra vermelha."""
    texto(tela, (cx, cy), "BASKETBALL", altura, AMARELO, PRETO, altura * 0.09, giro=giro, sombra=VERMELHO,
          deslocamento_mm=(altura * 0.06, altura * 0.07), italica=True, largura_max_mm=largura_max)


def bola(tela, cx, cy, r, contorno=True):
    """Uma bola de basquete: laranja, com o brilho e os gomos pretos (a cruz e as duas curvas)."""
    g = round(tela.px(r * 0.045))
    tela.d.ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], fill="#f07a1d")
    brilho = tela.camada()
    ImageDraw.Draw(brilho).ellipse([*tela.px(cx - r * 0.62, cy - r * 0.7), *tela.px(cx - r * 0.05, cy - r * 0.2)], fill=(255, 214, 140, 150))
    tela.colar(brilho, desfoque=r * 0.08)
    gomos = tela.camada()
    d = ImageDraw.Draw(gomos)
    d.line([tela.px(cx - r, cy), tela.px(cx + r, cy)], fill=PRETO, width=g)
    d.line([tela.px(cx, cy - r), tela.px(cx, cy + r)], fill=PRETO, width=g)
    for lado in (-1, 1):  # as curvas: um arco de um círculo maior, com o centro fora da bola
        ccx, R = cx + lado * r * 1.45, r * 1.05
        d.ellipse([*tela.px(ccx - R, cy - R), *tela.px(ccx + R, cy + R)], outline=PRETO, width=g)
    dentro = Image.new("L", tela.im.size, 0)
    ImageDraw.Draw(dentro).ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], fill=255)
    gomos.putalpha(ImageChops.multiply(gomos.getchannel("A"), dentro))
    tela.colar(gomos)
    if contorno:
        tela.d.ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], outline=PRETO, width=g)


def crianca(tela, x, pe, h, pose, camisa, numero, pele="#f2b98a", cabelo="#3a2414", virado=1):
    """Uma criança jogando, em desenho simples (pictograma com o contorno dos quadrinhos)."""
    d = tela.d
    g = round(tela.px(h * 0.012))

    def membro(a, b, largura, cor):
        d.polygon(capsula(*tela.px(*a), *tela.px(*b), tela.px(largura)), fill=cor, outline=PRETO, width=g)

    quadril = (x, pe - h * 0.47)
    # as pernas (uma dobrada no drible) e os tênis
    pes = ((x - h * 0.1, pe - h * 0.04), (x + h * 0.12 * virado, pe - h * 0.04)) if pose == "drible" else \
        ((x - h * 0.07, pe - h * 0.06), (x + h * 0.07, pe - h * 0.02))
    for k, p in enumerate(pes):
        joelho = (x + (-1 if k == 0 else 1) * h * 0.08 + (h * 0.05 * virado if pose == "drible" and k else 0), pe - h * 0.26)
        membro((quadril[0] + (-1 if k == 0 else 1) * h * 0.06, quadril[1]), joelho, h * 0.1, pele)
        membro(joelho, p, h * 0.09, pele)
        d.rounded_rectangle([*tela.px(p[0] - h * 0.06, p[1] - h * 0.04), *tela.px(p[0] + h * 0.08, p[1] + h * 0.03)],
                            radius=tela.px(h * 0.03), fill=BRANCO, outline=PRETO, width=g)
    # o calção e a camiseta com o número
    d.rounded_rectangle([*tela.px(x - h * 0.15, pe - h * 0.52), *tela.px(x + h * 0.15, pe - h * 0.36)], radius=tela.px(h * 0.04),
                        fill="#1f2a8a", outline=PRETO, width=g)
    d.rounded_rectangle([*tela.px(x - h * 0.15, pe - h * 0.78), *tela.px(x + h * 0.15, pe - h * 0.48)], radius=tela.px(h * 0.06),
                        fill=camisa, outline=PRETO, width=g)
    texto(tela, (x, pe - h * 0.63), numero, h * 0.1, BRANCO, PRETO, h * 0.012)
    # os braços e a bola
    ombros = ((x - h * 0.13, pe - h * 0.74), (x + h * 0.13, pe - h * 0.74))
    if pose == "arremesso":
        bx, by, br = x + h * 0.03 * virado, pe - h * 1.12, h * 0.1
        maos = ((bx - br * 0.8, by + br * 0.4), (bx + br * 0.8, by + br * 0.4))
    else:
        bx, by, br = x + h * 0.3 * virado, pe - h * 0.2, h * 0.1
        maos = ((x - h * 0.3 * virado, pe - h * 0.6), (bx, by - br * 1.05)) if virado > 0 else ((bx, by - br * 1.05), (x + h * 0.3, pe - h * 0.6))
    for ombro, mao in zip(ombros, maos):
        cotovelo = ((ombro[0] + mao[0]) / 2 + (ombro[0] - x) * 0.4, (ombro[1] + mao[1]) / 2 + h * 0.03)
        membro(ombro, cotovelo, h * 0.08, pele)
        membro(cotovelo, mao, h * 0.075, pele)
    bola(tela, bx, by, br)
    if pose == "drible":  # o risco do movimento da bola
        for k in range(3):
            xx = bx - br * 0.6 + k * br * 0.6
            d.line([tela.px(xx, by + br * 1.3), tela.px(xx, by + br * 1.9)], fill=BRANCO, width=g)
    # a cabeça: o rosto, o cabelo, os olhos e o sorriso
    cx, cy, r = x, pe - h * 0.88, h * 0.11
    d.ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], fill=pele, outline=PRETO, width=g)
    d.chord([*tela.px(cx - r * 1.04, cy - r * 1.1), *tela.px(cx + r * 1.04, cy + r * 0.6)], 180, 360, fill=cabelo, outline=PRETO, width=g)
    for lado in (-1, 1):
        ox = cx + lado * r * 0.38 + virado * r * 0.12
        d.ellipse([*tela.px(ox - r * 0.1, cy + r * 0.02), *tela.px(ox + r * 0.1, cy + r * 0.26)], fill=PRETO)
    d.arc([*tela.px(cx - r * 0.42 + virado * r * 0.1, cy + r * 0.1), *tela.px(cx + r * 0.42 + virado * r * 0.1, cy + r * 0.66)],
          20, 160, fill=PRETO, width=g)


def lateral_externa(peca, nome):
    largura, altura = peca["mm"]  # 2150 x 2400; a esquerda tem a parte alta à esquerda da imagem
    tela = Tela((largura, altura), px_por_mm=0.5, fundo=PRETO)
    sorte = semente(nome)
    espelho = nome.endswith("direita")
    X = (lambda v: largura - v) if espelho else (lambda v: v)
    faixas(tela, sorte, -35 if not espelho else 35, 150, 330)
    reticula(tela, (0, 0, largura, 1450), VERMELHO, 60, 15, direcao=(0, -1))
    # a bola grande na parte alta, com a retícula de sombra e o brilho
    cx, cy, r = X(470), 760, 420
    tela.d.ellipse([*tela.px(cx - r * 1.12, cy - r * 1.12), *tela.px(cx + r * 1.12, cy + r * 1.12)], fill=AMARELO, outline=PRETO,
                   width=round(tela.px(14)))
    bola(tela, cx, cy, r)
    # o balão do "WOW!" na diagonal
    explosao(tela, X(1090), 1110, 170, "WOW!", sorte, cor=ROSA, borda=AMARELO, letra=AMARELO)
    # embaixo, ao longo da parte baixa: as duas crianças e a explosão com o BASKETBALL
    explosao(tela, largura / 2 + (60 if not espelho else -60), 1960, 560, None, sorte, cor=AMARELO, borda=VERMELHO, pontas=18, achatar=0.5)
    letreiro(tela, largura / 2 + (60 if not espelho else -60), 1960, 170, giro=6 if not espelho else -6, largura_max=1050)
    crianca(tela, X(300), 2330, 820, "arremesso", VERMELHO, "10", virado=1 if not espelho else -1)
    crianca(tela, X(1880), 2330, 760, "drible", "#2fa8ff", "7", pele="#c98a5a", cabelo="#151010", virado=-1 if not espelho else 1)
    return tela


def lateral_interna(peca, nome):
    largura, altura = peca["mm"]  # 2131 x 1601, em L (a parte alta à direita na esquerda; à esquerda na direita)
    tela = Tela((largura, altura), px_por_mm=0.5, fundo=PRETO)
    sorte = semente(nome)
    espelho = nome.endswith("direita")
    faixas(tela, sorte, 28 if not espelho else -28, 190, 300)
    reticula(tela, (0, 0, largura, altura), ROSA, 66, 14, direcao=(0, -1))
    alto = (largura - 680, 0, largura, altura) if not espelho else (0, 0, 680, altura)
    explosao(tela, (alto[0] + alto[2]) / 2, 520, 250, "WOW!", sorte, cor=AMARELO, borda=ROSA, letra=VERMELHO)
    return tela


def fundo_cesta(peca):
    largura, altura = peca["mm"]  # 960 x 1371: a cesta fica a ~430 mm do alto
    tela = Tela((largura, altura), px_por_mm=0.6, fundo=PRETO)
    sorte = semente("fundo-cesta")
    faixas(tela, sorte, 60, 120, 260, area=(0, 300, largura, altura))
    reticula(tela, (0, 0, largura, altura), VERMELHO, 52, 13, direcao=(0, 1))
    # a janela branca do placar, no alto
    tela.d.rounded_rectangle([*tela.px(230, 70), *tela.px(730, 240)], radius=tela.px(22), fill=BRANCO, outline=VERMELHO,
                             width=round(tela.px(12)))
    texto(tela, (480, 155), "00", 110, "#20232a")
    # o "BOOM!" embaixo da cesta
    explosao(tela, largura / 2, 880, 360, "BOOM!", sorte, cor=AMARELO, borda=VERMELHO, letra=VERMELHO, pontas=16)
    return tela


def teto_interno(peca):
    largura, altura = peca["mm"]  # 960 x 681
    tela = Tela((largura, altura), px_por_mm=0.5, fundo=PRETO)
    sorte = semente("teto-interno")
    faixas(tela, sorte, -20, 110, 210)
    reticula(tela, (0, 0, largura, altura), AMARELO, 52, 11, direcao=(1, 0))
    return tela


def testeira_frente(peca):
    largura, altura = peca["mm"]  # 1000 x 300
    tela = Tela((largura, altura), px_por_mm=1.0, fundo=PRETO)
    sorte = semente("testeira-frente")
    faixas(tela, sorte, -12, 70, 120, cores=(VERMELHO, ROSA, LARANJA))
    reticula(tela, (0, 0, largura, altura), AMARELO, 34, 7, direcao=(1, 0))
    bola(tela, 85, altura / 2, 64)
    bola(tela, largura - 85, altura / 2, 64)
    letreiro(tela, largura / 2, altura / 2, 120, largura_max=640)
    return tela


def testeira_teto(peca):
    largura, altura = peca["mm"]  # 1000 x 430
    tela = Tela((largura, altura), px_por_mm=0.5, fundo=PRETO)
    faixas(tela, semente("testeira-teto"), 15, 90, 170)
    return tela


def testeira_lado(peca):
    largura, altura = peca["mm"]  # 430 x 300
    tela = Tela((largura, altura), px_por_mm=0.8, fundo=PRETO)
    sorte = semente("testeira-lado")
    faixas(tela, sorte, 30, 60, 110)
    explosao(tela, largura / 2, altura / 2, 120, "WOW!", sorte, cor=ROSA, borda=AMARELO, letra=AMARELO)
    return tela


def prancha(peca):
    largura, comprimento = peca["mm"]  # 960 x 2143: a cesta no alto da imagem
    tela = Tela((largura, comprimento), px_por_mm=0.6, fundo=PRETO)
    d = tela.d
    g = round(tela.px(22))
    m = 35  # as linhas de fora, rente às laterais
    d.rectangle([*tela.px(m, m), *tela.px(largura - m, comprimento - m)], outline=VERMELHO, width=g)
    cesta = (largura / 2, 150)
    # o garrafão e o círculo do lance livre
    d.rectangle([*tela.px(largura / 2 - 175, m), *tela.px(largura / 2 + 175, 640)], outline=VERMELHO, width=g)
    d.ellipse([*tela.px(largura / 2 - 175, 640 - 175), *tela.px(largura / 2 + 175, 640 + 175)], outline=VERMELHO, width=g)
    # a tabela e o aro desenhados
    d.line([tela.px(largura / 2 - 90, 95), tela.px(largura / 2 + 90, 95)], fill=VERMELHO, width=g)
    d.ellipse([*tela.px(cesta[0] - 32, cesta[1] - 32), *tela.px(cesta[0] + 32, cesta[1] + 32)], outline=VERMELHO, width=round(tela.px(14)))
    # a linha de três: as retas dos lados e o arco
    r3 = 690
    canto = 110
    yr = cesta[1] + math.sqrt(r3 ** 2 - (largura / 2 - canto) ** 2)
    d.line([tela.px(canto, m), tela.px(canto, yr)], fill=VERMELHO, width=g)
    d.line([tela.px(largura - canto, m), tela.px(largura - canto, yr)], fill=VERMELHO, width=g)
    a = math.degrees(math.acos((largura / 2 - canto) / r3))
    d.arc([*tela.px(cesta[0] - r3, cesta[1] - r3), *tela.px(cesta[0] + r3, cesta[1] + r3)], a, 180 - a, fill=VERMELHO, width=g)
    # o meio da quadra: a linha e o círculo
    meio = comprimento - 330
    d.line([tela.px(m, meio), tela.px(largura - m, meio)], fill=VERMELHO, width=g)
    d.ellipse([*tela.px(largura / 2 - 175, meio - 175), *tela.px(largura / 2 + 175, meio + 175)], outline=VERMELHO, width=g)
    return tela


def faixa_rampa(peca):
    largura, altura = peca["mm"]  # 474 x 90
    tela = Tela((largura, altura), px_por_mm=2.0, fundo=AMARELO)
    tela.d.rectangle([*tela.px(0, altura - 14), *tela.px(largura, altura)], fill=VERMELHO)
    tela.d.rectangle([*tela.px(0, 0), *tela.px(largura, 10)], fill=VERMELHO)
    texto(tela, (largura / 2, altura / 2 - 2), "BASKETBALL", 46, VERMELHO, PRETO, 4, italica=True, largura_max_mm=largura * 0.9)
    return tela


def poste(peca):
    largura, altura = peca["mm"]  # 60 x 960
    tela = Tela((largura, altura), px_por_mm=1.0, fundo=PRETO)
    d = tela.d
    for k, y in enumerate(range(-60, round(altura) + 60, 70)):  # as listras inclinadas
        d.polygon([tela.px(0, y), tela.px(largura, y - 40), tela.px(largura, y), tela.px(0, y + 40)], fill=CORES[k % len(CORES)])
    return tela


def frente(peca):
    largura, altura = peca["mm"]  # 1000 x 900
    tela = Tela((largura, altura), px_por_mm=0.75, fundo=PRETO)
    sorte = semente("frente")
    faixas(tela, sorte, -25, 120, 220)
    reticula(tela, (0, 0, largura, altura), ROSA, 48, 11, direcao=(0, 1))
    explosao(tela, 700, 250, 230, "POW!", sorte, cor=AMARELO, borda=VERMELHO, letra=VERMELHO)
    bola(tela, 230, 260, 150)
    letreiro(tela, largura / 2, 580, 145, giro=4, largura_max=880)
    return tela


def frente_lateral(peca):
    largura, altura = peca["mm"]  # 250 x 900
    tela = Tela((largura, altura), px_por_mm=1.0, fundo=PRETO)
    sorte = semente("frente-lateral")
    faixas(tela, sorte, -60, 70, 120)
    explosao(tela, largura / 2, 230, 120, "POW!", sorte, cor=AMARELO, borda=VERMELHO, letra=VERMELHO, altura_texto=58)
    bola(tela, largura / 2, 640, 80)
    return tela


def main(so=()):
    pecas = ler_pecas(PASTA)
    feitas = {
        "lateral-externa-esquerda": lambda p: lateral_externa(p, "lateral-externa-esquerda"),
        "lateral-externa-direita": lambda p: lateral_externa(p, "lateral-externa-direita"),
        "lateral-interna-esquerda": lambda p: lateral_interna(p, "lateral-interna-esquerda"),
        "lateral-interna-direita": lambda p: lateral_interna(p, "lateral-interna-direita"),
        "fundo-cesta": fundo_cesta, "teto-interno": teto_interno, "testeira-frente": testeira_frente,
        "testeira-teto": testeira_teto, "testeira-lado": testeira_lado, "prancha": prancha, "faixa-rampa": faixa_rampa,
        "poste": poste, "frente": frente, "frente-lateral": frente_lateral,
    }
    destino = PASTA / "adesivos"
    destino.mkdir(exist_ok=True)
    for nome, desenhar in feitas.items():
        if so and nome not in so:
            continue
        # 256 cores: o PNG fica 4 vezes menor (é só a arte provisória; o recorte da folha fica com todas)
        imagem = desenhar(pecas[nome]).salvar(destino / f"{nome}.png", cores=256)
        print(f"{nome}: {imagem.width} x {imagem.height} px")


if __name__ == "__main__":
    main(sys.argv[1:])
