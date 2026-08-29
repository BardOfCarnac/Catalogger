#!/usr/bin/env python3
"""Regression tests for the Little China and Reclamation Zone source-review batches."""
from pathlib import Path

from import_nc2045_audit_batch import import_batch
from world_fixture import WorldFixtureError, load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

# Bulk audit data is still only a draft input. It cannot create persistent shop state until
# the reviewed fixtures below have narrowed/corrected it.
for audit_rel in [
    "data/worlds/night-city-2045/import/little-china-core.audit-v0.2.json",
    "data/worlds/night-city-2045/import/reclamation-zone-core.audit-v0.2.json",
]:
    audit_source = load_json(ROOT / audit_rel)
    draft = import_batch(audit_source)
    assert len(draft["entities"]) == 6
    assert draft["fixture_status"] == "audit_draft"
    validate_document(draft, allow_drafts=True)
    try:
        realize_document(draft, engine)
    except WorldFixtureError:
        pass
    else:
        raise AssertionError("audit draft was allowed to generate persistent stock")

# Little China: the Hong Kong Market is a container; Jayaraman's is corrected from the old
# weapons inference to local fish/seafood; prepared tea/food stays local; and The Seep is
# explicitly prevented from becoming commerce. Only the pharmacy receives generated stock.
little_source = load_json(ROOT / "data/worlds/night-city-2045/little-china-core.v1.json")
validate_document(little_source)
little_a = realize_document(little_source, engine)
little_b = realize_document(little_source, engine)
assert little_a == little_b, "Little China fixture realization must be deterministic"
little = {row["name"]: row for row in little_a["entities"]}
assert len(little) == 8
assert {name for name, row in little.items() if row.get("assortment")} == {
    "Ling Husan’s New China Pharmacy"
}

hong_kong = little["The Hong Kong Market"]
assert hong_kong["entity_type"] == "container"
assert hong_kong["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in hong_kong

jayaraman = little["Jayaraman’s"]
assert "assortment" not in jayaraman
assert jayaraman["local_offerings"][0]["offering_key"] == "fish-seafood"
assert jayaraman["parent_entity_id"] == "NC2045-LOC-LITTLE-CHINA-099-THE-HONG-KONG-MARKET"

assert "assortment" not in little["Yuenyang Tea Shop"]
assert little["Yuenyang Tea Shop"]["local_offerings"][0]["offering_key"] == "tea-food"
assert "assortment" not in little["The Bonesetter"]
assert little["The Bonesetter"]["services"][0]["service_key"] == "medical-treatment"
assert "assortment" not in little["The Little Red Book"]

pharmacy = little["Ling Husan’s New China Pharmacy"]
assert pharmacy["assortment"]
for row in pharmacy["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "Medical & Chemical"
    assert path[:2] != ["Medical & Chemical", "Street Drugs"]

prosperity = little["Prosperity Garden Tenements"]
assert prosperity["entity_type"] == "container"
assert prosperity["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in prosperity

seep = little["The Seep"]
assert seep["stock_policy"] == "NO_STOCK"
assert "assortment" not in seep
assert seep["audit"]["decision"] == "DOWNGRADE_CONTEXT"

# Reclamation Zone: the station delegates to its children. Source-specific cosmetics,
# artificial flowers and reclaimed jewellery remain local wares instead of being replaced by
# unrelated catalogue clothing/furniture. Earl's and the Underground Bodega are the only
# persistent catalogue-backed sellers in this batch.
reclamation_source = load_json(ROOT / "data/worlds/night-city-2045/reclamation-zone-core.v1.json")
validate_document(reclamation_source)
reclamation_a = realize_document(reclamation_source, engine)
reclamation_b = realize_document(reclamation_source, engine)
assert reclamation_a == reclamation_b, "Reclamation Zone fixture realization must be deterministic"
reclamation = {row["name"]: row for row in reclamation_a["entities"]}
assert len(reclamation) == 6
assert {name for name, row in reclamation.items() if row.get("assortment")} == {
    "Earl’s Second Hand Shop", "Underground Bodega"
}

station = reclamation["Reclamation Zone Station"]
assert station["entity_type"] == "container"
assert station["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in station

for name, key in [
    ("Carmen’s Cosmetics", "cosmetics-personal-style"),
    ("Forever Beautiful", "artificial-flowers-decor"),
    ("Forgotten Treasures", "reclaimed-scrap-jewellery"),
]:
    entity = reclamation[name]
    assert "assortment" not in entity
    assert entity["local_offerings"][0]["offering_key"] == key
    assert entity["parent_entity_id"] == "NC2045-LOC-RECLAMATION-ZONE-162-RECLAMATION-ZONE-STATION"

earls = reclamation["Earl’s Second Hand Shop"]
assert earls["assortment"]
for row in earls["assortment"]:
    root = engine.commercial_by_id[row["item_id"]]["classification_path"][0]
    assert root in {"General Equipment", "Electronics & Communications", "Weapons"}

bodega = reclamation["Underground Bodega"]
assert bodega["assortment"]
for row in bodega["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[:2] == ["Food, Drink & Consumables", "Foodstuffs"] or path[0] == "General Equipment"

print(
    "OK: Little China + Reclamation Zone source-review batches; "
    f"Little China entities={len(little)}, Reclamation Zone entities={len(reclamation)}"
)
