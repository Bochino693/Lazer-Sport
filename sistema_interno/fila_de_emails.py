"""A fila de e-mails das campanhas anda dentro do próprio site (LEIA-ME seção 101).

O dono: "minhas campanhas não estão disparando e-mail para os clientes".

POR QUÊ. A campanha grava um e-mail por cliente na fila (EntregaCampanha,
"pendente") e quem enviava era só o `observar_pendencias` -- a linha
`worker:` do Procfile. O Render não lê o Procfile: o worker só existe se um
serviço "Background Worker" for criado à mão no painel dele (pago). Sem ele,
a fila nunca andava e toda campanha ficava "pendente" para sempre.

AGORA. O próprio processo do site esvazia a fila:
  * logo depois de criar a campanha (`disparar_agora`, numa thread: o clique
    não espera o SMTP);
  * e a cada minuto (`ligar`, chamado pelo gunicorn ao subir o worker web),
    o que também cobre as novas tentativas dos e-mails que falharam.
Um worker de verdade, se um dia existir, convive com isto: cada e-mail é
travado na fila (select_for_update + "processando") antes de sair, então
nenhum cliente recebe duas vezes.
"""

import logging
import threading
import time

from django.conf import settings
from django.db import close_old_connections

log = logging.getLogger(__name__)

_esvaziando = threading.Lock()  # um esvaziamento por vez neste processo
_ja_ligado = threading.Lock()
_ligado = False


def esvaziar(rodadas=30, pausa=1.0):
    """Manda os e-mails pendentes em lotes de 20 até a fila acabar. Devolve quantos processou."""
    if not _esvaziando.acquire(blocking=False):
        return 0
    total = 0
    try:
        from .campanhas import processar_emails_pendentes

        for _ in range(max(1, int(rodadas))):
            feitos = processar_emails_pendentes(limite=20)
            total += feitos
            if not feitos:
                break
            time.sleep(pausa)
    except Exception:  # o site não pode cair por causa do SMTP
        log.exception("Falha ao esvaziar a fila de e-mails das campanhas.")
    finally:
        _esvaziando.release()
        close_old_connections()
    if total:
        log.info("fila_de_emails processou=%s", total)
    return total


def disparar_agora():
    """Começa a mandar agora, sem prender quem clicou."""
    if not getattr(settings, "FILA_DE_EMAILS_NO_SITE", True):
        return False
    threading.Thread(target=esvaziar, name="fila-emails-agora", daemon=True).start()
    return True


def _ciclo(intervalo):
    time.sleep(min(30, intervalo))  # o processo ainda está subindo
    while True:
        esvaziar()
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
