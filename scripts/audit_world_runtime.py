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


fixture_count = 0
entity_count = 0
kind_counts: Counter[str] = Counter()
capability_counts: Counter[str] = Counter()
capability_signatures: Counter[str] = Counter()
relationship_counts: Counter[str] = Counter()
relationship_origins: Counter[str] = Counter()
legacy_type_to_kind: Counter[str] = Counter()

for path in sorted(WORLD_DIR.glob("*.v1.json")):
    source = json.loads(path.read_text(encoding="utf-8"))
    doc = normalize_document(source)
    if doc.get("fixture_status") != "source_reviewed":
        continue

    fixture_count += 1
    entity_count += len(doc["entities"])
    for entity in doc["entities"]:
        kind = derive_entity_kind(entity)
        capabilities = derive_capabilities(entity)
        kind_counts[kind] += 1
        legacy_type_to_kind[f"{entity.get('entity_type', '<missing>')}->{kind}"] += 1
        capability_counts.update(capabilities)
        capability_signatures["+".join(capabilities) if capabilities else "none"] += 1

    for rel in normalize_relationships(source):
        relationship_counts[rel["relationship_type"]] += 1
        relationship_origins[
            "legacy_parent_fallback" if rel.get("inferred_from") == "parent_entity_id" else "explicit"
        ] += 1

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

output = ROOT / "build/reports/night-city-2045-runtime-ontology-v0.3.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\nWrote {output.relative_to(ROOT)}")
