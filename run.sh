#!/usr/bin/env bash
# Punto de entrada fijo requerido por la especificación.
# Uso: ./run.sh "<instruccion>"
# Ejemplo: ./run.sh "add x5, x6, x7"
#
# Este script asume el esqueleto en Python tal cual se entrega. Si usted
# reestructura el proyecto (otro lenguaje, binario compilado, entorno
# virtual, etc.), ajuste este archivo para que siga invocando su solución
# de la misma forma: un solo argumento con la instrucción, y una línea de
# salida "HEX: 0x........".
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo 'Uso: ./run.sh "<instruccion>"' >&2
    echo 'Ejemplo: ./run.sh "add x5, x6, x7"' >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/src/encoder.py" "$1"
