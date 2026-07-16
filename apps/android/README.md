# KyMoRem Android Client

The Android app is now a real KyMoRem LAN client surface. It listens on
`54865/tcp`, accepts the KyMoRem secure PSK/AES-GCM transport and renders a
remote pointer surface inside the app.

## What Works

- Manual Android client registration on the KyMoRem server.
- Secure PSK/HKDF/AES-256-GCM handshake.
- `health_probe`, `hello`, `keepalive`, `enter`, `move`, `wheel`, `button`,
  `key`, `release`, `locate_pointer` and text clipboard frames.
- App-local pointer visualization with edge return reporting.
- Wheel events are aggregated visually so infinite-scroll bursts do not create
  a UI backlog.
- IT, EN and CH strings.

## Current Android Boundary

This client controls the KyMoRem Android app surface, not the full Android OS.
System-wide Android control requires an AccessibilityService or device-owner
deployment. That is intentionally separate because Android does not allow a
normal app to inject arbitrary global keyboard and pointer events.

## Install

Build locally:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\android\build-android.ps1
```

Install the universal debug APK for quick tests:

```powershell
.\.build-tools-android\android-sdk\platform-tools\adb.exe install -r apps\android\app\build\outputs\apk\debug\app-universal-debug.apk
```

For release packaging, use the unsigned APKs/AAB copied to `artifacts`.

## Use

1. Open KyMoRem on Android.
2. Enter a client name, for example `android-client`.
3. Enter the server token. It must be the same strong token used by the KyMoRem
   server.
4. Keep port `54865`.
5. Tap `Start`.
6. On the server, add a client with the Android device IP, port `54865`, and the
   same name.
7. Save, press `AGGIORNA`, then route to that edge.

The app status changes from listening to secure handshake to connected.

## Troubleshooting

- Token shorter than 24 characters is refused.
- The development token is refused.
- If the server says handshake rejected, regenerate/copy the real server token.
- If the Android card is offline, check that the phone is on the same LAN and
  that no Wi-Fi isolation blocks TCP `54865`.
- If movement enters but global Android apps do not move, that is expected for
  the app-local client. AccessibilityService is the next system-control layer.
