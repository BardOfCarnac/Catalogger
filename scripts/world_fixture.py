#!/usr/bin/env python3
"""Generic source-defined world-fixture realization for Vend-R.

A fixture is editorial world data, not generated shop state. Source-reviewed entities may
carry a ``stocking`` block which the WorldStockEngine realizes into a persistent assortment
and cycle-0 stock. Audit drafts are intentionally blocked from realization until reviewed.

The preferred v0.2 fixture shape is a flat ``entities`` graph with parent_entity_id links.
For the Kaito pilot, the loader also accepts the earlier single-location + vendors shape so
that the first fixture remains a useful regression case while the city is migrated in batches.
"""
from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

from world_stock_engine import WorldStockEngine

WORLD_NAMESPACE = uuid.UUID("b4e83129-88f1-5c25-8f52-807b93e5bd57")
REVIEWED = "source_reviewed"
DRAFT = "audit_draft"


class WorldFixtureError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_shop_id(entity_id: str) -> str:
    return str(uuid.uuid5(WORLD_NAMESPACE, entity_id))


def _legacy_to_flat(source: dict[str, Any]) -> dict[str, Any]:
    """Normalize the Kaito v0.1 shape into the v0.2 flat entity graph."""
    location = copy.deepcopy(source["location"])
    parent_id = location["entity_id"]
    location_entity = {
        "entity_id": parent_id,
        "name": location["name"],
        "entity_type": "container",
        "district": location.get("district"),
        "map_no": location.get("map_no"),
        "book_page": source.get("source", {}).get("page"),
        "provenance": source.get("provenance", "CANON_NAMED"),
        "source_ref": source.get("source", {}).get("ref"),
        "source_summary": location.get("source_summary"),
        "stock_policy": location.get("stock_policy", "CHILDREN_ONLY"),
        "schedule": copy.deepcopy(location.get("schedule")),
        "review_status": REVIEWED,
    }
    entities = [location_entity]
    for vendor in source.get("vendors", []):
        row = copy.deepcopy(vendor)
        row["parent_entity_id"] = parent_id
        row.setdefault("district", location.get("district"))
        row.setdefault("book_page", source.get("source", {}).get("page"))
        row.setdefault("provenance", source.get("provenance", "CANON_NAMED"))
        row.setdefault("source_ref", source.get("source", {}).get("ref"))
        row.setdefault("review_status", REVIEWED)
        mode = row.get("commercial_mode", "service_only")
        if mode in {"catalog_stock", "catalog_and_service", "catalog_and_local_wares"}:
            row["entity_type"] = "seller"
        elif mode == "local_wares":
            row["entity_type"] = "local_vendor"
        elif mode == "service_only":
            row["entity_type"] = "service"
        else:
            row["entity_type"] = "hybrid"
        entities.append(row)

    return {
        "format_version": "0.2.0",
        "world_id": source["world_id"],
        "fixture_id": f"{parent_id}:legacy-normalized",
        "fixture_status": REVIEWED,
        "provenance": source.get("provenance", "CANON_NAMED"),
        "source": copy.deepcopy(source.get("source", {})),
        "entities": entities,
    }


def normalize_document(source: dict[str, Any]) -> dict[str, Any]:
    if "entities" in source:
        return copy.deepcopy(source)
    if "location" in source and "vendors" in source:
        return _legacy_to_flat(source)
    raise WorldFixtureError("fixture must contain entities or legacy location+vendors")


