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
- **16 canonical RED-era food/drink commercial identities** (corporations, product lines, retail chains, and food brands)
- **6 canonical branded food/drink products** and **30 named official variants**
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
    brands.json                 canonical RED-era food/drink brand registry
    brand-products.json         branded products, named variants + stock display policy
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
    model.json                  scoring, breadth/depth, lifecycle and restock controls
    archetype-profiles.json     stocking defaults keyed to shop archetypes
  worlds/
    night-city-2045/            source-defined world/location fixtures
  audit/
    *.json.gz                   retained source-index/audit data
    id-redirects.json           retired ID -> canonical ID
docs/
  stocking-lifecycle.md         saved-bundle contract, events and conditions
schema/
  catalog.sql                   relational catalogue + commercial profile schema
  shops.sql                     persistent shop/assortment/stock/state schema
scripts/
  materialize_catalog.py        build ordinary JSON from canonical shards
  build_commercial_profiles.py  derive Vend-R item profiles
  review_product_identity.py    audit product-identity decisions
  stock_engine.py               eligibility/scoring/assortment mechanics
  world_stock_engine.py         hard source constraints for canonical sellers
  stock_lifecycle.py            durable bundles, backorders, events and inspection
  build_kaito_market.py         first end-to-end Night City 2045 world pilot
  build_city_stock.py           realize all canonical Night City catalogue sellers
  city_stock_state.py           once-daily city advance, purchase and order mutations
  validate_catalog.py           checksum + relational + taxonomy checks
  validate_stocking.py          stocking configuration checks
  test_stock_engine.py          deterministic stocking smoke tests
  test_stock_lifecycle.py       persistence/source/event/report smoke tests
  test_kaito_market.py          source-defined market integration test
```

Large, mostly static factual tables are stored as deterministic, versioned gzip JSON shards. `data/catalog/manifest.json` records every part, row count and SHA-256 checksum. Human-authored Vend-R classifications and stocking logic remain ordinary readable JSON rather than being hidden inside generated files.

## Commercial profile layer

The catalogue keeps **source classification** and **Vend-R classification** separate. Food/drink commercial identities are also kept distinct from manufacturers: `brands.json` can represent product lines, retailers, restaurant chains, importers, and producer brands without pretending they are all manufacturers. RTG categories/subcategories are retained for provenance; Vend-R layers a commercial model over them for generating plausible sellers and inventory.

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

The stocking system deliberately separates five concerns:

1. **Eligibility** — whether the shop can plausibly deal in the item at all.
2. **Affinity scoring** — a ranking signal from department/classification fit, market channels, semantic affinities, manufacturer relationships, price band, product identity and supply capability. Scores are not universal rarity percentages.
3. **Persistent assortment** — the shop's stable `core`, `regular`, and `occasional` relationships with products.
4. **Cycle stock** — quantity, condition, asking price and visibility for the current stock cycle.
5. **Specials** — temporary plausible surprises which do not become permanent assortment lines automatically. Unique items are restricted to this layer.

A shop can therefore sell out of a core line without forgetting that it normally carries that product. Restocking works from the saved assortment instead of rerolling the catalogue from scratch.

`data/stocking/model.json` holds the shared controls, including five breadth profiles, four independent stock-depth profiles, supply-capability matrices, role-presence rates, assortment-saturation pressure, quantity ranges, target/reorder behaviour, delivery delays and temporary-condition effects. `data/stocking/archetype-profiles.json` provides stocking defaults for all fourteen current shop archetypes without turning those templates into saved shops.

The helper in `stock_engine.py` can create a realized stocking context for testing, but it is deliberately **not** a shop identity/location generator. A real shop service should generate a shop elsewhere, persist its realized stocking context, then hand that context to the stocking layer.

## Stock lifecycle and persistence

`stock_lifecycle.py` wraps the scoring/assortment mechanics in a versioned saved-shop bundle. In addition to current stock it persists:

- each assortment line's score breakdown, target quantity and reorder point
- enabled source/book codes used when the shop was created
- pending `incoming` orders with deterministic arrival cycles
- temporary supply conditions
- append-only stock events
- pointers to the events produced by the most recent cycle

The current controlled temporary conditions are `shortage`, `surplus`, `disrupted_supply`, `fresh_delivery`, `liquidation`, and `hot_merchandise`. They may apply globally or target particular departments, supply profiles, market channels, manufacturers or item IDs. They bend current supply behaviour without rewriting the permanent assortment.

The lifecycle event stream records meaningful transitions such as `supplier_failed`, `backorder_placed`, `delivery_received`, `replenished`, `restocked`, `special_arrival` and `special_departed`. This gives later services an explainable world-state history instead of silent rerolls.

### Named consumer variants

Vend-R keeps mechanically identical consumer variants beneath the canonical catalogue item instead of duplicating rules entries. `data/catalog/brand-products.json` currently binds the published Kibble and Triti-Fizz variant lists to `Kibble Pack` and `Triti-Fizz`. A stock row can therefore expose several named flavors/formulas/formats while price, rules identity, quantity and assortment remain attached to the base item.

The number of variants shown scales with shop stock depth. Variant source provenance is filtered independently: for example, a CP:R-only dataset can still contain the base Kibble Pack while omitting variants sourced from `Collecting the Random`. This keeps the source-selection UI meaningful all the way down to flavor level.

Generate a deterministic persistent bundle, optionally restricted to books/sources the user has enabled:

```bash
python scripts/build_commercial_profiles.py
python scripts/stock_lifecycle.py generate \
  --archetype weapons-dealer \
  --seed rico-001 \
  --sources CP:R,BC \
  --output build/rico-stock.json
