#!/usr/bin/env python3
"""Regression tests for the final seven Night City 2045 CORE_RETAIL districts."""
from pathlib import Path

from import_nc2045_audit_batch import import_batch
from world_fixture import WorldFixtureError, load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

BATCHES = [
    ("executive-zone", "Executive Zone"),
    ("heywood-docks", "Heywood Docks"),
    ("heywood-industrial-zone", "Heywood Industrial Zone"),
    ("norcal-military-base", "NorCal Military Base"),
    ("playland-by-the-sea-lands", "Playland by the Sea Lands"),
    ("port-of-night-city", "Port of Night City"),
    ("the-hot-zone", "The Hot Zone"),
]

# Every final audit row remains a draft until the reviewed fixture replaces its inference.
for slug, _district in BATCHES:
    source = load_json(ROOT / f"data/worlds/night-city-2045/import/{slug}-core.audit-v0.2.json")
    draft = import_batch(source)
    assert len(draft["entities"]) == 1
    assert draft["fixture_status"] == "audit_draft"
    validate_document(draft, allow_drafts=True)
    try:
        realize_document(draft, engine)
    except WorldFixtureError:
        pass
    else:
        raise AssertionError(f"{slug} audit draft was allowed to generate persistent stock")

realized = {}
for slug, district in BATCHES:
    source = load_json(ROOT / f"data/worlds/night-city-2045/{slug}-core.v1.json")
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{district} fixture realization must be deterministic"
    realized[slug] = {row["name"]: row for row in a["entities"]}

# Executive Zone: premium Oasis stock is constrained, while source-explicit basics/flowers
# and delivery remain separate factual offerings/services.
execz = realized["executive-zone"]
oasis = execz["Oasis (Exec Zone)"]
assert oasis["assortment"]
for row in oasis["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] in {
        "General Equipment", "Fashion & Personal", "Electronics & Communications"
    } or path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]
assert {row["offering_key"] for row in oasis["local_offerings"]} == {
    "kibble-scop-staples", "fresh-cut-flowers"
}
assert {row["service_key"] for row in oasis["services"]} == {
    "agent-ordering", "exec-zone-drone-delivery"
}

# Heywood Docks: Piccolo is only the two source-named consumables, attached to SK Securities.
docks = realized["heywood-docks"]
assert set(docks) == {"SK Securities", "Piccolo"}
assert "assortment" not in docks["SK Securities"]
assert "assortment" not in docks["Piccolo"]
assert docks["Piccolo"]["parent_entity_id"] == "NC2045-LOC-HEYWOOD-DOCKS-243-SK-SECURITIES"
assert {row["offering_key"] for row in docks["Piccolo"]["local_offerings"]} == {"kibble", "smash"}

# Heywood Industrial Zone: the Furnace bodega is stock-bearing; the parent and rotating carts
# are not flattened into that shelf.
industrial = realized["heywood-industrial-zone"]
ironworks = industrial["The Old Ironworks Building"]
assert ironworks["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in ironworks
furnace = industrial["The Furnace"]
assert furnace["assortment"]
for row in furnace["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "General Equipment" or path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]
carts = industrial["Old Ironworks Street Carts"]
assert carts["provenance"] == "CANON_IMPLIED"
assert carts["stock_policy"] == "NO_STATIC_INVENTORY"
assert "assortment" not in carts

# NorCal PX: generated stock follows the explicit goods categories, not the audit's military
# spillover; source-named concessions/services remain children.
base = realized["norcal-military-base"]
px = base["Post Exchange (PX)"]
assert px["assortment"]
for row in px["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] in {"Weapons", "Fashion & Personal", "Electronics & Communications"} or path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]
assert "media-selection" in {row["offering_key"] for row in px["local_offerings"]}
for child in ["Hot Dingo", "Estero Bay Barber Shop", "COG Credit Union"]:
    assert base[child]["parent_entity_id"] == "NC2045-LOC-NORCAL-MILITARY-BASE-183-POST-EXCHANGE-PX"
assert {row["offering_key"] for row in base["Hot Dingo"]["local_offerings"]} == {"scopdog", "koff-pop"}

# Playland: preserve the actual souvenir range and scooter rental rather than substituting
# generic catalogue merchandise.
playland = realized["playland-by-the-sea-lands"]
gift = playland["Grand Junction Gift Shop"]
assert "assortment" not in gift
souvenir = gift["local_offerings"][0]
assert souvenir["price_eb_min"] == 20 and souvenir["price_eb_max"] == 100
rental = gift["services"][0]
assert rental["service_key"] == "scooter-rental" and rental["price_eb"] == 50

# Port: Dock 13's vague salvage storefront stays local and its occasional Night Market is a
# separate event rather than one permanent department-driven assortment.
port = realized["port-of-night-city"]
dock13 = port["Dock 13"]
assert "assortment" not in dock13
assert dock13["local_offerings"][0]["offering_key"] == "repackaged-dock-salvage"
market = port["Dock 13 Night Market"]
assert market["parent_entity_id"] == "NC2045-LOC-PORT-OF-NIGHT-CITY-152-DOCK-13"
assert market["stock_policy"] == "EVENT_ONLY"
assert market["schedule"]["frequency"] == "occasional"

# Hot Zone: Totentanz has ad-hoc trade, but direct review does not support a formal Night Market
# or stable generated shelf.
hot = realized["the-hot-zone"]
totentanz = hot["Totentanz"]
assert "assortment" not in totentanz
assert not any(row["entity_type"] == "event_market" for row in realized["the-hot-zone"].values())
assert {row["offering_key"] for row in totentanz["local_offerings"]} == {
    "ad-hoc-tech-bargains", "ad-hoc-drug-bargains", "discounted-smash"
}
assert totentanz["audit"]["decision"] == "REMOVE_UNSUPPORTED_EVENT_STOCK_AND_LOCALIZE_TRADE"

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == {"Oasis (Exec Zone)", "The Furnace", "Post Exchange (PX)"}

print(
    "OK: final seven NC2045 core districts source-reviewed; "
    f"districts={len(BATCHES)}, stock-bearing={len(stock_bearers)}"
)
