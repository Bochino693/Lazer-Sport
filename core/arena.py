"""Arena e Lazer & Sport Jogos — o que cada brinquedo vira na vitrine.

A ARENA NÃO PEDE CADASTRO NOVO. Ela monta a vitrine com o que o
brinquedo já tem: nome, categoria, tags, medidas e as quatro fotos da
galeria (frente, lados e verso). O desenho de cada um -- um gabinete de
fliperama, uma máquina de basquete, uma cama elástica -- é deduzido
daqui, pelas palavras do cadastro, e decide a seção e o jogo da casa.

Isso é de propósito. Um campo novo no `Brinquedos` pediria migração, e a
migração deste projeto é aplicada à mão (ver `publicar-seguro.ps1`): uma
publicação sem ela derrubaria TODA consulta de brinquedo do site com
"coluna não existe". Deduzindo, a arena sobe junto com o código e não
há nada para alguém lembrar de rodar.

Se um brinquedo cair no desenho errado, o conserto é uma palavra a mais
em `REGRAS`, e não um formulário.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from django.urls import reverse

from .formatos import dinheiro, medida
from .fotos import reduzir_imagem


# ======================================================================
# O DESENHO 3D DE CADA BRINQUEDO
# ======================================================================

#: (desenho, palavras). A PRIMEIRA regra que casar vence, então a ordem
#: importa: "basquete kids" tem que ser basquete, e não brinquedo
#: infantil; "simulador de tiro zumbi" tem que ser tiro, e não corrida.
REGRAS = (
    ("basquete", ("basquete", "basket", "cesta", "enterrada")),
    ("boliche", ("boliche", "bowling", "strike", "pino")),
    ("pinball", ("pinball", "pimbal", "pinbal", "fliper de bola")),
    ("pebolim", ("pebolim", "pembolim", "toto", "futebol de mesa", "fla flu", "botao")),
    ("futebol", ("futebol", "gol", "chute", "penalti", "penalty", "craque")),
    ("hockey", ("hockey", "hoquei", "air game", "aero game", "aerohockey", "disco")),
    ("garra", ("garra", "grua", "pelucia", "crane", "pegador", "premio")),
    ("boxe", ("boxe", "boxing", "soco", "punch", "forca", "martelo")),
    ("tiro", ("tiro", "zumbi", "zombie", "pistola", "arma", "shot", "shooting", "alvo")),
    ("musica", ("musica", "music", "danca", "ritmo", "hit", "bateria")),
    ("simulador", ("simulador", "corrida", "f1", "kart", "volante", "racing", "moto gp")),
    ("cama_elastica", ("cama elastica", "pula pula", "trampolim", "jump")),
    ("escalada", ("escalada", "parede", "climb", "rapel")),
    ("carrossel", ("carrossel", "gira gira", "roda gigante")),
    ("touro", ("touro", "rodeio")),
    ("playground", ("brinquedao", "playground", "castelo", "escorregador", "tobogã",
                    "toboga", "piscina de bolinha", "casinha", "labirinto", "kids play")),
    ("montaria", ("kiddie", "aranha", "cavalinho", "carrinho", "motoca", "animal",
                  "dino", "infantil", "kids")),
    ("fliperama", ("fliperama", "arcade", "retro", "multijogos", "multi jogos", "gabinete",
                   "video game", "game")),
)

#: Categoria decide quando o nome não diz nada ("Uiii", "Modelo 3").
POR_CATEGORIA = (
    ("brinquedo", "playground"),
    ("escalada", "escalada"),
    ("mecanic", "montaria"),
    ("fliperama", "fliperama"),
    ("digital", "simulador"),
    ("eletronic", "fliperama"),
)

PADRAO = "fliperama"

#: O tamanho de cada desenho quando o cadastro não tem medida -- ou tem
#: uma que não cabe num galpão (há "63,5 m" de largura num pinball real).
#: Altura × largura × profundidade, em metros.
MEDIDAS_PADRAO = {
    "basquete": (2.6, 1.0, 2.6),
    "boliche": (2.0, 1.0, 3.4),
    "pinball": (1.8, 0.75, 1.3),
    "pebolim": (0.95, 1.1, 1.45),
    "futebol": (2.2, 2.6, 2.4),
    "hockey": (1.0, 1.1, 2.1),
    "garra": (1.9, 0.8, 0.85),
    "boxe": (2.2, 0.9, 1.0),
    "tiro": (2.0, 1.1, 1.5),
    "musica": (2.1, 1.0, 1.2),
    "simulador": (1.6, 1.0, 1.9),
    "cama_elastica": (2.4, 3.0, 3.0),
    "escalada": (4.0, 2.4, 0.8),
    "carrossel": (2.4, 2.6, 2.6),
    "touro": (1.6, 1.0, 1.8),
    "playground": (3.0, 3.6, 3.6),
    "montaria": (1.4, 0.65, 1.0),
    "fliperama": (1.75, 0.7, 0.85),
}

#: Acima disto a medida é erro de digitação, e não brinquedo.
MAIOR_MEDIDA_PLAUSIVEL = Decimal("8")


def _normalizar(texto):
    """Minúsculas, sem acento e sem pontuação: "Pebolim-Eletrônico" -> "pebolim eletronico"."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def _contem(texto, palavra):
    """Palavra inteira, para "hit" não casar com "white" nem "pino" com "pinot"."""
    return re.search(r"(?:^| )" + re.escape(_normalizar(palavra)) + r"(?:$| )", texto) is not None