```

Advance that saved shop one stock cycle without rebuilding its assortment:

```bash
python scripts/stock_lifecycle.py restock \
  --input build/rico-stock.json \
  --output build/rico-stock-cycle-1.json
```

A restock can also activate a simple global temporary condition for that cycle/state:

```bash
python scripts/stock_lifecycle.py restock \
  --input build/rico-stock.json \
  --add-condition shortage \
  --output build/rico-shortage.json
```

More precise targeted conditions can be stored directly in the bundle state as documented in `docs/stocking-lifecycle.md`.

## Developer inspection (not the Vend-R UI)

Until the dedicated shop/location work has a real inventory surface, the lifecycle engine can render a deliberately plain Markdown report. This is only a debugging/taste-testing tool; it does not make any decisions about what the eventual Vend-R shop page should look like.

```bash
python scripts/stock_lifecycle.py inspect \
  --input build/rico-stock.json \
  --output build/rico-stock.md
```

The report shows core/regular/occasional lines, target and reorder quantities, current/incoming/sold state, score-component explanations, current specials and the latest cycle events.

You can still inspect raw candidate affinity scores independently of persistence:

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
3. `shop_assortment` — persistent core/regular/occasional product relationships, including target/reorder behaviour and scoring provenance
4. `stock` — cycle-specific quantity, condition, asking price, visibility and pending-order metadata; `special` stock can exist outside the assortment
5. `shop_state` / `stock_history` — mutable restock cycle, temporary conditions and stock events

`shop_archetypes` are generator templates only. The core rule is: **generated attributes become stored attributes**. Updating an archetype later must not silently mutate a shop already present in a campaign.

## Source-defined world fixtures

A canonical location is not the same thing as a generated shop template. `data/worlds/` stores factual location/business structure separately from the catalogue and from runtime stock. The first pilot, `data/worlds/night-city-2045/kaito-market.v1.json`, models Night City 2045 p. 60 as one market container with ten named child vendors.

The world layer makes several distinctions that the generic shop generator should not erase:

- **containers** such as markets own no duplicate inventory; stock belongs to their child sellers
- **catalogue stock** uses persistent VENDR item IDs and the ordinary stocking engine
- **local wares** represent source-defined everyday goods which have no suitable canonical Night Market Index item; they must not be replaced with an unrelated rules item simply to obtain an ID
- **services** can exist without stock at all
- hybrid vendors can combine catalogue stock, local wares and services

`world_stock_engine.py` adds persisted hard constraints for cases where source material is narrower than a generic archetype. These include exact item allowlists, classification-prefix restrictions, explicit inclusion exceptions, base-price bounds and pinned assortment lines. The constraints are properties of the realized seller, not changes to the global item catalogue or universal rarity rules.

Build the current Kaito Market pilot after generating commercial profiles:

```bash
python scripts/build_commercial_profiles.py
python scripts/build_kaito_market.py
python scripts/build_city_stock.py
python scripts/test_city_stock.py
python scripts/test_city_stock_state.py
python scripts/audit_city_stock_pulse.py
```

The generated pilot state is written under `build/data/worlds/` and is deterministic from the saved source fixture and seeds. A deployed world would import that initial state and then persist subsequent stock changes rather than regenerating the market on every visit.

## Shared Night City stock state

The current Night City implementation does not generate extra shops. `build_city_stock.py` realizes the source-reviewed canonical sellers that already declare catalogue stocking, then builds a reverse item-to-seller availability index. The current canonical network contains 56 catalogue-stock sellers and can expose 1,227 catalogue items through shelf stock, current specials or sourceable `ORDER` results without inventing additional businesses.

`city_stock_state.py` is the mutable shared-world layer. One `stock_day` produces one **city pulse**, not 56 independent shop simulations. The pulse first formulates a small deterministic daily budget (currently 40–70 mutations), then distributes sale, busy-sale, sellout, one-unit top-up, sold-line restore, special-arrival and special-departure changes across suitable existing stock. This is intentionally a surface simulation: it makes Night City look busy from a distance without modelling NPC customers or a real economy. Persistent assortment is never rerolled.

Shops are treated as available when queried; Vend-R does not enforce opening hours or simulate hourly logistics. An optional calendar date can trigger one pulse, while manual day advancement remains available for development/tabletop control. Missed real dates are not replayed.

Purchases reduce saved quantities immediately. `ORDER` before purchase means a seller is plausible enough to attempt sourcing the item. Placing the order makes **one sourcing roll**. A failed attempt is marked `source_failed_today` and cannot be spammed again until the next stock day. If the sourcing attempt succeeds, the order is confirmed and its later delivery is reliable; it does not roll supply again while in transit. Ordered stock never joins the seller's permanent assortment. Every mutation rebuilds the availability index.

`audit_city_stock_pulse.py` runs a short multi-day diagnostic so pulse weights can be tuned by observed surface stability rather than economic assumptions.

## Hosting direction

Git is the editorial source of truth for catalogue, generator and source-defined world seed data. A future live deployment can import the catalogue and derived commercial profiles into PostgreSQL/Supabase and add dynamic `shops`, `shop_assortment`, `stock`, `shop_state`, and `stock_history` rows around it.

## Validation

Run:

```bash
python scripts/validate_catalog.py
python scripts/build_commercial_profiles.py
python scripts/review_product_identity.py
python scripts/validate_stocking.py
python scripts/test_stock_engine.py
python scripts/test_stock_lifecycle.py
python scripts/test_kaito_market.py
python scripts/build_kaito_market.py
python scripts/build_city_stock.py
python scripts/test_city_stock.py
python scripts/test_city_stock_state.py
python scripts/audit_city_stock_pulse.py
```

The validator checks shard checksums and row counts, duplicate IDs, source/manufacturer foreign keys, retired-ID redirects, exact commercial-default coverage, every controlled vocabulary value, stocking-profile coverage and lifecycle configuration references. The stocking tests generate all fourteen archetypes, verify deterministic generation, enforce unique-items-as-specials, exercise speciality weighting, confirm restocking preserves assortment identity, test source filtering, pending deliveries, lifecycle events and the no-UI inspection report. The Kaito integration test additionally checks location-to-vendor containment, source-defined seller restrictions, local-offering/service separation and deterministic world realization. GitHub Actions runs the full sequence on pushes and pull requests.

## Unofficial content notice

Catalogger / Vend-R is unofficial content provided under the Homebrew Content Policy of R. Talsorian Games and is not approved or endorsed by RTG. This content references materials that are the property of R. Talsorian Games and its licensees.
