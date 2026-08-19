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


def has_relation(runtime: dict, source_id: str, target_id: str, relationship_type: str) -> bool:
    return any(
        row["source_entity_id"] == source_id
        and row["target_entity_id"] == target_id
        and row["relationship_type"] == relationship_type
        for row in runtime["relationships"]
    )


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
assert has_relation(little, fast_eddie, vertical, "contained_in")
fast_eddie_rel = next(row for row in little["relationships"] if row["source_entity_id"] == fast_eddie)
assert fast_eddie_rel["inferred_from"] == "parent_entity_id"
assert fast_eddie_rel["runtime_origin"] == "legacy_parent_fallback"

# T&C demonstrates why entity identity and behaviour are now separate. The legacy source type
# remains event_market for v0.2 consumers, but runtime identity is an outlet with event behaviour.
tc_stalls = "NC2045-EVENT-LITTLE-EUROPE-063-TORRELL-AND-CHIANG-MARKET-STALLS"
tc_shop = "NC2045-LOC-LITTLE-EUROPE-063-TORRELL-AND-CHIANG-S"
tc = next(row for row in little["entities"] if row["entity_id"] == tc_stalls)
assert tc["entity_type"] == "event_market"
assert tc["entity_kind"] == "outlet"
assert "event" in tc["capabilities"]
assert has_relation(little, tc_stalls, tc_shop, "operated_by")
assert not has_relation(little, tc_stalls, tc_shop, "contained_in")

# Mrs Suzuki's market is a real recurring event, but the legacy parent pointed to the bodega
# even though the event occurs elsewhere. Explicit operation therefore replaces fake containment.
suzuki_source = load("data/worlds/night-city-2045/old-japantown-core.v1.json")
suzuki = realize_runtime_document(suzuki_source, engine)
suzuki_event_id = "NC2045-EVT-OLD-JAPANTOWN-132-SUZUKI-MONTHLY-NIGHT-MARKET"
suzuki_bodega_id = "NC2045-LOC-OLD-JAPANTOWN-132-MRS-SUZUKI-S-BODEGA"
suzuki_event = next(row for row in suzuki["entities"] if row["entity_id"] == suzuki_event_id)
assert suzuki_event["entity_kind"] == "market_event"
assert {"event", "scheduled", "access_controlled"} <= set(suzuki_event["capabilities"])
assert has_relation(suzuki, suzuki_event_id, suzuki_bodega_id, "operated_by")
assert not has_relation(suzuki, suzuki_event_id, suzuki_bodega_id, "contained_in")

# Runtime registry migrations cover several distinct semantics without mutating v0.2 fixtures.
bella = realize_runtime_document(load("data/worlds/night-city-2045/downtown-core.v1.json"), engine)
assert has_relation(
    bella,
    "NC2045-EVENT-DOWNTOWN-082-BELLA-VISTA-NIGHT-MARKET",
    "NC2045-LOC-DOWNTOWN-082-BELLA-VISTA-MARKET",
    "market_event_at",
)

great_river = realize_runtime_document(
    load("data/worlds/night-city-2045/upper-marina-retail-capable.v1.json"), engine
)
assert has_relation(
    great_river,
    "NC2045-CHN-UPPER-MARINA-076-GREAT-RIVER",
    "NC2045-LOC-UPPER-MARINA-076-ZIGGURAT-CORPORATE-TERRACE",
    "fulfills_for",
)

holliday = realize_runtime_document(load("data/worlds/night-city-2045/new-westbrook-core.v1.json"), engine)
assert has_relation(
    holliday,
    "NC2045-CHN-NEW-WESTBROOK-216-HOLLIDAY-ROTATING-VENDORS",
    "NC2045-LOC-NEW-WESTBROOK-216-HOLLIDAY-MARKET",
    "appears_at",
)

faisal = realize_runtime_document(
    load("data/worlds/night-city-2045/watson-development-retail-capable.v1.json"), engine
)
assert has_relation(
    faisal,
    "NC2045-CHN-WATSON-DEVELOPMENT-188-FAISAL-FACTORY-OUTPUT",
    "NC2045-LOC-WATSON-DEVELOPMENT-188-FAISAL-S-CUSTOMS",
    "operated_by",
)

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

registry = load("data/worlds/night-city-2045/runtime-relationships.v0.3.json")
registry_rows = sum(len(rows) for rows in registry["fixtures"].values())
assert registry["format_version"] == "0.3.0"
assert registry["world_id"] == "night-city-2045"
assert registry_rows == 21, registry_rows

# Project the complete reviewed corpus. This is the key compatibility promise: v0.3 changes
# representation, not source content, stock realization or entity identity.
reviewed_fixtures = 0
reviewed_entities = 0
legacy_parent_links = 0
runtime_relationships = 0
runtime_explicit_relationships = 0
runtime_inferred_relationships = 0

for path in sorted(WORLD_DIR.glob("*.v1.json")):
    source = json.loads(path.read_text(encoding="utf-8"))
    doc = normalize_document(source)
    if doc.get("fixture_status") != "source_reviewed":
        continue

    reviewed_fixtures += 1
    reviewed_entities += len(doc["entities"])
    legacy_parent_links += sum(bool(row.get("parent_entity_id")) for row in doc["entities"])

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
    inferred = sum(row.get("inferred_from") == "parent_entity_id" for row in relations)
    runtime_inferred_relationships += inferred
    runtime_explicit_relationships += len(relations) - inferred
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
assert runtime_relationships == 218, runtime_relationships
assert runtime_explicit_relationships == 23, runtime_explicit_relationships
assert runtime_inferred_relationships == 195, runtime_inferred_relationships

print(
    "OK: v0.3 runtime projection; "
    f"fixtures={reviewed_fixtures}, entities={reviewed_entities}, "
    f"relationships={runtime_relationships}, explicit={runtime_explicit_relationships}, "
    f"legacy_fallbacks={runtime_inferred_relationships}"
)
