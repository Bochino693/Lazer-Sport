"""O estúdio das fotos das categorias: o salão, a luz, a câmera e as máquinas (Blender Cycles).

O pedido do dono (seção 95 do LEIA-ME-V10): "fotos realistas só das máquinas no
ambiente, sem crianças artificiais" e "deve ficar bem posicionado [...] tem
brinquedos flutuando... não está certo". E a régua do chefe dele: viva, nítida,
como a foto de um lanche de propaganda -- nada com cara de falso, como tirada por
uma câmera 4K, sem parede branca nem chão cinza, cores vivas e saturadas.

O QUE ESTE MÓDULO MONTA (com o `bpy`, o Blender como módulo do Python):

  * O SALÃO: uma área de diversão de shopping, moderna. O piso de resina polida
    numa cor viva (azul fundo, roxo...) que reflete de verdade (a camada de verniz
    do Principled BSDF: o reflexo nítido por cima, o fosco por baixo); a parede do
    fundo azul-marinho com as linhas de LED/neon nas cores da marca (#007BFF,
    #E63946, #FFD700, magenta, ciano) que ACENDEM a cena (são malhas que emitem
    luz: o piso e as máquinas recebem a cor); o teto escuro com as luminárias
    embutidas (o disco aceso e o foco embaixo) e os perfis de LED; e, numa
    abertura da parede, o fundo do shopping longe, cujas luzes viram bokeh.
  * A CÂMERA na altura dos olhos, lente natural (35-50 mm), nivelada (as
    verticais retas, o enquadramento pelo deslocamento da lente) e a
    profundidade de campo leve (f/2,8 no grupo das máquinas).
  * AS MÁQUINAS, de dois jeitos:
      - o .glb NOSSO (core/static/site/arena/modelos/<chave>.glb), só lido: os
        adesivos ganham o material de vinil brilhante (rugosidade ~0,25 e o
        verniz), os LEDs e as telas acendem;
      - a FOTO DO CATÁLOGO recortada (ferramentas/categorias/maquinas-alta/), num
        plano de pé virado para a câmera. A borda de baixo da caixa do recorte
        (medida no alfa, não chutada) fica EXATAMENTE no chão; a altura é a do
        cadastro (maquinas.json); o ângulo da foto (`giro`: o lado que ela mostra)
        diz para onde a máquina "olha". Atrás do plano vai uma CAIXA-SOMBRA do
        tamanho da máquina (largura, fundo e altura de verdade), invisível para a
        câmera, que recebe a própria foto PROJETADA DA CÂMERA: é ela que faz a
        sombra no chão, o escurecido do contato e o reflexo no piso -- a base da
        foto encosta no chão como uma máquina de verdade.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image, ImageEnhance, ImageFilter

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent.parent
MODELOS = RAIZ / "core" / "static" / "site" / "arena" / "modelos"
RECORTES = RAIZ / "ferramentas" / "categorias" / "maquinas-alta"
REPOSICAO = RAIZ / "ferramentas" / "categorias" / "reposicao"
FICHA = json.loads((RAIZ / "ferramentas" / "categorias" / "maquinas" / "maquinas.json").read_text(encoding="utf-8"))
PECAS = json.loads((REPOSICAO / "pecas.json").read_text(encoding="utf-8"))
#: Os recortes preparados (cortados no alfa e ampliados) e os renders: fora do repositório (.gitignore).
CACHE = PASTA / "render" / "recortes"

#: As cores da marca (e as do neon).
MARCA = {
    "azul": "#007BFF",
    "vermelho": "#E63946",
    "amarelo": "#FFD700",
    "magenta": "#FF2BD6",
    "ciano": "#19E3FF",
    "roxo": "#8A3CFF",
    "verde": "#2BFF88",
    "laranja": "#FF7A1A",
    "rosa": "#FF5FA8",
}

#: Os nomes dos nossos .glb (o nome do produto vai na lista das máquinas de cada foto).
GLB_NOME = {
    "brinquedao-modelo-2": "Brinquedão Modelo 2",
    "brinquedao-modelo-3": "Brinquedão Modelo 3",
    "brinquedao-modelo-4": "Brinquedão Modelo 4",
    "brinquedao-modelo-5": "Brinquedão Modelo 5",
    "brinquedao-ninja": "Brinquedão Ninja",
    "espaco-esportivo-modelo-1": "Espaço Esportivo Modelo 1",
    "trampolim-enterrada": "Trampolim de Enterrada",
    "trampolim-enterrada-espuma": "Trampolim de Enterrada",
    "strike-kids": "Strike Kids",
    "air-game-kids-alienigenas": "Air Game Kids Alienígenas",
    "air-game-kids-astronautas": "Air Game Kids Alienígenas",
    "basquete-street-quadrinhos": "Basquete Home Quadrinhos",
}

#: AS FOTOS DO CATÁLOGO: (giro, altura da foto, fundo da máquina em m).
#: `giro`: de que lado a foto foi tirada (graus; 0 = de frente, positivo = pela direita
#: de quem olha a máquina -- a lateral direita aparece). `altura`: o quanto a câmera
#: da foto estava acima (graus). Os dois vêm das capas do catálogo
#: (ferramentas/categorias/cenas.js, CATALOGO), conferidos no olho. `fundo`: a
#: profundidade de verdade da máquina (a largura sai do recorte).
FOTOS = {
    "mundo-zumbi": (-24, 8, 0.85),
    "simulador-mario-kart": (-24, 8, 1.9),
    "basquete-street": (24, 7, 2.6),
    "basquete-home": (20, 8, 2.3),
    "show-de-bola": (-24, 9, 1.5),
    "multi-jogos-retro": (22, 7, 0.9),
    "gabinete-games": (22, 8, 1.3),
    "pinball-32": (-24, 12, 1.3),
    "pinball-40": (24, 12, 1.35),
    "homem-aranha": (-22, 7, 0.8),
    "sonic-dash": (22, 7, 0.8),
    "subway-surfers": (22, 7, 0.8),
    "flappy-bird": (22, 7, 0.8),
    "speed-turbo": (-22, 7, 0.8),
    "nervo-teste": (8, 6, 0.75),
    "lazer-shot": (6, 6, 0.8),
    "top-racer": (22, 8, 1.4),
    "matrix-one-piece": (6, 6, 0.8),
    "homem-aranha-kids": (-12, 7, 0.7),
    "tomb-raider-kids": (-8, 7, 0.7),
    "corrida-dos-minions": (22, 9, 0.75),
    "pega-toupeira": (10, 10, 0.9),
    "pantera-kids": (8, 7, 0.7),
    "sonic-kids": (-8, 7, 0.7),
    "minions-kids": (8, 7, 0.7),
    "bob-esponja-kids": (-6, 7, 0.7),
    "air-game-kids": (4, 16, 1.4),
    "brinquedao-modelo-1": (-12, 10, 3.0),
    "air-game-premium": (22, 22, 1.25),
    "air-game-home": (20, 22, 1.1),
    "pebolim-eletronico": (-30, 18, 1.2),  # (a lateral comprida é a frente; a ponta curta à esquerda)
    "pac-man": (24, 22, 0.85),
    "matrix": (24, 24, 1.0),
    "multi-jogos": (-22, 12, 1.2),
    "labamba": (-24, 22, 2.2),
    "carrossel-sorvetinho": (10, 14, 1.8),
    "mini-roda-sorvete": (-15, 16, 1.9),  # (a cerca vista de frente, pela esquerda: o canto mais perto à esquerda)
    "sonic-racing": (22, 10, 1.9),
    "porsche-simulador": (24, 10, 2.0),
    "basquete-duplo": (-20, 8, 2.6),
    "basquete-kids": (-18, 10, 1.8),
    "cozinha-infantil": (-14, 9, 0.6),
    "oficina-de-engenharia": (-14, 9, 0.6),
    "salao-de-beleza": (-14, 9, 0.6),
    "kid-play": (10, 14, 4.0),
}


# ======================================================================
# O BÁSICO
# ======================================================================

def hex_linear(cor, mult=1.0):
    """'#RRGGBB' -> (r, g, b, 1) linear (o que o Blender espera nas cores)."""
    cor = cor.lstrip("#")
    srgb = [int(cor[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (lin[0] * mult, lin[1] * mult, lin[2] * mult, 1.0)


def limpar():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for bloco in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.lights, bpy.data.curves):
        for item in list(bloco):
            bloco.remove(item)


def ligar(objeto, colecao=None):
    (colecao or bpy.context.scene.collection).objects.link(objeto)
    return objeto


def malha(nome, verts, faces, uvs=None):
    m = bpy.data.meshes.new(nome)
    m.from_pydata(verts, [], faces)
    if uvs is not None:
        camada = m.uv_layers.new(name="UVMap")
        for poly in m.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                camada.data[li].uv = uvs[vi]
    m.update()
    return m


def caixa(nome, centro, tam, mat=None, giro=0.0):
    """Uma caixa (centro x, y, z; tamanho sx, sy, sz), girada `giro` rad em Z."""
    sx, sy, sz = (t / 2 for t in tam)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
         (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    o = bpy.data.objects.new(nome, malha(nome, v, f))
    o.location = centro
    o.rotation_euler = (0, 0, giro)
    if mat:
        o.data.materials.append(mat)
    return ligar(o)


def plano(nome, centro, tam, mat=None, normal="z"):
    sx, sy = tam[0] / 2, tam[1] / 2
    if normal == "z":
        v = [(-sx, -sy, 0), (sx, -sy, 0), (sx, sy, 0), (-sx, sy, 0)]
    elif normal == "-y":  # de pé, olhando para a câmera (-Y)
        v = [(-sx, 0, -sy), (sx, 0, -sy), (sx, 0, sy), (-sx, 0, sy)]
    else:  # "-z": olhando para baixo (o teto)
        v = [(-sx, -sy, 0), (-sx, sy, 0), (sx, sy, 0), (sx, -sy, 0)]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
    o = bpy.data.objects.new(nome, malha(nome, v, [(0, 1, 2, 3)], uvs))
    o.location = centro
    if mat:
        o.data.materials.append(mat)
    return ligar(o)


def tubo(nome, pontos, raio, mat, fechado=False, suave=False):
    """O tubo de neon: uma curva com espessura (bevel) pelos pontos."""
    c = bpy.data.curves.new(nome, "CURVE")
    c.dimensions = "3D"
    c.bevel_depth = raio
    c.bevel_resolution = 3
    c.use_fill_caps = True
    s = c.splines.new("NURBS" if suave else "POLY")
    s.points.add(len(pontos) - 1)
    for p, xyz in zip(s.points, pontos):
        p.co = (xyz[0], xyz[1], xyz[2], 1.0)
    s.use_cyclic_u = fechado
    if suave:
        s.order_u = 3
        s.use_endpoint_u = not fechado
        s.resolution_u = 12
    o = bpy.data.objects.new(nome, c)
    o.data.materials.append(mat)
    return ligar(o)


# ======================================================================
# OS MATERIAIS
# ======================================================================

def _nos(mat):
    mat.use_nodes = True
    return mat.node_tree.nodes, mat.node_tree.links


def mat_pbr(nome, cor, rug=0.5, metal=0.0, verniz=0.0, verniz_rug=0.05, espec=0.5):
    mat = bpy.data.materials.new(nome)
    nos, _ = _nos(mat)
    p = nos["Principled BSDF"]
    p.inputs["Base Color"].default_value = hex_linear(cor) if isinstance(cor, str) else cor
    p.inputs["Roughness"].default_value = rug
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = verniz
    p.inputs["Coat Roughness"].default_value = verniz_rug
    p.inputs["Specular IOR Level"].default_value = espec
    return mat


def mat_emissao(nome, cor, forca, forca_camera=None, amostrar=True):
    """O que acende (o neon, o LED, o disco da luminária).

    `forca_camera`: quanto a CÂMERA vê (o tubo de neon saturado, sem estourar no
    branco); o resto (o piso, as máquinas, o reflexo) recebe a `forca` toda.
    `amostrar=False`: o brilho só aparece (o disco da luminária, o bokeh); quem
    ilumina é a luz de verdade ao lado -- o render fica bem mais rápido.
    """
    mat = bpy.data.materials.new(nome)
    if not amostrar:
        mat.cycles.emission_sampling = "NONE"
    nos, links = _nos(mat)
    nos.remove(nos["Principled BSDF"])
    saida = nos["Material Output"]
    em = nos.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_linear(cor) if isinstance(cor, str) else cor
    em.inputs["Strength"].default_value = forca
    if forca_camera is None:
        links.new(em.outputs[0], saida.inputs["Surface"])
        return mat
    em2 = nos.new("ShaderNodeEmission")
    em2.inputs["Color"].default_value = em.inputs["Color"].default_value
    em2.inputs["Strength"].default_value = forca_camera
    caminho = nos.new("ShaderNodeLightPath")
    mix = nos.new("ShaderNodeMixShader")
    links.new(caminho.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(em.outputs[0], mix.inputs[1])
    links.new(em2.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], saida.inputs["Surface"])
    return mat


def mat_piso(cor, rug=0.2, verniz_rug=0.045, manchas=0.08, escala=1.0):
    """A resina polida: a cor viva com uma variação leve (o mosqueado da resina),
    o verniz quase espelho por cima e a rugosidade que varia um tanto (o polido real)."""
    mat = bpy.data.materials.new("piso-resina")
    nos, links = _nos(mat)
    p = nos["Principled BSDF"]
    base = hex_linear(cor)
    coord = nos.new("ShaderNodeTexCoord")
    ruido = nos.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 0.35 * escala
    ruido.inputs["Detail"].default_value = 6
    ruido.inputs["Roughness"].default_value = 0.6
    links.new(coord.outputs["Object"], ruido.inputs["Vector"])
    rampa = nos.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].position = 0.3
    rampa.color_ramp.elements[1].position = 0.7
    rampa.color_ramp.elements[0].color = tuple(c * (1 - manchas) for c in base[:3]) + (1,)
    rampa.color_ramp.elements[1].color = tuple(min(1, c * (1 + manchas)) for c in base[:3]) + (1,)
    links.new(ruido.outputs["Fac"], rampa.inputs["Fac"])
    links.new(rampa.outputs["Color"], p.inputs["Base Color"])
    # a rugosidade do verniz: quase espelho, com as marcas leves do polimento
    fino = nos.new("ShaderNodeTexNoise")
    fino.inputs["Scale"].default_value = 3.0 * escala
    fino.inputs["Detail"].default_value = 4
    links.new(coord.outputs["Object"], fino.inputs["Vector"])
    mapa = nos.new("ShaderNodeMapRange")
    mapa.inputs["To Min"].default_value = verniz_rug * 0.6
    mapa.inputs["To Max"].default_value = verniz_rug * 1.8
    links.new(fino.outputs["Fac"], mapa.inputs["Value"])
    links.new(mapa.outputs["Result"], p.inputs["Coat Roughness"])
    p.inputs["Roughness"].default_value = rug
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Coat IOR"].default_value = 1.5
    p.inputs["Specular IOR Level"].default_value = 0.5
    return mat


def mat_parede(cor, rug=0.55, textura=0.06):
    """A parede pintada (azul-marinho): fosca acetinada, com a textura leve da tinta."""
    mat = bpy.data.materials.new("parede")
    nos, links = _nos(mat)
    p = nos["Principled BSDF"]
    base = hex_linear(cor)
    coord = nos.new("ShaderNodeTexCoord")
    ruido = nos.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 1.2
    ruido.inputs["Detail"].default_value = 8
    links.new(coord.outputs["Object"], ruido.inputs["Vector"])
    rampa = nos.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].color = tuple(c * (1 - textura) for c in base[:3]) + (1,)
    rampa.color_ramp.elements[1].color = tuple(c * (1 + textura) for c in base[:3]) + (1,)
    links.new(ruido.outputs["Fac"], rampa.inputs["Fac"])
    links.new(rampa.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rug
    return mat


# ======================================================================
# O SALÃO
# ======================================================================

#: O salão padrão (cada cena muda o que quiser: cenas.py, `amb`).
AMBIENTE = {
    "piso": "#1838c8",          # a resina azul viva
    "piso_rug": 0.2,
    "parede": "#0b1450",        # o azul-marinho
    "teto": "#151c5c",
    "fundo": 11.0,              # a parede do fundo (m da câmera)
    "pe_direito": 3.8,
    "neon": ["azul", "magenta", "ciano", "amarelo"],
    "estilo": "linhas",         # linhas | diagonais | arcos | ondas | pontos
    "neon_forca": 14.0,
    "neon_camera": 2.2,
    "luz_teto": 4200,           # K
    "spot_w": 420,
    "frente_w": 1300,           # a luz geral da frente (o "softbox" do fotógrafo, atrás da câmera)
    "lavar_w": 260,             # os LEDs escondidos que lavam a parede do fundo (W por trecho de 4 m)
    "abertura": (2.6, 9.0),     # a parte da parede aberta para o shopping (x de, até) ou None
    "bokeh": 70,                # quantas luzes ao longe
    "semente": 7,
    "lados": True,              # as paredes dos lados (com os LEDs verticais)
    "faixa_rodape": True,       # o LED no pé da parede, lavando para cima
}


def kelvin(k):
    """A cor (linear) de uma luz branca de k kelvins (aproximação de Tanner Helland)."""
    t = k / 100
    r = 255 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    srgb = [max(0, min(255, v)) / 255 for v in (r, g, b)]
    return tuple((c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in srgb)


def luz(nome, tipo, pos, energia, cor=(1, 1, 1), tam=0.1, rot=(0, 0, 0), spot=None, spread=None, forma="DISK"):
    d = bpy.data.lights.new(nome, tipo)
    d.energy = energia
    d.color = cor[:3]
    if tipo == "AREA":
        d.shape = forma
        if forma in ("RECTANGLE", "ELLIPSE"):
            d.size, d.size_y = tam
        else:
            d.size = tam
        if spread is not None:
            d.spread = spread
    elif tipo in ("POINT", "SPOT"):
        d.shadow_soft_size = tam
    if tipo == "SPOT" and spot:
        d.spot_size, d.spot_blend = spot
    o = bpy.data.objects.new(nome, d)
    o.location = pos
    o.rotation_euler = rot
    return ligar(o)


def ambiente(op=None):
    """Monta o salão. Devolve o dicionário do ambiente usado (com os padrões)."""
    a = dict(AMBIENTE)
    a.update(op or {})
    rnd = random.Random(a["semente"])
    fundo, pd = a["fundo"], a["pe_direito"]

    # o mundo: escuro (a luz é a do salão)
    w = bpy.data.worlds.new("mundo")
    bpy.context.scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = hex_linear("#050816")
    w.node_tree.nodes["Background"].inputs[1].default_value = a.get("mundo", 1.0)

    # o piso de resina
    plano("piso", (0, fundo / 2 + 10, 0), (80, fundo + 40), mat_piso(a["piso"], a["piso_rug"]))

    # a parede do fundo (com a abertura para o shopping, se houver)
    parede = mat_parede(a["parede"])
    x0, x1 = -22.0, 22.0
    if a["abertura"]:
        ab0, ab1 = a["abertura"]
        caixa("parede-fundo-esq", ((x0 + ab0) / 2, fundo + 0.1, pd / 2), (ab0 - x0, 0.2, pd), parede)
        caixa("parede-fundo-dir", ((ab1 + x1) / 2, fundo + 0.1, pd / 2), (x1 - ab1, 0.2, pd), parede)
        # a viga em cima da abertura (com o LED)
        caixa("viga-abertura", ((ab0 + ab1) / 2, fundo + 0.1, pd - 0.35), (ab1 - ab0, 0.25, 0.7), parede)
        zona_distante(a, rnd, ab0, ab1)
    else:
        caixa("parede-fundo", (0, fundo + 0.1, pd / 2), (x1 - x0, 0.2, pd), parede)

    # as paredes dos lados (longe da câmera: mais ar do que parede) e o teto
    if a["lados"]:
        lado = a.get("lado_x", 9.5)
        for s in (-1, 1):
            caixa(f"parede-lado{s}", (s * lado, fundo / 2, pd / 2), (0.2, fundo + 8, pd), parede)
    teto = mat_pbr("teto", a["teto"], rug=0.7)
    plano("teto", (0, fundo / 2, pd), (60, fundo + 30), teto, normal="-z")

    neon_da_parede(a, rnd)
    luminarias(a, rnd)

    # a luz geral da frente: o "softbox" atrás e acima da câmera (as frentes das máquinas acesas)
    if a["frente_w"]:
        luz("frente", "AREA", (0, -3.5, 3.2), a["frente_w"], kelvin(5200), tam=(6.0, 2.0),
            rot=(math.radians(68), 0, 0), forma="RECTANGLE")
    return a


def _cores(a):
    return [MARCA.get(c, c) for c in a["neon"]]


def neon_da_parede(a, rnd):
    """As linhas de LED/neon da parede do fundo, que iluminam a cena de verdade."""
    fundo, pd = a["fundo"], a["pe_direito"]
    y = fundo - 0.03
    cores = _cores(a)
    mats = [mat_emissao(f"neon-{i}", c, a["neon_forca"], a["neon_camera"]) for i, c in enumerate(cores)]
    ab = a["abertura"]

    def trechos(xa, xb):
        """O trecho [xa, xb] sem a abertura."""
        if not ab:
            return [(xa, xb)]
        out = []
        if xa < ab[0]:
            out.append((xa, min(xb, ab[0] - 0.15)))
        if xb > ab[1]:
            out.append((max(xa, ab[1] + 0.15), xb))
        return [t for t in out if t[1] - t[0] > 0.3]

    # os LEDs escondidos na sanca e no rodapé que LAVAM a parede: o azul-marinho ganha o degradê
    # de luz da cor do neon (a parede não fica preta nem chapada)
    if a["lavar_w"]:
        cor_cima = hex_linear(cores[0])[:3]
        cor_baixo = hex_linear(cores[1 % len(cores)])[:3]
        for xa, xb in trechos(-16, 16):
            n = max(1, round((xb - xa) / 4))
            for i in range(n):
                xc = xa + (i + 0.5) * (xb - xa) / n
                tam = ((xb - xa) / n * 0.95, 0.12)
                luz(f"lavar-cima{xc:.1f}", "AREA", (xc, fundo - 0.45, pd - 0.08), a["lavar_w"], cor_cima, tam=tam,
                    rot=(math.radians(55), 0, 0), forma="RECTANGLE")
                luz(f"lavar-baixo{xc:.1f}", "AREA", (xc, fundo - 0.35, 0.05), a["lavar_w"] * 0.7, cor_baixo, tam=tam,
                    rot=(math.radians(125), 0, 0), forma="RECTANGLE")

    est = a["estilo"]
    if a["faixa_rodape"]:
        # o LED no rodapé lavando a parede para cima (a luz sobe na tinta)
        for xa, xb in trechos(-14, 14):
            tubo("rodape", [(xa, y - 0.05, 0.06), (xb, y - 0.05, 0.06)], 0.018, mats[0])
    if est == "linhas":
        alturas = [pd - 0.55, pd - 0.85, 1.05]
        for k, h in enumerate(alturas):
            m = mats[(k + 1) % len(mats)]
            for xa, xb in trechos(-14, 14):
                tubo(f"linha{k}", [(xa, y, h), (xb, y, h)], 0.014, m)
        # os riscos verticais entre as linhas
        for i, x in enumerate(np.arange(-8.5, 8.6, 1.7)):
            if ab and ab[0] - 0.2 < x < ab[1] + 0.2:
                continue
            tubo(f"vert{i}", [(x, y, 1.25), (x, y, pd - 1.05)], 0.012, mats[i % len(mats)])
    elif est == "diagonais":
        # as faixas de velocidade (esporte): diagonais paralelas em grupos de três
        for g, x in enumerate(np.arange(-12, 12, 2.6)):
            for k in range(3):
                xa = x + k * 0.32
                if ab and ab[0] - 1.6 < xa < ab[1] + 0.4:
                    continue
                tubo(f"diag{g}{k}", [(xa, y, 0.5), (xa + 1.3, y, pd - 0.6)], 0.016, mats[(g + k) % len(mats)])
        for xa, xb in trechos(-14, 14):
            tubo("linha-alta", [(xa, y, pd - 0.35), (xb, y, pd - 0.35)], 0.014, mats[1 % len(mats)])
    elif est == "arcos":
        # os círculos e os arcos de neon (fliperama), dois a dois, um dentro do outro
        for i, x in enumerate(np.arange(-10, 10.5, 2.6)):
            if ab and ab[0] - 1.4 < x < ab[1] + 1.4:
                continue
            h = 2.05 + (0.25 if i % 2 else -0.1)
            r = 0.62 if i % 2 else 0.5
            pts = [(x + r * math.cos(t), y, h + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 64, endpoint=False)]
            tubo(f"aro{i}", pts, 0.014, mats[i % len(mats)], fechado=True)
            r2 = r * 0.7
            pts = [(x + r2 * math.cos(t), y, h + r2 * math.sin(t)) for t in np.linspace(0.3, math.pi * 1.4, 40)]
            tubo(f"arco{i}", pts, 0.012, mats[(i + 1) % len(mats)])
        for xa, xb in trechos(-14, 14):
            tubo("linha-alta", [(xa, y, pd - 0.4), (xb, y, pd - 0.4)], 0.014, mats[2 % len(mats)])
            tubo("linha-baixa", [(xa, y, 0.9), (xb, y, 0.9)], 0.012, mats[3 % len(mats)])
    elif est == "ondas":
        # as ondas suaves (os pequenos), em três cores
        for k, h in enumerate((pd - 0.6, pd - 1.0)):
            for xa, xb in trechos(-14, 14):
                n = max(4, int((xb - xa) / 0.5))
                pts = [(xa + (xb - xa) * i / n, y, h + 0.16 * math.sin(i * 1.3 + k)) for i in range(n + 1)]
                tubo(f"onda{k}", pts, 0.016, mats[(k + 1) % len(mats)], suave=True)
        for i, x in enumerate(np.arange(-9, 9.5, 2.25)):
            if ab and ab[0] - 0.6 < x < ab[1] + 0.6:
                continue
            r = 0.34
            h = 1.65
            pts = [(x + r * math.cos(t), y, h + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]
            tubo(f"bola{i}", pts, 0.014, mats[i % len(mats)], fechado=True)
    elif est == "pontos":
        # as fileiras de luzinhas (as lâmpadas de festa) e as linhas
        for xa, xb in trechos(-14, 14):
            tubo("linha-alta", [(xa, y, pd - 0.45), (xb, y, pd - 0.45)], 0.014, mats[0])
        mat_b = mat_emissao("lampadinha", "#ffd27a", 18, 3.0, amostrar=False)
        for xa, xb in trechos(-14, 14):
            for x in np.arange(xa + 0.2, xb, 0.42):
                bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, location=(x, y - 0.06, pd - 0.75), segments=12, ring_count=6)
                bpy.context.object.data.materials.append(mat_b)

    # os LEDs verticais nas paredes dos lados (as linhas que fogem para o fundo)
    if a["lados"]:
        lado = a.get("lado_x", 9.5)
        for s in (-1, 1):
            for k, h in enumerate((pd - 0.5, 0.9)):
                tubo(f"lado{s}{k}", [(s * (lado - 0.12), 1.0, h), (s * (lado - 0.12), fundo - 0.2, h)], 0.014,
                     mats[(k + (s > 0)) % len(mats)])


def luminarias(a, rnd):
    """O teto: as luminárias embutidas (o disco aceso e o foco que desce) e os perfis de LED."""
    fundo, pd = a["fundo"], a["pe_direito"]
    lado = a.get("lado_x", 9.5)
    cor = kelvin(a["luz_teto"])
    disco = mat_emissao("downlight", (cor[0], cor[1], cor[2], 1), 40.0, 6.0, amostrar=False)
    aro = mat_pbr("aro-luminaria", "#1a1f2e", rug=0.3, metal=0.8)
    passo = a.get("passo_luz", 2.2)
    meio = (lado - 1.0) // passo * passo
    for x in np.arange(-meio, meio + 0.01, passo):
        for y in np.arange(passo, fundo - 0.5, passo):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.02, location=(x, y, pd - 0.006), vertices=32)
            bpy.context.object.data.materials.append(disco)
            bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=0.012, location=(x, y, pd - 0.002), vertices=32)
            bpy.context.object.data.materials.append(aro)
            luz(f"spot{x:.1f}{y:.1f}", "SPOT", (x, y, pd - 0.03), a["spot_w"], cor, tam=0.06,
                spot=(math.radians(70), 0.6))
    # os perfis de LED do teto, correndo para o fundo (as linhas que dão a profundidade)
    perfil = mat_emissao("perfil-teto", (cor[0], cor[1], cor[2], 1), 9.0, 2.6)
    for x in (-(meio + passo / 2), meio + passo / 2):
        caixa(f"perfil{x}", (x, fundo / 2 + 0.5, pd - 0.02), (0.06, fundo - 1.0, 0.025), perfil)
    cores = _cores(a)
    if len(cores) > 1:
        caixa("perfil-cor", (0, fundo - 1.2, pd - 0.02), (2 * meio, 0.05, 0.025),
              mat_emissao("perfil-cor", cores[1], 10.0, 2.4))


def zona_distante(a, rnd, x0, x1):
    """Pela abertura: o corredor do shopping lá longe -- o chão, o fundo e as luzes que viram bokeh."""
    fundo, pd = a["fundo"], a["pe_direito"]
    longe = fundo + 30
    meio = (x0 + x1) / 2
    caixa("fundo-longe", (meio, longe, 4), (60, 0.3, 8), mat_parede("#0b0f3a"))
    caixa("teto-longe", (meio, (fundo + longe) / 2, pd + 1.6), (60, longe - fundo, 0.2), mat_pbr("teto-l", "#05060f", rug=0.9))
    # as luzes do shopping lá longe: pontos quentes e alguns da cor da marca -- a lente desfoca (o bokeh)
    cores = ["#ffc46b", "#ffb36b", "#ffe0a8", "#ffd27a", MARCA["ciano"], MARCA["magenta"], MARCA["azul"], "#fff3dc"]
    mats = [mat_emissao(f"bokeh{i}", c, 30.0, 7.0, amostrar=False) for i, c in enumerate(cores)]
    for i in range(a["bokeh"]):
        x = rnd.uniform(x0 - 6, x1 + 6)
        y = rnd.uniform(fundo + 10, longe - 1)
        z = rnd.uniform(0.8, pd + 1.2)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=rnd.uniform(0.08, 0.2), location=(x, y, z), segments=12, ring_count=6)
        bpy.context.object.data.materials.append(rnd.choice(mats))
    # as fachadas acesas lá longe: só o brilho morno, baixo (nada escrito, nenhuma marca)
    for i in range(7):
        x = x0 - 6 + i * 4.2
        caixa(f"vitrine{i}", (x, longe - 0.2, 1.4), (3.0, 0.05, 2.0),
              mat_emissao(f"vitrine{i}", rnd.choice(["#ffcf8a", "#ffe2b8", "#f7c98f"]), 1.2, 0.55, amostrar=False))
    luz("luz-longe", "AREA", (meio, fundo + 14, pd + 1.4), 900, kelvin(3400), tam=(16, 12),
        rot=(0, 0, 0), forma="RECTANGLE")


# ======================================================================
# A CÂMERA
# ======================================================================

def camera(altura=1.55, lente=40, giro=0.0, desloc_y=-0.1, desloc_x=0.0, foco=5.0, f=2.8, x=0.0, y=0.0,
           inclinar=0.0):
    """A câmera nivelada (as verticais retas), na altura dos olhos; o enquadramento sobe/desce pelo
    deslocamento da lente (`desloc_y`, como a lente de arquitetura). `giro`: graus para a direita."""
    sc = bpy.context.scene
    dados = bpy.data.cameras.new("camera")
    dados.lens = lente
    dados.sensor_fit = "HORIZONTAL"
    dados.sensor_width = 36
    dados.shift_y = desloc_y
    dados.shift_x = desloc_x
    dados.clip_start = 0.05
    dados.clip_end = 200
    dados.dof.use_dof = f is not None
    if f is not None:
        dados.dof.focus_distance = foco
        dados.dof.aperture_fstop = f
        dados.dof.aperture_blades = 7
        dados.dof.aperture_rotation = math.radians(10)
    cam = bpy.data.objects.new("camera", dados)
    cam.location = (x, y, altura)
    cam.rotation_euler = (math.radians(90 - inclinar), 0, -math.radians(giro))
    ligar(cam)
    sc.camera = cam
    return cam


# ======================================================================
# AS MÁQUINAS
# ======================================================================

def _virada(pos, cam, giro):
    """A direção da frente da máquina em `pos`: para a câmera, girada `giro` graus.

    `giro` positivo = a câmera fica à direita de quem olha a máquina de frente (a
    lateral direita aparece), como nas fotos do catálogo. Devolve o ângulo em Z
    (rad) que leva a frente do modelo (-Y) para essa direção.
    """
    n = Vector((cam.location.x - pos[0], cam.location.y - pos[1])).normalized()
    g = math.radians(-giro)
    f = Vector((n.x * math.cos(g) - n.y * math.sin(g), n.x * math.sin(g) + n.y * math.cos(g)))
    return math.atan2(f.x, -f.y)


def _caixa_do(objetos):
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in objetos:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    return mn, mx


#: O que acende nos nossos .glb (pelo nome do material).
_LED = ("led_pontos", "fita-de-led", "neon", "placar", "digitos", "tela-do-jogo", "monitor", "botao-start", "botao_vermelho")


def melhorar_materiais(objetos, chave):
    """Os adesivos viram vinil brilhante (rugosidade ~0,25 + verniz); os LEDs e as telas acendem;
    o plástico rotomoldado fica acetinado. O .glb no disco não muda (só a cena)."""
    vistos = set()
    for o in objetos:
        for slot in getattr(o, "material_slots", []):
            m = slot.material
            if not m or m.name in vistos or not m.node_tree:
                continue
            vistos.add(m.name)
            p = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if p is None:
                continue
            nome = m.name.lower().split(".")[0]  # (o .glb importado de novo ganha ".001")
            tem_textura = any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes)
            emite = p.inputs["Emission Strength"].default_value > 0
            if emite or any(k in nome for k in _LED):
                if not p.inputs["Emission Color"].is_linked:
                    base = p.inputs["Base Color"]
                    if base.is_linked:
                        m.node_tree.links.new(base.links[0].from_socket, p.inputs["Emission Color"])
                    else:
                        p.inputs["Emission Color"].default_value = base.default_value
                atual = p.inputs["Emission Strength"].default_value or 1.0
                tela = any(k in nome for k in ("tela", "placar", "monitor")) or (chave == "strike-kids" and nome == "material_7")
                # o LED e o neon acesos de verdade (iluminam o que está perto); a tela, só acesa
                p.inputs["Emission Strength"].default_value = max(atual, 1.4) if tela else max(atual, 4.0)
                p.inputs["Roughness"].default_value = 0.2
                p.inputs["Coat Weight"].default_value = 0.4
                continue
            if nome.startswith("adesivo") or (tem_textura and chave == "strike-kids") or "arte" in nome or "painel" in nome or "placa" in nome:
                p.inputs["Roughness"].default_value = 0.25
                p.inputs["Coat Weight"].default_value = 0.8
                p.inputs["Coat Roughness"].default_value = 0.04
                continue
            if any(k in nome for k in ("tela-protecao", "rede", "vidro", "tela-verde", "tela-quadras")):
                continue
            if not tem_textura and p.inputs["Metallic"].default_value < 0.3:
                # o plástico e a pintura: acetinado, com um verniz leve
                p.inputs["Roughness"].default_value = min(p.inputs["Roughness"].default_value, 0.38)
                p.inputs["Coat Weight"].default_value = max(p.inputs["Coat Weight"].default_value, 0.25)
                p.inputs["Coat Roughness"].default_value = 0.08


def glb(chave, x, y, giro=0.0, cam=None, rot=None):
    """Um .glb nosso de pé no chão em (x, y), virado para a câmera com `giro` graus (ou `rot`, graus absolutos)."""
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(MODELOS / f"{chave}.glb"))
    novos = [o for o in bpy.data.objects if o not in antes]
    raiz = bpy.data.objects.new(f"glb-{chave}", None)
    ligar(raiz)
    for o in novos:
        if o.parent is None:
            o.parent = raiz
    bpy.context.view_layer.update()
    mn, mx = _caixa_do(novos)
    # o pé no chão (z mínimo = 0) e o centro da planta na origem do grupo
    for o in novos:
        if o.parent is raiz:
            o.location -= Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    raiz.location = (x, y, 0)
    ang = math.radians(rot) if rot is not None else _virada((x, y), cam or bpy.context.scene.camera, giro)
    raiz.rotation_euler = (0, 0, ang)
    melhorar_materiais(novos, chave)
    bpy.context.view_layer.update()
    for o in novos:
        if o.type == "MESH":
            o.visible_shadow = True
    return {
        "tipo": "glb", "chave": chave, "nome": GLB_NOME.get(chave, chave), "objetos": novos, "raiz": raiz,
        "planta": (mx.x - mn.x, mx.y - mn.y), "altura": mx.z - mn.z, "pos": (x, y), "angulo": ang,
    }


# ---------------------------------------------------------------- os recortes

def _alfa_bbox(im, limiar=128):
    return im.getchannel("A").point(lambda v: 255 if v >= limiar else 0).getbbox()


def _borrar(arr, raio):
    """Desfoque de caixa separável (três passadas ~ gaussiano), em numpy (H x W x C)."""
    out = arr.astype(np.float32)
    for _ in range(3):
        for eixo in (0, 1):
            pad = [(0, 0)] * out.ndim
            pad[eixo] = (raio + 1, raio)
            c = np.cumsum(np.pad(out, pad, mode="edge"), axis=eixo)
            n = out.shape[eixo]
            out = (np.take(c, range(2 * raio + 1, 2 * raio + 1 + n), axis=eixo) - np.take(c, range(0, n), axis=eixo)) / (2 * raio + 1)
    return out


def _sangrar(arr):
    """Preenche a cor dos pixels transparentes com a cor da borda (sem a franja escura/branca no filtro)."""
    rgb = arr[..., :3].astype(np.float32)
    a = arr[..., 3:4].astype(np.float32) / 255.0
    acum = rgb * a
    feito = a >= 0.02
    for raio in (2, 6, 16, 40):
        borr = _borrar(acum, raio)
        pb = _borrar(a, raio)
        cor = borr / np.maximum(pb, 1e-6)
        novo = (~feito) & (pb > 1e-4)
        rgb = np.where(novo, cor, rgb)
        feito = feito | novo
    out = arr.copy()
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out


def preparar_recorte(origem, chave, altura_min=1500, saturacao=1.06):
    """O recorte cortado na caixa do alfa (a borda de baixo é a base da máquina), ampliado
    sem franja (pré-multiplicado), um tanto mais nítido e vivo. Devolve (caminho, aspecto, contato):
    `contato` é onde (0-1, da esquerda) a máquina encosta no chão na foto (o pé mais baixo)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / f"{chave}.png"
    im = Image.open(origem).convert("RGBA")
    caixa_alfa = _alfa_bbox(im)
    im = im.crop(caixa_alfa)
    w, h = im.size
    # onde a máquina encosta no chão na foto: as colunas cujo pixel opaco mais baixo está
    # a menos de 2% da altura da borda de baixo (de, até: 0-1 da esquerda)
    a = np.asarray(im.getchannel("A")) >= 128
    tem = a.any(axis=0)
    baixo = np.where(tem, h - 1 - np.argmax(a[::-1], axis=0), -1)
    xs = np.nonzero(baixo >= h - 1 - max(2, int(h * 0.02)))[0]
    contato = (float(xs.min() / w), float(xs.max() / w)) if len(xs) else (0.0, 1.0)
    if not destino.exists() or destino.stat().st_mtime < Path(origem).stat().st_mtime:
        if h < altura_min:
            fator = altura_min / h
            im = im.convert("RGBa").resize((round(w * fator), round(h * fator)), Image.LANCZOS).convert("RGBA")
        cor = im.convert("RGB")
        cor = ImageEnhance.Color(cor).enhance(saturacao)
        cor = cor.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
        im = Image.merge("RGBA", (*cor.split(), im.getchannel("A")))
        im = Image.fromarray(_sangrar(np.asarray(im)))
        im.save(destino)
    return destino, w / h, contato


