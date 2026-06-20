# Barrier Research Notes

Barrier provides useful product lessons and field-failure lessons:

- Server owns the real keyboard and mouse.
- Clients are arranged in a screen grid.
- Moving across an edge switches the target screen.
- Clipboard sync is useful but sensitive.
- Users need auto discovery but also manual IP fallback.
- Platform code is the hard part.
- Hidden "starting" states are operationally expensive.
- Certificate bootstrap and fingerprint UI can become support traps.
- Wayland must be detected honestly, not treated as partial success.
- Clipboard sync must be bounded and opt-in.

KyMoRem keeps those lessons and changes the implementation shape:

- Protocol-first instead of GUI-first.
- Rust crates and small binaries.
- Android target from day one.
- Pairing and security documented as core features.
- Native input backends isolated behind a trait.
- Secure runtime key negotiation instead of static certificate file setup.
- Token-protected UDP discovery with manual IP fallback.
- Startup preflight that fails loudly when the platform cannot inject input.

See [Barrier Field Issue Review](barrier-field-issues.md) for the public issue
matrix that drove these decisions.

No Barrier source code has been copied into KyMoRem.
