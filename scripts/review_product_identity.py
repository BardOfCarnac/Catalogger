#!/usr/bin/env python3
"""Review product_identity across the whole catalogue.

This is an editorial helper, not a source-of-truth mutator. It loads the same
catalogue/default/override layers as the commercial-profile builder and prints
high-confidence naming signals plus unresolved items grouped by source bucket.
"""
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = json.loads((DATA / "catalog/manifest.json").read_text(encoding="utf-8"))


def load_table(name):
    rows = []
    for part in MANIFEST["tables"][name]["parts"]:
        with gzip.open(ROOT / part["path"], "rt", encoding="utf-8") as f:
            rows.extend(json.load(f))
    return rows


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


items = load_table("items")
classes = load_table("item-classifications")
item_mfrs = load_table("item-manufacturers")

classes_by_item = defaultdict(list)
for row in classes:
    classes_by_item[row["item_id"]].append(row)
mfr_items = {row["item_id"] for row in item_mfrs}

# Read all curated overrides because some already set product_identity.
override_rows = load_json(DATA / "curation/item-overrides.json")
for path in sorted((DATA / "curation/overrides").glob("*.json")):
    override_rows.extend(load_json(path))
override_identity = {
    row["item_id"]: row.get("set", {}).get("product_identity")
    for row in override_rows
    if row.get("set", {}).get("product_identity") is not None
}

GENERIC_NAMES = {
    "Medium Pistol", "Heavy Pistol", "Very Heavy Pistol", "SMG", "Heavy SMG", "Shotgun",
    "Assault Rifle", "Sniper Rifle", "Bow", "Crossbow", "Grenade Launcher", "Rocket Launcher",
    "Light Melee Weapon", "Medium Melee Weapon", "Heavy Melee Weapon", "Very Heavy Melee Weapon",
    "Cyberdeck (Poor Quality)", "Cyberdeck (Standard Quality)", "Cyberdeck (Excellent Quality)",
    "Agent (Standard)", "Compact Groundcar", "High Performance Groundcar", "Roadbike",
    "Super Groundcar", "Superbike", "Aerozep", "AV-4 Multipurpose Aerodyne", "AV-9 Super Aerodyne",
    "Gyrocopter", "Helicopter", "Cabin Cruiser", "Jetski", "Speedboat", "Yacht"
}

# Naming signals that are strong enough to be worth a targeted editorial pass.
TRADEMARK_RE = re.compile(r"[®™]")
MODEL_TOKEN_RE = re.compile(r"(?:^|[\s-])(?:Mk\.?\s*\d+|M\d+[A-Z]?|[A-Z]{2,}\d+[A-Z0-9-]*|\d{2,}[A-Z]+)(?:$|[\s-])", re.I)
STYLISED_RE = re.compile(r"(?:[a-z][A-Z]|[A-Z][a-z]+[A-Z][A-Za-z]*|[A-Z]{2,}[a-z]+)")
POSSESSIVE_RE = re.compile(r"(?:'s|’s)\b", re.I)
QUOTED_RE = re.compile(r"[“\"]([^”\"]+)[”\"]")


def primary_bucket(item_id):
    rows = classes_by_item[item_id]
    row = next((r for r in rows if r.get("is_primary")), rows[0])
    return f"{row['source_category']} / {row['source_subcategory']}"


def current_identity(item):
    iid = item["id"]
    if iid in override_identity:
        return override_identity[iid], "override"
    if iid in mfr_items:
        return "branded", "manufacturer"
    if item["name"] in GENERIC_NAMES:
        return "generic", "explicit-generic"
    return None, None


def naming_signal(name):
    if TRADEMARK_RE.search(name):
        return "branded", "trademark-symbol"
    if MODEL_TOKEN_RE.search(name):
        return "branded", "model-token"
    if STYLISED_RE.search(name):
        return "branded", "stylised-product-name"
    if POSSESSIVE_RE.search(name):
        return "unique?", "possessive-name"
    if QUOTED_RE.search(name):
        return "branded?", "quoted-model-name"
    return None, None


counts = Counter()
signal_rows = []
unresolved = defaultdict(list)
known_editorial = []
for item in items:
    ident, origin = current_identity(item)
    if ident:
        counts[(ident, origin)] += 1
        if origin != "manufacturer":
            known_editorial.append((ident, origin, item["id"], item["name"], primary_bucket(item["id"])))
        continue
    suggestion, reason = naming_signal(item["name"])
    if suggestion:
        signal_rows.append((suggestion, reason, item["id"], item["name"], primary_bucket(item["id"])))
    unresolved[primary_bucket(item["id"])].append((item["id"], item["name"]))

print("CURRENT PRODUCT IDENTITY")
for (ident, origin), count in sorted(counts.items()):
    print(f"  {ident:9} {origin:18} {count:4}")
print(f"  {'unknown':9} {'':18} {sum(len(v) for v in unresolved.values()):4}")

print("\nKNOWN NON-MANUFACTURER IDENTITIES (REVIEW THESE TOO)")
for ident, origin, iid, name, bucket in known_editorial:
    print(f"{ident:9} | {origin:16} | {iid} | {name} | {bucket}")

print("\nHIGH-CONFIDENCE / REVIEW-WORTHY NAMING SIGNALS")
for suggestion, reason, iid, name, bucket in signal_rows:
    print(f"{suggestion:9} | {reason:22} | {iid} | {name} | {bucket}")

print("\nUNRESOLVED BY SOURCE BUCKET")
for bucket in sorted(unresolved):
    rows = unresolved[bucket]
    print(f"\n## {bucket} ({len(rows)})")
    for iid, name in rows:
        print(f"{iid}\t{name}")
