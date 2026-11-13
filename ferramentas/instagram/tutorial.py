#!/usr/bin/env python3
"""Gera um Reel de passo a passo (tutorial legendado) com a tela do site dentro de um celular.

Uso:
  python3 ferramentas/instagram/tutorial.py roteiro.json saida.mp4

As telas vem de uma gravacao quadro a quadro (pastas de JPG + meta.json com a
duracao de cada foto e a posicao dos toques). O roteiro escolhe a abertura
("gancho"), os passos com as legendas e o encerramento:

  {
    "gravacao": "grav",                      pasta com meta.json e um trecho por subpasta
    "logo": "core/static/images/logoofi.png",
    "musica": "core/static/site/arena/jogos/strike-kids/sons/musica.mp3",
    "cores": ["#FF2D2D", "#FFD21A"],        degrade dos destaques
    "led": ["#FF2D2D", "#FFD21A", "#FFFFFF", "#FF7A00"],
    "velocidade": 1.25,                      acelera a gravacao
    "numeros": false,                        numero gigante no inicio de cada passo
    "gancho": {"tipo": "preco" | "pergunta" | "vitrine", ...},
    "passos": [{"trecho": "1_vitrine", "passo": 1,
                "legenda": ["Abra o site pelo link da bio", "e toque na oferta *Black Friday*"]}],
    "final": {"arte": "a10.jpg", "etiqueta": "...", "titulo": [...], "texto": [...], "botao": "..."}
  }

Palavras entre *asteriscos* saem destacadas na legenda. Sem locucao: so trilha
e legenda. Precisa de ffmpeg, Pillow e da fonte Inter instalados.
"""
import glob
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

import reel as r

W, H, FPS = r.W, r.H, r.FPS
INK, WHITE = r.INK, r.WHITE
TELA = (412, 860)                 # tamanho da tela gravada, em px de CSS
CEL_W, CEL_H = 620, 1294          # a tela dentro do video
CEL_X, CEL_Y = (W - CEL_W) // 2, 232
B = 18                            # borda do aparelho


def fundo(c1, c2, arte=None):
    """Fundo escuro com dois clarões nas cores do tema (ou a arte desfocada)."""
    if arte is not None:
        sc = max(W / arte.width, H / arte.height)
        f = arte.resize((int(arte.width * sc) + 1, int(arte.height * sc) + 1), Image.BILINEAR)
        l, t = (f.width - W) // 2, (f.height - H) // 2
        f = f.crop((l, t, l + W, t + H)).filter(ImageFilter.GaussianBlur(30))
        return ImageEnhance.Brightness(f).enhance(0.30)
    base = r.degrade((W, H), (6, 6, 12), (16, 8, 14), vertical=True)
    luz = Image.new("RGB", (W // 8, H // 8), (0, 0, 0))
    d = ImageDraw.Draw(luz)
    d.ellipse([-40, -30, 90, 110], fill=tuple(int(v * 0.55) for v in c1))
    d.ellipse([60, 150, 190, 290], fill=tuple(int(v * 0.40) for v in c2))
    luz = luz.filter(ImageFilter.GaussianBlur(26)).resize((W, H), Image.BILINEAR)
    from PIL import ImageChops
    return ImageChops.screen(base, luz)


def aparelho():
    """Moldura do celular (RGBA) e mascara da tela."""
    w, h = CEL_W + 2 * B, CEL_H + 2 * B
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=78, fill=(8, 8, 12, 255), outline=(90, 92, 110, 255), width=4)
    m = Image.new("L", (CEL_W, CEL_H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, CEL_W - 1, CEL_H - 1], radius=64, fill=255)
    return im, m


def linha_tempo(meta, vel):
    """Para cada quadro do video: indice da foto gravada. Tambem devolve os toques ja no novo tempo."""
    fotos = []
    for i, d in enumerate(meta["dur"]):
        fotos += [i] * d
    n = max(1, int(len(fotos) / vel))
    idx = [fotos[min(len(fotos) - 1, int(j * vel))] for j in range(n)]
    toques = [dict(t=int(tq["t"] / vel), x=tq["x"], y=tq["y"]) for tq in meta["toques"]]
    return idx, toques


def desenhar_toque(fr, toques, j, c1):
    d = ImageDraw.Draw(fr, "RGBA")
    sx, sy = CEL_W / TELA[0], CEL_H / TELA[1]
    for k, tq in enumerate(toques):
        x, y = CEL_X + tq["x"] * sx, CEL_Y + tq["y"] * sy
        dt = j - tq["t"]
        if -14 <= dt < 0:        # o "dedo" chega ate o alvo
            a = r.suave((dt + 14) / 14)
            x0, y0 = (CEL_X + CEL_W * 0.78, CEL_Y + CEL_H * 0.93)
            if k > 0:
                x0, y0 = CEL_X + toques[k - 1]["x"] * sx, CEL_Y + toques[k - 1]["y"] * sy
            px, py = x0 + (x - x0) * a, y0 + (y - y0) * a
            d.ellipse([px - 30, py - 30, px + 30, py + 30], fill=(255, 255, 255, 150), outline=INK + (255,), width=4)
        elif 0 <= dt < 16:       # toque: o ponto afunda e solta uma onda
            a = dt / 16
            rr = 30 + 70 * r.suave(a)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=c1 + (int(255 * (1 - a)),), width=9)
            p = 22 if dt < 5 else 30
            d.ellipse([x - p, y - p, x + p, y + p], fill=(255, 255, 255, 215), outline=INK + (255,), width=4)


