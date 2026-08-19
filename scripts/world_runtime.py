#!/usr/bin/env python3
"""Vend-R v0.3 runtime projection for source-reviewed world fixtures.

The reviewed v0.2 fixtures are editorial/source data and remain the source of truth. This
module projects them into a runtime graph with two deliberately orthogonal concepts:

* ``entity_kind`` describes what an entity *is* in the world.
* ``capabilities`` describe what that entity can *do* commercially.

Typed relationships live beside the entities. Existing ``parent_entity_id`` links remain
valid v0.2 input and are projected as ``contained_in`` only when a more specific explicit
relationship has not been supplied for the same source/target pair. Runtime-only migration
overrides may also live in ``data/worlds/<world>/runtime-relationships.v0.3.json`` so the
reviewed editorial fixtures do not need to be rewritten merely to correct runtime semantics.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from world_fixture import WorldFixtureError, normalize_document, realize_document
from world_stock_engine import WorldStockEngine

RUNTIME_VERSION = "0.3.0"
ROOT = Path(__file__).resolve().parents[1]

ENTITY_KINDS = {
    "place",
    "outlet",
    "vendor",
    "service_point",
    "market_event",
    "channel",
    "chain",
    "template",
    "reference",
    "unclassified",
}

KIND_BY_LEGACY_TYPE = {
    "container": "place",
    "context": "place",
    "seller": "outlet",
    "hybrid": "outlet",
    "local_vendor": "vendor",
    "service": "service_point",
    "event_market": "market_event",
    "channel": "channel",
    "template": "template",
    "reference": "reference",
    "unclassified": "unclassified",
}

CAPABILITY_ORDER = (
    "catalog_stock",
    "local_wares",
    "services",
    "event",
    "distribution",
    "scheduled",
    "access_controlled",
    "purchase_policy",
)
CAPABILITIES = set(CAPABILITY_ORDER)

RELATIONSHIP_TYPES = {
    "contained_in",
    "appears_at",
    "operated_by",
    "service_point_for",
    "chain_branch_of",
    "market_event_at",
    "supplies",
    "fulfills_for",
}


def derive_entity_kind(entity: dict[str, Any]) -> str:
    """Project a stable runtime kind from a reviewed v0.2 entity.

    ``runtime_kind`` is an intentionally narrow migration escape hatch for a source-reviewed
    entity whose legacy ``entity_type`` encoded behaviour rather than identity. Most fixtures
    require no override.
    """
    override = entity.get("runtime_kind")
    if override is not None:
        if override not in ENTITY_KINDS:
            raise WorldFixtureError(
                f"unknown runtime_kind for {entity.get('entity_id', '<unknown>')}: {override}"
            )
        return override

    legacy = entity.get("entity_type", "unclassified")
    return KIND_BY_LEGACY_TYPE.get(legacy, "unclassified")


def derive_capabilities(entity: dict[str, Any]) -> list[str]:
    """Derive orthogonal runtime capabilities from source or realized entity fields."""
    found: set[str] = set()

    if entity.get("stocking") or entity.get("assortment") or entity.get("shop"):
        found.add("catalog_stock")
    if entity.get("local_offerings"):
        found.add("local_wares")
    if entity.get("services"):
        found.add("services")
    if (
        entity.get("entity_type") == "event_market"
        or entity.get("event_profile")
        or entity.get("market_profile")
        or entity.get("stock_policy") == "EVENT_ONLY"
    ):
        found.add("event")
    if entity.get("entity_type") == "channel" or entity.get("distribution"):
        found.add("distribution")
    if entity.get("schedule"):
        found.add("scheduled")
    if entity.get("access_model") or entity.get("access"):
        found.add("access_controlled")
    if entity.get("purchase_policy"):
        found.add("purchase_policy")

    for cap in entity.get("runtime_capabilities_add", []):
        if cap not in CAPABILITIES:
            raise WorldFixtureError(
                f"unknown runtime capability for {entity.get('entity_id', '<unknown>')}: {cap}"
            )
        found.add(cap)
    for cap in entity.get("runtime_capabilities_remove", []):
        if cap not in CAPABILITIES:
            raise WorldFixtureError(
                f"unknown runtime capability for {entity.get('entity_id', '<unknown>')}: {cap}"
            )
        found.discard(cap)

    return [cap for cap in CAPABILITY_ORDER if cap in found]


def runtime_relationship_overrides(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Load runtime-only typed relationship migrations for one reviewed fixture.

    The registry is optional. It deliberately keys by ``fixture_id`` so runtime semantics can
    evolve without editing the source-reviewed v0.2 fixture. Relationship validation still
    happens in ``normalize_relationships`` against the fixture's actual entity IDs.
    """
    world_id = doc.get("world_id")
    fixture_id = doc.get("fixture_id")
    if not world_id or not fixture_id:
        return []

    path = ROOT / "data" / "worlds" / world_id / "runtime-relationships.v0.3.json"
    if not path.exists():
        return []

    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("world_id") != world_id:
        raise WorldFixtureError(
            f"runtime relationship registry world mismatch: {registry.get('world_id')} != {world_id}"
        )
    if registry.get("format_version") != RUNTIME_VERSION:
        raise WorldFixtureError(
            "runtime relationship registry version mismatch: "
            f"{registry.get('format_version')} != {RUNTIME_VERSION}"
        )

    fixtures = registry.get("fixtures", {})
    if not isinstance(fixtures, dict):
        raise WorldFixtureError("runtime relationship registry 'fixtures' must be an object")
    rows = fixtures.get(fixture_id, [])
    if not isinstance(rows, list):
        raise WorldFixtureError(
            f"runtime relationship registry fixture {fixture_id!r} must contain a list"
        )
    return copy.deepcopy(rows)


