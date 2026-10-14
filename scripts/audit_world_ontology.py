#!/usr/bin/env python3
"""Audit the long tail of Vend-R world-fixture ontology values.

This is intentionally descriptive rather than normative: it counts the vocabulary that
source review actually produced, flags values/signatures used only once or twice, and makes
odd structural patterns visible before we simplify the ontology or promote RETAIL_CAPABLE
records into the reviewed world layer.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from world_fixture import normalize_document

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data" / "worlds" / "night-city-2045"


def load_documents() -> list[tuple[Path, dict[str, Any]]]:
    docs: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(WORLD_DIR.glob("*.v1.json")):
        source = json.loads(path.read_text(encoding="utf-8"))
        doc = normalize_document(source)
        if doc.get("fixture_status") != "source_reviewed":
            continue
        docs.append((path, doc))
    return docs


def capability_signature(entity: dict[str, Any]) -> str:
    caps: list[str] = []
    if entity.get("stocking"):
        caps.append("catalog_stock")
    if entity.get("local_offerings"):
        caps.append("local_wares")
    if entity.get("services"):
        caps.append("services")
    if entity.get("entity_type") == "container":
        caps.append("container")
    if entity.get("entity_type") == "event_market" or entity.get("stock_policy") == "EVENT_ONLY" or entity.get("market_profile") or entity.get("event_profile"):
        caps.append("event")
    if entity.get("entity_type") == "channel" or entity.get("distribution"):
        caps.append("distribution")
    if entity.get("parent_entity_id"):
        caps.append("parented")
    if entity.get("stock_policy") == "NO_STOCK":
        caps.append("explicit_no_stock")
    if entity.get("schedule"):
        caps.append("schedule")
    return "+".join(sorted(caps)) if caps else "plain"


def sorted_counter(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def rare(counter: Counter[str], threshold: int = 2) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (item[1], item[0]))
        if count <= threshold
    ]


def build_report() -> dict[str, Any]:
    docs = load_documents()
    entities: list[dict[str, Any]] = []
    fixtures_by_entity: dict[str, str] = {}
    supply_relationships: list[dict[str, Any]] = []
    for path, doc in docs:
        for entity in doc["entities"]:
            row = dict(entity)
            row["_fixture_file"] = path.name
            entities.append(row)
            fixtures_by_entity[row["entity_id"]] = path.name
            for supply in row.get("supply_relationships", []):
                supply_relationships.append({
                    "fixture_file": path.name,
                    "fixture_id": doc.get("fixture_id"),
                    "entity_id": row["entity_id"],
                    "entity_name": row.get("name"),
                    "source_ref": row.get("source_ref"),
                    "relationship": supply,
                })

    entity_type = Counter(str(e.get("entity_type", "<missing>")) for e in entities)
    commercial_mode = Counter(str(e.get("commercial_mode", "<none>")) for e in entities)
    stock_policy = Counter(str(e.get("stock_policy", "<none>")) for e in entities)
    provenance = Counter(str(e.get("provenance", "<none>")) for e in entities)
    decision = Counter(str(e.get("audit", {}).get("decision", "<none>")) for e in entities)
    top_level_keys = Counter(key for e in entities for key in e if not key.startswith("_"))
    signatures = Counter(capability_signature(e) for e in entities)

    entity_by_id = {e["entity_id"]: e for e in entities}
    relationship_patterns: Counter[str] = Counter()
    relationship_examples: defaultdict[str, list[str]] = defaultdict(list)
    for e in entities:
        parent_id = e.get("parent_entity_id")
        if not parent_id:
            continue
        parent = entity_by_id.get(parent_id)
        parent_type = parent.get("entity_type") if parent else "external"
        pattern = f"{parent_type}->{e.get('entity_type')}"
        relationship_patterns[pattern] += 1
        if len(relationship_examples[pattern]) < 5:
            relationship_examples[pattern].append(f"{e.get('name')} ({e.get('_fixture_file')})")

    signature_examples: defaultdict[str, list[str]] = defaultdict(list)
    for e in entities:
        sig = capability_signature(e)
        if len(signature_examples[sig]) < 8:
            signature_examples[sig].append(f"{e.get('name')} ({e.get('_fixture_file')})")

    rare_register: list[dict[str, Any]] = []
    for dimension, counter in (
        ("entity_type", entity_type),
        ("commercial_mode", commercial_mode),
        ("stock_policy", stock_policy),
        ("provenance", provenance),
        ("audit_decision", decision),
        ("top_level_field", top_level_keys),
        ("capability_signature", signatures),
        ("relationship_pattern", relationship_patterns),
    ):
        for item in rare(counter):
            entry = {"dimension": dimension, **item}
            if dimension == "capability_signature":
                entry["examples"] = signature_examples[item["value"]]
            elif dimension == "relationship_pattern":
                entry["examples"] = relationship_examples[item["value"]]
            else:
                examples = []
                for e in entities:
                    match = False
                    if dimension == "entity_type":
                        match = str(e.get("entity_type", "<missing>")) == item["value"]
                    elif dimension == "commercial_mode":
                        match = str(e.get("commercial_mode", "<none>")) == item["value"]
                    elif dimension == "stock_policy":
                        match = str(e.get("stock_policy", "<none>")) == item["value"]
                    elif dimension == "provenance":
                        match = str(e.get("provenance", "<none>")) == item["value"]
                    elif dimension == "audit_decision":
                        match = str(e.get("audit", {}).get("decision", "<none>")) == item["value"]
                    elif dimension == "top_level_field":
                        match = item["value"] in e
                    if match and len(examples) < 8:
                        examples.append(f"{e.get('name')} ({e.get('_fixture_file')})")
                entry["examples"] = examples
            rare_register.append(entry)

    return {
        "world_id": "night-city-2045",
        "fixture_files": len(docs),
        "reviewed_entities": len(entities),
        "counts": {
            "entity_type": sorted_counter(entity_type),
            "commercial_mode": sorted_counter(commercial_mode),
            "stock_policy": sorted_counter(stock_policy),
            "provenance": sorted_counter(provenance),
            "audit_decision": sorted_counter(decision),
            "top_level_field": sorted_counter(top_level_keys),
            "capability_signature": sorted_counter(signatures),
            "relationship_pattern": sorted_counter(relationship_patterns),
        },
        "source_relationships": {
            "supply_relationships": len(supply_relationships),
        },
        "supply_relationships": supply_relationships,
        "rare_threshold": 2,
        "rare_register": rare_register,
    }


def print_section(title: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n## {title}")
    for row in rows:
        print(f"{row['count']:>4}  {row['value']}")


def main() -> None:
    report = build_report()
    print(f"Ontology audit: fixtures={report['fixture_files']} entities={report['reviewed_entities']}")
    for key, title in (
        ("entity_type", "Entity types"),
        ("commercial_mode", "Commercial modes"),
        ("stock_policy", "Stock policies"),
        ("provenance", "Provenance"),
        ("audit_decision", "Audit decisions"),
        ("capability_signature", "Capability signatures"),
        ("relationship_pattern", "Relationship patterns"),
        ("top_level_field", "Entity field usage"),
    ):
        print_section(title, report["counts"][key])

    print("\n## Source-level relationship fields")
    print(f"supply_relationships: {report['source_relationships']['supply_relationships']}")

    print("\n## Supply relationships")
    for row in report["supply_relationships"]:
        print(
            f"{row['fixture_file']} | {row['entity_name']} | {row['entity_id']} | "
            f"{json.dumps(row['relationship'], ensure_ascii=False, sort_keys=True)}"
        )

    print("\n## Rare register (count <= 2)")
    for row in report["rare_register"]:
        examples = "; ".join(row.get("examples", []))
        print(f"{row['dimension']} | {row['count']} | {row['value']} | {examples}")

    output = ROOT / "build" / "reports" / "night-city-2045-ontology-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
