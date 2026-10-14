#!/usr/bin/env python3
"""Regression tests for Executive Zone, Hot Zone and Port of Night City CONTEXT_ONLY reviews."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/worlds/night-city-2045"
engine = WorldStockEngine()


def load_review(candidate_name, fixture_name, expected_count):
    candidate_doc = load_json(DATA / candidate_name)
    schema = candidate_doc["schema"]
    candidates = [dict(zip(schema, row, strict=True)) for row in candidate_doc["rows"]]
    assert candidate_doc["candidate_count"] == len(candidates) == expected_count
    source = load_json(DATA / fixture_name)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b
    entities = {row["name"]: row for row in a["entities"]}
    by_id = {row["entity_id"]: row for row in a["entities"]}
    for candidate in candidates:
        assert candidate["entity_id"] in by_id
    assert not {name for name, row in entities.items() if row.get("assortment")}
    candidate_ids = {row["entity_id"] for row in candidates}
    direct_false_negatives = {
        row["name"] for row in entities.values()
        if row["entity_id"] in candidate_ids and row["entity_type"] not in {"context", "container"}
    }
    return candidates, entities, direct_false_negatives


exec_candidates, executive, exec_false = load_review(
    "context-only-candidates-executive-zone.v0.2.json",
    "executive-zone-context-only.v1.json",
    7,
)
assert len(executive) == 8
assert exec_false == {"Firebird Tearoom & Steam Baths", "Growing Shoots Daycare", "Monorail Station"}
assert executive["The Estates"]["entity_type"] == "container"
assert executive["Mister Kernaghan Procurement Service"]["parent_entity_id"] == "NC2045-LOC-EXECUTIVE-ZONE-234-THE-ESTATES"
assert executive["Firebird Tearoom & Steam Baths"]["entity_type"] == "hybrid"
assert executive["Growing Shoots Daycare"]["entity_type"] == "service"
assert executive["Monorail Station"]["entity_type"] == "service"
for name in {"Groundskeeper Shed", "HOA Offices", "Lazarus Base of Operations"}:
    assert executive[name]["entity_type"] == "context"
    assert executive[name]["stock_policy"] == "NO_STOCK"


hot_candidates, hot, hot_false = load_review(
    "context-only-candidates-the-hot-zone.v0.2.json",
    "the-hot-zone-context-only.v1.json",
    7,
)
assert len(hot) == 7
assert hot_false == {"Toggle’s Temple"}
assert hot["Toggle’s Temple"]["entity_type"] == "service"
assert hot["Toggle’s Temple"]["services"][0]["price_eb"] == 20
for name in {"The Crater", "Dark Zone One", "The Dump", "Eurasiabank Plaza", "The N54", "Safe Child"}:
    assert hot[name]["entity_type"] == "context"
    assert hot[name]["stock_policy"] == "NO_STOCK"


port_candidates, port, port_false = load_review(
    "context-only-candidates-port-of-night-city.v0.2.json",
    "port-of-night-city-context-only.v1.json",
    6,
)
assert len(port) == 7
assert port_false == {"Main Port", "Mestnyy Bank", "The Reclamation Plant"}
assert port["Main Port"]["entity_type"] == "service"
assert {s["service_key"] for s in port["Main Port"]["services"]} == {"port-cargo-handling", "dry-dock-vessel-repair"}
assert port["Mestnyy Bank"]["entity_type"] == "service"
assert port["The Reclamation Plant"]["entity_type"] == "hybrid"
assert port["Night City Department of Water"]["parent_entity_id"] == "NC2045-LOC-PORT-OF-NIGHT-CITY-154-THE-RECLAMATION-PLANT"
for name in {"Dock Cargo Community", "Harbor Patrol HQ", "Reclaimed Studios"}:
    assert port[name]["entity_type"] == "context"
    assert port[name]["stock_policy"] == "NO_STOCK"

print(
    "OK: Executive Zone + Hot Zone + Port CONTEXT_ONLY audit; "
    f"candidates={len(exec_candidates)+len(hot_candidates)+len(port_candidates)}, "
    f"entities={len(executive)+len(hot)+len(port)}, "
    f"direct_false_negatives={len(exec_false)+len(hot_false)+len(port_false)}, "
    "recovered_children=2, stock-bearing=0"
)
