#!/usr/bin/env python3
"""Regression tests for the Downtown CONTEXT_ONLY source-review pass."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/worlds/night-city-2045/context-only-candidates-downtown.v0.2.json"
FIXTURE = ROOT / "data/worlds/night-city-2045/downtown-context-only.v1.json"
engine = WorldStockEngine()

candidate_doc = load_json(CANDIDATES)
schema = candidate_doc["schema"]
candidates = [dict(zip(schema, row, strict=True)) for row in candidate_doc["rows"]]
assert candidate_doc["candidate_count"] == len(candidates) == 6

source = load_json(FIXTURE)
validate_document(source)
a = realize_document(source, engine)
b = realize_document(source, engine)
assert a == b
entities = {row["name"]: row for row in a["entities"]}
by_id = {row["entity_id"]: row for row in a["entities"]}
for candidate in candidates:
    assert candidate["entity_id"] in by_id

assert len(entities) == 13
assert entities["Cortex Complex"]["entity_type"] == "container"
assert entities["Cortex Complex"]["stock_policy"] == "CHILDREN_ONLY"
assert entities["Cortex Complex"]["services"][0]["service_key"] == "commercial-office-rental"

for name in {
    "Allworld Insurance",
    "Screaming Eagle Law",
    "Bodyweight Fitness",
    "Jack Skorkowsky Real Estate",
    "DizCom",
}:
    assert entities[name]["entity_type"] == "service"
    assert entities[name]["parent_entity_id"] == "NC2045-LOC-DOWNTOWN-083-CORTEX-COMPLEX"

for name in {"Reclon", "Bioflugh"}:
    assert entities[name]["entity_type"] == "context"
    assert entities[name]["parent_entity_id"] == "NC2045-LOC-DOWNTOWN-083-CORTEX-COMPLEX"
    assert entities[name]["stock_policy"] == "NO_STOCK"

assert entities["Folio"]["entity_type"] == "service"
assert entities["Folio"]["services"][0]["service_key"] == "fortune-reading"
assert entities["The Nightingale Theater"]["entity_type"] == "service"

for name in {"Continental Plaza", "Night City Firestation #2", "West Hill Church of God"}:
    assert entities[name]["entity_type"] == "context"
    assert entities[name]["stock_policy"] == "NO_STOCK"
    assert "assortment" not in entities[name]

stock_bearers = {name for name, row in entities.items() if row.get("assortment")}
assert stock_bearers == set()

candidate_ids = {row["entity_id"] for row in candidates}
direct_false_negatives = {
    row["name"] for row in entities.values()
    if row["entity_id"] in candidate_ids and row["entity_type"] not in {"context", "container"}
}
assert direct_false_negatives == {"Folio", "The Nightingale Theater"}

print(
    "OK: Downtown CONTEXT_ONLY audit; "
    f"candidates={len(candidates)}, entities={len(entities)}, direct_false_negatives={len(direct_false_negatives)}, "
    "recovered_children=7, stock-bearing=0"
)
