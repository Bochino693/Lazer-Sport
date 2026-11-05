#!/usr/bin/env bash
# Teste de carga do Lazer & Sport.
#
# Sobe o gunicorn de produção (gunicorn.conf.py + lazer.wsgi, ou seja, com o
# escudo de tráfego e o health check no caminho) na porta 8790, sobre uma
# CÓPIA do banco de demonstração, roda o locust em estágios (10, 25, 50,
# 100 e 200 usuários) e guarda os CSVs em ferramentas/carga/resultados/.
# Faz isso duas vezes: WEB_WORKERS=1 (como no Render hoje) e WEB_WORKERS=2.
#
# Uso:  ferramentas/carga/rodar.sh
#
# Variáveis opcionais:
#   CARGA_SCRATCH    pasta com venv-ls/ e lsdemo/ (padrão: o scratchpad da sessão)
#   CARGA_VENV       venv com django, gunicorn e locust
#   CARGA_PYTHONPATH pasta do ls_carga_settings.py
#   CARGA_PORTA      porta do gunicorn (8790)
#   CARGA_ESTAGIOS   "10 25 50 100 200"
#   CARGA_DURACAO    duração de cada estágio (60s)
#   CARGA_SPAWN      usuários criados por segundo (10)
#   CARGA_WORKERS    variantes de WEB_WORKERS a testar ("1 2")
#   CARGA_LATENCIA_MS latência artificial por consulta ao banco, em ms (0 =
#                    desligado). Com 40, o sqlite local passa a custar o que
#                    o Supabase custa pela rede (ver latencia_db.py); a
#                    etiqueta dos arquivos ganha o sufixo "_l40".
#   CARGA_ROTULO     prefixo da etiqueta dos arquivos ("antes_", "depois_"),
#                    para guardar duas medições lado a lado em resultados/.
set -euo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$AQUI/../.." && pwd)
S=${CARGA_SCRATCH:-/tmp/claude-0/-home-user/c8ca5d41-b6a7-53f6-ae6c-1c3afe7098e5/scratchpad}
VENV=${CARGA_VENV:-$S/venv-ls}
export PYTHONPATH=${CARGA_PYTHONPATH:-$S/lsdemo}
export DJANGO_SETTINGS_MODULE=${CARGA_SETTINGS:-ls_carga_settings}
export PORT=${CARGA_PORTA:-8790}
export PYTHONDONTWRITEBYTECODE=1
# gthread com 8 threads, como no Render; o escudo reserva 4 vagas públicas.
export WEB_THREADS=${WEB_THREADS:-8}
export PUBLIC_CONCURRENCY=${PUBLIC_CONCURRENCY:-4}
# Latência artificial por consulta (ferramentas/carga/latencia_db.py, ligada
# pelo ls_carga_settings quando a variável está definida).
export CARGA_LATENCIA_MS=${CARGA_LATENCIA_MS:-0}
ROTULO=${CARGA_ROTULO:-}

HOST_URL="http://127.0.0.1:$PORT"
RES="$AQUI/resultados"
ESTAGIOS=${CARGA_ESTAGIOS:-"10 25 50 100 200"}
DURACAO=${CARGA_DURACAO:-60s}
SPAWN=${CARGA_SPAWN:-10}
VARIANTES=${CARGA_WORKERS:-"1 2"}

mkdir -p "$RES"
cd "$RAIZ"

PID=""
AMOSTRADOR=""

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

parar_servidor() {
    if [ -n "$AMOSTRADOR" ] && kill -0 "$AMOSTRADOR" 2>/dev/null; then
        kill "$AMOSTRADOR" 2>/dev/null || true
    fi
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        log "parando gunicorn (pid $PID)"
        kill -TERM "$PID" 2>/dev/null || true
        for _ in $(seq 1 30); do
            kill -0 "$PID" 2>/dev/null || break
            sleep 1
        done
        kill -KILL "$PID" 2>/dev/null || true
    fi
    PID=""; AMOSTRADOR=""
}
trap parar_servidor EXIT

