# UI rework

This package is the active Tkinter interface for Mordheim Combat Lab. It does
not import or depend on `legacy_ui`.

## Current layout

The active shell preserves the legacy workbook navigation: **Candidate**,
**Enemy**, **Improvements**, **Weapons**, **Equipment**, and **House Rules**.
Those pages are backed directly by the typed KB/runtime contracts below; the
archived UI is not imported at runtime.  The House Rules page documents the
runtime scope instead of presenting retired-engine toggles as working options.

| Area | Destination | Current role |
| --- | --- | --- |
| Theme | `theme.py` | Extracted legacy visual language, applied by the new app. |
| UI copy and preferences | `localization.py`, `preferences.py` | Shared UI infrastructure. |
| Reusable controls | `widgets/` | Extracted controls, starting with contextual help. |
| Shared fighter editor | `editors.py` | One component for candidate and enemy configuration. |
| KB presentation queries | `services/catalogue.py` | Collections, warbands, profiles, and legal weapons. |
| Application shell | `app.py` | Compiles `FighterBuild` values and runs `core` simulations. |
| Workbook persistence | `workbooks.py` | Versioned `.xlsx` files with stable KB IDs and typed execution settings. |

## Next extraction steps

1. Add executable KB-backed equivalents for any legacy analysis that cannot
   yet be represented by the new runtime contract.
2. Keep workbook navigation and visual language stable while those views grow.

## Workbook contract

`workbooks.py` owns the active workbook format. It stores candidate and enemy
`FighterBuild` payloads, `DuelExecutionSettings`, and the optional last
`DuelResult` in a hidden JSON data sheet. The visible sheets are English
summaries only; loading always uses stable IDs rather than display labels.
