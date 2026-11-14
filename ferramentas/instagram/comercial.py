#!/usr/bin/env python3
"""Gera um comercial vertical (1080x1920) no estilo "apresentacao": cenas das maquinas em tela
cheia, legenda amarela entrando palavra por palavra, logo fixo no canto e logo animado no final.

Uso:
  python3 ferramentas/instagram/comercial.py roteiro.json saida.mp4

Roteiro (modelo em exemplos/institucional.json):
  {
    "logo": "core/static/images/logoofi.png",
    "musica": "core/static/site/arena/jogos/strike-kids/sons/musica.mp3",
    "ritmo": 2.5,                      palavras por segundo da legenda
    "cenas": [
      {"video": "fabrica.mov", "inicio": 0, "fala": "Já pensou em transformar um espaço parado"},
      {"foto": "boliche.jpg", "movimento": "pan", "fala": "Boliche,", "duracao": 0.8},
      {"foto": "playground.jpg", "movimento": "inteiro", "fala": "em um espaço de diversão?",
       "pip": [{"foto": "detalhe.jpg", "x": 250, "y": 520, "largura": 330, "em": 0.6}]},
      {"palco": [{"imagem": "recorte.webp", "altura": 600, "cx": 300, "base": 1100}], "fala": "..."},
      {"quadros": "giro_3d", "fala": "..."}
    ],
    "final": {"duracao": 4.0, "botao": "WhatsApp (11) 96056-3135", "texto": "Link na bio"}
  }

- "fala" e o texto da legenda da cena. Junte com "_" as palavras que devem aparecer juntas
  (ex.: "Lazer_&_Sport", "São_Paulo,"). Sem "duracao", a cena dura o tempo de ler a fala.
- "movimento" da foto: "pan" (enche a tela e desliza de um lado ao outro, mostrando a maquina
  toda), "inteiro" (foto inteira na largura, com fundo desfocado) ou "zoom" (enche a tela).
- "pip": fotos pequenas que entram por cima da cena (x, y = centro; "em" = segundo de entrada).
Sem locucao gerada: so trilha e legenda. Precisa de ffmpeg, Pillow e da fonte Inter.
"""
import json
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

import reel as r

W, H, FPS = r.W, r.H, r.FPS
INK, WHITE = r.INK, r.WHITE
AMARELO = (255, 214, 10)
ITALICO = "/usr/share/fonts/opentype/inter/Inter-ExtraBoldItalic.otf"


def cobrir(im, larg, alt):
    sc = max(larg / im.width, alt / im.height)
    return im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)


