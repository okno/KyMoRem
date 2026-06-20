# Android Packaging

Artifacts:

- Universal release APK.
- ABI split APKs for:
  - `armeabi-v7a` 32-bit ARM
  - `arm64-v8a` 64-bit ARM
  - `x86` 32-bit Intel emulator/device
  - `x86_64` 64-bit Intel emulator/device
- Android App Bundle `.aab`.

Required tools:

- JDK 17 or newer.
- Android SDK.
- Gradle or a generated Gradle wrapper.

Build on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\android\build-android.ps1
```

Build on Linux/macOS:

```bash
bash packaging/android/build-android.sh
```

The current Android app is an installable MVP shell with IT, EN, and CH
localizations. The TCP protocol client is the next milestone.
