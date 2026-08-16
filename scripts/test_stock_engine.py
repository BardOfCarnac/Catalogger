#!/usr/bin/env python3
"""Deterministic smoke tests for Vend-R stocking and restocking."""
from copy import deepcopy

from stock_engine import StockEngine


engine = StockEngine()

# Every archetype must generate a non-empty, duplicate-free persistent assortment.
for archetype_id in sorted(engine.archetypes):
    context = engine.make_context(archetype_id, f"ci-{archetype_id}")
    bundle = engine.generate(context)
    assortment_ids = [row["item_id"] for row in bundle["assortment"]]
    assert assortment_ids, f"empty assortment for {archetype_id}"
    assert len(assortment_ids) == len(set(assortment_ids)), f"duplicate assortment item: {archetype_id}"
    for row in bundle["assortment"]:
        assert row["role"] in {"core", "regular", "occasional"}
        assert engine.eligible(row["item_id"], context, special=False)
        assert engine.commercial_by_id[row["item_id"]]["product_identity"] != "unique"
    for row in bundle["stock"]:
        assert row["assortment_role"] in {"core", "regular", "occasional", "special"}
        assert engine.eligible(row["item_id"], context, special=row["assortment_role"] == "special")

# The medium weapons-dealer profile should realize the design target of 6/12/10 lines.
weapons_context = engine.make_context("weapons-dealer", "ci-weapons-fixed")
weapons_a = engine.generate(weapons_context)
weapons_b = engine.generate(engine.make_context("weapons-dealer", "ci-weapons-fixed"))
role_counts = {}
for row in weapons_a["assortment"]:
    role_counts[row["role"]] = role_counts.get(row["role"], 0) + 1
assert role_counts == {"core": 6, "regular": 12, "occasional": 10}, role_counts

# Same seed and realized context must give exactly the same assortment and cycle-0 stock.
assert weapons_a["assortment"] == weapons_b["assortment"]
assert weapons_a["stock"] == weapons_b["stock"]

# Selling out one core line must not erase the shop's relationship with that product.
restock_input = deepcopy(weapons_a)
core_item = next(row["item_id"] for row in restock_input["assortment"] if row["role"] == "core")
found = False
for row in restock_input["stock"]:
    if row["item_id"] == core_item:
        row["quantity"] = 0 if row["quantity"] is not None else None
        row["status"] = "sold"
        found = True
        break
# A core line can be temporarily absent at cycle 0; create a sold placeholder in that case.
if not found:
    restock_input["stock"].append({
        "id": "sold-placeholder",
        "shop_id": weapons_context["id"],
        "item_id": core_item,
        "quantity": 0,
        "condition": None,
        "asking_price": None,
        "price_modifier": 1,
        "visibility": "public",
        "status": "sold",
        "assortment_role": "core",
        "added_cycle": 0,
        "stock_reason": "core",
    })

restocked = engine.restock(restock_input)
assert restocked["state"]["stock_cycle"] == 1
assert [row["item_id"] for row in restocked["assortment"]] == [
    row["item_id"] for row in weapons_a["assortment"]
], "restock must not reroll persistent assortment"
assert core_item in {row["item_id"] for row in restocked["assortment"]}

# Explicit speciality paths should materially improve matching candidates without making
# unrelated eligible items impossible.
pistol_context = engine.make_context(
    "weapons-dealer",
    "ci-pistol-specialist",
    overrides={"preferred_classification_paths": [["Weapons", "Firearms", "Pistols"]]},
)
scored = engine.candidate_scores(pistol_context)
assert scored
assert any(row["components"]["speciality"] > 0 for row in scored), "speciality scoring did not activate"
assert any(row["components"]["speciality"] == 0 for row in scored), "speciality became a hard filter"

print(
    f"OK: stock engine generated {len(engine.archetypes)} archetypes; "
    f"weapons dealer assortment={len(weapons_a['assortment'])}, cycle-0 stock={len(weapons_a['stock'])}"
)
