# Packaging

KyMoRem is prepared for binary releases, but this repository does not currently
contain prebuilt binaries.

The build host must generate them once per platform:

- Windows builder: ZIP, `.exe`, `.msi`.
- Linux builder: `.deb`, `.tar.gz`, optional `.zip`.
- macOS builder: `.app`, `.pkg`, `.dmg`.
- Android builder: universal APK, split APKs, `.aab`.

## Why Not Build Everything Here?

The current machine does not have Rust, WiX, Inno Setup, Android SDK, Gradle, or
macOS packaging tools installed. macOS packages also need macOS tools such as
`pkgbuild` and `hdiutil`.

## One-Time Tool Install

Windows:

```powershell
winget install Rustlang.Rustup
winget install JRSoftware.InnoSetup
dotnet tool install --global wix
```

Linux:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
sudo apt install -y build-essential dpkg-dev fakeroot zip
```

macOS:

```bash
xcode-select --install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Android:

- JDK 17 or newer.
- Android SDK.
- Gradle or generated Gradle wrapper.

## Build Commands

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\release\build-all.ps1
```

Linux:

```bash
bash packaging/linux/build-linux.sh
```

macOS:

```bash
bash packaging/macos/build-macos.sh
```

Android:

```bash
bash packaging/android/build-android.sh
```

## Languages

Installer/app text currently includes:

- `it-IT`: primary.
- `en-US`: English.
- `ch-CH`: CH product slot. Platform-specific bundles may map this to a
  valid Swiss locale such as `de_CH`.
