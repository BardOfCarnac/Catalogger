#!/usr/bin/env python3
"""Regression tests for source-defined market profiles in runtime v0.3."""
from __future__ import annotations

import json
from pathlib import Path

from world_fixture import normalize_document
from world_runtime import realize_runtime_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"
engine = WorldStockEngine()


def load(name: str) -> dict:
    return json.loads((WORLD_DIR / name).read_text(encoding="utf-8"))


def entity(runtime: dict, entity_id: str) -> dict:
    return next(row for row in runtime["entities"] if row["entity_id"] == entity_id)


santo_source = load("santo-domingo-core.v1.json")
santo = realize_runtime_document(santo_source, engine)

bazaar = entity(santo, "NC2045-OUT-SANTO-DOMINGO-266-BAZAAR-EL-SABER")
assert bazaar["market_profile"] == {
    "archetype_id": "night-market-stall",
    "channels": ["nomad", "street", "specialist"],
    "vendor_rotation": "high",
}
assert bazaar["entity_kind"] == "market_event"
assert "event" in bazaar["capabilities"]

woodchipper = entity(santo, "NC2045-EVT-SANTO-DOMINGO-270-WOODCHIPPER-NIGHT-MARKET")
assert woodchipper["market_profile"] == {
    "archetype_id": "night-market-stall",
    "channels": ["nomad", "street", "grey_market"],
    "vendor_rotation": "high",
}
assert woodchipper["entity_kind"] == "market_event"
assert "event" in woodchipper["capabilities"]

port = realize_runtime_document(load("port-of-night-city-core.v1.json"), engine)
dock13 = entity(port, "NC2045-EVT-PORT-OF-NIGHT-CITY-152-DOCK-13-NIGHT-MARKET")
assert dock13["market_profile"] == {
    "archetype_id": "night-market-stall",
    "channels": ["pawn", "street", "grey_market", "nomad"],
    "vendor_rotation": "high",
}
assert dock13["entity_kind"] == "market_event"
assert "event" in dock13["capabilities"]

# An event can be source-established without a merchandise profile. Mrs. Suzuki's monthly
# Night Market deliberately remains such an event because the source does not define its wares.
suzuki = realize_runtime_document(load("old-japantown-core.v1.json"), engine)
suzuki_event = entity(suzuki, "NC2045-EVT-OLD-JAPANTOWN-132-SUZUKI-MONTHLY-NIGHT-MARKET")
assert "event" in suzuki_event["capabilities"]
assert "market_profile" not in suzuki_event

# Corpus-wide invariant: the three reviewed market-profile rows already share one shape, so
# runtime preserves them instead of introducing a redundant second normalized representation.
source_market_profiles = 0
runtime_market_profiles = 0
runtime_profiled_market_events = 0

for path in sorted(WORLD_DIR.glob("*.v1.json")):
    source = json.loads(path.read_text(encoding="utf-8"))
    doc = normalize_document(source)
    if doc.get("fixture_status") != "source_reviewed":
        continue

    source_market_profiles += sum("market_profile" in row for row in doc["entities"])
    runtime = realize_runtime_document(source, engine)
    runtime_market_profiles += sum("market_profile" in row for row in runtime["entities"])
    runtime_profiled_market_events += sum(
        "market_profile" in row and row["entity_kind"] == "market_event"
        for row in runtime["entities"]
    )

assert source_market_profiles == 3, source_market_profiles
assert runtime_market_profiles == 3, runtime_market_profiles
assert runtime_profiled_market_events == 3, runtime_profiled_market_events

print(
    "OK: runtime market profiles; "
    f"source_profiles={source_market_profiles}, runtime_profiles={runtime_market_profiles}, "
    f"profiled_market_events={runtime_profiled_market_events}"
)
