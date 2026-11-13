#!/usr/bin/env python3
"""Gera um Reel vertical (1080x1920) com cards animados a partir de videos e fotos reais.

Uso:
  python3 ferramentas/instagram/reel.py roteiro.json saida.mp4

O roteiro e um JSON (modelo completo em exemplos/strike_kids.json):
  {
    "logo": "core/static/images/logoofi.png",
    "site": "www.lazersport.com.br",
    "musica": "core/static/site/arena/jogos/strike-kids/sons/musica.mp3",
    "cenas": [
      {"video": "entrada.mov", "inicio": 30.0, "duracao": 3.2,
       "icone": "pino", "cores": ["#FFD21A", "#FF7A00"],
       "etiqueta": "FABRICACAO PROPRIA", "titulo": "STRIKE KIDS",
       "texto": ["O boliche infantil da Lazer & Sport"]},
      {"foto": "angulo.jpg", "duracao": 3.8, "final": true,
       "etiqueta": "DIRETO DA FABRICA", "titulo": ["QUER O STRIKE KIDS", "NO SEU ESPACO?"],
       "texto": ["Comente STRIKE", "e peca o seu orcamento"],
       "botao": "WhatsApp (11) 96056-3135"}
    ]
  }

Icones: pino, camera, cinco, led, regua, conversa, estrela (ou qualquer texto
curto, ex.: "2x"). Cores: par de hexadecimais do degrade do card; se faltar,
usa a paleta padrao em rodizio.

Precisa de ffmpeg, Pillow e da fonte Inter instalados.
"""
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
SB = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
INK = (14, 16, 34)
WHITE = (255, 255, 255)
GRN = (37, 211, 102)
# Vermelho e azul da marca + verde e amarelo do LED das maquinas.
LED = [(240, 69, 106), (255, 210, 26), (43, 227, 91), (25, 211, 255), (155, 92, 255)]
PALETA = [("#FFD21A", "#FF7A00"), ("#FF2E93", "#9B5CFF"), ("#2BE35B", "#19D3FF"),
          ("#19D3FF", "#6C8CFF"), ("#FF7A00", "#F0456A")]


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font(p, s):
    return ImageFont.truetype(p, s)


