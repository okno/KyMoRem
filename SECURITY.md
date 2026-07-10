# Security Policy

KyMoRem handles keyboard and pointer control. Treat each host and client as a
high-trust endpoint.

## Supported Versions

| Version | Supported |
| --- | --- |
| 0.2.0-rc2 | Active release-candidate support |
| 0.2.0-rc1 | Superseded by rc2 |
| 0.1.x | Best-effort technical seed support |

## Current Security Model

KyMoRem v0.2.0-rc2 protects sessions with:

- shared token required by discovery and TCP session establishment;
- server-side approval for generated/known clients;
- unknown discovery clients disabled unless explicit auto-approval is enabled;
- encrypted UDP discovery payloads on `54866/udp`;
- encrypted TCP input channel on `54865/tcp`;
- AES-256-GCM authenticated encryption for frame confidentiality/integrity;
- ML-KEM-768 hybrid key establishment when the optional PQ provider is present;
- PSK-HKDF-SHA256 fallback when the PQ provider is not available;
- local emergency release with `Ctrl+Esc`;
- clipboard sync disabled by default;
- no remote shell feature in the input protocol.

The post-quantum KEM target is ML-KEM, standardized by NIST in FIPS 203. The
project keeps cryptographic agility because deployments may temporarily run the
PSK fallback on systems where a PQ provider is not installed.

Reference:

- NIST FIPS 203 ML-KEM: https://csrc.nist.gov/pubs/fips/203/final

## Deployment Rules

- Replace `kymorem-local-default-change-me` before operational use. Runtime
  refuses it unless `KYMOREM_ALLOW_DEFAULT_TOKEN=1` is set for diagnostics.
- Keep `54865/tcp` and `54866/udp` limited to trusted LAN segments.
- Use host firewalls to scope traffic to expected subnets.
- Store SMTP credentials in environment variables, not in `config.json`.
- Do not enable clipboard sync without a separate data-loss policy.
- Run the Linux client as the graphical user, not as a system-wide root input
  daemon.

## Reporting Vulnerabilities

Use the repository security advisory workflow when available. Do not file public
issues for exploitable input injection, authentication bypass, transport
downgrade or token disclosure reports until a fix is ready.
