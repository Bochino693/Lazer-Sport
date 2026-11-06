"""Monta um .glb (glTF 2.0 binário) do zero, em Python puro, e mexe em um pronto.

POR QUE ISTO EXISTE. O painel cria objetos 3D de três jeitos -- pelas fotos
e medidas, pelas fotos de um projeto, ou convertendo um arquivo de outro
programa (.obj, .stl, .3ds, .dae, .gltf) -- e o site só abre .glb. Aqui
mora o que os três têm em comum: escrever o .glb (malhas, materiais e
fotos dentro de um arquivo só), encaixar o objeto no chão e no centro, na
escala certa, e encolher as fotos de dentro quando o arquivo passa do
limite do armazenamento (core/objetos_3d.TAMANHO_MAXIMO).

Sem numpy (o servidor não tem): os números vão direto para `struct`.
"""

from __future__ import annotations

import io
import json
import math
import struct

from PIL import Image, ImageOps

#: A maior foto que vai dentro do objeto (o lado maior, em pixels). Acima
#: disto o arquivo engorda e a placa de vídeo do celular reduz de qualquer jeito.
FOTO_MAXIMA = 1024

_FLOAT, _UINT16, _UINT32 = 5126, 5123, 5125
_ARRAY, _ELEMENTOS = 34962, 34963


# ----------------------------------------------------------------------
# AS FOTOS DE DENTRO DO OBJETO
# ----------------------------------------------------------------------

def tem_transparencia(imagem):
    """A imagem tem algum pixel vazado (o recorte)?"""
    if imagem.mode not in ("RGBA", "LA", "PA"):
        return False
    menor, _maior = imagem.getchannel("A").getextrema()
    return menor < 250


def preparar_foto(imagem, maximo=FOTO_MAXIMA, qualidade=86):
    """(bytes, tipo) da foto pronta para ir dentro do .glb.

    Com recorte (pixels vazados) vai em PNG; sem, em JPEG, bem menor. O lado
    maior fica em `maximo` pixels.
    """
    if isinstance(imagem, (bytes, bytearray)):
        imagem = Image.open(io.BytesIO(imagem))
        imagem.load()
    imagem = ImageOps.exif_transpose(imagem) if hasattr(imagem, "getexif") else imagem
    if imagem.mode == "P":
        imagem = imagem.convert("RGBA")
    if max(imagem.size) > maximo:
        escala = maximo / max(imagem.size)
        imagem = imagem.resize((max(1, round(imagem.width * escala)), max(1, round(imagem.height * escala))), Image.LANCZOS)
    saida = io.BytesIO()
    if tem_transparencia(imagem):
        imagem.convert("RGBA").save(saida, "PNG", optimize=True)
        return saida.getvalue(), "image/png"
    imagem.convert("RGB").save(saida, "JPEG", quality=qualidade, optimize=True, progressive=False)
    return saida.getvalue(), "image/jpeg"


# ----------------------------------------------------------------------
# ESCREVER UM .GLB
# ----------------------------------------------------------------------

