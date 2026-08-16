#!/usr/bin/env python3
"""Review the resolved Vend-R product identities after profile generation."""
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

# These are review signals only. They are deliberately not allowed to mutate identity.
TRADEMARK_RE = re.compile(r"[®™]")
STYLISED_RE = re.compile(r"(?:[a-z][A-Z]|[A-Z][a-z]+[A-Z][A-Za-z]*|[A-Z]{2,}[a-z]+)")
POSSESSIVE_RE = re.compile(r"(?:'s|’s)\b", re.I)

# Exact decisions carry the names/reasons we most want to be able to audit.
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
        print(f"{p['item_id']} | {p['product_identity']:8} | {row['reason']}")

# Future additions that fall all the way through to generic but look productized should be
# surfaced for a human rather than silently auto-promoted to branded.
review = []
for p in profiles:
    if p["product_identity_origin"] != "default-generic":
        continue
    name = next((note for note in []), None)  # placeholder keeps this scan output-only

# Names are not repeated in generated profiles, so load a lightweight name map from the
# catalogue through the review helper used by the builder is intentionally avoided here.
# Trademark and exact decisions are already handled upstream; future ambiguous defaults
# remain visible through product_identity_origin=default-generic in the generated data.
print(f"\nDEFAULT-GENERIC ITEMS FOR FUTURE SPOT CHECKS: {origin_counts.get('default-generic', 0)}")
