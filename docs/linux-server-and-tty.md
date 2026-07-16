# Linux Server And TTY Client

KyMoRem now has two Linux-side additions:

- `runtime/python/kymorem_linux_server.py`: Tk route-console server for Linux.
- `runtime/python/kymorem_tty_client.py`: text-mode client for a pure terminal
  or Linux virtual console without X11.

## Linux Server UI

The Linux server uses the same KMR route-console idea as the Windows UI:

- client selector;
- route map;
- `SERVER ON/OFF`;
- `CONNETTI CLIENT`;
- `PRENDI CONTROLLO`;
- `RILASCIA`;
- `AGGIORNA`;
- `CONTROL CENTER`.

Run:

```bash
cd KyMoRem
export KYMOREM_TOKEN="your-long-shared-token"
python3 runtime/python/kymorem_linux_server.py
```

Requirements:

```bash
sudo apt install python3-tk xdotool
```

Current Linux server input backend:

- pointer edge detection uses `xdotool getmouselocation`;
- remote pointer movement is sent by polling deltas;
- global keyboard capture is not implemented yet on Linux server;
- the future production backend should use evdev/uinput with explicit
  permissions.

## TTY Client Without X11

Run from a Linux console/TTY:

```bash
export KYMOREM_TOKEN="your-long-shared-token"
python3 runtime/python/kymorem_tty_client.py --bind 0.0.0.0 --port 54865 --name linux-tty
```

Or from the generated Linux package:

```bash
./Run-KyMoRem-TTY-Client.sh
```

What it does:

- accepts the normal KyMoRem secure transport;
- draws a text-mode cursor as `@`;
- moves that cursor with remote mouse frames;
- displays key/button/wheel state;
- receives text clipboard and emits OSC52 clipboard sequences when supported;
- reports terminal edges back to the server.

What it does not do yet:

- inject arbitrary keyboard into the active Linux virtual console;
- move a kernel/system mouse pointer in TTY.

Those require a privileged `uinput` backend. The TTY client is intentionally
safe by default and app-local, just like the Android client surface.

## Server Configuration Example

```json
{
  "name": "linux-tty",
  "host": "10.0.0.80",
  "port": 54865,
  "position": "down",
  "x": 0,
  "y": 1,
  "enabled": true,
  "approved": true,
  "source": "manual"
}
```

Save, press `AGGIORNA`, then enter from the configured edge.
