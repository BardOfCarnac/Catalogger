#!/usr/bin/env python3
"""Regression tests for the shared once-per-day Night City stock pulse."""
from __future__ import annotations

from build_city_stock import build_availability_index, build_catalogue_coverage
from city_stock_state import (
    advance_city_stock,
    initialize_city_stock,
    place_order,
    purchase_item,
    sync_calendar_date,
)
from world_stock_engine import WorldStockEngine

engine = WorldStockEngine()
city = initialize_city_stock(engine, "2045-01-01")

assert city["stock_day"] == 0
assert city["stock_cycle"] == 0
assert city["stock_date"] == "2045-01-01"
assert city["daily_stock_policy"]["city_pulses_per_day"] == 1
assert city["daily_stock_policy"]["full_seller_restock_passes"] == 0
assert city["daily_stock_policy"]["opening_hours_enforced"] is False
assert city["daily_stock_policy"]["clock_simulation"] is False
assert city["last_city_pulse"] is None

initial_assortments = {
    seller["entity_id"]: {
        (row["item_id"], row["role"])
        for row in seller["assortment"]
    }
    for seller in city["sellers"]
}

same, action = sync_calendar_date(city, "2045-01-01", engine)
assert action == "unchanged"
assert same["stock_day"] == 0

day1, action = sync_calendar_date(city, "2045-01-02", engine)
assert action == "advanced"
assert day1["stock_day"] == 1
assert day1["stock_cycle"] == 1
assert day1["stock_date"] == "2045-01-02"
assert all(seller["state"]["stock_cycle"] == 1 for seller in day1["sellers"])

pulse = day1["last_city_pulse"]
low, high = engine.model["city_pulse"]["daily_mutation_range"]
assert low <= pulse["budget"] <= high
assert sum(pulse["requested"].values()) == pulse["budget"]
assert 0 < pulse["applied_mutations"] <= pulse["budget"]
assert pulse["skipped_mutations"] == pulse["budget"] - pulse["applied_mutations"]
assert pulse["touched_sellers"] > 0

assert {
    seller["entity_id"]: {
        (row["item_id"], row["role"])
        for row in seller["assortment"]
    }
    for seller in day1["sellers"]
} == initial_assortments, "city pulse must never rebuild persistent assortment"

ambient_event_types = {
    "ambient_sale",
    "ambient_busy_sale",
    "ambient_sellout",
    "ambient_top_up",
    "ambient_restore",
    "special_arrival",
    "special_departed",
}
day1_events = [
    event
    for seller in day1["sellers"]
    for event in seller["history"]
    if event.get("cycle") == 1 and event.get("event_type") in ambient_event_types
]
assert len(day1_events) == pulse["applied_mutations"]

# A large date jump still causes only one pulse; unseen days are not replayed.
jumped, action = sync_calendar_date(day1, "2045-01-10", engine)
assert action == "advanced"
assert jumped["stock_day"] == 2
assert jumped["stock_date"] == "2045-01-10"
assert all(seller["state"]["stock_cycle"] == 2 for seller in jumped["sellers"])
assert jumped["last_city_pulse"]["stock_day"] == 2

# Find ordinary visible finite shelf stock and make a purchase.
purchase_target = None
for seller in jumped["sellers"]:
    for row in seller["stock"]:
        if (
            row.get("assortment_role") in {"core", "regular", "occasional", "special"}
            and row.get("status") == "in_stock"
            and row.get("visibility", "public") != "hidden"
            and isinstance(row.get("quantity"), int)
            and row["quantity"] > 0
        ):
            purchase_target = (seller["entity_id"], row["item_id"])
            break
    if purchase_target:
        break
assert purchase_target is not None

seller_id, purchase_item_id = purchase_target
seller_before = next(row for row in jumped["sellers"] if row["entity_id"] == seller_id)
visible_before = sum(
    int(row["quantity"])
    for row in seller_before["stock"]
    if row["item_id"] == purchase_item_id
    and row.get("status") == "in_stock"
    and row.get("visibility", "public") != "hidden"
    and isinstance(row.get("quantity"), int)
)

purchased, receipt = purchase_item(
    jumped, seller_id, purchase_item_id, quantity=1, engine=engine
)
assert receipt["quantity"] == 1
seller_after = next(row for row in purchased["sellers"] if row["entity_id"] == seller_id)
visible_after = sum(
    int(row["quantity"])
    for row in seller_after["stock"]
    if row["item_id"] == purchase_item_id
    and row.get("status") == "in_stock"
    and row.get("visibility", "public") != "hidden"
    and isinstance(row.get("quantity"), int)
)
assert visible_after == visible_before - 1
assert any(
    row["event_type"] == "purchase"
    and row.get("item_id") == purchase_item_id
    for row in seller_after["history"]
)

