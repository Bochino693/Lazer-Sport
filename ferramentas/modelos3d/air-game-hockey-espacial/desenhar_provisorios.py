"""A arte PROVISÓRIA dos adesivos do Air Game Hockey Espacial (adesivos/<peça>.png).

    python3 desenhar_provisorios.py            # todas as peças
    python3 desenhar_provisorios.py tampo      # só esta

Enquanto a folha de adesivos da fábrica não chega, cada peça ganha uma arte
no tema dela, no tamanho do pecas.json (a medida da face no 3D): o espaço
(céu com estrelas, redemoinhos, planetas e discos voadores), o chão lunar
laranja, o logotipo HOCKEY KIDS e alienígenas astronautas jogando hóquei --
formas simples, sem personagem de ninguém. Quando a folha chegar, o
recortar_adesivos.py troca estes arquivos pelas peças de verdade.
"""

import math
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parent))

from PIL import ImageDraw  # noqa: E402

from adesivos_comum import (  # noqa: E402
    Tela, chao_lunar, degrade, estrelas, ler_pecas, morros, nebulosa, planeta, semente, texto,
)

AZUL = "#1d4f8f"  # o azul da mesa (o de baixo das cabeceiras)
MOLDURA = "#1e56b0"  # a moldura azul do tampo
CEU = ("#090a2e", "#16135a", "#2a1166")
NEBULOSA = ("#ff3fb4", "#2fd3ff", "#8a5bff", "#3cffb0")
VERDE = "#7ee03a"
AMARELO = "#ffd21f"
CONTORNO = "#0b1240"


def logo(tela, cx, cy, altura):
    """O logotipo HOCKEY KIDS: HOCKEY em amarelo e KIDS em verde, com o contorno escuro e a sombra laranja."""
    texto(tela, (cx, cy - altura * 0.2), "HOCKEY", altura * 0.5, AMARELO, CONTORNO, altura * 0.06,
          sombra="#ff7a1a", deslocamento_mm=(altura * 0.03, altura * 0.04), italica=True)
    texto(tela, (cx, cy + altura * 0.33), "KIDS", altura * 0.4, VERDE, CONTORNO, altura * 0.06,
          sombra="#ff7a1a", deslocamento_mm=(altura * 0.03, altura * 0.04), italica=True)


def disco_voador(tela, cx, cy, largura):
    """Um disco voador com a cúpula, as luzes e um alienígena verde (só a cabeça e os olhos) dentro."""
    d = tela.d
    w, h = largura, largura * 0.26
    # a cúpula: o vidro azul-claro e a cabeça verde dentro
    d.ellipse([*tela.px(cx - w * 0.26, cy - h * 1.35), *tela.px(cx + w * 0.26, cy + h * 0.35)], fill="#9fe8ff", outline="#e8fbff",
              width=round(tela.px(w * 0.012)))
    cabeca = w * 0.12
    d.ellipse([*tela.px(cx - cabeca, cy - h * 0.95 - cabeca * 0.4), *tela.px(cx + cabeca, cy - h * 0.95 + cabeca * 1.4)], fill=VERDE)
    for lado in (-1, 1):
        ox = cx + lado * cabeca * 0.42
        d.ellipse([*tela.px(ox - cabeca * 0.24, cy - h * 0.72), *tela.px(ox + cabeca * 0.24, cy - h * 0.38)], fill="#111111")
    # o prato, com a faixa e as luzes
    d.ellipse([*tela.px(cx - w / 2, cy - h / 2), *tela.px(cx + w / 2, cy + h / 2)], fill="#b9c4d6", outline="#5d6880",
              width=round(tela.px(w * 0.014)))
    d.ellipse([*tela.px(cx - w * 0.44, cy - h * 0.06), *tela.px(cx + w * 0.44, cy + h * 0.4)], fill="#7f8aa3")
    for i in range(5):
        x = cx - w * 0.32 + w * 0.16 * i
        r = w * 0.03
        d.ellipse([*tela.px(x - r, cy + h * 0.1 - r), *tela.px(x + r, cy + h * 0.1 + r)], fill="#ffe14a")


