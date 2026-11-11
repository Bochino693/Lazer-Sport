"""O portal Lazer & Sport Games (/jogos/): a vitrine de todos os jogos do site.

Junta num lugar só os jogos da casa (core/arena.py: motores feitos à mão,
com ranking) e os que a equipe cadastra pelo painel (HTML5 e consoles pelo
emulador). Cada jogo vira um CARTÃO com o mesmo formato, e é esse formato
que a busca, os filtros e as faixas usam.

O QUE É DE TODO MUNDO E O QUE É DE CADA UM. A vitrine é igual para todo
visitante: sai do cache do catálogo (a lista de jogos) e de um cache curto
(as partidas contadas e os anúncios no ar). O que é de cada um -- a posição
de quem está logado no ranking -- é resolvido por requisição, fora daqui.
Com isso a página abre sem consulta nenhuma ao banco para quem só passeia.
"""

from __future__ import annotations

import datetime as dt
import unicodedata
from pathlib import Path

from django.core.cache import cache
from django.db import DatabaseError
from django.urls import reverse
from django.utils import timezone

from . import arena, paginas_tema, ranking
from .jogos_emulador import icone_da_funcao

CHAVE_VIVO = "portal-jogos:vivo:v1"
VIVO_SEGUNDOS = 120

#: As categorias dos jogos da casa (os cadastrados escolhem a sua no painel).
CATEGORIA_DA_CASA = {
    "strike-kids": "Esporte",
    "dragon-bowling": "Esporte",
    "lazer-shot": "Tiro",
    "super-boxing": "Luta",
    "slam-arena": "Esporte",
    "swish-arena": "Esporte",
    "gol-flash-arena": "Esporte",
    "craque-de-botao": "Esporte",
    "hit-music": "Música",
}

#: As estantes da biblioteca: cada sistema do emulador cai em uma.
FAMILIAS = {
    "psx": "playstation", "psp": "playstation",
    "nes": "nintendo", "snes": "nintendo", "n64": "nintendo", "gb": "nintendo", "gba": "nintendo", "nds": "nintendo",
    "vb": "nintendo",
    "segaMD": "sega", "segaMS": "sega", "segaGG": "sega", "segaCD": "sega", "sega32x": "sega", "segaSaturn": "sega",
    "arcade": "fliperama", "mame": "fliperama",
    "atari2600": "classicos", "atari5200": "classicos", "atari7800": "classicos", "jaguar": "classicos", "lynx": "classicos",
    "pce": "classicos", "pcfx": "classicos", "ngp": "classicos", "ws": "classicos", "coleco": "classicos", "3do": "classicos",
    "dos": "pc", "amiga": "pc", "c64": "pc", "c128": "pc", "vic20": "pc", "plus4": "pc", "pet": "pc",
}

#: (chave, nome, frase, ícone, cor): a ordem é a das estantes na página.
ESTANTES = (
    ("nosso", "Feitos pela Lazer & Sport", "Os jogos das nossas máquinas, com ranking e recorde da casa", "fa-crown", "#ffd23f"),
    ("playstation", "PlayStation e PSP", "Os discos do PS1 e os jogos do portátil da Sony", "fa-compact-disc", "#4f7cff"),
    ("nintendo", "Nintendo", "Do NES ao DS: cartuchos, portáteis e o Virtual Boy", "fa-gamepad", "#ff3b47"),
    ("sega", "Sega", "Mega Drive, Master System, Game Gear, Saturn e companhia", "fa-bolt", "#22d3ee"),
    ("fliperama", "Fliperama", "Os clássicos dos arcades, ficha por ficha", "fa-ghost", "#c45cff"),
    ("classicos", "Atari e clássicos", "Atari, PC Engine, Neo Geo Pocket, WonderSwan e outros", "fa-tv", "#ff8a1f"),
    ("pc", "PC antigo e computadores", "MS-DOS, Amiga e a família Commodore", "fa-floppy-disk", "#34d399"),
    ("html", "Jogos HTML5", "Abrem na hora, no celular ou no computador", "fa-html5", "#ff6a3d"),
)
TEMA = {chave: {"chave": chave, "nome": nome, "sub": sub, "icone": icone, "cor": cor} for chave, nome, sub, icone, cor in ESTANTES}
#: Compatibilidade: (chave, nome) das estantes.
NOMES_DAS_FAMILIAS = tuple((chave, nome) for chave, nome, *_ in ESTANTES)

