#!/usr/bin/env python3
"""Regression tests for the recovered Night City 2045 transit network."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data/worlds/night-city-2045"
NETWORK_PATH = WORLD_DIR / "transit/network.v0.1.json"
ROUTES_PATH = WORLD_DIR / "transit/routes.v0.1.geojson"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


network = load_json(NETWORK_PATH)
routes = load_json(ROUTES_PATH)
assert network["format_version"] == "0.1.0"
assert network["world_id"] == "night-city-2045"
assert network["network_id"] == "nc2045-transit-v0.1"
assert network["source"]["printed_page"] == 27
assert network["source"]["flashmap"] == "Railways"

# Preserve the source-derived global line geometry separately from logical station topology.
assert routes["type"] == "FeatureCollection"
assert routes["metadata"]["world_id"] == "night-city-2045"
assert routes["metadata"]["coordinate_space"] == "night_city_clean_master_5175x7966_px"
route_features = routes["features"]
assert len(route_features) == 6
route_by_id = {row["properties"]["line_id"]: row for row in route_features}
assert set(route_by_id) == {"red", "green", "blue", "orange", "cargo", "purple"}
for line_id in {"red", "green", "blue", "orange"}:
    assert route_by_id[line_id]["geometry"]["type"] == "LineString"
for line_id in {"cargo", "purple"}:
    assert route_by_id[line_id]["geometry"]["type"] == "MultiLineString"
assert route_by_id["red"]["geometry"]["coordinates"][0] == [1989.76, 2245.539]
assert route_by_id["cargo"]["properties"]["geometry_status"] == "derived_from_source_vector"
# The source freight geometry deliberately extends outside the clean master raster.
cargo_coords = [point for part in route_by_id["cargo"]["geometry"]["coordinates"] for point in part]
assert any(x > 5175 or y > 7966 or x < 0 or y < 0 for x, y in cargo_coords)

assert set(network["lines"]) == {"red", "green", "blue", "orange", "cargo", "purple"}
assert {row["system"] for row in network["lines"].values()} == {
    "NCART", "Cargo Rail", "Executive Monorail"
}

stations = network["stations"]
assert len(stations) == 50
assert [row["station_id"] for row in stations] == list(range(1, 51))
by_id = {row["station_id"]: row for row in stations}

expected = {
    "red": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "green": [4, 12, 13, 14, 15, 16, 11, 17],
    "blue": [6, 18, 19, 20, 21, 22, 23, 24, 25],
    "orange": [23, 26, 27, 28, 29, 30, 31],
}
assert {key: network["service_sequences"][key] for key in expected} == expected
assert network["service_sequences"]["cargo"] == {
    "inner_circuit": [32, 33, 34, 35, 32],
    "outer_circuit": [32, 33, 37, 36, 34, 35, 32],
}
assert network["service_sequences"]["purple"] == {
    "main_loop": [39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 39],
    "executive_zone_spur": [39, 38],
    "ziggurat_spur": [39, 40],
}

# Topology is encoded as ordered services/circuits. The recovered graph had 54 logical edges.
def edge_count(sequence: list[int]) -> int:
    return len(sequence) - 1


derived_edges = sum(edge_count(seq) for seq in expected.values())
derived_edges += sum(edge_count(seq) for seq in network["service_sequences"]["cargo"].values())
derived_edges += sum(edge_count(seq) for seq in network["service_sequences"]["purple"].values())
assert derived_edges == 54

# Station line memberships must agree exactly with the topology.
membership: dict[int, set[str]] = {station_id: set() for station_id in by_id}
for line, seq in expected.items():
    for station_id in seq:
        membership[station_id].add(line)
for seq in network["service_sequences"]["cargo"].values():
    for station_id in seq:
        membership[station_id].add("cargo")
for seq in network["service_sequences"]["purple"].values():
    for station_id in seq:
        membership[station_id].add("purple")
for station_id, row in by_id.items():
    assert set(row["lines"]) == membership[station_id], (station_id, row["lines"], membership[station_id])

# Only the four source transfer stations are interchanges.
transfer_ids = [row["station_id"] for row in network["transfers"]]
assert transfer_ids == [4, 6, 11, 23]
assert {station_id for station_id, row in by_id.items() if row["transfer"]} == {4, 6, 11, 23}

# The two same-named Charter Hill stations are distinct source IDs, not a fabricated interchange.
assert by_id[14]["name"] == by_id[39]["name"] == "Charter Hill Station"
assert by_id[14]["lines"] == ["green"]
assert by_id[39]["lines"] == ["purple"]
assert by_id[14]["transfer"] is False and by_id[39]["transfer"] is False
assert (by_id[14]["x_master_px"], by_id[14]["y_master_px"]) != (
    by_id[39]["x_master_px"], by_id[39]["y_master_px"]
)

# Guard the recovered refinement: the old graph accidentally retained the source marker centre
# for station 1 instead of the refined rail/street position.
assert (by_id[1]["x_master_px"], by_id[1]["y_master_px"]) == (1989.76, 2245.539)
assert (by_id[1]["x_master_px"], by_id[1]["y_master_px"]) != (1950.031, 2224.092)
assert by_id[1]["refinement"]["method"] == "named_street_rail_road_intersection"

# Normalized master-raster coordinates must agree with the stored pixel positions.
width = network["coordinate_space"]["width"]
height = network["coordinate_space"]["height"]
assert (width, height) == (5175, 7966)
for row in stations:
    assert abs(row["x_norm"] - row["x_master_px"] / width) < 1e-8
    assert abs(row["y_norm"] - row["y_master_px"] / height) < 1e-8

off_raster = [row["station_id"] for row in stations if not row["inside_master_raster"]]
assert off_raster == [35]
assert by_id[35]["name"] == "Pol-Bud Cement Factory"
assert by_id[35]["x_norm"] > 1.0
assert by_id[35]["refinement"]["method"] == "retained_off_raster_source_position"

# Resolve transit-to-world links against the same active + recovered canonical entity layer
# used by source-map geometry. Street-named transit nodes deliberately need no place identity.
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

linked_stations = 0
canonical_refs = 0
for row in stations:
    refs = row.get("canonical_refs", [])
    assert len({ref["entity_id"] for ref in refs}) == len(refs)
    if refs:
        linked_stations += 1
    for ref in refs:
        canonical_refs += 1
        assert ref["relation"] in {"same_site", "serves_named_destination"}
        assert ref["entity_id"] in fixture_entities, (row["station_id"], ref["entity_id"])

assert linked_stations == 24
assert canonical_refs == 27

same_site_expected = {
    11: "NC2045-LOC-HEYWOOD-INDUSTRIAL-ZONE-259-THE-INTERCHANGE",
    33: "NC2045-LOC-HEYWOOD-DOCKS-243-RAIL-YARD",
    34: "NC2045-LOC-OUTSKIRTS-299-UNION-RAILROAD-STATION",
    35: "NC2045-LOC-OUTSKIRTS-298-POL-BUD-CEMENT-FACTORY",
    36: "NC2045-LOC-OUTSKIRTS-297-MILITECH-BALLISTICS-EXPLOSIVES-RANGE",
    38: "NC2045-LOC-EXECUTIVE-ZONE-236-MONORAIL-STATION",
}
for station_id, entity_id in same_site_expected.items():
    assert by_id[station_id]["canonical_refs"] == [{"entity_id": entity_id, "relation": "same_site"}]

assert "source_page_uv" in network["reconciliation"].get("coordinate_space_note", "") or (
    "source_page_uv" in network["reconciliation"].get("policy", "")
), "network must explicitly distinguish district-local geometry from global transit coordinates"

print(
    "OK: Night City 2045 transit; "
    f"stations={len(stations)}, logical_edges={derived_edges}, "
    f"transfers={len(transfer_ids)}, linked_stations={linked_stations}, canonical_refs={canonical_refs}"
)
