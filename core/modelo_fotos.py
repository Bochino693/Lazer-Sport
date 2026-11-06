"""Fotos + medidas -> objeto 3D (.glb), sem programa de 3D.

A equipe tem as fotos (ou as imagens do projeto) e as medidas; o site precisa
do .glb. Aqui as fotos viram o objeto, de dois jeitos:

  PAINÉIS ("sprites" 2D com processamento): cada foto, recortada do fundo,
    vira um painel no lugar dela -- a frente na frente, o lado direito à
    direita, as costas atrás, o lado esquerdo à esquerda e a de cima em cima
    --, todos na medida real. De frente (e de cada lado) é a foto exata; nas
    diagonais se veem dois painéis em quina, e o meio é vazio.

  VOLUME: o contorno de cada foto recorta um bloco do tamanho do brinquedo
    (o que a frente não tem, sai; o que o lado não tem, sai; o mesmo com
    as costas, o outro lado e a de cima) e cada face do sólido que sobra
    ganha a foto da vista dela. De qualquer ângulo é um sólido, com o
    contorno certo; o que é vazado e não aparece no contorno (rede, tubo por
    dentro, o vão entre as torres visto de frente) fica cheio, e não se
    anda por dentro.

O recorte do fundo funciona com fundo limpo (parede lisa, céu, fundo de
estúdio, render com fundo branco): ele "escorre" das bordas da foto pelos
pixels parecidos. PNG que já vem recortado (com transparência) é usado como
está. Sem numpy (o servidor não tem): Pillow e Python puro.
"""

from __future__ import annotations

import io
from array import array
from collections import deque

from PIL import Image, ImageFilter, ImageOps, ImageStat

from .glb_montar import Cena, preparar_foto, tem_transparencia

VISTAS = ("frente", "direita", "costas", "esquerda", "cima")
NOMES_DAS_VISTAS = {
    "frente": "Frente",
    "direita": "Lado direito",
    "costas": "Costas",
    "esquerda": "Lado esquerdo",
    "cima": "De cima",
}
MODOS = ("paineis", "volume")

#: O lado maior da foto que se analisa (o recorte); a foto que vai no objeto é maior.
_LADO_DO_RECORTE = 320
#: Quantas fatias o volume tem no lado maior do brinquedo (3 cm num de 4 m).
_RESOLUCAO_DO_VOLUME = 128


class ErroDasFotos(ValueError):
    """Faltou algo (a frente, as medidas) ou uma foto não abre."""


# ----------------------------------------------------------------------
# O RECORTE DO FUNDO
# ----------------------------------------------------------------------

def abrir_foto(dados):
    try:
        imagem = Image.open(io.BytesIO(dados) if isinstance(dados, (bytes, bytearray)) else dados)
        imagem.load()
    except Exception as exc:  # noqa: BLE001 -- o Pillow levanta de vários tipos
        raise ErroDasFotos("Uma das fotos não abriu (envie JPG, PNG ou WEBP).") from exc
    imagem = ImageOps.exif_transpose(imagem)
    if max(imagem.size) > 2400:
        imagem.thumbnail((2400, 2400), Image.LANCZOS)
    return imagem


def _distancia(a, b, i, j):
    return abs(a[i] - b[j]) + abs(a[i + 1] - b[j + 1]) + abs(a[i + 2] - b[j + 2])


