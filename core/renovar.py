"""Os números "ao vivo" renovados sem fazer o visitante esperar.

POR QUE ISTO EXISTE. O ranking dos jogos (um minuto), as partidas e os
anúncios do portal (dois minutos) e o painel ao vivo da home (um minuto)
ficam num cache curto, de propósito: mudam com o uso. Só que, quando o
prazo vencia, quem chegava naquele instante pagava a conta inteira -- de
três a dez consultas, ~0,2 s cada uma com o Supabase pela rede. Era o
"/jogos/ demora na primeira vez e depois abre rápido" medido no ar
(LEIA-ME-V10, seção 63): com tráfego, quase todo minuto alguém era a
"primeira vez".

O QUE MUDA. Em produção, o número vencido continua servindo enquanto uma
linha de fundo monta o novo (uma por chave, por mais visitas que cheguem
juntas). Quem chega não espera; o número fica, no pior caso, alguns
segundos mais velho do que o prazo. Sem nada guardado (o servidor acabou
de subir, ou alguém apagou a chave -- um recorde novo, um anúncio salvo),
monta na hora, como antes: o recorde de quem acabou de jogar aparece já.

Nos testes e no computador (`RENOVAR_EM_SEGUNDO_PLANO` desligado), tudo
acontece na hora, como sempre foi.
"""

import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger("core.renovar")

#: Por quanto tempo, além do prazo, o número velho ainda serve enquanto o
#: novo não fica pronto (o banco fora do ar, por exemplo): dez prazos.
FOLEGO = 10

_trava = threading.Lock()
_renovando = set()


def em_segundo_plano():
    return bool(getattr(settings, "RENOVAR_EM_SEGUNDO_PLANO", False))


def _guardar(chave, dados, validade):
    vida = validade * FOLEGO if em_segundo_plano() else validade
    cache.set(chave, (time.time() + validade, dados), vida)


def valor(chave, montar, validade):
    """O que está em `chave`, renovado a cada `validade` segundos (`montar()` faz o novo)."""
    guardado = cache.get(chave)
    if guardado is not None:
        vence, dados = guardado
        if time.time() < vence:
            return dados
        if em_segundo_plano():
            _renovar_por_tras(chave, montar, validade)
            return dados
    dados = montar()
    _guardar(chave, dados, validade)
    return dados


def _renovar_por_tras(chave, montar, validade):
    with _trava:
        if chave in _renovando:
            return
        _renovando.add(chave)

    def tarefa():
        from django.db import connections

        try:
            _guardar(chave, montar(), validade)
        except Exception:  # noqa: BLE001 -- o número velho continua servindo
            log.warning("renovar %s falhou", chave, exc_info=True)
        finally:
            with _trava:
                _renovando.discard(chave)
            # a linha de trabalho não fica com conexão aberta com o banco
            connections.close_all()

    threading.Thread(target=tarefa, name=f"renovar:{chave}", daemon=True).start()