def validate_document(source: dict[str, Any], allow_drafts: bool = False) -> dict[str, Any]:
    doc = normalize_document(source)
    if not doc.get("world_id"):
        raise WorldFixtureError("missing world_id")
    if not doc.get("fixture_id"):
        raise WorldFixtureError("missing fixture_id")
    status = doc.get("fixture_status", DRAFT)
    if status not in {REVIEWED, DRAFT}:
        raise WorldFixtureError(f"unknown fixture_status: {status}")
    if status != REVIEWED and not allow_drafts:
        raise WorldFixtureError("audit_draft fixtures cannot be realized before source review")

    entities = doc.get("entities")
    if not isinstance(entities, list) or not entities:
        raise WorldFixtureError("fixture entities must be a non-empty list")

    ids: set[str] = set()
    for entity in entities:
        eid = entity.get("entity_id")
        if not eid:
            raise WorldFixtureError("entity missing entity_id")
        if eid in ids:
            raise WorldFixtureError(f"duplicate entity_id: {eid}")
        ids.add(eid)
        if not entity.get("name"):
            raise WorldFixtureError(f"entity missing name: {eid}")
        if not entity.get("entity_type"):
            raise WorldFixtureError(f"entity missing entity_type: {eid}")
        review = entity.get("review_status", status)
        if review not in {REVIEWED, DRAFT}:
            raise WorldFixtureError(f"unknown review_status for {eid}: {review}")
        if entity.get("stocking"):
            stocking = entity["stocking"]
            if not stocking.get("archetype_id") or not stocking.get("seed"):
                raise WorldFixtureError(f"stocking block needs archetype_id and seed: {eid}")
            if review != REVIEWED and not allow_drafts:
                raise WorldFixtureError(f"draft entity cannot generate stock: {eid}")
        if entity.get("entity_type") == "container" and entity.get("stocking"):
            raise WorldFixtureError(f"container cannot carry direct stocking block: {eid}")

    for entity in entities:
        parent = entity.get("parent_entity_id")
        if parent and parent not in ids and not entity.get("external_parent"):
            raise WorldFixtureError(
                f"parent_entity_id {parent!r} for {entity['entity_id']} is not in fixture"
            )
    return doc


def _realize_stocking(
    engine: WorldStockEngine,
    doc: dict[str, Any],
    entity: dict[str, Any],
) -> dict[str, Any]:
    realized = copy.deepcopy(entity)
    stocking = realized.pop("stocking", None)
    if not stocking:
        return realized

    shop_id = stable_shop_id(entity["entity_id"])
    context = engine.make_context(
        stocking["archetype_id"],
        stocking["seed"],
        shop_id=shop_id,
        overrides=stocking.get("overrides", {}),
    )
    bundle = engine.generate(context)
    realized["shop"] = {
        "id": shop_id,
        "name": entity["name"],
        "source_entity_id": entity["entity_id"],
        "parent_entity_id": entity.get("parent_entity_id"),
        "district": entity.get("district"),
        "provenance": entity.get("provenance", doc.get("provenance")),
        "source_ref": entity.get("source_ref") or doc.get("source", {}).get("ref"),
        "archetype_id": stocking["archetype_id"],
        "seed": stocking["seed"],
        "stocking_profile": copy.deepcopy(context),
    }
    realized["assortment"] = bundle["assortment"]
    realized["stock"] = bundle["stock"]
    realized["state"] = bundle["state"]
    return realized


def realize_document(
    source: dict[str, Any],
    engine: WorldStockEngine | None = None,
) -> dict[str, Any]:
    doc = validate_document(source, allow_drafts=False)
    engine = engine or WorldStockEngine()
    result = {
        "format_version": "0.2.0",
        "world_id": doc["world_id"],
        "fixture_id": doc["fixture_id"],
        "fixture_status": REVIEWED,
        "provenance": doc.get("provenance"),
        "source": copy.deepcopy(doc.get("source", {})),
        "entities": [],
    }
    for entity in doc["entities"]:
        result["entities"].append(_realize_stocking(engine, doc, entity))
    return result


def summary_lines(engine: WorldStockEngine, fixture: dict[str, Any]) -> list[str]:
    entities = fixture["entities"]
    stock_entities = [row for row in entities if row.get("assortment")]
    lines = [
        f"{fixture['fixture_id']}: entities={len(entities)}, stock-bearing={len(stock_entities)}"
    ]
    for entity in entities:
        assortment = entity.get("assortment", [])
        stock = entity.get("stock", [])
        if assortment:
            names = [engine.items_by_id[row["item_id"]]["name"] for row in stock[:8]]
            preview = ", ".join(names) if names else "temporarily no cycle-0 stock"
            lines.append(
                f"- {entity['name']}: {len(assortment)} persistent lines / "
                f"{len(stock)} cycle-0 stock; {preview}"
            )
        else:
            lines.append(
                f"- {entity['name']}: type={entity['entity_type']}, "
                f"local={len(entity.get('local_offerings', []))}, "
                f"services={len(entity.get('services', []))}"
            )
    return lines