#: As coleções de "Minha biblioteca". "recentes" e "aparelho" são do aparelho de
#: quem está vendo (o navegador sabe; o servidor não): o JavaScript preenche.
COLECOES = (
    ("todos", "Todos os jogos", "fa-layer-group"),
    ("recentes", "Jogados recentemente", "fa-clock-rotate-left"),
    ("aparelho", "Já no aparelho", "fa-download"),
    ("ranking", "Com ranking", "fa-trophy"),
    ("mais-jogados", "Mais jogados", "fa-fire"),
    ("novidades", "Novidades", "fa-star"),
)
COLECOES_DO_APARELHO = ("recentes", "aparelho")

#: O selo do console na capa.
SIGLAS = {
    "psx": "PS1", "psp": "PSP", "nes": "NES", "snes": "SNES", "n64": "N64", "gb": "GB", "gba": "GBA", "nds": "DS",
    "vb": "VB", "segaMD": "MEGA", "segaMS": "SMS", "segaGG": "GG", "segaCD": "SEGA CD", "sega32x": "32X",
    "segaSaturn": "SATURN", "arcade": "ARCADE", "mame": "ARCADE", "atari2600": "2600", "atari5200": "5200",
    "atari7800": "7800", "jaguar": "JAGUAR", "lynx": "LYNX", "pce": "PCE", "pcfx": "PC-FX", "ngp": "NGP", "ws": "WS",
    "coleco": "COLECO", "3do": "3DO", "dos": "DOS", "amiga": "AMIGA", "c64": "C64", "c128": "C128",
    "vic20": "VIC-20", "plus4": "PLUS/4", "pet": "PET",
}
ORDENS = (
    ("destaque", "Em destaque"),
    ("az", "Nome (A a Z)"),
    ("jogados", "Mais jogados"),
    ("novos", "Mais novos"),
)
#: Quantos jogos o carrossel do alto mostra.
DESTAQUES = 6
#: Na vista das estantes, quantos jogos cada uma mostra antes do "Ver todos".
POR_ESTANTE = 12
NOVIDADE_DIAS = 45

#: As artes do destaque dos jogos da casa (core/static/site/arena/capas/topo/): cenas de
#: verdade dos jogos, fotografadas no navegador e montadas pelo gerar.py da pasta. Cada jogo
#: tem a faixa larga (<slug>.webp, computador) e a quase quadrada (<slug>-estreito.webp, tablet
#: em pé e celular, onde o texto fica embaixo).
_PASTA_DOS_TOPOS = Path(__file__).resolve().parent / "static" / "site" / "arena" / "capas" / "topo"
SUFIXO_ESTREITO = "-estreito"
TOPOS_DA_CASA = frozenset(p.stem for p in _PASTA_DOS_TOPOS.glob("*.webp") if not p.stem.endswith(SUFIXO_ESTREITO))
TOPOS_ESTREITOS = frozenset(p.stem[: -len(SUFIXO_ESTREITO)] for p in _PASTA_DOS_TOPOS.glob(f"*{SUFIXO_ESTREITO}.webp"))


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()


