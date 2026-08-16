# Vend-R stocking lifecycle contract

The catalogue describes products. A saved shop must describe its own relationship with those products and survive repeated stock cycles without being regenerated from scratch.

`stock_lifecycle.py` therefore persists one self-contained bundle with five sections:

```json
{
  "format_version": "0.2.0",
  "engine_version": "0.2.0",
  "shop": {},
  "assortment": [],
  "stock": [],
  "state": {},
  "history": []
}
```

## `shop`

This is the realized stocking context handed to the engine by the eventual shop service. Generator-template values are copied here so later archetype edits do not mutate existing shops.

Important stocking fields include departments, supply capability, channel weights, product-identity bias, semantic affinities, price-band centre, condition bias, manufacturer affinities/refusals, classification specialities, breadth/depth and the shop seed.

`enabled_source_codes` is also stored here. `null` means the complete enabled catalogue. A list such as `["CP:R", "BC"]` means only items with at least one reference in those sources can enter that shop's assortment or special-stock pool. Source filtering happens before assortment selection and is therefore part of the saved shop contract rather than a display filter.

## `assortment`

One row per persistent product relationship:

- `role`: `core`, `regular` or `occasional`
- `affinity_score`: the score at the time the assortment was created
- `score_components`: explainable component breakdown
- `target_quantity`: the amount this shop normally aims to hold (`null` for continuously available offerings)
- `reorder_point`: the finite-quantity level at which replenishment becomes urgent
- `introduced_cycle`
- `last_stocked_cycle`
- `active`

Selling the final unit does not delete the assortment row. Unique products are never written into persistent assortment; they can only enter as cycle-specific specials.

## `stock`

Current physical/service availability. A row records item, quantity, condition, asking price, visibility, status and assortment role.

Statuses are:

- `in_stock`
- `reserved`
- `sold`
- `incoming`

`incoming` rows use `metadata.ordered_cycle` and `metadata.arrival_cycle`, allowing a failed replenishment to become a visible pending order rather than a silent reroll.

A `null` quantity means finite count does not meaningfully apply, as with a continuously available service or comparable offering.

## `state`

Mutable shop-cycle information:

- `stock_cycle`
- `temporary_conditions`
- `last_cycle_events`
- persisted source-filter snapshot

Temporary conditions use a controlled vocabulary from `data/stocking/model.json`:

- `shortage`
- `surplus`
- `disrupted_supply`
- `fresh_delivery`
- `liquidation`
- `hot_merchandise`

A condition can be global or targeted. A targeted entry may restrict itself by department, supply profile, market channel, manufacturer or explicit item ID, for example:

```json
{
  "type": "shortage",
  "target": {
    "departments": ["ammunition-ordnance"]
  }
}
```

Conditions bend presence, replenishment, quantity, price, specials and (where relevant) visibility without changing the shop's underlying assortment identity.

## `history`

Append-only explainable stock events. Current event types include:

- `assortment_created`
- `initial_stock`
- `supplier_failed`
- `backorder_placed`
- `delivery_received`
- `replenished`
- `restocked`
- `special_arrival`
- `special_departed`
- `condition_active`

The engine does not need to expose every event to players. They exist so later services can explain state changes, build timelines, surface selected delivery information, or debug unexpected inventories without reconstructing hidden random rolls.

## Restock semantics

A restock advances the saved bundle by one cycle and never rebuilds the persistent assortment.

1. Pending orders whose arrival cycle has been reached become current stock.
2. Existing unsold stock remains.
3. Low core/regular/occasional quantities may be topped up toward their saved targets.
4. Sold-out/absent assortment lines attempt replenishment using their role, supply profile and active temporary conditions.
5. Failed important lines may create an `incoming` backorder with a supply-dependent delay.
6. Existing unsold specials persist; depleted specials leave the active stock list.
7. New cycle specials are selected separately from permanent assortment.
8. Every meaningful change is appended to `history`.

## Developer inspection

The lifecycle CLI can render a deliberately plain Markdown report. It is not intended to define the Vend-R shop UI; it exists only to let us judge inventories while that interface is being developed elsewhere.

```bash
python scripts/build_commercial_profiles.py
python scripts/stock_lifecycle.py generate \
  --archetype weapons-dealer \
  --seed rico-001 \
  --sources CP:R,BC \
  --output build/rico-stock.json

python scripts/stock_lifecycle.py inspect \
  --input build/rico-stock.json \
  --output build/rico-stock.md
```

The report exposes core/regular/occasional lines, target/reorder amounts, current stock state, affinity score breakdowns, specials and the last cycle's events without making any product-interface decisions.