def modelo_3d(nome, categorias=(), tags=()):
    """O desenho 3D de um brinquedo, pelo nome, pelas tags e pela categoria.

    O nome vem primeiro porque é o que mais diz: "Basquete Street" na
    categoria "Eletrônicos" é uma máquina de basquete, e não um
    gabinete genérico de eletrônico.
    """
    texto = _normalizar(" ".join([nome or "", *tags]))
    for desenho, palavras in REGRAS:
        if any(_contem(texto, palavra) for palavra in palavras):
            return desenho

    categorias_texto = _normalizar(" ".join(categorias))
    for trecho, desenho in POR_CATEGORIA:
        if trecho in categorias_texto:
            return desenho
    return PADRAO


def medidas_para_3d(desenho, altura, largura, profundidade):
    """As medidas do cadastro, ou as do desenho quando faltam ou não fazem sentido."""
    valores = []
    for valor in (altura, largura, profundidade):
        try:
            numero = Decimal(str(valor)) if valor not in (None, "") else None
        except Exception:
            numero = None
        valores.append(numero)

    if all(v is not None and Decimal("0.2") <= v <= MAIOR_MEDIDA_PLAUSIVEL for v in valores):
        return [float(v) for v in valores], True
    return list(MEDIDAS_PADRAO.get(desenho, MEDIDAS_PADRAO[PADRAO])), False


def _url(imagem):
    try:
        return imagem.url if imagem else ""
    except Exception:
        # Arquivo sem nome ou storage fora do ar: o brinquedo continua na
        # arena, só que com a placa "sem foto" no lugar.
        return ""


# ======================================================================
# LAZER & SPORT JOGOS — os jogos da casa, em miniatura no navegador
# ======================================================================

