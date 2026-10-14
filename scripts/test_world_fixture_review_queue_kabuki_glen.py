#!/usr/bin/env python3
"""Regression tests for Kabuki + The Glen held-out Review Queue review."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = {
    "kabuki": ROOT / "data/worlds/night-city-2045/kabuki-review-queue.v1.json",
    "glen": ROOT / "data/worlds/night-city-2045/the-glen-review-queue.v1.json",
}

realized = {}
for key, path in FILES.items():
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{key} Review Queue fixture realization must be deterministic"
    realized[key] = {row["name"]: row for row in a["entities"]}

kabuki = realized["kabuki"]
queue_candidates = {
    "Cyborg Station", "Kabuki Ceremonial Hall", "Nakagawa Kabuki Theater", "No-Tell Motel",
    "Segotari HQ/EXCEL-1", "Tengen Towers", "Tyger Works Tower",
}
assert queue_candidates <= set(kabuki)
assert kabuki["Cyborg Station"]["entity_type"] == "service"
assert kabuki["Kabuki Ceremonial Hall"]["entity_type"] == "container"
assert kabuki["Sankai-tei"]["parent_entity_id"] == "NC2045-LOC-KABUKI-203-KABUKI-CEREMONIAL-HALL"
assert kabuki["No-Tell Motel"]["services"][0]["price_eb"] == 10
assert kabuki["No-Tell Motel"]["services"][1]["price_eb"] == 100
assert next(row for row in kabuki["Segotari HQ/EXCEL-1"]["services"] if row["service_key"] == "excel1-entry")["price_eb"] == 20
assert kabuki["Tengen Towers"]["entity_type"] == "container"
for name in {"Kiroshi Retail & Showroom", "Kendachi Retail & Showroom", "Tengen Towers Cyberware Clinic"}:
    assert kabuki[name]["parent_entity_id"] == "NC2045-LOC-KABUKI-206-TENGEN-TOWERS"
    assert "assortment" not in kabuki[name]
assert kabuki["Tyger Works Tower"]["entity_type"] == "container"
for name in {"Tyger Cab", "Tyger Eats", "Ameku Clinic", "Yagami Law Offices"}:
    assert kabuki[name]["parent_entity_id"] == "NC2045-LOC-KABUKI-206-TYGER-WORKS-TOWER"
assert kabuki["Tyger Eats"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert kabuki["Ameku Clinic"]["access_model"] == "tyger-claws-only"
assert kabuki["Yagami Law Offices"]["access_model"] == "tyger-claws-only"

glen = realized["glen"]
assert set(glen) == {
    "Archer & Li", "City Hall", "EuroBank", "NCPD Precinct #1", "Night City News Today",
    "Seafoam", "World Stock Exchange",
}
assert glen["City Hall"]["entity_type"] == "context"
assert glen["EuroBank"]["entity_type"] == "service"
assert glen["NCPD Precinct #1"]["entity_type"] == "hybrid"
assert glen["NCPD Precinct #1"]["schedule"]["kind"] == "monthly"
assert "assortment" not in glen["NCPD Precinct #1"]
assert glen["Night City News Today"]["services"][0]["service_key"] == "freelance-report-purchasing"
assert glen["Seafoam"]["entity_type"] == "service"
assert glen["World Stock Exchange"]["schedule"]["kind"] == "always_open"

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == set()

print(
    "OK: Kabuki + The Glen held-out Review Queue review; "
    f"candidates=14, recovered_children={len(kabuki) - 7}, stock-bearing=0"
)
