#!/usr/bin/env python3
"""Regression tests for conservative chain-affiliation projection in runtime v0.3."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from world_fixture import WorldFixtureError, normalize_document
from world_runtime import realize_runtime_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"
engine = WorldStockEngine()


def load(name: str) -> dict:
    return json.loads((WORLD_DIR / name).read_text(encoding="utf-8"))


def entity(runtime: dict, entity_id: str) -> dict:
    return next(row for row in runtime["entities"] if row["entity_id"] == entity_id)


# The three structured source affiliations project as profile data, not invented chain nodes.
suzuki_source = load("old-japantown-core.v1.json")
suzuki = realize_runtime_document(suzuki_source, engine)
suzuki_bodega = entity(suzuki, "NC2045-LOC-OLD-JAPANTOWN-132-MRS-SUZUKI-S-BODEGA")
assert suzuki_bodega["chain_profile"] == {
    "name": "Mrs. Suzuki's bodega chain",
    "operator": "Mrs. Suzuki and family",
}

university = realize_runtime_document(load("university-district-core.v1.json"), engine)
lombardy = entity(university, "NC2045-OUT-UNIVERSITY-DISTRICT-108-LOMBARDY-GROCERIES")
assert lombardy["chain_profile"] == {
    "name": "Mrs. Suzuki's bodega chain",
    "operator": "Mrs. Suzuki",
}

new_westbrook = realize_runtime_document(load("new-westbrook-core.v1.json"), engine)
oasis = entity(new_westbrook, "NC2045-OUT-NEW-WESTBROOK-214-OASIS")
assert oasis["chain_profile"] == {
    "name": "Oasis",
    "operator": "Continental Brands",
}

# Do not infer structured chain state from prose alone. Bless Your Heart is described as a
# branch in its source summary, but its reviewed v0.2 fixture has no chain_affiliation field.
upper_marina = realize_runtime_document(load("upper-marina-review-queue.v1.json"), engine)
bless_your_heart = entity(upper_marina, "NC2045-LOC-UPPER-MARINA-068-BLESS-YOUR-HEART")
assert "chain_profile" not in bless_your_heart

# Malformed structured affiliations fail closed.
bad = copy.deepcopy(load("new-westbrook-core.v1.json"))
bad_oasis = next(row for row in bad["entities"] if row["entity_id"] == "NC2045-OUT-NEW-WESTBROOK-214-OASIS")
bad_oasis["chain_affiliation"] = []
try:
    realize_runtime_document(bad, engine)
except WorldFixtureError:
    pass
else:
    raise AssertionError("malformed chain_affiliation was accepted")

# Corpus-wide invariant: three structured affiliations, zero chain entities, and zero
# chain_branch_of edges until a real first-class chain entity is source-reviewed.
source_affiliations = 0
runtime_chain_profiles = 0
runtime_chain_entities = 0
runtime_chain_edges = 0

for path in sorted(WORLD_DIR.glob("*.v1.json")):
    source = json.loads(path.read_text(encoding="utf-8"))
    doc = normalize_document(source)
    if doc.get("fixture_status") != "source_reviewed":
        continue

    source_affiliations += sum("chain_affiliation" in row for row in doc["entities"])
    runtime = realize_runtime_document(source, engine)
    runtime_chain_profiles += sum("chain_profile" in row for row in runtime["entities"])
    runtime_chain_entities += sum(row["entity_kind"] == "chain" for row in runtime["entities"])
    runtime_chain_edges += sum(
        row["relationship_type"] == "chain_branch_of" for row in runtime["relationships"]
    )

assert source_affiliations == 3, source_affiliations
assert runtime_chain_profiles == 3, runtime_chain_profiles
assert runtime_chain_entities == 0, runtime_chain_entities
assert runtime_chain_edges == 0, runtime_chain_edges

print(
    "OK: runtime chain profiles; "
    f"source_affiliations={source_affiliations}, profiles={runtime_chain_profiles}, "
    f"chain_entities={runtime_chain_entities}, chain_edges={runtime_chain_edges}"
)
