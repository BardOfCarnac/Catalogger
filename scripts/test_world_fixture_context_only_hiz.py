#!/usr/bin/env python3
"""Regression tests for the first true CONTEXT_ONLY false-negative audit: Heywood Industrial Zone."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/worlds/night-city-2045/context-only-candidates-hiz.v0.2.json"
FIXTURE = ROOT / "data/worlds/night-city-2045/heywood-industrial-zone-context-only.v1.json"

engine = WorldStockEngine()

candidate_doc = load_json(CANDIDATES)
schema = candidate_doc["schema"]
candidates = [dict(zip(schema, row, strict=True)) for row in candidate_doc["rows"]]
assert candidate_doc["candidate_count"] == len(candidates) == 16

source = load_json(FIXTURE)
validate_document(source)
a = realize_document(source, engine)
b = realize_document(source, engine)
assert a == b, "HIZ CONTEXT_ONLY fixture realization must be deterministic"
entities = {row["name"]: row for row in a["entities"]}
by_id = {row["entity_id"]: row for row in a["entities"]}

# Every audited CONTEXT_ONLY row receives an exact source-reviewed verdict.
for candidate in candidates:
    assert candidate["entity_id"] in by_id, candidate
    assert by_id[candidate["entity_id"]]["review_status"] == "source_reviewed"

# Definite false negatives: these are customer/business-facing and were not merely context.
assert entities["Aldecaldo Depot"]["entity_type"] == "service"
assert entities["Agron’s Boxed Lunches"]["entity_type"] == "hybrid"
assert entities["Agron’s Boxed Lunches"]["local_offerings"][0]["price_eb"] == 10
assert entities["Agron’s Boxed Lunches"]["services"][0]["service_key"] == "informal-loans"
assert entities["The Interchange"]["entity_type"] == "service"
assert {row["service_key"] for row in entities["The Interchange"]["services"]} == {
    "rail-passenger-stop", "rail-freight-interchange"
}
assert entities["Yang’s Wheels"]["entity_type"] == "hybrid"
assert {row["offering_key"] for row in entities["Yang’s Wheels"]["local_offerings"]} == {
    "bicycles", "skateboards", "inline-skates", "electric-scooters", "metrocars"
}
assert entities["Yang’s Wheels"]["services"][0]["service_key"] == "mobility-test-park"

# The Rambling Rose hides a named commercial child rather than being a shop itself.
assert entities["D.V. Rambling Rose"]["entity_type"] == "container"
assert entities["Fixie’s Couriers"]["parent_entity_id"] == "NC2045-LOC-HEYWOOD-INDUSTRIAL-ZONE-258-D-V-RAMBLING-ROSE"
assert entities["Fixie’s Couriers"]["services"][0]["service_key"] == "courier-logistics"

# Context rows must remain non-stock-bearing despite audit keyword spillover.
confirmed_context = {
    "Arroyo Concern Offices",
    "Continental Brands Manufacturing",
    "GunMart Manufacturing",
    "Militech Manufacturing Plant",
    "Petrochem Plastics Plant",
    "Raven Microcybernetics Factory",
    "Rocklin Augmentics Manufacturing",
    "The Rodeo",
    "SovOil Plastics Plant",
    "Trauma Team Pharmaceutical Plant",
    "Zhirafa Office Park",
}
for name in confirmed_context:
    assert entities[name]["entity_type"] == "context", name
    assert entities[name]["stock_policy"] == "NO_STOCK", name
    assert "assortment" not in entities[name], name

assert entities["The Rodeo"]["schedule"]["kind"] == "recurring"
assert entities["SovOil Plastics Plant"]["supply_relationships"][0]["target"] == "Oasis stores"

# Nothing in this first context-only pass should silently become generic Catalogger stock.
stock_bearers = {name for name, row in entities.items() if row.get("assortment")}
assert stock_bearers == set(), stock_bearers

promoted_candidate_names = {
    name for name, row in entities.items()
    if row.get("entity_id") in {c["entity_id"] for c in candidates}
    and row["entity_type"] not in {"context", "container"}
}
assert promoted_candidate_names == {
    "Aldecaldo Depot", "Agron’s Boxed Lunches", "The Interchange", "Yang’s Wheels"
}

print(
    "OK: HIZ CONTEXT_ONLY audit; "
    f"candidates={len(candidates)}, entities={len(entities)}, direct_false_negatives={len(promoted_candidate_names)}, "
    "recovered_children=1, stock-bearing=0"
)
