# Project status

## Implemented scope

- One NumPy/Cython close-combat engine shared by all catalogues.
- One schema-versioned knowledge contract for 49 Mordheimer and 34 Trollheim bands.
- Additive multi-category filtering for Core, 1A, 1B, 1C, and Trollheim, all
  enabled by default.
- Explicit canonical-family relationships and source variants.
- Configurable candidates and opponents, equipment comparisons, improvements,
  house rules, MOTTA ranking, cancellation, and Excel export.
- A Combat Lab workbook format containing the catalogue schema, selected categories, locale,
  stable band/profile IDs, enemies, and results.

Movement, terrain, multiple combats, psychology, magic, prayers, campaign rules,
and decisions outside a one-on-one duel remain out of scope.

## Knowledge decisions

- Mordheimer grades and Trollheim collection membership are independent metadata.
- Similar names never cause an automatic overwrite.
- Mechanically different records in one canonical family are labelled Mordheimer
  or Trollheim in the selector.
- Item costs and legality remain scoped to the selected band/profile.
- Missing translations fall back to the source text while bilingual records are
  completed progressively.

## Verification

```powershell
python tools\validate_knowledge_base.py
python tools\validate_runtime_knowledge.py
python -m pytest -q
python tools\benchmark_native_kernel.py -n 500000
```