def mascara_do_objeto(imagem, local=26, total=110):
    """A máscara (L, 255 = objeto) do que NÃO é o fundo, e a fração da foto que é objeto.

    O fundo "escorre" de todas as bordas da foto: um pixel vizinho entra no
    fundo se for parecido com o pixel de onde veio (`local`, para seguir um
    degradê de céu ou de estúdio) e não muito longe da cor da borda de onde
    partiu (`total`, para não atravessar a quina macia do objeto). O que o
    fundo não alcança é o objeto; pedacinhos soltos (menos de 0,4% da foto)
    voltam para o fundo.
    """
    pequena = imagem.convert("RGB")
    pequena.thumbnail((_LADO_DO_RECORTE, _LADO_DO_RECORTE), Image.BILINEAR)
    pequena = pequena.filter(ImageFilter.BoxBlur(1))
    w, h = pequena.size
    px = pequena.tobytes()
    n = w * h
    fundo = bytearray(n)
    semente = array("i", [0]) * n
    fila = deque()
    for x in range(w):
        for y in (0, h - 1):
            k = y * w + x
            if not fundo[k]:
                fundo[k] = 1
                semente[k] = k
                fila.append(k)
    for y in range(h):
        for x in (0, w - 1):
            k = y * w + x
            if not fundo[k]:
                fundo[k] = 1
                semente[k] = k
                fila.append(k)
    while fila:
        k = fila.popleft()
        x, y = k % w, k // w
        origem = semente[k]
        for v in (k - 1 if x else -1, k + 1 if x < w - 1 else -1, k - w if y else -1, k + w if y < h - 1 else -1):
            if v < 0 or fundo[v]:
                continue
            if _distancia(px, px, v * 3, k * 3) <= local and _distancia(px, px, v * 3, origem * 3) <= total:
                fundo[v] = 1
                semente[v] = origem
                fila.append(v)

    # pedacinhos soltos do objeto (poeira, reflexo) voltam para o fundo
    rotulo = bytearray(n)
    minimo = max(12, int(n * 0.004))
    for inicio in range(n):
        if fundo[inicio] or rotulo[inicio]:
            continue
        pedaco = [inicio]
        rotulo[inicio] = 1
        i = 0
        while i < len(pedaco):
            k = pedaco[i]
            i += 1
            x, y = k % w, k // w
            for v in (k - 1 if x else -1, k + 1 if x < w - 1 else -1, k - w if y else -1, k + w if y < h - 1 else -1):
                if v >= 0 and not fundo[v] and not rotulo[v]:
                    rotulo[v] = 1
                    pedaco.append(v)
        if len(pedaco) < minimo:
            for k in pedaco:
                fundo[k] = 1
    objeto = bytes(0 if f else 255 for f in fundo)
    fracao = objeto.count(255) / n
    mascara = Image.frombytes("L", (w, h), objeto)
    return mascara, fracao


