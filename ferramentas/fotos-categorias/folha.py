"""As folhas de conferência: antes e depois de cada categoria e o zoom na base de cada máquina.

    python folha.py <pasta de saída> [--webp <pasta dos .webp novos>] [--render <pasta dos renders>]

Grava:
  * antes-depois.jpg: cada categoria, a foto de antes (a do git, HEAD) e a nova;
  * novas.jpg: só as novas, em grade (como a home as mostra, em miniatura);
  * bases-<chave>.jpg: o recorte em volta da base de cada máquina, ampliado (a sombra de
    contato, nada de vão embaixo, nada atravessado) -- a posição sai do <chave>.json do gerar.py.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent.parent
SITE = RAIZ / "core" / "static" / "site" / "categorias"


def antiga(chave):
    caminho = f"core/static/site/categorias/{chave}.webp"
    r = subprocess.run(["git", "-C", str(RAIZ), "show", f"HEAD:{caminho}"], capture_output=True)
    if r.returncode or not r.stdout:
        return None
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def rotulo(img, texto):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8 + 7 * len(texto), 18), fill=(0, 0, 0))
    d.text((4, 3), texto, fill=(255, 255, 255))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("--webp", default=str(SITE))
    ap.add_argument("--render", default=str(PASTA / "render"))
    ap.add_argument("chaves", nargs="*")
    args = ap.parse_args()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    webp = Path(args.webp)
    chaves = args.chaves or sorted(p.stem for p in webp.glob("*.webp"))
    cw, ch = 480, 360
    # antes e depois
    folha = Image.new("RGB", (cw * 2 + 30, (ch + 10) * len(chaves)), (18, 18, 28))
    for i, chave in enumerate(chaves):
        y = i * (ch + 10)
        velha = antiga(chave)
        if velha:
            folha.paste(rotulo(velha.resize((cw, ch), Image.LANCZOS), f"{chave} (antes)"), (0, y))
        nova = Image.open(webp / f"{chave}.webp").convert("RGB")
        folha.paste(rotulo(nova.resize((cw, ch), Image.LANCZOS), f"{chave} (nova)"), (cw + 30, y))
    folha.save(saida / "antes-depois.jpg", quality=86)
    # só as novas, em grade de 4
    cols = 4
    linhas = (len(chaves) + cols - 1) // cols
    grade = Image.new("RGB", (cols * (cw + 8), linhas * (ch + 8)), (18, 18, 28))
    for i, chave in enumerate(chaves):
        nova = Image.open(webp / f"{chave}.webp").convert("RGB").resize((cw, ch), Image.LANCZOS)
        grade.paste(rotulo(nova, chave), ((i % cols) * (cw + 8), (i // cols) * (ch + 8)))
    grade.save(saida / "novas.jpg", quality=88)
    # o zoom nas bases
    for chave in chaves:
        info = Path(args.render) / f"{chave}.json"
        if not info.exists():
            continue
        dados = json.loads(info.read_text(encoding="utf-8"))
        img = Image.open(webp / f"{chave}.webp").convert("RGB")
        w, h = img.size
        cortes = []
        for m in dados["bases"]:
            x0, y0, x1, y1 = m["base"]
            cx0, cx1 = max(0, x0 - 0.04), min(1, x1 + 0.04)
            alto = (cx1 - cx0) * w * 0.5
            cy1 = min(h, y1 * h + alto * 0.35)
            cy0 = max(0, cy1 - alto)
            if cx1 <= cx0 or cy1 <= cy0:
                continue
            corte = img.crop((int(cx0 * w), int(cy0), int(cx1 * w), int(cy1)))
            escala = 520 / corte.width
            corte = corte.resize((520, max(1, int(corte.height * escala))), Image.LANCZOS)
            cortes.append(rotulo(corte, m["nome"]))
        if not cortes:
            continue
        alt = sum(c.height + 6 for c in cortes)
        f = Image.new("RGB", (520, alt), (18, 18, 28))
        y = 0
        for c in cortes:
            f.paste(c, (0, y))
            y += c.height + 6
        f.save(saida / f"bases-{chave}.jpg", quality=88)
    print(f"folhas em {saida}")


if __name__ == "__main__":
    main()
