"""Arquivo 3D de outro programa -> o .glb do site (o painel sobe e vê na hora).

Aceita o que os programas de projeto exportam:

  .glb             o formato do site: só se encaixa (chão, centro, medida)
  .gltf            com o .bin e as fotos num .zip (ou tudo embutido)
  .obj             com o .mtl e as fotos num .zip (ou sozinho, sem fotos)
  .stl             impressão 3D / CAD (sem cor: ganha uma cor neutra)
  .3ds             3ds Max e programas antigos (cores e fotos dos materiais)
  .dae / .kmz      COLLADA: o que o SketchUp exporta (.kmz é o .dae zipado)
  .zip             qualquer um dos de cima, com as fotos junto

E diz o que fazer com o que não dá para ler aqui (.skp, .fbx, .blend, .max):
exportar em um dos de cima, com o caminho no programa.

PRECISÃO. A forma é a do arquivo, ponto por ponto: nada é adivinhado. O que
pode mudar é só o tamanho -- a unidade (m, cm, mm, polegada) vem do arquivo
quando ele grava (o COLLADA grava), ou da escolha no painel, ou da altura
informada; sem nada disso, é adivinhada pela altura (brinquedo não tem 250 m).
"""

from __future__ import annotations

import base64
import io
import math
import posixpath
import re
import struct
import xml.etree.ElementTree as ET
import zipfile

from . import glb_montar
from .glb_montar import Cena, aplicar, encaixe, multiplicar, preparar_foto, soldar
from .objetos_3d import TAMANHO_MAXIMO

FORMATOS = (".glb", ".gltf", ".obj", ".stl", ".3ds", ".dae", ".kmz", ".zip")

#: O que não dá para abrir aqui, e como sair dele no programa de origem.
COMO_EXPORTAR = {
    ".skp": "No SketchUp: Arquivo > Exportar > Modelo 3D > COLLADA (.dae) (ou .glb, com a extensão glTF Exporter). Mande o .dae junto com as texturas num .zip.",
    ".fbx": "Abra o .fbx no Blender (grátis) e use Arquivo > Exportar > glTF 2.0 (.glb).",
    ".blend": "No Blender: Arquivo > Exportar > glTF 2.0 (.glb).",
    ".max": "No 3ds Max: File > Export > .fbx ou .obj (ou glTF, nas versões novas); depois suba o .obj com o .mtl e as texturas num .zip.",
    ".c4d": "No Cinema 4D: Arquivo > Exportar > glTF (.glb) ou Wavefront (.obj).",
    ".3dm": "No Rhino: Arquivo > Exportar > .obj ou .glb.",
    ".ply": "Abra no Blender e exporte em glTF 2.0 (.glb).",
}

#: Acima disto o celular engasga (e o arquivo passa do limite do armazenamento).
TRIANGULOS_MAXIMOS = 400_000
#: O .zip enviado, aberto, não passa disto (e não tem mais arquivos que isto).
ZIP_MAXIMO = 250 * 1024 * 1024
ZIP_ARQUIVOS = 2000

COR_NEUTRA = (0.78, 0.8, 0.84, 1.0)


class ErroDeConversao(ValueError):
    """O arquivo não deu para converter; a mensagem vai para quem enviou."""


# ----------------------------------------------------------------------
# O MODELO NO MEIO DO CAMINHO
# ----------------------------------------------------------------------

