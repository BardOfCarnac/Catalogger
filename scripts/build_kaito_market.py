#!/usr/bin/env python3
"""Materialize the first source-defined Night City 2045 Vend-R market state.

Kaito Market is deliberately mixed: some vendors draw persistent assortment from the
canonical catalogue, while food/service vendors retain source-defined local offerings instead
of being forced into inappropriate Night Market Index products.
"""
from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/worlds/night-city-2045/kaito-market.v1.json"
DEFAULT_OUTPUT = ROOT / "build/data/worlds/night-city-2045/kaito-market-pilot.json"
WORLD_NAMESPACE = uuid.UUID("b4e83129-88f1-5c25-8f52-807b93e5bd57")


def load_source() -> dict[str, Any]:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def stable_shop_id(entity_id: str) -> str:
    return str(uuid.uuid5(WORLD_NAMESPACE, entity_id))


def realize_market(engine: WorldStockEngine | None = None) -> dict[str, Any]:
    engine = engine or WorldStockEngine()
    source = load_source()
    result = {
        "format_version": "0.1.0",
        "world_id": source["world_id"],
        "provenance": source["provenance"],
        "source": copy.deepcopy(source["source"]),
        "location": copy.deepcopy(source["location"]),
        "vendors": [],
    }

    for vendor in source["vendors"]:
        realized = copy.deepcopy(vendor)
        stocking = realized.pop("stocking", None)
        if stocking:
            shop_id = stable_shop_id(vendor["entity_id"])
            context = engine.make_context(
                stocking["archetype_id"],
                stocking["seed"],
                shop_id=shop_id,
                overrides=stocking.get("overrides", {}),
            )
            bundle = engine.generate(context)
            realized["shop"] = {
                "id": shop_id,
                "name": vendor["name"],
                "source_entity_id": vendor["entity_id"],
                "parent_entity_id": source["location"]["entity_id"],
                "district": source["location"]["district"],
                "provenance": source["provenance"],
                "source_ref": source["source"]["ref"],
                "archetype_id": stocking["archetype_id"],
                "seed": stocking["seed"],
                "stocking_profile": copy.deepcopy(context),
            }
            realized["assortment"] = bundle["assortment"]
            realized["stock"] = bundle["stock"]
            realized["state"] = bundle["state"]
        result["vendors"].append(realized)

    return result


def summary_lines(engine: WorldStockEngine, market: dict[str, Any]) -> list[str]:
    lines = [
        f"{market['location']['name']}: {len(market['vendors'])} named vendors; parent stock policy={market['location']['stock_policy']}"
    ]
    for vendor in market["vendors"]:
        assortment = vendor.get("assortment", [])
        stock = vendor.get("stock", [])
        if assortment:
            names = [engine.items_by_id[row["item_id"]]["name"] for row in stock[:8]]
            preview = ", ".join(names) if names else "temporarily no cycle-0 stock"
            lines.append(
                f"- {vendor['name']}: {len(assortment)} persistent lines / {len(stock)} cycle-0 stock; {preview}"
            )
        else:
            local_count = len(vendor.get("local_offerings", []))
            service_count = len(vendor.get("services", []))
            lines.append(
                f"- {vendor['name']}: source-defined local offerings={local_count}, services={service_count}"
            )
    return lines


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build the Kaito Market Vend-R pilot state")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    engine = WorldStockEngine()
    market = realize_market(engine)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(market, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n".join(summary_lines(engine, market)))
    print(f"Wrote {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}")


if __name__ == "__main__":
    main()
