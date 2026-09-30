#!/usr/bin/env python3
"""Regression tests for the shared once-per-day Night City stock state."""
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
assert city["daily_stock_policy"]["restock_passes_per_day"] == 1
assert city["daily_stock_policy"]["opening_hours_enforced"] is False
assert city["daily_stock_policy"]["clock_simulation"] is False

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
assert {
    seller["entity_id"]: {
        (row["item_id"], row["role"])
        for row in seller["assortment"]
    }
    for seller in day1["sellers"]
} == initial_assortments, "daily restock must never rebuild persistent assortment"

# A large date jump still causes only one stock pass; unseen days are not replayed.
jumped, action = sync_calendar_date(day1, "2045-01-10", engine)
assert action == "advanced"
assert jumped["stock_day"] == 2
assert jumped["stock_date"] == "2045-01-10"
assert all(seller["state"]["stock_cycle"] == 2 for seller in jumped["sellers"])

# Find ordinary visible finite shelf stock and make a purchase.
purchase_target = None
for seller in jumped["sellers"]:
    for row in seller["stock"]:
        if (
            row.get("status") == "in_stock"
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

# Choose an item that is not a persistent line anywhere but can be sourced by a canonical seller.
index_before = build_availability_index(purchased, engine)
coverage = build_catalogue_coverage(purchased, index_before, engine)
orderable = next(
    row for row in coverage["items"]
    if row["coverage_status"] == "orderable_unassorted"
    and row["orderable_sellers"]
)
order_item_id = orderable["item_id"]
order_seller_id = orderable["orderable_sellers"][0]["source_entity_id"]

pre_item = next(row for row in index_before["items"] if row["item_id"] == order_item_id)
pre_seller = next(
    row for row in pre_item["sellers"]
    if row["source_entity_id"] == order_seller_id
)
assert pre_seller["availability"] == "order"
assert pre_seller["order_reason"] == "sourceable"
assert pre_seller["normally_carried"] is False

ordered, order_receipt = place_order(
    purchased, order_seller_id, order_item_id, quantity=1, engine=engine
)
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
    for row in order_shop["stock"]
)
assert any(
    row["event_type"] == "order_placed"
    and row.get("item_id") == order_item_id
    for row in order_shop["history"]
)

# Advance one city day at a time until the order's declared arrival day.
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
    "OK: daily city stock; "
    f"day={delivered['stock_day']}, "
    f"purchase={purchase_item_id}, "
    f"order={order_item_id}, "
    f"arrival_day={order_receipt['arrival_day']}"
)