def normalize_relationships(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Return typed relationships plus safe legacy-parent fallbacks.

    Relationships can be explicitly embedded in a reviewed fixture or supplied by the v0.3
    runtime migration registry. Either form suppresses the automatic
    ``parent_entity_id -> contained_in`` fallback for the same source/target pair. This is the
    key migration rule: old fixtures continue to work while overloaded parent links are
    corrected incrementally and without changing v0.2 consumer data.
    """
    doc = normalize_document(source)
    entities = doc["entities"]
    ids = {entity["entity_id"] for entity in entities}

    relationships: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    explicit_pairs: set[tuple[str, str]] = set()

    embedded = [(copy.deepcopy(rel), "fixture") for rel in doc.get("relationships", [])]
    migrated = [(copy.deepcopy(rel), "runtime_registry") for rel in runtime_relationship_overrides(doc)]

    for rel, origin in embedded + migrated:
        rel_type = rel.get("relationship_type")
        source_id = rel.get("source_entity_id")
        target_id = rel.get("target_entity_id")
        if rel_type not in RELATIONSHIP_TYPES:
            raise WorldFixtureError(f"unknown relationship_type: {rel_type}")
        if source_id not in ids:
            raise WorldFixtureError(f"relationship source is not in fixture: {source_id}")
        if not target_id:
            raise WorldFixtureError(f"relationship missing target for {source_id}")
        if target_id not in ids and not rel.get("external_target"):
            raise WorldFixtureError(
                f"relationship target {target_id!r} is not in fixture and not external"
            )
        key = (rel_type, source_id, target_id)
        if key in seen:
            raise WorldFixtureError(f"duplicate relationship: {key}")
        seen.add(key)
        explicit_pairs.add((source_id, target_id))
        rel.setdefault("runtime_origin", origin)
        relationships.append(rel)

    for entity in entities:
        source_id = entity["entity_id"]
        target_id = entity.get("parent_entity_id")
        if not target_id or (source_id, target_id) in explicit_pairs:
            continue
        if target_id not in ids and not entity.get("external_parent"):
            raise WorldFixtureError(
                f"legacy parent {target_id!r} for {source_id} is not in fixture"
            )
        key = ("contained_in", source_id, target_id)
        if key in seen:
            continue
        seen.add(key)
        rel = {
            "relationship_type": "contained_in",
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "inferred_from": "parent_entity_id",
            "runtime_origin": "legacy_parent_fallback",
        }
        if target_id not in ids:
            rel["external_target"] = True
        relationships.append(rel)

    return relationships


def realize_runtime_document(
    source: dict[str, Any],
    engine: WorldStockEngine | None = None,
) -> dict[str, Any]:
    """Realize a reviewed v0.2 fixture as a deterministic v0.3 runtime graph."""
    source_doc = normalize_document(source)
    realized = realize_document(source, engine)

    runtime_entities: list[dict[str, Any]] = []
    for entity in realized["entities"]:
        row = copy.deepcopy(entity)
        # Read migration overrides from the source entity because realization deliberately
        # preserves most source fields but the source remains authoritative here.
        source_entity = next(
            item for item in source_doc["entities"] if item["entity_id"] == entity["entity_id"]
        )
        row["entity_kind"] = derive_entity_kind(source_entity)
        row["capabilities"] = derive_capabilities(row)
        runtime_entities.append(row)

    result = {
        "format_version": RUNTIME_VERSION,
        "source_format_version": source_doc.get("format_version", "0.2.0"),
        "world_id": realized["world_id"],
        "fixture_id": realized["fixture_id"],
        "fixture_status": realized["fixture_status"],
        "provenance": realized.get("provenance"),
        "source": copy.deepcopy(realized.get("source", {})),
        "entities": runtime_entities,
        "relationships": normalize_relationships(source),
    }
    return result
