"""As 18 fotos das categorias: o salão de cada uma, a câmera e as máquinas DE VERDADE dela.

Cada cena: `amb` (o que muda no salão: a cor do piso e da parede, o neon, o estilo
das linhas, o tamanho), `cam` (a câmera: altura, lente, f, inclinação), `maquinas`
(uma função que põe as máquinas e devolve a lista delas) e `enquadrar` (como o
gerar.py enquadra o grupo: só o deslocamento da lente, ou também a câmera andando,
nas cenas dos .glb grandes). Só máquinas da própria categoria no site
(ferramentas/categorias/maquinas/catalogo.json; o teste core.tests_categorias_capas
confere a lista que o gerar.py grava em ferramentas/categorias/maquinas-das-fotos.json).
Nenhuma pessoa.

As posições são em volta da câmera: `em(distância, rumo)` -- o rumo em graus,
positivo para a direita. A máquina em foto olha para a câmera com o ângulo em que a
foto foi tirada (cena.FOTOS, `giro`, medido na própria foto); numa fila de frente, o
rumo é o -giro. `fila` arruma a fila na largura da foto (a medida de cada máquina
na foto, a distância que dá a largura pedida).
"""

import math

import cena as C


def em(dist, rumo):
    """(x, y) a `dist` metros da câmera (na origem, olhando +Y), `rumo` graus para a direita."""
    return dist * math.sin(math.radians(rumo)), dist * math.cos(math.radians(rumo))


def F(chave, dist, rumo, **op):
    """A máquina em foto do catálogo."""
    return C.foto(chave, *em(dist, rumo), **op)


def G(chave, dist, rumo, giro=0.0, **op):
    """O nosso .glb."""
    return C.glb(chave, *em(dist, rumo), giro=giro, **op)


def fila(itens, largura=0.80, folga=0.025, centro=0.5, dist=7.0, fixa=False, ao_fundo=False):
    """As máquinas lado a lado, da esquerda para a direita, enchendo `largura` da foto.

    `itens`: ("f", chave, op) para a foto do catálogo, ("g", chave, giro, op) para o .glb;
    op["d"] soma metros à distância daquele item (a fila em degraus). Mede cada uma
    (o quanto ocupa na foto), acha a distância que faz a fila ter a `largura` pedida
    (com a `folga` entre elas, em fração da foto; negativa: uma passa um tanto na
    frente da outra, em degraus) e põe cada uma no rumo dela. `fixa`: a distância é a
    `dist` (a fila de trás); `ao_fundo`: na lista das máquinas da foto, "(ao fundo)".
    """
    cam = C.bpy.context.scene.camera
    lente, sensor = cam.data.lens, cam.data.sensor_width
    desloc = cam.data.shift_x

    def criar(item, d, rumo):
        if item[0] == "f":
            op = dict(item[2] if len(item) > 2 else {})
            op.pop("d", None)
            return F(item[1], d, rumo, **op)
        op = dict(item[3] if len(item) > 3 else {})
        op.pop("d", None)
        return G(item[1], d, rumo, giro=item[2], **op)

    def extra(item):
        op = item[2] if item[0] == "f" and len(item) > 2 else (item[3] if len(item) > 3 else {})
        return op.get("d", 0.0)

    def ang(fx):  # fração da foto -> rumo (graus)
        return math.degrees(math.atan((fx - 0.5 - desloc) * sensor / lente))

    # 1) a medida de cada uma, no meio da foto, e a distância que dá a largura pedida (o ângulo
    #    cai com 1/d); três voltas, porque a foto medida de longe e de perto não ocupa igual
    alvo = ang(0.5 + largura / 2) - ang(0.5 - largura / 2) - folga * (len(itens) - 1) * (ang(1) - ang(0))
    originais = list(itens)
    d_nova = dist
    for _volta in range(1 if fixa else 3):
        larguras = []
        itens = list(originais)
        for i, item in enumerate(itens):
            m = criar(item, d_nova + extra(item), 0.0)
            e, dd, _c, _b = C.extensao_na_foto(m)
            larguras.append((ang(e), ang(dd)))
            C.remover(m)
            if item[0] == "f":  # o ângulo medido na foto fica o mesmo depois
                op = dict(item[2] if len(item) > 2 else {})
                op.setdefault("giro", m["giro"])
                itens[i] = ("f", item[1], op)
        escala = 1.0 if fixa else sum(b - a for a, b in larguras) / max(alvo, 1.0)
        d_nova *= escala
    larguras = [(a / escala, b / escala) for a, b in larguras]
    passo = folga * (ang(1) - ang(0))
    cursor = ang(centro) - (sum(b - a for a, b in larguras) + passo * (len(itens) - 1)) / 2
    feitas = []
    for item, (a, b) in zip(itens, larguras):
        rumo = cursor - a
        feitas.append(criar(item, d_nova + extra(item), rumo))
        feitas[-1]["ao_fundo"] = ao_fundo
        cursor += (b - a) + passo
    ext = [C.extensao_na_foto(m) for m in feitas]
    print(f"  fila: {len(itens)} máquinas a {d_nova:.1f} m; de {min(e[0] for e in ext):.2f} a {max(e[1] for e in ext):.2f} "
          f"na largura, de {min(e[2] for e in ext):.2f} a {max(e[3] for e in ext):.2f} na altura")
    return feitas


