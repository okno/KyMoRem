#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/kymorem"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"

pkill -f "$APP_DIR/kymorem_client.py" >/dev/null 2>&1 || true
pkill -f "$APP_DIR/kymorem-tray.sh" >/dev/null 2>&1 || true
pkill -f "yad --notification.*KyMoRem" >/dev/null 2>&1 || true
pkill -f "kymorem-client" >/dev/null 2>&1 || true
if command -v fuser >/dev/null 2>&1; then
  fuser -k 54865/tcp >/dev/null 2>&1 || true
  fuser -k 54866/udp >/dev/null 2>&1 || true
fi
rm -rf "$APP_DIR"
rm -f "$USER_HOME/.config/autostart/kymorem-client.desktop"
rm -f "$USER_HOME/.config/autostart/kymorem-tray.desktop"
echo "KyMoRem client removed."
