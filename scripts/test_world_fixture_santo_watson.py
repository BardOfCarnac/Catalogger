#!/usr/bin/env python3
"""Regression tests for the Santo Domingo and Watson Development source-review batches."""
from pathlib import Path

from import_nc2045_audit_batch import import_batch
from world_fixture import WorldFixtureError, load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

# Both six-profile audit batches remain non-realizable drafts until the source-reviewed fixtures
# below explicitly confirm, narrow or split them.
for audit_rel in [
    "data/worlds/night-city-2045/import/santo-domingo-core.audit-v0.2.json",
    "data/worlds/night-city-2045/import/watson-development-core.audit-v0.2.json",
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

# Santo Domingo: containers stay containers, only source-supported permanent sellers receive
# persistent assortments, and Woodchipper's office is separated from the nearby recurring market.
santo_source = load_json(ROOT / "data/worlds/night-city-2045/santo-domingo-core.v1.json")
validate_document(santo_source)
santo_a = realize_document(santo_source, engine)
santo_b = realize_document(santo_source, engine)
assert santo_a == santo_b, "Santo Domingo fixture realization must be deterministic"
santo = {row["name"]: row for row in santo_a["entities"]}
assert len(santo) == 13
assert {name for name, row in santo.items() if row.get("assortment")} == {"Caitlin Market", "YoBro!"}

aldecaldo = santo["Aldecaldo Camp"]
assert aldecaldo["entity_type"] == "container"
assert aldecaldo["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in aldecaldo

bazaar = santo["Bazaar El Saber"]
assert bazaar["entity_type"] == "event_market"
assert bazaar["stock_policy"] == "EVENT_ONLY"
assert "assortment" not in bazaar
assert santo["Doc Spindler"]["parent_entity_id"] == bazaar["entity_id"]
assert santo["Doc Spindler"]["services"][0]["service_key"] == "ripperdoc-treatment-installation"

caitlin = santo["Caitlin Market"]
assert caitlin["assortment"]
for row in caitlin["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert (
        path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]
        or path[0] == "Weapons"
        or path[:2] == ["Ammunition & Ordnance", "Ammunition"]
    )

yobro = santo["YoBro!"]
assert yobro["assortment"]
assert {row["service_key"] for row in yobro["services"]} == {"firing-range", "firearms-community-events"}
for row in yobro["assortment"]:
    root = engine.commercial_by_id[row["item_id"]]["classification_path"][0]
    assert root in {"Weapons", "Ammunition & Ordnance"}

h4 = santo["Megabuilding H4"]
assert h4["entity_type"] == "container"
assert h4["stock_policy"] == "CHILDREN_ONLY"
for name in ["Bar of Gold", "Gatcha Hotel", "H4 Clinic", "Pink Mohawk"]:
    assert santo[name]["parent_entity_id"] == h4["entity_id"]
    assert "assortment" not in santo[name]

north = santo["Northern Light Supplies"]
assert north["entity_type"] == "channel"
assert north["stock_policy"] == "NO_STOCK"
assert north["distribution"]["channel"] == "vendit"
assert "assortment" not in north

wood = santo["Woodchipper’s Garage"]
market = santo["Woodchipper’s Night Market"]
assert wood["entity_type"] == "service"
assert wood["stock_policy"] == "NO_STOCK"
assert "assortment" not in wood
assert market["entity_type"] == "event_market"
assert market["parent_entity_id"] == wood["entity_id"]
assert market["stock_policy"] == "EVENT_ONLY"
assert "assortment" not in market

# Watson: H10 delegates to named children; brand outlets have exact catalogue gates; discount
# stock obeys the 100eb ceiling; Snack & Shack generates only the bodega slice of a mixed-use site.
watson_source = load_json(ROOT / "data/worlds/night-city-2045/watson-development-core.v1.json")
validate_document(watson_source)
watson_a = realize_document(watson_source, engine)
watson_b = realize_document(watson_source, engine)
assert watson_a == watson_b, "Watson Development fixture realization must be deterministic"
watson = {row["name"]: row for row in watson_a["entities"]}
assert len(watson) == 11
assert {name for name, row in watson.items() if row.get("assortment")} == {
    "Gibson Battlegear Outlet", "Hundred Under Haven", "Data Inc", "Snack & Shack", "Turbo Neon Motors"
}

gibson = watson["Gibson Battlegear Outlet"]
gibson_allow = {"VENDR-0343", "VENDR-0347"}
assert gibson["assortment"]
assert {row["item_id"] for row in gibson["assortment"]} <= gibson_allow
assert gibson["local_offerings"][0]["offering_key"] == "gibson-affordable-fashion-line"
assert gibson["shop"]["stocking_profile"]["brand_affinities"]["Gibson Battlegear"] == 20

hundred = watson["Hundred Under Haven"]
assert hundred["assortment"]
assert hundred["shop"]["stocking_profile"]["max_base_price"] == 100
for row in hundred["assortment"]:
    item = engine.items_by_id[row["item_id"]]
    price = engine._base_price(item)
    assert price is None or price <= 100

h10 = watson["Megabuilding H10"]
assert h10["entity_type"] == "container"
assert h10["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in h10
for name in ["98.2 Shiv FM", "Big H Casino", "Hammer Me Nail Salon", "United Martial Arts", "Watson Community College"]:
    assert watson[name]["parent_entity_id"] == h10["entity_id"]
    assert "assortment" not in watson[name]

data = watson["Data Inc"]
assert data["parent_entity_id"] == h10["entity_id"]
assert data["assortment"]
for row in data["assortment"]:
    root = engine.commercial_by_id[row["item_id"]]["classification_path"][0]
    assert root in {"Electronics & Communications", "NET & Netrunning"}

snack = watson["Snack & Shack"]
assert snack["assortment"]
for row in snack["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[:2] == ["Food, Drink & Consumables", "Foodstuffs"] or path[0] == "General Equipment"

turbo = watson["Turbo Neon Motors"]
turbo_allow = {"VENDR-0926", "VENDR-0929"}
assert turbo["assortment"]
assert {row["item_id"] for row in turbo["assortment"]} <= turbo_allow
assert turbo["shop"]["stocking_profile"]["brand_affinities"]["Turbo Neon Motors"] == 20
assert {row["service_key"] for row in turbo["services"]} == {
    "custom-parts-fabrication", "vehicle-modification", "custom-vehicle-build"
}

print(
    "OK: Santo Domingo + Watson Development source-review batches; "
    f"Santo entities={len(santo)}, Watson entities={len(watson)}"
)
