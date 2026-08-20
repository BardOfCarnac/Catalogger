# Night City 2045 stock bridge

This bridge connects canonical Night City 2045 Vend-R stock-profile rows to Catalogger's existing `StockLifecycleEngine` without introducing a second stocking system or modifying the core engine.

Responsibilities stay separate: the Night City graph decides what a place is and whether it owns stock; the stock-profile row decides how it sells; Catalogger decides which canonical items qualify and score well; the lifecycle engine persists assortment, current stock, incoming orders, conditions and event history.

## Stock-mode policy

- `DIRECT_SELLER` -> persistent bundle.
- `AGGREGATE_CONTAINER` -> no parent inventory; delegate to child businesses.
- `EVENT_MARKET` -> bundle keyed to an `event_id`; do not restock that event bundle.
- `CHAIN_TEMPLATE` -> template owns no stock; instantiate a campaign branch first.
- `SERVICE_ONLY`, `REFERENCE_ONLY`, `CHANNEL_TEMPLATE`, `DISTRIBUTION_CHANNEL` -> no static shelf inventory.
- `HYBRID_DIRECT_EVENT` -> persistent base stock; event overlays can be added separately later.

## Translation and Night City constraints

The bridge maps primary/secondary departments, breadth/depth, supply capability, price centre/style, market-channel overrides, manufacturer affinity and canonical source metadata into a realized Catalogger context.

`install_night_city_constraints()` wraps one lifecycle-engine instance at the integration seam. It enforces four realized-shop controls used by the Night City profiles while keeping `stock_engine.py` unchanged:

- `exclude_departments`
- `max_base_price_eb`
- `min_price_tier`
- `minimum_manufacturer_share`

A named manufacturer affinity resolves from the human manufacturer name to Catalogger's normalized manufacturer ID and currently requests a 40% minimum assortment share where enough eligible manufacturer products exist.

## CLI

```bash
python scripts/build_commercial_profiles.py
python scripts/night_city_stock.py \
  --profiles data/shops/night-city-2045-live-demo-profiles.json \
  plan --entity NC2045-LOC-UPPER-MARINA-074-MIDNIGHT-ARMS-REGIONAL-OFFICE
```

Generate a persistent seller:

```bash
python scripts/night_city_stock.py \
  --profiles data/shops/night-city-2045-live-demo-profiles.json \
  generate \
  --entity NC2045-LOC-UPPER-MARINA-074-MIDNIGHT-ARMS-REGIONAL-OFFICE \
  --seed campaign-rico \
  --output build/midnight-arms.json
```

Generate an event inventory:

```bash
python scripts/night_city_stock.py \
  --profiles data/shops/night-city-2045-live-demo-profiles.json \
  generate \
  --entity NC2045-OUT-RANCHO-CORONADO-290-RC-NIGHT-MARKET \
  --seed campaign-rico \
  --event-id session-12-night-market \
  --output build/rc-night-market-session-12.json
```

The included profile file is only the connected vertical-slice sample. The bridge is designed to consume the larger Night City stock-profile dataset as it is brought into the repository.
