# Themes

KyMoRem intentionally avoids a generic utility look. The UI should feel like a
focused control console: readable, low-friction, and visually distinct.

## Default: Cyber Noir

Cyber Noir is the default theme. It keeps the neon identity but tones down the
punk edge:

- black-blue base
- cyan route lines
- magenta status accents
- acid green online state
- monospace HUD labels
- no decorative clutter around controls

## Additional Theme Tokens

Theme definitions live in:

```text
assets/themes/
```

Current themes:

- `cyber-noir`
- `stellar-dark`
- `terminal-green`
- `synthwave-night`

The Python MVP has the Cyber Noir palette compiled into the UI code. The token
files document the intended design system for the next GUI pass.
