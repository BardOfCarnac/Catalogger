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
    taxonomy.json               Vend-R departments + controlled vocabularies
  curation/
    defaults/                   RTG subcategory -> commercial defaults
    overrides/                  item-by-item commercial curation
    product-identity.json       generic/branded/bespoke/unique decisions
    item-tags.json              hand-maintained semantic affinities
    item-overrides.json         deliberate per-item exceptions
  shops/
    archetypes.json             shop-generator template seeds
  stocking/
    model.json                  scoring, breadth/depth, supply and restock controls
    archetype-profiles.json     stocking defaults keyed to shop archetypes
  audit/
    *.json.gz                   retained source-index/audit data
    id-redirects.json           retired ID -> canonical ID
schema/
  catalog.sql                   relational catalogue + commercial profile schema
  shops.sql                     persistent shop/assortment/stock/state schema
scripts/
  materialize_catalog.py        build ordinary JSON from canonical shards
  build_commercial_profiles.py  derive Vend-R item profiles
  review_product_identity.py    audit product-identity decisions
  stock_engine.py               persistent assortment + stocking/restock engine
  validate_catalog.py           checksum + relational + taxonomy checks
  validate_stocking.py          stocking configuration checks
  test_stock_engine.py          deterministic stocking smoke tests
```

Large, mostly static factual tables are stored as deterministic, versioned gzip JSON shards. `data/catalog/manifest.json` records every part, row count and SHA-256 checksum. Human-authored Vend-R classifications and stocking logic remain ordinary readable JSON rather than being hidden inside generated files.

## Commercial profile layer

The catalogue keeps **source classification** and **Vend-R classification** separate. RTG categories/subcategories are retained for provenance; Vend-R layers a commercial model over them for generating plausible sellers and inventory.

`data/catalog/taxonomy.json` defines controlled values for:

- product identity: generic, branded, bespoke, unique
- commodity kind: durable good, consumable, installed good, component, vehicle, software, service, subscription, property, virtual good
- quantity profile: singular, low stock, normal stock, high stock, bulk, continuous
- allowed/default condition
- supply profile
- market channels
- typed audience, use, and character affinities

The ten files under `data/curation/defaults/` cover **all 83 source category/subcategory pairs** in the Night Market Index dataset. Six deliberately broad source buckets are marked as requiring item-level curation at the source-default layer; the item override files resolve those mixed cases individually before the final profiles are built.

Build the current commercial profile for all catalogue items with:

```bash
python scripts/build_commercial_profiles.py
```

Generated profiles appear at `build/data/catalog/item-commercial-profiles.json` and are deliberately not committed.

To materialize convenient uncompressed source JSON for an app/import:

```bash
python scripts/materialize_catalog.py
```

Generated files under `build/data/` are ignored by Git.

## Persistent stocking model

The stocking engine deliberately separates five concerns:

1. **Eligibility** — whether the shop can plausibly deal in the item at all.
2. **Affinity scoring** — a ranking signal from department/classification fit, market channels, semantic affinities, manufacturer relationships, price band, product identity and supply capability. Scores are not universal rarity percentages.
3. **Persistent assortment** — the shop's stable `core`, `regular`, and `occasional` relationships with products.
4. **Cycle stock** — quantity, condition, asking price and visibility for the current stock cycle.
5. **Specials** — temporary plausible surprises which do not become permanent assortment lines automatically. Unique items are restricted to this layer.

A shop can therefore sell out of a core line without forgetting that it normally carries that product. Restocking works from the saved assortment instead of rerolling the catalogue from scratch.

`data/stocking/model.json` holds the shared controls, including five breadth profiles, four independent stock-depth profiles, supply-capability matrices, role-presence rates, assortment-saturation pressure, quantity ranges and condition/price behaviour. `data/stocking/archetype-profiles.json` provides stocking defaults for all fourteen current shop archetypes without turning those templates into saved shops.

The helper in `stock_engine.py` can create a realized stocking context for testing, but it is deliberately **not** a shop identity/location generator. A real shop service should generate a shop elsewhere, persist its realized stocking context, then hand that context to this engine.

Generate a deterministic assortment plus cycle-0 stock:

```bash
python scripts/build_commercial_profiles.py
python scripts/stock_engine.py generate \
  --archetype weapons-dealer \
  --seed rico-001 \
  --output build/rico-stock.json
```

Advance the saved shop by one stock cycle without rebuilding its assortment:

```bash
python scripts/stock_engine.py restock \
  --input build/rico-stock.json \
  --output build/rico-stock-cycle-1.json
```

Inspect why items score highly for a shop:

```bash
python scripts/stock_engine.py score \
  --archetype weapons-dealer \
  --seed preview \
  --limit 25
```

A realized shop context can add classification specialities, manufacturer affinities/refusals, changed breadth/depth, channel preferences, condition bias and other stocking values without modifying the catalogue.

## Persistent shop model

The persistent shop model now has five primary objects:

1. `items` — static canonical products/reference entries
2. `shops` — persistent business identity plus its realized stocking profile
3. `shop_assortment` — persistent core/regular/occasional product relationships
4. `stock` — cycle-specific quantity, condition, asking price and visibility; `special` stock can exist outside the assortment
5. `shop_state` / `stock_history` — mutable restock cycle, temporary conditions and stock events

`shop_archetypes` are generator templates only. The core rule is: **generated attributes become stored attributes**. Updating an archetype later must not silently mutate a shop already present in a campaign.

## Hosting direction

Git is the editorial source of truth for catalogue and generator data. A future live deployment can import the catalogue and derived commercial profiles into PostgreSQL/Supabase and add dynamic `shops`, `shop_assortment`, `stock`, `shop_state`, and `stock_history` rows around it.

## Validation

Run:

```bash
python scripts/validate_catalog.py
python scripts/build_commercial_profiles.py
python scripts/review_product_identity.py
python scripts/validate_stocking.py
python scripts/test_stock_engine.py
```

The validator checks shard checksums and row counts, duplicate IDs, source/manufacturer foreign keys, retired-ID redirects, exact commercial-default coverage, every controlled vocabulary value, stocking-profile coverage and stocking configuration references. The stocking smoke tests generate all fourteen archetypes, verify deterministic generation, enforce unique-items-as-specials, exercise speciality weighting, and confirm restocking preserves assortment identity. GitHub Actions runs the full sequence on pushes and pull requests.

## Unofficial content notice

Catalogger / Vend-R is unofficial content provided under the Homebrew Content Policy of R. Talsorian Games and is not approved or endorsed by RTG. This content references materials that are the property of R. Talsorian Games and its licensees.
