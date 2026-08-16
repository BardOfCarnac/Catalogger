#!/usr/bin/env python3
"""Persistence/source-filter/event/report smoke tests for Vend-R stocking lifecycle."""
from copy import deepcopy
import random

from stock_lifecycle import BUNDLE_FORMAT_VERSION, StockLifecycleEngine


engine = StockLifecycleEngine()

# Durable generation stores target/reorder behaviour and score provenance.
context = engine.make_context("weapons-dealer", "ci-lifecycle")
bundle = engine.generate(context)
engine.validate_bundle(bundle)
assert bundle["format_version"] == BUNDLE_FORMAT_VERSION
assert bundle["history"], "cycle-0 events were not recorded"
assert bundle["state"]["last_cycle_events"], "cycle-0 event pointers missing"
assert all("score_components" in row for row in bundle["assortment"])
assert all("target_quantity" in row and "reorder_point" in row for row in bundle["assortment"])
for row in bundle["assortment"]:
    target = row["target_quantity"]
    reorder = row["reorder_point"]
    if target is not None:
        assert 1 <= reorder <= target

# The durable format remains deterministic for identical realized shop context.
bundle_again = engine.generate(engine.make_context("weapons-dealer", "ci-lifecycle"))
assert bundle["assortment"] == bundle_again["assortment"]
assert bundle["stock"] == bundle_again["stock"]
assert bundle["history"] == bundle_again["history"]

# Enabled-book/source filtering happens before assortment generation and becomes part
# of the persisted shop contract.
core_only_context = engine.make_context(
    "general-store",
    "ci-core-only",
    overrides={"enabled_source_codes": ["CP:R"]},
)
core_only = engine.generate(core_only_context)
assert core_only["assortment"], "core-only source filter produced no assortment"
for line in core_only["assortment"]:
    assert "CP:R" in engine.source_codes_by_item[line["item_id"]]
assert core_only["state"]["source_filter"]["enabled_source_codes"] == ["CP:R"]
engine.validate_bundle(core_only)

# Targeted temporary conditions affect only matching products.
core_line = next(
    row for row in bundle["assortment"]
    if row["role"] == "core" and row["target_quantity"] is not None
)
bundle["state"]["temporary_conditions"] = [
    {"type": "shortage", "target": {"item_ids": [core_line["item_id"]]}}
]
mods = engine._cycle_modifiers(core_line["item_id"], bundle["state"])
assert mods["presence_multiplier"] == 0.7
assert mods["quantity_multiplier"] == 0.7
other_item = next(
    row["item_id"] for row in bundle["assortment"] if row["item_id"] != core_line["item_id"]
)
other_mods = engine._cycle_modifiers(other_item, bundle["state"])
assert other_mods["presence_multiplier"] == 1.0

# Pending orders are first-class stock rows and turn into deliveries on their arrival cycle.
delivery_input = deepcopy(bundle_again)
delivery_line = next(
    row for row in delivery_input["assortment"]
    if row["role"] == "core" and row["target_quantity"] is not None
)
delivery_item = delivery_line["item_id"]
delivery_input["stock"] = [
    row for row in delivery_input["stock"] if row["item_id"] != delivery_item
]
incoming = engine._incoming_row(
    random.Random("ci-incoming"),
    delivery_input["shop"],
    delivery_input["state"],
    delivery_line,
    0,
)
assert incoming is not None
incoming["metadata"]["arrival_cycle"] = 1
delivery_input["stock"].append(incoming)
engine.validate_bundle(delivery_input)
delivered = engine.restock(delivery_input)
assert delivered["state"]["stock_cycle"] == 1
assert any(
    row["item_id"] == delivery_item and row["status"] == "in_stock"
    for row in delivered["stock"]
), "incoming order did not become available stock"
assert any(
    row["event_type"] == "delivery_received" and row["item_id"] == delivery_item
    for row in delivered["history"]
), "delivery event not recorded"

# Restocking never rebuilds persistent assortment and records cycle events.
original_assortment_ids = [row["item_id"] for row in delivered["assortment"]]
cycle_two = engine.restock(delivered)
assert cycle_two["state"]["stock_cycle"] == 2
assert [row["item_id"] for row in cycle_two["assortment"]] == original_assortment_ids
assert cycle_two["state"]["last_cycle_events"]
assert all(
    event_id in {row["id"] for row in cycle_two["history"]}
    for event_id in cycle_two["state"]["last_cycle_events"]
)

# A no-UI developer report exposes assortment, stock state, score reasons and events.
report = engine.inspection_markdown(cycle_two)
assert "## Persistent assortment" in report
assert "Score breakdown" in report
assert "## Last cycle events" in report
assert delivery_line["role"] in report

print(
    f"OK: lifecycle format {BUNDLE_FORMAT_VERSION}; assortment={len(cycle_two['assortment'])}, "
    f"history={len(cycle_two['history'])}, source-filtered assortment={len(core_only['assortment'])}"
)
