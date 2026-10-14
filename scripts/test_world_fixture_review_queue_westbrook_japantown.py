#!/usr/bin/env python3
"""Regression tests for New Westbrook + Old Japantown held-out Review Queue review."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = {
    "westbrook": ROOT / "data/worlds/night-city-2045/new-westbrook-review-queue.v1.json",
    "japantown": ROOT / "data/worlds/night-city-2045/old-japantown-review-queue.v1.json",
}

realized = {}
for key, path in FILES.items():
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{key} Review Queue fixture realization must be deterministic"
    realized[key] = {row["name"]: row for row in a["entities"]}

westbrook = realized["westbrook"]
assert set(westbrook) == {
    "Denya Jinja", "Dilly’s", "Network 54 Plaza", "Silver Pixel Cloud",
    "ValueMart Village", "WorldSat Communications Offices",
}
assert westbrook["Denya Jinja"]["entity_type"] == "hybrid"
assert "assortment" not in westbrook["Denya Jinja"]
assert {row["price_eb"] for row in westbrook["Dilly’s"]["services"] if row["service_key"].startswith("room-")} == {20, 50, 100}
assert westbrook["Network 54 Plaza"]["entity_type"] == "container"
assert westbrook["Network 54 Plaza"]["stock_policy"] == "NO_STOCK"
assert westbrook["Silver Pixel Cloud"]["entity_type"] == "service"
assert westbrook["ValueMart Village"]["services"][0]["service_key"] == "low-cost-housing-rental"
assert westbrook["WorldSat Communications Offices"]["entity_type"] == "context"

japantown = realized["japantown"]
assert set(japantown) == {
    "The Basement", "Highcourt Plaza Hotel", "Imperial Bank", "Oni-Yama Jail", "Unnamed Cube Hotel",
}
basement = japantown["The Basement"]
assert basement["entity_type"] == "local_vendor"
assert {row["visibility"] for row in basement["local_offerings"]} == {"public", "trusted-customers"}
assert "assortment" not in basement
assert japantown["Highcourt Plaza Hotel"]["entity_type"] == "service"
assert japantown["Imperial Bank"]["services"][0]["service_key"] == "payday-loan"
assert japantown["Oni-Yama Jail"]["entity_type"] == "context"
assert japantown["Oni-Yama Jail"]["stock_policy"] == "NO_STOCK"
assert japantown["Unnamed Cube Hotel"]["entity_type"] == "service"

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == set()

print("OK: New Westbrook + Old Japantown held-out Review Queue review; candidates=11, stock-bearing=0")
