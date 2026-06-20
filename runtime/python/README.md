# KyMoRem Python Runtime

This runtime is the installable MVP used for the current Windows/Linux setup.

- `kymorem_server.py`: Windows GUI/controller. Default client is configurable
  and placed on the right edge.
- `kymorem_client.py`: Linux listener/receiver. Uses `xdotool` on the active X
  session.
- `kymorem_common.py`: shared protocol helpers and translations.

The Rust workspace remains the long-term core, but this Python runtime gives us
an immediately deployable LAN tool.
