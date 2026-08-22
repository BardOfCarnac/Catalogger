#!/usr/bin/env python3
"""Close-out regression for the complete Night City 2045 CONTEXT_ONLY census."""
import re
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/worlds/night-city-2045"
engine = WorldStockEngine()

candidate_files = sorted(DATA.glob("context-only-candidates-*.v0.2.json"))
assert len(candidate_files) == 25, len(candidate_files)

all_candidate_ids = set()
total_candidates = 0
total_entities = 0
direct_false_negatives = 0
recovered_children = 0
stock_bearing = 0

for candidate_path in candidate_files:
    candidate_doc = load_json(candidate_path)
    assert candidate_doc["classification"] == "CONTEXT_ONLY"
    district_slug = re.sub(r"[^a-z0-9]+", "-", candidate_doc["district"].lower()).strip("-")
    fixture_path = DATA / f"{district_slug}-context-only.v1.json"
    assert fixture_path.exists(), fixture_path

    schema = candidate_doc["schema"]
    candidates = [dict(zip(schema, row, strict=True)) for row in candidate_doc["rows"]]
    assert candidate_doc["candidate_count"] == len(candidates)
    candidate_ids = {row["entity_id"] for row in candidates}
    assert len(candidate_ids) == len(candidates)
    assert not (all_candidate_ids & candidate_ids)
    all_candidate_ids |= candidate_ids

    source = load_json(fixture_path)
    assert source["fixture_status"] == "source_reviewed"
    validate_document(source)
    realized_a = realize_document(source, engine)
    realized_b = realize_document(source, engine)
    assert realized_a == realized_b
    entities = realized_a["entities"]
    by_id = {row["entity_id"]: row for row in entities}
    assert candidate_ids <= set(by_id)

    total_candidates += len(candidates)
    total_entities += len(entities)
    direct_false_negatives += sum(
        1 for entity_id in candidate_ids
        if by_id[entity_id]["entity_type"] not in {"context", "container"}
    )
    recovered_children += sum(1 for row in entities if row["entity_id"] not in candidate_ids)
    stock_bearing += sum(1 for row in entities if row.get("assortment"))

assert total_candidates == 265, total_candidates
assert len(all_candidate_ids) == 265
assert stock_bearing == 0, stock_bearing

print(
    "OK: complete Night City 2045 CONTEXT_ONLY census; "
    f"district_slices={len(candidate_files)}, candidates={total_candidates}, "
    f"realized_entities={total_entities}, direct_false_negatives={direct_false_negatives}, "
    f"recovered_children={recovered_children}, stock-bearing={stock_bearing}"
)
