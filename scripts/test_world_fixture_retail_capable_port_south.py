#!/usr/bin/env python3
"""Regression tests for the first post-census RETAIL_CAPABLE review batch."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = {
    "port": ROOT / "data/worlds/night-city-2045/port-of-night-city-retail-capable.v1.json",
    "south": ROOT / "data/worlds/night-city-2045/south-night-city-retail-capable.v1.json",
}

realized = {}
for key, path in FILES.items():
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{key} RETAIL_CAPABLE fixture realization must be deterministic"
    realized[key] = {row["name"]: row for row in a["entities"]}

port = realized["port"]
assert set(port) == {
    "The Amber Room",
    "Maritime Supply",
    "Medical Technologies",
    "Rusty’s Dive Shack",
    "Sweetheart’s Tattoo Parlor",
    "The Yard",
}
assert "assortment" not in port["The Amber Room"]
assert port["The Amber Room"]["local_offerings"][0]["price_eb"] == 50

maritime = port["Maritime Supply"]
assert maritime["assortment"]
for row in maritime["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] in {"General Equipment", "Fashion & Personal"}
assert maritime["local_offerings"][0]["offering_key"] == "maritime-technology"

medical = port["Medical Technologies"]
assert "assortment" not in medical
assert {row["service_key"] for row in medical["services"]} == {
    "replacement-limb-growth", "cyberware-installation"
}
assert medical["local_offerings"][0]["offering_key"] == "questionable-cyberware"

rusty = port["Rusty’s Dive Shack"]
assert "assortment" not in rusty
assert rusty["local_offerings"][0]["price_eb"] == 10
sweetheart = port["Sweetheart’s Tattoo Parlor"]
assert sweetheart["parent_entity_id"] == "NC2045-LOC-PORT-OF-NIGHT-CITY-155-RUSTY-S-DIVE-SHACK"
assert sweetheart["provenance"] == "CANON_IMPLIED"
assert sweetheart["services"][0]["service_key"] == "tattooing"

assert port["The Yard"]["entity_type"] == "context"
assert port["The Yard"]["stock_policy"] == "NO_STOCK"
assert "assortment" not in port["The Yard"]

south = realized["south"]
assert set(south) == {"The Boneyard", "The Crypt", "GunMart", "MindNutz Lover", "Savage Docs"}
assert south["The Boneyard"]["entity_type"] == "container"
assert south["The Boneyard"]["stock_policy"] == "CHILDREN_ONLY"
crypt = south["The Crypt"]
assert crypt["parent_entity_id"] == "NC2045-LOC-SOUTH-NIGHT-CITY-140-THE-BONEYARD"
assert crypt["local_offerings"][0]["price_eb"] == 10

gunmart = south["GunMart"]
assert gunmart["assortment"]
assert gunmart["shop"]["stocking_profile"]["brand_affinities"]["GunMart"] == 20
assert gunmart["shop"]["stocking_profile"]["primary_departments"] == [
    "weapons", "ammunition-ordnance", "weapon-parts"
]

for name in ["MindNutz Lover", "Savage Docs"]:
    assert south[name]["entity_type"] == "service"
    assert "assortment" not in south[name]
assert south["Savage Docs"]["schedule"]["availability"] == "24/7"

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == {"Maritime Supply", "GunMart"}

print(
    "OK: first RETAIL_CAPABLE source-review batch; "
    f"candidates=9, recovered_children=2, stock-bearing={len(stock_bearers)}"
)
