"""O showroom da Lazer & Sport, montado no Blender (Cycles): o ambiente das fotos de produto.

O dono, com o print do catálogo (o Air Game Kids e os basquetes no fundo azul liso do estúdio
da seção 96): "esses brinquedos com o fundo azul devem ser de ambiente como falei, nada de
fundos singulares". O padrão é o da seção 64 do LEIA-ME V10 -- o SHOWROOM DA EMPRESA, fiel à
foto de verdade do Boliche Virtual -- e o acabamento é o da seção 96 (o Cycles, a mesma luz de
produto, a mesma nitidez, o OpenImageDenoise): nada de voltar ao three.js colado no fundo.

O lugar (em metros de verdade; a máquina fica em pé no porcelanato, na frente da parede):

  * O NICHO: o painel preto texturizado (o relevo em placas irregulares, como couro ou pedra)
    entre duas colunas de moldura branca, com a PLACA DO LOGO acesa (o logo oficial,
    core/static/images/logoofi.png, como placa: ferramentas/categorias/placa.py -- é a loja da
    empresa); em cima, a SANCA PRETA com os dois perfis de LED e os spots que lavam a parede;
    embaixo, o CANTEIRO BRANCO com as plantas tropicais (modeladas aqui, procedurais: bromélias,
    espadas e palmeiras), o friso de LED e as luzes de baixo que acendem as folhas.
  * À ESQUERDA DO NICHO: a parede com os adesivos de fliperama GENÉRICOS em pixel art (estrela,
    coração, moeda, raio, controle, seta e a trilha de pontinhos -- nada de personagem de
    ninguém), com os spots de cima.
  * À DIREITA DO NICHO: a vitrine de vidro fumê (reflete a loja e deixa ver, desfocadas, as
    prateleiras acesas com caixas e bolas coloridas, genéricas), os montantes e os frisos de LED
    azul.
  * O PISO: o porcelanato claro polido de 60 cm (o rejunte, os veios bem leves, o tom que muda
    de placa para placa), que reflete a máquina e as luzes.
  * O TETO escuro, com os perfis de LED e os spots, e as luzes gerais da loja (macias, mais
    fracas que as do produto: o lugar fica mais escuro que a máquina).

Cada tomada escolhe o CENÁRIO (o que fica atrás da máquina: "plantas", "logo", "fliperama",
"vitrine" ou "canto") e o ÂNGULO da sala (a parede vista de frente ou de lado): a sala é que
gira e anda, a câmera e a máquina ficam onde o enquadramento da seção 96 as pôs (um
enquadramento por máquina). O modo "noite" apaga a loja (ficam os LEDs, a placa e as luzes do
canteiro).

Roda dentro do renderizar.py (o `bpy` do pip, 5.0).
"""

from __future__ import annotations

import math
import random
import tempfile
from pathlib import Path

import bpy
import bmesh
import mathutils

from estudio import linear

RAIZ = Path(__file__).resolve().parents[2]
PLACA = RAIZ / "ferramentas" / "categorias" / "showroom" / "placa-lazer-sport.png"
TEMP = Path(tempfile.gettempdir()) / "fotos3d-showroom"

#: As medidas da loja (m).
ALTURA = 4.3            # o pé-direito
SANCA = 0.55            # a altura da sanca preta do nicho
NICHO = 6.4             # a largura do painel preto
COLUNA = 0.4            # a moldura branca de cada lado do nicho
CANTEIRO = (0.55, 0.55)  # altura e fundo do canteiro
FLIPERAMA = 9.4         # a largura da parede de adesivos
VITRINE = 9.4           # a largura da vitrine
LARGURA = 34.0          # a sala de parede a parede
FUNDO_DA_SALA = 30.0    # da parede do fundo à parede de trás da câmera

#: Onde a máquina fica, em x da parede do fundo (o meio do nicho é 0), em cada cenário.
CENARIOS = {
    "plantas": -1.55,     # o canteiro e o painel atrás; a placa aparece do lado
    "logo": -0.35,        # a placa do logo ao lado da máquina
    "fliperama": -(NICHO / 2 + COLUNA + FLIPERAMA / 2 - 0.6),
    "vitrine": NICHO / 2 + COLUNA + VITRINE / 2 - 0.8,
    "canto": NICHO / 2 + COLUNA * 0.5,  # a coluna branca: o nicho de um lado, a vitrine do outro
}
#: A placa do logo: o meio dela em x (no nicho) e a largura.
PLACA_X = 1.55
PLACA_LARGURA = 1.5

#: As cores (sRGB).
BRANCO = "#E9E6E1"
PRETO_PAINEL = "#121212"
PRETO_SANCA = "#0C0C0C"
TETO = "#1A1A1A"
PISO_1, PISO_2, REJUNTE = "#C9C4BC", "#BFB9B0", "#86807A"
AZUL_LED = "#3B82F6"


# ----------------------------------------------------------------------
# O básico
# ----------------------------------------------------------------------


def _ligar(obj, pai):
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = pai
    return obj


def _caixa(nome, centro, tamanho, mat, pai):
    """Uma caixa (centro x, y, z; tamanho largura, fundo, altura) na sala."""
    malha = bpy.data.meshes.new(nome)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = mathutils.Vector((v.co.x * tamanho[0], v.co.y * tamanho[1], v.co.z * tamanho[2])) + mathutils.Vector(centro)
    bm.to_mesh(malha)
    bm.free()
    obj = bpy.data.objects.new(nome, malha)
    obj.data.materials.append(mat)
    return _ligar(obj, pai)


def _plano(nome, cantos, mat, pai, uv=None):
    """Um quadrilátero pelos quatro cantos (na ordem), com a UV de 0 a 1 (ou `uv`)."""
    malha = bpy.data.meshes.new(nome)
    malha.from_pydata([tuple(c) for c in cantos], [], [(0, 1, 2, 3)])
    camada = malha.uv_layers.new()
    for i, (a, b) in enumerate(uv or ((0, 0), (1, 0), (1, 1), (0, 1))):
        camada.data[i].uv = (a, b)
    obj = bpy.data.objects.new(nome, malha)
    obj.data.materials.append(mat)
    return _ligar(obj, pai)


def _nos(mat):
    nos, ln = mat.node_tree.nodes, mat.node_tree.links
    return nos, ln, nos.get("Principled BSDF")


