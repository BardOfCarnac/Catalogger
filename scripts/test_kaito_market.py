#!/usr/bin/env python3
"""End-to-end assertions for the first Night City 2045 persistent market fixture."""
from build_kaito_market import realize_market
from world_stock_engine import WorldStockEngine


engine = WorldStockEngine()
market_a = realize_market(engine)
market_b = realize_market(engine)
assert market_a == market_b, "Kaito Market realization must be deterministic"

assert market_a["location"]["entity_id"] == "NC2045-LOC-LITTLE-EUROPE-060-KAITO-MARKET"
assert market_a["location"]["stock_policy"] == "CHILDREN_ONLY"
assert "stock" not in market_a["location"], "container location must not duplicate child inventory"

expected_names = {
    "Apocalypse Zone Tattoo",
    "App Shack",
    "Cheek Turn",
    "Fifty Farms",
    "Greg’s",
    "Imported Goods 4 Cheap",
    "Madame Zorina",
    "Sagar Hair Saloon",
    "Stone Mill",
    "Taco Taco",
}
vendors = {row["name"]: row for row in market_a["vendors"]}
assert set(vendors) == expected_names, (set(vendors), expected_names)
assert len(vendors) == 10

# Apocalypse Zone Tattoo: only the catalogue's Light Tattoo plus traditional tattoo service.
apocalypse = vendors["Apocalypse Zone Tattoo"]
assert {row["item_id"] for row in apocalypse["assortment"]} == {"VENDR-0708"}
assert {row["service_key"] for row in apocalypse["services"]} == {"traditional-tattoo"}

# App Shack: cheap general software only, never NET/Netrunning stock or expensive databases.
app_shack = vendors["App Shack"]
assert app_shack["assortment"], "App Shack should have a persistent software assortment"
for row in app_shack["assortment"]:
    iid = row["item_id"]
    path = engine.commercial_by_id[iid]["classification_path"]
    assert path[:2] == ["Electronics & Communications", "Software & Apps"], (iid, path)
    price = engine._base_price(engine.items_by_id[iid])
    assert price is None or price <= 100, (iid, price)
    assert engine.commercial_by_id[iid]["department"] != "netrunning"

# Cheek Turn: sidearms + ammunition, with an explicit light-armour exception list because
# the current catalogue taxonomy groups all armor into a single classification path.
cheek_turn = vendors["Cheek Turn"]
assert cheek_turn["assortment"], "Cheek Turn should have a persistent assortment"
light_armor_ids = {"VENDR-0329", "VENDR-0331", "VENDR-0332", "VENDR-0333"}
allowed_prefixes = [
    ["Weapons", "Firearms", "Medium Pistols"],
    ["Weapons", "Firearms", "Heavy Pistols"],
    ["Weapons", "Firearms", "Very Heavy Pistols"],
    ["Ammunition & Ordnance", "Ammunition"],
]
for row in cheek_turn["assortment"]:
    iid = row["item_id"]
    if iid in light_armor_ids:
        continue
    path = engine.commercial_by_id[iid]["classification_path"]
    assert any(path[: len(prefix)] == prefix for prefix in allowed_prefixes), (iid, path)

# The source-specific everyday traders must remain local offerings/services instead of being
# falsely substituted with unrelated canonical catalogue products.
for name in ["Fifty Farms", "Greg’s", "Madame Zorina", "Sagar Hair Saloon", "Stone Mill", "Taco Taco"]:
    assert "assortment" not in vendors[name], f"{name} should not receive synthetic catalogue stock"

assert vendors["Fifty Farms"]["local_offerings"][0]["offering_key"] == "fresh-produce"
assert {row["service_key"] for row in vendors["Madame Zorina"]["services"]} == {
    "fortune-telling", "message-post"
}
assert {row["price_eb"] for row in vendors["Taco Taco"]["local_offerings"]} == {5}

# Imported Goods remains the intentionally messy second-hand catalogue test case.
imported = vendors["Imported Goods 4 Cheap"]
assert imported["assortment"]
assert imported["shop"]["stocking_profile"]["pricing_style"] == "bargain"
assert imported["shop"]["stocking_profile"]["supply_capability"] == "irregular"

print(
    "OK: Kaito Market has 10 named vendors; "
    f"catalog-stock vendors={sum('assortment' in row for row in market_a['vendors'])}; "
    f"Cheek Turn lines={len(cheek_turn['assortment'])}; App Shack lines={len(app_shack['assortment'])}"
)
