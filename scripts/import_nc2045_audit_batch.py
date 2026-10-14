#!/usr/bin/env python3
"""Normalize a Night City 2045 commercial-audit batch into draft world entities.

This importer deliberately does *not* create live stock. It converts the v0.2 audit profile
rows into the generic world-fixture graph and marks the result ``audit_draft``. A human/source
review must promote/correct the draft before build_world_fixture.py is allowed to realize it.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from world_fixture import DRAFT, load_json, validate_document

ROOT = Path(__file__).resolve().parents[1]


def split_pipe(value: Any) -> list[str]:
    if not value:
        return []
    return [part for part in str(value).split("|") if part]


def slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value or "entity"


def draft_stocking(profile: dict[str, Any]) -> dict[str, Any] | None:
    archetype = profile.get("primary_archetype")
    if not archetype:
        return None
    overrides: dict[str, Any] = {}
    mapping = {
        "primary_departments": split_pipe(profile.get("primary_departments")),
        "secondary_departments": split_pipe(profile.get("secondary_departments")),
    }
    for key, value in mapping.items():
        if value:
            overrides[key] = value
    for key in ("breadth_profile", "depth_profile", "supply_capability", "price_tier_center", "pricing_style"):
        value = profile.get(key)
        if value:
            overrides[key] = value
    max_price = profile.get("max_base_price_eb")
    if max_price not in (None, ""):
        overrides["max_base_price"] = max_price
    channels = split_pipe(profile.get("market_channel_override"))
    if channels:
        overrides["channel_weights"] = {channel: 4 for channel in channels}
    return {
        "archetype_id": archetype,
        "seed": f"nc2045:{slug(profile['name'])}:audit-v0.2",
        "overrides": overrides,
    }


def entity_type(profile: dict[str, Any]) -> str:
    mode = profile.get("stock_mode")
    return {
        "DIRECT_SELLER": "seller",
        "AGGREGATE_CONTAINER": "container",
        "SERVICE_ONLY": "service",
        "HYBRID_DIRECT_EVENT": "hybrid",
        "EVENT_MARKET": "event_market",
        "DISTRIBUTION_CHANNEL": "channel",
        "CHAIN_TEMPLATE": "template",
        "CHANNEL_TEMPLATE": "template",
        "REFERENCE_ONLY": "reference",
    }.get(mode, "unclassified")


def profile_to_entity(profile: dict[str, Any]) -> dict[str, Any]:
    entity: dict[str, Any] = {
        "entity_id": profile["entity_id"],
        "name": profile["name"],
        "entity_type": entity_type(profile),
        "district": profile.get("district"),
        "book_page": profile.get("book_page"),
        "provenance": profile.get("provenance"),
        "source_ref": profile.get("source_ref"),
        "review_status": DRAFT,
        "audit": {
            "source_profile_version": "0.2",
            "entity_level": profile.get("entity_level"),
            "stock_mode": profile.get("stock_mode"),
            "parent_stock_policy": profile.get("parent_stock_policy"),
            "audit_action": profile.get("audit_action"),
            "assignment_confidence": profile.get("assignment_confidence"),
            "candidate_rule_summary": profile.get("candidate_rule_summary"),
            "modelling_note": profile.get("modelling_note"),
        },
    }
    if profile.get("parent_entity_id"):
        entity["parent_entity_id"] = profile["parent_entity_id"]
    stocking = draft_stocking(profile)
    if stocking and profile.get("stock_mode") in {"DIRECT_SELLER", "HYBRID_DIRECT_EVENT"}:
        entity["stocking"] = stocking
    return entity


def import_batch(source: dict[str, Any]) -> dict[str, Any]:
    profiles = source.get("profiles", [])
    if not profiles:
        raise ValueError("audit batch has no profiles")
    result = {
        "format_version": "0.2.0",
        "world_id": source.get("world_id", "night-city-2045"),
        "fixture_id": f"{source['batch_id']}:draft",
        "fixture_status": DRAFT,
        "provenance": "AUDIT_DERIVED",
        "source": {
            "title": "Night City 2045 commercial audit",
            "profile_version": source.get("source_profile_version", "0.2"),
        },
        "entities": [profile_to_entity(profile) for profile in profiles],
    }
    validate_document(result, allow_drafts=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert an NC2045 audit batch to a draft world fixture")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    result = import_batch(load_json(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for entity in result["entities"]:
        counts[entity["entity_type"]] = counts.get(entity["entity_type"], 0) + 1
    print(f"Imported {len(result['entities'])} audit entities -> {result['fixture_id']}")
    print("Types: " + ", ".join(f"{key}={counts[key]}" for key in sorted(counts)))
    print("Draft only: source review is required before stock realization")


if __name__ == "__main__":
    main()
