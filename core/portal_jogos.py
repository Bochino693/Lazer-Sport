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

from django.core.cache import cache
from django.db import DatabaseError
from django.urls import reverse
from django.utils import timezone

from . import arena, paginas_tema, ranking

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

#: Os filtros de console do portal: cada sistema do emulador cai em uma família.
FAMILIAS = {
    "psx": "playstation",
    "nes": "nintendo", "gb": "nintendo", "gba": "nintendo", "n64": "nintendo", "nds": "nintendo", "snes": "nintendo",
    "segaMD": "sega", "segaMS": "sega", "segaGG": "sega", "segaCD": "sega",
    "pce": "classicos", "atari2600": "classicos", "atari7800": "classicos", "c64": "classicos", "arcade": "classicos",
}
NOMES_DAS_FAMILIAS = (
    ("nosso", "Feitos pela Lazer & Sport"),
    ("playstation", "PlayStation"),
    ("nintendo", "Nintendo"),
    ("sega", "Sega"),
    ("classicos", "Atari, C64 e clássicos"),
    ("html", "Jogos HTML5"),
)


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
        "cor": jogo.get("cor") or "#3fd0ff",
        "url": jogo["url"],
        "tipo": "nosso",
        "familias": ["nosso"],
        "plataforma": "Lazer & Sport",
        "maquina": jogo.get("maquina", ""),
        "categoria": CATEGORIA_DA_CASA.get(jogo["slug"], ""),
        "ranking": True,
        "destaque": True,
        "criado": "",
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
        "cor": jogo.get("cor") or "#3fd0ff",
        "url": jogo["url"],
        "tipo": tipo,
        "familias": familias,
        "plataforma": jogo.get("sistema") or ("Lazer & Sport" if tipo == "nosso" else "HTML5"),
        "maquina": "",
        "categoria": jogo.get("categoria", ""),
        "ranking": False,
        "destaque": bool(jogo.get("destaque")),
        "criado": jogo.get("criado", ""),
    }


def cartoes(dados):
    """Todos os jogos do site como cartões (os da casa primeiro)."""
    from django.templatetags.static import static

    da_casa = []
    for jogo in dados["jogos"]:
        cartao = _cartao_da_casa(jogo)
        # a capa dos jogos da casa vem do static (o caminho em arena.JOGOS)
        for campo in ("capa", "poster"):
            valor = cartao[campo]
            if valor and not valor.startswith(("/", "http")):
                cartao[campo] = static(valor)
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


def vivo():
    """O que muda com o uso (partidas e anúncios), num cache curto."""
    dados = cache.get(CHAVE_VIVO)
    if dados is None:
        try:
            dados = {"partidas": _partidas(), "anuncios": _anuncios_no_ar()}
        except DatabaseError:
            dados = {"partidas": {}, "anuncios": []}
        cache.set(CHAVE_VIVO, dados, VIVO_SEGUNDOS)
    return dados


def esquecer_vivo():
    cache.delete(CHAVE_VIVO)


def montar(dados_do_catalogo, busca=""):
    """O contexto do portal (igual para todo visitante)."""
    todos = cartoes(dados_do_catalogo)
    estado = vivo()
    partidas = estado["partidas"]
    for cartao in todos:
        cartao["partidas"] = partidas.get(cartao["slug"], 0)
        cartao["busca"] = sem_acento(" ".join([cartao["titulo"], cartao["plataforma"], cartao["categoria"],
                                               cartao["maquina"], cartao["chamada"], cartao["descricao"][:200]]))

    destaques = [c for c in todos if c["tipo"] != "nosso" and c["destaque"]]
    destaques += [c for c in todos if c["tipo"] == "nosso"]
    destaques = destaques[:6]

    nossos = [c for c in todos if c["tipo"] == "nosso"]
    consoles = [c for c in todos if c["tipo"] == "console"]
    html = [c for c in todos if c["tipo"] == "html"]
    mais_jogados = sorted([c for c in todos if c["partidas"]], key=lambda c: -c["partidas"])[:10]
    agora = timezone.now()
    novidades = []
    for c in todos:
        if not c["criado"]:
            continue
        try:
            criado = dt.datetime.fromisoformat(c["criado"])
        except ValueError:
            continue
        if timezone.is_naive(criado):
            criado = timezone.make_aware(criado)
        if agora - criado <= dt.timedelta(days=45):
            novidades.append((criado, c))
    novidades = [c for _, c in sorted(novidades, key=lambda par: par[0], reverse=True)][:10]

    familias_presentes = {f for c in todos for f in c["familias"]}
    filtros = [(chave, nome) for chave, nome in NOMES_DAS_FAMILIAS if chave in familias_presentes]
    categorias = sorted({c["categoria"] for c in todos if c["categoria"]})

    termo = sem_acento(busca.strip())
    resultados = [c for c in todos if all(p in c["busca"] for p in termo.split())] if termo else []

    anuncios = estado["anuncios"]
    return {
        "todos": todos,
        "destaques": destaques,
        "faixas": [f for f in (
            {"id": "nossos", "titulo": "Feitos pela Lazer & Sport", "sub": "Os jogos das nossas máquinas, com ranking e recorde da casa", "jogos": nossos},
            {"id": "mais-jogados", "titulo": "Mais jogados", "sub": "O que a galera mais está jogando agora", "jogos": mais_jogados},
            {"id": "novidades", "titulo": "Novidades", "sub": "Chegaram por agora", "jogos": novidades},
            {"id": "consoles", "titulo": "Clássicos de console", "sub": "PlayStation, Nintendo, Atari e outros, direto no navegador", "jogos": consoles},
            {"id": "html", "titulo": "Jogos HTML5", "sub": "Abrem na hora, no celular ou no computador", "jogos": html},
        ) if f["jogos"]],
        "filtros": filtros,
        "categorias": categorias,
        "busca": busca.strip(),
        "resultados": resultados,
        "anuncio_topo": next((a for a in anuncios if a["local"] == "topo"), None),
        "anuncios_meio": [a for a in anuncios if a["local"] == "meio"],
        "total": len(todos),
    }


def ranking_do_portal():
    """O ranking geral e o campeão de cada jogo da casa (do cache do ranking)."""
    geral = ranking.ranking_geral(10)
    campeoes = []
    for jogo in arena.JOGOS:
        primeiro = ranking.ranking_do_jogo(jogo["slug"], 1)
        if primeiro:
            campeoes.append({"jogo": jogo["titulo"], "slug": jogo["slug"], "url": reverse("jogo", args=[jogo["slug"]]),
                             "cor": jogo.get("cor") or "#3fd0ff", **primeiro[0]})
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