def legenda(fr, linhas, t, c1, c2, passo, total):
    """Legenda em painel, com as palavras entrando uma a uma e *destaques* coloridos."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    x0, y0, x1, y1 = 60, 1410, W - 60, 1602
    r.painel(ov, (x0, y0, x1, y1), c1, c2, raio=44)
    if total:
        n, larg, esp = total, (x1 - x0 - 96 - 10 * (total - 1)) / total, 10
        for i in range(n):
            xa = x0 + 48 + i * (larg + esp)
            cor = c1 if i < passo else (70, 72, 96)
            d.rounded_rectangle([xa, y0 + 26, xa + larg, y0 + 36], radius=5, fill=cor + (255,))
    tudo = [p for l in linhas for p in l.replace("*", "").split()]
    f = r.ajustar(d, [l.replace("*", "") for l in linhas], r.XB, 58, x1 - x0 - 110)
    esp_palavra = f.size * 0.27
    alt = f.size * 1.22
    y = y0 + 40 + ((y1 - y0 - 40) - alt * len(linhas)) / 2 - f.size * 0.16
    k = 0
    for l in linhas:
        palavras, forte, itens = l.split(), False, []
        for p in palavras:
            ini, fim = p.startswith("*"), p.rstrip(".,:;!?").endswith("*")
            forte = forte or ini
            itens.append((p.replace("*", ""), forte))
            if fim:
                forte = False
        larg = sum(r.medir(d, p, f)[0] for p, _ in itens) + esp_palavra * (len(itens) - 1)
        x = (W - larg) / 2
        for p, fo in itens:
            a = r.suave((t - 0.12 - 0.075 * k) / 0.16)
            if a > 0:
                w, h, b = r.medir(d, p, f)
                dy = (1 - a) * 22
                cor = (c2 if fo else WHITE) + (int(255 * a),)
                d.text((x - b[0], y + dy), p, font=f, fill=cor)
            x += r.medir(d, p, f)[0] + esp_palavra
            k += 1
        y += alt
    fr.paste(ov, (0, 0), ov)


def chip_passo(fr, passo, total, c1):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    t = f"PASSO {passo} DE {total}"
    w = r.medir(ImageDraw.Draw(ov), t, r.font(r.XB, 40))[0] + 56
    r.etiqueta(ov, ((W - w) // 2, 150), t, c1, tam=40)
    fr.paste(ov, (0, 0), ov)


def titulo_central(fr, linhas, y, tam, c1, c2, escala=1.0, contorno=12, alpha=1.0):
    """Bloco de linhas grandes centralizadas, com degrade e contorno; escala para o 'estouro'."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = r.ajustar(d, [l for l, _ in linhas], r.XB, tam, W - 130)
    yy = y
    for l, forte in linhas:
        w = r.medir(d, l, f, contorno)[0]
        a, b_ = (c1, c2) if forte else (WHITE, (225, 228, 240))
        yy += r.texto_degrade(ov, ((W - w) // 2 + contorno, yy), l, f, a, b_, contorno=contorno) + int(f.size * 0.22)
    cx = ov.getbbox()
    if not cx:
        return
    rec = ov.crop(cx)
    if escala != 1.0:
        rec = rec.resize((max(1, int(rec.width * escala)), max(1, int(rec.height * escala))), Image.BICUBIC)
    if alpha < 1:
        rec.putalpha(rec.getchannel("A").point(lambda v: int(v * alpha)))
    fr.paste(rec, ((cx[0] + cx[2]) // 2 - rec.width // 2, (cx[1] + cx[3]) // 2 - rec.height // 2), rec)


def selo_desconto(fr, texto, cx, cy, raio, c1, c2, giro, escala=1.0):
    s = int(raio * 2 + 40)
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon(r.pontas(s / 2, s / 2, raio + 16, raio * .82, 16, giro), fill=WHITE + (255,))
    d.polygon(r.pontas(s / 2, s / 2, raio, raio * .78, 16, giro), fill=c2 + (255,))
    f = r.ajustar(d, [texto], r.XB, int(raio * .72), raio * 1.35)
    w, h, b = r.medir(d, texto, f)
    d.text((s / 2 - w / 2 - b[0], s / 2 - h / 2 - b[1]), texto, font=f, fill=INK + (255,))
    if escala != 1.0:
        im = im.resize((max(1, int(s * escala)), max(1, int(s * escala))), Image.BICUBIC)
    fr.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def cartao_arte(arte, larg, giro):
    a = arte.resize((larg, int(arte.height * larg / arte.width)), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", a.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, a.width - 1, a.height - 1], radius=44, fill=255)
    base = Image.new("RGBA", (a.width + 20, a.height + 20), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle([0, 0, base.width - 1, base.height - 1], radius=52, fill=WHITE + (255,))
    base.paste(a, (10, 10), m)
    return base.rotate(giro, expand=True, resample=Image.BICUBIC)


# ---------------------------------------------------------------- ganchos (abertura)
def gancho_preco(g, c1, c2, caminho):
    """Oferta na cara: arte + BLACK FRIDAY + de/por."""
    arte = Image.open(caminho(g["arte"])).convert("RGB")
    bg = fundo(c1, c2, arte)
    n = int(g.get("duracao", 3.4) * FPS)
    for k in range(n):
        t = k / FPS
        fr = bg.copy()
        s = max(0.05, r.mola(t / 0.45))
        cart = cartao_arte(arte, int(700 * s), -4)
        fr.paste(cart, ((W - cart.width) // 2, 760 - cart.height // 2), cart)
        if t > 0.35:
            titulo_central(fr, [(g.get("titulo", "BLACK FRIDAY"), True)], 150, 150, c1, c2, escala=max(0.05, r.mola((t - 0.35) / 0.4)))
        if t > 0.9 and g.get("selo"):
            selo_desconto(fr, g["selo"], 880, 420, 130, c1, c2, t * 1.2, escala=max(0.05, r.mola((t - 0.9) / 0.4)))
        if t > 1.2:
            a = r.suave((t - 1.2) / 0.3)
            d = ImageDraw.Draw(fr, "RGBA")
            f = r.font(r.XB, 64)
            w, h, b = r.medir(d, g["de"], f)
            x, y = (W - w) // 2, 1250
            d.rounded_rectangle([x - 36, y - 20, x + w + 36, y + h + 24], radius=40, fill=INK + (int(235 * a),))
            d.text((x - b[0], y - b[1]), g["de"], font=f, fill=(190, 194, 210, int(255 * a)))
            d.line([(x - 10, y + h / 2 + 2), (x + w + 10, y + h / 2 + 2)], fill=c1 + (int(255 * a),), width=8)
        if t > 1.55:
            titulo_central(fr, [(g["por"], True)], 1370, 190, c2, c1, escala=max(0.05, r.mola((t - 1.55) / 0.4)))
        if t > 2.2 and g.get("chamada"):
            a = r.suave((t - 2.2) / 0.3)
            d = ImageDraw.Draw(fr, "RGBA")
            f = r.font(r.SB, 54)
            w, h, b = r.medir(d, g["chamada"], f)
            d.rounded_rectangle([(W - w) // 2 - 44, 1610, (W + w) // 2 + 44, 1610 + h + 52], radius=50, fill=WHITE + (int(255 * a),))
            d.text(((W - w) // 2 - b[0], 1636 - b[1]), g["chamada"], font=f, fill=INK + (int(255 * a),))
        r.confete(fr, t, 0.9)
        if k < 4:
            fr = Image.blend(fr, Image.new("RGB", (W, H), WHITE), 0.6 * (1 - k / 4))
        yield fr


def gancho_pergunta(g, c1, c2, caminho):
    """Pergunta em palavras gigantes, uma linha por batida, e a resposta estourando."""
    bg = fundo(c1, c2)
    linhas = g["pergunta"]
    passo = g.get("batida", 0.3)
    t_resp = 0.25 + passo * len(linhas) + 0.55
    n = int(g.get("duracao", t_resp + 1.3) * FPS)
    d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = r.ajustar(d0, linhas, r.XB, 150, W - 140)
    alt = int(f.size * 1.16)
    y0 = (H - alt * len(linhas)) // 2 - 60
    for k in range(n):
        t = k / FPS
        fr = bg.copy()
        if t < t_resp:
            for i, l in enumerate(linhas):
                ti = 0.25 + passo * i
                if t >= ti:
                    ultima = i == len(linhas) - 1
                    titulo_central(fr, [(l, ultima)], y0 + alt * i, f.size, c1, c2,
                                   escala=max(0.05, r.mola((t - ti) / 0.3)), contorno=10)
        else:
            tr = t - t_resp
            titulo_central(fr, [(g["resposta"], True)], 620, 420, c2, c1, escala=max(0.05, r.mola(tr / 0.4)), contorno=16)
            if tr > 0.3:
                titulo_central(fr, [(g["complemento"], False)], 1120, 120, c1, c2,
                               escala=max(0.05, r.mola((tr - 0.3) / 0.35)), contorno=10)
            if abs(tr) < 0.14:
                fr = Image.blend(fr, Image.new("RGB", (W, H), WHITE), 0.7 * (1 - tr / 0.14))
        r.confete(fr, t, 0.7)
        yield fr


def gancho_vitrine(g, c1, c2, caminho):
    """Varias ofertas em cortes rapidos, com selo de desconto, e a chamada para o passo a passo."""
    itens = [(Image.open(caminho(i["arte"])).convert("RGB"), i.get("selo")) for i in g["ofertas"]]
    corte = int(g.get("corte", 0.46) * FPS)
    fecho = int(g.get("fecho", 1.1) * FPS)
    for i, (arte, selo) in enumerate(itens):
        bg = fundo(c1, c2, arte)
        for k in range(corte):
            t = k / FPS
            fr = bg.copy()
            s = 0.92 + 0.10 * r.mola(t / 0.3)
            cart = cartao_arte(arte, int(min(820, 1150 * arte.width / arte.height) * s), (-3, 3)[i % 2])
            fr.paste(cart, ((W - cart.width) // 2, 900 - cart.height // 2), cart)
            titulo_central(fr, [(g.get("titulo", "BLACK FRIDAY"), True)], 120, 130, c1, c2)
            if selo:
                selo_desconto(fr, selo, 890, 430, 120, c1, c2, t * 2, escala=max(0.05, r.mola(t / 0.25)))
            d = ImageDraw.Draw(fr, "RGBA")
            f = r.font(r.XB, 62)
            w, h, b = r.medir(d, g["faixa"], f)
            d.rounded_rectangle([(W - w) // 2 - 50, 1560, (W + w) // 2 + 50, 1560 + h + 56], radius=56, fill=c2 + (255,),
                                outline=WHITE + (255,), width=5)
            d.text(((W - w) // 2 - b[0], 1588 - b[1]), g["faixa"], font=f, fill=INK + (255,))
            if k < 4:
                fr = Image.blend(fr, Image.new("RGB", (W, H), WHITE), 0.6 * (1 - k / 4))
            yield fr
    bg = fundo(c1, c2)
    for k in range(fecho):
        t = k / FPS
        fr = bg.copy()
        titulo_central(fr, [(l, i == len(g["chamada"]) - 1) for i, l in enumerate(g["chamada"])], 640, 150, c1, c2,
                       escala=max(0.05, r.mola(t / 0.35)))
        r.confete(fr, t, 0.8)
        if k < 4:
            fr = Image.blend(fr, Image.new("RGB", (W, H), WHITE), 0.6 * (1 - k / 4))
        yield fr


GANCHOS = {"preco": gancho_preco, "pergunta": gancho_pergunta, "vitrine": gancho_vitrine}


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

    c1, c2 = r.hexrgb(spec["cores"][0]), r.hexrgb(spec["cores"][1])
    if spec.get("led"):
        r.LED = [r.hexrgb(h) for h in spec["led"]]
    faixa, masc_moldura = r.moldura()
    logo = caminho(spec.get("logo"))
    logo_im = None
    if logo:
        lg = Image.open(logo).convert("RGBA")
        logo_im = lg.resize((int(lg.width * 96 / lg.height), 96), Image.LANCZOS)
    grav = caminho(spec["gravacao"])
    meta = json.load(open(os.path.join(grav, "meta.json"), encoding="utf8"))
    vel = float(spec.get("velocidade", 1.25))
    bezel, masc_tela = aparelho()
    bg = fundo(c1, c2)
    branco = Image.new("RGB", (W, H), WHITE)
    total = max(p["passo"] for p in spec["passos"])

    out = sys.argv[2]
    mudo = out + ".mudo.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", mudo],
        stdin=subprocess.PIPE)
    n = 0

    def emitir(fr):
        nonlocal n
        desloc = int((n / FPS) * 420) % W
        fr.paste(faixa.crop((desloc, 0, desloc + W, H)), (0, 0), masc_moldura)
        ff.stdin.write(fr.tobytes())
        n += 1

    g = spec.get("gancho")
    if g:
        for fr in GANCHOS[g["tipo"]](g, c1, c2, caminho):
            emitir(fr)

    primeiro = True
    for ps in spec["passos"]:
        idx, toques = linha_tempo(meta[ps["trecho"]], vel)
        fotos = sorted(glob.glob(os.path.join(grav, ps["trecho"], "*.jpg")))
        cache = {}
        for j, i in enumerate(idx):
            t = j / FPS
            fr = bg.copy()
            if i not in cache:
                cache = {i: Image.open(fotos[i]).convert("RGB").resize((CEL_W, CEL_H), Image.LANCZOS)}
            # o celular sobe na primeira cena e da um leve "pulo" a cada passo
            sobe = int((1 - r.suave(t / 0.45)) * 900) if primeiro else int(26 * (1 - r.suave(t / 0.25)))
            fr.paste(bezel, (CEL_X - B, CEL_Y - B + sobe), bezel)
            fr.paste(cache[i], (CEL_X, CEL_Y + sobe), masc_tela)
            if sobe < 6:
                desenhar_toque(fr, toques, j, c2)
            if logo_im:
                fr.paste(logo_im, (52, 128), logo_im)
            chip_passo(fr, ps["passo"], total, c2)
            legenda(fr, ps["legenda"], t, c1, c2, ps["passo"], total)
            if spec.get("numeros") and t < 0.6 and not ps.get("sem_numero"):
                a = 1 - r.suave((t - 0.3) / 0.3)
                titulo_central(fr, [(str(ps["passo"]), True)], 520, 620, c2, c1, escala=max(0.05, r.mola(t / 0.3)),
                               contorno=20, alpha=a)
            if j < 4 and not primeiro:
                fr = Image.blend(fr, branco, 0.45 * (1 - j / 4))
            emitir(fr)
        primeiro = False

    fim = spec.get("final")
    if fim:
        arte = Image.open(caminho(fim["arte"])).convert("RGB") if fim.get("arte") else None
        bgf = fundo(c1, c2, arte)
        ov = r.modelo_final(fim, c1, c2, logo)
        for k in range(int(fim.get("duracao", 3.4) * FPS)):
            t = k / FPS
            fr = bgf.copy()
            a = r.suave(t / 0.4)
            o = ov if a >= 0.999 else ov.copy()
            if a < 0.999:
                o.putalpha(ov.getchannel("A").point(lambda v: int(v * a)))
            fr.paste(o, (0, int((1 - a) * 80)), o)
            r.confete(fr, n / FPS, 1.0)
            if k < 5:
                fr = Image.blend(fr, branco, 0.55 * (1 - k / 5))
            emitir(fr)

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
