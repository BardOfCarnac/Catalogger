#!/usr/bin/env python3
"""Regression tests for the Pacifica Playground and Rancho Coronado source-review batches."""
from pathlib import Path

from import_nc2045_audit_batch import import_batch
from world_fixture import WorldFixtureError, load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

# New bulk-audit rows remain drafts until the direct source-review fixtures below are used.
for audit_rel in [
    "data/worlds/night-city-2045/import/pacifica-playground-core.audit-v0.2.json",
    "data/worlds/night-city-2045/import/rancho-coronado-core.audit-v0.2.json",
]:
    audit_source = load_json(ROOT / audit_rel)
    draft = import_batch(audit_source)
    assert len(draft["entities"]) == 7
    assert draft["fixture_status"] == "audit_draft"
    validate_document(draft, allow_drafts=True)
    try:
        realize_document(draft, engine)
    except WorldFixtureError:
        pass
    else:
        raise AssertionError("audit draft was allowed to generate persistent stock")

# Pacifica Playground: source review preserves nested places and separates shelf stock from
# repairs, sourcing services and event-only commerce.
pacifica_source = load_json(ROOT / "data/worlds/night-city-2045/pacifica-playground-core.v1.json")
validate_document(pacifica_source)
pacifica_a = realize_document(pacifica_source, engine)
pacifica_b = realize_document(pacifica_source, engine)
assert pacifica_a == pacifica_b, "Pacifica fixture realization must be deterministic"
pacifica = {row["name"]: row for row in pacifica_a["entities"]}
assert len(pacifica) == 14
assert {name for name, row in pacifica.items() if row.get("assortment")} == {
    "Bits’n’Bolts", "The Nomad’s Market", "Pursuit Security Inc Showroom", "Stop. Shop. Stitch."
}

for name in ["Dream Forest Development", "Roots of the Forest", "Jodes Camp"]:
    assert pacifica[name]["entity_type"] == "container"
    assert pacifica[name]["stock_policy"] == "CHILDREN_ONLY"
    assert "assortment" not in pacifica[name]

bits = pacifica["Bits’n’Bolts"]
assert bits["assortment"]
assert {row["service_key"] for row in bits["services"]} == {"tech-repair", "quick-fix"}
assert bits["local_offerings"][0]["offering_key"] == "construction-salvage"
for row in bits["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] in {"General Equipment", "Electronics & Communications"}

doc_miles = pacifica["Doc Miles"]
assert "assortment" not in doc_miles
assert doc_miles["services"][0]["service_key"] == "ripperdoc-installation"

nomad_market = pacifica["The Nomad’s Market"]
assert nomad_market["assortment"]
for row in nomad_market["assortment"]:
    profile = engine.commercial_by_id[row["item_id"]]
    departments = {profile["department"], *profile.get("secondary_departments", [])}
    assert departments & {"weapons", "general-equipment", "food-consumables", "fashion-personal"}
assert {row["service_key"] for row in pacifica["Ojo"]["services"]} == {
    "diego-motors-sourcing", "vehicle-repair", "vehicle-upgrade"
}

pursuit = pacifica["Pursuit Security Inc Showroom"]
pursuit_allowlist = set(pursuit["shop"]["stocking_profile"]["allowed_item_ids"])
assert pursuit["assortment"]
assert {row["item_id"] for row in pursuit["assortment"]} <= pursuit_allowlist
assert pursuit["shop"]["stocking_profile"]["brand_affinities"]["Pursuit Security Inc."] == 20

smile = pacifica["Smile Another Day"]
assert "assortment" not in smile
assert {row["offering_key"] for row in smile["local_offerings"]} == {
    "retired-playland-merch", "ride-scrap", "old-costumes", "park-memorabilia"
}
assert pacifica["Smile Another Day Annual Night Market"]["entity_type"] == "event_market"

stitch = pacifica["Stop. Shop. Stitch."]
assert stitch["assortment"]
assert {"ripperdoc-clinic", "cyberware-installation"} <= {row["service_key"] for row in stitch["services"]}
for row in stitch["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] in {"Food, Drink & Consumables", "General Equipment"}

# Rancho Coronado: the source gate corrects two parser/containment errors. Neither Ingalls Farm
# nor Laguna Bend's Fuel Station is allowed to become a Rancho shop.
rancho_source = load_json(ROOT / "data/worlds/night-city-2045/rancho-coronado-core.v1.json")
validate_document(rancho_source)
corrections = {row["name"]: row for row in rancho_source["audit_corrections"]}
assert corrections["B. Ingalls Farm"]["decision"] == "REHOME_TO_OUTSKIRTS"
assert corrections["Fuel Station"]["decision"] == "REHOME_TO_OUTSKIRTS"
assert corrections["B. Ingalls Farm"]["corrected_source_ref"] == "Night City 2045 p. 294"
assert corrections["Fuel Station"]["corrected_source_ref"] == "Night City 2045 p. 296"

rancho_a = realize_document(rancho_source, engine)
rancho_b = realize_document(rancho_source, engine)
assert rancho_a == rancho_b, "Rancho Coronado fixture realization must be deterministic"
rancho = {row["name"]: row for row in rancho_a["entities"]}
assert len(rancho) == 7
assert {name for name, row in rancho.items() if row.get("assortment")} == {"XOOX"}
assert "B. Ingalls Farm" not in rancho
assert "Fuel Station" not in rancho

assert rancho["Minimallism"]["entity_type"] == "container"
assert rancho["Minimallism"]["stock_policy"] == "CHILDREN_ONLY"
assert rancho["RC Night Market"]["entity_type"] == "event_market"
assert rancho["Ms. Mynah’s Apparel Night Market"]["schedule"] == {"frequency": "monthly", "day_of_month": 5}
assert "assortment" not in rancho["6th Street Station"]
assert "assortment" not in rancho["The Samaritan"]

xoox = rancho["XOOX"]
assert xoox["assortment"]
assert xoox["shop"]["stocking_profile"]["supply_capability"] == "nomad"
assert xoox["parent_entity_id"] == "NC2045-LOC-RANCHO-CORONADO-290-MINIMALLISM"

print(
    "OK: Pacifica Playground + Rancho Coronado source-review batches; "
    f"Pacifica entities={len(pacifica)}, Rancho entities={len(rancho)}"
)
