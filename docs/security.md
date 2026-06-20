# Security Architecture

KyMoRem treats input control as a privileged operation.

## Baseline

- No plaintext input frames after handshake.
- Shared token required for discovery and session establishment.
- AES-256-GCM protects application frames.
- ML-KEM-768 is preferred when both peers provide `pqcrypto`.
- PSK-HKDF-SHA256 fallback remains encrypted but is not post-quantum.
- Clipboard sync is disabled.
- No remote shell or file-execution frame exists in the protocol.

## Main Threats

- unauthorized LAN endpoint attempting to inject input;
- token reuse after a device is retired;
- stale client process holding the TCP port;
- user losing local control while remote mode is active;
- operational alert credentials stored insecurely.

## Controls

- replace default token before deployment;
- restrict `54865/tcp` and `54866/udp` to trusted subnets;
- keep emergency release visible and local;
- use environment variables for SMTP secrets;
- rotate tokens when a client is removed;
- verify selected crypto suite in logs.
