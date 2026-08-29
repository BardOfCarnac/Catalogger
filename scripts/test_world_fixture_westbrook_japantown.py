#!/usr/bin/env python3
"""Regression tests for New Westbrook and Old Japantown source-review batches."""
from pathlib import Path

from import_nc2045_audit_batch import import_batch
from world_fixture import WorldFixtureError, load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

for audit_rel in [
    "data/worlds/night-city-2045/import/new-westbrook-core.audit-v0.2.json",
    "data/worlds/night-city-2045/import/old-japantown-core.audit-v0.2.json",
]:
    audit_source = load_json(ROOT / audit_rel)
    draft = import_batch(audit_source)
    assert len(draft["entities"]) == 2
    assert draft["fixture_status"] == "audit_draft"
    validate_document(draft, allow_drafts=True)
    try:
        realize_document(draft, engine)
    except WorldFixtureError:
        pass
    else:
        raise AssertionError("audit draft was allowed to generate persistent stock")

# New Westbrook: Canalside Plaza delegates to explicit tenants. Armory Pawn and the Oasis
# branch carry persistent catalogue stock; Holliday Market remains the stable event place while
# its unnamed rotating vendors own the generated event assortment.
west_source = load_json(ROOT / "data/worlds/night-city-2045/new-westbrook-core.v1.json")
validate_document(west_source)
west_a = realize_document(west_source, engine)
west_b = realize_document(west_source, engine)
assert west_a == west_b, "New Westbrook fixture realization must be deterministic"
west = {row["name"]: row for row in west_a["entities"]}
assert len(west) == 11
assert {name for name, row in west.items() if row.get("assortment")} == {
    "Oasis (Canalside Plaza)", "Armory Pawn Shop", "Holliday Market rotating vendors"
}

plaza = west["Canalside Plaza"]
assert plaza["entity_type"] == "container"
assert plaza["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in plaza
plaza_id = plaza["entity_id"]
for name in [
    "Sizzle Jams Talent Agency", "Rick Shaw’s Taxi Service", "Capitán Caliente (Canalside Plaza)",
    "Hardware Value", "The Mane Event", "Oasis (Canalside Plaza)", "Takayuki Law", "Armory Pawn Shop"
]:
    assert west[name]["parent_entity_id"] == plaza_id

armory = west["Armory Pawn Shop"]
assert armory["assortment"]
for row in armory["assortment"]:
    root = engine.commercial_by_id[row["item_id"]]["classification_path"][0]
    assert root in {"General Equipment", "Electronics & Communications", "Weapons", "Armor & Protection"}

canalside_oasis = west["Oasis (Canalside Plaza)"]
assert canalside_oasis["assortment"]
for row in canalside_oasis["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "General Equipment" or path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]

holliday = west["Holliday Market"]
assert holliday["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in holliday
rotating = west["Holliday Market rotating vendors"]
assert rotating["parent_entity_id"] == holliday["entity_id"]
assert rotating["provenance"] == "CANON_IMPLIED"
assert rotating["assortment"]

# Old Japantown: Mrs. Suzuki's catalogue-backed shelf is food-only, with Shroomer fungi kept
# as local wares. Her monthly invitation Night Market does not receive invented merchandise.
# White Side is localized to source-supported scavver trade, and Honest Hiro is promoted from
# RETAIL_CAPABLE as a source-explicit used-vehicle dealer without inventing exact car models.
oj_source = load_json(ROOT / "data/worlds/night-city-2045/old-japantown-core.v1.json")
validate_document(oj_source)
oj_a = realize_document(oj_source, engine)
oj_b = realize_document(oj_source, engine)
assert oj_a == oj_b, "Old Japantown fixture realization must be deterministic"
oj = {row["name"]: row for row in oj_a["entities"]}
assert len(oj) == 4
assert {name for name, row in oj.items() if row.get("assortment")} == {"Mrs. Suzuki’s Bodega"}

hiro = oj["Honest Hiro’s Used Cars"]
assert "assortment" not in hiro
assert hiro["local_offerings"][0]["minimum_ready_inventory"] == 12
assert hiro["supply_relationships"][0]["supplier"] == "Steel Vaqueros"

suzuki = oj["Mrs. Suzuki’s Bodega"]
assert suzuki["assortment"]
assert suzuki["local_offerings"][0]["offering_key"] == "shroomer-mushrooms-lichen"
for row in suzuki["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]

night_market = oj["Mrs. Suzuki’s monthly Night Market"]
assert night_market["parent_entity_id"] == suzuki["entity_id"]
assert night_market["provenance"] == "CANON_IMPLIED"
assert night_market["access_model"] == "invite_only"
assert night_market["schedule"]["frequency"] == "monthly"
assert night_market["stock_policy"] == "NO_STOCK"
assert "assortment" not in night_market

white = oj["White Side"]
assert "assortment" not in white
assert {row["offering_key"] for row in white["local_offerings"]} == {
    "non-irradiated-water", "kibble", "scavver-trade"
}
assert white["audit"]["decision"] == "CORRECT_TO_SOURCE_LOCAL_TRADE"

print(
    "OK: New Westbrook + Old Japantown source-review batches; "
    f"New Westbrook entities={len(west)}, Old Japantown entities={len(oj)}"
)
