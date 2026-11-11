"""As fotos das categorias: o lugar desfocado, os brinquedos nítidos, o corte 4:3 do card.

Lê os renders do gerar.cjs em `render/` e grava
`core/static/site/categorias/<chave>.webp`, 1600 × 1200, que é o que o
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

AS CAPAS DOS PRODUTOS ("capa:<chave>" no gerar.cjs, render/capa_<chave>.png):
o mesmo, quadrado (1600 × 1600, o card de produto e a galeria), gravado em
`core/static/site/arena/modelos/<chave>/capa.webp` -- a primeira foto do
cadastro do produto (core/cadastro_modelos.py, CADASTROS[chave]["fotos"]).

A NITIDEZ: o render vem no DOBRO do tamanho (3200 px de largura: o
supersampling) e aqui é reduzido com o filtro Lanczos -- as bordas, as
texturas e as sombras sem serrilhado. Na capa, o lugar desfoca pouco (como
nas imagens da fábrica, o salão inteiro se lê) e o brilho das luzes é leve.

O BRINQUEDO VIVO (LEIA-ME, seção 72). O cliente: "veja se vc consegue deixar
mais vivo os brinquedos nas fotos". Nas fotos de produto (as capas do
catálogo, as capas e as vistas dos nossos 3D), só NO BRINQUEDO (a máscara;
o fundo fica como está): a cor mais viva -- o "vibrance", que puxa mais a
cor fraca e quase nada a que já é forte, e nada o branco, o cinza e o preto
(sem estourar nem mudar o tom) --, o contraste local (a "clareza": o volume
das peças e a arte dos adesivos) e um tico de contraste. `VIVO` diz quanto.

O ARQUIVO fica abaixo de ~250 KB: a qualidade do WebP desce até caber.

    python ferramentas/categorias/compor.py                    (todas as que têm render)
    python ferramentas/categorias/compor.py kids               (só esta)
    python ferramentas/categorias/compor.py capa_strike-kids   (só esta capa)
"""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

PASTA = Path(__file__).resolve().parent
RENDERS = PASTA / "render"
DESTINO = PASTA.parent.parent / "core" / "static" / "site" / "categorias"
#: As capas do catálogo (seção 64): a foto de cada máquina no lugar dela, quadrada.
CATALOGO = PASTA.parent.parent / "core" / "static" / "site" / "capas_catalogo"
#: Onde ficam as fotos de cada produto nosso em 3D (a capa vai junto, como capa.webp).
MODELOS = PASTA.parent.parent / "core" / "static" / "site" / "arena" / "modelos"

LARGURA, ALTURA = 1600, 1200
#: O render tem o dobro da largura da foto (o supersampling).
LARGURA_DO_RENDER = 3200
#: O teto do arquivo (o card baixa a foto inteira).
TETO_KB = 250
#: O teto da capa do produto (quadrada; a galeria a mostra grande).
TETO_CAPA_KB = 250
#: O teto de cada vista da galeria dos nossos 3D.
TETO_VISTA_KB = 200
#: O desfoque do lugar onde o peso é 1 (em pixels do render de 3200; a prévia, na metade, usa a metade).
DESFOQUE = 8
#: Na capa, o lugar desfoca pouco: o salão se lê inteiro, como nas imagens da fábrica.
DESFOQUE_CAPA = 3
#: Na capa do catálogo, o fundo desfoca como numa foto (a profundidade de campo da câmera).
DESFOQUE_PRODUTO = 9
#: O brinquedo vivo (só no produto, nas fotos de produto): o vibrance (quanto a cor fraca sobe), a
#: clareza (o contraste local: o raio, em fração da largura, e a força em %), o contraste, o teto e
#: o piso (a luz, 0-255, acima e abaixo da qual a clareza e o contraste somem: o branco não estoura
#: e o preto não empasta).
VIVO = {"vibrance": 0.42, "clareza_raio": 1 / 90, "clareza": 22, "contraste": 1.05, "teto": 205, "piso": 48}
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
    # o card fixo "Peças e acessórios" da home (não é categoria; o mesmo corte 4:3)
    "pecas-e-acessorios": "#ea580c",
}
#: O desfoque de cada foto, quando não é o de sempre: a das peças é de perto (o fundo desfoca mais).
DESFOQUES = {"pecas-e-acessorios": 21}


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


