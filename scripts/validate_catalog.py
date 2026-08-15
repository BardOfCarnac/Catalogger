#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def load(rel):
    with open(DATA / rel, encoding="utf-8") as f:
        return json.load(f)

items = load("catalog/items.json")
manufacturers = load("catalog/manufacturers.json")
item_mfrs = load("catalog/item-manufacturers.json")
classes = load("catalog/item-classifications.json")
sources = load("catalog/sources.json")
item_sources = load("catalog/item-sources.json")
redirects = load("audit/id-redirects.json")

def unique(rows, key, label):
    vals = [r[key] for r in rows]
    dup = sorted({x for x in vals if vals.count(x) > 1})
    assert not dup, f"duplicate {label}: {dup[:10]}"

unique(items, "id", "item IDs")
unique(manufacturers, "id", "manufacturer IDs")
unique(sources, "code", "source codes")

item_ids = {r["id"] for r in items}
mfr_ids = {r["id"] for r in manufacturers}
source_codes = {r["code"] for r in sources}

for row in item_mfrs:
    assert row["item_id"] in item_ids, row
    assert row["manufacturer_id"] in mfr_ids, row
for row in classes:
    assert row["item_id"] in item_ids, row
    assert row["vendr_department"], row
for row in item_sources:
    assert row["item_id"] in item_ids, row
    assert row["source_code"] in source_codes, row
for row in redirects:
    assert row["canonical_vendr_id"] in item_ids, row
    assert row["retired_vendr_id"] not in item_ids, row

assert len(items) == 1275, f"expected 1275 canonical items, got {len(items)}"
print(f"OK: {len(items)} items, {len(manufacturers)} manufacturers, {len(item_sources)} item-source links")
