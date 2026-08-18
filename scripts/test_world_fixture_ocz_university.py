#!/usr/bin/env python3
"""Regression tests for Old Combat Zone and University District source-review batches."""
from pathlib import Path

from import_nc2045_audit_batch import import_batch
from world_fixture import WorldFixtureError, load_json, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

# Audit inputs stay drafts and cannot produce persistent shop state before source review.
for audit_rel, expected in [
    ("data/worlds/night-city-2045/import/old-combat-zone-core.audit-v0.2.json", 5),
    ("data/worlds/night-city-2045/import/university-district-core.audit-v0.2.json", 4),
]:
    audit_source = load_json(ROOT / audit_rel)
    draft = import_batch(audit_source)
    assert len(draft["entities"]) == expected
    assert draft["fixture_status"] == "audit_draft"
    validate_document(draft, allow_drafts=True)
    try:
        realize_document(draft, engine)
    except WorldFixtureError:
        pass
    else:
        raise AssertionError("audit draft was allowed to generate persistent stock")

# Old Combat Zone: only Kibble Kirkle receives generic catalogue stock. The Warren delegates,
# while Baskin Books, the Smithery and Uncle Anne's retain source-specific local wares.
ocz_source = load_json(ROOT / "data/worlds/night-city-2045/old-combat-zone-core.v1.json")
validate_document(ocz_source)
ocz_a = realize_document(ocz_source, engine)
ocz_b = realize_document(ocz_source, engine)
assert ocz_a == ocz_b, "Old Combat Zone fixture realization must be deterministic"
ocz = {row["name"]: row for row in ocz_a["entities"]}
assert len(ocz) == 5
assert {name for name, row in ocz.items() if row.get("assortment")} == {"Kibble Kirkle"}

warren = ocz["The Warren"]
assert warren["entity_type"] == "container"
assert warren["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in warren

kirkle = ocz["Kibble Kirkle"]
assert kirkle["assortment"]
for row in kirkle["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "General Equipment" or path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]

baskin = ocz["B. Baskin Books"]
assert "assortment" not in baskin
assert baskin["local_offerings"][0]["offering_key"] == "used-recovered-books"
assert baskin["purchase_policy"]["price_eb_each"] == 1

smithery = ocz["E. Smithery"]
assert "assortment" not in smithery
assert smithery["book_page"] == 172
assert smithery["customer_pricing"]["outsider_multiplier"] == 3.0
assert {row["offering_key"] for row in smithery["local_offerings"]} == {
    "unique-hand-forged-firearms", "reproduction-firearms"
}

uncle_anne = ocz["F. Uncle Anne’s"]
assert "assortment" not in uncle_anne
assert uncle_anne["book_page"] == 172
assert {row["offering_key"] for row in uncle_anne["local_offerings"]} == {
    "real-meat", "kibble-by-bag"
}

# University District: NCU delegates to campus children; the clinic remains a service; Carriage
# Street remains source-local; Lombardy and Retail Resale are the two constrained stock sellers.
uni_source = load_json(ROOT / "data/worlds/night-city-2045/university-district-core.v1.json")
validate_document(uni_source)
uni_a = realize_document(uni_source, engine)
uni_b = realize_document(uni_source, engine)
assert uni_a == uni_b, "University District fixture realization must be deterministic"
uni = {row["name"]: row for row in uni_a["entities"]}
assert len(uni) == 5
assert {name for name, row in uni.items() if row.get("assortment")} == {
    "I. Lombardy Groceries", "Retail Resale"
}

carriage = uni["Carriage Street Books/Afterwords Café"]
assert "assortment" not in carriage
assert {row["offering_key"] for row in carriage["local_offerings"]} == {
    "books-magazines-graphic-novels", "course-text-memory-chips", "cafe-food-coffee"
}

ncu = uni["Night City University"]
assert ncu["entity_type"] == "container"
assert ncu["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in ncu

clinic = uni["J. NCU Clinic"]
assert "assortment" not in clinic
assert clinic["parent_entity_id"] == "NC2045-LOC-UNIVERSITY-DISTRICT-108-NIGHT-CITY-UNIVERSITY"
assert {row["service_key"] for row in clinic["services"]} == {
    "campus-medical-treatment", "cyberware-implantation"
}

lombardy = uni["I. Lombardy Groceries"]
assert lombardy["book_page"] == 109
assert lombardy["assortment"]
for row in lombardy["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "General Equipment" or path[:2] == ["Food, Drink & Consumables", "Foodstuffs"]

resale = uni["Retail Resale"]
assert resale["assortment"]
for row in resale["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] == "Fashion & Personal"
assert resale["shop"]["stocking_profile"]["condition_weights"] == {
    "new": 0, "used": 10, "refurbished": 0, "damaged": 0, "salvaged": 0
}

print(
    "OK: Old Combat Zone + University District source-review batches; "
    f"OCZ entities={len(ocz)}, University entities={len(uni)}"
)
