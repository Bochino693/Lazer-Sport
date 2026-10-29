"""Arena 3D e Lazer & Sport Jogos — o que cada brinquedo vira na vitrine.

A ARENA NÃO PEDE CADASTRO NOVO. Ela monta a vitrine em 3D com o que o
brinquedo já tem: nome, categoria, tags, medidas e as quatro fotos da
galeria (frente, lados e verso). O desenho 3D que cada um ganha -- um
gabinete de fliperama, uma máquina de basquete, uma cama elástica -- é
deduzido daqui, pelas palavras do cadastro.

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

from django.templatetags.static import static
from django.urls import reverse

from .formatos import dinheiro, medida


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


def reduzir_imagem(url, largura=768):
    """Foto do Cloudinary no tamanho que a tela usa, e não no original.

    A foto de estúdio chega com 3000 px e alguns MB. Como textura de um
    gabinete que ocupa um quarto da tela, 768 px sobram -- e o celular
    agradece. Fora do Cloudinary a URL volta como está.
    """
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return url
    antes, depois = url.split("/upload/", 1)
    if depois.startswith(("c_", "w_", "f_", "q_")):
        return url
    return f"{antes}/upload/c_limit,w_{int(largura)},f_auto,q_auto/{depois}"


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
#: `variante`: os três boliches são um motor com três pistas, e os dois
#: basquetes, um motor com duas quadras.
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
        "comandos": "Arraste a bola e solte na direção dos pinos.",
        "desenhos": ("boliche",),
        "cor": "#ffb703",
        "capa": "site/arena/capas/strike-kids-logo.webp",
        "poster": "site/arena/capas/strike-kids-fundo.webp",
        "script": "site/arena/jogos/boliche.js",
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
        "comandos": "Arraste para mirar e solte para lançar. Mais rápido, mais força.",
        "desenhos": ("boliche",),
        "cor": "#ff6b1a",
        "capa": "site/arena/capas/dragon-bowling.webp",
        "poster": "site/arena/capas/dragon-bowling-poster.webp",
        "script": "site/arena/jogos/boliche.js",
        "variante": "dragon",
    },
    {
        "slug": "dragon-bowling-2",
        "titulo": "Dragon Bowling 2",
        "maquina": "Boliche de arcade Pro Ultra 4K",
        "chamada": "Bola azul marmorizada, jogo imprevisível",
        "descricao": (
            "A versão 2: bola azul com rastro luminoso, pinos de tabela, "
            "avisos de SPLIT e QUASE, e jogadas que nem sempre são strike."
        ),
        "comandos": "Arraste para mirar e solte para lançar.",
        "desenhos": ("boliche",),
        "cor": "#2f7bff",
        "capa": "site/arena/capas/dragon-bowling-2.webp",
        "poster": "site/arena/capas/dragon-bowling-2.webp",
        "script": "site/arena/jogos/boliche.js",
        "variante": "dragon2",
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
            "A máquina de soco com sensor de feixe: três socos para cravar a "
            "maior força da arena e entrar para o ranking."
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
            "As notas correm do centro para o anel. Acerte no tempo da "
            "música para emendar combos e subir de nota."
        ),
        "comandos": "Toque nas faixas quando a nota chegar ao anel (ou teclas A S D F J K L Ç).",
        "desenhos": ("musica",),
        "cor": "#ff3df2",
        "capa": "site/arena/capas/hit-music.webp",
        "poster": "site/arena/capas/hit-music-poster.webp",
        "script": "site/arena/jogos/hit-music.js",
        "variante": "",
    },
    {
        "slug": "elemental-beasts",
        "titulo": "Elemental Beasts",
        "maquina": "Batalha de criaturas para 2 jogadores",
        "chamada": "Arena elemental, cinco contra cinco",
        "descricao": (
            "Trinta criaturas de oito elementos. Escolha a carta certa: "
            "fogo vence natureza, água apaga fogo -- e a máquina joga contra você."
        ),
        "comandos": "Toque na carta da criatura que vai para o combate.",
        "desenhos": ("fliperama",),
        "cor": "#3fd0ff",
        "capa": "site/arena/capas/elemental-beasts.webp",
        "poster": "site/arena/capas/elemental-beasts.webp",
        "script": "site/arena/jogos/elemental-beasts.js",
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
        "Arraste para cima, na direção dos pinos.",
        "Solte: a direção e a velocidade do gesto viram a jogada.",
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
        "na_maquina": "Na máquina a bola corre pela pista do gabinete e os sensores dizem para onde ela foi.",
    },
    "dragon-bowling-2": {
        **_ARRASTO_BOLICHE,
        "na_maquina": "Na máquina a bola corre pela pista do gabinete e os sensores dizem para onde ela foi.",
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
            "Toque no saco de pancada ou no botão SOCAR.",
            "Acerte quando o medidor estiver no vermelho: é aí que o soco sai mais forte.",
        ),
        "na_maquina": "Na máquina o soco é no saco de pancada de verdade, e o sensor mede a força.",
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
        "botoes": (),
    },
    "elemental-beasts": {
        "gesto": "toque",
        "rotulo": "Escolha e ataque",
        "passos": (
            "Escolha a fera que vai para o combate.",
            "Toque num golpe para atacar: o elemento certo causa mais dano.",
        ),
        "na_maquina": "Na máquina os golpes são os botões do painel.",
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
# CORES E ADESIVOS — o mesmo gabinete em várias roupas
# ======================================================================

#: As cores em que a fábrica entrega os gabinetes. A ordem é a dos botões
#: na ficha 3D.
CORES_GABINETE = (
    ("vermelho", "Vermelho", "#e3192d"),
    ("rosa", "Rosa", "#ff3fa4"),
    ("amarelo", "Amarelo", "#ffc21a"),
    ("preto", "Preto", "#17171f"),
    ("azul", "Azul", "#1f6fff"),
    ("roxo", "Roxo", "#7b3fe4"),
    ("verde", "Verde", "#19b45a"),
    ("laranja", "Laranja", "#ff7a00"),
    ("branco", "Branco", "#eef2f8"),
)

#: Os 7 temas de adesivagem do Strike Kids, com os 12 adesivos de cada um
#: gerados pela própria ferramenta do jogo (`divulgacao/ferramentas/
#: gerar_gabinete.py --maquete`, no repositório do Strike Kids).
TEMAS_STRIKE_KIDS = (
    ("vermelho", "Vermelho"),
    ("azul", "Azul"),
    ("branco", "Branco"),
    ("espaco", "Espaço"),
    ("mar", "Fundo do Mar"),
    ("dinos", "Selva dos Dinos"),
    ("parque", "Parque de Diversões"),
)

#: Adesivos montados na hora, no navegador: a arte do jogo sobre a cor
#: escolhida -- é assim que o Dragon Bowling aparece rosa, vermelho,
#: amarelo ou preto. (nome, arte grande das laterais, logotipo, cor padrão)
ARTES_DE_ADESIVO = {
    "dragon": ("Dragon Bowling", "site/arena/capas/dragon-bowling-poster.webp", "site/arena/capas/dragon-bowling.webp", "vermelho"),
    "dragon2": ("Dragon Bowling 2", "site/arena/capas/dragon-bowling-2.webp", "site/arena/capas/dragon-bowling-2.webp", "azul"),
}

#: SÓ GANHA 3D A MÁQUINA QUE TEM OBJETO DE VERDADE.
#:
#: Hoje é o gabinete de boliche: as medidas e a posição de cada adesivo
#: vêm da planta do Strike Kids (`divulgacao/ferramentas/gerar_gabinete.py`
#: e a maquete `gabinete_render.gd`, no repositório do jogo), e o Dragon
#: Bowling roda no mesmo gabinete. As outras máquinas aparecem com as fotos
#: reais até chegarem os planos de corte -- gabinete inventado, não.
DESENHOS_COM_3D = {"boliche"}

#: Medidas do gabinete de boliche na planta (altura, largura, fundo em m).
GABINETE_BOLICHE = (2.38, 0.8, 3.2)

_COR_NO_NOME = {"rosa": "rosa", "pink": "rosa", "vermelh": "vermelho", "amarel": "amarelo",
                "pret": "preto", "black": "preto", "azul": "azul", "roxo": "roxo", "lilas": "roxo",
                "verde": "verde", "laranja": "laranja", "branc": "branco"}


def _cor_do_nome(nome):
    texto = _normalizar(nome)
    for trecho, cor in _COR_NO_NOME.items():
        if re.search(r"(?:^| )" + trecho, texto):
            return cor
    return None


def _familia_do_boliche(nome):
    """Qual boliche é: o infantil (Strike Kids), o do dragão, ou não se sabe."""
    texto = _normalizar(nome)
    if "dragon" in texto or "dragao" in texto:
        return "dragon"
    if any(_contem(texto, p) for p in ("strike", "kids", "infantil", "bob", "mia")):
        return "strike"
    return None


def _temas_strike():
    pasta = static("site/arena/adesivos/strike-kids/vermelho/01_letreiro_frente.webp").rsplit("/vermelho/", 1)[0]
    return [
        {
            "id": "strike-" + chave,
            "nome": "Strike Kids · " + rotulo,
            "tipo": "pronto",
            "pasta": f"{pasta}/{chave}/",
            "tela": static("site/arena/adesivos/strike-kids/tela.webp"),
            "miniatura": f"{pasta}/{chave}/01_letreiro_frente.webp",
        }
        for chave, rotulo in TEMAS_STRIKE_KIDS
    ]


def _artes_dragon():
    adesivos = []
    for chave in ("dragon", "dragon2"):
        rotulo, arte, logo, cor = ARTES_DE_ADESIVO[chave]
        adesivos.append({
            "id": chave, "nome": rotulo, "tipo": "arte",
            "arte": static(arte), "logo": static(logo), "cor": cor, "miniatura": static(logo),
        })
    return adesivos


def variantes(nome, desenho):
    """As roupas de uma máquina que tem 3D; `None` para as que não têm.

    O Strike Kids veste os 12 adesivos de verdade de um dos 7 temas; o
    Dragon Bowling, a arte do jogo sobre a cor escolhida. Um boliche que
    o nome não diz qual é recebe as duas famílias.
    """
    if desenho not in DESENHOS_COM_3D:
        return None
    familia = _familia_do_boliche(nome)
    texto = _normalizar(nome)
    if familia == "strike":
        adesivos = _temas_strike()
    elif familia == "dragon":
        adesivos = _artes_dragon()
    else:
        adesivos = _temas_strike() + _artes_dragon()

    padrao = adesivos[0]["id"]
    cor_do_nome = _cor_do_nome(nome)
    if familia == "dragon":
        padrao = "dragon2" if re.search(r"(?:^| )(2|ii|pro ultra)(?:$| )", texto) else "dragon"
    elif cor_do_nome and any(a["id"] == f"strike-{cor_do_nome}" for a in adesivos):
        padrao = f"strike-{cor_do_nome}"

    escolhida = next(a for a in adesivos if a["id"] == padrao)
    return {
        "adesivos": adesivos,
        "adesivo": padrao,
        "cores": [{"id": c, "nome": n, "hex": h} for c, n, h in CORES_GABINETE],
        "cor": cor_do_nome or escolhida.get("cor") or "vermelho",
    }


#: As máquinas da vitrine 3D. Aparecem mesmo que o catálogo ainda não
#: tenha um produto com esse nome; quando tem, a ficha usa as fotos, o
#: preço e o link do produto.
MAQUINAS_3D = (
    {
        "id": "strike-kids",
        "nome": "Strike Kids",
        "categoria": "Boliche infantil",
        "descricao": (
            "O boliche do Bob e da Mia, com 5 sensores, câmera para a foto dos "
            "jogadores e o gabinete em 7 temas de adesivagem."
        ),
        "jogo": "strike-kids",
        "capa": "site/arena/capas/strike-kids-logo.webp",
        "fotos": ("site/arena/capas/strike-kids-fundo.webp", "site/arena/capas/strike-kids-logo.webp"),
    },
    {
        "id": "dragon-bowling",
        "nome": "Dragon Bowling",
        "categoria": "Boliche de arcade",
        "descricao": (
            "O boliche de arcade com a arte do dragão, para 1 ou 2 jogadores. "
            "Escolha a cor do gabinete: rosa, vermelho, amarelo, preto e mais."
        ),
        "jogo": "dragon-bowling",
        "capa": "site/arena/capas/dragon-bowling.webp",
        "fotos": ("site/arena/capas/dragon-bowling-poster.webp", "site/arena/capas/dragon-bowling.webp",
                  "site/arena/capas/dragon-bowling-2.webp"),
    },
)


def maquinas_3d(catalogo):
    """A vitrine 3D: as máquinas com objeto real, ligadas ao produto do catálogo."""
    from .formatos import medida

    altura, largura, fundo = GABINETE_BOLICHE
    maquinas = []
    for indice, base in enumerate(MAQUINAS_3D):
        familia = "dragon" if base["id"].startswith("dragon") else "strike"
        produto = next(
            (b for b in catalogo if b.get("tem_3d") and _familia_do_boliche(b["nome"]) == familia),
            None,
        )
        fotos = (produto or {}).get("fotos") or [
            {"tipo": "arte", "url": static(caminho)} for caminho in base["fotos"]
        ]
        maquinas.append({
            "id": base["id"],
            "nome": produto["nome"] if produto else base["nome"],
            "url": produto["url"] if produto else "",
            "desenho": "boliche",
            "jogo": base["jogo"],
            "categorias": [base["categoria"]],
            "medidas": [altura, largura, fundo],
            "medidas_reais": True,
            "medidas_texto": " × ".join(medida(v) for v in (altura, largura, fundo)),
            "voltagem": (produto or {}).get("voltagem", ""),
            "preco": (produto or {}).get("preco", ""),
            "avaliacao": (produto or {}).get("avaliacao", 0),
            "capa": (produto or {}).get("capa") or static(base["capa"]),
            "fotos": fotos,
            "descricao": base["descricao"],
            "variantes": variantes(produto["nome"] if produto else base["nome"], "boliche"),
            "indice": indice,
        })
    return maquinas


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
    tem_3d = desenho in DESENHOS_COM_3D
    # O objeto 3D é o da planta; a medida do cadastro só aparece na ficha.
    medidas_do_objeto = list(GABINETE_BOLICHE) if tem_3d else medidas

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
        "jogo": jogo_do_desenho(desenho),
        "categorias": categorias,
        "medidas": medidas_do_objeto,
        "medidas_reais": medidas_reais,
        "medidas_texto": (
            " × ".join(medida(v) for v in (brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m))
            if medidas_reais else ""
        ),
        "voltagem": brinquedo.voltz or "",
        "preco": f"R$ {dinheiro(valor)}" if valor else "",
        "avaliacao": float(brinquedo.avaliacao or 0),
        "capa": capa or "",
        "fotos": [
            {"tipo": tipo, "url": fotos[tipo]}
            for tipo in TIPOS_DE_FOTO if fotos.get(tipo)
        ] or ([{"tipo": "perfil", "url": capa}] if capa else []),
        "descricao": (brinquedo.descricao or "")[:240],
        "tem_3d": tem_3d,
        "variantes": variantes(brinquedo.nome_brinquedo, desenho),
    }