def _cartao_da_casa(jogo):
    return {
        "slug": jogo["slug"],
        "titulo": jogo["titulo"],
        "chamada": jogo.get("chamada", ""),
        "descricao": jogo.get("descricao", ""),
        "capa": jogo.get("capa_url") or jogo.get("capa", ""),
        "poster": jogo.get("poster_url") or jogo.get("poster", ""),
        # as artes do destaque (a cena do jogo), quando já foram montadas
        "topo": f"site/arena/capas/topo/{jogo['slug']}.webp" if jogo["slug"] in TOPOS_DA_CASA else "",
        "topo_estreito": (f"site/arena/capas/topo/{jogo['slug']}{SUFIXO_ESTREITO}.webp"
                          if jogo["slug"] in TOPOS_ESTREITOS else ""),
        "cor": jogo.get("cor") or "#3fd0ff",
        "url": jogo["url"],
        "tipo": "nosso",
        "familias": ["nosso"],
        "plataforma": "Lazer & Sport",
        "sigla": "L&S",
        "maquina": jogo.get("maquina", ""),
        "categoria": CATEGORIA_DA_CASA.get(jogo["slug"], ""),
        "ranking": True,
        "destaque": True,
        "criado": "",
        "como": ((jogo.get("controle") or {}).get("rotulo") or ""),
        "sistema": "",
        "acoes": {},
        "icones": {},
        # o como jogar dos jogos da casa: dito para o computador e para o celular (core/arena.CONTROLES)
        "dicas": {"pc": (jogo.get("controle") or {}).get("pc", ""), "celular": (jogo.get("controle") or {}).get("celular", "")},
    }


def _cartao_cadastrado(jogo):
    if jogo.get("feito_pela_lazer"):
        tipo, familias = "nosso", ["nosso"]
    elif jogo.get("emulador"):
        tipo, familias = "console", [FAMILIAS.get(jogo.get("codigo_sistema", ""), "classicos")]
    else:
        tipo, familias = "html", ["html"]
    if jogo.get("emulador") and tipo == "nosso":
        familias.append(FAMILIAS.get(jogo.get("codigo_sistema", ""), "classicos"))
    return {
        "slug": jogo["slug"],
        "titulo": jogo["titulo"],
        "chamada": jogo.get("chamada", ""),
        "descricao": jogo.get("descricao", ""),
        "capa": jogo.get("capa", ""),
        "poster": jogo.get("poster", "") or jogo.get("capa", ""),
        # sem arte própria: o destaque monta um mural da capa no navegador (portal-jogos.js)
        "topo": "",
        "topo_estreito": "",
        "cor": jogo.get("cor") or "#3fd0ff",
        "url": jogo["url"],
        "tipo": tipo,
        "familias": familias,
        "plataforma": jogo.get("sistema") or ("Lazer & Sport" if tipo == "nosso" else "HTML5"),
        "sigla": SIGLAS.get(jogo.get("codigo_sistema", ""), "L&S" if tipo == "nosso" else "HTML5"),
        "maquina": "",
        "categoria": jogo.get("categoria", ""),
        "ranking": False,
        "destaque": bool(jogo.get("destaque")),
        "criado": jogo.get("criado", ""),
        "como": jogo.get("comandos", ""),
        "sistema": jogo.get("codigo_sistema", ""),
        "dicas": None,
        "acoes": jogo.get("acoes") or {},
        "icones": {botao: icone_da_funcao(texto) for botao, texto in (jogo.get("acoes") or {}).items()},
    }


def cartoes(dados):
    """Todos os jogos do site como cartões (os da casa primeiro)."""
    from django.templatetags.static import static

    from sistema_interno.templatetags.interno_extras import estatico

    da_casa = []
    for jogo in dados["jogos"]:
        cartao = _cartao_da_casa(jogo)
        # a capa dos jogos da casa vem do static (o caminho em arena.JOGOS)
        for campo in ("capa", "poster"):
            valor = cartao[campo]
            if valor and not valor.startswith(("/", "http")):
                cartao[campo] = static(valor)
        # as artes do destaque levam a versão do conteúdo (?v=): refeitas pelo gerar.py com o mesmo
        # nome, o navegador busca a nova em vez de guardar a velha por 30 dias
        for campo in ("topo", "topo_estreito"):
            if cartao[campo]:
                cartao[campo] = estatico(cartao[campo])
        da_casa.append(cartao)
    return da_casa + [_cartao_cadastrado(j) for j in dados["externos"]]