def recortar(imagem, recortar_fundo=True):
    """(foto RGBA recortada e enquadrada no objeto, aviso ou "").

    A foto sai cortada na caixa do objeto: as bordas dela são as bordas do
    brinquedo, e é isso que se casa com as medidas.
    """
    aviso = ""
    if tem_transparencia(imagem):
        rgba = imagem.convert("RGBA")
        alfa = rgba.getchannel("A")
    elif recortar_fundo:
        mascara, fracao = mascara_do_objeto(imagem)
        rgba = imagem.convert("RGBA")
        if fracao < 0.03 or fracao > 0.985:
            aviso = "o fundo não se separou do objeto (fundo cheio de coisas?): a foto foi usada inteira"
            alfa = Image.new("L", rgba.size, 255)
        else:
            alfa = mascara.resize(rgba.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(max(0.6, rgba.width / 900)))
            alfa = alfa.point(lambda v: 0 if v < 70 else 255 if v > 185 else (v - 70) * 255 // 115)
    else:
        rgba = imagem.convert("RGBA")
        alfa = Image.new("L", rgba.size, 255)
    rgba.putalpha(alfa)
    caixa = alfa.point(lambda v: 255 if v >= 128 else 0).getbbox()
    if caixa:
        rgba = rgba.crop(caixa)
    return rgba, aviso


def sem_fundo(rgba):
    """A foto para o VOLUME: o fundo vira a cor média do objeto (as quinas não ficam brancas)."""
    alfa = rgba.getchannel("A")
    binaria = alfa.point(lambda v: 255 if v >= 128 else 0)
    try:
        media = tuple(int(c) for c in ImageStat.Stat(rgba.convert("RGB"), mask=binaria).mean[:3])
    except ZeroDivisionError:
        media = (200, 200, 200)
    fundo = Image.new("RGB", rgba.size, media)
    fundo.paste(rgba.convert("RGB"), mask=alfa)
    return fundo, media


# ----------------------------------------------------------------------
# AS MEDIDAS
# ----------------------------------------------------------------------

def medidas_finais(fotos, informadas):
    """Largura, profundidade e altura (m): as informadas, e o que falta sai da proporção das fotos."""
    def numero(chave):
        try:
            valor = float(str(informadas.get(chave) or "").replace(",", "."))
        except ValueError:
            return None
        return valor if 0.05 <= valor <= 200 else None

    largura, profundidade, altura = numero("largura"), numero("profundidade"), numero("altura")
    avisos = []
    frente = fotos["frente"]
    aspecto_frente = frente.width / max(1, frente.height)
    lado = fotos.get("direita") or fotos.get("esquerda")
    aspecto_lado = lado.width / max(1, lado.height) if lado else None
    if altura is None:
        if largura:
            altura = largura / aspecto_frente
        elif profundidade and aspecto_lado:
            altura = profundidade / aspecto_lado
        else:
            altura = 2.0
            avisos.append("sem medida nenhuma: o objeto ficou com 2 m de altura (informe a altura real)")
    if largura is None:
        largura = altura * aspecto_frente
    if profundidade is None:
        if aspecto_lado:
            profundidade = altura * aspecto_lado
        else:
            profundidade = min(largura, altura) * 0.6
            avisos.append("sem foto do lado nem profundidade: a profundidade foi estimada")
    return round(largura, 3), round(profundidade, 3), round(altura, 3), avisos


# ----------------------------------------------------------------------
# AS FACES
# ----------------------------------------------------------------------

class _Partes:
    """Quadrados (dois triângulos cada) agrupados por material."""

    def __init__(self):
        self.partes = {}

    def quadrado(self, material, cantos, normal, uvs):
        a, b, c = cantos[0], cantos[1], cantos[2]
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        if nx * normal[0] + ny * normal[1] + nz * normal[2] < 0:
            cantos = cantos[::-1]
            uvs = uvs[::-1]
        parte = self.partes.setdefault(material, {"posicoes": [], "normais": [], "uvs": [], "indices": [], "material": material})
        base = len(parte["posicoes"]) // 3
        for canto, uv in zip(cantos, uvs):
            parte["posicoes"].extend(canto)
            parte["normais"].extend(normal)
            parte["uvs"].extend((min(1.0, max(0.0, uv[0])), min(1.0, max(0.0, uv[1]))))
        parte["indices"].extend((base, base + 1, base + 2, base, base + 2, base + 3))

    def lista(self):
        return [p for p in self.partes.values() if p["indices"]]


def _retangulos(linhas):
    """Junta os bits ligados de cada linha em retângulos (a "malha gulosa").

    `linhas`: inteiros (um bit por coluna). Sai (coluna0, coluna1, linha0, linha1),
    fim aberto. Menos faces = arquivo menor e mais leve de desenhar.
    """
    linhas = list(linhas)
    for r in range(len(linhas)):
        while linhas[r]:
            m = linhas[r]
            a = (m & -m).bit_length() - 1
            resto = ~(m >> a)
            b = a + (resto & -resto).bit_length() - 1
            corrida = ((1 << (b - a)) - 1) << a
            r1 = r + 1
            while r1 < len(linhas) and linhas[r1] & corrida == corrida:
                linhas[r1] &= ~corrida
                r1 += 1
            linhas[r] &= ~corrida
            yield a, b, r, r1


def _bits_das_colunas(mascara, colunas, linhas, espelhar=False):
    """A máscara reduzida a colunas x linhas -> um inteiro por linha (de baixo para cima)."""
    pequena = mascara.resize((colunas, linhas), Image.BOX).point(lambda v: 255 if v >= 110 else 0)
    dados = pequena.tobytes()
    saida = []
    for linha in range(linhas - 1, -1, -1):  # a linha 0 da imagem é a de cima
        bits = 0
        inicio = linha * colunas
        for c in range(colunas):
            if dados[inicio + c]:
                bits |= 1 << ((colunas - 1 - c) if espelhar else c)
        saida.append(bits)
    return saida


# ----------------------------------------------------------------------
# OS DOIS JEITOS
# ----------------------------------------------------------------------

def _paineis(cena, fotos, w, d, h):
    """Cada foto recortada vira um painel no lugar da vista dela, na medida real."""
    partes = _Partes()
    mx, mz = w / 2, d / 2
    tem_lado = bool(fotos.get("direita") or fotos.get("esquerda"))
    if not tem_lado:
        mz = 0.004  # só a frente: um painel recortado ("totem"), sem volume
    materiais = {}

    def material(vista):
        if vista not in materiais:
            dados, tipo = preparar_foto(fotos[vista], 1024 if vista in ("frente", "costas") else 896)
            # face única: de fora se vê cada painel; por dentro ele some (com as duas
            # faces, o painel do fundo aparecia pelos vãos e o objeto virava um cercado)
            materiais[vista] = cena.material(NOMES_DAS_VISTAS[vista], textura=cena.foto(dados, tipo), alfa="MASK", aspereza=0.9)
        return materiais[vista]

    costas = "costas" if fotos.get("costas") else None
    if costas is None:
        fotos["costas"] = ImageOps.mirror(fotos["frente"])
        costas = "costas"
    # frente (z+) e costas (z-): u corre da esquerda para a direita de quem olha
    partes.quadrado(material("frente"), [(-mx, 0, mz), (mx, 0, mz), (mx, h, mz), (-mx, h, mz)], (0, 0, 1),
                    [(0, 1), (1, 1), (1, 0), (0, 0)])
    partes.quadrado(material(costas), [(mx, 0, -mz), (-mx, 0, -mz), (-mx, h, -mz), (mx, h, -mz)], (0, 0, -1),
                    [(0, 1), (1, 1), (1, 0), (0, 0)])
    if tem_lado:
        if not fotos.get("direita"):
            fotos["direita"] = ImageOps.mirror(fotos["esquerda"])
        if not fotos.get("esquerda"):
            fotos["esquerda"] = ImageOps.mirror(fotos["direita"])
        partes.quadrado(material("direita"), [(mx, 0, mz), (mx, 0, -mz), (mx, h, -mz), (mx, h, mz)], (1, 0, 0),
                        [(0, 1), (1, 1), (1, 0), (0, 0)])
        partes.quadrado(material("esquerda"), [(-mx, 0, -mz), (-mx, 0, mz), (-mx, h, mz), (-mx, h, -mz)], (-1, 0, 0),
                        [(0, 1), (1, 1), (1, 0), (0, 0)])
    if fotos.get("cima") and tem_lado:
        # a foto de cima com a frente para baixo na imagem
        partes.quadrado(material("cima"), [(-mx, h, mz), (mx, h, mz), (mx, h, -mz), (-mx, h, -mz)], (0, 1, 0),
                        [(0, 1), (1, 1), (1, 0), (0, 0)])
    return partes.lista()


def _volume(cena, fotos, w, d, h):
    """O bloco recortado pelos contornos de todas as vistas, com a foto de cada vista na face dela."""
    passo = max(w, d, h) / _RESOLUCAO_DO_VOLUME
    nx, ny, nz = (max(2, round(v / passo)) for v in (w, h, d))
    cx, cy, cz = w / nx, h / ny, d / nz
    cheio_x = (1 << nx) - 1

    def contorno(vista, colunas, espelhar=False):
        return _bits_das_colunas(fotos[vista].getchannel("A"), colunas, ny, espelhar)

    frente = contorno("frente", nx)
    if fotos.get("costas"):
        # nas costas, a esquerda da foto é o lado direito do brinquedo
        frente = [a & b for a, b in zip(frente, contorno("costas", nx, espelhar=True))]
    # o lado: bit k = profundidade k (de trás, z-, para a frente, z+)
    lado = None
    if fotos.get("direita"):
        lado = contorno("direita", nz, espelhar=True)
    if fotos.get("esquerda"):
        esquerda = contorno("esquerda", nz)
        lado = esquerda if lado is None else [a & b for a, b in zip(lado, esquerda)]
    if lado is None:
        lado = [(1 << nz) - 1] * ny
    cima = None
    if fotos.get("cima"):
        # a foto de cima com a frente para baixo: a linha de cima da imagem é o fundo (z-)
        pequena = fotos["cima"].getchannel("A").resize((nx, nz), Image.BOX).point(lambda v: 255 if v >= 110 else 0).tobytes()
        cima = []
        for k in range(nz):
            bits = 0
            for c in range(nx):
                if pequena[k * nx + c]:
                    bits |= 1 << c
            cima.append(bits)

    # a ocupação: fatias[j][k] = bits em x
    fatias = []
    for j in range(ny):
        linha = []
        for k in range(nz):
            bits = frente[j] if (lado[j] >> k) & 1 else 0
            if cima is not None:
                bits &= cima[k]
            linha.append(bits)
        fatias.append(linha)

    # as fotos de cada face (sem transparência: o volume é sólido)
    texturas = {}
    medias = {}
    for vista in VISTAS:
        if fotos.get(vista):
            imagem, media = sem_fundo(fotos[vista])
            dados, tipo = preparar_foto(imagem, 1024 if vista in ("frente", "costas") else 768)
            texturas[vista] = cena.material(NOMES_DAS_VISTAS[vista], textura=cena.foto(dados, tipo), aspereza=0.88)
            medias[vista] = media
    if not (fotos.get("direita") or fotos.get("esquerda")):
        r, g, b = medias["frente"]
        texturas["lateral"] = cena.material("Lateral", cor=(r / 255 * 0.85, g / 255 * 0.85, b / 255 * 0.85, 1.0), aspereza=0.9)
    if "cima" not in texturas:
        # sem a foto de cima, o topo é liso, na cor do alto da frente (projetar a
        # frente para cima dava listras)
        frente_rgba = fotos["frente"]
        faixa = frente_rgba.crop((0, 0, frente_rgba.width, max(1, frente_rgba.height // 8)))
        _imagem, (r, g, b) = sem_fundo(faixa)
        texturas["topo"] = cena.material("Topo", cor=(min(1, r / 255 * 1.04), min(1, g / 255 * 1.04), min(1, b / 255 * 1.04), 1.0), aspereza=0.9)

    partes = _Partes()
    x0, z0 = -w / 2, -d / 2

    def uv_frente(x, y):
        return ((x - x0) / w, 1 - y / h)

    def uv_costas(x, y):
        return ((w / 2 - x) / w, 1 - y / h)

    def uv_direita(z, y):
        return ((d / 2 - z) / d, 1 - y / h)

    def uv_esquerda(z, y):
        return ((z - z0) / d, 1 - y / h)

    # frente/costas: planos z, retângulos em (x, y)
    for k in range(nz):
        for sentido in (1, -1):
            vizinho = k + sentido
            linhas = []
            for j in range(ny):
                atual = fatias[j][k]
                outro = fatias[j][vizinho] if 0 <= vizinho < nz else 0
                linhas.append(atual & ~outro)
            z = z0 + (k + (1 if sentido > 0 else 0)) * cz
            if sentido > 0:
                mat, uv = texturas["frente"], uv_frente
            elif "costas" in texturas:
                mat, uv = texturas["costas"], uv_costas
            else:
                mat, uv = texturas["frente"], uv_frente  # a frente vista por trás
            for a, b, r0, r1 in _retangulos(linhas):
                xa, xb, ya, yb = x0 + a * cx, x0 + b * cx, r0 * cy, r1 * cy
                cantos = [(xa, ya, z), (xb, ya, z), (xb, yb, z), (xa, yb, z)]
                partes.quadrado(mat, cantos, (0, 0, sentido), [uv(c[0], c[1]) for c in cantos])

    # os lados: planos x, retângulos em (z, y)
    planos = {}
    for j in range(ny):
        for k in range(nz):
            linha = fatias[j][k]
            if not linha:
                continue
            for sentido, expostos in ((1, linha & ~(linha >> 1)), (-1, linha & ~((linha << 1) & cheio_x))):
                while expostos:
                    bit = expostos & -expostos
                    i = bit.bit_length() - 1
                    expostos ^= bit
                    plano = planos.setdefault((i, sentido), [0] * ny)
                    plano[j] |= 1 << k
    for (i, sentido), linhas in planos.items():
        x = x0 + (i + (1 if sentido > 0 else 0)) * cx
        if sentido > 0:
            mat, uv = (texturas["direita"], uv_direita) if "direita" in texturas else (
                (texturas["esquerda"], uv_esquerda) if "esquerda" in texturas else (texturas["lateral"], uv_direita))
        else:
            mat, uv = (texturas["esquerda"], uv_esquerda) if "esquerda" in texturas else (
                (texturas["direita"], uv_direita) if "direita" in texturas else (texturas["lateral"], uv_esquerda))
        for a, b, r0, r1 in _retangulos(linhas):
            za, zb, ya, yb = z0 + a * cz, z0 + b * cz, r0 * cy, r1 * cy
            cantos = [(x, ya, za), (x, ya, zb), (x, yb, zb), (x, yb, za)]
            partes.quadrado(mat, cantos, (sentido, 0, 0), [uv(c[2], c[1]) for c in cantos])

    # em cima e embaixo: planos y, retângulos em (x, z)
    for j in range(ny):
        for sentido in (1, -1):
            vizinho = j + sentido
            linhas = [fatias[j][k] & ~(fatias[vizinho][k] if 0 <= vizinho < ny else 0) for k in range(nz)]
            y = (j + (1 if sentido > 0 else 0)) * cy
            for a, b, r0, r1 in _retangulos(linhas):
                xa, xb, za, zb = x0 + a * cx, x0 + b * cx, z0 + r0 * cz, z0 + r1 * cz
                cantos = [(xa, y, za), (xb, y, za), (xb, y, zb), (xa, y, zb)]
                if "cima" in texturas:
                    uvs = [((c[0] - x0) / w, (c[2] - z0) / d) for c in cantos]
                    mat = texturas["cima"]
                else:
                    uvs = [(0.5, 0.5)] * 4
                    mat = texturas["topo"]
                partes.quadrado(mat, cantos, (0, sentido, 0), uvs)
    return partes.lista()


def gerar(fotos_brutas, medidas=None, modo="paineis", recortar_fundo=True):
    """(bytes do .glb, info) a partir das fotos {vista: bytes ou imagem} e das medidas.

    A frente é obrigatória; o resto melhora o resultado. `medidas`:
    {"largura", "profundidade", "altura"} em metros (o que faltar sai da
    proporção das fotos).
    """
    if modo not in MODOS:
        raise ErroDasFotos("Escolha Painéis ou Volume.")
    if not fotos_brutas.get("frente"):
        raise ErroDasFotos("A foto da FRENTE é obrigatória (as outras melhoram o objeto).")
    fotos, avisos = {}, []
    for vista in VISTAS:
        bruta = fotos_brutas.get(vista)
        if bruta is None:
            continue
        imagem = bruta if isinstance(bruta, Image.Image) else abrir_foto(bruta)
        recortada, aviso = recortar(imagem, recortar_fundo)
        if aviso:
            avisos.append(f"{NOMES_DAS_VISTAS[vista]}: {aviso}")
        fotos[vista] = recortada
    w, d, h, avisos_medidas = medidas_finais(fotos, medidas or {})
    avisos.extend(avisos_medidas)
    for vista, par in (("costas", "frente"), ("esquerda", "direita"), ("direita", "esquerda")):
        if vista not in fotos and par in fotos and vista != "costas":
            avisos.append(f"{NOMES_DAS_VISTAS[vista]}: sem foto, foi espelhado do {NOMES_DAS_VISTAS[par].lower()}")
    if "costas" not in fotos:
        avisos.append("Costas: sem foto, ficou a frente espelhada")
    if modo == "paineis" and not (fotos.get("direita") or fotos.get("esquerda")):
        avisos.append("só a frente: o objeto ficou um painel recortado; mande um lado para ganhar volume")

    cena = Cena()
    vistas_usadas = [v for v in VISTAS if v in fotos]
    partes = (_paineis if modo == "paineis" else _volume)(cena, dict(fotos), w, d, h)
    malha = cena.malha("objeto", partes)
    cena.no("objeto", malha)
    glb = cena.glb({"origem": "fotos", "modo": modo, "vistas": vistas_usadas})
    return glb, {
        "modo": modo,
        "medidas": [round(h, 2), round(w, 2), round(d, 2)],
        "vistas": vistas_usadas,
        "avisos": avisos,
        "tamanho": len(glb),
        "faces": sum(len(p["indices"]) // 6 for p in partes),
    }
