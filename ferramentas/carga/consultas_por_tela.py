"""Quantas consultas ao banco cada tela do teste de carga faz.

Serve para traduzir o resultado medido com sqlite local para a produção:
cada consulta no Supabase custa uma ida e volta pela rede (20-60 ms),
então o tempo de uma tela em produção é, grosso modo,
``tempo_medido + consultas x latência``.

Uso (com o mesmo ambiente do rodar.sh)::

    PYTHONPATH=.../lsdemo DJANGO_SETTINGS_MODULE=ls_carga_settings \
        python ferramentas/carga/consultas_por_tela.py
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ls_carga_settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

PUBLICAS = ["/", "/brinquedos/", "/brinquedo/1/", "/jogos/", "/categoria/1/", "/static/site/ls-base.css"]
PAINEL = ["/", "/orcamentos/", "/clientes/", "/producao/", "/estoque/", "/avisos/estado/"]


def medir(cliente, caminho, **extra):
    # duas passadas: a primeira aquece caches de processo (vitrine, templates)
    cliente.get(caminho, **extra)
    with CaptureQueriesContext(connection) as capturadas:
        inicio = time.perf_counter()
        resposta = cliente.get(caminho, **extra)
        duracao = (time.perf_counter() - inicio) * 1000
    tempo_sql = sum(float(q.get("time") or 0) for q in capturadas.captured_queries) * 1000
    return resposta.status_code, len(capturadas), duracao, tempo_sql


def main():
    print(f"{'tela':34} {'status':>6} {'consultas':>9} {'ms total':>9} {'ms em SQL':>9}")
    publico = Client(HTTP_HOST="127.0.0.1")
    for caminho in PUBLICAS:
        status, n, ms, sql = medir(publico, caminho)
        print(f"{caminho:34} {status:>6} {n:>9} {ms:>9.1f} {sql:>9.1f}")

    usuario = get_user_model().objects.get(username=os.getenv("CARGA_USUARIO", "demo"))
    painel = Client(HTTP_HOST="interno.localhost")
    painel.force_login(usuario)
    for caminho in PAINEL:
        status, n, ms, sql = medir(painel, caminho)
        print(f"{'painel ' + caminho:34} {status:>6} {n:>9} {ms:>9.1f} {sql:>9.1f}")


if __name__ == "__main__":
    main()
