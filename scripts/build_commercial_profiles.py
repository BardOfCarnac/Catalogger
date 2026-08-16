#!/usr/bin/env python3
"""Build first-pass Vend-R commercial profiles from source classifications.

The source catalogue remains immutable. Commercial profiles are derived from:
1. data/curation/defaults/*.json
2. manufacturer presence / conservative identity inference
3. data/curation/item-overrides.json
4. data/curation/item-tags.json

Generated output is written under build/data/ and is not committed.
"""
import gzip
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "build/data/catalog/item-commercial-profiles.json"

MANIFEST = json.loads((DATA / "catalog/manifest.json").read_text(encoding="utf-8"))
TAXONOMY = json.loads((DATA / "catalog/taxonomy.json").read_text(encoding="utf-8"))
DEFAULT_DOCS = [
    json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((DATA / "curation/defaults").glob("*.json"))
]
if not DEFAULT_DOCS:
    raise FileNotFoundError("No commercial default files found under data/curation/defaults/")
OVERRIDES = json.loads((DATA / "curation/item-overrides.json").read_text(encoding="utf-8"))
ITEM_TAGS = json.loads((DATA / "curation/item-tags.json").read_text(encoding="utf-8"))

def load_table(name):
    rows = []
    for part in MANIFEST["tables"][name]["parts"]:
        with gzip.open(ROOT / part["path"], "rt", encoding="utf-8") as f:
            rows.extend(json.load(f))
    return rows

items = load_table("items")
classes = load_table("item-classifications")
item_mfrs = load_table("item-manufacturers")

DEFAULTS_VERSION = DEFAULT_DOCS[0]["version"]
DEFAULTS_TAXONOMY_VERSION = DEFAULT_DOCS[0]["taxonomy_version"]
for doc in DEFAULT_DOCS:
    if doc["version"] != DEFAULTS_VERSION or doc["taxonomy_version"] != DEFAULTS_TAXONOMY_VERSION:
        raise ValueError("Commercial default files disagree on version/taxonomy version")

defaults = {}
for doc in DEFAULT_DOCS:
    for row in doc["defaults"]:
        key = (row["source_category"], row["source_subcategory"])
        if key in defaults:
            raise ValueError(f"Duplicate commercial default: {key!r}")
        defaults[key] = row

classes_by_item = defaultdict(list)
for row in classes:
    classes_by_item[row["item_id"]].append(row)

mfrs_by_item = defaultdict(list)
for row in item_mfrs:
    mfrs_by_item[row["item_id"]].append(row["manufacturer_id"])

overrides_by_item = {row["item_id"]: row for row in OVERRIDES}
extra_tags_by_item = defaultdict(list)
for row in ITEM_TAGS:
    extra_tags_by_item[row["item_id"]].append(row)

# Conservative: these are unmistakably generic catalogue objects.
GENERIC_NAMES = {
    "Medium Pistol", "Heavy Pistol", "Very Heavy Pistol", "SMG", "Heavy SMG",
    "Shotgun", "Assault Rifle", "Sniper Rifle", "Bow", "Crossbow",
    "Grenade Launcher", "Rocket Launcher", "Light Melee Weapon",
    "Medium Melee Weapon", "Heavy Melee Weapon", "Very Heavy Melee Weapon",
    "Cyberdeck (Poor Quality)", "Cyberdeck (Standard Quality)",
    "Cyberdeck (Excellent Quality)", "Agent (Standard)",
    "Compact Groundcar", "High Performance Groundcar", "Roadbike",
    "Super Groundcar", "Superbike", "Aerozep", "AV-4 Multipurpose Aerodyne",
    "AV-9 Super Aerodyne", "Gyrocopter", "Helicopter", "Cabin Cruiser",
    "Jetski", "Speedboat", "Yacht"
}

def union(values):
    out = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out

def infer_identity(item_id, name):
    if mfrs_by_item.get(item_id):
        return "branded"
    if name in GENERIC_NAMES:
        return "generic"
    return None

