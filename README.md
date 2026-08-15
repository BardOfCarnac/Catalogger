# Catalogger

Working repository for the **Vend-R** catalogue and shop-generation data model.

Vend-R is intended to generate persistent Cyberpunk RED businesses: a shop has a stable identity, while its inventory and temporary state can change over time. The reference catalogue is deliberately kept as static, version-controlled data; persistent shops can later be hosted in PostgreSQL/Supabase without changing the canonical catalogue format.

## Current dataset

The initial catalogue is derived from **R. Talsorian Games' Night Market Index v1.24 (January 2026)**. It contains 1,275 canonical catalogue entities after resolving duplicated/cross-listed index entries while retaining the source classifications and page references.

This repository stores indexing/reference information rather than reproducing sourcebook descriptive text. Book/DLC references remain attached so users can consult the original material.

## Layout

```text
data/
  catalog/
    items.json                 canonical items
    manufacturers.json         normalized manufacturers
    item-manufacturers.json    item ↔ manufacturer links
    item-classifications.json  source taxonomy + Vend-R department
    sources.json               source-book/DLC legend
    item-sources.json          item ↔ source/page links
    taxonomy.json              Vend-R application taxonomy
  shops/
    archetypes.json            generator-template seeds
  audit/
    index-listings.json        raw source-index listings
    id-redirects.json          retired ID → canonical ID
    resolution-log.json        editorial decisions
schema/
  catalog.sql                  relational catalogue schema
  shops.sql                    persistent shop/stock/state schema
scripts/
  validate_catalog.py          consistency checks
```

## Data model

The core rule is that **generated attributes become stored attributes**. A generated shop records its realized identity; later changes to generator archetypes do not mutate an existing campaign's business. Only explicitly dynamic data such as stock and temporary shop state is refreshed.

Catalogue data is split into factual/source-derived fields and Vend-R application fields. Source classifications are never overwritten by the Vend-R taxonomy.

## Hosting direction

Git is the editorial source of truth for the catalogue. A future live deployment can import these tables into PostgreSQL/Supabase, where `shops`, `stock`, `shop_state`, and `stock_history` provide persistent campaign state.

## Validation

Run:

```bash
python scripts/validate_catalog.py
```

The GitHub Actions workflow runs the same checks on pushes and pull requests.

## Unofficial content notice

Catalogger / Vend-R is unofficial content provided under the Homebrew Content Policy of R. Talsorian Games and is not approved or endorsed by RTG. This content references materials that are the property of R. Talsorian Games and its licensees.