class Cena:
    """Um objeto 3D em construção: materiais, malhas e nós; `glb()` escreve o arquivo."""

    def __init__(self, gerador="Lazer & Sport"):
        self.bin = bytearray()
        self.gltf = {
            "asset": {"version": "2.0", "generator": gerador},
            "scene": 0,
            "scenes": [{"nodes": []}],
            "nodes": [],
            "meshes": [],
            "materials": [],
            "accessors": [],
            "bufferViews": [],
            "textures": [],
            "images": [],
            "samplers": [],
        }
        self._amostradores = {}
        self._desquantizar = {}  # malha -> a posição e a escala que desfazem a quantização
        self._quantizado = False

    # -- os blocos binários
    def _bloco(self, dados, alvo=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        vista = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(dados)}
        if alvo:
            vista["target"] = alvo
        self.bin += dados
        self.gltf["bufferViews"].append(vista)
        return len(self.gltf["bufferViews"]) - 1

    def _acessor(self, valores, tipo, largura):
        """Floats agrupados de `largura` em `largura` (VEC2, VEC3)."""
        n = len(valores) // largura
        acessor = {
            "bufferView": self._bloco(struct.pack(f"<{len(valores)}f", *valores), _ARRAY),
            "componentType": _FLOAT,
            "count": n,
            "type": tipo,
        }
        if tipo == "VEC3":
            acessor["min"] = [min(valores[i::3]) for i in range(3)]
            acessor["max"] = [max(valores[i::3]) for i in range(3)]
        self.gltf["accessors"].append(acessor)
        return len(self.gltf["accessors"]) - 1

    def _indices(self, indices, vertices):
        if vertices <= 65535:
            dados, tipo = struct.pack(f"<{len(indices)}H", *indices), _UINT16
        else:
            dados, tipo = struct.pack(f"<{len(indices)}I", *indices), _UINT32
        self.gltf["accessors"].append({
            "bufferView": self._bloco(dados, _ELEMENTOS),
            "componentType": tipo,
            "count": len(indices),
            "type": "SCALAR",
        })
        return len(self.gltf["accessors"]) - 1

    def _inteiros(self, valores, tipo, largura, formato, componente, passo=None, min_max=False):
        """Inteiros "normalizados" (KHR_mesh_quantization): metade ou um quarto do tamanho."""
        n = len(valores) // largura
        if passo:
            # cada vértice ocupa `passo` bytes (o glTF pede múltiplo de 4)
            sobra = passo - struct.calcsize("<" + formato * largura)
            dados = b"".join(
                struct.pack("<" + formato * largura, *valores[i:i + largura]) + b"\0" * sobra
                for i in range(0, len(valores), largura)
            )
        else:
            dados = struct.pack(f"<{len(valores)}{formato}", *valores)
        vista = self._bloco(dados, _ARRAY)
        if passo:
            self.gltf["bufferViews"][vista]["byteStride"] = passo
        acessor = {"bufferView": vista, "componentType": componente, "normalized": True, "count": n, "type": tipo}
        if min_max:
            acessor["min"] = [min(valores[i::largura]) for i in range(largura)]
            acessor["max"] = [max(valores[i::largura]) for i in range(largura)]
        self.gltf["accessors"].append(acessor)
        self._quantizado = True
        return len(self.gltf["accessors"]) - 1

    # -- o que vai dentro
    def foto(self, dados, tipo, repetir=False):
        """Uma foto (bytes já prontos: ver `preparar_foto`) -> índice da textura.

        `repetir`: a textura se repete (madeira, grama de um arquivo 3D); as
        fotos do objeto montado não se repetem (presas na borda).
        """
        self.gltf["images"].append({"bufferView": self._bloco(dados), "mimeType": tipo})
        modo = 10497 if repetir else 33071
        if modo not in self._amostradores:
            self.gltf["samplers"].append({"magFilter": 9729, "minFilter": 9987, "wrapS": modo, "wrapT": modo})
            self._amostradores[modo] = len(self.gltf["samplers"]) - 1
        self.gltf["textures"].append({"source": len(self.gltf["images"]) - 1, "sampler": self._amostradores[modo]})
        return len(self.gltf["textures"]) - 1

    def material(self, nome, cor=(1.0, 1.0, 1.0, 1.0), textura=None, alfa="OPAQUE", dois_lados=False,
                 aspereza=0.82, metal=0.0, corte=0.5):
        pbr = {"baseColorFactor": [round(float(c), 4) for c in cor], "metallicFactor": metal, "roughnessFactor": aspereza}
        if textura is not None:
            pbr["baseColorTexture"] = {"index": textura}
        material = {"name": nome[:60], "pbrMetallicRoughness": pbr}
        if alfa != "OPAQUE":
            material["alphaMode"] = alfa
            if alfa == "MASK":
                material["alphaCutoff"] = corte
        if dois_lados:
            material["doubleSided"] = True
        self.gltf["materials"].append(material)
        return len(self.gltf["materials"]) - 1

    def malha(self, nome, partes, quantizar=True):
        """`partes`: [{"posicoes", "normais", "uvs" (opcional), "indices", "material"}].

        `quantizar`: as posições vão em inteiros de 16 bits (com a escala no
        nó: precisão de décimos de milímetro num brinquedo de 6 m), as
        normais em 8 bits e as UVs em 16 -- o arquivo cai para perto da
        metade. Parte com mais de 65 535 vértices é dividida (índices de 16 bits).
        """
        partes = [pedaco for parte in partes if parte["indices"] for pedaco in _partir(parte)]
        if not partes:
            return None
        desquantizar = None
        if quantizar:
            baixo = [min(min(p["posicoes"][i::3]) for p in partes) for i in range(3)]
            alto = [max(max(p["posicoes"][i::3]) for p in partes) for i in range(3)]
            centro = [(baixo[i] + alto[i]) / 2 for i in range(3)]
            meia = max((alto[i] - baixo[i]) / 2 for i in range(3)) or 1.0
            desquantizar = {"translation": [round(c, 6) for c in centro], "scale": [meia, meia, meia]}
        primitivas = []
        for parte in partes:
            vertices = len(parte["posicoes"]) // 3
            if quantizar:
                pos = parte["posicoes"]
                q = [max(-32767, min(32767, round((pos[i] - centro[i % 3]) / meia * 32767))) for i in range(len(pos))]
                nor = [max(-127, min(127, round(v * 127))) for v in parte["normais"]]
                atributos = {
                    "POSITION": self._inteiros(q, "VEC3", 3, "h", 5122, passo=8, min_max=True),
                    "NORMAL": self._inteiros(nor, "VEC3", 3, "b", 5120, passo=4),
                }
                uvs = parte.get("uvs")
                if uvs:
                    if min(uvs) >= 0.0 and max(uvs) <= 1.0:
                        atributos["TEXCOORD_0"] = self._inteiros([round(v * 65535) for v in uvs], "VEC2", 2, "H", 5123)
                    else:  # textura que se repete (madeira, grama): fica em float
                        atributos["TEXCOORD_0"] = self._acessor(uvs, "VEC2", 2)
            else:
                atributos = {
                    "POSITION": self._acessor(parte["posicoes"], "VEC3", 3),
                    "NORMAL": self._acessor(parte["normais"], "VEC3", 3),
                }
                if parte.get("uvs"):
                    atributos["TEXCOORD_0"] = self._acessor(parte["uvs"], "VEC2", 2)
            primitiva = {"attributes": atributos, "indices": self._indices(parte["indices"], vertices), "mode": 4}
            if parte.get("material") is not None:
                primitiva["material"] = parte["material"]
            primitivas.append(primitiva)
        self.gltf["meshes"].append({"name": nome[:60], "primitives": primitivas})
        indice = len(self.gltf["meshes"]) - 1
        if desquantizar:
            self._desquantizar[indice] = desquantizar
        return indice

    def no(self, nome, malha=None, raiz=True, **transformacao):
        no = {"name": nome[:60]}
        transformacao = {k: v for k, v in transformacao.items() if v is not None}
        volta = self._desquantizar.get(malha) if malha is not None else None
        if malha is not None and volta and transformacao:
            # o nó já tem posição própria: a malha vai num filho com a escala dela
            self.gltf["nodes"].append({"name": nome[:60] + " (malha)", "mesh": malha, **volta})
            no["children"] = [len(self.gltf["nodes"]) - 1]
        elif malha is not None:
            no["mesh"] = malha
            transformacao = volta or {}
        no.update(transformacao)
        self.gltf["nodes"].append(no)
        indice = len(self.gltf["nodes"]) - 1
        if raiz:
            self.gltf["scenes"][0]["nodes"].append(indice)
        return indice

    def glb(self, extras=None):
        gltf = {k: v for k, v in self.gltf.items() if v != []}
        if self._quantizado:
            gltf["extensionsUsed"] = ["KHR_mesh_quantization"]
            gltf["extensionsRequired"] = ["KHR_mesh_quantization"]
        if extras:
            gltf["asset"]["extras"] = extras
        return escrever_glb(gltf, bytes(self.bin))