# Build a pool of sourceable-but-unassorted item/seller pairs.
index_before = build_availability_index(purchased, engine)
coverage = build_catalogue_coverage(purchased, index_before, engine)
sourceable_pairs: list[tuple[str, str]] = []
for item in coverage["items"]:
    if item["coverage_status"] != "orderable_unassorted":
        continue
    for seller in item["orderable_sellers"]:
        sourceable_pairs.append((item["item_id"], seller["source_entity_id"]))
assert sourceable_pairs

# Ordering is uncertain once, at placement. Find one deterministic failure and verify
# retrying on the same stock day does not let callers spam the sourcing roll.
failed_state = None
failed_receipt = None
failed_pair = None
for item_id, source_seller_id in sourceable_pairs[:500]:
    candidate_state, candidate_receipt = place_order(
        purchased, source_seller_id, item_id, quantity=1, engine=engine
    )
    if not candidate_receipt["accepted"]:
        failed_state = candidate_state
        failed_receipt = candidate_receipt
        failed_pair = (item_id, source_seller_id)
        break
assert failed_state is not None and failed_receipt is not None and failed_pair is not None
assert failed_receipt["reason"] == "source_failed_today"
assert failed_receipt["retry_day"] == purchased["stock_day"] + 1

failed_item_id, failed_seller_id = failed_pair
failed_shop = next(
    row for row in failed_state["sellers"] if row["entity_id"] == failed_seller_id
)
failed_history_count = len(failed_shop["history"])
repeat_state, repeat_receipt = place_order(
    failed_state, failed_seller_id, failed_item_id, quantity=1, engine=engine
)
repeat_shop = next(
    row for row in repeat_state["sellers"] if row["entity_id"] == failed_seller_id
)
assert repeat_receipt["accepted"] is False
assert repeat_receipt["event_id"] == failed_receipt["event_id"]
assert len(repeat_shop["history"]) == failed_history_count

# Find one deterministic accepted sourcing attempt from the same unchanged city state.
ordered = None
order_receipt = None
order_item_id = None
order_seller_id = None
for item_id, source_seller_id in sourceable_pairs:
    candidate_state, candidate_receipt = place_order(
        purchased, source_seller_id, item_id, quantity=1, engine=engine
    )
    if candidate_receipt["accepted"]:
        ordered = candidate_state
        order_receipt = candidate_receipt
        order_item_id = item_id
        order_seller_id = source_seller_id
        break
assert ordered is not None
assert order_receipt is not None
assert order_item_id is not None
assert order_seller_id is not None
assert order_receipt["order_kind"] == "sourceable"
assert order_receipt["estimated_delivery_days"] >= 1

ordered_index = build_availability_index(ordered, engine)
ordered_item = next(row for row in ordered_index["items"] if row["item_id"] == order_item_id)
ordered_seller = next(
    row for row in ordered_item["sellers"]
    if row["source_entity_id"] == order_seller_id
)
assert ordered_seller["availability"] == "order"
assert ordered_seller["order_reason"] == "incoming"
assert ordered_seller["incoming_arrival_cycle"] == order_receipt["arrival_day"]

order_shop = next(row for row in ordered["sellers"] if row["entity_id"] == order_seller_id)
assert any(
    row["item_id"] == order_item_id
    and row.get("status") == "incoming"
    and row.get("assortment_role") == "order"
    and row.get("metadata", {}).get("source_confirmed") is True
    for row in order_shop["stock"]
)
assert any(
    row["event_type"] == "order_placed"
    and row.get("item_id") == order_item_id
    for row in order_shop["history"]
)

# Accepted orders do not roll supply again. Advancing to the promised day must deliver it,
# while the ambient city pulse ignores customer-reserved order stock.
delivered = ordered
while delivered["stock_day"] < order_receipt["arrival_day"]:
    delivered = advance_city_stock(delivered, engine)

delivered_shop = next(
    row for row in delivered["sellers"] if row["entity_id"] == order_seller_id
)
order_rows = [
    row for row in delivered_shop["stock"]
    if row["item_id"] == order_item_id and row.get("assortment_role") == "order"
]
assert order_rows
assert any(row.get("status") == "in_stock" for row in order_rows)
assert any(
    row["event_type"] == "delivery_received"
    and row.get("item_id") == order_item_id
    for row in delivered_shop["history"]
)

delivered_index = build_availability_index(delivered, engine)
delivered_item = next(
    row for row in delivered_index["items"] if row["item_id"] == order_item_id
)
delivered_seller = next(
    row for row in delivered_item["sellers"]
    if row["source_entity_id"] == order_seller_id
)
assert delivered_seller["availability"] == "in_stock"
assert delivered_seller["assortment_role"] == "order"
assert delivered_seller["normally_carried"] is False

print(
    "OK: daily city pulse; "
    f"day={delivered['stock_day']}, "
    f"pulse={delivered['last_city_pulse']['applied_mutations']}/"
    f"{delivered['last_city_pulse']['budget']}, "
    f"purchase={purchase_item_id}, "
    f"failed_order={failed_item_id}, "
    f"accepted_order={order_item_id}, "
    f"arrival_day={order_receipt['arrival_day']}"
)