def _anuncios_no_ar():
    from .models import AnuncioJogos
    from .objetos_3d import tabela_pronta

    if not tabela_pronta(AnuncioJogos):
        return []
    hoje = timezone.localdate()
    lista = []
    for anuncio in AnuncioJogos.objects.filter(ativo=True).order_by("local", "ordem", "-id"):
        if (anuncio.inicio and anuncio.inicio > hoje) or (anuncio.fim and anuncio.fim < hoje):
            continue
        if not anuncio.imagem_url:
            continue
        lista.append({
            "id": anuncio.pk,
            "titulo": anuncio.titulo,
            "texto": anuncio.texto,
            "imagem": anuncio.imagem_url,
            "botao": anuncio.botao or "Saiba mais",
            "local": anuncio.local,
            "url": reverse("anuncio_jogos", args=[anuncio.pk]) if anuncio.link else "",
        })
    return lista


def _partidas():
    from .models import PartidasDoJogo
    from .objetos_3d import tabela_pronta

    if not tabela_pronta(PartidasDoJogo):
        return {}
    return dict(PartidasDoJogo.objects.values_list("slug", "partidas"))


def _jogadores_de_hoje():
    """Quantos cadastrados jogaram hoje um jogo com ranking (a linha do recorde de cada um é tocada a cada partida)."""
    from .models import RecordeJogo

    inicio = timezone.make_aware(dt.datetime.combine(timezone.localdate(), dt.time.min))
    return RecordeJogo.objects.filter(atualizado_em__gte=inicio).values("usuario_id").distinct().count()


def _montar_vivo():
    try:
        dados = {"partidas": _partidas(), "anuncios": _anuncios_no_ar()}
    except DatabaseError:
        dados = {"partidas": {}, "anuncios": []}
    try:
        dados["jogadores_hoje"] = _jogadores_de_hoje()
    except DatabaseError:
        dados["jogadores_hoje"] = 0
    return dados


def vivo():
    """O que muda com o uso (partidas, anúncios e quem jogou hoje), num cache curto.

    Vencido o prazo, em produção, o número de antes continua servindo
    enquanto o novo é montado por trás (core/renovar.py): eram três
    consultas na conta de quem chegava naquele minuto.
    """
    from .renovar import valor

    return valor(CHAVE_VIVO, _montar_vivo, VIVO_SEGUNDOS)


def contagens():
    """Só as partidas de cada jogo e quem jogou hoje: sem os anúncios, que levam links do portal
    (o painel, em outro endereço, não conhece essas rotas -- views_jogos_vivo usa isto)."""
    try:
        partidas = _partidas()
    except DatabaseError:
        partidas = {}
    try:
        hoje = _jogadores_de_hoje()
    except DatabaseError:
        hoje = 0
    return {"partidas": partidas, "jogadores_hoje": hoje}


def esquecer_vivo():
    cache.delete(CHAVE_VIVO)


def _criado(cartao):
    if not cartao["criado"]:
        return None
    try:
        criado = dt.datetime.fromisoformat(cartao["criado"])
    except ValueError:
        return None
    return timezone.make_aware(criado) if timezone.is_naive(criado) else criado


def _ordenar(jogos, ordem):
    if ordem == "az":
        return sorted(jogos, key=lambda c: sem_acento(c["titulo"]))
    if ordem == "jogados":
        return sorted(jogos, key=lambda c: (-c["partidas"], sem_acento(c["titulo"])))
    if ordem == "novos":
        antigo = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        return sorted(jogos, key=lambda c: (c["_criado"] or antigo, c["titulo"]), reverse=True)
    # em destaque: os da casa, os destacados, os mais jogados; o resto na ordem do painel
    return sorted(jogos, key=lambda c: (c["tipo"] != "nosso", not c["destaque"], -c["partidas"], c["_ordem"]))


