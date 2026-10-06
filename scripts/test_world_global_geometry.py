#!/usr/bin/env python3
"""Validate the unified global registration of Night City 2045 source-map points."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"
GLOBAL_PATH = WORLD_DIR / "map-geometry.global.v0.1.json"
CALIBRATION_PATH = WORLD_DIR / "map-calibration.global.v0.1.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


global_doc = load_json(GLOBAL_PATH)
cal_doc = load_json(CALIBRATION_PATH)
points = global_doc["points"]

assert global_doc["format_version"] == "0.1.0"
assert global_doc["world_id"] == "night-city-2045"
assert global_doc["coordinate_space"] == {
    "id": "night_city_clean_master_5175x7966_px",
    "width": 5175,
    "height": 7966,
    "origin": "top-left",
    "x_axis": "+right",
    "y_axis": "+down",
}
assert global_doc["summary"] == {
    "exact_global_points": 556,
    "approximate_global_points": 52,
    "nested_local_points": 52,
    "total_manifestations": 608,
    "unresolved_points": 0,
}
assert len(points) == 608

source_paths = [
    path for path in sorted(WORLD_DIR.glob("map-geometry.*.v0.1.json"))
    if path.name != GLOBAL_PATH.name
]
assert len(source_paths) == 26
source_docs = [load_json(path) for path in source_paths]
assert sum(len(doc["points"]) for doc in source_docs) == 608

by_district: dict[str, list[dict]] = {}
for row in points:
    by_district.setdefault(row["district"], []).append(row)
assert len(by_district) == 26

cal_by_district = {row["district"]: row for row in cal_doc["calibrations"]}
assert len(cal_by_district) == 25
assert cal_doc["local_only_maps"][0]["district"] == "Playland by the Sea Lands"

def sort_key(row: dict):
    return (
        int(row["map_no"]),
        row.get("map_suffix", ""),
        row.get("point_id", ""),
        row["entity_id"],
        tuple(row.get("source_page_uv", [row.get("x"), row.get("y")])),
    )

for doc in source_docs:
    district = doc["district"]
    source_rows = []
    for row in doc["points"]:
        source_rows.append({
            "district": district,
            "map_no": row["map_no"],
            **({"map_suffix": row["map_suffix"]} if row.get("map_suffix") else {}),
            **({"point_id": row["point_id"]} if row.get("point_id") else {}),
            "name": row["name"],
            "entity_id": row["entity_id"],
            "source_page_uv": [row["x"], row["y"]],
        })

    global_rows = by_district[district]
    assert len(global_rows) == len(source_rows), (district, len(global_rows), len(source_rows))

    for src, glob in zip(sorted(source_rows, key=sort_key), sorted(global_rows, key=sort_key)):
        assert glob["map_no"] == src["map_no"]
        assert glob.get("map_suffix") == src.get("map_suffix")
        assert glob.get("point_id") == src.get("point_id")
        assert glob["entity_id"] == src["entity_id"]
        assert glob["name"] == src["name"]
        assert glob["source_page_uv"] == src["source_page_uv"]

        gx, gy = glob["global_master_px"]
        gu, gv = glob["global_uv"]
        assert abs(gu - gx / 5175) < 2e-7
        assert abs(gv - gy / 7966) < 2e-7

        if district == "Playland by the Sea Lands":
            assert glob["registration"]["status"] == "approximate_parent_footprint"
            assert glob["registration"]["method"] == "playland_parent_footprint_affine"
        else:
            assert glob["registration"]["status"] == "source_exact"
            assert glob["registration"]["method"] == "source_master_image_transform"
            cal = cal_by_district[district]
            assert cal["status"] == "exact_full_city_master_registration"
            a = cal["placement_matrix"]["a"]
            d = cal["placement_matrix"]["d"]
            e = cal["placement_matrix"]["e"]
            f = cal["placement_matrix"]["f"]
            x_page = src["source_page_uv"][0] * 612
            y_page = src["source_page_uv"][1] * 792
            expected_x = ((x_page - e) / a) * 5175
            expected_y = ((y_page - f) / d) * 7966
            assert abs(gx - expected_x) < 0.01, (district, src["name"], gx, expected_x)
            assert abs(gy - expected_y) < 0.01, (district, src["name"], gy, expected_y)

playland = global_doc["nested_local_maps"]
assert len(playland) == 1
playland = playland[0]
assert playland["district"] == "Playland by the Sea Lands"
assert playland["point_count"] == 52
assert playland["registration_status"] == "approximate_parent_footprint"
x0, y0, x1, y1 = playland["global_footprint_bbox_master_px"]
for row in by_district["Playland by the Sea Lands"]:
    x, y = row["global_master_px"]
    assert x0 - 1e-6 <= x <= x1 + 1e-6
    assert y0 - 1e-6 <= y <= y1 + 1e-6

# Independent transit-derived checks on exact same-site registrations.
transit = load_json(WORLD_DIR / "transit/network.v0.1.json")
entity_points: dict[str, list[dict]] = {}
for row in points:
    entity_points.setdefault(row["entity_id"], []).append(row)
station_by_id = {row["station_id"]: row for row in transit["stations"]}

for station_id, entity_id, max_distance in [
    (34, "NC2045-LOC-OUTSKIRTS-299-UNION-RAILROAD-STATION", 30.0),
    (38, "NC2045-LOC-EXECUTIVE-ZONE-236-MONORAIL-STATION", 35.0),
]:
    station = station_by_id[station_id]
    row = entity_points[entity_id][0]
    dx = row["global_master_px"][0] - station["x_master_px"]
    dy = row["global_master_px"][1] - station["y_master_px"]
    assert (dx * dx + dy * dy) ** 0.5 < max_distance, (station_id, dx, dy)

print(
    "OK: unified global source-map geometry; "
    "exact=556, playland_approx=52, total=608, unresolved=0"
)
