#!/usr/bin/env python3
"""Regression tests for generic source-defined world fixtures and audit import gating."""
from pathlib import Path

from import_nc2045_audit_batch import import_batch
from world_fixture import WorldFixtureError, load_json, normalize_document, realize_document, validate_document
from world_stock_engine import WorldStockEngine

ROOT = Path(__file__).resolve().parents[1]
engine = WorldStockEngine()

# The original Kaito pilot remains valid through legacy normalization.
kaito_source = load_json(ROOT / "data/worlds/night-city-2045/kaito-market.v1.json")
kaito_flat = normalize_document(kaito_source)
assert kaito_flat["fixture_status"] == "source_reviewed"
assert len(kaito_flat["entities"]) == 11
assert kaito_flat["entities"][0]["entity_type"] == "container"
kaito_a = realize_document(kaito_source, engine)
kaito_b = realize_document(kaito_source, engine)
assert kaito_a == kaito_b, "Kaito generic realization must remain deterministic"
assert sum(bool(row.get("assortment")) for row in kaito_a["entities"]) == 4

# Audit imports are structured drafts only. They may validate in draft mode but must not
# generate live/persistent shop state until a source-review fixture replaces/promotes them.
for audit_rel, expected in [
    ("data/worlds/night-city-2045/import/downtown-core.audit-v0.2.json", 5),
    ("data/worlds/night-city-2045/import/little-europe-remainder.audit-v0.2.json", 3),
    ("data/worlds/night-city-2045/import/upper-marina-core.audit-v0.2.json", 12),
    ("data/worlds/night-city-2045/import/kabuki-core.audit-v0.2.json", 7),
    ("data/worlds/night-city-2045/import/north-heywood-core.audit-v0.2.json", 7),
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

# First source-reviewed batch: Downtown core.
downtown_source = load_json(ROOT / "data/worlds/night-city-2045/downtown-core.v1.json")
validate_document(downtown_source)
downtown_a = realize_document(downtown_source, engine)
downtown_b = realize_document(downtown_source, engine)
assert downtown_a == downtown_b, "Downtown fixture realization must be deterministic"
entities = {row["name"]: row for row in downtown_a["entities"]}
assert len(entities) == 11
assert sum(bool(row.get("assortment")) for row in entities.values()) == 2

# Bella Vista is a container. Digg's is the only permanent catalogue-backed regular stall in
# this first source-reviewed slice; the other named regular businesses stay local/service.
assert entities["Bella Vista Market"]["entity_type"] == "container"
assert entities["Digg’s"]["assortment"]
assert "assortment" not in entities["Refrosh Wash"]
assert "assortment" not in entities["Rainbow Art Supply"]
assert "assortment" not in entities["Fade Forever"]
assert entities["Bella Vista Night Market"]["entity_type"] == "event_market"

# Oasis is a child of Continental Brands Office and is stock-backed, but its source-reviewed
# departments are narrower than the first audit guess.
oasis = entities["Oasis Megamart"]
assert oasis["parent_entity_id"] == "NC2045-LOC-DOWNTOWN-082-CONTINENTAL-BRANDS-OFFICE"
assert oasis["assortment"]
for row in oasis["assortment"]:
    profile = engine.commercial_by_id[row["item_id"]]
    departments = {profile["department"], *profile.get("secondary_departments", [])}
    assert departments & {"food-consumables", "general-equipment"}
    price = engine._base_price(engine.items_by_id[row["item_id"]])
    assert price is None or price <= 100

# Source review corrected two important over-generations and the affected map numbers.
assert "assortment" not in entities["Europa Meatworks"]
assert "assortment" not in entities["Moleharty’s Books & Antiques"]
assert entities["Moleharty’s Books & Antiques"]["map_no"] == 16
assert entities["Munch Munch Munch"]["map_no"] == 17
assert {row["service_key"] for row in entities["Munch Munch Munch"]["services"]} >= {
    "annual-membership", "cube-room"
}

# Second source-reviewed batch: the three Little Europe core profiles not already resolved by
# Kaito Market. The market-like Vertical Neighborhood is corrected to context/container state;
# Everything and More stocks as a bodega; T&C combines stock, bespoke services and event stalls.
little_source = load_json(ROOT / "data/worlds/night-city-2045/little-europe-remainder.v1.json")
validate_document(little_source)
little_a = realize_document(little_source, engine)
little_b = realize_document(little_source, engine)
assert little_a == little_b, "Little Europe remainder must be deterministic"
little = {row["name"]: row for row in little_a["entities"]}
assert len(little) == 5
assert little["Continental Brands Vertical Neighborhood"]["entity_type"] == "container"
assert "assortment" not in little["Continental Brands Vertical Neighborhood"]
assert little["Fast Eddie"]["services"][0]["price_eb"] == 10
assert little["Everything and More"]["assortment"]
assert little["Torrell and Chiang’s"]["assortment"]
assert {row["service_key"] for row in little["Torrell and Chiang’s"]["services"]} >= {
    "bespoke-tailoring", "discreet-armor-tailoring", "specialist-dry-cleaning"
}
assert little["Torrell and Chiang’s Market Stalls"]["entity_type"] == "event_market"

# Third source-reviewed batch: all twelve Upper Marina CORE_RETAIL audit profiles. Source
# review also retains several named child businesses omitted from the original core extraction.
upper_source = load_json(ROOT / "data/worlds/night-city-2045/upper-marina-core.v1.json")
validate_document(upper_source)
upper_a = realize_document(upper_source, engine)
upper_b = realize_document(upper_source, engine)
assert upper_a == upper_b, "Upper Marina fixture realization must be deterministic"
upper = {row["name"]: row for row in upper_a["entities"]}
assert len(upper) == 17
expected_stock_names = {
    "Combat Concierge", "Corporate Cool", "Cybershack", "Skinlight", "Tech Time",
    "Midnight Arms Regional Office",
}
actual_stock_names = {name for name, row in upper.items() if row.get("assortment")}
assert actual_stock_names == expected_stock_names, (actual_stock_names, expected_stock_names)

# Containers never duplicate child inventory.
for name in ["Bay Bridge Residences", "Brownstone Waterfront", "Crystal Park Market", "Ziggurat Headquarters"]:
    assert upper[name]["entity_type"] == "container"
    assert "assortment" not in upper[name]

# Combat Concierge is the source-defined bodega/arms hybrid: goods stay inside the three named
# shelf departments, while armor repair and armed escort are services rather than fake stock.
combat = upper["Combat Concierge"]
assert combat["assortment"]
assert {row["service_key"] for row in combat["services"]} == {"armor-repair", "armed-escort"}
for row in combat["assortment"]:
    profile = engine.commercial_by_id[row["item_id"]]
    departments = {profile["department"], *profile.get("secondary_departments", [])}
    assert departments & {"food-consumables", "weapons", "ammunition-ordnance"}

# Corporate Cool was over-broad in the audit: source review supports workwear/uniforms, not
# armor stock. Every persistent line must therefore resolve through fashion-personal.
corporate = upper["Corporate Cool"]
assert corporate["assortment"]
for row in corporate["assortment"]:
    profile = engine.commercial_by_id[row["item_id"]]
    departments = {profile["department"], *profile.get("secondary_departments", [])}
    assert "fashion-personal" in departments
    assert profile["department"] != "armor-protection"

# Crystal Park children keep their individual commercial roles rather than flattening into one
# market inventory. Cybershack is only programs/hardware; Skinlight only Fashionware. Tech Time
# uses a tiny exact catalogue allowlist for actual tool items and keeps scrap world-local.
cybershack = upper["Cybershack"]
assert cybershack["assortment"]
for row in cybershack["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[:2] == ["NET & Netrunning", "Cyberdeck Hardware"] or path[:2] == ["NET & Netrunning", "Programs"]

skinlight = upper["Skinlight"]
assert skinlight["assortment"]
for row in skinlight["assortment"]:
    assert engine.commercial_by_id[row["item_id"]]["classification_path"][:2] == ["Cyberware", "Fashionware"]

tech_time = upper["Tech Time"]
assert {row["item_id"] for row in tech_time["assortment"]} == {"VENDR-0431", "VENDR-0432", "VENDR-0433"}
assert tech_time["local_offerings"][0]["offering_key"] == "technical-scrap"

assert "assortment" not in upper["Maxwell’s"]
assert upper["Maxwell’s"]["services"][0]["service_key"] == "shoe-repair"
assert "assortment" not in upper["Torch’s Total Repairs"]
assert upper["Torch’s Total Repairs"]["services"][0]["service_key"] == "tech-repair-dropoff"
assert "assortment" not in upper["Other Lives"]
assert "assortment" not in upper["Pizza to Go"]

# Metal Heaven is deliberately world-local until the catalogue can represent recordings and
# instruments without substituting unrelated entertainment/electronics. Midnight Arms remains
# catalogue-backed, but only for firearms and with a strong manufacturer preference.
metal = upper["Metal Heaven"]
assert "assortment" not in metal
assert {row["offering_key"] for row in metal["local_offerings"]} == {
    "music-tracks-bootlegs", "instrument-parts"
}

midnight = upper["Midnight Arms Regional Office"]
assert midnight["assortment"]
assert midnight["shop"]["stocking_profile"]["brand_affinities"]["Midnight Arms"] == 20
for row in midnight["assortment"]:
    profile = engine.commercial_by_id[row["item_id"]]
    departments = {profile["department"], *profile.get("secondary_departments", [])}
    assert "weapons" in departments

# Ziggurat's public museum/tours are representable, but the HQ is not promoted to a shop.
ziggurat = upper["Ziggurat Headquarters"]
assert ziggurat["stock_policy"] == "NO_STOCK"
assert {row["service_key"] for row in ziggurat["services"]} == {
    "ihara-grubb-net-museum", "headquarters-tour"
}

# Fourth source-constrained district batch: Kabuki. The market is a container, storage and
# hospitality remain non-stock services, and only three entities receive persistent catalogue
# assortments. Narrow hard gates prevent audit category spillover from becoming world state.
kabuki_source = load_json(ROOT / "data/worlds/night-city-2045/kabuki-core.v1.json")
validate_document(kabuki_source)
kabuki_a = realize_document(kabuki_source, engine)
kabuki_b = realize_document(kabuki_source, engine)
assert kabuki_a == kabuki_b, "Kabuki fixture realization must be deterministic"
kabuki = {row["name"]: row for row in kabuki_a["entities"]}
assert len(kabuki) == 8
assert {name for name, row in kabuki.items() if row.get("assortment")} == {
    "Murakami Suiun Imports", "Oasis (Kabuki)", "Sanroo Neuro-land"
}
assert kabuki["Kabuki Market"]["entity_type"] == "container"
assert kabuki["Kabuki Market"]["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in kabuki["Kabuki Market"]
assert "assortment" not in kabuki["Animelocaris"]
assert kabuki["Animelocaris"]["local_offerings"]
assert "assortment" not in kabuki["Nakagawa Garage Tower"]
assert {row["service_key"] for row in kabuki["Nakagawa Garage Tower"]["services"]} == {
    "secure-vehicle-storage", "secure-av-storage"
}
assert "assortment" not in kabuki["Yum Seng"]
assert kabuki["Yum Seng"]["local_offerings"][0]["offering_key"] == "seafood"
assert "karaoke-box" in {row["service_key"] for row in kabuki["Yum Seng"]["services"]}
assert kabuki["Murakami Suiun Vehicle Night Market"]["entity_type"] == "event_market"
assert kabuki["Murakami Suiun Vehicle Night Market"]["parent_entity_id"] == "NC2045-LOC-KABUKI-204-MURAKAMI-SUIUN-IMPORTS"

murakami = kabuki["Murakami Suiun Imports"]
assert murakami["assortment"]
for row in murakami["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] in {"Electronics & Communications", "Vehicles & Mobility", "General Equipment"}

kabuki_oasis = kabuki["Oasis (Kabuki)"]
assert kabuki_oasis["assortment"]
for row in kabuki_oasis["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] in {"Food, Drink & Consumables", "General Equipment"}

sanroo = kabuki["Sanroo Neuro-land"]
sanroo_allowlist = set(sanroo["shop"]["stocking_profile"]["allowed_item_ids"])
assert sanroo["assortment"]
assert {row["item_id"] for row in sanroo["assortment"]} <= sanroo_allowlist
for row in sanroo["assortment"]:
    profile = engine.commercial_by_id[row["item_id"]]
    departments = {profile["department"], *profile.get("secondary_departments", [])}
    assert departments & {"weapons", "ammunition-ordnance", "weapon-parts"}

# Fifth source-constrained district batch: North Heywood. Woodland Park delegates to its child
# businesses, Nana Meow stays world-local, and the generated shops are deliberately narrower
# than the first audit's broad department guesses.
north_source = load_json(ROOT / "data/worlds/night-city-2045/north-heywood-core.v1.json")
validate_document(north_source)
north_a = realize_document(north_source, engine)
north_b = realize_document(north_source, engine)
assert north_a == north_b, "North Heywood fixture realization must be deterministic"
north = {row["name"]: row for row in north_a["entities"]}
assert len(north) == 7
assert {name for name, row in north.items() if row.get("assortment")} == {
    "Byte & Switch", "Sleepeasy Home Solutions", "Truvy’s Salon", "Breeze", "Burning Bright Bodega"
}
assert north["Woodland Park"]["entity_type"] == "container"
assert north["Woodland Park"]["stock_policy"] == "CHILDREN_ONLY"
assert "assortment" not in north["Woodland Park"]
assert "assortment" not in north["Nana Meow’s Nursery"]
assert {row["offering_key"] for row in north["Nana Meow’s Nursery"]["local_offerings"]} == {
    "gardening-gear-supplies", "seeds"
}

byte_switch = north["Byte & Switch"]
assert byte_switch["assortment"]
assert byte_switch["local_offerings"][0]["offering_key"] == "questionable-cyberware-parts"
for row in byte_switch["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[0] in {"Electronics & Communications", "General Equipment"}
    assert path[:2] != ["Electronics & Communications", "Software & Apps"]

sleepeasy = north["Sleepeasy Home Solutions"]
assert sleepeasy["assortment"]
for row in sleepeasy["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[:2] in (["Housing & Property", "Furniture"], ["Housing & Property", "Home Accessories"])

truvy = north["Truvy’s Salon"]
assert truvy["assortment"]
for row in truvy["assortment"]:
    assert engine.commercial_by_id[row["item_id"]]["classification_path"][:2] == ["Cyberware", "Fashionware"]
assert "fashionware-installation" in {row["service_key"] for row in truvy["services"]}

breeze = north["Breeze"]
assert breeze["assortment"]
for row in breeze["assortment"]:
    assert engine.commercial_by_id[row["item_id"]]["classification_path"][:2] == ["Medical & Chemical", "Street Drugs"]

burning = north["Burning Bright Bodega"]
assert burning["assortment"]
for row in burning["assortment"]:
    path = engine.commercial_by_id[row["item_id"]]["classification_path"]
    assert path[:2] == ["Food, Drink & Consumables", "Foodstuffs"] or path[0] == "General Equipment"

print(
    "OK: generic world fixtures; "
    f"Kaito entities={len(kaito_a['entities'])}, Downtown entities={len(entities)}, "
    f"Little Europe remainder={len(little)}, Upper Marina entities={len(upper)}, "
    f"Kabuki entities={len(kabuki)}, North Heywood entities={len(north)}"
)
