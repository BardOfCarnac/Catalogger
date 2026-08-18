#!/usr/bin/env python3
"""Regression tests for South Night City and The Glen source-review batches."""
from pathlib import Path

from import_nc2045_audit_batch import import_batch
from world_fixture import WorldFixtureError, load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

# Audit inputs remain non-realizable drafts until direct source review.
for audit_rel, expected in [
    ("data/worlds/night-city-2045/import/south-night-city-core.audit-v0.2.json", 3),
    ("data/worlds/night-city-2045/import/the-glen-core.audit-v0.2.json", 3),
]:
    audit_source = load_json(ROOT / audit_rel)
    draft = import_batch(audit_source)
    assert len(draft["entities"]) == expected
    assert draft["fixture_status"] == "audit_draft"
    validate_document(draft, allow_drafts=True)
    try:
        realize_document(draft, engine)
    except WorldFixtureError:
        pass
    else:
        raise AssertionError("audit draft was allowed to generate persistent stock")

# South Night City: Container Mart delegates to seven named children. Only the ordinary
# neighborhood bodega receives generic catalogue stock; source-specific craft, salon,
# dental, braindance and shaved-ice commerce remain local/service state.
south_source = load_json(ROOT / "data/worlds/night-city-2045/south-night-city-core.v1.json")
validate_document(south_source)
south_a = realize_document(south_source, engine)
south_b = realize_document(south_source, engine)
assert south_a == south_b, "South Night City fixture realization must be deterministic"
south = {row["name"]: row for row in south_a["entities"]}
assert len(south) == 8
assert {name for name, row in south.items() if row.get("assortment")} == {"Container Bodega"}

mart = south["Container Mart"]
assert mart["entity_type"] == "container"
assert mart["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in mart

for name in [
    "Ancestral Threads", "Chopper’s", "Container Bodega", "Getaway Tours",
    "Old Lady Stuff", "Panik", "SlushSlurp"
]:
    assert south[name]["parent_entity_id"] == "NC2045-LOC-SOUTH-NIGHT-CITY-141-CONTAINER-MART"

bodega = south["Container Bodega"]
assert bodega["assortment"]
for row in bodega["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "General Equipment" or path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]

old_lady = south["Old Lady Stuff"]
assert "assortment" not in old_lady
assert old_lady["local_offerings"][0]["offering_key"] == "fiber-craft-supplies"
assert old_lady["services"][0]["service_key"] == "armor-repair"

assert "assortment" not in south["Ancestral Threads"]
assert "assortment" not in south["Chopper’s"]
assert "assortment" not in south["Getaway Tours"]
assert "assortment" not in south["Panik"]
assert "assortment" not in south["SlushSlurp"]
assert south["SlushSlurp"]["local_offerings"][0]["price_eb"] == 5

# The Glen: direct review removes unsupported market/catalogue stock from Club Atlantis and
# Kasim's. Worthy Housing remains housing context, while the nearby named DRGS 247 branch is
# recovered as a source-established local seller instead of leaking commerce onto the housing.
glen_source = load_json(ROOT / "data/worlds/night-city-2045/the-glen-core.v1.json")
validate_document(glen_source)
glen_a = realize_document(glen_source, engine)
glen_b = realize_document(glen_source, engine)
assert glen_a == glen_b, "The Glen fixture realization must be deterministic"
glen = {row["name"]: row for row in glen_a["entities"]}
assert len(glen) == 4
assert not {name for name, row in glen.items() if row.get("assortment")}

atlantis = glen["Club Atlantis"]
assert atlantis["audit"]["decision"] == "REMOVE_UNSUPPORTED_EVENT_STOCK"
assert {row["offering_key"] for row in atlantis["local_offerings"]} == {
    "international-bar", "halo-drop"
}
assert next(row for row in atlantis["local_offerings"] if row["offering_key"] == "halo-drop")["price_eb"] == 100

kasims = glen["Kasim’s"]
assert "assortment" not in kasims
assert kasims["schedule"]["closed_day"] == "Friday"
prices = {row["offering_key"]: row.get("price_eb") for row in kasims["local_offerings"]}
assert prices["turkish-street-coffee"] == 10
assert prices["nargile-tobacco"] == 20

worthy = glen["Worthy Housing"]
assert worthy["stock_policy"] == "NO_STOCK"
assert "assortment" not in worthy
assert worthy["services"][0]["service_key"] == "fbc-housing"

drgs = glen["DRGS 247 (The Glen)"]
assert drgs["provenance"] == "CANON_NAMED"
assert "assortment" not in drgs
assert drgs["local_offerings"][0]["offering_key"] == "bulk-brain-solution"

print(
    "OK: South Night City + The Glen source-review batches; "
    f"South entities={len(south)}, Glen entities={len(glen)}"
)
