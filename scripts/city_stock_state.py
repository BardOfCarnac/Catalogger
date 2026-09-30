#!/usr/bin/env python3
"""Mutable daily stock state for the single shared Night City 2045 world.

Vend-R treats shops as available when queried. There is no opening-hours clock and no
hourly logistics simulation. The city has one abstract stock day. Advancing the day gives
every canonical catalogue seller exactly one lifecycle/restock pass, then rebuilds the
item -> seller availability index.

Calendar dates are optional synchronization metadata only. The stock engine itself sees
integer days/cycles.
"""
from __future__ import annotations

import argparse
import copy
import json
import random
from datetime import date
from pathlib import Path
from typing import Any

from build_city_stock import (
    DEFAULT_COVERAGE_OUTPUT,
    DEFAULT_INDEX_OUTPUT,
    build_availability_index,
    build_catalogue_coverage,
    build_city_stock,
)
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_OUTPUT = (
    ROOT / "build/data/worlds/night-city-2045/city-stock-state.v0.1.json"
)


class CityStockError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_iso_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    date.fromisoformat(raw)
    return raw


def _seller_by_entity_id(city: dict[str, Any], entity_id: str) -> dict[str, Any]:
    matches = [row for row in city.get("sellers", []) if row["entity_id"] == entity_id]
    if not matches:
        raise CityStockError(f"unknown canonical seller: {entity_id}")
    if len(matches) != 1:
        raise CityStockError(f"duplicate canonical seller in city state: {entity_id}")
    return matches[0]


def _bundle_from_seller(
    seller: dict[str, Any],
    engine: WorldStockEngine,
) -> dict[str, Any]:
    return {
        "format_version": "0.2.0",
        "engine_version": engine.model["version"],
        "shop": copy.deepcopy(seller["shop"]),
        "assortment": copy.deepcopy(seller["assortment"]),
        "stock": copy.deepcopy(seller["stock"]),
        "state": copy.deepcopy(seller["state"]),
        "history": copy.deepcopy(seller["history"]),
    }


def _apply_bundle_to_seller(
    seller: dict[str, Any],
    bundle: dict[str, Any],
) -> None:
    for key in ("shop", "assortment", "stock", "state", "history"):
        seller[key] = copy.deepcopy(bundle[key])


def _refresh_city_counts(city: dict[str, Any]) -> None:
    coverage = city.setdefault("coverage", {})
    sellers = city.get("sellers", [])
    coverage["catalogue_stock_sellers"] = len(sellers)
    coverage["persistent_assortment_lines"] = sum(
        len(row.get("assortment", [])) for row in sellers
    )
    coverage["cycle_stock_rows"] = sum(len(row.get("stock", [])) for row in sellers)


