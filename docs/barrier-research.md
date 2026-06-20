# Barrier Research Notes

Barrier provides useful product lessons:

- Server owns the real keyboard and mouse.
- Clients are arranged in a screen grid.
- Moving across an edge switches the target screen.
- Clipboard sync is useful but sensitive.
- Users need auto discovery but also manual IP fallback.
- Platform code is the hard part.

KyMoRem keeps those lessons and changes the implementation shape:

- Protocol-first instead of GUI-first.
- Rust crates and small binaries.
- Android target from day one.
- Pairing and security documented as core features.
- Native input backends isolated behind a trait.

No Barrier source code has been copied into KyMoRem.
