"""Configuração do gunicorn — um lugar só, ajustável por variável.

POR QUE ISTO SAIU DO `Procfile`.

A linha do Procfile tinha onze parâmetros escritos à mão. Mudar qualquer
um exigia publicar código, e não havia onde explicar por que cada número
é aquele. Pior: dois deles eram causa direta de lentidão e de 502
intermitente no painel, e ninguém tinha como saber disso lendo a linha.

O QUE MUDOU E POR QUÊ

1. `max_requests` desligado por padrão. Era 600: a cada 600 requisições o
   ÚNICO worker era derrubado e refeito. Enquanto o Django subia de novo
   -- alguns segundos, com allauth, cloudinary e o resto --, as
   requisições em fila esperavam por esse tempo inteiro, e as que
   estouravam o prazo do proxy voltavam como 502 sem explicação nenhuma.
   Reciclar worker existe para conter vazamento de memória; com gthread e
   este aplicativo não há vazamento medido que justifique pagar esse
   preço várias vezes por dia. Quem quiser de volta: `WEB_MAX_REQUESTS`.

2. Mais threads (4 -> 8). O trabalho deste painel é esperar o Supabase
   responder, não calcular: enquanto uma thread espera o banco, a outra
   atende. Quatro threads com quatro pessoas na fábrica e o banco lento
   já enfileirava a quinta requisição atrás de um `SELECT` de 12
   segundos. Threads custam pilha, não cópia da aplicação -- é o
   parâmetro certo para subir numa instância pequena.

3. `backlog` maior. É a fila de conexões aceitas antes de o worker
   pegá-las. Durante a partida a frio ela é o que segura a requisição em
   vez de deixá-la ser recusada.

TUDO CONTINUA AJUSTÁVEL sem publicar código: WEB_WORKERS, WEB_THREADS,
WEB_TIMEOUT, WEB_MAX_REQUESTS. Se um dia a instância tiver memória
sobrando, WEB_WORKERS=2 passa a ser a melhora mais barata: com dois
processos, a queda de um deixa de ser a queda do site.

ATENÇÃO AO SUBIR `WEB_WORKERS`: o cache do painel é `LocMemCache`, que
vive dentro do processo. Com dois workers, cada um tem o seu, e os
contadores das bolinhas podem divergir por até `INTERNO_AVISOS_CACHE_TTL`
segundos entre uma tela e outra. Para mais de um worker sem esse efeito,
configure um cache compartilhado (Redis) antes.
"""

import os


def _inteiro(nome, padrao, minimo=0):
    try:
        return max(minimo, int(os.getenv(nome, str(padrao))))
    except (TypeError, ValueError):
        return padrao


bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

worker_class = "gthread"
workers = _inteiro("WEB_WORKERS", 1, minimo=1)
threads = _inteiro("WEB_THREADS", 8, minimo=2)

# Uma partida a frio com o Supabase pode passar de trinta segundos. O
# limite existe para matar requisição travada, não para matar requisição
# lenta -- por isso ele é folgado, e o `statement_timeout` de 12s do
# Django é quem corta consulta emperrada antes.
timeout = _inteiro("WEB_TIMEOUT", 90, minimo=30)
graceful_timeout = _inteiro("WEB_GRACEFUL_TIMEOUT", 30, minimo=5)
keepalive = _inteiro("WEB_KEEPALIVE", 5, minimo=0)

# 0 = desligado. Ver a explicação no topo deste arquivo.
max_requests = _inteiro("WEB_MAX_REQUESTS", 0)
max_requests_jitter = _inteiro("WEB_MAX_REQUESTS_JITTER", 0)

backlog = _inteiro("WEB_BACKLOG", 2048, minimo=64)

# /dev/shm evita que o heartbeat do worker vá parar num disco lento e o
# arbiter conclua, erradamente, que o worker morreu.
worker_tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else None

capture_output = True
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("WEB_LOG_LEVEL", "info")

# O tempo real de cada requisição no log de acesso: sem ele, "está
# lento" é uma impressão, e não um número que dá para comparar entre
# ontem e hoje.
access_log_format = (
    '%(h)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'
)
