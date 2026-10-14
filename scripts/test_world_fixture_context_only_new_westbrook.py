#!/usr/bin/env python3
"""Regression tests for the New Westbrook CONTEXT_ONLY source-review pass."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/worlds/night-city-2045/context-only-candidates-new-westbrook.v0.2.json"
FIXTURE = ROOT / "data/worlds/night-city-2045/new-westbrook-context-only.v1.json"
engine = WorldStockEngine()

candidate_doc = load_json(CANDIDATES)
schema = candidate_doc["schema"]
candidates = [dict(zip(schema, row, strict=True)) for row in candidate_doc["rows"]]
assert candidate_doc["candidate_count"] == len(candidates) == 12

source = load_json(FIXTURE)
validate_document(source)
a = realize_document(source, engine)
b = realize_document(source, engine)
assert a == b
entities = {row["name"]: row for row in a["entities"]}
by_id = {row["entity_id"]: row for row in a["entities"]}
for candidate in candidates:
    assert candidate["entity_id"] in by_id

assert entities["Aerocab"]["entity_type"] == "service"
assert entities["Augmented Optic"]["entity_type"] == "channel"
assert entities["Evergreen Apartments"]["entity_type"] == "service"
assert entities["Lincoln Lot"]["entity_type"] == "channel"
assert entities["Virtual Variety"]["entity_type"] == "hybrid"

assert entities["Rocklin Augmentics Innovation Hub"]["entity_type"] == "container"
assert entities["Rocklin Augmentics Innovation Hub"]["stock_policy"] == "CHILDREN_ONLY"
side_hustles = entities["Innovation Hub Tech/Medtech Side Hustles"]
assert side_hustles["parent_entity_id"] == "NC2045-LOC-NEW-WESTBROOK-218-ROCKLIN-AUGMENTICS-INNOVATION-HUB"
assert side_hustles["provenance"] == "CANON_IMPLIED"
assert side_hustles["services"][0]["service_key"] == "resident-tech-medtech-side-work"

confirmed_context = {
    "The Combat Zone",
    "Megabuilding H6 Construction Site",
    "Net54 88.2",
    "Network 54 Westbrook Private Acres",
    "Night City Firestation #1",
    "North Cargo Village",
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
    "Aerocab",
    "Augmented Optic",
    "Evergreen Apartments",
    "Lincoln Lot",
    "Virtual Variety",
}

print(
    "OK: New Westbrook CONTEXT_ONLY audit; "
    f"candidates={len(candidates)}, entities={len(entities)}, direct_false_negatives={len(false_negatives)}, "
    "recovered_children=1, stock-bearing=0"
)
