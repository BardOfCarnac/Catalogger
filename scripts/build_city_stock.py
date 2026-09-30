#!/usr/bin/env python3
"""Materialize the current canonical Night City 2045 catalogue-stock state.

This is deliberately not a shop generator. It realizes only source-reviewed canonical
entities that already carry an explicit `stocking` block. Local wares, services, channels,
markets and contextual places remain source data unless they explicitly opt into catalogue
stock.

Outputs:
  - city-stock.v0.1.json: persistent cycle-0 bundles for canonical stock-bearing sellers
  - availability-index.v0.1.json: reverse item -> seller availability lookup

The availability index includes normally-carried assortment lines even when absent from the
current cycle, so Vend-R can distinguish "sold out" from "this shop does not carry it".
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from world_fixture import normalize_document, stable_shop_id
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
WORLD_ID = "night-city-2045"
WORLD_DIR = ROOT / "data/worlds" / WORLD_ID
DEFAULT_CITY_OUTPUT = ROOT / "build/data/worlds/night-city-2045/city-stock.v0.1.json"
DEFAULT_INDEX_OUTPUT = ROOT / "build/data/worlds/night-city-2045/availability-index.v0.1.json"
DEFAULT_COVERAGE_OUTPUT = ROOT / "build/data/worlds/night-city-2045/stock-coverage.v0.1.json"

CATALOG_MODES = {
    "catalog_stock",
    "catalog_and_service",
    "catalog_and_local_wares",
    "catalog_and_local_wares_and_service",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_paths() -> list[Path]:
    paths = sorted(WORLD_DIR.glob("*.v1.json"))
    recovered = WORLD_DIR / "recovered"
    if recovered.exists():
        paths.extend(sorted(recovered.glob("*.v1.json")))
    return paths


def _reviewed_entities() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()
    files_seen = 0
    recovered_files = 0

    for path in fixture_paths():
        raw = load_json(path)
        if raw.get("world_id") != WORLD_ID:
            continue
        doc = normalize_document(raw)
        if doc.get("fixture_status") != "source_reviewed":
            continue
        files_seen += 1
        if path.parent.name == "recovered":
            recovered_files += 1

        for source_entity in doc["entities"]:
            review = source_entity.get("review_status", doc["fixture_status"])
            if review != "source_reviewed":
                continue
            entity = copy.deepcopy(source_entity)
            entity["_fixture_id"] = doc["fixture_id"]
            entity["_fixture_path"] = str(path.relative_to(ROOT))
            entity["_recovered_fixture"] = path.parent.name == "recovered"
            entity.setdefault("provenance", doc.get("provenance"))
            if entity["entity_id"] in seen:
                raise ValueError(f"duplicate canonical entity id: {entity['entity_id']}")
            seen.add(entity["entity_id"])
            entities.append(entity)

    metadata = {
        "fixture_files": files_seen,
        "recovered_fixture_files": recovered_files,
        "source_reviewed_entities": len(entities),
    }
    return entities, metadata


def _candidate_reason(entity: dict[str, Any]) -> str | None:
    if entity.get("stocking"):
        return None

    mode = entity.get("commercial_mode")
    if mode in CATALOG_MODES:
        return f"commercial_mode={mode} but no stocking block"

    if (
        entity.get("entity_type") in {"seller", "hybrid"}
        and not entity.get("local_offerings")
        and not entity.get("services")
        and entity.get("stock_policy") not in {"NO_STOCK", "NO_STATIC_INVENTORY", "EVENT_ONLY"}
    ):
        return "seller/hybrid has no explicit stock, local wares or services"

    return None


def _identity_fields(entity: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "entity_id",
        "name",
        "entity_type",
        "district",
        "map_no",
        "book_page",
        "parent_entity_id",
        "provenance",
        "source_ref",
        "commercial_mode",
        "access_model",
    )
    return {key: copy.deepcopy(entity[key]) for key in keys if entity.get(key) is not None}


def realize_seller(engine: WorldStockEngine, entity: dict[str, Any]) -> dict[str, Any]:
    stocking = entity["stocking"]
    shop_id = stable_shop_id(entity["entity_id"])
    context = engine.make_context(
        stocking["archetype_id"],
        stocking["seed"],
        shop_id=shop_id,
        overrides=stocking.get("overrides", {}),
    )
    bundle = engine.generate(context)

    # Attach canonical identity to the realized shop context without altering the source fixture.
    bundle["shop"].update(
        {
            "id": shop_id,
            "name": entity["name"],
            "source_entity_id": entity["entity_id"],
            "parent_entity_id": entity.get("parent_entity_id"),
            "district": entity.get("district"),
            "map_no": entity.get("map_no"),
            "book_page": entity.get("book_page"),
            "provenance": entity.get("provenance"),
            "source_ref": entity.get("source_ref"),
        }
    )

    return {
        **_identity_fields(entity),
        "shop_id": shop_id,
        "archetype_id": stocking["archetype_id"],
        "seed": stocking["seed"],
        "fixture_id": entity["_fixture_id"],
        "fixture_path": entity["_fixture_path"],
        "recovered_fixture": bool(entity["_recovered_fixture"]),
        "assortment": bundle["assortment"],
        "stock": bundle["stock"],
        "state": bundle["state"],
        "history": bundle["history"],
        "shop": bundle["shop"],
    }


def build_city_stock(engine: WorldStockEngine | None = None) -> dict[str, Any]:
    engine = engine or WorldStockEngine()
    entities, metadata = _reviewed_entities()

    sellers: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    local_wares_entities = 0
    service_entities = 0
    event_market_entities = 0
    distribution_entities = 0

    for entity in entities:
        if entity.get("local_offerings"):
            local_wares_entities += 1
        if entity.get("services"):
            service_entities += 1
        if entity.get("entity_type") == "event_market":
            event_market_entities += 1
        if entity.get("entity_type") == "channel" or entity.get("distribution"):
            distribution_entities += 1

        if entity.get("stocking"):
            sellers.append(realize_seller(engine, entity))
            continue

        reason = _candidate_reason(entity)
        if reason:
            unresolved.append(
                {
                    **_identity_fields(entity),
                    "fixture_path": entity["_fixture_path"],
                    "recovered_fixture": bool(entity["_recovered_fixture"]),
                    "reason": reason,
                }
            )

    sellers.sort(key=lambda row: row["entity_id"])
    unresolved.sort(key=lambda row: row["entity_id"])

    return {
        "format_version": "0.1.0",
        "world_id": WORLD_ID,
        "stock_cycle": 0,
        "stock_day": 0,
        "stock_date": None,
        "policy": {
            "shop_generation": False,
            "realization_rule": (
                "Only source-reviewed canonical entities with explicit stocking blocks are "
                "realized as catalogue-stock sellers."
            ),
            "local_wares_rule": (
                "Source-defined local wares remain local offerings and are not replaced by "
                "unrelated catalogue items."
            ),
        },
        "coverage": {
            **metadata,
            "catalogue_stock_sellers": len(sellers),
            "persistent_assortment_lines": sum(len(row["assortment"]) for row in sellers),
            "cycle_stock_rows": sum(len(row["stock"]) for row in sellers),
            "local_wares_entities": local_wares_entities,
            "service_entities": service_entities,
            "event_market_entities": event_market_entities,
            "distribution_entities": distribution_entities,
            "unresolved_catalogue_candidates": len(unresolved),
        },
        "unresolved_catalogue_candidates": unresolved,
        "sellers": sellers,
    }


def _positive_quantity(row: dict[str, Any]) -> bool:
    quantity = row.get("quantity")
    return quantity is None or int(quantity) > 0


def _availability_for_item(
    seller: dict[str, Any],
    item_id: str,
    assortment_by_item: dict[str, dict[str, Any]],
    stock_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    current = [
        row
        for row in stock_rows
        if row.get("status") in {"in_stock", "reserved"} and _positive_quantity(row)
    ]
    incoming = [row for row in stock_rows if row.get("status") == "incoming"]

    public = [row for row in current if row.get("visibility", "public") == "public"]
    ask = [row for row in current if row.get("visibility") == "ask"]
    hidden = [row for row in current if row.get("visibility") == "hidden"]

    if public:
        availability = "in_stock"
        selected = public
    elif ask:
        availability = "ask"
        selected = ask
    elif hidden:
        availability = "hidden"
        selected = hidden
    elif incoming:
        availability = "order"
        selected = incoming
    else:
        availability = "sold_out"
        selected = []

    quantities = [row.get("quantity") for row in selected]
    if not quantities:
        quantity: int | None = 0
    elif any(value is None for value in quantities):
        quantity = None
    else:
        quantity = sum(int(value) for value in quantities)

    prices = [float(row["asking_price"]) for row in selected if row.get("asking_price") is not None]
    conditions = sorted({str(row["condition"]) for row in selected if row.get("condition")})
    visibilities = sorted({str(row.get("visibility", "public")) for row in selected})
    arrival_cycles = sorted(
        {
            int(row["metadata"]["arrival_cycle"])
            for row in incoming
            if isinstance(row.get("metadata", {}).get("arrival_cycle"), int)
        }
    )

    assortment_line = assortment_by_item.get(item_id)
    stock_role = next(
        (row.get("assortment_role") for row in selected + incoming if row.get("assortment_role")),
        None,
    )
    role = assortment_line.get("role") if assortment_line else (stock_role or "special")

    return {
        "source_entity_id": seller["entity_id"],
        "shop_id": seller["shop_id"],
        "seller_name": seller["name"],
        "district": seller.get("district"),
        "map_no": seller.get("map_no"),
        "availability": availability,
        "normally_carried": assortment_line is not None,
        "assortment_role": role,
        "quantity": quantity,
        "asking_price": min(prices) if prices else None,
        "conditions": conditions,
        "visibilities": visibilities,
        "incoming_arrival_cycle": arrival_cycles[0] if arrival_cycles else None,
        "order_reason": "incoming" if availability == "order" else None,
        "estimated_delivery_cycles": None,
        "affinity_score": (
            float(assortment_line.get("affinity_score", 0))
            if assortment_line is not None
            else None
        ),
    }


def build_availability_index(
    city_stock: dict[str, Any],
    engine: WorldStockEngine | None = None,
) -> dict[str, Any]:
    engine = engine or WorldStockEngine()
    item_sellers: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for seller in city_stock["sellers"]:
        assortment_by_item = {row["item_id"]: row for row in seller["assortment"]}
        stock_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in seller["stock"]:
            stock_by_item[row["item_id"]].append(row)

        # Assortment ensures sold-out lines remain searchable. Current specials add themselves.
        item_ids = set(assortment_by_item) | set(stock_by_item)
        for item_id in sorted(item_ids):
            item_sellers[item_id].append(
                _availability_for_item(
                    seller,
                    item_id,
                    assortment_by_item,
                    stock_by_item.get(item_id, []),
                )
            )

    # Add sourceable, non-assortment items as ORDER rather than bloating shelves.
    # A seller must clear the engine's regular-stock affinity threshold as well as all
    # department/channel/source hard constraints. Existing assortment/current rows win.
    regular_threshold = float(engine.model["role_selection"]["regular"]["minimum_score"])
    represented_pairs = {
        (item_id, row["source_entity_id"])
        for item_id, rows in item_sellers.items()
        for row in rows
    }
    for item in engine.items:
        item_id = item["id"]
        profile = engine.commercial_by_id[item_id]
        supply = profile.get("supply_profile", "regular")
        delay = engine.lifecycle["delivery_delay_by_supply"].get(supply)
        for seller in city_stock["sellers"]:
            pair = (item_id, seller["entity_id"])
            if pair in represented_pairs:
                continue
            if not engine.eligible(item_id, seller["shop"], special=False):
                continue
            scored = engine.score(item_id, seller["shop"])
            score = float(scored["score"])
            if score < regular_threshold:
                continue
            item_sellers[item_id].append(
                {
                    "source_entity_id": seller["entity_id"],
                    "shop_id": seller["shop_id"],
                    "seller_name": seller["name"],
                    "district": seller.get("district"),
                    "map_no": seller.get("map_no"),
                    "availability": "order",
                    "normally_carried": False,
                    "assortment_role": None,
                    "quantity": 0,
                    "asking_price": None,
                    "conditions": [],
                    "visibilities": ["public"],
                    "incoming_arrival_cycle": None,
                    "order_reason": "sourceable",
                    "estimated_delivery_cycles": list(delay) if delay is not None else None,
                    "affinity_score": score,
                }
            )
            represented_pairs.add(pair)

    availability_priority = {
        "in_stock": 0,
        "ask": 1,
        "order": 2,
        "sold_out": 3,
        "hidden": 4,
    }
    items: list[dict[str, Any]] = []
    for item_id in sorted(item_sellers):
        sellers = sorted(
            item_sellers[item_id],
            key=lambda row: (
                availability_priority[row["availability"]],
                0 if row.get("order_reason") == "incoming" else 1,
                -float(row.get("affinity_score") or 0),
                row["district"] or "",
                row["seller_name"],
                row["source_entity_id"],
            ),
        )
        counts = defaultdict(int)
        for row in sellers:
            counts[row["availability"]] += 1
        items.append(
            {
                "item_id": item_id,
                "item_name": engine.items_by_id[item_id]["name"],
                "seller_count": len(sellers),
                "availability_counts": dict(sorted(counts.items())),
                "sellers": sellers,
            }
        )

    return {
        "format_version": "0.1.0",
        "world_id": city_stock["world_id"],
        "stock_cycle": city_stock["stock_cycle"],
        "stock_day": city_stock.get("stock_day", city_stock["stock_cycle"]),
        "stock_date": city_stock.get("stock_date"),
        "status_vocabulary": ["in_stock", "ask", "order", "sold_out", "hidden"],
        "visibility_note": (
            "hidden rows are retained for internal state but should not be exposed in ordinary "
            "player-facing search results."
        ),
        "order_note": (
            "ORDER can mean an actual incoming/backordered line (order_reason=incoming) or a "
            "non-assortment item an existing canonical seller can plausibly source at or above "
            "the regular-stock affinity threshold (order_reason=sourceable)."
        ),
        "indexed_item_count": len(items),
        "indexed_seller_count": len(city_stock["sellers"]),
        "items": items,
    }


def build_catalogue_coverage(
    city_stock: dict[str, Any],
    index: dict[str, Any],
    engine: WorldStockEngine | None = None,
) -> dict[str, Any]:
    """Explain which catalogue items the existing canonical seller network can support."""
    engine = engine or WorldStockEngine()
    sellers = city_stock["sellers"]
    persistent_item_ids = {
        line["item_id"]
        for seller in sellers
        for line in seller["assortment"]
    }
    current_special_item_ids = {
        stock_row["item_id"]
        for seller in sellers
        for stock_row in seller["stock"]
        if stock_row.get("assortment_role") == "special"
        and stock_row.get("status") in {"in_stock", "reserved"}
        and _positive_quantity(stock_row)
    }

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    department_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    commodity_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    regular_threshold = float(engine.model["role_selection"]["regular"]["minimum_score"])

    for item in sorted(engine.items, key=lambda row: row["id"]):
        item_id = item["id"]
        profile = engine.commercial_by_id[item_id]
        normal_scored = [
            (seller["entity_id"], float(engine.score(item_id, seller["shop"])["score"]))
            for seller in sellers
            if engine.eligible(item_id, seller["shop"], special=False)
        ]
        normal_scored.sort(key=lambda row: (-row[1], row[0]))
        normal_sellers = [entity_id for entity_id, _score in normal_scored]
        orderable_scored = [
            (entity_id, score)
            for entity_id, score in normal_scored
            if score >= regular_threshold
        ]
        special_sellers = normal_sellers or [
            seller["entity_id"]
            for seller in sellers
            if engine.eligible(item_id, seller["shop"], special=True)
        ]

        if item_id in persistent_item_ids:
            status = "persistent_assortment"
        elif item_id in current_special_item_ids:
            status = "current_special"
        elif orderable_scored:
            status = "orderable_unassorted"
        elif normal_sellers:
            status = "weakly_eligible_unassorted"
        elif special_sellers:
            status = "special_only_eligible"
        else:
            status = "no_eligible_canonical_seller"

        counts[status] += 1
        department = str(profile.get("department") or "unclassified")
        commodity = str(profile.get("commodity_kind") or "unclassified")
        department_counts[department][status] += 1
        commodity_counts[commodity][status] += 1
        rows.append(
            {
                "item_id": item_id,
                "item_name": item["name"],
                "department": department,
                "product_identity": profile.get("product_identity"),
                "commodity_kind": profile.get("commodity_kind"),
                "supply_profile": profile.get("supply_profile"),
                "market_channels": list(profile.get("market_channels", [])),
                "coverage_status": status,
                "normal_eligible_seller_count": len(normal_sellers),
                "normal_eligible_seller_ids": normal_sellers,
                "best_normal_affinity_score": normal_scored[0][1] if normal_scored else None,
                "orderable_threshold": regular_threshold,
                "orderable_seller_count": len(orderable_scored),
                "orderable_sellers": [
                    {"source_entity_id": entity_id, "affinity_score": score}
                    for entity_id, score in orderable_scored
                ],
                "special_eligible_seller_count": len(special_sellers),
                "special_eligible_seller_ids": special_sellers,
            }
        )

    return {
        "format_version": "0.1.0",
        "world_id": city_stock["world_id"],
        "stock_cycle": city_stock["stock_cycle"],
        "policy": {
            "seller_generation": False,
            "meaning": (
                "Coverage is measured only against source-reviewed canonical sellers with "
                "explicit stocking profiles. A gap is not permission to generate a shop."
            ),
        },
        "summary": {
            "catalogue_items_total": len(rows),
            **dict(sorted(counts.items())),
        },
        "by_department": {
            department: dict(sorted(values.items()))
            for department, values in sorted(department_counts.items())
        },
        "by_commodity_kind": {
            commodity: dict(sorted(values.items()))
            for commodity, values in sorted(commodity_counts.items())
        },
        "items": rows,
    }


def summary_lines(city_stock: dict[str, Any], index: dict[str, Any], coverage_report: dict[str, Any]) -> list[str]:
    coverage = city_stock["coverage"]
    lines = [
        (
            f"Night City 2045 city stock: sellers={coverage['catalogue_stock_sellers']}, "
            f"assortment_lines={coverage['persistent_assortment_lines']}, "
            f"cycle_stock_rows={coverage['cycle_stock_rows']}, "
            f"indexed_items={index['indexed_item_count']}"
        ),
        (
            f"Source world: entities={coverage['source_reviewed_entities']}, "
            f"local_wares={coverage['local_wares_entities']}, "
            f"services={coverage['service_entities']}, "
            f"event_markets={coverage['event_market_entities']}, "
            f"distribution={coverage['distribution_entities']}"
        ),
        f"Unresolved catalogue candidates: {coverage['unresolved_catalogue_candidates']}",
        (
            "Catalogue coverage: "
            + ", ".join(
                f"{key}={value}"
                for key, value in coverage_report["summary"].items()
                if key != "catalogue_items_total"
            )
        ),
        (
            "No eligible seller by department: "
            + ", ".join(
                f"{department}={values.get('no_eligible_canonical_seller', 0)}"
                for department, values in coverage_report["by_department"].items()
                if values.get("no_eligible_canonical_seller", 0)
            )
        ),
        (
            "Orderable but unassorted by department: "
            + ", ".join(
                f"{department}={values.get('orderable_unassorted', 0)}"
                for department, values in coverage_report["by_department"].items()
                if values.get("orderable_unassorted", 0)
            )
        ),
        (
            "No eligible seller by commodity kind: "
            + ", ".join(
                f"{commodity}={values.get('no_eligible_canonical_seller', 0)}"
                for commodity, values in coverage_report["by_commodity_kind"].items()
                if values.get("no_eligible_canonical_seller", 0)
            )
        ),
    ]
    for row in city_stock["unresolved_catalogue_candidates"]:
        lines.append(
            f"- {row['name']} [{row.get('district') or 'unknown district'}] — {row['reason']}"
        )
    return lines


def write_outputs(
    city_stock: dict[str, Any],
    index: dict[str, Any],
    coverage_report: dict[str, Any],
    city_output: Path,
    index_output: Path,
    coverage_output: Path,
) -> None:
    city_output.parent.mkdir(parents=True, exist_ok=True)
    index_output.parent.mkdir(parents=True, exist_ok=True)
    coverage_output.parent.mkdir(parents=True, exist_ok=True)
    city_output.write_text(
        json.dumps(city_stock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    index_output.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    coverage_output.write_text(
        json.dumps(coverage_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Realize canonical Night City 2045 stock")
    parser.add_argument("--city-output", default=str(DEFAULT_CITY_OUTPUT))
    parser.add_argument("--index-output", default=str(DEFAULT_INDEX_OUTPUT))
    parser.add_argument("--coverage-output", default=str(DEFAULT_COVERAGE_OUTPUT))
    args = parser.parse_args()

    engine = WorldStockEngine()
    city_stock = build_city_stock(engine)
    index = build_availability_index(city_stock, engine)
    coverage_report = build_catalogue_coverage(city_stock, index, engine)
    write_outputs(
        city_stock,
        index,
        coverage_report,
        Path(args.city_output),
        Path(args.index_output),
        Path(args.coverage_output),
    )

    print("\n".join(summary_lines(city_stock, index, coverage_report)))
    print(f"Wrote {Path(args.city_output)}")
    print(f"Wrote {Path(args.index_output)}")
    print(f"Wrote {Path(args.coverage_output)}")


if __name__ == "__main__":
    main()