def duas_filas(frente, atras, largura=0.62, recuo=3.0, folga_atras=0.03):
    """Duas filas: a da frente no meio (`largura` da foto) e a de trás, `recuo` metros atrás,
    aparecendo dos lados e por cima (as mesas e os brinquedos baixos, vistos do alto)."""
    cam = C.bpy.context.scene.camera
    f = fila(frente, largura=largura, folga=0.03)
    d = sum(math.hypot(m["pos"][0] - cam.location.x, m["pos"][1] - cam.location.y) for m in f) / len(f)
    return f + fila(atras, dist=d + recuo, fixa=True, folga=folga_atras)


def _baby():
    """A área baby do Brinquedão Modelo 4 (a placa "Área Baby", o piso de EVA, a piscina rasa de
    bolinhas): a nossa área baby de verdade. O Modelo 4 tem 19,6 m; a câmera fica no cantinho dele
    (a placa está a 4,3 m do meio do modelo, na frente)."""
    return [C.glb("brinquedao-modelo-4", -4.04, 9.11, rot=-12)]


CENAS = {
    # ---------------------------------------------------------------- os fliperamas: o neon da game zone
    "fliperama": {
        "amb": {"estilo": "arcos", "neon": ["magenta", "ciano", "roxo", "amarelo"], "piso": "#3a1fc8",
                "parede": "#101860", "abertura": (3.4, 9.0)},
        "cam": {"altura": 1.55, "lente": 38, "desloc_y": -0.07, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("f", "multi-jogos-retro"), ("f", "pinball-40"), ("f", "pinball-32"), ("f", "homem-aranha"),
        ], largura=0.90, folga=0.03),
    },
    # ---------------------------------------------------------------- os eletrônicos: os nossos 3D e as fotos
    "eletronicos": {
        "amb": {"estilo": "linhas", "neon": ["azul", "ciano", "magenta", "amarelo"], "piso": "#1a3ad8",
                "parede": "#101a64", "abertura": (-9.0, -3.6)},
        "cam": {"altura": 1.6, "lente": 36, "desloc_y": -0.08, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("g", "basquete-street-quadrinhos", 28), ("f", "sonic-dash"), ("f", "mundo-zumbi"),
            ("g", "strike-kids", -34),
        ], largura=0.90, folga=0.01),
    },
    # ---------------------------------------------------------------- os competitivos: um contra o outro
    "competitivos": {
        "amb": {"estilo": "diagonais", "neon": ["vermelho", "azul", "amarelo", "ciano"], "piso": "#1f34d0",
                "parede": "#101a64", "abertura": (3.6, 9.0)},
        "cam": {"altura": 1.6, "lente": 36, "desloc_y": -0.08, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("f", "basquete-street"), ("f", "air-game-premium", {"d": -2.0}),
            ("g", "basquete-street-quadrinhos", -30), ("f", "mundo-zumbi"),
        ], largura=0.90, folga=-0.03),
    },
    # ---------------------------------------------------------------- os esportivos: a cesta e o gol
    "esportivos": {
        "amb": {"estilo": "diagonais", "neon": ["amarelo", "azul", "vermelho", "verde"], "piso": "#1450e0",
                "parede": "#0f1d66", "abertura": None, "luz_teto": 5000},
        "cam": {"altura": 1.6, "lente": 36, "desloc_y": -0.08, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("f", "basquete-street", {"d": 1.0}), ("f", "basquete-home", {"d": -0.4}),
            ("g", "basquete-street-quadrinhos", -14, {"d": 1.0}), ("f", "show-de-bola", {"d": -0.2}),
        ], largura=0.90, folga=0.015),
    },
    # ---------------------------------------------------------------- os famosos: os personagens
    "famosos": {
        "amb": {"estilo": "pontos", "neon": ["magenta", "amarelo", "ciano", "azul"], "piso": "#5a20c8",
                "parede": "#181066", "abertura": (3.6, 9.0)},
        "cam": {"altura": 1.55, "lente": 38, "desloc_y": -0.07, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("f", "flappy-bird"), ("f", "sonic-dash"), ("g", "basquete-street-quadrinhos", -10, {"d": 0.6}),
            ("f", "pantera-kids", {"d": -0.5}), ("f", "homem-aranha"),
        ], largura=0.92, folga=0.0),
    },
    # ---------------------------------------------------------------- os kids: os pequenos
    "kids": {
        "amb": {"estilo": "ondas", "neon": ["rosa", "amarelo", "ciano", "laranja"], "piso": "#2a6af0",
                "parede": "#22146a", "abertura": None, "luz_teto": 3600},
        "cam": {"altura": 1.35, "lente": 38, "desloc_y": -0.06, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("g", "air-game-kids-alienigenas", 62, {"d": -1.4}), ("f", "minions-kids"), ("f", "sonic-kids"),
            ("f", "homem-aranha-kids"), ("f", "basquete-kids", {"d": 0.3}),
        ], largura=0.92, folga=0.012),
    },
    # ---------------------------------------------------------------- os simuladores: a corrida
    "simuladores": {
        "amb": {"estilo": "linhas", "neon": ["vermelho", "azul", "ciano", "amarelo"], "piso": "#1a36d0",
                "parede": "#101a64", "abertura": (-9.0, -4.0)},
        "cam": {"altura": 1.55, "lente": 36, "desloc_y": -0.08, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("f", "porsche-simulador"), ("f", "top-racer"), ("f", "lazer-shot"), ("f", "simulador-mario-kart"),
        ], largura=0.94, folga=0.02),
    },
    # ---------------------------------------------------------------- os mecânicos: o parquinho que gira
    "mecanicos": {
        "amb": {"estilo": "pontos", "neon": ["amarelo", "rosa", "laranja", "ciano"], "piso": "#6224dc",
                "parede": "#1e1068", "abertura": None, "luz_teto": 3500},
        "cam": {"altura": 3.0, "lente": 35, "desloc_y": -0.02, "inclinar": 12, "f": 2.8},
        "maquinas": lambda: duas_filas(
            [("f", "carrossel-sorvetinho", {"redonda": True})],
            [("f", "mini-roda-sorvete"), ("f", "labamba")], largura=0.36, recuo=2.7, folga_atras=0.21),
    },
    # ---------------------------------------------------------------- os jogos de mesa
    "jogos-de-mesa": {
        "amb": {"estilo": "linhas", "neon": ["ciano", "magenta", "azul", "amarelo"], "piso": "#3024d8",
                "parede": "#121a66", "abertura": (3.4, 9.0)},
        "cam": {"altura": 3.2, "lente": 35, "desloc_y": -0.02, "inclinar": 18, "f": 2.8},
        "maquinas": lambda: duas_filas(
            [("f", "pac-man"), ("g", "air-game-kids-alienigenas", 70)],
            [("f", "air-game-premium"), ("f", "pebolim-eletronico")], largura=0.56, recuo=2.8, folga_atras=0.22),
    },
    # ---------------------------------------------------------------- o boliche
    "boliche-virtual": {
        "amb": {"estilo": "arcos", "neon": ["magenta", "azul", "ciano", "amarelo"], "piso": "#4220d0",
                "parede": "#141866", "abertura": (3.6, 9.0)},
        "cam": {"altura": 1.6, "lente": 36, "desloc_y": -0.08, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("f", "boliche-virtual", {"fundo": 2.1, "giro": 72}), ("g", "strike-kids", -38), ("g", "strike-kids", -38),
        ], largura=0.86, folga=0.03),
    },
    # ---------------------------------------------------------------- os brinquedões
    "brinquedao": {
        "amb": {"estilo": "ondas", "neon": ["amarelo", "laranja", "rosa", "ciano"], "piso": "#2260ee",
                "parede": "#1a1466", "pe_direito": 5.4, "lado_x": 16.0, "abertura": None,
                "luz_teto": 3800, "spot_w": 650, "passo_luz": 3.0},
        "cam": {"altura": 1.8, "lente": 35, "desloc_y": -0.06, "inclinar": 8, "f": 4.0},
        "enquadrar": {"dolly": True, "alvo": (0.04, 0.16, 0.96, 0.86)},
        "maquinas": lambda: [
            G("brinquedao-modelo-2", 12.5, -9, giro=38),
            G("brinquedao-modelo-5", 7.0, 21, giro=-34),
        ],
    },
    # ---------------------------------------------------------------- a área ninja
    "area-ninja": {
        "amb": {"estilo": "diagonais", "neon": ["verde", "laranja", "azul", "amarelo"], "piso": "#1a40d8",
                "parede": "#101a64", "pe_direito": 5.4, "lado_x": 16.0, "abertura": None, "spot_w": 650, "passo_luz": 3.0},
        "cam": {"altura": 1.8, "lente": 35, "desloc_y": -0.06, "inclinar": 8, "f": 4.0},
        "enquadrar": {"dolly": True, "alvo": (0.04, 0.16, 0.96, 0.86)},
        "maquinas": lambda: [
            G("brinquedao-ninja", 12.0, 0, giro=36),
        ],
    },
    # ---------------------------------------------------------------- o espaço esportivo kids (39 x 23 m)
    "espaco-esportivo-kids": {
        "amb": {"estilo": "diagonais", "neon": ["azul", "amarelo", "vermelho", "ciano"], "piso": "#1a40d8",
                "parede": "#141e70", "pe_direito": 14.0, "lado_x": 34.0, "abertura": None, "spot_w": 4200,
                "passo_luz": 4.5, "frente_w": 9000, "lavar_w": 1400, "folga_fundo": 4.0, "mundo": 3.0},
        "cam": {"altura": 11.0, "lente": 32, "desloc_y": 0.0, "inclinar": 33, "f": 8.0},
        "enquadrar": {"dolly": True, "alvo": (0.02, 0.14, 0.98, 0.92)},
        "maquinas": lambda: [
            G("espaco-esportivo-modelo-1", 30.0, 0, giro=34),
        ],
    },
    # ---------------------------------------------------------------- o espaço kids play
    "espaco-kids-play": {
        "amb": {"estilo": "ondas", "neon": ["rosa", "ciano", "amarelo", "azul"], "piso": "#2a62ec",
                "parede": "#1c1266", "pe_direito": 4.4, "abertura": None, "luz_teto": 3800},
        "cam": {"altura": 1.55, "lente": 35, "desloc_y": -0.08, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("g", "brinquedao-modelo-5", 22, {"d": 1.2}), ("g", "air-game-kids-alienigenas", -64, {"d": -0.8}),
            ("f", "sonic-kids"), ("f", "minions-kids", {"d": 0.3}),
        ], largura=0.92, folga=0.015),
    },
    # ---------------------------------------------------------------- os trampolins: duas raias lado a lado
    "trampolins": {
        "amb": {"estilo": "diagonais", "neon": ["amarelo", "azul", "ciano", "vermelho"], "piso": "#1a3ed8",
                "parede": "#101a64", "pe_direito": 5.0, "lado_x": 14.0, "abertura": None, "spot_w": 600, "passo_luz": 2.8},
        "cam": {"altura": 1.7, "lente": 35, "desloc_y": -0.07, "inclinar": 10, "f": 4.0},
        "maquinas": lambda: fila([
            ("g", "trampolim-enterrada", 40), ("g", "trampolim-enterrada-espuma", 40, {"d": 1.5}),
        ], largura=0.92, folga=-0.02, dist=10.0),
    },
    # ---------------------------------------------------------------- a área baby (sem produto no catálogo:
    # o cantinho baby do Brinquedão Modelo 4, a nossa área baby de verdade, com a placa)
    "area-baby": {
        "amb": {"estilo": "ondas", "neon": ["rosa", "amarelo", "ciano", "verde"], "piso": "#2f70f0",
                "parede": "#24166e", "pe_direito": 4.4, "abertura": None, "luz_teto": 3500},
        "cam": {"altura": 1.5, "lente": 35, "desloc_y": 0.03, "f": 2.8},
        "enquadrar": None,
        "maquinas": _baby,
    },
    # ---------------------------------------------------------------- as casinhas cenográficas
    "casinhas-cenograficas": {
        "amb": {"estilo": "ondas", "neon": ["rosa", "amarelo", "laranja", "ciano"], "piso": "#2f6af0",
                "parede": "#2a1670", "abertura": None, "luz_teto": 3400, "lavar_w": 420, "frente_w": 1600},
        "cam": {"altura": 1.45, "lente": 38, "desloc_y": -0.06, "inclinar": 5, "f": 2.8},
        "maquinas": lambda: fila([
            ("f", "cozinha-infantil"), ("f", "oficina-de-engenharia"), ("f", "salao-de-beleza"),
        ], largura=0.88, folga=0.03, dist=6.0),
    },
}


