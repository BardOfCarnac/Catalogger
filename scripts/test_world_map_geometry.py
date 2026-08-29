#!/usr/bin/env python3
"""Structural and identity regression tests for Vend-R source-map geometry files."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


fixture_paths = sorted(WORLD_DIR.glob("*.v1.json")) + sorted((WORLD_DIR / "recovered").glob("*.v1.json"))
fixture_entities: dict[str, dict] = {}
for fixture_path in fixture_paths:
    fixture = load_json(fixture_path)
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
    doc = load_json(path)
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
            assert entity["map_no"] == row["map_no"], (
                f"source marker mismatch for {row['entity_id']}: "
                f"fixture={entity['map_no']} geometry={row['map_no']}"
            )

        co_located = row.get("co_located_entity_ids", [])
        assert isinstance(co_located, list), (path, row)
        assert len(co_located) == len(set(co_located)), (path, row)
        assert row["entity_id"] not in co_located, (path, row)
        for co_id in co_located:
            co_entity = fixture_entities.get(co_id)
            assert co_entity is not None, f"geometry co-location points at unknown entity: {co_id}"
            assert co_entity.get("district") == doc["district"], (path, row, co_entity)
            if co_entity.get("map_no") is not None:
                assert co_entity["map_no"] == row["map_no"], (
                    f"co-located source marker mismatch for {co_id}: "
                    f"fixture={co_entity['map_no']} geometry={row['map_no']}"
                )


def geometry(slug: str) -> dict:
    return load_json(WORLD_DIR / f"map-geometry.{slug}.v0.1.json")


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
    "new-westbrook": 25,
    "heywood-industrial-zone": 19,
    "heywood-docks": 10,
    "norcal-military-base": 17,
    "rancho-coronado": 11,
}
loaded: dict[str, dict] = {}
for slug, expected_len in ordinary_specs.items():
    doc = geometry(slug)
    loaded[slug] = doc
    assert len(doc["points"]) == expected_len
    assert [row["map_no"] for row in doc["points"]] == list(range(1, expected_len + 1))

assert any(
    row["entity_id"] == "NC2045-LOC-LITTLE-EUROPE-060-KAITO-MARKET"
    for row in loaded["little-europe"]["points"]
)
assert not any(
    row["name"] == "The Soup Truck" for row in loaded["new-westbrook"]["points"]
), "source explicitly says The Soup Truck is not shown on the map"
assert not any(
    "MAQUILADORAS" in row["entity_id"] for row in loaded["rancho-coronado"]["points"]
), "source explicitly lists The Maquiladoras as not shown on the map"

university_points = geometry("university-district")["points"]
assert len(university_points) == 33
assert [row["map_no"] for row in university_points if row.get("map_suffix") is None] == [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19
]
assert not any(row["map_no"] == 11 and row.get("map_suffix") is None for row in university_points)
assert {row["map_suffix"] for row in university_points if row.get("map_suffix")} == set("abcdefghijklm")
assert sum(row["map_no"] == 11 and row.get("map_suffix") == "d" for row in university_points) == 3
assert len({row["point_id"] for row in university_points}) == len(university_points)

executive_points = geometry("executive-zone")["points"]
assert len(executive_points) == 21
assert not any(row["map_no"] == 1 and row.get("map_suffix") is None for row in executive_points)
assert {row["map_suffix"] for row in executive_points if row["map_no"] == 1} == set("abcdefghijkl")
assert [row["map_no"] for row in executive_points if row.get("map_suffix") is None] == list(range(2, 11))
assert {row["entity_id"] for row in executive_points if row["map_no"] == 1} == {
    "NC2045-LOC-EXECUTIVE-ZONE-234-THE-ESTATES"
}

glen_points = geometry("the-glen")["points"]
assert len(glen_points) == 33
assert not any(row["map_no"] == 9 and row.get("map_suffix") is None for row in glen_points)
assert {row["map_suffix"] for row in glen_points if row["map_no"] == 9} == set("abcdef")
assert [row["map_no"] for row in glen_points if row.get("map_suffix") is None] == (
    list(range(1, 9)) + list(range(10, 29))
)

old_combat_points = geometry("old-combat-zone")["points"]
assert len(old_combat_points) == 22
assert [row["map_no"] for row in old_combat_points if row.get("map_suffix") is None] == list(range(1, 17))
assert {
    row["map_suffix"] for row in old_combat_points
    if row["map_no"] == 16 and row.get("map_suffix")
} == set("abcdef")
assert any(
    row["map_no"] == 16 and row.get("map_suffix") is None for row in old_combat_points
), "source map includes the Warren parent marker as well as 16a-16f"

watson_points = geometry("watson-development")["points"]
assert len(watson_points) == 46
assert not any(
    row["map_no"] == 6 and row.get("map_suffix") is None for row in watson_points
), "source map has no standalone Fork #6 marker"
assert {row["map_suffix"] for row in watson_points if row["map_no"] == 6} == set("abcdefghi")
assert [row["map_no"] for row in watson_points if row.get("map_suffix") is None] == (
    [1, 2, 3, 4, 5] + list(range(7, 39))
)
watson_fork_ids = {row["entity_id"] for row in watson_points if row["map_no"] == 6}
assert len(watson_fork_ids) == 9
assert all(
    fixture_entities[entity_id].get("parent_entity_id") == "NC2045-LOC-WATSON-DEVELOPMENT-188-THE-FORK"
    for entity_id in watson_fork_ids
)
for recovered_id in {
    "NC2045-LOC-WATSON-DEVELOPMENT-193-REDLINE",
    "NC2045-LOC-WATSON-DEVELOPMENT-193-SAKURA-S",
    "NC2045-LOC-WATSON-DEVELOPMENT-194-SMASH-CUT",
    "NC2045-LOC-WATSON-DEVELOPMENT-194-TRAUMA-TEAM-TOWER",
    "NC2045-LOC-WATSON-DEVELOPMENT-195-VARGTIMMEN",
}:
    assert sum(row["entity_id"] == recovered_id for row in watson_points) == 1, recovered_id

north_heywood_points = geometry("north-heywood")["points"]
assert len(north_heywood_points) == 23
assert [row["map_no"] for row in north_heywood_points if row.get("map_suffix") is None] == list(range(1, 18))
assert not any(
    row["map_no"] == 18 and row.get("map_suffix") is None for row in north_heywood_points
), "source legend names Woodland Park #18 but the map draws only 18a-18f"
assert {row["map_suffix"] for row in north_heywood_points if row["map_no"] == 18} == set("abcdef")
woodland_parent = "NC2045-LOC-NORTH-HEYWOOD-252-WOODLAND-PARK"
for row in north_heywood_points:
    if row["map_no"] == 18 and row.get("map_suffix") != "b":
        assert fixture_entities[row["entity_id"]].get("parent_entity_id") == woodland_parent
point_18b = next(
    row for row in north_heywood_points
    if row["map_no"] == 18 and row.get("map_suffix") == "b"
)
assert point_18b["entity_id"] == "NC2045-OUT-NORTH-HEYWOOD-252-BREEZE"
assert point_18b.get("co_located_entity_ids") == [
    "NC2045-MEN-NORTH-HEYWOOD-252-BURNING-BRIGHT-BODEGA"
]
assert fixture_entities[point_18b["entity_id"]].get("parent_entity_id") == woodland_parent
assert all(
    fixture_entities[entity_id].get("parent_entity_id") == woodland_parent
    for entity_id in point_18b["co_located_entity_ids"]
)

santo_points = geometry("santo-domingo")["points"]
assert len(santo_points) == 27
assert [row["map_no"] for row in santo_points if row.get("map_suffix") is None] == list(range(1, 20))
assert any(
    row["map_no"] == 2 and row.get("map_suffix") is None for row in santo_points
), "source map includes the Aldecaldo Camp parent #2 as well as 2a-2h"
assert {
    row["map_suffix"] for row in santo_points
    if row["map_no"] == 2 and row.get("map_suffix")
} == set("abcdefgh")
aldecaldo_parent = "NC2045-LOC-SANTO-DOMINGO-266-ALDECALDO-CAMP"
for row in santo_points:
    if row["map_no"] == 2 and row.get("map_suffix"):
        assert fixture_entities[row["entity_id"]].get("parent_entity_id") == aldecaldo_parent

assert len(paths) == 22, f"expected twenty-two mapped districts, found {len(paths)}"
total_points = sum(len(load_json(path)["points"]) for path in paths)
assert total_points == 503, f"expected 503 source-point manifestations, found {total_points}"
print(
    f"OK: source-map geometry; maps={len(paths)}, "
    f"fixture_entities={len(fixture_entities)}, total_points={total_points}"
)
