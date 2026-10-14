#!/usr/bin/env python3
"""Build a source-reviewed Vend-R fixture into a v0.3 runtime graph."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from world_runtime import realize_runtime_document
from world_stock_engine import WorldStockEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    runtime = realize_runtime_document(source, WorldStockEngine())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stock_bearing = sum(bool(row.get("assortment")) for row in runtime["entities"])
    explicit = sum(not row.get("inferred_from") for row in runtime["relationships"])
    print(
        f"{runtime['fixture_id']}: entities={len(runtime['entities'])}, "
        f"relationships={len(runtime['relationships'])}, explicit_relationships={explicit}, "
        f"stock-bearing={stock_bearing}"
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
