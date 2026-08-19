#!/usr/bin/env python3
"""Describe the v0.3 Vend-R runtime projection across the reviewed Night City corpus."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from world_fixture import normalize_document
from world_runtime import derive_capabilities, derive_entity_kind, normalize_relationships

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"


def rows(counter: Counter[str]) -> list[dict[str, int | str]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def fallback_row(path: Path, child: dict, parent: dict | None, rel: dict) -> dict[str, object]:
    return {
        "fixture": path.name,
        "source_entity_id": child["entity_id"],
        "source_name": child.get("name"),
        "source_kind": derive_entity_kind(child),
        "source_legacy_type": child.get("entity_type"),
        "capabilities": derive_capabilities(child),
        "target_entity_id": rel["target_entity_id"],
        "target_name": parent.get("name") if parent else None,
        "target_kind": derive_entity_kind(parent) if parent else None,
        "target_legacy_type": parent.get("entity_type") if parent else None,
        "source_ref": child.get("source_ref"),
        "source_summary": child.get("source_summary"),
        "chain_affiliation": child.get("chain_affiliation"),
        "supply_relationships": child.get("supply_relationships"),
    }


fixture_count = 0
entity_count = 0
kind_counts: Counter[str] = Counter()
capability_counts: Counter[str] = Counter()
capability_signatures: Counter[str] = Counter()
relationship_counts: Counter[str] = Counter()
relationship_origins: Counter[str] = Counter()
legacy_type_to_kind: Counter[str] = Counter()
priority_fallbacks: list[dict[str, object]] = []
non_place_parent_fallbacks: list[dict[str, object]] = []
relationship_hint_fallbacks: list[dict[str, object]] = []

for path in sorted(WORLD_DIR.glob("*.v1.json")):
    source = json.loads(path.read_text(encoding="utf-8"))
    doc = normalize_document(source)
    if doc.get("fixture_status") != "source_reviewed":
        continue

    fixture_count += 1
    entity_count += len(doc["entities"])
    entities_by_id = {entity["entity_id"]: entity for entity in doc["entities"]}
    for entity in doc["entities"]:
        kind = derive_entity_kind(entity)
        capabilities = derive_capabilities(entity)
        kind_counts[kind] += 1
        legacy_type_to_kind[f"{entity.get('entity_type', '<missing>')}->{kind}"] += 1
        capability_counts.update(capabilities)
        capability_signatures["+".join(capabilities) if capabilities else "none"] += 1

    for rel in normalize_relationships(source):
        relationship_counts[rel["relationship_type"]] += 1
        legacy_fallback = rel.get("inferred_from") == "parent_entity_id"
        relationship_origins["legacy_parent_fallback" if legacy_fallback else "explicit"] += 1
        if not legacy_fallback:
            continue
        child = entities_by_id.get(rel["source_entity_id"])
        parent = entities_by_id.get(rel["target_entity_id"])
        if child is None:
            continue

        row = fallback_row(path, child, parent, rel)
        capabilities = row["capabilities"]
        if "event" in capabilities or "distribution" in capabilities:
            priority_fallbacks.append(row)
        if parent is not None and derive_entity_kind(parent) != "place":
            non_place_parent_fallbacks.append(row)
        if child.get("chain_affiliation") or child.get("supply_relationships"):
            relationship_hint_fallbacks.append(row)

report = {
    "world_id": "night-city-2045",
    "runtime_version": "0.3.0",
    "fixture_files": fixture_count,
    "reviewed_entities": entity_count,
    "counts": {
        "entity_kind": rows(kind_counts),
        "capability": rows(capability_counts),
        "capability_signature": rows(capability_signatures),
        "relationship_type": rows(relationship_counts),
        "relationship_origin": rows(relationship_origins),
        "legacy_type_to_kind": rows(legacy_type_to_kind),
    },
    "priority_legacy_parent_fallbacks": priority_fallbacks,
    "non_place_parent_fallbacks": non_place_parent_fallbacks,
    "relationship_hint_fallbacks": relationship_hint_fallbacks,
}

print(f"Runtime ontology audit: fixtures={fixture_count} entities={entity_count}")
for key, title in (
    ("entity_kind", "Entity kinds"),
    ("capability", "Capabilities"),
    ("capability_signature", "Capability signatures"),
    ("relationship_type", "Relationship types"),
    ("relationship_origin", "Relationship origins"),
    ("legacy_type_to_kind", "Legacy type -> runtime kind"),
):
    print(f"\n## {title}")
    for row in report["counts"][key]:
        print(f"{row['count']:>4}  {row['value']}")

print("\n## Priority legacy parent fallbacks (event/distribution)")
for row in priority_fallbacks:
    capabilities = "+".join(row["capabilities"])
    print(
        f"{row['fixture']} | {row['source_name']} [{capabilities}] -> "
        f"{row['target_name'] or row['target_entity_id']}"
    )
    if row.get("source_summary"):
        print(f"    {row['source_summary']}")

print("\n## Legacy fallbacks whose parent is not a place")
for row in non_place_parent_fallbacks:
    print(
        f"{row['fixture']} | {row['source_name']} ({row['source_kind']}) -> "
        f"{row['target_name']} ({row['target_kind']})"
    )
    if row.get("source_summary"):
        print(f"    {row['source_summary']}")

print("\n## Legacy fallbacks with explicit chain/supply hints")
for row in relationship_hint_fallbacks:
    print(f"{row['fixture']} | {row['source_name']} -> {row['target_name']}")
    if row.get("chain_affiliation"):
        print(f"    chain_affiliation={row['chain_affiliation']}")
    if row.get("supply_relationships"):
        print(f"    supply_relationships={row['supply_relationships']}")

output = ROOT / "build/reports/night-city-2045-runtime-ontology-v0.3.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\nWrote {output.relative_to(ROOT)}")