def salvar(foto, saida, teto_kb=TETO_KB):
    """O WebP com a melhor qualidade que cabe no teto."""
    for qualidade in (86, 82, 78, 74, 70, 66, 62, 58):
        foto.save(saida, "WEBP", quality=qualidade, method=6)
        if saida.stat().st_size <= teto_kb * 1024:
            break
    return saida


#: A caixa do produto em cada foto de produto (a da máscara, em fração da foto): o teste mede
#: ali o contraste, a saturação e a nitidez ("nenhum pode ficar apagado").
AREAS = PASTA / "areas-dos-produtos.json"


def anotar_area(chave, mascara):
    import json

    caixa = mascara.point(lambda v: 255 if v > 128 else 0).getbbox()
    if not caixa or not chave.startswith(("produto_", "capa_", "vista_")):
        return
    w, h = mascara.size
    areas = json.loads(AREAS.read_text(encoding="utf-8")) if AREAS.exists() else {}
    areas[chave.split("~")[0]] = [round(caixa[0] / w, 3), round(caixa[1] / h, 3), round(caixa[2] / w, 3), round(caixa[3] / h, 3)]
    AREAS.write_text(json.dumps(dict(sorted(areas.items())), indent=1) + "\n", encoding="utf-8")


def compor_no_lugar(chave):
    """A foto no lugar: o lugar desfocado pelo peso e os brinquedos nítidos por cima."""
    cor = Image.open(RENDERS / f"{chave}.png").convert("RGB")
    peso = Image.open(RENDERS / f"{chave}-peso.png").convert("L")
    mascara = Image.open(RENDERS / f"{chave}-mascara.png").getchannel("A")
    if "~" not in chave:
        anotar_area(chave, mascara)
    capa = chave.startswith("capa_")
    produto = chave.startswith(("produto_", "vista_"))
    padrao = DESFOQUE_PRODUTO if produto else DESFOQUE_CAPA if capa else DESFOQUE
    raio = DESFOQUES.get(chave, padrao) * cor.width / LARGURA_DO_RENDER
    desfocado = cor.filter(ImageFilter.GaussianBlur(raio))
    # o lugar desfocado perde um tico de cor: os brinquedos saltam (sem ficar lavado)
    desfocado = ImageEnhance.Color(desfocado).enhance(0.95)
    lugar = Image.composite(desfocado, cor, peso.filter(ImageFilter.GaussianBlur(3)))
    foto = Image.composite(cor, lugar, mascara)
    # 4:3 nas categorias (1600 × 1200); a capa, quadrada, 1600 × 1600: a mesma largura; a vista
    # da galeria, o tamanho do arquivo de antes (o render tem o dobro)
    largura = cor.width // 2 if chave.startswith("vista_") else LARGURA
    foto = foto.resize((largura, round(largura * cor.height / cor.width)), Image.LANCZOS)
    foto = foto.filter(ImageFilter.UnsharpMask(radius=1.0, percent=40, threshold=2))
    if produto or capa:
        # a foto de produto: o produto bem nítido (a arte dos adesivos se lê; o fundo já está desfocado)
        no_produto = mascara.resize(foto.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))
        nitido = foto.filter(ImageFilter.UnsharpMask(radius=1.8, percent=90, threshold=2))
        foto = Image.composite(nitido, foto, no_produto)
        # e vivo: a cor, o volume e o contraste, só nele
        foto = Image.composite(vivo(foto), foto, no_produto)
    if produto:
        # a capa do catálogo, como uma foto: a cor como está (nada de saturar), o brilho só
        # nas lâmpadas, a vinheta leve e um grão bem fino
        return grao(vinheta(brilho(vida(foto, cor=1.0, contraste=1.03), forca=0.3), forca=0.1))
    if capa:
        # a capa: as cores limpas, o brilho só nos spots e a vinheta quase nada
        return vinheta(brilho(vida(foto, cor=1.06, contraste=1.03), forca=0.35), forca=0.08)
    return vinheta(brilho(vida(foto)))