def astronauta(tela, x, pe, altura, virado=1, traje="#f2f4f8"):
    """Um alienígena verde de traje espacial jogando hóquei (formas simples: capacete, corpo, taco)."""
    d = tela.d
    h = altura
    escuro = "#2b3550"
    grossa = round(tela.px(h * 0.012))
    # o taco: do alto das mãos até o chão, na frente, com a lâmina deitada
    mao = (x + virado * h * 0.2, pe - h * 0.48)
    ponta = (x + virado * h * 0.5, pe - h * 0.03)
    d.line([tela.px(*mao), tela.px(*ponta)], fill="#ff7a1a", width=round(tela.px(h * 0.035)))
    d.line([tela.px(*ponta), tela.px(ponta[0] + virado * h * 0.16, ponta[1])], fill="#ff7a1a", width=round(tela.px(h * 0.05)))
    # a mochila, as pernas e as botas
    d.rounded_rectangle([*tela.px(x - virado * h * 0.24 - h * 0.08, pe - h * 0.6), *tela.px(x - virado * h * 0.24 + h * 0.08, pe - h * 0.34)],
                        radius=tela.px(h * 0.03), fill="#c9cfdb", outline=escuro, width=grossa)
    for lado in (-1, 1):
        px0 = x + lado * h * 0.09
        passo = lado * virado * h * 0.04
        d.rounded_rectangle([*tela.px(px0 - h * 0.065 + passo, pe - h * 0.32), *tela.px(px0 + h * 0.065 + passo, pe - h * 0.05)],
                            radius=tela.px(h * 0.04), fill=traje, outline=escuro, width=grossa)
        d.rounded_rectangle([*tela.px(px0 - h * 0.08 + passo, pe - h * 0.08), *tela.px(px0 + h * 0.09 + passo, pe)],
                            radius=tela.px(h * 0.03), fill="#5b647a", outline=escuro, width=grossa)
    # o corpo, o painel do peito e os braços até o taco
    d.rounded_rectangle([*tela.px(x - h * 0.17, pe - h * 0.64), *tela.px(x + h * 0.17, pe - h * 0.28)],
                        radius=tela.px(h * 0.08), fill=traje, outline=escuro, width=grossa)
    d.rounded_rectangle([*tela.px(x - h * 0.07, pe - h * 0.53), *tela.px(x + h * 0.07, pe - h * 0.42)],
                        radius=tela.px(h * 0.02), fill="#ff3fb4", outline=escuro, width=grossa)
    for ombro in (x - virado * h * 0.12, x + virado * h * 0.12):
        d.line([tela.px(ombro, pe - h * 0.58), tela.px(*mao)], fill=escuro, width=round(tela.px(h * 0.075)))
        d.line([tela.px(ombro, pe - h * 0.58), tela.px(*mao)], fill=traje, width=round(tela.px(h * 0.05)))
    d.ellipse([*tela.px(mao[0] - h * 0.04, mao[1] - h * 0.04), *tela.px(mao[0] + h * 0.04, mao[1] + h * 0.04)], fill=VERDE, outline=escuro,
              width=grossa)
    # o capacete de vidro e a cabeça verde com os olhos grandes e as anteninhas
    cx, cy, r = x, pe - h * 0.8, h * 0.2
    d.ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], fill="#bdf2ff", outline=escuro, width=grossa)
    rc = r * 0.68
    for lado in (-1, 1):
        topo = (cx + lado * rc * 0.45, cy - rc * 1.25)
        d.line([tela.px(cx + lado * rc * 0.25, cy - rc * 0.6), tela.px(*topo)], fill="#3e8f1c", width=round(tela.px(h * 0.012)))
        d.ellipse([*tela.px(topo[0] - h * 0.018, topo[1] - h * 0.018), *tela.px(topo[0] + h * 0.018, topo[1] + h * 0.018)], fill="#ff3fb4")
    d.ellipse([*tela.px(cx - rc, cy - rc * 0.8), *tela.px(cx + rc, cy + rc * 1.05)], fill=VERDE)
    for lado in (-1, 1):
        ox = cx + lado * rc * 0.42 + virado * rc * 0.12
        d.ellipse([*tela.px(ox - rc * 0.26, cy - rc * 0.35), *tela.px(ox + rc * 0.26, cy + rc * 0.25)], fill="#141414")
        d.ellipse([*tela.px(ox - rc * 0.08, cy - rc * 0.28), *tela.px(ox + rc * 0.04, cy - rc * 0.16)], fill="#ffffff")
    d.arc([*tela.px(cx - rc * 0.32 + virado * rc * 0.1, cy + rc * 0.15), *tela.px(cx + rc * 0.32 + virado * rc * 0.1, cy + rc * 0.62)],
          20, 160, fill="#1f5a10", width=round(tela.px(h * 0.012)))
    # o brilho do vidro
    d.arc([*tela.px(cx - r * 0.8, cy - r * 0.8), *tela.px(cx + r * 0.8, cy + r * 0.8)], 200, 250, fill="#ffffff",
          width=round(tela.px(h * 0.018)))


