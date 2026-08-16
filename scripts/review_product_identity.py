#!/usr/bin/env python3
"""Review resolved Vend-R product identities after profile generation.

This script never changes data. It reports final identity counts and surfaces
future default-generic names that look productized enough to deserve a human look.
"""
import gzip
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROFILES = ROOT / "build/data/catalog/item-commercial-profiles.json"

if not PROFILES.exists():
    raise FileNotFoundError("Run scripts/build_commercial_profiles.py first")

profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
identity_rules = json.loads((DATA / "curation/product-identity.json").read_text(encoding="utf-8"))
manifest = json.loads((DATA / "catalog/manifest.json").read_text(encoding="utf-8"))

items = []
for part in manifest["tables"]["items"]["parts"]:
    with gzip.open(ROOT / part["path"], "rt", encoding="utf-8") as f:
        items.extend(json.load(f))
name_by_id = {row["id"]: row["name"] for row in items}

# Review signals only; these never auto-promote an item.
TRADEMARK_RE = re.compile(r"[®™]")
STYLISED_RE = re.compile(r"(?:[a-z][A-Z]|[A-Z][a-z]+[A-Z][A-Za-z]*|[A-Z]{2,}[a-z]+)")
POSSESSIVE_RE = re.compile(r"(?:'s|’s)\b", re.I)

exact_by_id = {row["item_id"]: row for row in identity_rules["exact"]}
identity_counts = Counter(p["product_identity"] for p in profiles)
origin_counts = Counter(p["product_identity_origin"] for p in profiles)
assert None not in identity_counts, "unresolved product identity remains"

print("RESOLVED PRODUCT IDENTITY")
for identity in sorted(identity_counts):
    print(f"  {identity:9} {identity_counts[identity]:4}")
print("\nIDENTITY ORIGIN")
for origin in sorted(origin_counts):
    print(f"  {origin:18} {origin_counts[origin]:4}")

print("\nEXACT EDITORIAL DECISIONS")
for p in profiles:
    row = exact_by_id.get(p["item_id"])
    if row:
        print(f"{p['item_id']} | {p['product_identity']:8} | {name_by_id[p['item_id']]} | {row['reason']}")

spot_checks = []
for p in profiles:
    if p["product_identity_origin"] != "default-generic":
        continue
    name = name_by_id[p["item_id"]]
    signals = []
    if TRADEMARK_RE.search(name): signals.append("trademark")
    if STYLISED_RE.search(name): signals.append("stylised")
    if POSSESSIVE_RE.search(name): signals.append("possessive")
    if signals:
        spot_checks.append((p["item_id"], name, ",".join(signals)))

print(f"\nDEFAULT-GENERIC ITEMS: {origin_counts.get('default-generic', 0)}")
print(f"DEFAULT-GENERIC NAMING SPOT CHECKS: {len(spot_checks)}")
for iid, name, signals in spot_checks:
    print(f"{iid} | {signals:18} | {name}")
