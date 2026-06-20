#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${KYMOREM_APP_DIR:-$HOME/.local/share/kymorem}"

systemctl --user disable --now kymorem-client.service >/dev/null 2>&1 || true
rm -f "$HOME/.config/systemd/user/kymorem-client.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true
pkill -f "$APP_DIR/bin/kymorem_client.py" >/dev/null 2>&1 || true
pkill -f "$APP_DIR/kymorem-tray.sh" >/dev/null 2>&1 || true
pkill -f "yad --notification.*KyMoRem" >/dev/null 2>&1 || true
rm -f "$HOME/.config/autostart/kymorem-tray.desktop"
rm -rf "$APP_DIR"

echo "KyMoRem standalone daemon removed."
