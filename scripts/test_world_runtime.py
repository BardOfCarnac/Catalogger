#!/usr/bin/env python3
"""Regression tests for the Vend-R v0.3 runtime projection."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from world_fixture import WorldFixtureError, normalize_document, realize_document
from world_runtime import (
    CAPABILITIES,
    ENTITY_KINDS,
    RELATIONSHIP_TYPES,
    normalize_relationships,
    realize_runtime_document,
)
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"
engine = WorldStockEngine()


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


# A normal containment link remains losslessly available through the parent fallback.
little_source = load("data/worlds/night-city-2045/little-europe-remainder.v1.json")
little = realize_runtime_document(little_source, engine)
little_by_name = {row["name"]: row for row in little["entities"]}
assert little["format_version"] == "0.3.0"
assert little["source_format_version"] == "0.2.0"
assert little_by_name["Everything and More"]["entity_kind"] == "outlet"
assert "catalog_stock" in little_by_name["Everything and More"]["capabilities"]
assert little_by_name["Fast Eddie"]["entity_kind"] == "service_point"
assert "services" in little_by_name["Fast Eddie"]["capabilities"]
fast_eddie = "NC2045-OUT-LITTLE-EUROPE-058-FAST-EDDIE-GUIDE"
vertical = "NC2045-LOC-LITTLE-EUROPE-058-CONTINENTAL-BRANDS-VERTICAL-NEIGHBORHOOD"
assert {
    "relationship_type": "contained_in",
    "source_entity_id": fast_eddie,
    "target_entity_id": vertical,
    "inferred_from": "parent_entity_id",
} in little["relationships"]

# T&C demonstrates why entity identity and behaviour are now separate. The legacy source type
# remains event_market for v0.2 consumers, but runtime identity is an outlet with event behaviour.
tc_stalls = "NC2045-EVENT-LITTLE-EUROPE-063-TORRELL-AND-CHIANG-MARKET-STALLS"
tc_shop = "NC2045-LOC-LITTLE-EUROPE-063-TORRELL-AND-CHIANG-S"
tc = next(row for row in little["entities"] if row["entity_id"] == tc_stalls)
assert tc["entity_type"] == "event_market"
assert tc["entity_kind"] == "outlet"
assert "event" in tc["capabilities"]
tc_rels = [row for row in little["relationships"] if row["source_entity_id"] == tc_stalls]
assert any(row["relationship_type"] == "operated_by" and row["target_entity_id"] == tc_shop for row in tc_rels)
assert not any(row["relationship_type"] == "contained_in" and row["target_entity_id"] == tc_shop for row in tc_rels)

# Mrs Suzuki's market is a real recurring event, but the legacy parent pointed to the bodega
# even though the event occurs elsewhere. Explicit operation therefore replaces fake containment.
suzuki_source = load("data/worlds/night-city-2045/old-japantown-core.v1.json")
suzuki = realize_runtime_document(suzuki_source, engine)
suzuki_event_id = "NC2045-EVT-OLD-JAPANTOWN-132-SUZUKI-MONTHLY-NIGHT-MARKET"
suzuki_bodega_id = "NC2045-LOC-OLD-JAPANTOWN-132-MRS-SUZUKI-S-BODEGA"
suzuki_event = next(row for row in suzuki["entities"] if row["entity_id"] == suzuki_event_id)
assert suzuki_event["entity_kind"] == "market_event"
assert {"event", "scheduled", "access_controlled"} <= set(suzuki_event["capabilities"])
suzuki_rels = [row for row in suzuki["relationships"] if row["source_entity_id"] == suzuki_event_id]
assert any(row["relationship_type"] == "operated_by" and row["target_entity_id"] == suzuki_bodega_id for row in suzuki_rels)
assert not any(row["relationship_type"] == "contained_in" and row["target_entity_id"] == suzuki_bodega_id for row in suzuki_rels)

# Relationship validation fails closed rather than silently accepting an ad-hoc vocabulary.
bad = copy.deepcopy(suzuki_source)
bad["relationships"].append({
    "relationship_type": "sort_of_near",
    "source_entity_id": suzuki_event_id,
    "target_entity_id": suzuki_bodega_id,
})
try:
    normalize_relationships(bad)
except WorldFixtureError:
    pass
else:
    raise AssertionError("unknown relationship type was accepted")

# Project the complete reviewed corpus. This is the key compatibility promise: v0.3 changes
# representation, not source content, stock realization or entity identity.
reviewed_fixtures = 0
reviewed_entities = 0
legacy_parent_links = 0
explicit_relationships = 0
runtime_relationships = 0
runtime_inferred_relationships = 0

for path in sorted(WORLD_DIR.glob("*.v1.json")):
    source = json.loads(path.read_text(encoding="utf-8"))
    doc = normalize_document(source)
    if doc.get("fixture_status") != "source_reviewed":
        continue

    reviewed_fixtures += 1
    reviewed_entities += len(doc["entities"])
    legacy_parent_links += sum(bool(row.get("parent_entity_id")) for row in doc["entities"])
    explicit_relationships += len(doc.get("relationships", []))

    v02 = realize_document(source, engine)
    v03_a = realize_runtime_document(source, engine)
    v03_b = realize_runtime_document(source, engine)
    assert v03_a == v03_b, f"runtime projection is not deterministic: {path.name}"

    ids_v02 = {row["entity_id"] for row in v02["entities"]}
    ids_v03 = {row["entity_id"] for row in v03_a["entities"]}
    assert ids_v03 == ids_v02, f"runtime projection changed entity identity: {path.name}"
    assert len(v03_a["entities"]) == len(v02["entities"])

    for entity in v03_a["entities"]:
        assert entity["entity_kind"] in ENTITY_KINDS
        assert set(entity["capabilities"]) <= CAPABILITIES

    relations = v03_a["relationships"]
    runtime_relationships += len(relations)
    runtime_inferred_relationships += sum(row.get("inferred_from") == "parent_entity_id" for row in relations)
    for rel in relations:
        assert rel["relationship_type"] in RELATIONSHIP_TYPES
        assert rel["source_entity_id"] in ids_v03
        if not rel.get("external_target"):
            assert rel["target_entity_id"] in ids_v03

    # Every old parent link still has one typed runtime edge for the same pair, but an explicit
    # relationship may correctly change its meaning away from contained_in.
    for entity in doc["entities"]:
        parent = entity.get("parent_entity_id")
        if not parent:
            continue
        matching = [
            rel for rel in relations
            if rel["source_entity_id"] == entity["entity_id"]
            and rel["target_entity_id"] == parent
        ]
        assert matching, f"legacy parent relationship was lost: {path.name} / {entity['entity_id']}"

assert reviewed_fixtures == 91, reviewed_fixtures
assert reviewed_entities == 700, reviewed_entities
assert legacy_parent_links == 218, legacy_parent_links
assert explicit_relationships == 2, explicit_relationships
assert runtime_relationships == 218, runtime_relationships
assert runtime_inferred_relationships == 216, runtime_inferred_relationships

print(
    "OK: v0.3 runtime projection; "
    f"fixtures={reviewed_fixtures}, entities={reviewed_entities}, "
    f"relationships={runtime_relationships}, explicit={explicit_relationships}, "
    f"legacy_fallbacks={runtime_inferred_relationships}"
)