def montar(dados_do_catalogo, busca="", estante="", genero="", ordem=""):
    """A biblioteca (igual para todo visitante): as estantes, as coleções, os gêneros e a lista pedida.

    Sem filtro, a página mostra as ESTANTES, uma por plataforma, cada uma
    com o seu tema. Com estante, coleção, gênero ou busca (?estante=,
    ?genero=, ?q=, como o JavaScript faz na hora), mostra uma lista só.
    """
    todos = cartoes(dados_do_catalogo)
    estado = vivo()
    partidas = estado["partidas"]
    agora = timezone.now()
    for i, cartao in enumerate(todos):
        cartao["partidas"] = partidas.get(cartao["slug"], 0)
        cartao["estante"] = next((f for f in cartao["familias"] if f in TEMA), "html")
        cartao["tema"] = TEMA[cartao["estante"]]["cor"]
        # o ícone do console: o desenho da arte de reserva do cartão, quando o jogo não tem capa
        cartao["icone"] = TEMA[cartao["estante"]]["icone"]
        cartao["busca"] = sem_acento(" ".join([cartao["titulo"], cartao["plataforma"], cartao["sigla"], cartao["categoria"],
                                               cartao["maquina"], cartao["chamada"], cartao["descricao"][:200]]))
        cartao["_ordem"] = i
        cartao["_criado"] = _criado(cartao)
        cartao["novidade"] = bool(cartao["_criado"] and agora - cartao["_criado"] <= dt.timedelta(days=NOVIDADE_DIAS))

    # o carrossel: primeiro os cadastrados que a equipe destacou; depois os jogos da casa, que se
    # revezam dia a dia (cada dia um abre a fila), para todos passarem pelo destaque com a cena deles
    destaques = [c for c in todos if c["tipo"] != "nosso" and c["destaque"]]
    da_casa = [c for c in todos if c["tipo"] == "nosso"]
    if da_casa:
        giro = timezone.localdate().toordinal() % len(da_casa)
        da_casa = da_casa[giro:] + da_casa[:giro]
    destaques = (destaques + da_casa)[:DESTAQUES]

    ordem = ordem if ordem in dict(ORDENS) else "destaque"
    estantes = []
    for chave, *_ in ESTANTES:
        jogos = _ordenar([c for c in todos if chave in c["familias"]], ordem)
        if jogos:
            estantes.append({**TEMA[chave], "jogos": jogos[:POR_ESTANTE], "total": len(jogos), "mais": len(jogos) > POR_ESTANTE})

    colecoes = {
        "todos": todos,
        "ranking": [c for c in todos if c["ranking"]],
        "mais-jogados": [c for c in todos if c["partidas"]],
        "novidades": [c for c in todos if c["novidade"]],
    }
    lista_de_colecoes = [
        {"chave": chave, "nome": nome, "icone": icone,
         "total": len(colecoes[chave]) if chave in colecoes else None, "do_aparelho": chave in COLECOES_DO_APARELHO}
        for chave, nome, icone in COLECOES
    ]
    generos = {}
    for c in todos:
        if c["categoria"]:
            generos[c["categoria"]] = generos.get(c["categoria"], 0) + 1

    # o que a pessoa pediu
    busca = busca.strip()
    termo = sem_acento(busca)
    lista, titulo, sub, tema = None, "", "", ""
    if estante in TEMA:
        lista = [c for c in todos if estante in c["familias"]]
        titulo, sub, tema = TEMA[estante]["nome"], TEMA[estante]["sub"], TEMA[estante]["cor"]
    elif estante in colecoes and estante != "todos":
        lista = colecoes[estante]
        titulo = dict((k, n) for k, n, _ in COLECOES)[estante]
        if estante == "mais-jogados" and ordem == "destaque":
            ordem = "jogados"
        if estante == "novidades" and ordem == "destaque":
            ordem = "novos"
    else:
        estante = ""
    if genero in generos:
        lista = [c for c in (lista if lista is not None else todos) if c["categoria"] == genero]
        titulo = f"{titulo} · {genero}" if titulo else genero
    else:
        genero = ""
    if termo:
        lista = [c for c in (lista if lista is not None else todos) if all(p in c["busca"] for p in termo.split())]
        titulo = f"Resultados para “{busca}”"
    if lista is not None:
        lista = _ordenar(lista, ordem)

    anuncios = estado["anuncios"]
    return {
        "todos": todos,
        "destaques": destaques,
        "estantes": estantes,
        "colecoes": lista_de_colecoes,
        "generos": sorted(({"nome": n, "total": t} for n, t in generos.items()), key=lambda g: sem_acento(g["nome"])),
        "ordens": ORDENS,
        "ordem": ordem,
        "estante": estante,
        "genero": genero,
        "busca": busca,
        "lista": lista,
        "lista_titulo": titulo,
        "lista_sub": sub,
        "lista_tema": tema,
        # compatibilidade (e o que os testes antigos olham)
        "resultados": lista if termo else [],
        "filtros": [(e["chave"], e["nome"]) for e in estantes],
        "categorias": sorted(generos, key=sem_acento),
        "anuncio_topo": next((a for a in anuncios if a["local"] == "topo"), None),
        "anuncios_meio": [a for a in anuncios if a["local"] == "meio"],
        "total": len(todos),
        # todas as partidas contadas (o toque em Jogar, PartidasDoJogo): o pulso do portal
        "partidas_total": sum(c["partidas"] for c in todos),
        "jogadores_hoje": estado.get("jogadores_hoje", 0),
    }


