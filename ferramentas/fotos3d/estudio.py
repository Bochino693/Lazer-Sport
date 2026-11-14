"""O estúdio de fotografia de produto, no Blender (Cycles): a luz, o fundo, os materiais e a câmera.

O chefe: "como o McDonald's: você olha a foto do lanche e quer comer, porque tem vida e
nitidez. As nossas estão apagadas, sem vida; os fundos parecem muito falsos, não uma foto de
câmera 4K". E: "o Basquete Home normal e o preto: a máquina encolheu". Daqui saem as fotos
dos nossos 3D como num estúdio de verdade (ver renderizar.py, que roda tudo, e produtos.py,
o que cada máquina fotografa):

  * O FUNDO INFINITO (o "cove"): o chão que sobe em curva até a parede, sem canto, em azul
    marinho profundo, com o brilho azul royal atrás da máquina (a luz de fundo com gelatina
    azul). O chão é brilhante (acrílico): o reflexo macio da máquina e a sombra de contato.
  * A LUZ: o softbox grande de cima, à esquerda (a principal), o rebatedor do outro lado, o
    softbox de teto (o brilho no alto das peças) e as duas luzes de recorte atrás, nas cores
    da marca -- azul #007BFF à esquerda e vermelho #E63946 à direita --, que desenham o
    contorno da máquina. A luz gira com a câmera: a máquina é que gira (a mesa giratória do
    fotógrafo), então todas as vistas têm a mesma luz e o mesmo fundo.
  * OS MATERIAIS (pelos nomes do .glb, `classe_do_material`): o adesivo vira vinil laminado
    brilhante (verniz por cima: o reflexo nítido do softbox), a estrutura preta vira pintura
    eletrostática acetinada, o metal é metal, a borracha é fosca, o acrílico deixa passar a
    luz, e o LED, o neon e a tela ACENDEM (emissão forte, com o brilho do Glare no
    compositor: iluminam a máquina e o chão, como na foto de verdade).
  * A CÂMERA: a de um fotógrafo (lente de 60 mm equivalente, f/9, um tico de profundidade de
    campo), na altura dos olhos. O ENQUADRAMENTO É UM SÓ POR MÁQUINA (`enquadrar`): a câmera
    se acha pelas medidas de verdade do adesivo de referência, e os outros adesivos da mesma
    máquina usam a MESMA câmera -- a mesma distância, a mesma lente: o mesmo tamanho na foto.
  * AS CORES: AgX com o "Punchy" (contraste e saturação de foto), a exposição acertada para o
    branco do adesivo não estourar.

As texturas do .glb são as artes da fábrica já ampliadas (desde a seção 92 do LEIA-ME V10,
4x com nitidez, até 2048 px: ficam como estão); a textura pequena (abaixo de 1024 px) o
estúdio amplia 2x (Lanczos) com um realce de borda leve (`realcar_textura`), e a arte da
pasta ferramentas/modelos3d/<máquina>/adesivos-hd/ (ou adesivos/) entra no lugar quando é
MAIOR que a do .glb (a mesma proporção): chegando a arte em alta da fábrica, é só pôr lá.

Roda com o Blender como módulo do Python (o `bpy` do pip, 5.0): ver renderizar.py.
"""

from __future__ import annotations

import io
import math
import os
import re
import tempfile
from pathlib import Path

import bpy  # (o bpy antes: ele é que põe o bmesh e o mathutils no caminho)
import bmesh
import mathutils
import numpy as np

# ----------------------------------------------------------------------
# Cores (sRGB da marca -> linear, que é o que o Cycles usa)
# ----------------------------------------------------------------------


def linear(hexa):
    """A cor "#RRGGBB" (sRGB) em RGB linear."""
    hexa = hexa.lstrip("#")
    saida = []
    for i in (0, 2, 4):
        c = int(hexa[i:i + 2], 16) / 255
        saida.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(saida)


AZUL_MARCA = "#007BFF"
VERMELHO_MARCA = "#E63946"
#: O fundo: o marinho das bordas e o azul royal do brilho atrás da máquina.
MARINHO = "#040A26"
MARINHO_CHAO = "#0A1440"
ROYAL = "#1D4BFF"

# ----------------------------------------------------------------------
# A cena e o render
# ----------------------------------------------------------------------

#: A transformação de cor da foto. O AgX (com o "Punchy") foi o primeiro: no adesivo claro e
#: saturado (o verde, o amarelo e o laranja do Strike Kids) ele leva a cor para o branco antes
#: da hora ("path to white") e a arte sai leitosa, puxando para o verde-oliva. O Khronos PBR
#: Neutral é o feito para foto de produto (e-commerce): até ~80% a cor da arte passa como é, e
#: só o brilho forte (o reflexo, o LED) é comprimido. O contraste e a vibração da foto vêm no
#: acabamento (acabamento.py). Para comparar: VISTA = "AgX" (com o "AgX - Punchy").
VISTA = "Khronos PBR Neutral"


