#!/usr/bin/env python3
"""Regression tests for the Old Japantown CONTEXT_ONLY source-review pass."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/worlds/night-city-2045/context-only-candidates-old-japantown.v0.2.json"
FIXTURE = ROOT / "data/worlds/night-city-2045/old-japantown-context-only.v1.json"
engine = WorldStockEngine()

candidate_doc = load_json(CANDIDATES)
schema = candidate_doc["schema"]
candidates = [dict(zip(schema, row, strict=True)) for row in candidate_doc["rows"]]
assert candidate_doc["candidate_count"] == len(candidates) == 13

source = load_json(FIXTURE)
validate_document(source)
a = realize_document(source, engine)
b = realize_document(source, engine)
assert a == b
entities = {row["name"]: row for row in a["entities"]}
by_id = {row["entity_id"]: row for row in a["entities"]}
for candidate in candidates:
    assert candidate["entity_id"] in by_id

assert entities["Crisis Medical Center"]["entity_type"] == "service"
assert entities["Dine ‘n Dash"]["entity_type"] == "local_vendor"
assert entities["The Grateful Crane"]["services"][0]["price_eb"] == 1
assert entities["Kid Kamp"]["entity_type"] == "service"
assert entities["Segotari Station Japantown"]["entity_type"] == "service"
assert entities["Kaifū Corner"]["entity_type"] == "context"
assert entities["Recluse"]["parent_entity_id"] == "NC2045-LOC-OLD-JAPANTOWN-131-KAIFU-CORNER"
assert entities["Recluse"]["services"][0]["service_key"] == "elite-netrunner-contract"

confirmed_context = {
    "The Bodukkan", "Gazebo Park", "Kaifū Corner", "Kakoi-chō", "The Precipice",
    "Sanroo Complex", "Segotari Factory", "Tartarus",
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
    "Crisis Medical Center", "Dine ‘n Dash", "The Grateful Crane", "Kid Kamp", "Segotari Station Japantown"
}

print(
    "OK: Old Japantown CONTEXT_ONLY audit; "
    f"candidates={len(candidates)}, entities={len(entities)}, direct_false_negatives={len(false_negatives)}, "
    "recovered_children=1, stock-bearing=0"
)
