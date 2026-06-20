# Cryptography

KyMoRem v0.1.1 uses a cryptographic transport layer around the JSON protocol.

## Suites

Preferred suite:

```text
ml-kem-768+psk-hkdf-sha256+aes-256-gcm
```

Fallback suite:

```text
psk-hkdf-sha256+aes-256-gcm
```

`ML-KEM-768` is available when the optional `pqcrypto` provider is installed.
Both suites use the shared token as a pre-shared secret component. Application
frames are encrypted and authenticated with `AES-256-GCM`.

## Discovery Protection

Discovery datagrams are encrypted with AES-GCM using a key derived from the
shared token. A token fingerprint is included for quick rejection; the token
itself is never broadcast.

## Key Derivation

Session keys are derived with HKDF-SHA256 from:

- shared token material;
- endpoint nonces;
- handshake transcript;
- ML-KEM shared secret when available.

## Operational Guidance

- Use a long random token per deployment.
- The development placeholder token is refused by default.
- Rotate tokens when an endpoint is retired.
- Prefer ML-KEM-capable builds for new deployments.
- Treat the PSK fallback as encrypted compatibility mode, not as post-quantum
  security.
- Do not create or migrate Barrier PEM files; KyMoRem does not depend on static
  user-managed certificate files in the Python MVP.

## Standards Reference

ML-KEM is standardized by NIST in FIPS 203:

```text
https://csrc.nist.gov/pubs/fips/203/final
```
