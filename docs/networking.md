# Networking

KyMoRem uses one TCP channel for input and one UDP channel for discovery.

## Default Flow

```text
host -> LAN broadcast:54866/udp   encrypted discovery listener
host -> client:54865/tcp          secure input session
```

The host initiates TCP connections, so Windows does not need to expose an
inbound control port. The Linux client listens on `54865/tcp` and advertises its
role on `54866/udp`.

## Firewall

Linux client:

```bash
sudo ufw allow from <trusted-subnet> to any port 54865 proto tcp
sudo ufw allow from <trusted-subnet> to any port 54866 proto udp
```

Windows host usually needs outbound TCP/UDP only. If local policy blocks UDP
broadcast, disable discovery and set `clients[0].host` manually.

## Diagnostics

Windows:

```powershell
Test-NetConnection -ComputerName <client-ip> -Port 54865
Get-NetTCPConnection -RemotePort 54865
Get-NetUDPEndpoint -LocalPort 54866 -ErrorAction SilentlyContinue
```

Linux:

```bash
ss -ltnp | grep 54865
ss -lunp | grep 54866
ss -tnp | grep 54865
```

## Reconnect Behavior

The Windows host tries to connect at startup and retries every few seconds if no
client is connected. Discovery can overwrite the first default client only when
that client still points to the loopback placeholder.

## Locked-Down Networks

For VLANs, routed subnets or enterprise Wi-Fi where broadcast is blocked:

1. Keep `discovery.enabled` set to `false`.
2. Set `clients[0].host` to the client address or DNS name.
3. Keep the same shared `token` on both endpoints.
