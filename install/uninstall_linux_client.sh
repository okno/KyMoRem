#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/kymorem"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"

kill_kymorem_port_owner() {
  local endpoint="$1"
  local proto="$2"
  command -v fuser >/dev/null 2>&1 || return 0
  local pids
  pids="$(fuser -n "$proto" "$endpoint" 2>/dev/null || true)"
  for pid in $pids; do
    local cmdline
    cmdline="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
    case "$cmdline" in
      *[Kk][Yy][Mm][Oo][Rr][Ee][Mm]*)
        kill -TERM "$pid" >/dev/null 2>&1 || true
        ;;
    esac
  done
}

remove_app_dir() {
  if [[ "$APP_DIR" != "/opt/kymorem" ]]; then
    echo "Refusing to remove unexpected APP_DIR: $APP_DIR" >&2
    exit 1
  fi
  rm -rf -- "$APP_DIR"
}

pkill -f "$APP_DIR/kymorem_client.py" >/dev/null 2>&1 || true
pkill -f "$APP_DIR/kymorem-tray.sh" >/dev/null 2>&1 || true
pkill -f "yad --notification.*KyMoRem" >/dev/null 2>&1 || true
pkill -f "kymorem-client" >/dev/null 2>&1 || true
kill_kymorem_port_owner "54865" tcp
kill_kymorem_port_owner "54866" udp
remove_app_dir
rm -f "$USER_HOME/.config/autostart/kymorem-client.desktop"
rm -f "$USER_HOME/.config/autostart/kymorem-tray.desktop"
echo "KyMoRem client removed."