subir_servidor() {
    local etiqueta=$1 workers=$2
    log "subindo gunicorn: WEB_WORKERS=$workers WEB_THREADS=$WEB_THREADS PUBLIC_CONCURRENCY=$PUBLIC_CONCURRENCY CARGA_LATENCIA_MS=$CARGA_LATENCIA_MS porta $PORT"
    WEB_WORKERS=$workers nohup "$VENV/bin/gunicorn" -c gunicorn.conf.py lazer.wsgi:application \
        > "$RES/${etiqueta}_gunicorn.log" 2>&1 &
    PID=$!
    for _ in $(seq 1 60); do
        if curl -fs -o /dev/null "$HOST_URL/healthz/"; then break; fi
        sleep 1
    done
    curl -fs -o /dev/null "$HOST_URL/healthz/" || { log "o gunicorn nao subiu"; tail -30 "$RES/${etiqueta}_gunicorn.log"; exit 1; }

    "$VENV/bin/python" "$AQUI/cpu_amostra.py" "$PID" "$RES/${etiqueta}_cpu.csv" 5 &
    AMOSTRADOR=$!

    # Aquecimento: uma passada por cada tela, para o cache da vitrine e os
    # templates compilados não entrarem na conta do primeiro estágio.
    for caminho in / /brinquedos/ /brinquedo/1/ /jogos/ /categoria/1/ /static/site/ls-base.css; do
        curl -s -o /dev/null "$HOST_URL$caminho"
    done
    curl -s -o /dev/null -H "Host: interno.localhost:$PORT" "$HOST_URL/login/inner/"
    printf 'etiqueta,workers,usuarios,inicio,fim,requisicoes_log,http503,http429,http5xx_django\n' > "$RES/${etiqueta}_estagios.csv"
}

estagio() {
    local etiqueta=$1 workers=$2 usuarios=$3
    local nome prefixo linha_ini inicio fim trecho n503 n429 n5xx total
    nome=$(printf '%s_u%03d' "$etiqueta" "$usuarios")
    prefixo="$RES/$nome"
    rm -f "${prefixo}"_*.csv
    linha_ini=$(wc -l < "$RES/${etiqueta}_gunicorn.log")
    inicio=$(date +%s)
    log "estagio $usuarios usuarios (${DURACAO}, spawn $SPAWN/s) -> $nome"
    "$VENV/bin/locust" -f "$AQUI/locustfile.py" --headless --host "$HOST_URL" \
        -u "$usuarios" -r "$SPAWN" -t "$DURACAO" --stop-timeout 10 \
        --csv "$prefixo" --only-summary --exit-code-on-error 0 --loglevel WARNING \
        > "${prefixo}_locust.txt" 2>&1 || log "locust terminou com erro (veja ${prefixo}_locust.txt)"
    fim=$(date +%s)
    trecho=$(tail -n +"$((linha_ini + 1))" "$RES/${etiqueta}_gunicorn.log" | grep -E '^[0-9.]+ "' || true)
    total=$(printf '%s\n' "$trecho" | grep -c . || true)
    n503=$(printf '%s\n' "$trecho" | grep -c '" 503 ' || true)
    n429=$(printf '%s\n' "$trecho" | grep -c '" 429 ' || true)
    n5xx=$(printf '%s\n' "$trecho" | grep -Ec '" 50[0-9] [0-9]+ [0-9]+ms' | awk -v a="$n503" '{print $1 - a}' || true)
    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s\n' "$etiqueta" "$workers" "$usuarios" "$inicio" "$fim" "$total" "$n503" "$n429" "$n5xx" \
        >> "$RES/${etiqueta}_estagios.csv"
    tail -n 4 "${prefixo}_locust.txt" | sed 's/^/    /'
    sleep 5
}

for workers in $VARIANTES; do
    etiqueta="${ROTULO}w${workers}"
    if [ "$CARGA_LATENCIA_MS" != "0" ]; then etiqueta="${etiqueta}_l${CARGA_LATENCIA_MS}"; fi
    subir_servidor "$etiqueta" "$workers"
    for usuarios in $ESTAGIOS; do
        estagio "$etiqueta" "$workers" "$usuarios"
    done
    parar_servidor
done

log "resumo"
"$VENV/bin/python" "$AQUI/resumir.py" "$RES" | tee "$RES/resumo.md"
