#!/usr/bin/env python3
"""Regression tests for canonical Night City 2045 city-stock realization."""
from __future__ import annotations

import json
from pathlib import Path

from build_city_stock import (
    DEFAULT_CITY_OUTPUT,
    DEFAULT_INDEX_OUTPUT,
    DEFAULT_COVERAGE_OUTPUT,
    build_availability_index,
    build_catalogue_coverage,
    build_city_stock,
    write_outputs,
)
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]

engine = WorldStockEngine()
city = build_city_stock(engine)
index = build_availability_index(city, engine)
coverage_report = build_catalogue_coverage(city, index, engine)

assert city["format_version"] == "0.1.0"
assert city["world_id"] == "night-city-2045"
assert city["stock_cycle"] == 0
assert city["policy"]["shop_generation"] is False

sellers = city["sellers"]
assert len(sellers) >= 4, "Kaito Market alone should provide four catalogue-stock sellers"
assert city["coverage"]["catalogue_stock_sellers"] == len(sellers)
assert city["coverage"]["persistent_assortment_lines"] == sum(
    len(row["assortment"]) for row in sellers
)
assert city["coverage"]["cycle_stock_rows"] == sum(len(row["stock"]) for row in sellers)

entity_ids = [row["entity_id"] for row in sellers]
shop_ids = [row["shop_id"] for row in sellers]
assert len(entity_ids) == len(set(entity_ids))
assert len(shop_ids) == len(set(shop_ids))

known_kaito_stock = {
    "NC2045-OUT-LITTLE-EUROPE-060-APOCALYPSE-ZONE-TATTOO",
    "NC2045-OUT-LITTLE-EUROPE-060-APP-SHACK",
    "NC2045-OUT-LITTLE-EUROPE-060-CHEEK-TURN",
    "NC2045-OUT-LITTLE-EUROPE-060-IMPORTED-GOODS-4-CHEAP",
}
assert known_kaito_stock <= set(entity_ids)

# Local/service-only Kaito entities must not be silently promoted into catalogue stock.
for forbidden in {
    "NC2045-OUT-LITTLE-EUROPE-060-FIFTY-FARMS",
    "NC2045-OUT-LITTLE-EUROPE-060-GREG-S",
    "NC2045-OUT-LITTLE-EUROPE-060-MADAME-ZORINA",
    "NC2045-OUT-LITTLE-EUROPE-060-SAGAR-HAIR-SALOON",
    "NC2045-OUT-LITTLE-EUROPE-060-STONE-MILL",
    "NC2045-OUT-LITTLE-EUROPE-060-TACO-TACO",
}:
    assert forbidden not in set(entity_ids)

# Every canonical seller now uses the lifecycle-aware world engine, including targets,
# reorder points, event history and source-filter state.
for seller in sellers:
    bundle = {
        "format_version": "0.2.0",
        "engine_version": engine.model["version"],
        "shop": seller["shop"],
        "assortment": seller["assortment"],
        "stock": seller["stock"],
        "state": seller["state"],
        "history": seller["history"],
    }
    engine.validate_bundle(bundle)
    assert seller["shop"]["source_entity_id"] == seller["entity_id"]
    assert seller["shop"]["id"] == seller["shop_id"]
    assert seller["state"]["stock_cycle"] == 0
    assert "source_filter" in seller["state"]
    assert seller["history"], seller["name"]
    for line in seller["assortment"]:
        assert "score_components" in line
        assert "target_quantity" in line
        assert "reorder_point" in line

# Source-pinned Cheek Turn stock must survive lifecycle enrichment.
cheek = next(
    row for row in sellers
    if row["entity_id"] == "NC2045-OUT-LITTLE-EUROPE-060-CHEEK-TURN"
)
cheek_lines = {row["item_id"]: row for row in cheek["assortment"]}
assert "VENDR-0332" in cheek_lines
assert cheek_lines["VENDR-0332"]["role"] == "regular"
assert cheek_lines["VENDR-0332"]["target_quantity"] is not None
assert cheek_lines["VENDR-0332"]["reorder_point"] is not None

assert index["format_version"] == "0.1.0"
assert index["world_id"] == "night-city-2045"
assert index["stock_cycle"] == 0
assert index["indexed_seller_count"] == len(sellers)
assert set(index["status_vocabulary"]) == {
    "in_stock", "ask", "order", "sold_out", "hidden"
}

items = {row["item_id"]: row for row in index["items"]}
assert index["indexed_item_count"] == len(items)
assert "VENDR-0332" in items
cheek_index = next(
    row for row in items["VENDR-0332"]["sellers"]
    if row["source_entity_id"] == cheek["entity_id"]
)
assert cheek_index["normally_carried"] is True
assert cheek_index["assortment_role"] == "regular"
assert cheek_index["availability"] in index["status_vocabulary"]

known_sellers = set(entity_ids)
for item in index["items"]:
    assert item["seller_count"] == len(item["sellers"])
    for row in item["sellers"]:
        assert row["source_entity_id"] in known_sellers
        assert row["availability"] in index["status_vocabulary"]
        if row["availability"] == "sold_out":
            assert row["normally_carried"] is True
            assert row["quantity"] == 0
        if row["availability"] == "order":
            assert row["incoming_arrival_cycle"] is not None

# Coverage audit is part of the output rather than hidden in build logs.
unresolved = city["unresolved_catalogue_candidates"]
assert city["coverage"]["unresolved_catalogue_candidates"] == len(unresolved)
assert len({row["entity_id"] for row in unresolved}) == len(unresolved)

# Catalogue coverage measures the existing seller network rather than generating shops.
summary = coverage_report["summary"]
assert summary["catalogue_items_total"] == len(engine.items)
assert sum(value for key, value in summary.items() if key != "catalogue_items_total") == len(engine.items)
assert len(coverage_report["items"]) == len(engine.items)
assert {row["coverage_status"] for row in coverage_report["items"]} <= {
    "persistent_assortment",
    "current_special",
    "normal_eligible_not_assorted",
    "special_only_eligible",
    "no_eligible_canonical_seller",
}
assert coverage_report["policy"]["seller_generation"] is False

# The generated files are ordinary deterministic build artifacts.
write_outputs(
    city,
    index,
    coverage_report,
    DEFAULT_CITY_OUTPUT,
    DEFAULT_INDEX_OUTPUT,
    DEFAULT_COVERAGE_OUTPUT,
)
assert json.loads(DEFAULT_CITY_OUTPUT.read_text(encoding="utf-8")) == city
assert json.loads(DEFAULT_INDEX_OUTPUT.read_text(encoding="utf-8")) == index
assert json.loads(DEFAULT_COVERAGE_OUTPUT.read_text(encoding="utf-8")) == coverage_report

print(
    "OK: city stock; "
    f"sellers={len(sellers)}, "
    f"assortment_lines={city['coverage']['persistent_assortment_lines']}, "
    f"stock_rows={city['coverage']['cycle_stock_rows']}, "
    f"indexed_items={index['indexed_item_count']}, "
    f"unresolved_candidates={len(unresolved)}, "
    f"no_eligible_seller={summary.get('no_eligible_canonical_seller', 0)}"
)
