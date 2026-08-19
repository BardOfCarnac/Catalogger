#!/usr/bin/env python3
"""Regression tests for Heywood Docks, North Heywood and Pacifica Playground CONTEXT_ONLY reviews."""
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


docks_candidates, docks, docks_false = load_review(
    "context-only-candidates-heywood-docks.v0.2.json",
    "heywood-docks-context-only.v1.json",
    8,
)
assert len(docks) == 8
assert docks_false == {
    "Decker, Tanaka & Rogers", "Dockside Billhooks Track", "Greenbox Storage Units",
    "HF&S Construction", "LoadStar Continental Shipping",
}
for name in docks_false:
    assert docks[name]["entity_type"] == "service"
for name in {"The Cylinders", "Rail Yard", "Shipping Yard"}:
    assert docks[name]["entity_type"] == "context"
    assert docks[name]["stock_policy"] == "NO_STOCK"
assert docks["Greenbox Storage Units"]["services"][0]["service_key"] == "secure-storage-rental"


north_candidates, north, north_false = load_review(
    "context-only-candidates-north-heywood.v0.2.json",
    "north-heywood-context-only.v1.json",
    8,
)
assert len(north) == 14
assert north_false == {"AmeriCar Distribution Center", "Haywire Circuit Gym"}
assert north["AmeriCar Distribution Center"]["entity_type"] == "channel"
assert north["AmeriCar Distribution Center"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert north["AmeriCar Distribution Center"]["distribution"]["buyer_types"] == ["dealerships", "Fixers"]
assert set(north["AmeriCar Distribution Center"]["distribution"]["source_explicit_models"]) == {
    "AmeriCar EconoCompact", "AmeriCar Family Star Van"
}
assert north["Haywire Circuit Gym"]["entity_type"] == "service"
for name in {"The Armory", "Dynalar Campus"}:
    assert north[name]["entity_type"] == "context"
    assert north[name]["stock_policy"] == "NO_STOCK"
for name in {"Evergreen Vista Park", "Neon Hollow Strip", "North Heywood Civic Nexus", "Turbine Alley"}:
    assert north[name]["entity_type"] == "container"
    assert north[name]["stock_policy"] == "CHILDREN_ONLY"
children = {
    "Evergreen Vista Park Informal Dealer Channel": "NC2045-LOC-NORTH-HEYWOOD-249-EVERGREEN-VISTA-PARK",
    "Edgework Escapes": "NC2045-LOC-NORTH-HEYWOOD-250-NEON-HOLLOW-STRIP",
    "Neon Hollow Rotating Vice Businesses": "NC2045-LOC-NORTH-HEYWOOD-250-NEON-HOLLOW-STRIP",
    "North Heywood Civic Nexus Cafeteria": "NC2045-LOC-NORTH-HEYWOOD-250-NORTH-HEYWOOD-CIVIC-NEXUS",
    "Turbine Alley Chop Shops & Workshops": "NC2045-LOC-NORTH-HEYWOOD-251-TURBINE-ALLEY",
    "Turbine Alley Drone Races": "NC2045-LOC-NORTH-HEYWOOD-251-TURBINE-ALLEY",
}
for name, parent in children.items():
    assert north[name]["parent_entity_id"] == parent
assert north["Evergreen Vista Park Informal Dealer Channel"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert north["Neon Hollow Rotating Vice Businesses"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert north["Turbine Alley Chop Shops & Workshops"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert north["Edgework Escapes"]["entity_type"] == "service"
assert north["North Heywood Civic Nexus Cafeteria"]["entity_type"] == "local_vendor"
assert north["Turbine Alley Drone Races"]["services"][1]["service_key"] == "race-betting"


pacifica_candidates, pacifica, pacifica_false = load_review(
    "context-only-candidates-pacifica-playground.v0.2.json",
    "pacifica-playground-context-only.v1.json",
    8,
)
assert len(pacifica) == 8
assert pacifica_false == {
    "Cubeland by the Sea", "Mister Rice Guy", "Playhouse", "ShellShock Central",
    "Scenic Cubes", "Torta-sienda",
}
for name in {"Pacifica Arcology Ruins", "Quaid Winston Memorial De-Salinization Plant"}:
    assert pacifica[name]["entity_type"] == "context"
    assert pacifica[name]["stock_policy"] == "NO_STOCK"
for name in {"Cubeland by the Sea", "Playhouse", "ShellShock Central", "Scenic Cubes"}:
    assert pacifica[name]["entity_type"] == "service"
assert pacifica["Mister Rice Guy"]["entity_type"] == "local_vendor"
prices = {row["offering_key"]: row["price_eb"] for row in pacifica["Mister Rice Guy"]["local_offerings"]}
assert prices == {"yellow-meal": 10, "pink-meal": 200}
assert pacifica["Torta-sienda"]["entity_type"] == "local_vendor"
assert pacifica["Torta-sienda"]["local_offerings"][0]["offering_key"] == "fresh-family-meals"
assert pacifica["ShellShock Central"]["benefits"][0]["value_percent"] == 5


print(
    "OK: Heywood Docks + North Heywood + Pacifica Playground CONTEXT_ONLY audit; "
    f"candidates={len(docks_candidates)+len(north_candidates)+len(pacifica_candidates)}, "
    f"entities={len(docks)+len(north)+len(pacifica)}, "
    f"direct_false_negatives={len(docks_false)+len(north_false)+len(pacifica_false)}, "
    f"recovered_children={len(children)}, stock-bearing=0"
)
