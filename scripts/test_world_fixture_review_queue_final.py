#!/usr/bin/env python3
"""Regression tests for the final 22 held-out Review Queue candidates."""
from pathlib import Path

from world_fixture import load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

FILES = {
    "charter": ROOT / "data/worlds/night-city-2045/charter-hill-review-queue.v1.json",
    "little_europe": ROOT / "data/worlds/night-city-2045/little-europe-review-queue.v1.json",
    "norcal": ROOT / "data/worlds/night-city-2045/norcal-military-base-review-queue.v1.json",
    "north_heywood": ROOT / "data/worlds/night-city-2045/north-heywood-review-queue.v1.json",
    "executive": ROOT / "data/worlds/night-city-2045/executive-zone-review-queue.v1.json",
    "port": ROOT / "data/worlds/night-city-2045/port-of-night-city-review-queue.v1.json",
    "reclamation": ROOT / "data/worlds/night-city-2045/reclamation-zone-review-queue.v1.json",
    "hiz": ROOT / "data/worlds/night-city-2045/heywood-industrial-zone-review-queue.v1.json",
    "santo": ROOT / "data/worlds/night-city-2045/santo-domingo-review-queue.v1.json",
    "south": ROOT / "data/worlds/night-city-2045/south-night-city-review-queue.v1.json",
    "hot": ROOT / "data/worlds/night-city-2045/the-hot-zone-review-queue.v1.json",
}

realized = {}
for key, path in FILES.items():
    source = load_json(path)
    validate_document(source)
    a = realize_document(source, engine)
    b = realize_document(source, engine)
    assert a == b, f"{key} Review Queue fixture realization must be deterministic"
    realized[key] = {row["name"]: row for row in a["entities"]}

# Charter Hill
charter = realized["charter"]
assert charter["The Columbarium"]["entity_type"] == "service"
assert charter["The Ladder"]["parent_entity_id"] == "NC2045-LOC-CHARTER-HILL-227-HILLSIDE-COUNTRY-CLUB"
assert charter["Café Divine"]["parent_entity_id"] == "NC2045-LOC-CHARTER-HILL-228-HOTEL-MUY-CARO"

# Little Europe
little = realized["little_europe"]
assert little["Old Saint Christopher Center"]["entity_type"] == "container"
assert little["Old Saint Christopher Lobby Boutiques"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert little["Old Saint Christopher Private Casino"]["access_model"] == "exclusive-hotel-guests"
assert little["Paradiso Terrestre"]["entity_type"] == "service"
assert any(row["service_key"] == "monthly-package-subscription" for row in little["Revere Courier Services"]["services"])

# NorCal
norcal = realized["norcal"]
assert norcal["Militech Offices"]["entity_type"] == "container"
assert norcal["Militech Client Showroom"]["access_model"] == "select-clients"
assert "assortment" not in norcal["Militech Client Showroom"]
assert norcal["The Oaks"]["entity_type"] == "context"
assert norcal["The Rec Center"]["entity_type"] == "service"

# North Heywood
north = realized["north_heywood"]
assert north["Acorn Towers"]["entity_type"] == "context"
assert north["Blue Air Studio Apartments"]["services"][0]["service_key"] == "long-term-studio-rental"
assert north["Perennial Heights/The Rupture"]["entity_type"] == "container"
assert north["Wash n’ Run"]["parent_entity_id"] == "NC2045-LOC-NORTH-HEYWOOD-251-PERENNIAL-HEIGHTS-THE-RUPTURE"
assert north["The Rupture"]["access_model"] == "discreet"

# Executive Zone
executive = realized["executive"]
assert executive["Executive Zone Casino/Country Club"]["schedule"]["kind"] == "daily_hours"
assert executive["Seacliff"]["local_offerings"][0]["price_eb"] == 100
assert executive["Puddleforge Games"]["entity_type"] == "channel"
assert executive["Puddleforge Games"]["stock_policy"] == "NO_STATIC_INVENTORY"

# Port
port = realized["port"]
assert port["Dock 14 Studio Apartments"]["entity_type"] == "context"
assert port["Flotsam"]["entity_type"] == "container"
assert port["Randy Dandy"]["local_offerings"][0]["price_eb"] == 20
assert port["Pilot's Club"]["access_model"] == "tug-pilots"

# Reclamation
reclamation = realized["reclamation"]
assert reclamation["Booster Bistro"]["entity_type"] == "hybrid"
assert reclamation["Foundry Tech School"]["entity_type"] == "service"

# Small districts
hiz = realized["hiz"]
assert hiz["Zhirafa MicroVillage"]["entity_type"] == "container"
assert hiz["Zhirafa MicroVillage Streetcarts"]["stock_policy"] == "NO_STATIC_INVENTORY"
assert hiz["Vodka Container"]["local_offerings"][0]["price_eb"] == 5
assert realized["santo"]["88.9 Nomad Presents Radio (NoPR)"]["entity_type"] == "service"
assert realized["south"]["University Cargo Bay"]["entity_type"] == "context"
assert realized["hot"]["Ashcroft Hotel"]["entity_type"] == "context"

stock_bearers = {
    row["name"]
    for fixture in realized.values()
    for row in fixture.values()
    if row.get("assortment")
}
assert stock_bearers == set(), stock_bearers

entity_count = sum(len(rows) for rows in realized.values())
assert entity_count == 36, entity_count
print("OK: final held-out Review Queue batch; candidates=22, entities=36, recovered_children=14, stock-bearing=0")
