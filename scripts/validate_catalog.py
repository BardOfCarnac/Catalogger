#!/usr/bin/env python3
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = json.loads((DATA / "catalog/manifest.json").read_text(encoding="utf-8"))

def load_table(name):
    meta = MANIFEST["tables"][name]
    rows = []
    for part in meta["parts"]:
        path = ROOT / part["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == part["sha256"], f"checksum mismatch: {part['path']}"
        with gzip.open(path, "rt", encoding="utf-8") as f:
            chunk = json.load(f)
        assert len(chunk) == part["rows"], f"row count mismatch: {part['path']}"
        rows.extend(chunk)
    assert len(rows) == meta["rows"], f"table row count mismatch: {name}"
    return rows

def load(rel):
    with open(DATA / rel, encoding="utf-8") as f:
        return json.load(f)

items = load_table("items")
classes = load_table("item-classifications")
item_sources = load_table("item-sources")
item_mfrs = load_table("item-manufacturers")
manufacturers = load("catalog/manufacturers.json")
sources = load("catalog/sources.json")
taxonomy = load("catalog/taxonomy.json")
default_docs = [
    json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((DATA / "curation/defaults").glob("*.json"))
]
assert default_docs, "no commercial default files found"
item_tags = load("curation/item-tags.json")
item_overrides = load("curation/item-overrides.json")
redirects = load("audit/id-redirects.json")

def unique(rows, key, label):
    vals = [r[key] for r in rows]
    assert len(vals) == len(set(vals)), f"duplicate {label}"

unique(items, "id", "item IDs")
unique(manufacturers, "id", "manufacturer IDs")
unique(sources, "code", "source codes")

item_ids = {r["id"] for r in items}
mfr_ids = {r["id"] for r in manufacturers}
source_codes = {r["code"] for r in sources}

for r in item_mfrs:
    assert r["item_id"] in item_ids and r["manufacturer_id"] in mfr_ids, r
for r in classes:
    assert r["item_id"] in item_ids and r["source_category"] and r.get("source_subcategory"), r
for r in item_sources:
    assert r["item_id"] in item_ids and r["source_code"] in source_codes, r
for r in redirects:
    assert r["canonical_vendr_id"] in item_ids and r["retired_vendr_id"] not in item_ids, r

# Controlled commercial vocabulary.
dept_ids = {r["id"] for r in taxonomy["departments"]}
identity_ids = {r["id"] for r in taxonomy["product_identity"]}
commodity_ids = {r["id"] for r in taxonomy["commodity_kinds"]}
quantity_ids = {r["id"] for r in taxonomy["quantity_profiles"]}
condition_ids = {r["id"] for r in taxonomy["conditions"]}
supply_ids = {r["id"] for r in taxonomy["supply_profiles"]}
channel_ids = {r["id"] for r in taxonomy["market_channels"]}
affinity_ids = {
    group: {r["id"] for r in rows}
    for group, rows in taxonomy["affinity_tags"].items()
}
assert set(affinity_ids) == {"audience", "use", "character"}

# Every source category/subcategory pair in the catalogue gets exactly one default.
default_versions = {doc["version"] for doc in default_docs}
default_tax_versions = {doc["taxonomy_version"] for doc in default_docs}
assert len(default_versions) == 1, f"default version mismatch: {default_versions}"
assert default_tax_versions == {taxonomy["version"]}, "defaults/taxonomy version mismatch"
default_rows = [row for doc in default_docs for row in doc["defaults"]]
default_keys = [(r["source_category"], r["source_subcategory"]) for r in default_rows]
assert len(default_keys) == len(set(default_keys)), "duplicate subcategory default"
source_keys = {(r["source_category"], r["source_subcategory"]) for r in classes}
assert set(default_keys) == source_keys, (
    f"subcategory default coverage mismatch; missing={sorted(source_keys-set(default_keys))}, "
    f"extra={sorted(set(default_keys)-source_keys)}"
)

for r in default_rows:
    assert r["department"] in dept_ids, r
    assert isinstance(r["classification_path"], list) and r["classification_path"], r
    assert r["commodity_kind"] in commodity_ids, r
    assert r["quantity_profile"] in quantity_ids, r
    assert r["default_condition"] in condition_ids, r
    assert r["allowed_conditions"] and all(v in condition_ids for v in r["allowed_conditions"]), r
    assert r["default_condition"] in r["allowed_conditions"], r
    assert r["supply_profile"] in supply_ids, r
    assert all(v in channel_ids for v in r["market_channels"]), r
    assert all(v in affinity_ids["audience"] for v in r["audience_tags"]), r
    assert all(v in affinity_ids["use"] for v in r["use_tags"]), r
    assert all(v in affinity_ids["character"] for v in r["character_tags"]), r
    assert isinstance(r["requires_item_curation"], bool), r

# Item-level semantic tags are intentionally sparse and curated.
seen_item_tags = set()
for r in item_tags:
    assert r["item_id"] in item_ids, r
    assert r["tag_type"] in affinity_ids, r
    assert r["tag_id"] in affinity_ids[r["tag_type"]], r
    key = (r["item_id"], r["tag_type"], r["tag_id"])
    assert key not in seen_item_tags, f"duplicate item tag: {key}"
    seen_item_tags.add(key)

# Overrides can replace scalar fields or add/remove controlled list values.
seen_overrides = set()
scalar_controls = {
    "product_identity": identity_ids,
    "department": dept_ids,
    "commodity_kind": commodity_ids,
    "quantity_profile": quantity_ids,
    "default_condition": condition_ids,
    "supply_profile": supply_ids,
}
list_controls = {
    "market_channels": channel_ids,
    "allowed_conditions": condition_ids,
    "secondary_departments": dept_ids,
}
for r in item_overrides:
    item_id = r["item_id"]
    assert item_id in item_ids, r
    assert item_id not in seen_overrides, f"duplicate override: {item_id}"
    seen_overrides.add(item_id)
    for key, value in r.get("set", {}).items():
        if key in scalar_controls and value is not None:
            assert value in scalar_controls[key], r
        if key == "classification_path":
            assert isinstance(value, list) and value, r
    for op in ("add", "remove"):
        block = r.get(op, {})
        for key, allowed in list_controls.items():
            if key in block:
                assert all(v in allowed for v in block[key]), r
        for group, values in block.get("affinity_tags", {}).items():
            assert group in affinity_ids, r
            assert all(v in affinity_ids[group] for v in values), r

assert len(items) == 1275
mixed = sum(1 for r in default_rows if r["requires_item_curation"])
print(
    f"OK: {len(items)} items, {len(manufacturers)} manufacturers, "
    f"{len(item_sources)} item-source links, {len(default_rows)} commercial defaults "
    f"({mixed} mixed source buckets flagged for item review)"
)