def apply_override(profile, override):
    if not override:
        return
    for key, value in override.get("set", {}).items():
        profile[key] = value

    additions = override.get("add", {})
    removals = override.get("remove", {})

    for key in ("market_channels", "allowed_conditions", "secondary_departments"):
        if key in additions:
            profile[key] = union(profile.get(key, []) + additions[key])
        if key in removals:
            remove = set(removals[key])
            profile[key] = [v for v in profile.get(key, []) if v not in remove]

    for group in ("audience", "use", "character"):
        add = additions.get("affinity_tags", {}).get(group, [])
        remove = set(removals.get("affinity_tags", {}).get(group, []))
        profile["affinity_tags"][group] = [
            v for v in union(profile["affinity_tags"].get(group, []) + add)
            if v not in remove
        ]

    if override.get("reason"):
        profile["curation_notes"].append(override["reason"])
    profile["requires_item_curation"] = bool(
        override.get("requires_item_curation", profile["requires_item_curation"])
    )

profiles = []
for item in items:
    item_id = item["id"]
    item_classes = classes_by_item[item_id]
    if not item_classes:
        raise ValueError(f"Item has no source classification: {item_id}")

    mapped = []
    for c in item_classes:
        key = (c["source_category"], c.get("source_subcategory"))
        if key not in defaults:
            raise ValueError(f"No subcategory default for {key!r} ({item_id})")
        mapped.append((c, defaults[key]))

    primary_candidates = [(c, d) for c, d in mapped if c.get("is_primary")]
    primary_c, primary_d = primary_candidates[0] if primary_candidates else mapped[0]

    profile = {
        "item_id": item_id,
        "product_identity": infer_identity(item_id, item["name"]),
        "department": primary_d["department"],
        "classification_path": primary_d["classification_path"],
        "secondary_departments": union(
            d["department"] for _, d in mapped if d["department"] != primary_d["department"]
        ),
        "commodity_kind": primary_d["commodity_kind"],
        "quantity_profile": primary_d["quantity_profile"],
        "allowed_conditions": list(primary_d["allowed_conditions"]),
        "default_condition": primary_d["default_condition"],
        "supply_profile": primary_d["supply_profile"],
        "market_channels": union(
            channel for _, d in mapped for channel in d["market_channels"]
        ),
        "affinity_tags": {
            "audience": union(tag for _, d in mapped for tag in d["audience_tags"]),
            "use": union(tag for _, d in mapped for tag in d["use_tags"]),
            "character": union(tag for _, d in mapped for tag in d["character_tags"]),
        },
        "inherited_from": [
            {
                "source_category": c["source_category"],
                "source_subcategory": c.get("source_subcategory"),
                "primary": bool(c.get("is_primary")),
            }
            for c, _ in mapped
        ],
        "requires_item_curation": any(d["requires_item_curation"] for _, d in mapped),
        "curation_notes": [],
        "profile_version": DEFAULTS_VERSION,
        "taxonomy_version": TAXONOMY["version"],
    }

    apply_override(profile, overrides_by_item.get(item_id))

    # item-tags.json adds semantic affinities that cannot be derived structurally.
    for row in extra_tags_by_item.get(item_id, []):
        group = row["tag_type"]
        tag_id = row["tag_id"]
        if tag_id not in profile["affinity_tags"][group]:
            profile["affinity_tags"][group].append(tag_id)

    if profile["default_condition"] not in profile["allowed_conditions"]:
        raise ValueError(f"default condition not allowed: {item_id}")

    profiles.append(profile)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

needs_curation = sum(bool(p["requires_item_curation"]) for p in profiles)
identity_known = sum(p["product_identity"] is not None for p in profiles)
print(f"Wrote {len(profiles)} commercial profiles -> {OUT.relative_to(ROOT)}")
print(f"{needs_curation} profiles inherit from mixed source buckets and need item-level review")
print(f"{identity_known} profiles have high-confidence product identity; remaining identity values stay null")
