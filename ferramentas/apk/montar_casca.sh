#!/bin/bash
# Compila o aplicativo dos jogos (ferramentas/apk/src) e grava core/apk_casca/classes.dex,
# o código que o painel põe em todo APK que gera (core/jogos_apk_gerar.py).
#
# Precisa do Java (JDK 8 ou mais novo) e baixa do Maven Central, uma vez:
#   - android.jar (com.google.android:android:4.1.1.4): a API do Android para compilar;
#   - dx (com.jakewharton.android.repackaged:dalvik-dx:16.0.1): converte para o Android.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
FERR="$AQUI/.ferramentas"
mkdir -p "$FERR" "$RAIZ/core/apk_casca"
[ -f "$FERR/android.jar" ] || curl -sSL -o "$FERR/android.jar" https://repo1.maven.org/maven2/com/google/android/android/4.1.1.4/android-4.1.1.4.jar
[ -f "$FERR/dx.jar" ] || curl -sSL -o "$FERR/dx.jar" https://repo1.maven.org/maven2/com/jakewharton/android/repackaged/dalvik-dx/16.0.1/dalvik-dx-16.0.1.jar
CLASSES="$(mktemp -d)"
trap 'rm -rf "$CLASSES"' EXIT
javac -encoding UTF-8 --release 8 -Xlint:-options -classpath "$FERR/android.jar" -d "$CLASSES" \
  $(find "$AQUI/src" -name '*.java')
java -cp "$FERR/dx.jar" com.android.dx.command.Main --dex --min-sdk-version=21 --output="$RAIZ/core/apk_casca/classes.dex" "$CLASSES"
echo "core/apk_casca/classes.dex: $(wc -c < "$RAIZ/core/apk_casca/classes.dex") bytes"