#: Cada jogo é uma máquina de verdade da Lazer & Sport -- os mesmos que
#: rodam nas TV Box das máquinas, com a arte de cada um -- e a sua versão
#: de bolso para jogar no site. `desenhos` liga o jogo aos brinquedos da
#: arena: quem abre a ficha de uma máquina de basquete vê "Jogar a
#: miniatura", e quem termina a partida vê "Quero essa máquina".
#:
#: Jogos da mesma família dividem o mesmo arquivo (`script`) e mudam só a
#: `variante`: os dois basquetes são um motor com duas quadras. Cada
#: boliche tem o seu: o Strike Kids é 3D, como o jogo, e o Dragon Bowling
#: é o porte do game.gd dele.
JOGOS = (
    {
        "slug": "strike-kids",
        "titulo": "Strike Kids",
        "maquina": "Boliche infantil de 5 sensores",
        "chamada": "O boliche do Bob e da Mia",
        "descricao": (
            "O boliche feito para as crianças: o Bob e a Mia torcem a cada "
            "jogada, a pista muda de cenário e os pinos caem com física de "
            "verdade."
        ),
        "comandos": "Arraste a bola e solte: o ponto da pista por onde o gesto passa é o sensor da jogada.",
        "desenhos": ("boliche",),
        "cor": "#ffb703",
        "capa": "site/arena/capas/strike-kids-logo.webp",
        "poster": "site/arena/capas/strike-kids-fundo.webp",
        "script": "site/arena/jogos/strike-kids.js",
        "variante": "strike-kids",
    },
    {
        "slug": "dragon-bowling",
        "titulo": "Dragon Bowling",
        "maquina": "Boliche de arcade",
        "chamada": "A pista é do dragão",
        "descricao": (
            "Boliche de arcade com a arte do dragão: 1 ou 2 jogadores, mapa "
            "dos pinos, STRIKE, ACERTO e PRA FORA no telão e recorde da casa."
        ),
        "comandos": "Arraste a bola para cima e solte: o lado da pista por onde o gesto passa é a jogada.",
        "desenhos": ("boliche",),
        "cor": "#ff6b1a",
        "capa": "site/arena/capas/dragon-bowling.webp",
        "poster": "site/arena/capas/dragon-bowling-poster.webp",
        "script": "site/arena/jogos/dragon-bowling.js",
        "variante": "dragon",
    },
    {
        "slug": "lazer-shot",
        "titulo": "Lazer Shot",
        "maquina": "Tiro ao alvo com pistola de luz",
        "chamada": "Torne-se o melhor atirador",
        "descricao": (
            "Garrafas, lanternas e vasos em cenários do Egito, de Atlântida "
            "e do deserto. Acerte o máximo antes de o tempo acabar."
        ),
        "comandos": "Toque ou clique nos alvos para atirar.",
        "desenhos": ("tiro",),
        "cor": "#ff2d3d",
        "capa": "site/arena/capas/lazer-shot.webp",
        "poster": "site/arena/capas/lazer-shot-poster.webp",
        "script": "site/arena/jogos/lazer-shot.js",
        "variante": "",
    },
    {
        "slug": "super-boxing",
        "titulo": "Super Boxing",
        "maquina": "Máquina de força (boxe)",
        "chamada": "Fight! Never give up!",
        "descricao": (
            "O adversário 3D no ringue sente cada soco: três socos para cravar "
            "a maior força da arena, nocautear o boxeador e entrar no ranking."
        ),
        "comandos": "Toque, clique ou aperte espaço quando o medidor estiver no vermelho.",
        "desenhos": ("boxe",),
        "cor": "#8a5cff",
        "capa": "site/arena/capas/super-boxing.webp",
        "poster": "site/arena/capas/super-boxing.webp",
        "script": "site/arena/jogos/super-boxing.js",
        "variante": "",
    },
    {
        "slug": "slam-arena",
        "titulo": "Slam Arena",
        "maquina": "Basquete arcade vertical",
        "chamada": "Enterre o limite, domine a arena",
        "descricao": (
            "Basquete de neon em três fases, sem botão: a cesta começa o "
            "jogo, e cada fase tem uma meta para passar."
        ),
        "comandos": "Arraste a bola para cima e solte, como um arremesso.",
        "desenhos": ("basquete",),
        "cor": "#ff8a00",
        "capa": "site/arena/capas/slam-arena.webp",
        "poster": "site/arena/capas/slam-arena-poster.webp",
        "script": "site/arena/jogos/basquete.js",
        "variante": "slam",
    },
    {
        "slug": "swish-arena",
        "titulo": "Swish Arena",
        "maquina": "Basquete arcade com placar de LED",
        "chamada": "Show your game",
        "descricao": (
            "Placar de LED gigante, últimos segundos valendo três e o modo "
            "EM CHAMAS: quatro cestas seguidas dobram os pontos."
        ),
        "comandos": "Arraste a bola em direção à cesta e solte.",
        "desenhos": ("basquete",),
        "cor": "#ff5a1f",
        "capa": "site/arena/capas/swish-arena.webp",
        "poster": "site/arena/capas/swish-arena-poster.webp",
        "script": "site/arena/jogos/basquete.js",
        "variante": "swish",
    },
    {
        "slug": "gol-flash-arena",
        "titulo": "Gol Flash Arena",
        "maquina": "Chute ao gol com alvos de luz",
        "chamada": "Acerte, marque e seja o craque",
        "descricao": (
            "Os anéis de luz acendem no gol: chute no que está aceso antes "
            "que ele apague. Quanto mais rápido, mais pontos."
        ),
        "comandos": "Arraste a bola na direção do anel aceso e solte.",
        "desenhos": ("futebol",),
        "cor": "#a6e22e",
        "capa": "site/arena/capas/gol-flash-arena.webp",
        "poster": "site/arena/capas/gol-flash-arena-poster.webp",
        "script": "site/arena/jogos/gol-flash.js",
        "variante": "",
    },
    {
        "slug": "craque-de-botao",
        "titulo": "Craque de Botão",
        "maquina": "Futebol de mesa para 2 jogadores",
        "chamada": "O futebol de botão de sempre, na tela",
        "descricao": (
            "Escolha a seleção, mire o botão e chute. Na máquina são dois "
            "jogadores com manche; aqui você enfrenta a máquina."
        ),
        "comandos": "Arraste um botão seu para trás e solte para chutar.",
        "desenhos": ("pebolim",),
        "cor": "#1fbf5b",
        "capa": "site/arena/capas/craque-de-botao.webp",
        "poster": "site/arena/capas/craque-de-botao-poster.webp",
        "script": "site/arena/jogos/craque-de-botao.js",
        "variante": "",
    },
    {
        "slug": "hit-music",
        "titulo": "Hit Music",
        "maquina": "Jogo de ritmo com tela circular",
        "chamada": "Toque, segure, arraste: sinta a batida",
        "descricao": (
            "Carmine e Paper Moon, as músicas da máquina, com a fase que ela "
            "gera: as notas correm do centro para o anel. Acerte no tempo "
            "para emendar combos e passar dos 70%."
        ),
        "comandos": "Toque nas faixas quando a nota chegar ao anel (ou teclas A S D F J K L Ç).",
        "desenhos": ("musica",),
        "cor": "#ff3df2",
        "capa": "site/arena/capas/hit-music.webp",
        "poster": "site/arena/capas/hit-music-poster.webp",
        "script": "site/arena/jogos/hit-music.js",
        "variante": "",
    },
)

