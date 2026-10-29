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
#: escolhida. (arte grande das laterais, logotipo do letreiro, cor padrão)
ARTES_DE_ADESIVO = {
    "dragon": ("Dragon Bowling", "site/arena/capas/dragon-bowling-poster.webp", "site/arena/capas/dragon-bowling.webp", "vermelho"),
    "dragon2": ("Dragon Bowling 2", "site/arena/capas/dragon-bowling-2.webp", "site/arena/capas/dragon-bowling-2.webp", "azul"),
    "slam": ("Slam Arena", "site/arena/capas/slam-arena-poster.webp", "site/arena/capas/slam-arena.webp", "preto"),
    "swish": ("Swish Arena", "site/arena/capas/swish-arena-poster.webp", "site/arena/capas/swish-arena.webp", "laranja"),
    "boxing": ("Super Boxing", "site/arena/capas/super-boxing.webp", "site/arena/capas/super-boxing.webp", "roxo"),
    "lazer-shot": ("Lazer Shot", "site/arena/capas/lazer-shot-poster.webp", "site/arena/capas/lazer-shot.webp", "preto"),
    "hit-music": ("Hit Music", "site/arena/capas/hit-music-poster.webp", "site/arena/capas/hit-music.webp", "roxo"),
    "gol-flash": ("Gol Flash Arena", "site/arena/capas/gol-flash-arena-poster.webp", "site/arena/capas/gol-flash-arena.webp", "verde"),
    "craque": ("Craque de Botão", "site/arena/capas/craque-de-botao-poster.webp", "site/arena/capas/craque-de-botao.webp", "verde"),
    "elemental": ("Elemental Beasts", "site/arena/capas/elemental-beasts.webp", "site/arena/capas/elemental-beasts.webp", "azul"),
    "lazer-sport": ("Lazer & Sport", "site/arena/capas/alvo.webp", "site/arena/capas/alvo.webp", "azul"),
}

#: Que artes cabem em cada tipo de máquina (a primeira é a padrão).
ADESIVOS_POR_DESENHO = {
    "boliche": ("dragon", "dragon2"),
    "basquete": ("slam", "swish"),
    "boxe": ("boxing",),
    "tiro": ("lazer-shot",),
    "musica": ("hit-music",),
    "futebol": ("gol-flash",),
    "pebolim": ("craque",),
    "fliperama": ("elemental", "lazer-shot"),
}

#: A cor que o nome do produto já diz ("Dragon Bowling Rosa").
_COR_NO_NOME = {"rosa": "rosa", "pink": "rosa", "vermelh": "vermelho", "amarel": "amarelo",
                "pret": "preto", "black": "preto", "azul": "azul", "roxo": "roxo", "lilas": "roxo",
                "verde": "verde", "laranja": "laranja", "branc": "branco"}


def _cor_do_nome(nome):
    texto = _normalizar(nome)
    for trecho, cor in _COR_NO_NOME.items():
        if re.search(r"(?:^| )" + trecho, texto):
            return cor
    return None


def variantes(nome, desenho):
    """As roupas possíveis de um brinquedo na arena: temas prontos e cores.

    O Strike Kids tem os adesivos de verdade (7 temas); os outros ganham a
    arte do jogo que roda neles, montada sobre a cor escolhida. Todo
    brinquedo tem pelo menos a roupa "Lazer & Sport".
    """
    texto = _normalizar(nome)
    adesivos = []

    if desenho == "boliche":
        pasta = static("site/arena/adesivos/strike-kids/vermelho/01_letreiro_frente.webp").rsplit("/vermelho/", 1)[0]
        for chave, rotulo in TEMAS_STRIKE_KIDS:
            adesivos.append({
                "id": "strike-" + chave,
                "nome": "Strike Kids · " + rotulo,
                "tipo": "pronto",
                "pasta": f"{pasta}/{chave}/",
                "tela": static("site/arena/adesivos/strike-kids/tela.webp"),
                "miniatura": f"{pasta}/{chave}/01_letreiro_frente.webp",
            })

    for chave in ADESIVOS_POR_DESENHO.get(desenho, ()) + ("lazer-sport",):
        rotulo, arte, logo, cor = ARTES_DE_ADESIVO[chave]
        adesivos.append({
            "id": chave,
            "nome": rotulo,
            "tipo": "arte",
            "arte": static(arte),
            "logo": static(logo),
            "cor": cor,
            "miniatura": static(logo),
        })

    # Qual roupa abre primeiro: a que o nome do produto pede.
    padrao = adesivos[0]["id"]
    if desenho == "boliche":
        if "dragon" in texto:
            padrao = "dragon2" if re.search(r"(?:^| )(2|ii|pro ultra)(?:$| )", texto) else "dragon"
        else:
            cor_tema = _cor_do_nome(nome)
            temas = {f"strike-{c}" for c, _ in TEMAS_STRIKE_KIDS}
            if cor_tema and f"strike-{cor_tema}" in temas:
                padrao = f"strike-{cor_tema}"
    else:
        familias = {"slam": "slam", "swish": "swish", "elemental": "elemental", "beast": "elemental"}
        for palavra, chave in familias.items():
            if palavra in texto and any(a["id"] == chave for a in adesivos):
                padrao = chave

    escolhida = next(a for a in adesivos if a["id"] == padrao)
    cor = _cor_do_nome(nome) or escolhida.get("cor") or "azul"
    return {
        "adesivos": adesivos,
        "adesivo": padrao,
        "cores": [{"id": c, "nome": n, "hex": h} for c, n, h in CORES_GABINETE],
        "cor": cor,
    }


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
        "medidas": medidas,
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
        "variantes": variantes(brinquedo.nome_brinquedo, desenho),
    }