def ceu(tela, sorte, area=None):
    """O fundo do espaço: o degradê, os redemoinhos e as estrelas."""
    x0, y0, x1, y1 = area or (0, 0, *tela.mm)
    fundo = degrade((round(tela.px(x1 - x0)), round(tela.px(y1 - y0))), CEU)
    tela.im.paste(fundo, (round(tela.px(x0)), round(tela.px(y0))))
    tela.d = ImageDraw.Draw(tela.im)
    nebulosa(tela, sorte, NEBULOSA, quantas=6, area=(x0, y0, x1, y1))
    area_mm = (x1 - x0) * (y1 - y0) / 1e6
    estrelas(tela, round(260 * area_mm), sorte, area=(x0, y0, x1, y1), brilhos=round(9 * area_mm) + 2)


def tampo(peca):
    largura, altura = peca["mm"]  # 2100 x 1064: o comprimento na horizontal
    tela = Tela((largura, altura), fundo=MOLDURA)
    sorte = semente("tampo")
    fim, lado = 180, 70  # a moldura: larga nas cabeceiras, estreita nos lados
    x0, x1, y0, y1 = fim, largura - fim, lado, altura - lado
    d = tela.d
    d.rectangle([*tela.px(x0, y0), *tela.px(x1, y1)], fill="#ffffff")
    # o chão lunar laranja nas duas cabeceiras do campo (a borda em morros, com crateras)
    for esquerda in (True, False):
        pts = []
        for i in range(31):
            t = i / 30
            y = y0 + (y1 - y0) * t
            fundo = 150 + 70 * math.sin(t * math.pi) + 26 * math.sin(t * math.pi * 7 + (0 if esquerda else 1.7))
            pts.append(((x0 + fundo) if esquerda else (x1 - fundo), y))
        borda = [(x0 if esquerda else x1, y0), *pts, (x0 if esquerda else x1, y1)]
        d.polygon([tela.px(*p) for p in borda], fill="#ff9a24")
        d.line([tela.px(*p) for p in pts], fill="#ffc24a", width=round(tela.px(10)))
        for k in range(7):
            cx = (x0 + sorte.uniform(30, 150)) if esquerda else (x1 - sorte.uniform(30, 150))
            cy = y0 + 70 + (y1 - y0 - 140) * (k + sorte.uniform(0.1, 0.9)) / 7
            r = sorte.uniform(18, 34)
            d.ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], fill="#ffc24a")
            d.ellipse([*tela.px(cx - r * 0.78, cy - r * 0.78), *tela.px(cx + r * 0.7, cy + r * 0.7)], fill="#e2620f")
    # as duas linhas azuis que dividem o campo em três
    for k in (1, 2):
        x = x0 + (x1 - x0) * k / 3
        d.rectangle([*tela.px(x - 6, y0), *tela.px(x + 6, y1)], fill=MOLDURA)
    # os círculos vermelhos perto dos cantos
    for cx in (x0 + 420, x1 - 420):
        for cy in (y0 + 210, y1 - 210):
            r = 80
            d.ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], outline="#e2232a", width=round(tela.px(12)))
            d.ellipse([*tela.px(cx - 14, cy - 14), *tela.px(cx + 14, cy + 14)], fill="#e2232a")
    # o logotipo no centro, sobre um círculo de céu
    cx, cy, r = largura / 2, altura / 2, 280
    mascara = tela.camada()
    ImageDraw.Draw(mascara).ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], fill=(255, 255, 255, 255))
    circulo = Tela((largura, altura), fundo="#000000")
    ceu(circulo, semente("tampo-centro"), area=(cx - r, cy - r, cx + r, cy + r))
    planeta(circulo, cx + r * 0.52, cy - r * 0.5, 48, "#ff7a1a", "#ffc24a", faixas=("#e2620f", "#ffb02e"), anel="#ffe28a")
    tela.im.paste(circulo.im, (0, 0), mascara)
    tela.d = ImageDraw.Draw(tela.im)
    tela.d.ellipse([*tela.px(cx - r, cy - r), *tela.px(cx + r, cy + r)], outline=MOLDURA, width=round(tela.px(14)))
    logo(tela, cx, cy, 300)
    # "Jogador 01" e "Jogador 02" nas cabeceiras, de frente para quem joga em cada uma, entre o campo e
    # a régua da borda (que cobre os 80 mm de fora)
    texto(tela, ((x1 + largura - 80) / 2, altura / 2), "JOGADOR 01", 56, "#ffffff", CONTORNO, 4, giro=90)
    texto(tela, ((80 + x0) / 2, altura / 2), "JOGADOR 02", 56, "#ffffff", CONTORNO, 4, giro=-90)
    return tela