JOGOS_POR_SLUG = {jogo["slug"]: jogo for jogo in JOGOS}


#: COMO SE JOGA CADA UM NO SIMULADOR.
#:
#: O comando de cada prévia é o gesto mais perto do que a máquina pede:
#: os boliches e os basquetes são arrasto (a bola vai na direção do
#: gesto), o tiro é clique, o Hit Music é toque e arrasto na mesa. Os
#: `botoes` aparecem embaixo da tela, como as setas da vitrine da 5D, só
#: nos jogos em que a máquina tem botão de verdade (o chute do Gol Flash,
#: o soco do Super Boxing, o manche do Craque de Botão) -- cada um manda a
#: mesma tecla que o teclado mandaria.
_ARRASTO_BOLICHE = {
    "gesto": "arrasto",
    "rotulo": "Arraste e solte",
    "passos": (
        "Encoste o dedo (ou o mouse) na bola.",
        "Arraste para cima, na direção dos pinos, e solte.",
        "O ponto da pista por onde o gesto passa é o sensor da jogada -- a força não muda nada, como na máquina.",
    ),
    "botoes": (),
}

CONTROLES = {
    "strike-kids": {
        **_ARRASTO_BOLICHE,
        "na_maquina": "Na máquina a criança rola a bola de verdade; 5 sensores na pista leem a jogada e a TV mostra o resultado.",
    },
    "dragon-bowling": {
        **_ARRASTO_BOLICHE,
        "passos": (
            "Encoste o dedo (ou o mouse) na bola.",
            "Arraste para cima e solte: o lado da pista por onde o gesto passa é o sensor da jogada.",
            "Pelo meio, com os 10 pinos de pé, é strike; pelos cantos, cai um pino só.",
        ),
        "na_maquina": "Na máquina a bola corre pela pista do gabinete e cruza um dos 5 sensores: é ele que decide a jogada.",
    },
    "lazer-shot": {
        "gesto": "clique",
        "rotulo": "Mire e clique",
        "passos": (
            "Aponte o mouse (ou o dedo) para o alvo.",
            "Clique ou toque para atirar.",
            "Acabou a munição? Recarregue.",
        ),
        "na_maquina": "Na máquina você atira com a pistola de luz apontada para a tela.",
        "botoes": ({"tecla": "KeyR", "icone": "fa-rotate", "rotulo": "Recarregar"},),
    },
    "super-boxing": {
        "gesto": "toque",
        "rotulo": "Toque para socar",
        "passos": (
            "Toque na tela ou no botão SOCAR.",
            "Acerte quando o medidor estiver no vermelho: é aí que o soco sai mais forte.",
            "Demorou? O boxeador soca a câmera, e cada soco dele tira um quarto da sua vida.",
        ),
        "na_maquina": "Na máquina o soco é no saco de pancada de verdade e o sensor mede a força; o boxeador 3D da tela reage a cada golpe.",
        "botoes": ({"tecla": "Space", "icone": "fa-hand-fist", "rotulo": "SOCAR!", "grande": True},),
    },
    "slam-arena": {
        "gesto": "arrasto",
        "rotulo": "Arraste e arremesse",
        "passos": (
            "Pegue a bola na rampa.",
            "Arraste para a cesta e solte: quanto mais rápido, mais forte.",
        ),
        "na_maquina": "Na máquina as bolas são de verdade e a cesta tem sensor.",
        "botoes": (),
    },
    "swish-arena": {
        "gesto": "arrasto",
        "rotulo": "Arraste e arremesse",
        "passos": (
            "Pegue a bola na rampa.",
            "Arraste em direção à cesta e solte.",
        ),
        "na_maquina": "Na máquina as bolas são de verdade e a cesta tem sensor.",
        "botoes": (),
    },
    "gol-flash-arena": {
        "gesto": "arrasto",
        "rotulo": "Arraste e chute",
        "passos": (
            "Arraste a bola na direção do anel aceso e solte.",
            "Ou mire com as setas e aperte CHUTAR.",
        ),
        "na_maquina": "Na máquina o chute é na bola de verdade, contra os alvos com sensor.",
        "botoes": (
            {"tecla": "ArrowLeft", "icone": "fa-arrow-left", "rotulo": "Mirar à esquerda", "so_icone": True},
            {"tecla": "Space", "icone": "fa-futbol", "rotulo": "CHUTAR", "grande": True},
            {"tecla": "ArrowRight", "icone": "fa-arrow-right", "rotulo": "Mirar à direita", "so_icone": True},
        ),
    },
    "craque-de-botao": {
        "gesto": "arrasto",
        "rotulo": "Puxe e solte",
        "passos": (
            "Encoste num botão do seu time.",
            "Puxe para trás, como um estilingue, e solte para chutar.",
            "Ou use o manche: troque de botão, gire a mira e chute.",
        ),
        "na_maquina": "Na máquina cada jogador tem o seu manche e o botão de chute.",
        "botoes": (
            {"tecla": "ArrowUp", "icone": "fa-arrows-rotate", "rotulo": "Trocar botão", "so_icone": True},
            {"tecla": "ArrowLeft", "icone": "fa-rotate-left", "rotulo": "Girar a mira para a esquerda", "so_icone": True},
            {"tecla": "Space", "icone": "fa-futbol", "rotulo": "CHUTAR", "grande": True},
            {"tecla": "ArrowRight", "icone": "fa-rotate-right", "rotulo": "Girar a mira para a direita", "so_icone": True},
        ),
    },
    "hit-music": {
        "gesto": "clique-arrasto",
        "rotulo": "Toque, segure e arraste",
        "passos": (
            "Toque a faixa quando a nota chegar ao anel.",
            "Nota longa: segure até ela acabar.",
            "Trilho com setas: arraste pelo caminho até o fim.",
        ),
        "na_maquina": "Na máquina você toca a mesa circular de luz, no ritmo da música.",
        # no computador o jogo inteiro vai no teclado
        "teclado": "Teclado: A S D F J K L Ç são as 8 faixas · segure na nota longa · no trilho, as teclas do caminho",
        "botoes": (),
    },
}

