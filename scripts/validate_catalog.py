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
brand_doc = load("catalog/brands.json")
brands = brand_doc["brands"]
brand_products_doc = load("catalog/brand-products.json")
brand_products = brand_products_doc["products"]
brand_variants = brand_products_doc["variants"]
stock_variant_policies = brand_products_doc["stock_variant_policies"]
taxonomy = load("catalog/taxonomy.json")
identity_rules = load("curation/product-identity.json")
default_docs = [
    json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((DATA / "curation/defaults").glob("*.json"))
]
assert default_docs, "no commercial default files found"
item_tags = load("curation/item-tags.json")
item_overrides = load("curation/item-overrides.json")
for path in sorted((DATA / "curation/overrides").glob("*.json")):
    item_overrides.extend(json.loads(path.read_text(encoding="utf-8")))
redirects = load("audit/id-redirects.json")

def unique(rows, key, label):
    vals = [r[key] for r in rows]
    assert len(vals) == len(set(vals)), f"duplicate {label}"

unique(items, "id", "item IDs")
unique(manufacturers, "id", "manufacturer IDs")
unique(sources, "code", "source codes")
unique(brands, "id", "brand IDs")
unique(brand_products, "id", "brand product IDs")
unique(brand_variants, "id", "brand variant IDs")

item_ids = {r["id"] for r in items}
mfr_ids = {r["id"] for r in manufacturers}
source_codes = {r["code"] for r in sources}
brand_ids = {r["id"] for r in brands}
brand_product_ids = {r["id"] for r in brand_products}
item_names = {}
for r in items:
    item_names.setdefault(r["name"], []).append(r["id"])
brand_kinds = {
    "corporation", "product_line", "retail_chain", "restaurant_chain",
    "importer_distributor", "producer_brand", "food_vendor_brand"
}

for r in brands:
    assert r["name"] and r["kind"] in brand_kinds, r
    assert r["status_2045"] in {"active", "inactive", "uncertain"}, r
    if r.get("parent_brand_id") is not None:
        assert r["parent_brand_id"] in brand_ids and r["parent_brand_id"] != r["id"], r
    if r.get("manufacturer_id") is not None:
        assert r["manufacturer_id"] in mfr_ids, r
    if r.get("owner_manufacturer_id") is not None:
        assert r["owner_manufacturer_id"] in mfr_ids, r
    assert len(r.get("aliases", [])) == len(set(r.get("aliases", []))), r
    seen_brand_sources = set()
    for ref in r.get("source_refs", []):
        assert ref["source_code"] in source_codes, r
        assert ref["source_code"] not in seen_brand_sources, r
        seen_brand_sources.add(ref["source_code"])


allowed_product_kinds = {"base_product", "named_product"}
allowed_variant_kinds = {"flavor", "formula", "format", "sensory_effect"}
for r in brand_products:
    assert r["brand_id"] in brand_ids, r
    assert r["product_kind"] in allowed_product_kinds, r
    catalog_name = r.get("catalog_item_name")
    if catalog_name is not None:
        assert len(item_names.get(catalog_name, [])) == 1, (
            f"brand product catalog binding must resolve exactly once: {catalog_name!r}"
        )
    price_basis = r.get("mechanical_price_basis")
    if price_basis is not None:
        assert price_basis.get("type") == "catalog_item", r
        basis_name = price_basis.get("catalog_item_name")
        assert len(item_names.get(basis_name, [])) == 1, (
            f"mechanical price basis must resolve exactly once: {basis_name!r}"
        )
        assert price_basis.get("relationship") == "same_price", r
    assert r.get("source_refs"), r
    for ref in r["source_refs"]:
        assert ref["source_code"] in source_codes, r

seen_variant_names = set()
for r in brand_variants:
    assert r["product_id"] in brand_product_ids, r
    assert r["vendr_variant_kind"] in allowed_variant_kinds, r
    key = (r["product_id"], r["name"])
    assert key not in seen_variant_names, f"duplicate product variant name: {key}"
    seen_variant_names.add(key)
    assert r.get("source_refs"), r
    for ref in r["source_refs"]:
        assert ref["source_code"] in source_codes, r

seen_variant_policies = set()
for r in stock_variant_policies:
    assert r["product_id"] in brand_product_ids, r
    assert r["product_id"] not in seen_variant_policies, f"duplicate variant policy: {r['product_id']}"
    seen_variant_policies.add(r["product_id"])
    assert len(item_names.get(r["catalog_item_name"], [])) == 1, r
    product = next(p for p in brand_products if p["id"] == r["product_id"])
    assert product.get("catalog_item_name") == r["catalog_item_name"], r
    ranges = r["display_range_by_depth"]
    assert set(ranges) == {"shallow", "normal", "deep", "warehouse"}, r
    for bounds in ranges.values():
        assert (
            isinstance(bounds, list) and len(bounds) == 2
            and all(isinstance(v, int) and v >= 0 for v in bounds)
            and bounds[0] <= bounds[1]
        ), r
    assert any(v["product_id"] == r["product_id"] for v in brand_variants), r

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
for r in brands:
    assert r.get("departments"), r
    assert all(v in dept_ids for v in r["departments"]), r

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

# Second-pass product identity rules.
assert identity_rules["default_identity"] in identity_ids, identity_rules
assert isinstance(identity_rules.get("version"), str) and identity_rules["version"], identity_rules
seen_exact = set()
for r in identity_rules["exact"]:
    assert r["item_id"] in item_ids, r
    assert r["item_id"] not in seen_exact, f"duplicate exact product identity: {r['item_id']}"
    assert r["identity"] in identity_ids, r
    seen_exact.add(r["item_id"])
seen_buckets = set()
for r in identity_rules["branded_source_buckets"]:
    key = (r["source_category"], r["source_subcategory"])
    assert key in source_keys, f"unknown branded source bucket: {key}"
    assert key not in seen_buckets, f"duplicate branded source bucket: {key}"
    seen_buckets.add(key)

assert len(items) == 1275
mixed = sum(1 for r in default_rows if r["requires_item_curation"])
print(
    f"OK: {len(items)} items, {len(manufacturers)} manufacturers, {len(brands)} brands, "
    f"{len(brand_products)} brand products, {len(brand_variants)} brand variants, "
    f"{len(item_sources)} item-source links, {len(default_rows)} commercial defaults, "
    f"{len(identity_rules['exact'])} exact identity decisions, {len(seen_buckets)} branded identity buckets "
    f"({mixed} mixed source buckets flagged for item review)"
)
