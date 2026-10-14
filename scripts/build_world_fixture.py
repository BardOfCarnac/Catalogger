#!/usr/bin/env python3
"""Build a source-reviewed Vend-R world fixture into persistent cycle-0 state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from world_fixture import load_json, realize_document, summary_lines
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize a source-reviewed world fixture")
    parser.add_argument("--input", required=True, help="Source fixture JSON")
    parser.add_argument("--output", required=True, help="Realized fixture JSON")
    args = parser.parse_args()

    source_path = Path(args.input)
    if not source_path.is_absolute():
        source_path = ROOT / source_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    engine = WorldStockEngine()
    fixture = realize_document(load_json(source_path), engine)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n".join(summary_lines(engine, fixture)))
    print(f"Wrote {output_path.relative_to(ROOT) if output_path.is_relative_to(ROOT) else output_path}")


if __name__ == "__main__":
    main()
