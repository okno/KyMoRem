# Release Process

## Versioning

KyMoRem uses semver-like versions:

```text
MAJOR.MINOR.PATCH
```

v0.x releases may change internal protocol details.

## Build Artifacts

Current release assets:

- Windows x64 standalone executable
- Windows x64 setup executable
- Windows x64 uninstaller
- Windows x64 portable ZIP
- Linux x64 `.deb`
- Linux x64 portable tar/zip
- Linux x64 standalone tar/zip
- SHA256 checksums

## Windows Build

```powershell
python -m PyInstaller --onefile --windowed --name KyMoRem runtime\python\kymorem_server.py
```

The local build script in the project performs the full packaging pass.

## Linux Standalone Build

The standalone package can be assembled from `packaging/linux/standalone` plus
`runtime/python`.

## GitHub Release

```powershell
gh release create v0.1.0 artifacts\* --title "KyMoRem v0.1.0" --notes-file RELEASE_NOTES.md
```

## Preflight

Before publishing:

- run the secure handshake smoke test;
- scan staged files for local paths, private IPs and secrets;
- verify that localization assets are limited to IT, EN and CH;
- regenerate checksums after any artifact rebuild.
