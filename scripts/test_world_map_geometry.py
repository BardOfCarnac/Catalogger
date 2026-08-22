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
    for entity in fixture.get("entities", []):
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
    map_numbers = [row["map_no"] for row in points]
    entity_ids = [row["entity_id"] for row in points]
    assert len(map_numbers) == len(set(map_numbers)), f"duplicate map number: {path}"
    assert len(entity_ids) == len(set(entity_ids)), f"duplicate entity id: {path}"

    for row in points:
        assert isinstance(row["map_no"], int) and row["map_no"] > 0, (path, row)
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

print(
    f"OK: source-map geometry; maps={len(paths)}, "
    f"fixture_entities={len(fixture_entities)}, "
    f"downtown_points={len(downtown['points'])}, "
    f"little_china_points={len(little_china['points'])}"
)
