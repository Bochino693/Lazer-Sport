#!/bin/bash
# Compila o programa dos jogos para Windows (ferramentas/exe) e grava
# core/exe_casca/jogo-windows.exe, a casca que o painel põe em todo .exe que gera
# (core/jogos_exe_gerar.py). Precisa do Go 1.22 ou mais novo; nada mais (sem cgo).
#   ./montar_casca.sh          a casca do Windows (a que vai no repositório)
#   ./montar_casca.sh linux    uma casca de Linux, só para testar o .exe aqui
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
mkdir -p "$RAIZ/core/exe_casca"
cd "$AQUI"
if [ "${1:-}" = "linux" ]; then
  CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags "-s -w" -o "$AQUI/jogo-linux" .
  echo "ferramentas/exe/jogo-linux: $(wc -c < "$AQUI/jogo-linux") bytes"
else
  CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "-s -w -H=windowsgui" -o "$RAIZ/core/exe_casca/jogo-windows.exe" .
  echo "core/exe_casca/jogo-windows.exe: $(wc -c < "$RAIZ/core/exe_casca/jogo-windows.exe") bytes"
fi
