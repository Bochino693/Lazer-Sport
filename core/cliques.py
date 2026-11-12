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
from django.db import DatabaseError, close_old_connections, connection, transaction
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

    A HORA da visita é tirada aqui, e não na gravação: na fila, a visita
    das 13h59 pode ser gravada às 14h00, e o gráfico de "Hoje" a poria na
    hora errada (core/interacoes.py).
    """
    from .interacoes import inicio_da_hora

    hora = inicio_da_hora()
    if not em_segundo_plano():
        _gravar(modelo, filtro, 1, dados_da_primeira, hora)
        return
    _fila.put((modelo, tuple(sorted(filtro.items())), tuple(sorted(dados_da_primeira.items())), hora))
    _garantir_linha()


def depois(funcao, *args):
    """Roda `funcao(*args)` na linha de fundo -- ou, fora da produção, depois do commit.

    Para as gravações que acompanham uma visita e que ninguém espera ver
    na própria resposta: a hora da visita e a ida ao carrinho no gráfico
    (core/interacoes.py) e o "visto por último" das contas (core/presenca.py).

    Sem a linha de fundo (computador, testes), fica para DEPOIS DO COMMIT:
    é o que a fila faria -- a gravação não entra na transação da página nem
    na conta de consultas dela. No computador, sem transação aberta, roda
    na hora; nos testes, só com `captureOnCommitCallbacks(execute=True)`.
    """
    if not em_segundo_plano():
        transaction.on_commit(lambda: funcao(*args))
        return
    _fila.put((None, funcao, args, None))
    _garantir_linha()


def _gravar(modelo, filtro, quantidade, dados_da_primeira, hora=None):
    """Soma `quantidade` cliques com um UPDATE só; a linha nasce na primeira visita."""
    atualizadas = modelo.objects.filter(**filtro).update(
        quantidade_click=F("quantidade_click") + quantidade,
    )
    if not atualizadas:
        modelo.objects.create(**filtro, quantidade_click=quantidade, **dados_da_primeira)

    # O contador antigo já foi gravado; o "quando" vai para o gráfico.
    # `visita_do_contador` nunca levanta: o gráfico não derruba a contagem.
    # Na linha de fundo grava já; na requisição, depois do commit (`depois`).
    from .interacoes import visita_do_contador

    if em_segundo_plano():
        visita_do_contador(modelo, filtro, quantidade, hora)
    else:
        depois(visita_do_contador, modelo, filtro, quantidade, hora)


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
    tarefas = []
    for modelo, filtro, dados, hora in lote:
        if modelo is None:
            # `depois(funcao, *args)`: aqui `filtro` é a função e `dados`, os argumentos
            tarefas.append((filtro, dados))
            continue
        chave = (modelo, filtro, hora)
        quantidade, _ = somados.get(chave, (0, dados))
        somados[chave] = (quantidade + 1, dados)

    # a conexão desta linha vive entre as rodadas: a velha ou quebrada é
    # trocada aqui, como o Django faz a cada requisição
    close_old_connections()
    gravados = 0
    for (modelo, filtro, hora), (quantidade, dados) in somados.items():
        try:
            _gravar(modelo, dict(filtro), quantidade, dict(dados), hora)
            gravados += quantidade
        except DatabaseError:
            log.warning("cliques: %s cliques de %s não foram gravados", quantidade, modelo.__name__, exc_info=True)
            # conexão em estado ruim: a próxima rodada abre outra
            connection.close()
    for funcao, argumentos in tarefas:
        try:
            funcao(*argumentos)
        except Exception:  # noqa: BLE001 -- uma tarefa ruim não leva as outras junto
            log.warning("cliques: a tarefa %s falhou", getattr(funcao, "__name__", funcao), exc_info=True)
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
        # pela fila, e não pelo número gravado: uma rodada só de tarefas grava 0 cliques
        while not _fila.empty():
            gravar_pendentes()
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
