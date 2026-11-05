"""Latência artificial por consulta: faz o sqlite local "parecer" o Supabase.

O teste de carga roda sobre sqlite em arquivo (0-2 ms por consulta), mas
em produção cada consulta é uma ida e volta pela rede até o Supabase,
20-60 ms. Esse tempo não é CPU: a thread fica parada esperando (psycopg2
solta o GIL), e é exatamente isso que ocupa as vagas públicas do escudo
de tráfego.

Este módulo reproduz essa espera: cada consulta dorme ``CARGA_LATENCIA_MS``
milissegundos (``time.sleep`` também solta o GIL) antes de executar. O
``rodar.sh`` liga isso com ``CARGA_LATENCIA_MS=40``; o ``ls_carga_settings``
chama ``instalar()`` quando a variável está definida.

Uso em um settings::

    from latencia_db import instalar
    instalar()   # lê CARGA_LATENCIA_MS; 0 ou vazio = desligado
"""

from __future__ import annotations

import os
import time

from django.db.backends.signals import connection_created


def _latencia_segundos() -> float:
    try:
        return max(0.0, float(os.getenv("CARGA_LATENCIA_MS", "0") or 0)) / 1000.0
    except ValueError:
        return 0.0


def _dormir_e_executar(execute, sql, params, many, context):
    time.sleep(_LATENCIA)
    return execute(sql, params, many, context)


_LATENCIA = 0.0


def _ao_abrir_conexao(sender, connection, **kwargs):
    # Permanente (e não o `with connection.execute_wrapper(...)`): a
    # conexão vive o processo inteiro e toda consulta dela deve pagar.
    if _dormir_e_executar not in connection.execute_wrappers:
        connection.execute_wrappers.append(_dormir_e_executar)


def instalar() -> float:
    """Liga a latência artificial se CARGA_LATENCIA_MS > 0. Devolve o valor em s."""
    global _LATENCIA
    _LATENCIA = _latencia_segundos()
    if _LATENCIA > 0:
        connection_created.connect(_ao_abrir_conexao, weak=False, dispatch_uid="carga.latencia_db")
    return _LATENCIA