def _partir(parte, teto=65535):
    """A parte com mais de `teto` vértices vira várias (cada uma com índices de 16 bits)."""
    if len(parte["posicoes"]) // 3 <= teto:
        return [parte]
    pedacos = []
    atual = None
    indices = parte["indices"]
    for t in range(0, len(indices), 3):
        if atual is None or len(atual["mapa"]) > teto - 3:
            atual = {"mapa": {}, "posicoes": [], "normais": [], "uvs": [] if parte.get("uvs") else None,
                     "indices": [], "material": parte.get("material")}
            pedacos.append(atual)
        for antigo in indices[t:t + 3]:
            novo = atual["mapa"].get(antigo)
            if novo is None:
                novo = len(atual["mapa"])
                atual["mapa"][antigo] = novo
                atual["posicoes"].extend(parte["posicoes"][antigo * 3:antigo * 3 + 3])
                atual["normais"].extend(parte["normais"][antigo * 3:antigo * 3 + 3])
                if atual["uvs"] is not None:
                    atual["uvs"].extend(parte["uvs"][antigo * 2:antigo * 2 + 2])
            atual["indices"].append(novo)
    for pedaco in pedacos:
        del pedaco["mapa"]
    return pedacos


def escrever_glb(gltf, binario):
    """O arquivo .glb: cabeçalho, o bloco JSON e o bloco binário (alinhados em 4)."""
    gltf = dict(gltf)
    if binario:
        gltf["buffers"] = [{"byteLength": len(binario)}]
    else:
        gltf.pop("buffers", None)
    texto = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    texto += b" " * (-len(texto) % 4)
    binario = bytes(binario) + b"\0" * (-len(binario) % 4)
    total = 12 + 8 + len(texto) + (8 + len(binario) if binario else 0)
    partes = [struct.pack("<4sII", b"glTF", 2, total), struct.pack("<I4s", len(texto), b"JSON"), texto]
    if binario:
        partes += [struct.pack("<I4s", len(binario), b"BIN\0"), binario]
    return b"".join(partes)


