#!/bin/sh
exec python3 "$(dirname "$0")/src/encoder.py" "$@"
