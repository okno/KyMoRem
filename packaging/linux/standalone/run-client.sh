#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
PYTHON="${KYMOREM_PYTHON:-$DIR/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="${KYMOREM_PYTHON:-/usr/bin/python3}"
fi
exec "$PYTHON" "$DIR/bin/kymorem_client.py" \
  --bind "${KYMOREM_BIND:-0.0.0.0}" \
  --port "${KYMOREM_PORT:-54865}" \
  --name "${KYMOREM_NAME:-$(hostname)}"
