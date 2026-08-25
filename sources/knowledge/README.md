# Unified knowledge base

Every runtime band uses `schema/band.schema.json`, regardless of its source.

- `bands/mordheimer/`: 49 source-normalized Mordheimer records.
- `bands/trollheim/`: 34 source-normalized Trollheim records.
- `schema/`: the shared schema version 1 contract.
- `catalog/`: shared combat-rule source material.
- `index/`: source scope and editorial metadata.
- `intake/`: preserved Mordheimer capture inputs; these are not loaded at runtime.

Top-level collection differences are represented by `collections`, `categories`,
`grade`, `setting`, `publication`, and `sources`. Records known to describe the
same conceptual band use the same `canonical_family`. They remain separate when
their normalized gameplay data differs.

All named records contain an `en`/`es` translation shape. A null translation falls
back to the original source text and is visible to the translation audit.
