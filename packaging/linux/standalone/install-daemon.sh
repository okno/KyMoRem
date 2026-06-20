#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${KYMOREM_APP_DIR:-$HOME/.local/share/kymorem}"
UNIT_DIR="$HOME/.config/systemd/user"
AUTOSTART_DIR="$HOME/.config/autostart"

mkdir -p "$APP_DIR/bin" "$UNIT_DIR" "$AUTOSTART_DIR"
cp -R "$DIR/bin/." "$APP_DIR/bin/"
cp "$DIR/run-client.sh" "$APP_DIR/run-client.sh"
cp "$DIR/run-test.sh" "$APP_DIR/run-test.sh"
cp "$DIR/requirements.txt" "$APP_DIR/requirements.txt"
cp "$DIR/kymorem-tray.sh" "$APP_DIR/kymorem-tray.sh"
[ -f "$DIR/kymorem-64.png" ] && cp "$DIR/kymorem-64.png" "$APP_DIR/kymorem-64.png"
chmod 0755 "$APP_DIR/run-client.sh" "$APP_DIR/run-test.sh" "$APP_DIR/kymorem-tray.sh" "$APP_DIR/bin/kymorem_client.py"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip wheel
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
"$APP_DIR/.venv/bin/python" -m pip install "pqcrypto>=0.4.0" || echo "pqcrypto non disponibile: fallback cifrato PSK-HKDF+AESGCM."

sed "s|@APP_DIR@|$APP_DIR|g" "$DIR/kymorem-client.service" > "$UNIT_DIR/kymorem-client.service"
systemctl --user daemon-reload
systemctl --user enable --now kymorem-client.service

cat > "$AUTOSTART_DIR/kymorem-tray.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=KyMoRem Tray
Comment=KyMoRem client tray
Exec=$APP_DIR/kymorem-tray.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "KyMoRem standalone daemon installed."
echo "Status: systemctl --user status kymorem-client.service"