#: O ícone de cada gesto, no seletor e na faixa de comandos.
ICONES_DO_GESTO = {
    "arrasto": "fa-hand-pointer",
    "clique": "fa-crosshairs",
    "toque": "fa-hand-point-up",
    "clique-arrasto": "fa-hand-sparkles",
}


def jogos_do_simulador(jogos):
    """Os jogos com o comando de cada um e o endereço da página dele."""
    saida = []
    for jogo in jogos:
        controle = CONTROLES.get(jogo["slug"], _ARRASTO_BOLICHE)
        saida.append({
            **jogo,
            "controle": controle,
            "icone_gesto": ICONES_DO_GESTO.get(controle["gesto"], "fa-hand-pointer"),
            # a capa em 128 px, para o seletor e o letreiro da máquina
            "miniatura": f"site/arena/capas/mini/{jogo['slug']}.webp",
            "url": reverse("jogo", args=[jogo["slug"]]),
        })
    return saida


def jogo_do_desenho(desenho):
    """O primeiro jogo que tem a miniatura deste tipo de máquina."""
    for jogo in JOGOS:
        if desenho in jogo["desenhos"]:
            return jogo["slug"]
    return ""


# ======================================================================
# AS SEÇÕES DA ARENA
# ======================================================================

#: A arena separa as máquinas em três seções, nesta ordem. O 3D montado à
#: mão (o gabinete de boliche) saiu: não era a máquina de verdade. Os
#: objetos 3D voltam feitos a partir das fotos reais de cada máquina
#: (frente, lados e costas), e até lá cada seção mostra as fotos.
GRUPOS_DA_ARENA = (
    {
        "id": "jogos",
        "titulo": "Com jogos da Lazer & Sport",
        "kicker": "Desenvolvidos aqui",
        "texto": "As máquinas que rodam os jogos feitos na nossa fábrica. Cada uma tem a prévia para jogar.",
    },
    {
        "id": "maquinas",
        "titulo": "As máquinas que já fazíamos",
        "kicker": "Catálogo da fábrica",
        "texto": "Fliperamas, mesas, simuladores, garras e as outras máquinas de sempre.",
    },
    {
        "id": "brinquedoes",
        "titulo": "Trampolins e brinquedões",
        "kicker": "Espaços kids",
        "texto": "Camas elásticas, playgrounds e brinquedões para o espaço kids.",
    },
)