def nova_cena(amostras=40, limiar=0.035, transparente=False):
    """A cena vazia com o Cycles na CPU, o OpenImageDenoise, a amostragem adaptativa e o AgX."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cena = bpy.context.scene
    cena.render.engine = "CYCLES"
    ciclos = cena.cycles
    ciclos.device = "CPU"
    cena.render.threads_mode = "FIXED"
    cena.render.threads = os.cpu_count() or 4
    ciclos.samples = amostras
    ciclos.use_adaptive_sampling = True
    ciclos.adaptive_threshold = limiar
    ciclos.adaptive_min_samples = max(8, amostras // 3)
    # a árvore de luzes (para cenas com milhares de luzes) deixava o render ~2,7x mais lento:
    # aqui são cinco softboxes e os LEDs
    ciclos.use_light_tree = False
    ciclos.use_denoising = True
    try:
        ciclos.denoiser = "OPENIMAGEDENOISE"
    except TypeError:  # (o enum é dinâmico: sem o OIDN, fica o que houver)
        pass
    ciclos.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    ciclos.denoising_prefilter = "ACCURATE"
    try:
        ciclos.denoising_quality = "HIGH"
    except (TypeError, AttributeError):
        pass
    ciclos.max_bounces = 6
    ciclos.diffuse_bounces = 2
    ciclos.glossy_bounces = 3
    ciclos.transmission_bounces = 6
    ciclos.transparent_max_bounces = 16
    ciclos.sample_clamp_direct = 0
    ciclos.sample_clamp_indirect = 6
    ciclos.caustics_reflective = False
    ciclos.caustics_refractive = False
    ciclos.blur_glossy = 0.5
    ciclos.pixel_filter_type = "BLACKMAN_HARRIS"
    cena.render.filter_size = 1.2
    cena.render.film_transparent = transparente
    cena.render.use_persistent_data = True
    cena.render.image_settings.file_format = "PNG"
    cena.render.image_settings.color_mode = "RGBA" if transparente else "RGB"
    cena.render.image_settings.color_depth = "8"
    cena.render.image_settings.compression = 15
    cena.view_settings.view_transform = VISTA
    if VISTA == "AgX":
        cena.view_settings.look = "AgX - Punchy"
    cena.view_settings.exposure = 0.0
    cena.view_settings.gamma = 1.0
    # o mundo: o escuro do estúdio (só um tico de azul nos reflexos de cima)
    mundo = bpy.data.worlds.new("estudio")
    cena.world = mundo
    arvore = mundo.node_tree
    fundo = arvore.nodes.get("Background") or arvore.nodes.new("ShaderNodeBackground")
    fundo.inputs["Color"].default_value = (*linear("#0B1230"), 1)
    fundo.inputs["Strength"].default_value = 0.12
    return cena


def compositor(cena, brilho=0.18, limiar=2.5, tamanho=0.42):
    """O brilho do LED e do neon (o Glare "Bloom" no linear, antes do AgX): como a lente de verdade."""
    grupo = bpy.data.node_groups.new("fotos3d", "CompositorNodeTree")
    cena.compositing_node_group = grupo
    grupo.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    camadas = grupo.nodes.new("CompositorNodeRLayers")
    glare = grupo.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Quality"].default_value = "Medium"
    glare.inputs["Threshold"].default_value = limiar
    glare.inputs["Strength"].default_value = brilho
    glare.inputs["Size"].default_value = tamanho
    saida = grupo.nodes.new("NodeGroupOutput")
    grupo.links.new(camadas.outputs["Image"], glare.inputs["Image"])
    grupo.links.new(glare.outputs["Image"], saida.inputs[0])
    cena.render.use_compositing = True
    return glare


# ----------------------------------------------------------------------
# O fundo infinito
# ----------------------------------------------------------------------


def criar_fundo(escala=1.0, brilho_fundo=1.5, centro_brilho=1.2, raio_brilho=3.2):
    """O fundo infinito: o chão (brilhante, acrílico) que sobe em curva até a parede (fosca).

    `escala`: o tamanho da máquina (1 = ~2,5 m). O brilho azul royal fica na parede, atrás da
    máquina, na altura `centro_brilho` (m), com o raio `raio_brilho` (m).
    """
    fundo_y = 4.2 * escala + 1.2
    raio = 2.6 * escala + 0.6
    frente_y = -30.0
    altura = 30.0
    largura = 60.0
    perfil = [(frente_y, 0.0)]
    passos = 32
    for i in range(passos + 1):
        t = (math.pi / 2) * i / passos
        perfil.append((fundo_y - raio + raio * math.sin(t), raio - raio * math.cos(t)))
    perfil.append((fundo_y, altura))
    malha = bpy.data.meshes.new("fundo-infinito")
    bm = bmesh.new()
    linhas = []
    for x in (-largura / 2, largura / 2):
        linhas.append([bm.verts.new((x, y, z)) for y, z in perfil])
    for i in range(len(perfil) - 1):
        face = bm.faces.new((linhas[0][i], linhas[1][i], linhas[1][i + 1], linhas[0][i + 1]))
        face.smooth = True
    bm.normal_update()
    bm.to_mesh(malha)
    bm.free()
    objeto = bpy.data.objects.new("fundo-infinito", malha)
    bpy.context.scene.collection.objects.link(objeto)
    # a normal do chão tem de apontar para cima
    if malha.polygons[0].normal.z < 0:
        bm = bmesh.new()
        bm.from_mesh(malha)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(malha)
        bm.free()
    objeto.data.materials.append(material_do_fundo(fundo_y, centro_brilho, raio_brilho * max(escala, 0.6), brilho_fundo))
    return objeto


def material_do_fundo(fundo_y, centro_z, raio, forca):
    """O marinho com o brilho royal atrás da máquina; o chão envernizado (o reflexo) e a parede fosca."""
    mat = bpy.data.materials.new("fundo-infinito")
    # o brilho do fundo não é luz que se mira (o fundo é enorme): só o que bate nele o vê. Bem
    # mais rápido, e a máquina continua com o azul nas bordas pelos reflexos
    mat.cycles.emission_sampling = "NONE"
    nos = mat.node_tree.nodes
    ln = mat.node_tree.links
    bsdf = nos.get("Principled BSDF")
    coord = nos.new("ShaderNodeTexCoord")
    xyz = nos.new("ShaderNodeSeparateXYZ")
    ln.new(coord.outputs["Object"], xyz.inputs[0])
    # o brilho: um gradiente esférico em volta de um ponto na parede, atrás da máquina
    mapa = nos.new("ShaderNodeMapping")
    mapa.inputs["Location"].default_value = (0.0, -fundo_y / raio, -centro_z / raio)
    mapa.inputs["Scale"].default_value = (1 / raio, 1 / raio, 1 / (raio * 0.8))
    ln.new(coord.outputs["Object"], mapa.inputs["Vector"])
    # (o Mapping aplica escala e depois soma a posição: o ponto (0, fundo_y, centro_z) vai para a origem)
    grad = nos.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    ln.new(mapa.outputs["Vector"], grad.inputs["Vector"])
    rampa = nos.new("ShaderNodeValToRGB")
    els = rampa.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (*linear(MARINHO), 1)
    els[1].position = 1.0
    els[1].color = (*linear(ROYAL), 1)
    meio = els.new(0.45)
    meio.color = (*linear("#0D2280"), 1)
    rampa.color_ramp.interpolation = "B_SPLINE"
    ln.new(grad.outputs["Fac"], rampa.inputs["Fac"])
    ln.new(rampa.outputs["Color"], bsdf.inputs["Emission Color"])
    # o brilho só para a câmera (e para o reflexo no chão): nos adesivos brilhantes, o fundo é
    # escuro, como o estúdio de verdade com as bandeiras pretas em volta -- a arte reflete só os
    # softboxes e fica com as cores cheias, sem o véu azul
    caminho = nos.new("ShaderNodeLightPath")
    so_camera = nos.new("ShaderNodeMath")
    so_camera.operation = "MULTIPLY"
    so_camera.inputs[1].default_value = forca
    ln.new(caminho.outputs["Is Camera Ray"], so_camera.inputs[0])
    ln.new(so_camera.outputs["Value"], bsdf.inputs["Emission Strength"])
    mat["forca_do_brilho"] = forca
    # a cor de base: o marinho (a luz das máquinas e dos softboxes cai nele)
    bsdf.inputs["Base Color"].default_value = (*linear(MARINHO_CHAO), 1)
    # o chão (z ~ 0) envernizado; a parede, fosca: a passagem é suave (sem emenda)
    passagem = nos.new("ShaderNodeMapRange")
    passagem.inputs["From Min"].default_value = 0.02
    passagem.inputs["From Max"].default_value = 0.9
    passagem.inputs["To Min"].default_value = 1.0
    passagem.inputs["To Max"].default_value = 0.0
    passagem.interpolation_type = "SMOOTHSTEP"
    ln.new(xyz.outputs["Z"], passagem.inputs["Value"])
    ln.new(passagem.outputs["Result"], bsdf.inputs["Coat Weight"])
    bsdf.inputs["Coat Roughness"].default_value = 0.1
    bsdf.inputs["Coat IOR"].default_value = 1.5
    aspereza = nos.new("ShaderNodeMapRange")
    aspereza.inputs["From Min"].default_value = 0.02
    aspereza.inputs["From Max"].default_value = 0.9
    aspereza.inputs["To Min"].default_value = 0.35
    aspereza.inputs["To Max"].default_value = 0.8
    aspereza.interpolation_type = "SMOOTHSTEP"
    ln.new(xyz.outputs["Z"], aspereza.inputs["Value"])
    ln.new(aspereza.outputs["Result"], bsdf.inputs["Roughness"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.4
    return mat


# ----------------------------------------------------------------------
# A luz
# ----------------------------------------------------------------------

#: As luzes do estúdio: (nome, azimute, elevação, distância, largura, altura, potência, cor, espalhamento).
#: Azimute 0 = do lado da câmera (-Y); positivo = para a direita da câmera. Distâncias em
#: "escalas" (1 = máquina de ~2,5 m) e a potência em W para essa escala (cresce com o quadrado).
LUZES = (
    ("principal", -38, 46, 4.6, 2.4, 1.6, 290, "#FFF6EC", 80),
    ("rebatedor", 62, 30, 6.0, 2.0, 2.0, 75, "#EEF3FF", 110),
    ("teto", 180, 68, 3.6, 1.6, 1.0, 130, "#FFFFFF", 70),
    ("recorte-azul", -158, 20, 3.0, 0.3, 2.2, 130, AZUL_MARCA, 28),
    ("recorte-vermelho", 158, 20, 3.0, 0.3, 2.2, 120, VERMELHO_MARCA, 28),
)


def criar_luzes(escala=1.0, centro=(0, 0, 1.0), fator=1.0, so_cor=1.0):
    """As luzes, apontadas para o `centro` da máquina. `fator` multiplica as brancas e `so_cor` as de cor."""
    luzes = []
    alvo = mathutils.Vector(centro)
    for nome, az, el, dist, larg, alt, potencia, cor, espalhamento in LUZES:
        dados = bpy.data.lights.new(nome, "AREA")
        dados.shape = "RECTANGLE"
        dados.size = larg * escala
        dados.size_y = alt * escala
        colorida = nome.startswith("recorte")
        dados.energy = potencia * escala ** 2 * (so_cor if colorida else fator)
        dados.color = linear(cor)
        dados.spread = math.radians(espalhamento)
        obj = bpy.data.objects.new(nome, dados)
        bpy.context.scene.collection.objects.link(obj)
        a, e = math.radians(az), math.radians(el)
        d = dist * escala
        obj.location = alvo + mathutils.Vector((d * math.sin(a) * math.cos(e), -d * math.cos(a) * math.cos(e), d * math.sin(e)))
        direcao = alvo - obj.location
        obj.rotation_euler = direcao.to_track_quat("-Z", "Y").to_euler()
        obj.visible_camera = False
        obj["alvo"] = tuple(alvo)
        luzes.append(obj)
    return luzes


def espelhar_luzes(luzes, lado):
    """Põe a luz principal (e o rebatedor do outro lado) do `lado` da câmera (-1 esquerda, +1 direita).

    O fotógrafo leva o softbox para o lado da face que a foto mostra: na vista de 3/4 pela
    direita, a principal vai para a direita. As luzes de recorte não mudam (o azul da marca
    sempre à esquerda, o vermelho à direita).
    """
    for luz in luzes:
        if luz.name.startswith("recorte") or luz.name == "teto":
            continue
        x = abs(luz.location.x) * (lado if luz.name == "principal" else -lado)
        luz.location.x = x
        alvo = mathutils.Vector(luz["alvo"])
        luz.rotation_euler = (alvo - luz.location).to_track_quat("-Z", "Y").to_euler()


# ----------------------------------------------------------------------
# A máquina: o .glb no tamanho de verdade, em cima da mesa giratória
# ----------------------------------------------------------------------


def importar_maquina(glb, altura_real, nome="maquina"):
    """Importa o .glb no tamanho de verdade (a altura do cadastro), centrado, com o pé no chão.

    Devolve (giro, malhas, medidas): `giro` é o vazio que gira a máquina (a mesa giratória), e
    `medidas` (largura, profundidade, altura) em metros, já na escala. A escala é uma só (pela
    altura): a arte não deforma; se a largura ou a profundidade do .glb não batem com as do
    cadastro, o aviso sai no terminal (e no relatório).
    """
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    novos = [o for o in bpy.data.objects if o not in antes]
    bpy.context.view_layer.update()
    malhas = [o for o in novos if o.type == "MESH"]
    pontos = _pontos(malhas)
    minimo, maximo = pontos.min(axis=0), pontos.max(axis=0)
    escala = altura_real / float(maximo[2] - minimo[2])
    giro = bpy.data.objects.new(f"{nome}-giro", None)
    ajuste = bpy.data.objects.new(f"{nome}-ajuste", None)
    bpy.context.scene.collection.objects.link(giro)
    bpy.context.scene.collection.objects.link(ajuste)
    ajuste.parent = giro
    ajuste.scale = (escala,) * 3
    centro = (minimo + maximo) / 2
    ajuste.location = (-centro[0] * escala, -centro[1] * escala, -minimo[2] * escala)
    for obj in novos:
        if obj.parent is None:
            obj.parent = ajuste
    bpy.context.view_layer.update()
    medidas = tuple(float(v) for v in (maximo - minimo) * escala)
    return giro, malhas, medidas


def _pontos(objetos):
    """Os vértices (no mundo) dos objetos, num array N x 3."""
    todos = []
    for obj in objetos:
        if obj.type != "MESH" or not obj.data.vertices:
            continue
        co = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
        obj.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array(obj.matrix_world)
        todos.append(co @ m[:3, :3].T + m[:3, 3])
    return np.concatenate(todos) if todos else np.zeros((0, 3))


def pontos_da_maquina(malhas, filtro=None):
    """Os vértices das malhas (no mundo); `filtro`: regex nos nomes do objeto/material (o detalhe)."""
    if filtro:
        regex = re.compile(filtro, re.I)
        malhas = [o for o in malhas if regex.search(o.name) or any(
            s.material and regex.search(s.material.name) for s in o.material_slots)]
    return _pontos(malhas)


# ----------------------------------------------------------------------
# Os materiais
# ----------------------------------------------------------------------

#: Os parâmetros de cada classe (Principled BSDF). Os da arte seguem o vinil impresso com
#: laminação brilhante: aspereza 0,25 e verniz (coat) 0,5 bem liso -- o reflexo do softbox.
CLASSES = {
    "adesivo": {"Roughness": 0.27, "Specular IOR Level": 0.5, "Coat Weight": 0.5, "Coat Roughness": 0.04, "Metallic": 0.0},
    "pista": {"Roughness": 0.16, "Specular IOR Level": 0.55, "Coat Weight": 0.85, "Coat Roughness": 0.025, "Metallic": 0.0},
    "pintura": {"Roughness": 0.36, "Specular IOR Level": 0.5, "Coat Weight": 0.25, "Coat Roughness": 0.12, "Metallic": 0.0},
    "preto": {"Roughness": 0.4, "Specular IOR Level": 0.5, "Coat Weight": 0.12, "Coat Roughness": 0.2, "Metallic": 0.0},
    "metal": {"Roughness": 0.16, "Metallic": 1.0, "Coat Weight": 0.0},
    "metal-pintado": {"Roughness": 0.3, "Metallic": 0.0, "Coat Weight": 0.6, "Coat Roughness": 0.05},
    "borracha": {"Roughness": 0.78, "Specular IOR Level": 0.3, "Coat Weight": 0.0, "Metallic": 0.0},
    "plastico": {"Roughness": 0.22, "Specular IOR Level": 0.5, "Coat Weight": 0.35, "Coat Roughness": 0.05, "Metallic": 0.0},
    "bola": {"Roughness": 0.5, "Specular IOR Level": 0.45, "Coat Weight": 0.15, "Coat Roughness": 0.2, "Metallic": 0.0},
    "rede": {"Roughness": 0.85, "Specular IOR Level": 0.3, "Coat Weight": 0.0, "Metallic": 0.0},
    "vidro": {"Roughness": 0.02, "Transmission Weight": 1.0, "IOR": 1.49, "Coat Weight": 0.0, "Metallic": 0.0},
    "luz": {"Roughness": 0.2, "Specular IOR Level": 0.5, "Coat Weight": 0.6, "Coat Roughness": 0.03, "Metallic": 0.0},
    "tela": {"Roughness": 0.2, "Specular IOR Level": 0.5, "Coat Weight": 1.0, "Coat Roughness": 0.02, "Metallic": 0.0},
}

#: A força da luz de cada classe que acende (W/m²; o branco do adesivo, na luz do estúdio, fica ~1).
EMISSAO = {"luz": 6.0, "tela": 2.0, "adesivo": 1.2}


def _nomes(mat, objetos):
    usados = [o.name for o in objetos if any(s.material == mat for s in o.material_slots)]
    return " ".join([mat.name] + usados).lower()


def _bsdf(mat):
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if mat.node_tree else None


def _textura(socket):
    """A imagem ligada a um socket (direto ou por um Mapping/Mix), ou None."""
    if not socket.is_linked:
        return None
    pilha = [socket.links[0].from_node]
    vistos = set()
    while pilha:
        no = pilha.pop()
        if no in vistos:
            continue
        vistos.add(no)
        if no.type == "TEX_IMAGE" and no.image:
            return no
        for entrada in no.inputs:
            if entrada.is_linked:
                pilha.append(entrada.links[0].from_node)
    return None


def _emite(bsdf):
    forca = bsdf.inputs["Emission Strength"].default_value
    cor = bsdf.inputs["Emission Color"]
    return forca > 0 and (cor.is_linked or any(c > 0.001 for c in cor.default_value[:3]))


def classe_do_material(mat, objetos):
    """A classe do material, pelos nomes (o do material e os dos objetos) e pelo que ele tem."""
    nomes = _nomes(mat, objetos)
    bsdf = _bsdf(mat)
    if bsdf is None:
        return "pintura"
    emite = _emite(bsdf)
    textura = _textura(bsdf.inputs["Base Color"]) or _textura(bsdf.inputs["Emission Color"])
    if re.search(r"vidro|acrilic|glass|cupula", nomes):
        return "vidro"
    if emite and re.search(r"monitor|tela(?!-)|tela$|placar|display|screen", nomes) and not re.search(r"digito", nomes):
        return "tela"
    if re.search(r"\bbola|bolas|ball", nomes):
        return "bola"
    if re.search(r"rede", nomes):
        return "rede"
    if re.search(r"pista|prancha|quadra", nomes) and textura is not None:
        return "pista"
    if textura is not None and re.search(r"adesivo|arte|acab|sticker|painel", nomes):
        return "adesivo"
    cor = bsdf.inputs["Base Color"].default_value
    escuro = 0.2126 * cor[0] + 0.7152 * cor[1] + 0.0722 * cor[2] < 0.03
    # (a fita de LED sem emissão e escura é o trilho dela: preto, não acende)
    if emite or (re.search(r"neon|\bled|led_|led-|fita|lamp|luz|digito|start", nomes) and not escuro):
        return "luz"
    if textura is not None:
        return "adesivo"
    if re.search(r"moedeiro|suporte|chapa|cromo|inox|metal|parafuso", nomes):
        return "metal"
    if re.search(r"\baro\b|aro$|^aro", nomes):
        return "metal-pintado"
    if re.search(r"pes-|pés|borracha|rubber|pneu|nivelador", nomes):
        return "borracha"
    if re.search(r"rebatedor|disco|botao|botão|plastic|placar|moldura|lente", nomes):
        return "plastico"
    if escuro:
        return "preto"
    return "pintura"


def aplicar_materiais(malhas, emissao=None, artes=None, fator_textura=2):
    """Troca os materiais do .glb pelos de estúdio. Devolve {material: classe} (o relatório).

    `emissao`: {classe: força} por cima de EMISSAO (o produto pode pedir LED mais forte).
    `artes`: a pasta com a arte em alta (adesivos/<peça>.png): entra no lugar da textura do
    .glb quando é maior e tem a mesma proporção.
    """
    forcas = {**EMISSAO, **(emissao or {})}
    materiais = {}
    for obj in malhas:
        for slot in obj.material_slots:
            if slot.material is not None:
                materiais[slot.material.name] = slot.material
    relatorio = {}
    imagens_feitas = {}
    for nome, mat in materiais.items():
        classe = classe_do_material(mat, malhas)
        relatorio[nome] = classe
        bsdf = _bsdf(mat)
        if bsdf is None:
            continue
        for chave, valor in CLASSES[classe].items():
            if chave in bsdf.inputs:
                bsdf.inputs[chave].default_value = valor
        if classe == "metal" and not bsdf.inputs["Base Color"].is_linked:
            cor = bsdf.inputs["Base Color"].default_value
            if 0.2126 * cor[0] + 0.7152 * cor[1] + 0.0722 * cor[2] > 0.2:
                bsdf.inputs["Base Color"].default_value = (0.78, 0.79, 0.81, 1)  # o cromo
            else:  # o metal pintado de preto (a porta do moedeiro): acetinado
                bsdf.inputs["Roughness"].default_value = 0.35
        if classe in ("luz", "tela"):
            if not _emite(bsdf):  # o LED sem emissão no .glb: acende com a própria cor
                if bsdf.inputs["Base Color"].is_linked:
                    mat.node_tree.links.new(bsdf.inputs["Base Color"].links[0].from_socket, bsdf.inputs["Emission Color"])
                else:
                    bsdf.inputs["Emission Color"].default_value = bsdf.inputs["Base Color"].default_value
            bsdf.inputs["Emission Strength"].default_value = forcas[classe]
        elif classe == "adesivo" and _emite(bsdf):
            # o letreiro com luz por trás (a testeira): acende de leve
            bsdf.inputs["Emission Strength"].default_value = forcas["adesivo"]
        else:
            bsdf.inputs["Emission Strength"].default_value = 0.0
        if classe in ("adesivo", "pista", "tela", "bola"):
            for no in mat.node_tree.nodes:
                if no.type == "TEX_IMAGE" and no.image and no.image.name not in ("",):
                    if no.image.name not in imagens_feitas:
                        imagens_feitas[no.image.name] = realcar_textura(no.image, nome, artes, fator_textura)
                    no.image = imagens_feitas[no.image.name]
                    no.interpolation = "Linear"  # (a textura já vem ampliada com o Lanczos: o cúbico só custava tempo)
    return relatorio


def _arte_em_alta(nome_material, artes, largura, altura):
    """A arte da pasta `artes` para o material (adesivo-<peça> -> <peça>.png), se é maior e da mesma proporção."""
    if not artes:
        return None
    from PIL import Image

    peca = re.sub(r"^adesivo-", "", nome_material)
    pasta = Path(artes)
    for caminho in (pasta.parent / f"{pasta.name}-hd" / f"{peca}.webp", pasta / f"{peca}.png"):
        if not caminho.exists():
            continue
        with Image.open(caminho) as img:
            w, h = img.size
        if w > largura and abs(w / h - largura / altura) <= 0.01 * (largura / altura):
            return caminho
    return None


def realcar_textura(imagem, nome_material, artes, fator):
    """A textura ampliada (Lanczos) com realce de borda leve: a impressão sai nítida de perto.

    Usa a arte em alta da pasta `artes` quando ela é maior que a do .glb.
    """
    from PIL import Image, ImageFilter

    largura, altura = imagem.size
    if not largura or not altura:
        return imagem
    fonte = _arte_em_alta(nome_material, artes, largura, altura)
    if fonte is not None:
        pil = Image.open(fonte)
    elif imagem.packed_file is not None:
        pil = Image.open(io.BytesIO(imagem.packed_file.data))
    elif imagem.filepath and Path(bpy.path.abspath(imagem.filepath)).exists():
        pil = Image.open(bpy.path.abspath(imagem.filepath))
    else:
        return imagem
    tem_alfa = "A" in pil.getbands()
    pil = pil.convert("RGBA" if tem_alfa else "RGB")
    if max(pil.size) < 64:  # as tirinhas (o LED, a rede): ficam como estão
        return imagem
    if max(pil.size) >= 1024 and fonte is None:
        # a arte do .glb já vem em alta (a seção 92: ampliada 4x com nitidez, até 2048 px): fica
        return imagem
    escala = min(fator, 2048 / max(pil.size)) if max(pil.size) < 1024 else 1.0
    if escala > 1.01:
        pil = pil.resize((round(pil.width * escala), round(pil.height * escala)), Image.LANCZOS)
        pil = pil.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
    pasta = Path(tempfile.gettempdir()) / "fotos3d-texturas"
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"{re.sub(r'[^a-z0-9_-]+', '-', (nome_material + '-' + imagem.name).lower())}.png"
    pil.save(destino)
    nova = bpy.data.images.load(str(destino), check_existing=False)
    nova.colorspace_settings.name = imagem.colorspace_settings.name
    nova.alpha_mode = imagem.alpha_mode
    nova.pack()
    return nova


# ----------------------------------------------------------------------
# A câmera e o enquadramento
# ----------------------------------------------------------------------

SENSOR = 36.0  # mm (o "full frame": a lente de 60 mm é a de 60 mm equivalente)


def criar_camera(lente=60.0, f_stop=9.0):
    dados = bpy.data.cameras.new("camera")
    dados.lens = lente
    dados.sensor_width = SENSOR
    dados.sensor_fit = "HORIZONTAL"
    dados.dof.use_dof = True
    dados.dof.aperture_fstop = f_stop
    dados.dof.aperture_blades = 7
    obj = bpy.data.objects.new("camera", dados)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.camera = obj
    return obj


def _projetar(pontos, posicao, inclinacao, lente, aspecto):
    """(u, v, profundidade) dos pontos na câmera em `posicao`, olhando para +Y, inclinada `inclinacao` rad.

    u e v em frações do quadro (-0,5..0,5), com o sensor horizontal de 36 mm e a altura 36/aspecto.
    """
    rel = pontos - np.asarray(posicao)
    c, s = math.cos(inclinacao), math.sin(inclinacao)
    # eixo da vista: (0, cos, sin); o "para cima" da câmera: (0, -sin, cos)
    frente = rel[:, 1] * c + rel[:, 2] * s
    cima = -rel[:, 1] * s + rel[:, 2] * c
    direita = rel[:, 0]
    u = (direita / frente) * lente / SENSOR
    v = (cima / frente) * lente / (SENSOR / aspecto)
    return u, v, frente


def enquadrar(pontos, altura_camera, aspecto, margem=0.075, lente=60.0, inclinacao_fixa=None):
    """A câmera que põe os pontos (a máquina de referência) no quadro, com a `margem` dos lados.

    A câmera fica em x = 0, do lado -Y, na `altura_camera` (m), olhando para +Y (a máquina é
    que gira); acha a distância e a inclinação que deixam a máquina centrada na vertical (ou
    usa a `inclinacao_fixa`, em graus, e centra com o deslocamento vertical da lente) e o
    deslocamento horizontal da lente (shift) que a centra na horizontal. A máquina enche o
    quadro: o lado que limita fica com a `margem` (fração) de cada lado. O quadro é paisagem
    ou quadrado (aspecto >= 1). Devolve {"posicao", "inclinacao", "shift_x", "shift_y",
    "foco", "lente", "aspecto", "caixa"} (a caixa da máquina na foto, em frações).
    """
    centro = (pontos.min(axis=0) + pontos.max(axis=0)) / 2
    raio = float(np.linalg.norm(pontos.max(axis=0) - pontos.min(axis=0))) / 2
    distancia = max(raio * lente / SENSOR * 2.2, 1.0)
    cheio = 1 - 2 * margem
    ajuste = 0.0
    for _ in range(200):
        posicao = (0.0, float(centro[1]) - distancia, altura_camera)
        if inclinacao_fixa is None:
            base = math.atan2(float(centro[2]) - altura_camera, distancia)
        else:
            base = math.radians(inclinacao_fixa)
        u, v, _prof = _projetar(pontos, posicao, base + ajuste, lente, aspecto)
        tamanho = max(u.max() - u.min(), v.max() - v.min())
        meio_v = (v.max() + v.min()) / 2
        if inclinacao_fixa is None:
            ajuste += math.atan(meio_v * (SENSOR / aspecto) / lente) * 0.8
        distancia *= (tamanho / cheio) ** 0.8
        if abs(tamanho - cheio) < 2e-5 and (inclinacao_fixa is not None or abs(meio_v) < 2e-5):
            break
    posicao = (0.0, float(centro[1]) - distancia, altura_camera)
    inclinacao = base + ajuste
    u, v, prof = _projetar(pontos, posicao, inclinacao, lente, aspecto)
    # o shift do Blender é em frações do lado maior do sensor (a largura, no quadro deitado)
    shift_x = float((u.max() + u.min()) / 2)
    shift_y = float((v.max() + v.min()) / 2) / aspecto if inclinacao_fixa is not None else 0.0
    quadro = {"posicao": posicao, "inclinacao": inclinacao, "shift_x": shift_x, "shift_y": shift_y,
              "foco": float(np.median(prof)), "lente": lente, "aspecto": aspecto}
    quadro["caixa"] = projetar_no_quadro(pontos, quadro)
    return quadro


def posicionar_camera(camera, quadro):
    """Põe a câmera no quadro calculado por `enquadrar`."""
    camera.location = quadro["posicao"]
    # a câmera do Blender olha para -Z: girar 90° em X olha para +Y; a inclinação soma
    camera.rotation_euler = (math.pi / 2 + quadro["inclinacao"], 0.0, 0.0)
    camera.data.lens = quadro["lente"]
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.sensor_width = SENSOR
    camera.data.shift_x = quadro["shift_x"]
    camera.data.shift_y = quadro["shift_y"]
    camera.data.dof.focus_distance = quadro["foco"]


def projetar_no_quadro(pontos, quadro):
    """(x0, y0, x1, y1) em frações da foto (0..1, y para baixo) da caixa dos pontos no quadro."""
    aspecto = quadro["aspecto"]
    u, v, _ = _projetar(pontos, quadro["posicao"], quadro["inclinacao"], quadro["lente"], aspecto)
    u = u - quadro["shift_x"]
    v = v - quadro["shift_y"] * aspecto
    return (float(u.min() + 0.5), float(0.5 - v.max()), float(u.max() + 0.5), float(0.5 - v.min()))


# ----------------------------------------------------------------------
# A foto da fábrica no estúdio (o adesivo que ainda não tem 3D)
# ----------------------------------------------------------------------


def cartao_da_foto(caminho, quadro, caixa_alvo):
    """Um "cartão" com a foto recortada da fábrica, em pé no chão, onde a máquina de referência fica.

    O adesivo sem 3D (o Basquete Home azul) entra no MESMO quadro, no MESMO tamanho da máquina
    de referência (a caixa dela na foto, `caixa_alvo`): o cartão fica de frente para a câmera,
    com o pé no chão (onde o raio do pé da caixa encontra o chão), e dá a sombra de contato e o
    reflexo no chão; ele mesmo não aparece na câmera (a foto entra por cima, no acabamento, com
    as cores dela). Devolve (objeto, caixa da foto em frações do quadro, o PNG recortado).
    """
    from PIL import Image

    with Image.open(caminho) as img:
        img = img.convert("RGBA")
        recorte = img.getbbox() if img.getchannel("A").getextrema()[0] == 255 else img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        img = img.crop(recorte)
        pasta = Path(tempfile.gettempdir()) / "fotos3d-texturas"
        pasta.mkdir(exist_ok=True)
        destino = pasta / ("cartao-" + Path(caminho).stem + ".png")
        img.save(destino)
        largura_img, altura_img = img.size
    aspecto_img = largura_img / altura_img
    x0, y0, x1, y1 = caixa_alvo
    altura_frac = y1 - y0
    largura_frac = altura_frac * aspecto_img / quadro["aspecto"]
    meio_x = (x0 + x1) / 2
    caixa = (meio_x - largura_frac / 2, y0, meio_x + largura_frac / 2, y1)
    # o raio do pé da caixa (em fração do quadro) encontra o chão: a profundidade do cartão
    lente, aspecto = quadro["lente"], quadro["aspecto"]
    v_pe = (0.5 - y1) + quadro["shift_y"] * aspecto
    inc = quadro["inclinacao"]
    # direção do raio no mundo: frente*(0, cos, sin) + cima*(0, -sin, cos) + direita*(1,0,0), com frente = 1
    cima = v_pe * (SENSOR / aspecto) / lente
    dz = math.sin(inc) + cima * math.cos(inc)
    altura_cam = quadro["posicao"][2]
    t = -altura_cam / dz  # quando o raio chega a z = 0
    profundidade = t  # (a componente "frente" do raio é 1)
    # o tamanho do cartão nessa profundidade
    meia_l = (largura_frac / 2) * profundidade * SENSOR / lente
    alt = altura_frac * profundidade * (SENSOR / aspecto) / lente
    u_meio = (meio_x - 0.5) + quadro["shift_x"]
    v_meio = (0.5 - (y0 + y1) / 2) + quadro["shift_y"] * aspecto
    malha = bpy.data.meshes.new("cartao")
    malha.from_pydata(
        [(-meia_l, -alt / 2, 0), (meia_l, -alt / 2, 0), (meia_l, alt / 2, 0), (-meia_l, alt / 2, 0)], [], [(0, 1, 2, 3)])
    uv = malha.uv_layers.new()
    for i, (a, b) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = (a, b)
    obj = bpy.data.objects.new("cartao", malha)
    bpy.context.scene.collection.objects.link(obj)
    camera_pos = mathutils.Vector(quadro["posicao"])
    frente = mathutils.Vector((0, math.cos(inc), math.sin(inc)))
    cima_v = mathutils.Vector((0, -math.sin(inc), math.cos(inc)))
    centro = camera_pos + profundidade * (frente + cima_v * (v_meio * (SENSOR / aspecto) / lente)) + mathutils.Vector(
        (u_meio * profundidade * SENSOR / lente, 0, 0))
    obj.location = centro
    obj.rotation_euler = (math.pi / 2 + inc, 0, 0)
    obj.visible_camera = False
    mat = bpy.data.materials.new("cartao")
    nos, ln = mat.node_tree.nodes, mat.node_tree.links
    for no in list(nos):
        nos.remove(no)
    tex = nos.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(destino))
    emissao = nos.new("ShaderNodeEmission")
    emissao.inputs["Strength"].default_value = 0.9
    transparente = nos.new("ShaderNodeBsdfTransparent")
    mistura = nos.new("ShaderNodeMixShader")
    saida = nos.new("ShaderNodeOutputMaterial")
    ln.new(tex.outputs["Color"], emissao.inputs["Color"])
    ln.new(tex.outputs["Alpha"], mistura.inputs["Fac"])
    ln.new(transparente.outputs["BSDF"], mistura.inputs[1])
    ln.new(emissao.outputs["Emission"], mistura.inputs[2])
    ln.new(mistura.outputs["Shader"], saida.inputs["Surface"])
    obj.data.materials.append(mat)
    return obj, caixa, destino
