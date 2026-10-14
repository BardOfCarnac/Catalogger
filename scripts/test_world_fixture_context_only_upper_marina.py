#!/usr/bin/env python3
"""Regression tests for the Upper Marina CONTEXT_ONLY source-review pass."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/worlds/night-city-2045/context-only-candidates-upper-marina.v0.2.json"
FIXTURE = ROOT / "data/worlds/night-city-2045/upper-marina-context-only.v1.json"
engine = WorldStockEngine()

candidate_doc = load_json(CANDIDATES)
schema = candidate_doc["schema"]
candidates = [dict(zip(schema, row, strict=True)) for row in candidate_doc["rows"]]
assert candidate_doc["candidate_count"] == len(candidates) == 18

source = load_json(FIXTURE)
validate_document(source)
a = realize_document(source, engine)
b = realize_document(source, engine)
assert a == b
entities = {row["name"]: row for row in a["entities"]}
by_id = {row["entity_id"]: row for row in a["entities"]}
for candidate in candidates:
    assert candidate["entity_id"] in by_id

assert entities["CMax"]["entity_type"] == "hybrid"
assert entities["CMax"]["local_offerings"][0]["offering_key"] == "themed-lobby-food"
assert entities["The Garden of Earthly Delights"]["entity_type"] == "service"
assert entities["Great River Storehouse"]["entity_type"] == "channel"
assert entities["Great River Storehouse"]["distribution"]["ordering_channel"] == "The Garden"
assert entities["La Lune Bleue"]["services"][1]["price_eb"] == 500
assert entities["Marina Breeze Apartments"]["services"][0]["service_key"] == "residential-rental"
assert entities["Marina FloatHomes"]["services"][0]["service_key"] == "floating-residential-rental"
assert entities["Night City Convention Center"]["entity_type"] == "service"
assert entities["Otter Docks Transfer Station"]["entity_type"] == "channel"
assert entities["REO Meatwagon"]["services"][0]["service_key"] == "emergency-ambulance-response"
assert entities["TravlStay CityCenter"]["services"][0]["service_key"] == "cube-hotel-lodging"

confirmed_context = {
    "Digital Divinity Incorporated, NC", "Court Towers", "Flowertown", "Hydrosubsidium R&D",
    "JC Homes", "Megabuilding H8 Construction Site", "Oceanside Docks", "Upper Marina Substation 2",
}
for name in confirmed_context:
    assert entities[name]["entity_type"] == "context"
    assert entities[name]["stock_policy"] == "NO_STOCK"
    assert "assortment" not in entities[name]

stock_bearers = {name for name, row in entities.items() if row.get("assortment")}
assert stock_bearers == set()

candidate_ids = {row["entity_id"] for row in candidates}
false_negatives = {
    row["name"] for row in entities.values()
    if row["entity_id"] in candidate_ids and row["entity_type"] not in {"context", "container"}
}
assert false_negatives == {
    "CMax", "The Garden of Earthly Delights", "Great River Storehouse", "La Lune Bleue",
    "Marina Breeze Apartments", "Marina FloatHomes", "Night City Convention Center",
    "Otter Docks Transfer Station", "REO Meatwagon", "TravlStay CityCenter",
}

print(
    "OK: Upper Marina CONTEXT_ONLY audit; "
    f"candidates={len(candidates)}, entities={len(entities)}, direct_false_negatives={len(false_negatives)}, "
    "recovered_children=0, stock-bearing=0"
)
