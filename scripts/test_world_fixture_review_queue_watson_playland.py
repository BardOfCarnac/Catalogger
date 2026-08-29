#!/usr/bin/env python3
"""Regression tests for the first held-out Review Queue source-review batch."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = {
    "watson": ROOT / "data/worlds/night-city-2045/watson-development-review-queue.v1.json",
    "playland": ROOT / "data/worlds/night-city-2045/playland-by-the-sea-lands-review-queue.v1.json",
}

realized = {}
for key, path in FILES.items():
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{key} Review Queue fixture realization must be deterministic"
    realized[key] = {row["name"]: row for row in a["entities"]}

watson = realized["watson"]
watson_candidates = {
    "Akagi-ryu Karate", "Canadian Consulate", "Ebunike Docks", "The Fork", "HTown",
    "Megabuilding H11", "Morgan’s", "NCPD Precinct #3", "Oumei-ji Temple",
    "Petrochem Offices", "SovOil Offices", "Trauma Team Corporate Living Center",
    "UnoMas Mexican Bar & Grill",
}
assert watson_candidates <= set(watson)
assert watson["Akagi-ryu Karate"]["entity_type"] == "service"
for name in {"Canadian Consulate", "Ebunike Docks", "HTown"}:
    assert watson[name]["entity_type"] == "context"
    assert "assortment" not in watson[name]
assert watson["The Fork"]["entity_type"] == "container"
assert watson["Megabuilding H11"]["entity_type"] == "container"

h11_children = {
    "Big H Casino", "Data Inc", "Hammer Me Nail Salon", "United Martial Arts",
    "Watson Community College", "Delta 777", "Divine Tastes", "Iron Spirit",
    "Savage Docs North",
}
for name in h11_children:
    assert watson[name]["parent_entity_id"] == "NC2045-LOC-WATSON-DEVELOPMENT-191-MEGABUILDING-H11"
assert watson["Data Inc"]["assortment"]
for row in watson["Data Inc"]["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "Electronics & Communications"
    assert path[:2] != ["Electronics & Communications", "Software & Apps"]

morgan = watson["Morgan’s"]
assert "assortment" not in morgan
assert {row["visibility"] for row in morgan["local_offerings"]} == {"public", "regular-customers"}
assert watson["The Blue Ranger"]["parent_entity_id"] == "NC2045-LOC-WATSON-DEVELOPMENT-191-NCPD-PRECINCT-3"
assert "assortment" not in watson["The Blue Ranger"]
assert watson["Oumei-ji Street Food Stalls"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert watson["Petrochem Museum & Gift Shop"]["parent_entity_id"] == "NC2045-LOC-WATSON-DEVELOPMENT-192-PETROCHEM-OFFICES"
assert watson["SovOil Museum & Gift Shop"]["parent_entity_id"] == "NC2045-LOC-WATSON-DEVELOPMENT-194-SOVOIL-OFFICES"
assert watson["Trauma Team Corporate Living Center"]["access_model"] == "employees-and-families"
assert next(row for row in watson["UnoMas Mexican Bar & Grill"]["local_offerings"] if row["offering_key"] == "mexican-beer")["price_eb"] == 10

playland = realized["playland"]
playland_candidates = {
    "Island Dreams Hotel", "Smash Bar & Grill", "Wharf Club", "Wharf Hotel", "Grand Hotel",
    "GunMart Museum of Movie Weapons (B)", "Horror Classics Buffet Theatre", "Autumn Palace Hotel",
    "Lovers Café", "Playland Amphitheatre & Reflection Deck (A)", "Bioexotic Cat Café",
    "Boba World", "Kibble Cakes",
}
assert set(playland) == playland_candidates
assert playland["Wharf Club"]["entity_type"] == "context"
assert playland["Wharf Club"]["stock_policy"] == "NO_STOCK"
assert playland["Island Dreams Hotel"]["services"][0]["price_eb"] == 200
assert playland["Wharf Hotel"]["services"][0]["price_eb"] == 500
assert playland["Grand Hotel"]["services"][0]["price_eb"] == 250
assert playland["Autumn Palace Hotel"]["services"][0]["price_eb"] == 350
assert next(row for row in playland["Playland Amphitheatre & Reflection Deck (A)"]["services"] if row["service_key"] == "visitor-photography")["price_eb"] == 10
assert next(row for row in playland["Bioexotic Cat Café"]["local_offerings"] if row["offering_key"] == "cafe-drink-snack")["price_eb"] == 20
assert playland["Boba World"]["local_offerings"][0]["price_eb"] == 10
assert playland["Kibble Cakes"]["local_offerings"][0]["price_eb"] == 10
assert "assortment" not in playland["GunMart Museum of Movie Weapons (B)"]

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == {"Data Inc"}

print(
    "OK: first held-out Review Queue batch; "
    f"candidates=26, recovered_children={len(watson) - 13}, stock-bearing={len(stock_bearers)}"
)
