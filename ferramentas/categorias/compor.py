"""As fotos das categorias: o fundo claro e o corte 4:3 do card.

Lê os renders de `render/<chave>.png` (o gerar.cjs: o objeto e a sombra,
com o fundo transparente) e grava `core/static/site/categorias/<chave>.webp`,
1200 × 900, que é o que o cadastro sobe para a categoria (ver
core/categorias_capas.py e `python manage.py atualizar_capas_categorias`).

O CORTE. O card da home (.categoria-media, ls-home.css) é uma caixa de
~237 × 176 px com `object-fit: contain`: a foto 4:3 enche a caixa sem
faixa vazia. O objeto fica no meio, com folga dos lados e embaixo e uma
folga maior em cima, onde o card põe a etiqueta "Categoria" (no canto de
cima à esquerda) -- nada importante encosta na borda.

O FUNDO. O mesmo claro do card (branco no meio, azul-acinzentado bem leve
nas bordas), com um brilho bem fraco da cor da categoria atrás do objeto:
as fotos ficam da mesma família, e cada uma com a sua cor.

    python ferramentas/categorias/compor.py            (todas as que têm render)
    python ferramentas/categorias/compor.py kids       (só esta)
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PASTA = Path(__file__).resolve().parent
RENDERS = PASTA / "render"
DESTINO = PASTA.parent.parent / "core" / "static" / "site" / "categorias"

LARGURA, ALTURA = 1200, 900
#: As folgas, em fração da foto final: (esquerda, cima, direita, baixo).
FOLGAS = (0.065, 0.13, 0.065, 0.075)

#: A cor de cada categoria (o brilho atrás do objeto).
CORES = {
    "brinquedao": "#22c55e",
    "area-ninja": "#f97316",
    "area-baby": "#ec4899",
    "trampolins": "#facc15",
    "espaco-esportivo-kids": "#2563eb",
    "espaco-kids-play": "#8b5cf6",
    "boliche-virtual": "#7c3aed",
    "eletronicos": "#0878f9",
    "fliperama": "#db2777",
    "simuladores": "#ef4444",
    "mecanicos": "#f472b6",
    "jogos-de-mesa": "#16a34a",
    "competitivos": "#f59e0b",
    "famosos": "#fbbf24",
    "esportivos": "#ea580c",
    "kids": "#06b6d4",
}


def _hex(cor):
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


def fundo(cor, centro):
    """O fundo claro do card, com o brilho da cor da categoria em `centro` (x, y)."""
    base = Image.new("RGB", (LARGURA, ALTURA), "#e8eff8")
    # o claro do meio: um círculo branco bem esfumado, um pouco acima do meio
    luz = Image.new("L", (LARGURA, ALTURA), 0)
    ImageDraw.Draw(luz).ellipse((-150, -260, LARGURA + 150, ALTURA + 40), fill=255)
    luz = luz.filter(ImageFilter.GaussianBlur(170))
    base = Image.composite(Image.new("RGB", base.size, "#ffffff"), base, luz)
    # o brilho da categoria atrás do objeto
    brilho = Image.new("L", (LARGURA, ALTURA), 0)
    cx, cy = centro
    ImageDraw.Draw(brilho).ellipse((cx - 430, cy - 300, cx + 430, cy + 260), fill=46)
    brilho = brilho.filter(ImageFilter.GaussianBlur(140))
    return Image.composite(Image.new("RGB", base.size, _hex(cor)), base, brilho)


def compor(chave, destino=DESTINO):
    render = Image.open(RENDERS / f"{chave}.png").convert("RGBA")
    alfa = render.getchannel("A")
    # o objeto (a sombra do chão é transparente: fica de fora da conta)
    caixa = alfa.point(lambda v: 255 if v > 180 else 0).getbbox()
    if not caixa:
        raise SystemExit(f"{chave}: o render está vazio")
    x0, y0, x1, y1 = caixa
    w, h = x1 - x0, y1 - y0
    esq, cima, dir_, baixo = FOLGAS
    util_l, util_a = 1 - esq - dir_, 1 - cima - baixo
    # a largura do corte (em pixels do render) que põe o objeto dentro das folgas
    corte_l = max(w / util_l, h / (util_a * ALTURA / LARGURA))
    corte_a = corte_l * ALTURA / LARGURA
    cx = (x0 + x1) / 2
    # na vertical, o objeto fica no meio do espaço útil
    topo = y0 - (cima * corte_a + (util_a * corte_a - h) / 2)
    esquerda = cx - corte_l / 2
    caixa_corte = tuple(round(v) for v in (esquerda, topo, esquerda + corte_l, topo + corte_a))
    # o corte pode sair do render: o que está fora é transparente
    recorte = Image.new("RGBA", (caixa_corte[2] - caixa_corte[0], caixa_corte[3] - caixa_corte[1]), (0, 0, 0, 0))
    recorte.paste(render, (-caixa_corte[0], -caixa_corte[1]))
    recorte = recorte.resize((LARGURA, ALTURA), Image.LANCZOS)
    # o centro do objeto na foto final (para o brilho)
    escala = LARGURA / corte_l
    centro = ((cx - caixa_corte[0]) * escala, ((y0 + y1) / 2 - caixa_corte[1]) * escala)
    foto = fundo(CORES.get(chave.split("@")[0], "#0878f9"), centro).convert("RGBA")
    foto.alpha_composite(recorte)
    foto = foto.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=45, threshold=2))
    destino.mkdir(parents=True, exist_ok=True)
    saida = destino / f"{chave}.webp"
    foto.save(saida, "WEBP", quality=84, method=6)
    return saida


def main(argumentos):
    # "--para <pasta>": grava as provas em outra pasta (os ângulos experimentados)
    destino = DESTINO
    if "--para" in argumentos:
        i = argumentos.index("--para")
        destino = Path(argumentos[i + 1])
        argumentos = argumentos[:i] + argumentos[i + 2:]
    chaves = argumentos or sorted(p.stem for p in RENDERS.glob("*.png") if p.stem in CORES)
    for chave in chaves:
        saida = compor(chave, destino)
        print(f"{chave}: {saida} ({saida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
