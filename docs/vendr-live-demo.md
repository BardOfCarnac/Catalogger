# Vend-R live Catalogger demo

This connected vertical slice turns the existing Vend-R browser concept into a real client of Catalogger's persistent stocking lifecycle.

The sample covers Data Inc, Hundred Under Haven, Gibson Battlegear Outlet, Midnight Arms Regional Office, Tech Time, Oasis (Kabuki), Cheek Turn, RC Night Market and Kaito Market. Together they exercise persistent sellers, manufacturer affinity, a hard 100eb discount ceiling, irregular second-hand stock, event inventory and a multi-vendor parent that deliberately owns no duplicate stock.

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
