"""Converte as artes dos kits (PNG de ferramentas/kits/gerar.js) para .webp.

    python -I ferramentas/kits/para_webp.py <pasta-com-os-png> [destino]

Destino padrão: core/static/site/kits/. Qualidade 88: a arte tem texto, e o
.webp com menos que isso borra as letras miúdas dos itens.
"""

import sys
from pathlib import Path

from PIL import Image

KITS = ("kit-boliche-virtual", "kit-strike-kids", "kit-lazer-shot")


def main(origem, destino):
    destino.mkdir(parents=True, exist_ok=True)
    for chave in KITS:
        png = origem / f"{chave}.png"
        webp = destino / f"{chave}.webp"
        with Image.open(png) as imagem:
            imagem = imagem.convert("RGB")
            if imagem.size != (1200, 1200):  # renderizada em 2x: reduz com bordas lisas
                imagem = imagem.resize((1200, 1200), Image.LANCZOS)
            imagem.save(webp, "WEBP", quality=88, method=6)
        print(webp, webp.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parents[2]
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else raiz / "core" / "static" / "site" / "kits"
    main(origem, destino)
