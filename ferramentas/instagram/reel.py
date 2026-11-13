#!/usr/bin/env python3
"""Gera um Reel vertical (1080x1920) editado a partir de videos e fotos reais.

Uso:
  python3 ferramentas/instagram/reel.py roteiro.json saida.mp4

Cada cena do roteiro tem uma fonte e um modelo de card:

  fonte:   "video" (+ "inicio"), "foto" (+ "foco" 0..1 para o corte lateral),
           "quadros" (pasta de PNGs com fundo transparente, ex.: giro 3D feito
           por girar3d.js) ou "palco" (lista de recortes lado a lado, cada um
           com "imagem" ou "quadros", "altura", "cx" e "base" em pixels)
  modelo:  "heroi"   titulo grande central com adesivo inclinado
           "card"    card inferior com icone ("lado": "esquerda" | "direita")
           "numero"  numero gigante com estrela + texto
           "medidas" linhas de cota desenhadas sobre a foto ("linhas")
           "final"   encerramento com logo e botao
  comuns:  "duracao", "etiqueta", "titulo", "texto", "icone", "cores"
           "enquadre": "inteiro" mostra a foto ou o video inteiro numa janela
           acima do card, sem cortar o brinquedo (use sempre em foto de produto)

Icones: pino, camera, trofeu, radar, lampada, cubo, regua, conversa, estrela
(ou um texto curto, ex.: "5"). Veja o modelo em exemplos/strike_kids.json.

Precisa de ffmpeg, Pillow e da fonte Inter instalados.
"""
import glob
import json
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
SB = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
INK = (14, 16, 34)
WHITE = (255, 255, 255)
GRN = (37, 211, 102)
# Vermelho e azul da marca + verde, amarelo e roxo do LED das maquinas.
LED = [(240, 69, 106), (255, 210, 26), (43, 227, 91), (25, 211, 255), (155, 92, 255)]
PALETA = [("#FFD21A", "#FF7A00"), ("#FF2E93", "#9B5CFF"), ("#2BE35B", "#19D3FF"),
          ("#19D3FF", "#6C8CFF"), ("#FF7A00", "#F0456A")]


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font(p, s):
    return ImageFont.truetype(p, int(s))


def medir(d, t, f, stroke=0):
    b = d.textbbox((0, 0), t, font=f, stroke_width=stroke)
    return b[2] - b[0], b[3] - b[1], b


def lista(v):
    return v if isinstance(v, list) else [v]


def ajustar(d, linhas, caminho_fonte, maximo, largura):
    s = maximo
    while s > 40 and max(medir(d, l, font(caminho_fonte, s))[0] for l in linhas) > largura:
        s -= 2
    return font(caminho_fonte, s)


def degrade(size, c1, c2, vertical=False):
    w, h = size
    n = h if vertical else w
    faixa = Image.new("RGB", (n, 1))
    for i in range(n):
        k = i / max(1, n - 1)
        faixa.putpixel((i, 0), tuple(int(c1[j] + (c2[j] - c1[j]) * k) for j in range(3)))
    if vertical:
        return faixa.rotate(-90, expand=True).resize((w, h))
    return faixa.resize((w, h))


def texto_degrade(camada, pos, t, f, c1, c2, contorno=0):
    """Texto preenchido com degrade e contorno escuro opcional; devolve a altura."""
    d = ImageDraw.Draw(camada)
    w, h, b = medir(d, t, f, contorno)
    if contorno:
        d.text((pos[0] - b[0], pos[1] - b[1]), t, font=f, fill=INK + (255,),
               stroke_width=contorno, stroke_fill=INK + (255,))
    m = Image.new("L", (w + 8, h + 8), 0)
    ImageDraw.Draw(m).text((4 - b[0], 4 - b[1]), t, font=f, fill=255)
    cor = degrade(m.size, c1, c2).convert("RGBA")
    cor.putalpha(m)
    camada.alpha_composite(cor, (pos[0] - 4, pos[1] - 4))
    return h


