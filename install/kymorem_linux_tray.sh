#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/kymorem"
PORT="${KYMOREM_PORT:-54865}"
ICON="$APP_DIR/kymorem-64.png"
RUNTIME_DIR="${KYMOREM_RUNTIME_DIR:-${XDG_RUNTIME_DIR:-/tmp/kymorem-$(id -u)}}"
mkdir -p "$RUNTIME_DIR"
chmod 700 "$RUNTIME_DIR" >/dev/null 2>&1 || true
LOG="$RUNTIME_DIR/kymorem-client.log"
LAUNCH_LOG="$RUNTIME_DIR/kymorem-tray.log"

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && [ -S "/run/user/$(id -u)/bus" ]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
fi

ensure_client() {
  if ! pgrep -f "$APP_DIR/kymorem_client.py" >/dev/null 2>&1; then
    nohup "$APP_DIR/start-client.sh" >>"$LAUNCH_LOG" 2>&1 &
    sleep 1
  fi
}

restart_client() {
  pkill -f "$APP_DIR/kymorem_client.py" >/dev/null 2>&1 || true
  nohup "$APP_DIR/start-client.sh" >>"$LAUNCH_LOG" 2>&1 &
}

stop_client() {
  pkill -f "$APP_DIR/kymorem_client.py" >/dev/null 2>&1 || true
}

show_status() {
  if pgrep -f "$APP_DIR/kymorem_client.py" >/dev/null 2>&1; then
    MSG="KyMoRem client attivo su porta $PORT"
  else
    MSG="KyMoRem client fermo"
  fi
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "KyMoRem" "$MSG"
  else
    xmessage "$MSG" >/dev/null 2>&1 || true
  fi
}

show_log() {
  if command -v xmessage >/dev/null 2>&1; then
    tail -n 35 "$LOG" 2>/dev/null | xmessage -file - >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "KyMoRem log" "$(tail -n 8 "$LOG" 2>/dev/null)"
  fi
}

quit_tray() {
  stop_client
  pkill -f "yad --notification.*KyMoRem" >/dev/null 2>&1 || true
  pkill -f "$APP_DIR/kymorem-tray.sh" >/dev/null 2>&1 || true
}

ensure_client

if ! command -v yad >/dev/null 2>&1; then
  echo "yad is required for KyMoRem tray" >>"$LAUNCH_LOG"
  wait
fi

MENU="Status!$APP_DIR/kymorem-tray.sh --status|Restart client!$APP_DIR/kymorem-tray.sh --restart|Stop client!$APP_DIR/kymorem-tray.sh --stop|Show log!$APP_DIR/kymorem-tray.sh --log|Quit!$APP_DIR/kymorem-tray.sh --quit"

case "${1:-}" in
  --status) show_status; exit 0 ;;
  --restart) restart_client; show_status; exit 0 ;;
  --stop) stop_client; show_status; exit 0 ;;
  --log) show_log; exit 0 ;;
  --quit) quit_tray; exit 0 ;;
esac

exec yad \
  --notification \
  --image="$ICON" \
  --text="KyMoRem client // right-side receiver // $PORT" \
  --command="$APP_DIR/kymorem-tray.sh --status" \
  --menu="$MENU"
