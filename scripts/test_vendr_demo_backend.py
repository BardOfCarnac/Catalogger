#!/usr/bin/env python3
"""End-to-end backend smoke test for the connected Vend-R demo (no HTTP needed)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from vendr_demo_backend import DEFAULT_PROFILES, VendRDemoBackend
from night_city_stock import load_runtime

DATA_INC = "NC2045-OUT-WATSON-DEVELOPMENT-190-DATA-INC"
RC_MARKET = "NC2045-OUT-RANCHO-CORONADO-290-RC-NIGHT-MARKET"
KAITO = "NC2045-LOC-LITTLE-EUROPE-060-KAITO-MARKET"

bridge = load_runtime(DEFAULT_PROFILES)
with tempfile.TemporaryDirectory(prefix="vendr-demo-test-") as tmp:
    backend = VendRDemoBackend(
        bridge=bridge,
        profiles_path=DEFAULT_PROFILES,
        state_dir=Path(tmp),
        world_seed="ci-live-demo",
        default_event_id="ci-event",
    )

    before = backend.shop_payload(DATA_INC)
    assert before["materialized"] is True
    assert before["stock"], "Data Inc materialized with no live stock"
    persisted = backend.shop_payload(DATA_INC, materialize=False)
    assert persisted["stock"] == before["stock"], "reopening changed persistent stock"

    purchasable = next(
        row for row in before["stock"]
        if row.get("status") == "in_stock" and isinstance(row.get("quantity"), int) and row["quantity"] > 0
    )
    after_purchase = backend.purchase(DATA_INC, purchasable["item_id"], 1)
    same = next(row for row in after_purchase["stock"] if row["item_id"] == purchasable["item_id"])
    assert same["quantity"] == purchasable["quantity"] - 1

    cycle0 = after_purchase["state"]["stock_cycle"]
    after_restock = backend.restock(DATA_INC)
    assert after_restock["state"]["stock_cycle"] == cycle0 + 1

    search = backend.search(purchasable["name"])
    assert search["items"], "catalogue search did not find a known item"

    event = backend.shop_payload(RC_MARKET, requested_event_id="ci-event")
    assert event["materialized"] is True
    assert event["event_id"] == "ci-event"

    container = backend.shop_payload(KAITO, materialize=False)
    assert container["plan"]["owns_stock"] is False
    assert container["plan"]["action"] == "delegate_to_children"

print("OK: connected Vend-R demo persists, purchases, restocks, searches, events and containers")
