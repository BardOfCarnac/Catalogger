#!/usr/bin/env python3
"""Unit tests for Night City stock-profile translation, independent of the full catalogue build."""
from copy import deepcopy

from night_city_stock import NightCityStockBridge, context_patch, plan_profile


MANUFACTURERS = [
    {"id": "MFR-0057", "name": "Midnight Arms"},
    {"id": "MFR-0032", "name": "Gibson Battlegear"},
]

DIRECT = {
    "entity_id": "NC2045-LOC-UPPER-MARINA-074-MIDNIGHT-ARMS-REGIONAL-OFFICE",
    "name": "Midnight Arms Regional Office",
    "district": "Upper Marina",
    "book_page": 74,
    "source_ref": "Night City 2045 p. 74",
    "stock_mode": "DIRECT_SELLER",
    "primary_archetype": "weapons-dealer",
    "primary_departments": "weapons|ammunition-ordnance|weapon-parts",
    "secondary_departments": "armor-protection",
    "manufacturer_affinity": "Midnight Arms",
    "exclude_departments": "cyberware|medical-chemical",
    "market_channel_override": "corporate|specialist|retail",
    "breadth_profile": "medium",
    "depth_profile": "normal",
    "supply_capability": "corporate",
    "price_tier_center": "Expensive",
    "pricing_style": "fair",
    "max_base_price_eb": "",
    "min_price_tier": "",
    "parent_stock_policy": "OWN_STOCK",
    "assignment_confidence": "HIGH",
    "modelling_note": "Manufacturer-backed firearms showroom.",
}

EVENT = {
    "entity_id": "NC2045-OUT-RANCHO-CORONADO-290-RC-NIGHT-MARKET",
    "name": "RC Night Market",
    "district": "Rancho Coronado",
    "book_page": 290,
    "source_ref": "Night City 2045 p. 290",
    "stock_mode": "EVENT_MARKET",
    "primary_archetype": "night-market-stall",
    "market_channel_override": "street|grey_market|black_market",
    "breadth_profile": "small",
    "depth_profile": "shallow",
    "supply_capability": "irregular",
    "price_tier_center": "Expensive",
    "pricing_style": "gouging",
    "parent_stock_policy": "EVENT_ONLY",
    "assignment_confidence": "HIGH",
}

CONTAINER = {
    "entity_id": "NC2045-LOC-LITTLE-EUROPE-060-KAITO-MARKET",
    "name": "Kaito Market",
    "stock_mode": "AGGREGATE_CONTAINER",
    "parent_stock_policy": "CHILDREN_ONLY",
}

TEMPLATE = {
    "entity_id": "NC2045-IMP-HUNDRED-UNDER-HAVEN",
    "name": "Hundred Under Haven district branches",
    "stock_mode": "CHAIN_TEMPLATE",
    "primary_archetype": "general-store",
    "primary_departments": "general-equipment|food-consumables",
    "secondary_departments": "electronics-comms|fashion-personal",
    "breadth_profile": "broad",
    "depth_profile": "shallow",
    "supply_capability": "ordinary",
    "price_tier_center": "Everyday",
    "pricing_style": "bargain",
    "max_base_price_eb": 100,
    "parent_stock_policy": "OWN_STOCK",
}


class FakeEngine:
    def __init__(self):
        self.model = {"brand_score_cap": 20}
        self.generated = []

    @staticmethod
    def _deep_update(target, patch):
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                FakeEngine._deep_update(target[key], value)
            else:
                target[key] = deepcopy(value)

    def make_context(self, archetype, seed, shop_id=None, overrides=None):
        context = {
            "id": shop_id or f"fake:{archetype}:{seed}",
            "seed": seed,
            "archetype_id": archetype,
            "primary_departments": ["weapons"],
            "secondary_departments": ["armor-protection"],
            "channel_weights": {"specialist": 15, "retail": 12, "street": 6},
            "breadth_profile": "medium",
            "depth_profile": "normal",
            "supply_capability": "specialist",
            "price_tier_center": "Expensive",
            "pricing_style": "fair",
            "brand_affinities": {},
        }
        self._deep_update(context, overrides or {})
        return context

    def generate(self, context):
        bundle = {"shop": deepcopy(context), "assortment": [], "stock": [], "state": {"stock_cycle": 0}, "history": []}
        self.generated.append(bundle)
        return bundle

    def restock(self, bundle):
        result = deepcopy(bundle)
        result["state"]["stock_cycle"] += 1
        return result


assert plan_profile(DIRECT)["action"] == "generate_persistent_stock"
assert plan_profile(EVENT)["action"] == "generate_event_stock"
assert plan_profile(CONTAINER)["action"] == "delegate_to_children"
assert plan_profile(TEMPLATE)["action"] == "instantiate_branch_then_generate"

base = FakeEngine().make_context("weapons-dealer", "x", "shop")
base["brand_score_cap"] = 20
patch = context_patch(DIRECT, base, {"midnight arms": "MFR-0057"}, ["CP:R"])
assert patch["brand_affinities"] == {"MFR-0057": 20.0}
assert patch["minimum_manufacturer_share"] == 0.40
assert patch["channel_weights"] == {"corporate": 10.0, "specialist": 15.0, "retail": 12.0}
assert patch["enabled_source_codes"] == ["CP:R"]
assert patch["exclude_departments"] == ["cyberware", "medical-chemical"]

engine = FakeEngine()
bridge = NightCityStockBridge(engine, [DIRECT, EVENT, CONTAINER, TEMPLATE], MANUFACTURERS)
context = bridge.make_context(DIRECT["entity_id"], seed="campaign-a")
assert context["id"] == DIRECT["entity_id"]
assert context["vendr_stock_mode"] == "DIRECT_SELLER"
assert context["brand_affinities"]["MFR-0057"] == 20.0

try:
    bridge.make_context(CONTAINER["entity_id"], seed="x")
except ValueError as exc:
    assert "does not own static stock" in str(exc)
else:
    raise AssertionError("aggregate container unexpectedly generated stock")

try:
    bridge.make_context(EVENT["entity_id"], seed="x")
except ValueError as exc:
    assert "event-id" in str(exc)
else:
    raise AssertionError("event market did not require event_id")

event_context = bridge.make_context(EVENT["entity_id"], seed="x", event_id="2045-08-20-evening")
assert event_context["vendr_lifecycle"] == "event"
assert event_context["id"].endswith("@2045-08-20-evening")

try:
    bridge.make_context(TEMPLATE["entity_id"], seed="x")
except ValueError as exc:
    assert "chain template" in str(exc)
else:
    raise AssertionError("chain template generated without a branch ID")

branch = bridge.make_context(TEMPLATE["entity_id"], seed="x", shop_id="campaign-a:HUH:watson")
assert branch["vendr_stock_mode"] == "CHAIN_BRANCH_INSTANCE"
assert branch["max_base_price_eb"] == 100.0

bundle = bridge.generate(DIRECT["entity_id"], seed="campaign-a")
assert bundle["metadata"]["night_city_profile_entity_id"] == DIRECT["entity_id"]
restocked = bridge.restock(bundle)
assert restocked["state"]["stock_cycle"] == 1

event_bundle = bridge.generate(EVENT["entity_id"], seed="campaign-a", event_id="evt-1")
try:
    bridge.restock(event_bundle)
except ValueError as exc:
    assert "do not restock" in str(exc)
else:
    raise AssertionError("event bundle was restocked instead of regenerated")

print("OK: Night City stock-profile bridge translation and lifecycle policy")
