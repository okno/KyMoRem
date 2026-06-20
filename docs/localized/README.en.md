# KyMoRem Quick Start

KyMoRem shares keyboard and pointer input on a LAN through a Windows host and a
Linux X11 client.

## Windows Host

1. Install `KyMoRem-0.1.1-windows-x64-setup.exe`.
2. Open `%APPDATA%\KyMoRem\config.json`.
3. Replace `token` with a long shared value.
4. Start KyMoRem. Discovery can automatically select the first client.

## Linux Client

```bash
tar -xzf KyMoRem-0.1.1-linux-x64-standalone.tar.gz
cd KyMoRem-linux-x64-standalone
export KYMOREM_TOKEN="long-shared-token"
./run-client.sh
```

## Test

```bash
export KYMOREM_TOKEN="long-shared-token"
./run-test.sh 127.0.0.1 54865
```

## Usage

When the client is connected, move the pointer through the right edge of the
host screen. To leave remote mode, use the client's left edge or `Ctrl+Esc` on
the host.

## Ports

```text
54865/tcp  encrypted session
54866/udp  encrypted LAN discovery
```

## Uninstall

Windows:

```text
artifacts\KyMoRem-0.1.1-windows-x64-uninstall.exe
```

Linux:

```bash
sudo /opt/kymorem/uninstall_linux_client.sh
```
