# Android Client

KyMoRem Android is a LAN client that listens for the desktop server and renders
an app-local remote surface.

## Supported In This Build

- TCP listener on `54865`.
- KyMoRem secure transport using `psk-hkdf-sha256+aes-256-gcm`.
- Pointer enter/move visualization.
- Wheel aggregation.
- Button/key state display.
- Text clipboard receive/request.
- Edge reporting back to the server.

## Why App-Local First

Android blocks arbitrary global input injection for normal apps. A safe Android
path is:

1. App-local surface to verify pairing, crypto, latency and routing.
2. AccessibilityService for gestures and focused text fields.
3. Device-owner mode for managed devices that need deeper control.

This implementation completes step 1.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File packaging\android\build-android.ps1
```

Useful local outputs:

```text
apps/android/app/build/outputs/apk/debug/app-universal-debug.apk
apps/android/app/build/outputs/apk/release/app-universal-release-unsigned.apk
apps/android/app/build/outputs/bundle/release/app-release.aab
```

## Install

Enable USB debugging on Android, then:

```powershell
.\.build-tools-android\android-sdk\platform-tools\adb.exe install -r apps\android\app\build\outputs\apk\debug\app-universal-debug.apk
```

## Configure The Server

Add a client entry:

```json
{
  "name": "android-client",
  "host": "ANDROID_LAN_IP",
  "port": 54865,
  "position": "right",
  "x": 1,
  "y": 0,
  "enabled": true,
  "approved": true,
  "source": "manual"
}
```

Then start Android listener, save the server config, press `AGGIORNA` and enter
from the configured edge.

## Troubleshooting

- `token fingerprint mismatch`: token differs between server and Android.
- `offline`: Android app is not listening, Android IP changed, or LAN blocks
  TCP `54865`.
- `connected` but no system-wide Android movement: expected for app-local mode.
- Scroll bursts: the Android surface aggregates wheel state and does not queue
  each tick as a separate visual action.
