# Email Relay

KyMoRem includes an optional SMTP relay for operational events. It is disabled
by default and does not store SMTP passwords in the repository or default
configuration.

## Use Cases

- notify administrators when a client connects or disconnects;
- notify operators when a security handshake fails;
- integrate with a mailbox, ticketing rule or monitoring bridge.

## Configuration

```json
{
  "email_relay": {
    "enabled": true,
    "smtp_host": "smtp.example.invalid",
    "smtp_port": 587,
    "smtp_starttls": true,
    "smtp_username": "kymorem-relay",
    "smtp_password_env": "KYMOREM_SMTP_PASSWORD",
    "from": "kymorem@example.invalid",
    "to": ["ops@example.invalid"],
    "events": ["client_connected", "client_disconnected", "security_error"]
  }
}
```

Set the password outside the config file:

```powershell
[Environment]::SetEnvironmentVariable("KYMOREM_SMTP_PASSWORD", "<secret>", "User")
```

## Event Types

- `client_connected`
- `client_disconnected`
- `security_error`

Relay failure is logged and never blocks input routing.