#: Os desenhos que vão para "Trampolins e brinquedões".
DESENHOS_DE_BRINQUEDAO = {"cama_elastica", "playground"}


def grupo_da_arena(desenho, jogo):
    """A seção da máquina: a do jogo da casa vem antes de tudo."""
    if jogo:
        return "jogos"
    if desenho in DESENHOS_DE_BRINQUEDAO:
        return "brinquedoes"
    return "maquinas"


def grupos_da_arena(catalogo):
    """As seções com as máquinas de cada uma; seção vazia não aparece."""
    return [
        {**grupo, "brinquedos": [b for b in catalogo if b["grupo"] == grupo["id"]]}
        for grupo in GRUPOS_DA_ARENA
        if any(b["grupo"] == grupo["id"] for b in catalogo)
    ]


# ======================================================================
# A VITRINE, PRONTA PARA O JAVASCRIPT
# ======================================================================

TIPOS_DE_FOTO = ("perfil", "lado_direito", "verso", "lado_esquerdo")


def dados_do_brinquedo(brinquedo, url_detalhe):
    """Um brinquedo como a arena o desenha: forma, tamanho, fotos e ficha.

    Espera `categorias_brinquedos`, `tags` e `imagens_brinquedo` já
    trazidos com `prefetch_related` -- aqui nada consulta o banco.
    """
    categorias = [c.nome_categoria for c in brinquedo.categorias_brinquedos.all() if c.nome_categoria]
    tags = [t.nome_tags for t in brinquedo.tags.all() if t.nome_tags]
    desenho = modelo_3d(brinquedo.nome_brinquedo, categorias, tags)
    medidas, medidas_reais = medidas_para_3d(
        desenho, brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m,
    )
    jogo = jogo_do_desenho(desenho)

    fotos = {}
    for foto in brinquedo.imagens_brinquedo.all():
        if foto.tipo in TIPOS_DE_FOTO and foto.tipo not in fotos:
            fotos[foto.tipo] = reduzir_imagem(_url(foto.imagem))
    capa = fotos.get("perfil") or reduzir_imagem(_url(brinquedo.imagem_perfil))

    valor = brinquedo.valor_brinquedo
    return {
        "id": brinquedo.pk,
        "nome": brinquedo.nome_brinquedo,
        "url": url_detalhe,
        "desenho": desenho,
        "jogo": jogo,
        "grupo": grupo_da_arena(desenho, jogo),
        "categorias": categorias,
        "medidas": medidas,
        "medidas_reais": medidas_reais,
        "medidas_texto": (
            " × ".join(medida(v) for v in (brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m))
            if medidas_reais else ""
        ),
        "voltagem": brinquedo.voltz or "",
        # Preço só de quem está à venda na loja; o resto é orçamento.
        "preco": f"R$ {dinheiro(valor)}" if brinquedo.disponivel_na_loja else "",
        "avaliacao": float(brinquedo.avaliacao or 0),
        "capa": capa or "",
        "fotos": [
            {"tipo": tipo, "url": fotos[tipo]}
            for tipo in TIPOS_DE_FOTO if fotos.get(tipo)
        ] or ([{"tipo": "perfil", "url": capa}] if capa else []),
        "descricao": (brinquedo.descricao or "")[:240],
    }
