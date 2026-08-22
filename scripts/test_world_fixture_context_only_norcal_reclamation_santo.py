#!/usr/bin/env python3
"""Regression tests for NorCal Military Base, Reclamation Zone and Santo Domingo CONTEXT_ONLY reviews."""
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


norcal_candidates, norcal, norcal_false = load_review(
    "context-only-candidates-norcal-military-base.v0.2.json",
    "norcal-military-base-context-only.v1.json",
    11,
)
assert len(norcal) == 11
assert norcal_false == {"Motor Pool"}
assert norcal["Motor Pool"]["entity_type"] == "service"
assert norcal["Motor Pool"]["services"][0]["service_key"] == "resident-vehicle-repair"
for name in {
    "157th Tactical Air Squadron Airfield", "Estero Bay Military COG Academy",
    "Fire & Emergency Response Center", "Main Gate", "Mess Hall",
    "Military Police Headquarters", "Militech Corporate Housing", "Parade Ground",
    "The Potentilla", "Task Force 384 Docks",
}:
    assert norcal[name]["entity_type"] == "context"
    assert norcal[name]["stock_policy"] == "NO_STOCK"


recl_candidates, recl, recl_false = load_review(
    "context-only-candidates-reclamation-zone.v0.2.json",
    "reclamation-zone-context-only.v1.json",
    11,
)
assert len(recl) == 11
assert recl_false == {"Flashback", "Gordon’s Garage", "Herschel’s Crematorium", "Second City Solos Firing Range"}
assert recl["Flashback"]["entity_type"] == "service"
assert recl["Gordon’s Garage"]["services"][0]["service_key"] == "vehicle-repair-modification"
assert recl["Herschel’s Crematorium"]["services"][0]["service_key"] == "funeral-cremation"
assert recl["Second City Solos Firing Range"]["entity_type"] == "hybrid"
assert recl["Second City Solos Firing Range"]["local_offerings"][0]["price_eb"] == 20
for name in {
    "Country Cars", "Freddie Douglas School", "McGee Speedway", "La Perrera",
    "Metal Mountain", "Mobile Mosque Prayer Center", "NCART Yards",
}:
    assert recl[name]["entity_type"] == "context"


santo_candidates, santo, santo_false = load_review(
    "context-only-candidates-santo-domingo.v0.2.json",
    "santo-domingo-context-only.v1.json",
    11,
)
assert len(santo) == 17
assert santo_false == {"Aldecaldo Warriors Track", "Heywood Suites", "Salón de Valentino"}
assert santo["Aldecaldo Warriors Track"]["local_offerings"][0]["price_eb"] == 10
assert santo["Ciudad Techito"]["entity_type"] == "container"
assert santo["Ciudad Techito Local Guides"]["provenance"] == "CANON_IMPLIED"
assert santo["Ciudad Techito Local Guides"]["services"][0]["price_eb_range"] == [5, 10]
assert santo["Hunger Street"]["entity_type"] == "container"
for name in {"Buck-a-Slice", "Cart Chrome", "Monster T", "SharkBites", "TacoSCOP"}:
    assert santo[name]["entity_type"] == "local_vendor"
    assert santo[name]["parent_entity_id"] == "NC2045-LOC-SANTO-DOMINGO-268-HUNGER-STREET"
assert santo["Heywood Suites"]["entity_type"] == "service"
assert santo["Salón de Valentino"]["services"][0]["service_key"] == "municipal-administration"
for name in {
    "Aldecaldo Peacekeepers HQ", "Altar a Nuestra Señora de la Santa Muerte",
    "Coronado Dam", "East Cargo Village", "NCPD Precinct #2", "SovOil Paint Factory",
}:
    assert santo[name]["entity_type"] == "context"

print(
    "OK: NorCal Military Base + Reclamation Zone + Santo Domingo CONTEXT_ONLY audit; "
    f"candidates={len(norcal_candidates)+len(recl_candidates)+len(santo_candidates)}, "
    f"entities={len(norcal)+len(recl)+len(santo)}, "
    f"direct_false_negatives={len(norcal_false)+len(recl_false)+len(santo_false)}, "
    "recovered_children=6, stock-bearing=0"
)
