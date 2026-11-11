"""Os contadores de clique do catálogo, gravados fora da requisição.

POR QUE ISTO EXISTE. A página do brinquedo, a da categoria, a do combo e a
da promoção saem do cache do catálogo (core/home_cache.py) sem consultar o
banco -- menos uma coisa: o contador de cliques, que é por visita. Era um
`UPDATE` no meio da requisição, e com o Supabase pela rede isso custa duas
viagens (a conferência da conexão reaproveitada, `conn_health_checks`, e o
próprio `UPDATE`). Medido no ar: a ficha do brinquedo em cache levava
~0,9 s, a lista de brinquedos (sem consulta nenhuma) ~0,65 s. A diferença
era o contador. E, com o banco fora do ar, a página que já estava pronta no
cache caía em erro 500 por causa dele.

O QUE MUDA. A visita entra numa fila na memória do processo e a resposta
sai na hora; uma linha de trabalho de fundo grava a fila, somando as visitas
do mesmo produto num `UPDATE` só. O número que o painel mostra é o mesmo,
alguns milissegundos depois.

O QUE SE PERDE, E POR QUE SERVE. Se o processo morrer com cliques na fila
(um deploy no meio de uma rajada), esses poucos não são contados. É um
contador de interesse, não um registro de venda: trocar a certeza do último
clique por meio segundo em toda página de produto é o negócio certo.

Desligado nos testes e no computador (`CLIQUES_EM_SEGUNDO_PLANO`): ali o
`UPDATE` acontece na hora, como antes, e o teste confere o número logo
depois da visita.
"""

import atexit
import logging
import queue
import threading

from django.conf import settings
from django.db import DatabaseError, close_old_connections, connection
from django.db.models import F

log = logging.getLogger("core.cliques")

#: Quantos cliques uma rodada grava no máximo (o resto fica para a seguinte).
POR_RODADA = 500

_fila = queue.Queue()
_trava = threading.Lock()
_linha = None


def em_segundo_plano():
    return bool(getattr(settings, "CLIQUES_EM_SEGUNDO_PLANO", False))


def registrar(modelo, filtro, **dados_da_primeira):
    """Conta uma visita: `filtro` acha a linha do contador; `dados_da_primeira` a cria.

    `filtro` usa só valores simples (o id do produto), porque a gravação
    pode acontecer em outra linha de trabalho, longe deste objeto.
    """
    if not em_segundo_plano():
        _gravar(modelo, filtro, 1, dados_da_primeira)
        return
    _fila.put((modelo, tuple(sorted(filtro.items())), tuple(sorted(dados_da_primeira.items()))))
    _garantir_linha()


def _gravar(modelo, filtro, quantidade, dados_da_primeira):
    """Soma `quantidade` cliques com um UPDATE só; a linha nasce na primeira visita."""
    atualizadas = modelo.objects.filter(**filtro).update(
        quantidade_click=F("quantidade_click") + quantidade,
    )
    if not atualizadas:
        modelo.objects.create(**filtro, quantidade_click=quantidade, **dados_da_primeira)


def gravar_pendentes(bloquear=False):
    """Grava o que está na fila, somando as visitas do mesmo produto. Devolve quantos cliques gravou.

    `bloquear=True` espera o primeiro clique chegar (é o laço da linha de
    fundo); sem isso, grava o que houver e volta (testes, desligamento).
    """
    lote = []
    try:
        lote.append(_fila.get(block=bloquear))
    except queue.Empty:
        return 0
    while len(lote) < POR_RODADA:
        try:
            lote.append(_fila.get_nowait())
        except queue.Empty:
            break

    somados = {}
    for modelo, filtro, dados in lote:
        chave = (modelo, filtro)
        quantidade, _ = somados.get(chave, (0, dados))
        somados[chave] = (quantidade + 1, dados)

    # a conexão desta linha vive entre as rodadas: a velha ou quebrada é
    # trocada aqui, como o Django faz a cada requisição
    close_old_connections()
    gravados = 0
    for (modelo, filtro), (quantidade, dados) in somados.items():
        try:
            _gravar(modelo, dict(filtro), quantidade, dict(dados))
            gravados += quantidade
        except DatabaseError:
            log.warning("cliques: %s cliques de %s não foram gravados", quantidade, modelo.__name__, exc_info=True)
            # conexão em estado ruim: a próxima rodada abre outra
            connection.close()
    return gravados


def _laco():
    while True:
        try:
            gravar_pendentes(bloquear=True)
        except Exception:  # noqa: BLE001 -- a linha de fundo nunca morre por um defeito
            log.exception("cliques: a rodada falhou")


def _ao_sair():
    """O processo vai embora (deploy, reinício): grava o que ainda está na fila."""
    try:
        while gravar_pendentes():
            pass
    except Exception:  # noqa: BLE001 -- saindo, não há a quem avisar além do log
        log.warning("cliques: a fila não foi gravada ao sair", exc_info=True)


def _garantir_linha():
    """Sobe a linha de fundo na primeira visita (uma por processo, já depois do fork do gunicorn)."""
    global _linha
    if _linha is not None and _linha.is_alive():
        return
    with _trava:
        if _linha is not None and _linha.is_alive():
            return
        if _linha is None:
            atexit.register(_ao_sair)
        _linha = threading.Thread(target=_laco, name="cliques-do-catalogo", daemon=True)
        _linha.start()
