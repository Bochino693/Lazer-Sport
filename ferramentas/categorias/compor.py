"""As fotos das categorias: o lugar desfocado, os brinquedos nítidos, o corte 4:3 do card.

Lê os renders do gerar.cjs em `render/` e grava
`core/static/site/categorias/<chave>.webp`, 1200 × 900, que é o que o
cadastro sobe para a categoria (ver core/categorias_capas.py e
`python manage.py atualizar_capas_categorias`).

NO LUGAR (as 16 fotos: o buffet, o shopping, a game zone...). O render já
vem enquadrado em 4:3 (cenas.js, `enquadrar`): os brinquedos no meio, com
folga dos lados e embaixo e uma folga maior em cima, onde o card põe a
etiqueta "Categoria". Junto vêm a máscara dos brinquedos e o peso do
desfoque (pela profundidade: o que está longe deles). Aqui o lugar é
desfocado na medida do peso e os brinquedos voltam por cima, nítidos --
como numa foto com o fundo fora de foco: eles saltam, e o lugar se lê.

NO ESTÚDIO (sem lugar: as provas de ângulo, "glb:<nome>"). O render vem
com o fundo transparente; aqui entram o fundo claro do card e o corte em
volta do objeto.

O ARQUIVO fica abaixo de ~150 KB: a qualidade do WebP desce até caber.

    python ferramentas/categorias/compor.py            (todas as que têm render)
    python ferramentas/categorias/compor.py kids       (só esta)
"""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

PASTA = Path(__file__).resolve().parent
RENDERS = PASTA / "render"
DESTINO = PASTA.parent.parent / "core" / "static" / "site" / "categorias"

LARGURA, ALTURA = 1200, 900
#: O teto do arquivo (o card baixa a foto inteira).
TETO_KB = 150
#: O desfoque do lugar onde o peso é 1 (em pixels do render, que tem o dobro da foto).
DESFOQUE = 6
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


def salvar(foto, saida):
    """O WebP com a melhor qualidade que cabe no teto."""
    for qualidade in (86, 82, 78, 74, 70, 66, 62, 58):
        foto.save(saida, "WEBP", quality=qualidade, method=6)
        if saida.stat().st_size <= TETO_KB * 1024:
            break
    return saida


def compor_no_lugar(chave):
    """A foto no lugar: o lugar desfocado pelo peso e os brinquedos nítidos por cima."""
    cor = Image.open(RENDERS / f"{chave}.png").convert("RGB")
    peso = Image.open(RENDERS / f"{chave}-peso.png").convert("L")
    mascara = Image.open(RENDERS / f"{chave}-mascara.png").getchannel("A")
    desfocado = cor.filter(ImageFilter.GaussianBlur(DESFOQUE))
    # o lugar desfocado perde um tico de cor: os brinquedos saltam (sem ficar lavado)
    desfocado = ImageEnhance.Color(desfocado).enhance(0.95)
    lugar = Image.composite(desfocado, cor, peso.filter(ImageFilter.GaussianBlur(3)))
    foto = Image.composite(cor, lugar, mascara)
    foto = foto.resize((LARGURA, ALTURA), Image.LANCZOS)
    foto = foto.filter(ImageFilter.UnsharpMask(radius=1.1, percent=50, threshold=2))
    return vinheta(brilho(vida(foto)))


def vida(foto):
    """As cores um tanto mais vivas e com mais contraste."""
    foto = ImageEnhance.Color(foto).enhance(1.12)
    return ImageEnhance.Contrast(foto).enhance(1.05)


def brilho(foto, limite=236, forca=0.7):
    """O brilho das luzes (bloom): o que é quase branco (as lâmpadas, o miolo do neon) se espalha.

    Pela luminância, e não pelo canal mais forte: um piso azul bem saturado
    tem o azul alto, mas não é luz -- e ficava lavado.
    """
    mascara = foto.convert("L").point(lambda v: 0 if v < limite else min(255, (v - limite) * 14))
    luzes = Image.composite(foto, Image.new("RGB", foto.size, 0), mascara)
    perto = luzes.filter(ImageFilter.GaussianBlur(10))
    longe = luzes.filter(ImageFilter.GaussianBlur(34))
    halo = ImageChops.add(ImageEnhance.Brightness(perto).enhance(forca), ImageEnhance.Brightness(longe).enhance(forca * 0.8))
    return ImageChops.screen(foto, halo)


def vinheta(foto, forca=0.18):
    """A vinheta leve: as bordas um tico mais escuras levam o olho para o meio."""
    w, h = foto.size
    m = Image.new("L", (w // 8, h // 8), 0)
    ImageDraw.Draw(m).ellipse((-w // 40, -h // 40, w // 8 + w // 40, h // 8 + h // 40), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(w // 50)).resize((w, h), Image.BILINEAR)
    escura = ImageEnhance.Brightness(foto).enhance(1 - forca)
    return Image.composite(foto, escura, m)


def compor_no_estudio(chave):
    """A foto de estúdio: o fundo claro do card e o corte em volta do objeto."""
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
    return foto.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=45, threshold=2))


def compor(chave, destino=DESTINO):
    no_lugar = (RENDERS / f"{chave}-mascara.png").exists()
    foto = compor_no_lugar(chave) if no_lugar else compor_no_estudio(chave)
    destino.mkdir(parents=True, exist_ok=True)
    return salvar(foto, destino / f"{chave}.webp")


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