def fundo_desfocado(im):
    f = cobrir(im.resize((im.width // 6 + 1, im.height // 6 + 1)), W, H)
    l, t = (f.width - W) // 2, (f.height - H) // 2
    f = f.crop((l, t, l + W, t + H)).filter(ImageFilter.GaussianBlur(26))
    return ImageEnhance.Brightness(f).enhance(0.55)


def quadros_foto(path, dur, movimento):
    im = Image.open(path).convert("RGB")
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.25)).enhance(1.06)
    n = int(round(dur * FPS))
    bg = fundo_desfocado(im)
    if movimento == "zoom":
        base = cobrir(im, W, H)
        l, t = (base.width - W) // 2, (base.height - H) // 2
        base = base.crop((l, t, l + W, t + H))
        for k in range(n):
            yield r.aproximar(base, 1.0 + 0.08 * k / n)
        return
    if movimento == "inteiro":
        for k in range(n):
            z = 1.0 + 0.05 * k / n
            w, h = int(W * z), int(im.height * W / im.width * z)
            fr = bg.copy()
            fr.paste(im.resize((w, h), Image.BILINEAR), ((W - w) // 2, (H - h) // 2))
            yield fr
        return
    # pan: a foto ocupa 1500 px de altura e desliza de lado, mostrando a maquina inteira
    alt = 1500
    larg = int(im.width * alt / im.height)
    grande = im.resize((larg, alt), Image.LANCZOS)
    sobra = max(0, larg - W)
    y = (H - alt) // 2
    borda = Image.new("L", (W, alt), 255)
    d = ImageDraw.Draw(borda)
    for i in range(60):  # esmaece em cima e embaixo para fundir com o fundo desfocado
        v = int(255 * i / 60)
        d.line([(0, i), (W, i)], fill=v)
        d.line([(0, alt - 1 - i), (W, alt - 1 - i)], fill=v)
    for k in range(n):
        a = k / max(1, n - 1)
        x = int(sobra * (0.12 + 0.76 * (0.5 - 0.5 * math.cos(math.pi * a))))
        fr = bg.copy()
        fr.paste(grande.crop((x, 0, x + W, alt)), (0, y), borda)
        yield fr


def selo_logo(caminho_logo, diam=200):
    """Logo num circulo branco com aro amarelo, para o canto da tela."""
    S = diam * 3
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=AMARELO + (255,))
    d.ellipse([S * .045, S * .045, S * .955, S * .955], fill=WHITE + (255,))
    lg = Image.open(caminho_logo).convert("RGBA")
    w = int(S * .80)
    lg = lg.resize((w, int(lg.height * w / lg.width)), Image.LANCZOS)
    im.alpha_composite(lg, ((S - lg.width) // 2, (S - lg.height) // 2))
    im = im.resize((diam, diam), Image.LANCZOS)
    som = Image.new("RGBA", (diam + 60, diam + 60), (0, 0, 0, 0))
    ImageDraw.Draw(som).ellipse([30, 38, diam + 30, diam + 38], fill=(0, 0, 0, 150))
    som = som.filter(ImageFilter.GaussianBlur(12))
    som.alpha_composite(im, (30, 30))
    return som


def palavra_legenda(fr, texto, t, y=1270):
    """Uma palavra (ou grupo) por vez: amarelo, italico, contorno escuro, entrando com 'estouro'."""
    d0 = ImageDraw.Draw(fr)
    f = r.ajustar(d0, [texto], ITALICO, 124, W - 150)
    cont = 12
    w, h, b = r.medir(d0, texto, f, cont)
    ov = Image.new("RGBA", (w + 60, h + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.text((30 - b[0] + 6, 30 - b[1] + 10), texto, font=f, fill=(0, 0, 0, 150), stroke_width=cont, stroke_fill=(0, 0, 0, 150))
    ov = ov.filter(ImageFilter.GaussianBlur(5))
    d = ImageDraw.Draw(ov)
    d.text((30 - b[0], 30 - b[1]), texto, font=f, fill=AMARELO + (255,), stroke_width=cont, stroke_fill=INK + (255,))
    s = max(0.3, r.mola(t / 0.16))
    if abs(s - 1) > 0.01:
        ov = ov.resize((max(1, int(ov.width * s)), max(1, int(ov.height * s))), Image.BICUBIC)
    fr.paste(ov, ((W - ov.width) // 2, y - ov.height // 2), ov)


def cartao(path, largura, giro):
    im = Image.open(path).convert("RGB")
    im = im.resize((largura, int(im.height * largura / im.width)), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=30, fill=255)
    base = Image.new("RGBA", (im.width + 16, im.height + 16), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle([0, 0, base.width - 1, base.height - 1], radius=36, fill=WHITE + (255,))
    base.paste(im, (8, 8), m)
    return base.rotate(giro, expand=True, resample=Image.BICUBIC)


def desenhar_pips(fr, pips, t):
    for i, (pp, card) in enumerate(pips):
        dt = t - pp.get("em", 0.4)
        if dt <= 0:
            continue
        s = max(0.05, r.mola(dt / 0.35))
        c = card if abs(s - 1) < 0.01 else card.resize((max(1, int(card.width * s)), max(1, int(card.height * s))), Image.BICUBIC)
        som = Image.new("L", (W, H), 0)
        ImageDraw.Draw(som).rounded_rectangle([pp["x"] - c.width // 2 + 10, pp["y"] - c.height // 2 + 24,
                                               pp["x"] + c.width // 2 - 10, pp["y"] + c.height // 2 + 24], radius=36, fill=150)
        fr.paste((0, 0, 0), (0, 0), som.filter(ImageFilter.GaussianBlur(16)))
        fr.paste(c, (pp["x"] - c.width // 2, pp["y"] - c.height // 2), c)


def encerramento(fim, logo, n0):
    """Logo animado: aro de lampadas acendendo, raios girando, logo estourando e confete."""
    n = int(fim.get("duracao", 4.0) * FPS)
    rnd = random.Random(3)
    estrelas = [(rnd.random() * W, rnd.random() * H, 1 + rnd.random() * 3, rnd.random() * 6.28) for _ in range(120)]
    lg = Image.open(logo).convert("RGBA")
    lg = lg.resize((600, int(lg.height * 600 / lg.width)), Image.LANCZOS)
    cx, cy, raio, lamp = W // 2, 800, 400, 28
    base = r.degrade((W, H), (20, 8, 60), (4, 4, 16), vertical=True)
    for k in range(n):
        t = k / FPS
        fr = base.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        for (x, y, s, f) in estrelas:
            a = int(120 + 110 * math.sin(t * 3 + f))
            d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255, max(0, a)))
        raios = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(raios)
        forca = r.suave((t - 0.5) / 0.5)
        for i in range(16):
            a0 = 2 * math.pi * i / 16 + t * 0.5
            a1 = a0 + math.pi / 16
            cor = r.LED[i % len(r.LED)] + (int(70 * forca),)
            dr.polygon([(cx, cy), (cx + 1500 * math.cos(a0), cy + 1500 * math.sin(a0)),
                        (cx + 1500 * math.cos(a1), cy + 1500 * math.sin(a1))], fill=cor)
        fr.paste(raios, (0, 0), raios)
        d = ImageDraw.Draw(fr, "RGBA")
        acesas = int(lamp * r.suave(t / 0.8)) + 1
        for i in range(min(lamp, acesas)):
            a = 2 * math.pi * i / lamp - math.pi / 2
            x, y = cx + raio * math.cos(a), cy + raio * math.sin(a)
            pisca = 0.65 + 0.35 * math.sin(t * 9 + i)
            d.ellipse([x - 34, y - 34, x + 34, y + 34], fill=(255, 214, 10, int(70 * pisca)))
            d.ellipse([x - 17, y - 17, x + 17, y + 17], fill=(255, 240, 170, 255))
        if t > 0.45:
            s = max(0.05, r.mola((t - 0.45) / 0.5))
            disco = int(330 * s)
            d.ellipse([cx - disco, cy - disco, cx + disco, cy + disco], fill=WHITE + (255,), outline=AMARELO + (255,), width=12)
            l2 = lg.resize((max(1, int(lg.width * s)), max(1, int(lg.height * s))), Image.BICUBIC)
            fr.paste(l2, (cx - l2.width // 2, cy - l2.height // 2), l2)
            if t - 0.45 < 0.15:
                fr = Image.blend(fr, Image.new("RGB", (W, H), WHITE), 0.6 * (1 - (t - 0.45) / 0.15))
        if t > 1.3:
            a = r.suave((t - 1.3) / 0.4)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            do = ImageDraw.Draw(ov)
            y = 1300 + int((1 - a) * 60)
            bt = fim.get("botao")
            if bt:
                fb = r.font(r.XB, 60)
                w, h, b = r.medir(do, bt, fb)
                ic = r.icone("conversa", 86, cor=INK, tinta=r.GRN)
                bw = w + ic.width + 24
                do.rounded_rectangle([(W - bw) // 2 - 52, y, (W + bw) // 2 + 52, y + 136], radius=68, fill=r.GRN + (255,),
                                     outline=WHITE + (255,), width=5)
                ov.alpha_composite(ic, ((W - bw) // 2, y + 25))
                do.text(((W - bw) // 2 + ic.width + 24 - b[0], y + (136 - h) // 2 - b[1]), bt, font=fb, fill=INK + (255,))
                y += 136 + 34
            tx = fim.get("texto")
            if tx:
                ft = r.font(r.XB, 56)
                w, h, b = r.medir(do, tx, ft)
                do.rounded_rectangle([(W - w) // 2 - 48, y, (W + w) // 2 + 48, y + 112], radius=56, fill=WHITE + (255,))
                do.text(((W - w) // 2 - b[0], y + (112 - h) // 2 - b[1]), tx, font=ft, fill=INK + (255,))
            if a < 1:
                ov.putalpha(ov.getchannel("A").point(lambda v: int(v * a)))
            fr.paste(ov, (0, 0), ov)
        r.confete(fr, (n0 + k) / FPS, min(1.0, t / 0.8))
        yield fr


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
    selo = selo_logo(logo) if logo else None
    ritmo = float(spec.get("ritmo", 2.5))
    c1, c2 = r.hexrgb(spec.get("cores", ["#FFE600", "#FF8A00"])[0]), r.hexrgb(spec.get("cores", ["#FFE600", "#FF8A00"])[1])
    branco = Image.new("RGB", (W, H), WHITE)
    sombra = Image.new("L", (1, H), 0)
    for y in range(H):  # escurece um pouco a faixa da legenda e o topo
        a = int(110 * max(0, 1 - abs(y - 1290) / 420)) if y > 870 else int(70 * max(0, 1 - y / 380))
        sombra.putpixel((0, y), a)
    sombra = sombra.resize((W, H))
    preto = Image.new("RGB", (W, H), (0, 0, 0))

    out = sys.argv[2]
    mudo = out + ".mudo.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", mudo],
        stdin=subprocess.PIPE)
    n = 0
    for c in spec["cenas"]:
        palavras = [p.replace("_", " ") for p in c.get("fala", "").split()]
        dur = float(c.get("duracao") or max(1.0, len(palavras) / ritmo + 0.25))
        if "video" in c:
            gen, real = r.quadros_video(caminho(c["video"]), c.get("inicio", 0), dur), True
        elif "palco" in c:
            gen, real = r.quadros_palco(c["palco"], dur, c1, c2, caminho), False
        elif "quadros" in c:
            gen, real = r.quadros_3d(caminho(c["quadros"]), dur, c1, c2), False
        else:
            gen, real = quadros_foto(caminho(c["foto"]), dur, c.get("movimento", "pan")), False
        pips = [(pp, cartao(caminho(pp["foto"]), pp.get("largura", 320), pp.get("giro", (-5, 5)[i % 2])))
                for i, pp in enumerate(c.get("pip", []))]
        ini, fim = 0.06, dur - 0.10
        passo = (fim - ini) / max(1, len(palavras))
        for k, fr in enumerate(gen):
            t = k / FPS
            if real:
                fr = r.aproximar(fr, 1.0 + 0.05 * t / dur + 0.12 * (1 - r.suave(t / 0.2)))
                fr = r.brilho_neon(fr, 0.25)
            elif "foto" in c:
                fr = r.aproximar(fr, 1.0 + 0.10 * (1 - r.suave(t / 0.2)))
            fr = Image.composite(preto, fr, sombra)
            if pips:
                desenhar_pips(fr, pips, t)
            if palavras and t >= ini:
                i = min(len(palavras) - 1, int((t - ini) / passo))
                palavra_legenda(fr, palavras[i], t - ini - i * passo)
            if selo:
                fr.paste(selo, (W - selo.width - 22, 118), selo)
            if k < 4 and n > 0:
                fr = Image.blend(fr, branco, 0.5 * (1 - k / 4))
            ff.stdin.write(fr.tobytes())
            n += 1
    if spec.get("final") and logo:
        for fr in encerramento(spec["final"], logo, n):
            ff.stdin.write(fr.tobytes())
            n += 1
    ff.stdin.close()
    ff.wait()
    seg = n / FPS
    mus = caminho(spec.get("musica"))
    if mus:
        subprocess.check_call(
            ["ffmpeg", "-v", "error", "-y", "-i", mudo, "-stream_loop", "-1", "-i", mus, "-filter_complex",
             f"[1:a]volume=0.85,afade=t=in:d=0.2,afade=t=out:st={seg - 1.4}:d=1.4[a]", "-map", "0:v", "-map", "[a]",
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
