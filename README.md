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
    item-tags.json              hand-maintained semantic affinities
    item-overrides.json         deliberate per-item exceptions
  shops/
    archetypes.json             shop-generator template seeds
  audit/
    *.json.gz                   retained source-index/audit data
    id-redirects.json           retired ID -> canonical ID
schema/
  catalog.sql                   relational catalogue + commercial profile schema
  shops.sql                     persistent shop/stock/state schema
scripts/
  materialize_catalog.py        build ordinary JSON from canonical shards
  build_commercial_profiles.py  derive first-pass Vend-R item profiles
  validate_catalog.py           checksum + relational + taxonomy checks
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

The ten files under `data/curation/defaults/` cover **all 83 source category/subcategory pairs** in the Night Market Index dataset. Six deliberately broad source buckets are marked `requires_item_curation` rather than pretending a source-level default is precise enough: General Gear, Apps and Software, Cyberware Alternatives, Unique Vehicles, Netrunning Accessories, and Entertainment & Services / General.

Build the current first-pass profile for all catalogue items with:

```bash
python scripts/build_commercial_profiles.py
```

The builder takes scalar behaviour from an item's primary source classification, unions useful market/audience affinities from secondary classifications, applies conservative product-identity inference, then applies `item-overrides.json` and `item-tags.json`. Generated profiles appear at `build/data/catalog/item-commercial-profiles.json` and are deliberately not committed.

To materialize convenient uncompressed source JSON for an app/import:

```bash
python scripts/materialize_catalog.py
```

Generated files under `build/data/` are ignored by Git.

## Persistent shop model

The persistent shop model has four primary objects:

1. `items` — static canonical products/reference entries
2. `shops` — persistent business identity
3. `stock` — a particular shop's occurrence of an item, quantity, condition and asking price
4. `shop_state` — mutable restock cycle and temporary conditions

`shop_archetypes` are generator templates only. The core rule is: **generated attributes become stored attributes**. Updating an archetype later must not silently mutate a shop already present in a campaign.

## Hosting direction

Git is the editorial source of truth for catalogue and generator data. A future live deployment can import the catalogue and derived commercial profiles into PostgreSQL/Supabase and add dynamic `shops`, `stock`, `shop_state`, and `stock_history` rows around it.

## Validation

Run:

```bash
python scripts/validate_catalog.py
python scripts/build_commercial_profiles.py
```

The validator checks shard checksums and row counts, duplicate IDs, source/manufacturer foreign keys, retired-ID redirects, exact commercial-default coverage, and every controlled vocabulary value. GitHub Actions runs both validation and profile generation on pushes and pull requests.

## Unofficial content notice

Catalogger / Vend-R is unofficial content provided under the Homebrew Content Policy of R. Talsorian Games and is not approved or endorsed by RTG. This content references materials that are the property of R. Talsorian Games and its licensees.
