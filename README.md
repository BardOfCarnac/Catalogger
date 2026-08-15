# Catalogger

Working repository for the **Vend-R** catalogue and persistent shop-generation data model for Cyberpunk RED.

Vend-R treats a shop as a stable world entity: its identity is generated once and retained, while stock and temporary state can change over time. The reference catalogue is deliberately static and version-controlled; persistent campaign shops can later live in PostgreSQL/Supabase without changing the canonical catalogue format.

## Current dataset

The initial catalogue is derived from **R. Talsorian Games' Night Market Index v1.24 (January 2026)**. The canonicalized dataset currently contains:

- **1,275 canonical catalogue entities**
- **1,313 item classification links**
- **1,709 item/source-page links**
- **482 item/manufacturer links**
- **113 normalized manufacturers**
- **1,316 retained raw index listings** for audit/provenance
- **7 retired IDs** redirected to canonical items

The repository stores indexing/reference information rather than reproducing sourcebook descriptive text. Book/DLC references remain attached so users can consult the original material.

## Repository layout

```text
data/
  catalog/
    manifest.json               versioned shard manifest/checksums
    *.json.gz                   canonical source-data shards
    manufacturers.json          normalized manufacturers
    sources.json                source-book/DLC legend
    taxonomy.json               Vend-R application taxonomy
  curation/
    item-tags.json              hand-maintained commercial/shop tags
    item-overrides.json         deliberate curated overrides
  shops/
    archetypes.json             shop-generator template seeds
  audit/
    *.json.gz                   retained source-index/audit data
    id-redirects.json           retired ID -> canonical ID
schema/
  catalog.sql                   relational catalogue schema
  shops.sql                     persistent shop/stock/state schema
scripts/
  materialize_catalog.py        build ordinary JSON from canonical shards
  validate_catalog.py           checksum + relational consistency checks
```

Large, mostly static factual tables are stored as deterministic, versioned gzip JSON shards. `data/catalog/manifest.json` records every part, row count and SHA-256 checksum. Human-authored Vend-R classifications and future stocking logic remain ordinary readable JSON rather than being hidden inside generated files.

To materialize convenient uncompressed JSON for an app/import:

```bash
python scripts/materialize_catalog.py
```

The generated files appear under `build/data/` and are deliberately ignored by Git.

## Data model

The catalogue keeps **source classification** and **Vend-R classification** separate. RTG categories/subcategories are retained for provenance; Vend-R layers a commercial taxonomy over them for generating plausible sellers and inventory.

The persistent shop model has four primary objects:

1. `items` — static canonical products/reference entries
2. `shops` — persistent business identity
3. `stock` — a particular shop's occurrence of an item, quantity, condition and asking price
4. `shop_state` — mutable restock cycle and temporary conditions

`shop_archetypes` are generator templates only. The core rule is: **generated attributes become stored attributes**. Updating an archetype later must not silently mutate a shop already present in a campaign.

## Hosting direction

Git is the editorial source of truth for catalogue and generator data. A future live deployment can import the catalogue into PostgreSQL/Supabase and add dynamic `shops`, `stock`, `shop_state`, and `stock_history` rows around it.

## Validation

Run:

```bash
python scripts/validate_catalog.py
```

The validator checks shard checksums and row counts, duplicate IDs, source/manufacturer foreign keys, classification coverage, and retired-ID redirects. GitHub Actions runs the same validation on pushes and pull requests.

## Unofficial content notice

Catalogger / Vend-R is unofficial content provided under the Homebrew Content Policy of R. Talsorian Games and is not approved or endorsed by RTG. This content references materials that are the property of R. Talsorian Games and its licensees.
