# Windows Packaging

Targets:

- `x64`: `x86_64-pc-windows-msvc`
- `x86`: `i686-pc-windows-msvc`

Artifacts:

- Portable ZIP.
- Inno Setup `.exe` installer with uninstall support.
- WiX `.msi` installer with uninstall support.

Required tools:

```powershell
winget install Rustlang.Rustup
winget install JRSoftware.InnoSetup
dotnet tool install --global wix
```

Build:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build-windows.ps1
```

Italian is the primary language. English and CH are included as secondary
languages.
