#!/usr/bin/env python3
"""Smoke tests for Night City hard gates layered over Catalogger's stock engine."""
from __future__ import annotations

import math
from stock_lifecycle import StockLifecycleEngine
from night_city_stock import install_night_city_constraints

engine = install_night_city_constraints(StockLifecycleEngine())

cap = engine.make_context("general-store", "vendr-cap", overrides={"max_base_price_eb": 100})
for item in engine.items:
    if engine.eligible(item["id"], cap):
        price = engine._base_price(item)
        assert price is None or price <= 100, (item["id"], price)

minimum = engine.make_context("general-store", "vendr-min", overrides={"min_price_tier": "Premium"})
order = engine.model["price_score"]["tier_order"]
for item in engine.items:
    if engine.eligible(item["id"], minimum):
        tier = engine._price_tier(item)
        assert tier is None or order.index(tier) >= order.index("Premium"), (item["id"], tier)

excluded = engine.make_context("general-store", "vendr-exclude", overrides={"exclude_departments": ["cyberware"]})
for item in engine.items:
    if engine.eligible(item["id"], excluded):
        assert "cyberware" not in engine._item_departments(engine.commercial_by_id[item["id"]])

base = engine.make_context("weapons-dealer", "vendr-brand-base")
eligible_by_mfr: dict[str, set[str]] = {}
for item in engine.items:
    if engine.eligible(item["id"], base):
        for mfr in engine.manufacturers_by_item.get(item["id"], []):
            eligible_by_mfr.setdefault(mfr, set()).add(item["id"])
brand_id, available_brand = max(eligible_by_mfr.items(), key=lambda pair: len(pair[1]))
context = engine.make_context(
    "weapons-dealer", "vendr-brand-floor",
    overrides={"brand_affinities": {brand_id: 20}, "minimum_manufacturer_share": 0.40},
)
assortment = engine.build_assortment(context)
branded = sum(brand_id in engine.manufacturers_by_item.get(row["item_id"], []) for row in assortment)
expected = min(int(math.ceil(len(assortment) * 0.40)), len(available_brand))
assert branded >= expected, (brand_id, branded, expected)

print("OK: Night City hard price/department gates and manufacturer-share floor")
