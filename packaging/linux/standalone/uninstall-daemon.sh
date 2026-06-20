#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${KYMOREM_APP_DIR:-$HOME/.local/share/kymorem}"

remove_app_dir() {
  case "$APP_DIR" in
    "$HOME/.local/share/kymorem"|"$HOME/.local/share/kymorem-"*)
      rm -rf -- "$APP_DIR"
      ;;
    *)
      echo "Refusing to remove unexpected APP_DIR: $APP_DIR" >&2
      exit 1
      ;;
  esac
}

systemctl --user disable --now kymorem-client.service >/dev/null 2>&1 || true
rm -f "$HOME/.config/systemd/user/kymorem-client.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true
pkill -f "$APP_DIR/bin/kymorem_client.py" >/dev/null 2>&1 || true
pkill -f "$APP_DIR/kymorem-tray.sh" >/dev/null 2>&1 || true
pkill -f "yad --notification.*KyMoRem" >/dev/null 2>&1 || true
rm -f "$HOME/.config/autostart/kymorem-tray.desktop"
remove_app_dir

echo "KyMoRem standalone daemon removed."
