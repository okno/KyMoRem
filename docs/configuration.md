# Configuration

## Windows Host

The Windows host reads:

```text
%APPDATA%\KyMoRem\config.json
```

Example:

```json
{
  "language": "it",
  "theme": "old_school_x11",
  "mode": "client",
  "server_on": false,
  "server_name": "Windows Host",
  "token": "replace-with-a-long-shared-token",
  "edge": "right",
  "security": {
    "required": true,
    "preferred_suite": "ml-kem-768+psk-hkdf-sha256+aes-256-gcm",
    "fallback_suite": "psk-hkdf-sha256+aes-256-gcm"
  },
  "clipboard": {
    "enabled": false,
    "max_bytes": 1048576,
    "text_only": true,
    "files_enabled": false,
    "max_file_bytes": 5242880,
    "chunk_bytes": 32768,
    "inbox_dir": "KyMoRem Inbox"
  },
  "discovery": {
    "enabled": true,
    "auto_connect": true,
    "udp_port": 54866
  },
  "email_relay": {
    "enabled": false,
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_starttls": true,
    "smtp_username": "",
    "smtp_password_env": "KYMOREM_SMTP_PASSWORD",
    "from": "kymorem@example.invalid",
    "to": [],
    "events": ["client_connected", "client_disconnected", "security_error"]
  },
  "clients": [
    {
      "name": "right-side-linux",
      "host": "192.0.2.50",
      "port": 54865,
      "position": "right"
    }
  ]
}
```

Restart KyMoRem after editing.

Clipboard text sync requires `clipboard.enabled=true`. File transfer also
requires `clipboard.files_enabled=true`. Incoming files are saved to
`Downloads/KyMoRem Inbox` on Windows and `~/KyMoRem Inbox` on Linux. File chunks
stay below the secure frame limit and each file is bounded by
`clipboard.max_file_bytes`.

Portable Windows and Win7 clients listen for inbound control traffic on
`54865/tcp` and advertise discovery on `54866/udp`. To pre-authorize private-LAN
access without waiting for the first Windows Firewall popup, the client now
tries to install the required rules automatically on first launch. If you prefer
to prepare the machine in advance, run the client once as administrator with:

```powershell
KyMoRem-0.2.0-rc1-windows7-x86-client.exe --install-firewall-rules
```

The built-in helper installs inbound rules scoped to the `Private` profile and
`LocalSubnet`. Remove them later with `--remove-firewall-rules`.

The placeholder `kymorem-local-default-change-me` is a development marker, not
a deployment secret. The runtime refuses it unless
`KYMOREM_ALLOW_DEFAULT_TOKEN=1` is set for diagnostics.

## Linux Client

Environment variables:

```bash
KYMOREM_BIND=0.0.0.0
KYMOREM_PORT=54865
KYMOREM_NAME=right-side-linux
KYMOREM_TOKEN=replace-with-a-long-shared-token
DISPLAY=:0
XAUTHORITY=$HOME/.Xauthority
```

For daemon deployments prefer a protected token file and `--token-file` so the
shared secret is not visible in process listings:

```bash
sudo install -m 0640 -o root -g linux /path/to/token /opt/kymorem/.token
/opt/kymorem/kymorem_client.py --bind 0.0.0.0 --port 54865 --token-file /opt/kymorem/.token
```

Installed client path:

```text
/opt/kymorem
```

Autostart entry:

```text
~/.config/autostart/kymorem-tray.desktop
```

## Localization

Supported product slots:

```text
it  Italian, primary
en  English
ch  Swiss slot
```

No other localization files are part of the v0.2.0-rc1 public package.
