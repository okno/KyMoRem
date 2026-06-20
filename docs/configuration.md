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
  "theme": "cyber_noir",
  "server_name": "Windows Host",
  "token": "replace-with-a-long-shared-token",
  "edge": "right",
  "security": {
    "required": true,
    "preferred_suite": "ml-kem-768+psk-hkdf-sha256+aes-256-gcm",
    "fallback_suite": "psk-hkdf-sha256+aes-256-gcm"
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

No other localization files are part of the v0.1.0 public package.
