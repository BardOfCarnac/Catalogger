#!/usr/bin/env python3
"""Vend-R v0.3 runtime projection for source-reviewed world fixtures.

The reviewed v0.2 fixtures are editorial/source data and remain the source of truth. This
module projects them into a runtime graph with two deliberately orthogonal concepts:

* ``entity_kind`` describes what an entity *is* in the world.
* ``capabilities`` describe what that entity can *do* commercially.

Typed relationships live beside the entities. Existing ``parent_entity_id`` links remain
valid v0.2 input and are projected as ``contained_in`` only when a more specific explicit
relationship has not been supplied for the same source/target pair. This lets the city move
away from overloaded parent links incrementally without rewriting the reviewed corpus.
"""
from __future__ import annotations

import copy
from typing import Any

from world_fixture import WorldFixtureError, normalize_document, realize_document
from world_stock_engine import WorldStockEngine

RUNTIME_VERSION = "0.3.0"

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


def normalize_relationships(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Return explicit typed relationships plus safe legacy-parent fallbacks.

    An explicit relationship for a source/target pair suppresses the automatic
    ``parent_entity_id -> contained_in`` fallback for that pair. This is the key migration
    rule: old fixtures continue to work, while overloaded parent links can be corrected one
    relationship at a time without breaking v0.2 consumers.
    """
    doc = normalize_document(source)
    entities = doc["entities"]
    ids = {entity["entity_id"] for entity in entities}

    relationships: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    explicit_pairs: set[tuple[str, str]] = set()

    for raw in doc.get("relationships", []):
        rel = copy.deepcopy(raw)
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
