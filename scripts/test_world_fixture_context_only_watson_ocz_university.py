#!/usr/bin/env python3
"""Regression tests for Watson Development, Old Combat Zone and University District CONTEXT_ONLY reviews."""
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


watson_candidates, watson, watson_false = load_review(
    "context-only-candidates-watson-development.v0.2.json",
    "watson-development-context-only.v1.json",
    11,
)
assert len(watson) == 11
assert watson_false == {
    "City Tot Daycare", "FūdHouse", "Hammered Up Liquor",
    "The Pochinko Carnival", "Watson Central Cubelife",
}
assert watson["City Tot Daycare"]["entity_type"] == "service"
assert watson["FūdHouse"]["entity_type"] == "local_vendor"
assert watson["Hammered Up Liquor"]["entity_type"] == "local_vendor"
assert watson["The Pochinko Carnival"]["entity_type"] == "hybrid"
assert watson["The Pochinko Carnival"]["purchase_policy"][0]["price_eb"] == 10
assert watson["Watson Central Cubelife"]["services"][0]["service_key"] == "cube-hotel-lodging"
for name in {
    "Joint Temporary Housing Solution", "NeoSoviet Consulate", "The Obituary",
    "Petrochem Oil Refinery", "SkidRow Limited", "SovOil Oil Refinery",
}:
    assert watson[name]["entity_type"] == "context"
    assert watson[name]["stock_policy"] == "NO_STOCK"


ocz_candidates, ocz, ocz_false = load_review(
    "context-only-candidates-old-combat-zone.v0.2.json",
    "old-combat-zone-context-only.v1.json",
    9,
)
assert len(ocz) == 9
assert ocz_false == {"Always Hot", "The Arena", "Bladeware"}
assert ocz["Always Hot"]["entity_type"] == "service"
assert ocz["The Arena"]["entity_type"] == "service"
assert ocz["Bladeware"]["entity_type"] == "local_vendor"
assert {o["offering_key"] for o in ocz["Bladeware"]["local_offerings"]} == {"carried-blades", "implanted-blades"}
for name in {
    "The Farnsworth Building", "Ionic Semiconductor Building", "The Laydown",
    "The Lodge", "Substation 12", "The Terrace",
}:
    assert ocz[name]["entity_type"] == "context"
    assert ocz[name]["stock_policy"] == "NO_STOCK"


uni_candidates, uni, uni_false = load_review(
    "context-only-candidates-university-district.v0.2.json",
    "university-district-context-only.v1.json",
    9,
)
assert len(uni) == 18
assert uni_false == {"Night City Symphony Hall", "Parkside Living", "University Crèche", "University Cubes"}
assert uni["Biotechnica Campus"]["entity_type"] == "container"
assert uni["Biotechnica Campus"]["stock_policy"] == "CHILDREN_ONLY"
assert uni["Attraction Sphere Sigma"]["parent_entity_id"] == "NC2045-LOC-UNIVERSITY-DISTRICT-106-BIOTECHNICA-CAMPUS"
assert uni["Food Truck Plaza"]["entity_type"] == "container"
assert uni["Food Truck Plaza"]["stock_policy"] == "CHILDREN_ONLY"
food_children = {
    "Buck-a-Slice", "Captain Cajun’s Nifty Nuggets", "Green Pretzels", "Happy Noodles",
    "Kibble Cookie Kraze", "Ramen Late", "SoSushiMe", "Vendit Wagon",
}
for name in food_children:
    assert uni[name]["entity_type"] == "local_vendor"
    assert uni[name]["parent_entity_id"] == "NC2045-LOC-UNIVERSITY-DISTRICT-107-FOOD-TRUCK-PLAZA"
for name in {"Biotechnica Habitation Sphere Alpha", "Campus Chapel", "Princessland"}:
    assert uni[name]["entity_type"] == "context"
    assert uni[name]["stock_policy"] == "NO_STOCK"
for name in {"Night City Symphony Hall", "Parkside Living", "University Crèche", "University Cubes"}:
    assert uni[name]["entity_type"] == "service"

print(
    "OK: Watson + Old Combat Zone + University CONTEXT_ONLY audit; "
    f"candidates={len(watson_candidates)+len(ocz_candidates)+len(uni_candidates)}, "
    f"entities={len(watson)+len(ocz)+len(uni)}, "
    f"direct_false_negatives={len(watson_false)+len(ocz_false)+len(uni_false)}, "
    "recovered_children=9, stock-bearing=0"
)
