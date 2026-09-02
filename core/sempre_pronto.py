"""Mantém a instância de pé e a conexão do banco quente.

O PROBLEMA, DITO SEM RODEIO

A hospedagem suspende o processo quando ele fica alguns minutos sem
receber requisição. Voltar custa de vinte a sessenta segundos: o
contêiner sobe, o Python importa Django, allauth, cloudinary e o resto, e
só então a primeira requisição começa a ser atendida. Quem estava
esperando vê a tela parada -- e, se a espera passar do prazo do proxy, vê
um 502.

Nada disso é lentidão do código. Uma tela do painel resolve em algumas
centenas de milissegundos com a instância de pé; a mesma tela leva quase
um minuto com a instância voltando do sono. É a diferença entre um
sistema que responde e um sistema que a fábrica desiste de usar.

O QUE ESTE MÓDULO FAZ, E O QUE ELE NÃO RESOLVE

Faz duas coisas, e as duas são baratas:

  1. GERA TRÁFEGO DE ENTRADA. A suspensão é decidida por ausência de
     requisição vinda de fora. Uma batida periódica em `/healthz/`, pelo
     endereço público, é requisição vinda de fora -- e enquanto ela
     existir a instância não dorme.

  2. MANTÉM A CONEXÃO DO BANCO VIVA. Mesmo com a instância de pé, o
     pooler do Supabase encerra conexão ociosa. A primeira consulta
     depois disso paga DNS, TCP e TLS antes de ler qualquer linha --
     segundos, numa tela que deveria abrir em menos de um. Um `SELECT 1`
     no mesmo ciclo mantém a conexão de `CONN_MAX_AGE` quente.

NÃO RESOLVE a partida a frio de um deploy, nem a de uma instância que já
dormiu antes de este processo subir. Para isso não há remédio em código:
é o plano de hospedagem. Ver `docs/RENDER_502.md`.

ONDE ISTO RODA

Dentro do processo web, numa thread de fundo, e também no processo
`worker` do Procfile. Os dois batem no mesmo endereço e um só já basta --
a batida é idempotente e barata, e ter os dois é redundância barata para
o caso de um deles cair.

POR QUE A BATIDA VAI EM `/pronto/`, E NÃO EM `/healthz/`

`/healthz/` responde sem tocar o banco -- é o health check da hospedagem,
e ele PRECISA ser assim, senão uma oscilação do Supabase derrubaria o
processo web inteiro. Ele resolveria a primeira metade do problema (a
instância não dorme) e nada da segunda.

`/pronto/` faz um `SELECT 1`. E, principalmente, ele chega pela rede: cai
numa das threads que atendem requisição, que é exatamente onde a conexão
precisa estar quente. Aquecer o banco DENTRO desta thread não serviria de
nada -- conexão em Django é por thread, e a desta aqui nunca atende
ninguém.
"""

import logging
import sys
import threading
import time
from urllib.parse import urlsplit

from django.conf import settings

log = logging.getLogger("lazer.performance")

#: Trava de processo. Gunicorn com mais de um worker importa este módulo
#: uma vez por processo, e cada um pode ter a sua thread -- mas duas
#: threads no MESMO processo seriam duas batidas iguais, sem ganho.
_ja_ligado = threading.Lock()
_ligado = False


def _ativo():
    """Vale a pena manter esta instância acordada?"""
    if not getattr(settings, "SEMPRE_PRONTO", False):
        return False
    # `manage.py migrate`, `collectstatic` e `test` também carregam os
    # apps. Uma thread de rede ali atrapalha o comando, polui o log do
    # deploy com batidas num endereço que ainda não está no ar, e no
    # `test` deixaria uma thread viva entre casos.
    if _comando_de_manutencao():
        return False
    return bool(_endereco())


#: Comandos que carregam os apps mas não são o servidor. `runserver` e
#: `observar_pendencias` ficam de fora da lista de propósito: os dois são
#: processos longos, e nos dois a instância precisa continuar de pé.
_COMANDOS_SEM_BATIDA = frozenset({
    "migrate", "makemigrations", "collectstatic", "test", "shell",
    "createsuperuser", "check", "dbshell", "showmigrations", "loaddata",
    "dumpdata", "compress", "squashmigrations",
})


def _comando_de_manutencao():
    argumentos = list(sys.argv[1:2])
    return bool(argumentos) and argumentos[0] in _COMANDOS_SEM_BATIDA


def _endereco():
    """O endereço público desta instância, sem barra no fim."""
    base = (
        getattr(settings, "SEMPRE_PRONTO_URL", "")
        or getattr(settings, "INTERNO_BASE_URL", "")
        or getattr(settings, "SITE_URL", "")
    ).strip().rstrip("/")
    if not base:
        return ""
    partes = urlsplit(base)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return ""
    return f"{partes.scheme}://{partes.netloc}"


def _bater(endereco, sessao):
    """Uma batida. Nunca levanta: ela roda sozinha e para sempre."""
    try:
        inicio = time.perf_counter()
        resposta = sessao.get(
            f"{endereco}/pronto/?origem=sempre-pronto",
            timeout=20,
            headers={"User-Agent": "lazersport-sempre-pronto/1"},
        )
        duracao = round((time.perf_counter() - inicio) * 1000)
        if resposta.status_code != 200:
            log.warning(
                "sempre_pronto status=%s duration_ms=%s",
                resposta.status_code, duracao,
            )
        elif duracao > 5000:
            # Demorou: a instância provavelmente estava dormindo e
            # acabou de acordar. Registrar isso é o que permite descobrir
            # que o intervalo está frouxo demais.
            log.warning("sempre_pronto acordou duration_ms=%s", duracao)
    except Exception as erro:  # rede, DNS, TLS, o que for
        log.warning("sempre_pronto falhou: %s", erro.__class__.__name__)


def _ciclo(endereco, intervalo):
    import requests

    sessao = requests.Session()
    # A primeira batida espera um pouco: o processo ainda está subindo, e
    # bater no próprio endereço antes de o servidor aceitar conexão só
    # geraria um aviso de falha no primeiro segundo de vida.
    time.sleep(min(30, intervalo))
    while True:
        _bater(endereco, sessao)
        time.sleep(intervalo)


def ligar():
    """Sobe a thread, uma vez por processo."""
    global _ligado

    if not _ativo():
        return False
    with _ja_ligado:
        if _ligado:
            return False
        _ligado = True

    endereco = _endereco()
    intervalo = max(60, int(getattr(settings, "SEMPRE_PRONTO_INTERVALO", 240)))
    thread = threading.Thread(
        target=_ciclo,
        args=(endereco, intervalo),
        name="sempre-pronto",
        daemon=True,
    )
    thread.start()
    log.info(
        "sempre_pronto ligado endereco=%s intervalo=%ss", endereco, intervalo,
    )
    return True
