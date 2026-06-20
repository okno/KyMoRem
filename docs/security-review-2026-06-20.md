# Security Review 2026-06-20

Scope: Python runtime, Linux client lifecycle, Windows host UI/controller,
discovery, transport crypto, SMTP relay, installer scripts, and operational
documentation.

Reviewer model: hostile LAN user, malicious paired endpoint, local low-privilege
user on the Linux client, accidental operator misconfiguration, and stale
process recovery after Barrier/KyMoRem replacement.

## Cycle 1: Default Token Refusal

Finding: the development token could be used as a real deployment secret.

Fix:

- added token validation in `runtime/python/kymorem_crypto.py`;
- refused the default token unless `KYMOREM_ALLOW_DEFAULT_TOKEN=1`;
- enforced minimum token length.

Residual risk: token quality still depends on operator choice.

## Cycle 2: Frame Size Limit

Finding: JSON frame parsing accepted unbounded pending input.

Fix:

- added `MAX_FRAME_BYTES`;
- bounded plaintext and secure handshake frames;
- rejected oversized discovery datagrams.

Residual risk: authenticated peers can still send many valid frames; rate
limiting is a future control.

## Cycle 3: Secure Frame Replay Detection

Finding: encrypted frames had sequence numbers but the receiver did not enforce
monotonic order.

Fix:

- added receive-side sequence tracking;
- rejected replayed or out-of-order secure frames;
- rejected secure-frame suite mismatches.

Residual risk: TCP-level DoS remains possible from a paired endpoint.

## Cycle 4: Constant-Time Proof Checks

Finding: handshake proof and token-id checks used normal equality.

Fix:

- switched proof and token-id comparisons to `hmac.compare_digest`;
- changed token id derivation from raw SHA-256 prefix to HMAC-based id.

Residual risk: token ids are still observable metadata; strong tokens remain
required.

## Cycle 5: Safer Local IP Hint

Finding: local IP detection referenced a public resolver address.

Fix:

- replaced external address reference with TEST-NET route probing.

Residual risk: route-based hints can still be wrong on complex networks; peer
address fallback remains active.

## Cycle 6: Socket Cleanup Safety

Finding: `fuser -k` could terminate a non-KyMoRem process occupying the port.

Fix:

- runtime cleanup now enumerates socket owners and kills only command lines that
  contain `kymorem`;
- Linux installer and uninstaller use the same owner check before killing port
  holders;
- tray restart/stop uses process-name cleanup and lets the client perform the
  port-owner safety check;
- non-KyMoRem owners are logged and preserved.

Residual risk: a malicious local user could craft a command line containing the
KyMoRem name. OS process ownership and service isolation remain the stronger
control.

## Cycle 7: SMTP Relay Header and TLS Hardening

Finding: relay configuration could carry unsafe header values and STARTTLS used
implicit defaults.

Fix:

- sanitized subject, sender and recipient fields;
- required SMTP password when username is configured;
- added default TLS context for STARTTLS.

Residual risk: relay security depends on SMTP provider policy.

## Cycle 8: Runtime File Symlink Hardening

Finding: PID/log files used predictable `/tmp` paths.

Fix:

- moved PID/log files into per-user runtime directory;
- created fallback `/tmp/kymorem-$UID` with `0700`;
- wrote PID with `O_NOFOLLOW` where available;
- guarded Linux/macOS/Windows uninstall removal paths before recursive
  deletion;
- escaped PowerShell shortcut paths during Windows setup.

Residual risk: launch logs created by shell wrappers may still be in `/tmp` for
early bootstrap diagnostics.

## Cycle 9: Disconnect Fail-Open To Local Control

Finding: if the secure link dropped during remote mode, the host loop could keep
the cursor anchored until the emergency hotkey was used.

Fix:

- disconnect events now force release from remote mode.

Residual risk: OS-level input hooks are not yet native; polling remains MVP
behavior.

## Cycle 10: Invalid Token Retry Control

Finding: invalid/default token configuration could cause repeated connection
attempts and noisy logs.

Fix:

- Windows host validates token before connecting;
- UI status changes to `TOKEN REQUIRED`;
- discovery does not start with invalid token;
- Linux client exits with code `64` on token/configuration errors so systemd
  can avoid restart loops.

Residual risk: operators must still distribute the same strong token to both
endpoints.

## Verification Targets

- `py_compile` on runtime and packaging Python files: passed.
- In-memory secure handshake with ML-KEM when provider is available: passed,
  selected `ml-kem-768+psk-hkdf-sha256+aes-256-gcm`.
- Replay rejection test: passed, duplicate secure frame rejected.
- Oversized handshake frame test: passed, `MAX_FRAME_BYTES` enforced.
- Default-token refusal test: passed.
- Mouse movement delta clamp test: passed.
- Bandit static scan: attempted, but the installed Bandit release failed under
  Python 3.14 AST compatibility; targeted manual review and executable tests
  were used instead.
- `pip-audit -r packaging/linux/standalone/requirements.txt`: passed, no known
  vulnerabilities found.
- Secret scan before push: passed for private IP, plaintext password pattern,
  local Windows user path, private key markers and common access-token prefixes.
