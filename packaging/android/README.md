# Android Packaging

Artifacts:

- Universal APK.
- ABI split APKs for:
  - `armeabi-v7a` 32-bit ARM
  - `arm64-v8a` 64-bit ARM
  - `x86` 32-bit Intel emulator/device
  - `x86_64` 64-bit Intel emulator/device
- Android App Bundle `.aab`.

The build script prefers the portable toolchain in `.build-tools-android` when
present, then falls back to system Java/Gradle.

Build on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\android\build-android.ps1
```

Build on Linux/macOS:

```bash
bash packaging/android/build-android.sh
```

Outputs are copied to `artifacts` using the configured version.

Quick debug install:

```powershell
.\.build-tools-android\android-sdk\platform-tools\adb.exe install -r apps\android\app\build\outputs\apk\debug\app-universal-debug.apk
```

The Android client is an app-local KyMoRem surface with the secure PSK/AES-GCM
transport. Full system-wide Android control requires a later Accessibility
service or device-owner mode.
