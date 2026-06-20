# macOS Packaging

Targets:

- `x64`: Intel 64-bit, `x86_64-apple-darwin`
- `arm64`: Apple Silicon, `aarch64-apple-darwin`
- `universal2`: created with `lipo` when both builds exist

macOS 32-bit is intentionally not produced. Current macOS releases do not run
32-bit applications, and modern Rust/macOS distribution is 64-bit.

Artifacts:

- `.app` bundle.
- `.pkg` installer.
- `.dmg` disk image.
- `uninstall.sh` inside the app resources.

Required tools:

```bash
xcode-select --install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Build:

```bash
cd KyMoRem
bash packaging/macos/build-macos.sh
```

Accessibility and Input Monitoring permissions are required before real native
input backends can control other apps.