class Modelo:
    """Triângulos por material, já em coordenadas da cena (antes do encaixe)."""

    def __init__(self):
        self.materiais = {}  # nome -> {"cor": (r, g, b, a), "textura": "arquivo" | None}
        self.triangulos = {}  # nome do material -> [((p1, p2, p3), (uv1, uv2, uv3) | None)]
        self.total = 0

    def material(self, nome, cor=COR_NEUTRA, textura=None):
        if nome not in self.materiais:
            self.materiais[nome] = {"cor": tuple(cor), "textura": textura}
        return nome

    def triangulo(self, material, pontos, uvs=None):
        self.total += 1
        if self.total > TRIANGULOS_MAXIMOS:
            raise ErroDeConversao(
                f"O objeto tem mais de {TRIANGULOS_MAXIMOS:,} triângulos: pesado demais para o site. "
                "Simplifique no programa (no Blender: modificador Decimate) e envie de novo.".replace(",", ".")
            )
        if material not in self.materiais:
            self.material(material)
        self.triangulos.setdefault(material, []).append((pontos, uvs))

    def tirar_soltas(self, margem=0.15, teto=0.12):
        """Tira as peças soltas longe do conjunto; devolve quantos triângulos saíram.

        Arquivo de projeto costuma levar junto o que não é o brinquedo: cotas,
        linhas de chão, pessoas e carros de escala espalhados a dezenas de
        metros (o .3ds do trampolim tinha 2 610 assim, numa área de 170 m). A
        caixa "de verdade" é a de 96% dos triângulos (do 2% ao 98% em cada
        eixo), com folga de `margem`; o que fica fora dela sai -- só se for
        pouco (até `teto` do total): muito fora quer dizer que o objeto é
        espalhado mesmo, e aí nada sai.
        """
        centros = [[], [], []]
        for lista in self.triangulos.values():
            for pontos, _uvs in lista:
                for i in range(3):
                    centros[i].append((pontos[0][i] + pontos[1][i] + pontos[2][i]) / 3)
        total = len(centros[0])
        if total < 50:
            return 0
        limites = []
        for valores in centros:
            ordem = sorted(valores)
            baixo, alto = ordem[int(total * 0.02)], ordem[int(total * 0.98) - 1]
            folga = (alto - baixo) * margem + 1e-9
            limites.append((baixo - folga, alto + folga))

        def dentro(pontos):
            for i in range(3):
                c = (pontos[0][i] + pontos[1][i] + pontos[2][i]) / 3
                if c < limites[i][0] or c > limites[i][1]:
                    return False
            return True

        filtrado = {nome: [t for t in lista if dentro(t[0])] for nome, lista in self.triangulos.items()}
        restantes = sum(len(lista) for lista in filtrado.values())
        if total - restantes == 0 or (total - restantes) > total * teto:
            return 0
        self.triangulos = {nome: lista for nome, lista in filtrado.items() if lista}
        self.total = restantes
        return total - restantes

    def caixa(self):
        baixo = [math.inf] * 3
        alto = [-math.inf] * 3
        for lista in self.triangulos.values():
            for pontos, _uvs in lista:
                for p in pontos:
                    for i in range(3):
                        if p[i] < baixo[i]:
                            baixo[i] = p[i]
                        if p[i] > alto[i]:
                            alto[i] = p[i]
        if baixo[0] == math.inf:
            raise ErroDeConversao("O arquivo não tem nenhuma face (triângulo) para mostrar.")
        return baixo, alto


class Arquivos:
    """Os arquivos que vieram junto (o .zip): acha a textura pelo nome, de qualquer jeito.

    O programa de origem grava o caminho da sua máquina ("C:\\Projetos\\madeira.JPG");
    aqui vale o nome do arquivo, sem pasta e sem diferença de maiúscula.
    """

    def __init__(self, itens=None):
        self.itens = dict(itens or {})
        self.por_nome = {}
        for caminho, dados in self.itens.items():
            self.por_nome.setdefault(posixpath.basename(caminho).lower(), dados)

    def achar(self, nome):
        if not nome:
            return None
        nome = nome.replace("\\", "/").strip().strip('"')
        if nome.lower().startswith("file:"):
            nome = re.sub(r"^file:/*", "", nome, flags=re.IGNORECASE)
        from urllib.parse import unquote

        nome = unquote(nome)
        return self.itens.get(nome) or self.por_nome.get(posixpath.basename(nome).lower())


