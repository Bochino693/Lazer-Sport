"""Avisar o Bing (e quem mais usa o IndexNow) de que páginas do site mudaram.

O Google não participa do IndexNow -- para ele, o caminho é o Search
Console e o sitemap.xml. Mas o Bing participa, e o índice do Bing é o que
alimenta o Copilot, o DuckDuckGo e as buscas de vários assistentes. Sem o
aviso, uma página nova espera o robô passar sozinho, o que leva semanas.

COMO LIGA. A variável INDEXNOW_KEY (8 a 128 letras ou números, inventada
por vocês; pode ser um UUID sem os traços). O site passa a responder a
chave em /<chave>.txt -- é assim que o Bing confere que o aviso veio do
dono do site --, e o comando `python manage.py avisar_buscadores` manda
a lista de páginas do sitemap.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.http import Http404, HttpResponse

ENDERECO = "https://api.indexnow.org/indexnow"
CHAVE_VALIDA = re.compile(r"^[A-Za-z0-9-]{8,128}$")


def chave() -> str:
    valor = str(getattr(settings, "INDEXNOW_KEY", "") or "").strip()
    return valor if CHAVE_VALIDA.match(valor) else ""


def arquivo_da_chave(request, nome):
    """/<chave>.txt: só responde a chave configurada, e nada mais."""
    atual = chave()
    if not atual or nome != atual:
        raise Http404
    return HttpResponse(atual, content_type="text/plain; charset=utf-8")


def enderecos_do_sitemap() -> list[str]:
    """Todas as páginas do sitemap.xml, com o endereço público."""
    from .urls import sitemaps

    lista = []
    for classe in sitemaps.values():
        mapa = classe()
        for item in mapa.get_urls():
            lista.append(item["location"])
    return list(dict.fromkeys(lista))


def avisar(enderecos, enviar=None) -> dict:
    """Manda a lista ao IndexNow. `enviar(url, corpo)` existe para os testes."""
    atual = chave()
    if not atual:
        raise ValueError("Configure INDEXNOW_KEY antes de avisar os buscadores.")
    site = str(getattr(settings, "SITE_URL", "") or "https://www.lazersport.com.br").rstrip("/")
    host = urlsplit(site).netloc
    corpo = {"host": host, "key": atual, "keyLocation": f"{site}/{atual}.txt",
             "urlList": [u for u in enderecos if urlsplit(u).netloc == host][:10000]}
    if enviar is None:
        import requests

        def enviar(url, dados):
            resposta = requests.post(url, data=json.dumps(dados), timeout=30,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
            return resposta.status_code
    status = enviar(ENDERECO, corpo)
    return {"status": status, "enviados": len(corpo["urlList"])}
