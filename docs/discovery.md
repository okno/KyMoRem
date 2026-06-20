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

When `discovery.auto_connect` is enabled, the host can adopt the first
discovered client as the right-side target if the current configured host is
still the loopback placeholder.

Manual configuration always wins over discovery.

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