def suave(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def mola(x):
    """Entrada com leve estouro (passa de 1 e volta)."""
    x = max(0.0, min(1.0, x))
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2


# ---------------------------------------------------------------- icones
def icone(nome, tam, cor=WHITE, tinta=INK):
    S = tam * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, k = cor + (255,), tinta + (255,)
    e = int(S * .07)

    def P(x, y):
        return (x * S, y * S)

    def elipse(x0, y0, x1, y1, fill):
        d.ellipse([P(x0, y0), P(x1, y1)], fill=fill)

    if nome == "pino":
        elipse(.36, .08, .56, .28, c)
        d.polygon([P(.40, .24), P(.52, .24), P(.56, .46), P(.36, .46)], fill=c)
        elipse(.26, .36, .66, .94, c)
        d.rectangle([P(.385, .285), P(.535, .315)], fill=k)
        d.rectangle([P(.375, .345), P(.545, .375)], fill=k)
        elipse(.58, .62, .90, .94, k)
        elipse(.61, .65, .87, .91, c)
        for x, y in ((.70, .73), (.77, .73), (.74, .80)):
            elipse(x - .02, y - .02, x + .02, y + .02, k)
    elif nome == "camera":
        d.rounded_rectangle([P(.38, .20), P(.62, .34)], radius=S * .04, fill=c)
        d.rounded_rectangle([P(.12, .28), P(.88, .80)], radius=S * .10, fill=c)
        elipse(.33, .37, .67, .71, k)
        elipse(.41, .45, .59, .63, c)
        elipse(.73, .36, .80, .43, k)
    elif nome == "trofeu":
        d.polygon([P(.28, .14), P(.72, .14), P(.66, .52), P(.34, .52)], fill=c)
        elipse(.30, .34, .70, .64, c)
        d.arc([P(.10, .16), P(.36, .46)], 90, 270, fill=c, width=e)
        d.arc([P(.64, .16), P(.90, .46)], 270, 90, fill=c, width=e)
        d.rectangle([P(.45, .60), P(.55, .76)], fill=c)
        d.rounded_rectangle([P(.28, .74), P(.72, .88)], radius=S * .03, fill=c)
    elif nome == "radar":
        for r in (.40, .27):
            d.arc([P(.5 - r, .56 - r), P(.5 + r, .56 + r)], 200, 340, fill=c, width=e)
        elipse(.40, .46, .60, .66, c)
        d.rectangle([P(.47, .62), P(.53, .88)], fill=c)
    elif nome == "lampada":
        elipse(.26, .12, .74, .60, c)
        d.rounded_rectangle([P(.38, .54), P(.62, .74)], radius=S * .03, fill=c)
        d.rounded_rectangle([P(.41, .78), P(.59, .86)], radius=S * .03, fill=c)
        d.line([P(.44, .30), P(.50, .44), P(.56, .30)], fill=k, width=int(S * .045))
    elif nome == "cubo":
        topo = [P(.5, .10), P(.86, .30), P(.5, .50), P(.14, .30)]
        esq = [P(.14, .36), P(.47, .55), P(.47, .92), P(.14, .72)]
        dirt = [P(.86, .36), P(.53, .55), P(.53, .92), P(.86, .72)]
        for p in (topo, esq, dirt):
            d.polygon(p, fill=c)
    elif nome == "regua":
        d.line([P(.14, .5), P(.86, .5)], fill=c, width=e)
        for x, s in ((.14, 1), (.86, -1)):
            d.polygon([P(x - s * .04, .5), P(x + s * .14, .36), P(x + s * .14, .64)], fill=c)
        d.line([P(.10, .26), P(.10, .74)], fill=c, width=e)
        d.line([P(.90, .26), P(.90, .74)], fill=c, width=e)
    elif nome == "conversa":
        d.rounded_rectangle([P(.12, .18), P(.88, .70)], radius=S * .14, fill=c)
        d.polygon([P(.26, .66), P(.24, .88), P(.46, .68)], fill=c)
        for x in (.33, .50, .67):
            elipse(x - .05, .39, x + .05, .49, k)
    elif nome == "estrela":
        d.polygon(pontas(.5 * S, .52 * S, .42 * S, .18 * S, 5), fill=c)
    else:
        t = str(nome)[:3]
        f = font(XB, S * (.72 if len(t) == 1 else .46))
        w, h, b = medir(d, t, f)
        d.text(((S - w) / 2 - b[0], (S - h) / 2 - b[1]), t, font=f, fill=c)
    return im.resize((tam, tam), Image.LANCZOS)


def pontas(cx, cy, r1, r2, n, giro=0.0):
    pts = []
    for i in range(2 * n):
        a = math.pi / n * i - math.pi / 2 + giro
        r = r1 if i % 2 == 0 else r2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def azulejo(nome, lado, c1, c2, giro=-8):
    """Icone em quadrado arredondado (estilo app), com borda branca e inclinado."""
    S = lado * 3
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=S * .28, fill=WHITE + (255,))
    miolo = degrade((S, S), c1, c2, vertical=True).convert("RGBA")
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle([S * .06, S * .06, S * .94, S * .94], radius=S * .23, fill=255)
    base.paste(miolo, (0, 0), m)
    ic = icone(nome, int(S * .66), cor=WHITE, tinta=c2)
    base.alpha_composite(ic, ((S - ic.width) // 2, (S - ic.height) // 2))
    base = base.resize((lado, lado), Image.LANCZOS)
    return base.rotate(giro, expand=True, resample=Image.BICUBIC)


# ---------------------------------------------------------------- modelos de card
def painel(ov, caixa, c1, c2, raio=48):
    x0, y0, x1, y1 = caixa
    borda = degrade((x1 - x0, y1 - y0), c1, c2).convert("RGBA")
    mb = Image.new("L", borda.size, 0)
    ImageDraw.Draw(mb).rounded_rectangle([0, 0, borda.width - 1, borda.height - 1], radius=raio, fill=255)
    borda.putalpha(mb)
    ov.alpha_composite(borda, (x0, y0))
    miolo = degrade((x1 - x0 - 14, y1 - y0 - 14), (30, 16, 84), (10, 10, 34), vertical=True).convert("RGBA")
    mm = Image.new("L", miolo.size, 0)
    ImageDraw.Draw(mm).rounded_rectangle([0, 0, miolo.width - 1, miolo.height - 1], radius=raio - 7, fill=246)
    miolo.putalpha(mm)
    ov.alpha_composite(miolo, (x0 + 7, y0 + 7))


def etiqueta(ov, xy, t, cor, tam=38, giro=0):
    f = font(XB, tam)
    w, h, b = medir(ImageDraw.Draw(ov), t, f)
    tag = Image.new("RGBA", (w + 56, tam + 34), (0, 0, 0, 0))
    d = ImageDraw.Draw(tag)
    d.rounded_rectangle([0, 0, tag.width - 1, tag.height - 1], radius=tag.height // 2, fill=cor + (255,),
                        outline=WHITE + (255,), width=4)
    d.text((28 - b[0], (tag.height - h) // 2 - b[1]), t, font=f, fill=INK + (255,))
    if giro:
        tag = tag.rotate(giro, expand=True, resample=Image.BICUBIC)
    ov.alpha_composite(tag, xy)
    return tag.size


def modelo_card(c, c1, c2):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    direita = c.get("lado") == "direita"
    x0, x1, pad, lado = 54, W - 54, 48, 176
    larg = x1 - x0 - 2 * pad
    tit, sub = lista(c["titulo"]), lista(c.get("texto", []))
    ft = ajustar(d, tit, XB, c.get("tamanho", 110), larg)
    fs = ajustar(d, sub, SB, 52, larg) if sub else None
    alt_t = sum(medir(d, l, ft)[1] for l in tit) + 16 * (len(tit) - 1)
    alt_s = sum(medir(d, l, fs)[1] for l in sub) + 14 * (len(sub) - 1) if sub else 0
    y1 = 1600
    y0 = y1 - (lado // 2 + 40 + alt_t + (26 + alt_s if sub else 0) + pad + 24)
    painel(ov, (x0, y0, x1, y1), c1, c2)
    az = azulejo(c.get("icone", "estrela"), lado, c1, c2, 8 if direita else -8)
    ax = x1 - pad - az.width + 10 if direita else x0 + pad - 10
    ov.alpha_composite(az, (ax, y0 - az.height // 2 - 6))
    k = c.get("etiqueta", "")
    if k:
        kw = medir(d, k, font(XB, 38))[0] + 56
        etiqueta(ov, (x0 + pad if direita else x1 - pad - kw, y0 - 36), k, c1)
    y = y0 + lado // 2 + 40
    for l in tit:
        w = medir(d, l, ft)[0]
        y += texto_degrade(ov, (x1 - pad - w if direita else x0 + pad, y), l, ft, c1, c2) + 16
    y += 10
    for l in sub:
        w, h, b = medir(d, l, fs)
        d.text(((x1 - pad - w if direita else x0 + pad) - b[0], y - b[1]), l, font=fs, fill=WHITE + (255,))
        y += h + 14
    ov.alpha_composite(degrade((larg, 8), c1, c2).convert("RGBA"), (x0 + pad, y1 - pad + 4))
    return ov


def modelo_heroi(c, c1, c2):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    tit, sub = lista(c["titulo"]), lista(c.get("texto", []))
    ft = ajustar(d, tit, XB, c.get("tamanho", 190), W - 150)
    y = 1180
    k = c.get("etiqueta", "")
    if k:
        tw, th = etiqueta(ov, (90, y - 30), k, c1, tam=44, giro=5)
        y += th + 6
    for l in tit:
        w = medir(d, l, ft, 14)[0]
        y += texto_degrade(ov, ((W - w) // 2 + 14, y), l, ft, c1, c2, contorno=14) + 34
    if sub:
        fs = ajustar(d, sub, SB, 50, W - 220)
        alt = sum(medir(d, l, fs)[1] for l in sub) + 12 * (len(sub) - 1)
        lw = max(medir(d, l, fs)[0] for l in sub)
        d.rounded_rectangle([(W - lw) // 2 - 40, y, (W + lw) // 2 + 40, y + alt + 44], radius=40,
                            fill=INK + (235,), outline=c1 + (255,), width=4)
        yy = y + 22
        for l in sub:
            w, h, b = medir(d, l, fs)
            d.text(((W - w) // 2 - b[0], yy - b[1]), l, font=fs, fill=WHITE + (255,))
            yy += h + 12
    return ov


def modelo_numero(c, c1, c2):
    """Camada fixa (texto); a estrela e o numero sao desenhados por quadro."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    tit, sub = lista(c["titulo"]), lista(c.get("texto", []))
    x = 470
    larg = W - 70 - x
    ft = ajustar(d, tit, XB, 92, larg)
    fs = ajustar(d, sub, SB, 46, larg) if sub else None
    alt = sum(medir(d, l, ft)[1] + 14 for l in tit) + (sum(medir(d, l, fs)[1] + 12 for l in sub) if sub else 0)
    y0 = 1420 - alt // 2 - 44
    painel(ov, (x - 150, y0, W - 54, y0 + alt + 96), c1, c2)
    y = y0 + 46
    for l in tit:
        y += texto_degrade(ov, (x, y), l, ft, c1, c2) + 14
    y += 6
    for l in sub:
        w, h, b = medir(d, l, fs)
        d.text((x - b[0], y - b[1]), l, font=fs, fill=WHITE + (255,))
        y += h + 12
    k = c.get("etiqueta", "")
    if k:
        etiqueta(ov, (x, y0 - 36), k, c1)
    return ov


def desenhar_numero(fr, c, c1, c2, t, a):
    cx, cy, r = 250, 1420, 215
    est = Image.new("RGBA", (2 * r + 40, 2 * r + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(est)
    d.polygon(pontas(r + 20, r + 20, r + 16, r * .80, 14, t * 0.9), fill=WHITE + (255,))
    d.polygon(pontas(r + 20, r + 20, r, r * .76, 14, t * 0.9), fill=c1 + (255,))
    d.ellipse([r + 20 - r * .66, r + 20 - r * .66, r + 20 + r * .66, r + 20 + r * .66], fill=c2 + (255,))
    num = str(c.get("numero", "5"))
    f = font(XB, 300 if len(num) == 1 else 190)
    w, h, b = medir(d, num, f, 10)
    d.text((r + 20 - w / 2 - b[0], r + 20 - h / 2 - b[1]), num, font=f, fill=WHITE + (255,),
           stroke_width=10, stroke_fill=INK + (255,))
    s = max(0.05, mola(a))
    est = est.resize((int(est.width * s), int(est.height * s)), Image.BICUBIC)
    fr.paste(est, (cx - est.width // 2, cy - est.height // 2), est)


def desenhar_medidas(fr, c, c1, c2, t):
    d = ImageDraw.Draw(fr, "RGBA")
    f = font(XB, 54)
    for i, ln in enumerate(c.get("linhas", [])):
        a = suave((t - 0.25 - i * 0.35) / 0.5)
        if a <= 0:
            continue
        cor = LED[(i + 1) % len(LED)]
        (xa, ya), (xb, yb) = ln["de"], ln["ate"]
        xm, ym = xa + (xb - xa) * a, ya + (yb - ya) * a
        d.line([(xa, ya), (xm, ym)], fill=INK + (255,), width=18)
        d.line([(xa, ya), (xm, ym)], fill=cor + (255,), width=10)
        for (px, py) in ((xa, ya), (xm, ym)):
            d.ellipse([px - 17, py - 17, px + 17, py + 17], fill=WHITE + (255,), outline=INK + (255,), width=5)
        if a > 0.6:
            w, h, b = medir(d, ln["rotulo"], f)
            cx, cy = ln.get("pos", [(xa + xb) / 2, (ya + yb) / 2])
            d.rounded_rectangle([cx - w / 2 - 30, cy - h / 2 - 22, cx + w / 2 + 30, cy + h / 2 + 22], radius=40,
                                fill=cor + (255,), outline=WHITE + (255,), width=5)
            d.text((cx - w / 2 - b[0], cy - h / 2 - b[1]), ln["rotulo"], font=f, fill=INK + (255,))


def modelo_medidas(c, c1, c2):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if c.get("titulo"):
        d = ImageDraw.Draw(ov)
        t = lista(c["titulo"])[0]
        f = ajustar(d, [t], XB, 64, W - 400)
        w, h, b = medir(d, t, f)
        x, y = W - 70 - w - 60, 240
        d.rounded_rectangle([x, y, x + w + 60, y + h + 52], radius=44, fill=INK + (240,), outline=c1 + (255,), width=5)
        texto_degrade(ov, (x + 30, y + 26), t, f, c1, c2)
    return ov


def modelo_final(c, c1, c2, caminho_logo):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    y = 340
    if caminho_logo:
        lg = Image.open(caminho_logo).convert("RGBA")
        lg = lg.resize((560, int(lg.height * 560 / lg.width)), Image.LANCZOS)
        ov.alpha_composite(lg, ((W - 560) // 2, y))
        y += lg.height + 64
    k = c.get("etiqueta", "")
    if k:
        kw = medir(d, k, font(XB, 40))[0] + 56
        _, th = etiqueta(ov, ((W - kw) // 2, y), k, c1, tam=40)
        y += th + 40
    tit = lista(c.get("titulo", []))
    ft = ajustar(d, tit, XB, c.get("tamanho", 100), W - 150)
    for l in tit:
        w = medir(d, l, ft, 8)[0]
        y += texto_degrade(ov, ((W - w) // 2 + 8, y), l, ft, c1, c2, contorno=8) + 26
    y += 20
    fs = font(SB, 54)
    for l in lista(c.get("texto", [])):
        w, h, b = medir(d, l, fs)
        d.text(((W - w) // 2 - b[0], y - b[1]), l, font=fs, fill=WHITE + (255,))
        y += h + 16
    y += 44
    t = c.get("botao")
    if t:
        fb = font(XB, 58)
        w, h, b = medir(d, t, fb)
        ic = icone("conversa", 84, cor=INK, tinta=GRN)
        bw = w + ic.width + 24
        d.rounded_rectangle([(W - bw) // 2 - 50, y, (W + bw) // 2 + 50, y + 132], radius=66, fill=GRN + (255,),
                            outline=WHITE + (255,), width=5)
        ov.alpha_composite(ic, ((W - bw) // 2, y + 24))
        d.text(((W - bw) // 2 + ic.width + 24 - b[0], y + (132 - h) // 2 - b[1]), t, font=fb, fill=INK + (255,))
    return ov


# ---------------------------------------------------------------- efeitos globais
def moldura():
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([14, 14, W - 15, H - 15], radius=66, fill=255)
    d.rounded_rectangle([30, 30, W - 31, H - 31], radius=50, fill=0)
    faixa = Image.new("RGB", (2 * W, 1))
    n = len(LED)
    for x in range(2 * W):
        p = (x % W) / W * n
        a, b = LED[int(p) % n], LED[(int(p) + 1) % n]
        k = p - int(p)
        faixa.putpixel((x, 0), tuple(int(a[j] + (b[j] - a[j]) * k) for j in range(3)))
    return faixa.resize((2 * W, H)), m.filter(ImageFilter.GaussianBlur(0.8))


def sombra_fundo():
    s = Image.new("L", (1, H), 0)
    for y in range(H):
        a = 0
        if y > 1100:
            a = int(135 * min(1, (y - 1100) / 450))
        if y < 420:
            a = max(a, int(110 * (1 - y / 420)))
        s.putpixel((0, y), a)
    return s.resize((W, H))


def camada_logo(caminho_logo):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not caminho_logo:
        return ov
    lg = Image.open(caminho_logo).convert("RGBA")
    lg = lg.resize((int(lg.width * 150 / lg.height), 150), Image.LANCZOS)
    x, y = 64, 196
    som = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    som.paste((0, 0, 0, 170), (x, y + 8), lg.getchannel("A"))
    ov.alpha_composite(som.filter(ImageFilter.GaussianBlur(12)))
    ov.alpha_composite(lg, (x, y))
    return ov


def confete(fr, tempo, forca=1.0):
    d = ImageDraw.Draw(fr, "RGBA")
    rnd = random.Random(7)
    for i in range(34):
        x0, vel, tam, fase = rnd.random() * W, 60 + rnd.random() * 140, 7 + rnd.random() * 13, rnd.random() * 6.28
        y = (H + 80) - ((tempo * vel + rnd.random() * H) % (H + 160))
        x = x0 + 30 * math.sin(tempo * 1.7 + fase)
        cor = LED[i % len(LED)]
        al = int(230 * forca)
        if i % 3 == 0:
            d.polygon(pontas(x, y, tam * 1.5, tam * .45, 4, tempo * 2 + fase), fill=cor + (al,))
        else:
            d.ellipse([x - tam / 2, y - tam / 2, x + tam / 2, y + tam / 2], fill=cor + (al,))


def brilho_neon(fr, forca=0.34):
    """Halo de luz: as areas claras 'vazam' cor, como LED em ambiente escuro."""
    p = fr.resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7))
    p = ImageEnhance.Brightness(ImageEnhance.Color(p).enhance(1.6)).enhance(0.75).resize((W, H), Image.BILINEAR)
    return Image.blend(fr, ImageChops.screen(fr, p), forca)


def aproximar(fr, z):
    if z <= 1.001:
        return fr
    w, h = int(W / z), int(H / z)
    l, t = (W - w) // 2, (H - h) // 2
    return fr.resize((W, H), Image.BILINEAR, box=(l, t, l + w, t + h))


def fundo_3d(c1, c2, tempo):
    base = degrade((W, H), (64, 22, 150), (10, 12, 48), vertical=True).convert("RGBA")
    raios = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(raios)
    cx, cy, R, n = W // 2, 760, 1700, 14
    for i in range(n):
        a0 = 2 * math.pi * i / n + tempo * 0.35
        a1 = a0 + math.pi / n
        cor = (c1 if i % 2 == 0 else c2) + (70,)
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                   (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=cor)
    base.alpha_composite(raios)
    luz = Image.new("L", (W // 8, H // 8), 0)
    ImageDraw.Draw(luz).ellipse([10, 30, W // 8 - 10, H // 8 - 70], fill=150)
    luz = luz.filter(ImageFilter.GaussianBlur(26)).resize((W, H))
    base.paste(Image.new("RGBA", (W, H), WHITE + (255,)), (0, 0), luz.point(lambda v: v // 3))
    return base.convert("RGB")


# ---------------------------------------------------------------- fontes de quadros
GRADE = ("scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,"
         "unsharp=7:7:1.1:5:5:0.0,eq=contrast=1.14:saturation=1.5:brightness=0.015:gamma=1.04,"
         "vibrance=intensity=0.4")


def quadros_video(mov, inicio, dur):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(inicio), "-t", str(dur + 0.2), "-i", mov, "-vf", GRADE,
                          "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    for _ in range(int(round(dur * FPS))):
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        yield Image.frombytes("RGB", (W, H), b)
    p.stdout.close()
    p.wait()


def enquadrar(img, c1, c2, t, fundo=None):
    """Mostra a imagem INTEIRA numa janela acima do card, sobre o proprio fundo desfocado."""
    if fundo is None:
        sc = max(W / img.width, H / img.height)
        f = img.resize((int(img.width * sc / 8) + 1, int(img.height * sc / 8) + 1), Image.BILINEAR)
        f = ImageEnhance.Brightness(f.filter(ImageFilter.GaussianBlur(5))).enhance(0.5).resize(
            (int(img.width * sc) + 1, int(img.height * sc) + 1), Image.BILINEAR)
        l, tp = (f.width - W) // 2, (f.height - H) // 2
        fundo = f.crop((l, tp, l + W, tp + H))
    fr = fundo.copy()
    x0, y0, x1, y1 = 60, 150, W - 60, 1100
    s = min((x1 - x0) / img.width, (y1 - y0) / img.height) * (0.94 + 0.06 * mola(t / 0.45))
    w, h = int(img.width * s), int(img.height * s)
    jan = img.resize((w, h), Image.LANCZOS if img.width > w else Image.BICUBIC)
    x, y = (W - w) // 2, y0 + (y1 - y0 - h) // 2
    b = 10
    som = Image.new("L", (W, H), 0)
    ImageDraw.Draw(som).rounded_rectangle([x - b, y - b + 16, x + w + b, y + h + b + 16], radius=44, fill=190)
    fr.paste((0, 0, 0), (0, 0), som.filter(ImageFilter.GaussianBlur(22)))
    borda = degrade((w + 2 * b, h + 2 * b), c1, c2).convert("RGBA")
    mb = Image.new("L", borda.size, 0)
    ImageDraw.Draw(mb).rounded_rectangle([0, 0, borda.width - 1, borda.height - 1], radius=44, fill=255)
    fr.paste(borda, (x - b, y - b), mb)
    mj = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mj).rounded_rectangle([0, 0, w - 1, h - 1], radius=36, fill=255)
    fr.paste(jan, (x, y), mj)
    return fr, fundo


def quadros_foto(path, dur, foco=0.5, inteiro=False):
    im = Image.open(path).convert("RGB")
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.4)).enhance(1.1)
    if inteiro:
        for _ in range(int(round(dur * FPS))):
            yield im
        return
    sc = max(W / im.width, H / im.height)
    r = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    l, t = int((r.width - W) * foco), (r.height - H) // 2
    r = r.crop((l, t, l + W, t + H))
    for _ in range(int(round(dur * FPS))):
        yield r.copy()


def quadros_palco(itens, dur, c1, c2, caminho):
    """Varios recortes (PNG/WebP com fundo transparente ou pastas de giro 3D) lado a lado."""
    prep = []
    for it in itens:
        if "quadros" in it:
            prep.append((it, sorted(glob.glob(os.path.join(caminho(it["quadros"]), "*.png"))), None))
        else:
            im = Image.open(caminho(it["imagem"])).convert("RGBA")
            prep.append((it, None, im.crop(im.getbbox())))
    n = int(round(dur * FPS))
    for k in range(n):
        fr = fundo_3d(c1, c2, k / FPS)
        for j, (it, arqs, fixo) in enumerate(prep):
            if arqs:
                m = Image.open(arqs[min(len(arqs) - 1, int(k * len(arqs) / n))]).convert("RGBA")
                m = m.crop(m.getbbox())
            else:
                m = fixo
            entra = mola((k / FPS - 0.12 * j) / 0.5)  # cada recorte "pula" para o lugar
            s = it["altura"] / m.height
            m = m.resize((max(1, int(m.width * s)), max(1, int(m.height * s))), Image.LANCZOS)
            x = int(it["cx"] - m.width / 2)
            y = int(it["base"] - m.height + (1 - min(1.0, entra)) * 500 - max(0.0, entra - 1) * 260)
            ch = Image.new("L", (W, H), 0)
            ImageDraw.Draw(ch).ellipse([x + 30, it["base"] - 34, x + m.width - 30, it["base"] + 34], fill=150)
            fr.paste((0, 0, 0), (0, 0), ch.filter(ImageFilter.GaussianBlur(18)))
            fr.paste(m, (x, y), m)
        yield fr


def quadros_3d(pasta, dur, c1, c2):
    arqs = sorted(glob.glob(os.path.join(pasta, "*.png")))
    n = int(round(dur * FPS))
    for k in range(n):
        fr = fundo_3d(c1, c2, k / FPS)
        m = Image.open(arqs[min(len(arqs) - 1, int(k * len(arqs) / n))]).convert("RGBA")
        m = m.crop(m.getbbox())
        s = min(860 / m.width, 830 / m.height)
        m = m.resize((int(m.width * s), int(m.height * s)), Image.LANCZOS)
        x, y = (W - m.width) // 2, 1130 - m.height
        ch = Image.new("L", (W, H), 0)
        ImageDraw.Draw(ch).ellipse([x + 40, 1095, x + m.width - 40, 1165], fill=150)
        fr.paste((0, 0, 0), (0, 0), ch.filter(ImageFilter.GaussianBlur(18)))
        fr.paste(m, (x, y), m)
        yield fr


# ---------------------------------------------------------------- montagem
def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding="utf8"))
    base = os.path.dirname(os.path.abspath(sys.argv[1]))

    def caminho(p):
        if not p:
            return None
        return p if os.path.isabs(p) or os.path.exists(p) else os.path.join(base, p)

    logo = caminho(spec.get("logo"))
    faixa, masc_moldura = moldura()
    sombra = sombra_fundo()
    preto = Image.new("RGB", (W, H), (0, 0, 0))
    branco = Image.new("RGB", (W, H), WHITE)
    logo_topo = camada_logo(logo)

    out = sys.argv[2]
    mudo = out + ".mudo.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", mudo],
        stdin=subprocess.PIPE)
    n = 0
    for i, c in enumerate(spec["cenas"]):
        dur = float(c["duracao"])
        mod = c.get("modelo", "card")
        cores = c.get("cores") or PALETA[i % len(PALETA)]
        c1, c2 = hexrgb(cores[0]), hexrgb(cores[1])
        if "video" in c:
            gen, real = quadros_video(caminho(c["video"]), c.get("inicio", 0), dur), True
        elif "palco" in c:
            gen, real = quadros_palco(c["palco"], dur, c1, c2, caminho), False
        elif "quadros" in c:
            gen, real = quadros_3d(caminho(c["quadros"]), dur, c1, c2), False
        else:
            gen, real = quadros_foto(caminho(c["foto"]), dur, c.get("foco", 0.5), c.get("enquadre") == "inteiro"), True
        if mod == "heroi":
            ov = modelo_heroi(c, c1, c2)
        elif mod == "numero":
            ov = modelo_numero(c, c1, c2)
        elif mod == "medidas":
            ov = modelo_medidas(c, c1, c2)
        elif mod == "final":
            ov = modelo_final(c, c1, c2, logo)
        else:
            ov = modelo_card(c, c1, c2)
        caixa = ov.getbbox()
        inteiro = c.get("enquadre") == "inteiro"
        fundo_fixo = None
        for k, fr in enumerate(gen):
            t = k / FPS
            fim = mod == "final"
            if inteiro:
                eh_foto = "foto" in c
                fr, fundo = enquadrar(fr, c1, c2, t, fundo_fixo)
                if eh_foto:
                    fundo_fixo = fundo
            # movimento de camera: aproxima devagar, com um "soco" de zoom no corte
            if mod != "medidas" and not inteiro:
                fr = aproximar(fr, 1.0 + 0.07 * t / dur + 0.16 * (1 - suave(t / 0.22)))
            if real and not fim and not inteiro:
                fr = brilho_neon(fr)
                fr = Image.composite(preto, fr, sombra)
            a = suave((t - 0.18) / 0.4)
            if not fim:
                a *= 1 - suave((t - (dur - 0.16)) / 0.16)
            if fim and a > 0:
                escuro = ImageEnhance.Brightness(fr.filter(ImageFilter.GaussianBlur(14))).enhance(0.32)
                fr = Image.blend(fr, escuro, a)
            if mod == "medidas":
                desenhar_medidas(fr, c, c1, c2, t)
            if a > 0 and caixa:
                o = ov if a >= 0.999 else ov.copy()
                if a < 0.999:
                    o.putalpha(ov.getchannel("A").point(lambda v: int(v * a)))
                if mod == "heroi":  # titulo "estoura" na tela
                    s = max(0.05, mola((t - 0.18) / 0.45))
                    rec = o.crop(caixa)
                    rec = rec.resize((max(1, int(rec.width * s)), max(1, int(rec.height * s))), Image.BICUBIC)
                    cx, cy = (caixa[0] + caixa[2]) // 2, (caixa[1] + caixa[3]) // 2
                    fr.paste(rec, (cx - rec.width // 2, cy - rec.height // 2), rec)
                else:
                    des = int((1 - a) * 90)
                    dx = des if c.get("lado") == "direita" else (-des if mod == "numero" else 0)
                    dy = des if mod in ("card", "final") and not dx else 0
                    fr.paste(o, (dx, dy), o)
            if mod == "numero":
                desenhar_numero(fr, c, c1, c2, t, (t - 0.1) / 0.5)
            if mod in ("heroi", "final") or not real:
                confete(fr, n / FPS, 1.0 if fim else 0.85)
            if not fim:
                fr.paste(logo_topo, (0, 0), logo_topo)
            if k < 5 and n > 0:  # flash de corte
                fr = Image.blend(fr, branco, 0.55 * (1 - k / 5))
            desloc = int((n / FPS) * 420) % W
            fr.paste(faixa.crop((desloc, 0, desloc + W, H)), (0, 0), masc_moldura)
            ff.stdin.write(fr.tobytes())
            n += 1
    ff.stdin.close()
    ff.wait()
    seg = n / FPS
    mus = caminho(spec.get("musica"))
    if mus:
        subprocess.check_call(
            ["ffmpeg", "-v", "error", "-y", "-i", mudo, "-stream_loop", "-1", "-i", mus, "-filter_complex",
             f"[1:a]volume=0.85,afade=t=in:d=0.2,afade=t=out:st={seg - 1.2}:d=1.2[a]", "-map", "0:v", "-map", "[a]",
             "-t", str(seg), "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
             "-movflags", "+faststart", out])
    else:
        subprocess.check_call(
            ["ffmpeg", "-v", "error", "-y", "-i", mudo, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-shortest", "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", out])
    os.remove(mudo)
    print(f"OK {out} ({seg:.1f} s)")


if __name__ == "__main__":
    main()
