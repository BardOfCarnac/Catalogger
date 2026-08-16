#!/usr/bin/env python3
"""Validate Vend-R stocking configuration and archetype stocking defaults."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load(path):
    return json.loads((DATA / path).read_text(encoding="utf-8"))


taxonomy = load("catalog/taxonomy.json")
model = load("stocking/model.json")
archetypes_doc = load("shops/archetypes.json")
profiles_doc = load("stocking/archetype-profiles.json")

dept_ids = {row["id"] for row in taxonomy["departments"]}
identity_ids = {row["id"] for row in taxonomy["product_identity"]}
condition_ids = {row["id"] for row in taxonomy["conditions"]}
channel_ids = {row["id"] for row in taxonomy["market_channels"]}
supply_ids = {row["id"] for row in taxonomy["supply_profiles"]}
affinity_ids = {
    group: {row["id"] for row in rows}
    for group, rows in taxonomy["affinity_tags"].items()
}

archetypes = {row["id"]: row for row in archetypes_doc["archetypes"]}
profiles = {row["archetype_id"]: row for row in profiles_doc["profiles"]}
assert len(profiles) == len(profiles_doc["profiles"]), "duplicate archetype stocking profile"
assert set(archetypes) == set(profiles), (
    f"stock profile coverage mismatch missing={sorted(set(archetypes)-set(profiles))} "
    f"extra={sorted(set(profiles)-set(archetypes))}"
)

for archetype in archetypes.values():
    for key in ("primary_departments", "secondary_departments"):
        assert all(value in dept_ids for value in archetype.get(key, [])), archetype

assert set(model["supply_scores"]) >= {
    profile["supply_capability"] for profile in profiles.values()
}, "missing supply capability matrix"
for capability, values in model["supply_scores"].items():
    assert set(values) == supply_ids, f"supply matrix incomplete: {capability}"

for name, breadth in model["breadth_profiles"].items():
    assert set(breadth) == {"core", "regular", "occasional"}, name
    assert all(isinstance(value, int) and value >= 0 for value in breadth.values()), name
for name, depth in model["depth_profiles"].items():
    assert float(depth) > 0, name

assert set(model["presence_by_role"]) == {"core", "regular", "occasional"}
assert set(model["role_selection"]) == {"core", "regular", "occasional"}
assert set(model["presence_supply_adjustment"]) == supply_ids
assert set(model["condition_price_factors"]) == condition_ids

for profile in profiles.values():
    assert profile["breadth_profile"] in model["breadth_profiles"], profile
    assert profile["depth_profile"] in model["depth_profiles"], profile
    assert profile["supply_capability"] in model["supply_scores"], profile
    assert profile["pricing_style"] in model["pricing_styles"], profile
    assert profile.get("price_tier_center") in model["price_score"]["tier_order"], profile
    assert set(profile.get("channel_weights", {})) <= channel_ids, profile
    assert set(profile.get("identity_weights", {})) <= identity_ids, profile
    assert set(profile.get("condition_weights", {})) <= condition_ids, profile
    assert len(profile.get("specials", [])) == 2, profile
    low, high = profile["specials"]
    assert isinstance(low, int) and isinstance(high, int) and 0 <= low <= high, profile
    preferences = profile.get("affinity_preferences", {})
    assert set(preferences) <= set(affinity_ids), profile
    for group, values in preferences.items():
        assert set(values) <= affinity_ids[group], profile

print(
    f"OK: stocking model {model['version']}, {len(profiles)} archetype stocking profiles, "
    f"{len(model['breadth_profiles'])} breadth profiles, {len(model['depth_profiles'])} depth profiles"
)
