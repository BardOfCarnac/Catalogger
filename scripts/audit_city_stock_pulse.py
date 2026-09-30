#!/usr/bin/env python3
"""Short diagnostic run for the intentionally impressionistic Night City stock pulse."""
from __future__ import annotations

from collections import Counter

from city_stock_state import advance_city_stock, initialize_city_stock
from world_stock_engine import WorldStockEngine


def metrics(city):
    current_rows = 0
    finite_units = 0
    sold_rows = 0
    incoming_rows = 0
    specials = 0
    for seller in city["sellers"]:
        for row in seller["stock"]:
            status = row.get("status")
            quantity = row.get("quantity")
            if status == "in_stock" and (quantity is None or int(quantity) > 0):
                current_rows += 1
                if isinstance(quantity, int):
                    finite_units += quantity
                if row.get("assortment_role") == "special":
                    specials += 1
            elif status == "sold":
                sold_rows += 1
            elif status == "incoming":
                incoming_rows += 1
    return {
        "current_rows": current_rows,
        "finite_units": finite_units,
        "sold_rows": sold_rows,
        "incoming_rows": incoming_rows,
        "specials": specials,
    }


engine = WorldStockEngine()
city = initialize_city_stock(engine)
assortment_signature = {
    seller["entity_id"]: tuple(
        sorted((row["item_id"], row["role"]) for row in seller["assortment"])
    )
    for seller in city["sellers"]
}

print("day  current  units  sold  incoming  specials  pulse  touched  mutations")
print(
    f"{city['stock_day']:>3}  "
    f"{metrics(city)['current_rows']:>7}  "
    f"{metrics(city)['finite_units']:>5}  "
    f"{metrics(city)['sold_rows']:>4}  "
    f"{metrics(city)['incoming_rows']:>8}  "
    f"{metrics(city)['specials']:>8}  "
    f"{'-':>5}  {'-':>7}  -"
)

totals = Counter()
for _ in range(14):
    city = advance_city_stock(city, engine)
    pulse = city["last_city_pulse"]
    day_metrics = metrics(city)
    for kind, count in pulse["applied"].items():
        totals[kind] += count

    assert {
        seller["entity_id"]: tuple(
            sorted((row["item_id"], row["role"]) for row in seller["assortment"])
        )
        for seller in city["sellers"]
    } == assortment_signature
    assert pulse["applied_mutations"] > 0
    assert day_metrics["current_rows"] > 0

    print(
        f"{city['stock_day']:>3}  "
        f"{day_metrics['current_rows']:>7}  "
        f"{day_metrics['finite_units']:>5}  "
        f"{day_metrics['sold_rows']:>4}  "
        f"{day_metrics['incoming_rows']:>8}  "
        f"{day_metrics['specials']:>8}  "
        f"{pulse['applied_mutations']:>2}/{pulse['budget']:<2}  "
        f"{pulse['touched_sellers']:>7}  "
        + ",".join(f"{key}:{value}" for key, value in pulse["applied"].items())
    )

print("14-day applied totals:", ", ".join(f"{k}={v}" for k, v in sorted(totals.items())))