def lateral(peca, nome):
    largura, altura = peca["mm"]  # 2100 x 1000, vista de fora; o y da imagem desce
    tela = Tela((largura, altura))
    sorte = semente(nome)
    ceu(tela, sorte)
    # planetas e discos voadores no alto (as pontas sobem até o alto da imagem; no meio, o alto é 115 mm)
    planeta(tela, 1880, 175, 82, "#ff7a1a", "#ffc24a", faixas=("#e2620f", "#ffb02e", "#e2620f"), anel="#ffe28a")
    planeta(tela, 230, 210, 58, "#2c7bff", "#8fd0ff", faixas=("#1b55c9", "#5fb2ff"))
    planeta(tela, 720, 190, 26, "#ff3fb4", "#ffa3dc")
    planeta(tela, 1430, 205, 20, "#3cffb0", "#c4ffe8")
    disco_voador(tela, 820, 175, 130)
    disco_voador(tela, 1290, 165, 110)
    # o chão lunar laranja embaixo (os pés da lateral ficam nele) e as crateras
    chao_lunar(tela, morros(0, largura, 470, 70, sorte), sorte, crateras=14)
    # os alienígenas astronautas jogando, um de cada lado do logotipo, e o disco no meio
    astronauta(tela, 520, 478, 300, virado=1)
    astronauta(tela, 1580, 478, 300, virado=-1, traje="#e9f7ff")
    tela.d.ellipse([*tela.px(990, 466), *tela.px(1060, 486)], fill="#e2232a", outline="#7a0d10", width=round(tela.px(3)))
    logo(tela, largura / 2, 300, 250)
    return tela


def cabeceira(peca, nome):
    largura, altura = peca["mm"]  # 1064 x 795: a arte em cima (55%), o azul liso embaixo (45%)
    tela = Tela((largura, altura), fundo=AZUL)
    sorte = semente(nome)
    arte = altura * 0.55
    ceu(tela, sorte, area=(0, 0, largura, arte))
    tela.d.rectangle([*tela.px(0, arte), *tela.px(largura, altura)], fill=AZUL)  # o brilho do céu não passa para o azul
    planeta(tela, largura * 0.84, 110, 56, "#ff7a1a", "#ffc24a", faixas=("#e2620f", "#ffb02e"), anel="#ffe28a")
    disco_voador(tela, largura * 0.16, 120, 150)
    chao_lunar(tela, morros(0, largura, arte - 40, 40, sorte), sorte, crateras=5, area=(0, 0, largura, arte))
    logo(tela, largura / 2, arte * 0.42, 170)
    # a emenda da arte com o azul: um friso laranja
    tela.d.rectangle([*tela.px(0, arte - 6), *tela.px(largura, arte + 6)], fill="#ff9a24")
    return tela


def main(so=()):
    pecas = ler_pecas(PASTA)
    feitas = {
        "tampo": lambda p: tampo(p),
        "lateral-esquerda": lambda p: lateral(p, "lateral-esquerda"),
        "lateral-direita": lambda p: lateral(p, "lateral-direita"),
        "lateral-esquerda-2": lambda p: cabeceira(p, "lateral-esquerda-2"),
        "lateral-direita-2": lambda p: cabeceira(p, "lateral-direita-2"),
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
