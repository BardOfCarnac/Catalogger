# Vend-R live Catalogger demo

This connected vertical slice turns the existing Vend-R browser concept into a real client of Catalogger's persistent stocking lifecycle.

The connected demo now loads the full Vend-R v0.8 Night City stock-profile set: 109 authoritative commercial profiles spanning persistent sellers, aggregate containers, event markets, hybrid direct/event businesses, services, templates and references. The original nine-place slice remains useful as a compact fixture, but it is no longer the demo backend's default world.

## Run

```bash
python scripts/build_commercial_profiles.py
python scripts/vendr_demo_server.py
```

Open `http://127.0.0.1:8787/`.

Opening an unopened stock-owning seller creates its durable Catalogger bundle. Reloading reads the same bundle. Purchases decrement saved stock; GM restock advances the lifecycle; source selection applies when an unopened shop is first materialized; event markets are keyed to event IDs; aggregate markets delegate to child businesses.

## Validation

The repository workflow additionally runs:

```bash
python scripts/test_night_city_stock.py
python scripts/test_vendr_stock_engine_contract.py
python scripts/test_vendr_demo_backend.py
python -m py_compile scripts/night_city_stock.py scripts/vendr_demo_backend.py scripts/vendr_demo_server.py
node --check web/vendr-live/app.js
```