def _pecas():
    """O card fixo "Peças e acessórios" da home: as PEÇAS DE VERDADE do catálogo (a página
    /pecas-reposicao/), cada uma a foto dela recortada (ferramentas/categorias/reposicao/), de pé
    no balcão de acrílico azul de uma game zone, no tamanho de verdade, com a sombra e o reflexo
    no tampo; atrás, desfocados, o neon e as luzes do salão. Câmera de foto de produto: perto,
    de cima (~18 graus), 55 mm, f/8. Ficam de fora os rolos de cabo flexível (a foto deles é de
    cima, deitada: no balcão viraria um adesivo) e o cabo HDMI (o recorte guarda o fundo cinza
    dentro da volta do cabo)."""
    balcao_z = 0.95
    C.ambiente({"estilo": "linhas", "neon": ["magenta", "ciano", "azul", "amarelo"], "piso": "#2a1cc0",
                "parede": "#141c6a", "fundo": 7.5, "abertura": (1.2, 6.0), "frente_w": 400})
    # o balcão: o tampo de acrílico azul profundo (o verniz espelha as peças) e a frente com o LED
    tampo = C.mat_pbr("tampo-acrilico", "#0a2fb8", rug=0.18, verniz=1.0, verniz_rug=0.035)
    C.caixa("tampo", (0, 1.3, balcao_z - 0.02), (3.4, 1.8, 0.04), tampo)
    C.caixa("corpo", (0, 1.3, balcao_z / 2 - 0.02), (3.3, 1.7, balcao_z - 0.04), C.mat_pbr("corpo", "#0d1a6e", rug=0.35, verniz=0.5))
    cam = C.camera(altura=balcao_z + 0.42, lente=55, desloc_y=0.0, foco=0.98, f=8.0, y=0.10)
    cam.rotation_euler = (C.math.radians(90 - 18), 0, 0)
    # a luz de estúdio: a caixa de luz macia em cima da câmera (o reflexo dela fica fora da foto)
    # e o recorte magenta e ciano por trás (o contorno das peças)
    C.luz("softbox", "AREA", (0.0, -0.35, balcao_z + 1.3), 85, C.kelvin(5400), tam=(1.2, 0.6),
          rot=(C.math.radians(40), 0, 0), forma="RECTANGLE")
    C.luz("recorte-m", "AREA", (-0.8, 1.9, balcao_z + 0.5), 18, C.hex_linear("#ff3fd0")[:3], tam=(0.5, 0.5),
          rot=(C.math.radians(-60), 0, C.math.radians(-35)), forma="RECTANGLE")
    C.luz("recorte-c", "AREA", (0.8, 1.9, balcao_z + 0.5), 18, C.hex_linear("#19e3ff")[:3], tam=(0.5, 0.5),
          rot=(C.math.radians(-60), 0, C.math.radians(35)), forma="RECTANGLE")
    z = balcao_z
    pecas = [
        # atrás: a caixinha de som de frente
        C.peca("mini-caixa-de-som-frente", 0.02, 1.20, z, alto=0.10, fundo=0.05),
        # na frente: os bonecos do pebolim, a maneta e o disco do air game e a caixinha de som
        C.peca("boneco-pebolim-vermelho", -0.23, 1.04, z, alto=0.12, fundo=0.03, inclinar=False),
        C.peca("boneco-pebolim-amarelo", -0.17, 1.08, z, alto=0.12, fundo=0.03, inclinar=False),
        C.peca("maneta-air-game", -0.05, 0.99, z, alto=0.075, fundo=0.09),
        C.peca("disco-air-game", 0.085, 0.95, z, alto=0.012, fundo=0.07),
        C.peca("mini-caixa-de-som", 0.20, 1.02, z, alto=0.075, fundo=0.09),
    ]
    return pecas


CENAS["pecas-e-acessorios"] = {"montar": _pecas}
