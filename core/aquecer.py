"""O cache das telas principais AQUECIDO antes de o visitante chegar.

POR QUE ISTO EXISTE. As telas públicas saem do cache em ~10 ms, mas a
primeira depois de o cache esvaziar -- o site acabou de subir, ou alguém
editou um produto, uma foto, um jogo (core/signals.py apaga tudo o que
deriva do catálogo) -- faz de 20 a 50 consultas ao banco, e cada uma é uma
ida e volta até o Supabase. Era essa a página inicial "demorando para
abrir": quem chegava logo depois de uma edição ou de uma subida pagava a
conta inteira.

Agora quem paga é o próprio servidor, em segundo plano: alguns segundos
depois de o cache esvaziar (e logo depois de o servidor subir), uma linha
de trabalho pede ela mesma as telas principais, como um visitante sem
conta, e o cache já está cheio quando a pessoa chega. Várias edições
seguidas (o painel grava o produto, depois as fotos...) viram um
aquecimento só: cada pedido novo adia o anterior.

Desligado nos testes e no computador (`AQUECER_CACHE`); em produção, ligado.
"""

import logging
import threading

from django.conf import settings

log = logging.getLogger("core.aquecer")

#: As telas que o visitante mais abre primeiro (as do menu).
PAGINAS = ("/", "/jogos/", "/loja/", "/arena/", "/brinquedos/", "/projetos/", "/eventos/", "/pecas-reposicao/")
NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/130.0.0.0 Safari/537.36 LazerSportAquecimento")

_trava = threading.Lock()
_agendado = None


def ligado():
    return bool(getattr(settings, "AQUECER_CACHE", False))


def agendar(atraso=4.0, motivo="cache vazio"):
    """Aquece as telas daqui a `atraso` segundos (um pedido novo adia o anterior)."""
    global _agendado
    if not ligado():
        return
    with _trava:
        if _agendado is not None:
            _agendado.cancel()
        _agendado = threading.Timer(atraso, aquecer, kwargs={"motivo": motivo})
        _agendado.daemon = True
        _agendado.start()


def aquecer(motivo=""):
    """Pede as telas principais como um visitante sem conta (o cache fica cheio)."""
    from django.db import connections
    from django.test import Client

    host = getattr(settings, "AQUECER_HOST", "") or "www.lazersport.com.br"
    cliente = Client(HTTP_USER_AGENT=NAVEGADOR, HTTP_ACCEPT="text/html")
    feitas = []
    try:
        for caminho in PAGINAS:
            try:
                resposta = cliente.get(caminho, HTTP_HOST=host, secure=True)
                feitas.append(f"{caminho}={resposta.status_code}")
            except Exception as erro:  # noqa: BLE001 -- uma tela com problema não segura as outras
                feitas.append(f"{caminho}=erro")
                log.warning("aquecer %s falhou: %r", caminho, erro)
    finally:
        # a linha de trabalho não fica com conexão aberta com o banco
        connections.close_all()
    log.info("cache aquecido (%s): %s", motivo, " ".join(feitas))
