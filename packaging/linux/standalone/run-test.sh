#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-127.0.0.1}"
PORT="${2:-54865}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${KYMOREM_PYTHON:-$DIR/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="${KYMOREM_PYTHON:-/usr/bin/python3}"
fi

"$PYTHON" - "$DIR/bin" "$HOST" "$PORT" "${KYMOREM_TOKEN:-kymorem-local-default-change-me}" <<'PY'
import socket
import sys

sys.path.insert(0, sys.argv[1])
from kymorem_common import VERSION, frame
from kymorem_crypto import secure_connect

host = sys.argv[2]
port = int(sys.argv[3])
token = sys.argv[4]

with socket.create_connection((host, port), timeout=5) as sock:
    sock.settimeout(5)
    link = secure_connect(sock, token, {"role": "tester", "name": "standalone-test", "platform": "linux", "version": VERSION})
    link.send(frame("hello", role="tester", name="standalone-test"))
    link.send(frame("pulse"))
    for message in link.read_frames():
        print(message)
        if message.get("type") == "pulse_ack":
            break
PY
