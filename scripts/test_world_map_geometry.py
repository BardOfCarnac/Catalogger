#!/usr/bin/env python3
"""Structural and identity regression tests for Vend-R source-map geometry files."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"

fixture_paths = sorted(WORLD_DIR.glob("*.v1.json")) + sorted(
    (WORLD_DIR / "recovered").glob("*.v1.json")
)
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
    assert doc["world_id"], path
    assert doc["map_id"], path
    assert doc["district"], path
    assert doc["coordinate_space"] == "source_page_uv", path

    points = doc["points"]
    assert points, path

    point_ids = [row["point_id"] for row in points if row.get("point_id")]
    assert len(point_ids) == len(set(point_ids)), f"duplicate point id: {path}"

    coordinate_keys = [
        (row["map_no"], row.get("map_suffix"), row["x"], row["y"])
        for row in points
    ]
    assert len(coordinate_keys) == len(set(coordinate_keys)), f"duplicate source point: {path}"

    for row in points:
        assert isinstance(row["map_no"], int) and row["map_no"] > 0, (path, row)
        suffix = row.get("map_suffix")
        if suffix is not None:
            assert len(suffix) == 1 and suffix.isascii() and suffix.islower(), (path, row)
        assert row["name"], (path, row)
        assert row["entity_id"], (path, row)
        assert 0.0 <= row["x"] <= 1.0, (path, row)
        assert 0.0 <= row["y"] <= 1.0, (path, row)

        entity = fixture_entities.get(row["entity_id"])
        assert entity is not None, f"geometry points at unknown entity: {row['entity_id']}"
        assert entity.get("district") == doc["district"], (path, row, entity)
        if entity.get("map_no") is not None:
            assert entity["map_no"] == row["map_no"], (
                f"source marker mismatch for {row['entity_id']}: "
                f"fixture={entity['map_no']} geometry={row['map_no']}"
            )

downtown = json.loads(
    (WORLD_DIR / "map-geometry.downtown.v0.1.json").read_text(encoding="utf-8")
)
assert [row["map_no"] for row in downtown["points"]] == list(range(1, 24))
assert len(downtown["points"]) == 23

little_china = json.loads(
    (WORLD_DIR / "map-geometry.little-china.v0.1.json").read_text(encoding="utf-8")
)
assert [row["map_no"] for row in little_china["points"]] == list(range(1, 16))
assert len(little_china["points"]) == 15

university = json.loads(
    (WORLD_DIR / "map-geometry.university-district.v0.1.json").read_text(encoding="utf-8")
)
university_points = university["points"]
assert len(university_points) == 33
assert [
    row["map_no"] for row in university_points if row.get("map_suffix") is None
] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19]
assert not any(
    row["map_no"] == 11 and row.get("map_suffix") is None
    for row in university_points
), "the source map has no fabricated unsuffixed #11 centroid"
assert {row["map_suffix"] for row in university_points if row.get("map_suffix")} == set("abcdefghijklm")
assert sum(
    row["map_no"] == 11 and row.get("map_suffix") == "d"
    for row in university_points
) == 3, "the source draws The Cells / 11d at three distinct positions"
assert len({row["point_id"] for row in university_points}) == len(university_points)

upper_marina = json.loads(
    (WORLD_DIR / "map-geometry.upper-marina.v0.1.json").read_text(encoding="utf-8")
)
assert [row["map_no"] for row in upper_marina["points"]] == list(range(1, 41))
assert len(upper_marina["points"]) == 40

little_europe = json.loads(
    (WORLD_DIR / "map-geometry.little-europe.v0.1.json").read_text(encoding="utf-8")
)
assert [row["map_no"] for row in little_europe["points"]] == list(range(1, 24))
assert len(little_europe["points"]) == 23
assert any(
    row["entity_id"] == "NC2045-LOC-LITTLE-EUROPE-060-KAITO-MARKET"
    for row in little_europe["points"]
), "Little Europe must resolve the legacy dedicated Kaito Market fixture"

print(
    f"OK: source-map geometry; maps={len(paths)}, "
    f"fixture_entities={len(fixture_entities)}, "
    f"downtown_points={len(downtown['points'])}, "
    f"little_china_points={len(little_china['points'])}, "
    f"university_points={len(university_points)}, "
    f"upper_marina_points={len(upper_marina['points'])}, "
    f"little_europe_points={len(little_europe['points'])}"
)
