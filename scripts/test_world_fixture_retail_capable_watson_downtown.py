#!/usr/bin/env python3
"""Regression tests for Watson Development and Downtown RETAIL_CAPABLE review."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = {
    "watson": ROOT / "data/worlds/night-city-2045/watson-development-retail-capable.v1.json",
    "downtown": ROOT / "data/worlds/night-city-2045/downtown-retail-capable.v1.json",
}

realized = {}
for key, path in FILES.items():
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{key} RETAIL_CAPABLE fixture realization must be deterministic"
    realized[key] = {row["name"]: row for row in a["entities"]}

watson = realized["watson"]
assert set(watson) == {
    "Faisal’s Customs",
    "Faisal’s Customs Factory Output",
    "Old Black Rum Pub",
    "Red Oktober",
    "Whammer Arena",
}
faisal = watson["Faisal’s Customs"]
assert "assortment" not in faisal
assert {row["offering_key"] for row in faisal["local_offerings"]} == {
    "faisal-designed-firearms", "faisal-custom-weapons"
}
factory = watson["Faisal’s Customs Factory Output"]
assert factory["entity_type"] == "channel"
assert factory["parent_entity_id"] == "NC2045-LOC-WATSON-DEVELOPMENT-188-FAISAL-S-CUSTOMS"
assert factory["stock_policy"] == "NO_STATIC_INVENTORY"
assert factory["distribution"]["destinations"] == ["vendits", "bodegas"]

black_rum = watson["Old Black Rum Pub"]
assert "assortment" not in black_rum
assert black_rum["local_offerings"][0]["price_eb"] == 10
assert next(row for row in black_rum["services"] if row["service_key"] == "surge-injection")["price_eb"] == 20

red_oktober = watson["Red Oktober"]
assert "assortment" not in red_oktober
assert red_oktober["local_offerings"][0]["price_eb"] == 20
assert watson["Whammer Arena"]["entity_type"] == "service"
assert "assortment" not in watson["Whammer Arena"]

downtown = realized["downtown"]
assert set(downtown) == {
    "Gilded Phoenix Arcade",
    "Guns & Dolls",
    "Jade Blossom Spa",
    "Jade Blossom Counterfeit Distribution",
}
assert downtown["Gilded Phoenix Arcade"]["entity_type"] == "service"
assert "assortment" not in downtown["Gilded Phoenix Arcade"]

guns = downtown["Guns & Dolls"]
assert guns["assortment"]
for row in guns["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "Weapons"
assert {row["service_key"] for row in guns["services"]} == {"strip-club", "brothel"}

spa = downtown["Jade Blossom Spa"]
assert spa["entity_type"] == "service"
assert "assortment" not in spa
counterfeit = downtown["Jade Blossom Counterfeit Distribution"]
assert counterfeit["entity_type"] == "channel"
assert counterfeit["parent_entity_id"] == "NC2045-LOC-DOWNTOWN-085-JADE-BLOSSOM-SPA"
assert counterfeit["stock_policy"] == "NO_STATIC_INVENTORY"
assert "assortment" not in counterfeit

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == {"Guns & Dolls"}

print(
    "OK: Watson + Downtown RETAIL_CAPABLE review; "
    f"candidates=7, recovered_channels=2, stock-bearing={len(stock_bearers)}"
)