def medir(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
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


def texto_degrade(camada, pos, t, f, c1, c2):
    w, h, b = medir(ImageDraw.Draw(camada), t, f)
    m = Image.new("L", (w + 8, h + 8), 0)
    ImageDraw.Draw(m).text((4 - b[0], 4 - b[1]), t, font=f, fill=255)
    cor = degrade(m.size, c1, c2).convert("RGBA")
    cor.putalpha(m)
    camada.alpha_composite(cor, (pos[0] - 4, pos[1] - 4))
    return h


# ---------------------------------------------------------------- icones
def icone(nome, tam, cor=WHITE, tinta=INK):
    """Icone desenhado em 4x e reduzido, para ficar com borda lisa."""
    S = tam * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = cor + (255,)
    k = tinta + (255,)

    def P(x, y):
        return (x * S, y * S)

    def elipse(x0, y0, x1, y1, fill):
        d.ellipse([P(x0, y0), P(x1, y1)], fill=fill)

    if nome == "pino":
        elipse(.36, .10, .56, .30, c)
        d.polygon([P(.40, .26), P(.52, .26), P(.56, .46), P(.36, .46)], fill=c)
        elipse(.27, .36, .65, .92, c)
        d.rectangle([P(.385, .295), P(.535, .325)], fill=k)
        d.rectangle([P(.375, .355), P(.545, .385)], fill=k)
        elipse(.58, .62, .86, .90, c)
        elipse(.56, .60, .88, .92, None)
        d.ellipse([P(.58, .62), P(.86, .90)], outline=k, width=int(S * .02))
        for x, y in ((.68, .70), (.75, .70), (.72, .77)):
            elipse(x - .02, y - .02, x + .02, y + .02, k)
    elif nome == "camera":
        d.rounded_rectangle([P(.38, .22), P(.62, .36)], radius=S * .04, fill=c)
        d.rounded_rectangle([P(.14, .30), P(.86, .78)], radius=S * .09, fill=c)
        elipse(.35, .39, .65, .69, k)
        elipse(.42, .46, .58, .62, c)
        elipse(.72, .37, .79, .44, k)
    elif nome == "led":
        def brilho(cx, cy, r):
            pts = []
            for i in range(8):
                a = math.pi / 4 * i - math.pi / 2
                rr = r if i % 2 == 0 else r * .30
                pts.append(P(cx + rr * math.cos(a), cy + rr * math.sin(a)))
            d.polygon(pts, fill=c)
        brilho(.44, .54, .34)
        brilho(.76, .26, .16)
        brilho(.78, .78, .10)
    elif nome == "estrela":
        pts = []
        for i in range(10):
            a = math.pi / 5 * i - math.pi / 2
            rr = .40 if i % 2 == 0 else .17
            pts.append(P(.5 + rr * math.cos(a), .52 + rr * math.sin(a)))
        d.polygon(pts, fill=c)
    elif nome == "regua":
        e = int(S * .07)
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
    else:  # texto curto: "5", "2x"...
        t = "5" if nome == "cinco" else str(nome)[:3]
        f = font(XB, int(S * (.72 if len(t) == 1 else .46)))
        w, h, b = medir(d, t, f)
        d.text(((S - w) / 2 - b[0], (S - h) / 2 - b[1]), t, font=f, fill=c)
    return im.resize((tam, tam), Image.LANCZOS)


def selo(nome, diam, c1, c2):
    """Circulo em degrade com anel branco e o icone dentro."""
    S = diam * 4
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse([0, 0, S - 1, S - 1], fill=255)
    base = Image.new("RGBA", (S, S), WHITE + (255,))
    miolo = degrade((S, S), c1, c2, vertical=True).convert("RGBA")
    mm = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mm).ellipse([S * .06, S * .06, S * .94, S * .94], fill=255)
    base.paste(miolo, (0, 0), mm)
    base.putalpha(m)
    base = base.resize((diam, diam), Image.LANCZOS)
    ic = icone(nome, int(diam * .66), cor=INK)
    base.alpha_composite(ic, ((diam - ic.width) // 2, (diam - ic.height) // 2))
    return base


# ---------------------------------------------------------------- camadas
def moldura():
    """Moldura da tela com as cores do LED; devolve (faixa colorida, mascara)."""
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([16, 16, W - 17, H - 17], radius=64, fill=255)
    d.rounded_rectangle([28, 28, W - 29, H - 29], radius=52, fill=0)
    faixa = Image.new("RGB", (2 * W, 1))
    n = len(LED)
    for x in range(2 * W):
        p = (x % W) / W * n
        a, b = LED[int(p) % n], LED[(int(p) + 1) % n]
        k = p - int(p)
        faixa.putpixel((x, 0), tuple(int(a[j] + (b[j] - a[j]) * k) for j in range(3)))
    return faixa.resize((2 * W, H)), m.filter(ImageFilter.GaussianBlur(0.8))


def sombra_inferior():
    s = Image.new("L", (1, H), 0)
    for y in range(H):
        a = 0
        if y > 1150:
            a = int(120 * min(1, (y - 1150) / 450))
        if y < 460:
            a = max(a, int(120 * (1 - y / 460)))
        s.putpixel((0, y), a)
    return s.resize((W, H))


def camada_logo(caminho_logo, altura, y):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not caminho_logo:
        return ov
    lg = Image.open(caminho_logo).convert("RGBA")
    lg = lg.resize((int(lg.width * altura / lg.height), altura), Image.LANCZOS)
    x = (W - lg.width) // 2
    som = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    som.paste((0, 0, 0, 150), (x, y + 10), lg.getchannel("A"))
    ov.alpha_composite(som.filter(ImageFilter.GaussianBlur(14)))
    ov.alpha_composite(lg, (x, y))
    return ov


def card(c, c1, c2):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    x0, x1, pad, diam = 54, W - 54, 48, 168
    larg = x1 - x0 - 2 * pad
    tit = lista(c["titulo"])
    sub = lista(c.get("texto", []))
    ft = ajustar(d, tit, XB, c.get("tamanho", 112), larg)
    fs = ajustar(d, sub, SB, 52, larg) if sub else None
    fk = font(XB, 36)
    alt_t = sum(medir(d, l, ft)[1] for l in tit) + 16 * (len(tit) - 1)
    alt_s = sum(medir(d, l, fs)[1] for l in sub) + 14 * (len(sub) - 1) if sub else 0
    total = diam // 2 + 34 + alt_t + (26 + alt_s if sub else 0) + pad + 22
    y1 = 1600
    y0 = y1 - total
    # borda em degrade + painel escuro
    borda = degrade((x1 - x0, y1 - y0), c1, c2).convert("RGBA")
    mb = Image.new("L", borda.size, 0)
    ImageDraw.Draw(mb).rounded_rectangle([0, 0, borda.width - 1, borda.height - 1], radius=48, fill=255)
    borda.putalpha(mb)
    ov.alpha_composite(borda, (x0, y0))
    miolo = degrade((x1 - x0 - 12, y1 - y0 - 12), (18, 14, 58), (9, 10, 30), vertical=True).convert("RGBA")
    mm = Image.new("L", miolo.size, 0)
    ImageDraw.Draw(mm).rounded_rectangle([0, 0, miolo.width - 1, miolo.height - 1], radius=42, fill=245)
    miolo.putalpha(mm)
    ov.alpha_composite(miolo, (x0 + 6, y0 + 6))
    # pontos de LED no canto
    for i, cor in enumerate(LED[:4]):
        cx = x1 - pad - 14 - i * 40
        d.ellipse([cx - 11, y0 + 36, cx + 11, y0 + 58], fill=cor + (255,))
    # selo com icone, metade para fora do card
    ov.alpha_composite(selo(c.get("icone", "estrela"), diam, c1, c2), (x0 + pad - 8, y0 - diam // 2))
    # etiqueta
    k = c.get("etiqueta", "")
    if k:
        kw, _, kb = medir(d, k, fk)
        kx = x0 + pad + diam + 12
        d.rounded_rectangle([kx, y0 + 22, kx + kw + 44, y0 + 82], radius=30, fill=c1 + (255,))
        d.text((kx + 22 - kb[0], y0 + 34 - kb[1] + 2), k, font=fk, fill=INK + (255,))
    y = y0 + diam // 2 + 34
    for l in tit:
        y += texto_degrade(ov, (x0 + pad, y), l, ft, c1, c2) + 16
    y += 10
    for l in sub:
        w, h, b = medir(d, l, fs)
        d.text((x0 + pad - b[0], y - b[1]), l, font=fs, fill=WHITE + (255,))
        y += h + 14
    # linha de degrade no rodape do card
    linha = degrade((larg, 8), c1, c2).convert("RGBA")
    ov.alpha_composite(linha, (x0 + pad, y1 - pad + 6))
    return ov


def card_final(c, c1, c2, caminho_logo, site):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    y = 330
    if caminho_logo:
        lg = Image.open(caminho_logo).convert("RGBA")
        lg = lg.resize((520, int(lg.height * 520 / lg.width)), Image.LANCZOS)
        ov.alpha_composite(lg, ((W - 520) // 2, y))
        y += lg.height + 60
    fk = font(XB, 38)
    k = c.get("etiqueta", "")
    if k:
        kw, _, kb = medir(d, k, fk)
        d.rounded_rectangle([(W - kw) // 2 - 26, y, (W + kw) // 2 + 26, y + 66], radius=33, fill=c1 + (255,))
        d.text(((W - kw) // 2 - kb[0], y + 15 - kb[1] + 2), k, font=fk, fill=INK + (255,))
        y += 66 + 40
    tit = lista(c.get("titulo", []))
    ft = ajustar(d, tit, XB, c.get("tamanho", 96), W - 160)
    for l in tit:
        w, h, _ = medir(d, l, ft)
        y += texto_degrade(ov, ((W - w) // 2, y), l, ft, c1, c2) + 20
    y += 24
    fs = font(SB, 52)
    for l in lista(c.get("texto", [])):
        w, h, b = medir(d, l, fs)
        d.text(((W - w) // 2 - b[0], y - b[1]), l, font=fs, fill=WHITE + (255,))
        y += h + 16
    y += 44
    fb = font(XB, 58)
    t = c.get("botao")
    if t:
        w, h, b = medir(d, t, fb)
        ic = icone("conversa", 84, cor=INK, tinta=GRN)
        bw = w + ic.width + 24
        d.rounded_rectangle([(W - bw) // 2 - 50, y, (W + bw) // 2 + 50, y + 128], radius=64, fill=GRN + (255,))
        ov.alpha_composite(ic, ((W - bw) // 2, y + 22))
        d.text(((W - bw) // 2 + ic.width + 24 - b[0], y + (128 - h) // 2 - b[1]), t, font=fb, fill=INK + (255,))
        y += 128 + 30
    if site:
        fw = font(XB, 50)
        w, h, b = medir(d, site, fw)
        d.rounded_rectangle([(W - w) // 2 - 46, y, (W + w) // 2 + 46, y + 108], radius=54,
                            fill=(255, 255, 255, 255), outline=LED[0] + (255,), width=6)
        d.text(((W - w) // 2 - b[0], y + (108 - h) // 2 - b[1]), site, font=fw, fill=INK + (255,))
    return ov


# ---------------------------------------------------------------- quadros
def suave(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def quadros_video(mov, inicio, dur):
    p = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", str(inicio), "-t", str(dur), "-i", mov, "-vf",
         "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,"
         "unsharp=5:5:0.6,eq=contrast=1.06:saturation=1.18",
         "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    for _ in range(int(dur * FPS)):
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        yield Image.frombytes("RGB", (W, H), b)
    p.stdout.close()
    p.wait()


def quadros_foto(path, dur, z1):
    im = ImageEnhance.Color(Image.open(path).convert("RGB")).enhance(1.12)
    sc = max(W / im.width, H / im.height)
    n = int(dur * FPS)
    for k in range(n):
        z = sc * (1.0 + (z1 - 1.0) * k / n)
        w, h = int(im.width * z), int(im.height * z)
        r = im.resize((w, h), Image.BILINEAR)
        l, t = (w - W) // 2, (h - H) // 2
        yield r.crop((l, t, l + W, t + H))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding="utf8"))
    base = os.path.dirname(os.path.abspath(sys.argv[1]))

    def caminho(p):
        if not p:
            return None
        return p if os.path.isabs(p) or os.path.exists(p) else os.path.join(base, p)

    logo, site = caminho(spec.get("logo")), spec.get("site", "")
    faixa, masc_moldura = moldura()
    sombra = sombra_inferior()
    preto = Image.new("RGB", (W, H), (0, 0, 0))
    logo_topo = camada_logo(logo, 170, 190)

    out = sys.argv[2]
    mudo = out + ".mudo.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", mudo],
        stdin=subprocess.PIPE)
    n = 0
    for i, c in enumerate(spec["cenas"]):
        dur, fim = float(c["duracao"]), bool(c.get("final"))
        cores = c.get("cores") or PALETA[i % len(PALETA)]
        c1, c2 = hexrgb(cores[0]), hexrgb(cores[1])
        if "video" in c:
            gen = quadros_video(caminho(c["video"]), c.get("inicio", 0), dur)
        else:
            gen = quadros_foto(caminho(c["foto"]), dur, 1.06 if fim else 1.10)
        ov = card_final(c, c1, c2, logo, site) if fim else card(c, c1, c2)
        for k, fr in enumerate(gen):
            t = k / FPS
            a = suave((t - 0.2) / 0.45)
            if not fim:
                a *= 1 - suave((t - (dur - 0.2)) / 0.2)
                fr = Image.composite(preto, fr, sombra)
            elif a > 0:
                escuro = ImageEnhance.Brightness(fr.filter(ImageFilter.GaussianBlur(12))).enhance(0.30)
                fr = Image.blend(fr, escuro, a)
            if a > 0:
                o = ov.copy()
                o.putalpha(ov.getchannel("A").point(lambda v: int(v * a)))
                fr.paste(o, (0, int((1 - a) * 70)), o)
            if not fim:
                fr.paste(logo_topo, (0, 0), logo_topo)
            desloc = int((n / FPS) * 360) % W  # as cores correm pela moldura
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
             f"[1:a]volume=0.8,afade=t=in:d=0.3,afade=t=out:st={seg - 1.2}:d=1.2[a]", "-map", "0:v", "-map", "[a]",
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
