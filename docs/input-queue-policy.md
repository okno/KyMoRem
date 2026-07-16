# Input Queue Policy

KyMoRem treats pointer movement and mouse wheel input as realtime state, not as
an infinite command log.

## Goals

- A Logitech G502-style infinite scroll must not freeze the host or client.
- Slow TCP clients must not make the Windows hook thread wait on `sendall`.
- Keyboard, button, release and clipboard frames remain reliable.
- Movement and wheel frames prefer the newest useful state.

## Server Pipeline

1. The Windows hook captures raw input.
2. `ControlEngine` coalesces mouse move deltas and wheel deltas.
3. `RemoteLink` has a dedicated sender thread.
4. Realtime move/wheel frames are coalesced again at the network boundary.
5. If the socket is slow, old realtime deltas are capped or replaced instead of
   growing an unbounded queue.

## Reliable Frames

These are queued reliably:

- `enter`
- `release`
- `key`
- `button`
- clipboard and file-transfer frames

If the network queue is full, nonessential keepalive/locate frames are dropped
first to make room.

## Realtime Frames

These are bounded and coalesced:

- `move`
- `wheel`

Wheel backlog is capped both before the network queue and at the network sender
layer. This prevents multi-second scroll drains after an infinite-scroll burst.

## Applying The Fix

Update the server runtime first. Then update clients so their per-frame wheel
clamps are active:

- Windows host: reinstall or replace `%LOCALAPPDATA%\KyMoRem\KyMoRem.exe`.
- Linux client: regenerate with `New-KyMoRemLinuxClientPackage.ps1`, copy to
  the Linux machine and restart `kymorem-client.service`.
- Windows 7 client: regenerate with `New-KyMoRemWin7ClientPackage.ps1`, close
  the old console and run the new `Start-KyMoRem-Win7-Client.cmd`.
- Android client: rebuild/install the APK and start the listener.

After updating, press `AGGIORNA` on the server and use `Ctrl+Esc` to clear any
old active remote state.
