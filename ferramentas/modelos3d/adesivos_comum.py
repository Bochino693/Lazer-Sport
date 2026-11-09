"""O recorte das folhas de adesivos da fábrica (Air Game Kids Alienígenas, Basquete Street Quadrinhos).

Cada máquina com adesivos tem, na pasta dela (ferramentas/modelos3d/<id>/):

  * folha-adesivos.png -- a folha da gráfica, com as peças sobre o fundo
    branco e o nome de cada uma escrito em cima;
  * recortes.json -- onde está cada peça na folha: a `caixa` aproximada
    [x0, y0, x1, y1] (em px da folha; o recorte acha a peça de verdade dentro
    dela), e, se precisar, `angulo` (endireita a peça desenhada torta, em
    graus, anti-horário), `girar` (0/90/180/270), `espelhar`, `apagar`
    (caixas de outras peças que encostam nela), `forma` ("contorno" para a
    peça recortada; "retangulo" para a reta) e `dobras` (onde a peça dobra,
    em frações da altura);
  * recortar_adesivos.py -- roda o `recortar` daqui e grava:
      - adesivos/<peça>.png: a peça recortada no limite dela, sem margem
        branca, exatamente como está na folha;
      - formas.json: o tamanho de cada peça em px e, na peça recortada, o
        CONTORNO de verdade (o polígono da máscara não-branca, simplificado,
        em frações da imagem, a partir do canto de cima à esquerda). É ele que
        o montar.js usa como contorno da placa no 3D.

A arte é usada como está na folha: o recorte não redesenha, não recolore e não
tira nada. Só precisa do Pillow (pip install pillow).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

#: o quanto um pixel precisa fugir do branco para ser da peça (0 a 255)
LIMIAR = 40
#: a margem em volta da caixa aproximada, em px da folha
MARGEM = 8
#: a tolerância da simplificação do contorno, em px da folha
TOLERANCIA = 0.7
#: o fechamento da máscara (px): um traço branco da arte que encosta na borda
#: (as linhas brancas finas da arte) não vira um recorte na peça
FECHAR = 3


# ======================================================================
# A MÁSCARA DA PEÇA: o maior pedaço não branco, com os buracos preenchidos
# ======================================================================

def _nao_branco(imagem, limiar):
    """1 onde o pixel foge do branco (em algum canal mais que `limiar`), 0 no fundo."""
    canais = [ImageOps.invert(c) for c in imagem.convert("RGB").split()]
    escuro = ImageChops.lighter(ImageChops.lighter(canais[0], canais[1]), canais[2])
    return bytearray(1 if v > limiar else 0 for v in escuro.tobytes())


def _vizinhos(i, w, h):
    x, y = i % w, i // w
    if x > 0:
        yield i - 1
    if x < w - 1:
        yield i + 1
    if y > 0:
        yield i - w
    if y < h - 1:
        yield i + w


def _maior_pedaco(m, w, h):
    """O maior pedaço ligado (4-vizinhos) da máscara: os nomes escritos e as peças vizinhas ficam de fora."""
    visto = bytearray(len(m))
    melhor = []
    for inicio in range(len(m)):
        if not m[inicio] or visto[inicio]:
            continue
        visto[inicio] = 1
        fila, pedaco = deque([inicio]), [inicio]
        while fila:
            i = fila.popleft()
            for j in _vizinhos(i, w, h):
                if m[j] and not visto[j]:
                    visto[j] = 1
                    fila.append(j)
                    pedaco.append(j)
        if len(pedaco) > len(melhor):
            melhor = pedaco
    saida = bytearray(len(m))
    for i in melhor:
        saida[i] = 1
    return saida


def _preencher_buracos(m, w, h):
    """O branco de dentro da peça (o placar, as letras brancas) é da peça: só o de fora é fundo."""
    fora = bytearray(len(m))
    fila = deque(i for i in range(len(m)) if not m[i] and (i % w in (0, w - 1) or i // w in (0, h - 1)))
    for i in fila:
        fora[i] = 1
    while fila:
        i = fila.popleft()
        for j in _vizinhos(i, w, h):
            if not m[j] and not fora[j]:
                fora[j] = 1
                fila.append(j)
    return bytearray(0 if fora[i] else 1 for i in range(len(m)))


def _fechar(m, w, h, raio=FECHAR):
    """Fecha os cortes finos (até 2*raio px) da peça: dilata e erode com um quadrado (as quinas retas ficam retas)."""
    if raio <= 0:
        return m
    folga = raio + 2
    img = Image.new("L", (w + 2 * folga, h + 2 * folga), 0)
    img.paste(Image.frombytes("L", (w, h), bytes(255 if v else 0 for v in m)), (folga, folga))
    lado = 2 * raio + 1
    img = img.filter(ImageFilter.MaxFilter(lado)).filter(ImageFilter.MinFilter(lado))
    dados = img.crop((folga, folga, folga + w, folga + h)).tobytes()
    return bytearray(1 if v > 127 else 0 for v in dados)


def _encolher(m, w, h):
    """Tira 1 px da borda (o contorno fica dentro da arte: no 3D não aparece o branco da folha)."""
    saida = bytearray(len(m))
    for i in range(len(m)):
        if m[i] and all(m[j] for j in _vizinhos(i, w, h)) and 0 < i % w < w - 1 and 0 < i // w < h - 1:
            saida[i] = 1
    return saida


def _caixa_da_mascara(m, w, h):
    xs = [i % w for i in range(len(m)) if m[i]]
    ys = [i // w for i in range(len(m)) if m[i]]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


# ======================================================================
# O CONTORNO: a borda dos pixels da máscara, simplificada
# ======================================================================

def _borda(m, w, h):
    """A volta de fora da máscara, pelos cantos dos pixels (sentido horário na imagem)."""
    dentro = lambda x, y: 0 <= x < w and 0 <= y < h and m[y * w + x]  # noqa: E731
    saidas = {}
    for y in range(h):
        for x in range(w):
            if not dentro(x, y):
                continue
            if not dentro(x, y - 1):
                saidas.setdefault((x, y), []).append((x + 1, y))
            if not dentro(x + 1, y):
                saidas.setdefault((x + 1, y), []).append((x + 1, y + 1))
            if not dentro(x, y + 1):
                saidas.setdefault((x + 1, y + 1), []).append((x, y + 1))
            if not dentro(x - 1, y):
                saidas.setdefault((x, y + 1), []).append((x, y))
    inicio = min(saidas, key=lambda p: (p[1], p[0]))
    volta, atual, direcao = [inicio], inicio, (1, 0)
    while True:
        opcoes = saidas[atual]
        if len(opcoes) > 1:  # dois pixels que se tocam na quina: vira para dentro (à direita) primeiro
            def giro(p):
                d = (p[0] - atual[0], p[1] - atual[1])
                return {(-direcao[1], direcao[0]): 0, direcao: 1, (direcao[1], -direcao[0]): 2}.get(d, 3)
            opcoes.sort(key=giro)
        proximo = opcoes.pop(0)
        direcao = (proximo[0] - atual[0], proximo[1] - atual[1])
        atual = proximo
        if atual == inicio:
            return volta
        volta.append(atual)


def _simplificar(pontos, tolerancia):
    """Ramer-Douglas-Peucker num polígono fechado."""
    def rdp(trecho):
        if len(trecho) < 3:
            return trecho
        (x0, y0), (x1, y1) = trecho[0], trecho[-1]
        dx, dy = x1 - x0, y1 - y0
        comprimento = math.hypot(dx, dy) or 1e-9
        pior, indice = 0.0, 0
        for k in range(1, len(trecho) - 1):
            x, y = trecho[k]
            d = abs(dy * (x - x0) - dx * (y - y0)) / comprimento
            if d > pior:
                pior, indice = d, k
        if pior <= tolerancia:
            return [trecho[0], trecho[-1]]
        return rdp(trecho[:indice + 1])[:-1] + rdp(trecho[indice:])
    # parte o polígono no ponto mais longe do primeiro
    longe = max(range(len(pontos)), key=lambda k: math.dist(pontos[0], pontos[k]))
    a = rdp(pontos[:longe + 1])
    b = rdp(pontos[longe:] + [pontos[0]])
    return a[:-1] + b[:-1]


# ======================================================================
# O RECORTE
# ======================================================================

def ler_formas(pasta):
    """O formas.json da máquina: {peça: {"px": [w, h], "contorno"?: [[u, v], ...], "dobras"?: [...]}}."""
    return json.loads((Path(pasta) / "formas.json").read_text(encoding="utf-8"))


def _casco(pontos):
    """O fecho convexo (cadeia monótona)."""
    pontos = sorted(set(pontos))
    def vira(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    baixo, cima = [], []
    for p in pontos:
        while len(baixo) >= 2 and vira(baixo[-2], baixo[-1], p) <= 0:
            baixo.pop()
        baixo.append(p)
    for p in reversed(pontos):
        while len(cima) >= 2 and vira(cima[-2], cima[-1], p) <= 0:
            cima.pop()
        cima.append(p)
    return baixo[:-1] + cima[:-1]


def _menor_retangulo(m, w, h):
    """O menor retângulo girado que contém a máscara: (centro, ângulo do lado comprido em graus, comprido, curto)."""
    borda = []
    for i in range(len(m)):
        if m[i]:
            x, y = i % w, i // w
            borda += [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
    casco = _casco(borda)
    melhor = None
    for k in range(len(casco)):
        (ax, ay), (bx, by) = casco[k], casco[(k + 1) % len(casco)]
        ang = math.atan2(by - ay, bx - ax)
        c, s = math.cos(ang), math.sin(ang)
        us = [x * c + y * s for x, y in casco]
        vs = [-x * s + y * c for x, y in casco]
        area = (max(us) - min(us)) * (max(vs) - min(vs))
        if melhor is None or area < melhor[0]:
            uc, vc = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
            centro = (uc * c - vc * s, uc * s + vc * c)
            melhor = (area, centro, ang, max(us) - min(us), max(vs) - min(vs))
    _, centro, ang, du, dv = melhor
    if dv > du:  # o lado comprido na horizontal
        ang, du, dv = ang + math.pi / 2, dv, du
    return centro, math.degrees(ang), du, dv


def recortar_peca(folha, dados, limiar=LIMIAR):
    """Uma peça da folha: (a imagem recortada, a caixa na folha, o contorno em frações ou None).

    `angulo` (a peça desenhada torta): a peça é endireitada pelo menor
    retângulo girado da máscara dela (o ângulo de verdade, achado aqui; o do
    recortes.json só escolhe o sentido, o mais perto dele) e recortada
    exatamente nele, 1 px para dentro.
    """
    x0, y0, x1, y1 = dados["caixa"]
    x0, y0 = max(0, x0 - MARGEM), max(0, y0 - MARGEM)
    x1, y1 = min(folha.width, x1 + MARGEM), min(folha.height, y1 + MARGEM)
    regiao = folha.crop((x0, y0, x1, y1))
    pintar = ImageDraw.Draw(regiao)
    for ax0, ay0, ax1, ay1 in dados.get("apagar", ()):
        pintar.rectangle([ax0 - x0, ay0 - y0, ax1 - x0 - 1, ay1 - y0 - 1], fill="white")
    w, h = regiao.size
    limiar = dados.get("limiar", limiar)
    m = _maior_pedaco(_nao_branco(regiao, limiar), w, h)
    m = _preencher_buracos(_fechar(m, w, h, dados.get("fechar", FECHAR)), w, h)
    caixa_na_folha = None
    if dados.get("angulo") is not None:
        (cx, cy), ang, comprido, curto = _menor_retangulo(m, w, h)
        # girar a imagem `ang` graus (anti-horário na tela; o y da imagem desce) deita o lado
        # comprido; dos dois sentidos, o mais perto do ângulo pedido
        giro = ang
        if abs(((giro - dados["angulo"]) + 180) % 360 - 180) > 90:
            giro += 180
        lado = int(comprido + curto) + 4
        base = Image.new("RGB", (w + 2 * lado, h + 2 * lado), "white")
        base.paste(regiao, (lado, lado))
        girada = base.rotate(giro, resample=Image.Resampling.BICUBIC, center=(cx + lado, cy + lado), fillcolor="white")
        meio_c, meio_l = comprido / 2 - 1, curto / 2 - 1
        peca = girada.crop((round(cx + lado - meio_c), round(cy + lado - meio_l), round(cx + lado + meio_c), round(cy + lado + meio_l)))
        caixa_na_folha = [x0, y0, x1, y1]
    girar = int(dados.get("girar", 0)) % 360
    if dados.get("angulo") is None:
        cx0, cy0, cx1, cy1 = _caixa_da_mascara(m, w, h)
        peca = regiao.crop((cx0, cy0, cx1, cy1))
        caixa_na_folha = [x0 + cx0, y0 + cy0, x0 + cx1, y0 + cy1]
        sub = bytearray(m[(cy0 + y) * w + cx0 + x] for y in range(cy1 - cy0) for x in range(cx1 - cx0))
    if girar:
        peca = peca.rotate(girar, expand=True)
    if dados.get("espelhar"):
        peca = peca.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    contorno = None
    if dados.get("forma", "retangulo") == "contorno":
        if girar or dados.get("espelhar") or dados.get("angulo") is not None:
            raise SystemExit("A peça com contorno não pode ser girada nem espelhada no recorte.")
        pw, ph = peca.size
        dentro = _encolher(sub, pw, ph)
        pontos = _simplificar(_borda(dentro, pw, ph), TOLERANCIA)
        contorno = [[round(x / pw, 5), round(y / ph, 5)] for x, y in pontos]
    return peca, caixa_na_folha, contorno


def recortar(pasta, argumentos=None):
    """Recorta a folha nas peças: adesivos/<peça>.png e o formas.json (ver o começo deste arquivo)."""
    pasta = Path(pasta)
    parser = argparse.ArgumentParser(description="Recorta a folha de adesivos nas peças (adesivos/<peça>.png e formas.json).")
    parser.add_argument("folha", nargs="?", help="a imagem da folha (senão, a do recortes.json)")
    parser.add_argument("--recortes", default=str(pasta / "recortes.json"), help="o arquivo com as caixas")
    parser.add_argument("--so", nargs="*", help="só estas peças")
    parser.add_argument("--previa", action="store_true", help="desenha na folha as caixas achadas e os contornos (previa-recortes.png)")
    parser.add_argument("--saida", help="a pasta das peças (padrão: adesivos/ da máquina)")
    args = parser.parse_args(argumentos)

    recortes = json.loads(Path(args.recortes).read_text(encoding="utf-8"))
    nome = Path(args.folha or recortes["folha"])
    if not nome.is_absolute() and not nome.exists():
        nome = pasta / nome  # o nome do recortes.json: na pasta da máquina
    Image.MAX_IMAGE_PIXELS = None  # a folha da gráfica pode ser enorme
    folha = Image.open(nome).convert("RGB")
    escolhidas = {k: v for k, v in recortes["pecas"].items() if not args.so or k in args.so}
    destino = Path(args.saida) if args.saida else pasta / "adesivos"
    destino.mkdir(parents=True, exist_ok=True)
    caminho_formas = (destino.parent if args.saida else pasta) / "formas.json"
    formas = json.loads(caminho_formas.read_text(encoding="utf-8")) if caminho_formas.exists() else {}
    previa = folha.copy() if args.previa else None
    desenho = ImageDraw.Draw(previa) if previa else None
    for peca, dados in escolhidas.items():
        imagem, caixa, contorno = recortar_peca(folha, dados)
        imagem.save(destino / f"{peca}.png", optimize=True)
        forma = {"px": list(imagem.size), "caixa": caixa}
        if contorno:
            forma["contorno"] = contorno
        if dados.get("dobras"):
            forma["dobras"] = dados["dobras"]
        formas[peca] = forma
        print(f"{peca}: {imagem.width} x {imagem.height} px" + (f", contorno com {len(contorno)} pontos" if contorno else ""))
        if desenho:
            desenho.rectangle(caixa, outline="#ff2bd6", width=2)
            if contorno and not (dados.get("angulo") or dados.get("girar")):
                x0, y0 = caixa[0], caixa[1]
                desenho.line([(x0 + u * imagem.width, y0 + v * imagem.height) for u, v in contorno + contorno[:1]],
                             fill="#00c853", width=1)
            try:
                letra = ImageFont.truetype("DejaVuSans-Bold.ttf", 12)
            except OSError:
                letra = ImageFont.load_default()
            desenho.text((caixa[0] + 3, caixa[1] + 2), peca, font=letra, fill="#ff2bd6", stroke_width=2, stroke_fill="white")
    caminho_formas.write_text(json.dumps(formas, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if previa:
        previa.save(pasta / "previa-recortes.png")
        print("prévia:", pasta / "previa-recortes.png")
    print("Pronto. Agora refaça o 3D: node gerar.cjs glb fotos (e o gltfpack; ver o README).")
