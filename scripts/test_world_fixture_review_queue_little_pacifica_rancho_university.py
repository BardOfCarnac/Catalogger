#!/usr/bin/env python3
"""Regression tests for Little China, Pacifica, Rancho, and University held-out Review Queue review."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = {
    "little": ROOT / "data/worlds/night-city-2045/little-china-review-queue.v1.json",
    "pacifica": ROOT / "data/worlds/night-city-2045/pacifica-playground-review-queue.v1.json",
    "rancho": ROOT / "data/worlds/night-city-2045/rancho-coronado-review-queue.v1.json",
    "university": ROOT / "data/worlds/night-city-2045/university-district-review-queue.v1.json",
}

realized = {}
for key, path in FILES.items():
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{key} Review Queue fixture realization must be deterministic"
    realized[key] = {row["name"]: row for row in a["entities"]}

little = realized["little"]
assert {"Bridgetown", "The Forlorn Hope Wreckage", "Guăngbō Tower", "The Parisian"} <= set(little)
assert little["Bridgetown"]["entity_type"] == "context"
assert little["Bridgetown Bodega"]["parent_entity_id"] == "NC2045-LOC-LITTLE-CHINA-098-BRIDGETOWN"
assert little["Bridgetown Bodega"]["local_offerings"][0]["offering_key"] == "incense"
assert little["Guăngbō Tower"]["entity_type"] == "container"
for name in {"Gold Dragons Security", "Libertine Lanes", "Ling Po Public Library", "LCRA Clinic", "Virtex's Virtuality Venue"}:
    assert little[name]["parent_entity_id"] == "NC2045-LOC-LITTLE-CHINA-098-GUANGBO-TOWER"
assert little["Virtex's Virtuality Venue"]["entity_type"] == "context"
assert little["The Parisian"]["entity_type"] == "context"

pacifica = realized["pacifica"]
assert set(pacifica) == {
    "Obsidian Equinox Marina & Docks", "Pleasant Valley Apartments", "Tanson Group Headquarters", "WNS Offices"
}
assert pacifica["Obsidian Equinox Marina & Docks"]["services"][0]["price_eb"] == 1000
assert pacifica["Pleasant Valley Apartments"]["entity_type"] == "local_vendor"
assert "assortment" not in pacifica["Pleasant Valley Apartments"]
assert pacifica["Tanson Group Headquarters"]["entity_type"] == "channel"
assert pacifica["Tanson Group Headquarters"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert pacifica["WNS Offices"]["services"][1]["service_key"] == "talent-scouting"

rancho = realized["rancho"]
assert set(rancho) == {"106.9 Sangre y arena", "Coronado Heights", "The Culms", "Jack 'N' the Green"}
assert rancho["106.9 Sangre y arena"]["entity_type"] == "service"
assert rancho["Coronado Heights"]["entity_type"] == "context"
assert rancho["The Culms"]["entity_type"] == "channel"
assert rancho["The Culms"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert rancho["Jack 'N' the Green"]["entity_type"] == "hybrid"
assert rancho["Jack 'N' the Green"]["distribution"]["service_area"] == "high-end restaurants across Night City"

university = realized["university"]
assert set(university) == {"Biograph Theater", "Fashion Cuts", "Stems & Seeds", "Tumble and Dry"}
assert university["Biograph Theater"]["entity_type"] == "service"
assert university["Fashion Cuts"]["assortment"]
for row in university["Fashion Cuts"]["assortment"]:
    assert engine.commercial_by_id[row["item_id"]]["classification_path"][:2] == ["Cyberware", "Fashionware"]
assert university["Stems & Seeds"]["schedule"]["kind"] == "day_market"
assert "assortment" not in university["Stems & Seeds"]
assert university["Tumble and Dry"]["schedule"]["kind"] == "always_open"

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == {"Fashion Cuts"}

print(
    "OK: Little China + Pacifica + Rancho + University Review Queue review; "
    f"candidates=16, recovered_children={len(little) - 4}, stock-bearing={len(stock_bearers)}"
)
