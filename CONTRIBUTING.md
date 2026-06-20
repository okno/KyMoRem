# Contributing

KyMoRem is early-stage systems software. Contributions should keep two values in
tension: make the tool pleasant to use, and keep input-control security obvious.

## Development Rules

- Keep platform-specific input code behind a narrow abstraction.
- Do not enable clipboard sync by default.
- Do not add unauthenticated input channels.
- Prefer explicit configuration over hidden LAN magic.
- Keep debug commands documented when changing runtime behavior.

## Python MVP

The production MVP currently lives in:

```text
runtime/python/
```

Compile checks:

```powershell
python -m py_compile runtime\python\kymorem_common.py runtime\python\kymorem_client.py runtime\python\kymorem_server.py
```

## Rust Core

The Rust workspace is the long-term protocol and core foundation:

```powershell
cargo test --workspace
```

## Release Artifacts

Do not commit generated artifacts. Build outputs go to `artifacts/` and are
attached to GitHub releases.

## Documentation

Update `DEBUGGING.md` whenever behavior changes in a way that affects operators.
Update `FAQ.md` when a user-facing limitation or workflow changes.
