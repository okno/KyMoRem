# Localization

KyMoRem v0.2.0-rc1 ships exactly three product localization slots.

| Slot | Purpose |
| --- | --- |
| `it` | Italian, primary |
| `en` | English |
| `ch` | Swiss slot |

No additional language slot is part of the public package.

## Repository Mapping

- Runtime UI: `it`, `en`, `ch`.
- Product metadata: `it-IT`, `en-US`, `ch-CH`.
- macOS platform resources: `it.lproj`, `en.lproj`, `de_CH.lproj`.
- Android platform resources: default English, `values-it`, `values-de-rCH`.

The platform mappings exist only because operating systems require locale
identifiers. Product documentation and UI selection remain IT, EN and CH.
