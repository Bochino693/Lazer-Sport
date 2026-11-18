"""A fila de e-mails das campanhas anda dentro do próprio site (LEIA-ME seções 101 e 107).

O dono: "minhas campanhas não estão disparando e-mail para os clientes" e,
depois da seção 101, "os emails em massa das campanhas não vão".

O Render não lê o `worker:` do Procfile, então quem esvazia a fila é o
próprio processo do site:
  * logo depois de criar a campanha (`disparar_agora`, numa thread: o clique
    não espera o SMTP);
  * e a cada minuto (`ligar`, chamado pelo gunicorn ao subir o worker web,
    gunicorn.conf.py), o que também cobre as novas tentativas, a volta da
    pausa do provedor e os e-mails que um reinício deixou no meio.

Por que mesmo assim nada saía (seção 107): a reserva de cada e-mail usava
`select_for_update` com um JOIN que o PostgreSQL recusa, e o erro morria no
`log.exception` daqui. O envio agora está em `campanhas.py` (reserva por
UPDATE condicional, lotes pequenos com pausa, falha classificada); aqui fica
o ritmo e a garantia de que a ronda não morre:
  * cada rodada grava a hora em que rodou (o painel mostra se a fila parou);
  * um erro da rodada vai para o painel, não só para o log;
  * a thread da ronda nunca termina por causa de uma exceção.
Um worker de verdade, se um dia existir, convive com isto: cada e-mail é
reservado antes de sair, então nenhum cliente recebe duas vezes.
"""

import logging
import threading
import time

from django.conf import settings
from django.db import close_old_connections, connection, connections

log = logging.getLogger(__name__)

_esvaziando = threading.Lock()  # um esvaziamento por vez neste processo
_ja_ligado = threading.Lock()
_ligado = False


def esvaziar(rodadas=500, pausa=None):
    """Manda a fila em lotes até ela acabar ou o provedor pedir pausa.

    Entre um lote e outro espera CAMPANHA_EMAIL_PAUSA_LOTE segundos. Devolve
    quantos e-mails resolveu (enviados, falhos ou ignorados).
    """
    if not _esvaziando.acquire(blocking=False):
        return 0
    total = 0
    if pausa is None:
        pausa = float(getattr(settings, "CAMPANHA_EMAIL_PAUSA_LOTE", 0) or 0)
    try:
        from .campanhas import fila_pausada, processar_emails_pendentes

        for _ in range(max(1, int(rodadas))):
            feitos = processar_emails_pendentes()
            total += feitos
            if not feitos or fila_pausada():
                break
            if pausa:
                time.sleep(pausa)
    except Exception as erro:  # o site não pode cair por causa do SMTP -- mas o painel fica sabendo
        log.exception("Falha ao esvaziar a fila de e-mails das campanhas.")
        from .campanhas import registrar_erro_da_fila

        registrar_erro_da_fila(erro)
    finally:
        _esvaziando.release()
        if not connection.in_atomic_block:
            close_old_connections()
    if total:
        log.info("fila_de_emails processou=%s", total)
    return total


def _fechar_conexoes_da_thread():
    """A conexão com o banco desta thread não fica aberta depois da rodada
    (o pooler do Supabase derruba conexão ociosa; a próxima abre limpa)."""
    try:
        if not connection.in_atomic_block:
            connections.close_all()
    except Exception:
        pass


def _em_segundo_plano():
    try:
        esvaziar()
    except Exception:
        log.exception("A rodada da fila de e-mails caiu.")
    finally:
        _fechar_conexoes_da_thread()


def disparar_agora():
    """Começa a mandar agora, sem prender quem clicou."""
    if not getattr(settings, "FILA_DE_EMAILS_NO_SITE", True):
        return False
    threading.Thread(target=_em_segundo_plano, name="fila-emails-agora", daemon=True).start()
    return True


def _uma_volta():
    """Uma volta da ronda. Nada aqui pode matar a thread."""
    try:
        esvaziar()
    except Exception:
        log.exception("A ronda da fila de e-mails falhou; tenta de novo no próximo minuto.")
    finally:
        _fechar_conexoes_da_thread()


def _ciclo(intervalo):
    time.sleep(min(30, intervalo))  # o processo ainda está subindo
    while True:
        _uma_volta()
        time.sleep(intervalo)


def ligar():
    """A ronda de minuto em minuto, uma vez por processo do site."""
    global _ligado

    if not getattr(settings, "FILA_DE_EMAILS_NO_SITE", True):
        return False
    with _ja_ligado:
        if _ligado:
            return False
        _ligado = True
    intervalo = max(30, int(getattr(settings, "FILA_DE_EMAILS_INTERVALO", 60)))
    threading.Thread(target=_ciclo, args=(intervalo,), name="fila-emails", daemon=True).start()
    log.info("fila_de_emails ligada intervalo=%ss", intervalo)
    return True
