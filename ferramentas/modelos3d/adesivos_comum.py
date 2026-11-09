"""O que as ferramentas dos adesivos dividem (Air Game Hockey Espacial, Basquete Street Quadrinhos).

Cada máquina com adesivos tem, na pasta dela (ferramentas/modelos3d/<id>/):

  * adesivos/<peça>.png -- a arte de cada peça, vista de fora e em pé, como
    na folha da fábrica; é o que o montar.js cola no objeto 3D;
  * pecas.json -- o tamanho de cada peça (mm), onde ela vai e, na peça
    recortada, o contorno (em frações da imagem). O gerar.cjs grava, a
    partir do montar.js: é a medida da face no 3D;
  * recortes.json -- onde cada peça está na folha de adesivos da fábrica
    (a caixa, em px da folha, e quanto girar);
  * recortar_adesivos.py -- recorta a folha nas peças (usa `recortar`, daqui);
  * desenhar_provisorios.py -- a arte provisória, enquanto a folha não chega.

Só precisa do Pillow (pip install pillow).
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ======================================================================
# AS PEÇAS E O RECORTE DA FOLHA
# ======================================================================


def ler_pecas(pasta):
    """O pecas.json da máquina: {peça: {"arquivo", "mm": [largura, altura], "onde", "contorno"?}}."""
    return json.loads((Path(pasta) / "pecas.json").read_text(encoding="utf-8"))


def _caixa(dados, folha):
    """A caixa da peça na folha, em px: [x0, y0, x1, y1]; ou "caixa_rel", em frações da folha."""
    if "caixa_rel" in dados:
        x0, y0, x1, y1 = dados["caixa_rel"]
        return [round(x0 * folha.width), round(y0 * folha.height), round(x1 * folha.width), round(y1 * folha.height)]
    return [round(v) for v in dados["caixa"]]


def recortar(pasta, argumentos=None):
    """Recorta a folha de adesivos da fábrica nas peças (adesivos/<peça>.png).

    Lê o recortes.json da pasta: a folha (o arquivo da imagem) e, de cada
    peça, a caixa na folha ([x0, y0, x1, y1] em px, ou "caixa_rel" em frações),
    quanto girar (0, 90, 180 ou 270 graus, no sentido anti-horário, para a
    peça ficar em pé, vista de fora) e se espelha. Confere a proporção com a
    do pecas.json (a medida da face no 3D) e avisa quando passa de 4%.
    """
    pasta = Path(pasta)
    parser = argparse.ArgumentParser(description="Recorta a folha de adesivos nas peças (adesivos/<peça>.png).")
    parser.add_argument("folha", nargs="?", help="a imagem da folha (senão, a do recortes.json)")
    parser.add_argument("--recortes", default=str(pasta / "recortes.json"), help="o arquivo com as caixas")
    parser.add_argument("--so", nargs="*", help="só estas peças")
    parser.add_argument("--previa", action="store_true", help="só desenha as caixas na folha (previa-recortes.jpg), sem recortar")
    parser.add_argument("--maximo", type=int, default=2048, help="o lado maior de cada peça, em px (padrão 2048)")
    parser.add_argument("--esticar", action="store_true", help="estica cada peça na proporção do pecas.json")
    parser.add_argument("--saida", help="a pasta das peças (padrão: adesivos/ da máquina)")
    args = parser.parse_args(argumentos)

    recortes = json.loads(Path(args.recortes).read_text(encoding="utf-8"))
    pecas = ler_pecas(pasta)
    folhas = {}

    def abrir(nome):
        caminho = Path(nome)
        if not caminho.is_absolute() and not caminho.exists():
            caminho = pasta / caminho  # o nome do recortes.json: na pasta da máquina
        if caminho not in folhas:
            Image.MAX_IMAGE_PIXELS = None  # a folha da gráfica é enorme
            folhas[caminho] = Image.open(caminho).convert("RGB")
        return folhas[caminho]

    padrao = args.folha or recortes.get("folha")
    escolhidas = {k: v for k, v in recortes["pecas"].items() if not args.so or k in args.so}
    vazias = sorted(k for k, v in escolhidas.items() if not (v.get("caixa") or v.get("caixa_rel")))
    if vazias:
        print("Sem caixa ainda (ficam como estão):", ", ".join(vazias))
    escolhidas = {k: v for k, v in escolhidas.items() if k not in vazias}
    if not escolhidas:
        raise SystemExit("Nenhuma peça com caixa no recortes.json: marque onde cada peça está na folha.")
    if not padrao and any("folha" not in v for v in escolhidas.values()):
        raise SystemExit("Diga a folha: python3 recortar_adesivos.py caminho/da/folha.jpg (ou \"folha\" no recortes.json).")
    desconhecidas = sorted(set(escolhidas) - set(pecas))
    if desconhecidas:
        raise SystemExit(f"Peças que o pecas.json não tem: {', '.join(desconhecidas)}")

    if args.previa:
        por_folha = {}
        for peca, dados in escolhidas.items():
            por_folha.setdefault(dados.get("folha", padrao), []).append((peca, dados))
        for i, (nome, lista) in enumerate(por_folha.items()):
            folha = abrir(nome).copy()
            escala = min(1.0, 2400 / max(folha.size))
            folha = folha.resize((round(folha.width * escala), round(folha.height * escala)))
            d = ImageDraw.Draw(folha)
            letra = fonte(max(14, round(folha.width / 70)))
            for peca, dados in lista:
                x0, y0, x1, y1 = [v * escala for v in _caixa(dados, abrir(nome))]
                d.rectangle([x0, y0, x1, y1], outline="#ff2bd6", width=max(2, round(folha.width / 600)))
                d.text((x0 + 6, y0 + 4), f"{peca} ({dados.get('girar', 0)}°)", font=letra, fill="#ff2bd6",
                       stroke_width=3, stroke_fill="#ffffff")
            saida = pasta / ("previa-recortes.jpg" if i == 0 else f"previa-recortes-{i + 1}.jpg")
            folha.save(saida, quality=85)
            print("prévia:", saida)
        return

    destino = Path(args.saida) if args.saida else pasta / "adesivos"
    destino.mkdir(parents=True, exist_ok=True)
    for peca, dados in escolhidas.items():
        folha = abrir(dados.get("folha", padrao))
        x0, y0, x1, y1 = _caixa(dados, folha)
        if not (0 <= x0 < x1 <= folha.width and 0 <= y0 < y1 <= folha.height):
            raise SystemExit(f"{peca}: a caixa {[x0, y0, x1, y1]} sai da folha ({folha.width} x {folha.height})")
        imagem = folha.crop((x0, y0, x1, y1))
        girar = int(dados.get("girar", 0)) % 360
        if girar:
            imagem = imagem.rotate(girar, expand=True)
        if dados.get("espelhar"):
            imagem = imagem.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        largura, altura = pecas[peca]["mm"]
        proporcao = (imagem.width / imagem.height) / (largura / altura)
        if args.esticar:
            imagem = imagem.resize((imagem.width, round(imagem.width * altura / largura)), Image.Resampling.LANCZOS)
        elif abs(proporcao - 1) > 0.04:
            print(f"AVISO {peca}: o recorte tem {imagem.width} x {imagem.height} px e a peça {largura} x {altura} mm "
                  f"({(proporcao - 1) * 100:+.1f}% na proporção); confira a caixa e o giro (o 3D estica)")
        escala = min(1.0, args.maximo / max(imagem.size))
        if escala < 1:
            imagem = imagem.resize((round(imagem.width * escala), round(imagem.height * escala)), Image.Resampling.LANCZOS)
        imagem.save(destino / f"{peca}.png", optimize=True)
        print(f"{peca}: {imagem.width} x {imagem.height} px")
    faltam = sorted(set(pecas) - set(recortes["pecas"]))
    if faltam:
        print("Fora do recortes.json (ficam como estão):", ", ".join(faltam))
    print("Pronto. Agora refaça o 3D: node gerar.cjs glb fotos (e o gltfpack; ver o README).")


# ======================================================================
# A ARTE PROVISÓRIA: uma tela em mm, desenhada em dobro e reduzida (sem serrilhado)
# ======================================================================

FONTES = {
    (True, False): ("/usr/share/fonts/opentype/inter/Inter-Black.otf", "DejaVuSans-Bold.ttf"),
    (True, True): ("/usr/share/fonts/opentype/inter/Inter-BlackItalic.otf", "DejaVuSans-BoldOblique.ttf"),
    (False, False): ("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "DejaVuSans-Bold.ttf"),
    (False, True): ("/usr/share/fonts/opentype/inter/Inter-BoldItalic.otf", "DejaVuSans-BoldOblique.ttf"),
}


def fonte(tamanho, pesada=True, italica=False):
    """Uma fonte grossa (a Inter Black, se houver; senão a DejaVu Bold)."""
    for caminho in FONTES[(pesada, italica)]:
        try:
            return ImageFont.truetype(caminho, max(1, round(tamanho)))
        except OSError:
            continue
    return ImageFont.load_default()


class Tela:
    """Uma peça para desenhar em mm: `px(mm)` converte; desenha em dobro e reduz no fim."""

    def __init__(self, mm, px_por_mm=0.75, fundo="#000000", dobro=2):
        self.mm = mm
        self.final = (round(mm[0] * px_por_mm), round(mm[1] * px_por_mm))
        self.k = px_por_mm * dobro
        self.im = Image.new("RGBA", (round(mm[0] * self.k), round(mm[1] * self.k)), fundo)
        self.d = ImageDraw.Draw(self.im)

    @property
    def tamanho(self):
        return self.im.size

    def px(self, *valores):
        """mm -> px da tela de trabalho (um número ou vários)."""
        saida = [v * self.k for v in valores]
        return saida[0] if len(saida) == 1 else saida

    def camada(self):
        return Image.new("RGBA", self.im.size, (0, 0, 0, 0))

    def colar(self, camada, desfoque=0, modo="normal"):
        if desfoque:
            camada = camada.filter(ImageFilter.GaussianBlur(self.px(desfoque)))
        if modo == "somar":
            base = self.im.convert("RGB")
            self.im = Image.merge("RGBA", (*ImageChops.add(base, _sobre_preto(camada)).split(), self.im.getchannel("A")))
        else:
            self.im.alpha_composite(camada)
        self.d = ImageDraw.Draw(self.im)

    def salvar(self, caminho, cores=None):
        imagem = self.im.convert("RGB").resize(self.final, Image.Resampling.LANCZOS)
        if cores:  # menos cores: o PNG fica bem menor (é só a arte provisória)
            imagem = imagem.quantize(cores, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        imagem.save(caminho, optimize=True)
        return imagem


def _sobre_preto(camada):
    preto = Image.new("RGBA", camada.size, (0, 0, 0, 255))
    preto.alpha_composite(camada)
    return preto.convert("RGB")


def degrade(tamanho, cores, horizontal=False):
    """Um degradê de várias cores (de cima para baixo, ou da esquerda para a direita)."""
    w, h = tamanho
    n = w if horizontal else h
    faixa = Image.new("RGB", (1, n) if not horizontal else (n, 1))
    rgb = [Image.new("RGB", (1, 1), c).getpixel((0, 0)) for c in cores]
    for i in range(n):
        t = i / max(1, n - 1) * (len(rgb) - 1)
        k = min(int(t), len(rgb) - 2)
        f = t - k
        cor = tuple(round(rgb[k][j] + (rgb[k + 1][j] - rgb[k][j]) * f) for j in range(3))
        faixa.putpixel((0, i) if not horizontal else (i, 0), cor)
    return faixa.resize((w, h), Image.Resampling.BILINEAR).convert("RGBA")


def poligono_estrela(cx, cy, r_fora, r_dentro, pontas, giro=0.0, sorte=None):
    """Os pontos de uma estrela (a explosão dos quadrinhos, com as pontas irregulares)."""
    pts = []
    for i in range(pontas * 2):
        a = giro + math.pi * i / pontas
        r = r_fora if i % 2 == 0 else r_dentro
        if sorte is not None:
            r *= 0.82 + 0.3 * sorte.random() if i % 2 == 0 else 0.92 + 0.12 * sorte.random()
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def capsula(x0, y0, x1, y1, largura, passos=14):
    """O contorno de uma faixa de pontas redondas, de (x0, y0) a (x1, y1)."""
    ang = math.atan2(y1 - y0, x1 - x0)
    r = largura / 2
    pts = []
    for cx, cy, a0 in ((x1, y1, ang - math.pi / 2), (x0, y0, ang + math.pi / 2)):
        for i in range(passos + 1):
            a = a0 + math.pi * i / passos
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def texto(tela, centro, frase, altura_mm, cor, contorno=None, grossura_mm=0, giro=0, sombra=None,
          deslocamento_mm=(0, 0), italica=False, largura_max_mm=None):
    """Escreve centrado em `centro` (mm), com o contorno, a sombra e girado (graus, anti-horário)."""
    tamanho = tela.px(altura_mm) * 1.32
    letra = fonte(tamanho, italica=italica)
    grossura = round(tela.px(grossura_mm)) if contorno else 0
    caixa = letra.getbbox(frase, stroke_width=grossura)
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    if largura_max_mm and w > tela.px(largura_max_mm):
        return texto(tela, centro, frase, altura_mm * tela.px(largura_max_mm) / w, cor, contorno, grossura_mm, giro,
                     sombra, deslocamento_mm, italica)
    folga = round(tela.px(abs(max(deslocamento_mm, key=abs)) if sombra else 0)) + 8
    camada = Image.new("RGBA", (w + 2 * folga + 8, h + 2 * folga + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    origem = (folga + 4 - caixa[0], folga + 4 - caixa[1])
    if sombra:
        dx, dy = tela.px(*deslocamento_mm)
        d.text((origem[0] + dx, origem[1] + dy), frase, font=letra, fill=sombra, stroke_width=grossura, stroke_fill=sombra)
    d.text(origem, frase, font=letra, fill=cor, stroke_width=grossura, stroke_fill=contorno)
    if giro:
        camada = camada.rotate(giro, expand=True, resample=Image.Resampling.BICUBIC)
    cx, cy = tela.px(*centro)
    tela.im.alpha_composite(camada, (round(cx - camada.width / 2), round(cy - camada.height / 2)))
    tela.d = ImageDraw.Draw(tela.im)


def estrelas(tela, quantas, sorte, area=None, cores=("#ffffff", "#fff6c8", "#cfe8ff"), brilhos=0):
    """O céu: pontinhos de vários tamanhos e algumas estrelas de quatro pontas com o brilho."""
    x0, y0, x1, y1 = area or (0, 0, *tela.mm)
    for _ in range(quantas):
        x, y = sorte.uniform(x0, x1), sorte.uniform(y0, y1)
        r = tela.px(sorte.choice((1.2, 1.6, 2.2, 2.2, 3.0, 4.2)))
        cx, cy = tela.px(x, y)
        tela.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=sorte.choice(cores))
    brilho = tela.camada()
    d = ImageDraw.Draw(brilho)
    for _ in range(brilhos):
        x, y = sorte.uniform(x0 + 25, x1 - 25), sorte.uniform(y0 + 25, y1 - 25)
        cx, cy = tela.px(x, y)
        r = tela.px(sorte.uniform(10, 24))
        d.ellipse([cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5], fill=(255, 255, 255, 90))
        for a in (0, math.pi / 2):
            pts = [(cx + r * math.cos(a), cy + r * math.sin(a)), (cx + r * 0.12 * math.cos(a + math.pi / 2), cy + r * 0.12 * math.sin(a + math.pi / 2)),
                   (cx - r * math.cos(a), cy - r * math.sin(a)), (cx - r * 0.12 * math.cos(a + math.pi / 2), cy - r * 0.12 * math.sin(a + math.pi / 2))]
            tela.d.polygon(pts, fill="#ffffff")
    tela.colar(brilho, desfoque=3)


def nebulosa(tela, sorte, cores, quantas=5, area=None):
    """Os redemoinhos coloridos do céu: espirais grossas, desfocadas e somadas."""
    x0, y0, x1, y1 = area or (0, 0, *tela.mm)
    camada = tela.camada()
    d = ImageDraw.Draw(camada)
    for i in range(quantas):
        cx, cy = sorte.uniform(x0, x1), sorte.uniform(y0, y1)
        cor = cores[i % len(cores)]
        rgb = Image.new("RGB", (1, 1), cor).getpixel((0, 0))
        voltas = sorte.uniform(1.2, 2.2)
        r_max = sorte.uniform(0.18, 0.32) * min(x1 - x0, y1 - y0) * 2.2
        sentido = sorte.choice((-1, 1))
        pts = []
        for k in range(160):
            t = k / 159
            a = sentido * t * voltas * 2 * math.pi
            r = r_max * (0.08 + 0.92 * t)
            pts.append(tela.px(cx + r * math.cos(a), cy + r * 0.62 * math.sin(a)))
        for k in range(len(pts) - 1):
            alfa = round(110 * math.sin(math.pi * k / len(pts)))
            d.line([pts[k], pts[k + 1]], fill=(*rgb, alfa), width=round(tela.px(r_max * 0.18)))
    tela.colar(camada, desfoque=26, modo="somar")


def planeta(tela, cx, cy, r, cor, cor_clara, faixas=None, anel=None, giro_anel=-14):
    """Um planeta com a luz de cima à esquerda, as faixas e, se quiser, o anel."""
    if anel:
        _anel(tela, cx, cy, r, anel, giro_anel, metade="tras")
    k = tela.k
    lado = round(2 * r * k)
    disco = degrade((lado, lado), (cor_clara, cor, cor), horizontal=False)
    if faixas:
        d = ImageDraw.Draw(disco)
        for i, faixa in enumerate(faixas):
            y = lado * (0.18 + 0.64 * i / max(1, len(faixas) - 1))
            d.ellipse([-lado * 0.3, y - lado * 0.05, lado * 1.3, y + lado * 0.05], fill=faixa)
    sombra = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(sombra).ellipse([lado * 0.18, lado * 0.15, lado * 1.25, lado * 1.2], fill=110)
    sombra = sombra.filter(ImageFilter.GaussianBlur(lado * 0.08))
    disco = Image.composite(Image.new("RGBA", (lado, lado), (10, 6, 30, 255)), disco, sombra)
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).ellipse([0, 0, lado - 1, lado - 1], fill=255)
    disco.putalpha(mascara)
    tela.im.alpha_composite(disco, (round((cx - r) * k), round((cy - r) * k)))
    tela.d = ImageDraw.Draw(tela.im)
    if anel:
        _anel(tela, cx, cy, r, anel, giro_anel, metade="frente")


def _anel(tela, cx, cy, r, cor, giro, metade):
    camada = tela.camada()
    d = ImageDraw.Draw(camada)
    caixa = [*tela.px(cx - r * 1.75, cy - r * 0.42), *tela.px(cx + r * 1.75, cy + r * 0.42)]
    inicio, fim = (180, 360) if metade == "tras" else (0, 180)
    d.arc(caixa, inicio, fim, fill=cor, width=round(tela.px(r * 0.16)))
    camada = camada.rotate(giro, center=tela.px(cx, cy), resample=Image.Resampling.BICUBIC)
    tela.colar(camada)


def cratera(tela, cx, cy, r, escura, clara):
    """Uma cratera do chão lunar: a cova escura com a borda clara embaixo."""
    tela.d.ellipse([*tela.px(cx - r, cy - r * 0.42), *tela.px(cx + r, cy + r * 0.42)], fill=clara)
    tela.d.ellipse([*tela.px(cx - r * 0.86, cy - r * 0.44), *tela.px(cx + r * 0.86, cy + r * 0.26)], fill=escura)


def chao_lunar(tela, borda, sorte, cores=("#ffb02e", "#ff7a1a"), cratera_escura="#d9560f", cratera_clara="#ffd27a",
               crateras=8, area=None):
    """O chão lunar laranja: a linha dos morros (`borda`: [(x, y), ...] em mm) até embaixo, com crateras."""
    x0, y0, x1, y1 = area or (0, 0, *tela.mm)
    mascara = Image.new("L", tela.im.size, 0)
    ImageDraw.Draw(mascara).polygon([tela.px(*p) for p in borda] + [tela.px(x1, y1), tela.px(x0, y1)], fill=255)
    topo = min(p[1] for p in borda)
    camada = Image.new("RGBA", tela.im.size, (0, 0, 0, 0))
    camada.paste(degrade((tela.im.size[0], max(2, round(tela.px(y1 - topo)))), cores), (0, round(tela.px(topo))))
    tela.im.paste(camada, (0, 0), mascara)
    tela.d = ImageDraw.Draw(tela.im)
    feitas = 0
    tentativas = 0
    while feitas < crateras and tentativas < 400:
        tentativas += 1
        x = sorte.uniform(x0 + 30, x1 - 30)
        y = sorte.uniform(topo + 30, y1 - 10)
        if mascara.getpixel((min(mascara.width - 1, round(tela.px(x))), min(mascara.height - 1, round(tela.px(y - 25))))) < 128:
            continue
        cratera(tela, x, y, sorte.uniform(18, 46), cratera_escura, cratera_clara)
        feitas += 1


def morros(x0, x1, y_base, altura, sorte, passos=40, ondas=3):
    """A linha de morros suaves do chão lunar, de x0 a x1 (mm)."""
    fases = [sorte.uniform(0, 2 * math.pi) for _ in range(ondas)]
    pts = []
    for i in range(passos + 1):
        x = x0 + (x1 - x0) * i / passos
        t = i / passos
        y = y_base - altura * (0.5 + 0.5 * sum(math.sin(t * math.pi * (k + 1.3) * 1.7 + fases[k]) / (k + 1) for k in range(ondas)) / 1.8)
        pts.append((x, y))
    return pts


def semente(nome):
    """O sorteio de cada peça é sempre o mesmo (refazer dá a mesma arte)."""
    return random.Random(sum(ord(c) * (i + 1) for i, c in enumerate(nome)))