def _record_seller_event(
    seller: dict[str, Any],
    engine: WorldStockEngine,
    cycle: int,
    event_type: str,
    item_id: str | None = None,
    quantity_delta: int | None = None,
    price: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one lifecycle-style event without copying the whole seller bundle."""
    bundle = {
        "shop": seller["shop"],
        "history": seller.setdefault("history", []),
    }
    event = engine._append_event(
        bundle,
        cycle,
        event_type,
        item_id=item_id,
        quantity_delta=quantity_delta,
        price=price,
        metadata=metadata,
    )
    seller["history"] = bundle["history"]
    seller.setdefault("state", {}).setdefault("last_cycle_events", []).append(event["id"])
    return event


def _weighted_label(
    rng: random.Random,
    weights: dict[str, int | float],
) -> str:
    rows = [(label, max(0.0, float(weight))) for label, weight in weights.items()]
    total = sum(weight for _label, weight in rows)
    if total <= 0:
        raise CityStockError("city pulse mutation weights must contain a positive value")
    target = rng.random() * total
    running = 0.0
    for label, weight in rows:
        running += weight
        if target <= running:
            return label
    return rows[-1][0]


def _assortment_by_item(seller: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["item_id"]: row
        for row in seller.get("assortment", [])
        if row.get("active", True)
    }


def _present_stock_row(
    seller: dict[str, Any],
    item_id: str,
) -> dict[str, Any] | None:
    rows = [
        row
        for row in seller.get("stock", [])
        if row["item_id"] == item_id
        and row.get("status") in {"in_stock", "reserved"}
        and (row.get("quantity") is None or int(row.get("quantity", 0)) > 0)
    ]
    return rows[0] if rows else None


def _deliver_due_orders(
    city: dict[str, Any],
    engine: WorldStockEngine,
    next_day: int,
) -> int:
    delivered = 0
    for seller in city.get("sellers", []):
        for row in seller.get("stock", []):
            if row.get("status") != "incoming":
                continue
            arrival = row.get("metadata", {}).get("arrival_cycle")
            if not isinstance(arrival, int) or arrival > next_day:
                continue
            row["status"] = "in_stock"
            row["added_cycle"] = next_day
            row.setdefault("metadata", {})["delivered_cycle"] = next_day
            _record_seller_event(
                seller,
                engine,
                next_day,
                "delivery_received",
                item_id=row["item_id"],
                quantity_delta=row.get("quantity"),
                price=row.get("asking_price"),
                metadata={
                    "stock_id": row.get("id"),
                    "order_kind": row.get("metadata", {}).get("order_kind"),
                },
            )
            delivered += 1
    return delivered


def _pulse_sale_candidates(
    city: dict[str, Any],
    used: set[tuple[str, str]],
    minimum_quantity: int = 1,
    maximum_quantity: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for seller in city.get("sellers", []):
        for row in seller.get("stock", []):
            key = (seller["entity_id"], row.get("id") or row["item_id"])
            if key in used:
                continue
            if row.get("assortment_role") not in {"core", "regular", "occasional"}:
                continue
            if row.get("status") != "in_stock":
                continue
            if row.get("visibility", "public") == "hidden":
                continue
            quantity = row.get("quantity")
            if not isinstance(quantity, int) or quantity < minimum_quantity:
                continue
            if maximum_quantity is not None and quantity > maximum_quantity:
                continue
            candidates.append((seller, row))
    return candidates


def _pulse_top_up_candidates(
    city: dict[str, Any],
    used: set[tuple[str, str]],
) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    candidates: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for seller in city.get("sellers", []):
        assortment = _assortment_by_item(seller)
        for row in seller.get("stock", []):
            key = (seller["entity_id"], row["item_id"])
            if key in used or row.get("status") != "in_stock":
                continue
            line = assortment.get(row["item_id"])
            if line is None or row.get("assortment_role") not in {"core", "regular", "occasional"}:
                continue
            target = line.get("target_quantity")
            quantity = row.get("quantity")
            if not isinstance(target, int) or not isinstance(quantity, int):
                continue
            if quantity < target:
                candidates.append((seller, row, line))
    return candidates


def _pulse_restore_candidates(
    city: dict[str, Any],
    used: set[tuple[str, str]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for seller in city.get("sellers", []):
        for item_id, line in _assortment_by_item(seller).items():
            key = (seller["entity_id"], item_id)
            if key in used:
                continue
            if _present_stock_row(seller, item_id) is not None:
                continue
            if any(
                row["item_id"] == item_id and row.get("status") == "incoming"
                for row in seller.get("stock", [])
            ):
                continue
            candidates.append((seller, line))
    return candidates


def _apply_city_pulse(
    city: dict[str, Any],
    engine: WorldStockEngine,
    next_day: int,
) -> dict[str, Any]:
    """Generate a small citywide mutation budget, then distribute it across stock."""
    config = engine.model.get("city_pulse", {})
    low, high = config.get("daily_mutation_range", [40, 70])
    rng = random.Random(
        f"{city.get('world_id', 'night-city-2045')}:city-pulse:{next_day}:"
        f"{engine.model['version']}"
    )
    budget = rng.randint(int(low), int(high))
    weights = config.get(
        "mutation_weights",
        {
            "sale": 45,
            "busy_sale": 12,
            "sellout": 8,
            "top_up": 18,
            "restore": 9,
            "special_arrival": 5,
            "special_departure": 3,
        },
    )
    plan = [_weighted_label(rng, weights) for _ in range(budget)]
    requested: dict[str, int] = {}
    applied: dict[str, int] = {}
    used: set[tuple[str, str]] = set()
    touched_sellers: set[str] = set()

    for mutation in plan:
        requested[mutation] = requested.get(mutation, 0) + 1
        changed = False

        if mutation == "sale":
            candidates = _pulse_sale_candidates(city, used, minimum_quantity=1)
            if candidates:
                seller, row = rng.choice(candidates)
                row["quantity"] -= 1
                if row["quantity"] <= 0:
                    row["quantity"] = 0
                    row["status"] = "sold"
                used.add((seller["entity_id"], row.get("id") or row["item_id"]))
                _record_seller_event(
                    seller,
                    engine,
                    next_day,
                    "ambient_sale",
                    item_id=row["item_id"],
                    quantity_delta=-1,
                    price=row.get("asking_price"),
                    metadata={"city_pulse": True},
                )
                touched_sellers.add(seller["entity_id"])
                changed = True

        elif mutation == "busy_sale":
            minimum = 2
            candidates = _pulse_sale_candidates(city, used, minimum_quantity=minimum)
            if candidates:
                seller, row = rng.choice(candidates)
                qlow, qhigh = config.get("busy_sale_quantity_range", [2, 4])
                amount = min(int(row["quantity"]), rng.randint(int(qlow), int(qhigh)))
                row["quantity"] -= amount
                if row["quantity"] <= 0:
                    row["quantity"] = 0
                    row["status"] = "sold"
                used.add((seller["entity_id"], row.get("id") or row["item_id"]))
                _record_seller_event(
                    seller,
                    engine,
                    next_day,
                    "ambient_busy_sale",
                    item_id=row["item_id"],
                    quantity_delta=-amount,
                    price=row.get("asking_price"),
                    metadata={"city_pulse": True},
                )
                touched_sellers.add(seller["entity_id"])
                changed = True

        elif mutation == "sellout":
            maximum = int(config.get("sellout_max_quantity", 3))
            candidates = _pulse_sale_candidates(
                city,
                used,
                minimum_quantity=1,
                maximum_quantity=maximum,
            )
            if candidates:
                seller, row = rng.choice(candidates)
                amount = int(row["quantity"])
                row["quantity"] = 0
                row["status"] = "sold"
                used.add((seller["entity_id"], row.get("id") or row["item_id"]))
                _record_seller_event(
                    seller,
                    engine,
                    next_day,
                    "ambient_sellout",
                    item_id=row["item_id"],
                    quantity_delta=-amount,
                    price=row.get("asking_price"),
                    metadata={"city_pulse": True},
                )
                touched_sellers.add(seller["entity_id"])
                changed = True

        elif mutation == "top_up":
            candidates = _pulse_top_up_candidates(city, used)
            if candidates:
                seller, row, line = rng.choice(candidates)
                target = int(line["target_quantity"])
                old_quantity = int(row["quantity"])
                row["quantity"] = target
                used.add((seller["entity_id"], row["item_id"]))
                _record_seller_event(
                    seller,
                    engine,
                    next_day,
                    "ambient_top_up",
                    item_id=row["item_id"],
                    quantity_delta=target - old_quantity,
                    price=row.get("asking_price"),
                    metadata={"city_pulse": True, "target_quantity": target},
                )
                line["last_stocked_cycle"] = next_day
                touched_sellers.add(seller["entity_id"])
                changed = True

        elif mutation == "restore":
            candidates = _pulse_restore_candidates(city, used)
            if candidates:
                seller, line = rng.choice(candidates)
                item_id = line["item_id"]
                role = line["role"]
                row_rng = random.Random(
                    f"{seller['shop']['seed']}:city-pulse:restore:{next_day}:{item_id}"
                )
                row = engine._stock_row(row_rng, seller["shop"], item_id, role, next_day)
                target = line.get("target_quantity")
                if isinstance(target, int):
                    row["quantity"] = target
                seller["stock"].append(row)
                line["last_stocked_cycle"] = next_day
                used.add((seller["entity_id"], item_id))
                _record_seller_event(
                    seller,
                    engine,
                    next_day,
                    "ambient_restore",
                    item_id=item_id,
                    quantity_delta=row.get("quantity"),
                    price=row.get("asking_price"),
                    metadata={"city_pulse": True, "role": role},
                )
                touched_sellers.add(seller["entity_id"])
                changed = True

        elif mutation == "special_departure":
            candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for seller in city.get("sellers", []):
                for row in seller.get("stock", []):
                    key = (seller["entity_id"], row.get("id") or row["item_id"])
                    if key in used:
                        continue
                    if row.get("assortment_role") != "special" or row.get("status") != "in_stock":
                        continue
                    candidates.append((seller, row))
            if candidates:
                seller, row = rng.choice(candidates)
                quantity = row.get("quantity")
                row["quantity"] = 0 if isinstance(quantity, int) else quantity
                row["status"] = "sold"
                used.add((seller["entity_id"], row.get("id") or row["item_id"]))
                _record_seller_event(
                    seller,
                    engine,
                    next_day,
                    "special_departed",
                    item_id=row["item_id"],
                    quantity_delta=(-int(quantity) if isinstance(quantity, int) else None),
                    price=row.get("asking_price"),
                    metadata={"city_pulse": True},
                )
                touched_sellers.add(seller["entity_id"])
                changed = True

        elif mutation == "special_arrival":
            sellers = list(city.get("sellers", []))
            rng.shuffle(sellers)
            for seller in sellers:
                excluded = {
                    row["item_id"] for row in seller.get("assortment", [])
                } | {
                    row["item_id"]
                    for row in seller.get("stock", [])
                    if row.get("status") in {"in_stock", "incoming", "reserved"}
                }
                special_context = copy.deepcopy(seller["shop"])
                special_context["specials"] = [1, 1]
                row_rng = random.Random(
                    f"{seller['shop']['seed']}:city-pulse:special:{next_day}:"
                    f"{len(seller.get('history', []))}"
                )
                rows = engine._pick_specials(row_rng, special_context, excluded, next_day)
                if not rows:
                    continue
                row = rows[0]
                seller["stock"].append(row)
                used.add((seller["entity_id"], row.get("id") or row["item_id"]))
                _record_seller_event(
                    seller,
                    engine,
                    next_day,
                    "special_arrival",
                    item_id=row["item_id"],
                    quantity_delta=row.get("quantity"),
                    price=row.get("asking_price"),
                    metadata={"city_pulse": True},
                )
                touched_sellers.add(seller["entity_id"])
                changed = True
                break

        if changed:
            applied[mutation] = applied.get(mutation, 0) + 1

    return {
        "stock_day": next_day,
        "budget": budget,
        "requested": dict(sorted(requested.items())),
        "applied": dict(sorted(applied.items())),
        "applied_mutations": sum(applied.values()),
        "skipped_mutations": budget - sum(applied.values()),
        "touched_sellers": len(touched_sellers),
    }


def initialize_city_stock(
    engine: WorldStockEngine | None = None,
    stock_date: str | None = None,
) -> dict[str, Any]:
    engine = engine or WorldStockEngine()
    city = build_city_stock(engine)
    city["stock_day"] = 0
    city["stock_cycle"] = 0
    city["stock_date"] = _validate_iso_date(stock_date)
    city["daily_stock_policy"] = {
        "city_pulses_per_day": 1,
        "full_seller_restock_passes": 0,
        "opening_hours_enforced": False,
        "clock_simulation": False,
        "missed_calendar_days_replayed": False,
        "meaning": (
            "One explicit city-day advance generates a small citywide stock-change budget "
            "and distributes it across suitable canonical sellers. Shops are otherwise "
            "treated as available when queried."
        ),
    }
    city["last_city_pulse"] = None
    _refresh_city_counts(city)
    return city


def advance_city_stock(
    city: dict[str, Any],
    engine: WorldStockEngine | None = None,
    stock_date: str | None = None,
) -> dict[str, Any]:
    """Advance the shared city by exactly one cheap, city-scale stock pulse."""
    engine = engine or WorldStockEngine()
    result = copy.deepcopy(city)
    current_day = int(result.get("stock_day", result.get("stock_cycle", 0)))
    next_day = current_day + 1

    # Every seller shares the city's day counter, but we do not run a full restock simulation
    # for every seller. Daily movement comes from one small mutation budget for the whole city.
    for seller in result.get("sellers", []):
        seller_cycle = int(seller.get("state", {}).get("stock_cycle", current_day))
        if seller_cycle != current_day:
            raise CityStockError(
                f"seller cycle drift for {seller['entity_id']}: "
                f"seller={seller_cycle} city={current_day}"
            )
        seller.setdefault("state", {})["stock_cycle"] = next_day
        seller["state"]["last_cycle_events"] = []

    delivered = _deliver_due_orders(result, engine, next_day)
    pulse = _apply_city_pulse(result, engine, next_day)
    pulse["confirmed_deliveries"] = delivered

    result["stock_day"] = next_day
    result["stock_cycle"] = next_day
    result["last_city_pulse"] = pulse
    if stock_date is not None:
        result["stock_date"] = _validate_iso_date(stock_date)
    _refresh_city_counts(result)
    return result


def sync_calendar_date(
    city: dict[str, Any],
    target_date: str,
    engine: WorldStockEngine | None = None,
) -> tuple[dict[str, Any], str]:
    """Synchronize an optional calendar date without replaying missed days.

    First synchronization labels the current stock day. Repeating the same date is a no-op.
    Any later date advances the city exactly once and labels the resulting stock day with the
    new date. This deliberately avoids simulating unseen intermediate days.
    """
    engine = engine or WorldStockEngine()
    target_date = _validate_iso_date(target_date) or target_date
    current = city.get("stock_date")
    if current is None:
        result = copy.deepcopy(city)
        result["stock_date"] = target_date
        return result, "initialized"
    if current == target_date:
        return copy.deepcopy(city), "unchanged"

    current_day = date.fromisoformat(str(current))
    requested_day = date.fromisoformat(target_date)
    if requested_day < current_day:
        raise CityStockError(
            f"cannot synchronize stock backwards: {target_date} < {current}"
        )
    return advance_city_stock(city, engine, stock_date=target_date), "advanced"


def _present_purchase_rows(
    seller: dict[str, Any],
    item_id: str,
) -> list[dict[str, Any]]:
    visibility_order = {"public": 0, "ask": 1, "hidden": 2}
    rows = [
        row
        for row in seller.get("stock", [])
        if row["item_id"] == item_id
        and row.get("status") == "in_stock"
        and row.get("visibility", "public") != "hidden"
        and (row.get("quantity") is None or int(row.get("quantity", 0)) > 0)
    ]
    rows.sort(
        key=lambda row: (
            visibility_order.get(row.get("visibility", "public"), 9),
            0 if row.get("assortment_role") == "order" else 1,
            row.get("added_cycle", 0),
            row.get("id", ""),
        )
    )
    return rows


def purchase_item(
    city: dict[str, Any],
    seller_entity_id: str,
    item_id: str,
    quantity: int = 1,
    engine: WorldStockEngine | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Purchase visible current stock and persist the quantity reduction."""
    if quantity < 1:
        raise CityStockError("purchase quantity must be at least 1")
    engine = engine or WorldStockEngine()
    if item_id not in engine.items_by_id:
        raise CityStockError(f"unknown catalogue item: {item_id}")

    result = copy.deepcopy(city)
    seller = _seller_by_entity_id(result, seller_entity_id)
    rows = _present_purchase_rows(seller, item_id)
    finite_available = sum(
        int(row["quantity"]) for row in rows if row.get("quantity") is not None
    )
    unlimited = any(row.get("quantity") is None for row in rows)
    if not unlimited and finite_available < quantity:
        raise CityStockError(
            f"insufficient current stock for {item_id} at {seller['name']}: "
            f"requested={quantity} available={finite_available}"
        )

    remaining = quantity
    total_price = 0.0
    priced_units = 0
    stock_ids: list[str] = []

    for row in rows:
        if remaining <= 0:
            break
        row_quantity = row.get("quantity")
        take = remaining if row_quantity is None else min(remaining, int(row_quantity))
        if take <= 0:
            continue
        stock_ids.append(row.get("id", ""))
        if row.get("asking_price") is not None:
            total_price += float(row["asking_price"]) * take
            priced_units += take
        if row_quantity is not None:
            row["quantity"] = int(row_quantity) - take
            if row["quantity"] <= 0:
                row["quantity"] = 0
                row["status"] = "sold"
        remaining -= take

    bundle = _bundle_from_seller(seller, engine)
    event = engine._append_event(
        bundle,
        int(result.get("stock_day", result.get("stock_cycle", 0))),
        "purchase",
        item_id=item_id,
        quantity_delta=-quantity,
        price=(round(total_price / priced_units, 2) if priced_units else None),
        metadata={
            "requested_quantity": quantity,
            "stock_ids": [value for value in stock_ids if value],
            "total_price": round(total_price, 2) if priced_units else None,
        },
    )
    _apply_bundle_to_seller(seller, bundle)
    _refresh_city_counts(result)

    return result, {
        "event_id": event["id"],
        "seller_entity_id": seller_entity_id,
        "seller_name": seller["name"],
        "item_id": item_id,
        "item_name": engine.items_by_id[item_id]["name"],
        "quantity": quantity,
        "total_price": round(total_price, 2) if priced_units else None,
    }


def place_order(
    city: dict[str, Any],
    seller_entity_id: str,
    item_id: str,
    quantity: int = 1,
    engine: WorldStockEngine | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Attempt to source an item once; accepted orders then have reliable delivery."""
    if quantity < 1:
        raise CityStockError("order quantity must be at least 1")
    engine = engine or WorldStockEngine()
    if item_id not in engine.items_by_id:
        raise CityStockError(f"unknown catalogue item: {item_id}")

    result = copy.deepcopy(city)
    seller = _seller_by_entity_id(result, seller_entity_id)
    assortment = {row["item_id"]: row for row in seller.get("assortment", [])}

    if _present_purchase_rows(seller, item_id):
        raise CityStockError(
            f"{engine.items_by_id[item_id]['name']} is currently in stock at {seller['name']}"
        )
    if any(
        row["item_id"] == item_id and row.get("status") == "incoming"
        for row in seller.get("stock", [])
    ):
        raise CityStockError(
            f"{engine.items_by_id[item_id]['name']} already has an incoming order at {seller['name']}"
        )

    normally_carried = item_id in assortment
    score = float(engine.score(item_id, seller["shop"])["score"])
    threshold = float(engine.model["role_selection"]["regular"]["minimum_score"])
    if not normally_carried:
        if not engine.eligible(item_id, seller["shop"], special=False):
            raise CityStockError(
                f"{seller['name']} cannot source {engine.items_by_id[item_id]['name']}"
            )
        if score < threshold:
            raise CityStockError(
                f"{seller['name']} is only weakly eligible for "
                f"{engine.items_by_id[item_id]['name']} (score={score:g}, threshold={threshold:g})"
            )

    cycle = int(result.get("stock_day", result.get("stock_cycle", 0)))
    previous_attempt = next(
        (
            row for row in reversed(seller.get("history", []))
            if row.get("item_id") == item_id
            and row.get("cycle") == cycle
            and row.get("event_type") in {"order_placed", "order_source_failed"}
        ),
        None,
    )
    if previous_attempt is not None:
        if previous_attempt["event_type"] == "order_source_failed":
            return result, {
                "accepted": False,
                "seller_entity_id": seller_entity_id,
                "seller_name": seller["name"],
                "item_id": item_id,
                "item_name": engine.items_by_id[item_id]["name"],
                "quantity": quantity,
                "attempt_day": cycle,
                "retry_day": cycle + 1,
                "reason": "source_failed_today",
                "event_id": previous_attempt["id"],
            }
        raise CityStockError(
            f"{engine.items_by_id[item_id]['name']} already has an accepted order "
            f"at {seller['name']} today"
        )

    attempts = sum(
        1
        for row in seller.get("history", [])
        if row.get("event_type") in {"order_placed", "order_source_failed"}
        and row.get("item_id") == item_id
    )
    rng = random.Random(
        f"{seller['shop']['seed']}:source-order:{cycle}:{item_id}:"
        f"{attempts}:{engine.model['version']}"
    )

    profile = engine.commercial_by_id[item_id]
    supply = profile.get("supply_profile", "regular")
    pulse_config = engine.model.get("city_pulse", {})
    base_chance = float(
        pulse_config.get("order_source_success_by_supply", {}).get(supply, 0.75)
    )
    bonus_cap = float(pulse_config.get("order_affinity_bonus_cap", 0.08))
    affinity_bonus = min(
        bonus_cap,
        max(0.0, (score - threshold) / 100.0 * bonus_cap),
    )
    source_chance = min(0.995, max(0.01, base_chance + affinity_bonus))
    source_roll = rng.random()

    if source_roll > source_chance:
        event = _record_seller_event(
            seller,
            engine,
            cycle,
            "order_source_failed",
            item_id=item_id,
            quantity_delta=quantity,
            metadata={
                "normally_carried": normally_carried,
                "supply_profile": supply,
                "affinity_score": score,
                "source_chance": round(source_chance, 4),
                "source_roll": round(source_roll, 4),
            },
        )
        _refresh_city_counts(result)
        return result, {
            "accepted": False,
            "event_id": event["id"],
            "seller_entity_id": seller_entity_id,
            "seller_name": seller["name"],
            "item_id": item_id,
            "item_name": engine.items_by_id[item_id]["name"],
            "quantity": quantity,
            "attempt_day": cycle,
            "retry_day": cycle + 1,
            "reason": "source_failed_today",
        }

    row = engine._stock_row(rng, seller["shop"], item_id, "order", cycle)
    engine._apply_cycle_row_modifiers(
        rng,
        row,
        seller["shop"],
        seller["state"],
        target_quantity=quantity,
    )
    delay = engine._delivery_delay(rng, item_id)
    row["quantity"] = quantity
    row["status"] = "incoming"
    row["assortment_role"] = "order"
    row["stock_reason"] = "order"
    row["metadata"] = {
        **row.get("metadata", {}),
        "ordered_cycle": cycle,
        "arrival_cycle": cycle + delay,
        "order_kind": "assortment_order" if normally_carried else "sourceable",
        "requested_quantity": quantity,
        "affinity_score": score,
        "source_confirmed": True,
    }
    seller["stock"].append(row)

    event = _record_seller_event(
        seller,
        engine,
        cycle,
        "order_placed",
        item_id=item_id,
        quantity_delta=quantity,
        price=row.get("asking_price"),
        metadata={
            "arrival_cycle": cycle + delay,
            "order_kind": row["metadata"]["order_kind"],
            "affinity_score": score,
            "stock_id": row["id"],
            "source_confirmed": True,
        },
    )
    _refresh_city_counts(result)

    return result, {
        "accepted": True,
        "event_id": event["id"],
        "seller_entity_id": seller_entity_id,
        "seller_name": seller["name"],
        "item_id": item_id,
        "item_name": engine.items_by_id[item_id]["name"],
        "quantity": quantity,
        "ordered_day": cycle,
        "arrival_day": cycle + delay,
        "estimated_delivery_days": delay,
        "order_kind": row["metadata"]["order_kind"],
        "asking_price": row.get("asking_price"),
    }


def build_state_outputs(
    city: dict[str, Any],
    engine: WorldStockEngine | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    engine = engine or WorldStockEngine()
    index = build_availability_index(city, engine)
    coverage = build_catalogue_coverage(city, index, engine)
    return index, coverage


def write_state_outputs(
    city: dict[str, Any],
    state_output: Path,
    index_output: Path,
    coverage_output: Path,
    engine: WorldStockEngine | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    engine = engine or WorldStockEngine()
    index, coverage = build_state_outputs(city, engine)
    for path in (state_output, index_output, coverage_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    state_output.write_text(
        json.dumps(city, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    index_output.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    coverage_output.write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index, coverage


def _mutation_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    source = Path(args.input)
    state_output = Path(args.output) if args.output else source
    index_output = Path(args.index_output) if args.index_output else DEFAULT_INDEX_OUTPUT
    coverage_output = (
        Path(args.coverage_output) if args.coverage_output else DEFAULT_COVERAGE_OUTPUT
    )
    return state_output, index_output, coverage_output


def _add_mutation_io(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", help="defaults to overwriting --input")
    parser.add_argument("--index-output")
    parser.add_argument("--coverage-output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the shared Night City daily stock state")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create the canonical cycle-0 city state")
    init.add_argument("--date", dest="stock_date", help="optional YYYY-MM-DD label")
    init.add_argument("--output", default=str(DEFAULT_STATE_OUTPUT))
    init.add_argument("--index-output", default=str(DEFAULT_INDEX_OUTPUT))
    init.add_argument("--coverage-output", default=str(DEFAULT_COVERAGE_OUTPUT))

    advance = sub.add_parser("advance", help="apply one citywide daily stock pulse")
    _add_mutation_io(advance)
    advance.add_argument("--date", dest="stock_date", help="optional YYYY-MM-DD label")

    sync = sub.add_parser(
        "sync-date",
        help="initialize/synchronize a calendar label; a later date advances exactly once",
    )
    _add_mutation_io(sync)
    sync.add_argument("--date", dest="stock_date", required=True)

    purchase = sub.add_parser("purchase", help="reduce current stock at one canonical seller")
    _add_mutation_io(purchase)
    purchase.add_argument("--seller", required=True)
    purchase.add_argument("--item", required=True)
    purchase.add_argument("--quantity", type=int, default=1)

    order = sub.add_parser("order", help="place a sourced order without changing assortment")
    _add_mutation_io(order)
    order.add_argument("--seller", required=True)
    order.add_argument("--item", required=True)
    order.add_argument("--quantity", type=int, default=1)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    engine = WorldStockEngine()

    if args.command == "init":
        city = initialize_city_stock(engine, args.stock_date)
        index, _coverage = write_state_outputs(
            city,
            Path(args.output),
            Path(args.index_output),
            Path(args.coverage_output),
            engine,
        )
        print(
            f"Initialized stock_day={city['stock_day']} sellers={len(city['sellers'])} "
            f"indexed_items={index['indexed_item_count']}"
        )
        return

    source = Path(args.input)
    city = load_json(source)

    if args.command == "advance":
        city = advance_city_stock(city, engine, args.stock_date)
        message = f"Advanced to stock_day={city['stock_day']}"
    elif args.command == "sync-date":
        city, action = sync_calendar_date(city, args.stock_date, engine)
        message = (
            f"Calendar sync={action} stock_day={city.get('stock_day', 0)} "
            f"stock_date={city.get('stock_date')}"
        )
    elif args.command == "purchase":
        city, receipt = purchase_item(
            city, args.seller, args.item, args.quantity, engine
        )
        message = json.dumps(receipt, ensure_ascii=False)
    elif args.command == "order":
        city, receipt = place_order(
            city, args.seller, args.item, args.quantity, engine
        )
        message = json.dumps(receipt, ensure_ascii=False)
    else:
        raise AssertionError(args.command)

    state_output, index_output, coverage_output = _mutation_paths(args)
    index, _coverage = write_state_outputs(
        city, state_output, index_output, coverage_output, engine
    )
    print(message)
    print(
        f"Wrote state={state_output} index={index_output} "
        f"indexed_items={index['indexed_item_count']}"
    )


if __name__ == "__main__":
    main()