def abrir_zip(dados):
    """{caminho: bytes} do .zip, com teto de tamanho e de quantidade (contra .zip-bomba)."""
    try:
        pacote = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile as exc:
        raise ErroDeConversao("O .zip está corrompido.") from exc
    infos = [i for i in pacote.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")]
    if len(infos) > ZIP_ARQUIVOS:
        raise ErroDeConversao(f"O .zip tem arquivos demais (mais de {ZIP_ARQUIVOS}).")
    if sum(i.file_size for i in infos) > ZIP_MAXIMO:
        raise ErroDeConversao("O .zip aberto passa de 250 MB: mande só o objeto e as texturas.")
    return {i.filename.replace("\\", "/"): pacote.read(i) for i in infos}


# ----------------------------------------------------------------------
# OS FORMATOS
# ----------------------------------------------------------------------

def _numeros(texto):
    return [float(x) for x in texto.split()] if texto else []


def ler_obj(dados, arquivos):
    texto = dados.decode("utf-8", errors="replace")
    modelo = Modelo()
    v, vt = [], []
    material = modelo.material("padrao")
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha[0] == "#":
            continue
        partes = linha.split()
        tag = partes[0]
        if tag == "v" and len(partes) >= 4:
            v.append((float(partes[1]), float(partes[2]), float(partes[3])))
        elif tag == "vt" and len(partes) >= 3:
            vt.append((float(partes[1]), 1.0 - float(partes[2])))  # o glTF conta o v de cima
        elif tag == "f" and len(partes) >= 4:
            cantos = []
            for pedaco in partes[1:]:
                numeros = pedaco.split("/")
                iv = int(numeros[0])
                iv = iv - 1 if iv > 0 else len(v) + iv
                it = None
                if len(numeros) > 1 and numeros[1]:
                    it = int(numeros[1])
                    it = it - 1 if it > 0 else len(vt) + it
                cantos.append((iv, it))
            for k in range(1, len(cantos) - 1):
                trio = (cantos[0], cantos[k], cantos[k + 1])
                pontos = tuple(v[c[0]] for c in trio)
                uvs = tuple(vt[c[1]] for c in trio) if all(c[1] is not None for c in trio) else None
                modelo.triangulo(material, pontos, uvs)
        elif tag == "usemtl":
            material = " ".join(partes[1:]) or "padrao"
        elif tag == "mtllib":
            mtl = arquivos.achar(" ".join(partes[1:]))
            if mtl:
                _ler_mtl(mtl, modelo)
    return modelo, {"eixo_z": False}


def _ler_mtl(dados, modelo):
    atual = None
    for linha in dados.decode("utf-8", errors="replace").splitlines():
        partes = linha.strip().split()
        if not partes:
            continue
        tag = partes[0]
        if tag == "newmtl":
            nome = " ".join(partes[1:])
            atual = modelo.materiais.setdefault(nome, {"cor": COR_NEUTRA, "textura": None})
        elif atual is None:
            continue
        elif tag == "Kd" and len(partes) >= 4:
            atual["cor"] = (float(partes[1]), float(partes[2]), float(partes[3]), atual["cor"][3])
        elif tag == "d" and len(partes) >= 2:
            atual["cor"] = atual["cor"][:3] + (float(partes[1]),)
        elif tag == "Tr" and len(partes) >= 2:
            atual["cor"] = atual["cor"][:3] + (1.0 - float(partes[1]),)
        elif tag == "map_Kd" and len(partes) >= 2:
            atual["textura"] = partes[-1]


def ler_stl(dados, arquivos):
    modelo = Modelo()
    material = modelo.material("stl", (0.72, 0.76, 0.82, 1.0))
    if len(dados) >= 84:
        quantos = struct.unpack_from("<I", dados, 80)[0]
        if 84 + quantos * 50 == len(dados):
            for i in range(quantos):
                valores = struct.unpack_from("<12f", dados, 84 + i * 50)
                modelo.triangulo(material, (valores[3:6], valores[6:9], valores[9:12]))
            return modelo, {"eixo_z": True}
    texto = dados.decode("latin-1")
    if "facet" not in texto:
        raise ErroDeConversao("O .stl não tem faces (nem binário, nem texto).")
    pontos = [tuple(float(n) for n in m) for m in re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", texto)]
    for i in range(0, len(pontos) - 2, 3):
        modelo.triangulo(material, (pontos[i], pontos[i + 1], pontos[i + 2]))
    return modelo, {"eixo_z": True}


def ler_3ds(dados, arquivos):
    """Os blocos do .3ds: objetos (vértices, faces, materiais por face, UV) e materiais."""
    modelo = Modelo()
    materiais = {}

    def texto(posicao):
        fim = dados.index(b"\0", posicao)
        return dados[posicao:fim].decode("latin-1"), fim + 1

    def cor(posicao, fim):
        while posicao + 6 <= fim:
            cid, tamanho = struct.unpack_from("<HI", dados, posicao)
            if tamanho < 6:
                break
            if cid in (0x0011, 0x0012):
                return tuple(b / 255 for b in dados[posicao + 6:posicao + 9])
            if cid in (0x0010, 0x0013):
                return struct.unpack_from("<3f", dados, posicao + 6)
            posicao += tamanho
        return None

    def porcentagem(posicao, fim):
        while posicao + 6 <= fim:
            cid, tamanho = struct.unpack_from("<HI", dados, posicao)
            if tamanho < 6:
                break
            if cid == 0x0030:
                return struct.unpack_from("<h", dados, posicao + 6)[0] / 100
            if cid == 0x0031:
                return struct.unpack_from("<f", dados, posicao + 6)[0]
            posicao += tamanho
        return 0.0

    def material(posicao, fim):
        atual = {"nome": f"mat{len(materiais)}", "cor": COR_NEUTRA[:3], "alfa": 1.0, "textura": None}
        while posicao + 6 <= fim:
            cid, tamanho = struct.unpack_from("<HI", dados, posicao)
            if tamanho < 6:
                break
            corpo, final = posicao + 6, posicao + tamanho
            if cid == 0xA000:
                atual["nome"] = texto(corpo)[0]
            elif cid == 0xA020:
                atual["cor"] = cor(corpo, final) or atual["cor"]
            elif cid == 0xA050:
                atual["alfa"] = max(0.05, 1.0 - porcentagem(corpo, final))
            elif cid == 0xA200:
                interno = corpo
                while interno + 6 <= final:
                    sid, stam = struct.unpack_from("<HI", dados, interno)
                    if stam < 6:
                        break
                    if sid == 0xA300:
                        atual["textura"] = texto(interno + 6)[0]
                    interno += stam
            posicao += tamanho
        materiais[atual["nome"]] = atual

    def objeto(posicao, fim):
        while posicao + 6 <= fim:
            cid, tamanho = struct.unpack_from("<HI", dados, posicao)
            if tamanho < 6:
                break
            corpo, final = posicao + 6, posicao + tamanho
            if cid == 0x4100:
                objeto(corpo, final)  # o TRIMESH: os blocos de dentro
            elif cid == 0x4110:
                n = struct.unpack_from("<H", dados, corpo)[0]
                valores = struct.unpack_from(f"<{3 * n}f", dados, corpo + 2)
                estado["vertices"] = [valores[i:i + 3] for i in range(0, 3 * n, 3)]
            elif cid == 0x4120:
                n = struct.unpack_from("<H", dados, corpo)[0]
                valores = struct.unpack_from(f"<{4 * n}H", dados, corpo + 2)
                estado["faces"] = [valores[i:i + 3] for i in range(0, 4 * n, 4)]
                estado["grupos"] = []
                interno = corpo + 2 + 8 * n
                while interno + 6 <= final:
                    sid, stam = struct.unpack_from("<HI", dados, interno)
                    if stam < 6:
                        break
                    if sid == 0x4130:
                        nome, p = texto(interno + 6)
                        quantas = struct.unpack_from("<H", dados, p)[0]
                        estado["grupos"].append((nome, struct.unpack_from(f"<{quantas}H", dados, p + 2)))
                    interno += stam
            elif cid == 0x4140:
                n = struct.unpack_from("<H", dados, corpo)[0]
                valores = struct.unpack_from(f"<{2 * n}f", dados, corpo + 2)
                estado["uvs"] = [(valores[i], 1.0 - valores[i + 1]) for i in range(0, 2 * n, 2)]
            posicao += tamanho

    def descarregar():
        vertices = estado.get("vertices") or []
        faces = estado.get("faces") or []
        uvs = estado.get("uvs") or []
        if vertices and faces:
            material_da_face = {}
            for nome, indices in estado.get("grupos") or []:
                for i in indices:
                    material_da_face[i] = nome
            for i, (a, b, c) in enumerate(faces):
                if max(a, b, c) >= len(vertices):
                    continue
                pontos = (vertices[a], vertices[b], vertices[c])
                trio = (uvs[a], uvs[b], uvs[c]) if len(uvs) == len(vertices) else None
                modelo.triangulo(material_da_face.get(i, "padrao"), pontos, trio)
        estado.clear()

    def andar(posicao, fim):
        while posicao + 6 <= fim:
            cid, tamanho = struct.unpack_from("<HI", dados, posicao)
            if tamanho < 6 or posicao + tamanho > fim:
                break
            corpo, final = posicao + 6, posicao + tamanho
            if cid in (0x4D4D, 0x3D3D):
                andar(corpo, final)
            elif cid == 0xAFFF:
                material(corpo, final)
            elif cid == 0x4000:
                _nome, p = texto(corpo)
                objeto(p, final)
                descarregar()
            posicao += tamanho

    estado = {}
    if len(dados) < 16 or struct.unpack_from("<H", dados, 0)[0] != 0x4D4D:
        raise ErroDeConversao("O arquivo não é um .3ds.")
    try:
        andar(0, len(dados))
    except (struct.error, ValueError, IndexError) as exc:
        if not modelo.total:
            raise ErroDeConversao("O .3ds está corrompido.") from exc
    for nome, m in materiais.items():
        modelo.materiais[nome] = {"cor": tuple(m["cor"]) + (m["alfa"],), "textura": m["textura"]}
    return modelo, {"eixo_z": True}


# -- COLLADA (.dae): o SketchUp ----------------------------------------

def _matriz_dae(no):
    """A transformação de um <node>, na ordem em que vem (matrix, translate, rotate, scale)."""
    m = glb_montar._IDENTIDADE
    for filho in no:
        tag = filho.tag
        if tag == "matrix":
            v = _numeros(filho.text)
            if len(v) == 16:  # o COLLADA grava por linhas
                m = multiplicar(m, [v[r * 4 + c] for c in range(4) for r in range(4)])
        elif tag == "translate":
            x, y, z = (_numeros(filho.text) + [0, 0, 0])[:3]
            m = multiplicar(m, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1])
        elif tag == "scale":
            x, y, z = (_numeros(filho.text) + [1, 1, 1])[:3]
            m = multiplicar(m, [x, 0, 0, 0, 0, y, 0, 0, 0, 0, z, 0, 0, 0, 0, 1])
        elif tag == "rotate":
            v = _numeros(filho.text)
            if len(v) == 4:
                x, y, z, graus = v
                tamanho = math.sqrt(x * x + y * y + z * z) or 1.0
                x, y, z = x / tamanho, y / tamanho, z / tamanho
                a = math.radians(graus)
                c, s, t = math.cos(a), math.sin(a), 1 - math.cos(a)
                m = multiplicar(m, [
                    t * x * x + c, t * x * y + s * z, t * x * z - s * y, 0,
                    t * x * y - s * z, t * y * y + c, t * y * z + s * x, 0,
                    t * x * z + s * y, t * y * z - s * x, t * z * z + c, 0,
                    0, 0, 0, 1,
                ])
    return m


def ler_dae(dados, arquivos):
    if b"<!ENTITY" in dados[:4096] or b"<!DOCTYPE" in dados[:4096]:
        raise ErroDeConversao("O .dae traz declarações que não são aceitas (DOCTYPE/ENTITY).")
    try:
        raiz = ET.fromstring(dados)
    except ET.ParseError as exc:
        raise ErroDeConversao("O .dae está corrompido (o XML não abre).") from exc
    for elemento in raiz.iter():
        if isinstance(elemento.tag, str) and "}" in elemento.tag:
            elemento.tag = elemento.tag.split("}", 1)[1]
    por_id = {e.get("id"): e for e in raiz.iter() if e.get("id")}

    def alvo(url):
        return por_id.get((url or "").lstrip("#"))

    asset = raiz.find("asset")
    unidade = None
    eixo_z = False
    if asset is not None:
        un = asset.find("unit")
        if un is not None and un.get("meter"):
            try:
                unidade = float(un.get("meter"))
            except ValueError:
                unidade = None
        eixo_z = (asset.findtext("up_axis") or "Y_UP").strip().upper() == "Z_UP"

    # as fotos e os materiais
    imagens = {}
    for img in raiz.iter("image"):
        caminho = img.findtext("init_from") or img.findtext("init_from/ref") or ""
        imagens[img.get("id")] = caminho.strip()

    def efeito(ef):
        perfil = ef.find("profile_COMMON")
        if perfil is None:
            return {"cor": COR_NEUTRA, "textura": None}
        params = {p.get("sid"): p for p in perfil.iter("newparam")}
        tecnica = perfil.find("technique")
        sombreador = None
        if tecnica is not None:
            for nome in ("phong", "lambert", "blinn", "constant"):
                sombreador = tecnica.find(nome)
                if sombreador is not None:
                    break
        cor, textura = COR_NEUTRA[:3] + (1.0,), None
        if sombreador is not None:
            difusa = sombreador.find("diffuse")
            if difusa is not None:
                if difusa.find("color") is not None:
                    v = _numeros(difusa.findtext("color"))
                    cor = tuple((v + [1.0] * 4)[:4])
                tex = difusa.find("texture")
                if tex is not None:
                    chave = tex.get("texture")
                    amostrador = params.get(chave)
                    if amostrador is not None:
                        fonte = amostrador.findtext("sampler2D/source") or amostrador.findtext("sampler2D/instance_image")
                        superficie = params.get((fonte or "").strip())
                        imagem_id = superficie.findtext("surface/init_from") if superficie is not None else None
                        if imagem_id is None:
                            inst = amostrador.find("sampler2D/instance_image")
                            imagem_id = (inst.get("url") or "").lstrip("#") if inst is not None else None
                        textura = imagens.get((imagem_id or "").strip())
                    else:
                        textura = imagens.get(chave)
            transparente = sombreador.find("transparent")
            quanto = sombreador.findtext("transparency/float")
            if transparente is not None and quanto:
                try:
                    q = float(quanto)
                    v = _numeros(transparente.findtext("color")) or [1, 1, 1, 1]
                    if (transparente.get("opaque") or "A_ONE") == "RGB_ZERO":
                        alfa = 1 - (sum(v[:3]) / 3) * q
                    else:
                        alfa = (v[3] if len(v) > 3 else 1) * q
                    if 0.02 < alfa < 0.98:
                        cor = cor[:3] + (max(0.12, alfa),)
                except ValueError:
                    pass
        return {"cor": cor, "textura": textura}

    materiais = {}
    for mat in raiz.iter("material"):
        inst = mat.find("instance_effect")
        ef = alvo(inst.get("url")) if inst is not None else None
        materiais[mat.get("id")] = efeito(ef) if ef is not None else {"cor": COR_NEUTRA, "textura": None}

    modelo = Modelo()
    for nome, m in materiais.items():
        modelo.materiais[nome] = m

    cache = {}

    def geometria(geo):
        if geo.get("id") in cache:
            return cache[geo.get("id")]
        malha = geo.find("mesh")
        saida = []
        if malha is None:
            cache[geo.get("id")] = saida
            return saida
        fontes = {}
        for fonte in malha.findall("source"):
            arr = fonte.find("float_array")
            acessor = fonte.find("technique_common/accessor")
            passo = int(acessor.get("stride") or 1) if acessor is not None else 3
            fontes[fonte.get("id")] = (_numeros(arr.text) if arr is not None else [], passo)
        vertices = {}
        for vt in malha.findall("vertices"):
            for entrada in vt.findall("input"):
                if entrada.get("semantic") == "POSITION":
                    vertices[vt.get("id")] = entrada.get("source", "").lstrip("#")
        for prim in malha:
            if prim.tag not in ("triangles", "polylist", "polygons"):
                continue
            entradas = prim.findall("input")
            passo = max((int(e.get("offset") or 0) for e in entradas), default=0) + 1
            pos_off = uv_off = None
            pos_fonte = uv_fonte = None
            for e in entradas:
                semantica = e.get("semantic")
                fonte = e.get("source", "").lstrip("#")
                if semantica == "VERTEX":
                    pos_off, pos_fonte = int(e.get("offset") or 0), fontes.get(vertices.get(fonte, fonte))
                elif semantica == "TEXCOORD" and uv_off is None:
                    uv_off, uv_fonte = int(e.get("offset") or 0), fontes.get(fonte)
            if pos_fonte is None:
                continue
            if prim.tag == "triangles":
                listas = [_numeros(prim.findtext("p"))]
                contagens = [[3] * (len(listas[0]) // (3 * passo))]
            elif prim.tag == "polylist":
                listas = [_numeros(prim.findtext("p"))]
                contagens = [[int(x) for x in _numeros(prim.findtext("vcount"))]]
            else:
                listas = [_numeros(p.text) for p in prim.findall("p")]
                contagens = [[len(l) // passo] for l in listas]
            triangulos = []
            pv, pp = pos_fonte
            for lista, quantos in zip(listas, contagens):
                indice = 0
                for n in quantos:
                    cantos = []
                    for k in range(n):
                        base = (indice + k) * passo
                        if base + passo > len(lista):
                            break
                        iv = int(lista[base + pos_off])
                        ponto = tuple(pv[iv * pp:iv * pp + 3])
                        uv = None
                        if uv_fonte is not None:
                            tv, tp = uv_fonte
                            it = int(lista[base + uv_off])
                            if it * tp + 1 < len(tv):
                                uv = (tv[it * tp], 1.0 - tv[it * tp + 1])
                        if len(ponto) == 3:
                            cantos.append((ponto, uv))
                    indice += n
                    for k in range(1, len(cantos) - 1):
                        trio = (cantos[0], cantos[k], cantos[k + 1])
                        uvs = tuple(c[1] for c in trio) if all(c[1] for c in trio) else None
                        triangulos.append((tuple(c[0] for c in trio), uvs))
            saida.append((prim.get("material") or "", triangulos))
        cache[geo.get("id")] = saida
        return saida

    def instanciar(no, pai, profundidade=0):
        if profundidade > 48:
            return
        matriz = multiplicar(pai, _matriz_dae(no))
        for filho in no:
            if filho.tag == "instance_geometry":
                geo = alvo(filho.get("url"))
                if geo is None:
                    continue
                ligacoes = {
                    im.get("symbol"): (im.get("target") or "").lstrip("#")
                    for im in filho.iter("instance_material")
                }
                for simbolo, triangulos in geometria(geo):
                    nome = ligacoes.get(simbolo, simbolo) or "padrao"
                    for pontos, uvs in triangulos:
                        modelo.triangulo(nome, tuple(aplicar(matriz, p) for p in pontos), uvs)
            elif filho.tag == "instance_node":
                outro = alvo(filho.get("url"))
                if outro is not None:
                    instanciar(outro, matriz, profundidade + 1)
            elif filho.tag == "node":
                instanciar(filho, matriz, profundidade + 1)

    cena = raiz.find("scene/instance_visual_scene")
    visual = alvo(cena.get("url")) if cena is not None else None
    if visual is None:
        visual = next(iter(raiz.iter("visual_scene")), None)
    if visual is not None:
        for no in visual.findall("node"):
            instanciar(no, glb_montar._IDENTIDADE)
    else:
        for geo in raiz.iter("geometry"):
            for simbolo, triangulos in geometria(geo):
                for pontos, uvs in triangulos:
                    modelo.triangulo(simbolo or "padrao", pontos, uvs)
    return modelo, {"eixo_z": eixo_z, "unidade": unidade}


# -- glTF separado (.gltf + .bin + fotos) ------------------------------

def _dados_da_uri(uri, arquivos):
    if uri.startswith("data:"):
        _cabeca, _virgula, corpo = uri.partition(",")
        return base64.b64decode(corpo)
    achado = arquivos.achar(uri)
    if achado is None:
        raise ErroDeConversao(f"Falta o arquivo \"{uri}\" que o .gltf usa: mande tudo junto num .zip.")
    return achado


def gltf_para_glb(dados, arquivos):
    import json

    try:
        gltf = json.loads(dados.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ErroDeConversao("O .gltf está corrompido (o JSON não abre).") from exc
    novo = bytearray()
    bases = []
    for buffer in gltf.get("buffers") or []:
        while len(novo) % 4:
            novo.append(0)
        bases.append(len(novo))
        novo += _dados_da_uri(buffer.get("uri", ""), arquivos)[: buffer.get("byteLength")]
    for vista in gltf.get("bufferViews") or []:
        vista["byteOffset"] = vista.get("byteOffset", 0) + bases[vista.get("buffer", 0)]
        vista["buffer"] = 0
    for imagem in gltf.get("images") or []:
        uri = imagem.pop("uri", None)
        if uri is None:
            continue
        foto = _dados_da_uri(uri, arquivos)
        while len(novo) % 4:
            novo.append(0)
        gltf.setdefault("bufferViews", []).append({"buffer": 0, "byteOffset": len(novo), "byteLength": len(foto)})
        novo += foto
        imagem["bufferView"] = len(gltf["bufferViews"]) - 1
        imagem.setdefault("mimeType", "image/png" if foto[:4] == b"\x89PNG" else "image/jpeg")
    return gltf, bytes(novo)


# ----------------------------------------------------------------------
# DO MODELO AO .GLB
# ----------------------------------------------------------------------

def montar(modelo, arquivos, eixo_z=False, unidade="auto", medidas=None):
    """O .glb do modelo: encaixado no chão, no centro e na medida, com as fotos dentro."""
    matriz, info = encaixe(modelo.caixa(), eixo_z, unidade, medidas)
    cena = Cena()
    partes = []
    fotos = {}
    avisos = []
    levados = {}  # cada ponto levado uma vez só (ele se repete em vários triângulos)
    for nome, lista in modelo.triangulos.items():
        if not lista:
            continue
        dados_material = modelo.materiais.get(nome) or {"cor": COR_NEUTRA, "textura": None}
        textura = None
        alfa = "BLEND" if dados_material["cor"][3] < 0.98 else "OPAQUE"
        arquivo_textura = dados_material.get("textura")
        if arquivo_textura and any(uvs for _p, uvs in lista):
            if arquivo_textura not in fotos:
                bruto = arquivos.achar(arquivo_textura)
                if bruto is None:
                    avisos.append(f"Faltou a textura \"{posixpath.basename(arquivo_textura.replace(chr(92), '/'))}\": a peça ficou na cor do material.")
                    fotos[arquivo_textura] = None
                else:
                    try:
                        foto, tipo = preparar_foto(bruto)
                        fotos[arquivo_textura] = (cena.foto(foto, tipo, repetir=True), tipo)
                    except Exception:  # noqa: BLE001 -- textura que o Pillow não abre
                        avisos.append(f"A textura \"{arquivo_textura}\" não abriu: a peça ficou na cor do material.")
                        fotos[arquivo_textura] = None
            if fotos.get(arquivo_textura):
                textura, tipo = fotos[arquivo_textura]
                if tipo == "image/png" and alfa == "OPAQUE":
                    alfa = "MASK"
        cor = dados_material["cor"] if textura is None else (1.0, 1.0, 1.0, dados_material["cor"][3])
        indice = cena.material(nome or "material", cor, textura, alfa, dois_lados=True)
        triangulos = [
            (tuple(levados[p] if p in levados else levados.setdefault(p, aplicar(matriz, p)) for p in pontos),
             uvs if textura is not None else None)
            for pontos, uvs in lista
        ]
        parte = soldar(triangulos)
        parte["material"] = indice
        partes.append(parte)
    malha = cena.malha("objeto", partes)
    if malha is None:
        raise ErroDeConversao("O arquivo não tem nenhuma face (triângulo) para mostrar.")
    cena.no("objeto", malha)
    info.update({"triangulos": modelo.total, "materiais": len(partes), "fotos": sum(1 for f in fotos.values() if f), "avisos": avisos})
    return cena.glb({"origem": "conversao"}), info


LEITORES = {".obj": ler_obj, ".stl": ler_stl, ".3ds": ler_3ds, ".dae": ler_dae}


def _extensao(nome):
    return posixpath.splitext((nome or "").lower())[1]


def converter(nome, dados, eixo="auto", unidade="auto", medidas=None, limpar=True):
    """(bytes do .glb, info) do arquivo enviado; ErroDeConversao com o motivo, se não der.

    `eixo`: "auto" (o do formato), "y" ou "z" (o lado de cima do arquivo).
    `unidade`: "auto" ou uma de glb_montar.UNIDADES. `medidas`: as do painel
    (a primeira informada manda na escala). `limpar`: tirar as peças soltas
    longe do conjunto (ver Modelo.tirar_soltas).
    """
    extensao = _extensao(nome)
    if extensao in COMO_EXPORTAR:
        raise ErroDeConversao(f"Esse formato ({extensao}) não abre aqui. {COMO_EXPORTAR[extensao]}")
    if extensao not in FORMATOS:
        raise ErroDeConversao("Envie um destes: " + ", ".join(FORMATOS) + ".")
    arquivos = Arquivos()
    if extensao in (".zip", ".kmz"):
        itens = abrir_zip(dados)
        arquivos = Arquivos(itens)
        candidatos = [(c, d) for c, d in itens.items() if _extensao(c) in (".glb", ".gltf", ".obj", ".stl", ".3ds", ".dae")]
        if not candidatos:
            sobras = sorted({_extensao(c) for c in itens if _extensao(c) in COMO_EXPORTAR})
            dica = f" Veio {', '.join(sobras)}: {COMO_EXPORTAR[sobras[0]]}" if sobras else ""
            raise ErroDeConversao("O .zip não traz nenhum objeto 3D (.glb, .gltf, .obj, .stl, .3ds ou .dae)." + dica)
        # o maior é o objeto (os outros, peças soltas ou cópias)
        nome, dados = max(candidatos, key=lambda par: len(par[1]))
        extensao = _extensao(nome)

    escolhido_z = {"y": False, "z": True}.get(eixo)
    info_formato = {}
    if extensao in (".glb", ".gltf"):
        try:
            gltf, binario = glb_montar.ler_glb(dados) if extensao == ".glb" else gltf_para_glb(dados, arquivos)
        except ValueError as exc:
            raise ErroDeConversao(str(exc)) from exc
        try:
            gltf, binario, info = glb_montar.encaixar_glb(gltf, binario, bool(escolhido_z), unidade, medidas)
        except ValueError as exc:
            raise ErroDeConversao(str(exc)) from exc
        saida = glb_montar.escrever_glb(gltf, binario)
        for maximo in (glb_montar.FOTO_MAXIMA, 768, 512):
            if len(saida) <= TAMANHO_MAXIMO:
                break
            gltf, binario = glb_montar.encolher_fotos(gltf, binario, maximo)
            saida = glb_montar.escrever_glb(gltf, binario)
        info.update({
            "triangulos": None,
            "materiais": len(gltf.get("materials") or []),
            "fotos": len(gltf.get("images") or []),
            "avisos": [],
        })
    else:
        modelo, info_formato = LEITORES[extensao](dados, arquivos)
        soltas = modelo.tirar_soltas() if limpar else 0
        eixo_z = info_formato.get("eixo_z", False) if escolhido_z is None else escolhido_z
        unidade_usada = unidade
        if unidade == "auto" and info_formato.get("unidade"):
            unidade_usada = info_formato["unidade"]
        saida, info = montar(modelo, arquivos, eixo_z, unidade_usada, medidas)
        info["eixo"] = "z" if eixo_z else "y"
        if soltas:
            quantos = f"{soltas:,}".replace(",", ".")
            info["avisos"].insert(0, f"{quantos} triângulos soltos longe do conjunto saíram (cotas, linhas, pessoas de escala).")
    if len(saida) > TAMANHO_MAXIMO:
        raise ErroDeConversao(
            f"O objeto convertido passou de {TAMANHO_MAXIMO // (1024 * 1024)} MB. "
            "Reduza as texturas ou simplifique a malha no programa e envie de novo."
        )
    info["formato"] = extensao.lstrip(".")
    info["arquivo"] = posixpath.basename(nome)
    info["tamanho"] = len(saida)
    return saida, info