def vivo(foto, vibrance=None, clareza=None, contraste=None):
    """O brinquedo mais vivo, sem estourar: o vibrance, a clareza e um tico de contraste (`VIVO`).

    O vibrance: a saturação s vira s + k·s·(1 - s/255) -- a cor fraca sobe, a
    forte quase não muda e o branco, o cinza e o preto (s = 0) ficam como
    estão; o tom e a luz não mudam. A clareza: o unsharp de raio largo, que
    dá volume às peças sem serrilhar as bordas.
    """
    vibrance = VIVO["vibrance"] if vibrance is None else vibrance
    clareza = VIVO["clareza"] if clareza is None else clareza
    contraste = VIVO["contraste"] if contraste is None else contraste
    h, s, v = foto.convert("HSV").split()
    s = s.point(lambda x: min(255, round(x + vibrance * x * (255 - x) / 255)))
    foto = Image.merge("HSV", (h, s, v)).convert("RGB")
    raio = max(2, round(foto.width * VIVO["clareza_raio"]))
    forte = foto.filter(ImageFilter.UnsharpMask(radius=raio, percent=clareza, threshold=3))
    forte = ImageEnhance.Contrast(forte).enhance(contraste)
    # sem estourar nem empretecer: no que já é quase branco (a luz acima de `VIVO["teto"]`) e no
    # que já é quase preto (abaixo de `VIVO["piso"]`), a clareza e o contraste somem aos poucos --
    # o branco não vira chapado, o brilho não cresce e o preto do gabinete guarda os detalhes
    teto, piso = VIVO["teto"], VIVO["piso"]
    claro = v.point(lambda x: 0 if x < teto else min(255, (x - teto) * 255 // max(1, 250 - teto)))
    escuro = v.point(lambda x: 0 if x > piso else min(255, (piso - x) * 255 // max(1, piso - 6)))
    return Image.composite(foto, forte, ImageChops.lighter(claro, escuro))


def vida(foto, cor=1.12, contraste=1.05):
    """As cores um tanto mais vivas e com mais contraste."""
    foto = ImageEnhance.Color(foto).enhance(cor)
    return ImageEnhance.Contrast(foto).enhance(contraste)


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


def grao(foto, forca=4.0):
    """Um grão bem leve, como o do sensor da câmera (o mesmo sempre: a semente é fixa)."""
    import random

    aleatorio = random.Random(7)
    ruido = Image.new("L", foto.size)
    ruido.putdata([max(0, min(255, int(128 + aleatorio.gauss(0, forca)))) for _ in range(foto.size[0] * foto.size[1])])
    ruido = ruido.filter(ImageFilter.GaussianBlur(0.5))
    neutro = Image.new("L", foto.size, 128)
    canais = [ImageChops.add(ImageChops.subtract(c, neutro, offset=128), ruido, offset=-128) for c in foto.split()]
    return Image.merge("RGB", canais)


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
    if chave.startswith("vista_"):
        # a vista da galeria: por cima do arquivo de antes, em core/static/site/arena/modelos/<chave>/<vista>.webp
        if destino == DESTINO:
            modelo, vista = chave[len("vista_"):].split("_", 1)
            saida = MODELOS / modelo / f"{vista}.webp"
        else:
            saida = destino / f"{chave}.webp"
        return salvar(foto, saida, TETO_VISTA_KB)
    if chave.startswith("produto_"):
        # a capa do catálogo: core/static/site/capas_catalogo/<chave>.webp (ou, nas provas, <pasta>/produto_<chave>.webp)
        saida = CATALOGO / f"{chave[len('produto_'):]}.webp" if destino == DESTINO else destino / f"{chave}.webp"
        saida.parent.mkdir(parents=True, exist_ok=True)
        return salvar(foto, saida, TETO_CAPA_KB)
    if chave.startswith("capa_"):
        # a capa do produto: na pasta dele (ou, nas provas, <pasta>/capa_<chave>.webp)
        saida = MODELOS / chave[len("capa_"):] / "capa.webp" if destino == DESTINO else destino / f"{chave}.webp"
        saida.parent.mkdir(parents=True, exist_ok=True)
        return salvar(foto, saida, TETO_CAPA_KB)
    destino.mkdir(parents=True, exist_ok=True)
    return salvar(foto, destino / f"{chave}.webp")


def main(argumentos):
    # "--para <pasta>": grava as provas em outra pasta (os ângulos experimentados)
    destino = DESTINO
    if "--para" in argumentos:
        i = argumentos.index("--para")
        destino = Path(argumentos[i + 1])
        argumentos = argumentos[:i] + argumentos[i + 2:]
    chaves = argumentos or sorted(
        p.stem for p in RENDERS.glob("*.png")
        if p.stem in CORES or (p.stem.startswith(("capa_", "produto_", "vista_")) and not p.stem.endswith(("-mascara", "-peso")))
    )
    for chave in chaves:
        saida = compor(chave, destino)
        print(f"{chave}: {saida} ({saida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
