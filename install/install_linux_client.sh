#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/kymorem"
PORT="${KYMOREM_PORT:-54865}"
NAME="${KYMOREM_NAME:-linux-client}"
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

echo "Stopping old KyMoRem and Barrier instances..."
pkill -f "$APP_DIR/kymorem_client.py" >/dev/null 2>&1 || true
pkill -f "kymorem-client" >/dev/null 2>&1 || true
pkill -f "barrier|barrierc|barriers" >/dev/null 2>&1 || true
systemctl stop Barrier barrier barriers barrierc >/dev/null 2>&1 || true
systemctl disable Barrier barrier barriers barrierc >/dev/null 2>&1 || true
kill_kymorem_port_owner "$PORT" tcp
kill_kymorem_port_owner "54866" udp

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3 python3-venv python3-pip xdotool x11-utils xclip xsel psmisc yad libnotify-bin
  apt-get purge -y barrier barrier-common >/dev/null 2>&1 || true
  apt-get autoremove -y >/dev/null 2>&1 || true
fi

mkdir -p "$APP_DIR"
install -m 0755 /tmp/kymorem_client.py "$APP_DIR/kymorem_client.py"
install -m 0644 /tmp/kymorem_common.py "$APP_DIR/kymorem_common.py"
install -m 0644 /tmp/kymorem_crypto.py "$APP_DIR/kymorem_crypto.py"
install -m 0644 /tmp/kymorem_discovery.py "$APP_DIR/kymorem_discovery.py"
if [ -f /tmp/uninstall_linux_client.sh ]; then
  install -m 0755 /tmp/uninstall_linux_client.sh "$APP_DIR/uninstall_linux_client.sh"
fi
if [ -f /tmp/kymorem_linux_tray.sh ]; then
  install -m 0755 /tmp/kymorem_linux_tray.sh "$APP_DIR/kymorem-tray.sh"
fi
if [ -f /tmp/kymorem-64.png ]; then
  install -m 0644 /tmp/kymorem-64.png "$APP_DIR/kymorem-64.png"
fi

python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/python" -m pip install --upgrade pip wheel
cat > "$APP_DIR/requirements.txt" <<'EOF'
cryptography==49.0.0
pqcrypto==0.4.0
EOF
"$APP_DIR/venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt" || {
  "$APP_DIR/venv/bin/python" -m pip install "cryptography==49.0.0"
  echo "pqcrypto non disponibile: KyMoRem usera il fallback cifrato PSK-HKDF+AESGCM."
}

cat > "$APP_DIR/start-client.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export DISPLAY="\${DISPLAY:-:0}"
export XAUTHORITY="\${XAUTHORITY:-$USER_HOME/.Xauthority}"
pkill -f "$APP_DIR/kymorem_client.py" >/dev/null 2>&1 || true
if [ -f "$APP_DIR/.token" ]; then
  exec "$APP_DIR/venv/bin/python" "$APP_DIR/kymorem_client.py" --bind 0.0.0.0 --port "$PORT" --name "$NAME" --token-file "$APP_DIR/.token"
fi
export KYMOREM_TOKEN="\${KYMOREM_TOKEN:-kymorem-local-default-change-me}"
exec "$APP_DIR/venv/bin/python" "$APP_DIR/kymorem_client.py" --bind 0.0.0.0 --port "$PORT" --name "$NAME"
EOF
chmod 0755 "$APP_DIR/start-client.sh"

mkdir -p "$USER_HOME/.config/autostart"
rm -f "$USER_HOME/.config/autostart/kymorem-client.desktop"
cat > "$USER_HOME/.config/autostart/kymorem-tray.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=KyMoRem Tray
Comment=KyMoRem client tray
Exec=$APP_DIR/kymorem-tray.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
chown -R "$USER_NAME:$USER_NAME" "$USER_HOME/.config/autostart" || true
chown -R root:root "$APP_DIR"

echo "Launching KyMoRem client now..."
sudo -u "$USER_NAME" DISPLAY=:0 XAUTHORITY="$USER_HOME/.Xauthority" nohup "$APP_DIR/start-client.sh" >/tmp/kymorem-client.launch.log 2>&1 &
if [ -x "$APP_DIR/kymorem-tray.sh" ]; then
  sudo -u "$USER_NAME" DISPLAY=:0 XAUTHORITY="$USER_HOME/.Xauthority" nohup "$APP_DIR/kymorem-tray.sh" >/tmp/kymorem-tray.launch.log 2>&1 &
fi
sleep 1
echo "KyMoRem client installed on port $PORT."