def ranking_do_portal():
    """O ranking geral e o campeão de cada jogo da casa (do cache do ranking)."""
    geral = ranking.ranking_geral(10)
    # todos os campeões de uma leitura só (era uma consulta por jogo)
    primeiros = ranking.campeoes()
    campeoes = []
    for jogo in arena.JOGOS:
        primeiro = primeiros.get(jogo["slug"])
        if primeiro:
            campeoes.append({"jogo": jogo["titulo"], "slug": jogo["slug"], "url": reverse("jogo", args=[jogo["slug"]]),
                             "cor": jogo.get("cor") or "#3fd0ff", **primeiro})
    return {"geral": geral, "campeoes": campeoes}


def parecidos(dados_do_catalogo, slug, quantos=8):
    """Os jogos cadastrados mais perto de um (mesmo console, mesma categoria), para a página dele.

    Os jogos da casa ficam de fora: a página já tem a faixa deles.
    """
    todos = [c for c in cartoes(dados_do_catalogo) if c["slug"] not in arena.JOGOS_POR_SLUG]
    este = next((c for c in todos if c["slug"] == slug), None)
    if este is None:
        return []
    partidas = vivo()["partidas"]

    def nota(c):
        mesma_familia = bool(set(c["familias"]) & set(este["familias"]))
        mesma_categoria = bool(este["categoria"]) and c["categoria"] == este["categoria"]
        return (2 if mesma_familia else 0) + (1 if mesma_categoria else 0)

    outros = [c for c in todos if c["slug"] != slug]
    outros.sort(key=lambda c: (-nota(c), -partidas.get(c["slug"], 0), c["titulo"]))
    return outros[:quantos]


def anuncio_da_pagina_do_jogo():
    return next((a for a in vivo()["anuncios"] if a["local"] == "jogo"), None)


def tema_da_busca():
    """Para o SEO da página: o texto de busca da página de jogos (paginas_tema)."""
    return paginas_tema.TEMAS.get("jogos-de-boliche", {})
