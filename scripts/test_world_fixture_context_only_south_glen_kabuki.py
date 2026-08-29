#!/usr/bin/env python3
"""Regression tests for the South Night City, The Glen and Kabuki CONTEXT_ONLY source-review pass."""
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
    stock_bearers = {name for name, row in entities.items() if row.get("assortment")}
    assert stock_bearers == set()
    return candidates, entities


south_candidates, south = load_review(
    "context-only-candidates-south-night-city.v0.2.json",
    "south-night-city-context-only.v1.json",
    10,
)
assert len(south) == 12
assert south["Combat Cabb Headquarters"]["entity_type"] == "service"
assert south["KidZ"]["entity_type"] == "service"
assert south["MAX-TAC HQ"]["entity_type"] == "service"
assert south["Silverhand Studios"]["entity_type"] == "service"
assert south["Haakensen Tower"]["entity_type"] == "container"
assert south["Haakensen Tower"]["stock_policy"] == "CHILDREN_ONLY"
for name in {"Mayoral Race", "Scythe Security"}:
    assert south[name]["parent_entity_id"] == "NC2045-LOC-SOUTH-NIGHT-CITY-142-HAAKENSEN-TOWER"
assert south["Mayoral Race"]["local_offerings"][0]["price_eb"] == 5
for name in {
    "Fort Sumter", "Lazarus Training Center", "South Cargo Village",
    "South Night City Volunteer Fire Station", "Union Chapel Building",
}:
    assert south[name]["entity_type"] == "context"
    assert south[name]["stock_policy"] == "NO_STOCK"
south_candidate_ids = {row["entity_id"] for row in south_candidates}
south_false_negatives = {
    row["name"] for row in south.values()
    if row["entity_id"] in south_candidate_ids and row["entity_type"] not in {"context", "container"}
}
assert south_false_negatives == {
    "Combat Cabb Headquarters", "KidZ", "MAX-TAC HQ", "Silverhand Studios"
}


glen_candidates, glen = load_review(
    "context-only-candidates-the-glen.v0.2.json",
    "the-glen-context-only.v1.json",
    11,
)
assert len(glen) == 22
assert glen["1st Night City Bank"]["entity_type"] == "service"
assert glen["DMV"]["entity_type"] == "service"
assert glen["Consulate Causeway"]["entity_type"] == "container"
assert glen["Raven Microcybernetics"]["entity_type"] == "container"
for name in {
    "EEC Consulate", "Japanese Consulate", "Mexican Consulate",
    "Pacifica Confederation Offices", "Organization of American States Mission",
    "United States Consulate",
}:
    assert glen[name]["parent_entity_id"] == "NC2045-LOC-THE-GLEN-118-CONSULATE-CAUSEWAY"
    assert glen[name]["entity_type"] == "service"
for name in {
    "Clean Sweep Enterprises", "Dayton Aeronautics", "Everest VentureWare",
    "KillStrom Music", "Doctor William Galen",
}:
    assert glen[name]["parent_entity_id"] == "NC2045-LOC-THE-GLEN-123-RAVEN-MICROCYBERNETICS"
assert glen["Clean Sweep Enterprises"]["entity_type"] == "service"
assert glen["Doctor William Galen"]["entity_type"] == "service"
for name in {"Dayton Aeronautics", "Everest VentureWare", "KillStrom Music"}:
    assert glen[name]["entity_type"] == "context"
glen_candidate_ids = {row["entity_id"] for row in glen_candidates}
glen_false_negatives = {
    row["name"] for row in glen.values()
    if row["entity_id"] in glen_candidate_ids and row["entity_type"] not in {"context", "container"}
}
assert glen_false_negatives == {"1st Night City Bank", "DMV"}


kabuki_candidates, kabuki = load_review(
    "context-only-candidates-kabuki.v0.2.json",
    "kabuki-context-only.v1.json",
    6,
)
assert len(kabuki) == 8
assert kabuki["100.0 G3 Gun-Gal Station"]["entity_type"] == "container"
assert kabuki["The Cabbit"]["parent_entity_id"] == "NC2045-LOC-KABUKI-202-100-0-G3-GUN-GAL-STATION"
assert kabuki["G3 Music Chips on The Garden"]["parent_entity_id"] == "NC2045-LOC-KABUKI-202-100-0-G3-GUN-GAL-STATION"
assert kabuki["G3 Music Chips on The Garden"]["entity_type"] == "channel"
assert kabuki["G3 Music Chips on The Garden"]["provenance"] == "CANON_IMPLIED"
assert kabuki["Nakagawa Academy"]["entity_type"] == "service"
assert kabuki["Nakagawa Academy"]["services"][0]["price_eb"] == 100
assert kabuki["Rokumei-kan"]["entity_type"] == "hybrid"
assert kabuki["Rokumei-kan"]["local_offerings"][0]["price_eb"] == 50
assert kabuki["Tyger Dojo/Tora-no-Ana"]["entity_type"] == "service"
for name in {"91.9 Royal Blue", "Toranoko Gakuen"}:
    assert kabuki[name]["entity_type"] == "context"
    assert kabuki[name]["stock_policy"] == "NO_STOCK"
kabuki_candidate_ids = {row["entity_id"] for row in kabuki_candidates}
kabuki_false_negatives = {
    row["name"] for row in kabuki.values()
    if row["entity_id"] in kabuki_candidate_ids and row["entity_type"] not in {"context", "container"}
}
assert kabuki_false_negatives == {"Nakagawa Academy", "Rokumei-kan", "Tyger Dojo/Tora-no-Ana"}

print(
    "OK: South Night City + The Glen + Kabuki CONTEXT_ONLY audit; "
    f"candidates={len(south_candidates) + len(glen_candidates) + len(kabuki_candidates)}, "
    f"entities={len(south) + len(glen) + len(kabuki)}, "
    f"direct_false_negatives={len(south_false_negatives) + len(glen_false_negatives) + len(kabuki_false_negatives)}, "
    "recovered_children=15, stock-bearing=0"
)
