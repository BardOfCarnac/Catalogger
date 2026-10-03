#!/usr/bin/env python3
"""Regression tests for Playland, Little Europe and Charter Hill CONTEXT_ONLY reviews."""
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


play_candidates, play, play_false = load_review(
    "context-only-candidates-playland-by-the-sea-lands.v0.2.json",
    "playland-by-the-sea-lands-context-only.v1.json",
    34,
)
assert len(play) == 34
assert play_false == set(play) - {"Artificial Beach", "Submarine Tours"}
assert play["Artificial Beach"]["entity_type"] == "context"
assert play["Submarine Tours"]["entity_type"] == "context"
assert play["Lemon-Aid Rx"]["local_offerings"][0]["price_eb"] == 10
assert play["San Francisco Sweets"]["local_offerings"][0]["price_eb"] == 25
assert play["Sourdough Central"]["local_offerings"][1]["price_eb"] == 100
assert play["Carnival of Screams"]["services"][0]["price_eb"] == 10
assert play["Klaws"]["entity_type"] == "hybrid"
assert play["Klaws"]["local_offerings"][0]["pricing_note"] == "Twice the going price"
assert play["The Elflines Online Experience"]["services"][0]["service_key"] == "elflines-online-play"

le_candidates, le, le_false = load_review(
    "context-only-candidates-little-europe.v0.2.json",
    "little-europe-context-only.v1.json",
    12,
)
assert len(le) == 22
assert le_false == {"101.1 Killzone", "Cube-A-Rama", "Danger Gal Offices", "Red Cab Company", "Shady Oaks Elementary", "Soprano’s"}
assert le["Bristol Business Park"]["entity_type"] == "container"
assert le["Bristol Business Park"]["stock_policy"] == "CHILDREN_ONLY"
for name in {
    "Little Europe Communal Bathhouse", "Dewey, Cheatum, and Howe Tax Accountancy", "The Park",
    "Fax-Press", "Black Stone Gaming", "E-Z Cyberware", "Night City Tourism",
    "Hotdesk Co-op", "Aural Experiences", "Software Solutions",
}:
    assert le[name]["parent_entity_id"] == "NC2045-LOC-LITTLE-EUROPE-056-BRISTOL-BUSINESS-PARK"
assert le["Little Europe Communal Bathhouse"]["services"][0]["price_eb_range"] == [1, 2]
assert le["Danger Gal Offices"]["entity_type"] == "hybrid"
for name in {"Biotechnica Reference Forest RF-14", "Camden Court", "Danger Gal Housing Facility", "Holy Angels Church", "Night Corp HQ"}:
    assert le[name]["entity_type"] == "context"

ch_candidates, ch, ch_false = load_review(
    "context-only-candidates-charter-hill.v0.2.json",
    "charter-hill-context-only.v1.json",
    11,
)
assert len(ch) == 12
assert ch_false == {"92.9 Night FM", "Charter Hill Museum of All Art", "The Flow Megachurch", "Eye of the Tiger", "L'Ermitage", "Many Hands", "Seral Grove", "Ward Security"}
assert ch["Charter Hill Museum of All Art"]["services"][0]["price_eb"] == 100
assert ch["L'Ermitage"]["services"][0]["deposit_eb"] == 5000
assert ch["Sanger Connell Private Taxi"]["parent_entity_id"] == "NC2045-LOC-CHARTER-HILL-228-L-ERMITAGE"
assert ch["Sanger Connell Private Taxi"]["provenance"] == "CANON_IMPLIED"
assert ch["Sanger Connell Private Taxi"]["services"][1]["price_eb_per_person"] == 500
for name in {"Checkpoint Lincoln", "Colonial Studios", "Your Neighborhood"}:
    assert ch[name]["entity_type"] == "context"

print(
    "OK: Playland + Little Europe + Charter Hill CONTEXT_ONLY audit; "
    f"candidates={len(play_candidates)+len(le_candidates)+len(ch_candidates)}, "
    f"entities={len(play)+len(le)+len(ch)}, "
    f"direct_false_negatives={len(play_false)+len(le_false)+len(ch_false)}, "
    "recovered_children=11, stock-bearing=0"
)
