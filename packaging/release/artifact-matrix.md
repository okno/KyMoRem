# Release Artifact Matrix

This matrix documents the packaging targets and naming policy. The v0.1.1
assets published from the current build host are the Windows x64 and Linux x64
files listed in `RELEASE_NOTES.md`. x86, macOS and Android targets require their
native/cross toolchains and are kept as build recipes until produced on those
platforms.

## Windows

| Artifact | Arch | Notes |
| --- | --- | --- |
| `KyMoRem-0.1.1-windows-x64-portable.zip` | 64-bit | No installer; includes portable uninstall script |
| `KyMoRem-0.1.1-windows-x86-portable.zip` | 32-bit | No installer; includes portable uninstall script |
| `KyMoRem-0.1.1-windows-x64-setup.exe` | 64-bit | Inno Setup installer/uninstaller |
| `KyMoRem-0.1.1-windows-x86-setup.exe` | 32-bit | Inno Setup installer/uninstaller |
| `KyMoRem-0.1.1-windows-x64.msi` | 64-bit | WiX MSI installer/uninstaller |
| `KyMoRem-0.1.1-windows-x86.msi` | 32-bit | WiX MSI installer/uninstaller |

## Linux

| Artifact | Arch | Notes |
| --- | --- | --- |
| `KyMoRem-0.1.1-linux-x64.deb` | amd64 | Debian installer; uninstall with `apt remove kymorem` |
| `KyMoRem-0.1.1-linux-x86.deb` | i386 | Debian installer; uninstall with `apt remove kymorem` |
| `KyMoRem-0.1.1-linux-x64-portable.tar.gz` | 64-bit | Portable |
| `KyMoRem-0.1.1-linux-x86-portable.tar.gz` | 32-bit | Portable |
| `KyMoRem-0.1.1-linux-x64-portable.zip` | 64-bit | Portable when `zip` is installed |
| `KyMoRem-0.1.1-linux-x86-portable.zip` | 32-bit | Portable when `zip` is installed |

## macOS

| Artifact | Arch | Notes |
| --- | --- | --- |
| `KyMoRem-0.1.1-macos-x64.pkg` | Intel 64-bit | Installer |
| `KyMoRem-0.1.1-macos-arm64.pkg` | Apple Silicon 64-bit | Installer |
| `KyMoRem-0.1.1-macos-universal2.pkg` | Intel + Apple Silicon | Universal installer |
| `KyMoRem-0.1.1-macos-x64.dmg` | Intel 64-bit | Disk image |
| `KyMoRem-0.1.1-macos-arm64.dmg` | Apple Silicon 64-bit | Disk image |
| `KyMoRem-0.1.1-macos-universal2.dmg` | Intel + Apple Silicon | Universal disk image |

macOS 32-bit is not produced because supported macOS versions do not run 32-bit
applications.

## Android

| Artifact | Arch | Notes |
| --- | --- | --- |
| `KyMoRem-0.1.1-android-app-universal-release.apk` | Universal | Includes all configured ABIs |
| `KyMoRem-0.1.1-android-app-armeabi-v7a-release.apk` | ARM 32-bit | Split APK |
| `KyMoRem-0.1.1-android-app-arm64-v8a-release.apk` | ARM 64-bit | Split APK |
| `KyMoRem-0.1.1-android-app-x86-release.apk` | x86 32-bit | Split APK |
| `KyMoRem-0.1.1-android-app-x86_64-release.apk` | x86 64-bit | Split APK |
| `KyMoRem-0.1.1-android-release.aab` | Store bundle | Android App Bundle |
