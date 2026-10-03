#!/usr/bin/env python3
"""Regression tests for normalized customer-to-business purchase policies in runtime v0.3."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from world_fixture import WorldFixtureError, normalize_document
from world_runtime import realize_runtime_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"
engine = WorldStockEngine()


def load(name: str) -> dict:
    return json.loads((WORLD_DIR / name).read_text(encoding="utf-8"))


def entity(runtime: dict, entity_id: str) -> dict:
    return next(row for row in runtime["entities"] if row["entity_id"] == entity_id)


# A legacy object-shaped buyback rule becomes the same runtime list shape as newer rows.
old_combat_source = load("old-combat-zone-core.v1.json")
old_combat = realize_runtime_document(old_combat_source, engine)
baskin = entity(old_combat, "NC2045-OUT-OLD-COMBAT-ZONE-171-BASKIN-BOOKS")
assert baskin["purchase_profile"] == [{
    "purchase_key": "book-buyback",
    "label": "Buys recovered books from local children and scavengers",
    "price_eb_each": 1,
}]
assert "purchase_policy" in baskin["capabilities"]

# Source list-shaped bounty terms remain one normalized purchase row.
watson_source = load("watson-development-context-only.v1.json")
watson = realize_runtime_document(watson_source, engine)
pochinko = entity(watson, "NC2045-LOC-WATSON-DEVELOPMENT-193-THE-POCHINKO-CARNIVAL")
assert pochinko["purchase_profile"] == [{
    "purchase_key": "bozo-nose-bounty",
    "label": "Bounty for a genuine Bozo nose",
    "price_eb": 10,
}]
assert "purchase_policy" in pochinko["capabilities"]

# Open-ended procurement keeps the source's non-numeric pricing note rather than inventing a rate.
little_china_source = load("little-china-context-only.v1.json")
little_china = realize_runtime_document(little_china_source, engine)
aquarium = entity(little_china, "NC2045-LOC-LITTLE-CHINA-101-RICHARD-NIGHT-AQUARIUM")
assert aquarium["purchase_profile"] == [{
    "purchase_key": "aquarium-specimen-acquisition",
    "label": "Freelance acquisition of aquarium specimens",
    "price_note": "Management may pay freelancers; no fixed rate is stated.",
}]
assert "purchase_policy" in aquarium["capabilities"]

# Malformed purchase data fails closed instead of silently granting a purchase capability.
bad = copy.deepcopy(watson_source)
bad_pochinko = next(
    row for row in bad["entities"]
    if row["entity_id"] == "NC2045-LOC-WATSON-DEVELOPMENT-193-THE-POCHINKO-CARNIVAL"
)
bad_pochinko["purchase_policy"] = "sometimes"
try:
    realize_runtime_document(bad, engine)
except WorldFixtureError:
    pass
else:
    raise AssertionError("malformed purchase_policy was accepted")

# Corpus-wide invariant: exactly three source purchase policies become exactly three profiles
# and three purchase-capable runtime entities.
source_purchase_entities = 0
runtime_purchase_profiles = 0
runtime_purchase_capabilities = 0

for path in sorted(WORLD_DIR.glob("*.v1.json")):
    source = json.loads(path.read_text(encoding="utf-8"))
    doc = normalize_document(source)
    if doc.get("fixture_status") != "source_reviewed":
        continue

    source_purchase_entities += sum("purchase_policy" in row for row in doc["entities"])
    runtime = realize_runtime_document(source, engine)
    runtime_purchase_profiles += sum("purchase_profile" in row for row in runtime["entities"])
    runtime_purchase_capabilities += sum(
        "purchase_policy" in row["capabilities"] for row in runtime["entities"]
    )

assert source_purchase_entities == 3, source_purchase_entities
assert runtime_purchase_profiles == 3, runtime_purchase_profiles
assert runtime_purchase_capabilities == 3, runtime_purchase_capabilities

print(
    "OK: runtime purchase profiles; "
    f"source_entities={source_purchase_entities}, profiles={runtime_purchase_profiles}, "
    f"capabilities={runtime_purchase_capabilities}"
)