def ler_glb(dados):
    """(gltf, binário) de um .glb; ValueError se não for um."""
    if len(dados) < 20:
        raise ValueError("O arquivo é pequeno demais para ser um .glb.")
    magica, versao, _total = struct.unpack_from("<4sII", dados, 0)
    if magica != b"glTF" or versao != 2:
        raise ValueError("O arquivo não é um .glb (glTF 2.0 binário).")
    gltf, binario, posicao = None, b"", 12
    while posicao + 8 <= len(dados):
        tamanho, tipo = struct.unpack_from("<I4s", dados, posicao)
        corpo = dados[posicao + 8:posicao + 8 + tamanho]
        if tipo == b"JSON":
            gltf = json.loads(bytes(corpo).decode("utf-8"))
        elif tipo == b"BIN\0" and not binario:
            binario = bytes(corpo)
        posicao += 8 + tamanho
    if gltf is None:
        raise ValueError("O .glb está corrompido (sem o JSON de dentro).")
    return gltf, binario


# ----------------------------------------------------------------------
# GEOMETRIA: normais, solda dos vértices
# ----------------------------------------------------------------------

def _normal(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    tamanho = math.sqrt(nx * nx + ny * ny + nz * nz)
    if tamanho < 1e-20:
        return None, 0.0
    return (nx / tamanho, ny / tamanho, nz / tamanho), tamanho


def soldar(triangulos, angulo=40.0):
    """Triângulos soltos -> malha indexada, com normais suaves até `angulo` graus.

    `triangulos`: lista de ((p1, p2, p3), (uv1, uv2, uv3) ou None). As quinas
    vivas (a dobra de uma caixa, o degrau de uma escada) continuam vivas; as
    curvas (um tubo, uma bola) ficam lisas. Triângulos sem área saem.

    O mesmo ponto vem igualzinho em todos os triângulos que o usam (sai da
    mesma lista de vértices do arquivo), então a solda é pelo próprio número,
    sem arredondar; a normal sai já nos 8 bits com que vai para o arquivo.
    """
    limite = math.cos(math.radians(angulo))
    normais_face, areas, pontos_face, uvs_face = [], [], [], []
    por_ponto = {}
    for pontos, uvs in triangulos:
        normal, area = _normal(*pontos)
        if normal is None:
            continue
        indice = len(normais_face)
        normais_face.append(normal)
        areas.append(area)
        pontos_face.append(pontos)
        uvs_face.append(uvs)
        for p in pontos:
            lista = por_ponto.get(p)
            if lista is None:
                por_ponto[p] = [indice]
            else:
                lista.append(indice)

    posicoes, normais, uvs_saida, indices = [], [], [], []
    tem_uv = any(uvs_face)
    vistos = {}
    suaves = {}
    sqrt = math.sqrt
    for i, pontos in enumerate(pontos_face):
        n = normais_face[i]
        uvs = uvs_face[i]
        for k in (0, 1, 2):
            p = pontos[k]
            chave_normal = (p, n)
            nq = suaves.get(chave_normal)
            if nq is None:
                sx = sy = sz = 0.0
                for j in por_ponto[p]:
                    m = normais_face[j]
                    if m[0] * n[0] + m[1] * n[1] + m[2] * n[2] >= limite:
                        a = areas[j]
                        sx += m[0] * a
                        sy += m[1] * a
                        sz += m[2] * a
                tamanho = sqrt(sx * sx + sy * sy + sz * sz) or 1.0
                nq = (int(sx / tamanho * 127 + 127.5) - 127, int(sy / tamanho * 127 + 127.5) - 127,
                      int(sz / tamanho * 127 + 127.5) - 127)
                suaves[chave_normal] = nq
            uv = uvs[k] if uvs else (0.0, 0.0)
            chave = (p, nq, uv)
            achado = vistos.get(chave)
            if achado is None:
                achado = len(posicoes) // 3
                vistos[chave] = achado
                posicoes.extend(p)
                normais.extend((nq[0] / 127, nq[1] / 127, nq[2] / 127))
                if tem_uv:
                    uvs_saida.extend(uv)
            indices.append(achado)
    return {"posicoes": posicoes, "normais": normais, "uvs": uvs_saida if tem_uv else None, "indices": indices}


# ----------------------------------------------------------------------
# A CAIXA DE UM .GLB PRONTO E O ENCAIXE (chão, centro, escala, eixo)
# ----------------------------------------------------------------------

_IDENTIDADE = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
#: Z para cima (SketchUp, 3ds Max, impressão 3D) -> Y para cima (o glTF): gira -90° em X.
Z_PARA_Y = [1.0, 0, 0, 0, 0, 0, -1.0, 0, 0, 1.0, 0, 0, 0, 0, 0, 1.0]


def multiplicar(a, b):
    """a·b, matrizes 4x4 por colunas (como no glTF)."""
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def aplicar(m, p):
    x, y, z = p
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


def caixa_do_gltf(gltf, raiz=None):
    """(menor, maior) do objeto na cena, levado por `raiz`; None sem malha medível."""
    from .objetos_3d import _MAXIMO_DO_TIPO, _matriz_do_no

    cenas = gltf.get("scenes") or []
    cena = cenas[gltf.get("scene", 0)] if cenas else None
    nos = gltf.get("nodes") or []
    malhas = gltf.get("meshes") or []
    acessores = gltf.get("accessors") or []
    baixo = [math.inf] * 3
    alto = [-math.inf] * 3

    def andar(indice, pai, profundidade=0):
        if profundidade > 64:
            return
        no = nos[indice]
        matriz = multiplicar(pai, _matriz_do_no(no))
        if "mesh" in no:
            for primitiva in malhas[no["mesh"]].get("primitives") or []:
                posicao = (primitiva.get("attributes") or {}).get("POSITION")
                if posicao is None:
                    continue
                acessor = acessores[posicao]
                menor, maior = acessor.get("min"), acessor.get("max")
                if not menor or not maior or len(menor) < 3:
                    continue
                if acessor.get("normalized") and acessor.get("componentType") in _MAXIMO_DO_TIPO:
                    teto = _MAXIMO_DO_TIPO[acessor["componentType"]]
                    menor = [max(v / teto, -1.0) for v in menor]
                    maior = [max(v / teto, -1.0) for v in maior]
                for x in (menor[0], maior[0]):
                    for y in (menor[1], maior[1]):
                        for z in (menor[2], maior[2]):
                            ponto = aplicar(matriz, (x, y, z))
                            for eixo in range(3):
                                baixo[eixo] = min(baixo[eixo], ponto[eixo])
                                alto[eixo] = max(alto[eixo], ponto[eixo])
        for filho in no.get("children") or []:
            andar(filho, matriz, profundidade + 1)

    try:
        raizes = cena.get("nodes") if cena else range(len(nos))
        for indice in raizes or []:
            andar(indice, raiz or _IDENTIDADE)
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    if baixo[0] == math.inf:
        return None
    return baixo, alto


#: Quanto vale 1 unidade do arquivo, em metros.
UNIDADES = {"m": 1.0, "cm": 0.01, "mm": 0.001, "pol": 0.0254, "pe": 0.3048}


def unidade_provavel(altura):
    """A unidade do arquivo pela altura do objeto: brinquedo não tem 250 m nem 3 mm.

    Até 30 de altura, metros; até 1 500, centímetros; acima, milímetros.
    """
    if altura <= 30:
        return "m"
    if altura <= 1500:
        return "cm"
    return "mm"


def encaixe(caixa, eixo_z=False, unidade="auto", medidas=None):
    """A matriz que põe o objeto em pé, no chão, no centro e no tamanho certo.

    `medidas`: {"altura", "largura", "profundidade"} em metros, do que se
    conhece; a escala sai da primeira informada (na ordem altura, largura,
    profundidade), igual nos três eixos (o objeto não deforma). Sem medidas,
    vale a unidade (a escolhida, ou a provável pela altura).

    Devolve (matriz, info) -- info com a unidade usada e as medidas finais.
    """
    rotacao = Z_PARA_Y if eixo_z else _IDENTIDADE
    menor, maior = caixa
    cantos = [aplicar(rotacao, (x, y, z)) for x in (menor[0], maior[0]) for y in (menor[1], maior[1]) for z in (menor[2], maior[2])]
    baixo = [min(c[i] for c in cantos) for i in range(3)]
    alto = [max(c[i] for c in cantos) for i in range(3)]
    largura, altura, profundidade = (alto[i] - baixo[i] for i in range(3))
    medidas = {k: float(v) for k, v in (medidas or {}).items() if v}
    escala, usada = None, unidade
    for nome, valor in (("altura", altura), ("largura", largura), ("profundidade", profundidade)):
        if medidas.get(nome) and valor > 1e-9:
            escala, usada = medidas[nome] / valor, f"ajustada pela {nome}"
            break
    if escala is None:
        if isinstance(unidade, (int, float)) and unidade > 0:
            # o próprio arquivo diz quanto vale a unidade dele (o COLLADA grava)
            escala = float(unidade)
            usada = next((f"{k} (do arquivo)" for k, v in UNIDADES.items() if abs(v - escala) < 1e-9), f"{escala:g} m (do arquivo)")
        else:
            if unidade not in UNIDADES:
                unidade = unidade_provavel(altura)
                usada = f"{unidade} (adivinhada pela altura)"
            escala = UNIDADES[unidade]
    cx, cz = (baixo[0] + alto[0]) / 2, (baixo[2] + alto[2]) / 2
    # escala depois do giro; depois o centro vai para x=z=0 e a base para y=0
    s = escala
    matriz = [
        rotacao[0] * s, rotacao[1] * s, rotacao[2] * s, 0,
        rotacao[4] * s, rotacao[5] * s, rotacao[6] * s, 0,
        rotacao[8] * s, rotacao[9] * s, rotacao[10] * s, 0,
        -cx * s, -baixo[1] * s, -cz * s, 1.0,
    ]
    finais = [round(altura * s, 2), round(largura * s, 2), round(profundidade * s, 2)]
    return matriz, {"unidade": usada, "medidas": finais, "escala": s}


def encaixar_glb(gltf, binario, eixo_z=False, unidade="auto", medidas=None):
    """Põe um .glb pronto em pé, no chão e na medida: um nó novo por cima de tudo."""
    caixa = caixa_do_gltf(gltf)
    if caixa is None:
        raise ValueError("O arquivo não tem nenhuma malha que dê para medir.")
    matriz, info = encaixe(caixa, eixo_z, unidade, medidas)
    if all(abs(a - b) < 1e-9 for a, b in zip(matriz, _IDENTIDADE)):
        return gltf, binario, info
    gltf = json.loads(json.dumps(gltf))  # cópia
    cenas = gltf.setdefault("scenes", [{"nodes": list(range(len(gltf.get("nodes") or [])))}])
    cena = cenas[gltf.get("scene", 0)]
    nos = gltf.setdefault("nodes", [])
    nos.append({"name": "Lazer & Sport (encaixe)", "matrix": [round(v, 9) for v in matriz], "children": list(cena.get("nodes") or [])})
    cena["nodes"] = [len(nos) - 1]
    return gltf, binario, info


def encolher_fotos(gltf, binario, maximo=FOTO_MAXIMA):
    """Refaz o bloco binário com as fotos de dentro reduzidas (PNG só com recorte).

    Cada pedaço do binário é copiado de novo, alinhado; o das fotos entra no
    lugar do original já reduzido. As malhas não mudam.
    """
    fotos = {img["bufferView"]: i for i, img in enumerate(gltf.get("images") or []) if "bufferView" in img}
    if not fotos:
        return gltf, binario
    gltf = json.loads(json.dumps(gltf))
    novo = bytearray()
    for indice, vista in enumerate(gltf["bufferViews"]):
        if vista.get("buffer", 0) != 0:
            continue
        inicio = vista.get("byteOffset", 0)
        pedaco = binario[inicio:inicio + vista["byteLength"]]
        if indice in fotos:
            try:
                pedaco, tipo = preparar_foto(bytes(pedaco), maximo)
                gltf["images"][fotos[indice]]["mimeType"] = tipo
            except Exception:  # noqa: BLE001 -- foto que o Pillow não abre fica como veio
                pass
        while len(novo) % 4:
            novo.append(0)
        vista["byteOffset"] = len(novo)
        vista["byteLength"] = len(pedaco)
        novo += pedaco
    return gltf, bytes(novo)
