"""As páginas por tema de busca (core/paginas_tema.py): /boliche/, /fliperama/..."""

from __future__ import annotations

import json

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse

from . import arena, paginas_tema
from .models import Brinquedos

CACHE_SEGUNDOS = 10 * 60


def _site():
    return str(getattr(settings, "SITE_URL", "") or "https://www.lazersport.com.br").rstrip("/")


def _brinquedos_do_tema(palavras, limite=8):
    """Os brinquedos ativos do catálogo cujo nome (ou descrição) fala do tema."""
    from .fotos import reduzir_imagem

    filtro = Q()
    for palavra in palavras:
        filtro |= Q(nome_brinquedo__icontains=palavra) | Q(descricao__icontains=palavra)
    achados = []
    for b in Brinquedos.objects.filter(ativo=True).filter(filtro).order_by("-avaliacao", "nome_brinquedo")[:limite]:
        try:
            foto = reduzir_imagem(b.imagem_brinquedo.url, 480) if b.imagem_brinquedo else ""
        except Exception:
            foto = ""
        achados.append({"nome": b.nome_brinquedo, "foto": foto,
                        "url": reverse("brinquedo_detalhe", args=[b.pk])})
    return achados


def _montar(slug):
    dados = paginas_tema.tema(slug)
    if not dados:
        raise Http404
    site = _site()
    url = site + reverse("pagina_tema", args=[slug])
    jogos = []
    for s in dados["jogos"]:
        jogo = arena.JOGOS_POR_SLUG.get(s)
        if jogo:
            jogos.append({"slug": s, "titulo": jogo["titulo"], "maquina": jogo["maquina"],
                          "chamada": jogo["chamada"], "descricao": jogo["descricao"],
                          "capa": static(jogo["capa"]), "cor": jogo.get("cor") or "#2f8bff",
                          "url": reverse("jogo", args=[s])})
    brinquedos = _brinquedos_do_tema(dados["palavras"])
    relacionados = [{"slug": r, "menu": paginas_tema.TEMAS[r]["menu"], "h1": paginas_tema.TEMAS[r]["h1"],
                     "url": reverse("pagina_tema", args=[r])} for r in dados["relacionados"] if r in paginas_tema.TEMAS]

    # dados estruturados: trilha, perguntas e a lista das máquinas
    grafo = [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Início", "item": site + "/"},
            {"@type": "ListItem", "position": 2, "name": dados["menu"], "item": url},
        ]},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": p, "acceptedAnswer": {"@type": "Answer", "text": r}}
            for p, r in dados["perguntas"]
        ]},
        {"@type": "ItemList", "name": dados["h1"], "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": f'{j["titulo"]} — {j["maquina"]}', "url": site + j["url"]}
            for i, j in enumerate(jogos)
        ] + [
            {"@type": "ListItem", "position": len(jogos) + i + 1, "name": b["nome"], "url": site + b["url"]}
            for i, b in enumerate(brinquedos)
        ]},
    ]
    imagem = site + (jogos[0]["capa"] if jogos else static("images/compartilhar/lazer-sport-1200x630.jpg"))
    return {
        "tema": dados,
        "jogos": jogos,
        "brinquedos_tema": brinquedos,
        "relacionados": relacionados,
        "url_canonica": url,
        "imagem_compartilhar": imagem,
        "dados_estruturados": json.dumps({"@context": "https://schema.org", "@graph": grafo}, ensure_ascii=False),
    }


def pagina_tema(request, tema):
    chave = f"pagina-tema:{tema}"
    contexto = cache.get(chave)
    if contexto is None:
        contexto = _montar(tema)
        cache.set(chave, contexto, CACHE_SEGUNDOS)
    return render(request, "pagina_tema.html", contexto)
