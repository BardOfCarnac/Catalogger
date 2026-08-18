#!/usr/bin/env python3
"""Regression tests for the remaining Night City 2045 RETAIL_CAPABLE review fixtures."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = [
    "kabuki-retail-capable.v1.json",
    "old-combat-zone-retail-capable.v1.json",
    "old-japantown-retail-capable.v1.json",
    "pacifica-playground-retail-capable.v1.json",
    "the-glen-retail-capable.v1.json",
    "charter-hill-retail-capable.v1.json",
    "little-europe-retail-capable.v1.json",
    "upper-marina-retail-capable.v1.json",
    "heywood-docks-retail-capable.v1.json",
    "heywood-industrial-zone-retail-capable.v1.json",
    "little-china-retail-capable.v1.json",
    "new-westbrook-retail-capable.v1.json",
    "playland-by-the-sea-lands-retail-capable.v1.json",
    "rancho-coronado-retail-capable.v1.json",
]

fixtures = {}
all_entities = {}
for filename in FILES:
    path = ROOT / "data/worlds/night-city-2045" / filename
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{filename} realization must be deterministic"
    fixtures[filename] = a
    for row in a["entities"]:
        assert row["entity_id"] not in all_entities, row["entity_id"]
        all_entities[row["entity_id"]] = row

by_name = {row["name"]: row for row in all_entities.values()}

# Only three entities in this tranche should generate persistent catalogue stock.
stock_bearers = {row["name"] for row in all_entities.values() if row.get("assortment")}
assert stock_bearers == {"Matsura Food Products", "The Cutting Edge", "2A"}

matsura = by_name["Matsura Food Products"]
for line in matsura["assortment"]:
    path = engine.commercial_by_id[line["item_id"]]["classification_path"]
    assert path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]

cutting = by_name["The Cutting Edge"]
for line in cutting["assortment"]:
    path = engine.commercial_by_id[line["item_id"]]["classification_path"]
    assert path[0] == "Fashion & Personal"
assert {s["service_key"] for s in cutting["services"]} == {
    "hair-salon", "nail-salon", "fashionware-salon"
}

two_a = by_name["2A"]
for line in two_a["assortment"]:
    path = engine.commercial_by_id[line["item_id"]]["classification_path"]
    assert path[0] == "Weapons"
assert two_a["services"][0]["service_key"] == "gun-range"

# Kabuki: service/identity-shop distinctions survive source review.
assert by_name["Delphi X"]["entity_type"] == "service"
assert "assortment" not in by_name["Houou"]
assert by_name["Houou"]["local_offerings"][0]["offering_key"] == "fake-sin-cards"

# Old Combat Zone: opportunistic/local trade is not inflated into generated shelves.
assert by_name["Flasher’s Corner"]["entity_type"] == "local_vendor"
assert "assortment" not in by_name["Flasher’s Corner"]
assert by_name["The Underground"]["stock_policy"] == "NO_STOCK"
assert by_name["The Underground"]["supply_relationships"][0]["target"] == "Mrs. Suzuki’s Bodega"

# Old Japantown and Pacifica retain source-local digital/event/hospitality behavior.
assert "assortment" not in by_name["Lovely Drone Heroes Café"]
assert "assortment" not in by_name["Neo Galaxy Cards and Comics"]
assert by_name["Pacifica Parties"]["parent_entity_id"] == by_name["The Ascension"]["entity_id"]
assert by_name["Volkodav Racetrack"]["schedule"]["availability"] == "24/7 races"
assert by_name["The XX (The Twenty)"]["schedule"]["opens"] == "15:00"

# Glen: civic/event commerce is split from actual storefront commerce.
assert by_name["Hall of Justice"]["entity_type"] == "context"
assert by_name["Hall of Justice Concession Vendors"]["entity_type"] == "channel"
assert by_name["Hall of Justice Concession Vendors"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert by_name["Merrill, Asukaga & Finch Offices"]["entity_type"] == "container"
assert by_name["Merrill, Asukaga & Finch Offices"]["stock_policy"] == "CHILDREN_ONLY"

# Charter Hill: exact named drug range and service-only crèche.
drgs = by_name["DRGS 247"]
assert {o["offering_key"] for o in drgs["local_offerings"]} >= {
    "boost", "prime-time", "synthcoke", "white-lace"
}
assert by_name["Your Next Big Crèche"]["entity_type"] == "service"

# Little Europe: second-hand cyberware and the tech Night Market remain separate children.
assert by_name["80/20"]["parent_entity_id"] == by_name["Chopper’s"]["entity_id"]
assert by_name["3-Piece’s Joint"]["entity_type"] == "event_market"
assert by_name["3-Piece’s Joint"]["stock_policy"] == "EVENT_ONLY"

# Upper Marina: restricted salvage shop plus delivery channel, no invented shelves.
forge = by_name["The Forge"]
assert forge["access_model"] == "friendly-only"
assert "assortment" not in forge
assert by_name["Great River"]["entity_type"] == "channel"
assert by_name["Great River"]["stock_policy"] == "NO_STATIC_INVENTORY"

# Remaining singles are venue/context/channel/local-shop corrections.
assert by_name["Warehouse 13 Night Market"]["parent_entity_id"] == by_name["Warehouse 13"]["entity_id"]
assert by_name["Ziggurat Warehouses"]["entity_type"] == "context"
assert by_name["Ziggurat Warehouses"]["stock_policy"] == "NO_STOCK"
assert by_name["Ling Po Imports"]["entity_type"] == "channel"
assert by_name["Ling Po Imports"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert by_name["Rocklin Augmentics Campus"]["stock_policy"] == "CHILDREN_ONLY"
assert by_name["Hidalgo Gallery"]["parent_entity_id"] == by_name["Rocklin Augmentics Campus"]["entity_id"]
assert by_name["Classique Corsets"]["local_offerings"][0]["price_eb"] == 100
assert by_name["The Henhouse"]["entity_type"] == "service"
assert "assortment" not in by_name["The Henhouse"]

print(
    "OK: remaining RETAIL_CAPABLE source-review fixtures; "
    f"fixtures={len(FILES)}, entities={len(all_entities)}, stock-bearing={len(stock_bearers)}"
)
