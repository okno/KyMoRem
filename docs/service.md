# Service Design

KyMoRem is a two-role service with explicit host/client behavior.

## Host

The host owns the physical keyboard and pointer.

Responsibilities:

- maintain the desktop UI and tray;
- discover compatible clients;
- monitor configured and discovered clients;
- establish the secure transport;
- detect right-edge entry;
- stream pointer, button, wheel and key frames;
- provide emergency release;
- send optional operational email notifications.

## Client

The client receives events and injects them into the active desktop session.

Responsibilities:

- kill stale KyMoRem processes before launch;
- free the configured TCP and UDP ports;
- advertise role and capabilities through encrypted discovery;
- accept only authenticated secure sessions;
- inhibit idle/sleep where the platform allows it while the listener is active;
- wake the display before remote mouse or keyboard injection;
- dispatch input frames through the platform backend;
- report edge return events and operational errors.

The wake guard is a readiness feature, not an authentication bypass. It does not
unlock protected sessions and it cannot keep a listener alive after hardware
suspend unless firmware or OS Wake-on-LAN policy is configured separately.

## Runtime Flow

```text
client starts
client kills stale instance
client binds 54865/tcp
client starts wake guard / idle inhibitor
client broadcasts encrypted discovery on 54866/udp
host discovers role=client
host opens TCP session
peers negotiate secure transport
host streams encrypted input frames
client injects local input
```

## Linux User Service

The Linux target is a user-level daemon because input injection needs the active
graphical session. A system-wide daemon usually lacks `DISPLAY`, `XAUTHORITY`
and the user DBus session.

## Failure Boundaries

- UI failure should not leave uncontrolled remote input active.
- Client restart must release the old listener and discovery socket.
- Security handshake failure must not downgrade to plaintext.
- Email relay failure must not block input routing.
