# LAN Discovery

KyMoRem discovery is a small proprietary UDP broadcast protocol. It is designed
to classify endpoints as host or client without exposing plaintext metadata to
devices that do not know the shared token.

It does not use Bonjour, Avahi compatibility shims or Barrier's screen-name
autoconfiguration model.

## Port

```text
54866/udp
```

## Announcement

Each endpoint periodically emits an encrypted `discovery_announce` payload:

```json
{
  "role": "client",
  "name": "linux-client",
  "host": "192.0.2.50",
  "port": 54865,
  "platform": "linux",
  "capabilities": {
    "aead": "AES-256-GCM",
    "hkdf": "HKDF-SHA256",
    "post_quantum_kem": "ML-KEM-768"
  }
}
```

The host accepts only announcements that decrypt with the configured token.

## Autoconnect Policy

When `discovery.auto_connect` is enabled, the host can connect automatically to
an enabled client that has already been approved or manually configured.

Manual configuration always wins over discovery.

Unknown discovery clients are not approved by default. They are saved as
`discovery_pending` with `enabled=false`, so they can be reviewed without
becoming an active pointer target.

To restore the older trust-on-token behavior for a lab network, set:

```json
{
  "discovery": {
    "auto_approve": true
  }
}
```

## Pre-Approved Pending Clients

Server-side onboarding can register a client before its IP address is known:

```json
{
  "name": "windows7",
  "host": "pending",
  "port": 54865,
  "x": 4,
  "y": 0,
  "enabled": true,
  "source": "manual",
  "approved": true
}
```

When a discovery announcement decrypts with the configured token and carries the
same client name and port, the host replaces `pending` with the real LAN address
instead of creating a separate discovery client.

Use `scripts/New-KyMoRemWin7ClientPackage.ps1` to create this entry and the
matching Windows 7 client folder.

## Broadcast-Limited Networks

When broadcast is blocked, set:

```json
{
  "discovery": {
    "enabled": false
  }
}
```

Then configure `clients[0].host` manually.
