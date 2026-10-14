#!/usr/bin/env python3
"""Regression tests for Upper Marina + Downtown held-out Review Queue review."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = {
    "upper": ROOT / "data/worlds/night-city-2045/upper-marina-review-queue.v1.json",
    "downtown": ROOT / "data/worlds/night-city-2045/downtown-review-queue.v1.json",
}

realized = {}
for key, path in FILES.items():
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{key} Review Queue fixture realization must be deterministic"
    realized[key] = {row["name"]: row for row in a["entities"]}

upper = realized["upper"]
assert set(upper) == {
    "Bless Your Heart", "GraffitiX", "Kraken Line Water Taxis", "McCartney Cubes",
    "McCartney Field Stadium", "Morro Strand Yacht Club", "Night City Bubbles", "Quarantine",
}
assert upper["Kraken Line Water Taxis"]["services"][0]["price_eb"] == 20
assert upper["McCartney Cubes"]["entity_type"] == "service"
assert upper["McCartney Field Stadium"]["entity_type"] == "service"
assert upper["Morro Strand Yacht Club"]["entity_type"] == "service"
assert {row["service_key"] for row in upper["Night City Bubbles"]["services"]} == {
    "spa-services", "social-escort", "corporate-account"
}
assert {row["service_key"] for row in upper["Quarantine"]["services"]} == {
    "pub-hospitality", "fixit-fridays"
}
for row in upper.values():
    assert "assortment" not in row

downtown = realized["downtown"]
queue_candidates = {
    "Acacia Way", "Café Bouchon", "Clocktower Residences", "Goosetopia",
    "New Libertine Tower", "Studio Blocks A thru D", "West Hill Park",
}
assert queue_candidates <= set(downtown)
assert downtown["Acacia Way"]["entity_type"] == "context"
assert downtown["West Hill Park"]["entity_type"] == "context"
assert downtown["Goosetopia"]["entity_type"] == "local_vendor"
assert "assortment" not in downtown["Goosetopia"]
assert downtown["New Libertine Tower"]["entity_type"] == "container"
for name in {"GHP Architectural", "Gueller and Stravinsky", "Rael Sanschez Clinic"}:
    assert downtown[name]["parent_entity_id"] == "NC2045-LOC-DOWNTOWN-085-NEW-LIBERTINE-TOWER"
assert downtown["Studio Blocks A thru D"]["entity_type"] == "container"
for name in {"BlueRaven", "Lotos"}:
    assert downtown[name]["parent_entity_id"] == "NC2045-LOC-DOWNTOWN-086-STUDIO-BLOCKS-A-THRU-D"
    assert "assortment" not in downtown[name]
assert downtown["BlueRaven"]["services"][0]["service_key"] == "bespoke-weapon-customization"

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == set()

print(
    "OK: Upper Marina + Downtown held-out Review Queue review; "
    f"candidates=15, recovered_children={len(downtown) - 7}, stock-bearing={len(stock_bearers)}"
)