def _projecao(cam_l, pontos):
    """Projeta (da câmera, em coordenadas do plano: o plano é y = 0) os pontos no plano."""
    out = []
    for p in pontos:
        d = p - cam_l
        t = -cam_l.y / d.y if d.y > 1e-9 else 1e4  # (o ponto atrás da câmera: muito longe)
        q = cam_l + d * t
        out.append((q.x, q.z))
    return out


def _mat_recorte(nome, imagem, emissao, plano_obj=None, cam_l=None, extensao=None):
    """O material do recorte: a cor da foto, metade emitida (a foto como ela é) e metade acesa
    pela luz do salão (pega a cor do neon); o alfa recorta. No plano, as coordenadas são as do
    plano (UV); na caixa-sombra, a foto PROJETADA DA CÂMERA através do plano."""
    mat = bpy.data.materials.new(nome)
    nos, links = _nos(mat)
    nos.remove(nos["Principled BSDF"])
    saida = nos["Material Output"]
    tex = nos.new("ShaderNodeTexImage")
    tex.image = imagem
    tex.interpolation = "Cubic"
    tex.extension = "CLIP"
    if plano_obj is not None:
        u0, u1, v1 = extensao
        coord = nos.new("ShaderNodeTexCoord")
        coord.object = plano_obj
        sub = nos.new("ShaderNodeVectorMath")
        sub.operation = "SUBTRACT"
        links.new(coord.outputs["Object"], sub.inputs[0])
        sub.inputs[1].default_value = cam_l
        sep = nos.new("ShaderNodeSeparateXYZ")
        links.new(sub.outputs[0], sep.inputs[0])
        # t = -cy / dy
        div = nos.new("ShaderNodeMath")
        div.operation = "DIVIDE"
        div.inputs[0].default_value = -cam_l.y
        links.new(sep.outputs["Y"], div.inputs[1])
        esc = nos.new("ShaderNodeVectorMath")
        esc.operation = "SCALE"
        links.new(sub.outputs[0], esc.inputs[0])
        links.new(div.outputs[0], esc.inputs["Scale"])
        soma = nos.new("ShaderNodeVectorMath")
        soma.operation = "ADD"
        links.new(esc.outputs[0], soma.inputs[0])
        soma.inputs[1].default_value = cam_l
        sep2 = nos.new("ShaderNodeSeparateXYZ")
        links.new(soma.outputs[0], sep2.inputs[0])
        u = nos.new("ShaderNodeMapRange")
        u.inputs["From Min"].default_value = u0
        u.inputs["From Max"].default_value = u1
        u.clamp = False
        links.new(sep2.outputs["X"], u.inputs["Value"])
        v = nos.new("ShaderNodeMapRange")
        v.inputs["From Min"].default_value = 0.0
        v.inputs["From Max"].default_value = v1
        v.clamp = False
        links.new(sep2.outputs["Z"], v.inputs["Value"])
        uv = nos.new("ShaderNodeCombineXYZ")
        links.new(u.outputs["Result"], uv.inputs["X"])
        links.new(v.outputs["Result"], uv.inputs["Y"])
        links.new(uv.outputs[0], tex.inputs["Vector"])
    difuso = nos.new("ShaderNodeBsdfPrincipled")
    difuso.inputs["Roughness"].default_value = 0.42
    difuso.inputs["Specular IOR Level"].default_value = 0.25
    links.new(tex.outputs["Color"], difuso.inputs["Base Color"])
    em = nos.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    links.new(tex.outputs["Color"], em.inputs["Color"])
    mix = nos.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = emissao
    links.new(difuso.outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    transp = nos.new("ShaderNodeBsdfTransparent")
    alfa = nos.new("ShaderNodeMixShader")
    links.new(tex.outputs["Alpha"], alfa.inputs["Fac"])
    links.new(transp.outputs[0], alfa.inputs[1])
    links.new(mix.outputs[0], alfa.inputs[2])
    links.new(alfa.outputs[0], saida.inputs["Surface"])
    return mat


def foto(chave, x, y, cam=None, giro=None, fundo=None, altura=None, emissao=0.40, origem=None, nome=None, redonda=False):
    """A máquina do catálogo em foto, de pé em (x, y) -- (x, y) é o centro da PLANTA da máquina.

    O plano da foto fica de pé, de frente para a câmera, passando pelo canto da
    máquina mais perto dela; a borda de baixo da foto (a caixa do alfa) fica no
    chão. A caixa-sombra (largura x fundo x altura de verdade) fica atrás: ela faz a
    sombra, o contato e o reflexo, com a foto projetada da câmera.
    """
    cam = cam or bpy.context.scene.camera
    g_foto, _alt_foto, fundo_padrao = FOTOS.get(chave, (0, 8, 0.8))
    D0 = fundo or fundo_padrao
    if altura is None:
        altura = FICHA[chave]["altura"] if chave in FICHA else PECAS[chave]["altura"]
    H = altura
    caminho, aspecto, contato = preparar_recorte(origem or (RECORTES / f"{chave}.webp"), chave)
    C = cam.location.copy()
    centro = Vector((x, y, 0))
    m = Vector((x - C.x, y - C.y, 0)).normalized()   # da câmera para a máquina (o normal do plano)
    r = Vector((m.y, -m.x, 0))                        # a direita de quem olha
    M = Matrix((r, m, Vector((0, 0, 1)))).transposed()   # colunas: x=r, y=m, z=up
    Minv = M.inverted()

    def medir(g, W, D):
        """A caixa W x D x H virada `g` graus: o canto mais perto e a projeção dela no plano."""
        R = Matrix.Rotation(_virada((x, y), cam, g), 3, "Z")
        if redonda:  # a máquina redonda (o carrossel): o cilindro de diâmetro W
            cantos = [centro + Vector((W / 2 * math.cos(t), W / 2 * math.sin(t), z))
                      for t in np.linspace(0, 2 * math.pi, 48, endpoint=False) for z in (0, H)]
        else:
            cantos = [centro + R @ Vector((sx * W / 2, sy * D / 2, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, H)]
        perto = min((c for c in cantos if c.z == 0), key=lambda c: (c - C).dot(m))
        cam_l = Minv @ (C - perto)
        proj = _projecao(cam_l, [Minv @ (c - perto) for c in cantos])
        us = [q[0] for q in proj]
        return perto, cam_l, min(us), max(us), max(q[1] for q in proj)

    def largura(g, D):
        """A largura que faz a caixa projetada ter o formato da foto (bisseção); devolve (W, D)."""
        def razao(W):
            _p, _c, u0, u1, v1 = medir(g, W, D)
            return (u1 - u0) / v1
        while razao(0.05) > aspecto and D > 0.1:
            D *= 0.85
        lo, hi = 0.05, 40.0
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if razao(mid) < aspecto else (lo, mid)
        return (lo + hi) / 2, D

    def canto(g, D):
        W, D = largura(g, D)
        _p, _c, u0, u1, _v = medir(g, W, D)
        return -u0 / (u1 - u0)

    # O ÂNGULO DA FOTO, MEDIDO NELA: quando a base tem um canto (o pé da foto estreito), o
    # canto mais perto da caixa tem de cair nele. Procura em todo ângulo (de grau em grau,
    # os dois lados) o que põe o canto no pé da foto, preferindo o lado de FOTOS (o lado
    # que a foto mostra, conferido no olho) e o ângulo de foto de produto (até ~60 graus).
    # Base lisa ou redonda (o pé largo): fica o ângulo de FOTOS.
    giro_usado = g_foto if giro is None else giro
    medido = False
    if giro is None and not redonda and contato[1] - contato[0] < 0.25:
        def erro(g):  # o quanto o canto cai fora do pé da foto (0 = dentro)
            c = canto(g, D0)
            return max(0.0, contato[0] - c, c - contato[1])

        melhor = None
        for g in range(-85, 86):
            if abs(g) < 2:
                continue
            e = erro(g)
            custo = (e + (0.06 if (g > 0) != (g_foto > 0) else 0) + (0.25 if abs(g) > 62 else 0)
                     + 0.002 * abs(abs(g) - abs(g_foto)))
            if e < 0.05 and (melhor is None or custo < melhor[0]):
                melhor = (custo, g)
        if melhor:
            giro_usado = float(melhor[1])
            medido = True
    W, D = largura(giro_usado, D0)
    ang = _virada((x, y), cam, giro_usado)
    perto, cam_l, u0, u1, v1 = medir(giro_usado, W, D)

    # o plano da foto (de pé, no canto mais perto; a borda de baixo no chão)
    verts = [(u0, 0, 0), (u1, 0, 0), (u1, 0, v1), (u0, 0, v1)]
    plano_obj = bpy.data.objects.new(f"foto-{chave}", malha(f"foto-{chave}", verts, [(0, 1, 2, 3)], [(0, 0), (1, 0), (1, 1), (0, 1)]))
    plano_obj.matrix_world = Matrix.Translation(perto) @ M.to_4x4()
    ligar(plano_obj)
    img = bpy.data.images.load(str(caminho), check_existing=True)
    img.alpha_mode = "STRAIGHT"
    plano_obj.data.materials.append(_mat_recorte(f"foto-{chave}", img, emissao))
    plano_obj.visible_diffuse = False
    plano_obj.visible_glossy = False
    plano_obj.visible_transmission = False
    plano_obj.visible_volume_scatter = False
    plano_obj.visible_shadow = False

    # a caixa-sombra: a máquina de verdade (invisível para a câmera), com a foto projetada
    if redonda:
        D = W
        bpy.ops.mesh.primitive_cylinder_add(radius=W / 2, depth=H, location=(x, y, H / 2), vertices=48)
        sombra = bpy.context.object
        sombra.name = f"sombra-{chave}"
    else:
        sombra = caixa(f"sombra-{chave}", (x, y, H / 2), (W, D, H), giro=ang)
    sombra.data.materials.append(_mat_recorte(f"sombra-{chave}", img, emissao, plano_obj, cam_l, (u0, u1, v1)))
    sombra.visible_camera = False
    sombra.visible_transmission = False

    # conferências: o pé da foto e o canto mais perto da caixa devem cair no mesmo lugar
    canto_u = (0 - u0) / (u1 - u0)
    alerta = contato[1] - contato[0] < 0.4 and not (contato[0] - 0.12 <= canto_u <= contato[1] + 0.12)
    giro = giro_usado
    elev = math.degrees(math.atan2(C.z - H / 2, (Vector((x, y, 0)) - Vector((C.x, C.y, 0))).length))
    rumo = math.degrees(ang)
    print(f"  {chave}: {W:.2f} x {D:.2f} x {H:.2f} m, foto {aspecto:.2f}, canto {canto_u:.2f} / pé da foto {contato[0]:.2f}-{contato[1]:.2f}"
          f"{'  <-- CONFERIR O GIRO' if alerta else ''}; giro {giro:.0f}{' (medido)' if medido else ''}; elevação {elev:.0f} (foto {_alt_foto}); frente para {rumo:.0f} graus")
    return {
        "tipo": "foto", "chave": chave, "nome": nome or (FICHA.get(chave) or PECAS.get(chave))["nome"],
        "objetos": [plano_obj, sombra], "plano": plano_obj, "sombra": sombra,
        "planta": (W, D), "altura": H, "pos": (x, y), "angulo": ang, "alerta": alerta, "giro": giro,
    }


def peca(chave, x, y, z0=0.0, cam=None, altura=None, fundo=None, alto=None, emissao=0.5, inclinar=True, recuo=0.0):
    """A peça de reposição em foto (ferramentas/categorias/reposicao/), de pé no balcão em (x, y, z0).

    A foto da peça é de cima (a maioria) ou de frente: o plano fica perpendicular ao
    olhar da câmera (inclinado para trás o quanto a câmera olha de cima), com a borda
    de baixo da caixa do alfa no balcão. `altura`: a altura da foto (reposicao/pecas.json);
    `alto` e `fundo`: o tamanho de verdade da peça para a caixa-sombra (a sombra, o
    contato e o reflexo no balcão), que recebe a foto projetada da câmera.
    """
    cam = cam or bpy.context.scene.camera
    L = altura or PECAS[chave]["altura"]
    caminho, aspecto, _contato = preparar_recorte(REPOSICAO / f"{chave}.webp", f"peca-{chave}", altura_min=900)
    Wp = L * aspecto
    C = cam.location.copy()
    base = Vector((x, y, z0))
    plano_m = Vector((x - C.x, y - C.y, 0)).normalized()
    r = Vector((plano_m.y, -plano_m.x, 0))
    # o normal do plano: o olhar da câmera até o pé (o plano de frente para ela)
    olhar = (base - C).normalized() if inclinar else plano_m
    n = (olhar - olhar.dot(r) * r).normalized()
    up = r.cross(n).normalized()
    if up.z < 0:
        up = -up
    M = Matrix((r, n, up)).transposed()
    plano_obj = bpy.data.objects.new(
        f"peca-{chave}-{x:.2f}",
        malha(f"peca-{chave}", [(-Wp / 2, 0, 0), (Wp / 2, 0, 0), (Wp / 2, 0, L), (-Wp / 2, 0, L)], [(0, 1, 2, 3)],
              [(0, 0), (1, 0), (1, 1), (0, 1)]))
    plano_obj.matrix_world = Matrix.Translation(base) @ M.to_4x4()
    ligar(plano_obj)
    img = bpy.data.images.load(str(caminho), check_existing=True)
    img.alpha_mode = "STRAIGHT"
    plano_obj.data.materials.append(_mat_recorte(f"peca-{chave}", img, emissao))
    for prop in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter", "visible_shadow"):
        setattr(plano_obj, prop, False)
    # a caixa-sombra atrás do pé (o tamanho de verdade), com a foto projetada
    hp = alto or L * 0.6
    dp = fundo or Wp * 0.7
    wp = Wp * 0.92
    centro = base + plano_m * (dp / 2 + recuo) + Vector((0, 0, hp / 2))
    ang = math.atan2(-plano_m.x, plano_m.y)
    sombra = caixa(f"sombra-peca-{chave}-{x:.2f}", tuple(centro), (wp, dp, hp), giro=ang)
    cam_l = M.inverted() @ (C - base)
    sombra.data.materials.append(_mat_recorte(f"sombra-peca-{chave}", img, emissao, plano_obj, cam_l, (-Wp / 2, Wp / 2, L)))
    sombra.visible_camera = False
    sombra.visible_transmission = False
    return {
        "tipo": "peca", "chave": chave, "nome": PECAS[chave]["nome"], "objetos": [plano_obj, sombra],
        "planta": (wp, dp), "altura": hp, "pos": (centro.x, centro.y), "angulo": ang, "z0": z0, "sem_colisao": False,
    }


# ======================================================================
# O RENDER
# ======================================================================

def configurar(largura=1600, altura=1200, amostras=256, limiar=0.015, threads=3, exposicao=0.2):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.render.resolution_x = largura
    sc.render.resolution_y = altura
    sc.render.resolution_percentage = 100
    sc.render.threads_mode = "FIXED"
    sc.render.threads = threads
    sc.cycles.samples = amostras
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = limiar
    sc.cycles.adaptive_min_samples = min(32, amostras)
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    sc.cycles.denoising_prefilter = "ACCURATE"
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 4
    sc.cycles.transmission_bounces = 6
    sc.cycles.transparent_max_bounces = 24
    sc.cycles.sample_clamp_indirect = 6.0
    sc.cycles.blur_glossy = 0.6
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.use_light_tree = True
    sc.render.film_transparent = False
    sc.render.filter_size = 1.2
    sc.view_settings.view_transform = "Khronos PBR Neutral"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = exposicao
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    sc.render.image_settings.color_mode = "RGB"


def projetar_bases(maquinas):
    """Onde está a base de cada máquina na foto (em fração 0-1, de cima para baixo): para o zoom da conferência."""
    from bpy_extras.object_utils import world_to_camera_view

    sc = bpy.context.scene
    bpy.context.view_layer.update()
    cam = sc.camera
    out = []
    for m in maquinas:
        x, y = m["pos"]
        W, D = m["planta"]
        R = Matrix.Rotation(m["angulo"], 3, "Z")
        z0 = m.get("z0", 0.0)
        cantos = [Vector((x, y, z0)) + R @ Vector((sx * W / 2, sy * D / 2, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, m["altura"])]
        pts = [world_to_camera_view(sc, cam, c) for c in cantos]
        base = [world_to_camera_view(sc, cam, c) for c in cantos if abs(c.z - z0) < 1e-6]
        out.append({
            "nome": m["nome"], "tipo": m["tipo"],
            "caixa": [min(p.x for p in pts), 1 - max(p.y for p in pts), max(p.x for p in pts), 1 - min(p.y for p in pts)],
            "base": [min(p.x for p in base), 1 - max(p.y for p in base), max(p.x for p in base), 1 - min(p.y for p in base)],
        })
    return out


def remover(m):
    """Tira a máquina da cena (a medida do arranjo: cenas.fila)."""
    objs = list(m["objetos"])
    if m.get("raiz"):
        objs.append(m["raiz"])
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)


def _pontos_da_maquina(m):
    """Os pontos que contornam a máquina (a caixa de cada malha do .glb; a caixa da foto)."""
    if m["tipo"] == "glb":
        bpy.context.view_layer.update()
        return [o.matrix_world @ Vector(c) for o in m["objetos"] if o.type == "MESH" for c in o.bound_box]
    x, y = m["pos"]
    W, D = m["planta"]
    z0 = m.get("z0", 0.0)
    R = Matrix.Rotation(m["angulo"], 3, "Z")
    pts = [Vector((x, y, z0)) + R @ Vector((sx * W / 2, sy * D / 2, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, m["altura"])]
    if m.get("plano"):
        pts += [m["plano"].matrix_world @ v.co for v in m["plano"].data.vertices]
    return pts


def caixa_na_foto(maquinas):
    """(esquerda, cima, direita, baixo) de todas as máquinas na foto, em fração (0-1)."""
    from bpy_extras.object_utils import world_to_camera_view

    sc = bpy.context.scene
    bpy.context.view_layer.update()
    pts = [world_to_camera_view(sc, sc.camera, p) for m in maquinas for p in _pontos_da_maquina(m)]
    pts = [p for p in pts if p.z > 0]
    return min(p.x for p in pts), 1 - max(p.y for p in pts), max(p.x for p in pts), 1 - min(p.y for p in pts)


def enquadrar(maquinas, alvo=(0.05, 0.14, 0.95, 0.85), dolly=True, base=True):
    """Enquadra as máquinas na foto.

    `dolly`: a câmera anda para a frente/para trás (no eixo dela) até o grupo caber no
    `alvo` (só nas cenas de .glb: a foto do catálogo olha para a câmera e é posta
    depois dela); depois o deslocamento da lente (sem mudar a perspectiva) centra o
    grupo na largura e põe a base dele na linha de baixo do alvo (`base`) -- o chão
    com o reflexo embaixo e a folga de cima para a etiqueta "Categoria" do card.
    """
    sc = bpy.context.scene
    cam = sc.camera
    tx0, ty0, tx1, ty1 = alvo
    if dolly:
        frente = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
        frente.z = 0
        frente.normalize()
        for _ in range(40):
            x0, y0, x1, y1 = caixa_na_foto(maquinas)
            razao = max((x1 - x0) / (tx1 - tx0), (y1 - y0) / (ty1 - ty0))
            if abs(razao - 1) < 0.01:
                break
            centro = sum((p for m in maquinas for p in _pontos_da_maquina(m)), Vector()) / sum(
                len(_pontos_da_maquina(m)) for m in maquinas)
            dist = (Vector((centro.x, centro.y, 0)) - Vector((cam.location.x, cam.location.y, 0))).length
            cam.location -= frente * dist * (razao - 1) * 0.7
    for _ in range(3):
        x0, y0, x1, y1 = caixa_na_foto(maquinas)
        cam.data.shift_x -= ((tx0 + tx1) / 2 - (x0 + x1) / 2)
        if base:
            cam.data.shift_y += (ty1 - y1) * sc.render.resolution_y / sc.render.resolution_x
        else:
            cam.data.shift_y += ((ty0 + ty1) / 2 - (y0 + y1) / 2) * sc.render.resolution_y / sc.render.resolution_x
    x0, y0, x1, y1 = caixa_na_foto(maquinas)
    print(f"  enquadrado: câmera em ({cam.location.x:.1f}, {cam.location.y:.1f}, {cam.location.z:.1f}), "
          f"desloc ({cam.data.shift_x:.3f}, {cam.data.shift_y:.3f}); máquinas de {x0:.2f}-{x1:.2f} x {y0:.2f}-{y1:.2f}")
    return x0, y0, x1, y1


def extensao_no_chao(m):
    """(x mín, y mín, x máx, y máx) da planta da máquina no chão."""
    x, y = m["pos"]
    W, D = m["planta"]
    R = Matrix.Rotation(m["angulo"], 3, "Z")
    pts = [Vector((x, y, 0)) + R @ Vector((sx * W / 2, sy * D / 2, 0)) for sx in (-1, 1) for sy in (-1, 1)]
    return min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts)


def extensao_na_foto(m):
    """(esquerda, direita, cima, baixo) da máquina na foto, em fração (0-1)."""
    caixa = projetar_bases([m])[0]["caixa"]
    return caixa[0], caixa[2], caixa[1], caixa[3]


def colisoes(maquinas, folga=0.05):
    """As plantas (retângulos girados) que se cruzam: avisa (nenhuma máquina dentro da outra)."""
    def poligono(m):
        x, y = m["pos"]
        W, D = m["planta"]
        W, D = W + folga, D + folga
        c, s = math.cos(m["angulo"]), math.sin(m["angulo"])
        return [(x + c * px - s * py, y + s * px + c * py) for px, py in ((-W / 2, -D / 2), (W / 2, -D / 2), (W / 2, D / 2), (-W / 2, D / 2))]

    def separa(p1, p2):
        for pol in (p1, p2):
            for i in range(4):
                x1, y1 = pol[i]
                x2, y2 = pol[(i + 1) % 4]
                nx, ny = y2 - y1, x1 - x2
                a = [nx * px + ny * py for px, py in p1]
                b = [nx * px + ny * py for px, py in p2]
                if max(a) < min(b) or max(b) < min(a):
                    return True
        return False

    achados = []
    for i, a in enumerate(maquinas):
        for b in maquinas[i + 1:]:
            if a.get("sem_colisao") or b.get("sem_colisao"):
                continue
            if not separa(poligono(a), poligono(b)):
                achados.append((a["nome"], b["nome"]))
    return achados
