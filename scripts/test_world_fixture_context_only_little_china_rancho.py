#!/usr/bin/env python3
"""Regression tests for the final Little China and Rancho Coronado CONTEXT_ONLY reviews."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/worlds/night-city-2045"
engine = WorldStockEngine()


def load_review(candidate_name, fixture_name, expected_count):
    candidate_doc = load_json(DATA / candidate_name)
    schema = candidate_doc["schema"]
    candidates = [dict(zip(schema, row, strict=True)) for row in candidate_doc["rows"]]
    assert candidate_doc["candidate_count"] == len(candidates) == expected_count
    source = load_json(DATA / fixture_name)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b
    entities = {row["name"]: row for row in a["entities"]}
    by_id = {row["entity_id"]: row for row in a["entities"]}
    for candidate in candidates:
        assert candidate["entity_id"] in by_id
    assert not {name for name, row in entities.items() if row.get("assortment")}
    candidate_ids = {row["entity_id"] for row in candidates}
    direct_false_negatives = {
        row["name"] for row in entities.values()
        if row["entity_id"] in candidate_ids and row["entity_type"] not in {"context", "container"}
    }
    return candidates, entities, direct_false_negatives


little_candidates, little, little_false = load_review(
    "context-only-candidates-little-china.v0.2.json",
    "little-china-context-only.v1.json",
    5,
)
assert len(little) == 5
assert little_false == {"Madame Lin’s Massage Parlor", "Hydrosubsidium", "Richard Night Aquarium"}
assert little["Guānyīn Temple"]["entity_type"] == "context"
assert little["Madame Lin’s Massage Parlor"]["entity_type"] == "service"
assert little["Hydrosubsidium"]["entity_type"] == "service"
assert little["Ling Po Imports Wreckage"]["entity_type"] == "context"
assert little["Richard Night Aquarium"]["entity_type"] == "hybrid"
assert little["Richard Night Aquarium"]["purchase_policy"][0]["purchase_key"] == "aquarium-specimen-acquisition"

rancho_candidates, rancho, rancho_false = load_review(
    "context-only-candidates-rancho-coronado.v0.2.json",
    "rancho-coronado-context-only.v1.json",
    5,
)
assert len(rancho) == 5
assert rancho_false == {"Albino Alligator Car Wash"}
assert rancho["Albino Alligator Car Wash"]["entity_type"] == "local_vendor"
assert rancho["Albino Alligator Car Wash"]["local_offerings"][0]["offering_key"] == "bucketed-clean-water"
for name in {"Bread and Roses", "Digital Divinity Ruins", "Eagle Rock Stadium", "The Island"}:
    assert rancho[name]["entity_type"] == "context"
    assert rancho[name]["stock_policy"] == "NO_STOCK"

print(
    "OK: Little China + Rancho Coronado CONTEXT_ONLY audit; "
    f"candidates={len(little_candidates)+len(rancho_candidates)}, "
    f"entities={len(little)+len(rancho)}, "
    f"direct_false_negatives={len(little_false)+len(rancho_false)}, "
    "recovered_children=0, stock-bearing=0"
)