def mat_pintura(nome, cor, aspereza=0.5, especular=0.5, verniz=0.0):
    mat = bpy.data.materials.new(nome)
    _, _, bsdf = _nos(mat)
    bsdf.inputs["Base Color"].default_value = (*linear(cor), 1)
    bsdf.inputs["Roughness"].default_value = aspereza
    bsdf.inputs["Specular IOR Level"].default_value = especular
    bsdf.inputs["Coat Weight"].default_value = verniz
    return mat


def mat_luz(nome, cor, forca, amostrar=False):
    """O que acende (o LED, o spot, o friso): só a emissão. `amostrar`: ilumina de verdade o que está perto."""
    mat = bpy.data.materials.new(nome)
    nos, ln, bsdf = _nos(mat)
    nos.remove(bsdf)
    emissao = nos.new("ShaderNodeEmission")
    emissao.inputs["Color"].default_value = (*linear(cor), 1)
    emissao.inputs["Strength"].default_value = forca
    ln.new(emissao.outputs["Emission"], nos.get("Material Output").inputs["Surface"])
    mat.cycles.emission_sampling = "AUTO" if amostrar else "NONE"
    mat["forca"] = forca
    return mat


def _luz(nome, tipo, pos, energia, cor, pai, alvo=None, tamanho=0.1, cone=None, borda=0.5, forma="DISK"):
    dados = bpy.data.lights.new(nome, tipo)
    dados.energy = energia
    dados.color = linear(cor) if isinstance(cor, str) else cor
    if tipo == "SPOT":
        dados.spot_size = math.radians(cone or 60)
        dados.spot_blend = borda
        dados.shadow_soft_size = tamanho
    elif tipo == "AREA":
        dados.shape = forma
        dados.size = tamanho
    else:
        dados.shadow_soft_size = tamanho
    obj = bpy.data.objects.new(nome, dados)
    obj.location = pos
    if alvo is not None:
        obj.rotation_euler = (mathutils.Vector(alvo) - mathutils.Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    obj.visible_camera = False
    obj["energia"] = energia
    return _ligar(obj, pai)


# ----------------------------------------------------------------------
# Os materiais da loja
# ----------------------------------------------------------------------


def mat_porcelanato(placa=0.6, semente=19):
    """O porcelanato claro polido: as placas de 60 cm, o rejunte, o tom de cada placa e os veios leves."""
    mat = bpy.data.materials.new("porcelanato")
    nos, ln, bsdf = _nos(mat)
    coord = nos.new("ShaderNodeTexCoord")
    tijolo = nos.new("ShaderNodeTexBrick")
    tijolo.offset = 0.0
    tijolo.squash = 1.0
    tijolo.inputs["Scale"].default_value = 1.0
    tijolo.inputs["Brick Width"].default_value = placa
    tijolo.inputs["Row Height"].default_value = placa
    tijolo.inputs["Mortar Size"].default_value = 0.0035
    tijolo.inputs["Mortar Smooth"].default_value = 0.6
    tijolo.inputs["Bias"].default_value = 0.0
    tijolo.inputs["Color1"].default_value = (*linear(PISO_1), 1)
    tijolo.inputs["Color2"].default_value = (*linear(PISO_2), 1)
    tijolo.inputs["Mortar"].default_value = (*linear(REJUNTE), 1)
    ln.new(coord.outputs["Object"], tijolo.inputs["Vector"])
    # os veios: o ruído esticado, bem leve (multiplica a cor)
    mapa = nos.new("ShaderNodeMapping")
    mapa.inputs["Scale"].default_value = (0.45, 1.6, 1.0)
    mapa.inputs["Rotation"].default_value = (0, 0, math.radians(31))
    mapa.inputs["Location"].default_value = (semente * 0.37, semente * 0.11, 0)
    ln.new(coord.outputs["Object"], mapa.inputs["Vector"])
    ruido = nos.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 2.2
    ruido.inputs["Detail"].default_value = 9.0
    ruido.inputs["Roughness"].default_value = 0.62
    ruido.inputs["Distortion"].default_value = 1.4
    ln.new(mapa.outputs["Vector"], ruido.inputs["Vector"])
    veio = nos.new("ShaderNodeValToRGB")
    veio.color_ramp.elements[0].position = 0.46
    veio.color_ramp.elements[0].color = (0.86, 0.85, 0.84, 1)
    veio.color_ramp.elements[1].position = 0.56
    veio.color_ramp.elements[1].color = (1, 1, 1, 1)
    ln.new(ruido.outputs["Fac"], veio.inputs["Fac"])
    mistura = nos.new("ShaderNodeMix")
    mistura.data_type = "RGBA"
    mistura.blend_type = "MULTIPLY"
    mistura.inputs["Factor"].default_value = 1.0
    ln.new(tijolo.outputs["Color"], mistura.inputs["A"])
    ln.new(veio.outputs["Color"], mistura.inputs["B"])
    ln.new(mistura.outputs["Result"], bsdf.inputs["Base Color"])
    # o polido: a placa lisa e brilhante; o rejunte fosco e afundado
    aspereza = nos.new("ShaderNodeMapRange")
    aspereza.inputs["To Min"].default_value = 0.075
    aspereza.inputs["To Max"].default_value = 0.6
    ln.new(tijolo.outputs["Fac"], aspereza.inputs["Value"])
    ln.new(aspereza.outputs["Result"], bsdf.inputs["Roughness"])
    relevo = nos.new("ShaderNodeBump")
    relevo.inputs["Strength"].default_value = 0.35
    relevo.inputs["Distance"].default_value = 0.002
    relevo.invert = True
    ln.new(tijolo.outputs["Fac"], relevo.inputs["Height"])
    ln.new(relevo.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.55
    return mat


def mat_painel_preto():
    """O painel preto texturizado: as placas irregulares em relevo (Voronoi), acetinado."""
    mat = bpy.data.materials.new("painel-preto")
    nos, ln, bsdf = _nos(mat)
    coord = nos.new("ShaderNodeTexCoord")
    voronoi = nos.new("ShaderNodeTexVoronoi")
    voronoi.feature = "DISTANCE_TO_EDGE"
    voronoi.inputs["Scale"].default_value = 2.1
    voronoi.inputs["Randomness"].default_value = 1.0
    ln.new(coord.outputs["Object"], voronoi.inputs["Vector"])
    borda = nos.new("ShaderNodeMapRange")
    borda.inputs["From Min"].default_value = 0.0
    borda.inputs["From Max"].default_value = 0.025
    ln.new(voronoi.outputs["Distance"], borda.inputs["Value"])
    ruido = nos.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 14.0
    ruido.inputs["Detail"].default_value = 6.0
    ln.new(coord.outputs["Object"], ruido.inputs["Vector"])
    soma = nos.new("ShaderNodeMath")
    soma.operation = "MULTIPLY_ADD"
    soma.inputs[1].default_value = 0.15
    ln.new(ruido.outputs["Fac"], soma.inputs[0])
    ln.new(borda.outputs["Result"], soma.inputs[2])
    relevo = nos.new("ShaderNodeBump")
    relevo.inputs["Strength"].default_value = 0.22
    relevo.inputs["Distance"].default_value = 0.006
    ln.new(soma.outputs["Value"], relevo.inputs["Height"])
    ln.new(relevo.outputs["Normal"], bsdf.inputs["Normal"])
    tom = nos.new("ShaderNodeMapRange")
    tom.inputs["To Min"].default_value = 0.75
    tom.inputs["To Max"].default_value = 1.15
    ln.new(ruido.outputs["Fac"], tom.inputs["Value"])
    cor = nos.new("ShaderNodeMix")
    cor.data_type = "RGBA"
    cor.blend_type = "MULTIPLY"
    cor.inputs["Factor"].default_value = 1.0
    cor.inputs["A"].default_value = (*linear(PRETO_PAINEL), 1)
    ln.new(tom.outputs["Result"], cor.inputs["B"])
    ln.new(cor.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.48
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    return mat


def mat_vidro_fume(tom="#9AA6B8"):
    """O vidro escuro da vitrine (fumê), como placa fina: o reflexo pela lei de Fresnel (mais forte de lado)
    e, através dele, escurecido, o que está lá dentro (sem desviar o raio: é uma lâmina)."""
    mat = bpy.data.materials.new("vidro-fume")
    nos, ln, bsdf = _nos(mat)
    nos.remove(bsdf)
    fresnel = nos.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.52
    reforco = nos.new("ShaderNodeMath")  # (a placa tem duas faces: reflete um tanto mais que uma)
    reforco.operation = "MULTIPLY"
    reforco.inputs[1].default_value = 1.6
    reforco.use_clamp = True
    ln.new(fresnel.outputs["Fac"], reforco.inputs[0])
    atravessa = nos.new("ShaderNodeBsdfTransparent")
    atravessa.inputs["Color"].default_value = (*linear(tom), 1)
    brilho = nos.new("ShaderNodeBsdfGlossy")
    brilho.inputs["Roughness"].default_value = 0.0
    mistura = nos.new("ShaderNodeMixShader")
    ln.new(reforco.outputs["Value"], mistura.inputs["Fac"])
    ln.new(atravessa.outputs["BSDF"], mistura.inputs[1])
    ln.new(brilho.outputs["BSDF"], mistura.inputs[2])
    ln.new(mistura.outputs["Shader"], nos.get("Material Output").inputs["Surface"])
    return mat


def mat_imagem(nome, caminho, aspereza=0.6, emissao=0.0, alfa=False, verniz=0.0):
    """Um material com a imagem (a placa, os adesivos), com emissão opcional (o que acende)."""
    mat = bpy.data.materials.new(nome)
    nos, ln, bsdf = _nos(mat)
    tex = nos.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(caminho), check_existing=True)
    tex.image.pack()
    tex.interpolation = "Cubic"
    tex.extension = "CLIP"  # (sem repetir: a borda de baixo da placa não reaparece em cima)
    ln.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if emissao:
        ln.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emissao
    if alfa:
        ln.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = aspereza
    bsdf.inputs["Coat Weight"].default_value = verniz
    bsdf.inputs["Coat Roughness"].default_value = 0.08
    mat["emissao"] = emissao
    return mat


def mat_folha(nome, cor, semente):
    """A folha: o verde com o tom que muda de folha em folha (o atributo `tom`), a nervura e a luz que atravessa."""
    mat = bpy.data.materials.new(nome)
    nos, ln, bsdf = _nos(mat)
    saida = nos.get("Material Output")
    atributo = nos.new("ShaderNodeAttribute")
    atributo.attribute_name = "tom"
    uv = nos.new("ShaderNodeUVMap")
    separa = nos.new("ShaderNodeSeparateXYZ")
    ln.new(uv.outputs["UV"], separa.inputs[0])
    # o verde: mais escuro na base, mais claro na ponta; a nervura (u = 0,5) mais clara
    rampa = nos.new("ShaderNodeValToRGB")
    base = linear(cor)
    rampa.color_ramp.elements[0].color = (*[c * 0.55 for c in base], 1)
    rampa.color_ramp.elements[1].color = (*[min(1, c * 1.35) for c in base], 1)
    ln.new(separa.outputs["Y"], rampa.inputs["Fac"])
    nervura = nos.new("ShaderNodeMath")
    nervura.operation = "PINGPONG"
    nervura.inputs[1].default_value = 0.5
    ln.new(separa.outputs["X"], nervura.inputs[0])
    linha = nos.new("ShaderNodeMapRange")
    linha.inputs["From Min"].default_value = 0.47
    linha.inputs["From Max"].default_value = 0.5
    linha.inputs["To Min"].default_value = 0.0
    linha.inputs["To Max"].default_value = 0.35
    ln.new(nervura.outputs["Value"], linha.inputs["Value"])
    clara = nos.new("ShaderNodeMix")
    clara.data_type = "RGBA"
    clara.blend_type = "SCREEN"
    clara.inputs["B"].default_value = (0.55, 0.62, 0.35, 1)
    ln.new(linha.outputs["Result"], clara.inputs["Factor"])
    ln.new(rampa.outputs["Color"], clara.inputs["A"])
    variar = nos.new("ShaderNodeHueSaturation")
    ln.new(clara.outputs["Result"], variar.inputs["Color"])
    matiz = nos.new("ShaderNodeMapRange")
    matiz.inputs["To Min"].default_value = 0.47
    matiz.inputs["To Max"].default_value = 0.53
    ln.new(atributo.outputs["Fac"], matiz.inputs["Value"])
    ln.new(matiz.outputs["Result"], variar.inputs["Hue"])
    valor = nos.new("ShaderNodeMapRange")
    valor.inputs["To Min"].default_value = 0.78
    valor.inputs["To Max"].default_value = 1.18
    ln.new(atributo.outputs["Fac"], valor.inputs["Value"])
    ln.new(valor.outputs["Result"], variar.inputs["Value"])
    ln.new(variar.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.42
    bsdf.inputs["Specular IOR Level"].default_value = 0.45
    bsdf.inputs["Coat Weight"].default_value = 0.25
    bsdf.inputs["Coat Roughness"].default_value = 0.18
    # a luz de baixo atravessa a folha (o verde-claro aceso das plantas do canteiro)
    translucida = nos.new("ShaderNodeBsdfTranslucent")
    ln.new(variar.outputs["Color"], translucida.inputs["Color"])
    mistura = nos.new("ShaderNodeMixShader")
    mistura.inputs["Fac"].default_value = 0.28
    ln.new(bsdf.outputs["BSDF"], mistura.inputs[1])
    ln.new(translucida.outputs["BSDF"], mistura.inputs[2])
    ln.new(mistura.outputs["Shader"], saida.inputs["Surface"])
    return mat


# ----------------------------------------------------------------------
# As plantas (procedurais: nada baixado)
# ----------------------------------------------------------------------


def _folha(bm, tom, base, azimute, comprimento, largura, elevacao, queda, torcao=0.0, dobra=0.22, segmentos=12,
           ponta=0.85, alargar=0.12):
    """Uma folha: a fita que sai da `base` e arqueia (a `queda`), afinando até a ponta, com a nervura dobrada."""
    direcao = mathutils.Vector((math.cos(azimute), math.sin(azimute), 0))
    lateral = mathutils.Vector((-math.sin(azimute), math.cos(azimute), 0))
    linhas = []
    pontos = []
    for i in range(segmentos + 1):
        t = i / segmentos
        horizontal = comprimento * t * math.cos(elevacao) + comprimento * queda * 0.35 * t * t
        altura = comprimento * (t * math.sin(elevacao) - queda * t * t)
        p = mathutils.Vector(base) + direcao * horizontal + mathutils.Vector((0, 0, altura))
        pontos.append(p)
    for i, p in enumerate(pontos):
        t = i / segmentos
        # a largura: estreita no pé, larga logo depois, afinando até a ponta
        forma = min(1.0, t / alargar) * (1 - t ** 1.6) ** ponta if t < 1 else 0.0
        w = largura * max(forma, 0.0) / 2
        ang = torcao * t
        lado = lateral * math.cos(ang) + mathutils.Vector((0, 0, 1)) * math.sin(ang) * 0.4
        cima = mathutils.Vector((0, 0, 1)) * (dobra * w * 2)
        linhas.append([bm.verts.new(p - lado * w - cima * 0.0), bm.verts.new(p + cima), bm.verts.new(p + lado * w)])
    camada_uv = bm.loops.layers.uv.verify()
    camada_tom = bm.loops.layers.float_color.get("tom") or bm.loops.layers.float_color.new("tom")
    for i in range(segmentos):
        for j in range(2):
            vs = (linhas[i][j], linhas[i][j + 1], linhas[i + 1][j + 1], linhas[i + 1][j])
            face = bm.faces.new(vs)
            face.smooth = True
            for laco in face.loops:
                ii = next(k for k in range(segmentos + 1) if laco.vert in linhas[k])
                jj = linhas[ii].index(laco.vert)
                laco[camada_uv].uv = (jj / 2, ii / segmentos)
                laco[camada_tom] = (tom, tom, tom, 1.0)


def _planta(nome, tipo, pos, altura, rnd, mats, pai):
    """Uma planta inteira (um objeto): a `bromelia` (a roseta de folhas arqueadas), a `espada` (as folhas em pé,
    a espada-de-são-jorge) ou a `palmeira` (a areca: as frondes arqueadas cheias de folíolos)."""
    bm = bmesh.new()
    if tipo == "bromelia":
        n = rnd.randint(24, 32)
        for k in range(n):
            az = k * 2.39996 + rnd.uniform(-0.2, 0.2)
            dentro = 1 - k / n
            comp = altura * (0.7 + 0.5 * (1 - dentro)) * rnd.uniform(0.85, 1.1)
            elev = math.radians(30 + 50 * dentro + rnd.uniform(-6, 6))
            _folha(bm, rnd.random(), pos, az, comp, comp * rnd.uniform(0.1, 0.14), elev, rnd.uniform(0.35, 0.65) * (1.2 - dentro * 0.5),
                   torcao=rnd.uniform(-0.6, 0.6), dobra=0.28, ponta=0.7)
    elif tipo == "espada":
        n = rnd.randint(8, 12)
        for k in range(n):
            az = k * 2.39996 + rnd.uniform(-0.3, 0.3)
            r = rnd.uniform(0.0, 0.08)
            base = (pos[0] + r * math.cos(az), pos[1] + r * math.sin(az), pos[2])
            comp = altura * rnd.uniform(0.65, 1.05)
            _folha(bm, rnd.random(), base, az, comp, comp * rnd.uniform(0.1, 0.13), math.radians(rnd.uniform(72, 87)),
                   rnd.uniform(0.0, 0.08), torcao=rnd.uniform(-1.2, 1.2), dobra=0.12, ponta=0.45, alargar=0.25)
    else:  # a palmeira (areca): as frondes saem do chão, arqueiam e caem; os folíolos dos dois lados
        n = rnd.randint(7, 10)
        for k in range(n):
            az = k * 2.39996 + rnd.uniform(-0.25, 0.25)
            comp = altura * rnd.uniform(0.8, 1.1)
            elev = math.radians(rnd.uniform(58, 80))
            queda = rnd.uniform(0.35, 0.55)
            direcao = mathutils.Vector((math.cos(az), math.sin(az), 0))
            segs = 18
            raque = []
            for i in range(segs + 1):
                t = i / segs
                h = comp * t * math.cos(elev) + comp * queda * 0.35 * t * t
                z = comp * (t * math.sin(elev) - queda * t * t)
                raque.append(mathutils.Vector(pos) + direcao * h + mathutils.Vector((0, 0, z)))
            _folha(bm, rnd.random(), pos, az, comp, 0.018, elev, queda, dobra=0.0, ponta=0.2, alargar=0.05, segmentos=segs)
            tom = rnd.random()
            for i in range(4, segs):
                t = i / segs
                p = raque[i]
                tangente = (raque[i + 1] - raque[i - 1]).normalized()
                az_t = math.atan2(tangente.y, tangente.x)
                tamanho = comp * 0.36 * math.sin(math.pi * min(1.0, (t - 0.15) / 0.9)) + 0.04
                for lado in (-1, 1):
                    az_f = az_t + lado * math.radians(rnd.uniform(55, 75))
                    _folha(bm, (tom + rnd.uniform(-0.1, 0.1)) % 1, tuple(p), az_f, tamanho, tamanho * 0.13,
                           math.asin(max(-0.9, min(0.9, tangente.z))) * 0.5 + math.radians(rnd.uniform(-5, 15)),
                           rnd.uniform(0.35, 0.6), torcao=rnd.uniform(-0.4, 0.4), dobra=0.18, ponta=0.8, segmentos=5)
    malha = bpy.data.meshes.new(nome)
    bm.to_mesh(malha)
    bm.free()
    obj = bpy.data.objects.new(nome, malha)
    obj.data.materials.append(mats[tipo])
    _ligar(obj, pai)
    return obj


# ----------------------------------------------------------------------
# Os adesivos de fliperama (pixel art genérica)
# ----------------------------------------------------------------------

DESENHOS = {
    "estrela": ["..#..", ".###.", "#####", ".#.#.", "#...#"],
    "coracao": [".#.#.", "#####", "#####", ".###.", "..#.."],
    "moeda": [".###.", "##.##", "#.#.#", "##.##", ".###."],
    "raio": ["..##", ".##.", "####", ".##.", "##.."],
    "controle": [".#####.", "#.###.#", "##.#.##", "#######", "##...##"],
    "seta": ["..#..", ".###.", "#####", "..#..", "..#.."],
}
CORES_ADESIVOS = ["#FACC15", "#22D3EE", "#F472B6", "#4ADE80", "#FB923C", "#A78BFA"]


def textura_fliperama(largura=3072, altura=1408, semente=31):
    """A parede de adesivos: o fundo grafite e os desenhos em pixel, de vários tamanhos, e a trilha de pontinhos."""
    from PIL import Image, ImageDraw

    TEMP.mkdir(parents=True, exist_ok=True)
    destino = TEMP / f"adesivos-fliperama-{semente}-v3.png"
    if destino.exists():
        return destino
    rnd = random.Random(semente)
    img = Image.new("RGB", (largura, altura), "#17171F")
    d = ImageDraw.Draw(img)
    # um tico de textura no fundo (a parede pintada)
    for _ in range(9000):
        x, y = rnd.randrange(largura), rnd.randrange(altura)
        c = 23 + rnd.randint(-3, 3)
        d.point((x, y), fill=(c, c, c + 7))
    nomes = list(DESENHOS)
    ocupado = []
    px = 13
    for i in range(120):
        forma = DESENHOS[nomes[i % len(nomes)]]
        s = px * rnd.choice((1, 1, 2, 2, 3))
        larg, alt = len(forma[0]) * s, len(forma) * s
        for _tentativa in range(30):
            x0 = rnd.randrange(20, largura - larg - 20)
            y0 = rnd.randrange(int(altura * 0.06), int(altura * 0.86) - alt)
            caixa = (x0 - 24, y0 - 24, x0 + larg + 24, y0 + alt + 24)
            if all(caixa[2] < o[0] or caixa[0] > o[2] or caixa[3] < o[1] or caixa[1] > o[3] for o in ocupado):
                break
        else:
            continue
        ocupado.append(caixa)
        cor = CORES_ADESIVOS[(i * 5) % len(CORES_ADESIVOS)]
        for y, linha in enumerate(forma):
            for x, ch in enumerate(linha):
                if ch == "#":
                    d.rectangle((x0 + x * s, y0 + y * s, x0 + x * s + s - 3, y0 + y * s + s - 3), fill=cor)
    for i in range(48):  # a trilha de pontinhos, como de jogo
        x = 14 + i * (largura / 48)
        d.rectangle((x, altura * 0.9, x + 14, altura * 0.9 + 14), fill="#FDE68A")
    img.save(destino)
    return destino


# ----------------------------------------------------------------------
# A sala
# ----------------------------------------------------------------------


class Showroom:
    """O showroom montado (tudo filho do vazio `sala`): `posicionar` põe o cenário atrás da máquina."""

    def __init__(self, semente=19, plantas=True, altura_da_maquina=2.0):
        self.rnd = random.Random(semente)
        # a placa do logo: o alto dela um tanto acima do alto da máquina (inteira na foto, ao lado
        # dela), nunca abaixo das plantas nem dentro da sanca
        self.placa_topo = min(ALTURA - SANCA - 0.3, max(2.45, altura_da_maquina + 0.45))
        self.sala = bpy.data.objects.new("sala", None)
        bpy.context.scene.collection.objects.link(self.sala)
        self.luzes_da_loja = []   # (obj, energia): apagam à noite
        self.luzes_acesas = []    # (obj, energia): os LEDs e o canteiro (ficam à noite, mais fortes)
        self.emissores_da_loja = []  # (material, força): os spots do teto, apagados à noite
        self.placa_obj = None
        self._montar(plantas)

    # --- a montagem -------------------------------------------------------------------------
    def _montar(self, plantas):
        pai = self.sala
        branco = mat_pintura("branco", BRANCO, aspereza=0.55, especular=0.4)
        self.branco = branco
        piso = mat_porcelanato()
        meia = LARGURA / 2
        # o piso (y < 0 é a loja; a parede do fundo em y = 0)
        _plano("piso", ((-meia, -FUNDO_DA_SALA, 0), (meia, -FUNDO_DA_SALA, 0), (meia, 0.5, 0), (-meia, 0.5, 0)), piso, pai)
        # o teto escuro
        teto = mat_pintura("teto", TETO, aspereza=0.9, especular=0.2)
        _plano("teto", ((-meia, 0.5, ALTURA), (meia, 0.5, ALTURA), (meia, -FUNDO_DA_SALA, ALTURA), (-meia, -FUNDO_DA_SALA, ALTURA)), teto, pai)
        # as paredes brancas: a de trás da câmera e as dos lados (aparecem nos reflexos)
        _plano("parede-tras", ((meia, -FUNDO_DA_SALA, 0), (-meia, -FUNDO_DA_SALA, 0), (-meia, -FUNDO_DA_SALA, ALTURA), (meia, -FUNDO_DA_SALA, ALTURA)), branco, pai)
        fliperama_tex = textura_fliperama()
        adesivos = mat_imagem("adesivos-fliperama", fliperama_tex, aspereza=0.38, verniz=0.3)
        _plano("parede-esquerda", ((-meia, 0.5, 0), (-meia, -FUNDO_DA_SALA, 0), (-meia, -FUNDO_DA_SALA, ALTURA), (-meia, 0.5, ALTURA)),
               adesivos, pai, uv=((0, 0), (FUNDO_DA_SALA / FLIPERAMA, 0), (FUNDO_DA_SALA / FLIPERAMA, 1), (0, 1)))
        _plano("parede-direita", ((meia, -FUNDO_DA_SALA, 0), (meia, 0.5, 0), (meia, 0.5, ALTURA), (meia, -FUNDO_DA_SALA, ALTURA)), branco, pai)
        # a parede do fundo, branca, atrás de tudo (aberta no vão da vitrine: lá dentro é a loja)
        v0, v1 = NICHO / 2 + COLUNA, NICHO / 2 + COLUNA + VITRINE
        for x0, x1 in ((-meia, v0), (v1, meia)):
            _plano("parede-fundo", ((x0, 0.02, 0), (x1, 0.02, 0), (x1, 0.02, ALTURA), (x0, 0.02, ALTURA)), branco, pai)
        self._nicho(pai, branco, plantas)
        x0 = -(NICHO / 2 + COLUNA)
        self._fliperama(pai, adesivos, x0 - FLIPERAMA, x0)
        x1 = NICHO / 2 + COLUNA
        self._vitrine(pai, x1, x1 + VITRINE)
        self._teto(pai)

    def _nicho(self, pai, branco, plantas):
        meio = NICHO / 2
        topo = ALTURA - SANCA
        _plano("painel-preto", ((-meio, 0.0, 0), (meio, 0.0, 0), (meio, 0.0, topo), (-meio, 0.0, topo)), mat_painel_preto(), pai)
        for lado in (-1, 1):  # as colunas de moldura branca
            _caixa(f"coluna-{lado}", (lado * (meio + COLUNA / 2), -0.25, ALTURA / 2), (COLUNA, 0.5, ALTURA), branco, pai)
        # a sanca preta com os dois perfis de LED e os spots
        sanca = mat_pintura("sanca", PRETO_SANCA, aspereza=0.55, especular=0.35)
        _caixa("sanca", (0, -0.25, ALTURA - SANCA / 2), (NICHO, 0.5, SANCA), sanca, pai)
        led = mat_luz("led-sanca", "#FFFFFF", 9.0)
        for y in (-0.47, -0.03):
            _caixa("perfil-led", (0, y, topo - 0.012), (NICHO - 0.2, 0.022, 0.012), led, pai)
        lata = mat_pintura("lata-spot", "#1A1A1A", aspereza=0.35, especular=0.6)
        disco = mat_luz("spot-sanca", "#FFF1D8", 30.0)
        for i in range(-2, 3):
            x = i * 1.25
            _caixa(f"spot-{i}", (x, -0.25, topo - 0.05), (0.09, 0.09, 0.1), lata, pai)
            _caixa(f"spot-luz-{i}", (x, -0.25, topo - 0.101), (0.05, 0.05, 0.002), disco, pai)
            luz = _luz(f"spot-sanca-{i}", "SPOT", (x, -0.3, topo - 0.12), 40.0, "#FFE9CC", pai,
                       alvo=(x, 0.0, 0.9), tamanho=0.03, cone=55, borda=0.7)
            self.luzes_da_loja.append((luz, 40.0))
        # a placa do logo, acesa (o branco e o vermelho acesos; o alvo, um tanto)
        if PLACA.exists():
            from PIL import Image

            with Image.open(PLACA) as img:
                proporcao = img.height / img.width
            alt = PLACA_LARGURA * proporcao
            z = self.placa_topo - alt / 2
            placa = mat_imagem("placa", PLACA, aspereza=0.35, emissao=1.6, alfa=True)
            meia_l, meia_a = PLACA_LARGURA / 2, alt / 2
            obj = _plano("placa", ((-meia_l, 0, -meia_a), (meia_l, 0, -meia_a), (meia_l, 0, meia_a), (-meia_l, 0, meia_a)), placa, pai)
            obj.location = (PLACA_X, -0.03, z)  # (a origem no meio: a tomada pode baixar e diminuir a placa)
            self.placa_obj = obj
            self.placa_meia_altura = meia_a
        # o canteiro branco com o friso de LED, a terra e as plantas com a luz de baixo
        ca, cp = CANTEIRO
        largura = NICHO - 0.2
        _caixa("canteiro", (0, -cp / 2, ca / 2), (largura, cp, ca), branco, pai)
        friso = mat_luz("friso-canteiro", "#FFFFFF", 6.0, amostrar=True)
        _caixa("friso-canteiro", (0, -cp - 0.012, 0.035), (largura - 0.1, 0.012, 0.02), friso, pai)
        terra = mat_pintura("terra", "#2B1D14", aspereza=1.0, especular=0.2)
        _caixa("terra", (0, -cp / 2, ca + 0.005), (largura - 0.08, cp - 0.08, 0.02), terra, pai)
        seixos = mat_pintura("seixos", "#A49D93", aspereza=0.6, especular=0.4)
        rnd = self.rnd
        bm = bmesh.new()
        for _ in range(260):  # os seixos por cima da terra
            x = rnd.uniform(-largura / 2 + 0.06, largura / 2 - 0.06)
            y = rnd.uniform(-cp + 0.06, -0.06)
            r = rnd.uniform(0.012, 0.024)
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r,
                                       matrix=mathutils.Matrix.Translation((x, y, ca + 0.012)) @ mathutils.Matrix.Diagonal((1, 1, 0.55, 1)))
        malha = bpy.data.meshes.new("seixos")
        bm.to_mesh(malha)
        bm.free()
        obj = bpy.data.objects.new("seixos", malha)
        obj.data.materials.append(seixos)
        _ligar(obj, pai)
        if not plantas:
            return
        mats = {
            "bromelia": mat_folha("folha-bromelia", "#3F7F2E", 1),
            "espada": mat_folha("folha-espada", "#2F6A35", 2),
            "palmeira": mat_folha("folha-palmeira", "#4C8A30", 3),
        }
        tipos = ("palmeira", "bromelia", "espada", "bromelia", "palmeira", "espada", "bromelia", "palmeira", "bromelia", "espada",
                 "palmeira")
        n = len(tipos)
        for i, tipo in enumerate(tipos):
            x = -largura / 2 + 0.35 + (i + rnd.uniform(0.2, 0.8)) * ((largura - 0.7) / n)
            y = -cp / 2 + rnd.uniform(-0.08, 0.08)
            altura = {"bromelia": rnd.uniform(0.55, 0.75), "espada": rnd.uniform(0.7, 1.0), "palmeira": rnd.uniform(1.0, 1.35)}[tipo]
            _planta(f"planta-{i}", tipo, (x, y, ca + 0.01), altura, rnd, mats, pai)
            if i % 2 == 0:  # a luz de baixo (o embutido no canteiro), quente
                luz = _luz(f"luz-planta-{i}", "SPOT", (x + 0.12, -cp + 0.1, ca + 0.03), 22.0, "#FFCF8A", pai,
                           alvo=(x, -0.05, ca + 1.6), tamanho=0.02, cone=70, borda=0.8)
                self.luzes_acesas.append((luz, 22.0))

    def _fliperama(self, pai, adesivos, x0, x1):
        _plano("fliperama", ((x0, -0.01, 0), (x1, -0.01, 0), (x1, -0.01, ALTURA), (x0, -0.01, ALTURA)), adesivos, pai)
        for i, x in enumerate((x0 + 1.5, (x0 + x1) / 2, x1 - 1.5)):  # os spots que lavam a parede
            luz = _luz(f"spot-fliperama-{i}", "SPOT", (x, -1.1, ALTURA - 0.08), 90.0, "#FFF0DC", pai,
                       alvo=(x, 0.0, 1.0), tamanho=0.04, cone=70, borda=0.8)
            self.luzes_da_loja.append((luz, 90.0))

    def _vitrine(self, pai, x0, x1):
        """A vitrine: o vidro escuro (fumê) de verdade, que reflete a loja e deixa ver lá dentro as prateleiras
        acesas (desfocadas), os montantes e os frisos de LED azul."""
        vidro = mat_vidro_fume()
        _plano("vitrine", ((x0, -0.04, 0.0), (x1, -0.04, 0.0), (x1, -0.04, ALTURA), (x0, -0.04, ALTURA)), vidro, pai)
        fundo = mat_pintura("fundo-vitrine", "#3A4250", aspereza=0.7, especular=0.3)
        _plano("fundo-vitrine", ((x0, 1.3, 0.0), (x1, 1.3, 0.0), (x1, 1.3, ALTURA), (x0, 1.3, ALTURA)), fundo, pai)
        _plano("piso-vitrine", ((x0, -0.03, 0.001), (x1, -0.03, 0.001), (x1, 1.3, 0.001), (x0, 1.3, 0.001)), fundo, pai)
        _plano("teto-vitrine", ((x0, 1.3, ALTURA - 0.3), (x1, 1.3, ALTURA - 0.3), (x1, -0.03, ALTURA - 0.3), (x0, -0.03, ALTURA - 0.3)), fundo, pai)
        for x in (x0, x1):
            _plano("lado-vitrine", ((x, -0.03, 0), (x, 1.3, 0), (x, 1.3, ALTURA), (x, -0.03, ALTURA)), fundo, pai)
        prateleira = mat_pintura("prateleira", "#D8D8D8", aspereza=0.3, especular=0.5)
        luz_prateleira = mat_luz("luz-prateleira", "#FFF4E6", 14.0, amostrar=True)
        self.emissores_da_loja.append((luz_prateleira, 14.0))
        rnd = random.Random(7)
        cores = ("#FACC15", "#22D3EE", "#F472B6", "#4ADE80", "#FB923C", "#A78BFA", "#F8FAFC")
        enfeites = [mat_pintura(f"enfeite-{i}", c, aspereza=0.35, especular=0.5) for i, c in enumerate(cores)]
        for k in range(3):
            z = 0.75 + k * 0.85
            _caixa(f"prateleira-{k}", ((x0 + x1) / 2, 0.85, z), (x1 - x0 - 0.3, 0.5, 0.03), prateleira, pai)
            _caixa(f"luz-prateleira-{k}", ((x0 + x1) / 2, 0.7, z - 0.02), (x1 - x0 - 0.4, 0.04, 0.01), luz_prateleira, pai)
            # o que está exposto: caixas e bolas coloridas, genéricas (nada de marca)
            x = x0 + 0.4
            while x < x1 - 0.5:
                largura = rnd.uniform(0.18, 0.4)
                altura = rnd.uniform(0.15, 0.45)
                mat = rnd.choice(enfeites)
                if rnd.random() < 0.35:
                    bm = bmesh.new()
                    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=altura / 2,
                                              matrix=mathutils.Matrix.Translation((x + largura / 2, 0.85, z + 0.015 + altura / 2)))
                    malha = bpy.data.meshes.new("bola")
                    bm.to_mesh(malha)
                    bm.free()
                    for f in malha.polygons:
                        f.use_smooth = True
                    obj = bpy.data.objects.new("bola", malha)
                    obj.data.materials.append(mat)
                    _ligar(obj, pai)
                else:
                    _caixa("caixa-exposta", (x + largura / 2, 0.85, z + 0.015 + altura / 2), (largura, 0.3, altura), mat, pai)
                x += largura + rnd.uniform(0.15, 0.5)
        montante = mat_pintura("montante", "#1F2937", aspereza=0.35, especular=0.6)
        n = 4
        for i in range(n + 1):
            x = x0 + 0.1 + i * (x1 - x0 - 0.2) / n
            _caixa(f"montante-{i}", (x, -0.08, ALTURA / 2), (0.07, 0.08, ALTURA), montante, pai)
        led = mat_luz("friso-azul", AZUL_LED, 14.0, amostrar=True)
        for z in (ALTURA - 0.45, 0.25):
            _caixa("friso-azul", ((x0 + x1) / 2, -0.11, z), (x1 - x0, 0.03, 0.03), led, pai)
        for i, x in enumerate((x0 + 1.6, (x0 + x1) / 2, x1 - 1.6)):  # os spots do corredor da vitrine
            luz = _luz(f"spot-vitrine-{i}", "SPOT", (x, -1.4, ALTURA - 0.08), 70.0, "#FFF0DC", pai,
                       alvo=(x, -0.8, 0.0), tamanho=0.04, cone=75, borda=0.8)
            self.luzes_da_loja.append((luz, 70.0))

    def _teto(self, pai):
        led = mat_luz("perfil-teto", "#FFFFFF", 7.0)
        disco = mat_luz("spot-teto", "#FFE8C4", 20.0)
        self.emissores_da_loja += [(led, 7.0), (disco, 20.0)]
        for k in range(7):
            y = -1.4 - k * 2.2
            _caixa(f"perfil-teto-{k}", (0, y, ALTURA - 0.01), (LARGURA - 4, 0.05, 0.015), led, pai)
            for i in range(-9, 10):
                x = i * 1.6 + (k % 2) * 0.8
                _caixa(f"spot-teto-{k}-{i}", (x, y - 1.1, ALTURA - 0.006), (0.09, 0.09, 0.01), disco, pai)
        # a luz geral da loja: as placas grandes e macias do teto (mais fracas que as do produto)
        for i, (x, y) in enumerate(((-6, -3.5), (0, -3.5), (6, -3.5), (-6, -9), (0, -9), (6, -9))):
            luz = _luz(f"geral-{i}", "AREA", (x, y, ALTURA - 0.05), 110.0, "#FFF2E2", pai, alvo=(x, y, 0), tamanho=2.4)
            self.luzes_da_loja.append((luz, 110.0))

    # --- o cenário de cada tomada ----------------------------------------------------------
    def posicionar(self, cenario="plantas", angulo=0.0, fundo=2.4, deslocar=0.0, quadro=None, placa=0.82, tamanho_placa=1.0,
                   topo_da_placa=0.06):
        """Põe a sala em volta da máquina (no centro do mundo): o `cenario` atrás dela, a `fundo` m da parede,
        a parede girada `angulo` graus (positivo: a parede vira para a direita da foto).

        No cenário "logo", com o `quadro` da câmera, a sala anda até o meio da placa cair na fração `placa`
        da largura da foto (0,82: à direita da máquina; 0,18: à esquerda), e a placa desce, se for
        preciso, até o alto dela ficar a `topo_da_placa` (fração da altura) do alto da foto: a placa
        inteira, nunca cortada -- e, na capa, abaixo da faixa de cima do card, onde moram os selos
        ("Projeto sob consulta", "À venda"; LEIA-ME 107). `tamanho_placa` diminui a placa (as máquinas
        grandes: a câmera longe, a placa ficaria enorme).
        Devolve a caixa da placa na foto (frações) ou None.
        """
        x = CENARIOS[cenario] + deslocar
        if self.placa_obj is not None:
            self.placa_obj.scale = (tamanho_placa,) * 3
            self.placa_obj.location.z = self.placa_topo - self.placa_meia_altura * tamanho_placa
        if cenario == "logo" and quadro is not None and self.placa_obj is not None:
            for _volta in range(3):
                menor, maior = -14.0, 14.0
                for _ in range(40):  # (a sala para a direita leva a placa para a esquerda da foto)
                    meio = (menor + maior) / 2
                    self._por(meio, angulo, fundo)
                    x0, _y0, x1, _y1 = self.caixa_da_placa(quadro)
                    if (x0 + x1) / 2 > placa:
                        menor = meio
                    else:
                        maior = meio
                x = (menor + maior) / 2 + deslocar
                self._por(x, angulo, fundo)
                # o alto da placa dentro da foto (com a folga pedida), sem descer para dentro das plantas
                piso_da_placa = CANTEIRO[0] + 0.8 + self.placa_meia_altura * tamanho_placa
                z = self.placa_obj.location.z
                while self.caixa_da_placa(quadro)[1] < topo_da_placa and z > piso_da_placa:
                    z = max(piso_da_placa, z - 0.02)
                    self.placa_obj.location.z = z
                    bpy.context.view_layer.update()
        elif quadro is not None and self.placa_obj is not None and not self._placa_inteira_ou_fora(x, angulo, fundo, quadro):
            # nos outros cenários a placa pode aparecer, mas nunca cortada na borda: a sala anda o mínimo
            # (de 10 em 10 cm) até ela ficar inteira na foto ou de fora
            for passo in (0.1 * k for k in range(1, 60)):
                achado = next((x + sinal * passo for sinal in (1, -1)
                               if self._placa_inteira_ou_fora(x + sinal * passo, angulo, fundo, quadro)), None)
                if achado is not None:
                    x = achado
                    break
        self._por(x, angulo, fundo)
        if quadro is not None and self.placa_obj is not None:
            return self.caixa_da_placa(quadro)
        return None

    def _placa_inteira_ou_fora(self, x, angulo, fundo, quadro, folga=0.02):
        self._por(x, angulo, fundo)
        x0, y0, x1, y1 = self.caixa_da_placa(quadro)
        inteira = x0 >= folga and y0 >= folga and x1 <= 1 - folga and y1 <= 1 - folga
        fora = x1 <= 0 or y1 <= 0 or x0 >= 1 or y0 >= 1
        return inteira or fora

    def _por(self, x, angulo, fundo):
        theta = math.radians(angulo)
        rot = mathutils.Matrix.Rotation(theta, 4, "Z")
        local = mathutils.Vector((x, -fundo, 0.0))
        self.sala.rotation_euler = (0, 0, theta)
        self.sala.location = -(rot @ local)
        bpy.context.view_layer.update()

    def caixa_da_placa(self, quadro):
        """(x0, y0, x1, y1) da placa na foto, em frações (y para baixo)."""
        import numpy as np

        from estudio import projetar_no_quadro

        m = self.placa_obj.matrix_world
        pontos = np.array([tuple(m @ v.co) for v in self.placa_obj.data.vertices])
        return projetar_no_quadro(pontos, quadro)

    def modo(self, nome, fator_loja=1.0):
        """'estudio' (a loja acesa) ou 'noite' (a loja apagada: os LEDs, a placa e o canteiro acesos)."""
        noite = nome == "noite"
        for luz, energia in self.luzes_da_loja:
            luz.data.energy = energia * (0.06 if noite else fator_loja)
        for luz, energia in self.luzes_acesas:
            luz.data.energy = energia * (1.6 if noite else 1.0)
        for mat, forca in self.emissores_da_loja:
            no = next(n for n in mat.node_tree.nodes if n.type == "EMISSION")
            no.inputs["Strength"].default_value = forca * (0.35 if noite else 1.0)

    def esconder(self, sim=True):
        """Some com a loja (o recorte sem fundo, para as artes)."""
        for obj in self.sala.children_recursive:
            obj.hide_render = sim
