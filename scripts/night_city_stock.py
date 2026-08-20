#!/usr/bin/env python3
"""Bridge Night City 2045 Vend-R stock profiles into Catalogger's lifecycle engine.

This module deliberately does not duplicate Catalogger's scoring/restock mechanics.
It translates a canonical Night City stock-profile row into the realized shop context
expected by StockLifecycleEngine, and handles location modes that should not own stock.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any


STOCK_OWNING_MODES = {"DIRECT_SELLER", "HYBRID_DIRECT_EVENT"}
EVENT_MODES = {"EVENT_MARKET"}
TEMPLATE_MODES = {"CHAIN_TEMPLATE"}
DELEGATING_MODES = {"AGGREGATE_CONTAINER"}
NO_STOCK_MODES = {
    "SERVICE_ONLY",
    "REFERENCE_ONLY",
    "CHANNEL_TEMPLATE",
    "DISTRIBUTION_CHANNEL",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def split_pipe(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split("|") if part.strip()]


def optional_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("eb", "").strip())


def load_profiles(path: Path) -> list[dict[str, Any]]:
    doc = load_json(path)
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict) and isinstance(doc.get("profiles"), list):
        return doc["profiles"]
    raise ValueError("Night City profile file must be a JSON list or {'profiles': [...]} object")


def profile_lookup(profiles: list[dict[str, Any]], selector: str) -> dict[str, Any]:
    exact_id = [row for row in profiles if row.get("entity_id") == selector]
    if len(exact_id) == 1:
        return exact_id[0]
    folded = selector.casefold()
    by_name = [row for row in profiles if str(row.get("name", "")).casefold() == folded]
    if len(by_name) == 1:
        return by_name[0]
    if not exact_id and not by_name:
        raise KeyError(f"no Night City stock profile matches {selector!r}")
    raise KeyError(f"ambiguous Night City stock profile selector {selector!r}")


def manufacturer_index(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {str(row["name"]).casefold(): str(row["id"]) for row in rows}


def resolve_manufacturer_ids(profile: dict[str, Any], manufacturers: dict[str, str]) -> list[str]:
    result: list[str] = []
    for name in split_pipe(profile.get("manufacturer_affinity")):
        mfr_id = manufacturers.get(name.casefold())
        if mfr_id is None:
            raise ValueError(
                f"unknown manufacturer affinity {name!r} for {profile.get('entity_id')}; "
                "add/normalize the manufacturer before generating stock"
            )
        result.append(mfr_id)
    return result


def plan_profile(profile: dict[str, Any]) -> dict[str, Any]:
    mode = str(profile.get("stock_mode") or "").strip().upper()
    base = {
        "entity_id": profile.get("entity_id"),
        "name": profile.get("name"),
        "stock_mode": mode,
        "parent_stock_policy": profile.get("parent_stock_policy") or "",
    }
    if mode in STOCK_OWNING_MODES:
        return {**base, "action": "generate_persistent_stock", "owns_stock": True}
    if mode in EVENT_MODES:
        return {**base, "action": "generate_event_stock", "owns_stock": True}
    if mode in TEMPLATE_MODES:
        return {**base, "action": "instantiate_branch_then_generate", "owns_stock": False}
    if mode in DELEGATING_MODES:
        return {**base, "action": "delegate_to_children", "owns_stock": False}
    if mode in NO_STOCK_MODES:
        return {**base, "action": "no_static_inventory", "owns_stock": False}
    raise ValueError(f"unknown stock_mode {mode!r} for {profile.get('entity_id')}")


def channel_override_weights(channels: list[str], base: dict[str, Any]) -> dict[str, float]:
    """Convert the audit's channel allow-list into engine weights.

    Existing archetype weights are retained where available; explicitly requested channels
    absent from the archetype receive a strong neutral weight of 10. Channels not named by
    the Night City profile are removed, because market_channel_override is an explicit override.
    """
    if not channels:
        return copy.deepcopy(base.get("channel_weights", {}))
    existing = base.get("channel_weights", {})
    return {channel: float(existing.get(channel, 10)) for channel in channels}


def context_patch(
    profile: dict[str, Any],
    base_context: dict[str, Any],
    manufacturers: dict[str, str],
    enabled_source_codes: list[str] | None = None,
) -> dict[str, Any]:
    mode = str(profile.get("stock_mode") or "").strip().upper()
    patch: dict[str, Any] = {
        "vendr_entity_id": profile.get("entity_id"),
        "vendr_name": profile.get("name"),
        "vendr_district": profile.get("district"),
        "vendr_book_page": profile.get("book_page"),
        "vendr_source_ref": profile.get("source_ref"),
        "vendr_stock_mode": mode,
        "vendr_parent_stock_policy": profile.get("parent_stock_policy"),
        "vendr_profile_confidence": profile.get("assignment_confidence"),
        "vendr_profile_note": profile.get("modelling_note"),
    }

    for source_key, target_key in (
        ("primary_departments", "primary_departments"),
        ("secondary_departments", "secondary_departments"),
        ("exclude_departments", "exclude_departments"),
    ):
        values = split_pipe(profile.get(source_key))
        if values:
            patch[target_key] = values

    for key in ("breadth_profile", "depth_profile", "supply_capability", "price_tier_center", "pricing_style"):
        value = profile.get(key)
        if value not in (None, ""):
            patch[key] = value

    channels = split_pipe(profile.get("market_channel_override"))
    if channels:
        patch["channel_weights"] = channel_override_weights(channels, base_context)

    brand_ids = resolve_manufacturer_ids(profile, manufacturers)
    if brand_ids:
        brand_cap = float(base_context.get("brand_score_cap", 20))
        patch["brand_affinities"] = {mfr_id: brand_cap for mfr_id in brand_ids}
        patch["minimum_manufacturer_share"] = 0.40

    max_price = optional_number(profile.get("max_base_price_eb"))
    if max_price is not None:
        patch["max_base_price_eb"] = max_price
    min_tier = profile.get("min_price_tier")
    if min_tier not in (None, ""):
        patch["min_price_tier"] = str(min_tier)

    if enabled_source_codes is not None:
        patch["enabled_source_codes"] = sorted(set(enabled_source_codes))

    return patch


def install_night_city_constraints(engine: Any) -> Any:
    """Install Night City profile gates on one lifecycle-engine instance.

    Catalogger's core engine remains untouched. These are realized-shop constraints
    carried by the Night City commercial profiles, so the bridge enforces them at the
    integration seam: excluded departments, hard price bounds, and a minimum share for
    positively-affiliated manufacturers.
    """
    if getattr(engine, "_night_city_constraints_installed", False):
        return engine

    base_eligible = engine.eligible
    base_build_assortment = engine.build_assortment

    def eligible(item_id: str, context: dict[str, Any], special: bool = False) -> bool:
        if not base_eligible(item_id, context, special=special):
            return False
        item = engine.items_by_id[item_id]
        profile = engine.commercial_by_id[item_id]
        item_departments = engine._item_departments(profile)

        excluded = set(context.get("exclude_departments", []))
        if excluded and item_departments & excluded:
            return False

        max_price = optional_number(context.get("max_base_price_eb"))
        if max_price is not None:
            base_price = engine._base_price(item)
            if base_price is not None and base_price > max_price:
                return False

        min_tier = context.get("min_price_tier")
        if min_tier:
            order = engine.model["price_score"]["tier_order"]
            if min_tier not in order:
                raise ValueError(f"unknown minimum price tier: {min_tier}")
            item_tier = engine._price_tier(item)
            if item_tier in order and order.index(item_tier) < order.index(min_tier):
                return False
        return True

    def build_assortment(context: dict[str, Any]) -> list[dict[str, Any]]:
        assortment = base_build_assortment(context)
        share = max(0.0, min(1.0, float(context.get("minimum_manufacturer_share", 0.0))))
        brand_ids = {
            mfr_id
            for mfr_id, weight in context.get("brand_affinities", {}).items()
            if float(weight) > 0
        }
        if not assortment or not brand_ids or share <= 0:
            return assortment

        selected = {row["item_id"] for row in assortment}
        branded_count = sum(
            bool(set(engine.manufacturers_by_item.get(row["item_id"], [])) & brand_ids)
            for row in assortment
        )
        candidates = [
            row for row in engine.candidate_scores(context, special=False)
            if row["item_id"] not in selected
            and set(engine.manufacturers_by_item.get(row["item_id"], [])) & brand_ids
        ]
        candidates.sort(key=lambda row: (-float(row["score"]), row["item_id"]))
        total_available_brand = branded_count + len(candidates)
        target = min(int(math.ceil(len(assortment) * share)), total_available_brand)
        needed = max(0, target - branded_count)
        if needed == 0:
            return assortment

        role_rank = {"occasional": 0, "regular": 1, "core": 2}
        replaceable = [
            row for row in assortment
            if not (set(engine.manufacturers_by_item.get(row["item_id"], [])) & brand_ids)
        ]
        replaceable.sort(
            key=lambda row: (
                role_rank.get(row.get("role", "regular"), 1),
                float(row.get("affinity_score", 0)),
                row["item_id"],
            )
        )

        reorder_fraction = getattr(engine, "lifecycle", {}).get("reorder_fraction_by_role", {})
        for line, candidate in zip(replaceable[:needed], candidates[:needed]):
            scored = engine.score(candidate["item_id"], context)
            line["item_id"] = candidate["item_id"]
            line["affinity_score"] = scored["score"]
            if "score_components" in line:
                line["score_components"] = scored["components"]
            if hasattr(engine, "_target_quantity") and "target_quantity" in line:
                target_qty = engine._target_quantity(context, candidate["item_id"], line["role"])
                line["target_quantity"] = target_qty
                fraction = float(reorder_fraction.get(line["role"], 0.35))
                line["reorder_point"] = (
                    None if target_qty is None else max(1, int(round(target_qty * fraction)))
                )
        return assortment

    engine.eligible = eligible
    engine.build_assortment = build_assortment
    engine._night_city_constraints_installed = True
    return engine


class NightCityStockBridge:
    def __init__(
        self,
        engine: Any,
        profiles: list[dict[str, Any]],
        manufacturer_rows: list[dict[str, Any]],
    ) -> None:
        self.engine = engine
        self.profiles = profiles
        self.manufacturers = manufacturer_index(manufacturer_rows)

    def get(self, selector: str) -> dict[str, Any]:
        return profile_lookup(self.profiles, selector)

    def plan(self, selector: str) -> dict[str, Any]:
        return plan_profile(self.get(selector))

    def make_context(
        self,
        selector: str,
        seed: str,
        shop_id: str | None = None,
        event_id: str | None = None,
        enabled_source_codes: list[str] | None = None,
        extra_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = self.get(selector)
        plan = plan_profile(profile)
        mode = plan["stock_mode"]
        if mode in DELEGATING_MODES | NO_STOCK_MODES:
            raise ValueError(f"{profile.get('name')} does not own static stock ({plan['action']})")
        if mode in TEMPLATE_MODES and not shop_id:
            raise ValueError(
                f"{profile.get('name')} is a chain template; provide --shop-id for a realized branch"
            )
        if mode in EVENT_MODES and not event_id:
            raise ValueError(f"{profile.get('name')} is an event market; provide --event-id")

        archetype = str(profile.get("primary_archetype") or "").strip()
        if not archetype:
            raise ValueError(f"stock-owning profile {profile.get('entity_id')} has no primary_archetype")

        actual_shop_id = shop_id or str(profile["entity_id"])
        actual_seed = str(seed)
        if mode in EVENT_MODES:
            actual_shop_id = shop_id or f"{profile['entity_id']}@{event_id}"
            actual_seed = f"{seed}:event:{event_id}"

        base = self.engine.make_context(archetype, actual_seed, actual_shop_id)
        base["brand_score_cap"] = float(self.engine.model.get("brand_score_cap", 20))
        patch = context_patch(profile, base, self.manufacturers, enabled_source_codes)
        patch["vendr_event_id"] = event_id
        patch["vendr_lifecycle"] = "event" if mode in EVENT_MODES else "persistent"
        if mode in TEMPLATE_MODES:
            patch["vendr_template_entity_id"] = profile.get("entity_id")
            patch["vendr_stock_mode"] = "CHAIN_BRANCH_INSTANCE"
        if extra_overrides:
            self.engine._deep_update(patch, extra_overrides)
        return self.engine.make_context(archetype, actual_seed, actual_shop_id, patch)

    def generate(self, selector: str, **kwargs: Any) -> dict[str, Any]:
        context = self.make_context(selector, **kwargs)
        bundle = self.engine.generate(context)
        bundle.setdefault("metadata", {})["night_city_profile_entity_id"] = context["vendr_entity_id"]
        bundle["metadata"]["night_city_stock_mode"] = context["vendr_stock_mode"]
        return bundle

    def restock(self, bundle: dict[str, Any]) -> dict[str, Any]:
        mode = bundle.get("shop", {}).get("vendr_stock_mode")
        lifecycle = bundle.get("shop", {}).get("vendr_lifecycle")
        if lifecycle == "event" or mode == "EVENT_MARKET":
            raise ValueError("event-market bundles do not restock; generate a new event with a new event_id")
        return self.engine.restock(bundle)


def load_runtime(profiles_path: Path) -> NightCityStockBridge:
    from stock_lifecycle import ROOT, StockLifecycleEngine  # type: ignore

    engine = install_night_city_constraints(StockLifecycleEngine())
    manufacturers = load_json(ROOT / "data/catalog/manufacturers.json")
    return NightCityStockBridge(engine, load_profiles(profiles_path), manufacturers)


def parse_sources(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Night City 2045 -> Vend-R stock lifecycle bridge")
    parser.add_argument("--profiles", required=True, help="Night City stock-profile JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="show whether/how a canonical entity owns stock")
    plan.add_argument("--entity", required=True, help="entity_id or exact canonical name")

    generate = sub.add_parser("generate", help="generate a durable shop/event bundle")
    generate.add_argument("--entity", required=True)
    generate.add_argument("--seed", required=True)
    generate.add_argument("--shop-id", help="campaign-specific shop/branch ID; required for CHAIN_TEMPLATE")
    generate.add_argument("--event-id", help="required for EVENT_MARKET")
    generate.add_argument("--sources", help="comma-separated enabled Catalogger source codes")
    generate.add_argument("--context-overrides", help="optional JSON object merged last")
    generate.add_argument("--output", required=True)

    restock = sub.add_parser("restock", help="advance a persistent canonical shop by one stock cycle")
    restock.add_argument("--input", required=True)
    restock.add_argument("--output", required=True)

    inspect = sub.add_parser("inspect", help="render Catalogger's developer stock report")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--output")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bridge = load_runtime(Path(args.profiles))
    if args.command == "plan":
        print(json.dumps(bridge.plan(args.entity), ensure_ascii=False, indent=2))
        return
    if args.command == "generate":
        extra = load_json(Path(args.context_overrides)) if args.context_overrides else None
        bundle = bridge.generate(
            args.entity,
            seed=args.seed,
            shop_id=args.shop_id,
            event_id=args.event_id,
            enabled_source_codes=parse_sources(args.sources),
            extra_overrides=extra,
        )
        Path(args.output).write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(bridge.engine.summarize(bundle), ensure_ascii=False, indent=2))
        return
    if args.command == "restock":
        bundle = load_json(Path(args.input))
        result = bridge.restock(bundle)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(bridge.engine.summarize(result), ensure_ascii=False, indent=2))
        return
    if args.command == "inspect":
        bundle = load_json(Path(args.input))
        report = bridge.engine.inspection_markdown(bundle)
        if args.output:
            Path(args.output).write_text(report, encoding="utf-8")
            print(args.output)
        else:
            print(report)
        return


if __name__ == "__main__":
    main()
