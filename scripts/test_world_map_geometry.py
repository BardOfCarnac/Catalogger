#!/usr/bin/env python3
"""Structural and identity regression tests for Vend-R source-map geometry files."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"

fixture_paths = sorted(WORLD_DIR.glob("*.v1.json")) + sorted((WORLD_DIR / "recovered").glob("*.v1.json"))
fixture_entities: dict[str, dict] = {}
for fixture_path in fixture_paths:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    candidates = list(fixture.get("entities", []))
    legacy_location = fixture.get("location")
    if isinstance(legacy_location, dict) and legacy_location.get("entity_id"):
        candidates.append(legacy_location)
    for entity in candidates:
        entity_id = entity["entity_id"]
        assert entity_id not in fixture_entities, f"duplicate fixture entity id: {entity_id}"
        fixture_entities[entity_id] = entity

paths = sorted(WORLD_DIR.glob("map-geometry.*.v0.1.json"))
assert paths, "no source-map geometry files found"
for path in paths:
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["format_version"] == "0.1.0", path
    assert doc["world_id"] and doc["map_id"] and doc["district"], path
    assert doc["coordinate_space"] == "source_page_uv", path
    points = doc["points"]
    assert points, path
    point_ids = [row["point_id"] for row in points if row.get("point_id")]
    assert len(point_ids) == len(set(point_ids)), f"duplicate point id: {path}"
    coordinate_keys = [(row["map_no"], row.get("map_suffix"), row["x"], row["y"]) for row in points]
    assert len(coordinate_keys) == len(set(coordinate_keys)), f"duplicate source point: {path}"
    for row in points:
        assert isinstance(row["map_no"], int) and row["map_no"] > 0, (path, row)
        suffix = row.get("map_suffix")
        if suffix is not None:
            assert len(suffix) == 1 and suffix.isascii() and suffix.islower(), (path, row)
        assert row["name"] and row["entity_id"], (path, row)
        assert 0.0 <= row["x"] <= 1.0 and 0.0 <= row["y"] <= 1.0, (path, row)
        entity = fixture_entities.get(row["entity_id"])
        assert entity is not None, f"geometry points at unknown entity: {row['entity_id']}"
        assert entity.get("district") == doc["district"], (path, row, entity)
        if entity.get("map_no") is not None:
            assert entity["map_no"] == row["map_no"], f"source marker mismatch for {row['entity_id']}: fixture={entity['map_no']} geometry={row['map_no']}"

ordinary_specs = {
    "downtown": 23,
    "little-china": 15,
    "upper-marina": 40,
    "little-europe": 23,
    "charter-hill": 18,
    "kabuki": 24,
    "old-japantown": 26,
    "south-night-city": 17,
    "port-of-night-city": 15,
    "reclamation-zone": 15,
}
loaded: dict[str, dict] = {}
for slug, expected_len in ordinary_specs.items():
    doc = json.loads((WORLD_DIR / f"map-geometry.{slug}.v0.1.json").read_text(encoding="utf-8"))
    loaded[slug] = doc
    assert len(doc["points"]) == expected_len
    assert [row["map_no"] for row in doc["points"]] == list(range(1, expected_len + 1))
assert any(row["entity_id"] == "NC2045-LOC-LITTLE-EUROPE-060-KAITO-MARKET" for row in loaded["little-europe"]["points"])

university = json.loads((WORLD_DIR / "map-geometry.university-district.v0.1.json").read_text(encoding="utf-8"))
university_points = university["points"]
assert len(university_points) == 33
assert [row["map_no"] for row in university_points if row.get("map_suffix") is None] == [1,2,3,4,5,6,7,8,9,10,12,13,14,15,16,17,18,19]
assert not any(row["map_no"] == 11 and row.get("map_suffix") is None for row in university_points)
assert {row["map_suffix"] for row in university_points if row.get("map_suffix")} == set("abcdefghijklm")
assert sum(row["map_no"] == 11 and row.get("map_suffix") == "d" for row in university_points) == 3
assert len({row["point_id"] for row in university_points}) == len(university_points)

executive_zone = json.loads((WORLD_DIR / "map-geometry.executive-zone.v0.1.json").read_text(encoding="utf-8"))
executive_points = executive_zone["points"]
assert len(executive_points) == 21
assert not any(row["map_no"] == 1 and row.get("map_suffix") is None for row in executive_points)
assert {row["map_suffix"] for row in executive_points if row["map_no"] == 1} == set("abcdefghijkl")
assert [row["map_no"] for row in executive_points if row.get("map_suffix") is None] == list(range(2, 11))
assert {row["entity_id"] for row in executive_points if row["map_no"] == 1} == {"NC2045-LOC-EXECUTIVE-ZONE-234-THE-ESTATES"}

the_glen = json.loads((WORLD_DIR / "map-geometry.the-glen.v0.1.json").read_text(encoding="utf-8"))
glen_points = the_glen["points"]
assert len(glen_points) == 33
assert not any(row["map_no"] == 9 and row.get("map_suffix") is None for row in glen_points)
assert {row["map_suffix"] for row in glen_points if row["map_no"] == 9} == set("abcdef")
assert [row["map_no"] for row in glen_points if row.get("map_suffix") is None] == list(range(1, 9)) + list(range(10, 29))

old_combat = json.loads((WORLD_DIR / "map-geometry.old-combat-zone.v0.1.json").read_text(encoding="utf-8"))
old_combat_points = old_combat["points"]
assert len(old_combat_points) == 22
assert [row["map_no"] for row in old_combat_points if row.get("map_suffix") is None] == list(range(1, 17))
assert {row["map_suffix"] for row in old_combat_points if row["map_no"] == 16 and row.get("map_suffix")} == set("abcdef")
assert any(row["map_no"] == 16 and row.get("map_suffix") is None for row in old_combat_points), "source map includes the Warren parent marker as well as 16a-16f"

watson = json.loads((WORLD_DIR / "map-geometry.watson-development.v0.1.json").read_text(encoding="utf-8"))
watson_points = watson["points"]
assert len(watson_points) == 46
assert not any(row["map_no"] == 6 and row.get("map_suffix") is None for row in watson_points), "source map has no standalone Fork #6 marker"
assert {row["map_suffix"] for row in watson_points if row["map_no"] == 6} == set("abcdefghi")
assert [row["map_no"] for row in watson_points if row.get("map_suffix") is None] == [1,2,3,4,5] + list(range(7,39))
watson_fork_ids = {row["entity_id"] for row in watson_points if row["map_no"] == 6}
assert len(watson_fork_ids) == 9
assert all(fixture_entities[entity_id].get("parent_entity_id") == "NC2045-LOC-WATSON-DEVELOPMENT-188-THE-FORK" for entity_id in watson_fork_ids)
for recovered_id in {
    "NC2045-LOC-WATSON-DEVELOPMENT-193-REDLINE",
    "NC2045-LOC-WATSON-DEVELOPMENT-193-SAKURA-S",
    "NC2045-LOC-WATSON-DEVELOPMENT-194-SMASH-CUT",
    "NC2045-LOC-WATSON-DEVELOPMENT-194-TRAUMA-TEAM-TOWER",
    "NC2045-LOC-WATSON-DEVELOPMENT-195-VARGTIMMEN",
}:
    assert sum(row["entity_id"] == recovered_id for row in watson_points) == 1, recovered_id

assert len(paths) == 15, f"expected fifteen mapped districts, found {len(paths)}"
total_points = sum(len(json.loads(path.read_text(encoding="utf-8"))["points"]) for path in paths)
assert total_points == 371, f"expected 371 source-point manifestations, found {total_points}"
print(f"OK: source-map geometry; maps={len(paths)}, fixture_entities={len(fixture_entities)}, total_points={total_points}")
