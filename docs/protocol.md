# Protocol

KyMoRem v1 uses newline-delimited JSON envelopes. After the TCP handshake,
application frames are carried inside authenticated encrypted `secure` frames.

Default ports:

```text
54865/tcp  secure host-client session
54866/udp  encrypted LAN discovery
```

## Plain Handshake Frames

Only the transport handshake is sent in plaintext:

```text
host   -> client: kymorem_crypto_init
client -> host:   kymorem_crypto_challenge
host   -> client: kymorem_crypto_finish
client -> host:   kymorem_crypto_ack
```

The handshake negotiates one of:

```text
ml-kem-768+psk-hkdf-sha256+aes-256-gcm
psk-hkdf-sha256+aes-256-gcm
```

`ml-kem-768` is selected when both peers expose the optional PQ provider.
Otherwise the protocol falls back to PSK-HKDF with AES-256-GCM. The selected
suite is logged by both peers.

## Secure Frame Shape

Every encrypted application message is wrapped as:

```json
{
  "protocol": 1,
  "type": "secure",
  "payload": {
    "suite": "ml-kem-768+psk-hkdf-sha256+aes-256-gcm",
    "seq": 1,
    "nonce": "base64url",
    "data": "base64url"
  }
}
```

The decrypted application frame retains the common shape:

```json
{"protocol":1,"type":"move","ts":1781910000000,"payload":{"dx":10,"dy":-2}}
```

## Application Frame Types

- `hello`: endpoint identity, role, version and display metadata.
- `status`: client status report.
- `move`: relative pointer movement.
- `button`: pointer button up/down.
- `wheel`: scroll delta.
- `key`: keyboard key up/down.
- `release`: end remote-control mode.
- `edge`: client reports pointer reached an edge.
- `pulse`: operational test request.
- `pulse_ack`: operational test response.
- `error`: structured client-side dispatch error.

## Discovery Frame

Discovery uses UDP broadcast. Payloads are encrypted with a key derived from the
shared token:

```json
{
  "magic": "KMRD1",
  "protocol": 1,
  "kid": "token-fingerprint",
  "nonce": "base64url",
  "data": "base64url"
}
```

The decrypted payload is a `discovery_announce` frame containing role, host,
port, platform, process id and crypto capabilities.

## Compatibility Rule

Peers disconnect when the protocol version or security suite cannot be
negotiated. Backward compatibility should be added only after the v1 behavior is
stable across Windows, Linux, macOS and Android.
