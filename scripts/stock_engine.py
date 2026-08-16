#!/usr/bin/env python3
"""Vend-R persistent assortment and stocking engine.

The engine deliberately separates:
1. eligibility -- could this shop plausibly deal in the item?
2. affinity scoring -- how characteristic is the item for this shop?
3. assortment -- persistent core/regular/occasional product relationships
4. stock -- cycle-specific quantity, condition, asking price and visibility
5. specials -- cycle-specific plausible surprises, including unique items

Scores are ranking signals, never universal item rarity percentages.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import math
import random
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BUILD = ROOT / "build/data/catalog"
PROFILE_PATH = BUILD / "item-commercial-profiles.json"
NAMESPACE = uuid.UUID("f3165aa5-0327-4d33-97b8-a4a70f856e01")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_table(manifest: dict[str, Any], name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for part in manifest["tables"][name]["parts"]:
        with gzip.open(ROOT / part["path"], "rt", encoding="utf-8") as handle:
            rows.extend(json.load(handle))
    return rows


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def weighted_choice(rng: random.Random, rows: list[Any], weights: list[float]) -> Any:
    positive = [max(0.0, float(w)) for w in weights]
    total = sum(positive)
    if not rows:
        raise ValueError("weighted_choice called with no rows")
    if total <= 0:
        return rows[rng.randrange(len(rows))]
    target = rng.random() * total
    running = 0.0
    for row, weight in zip(rows, positive):
        running += weight
        if target <= running:
            return row
    return rows[-1]


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").replace("eb", "").strip())
        except ValueError:
            return None
    return None


class StockEngine:
    def __init__(self) -> None:
        self.manifest = load_json(DATA / "catalog/manifest.json")
        self.model = load_json(DATA / "stocking/model.json")
        self.archetypes_doc = load_json(DATA / "shops/archetypes.json")
        self.stock_profiles_doc = load_json(DATA / "stocking/archetype-profiles.json")
        if not PROFILE_PATH.exists():
            raise FileNotFoundError(
                f"{PROFILE_PATH.relative_to(ROOT)} is missing; run "
                "python scripts/build_commercial_profiles.py first"
            )

        self.items = load_table(self.manifest, "items")
        self.item_manufacturers = load_table(self.manifest, "item-manufacturers")
        self.commercial_profiles = load_json(PROFILE_PATH)

        self.items_by_id = {row["id"]: row for row in self.items}
        self.commercial_by_id = {row["item_id"]: row for row in self.commercial_profiles}
        self.manufacturers_by_item: dict[str, list[str]] = defaultdict(list)
        for row in self.item_manufacturers:
            self.manufacturers_by_item[row["item_id"]].append(row["manufacturer_id"])

        self.archetypes = {row["id"]: row for row in self.archetypes_doc["archetypes"]}
        self.stock_profiles = {
            row["archetype_id"]: row for row in self.stock_profiles_doc["profiles"]
        }
        missing = set(self.archetypes) - set(self.stock_profiles)
        extra = set(self.stock_profiles) - set(self.archetypes)
        if missing or extra:
            raise ValueError(f"stock-profile/archetype mismatch missing={missing} extra={extra}")

    # ------------------------------------------------------------------
    # Shop stocking context
    # ------------------------------------------------------------------
    def make_context(
        self,
        archetype_id: str,
        seed: str,
        shop_id: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a realized stocking context for a shop.

        This is not a shop-identity generator. A real shop service should persist this
        realized context with the shop. The helper exists so the stocking engine can be
        used and tested independently of the separate shop/location generator.
        """
        if archetype_id not in self.archetypes:
            raise KeyError(f"unknown archetype: {archetype_id}")
        archetype = self.archetypes[archetype_id]
        template = copy.deepcopy(self.stock_profiles[archetype_id])
        sid = shop_id or str(uuid.uuid5(NAMESPACE, f"shop:{archetype_id}:{seed}"))
        context = {
            "id": sid,
            "seed": str(seed),
            "archetype_id": archetype_id,
            "primary_departments": list(archetype.get("primary_departments", [])),
            "secondary_departments": list(archetype.get("secondary_departments", [])),
            "breadth_profile": template["breadth_profile"],
            "depth_profile": template["depth_profile"],
            "supply_capability": template["supply_capability"],
            "channel_weights": dict(template.get("channel_weights", {})),
            "identity_weights": dict(template.get("identity_weights", {})),
            "affinity_preferences": copy.deepcopy(template.get("affinity_preferences", {})),
            "price_tier_center": template.get("price_tier_center"),
            "condition_weights": dict(template.get("condition_weights", {})),
            "pricing_style": template.get("pricing_style", "fair"),
            "specials": list(template.get("specials", [0, 2])),
            "preferred_classification_paths": [],
            "brand_affinities": {},
            "refused_manufacturers": [],
            "excluded_item_ids": [],
            "stocking_model_version": self.model["version"],
            "stocking_profile_version": self.stock_profiles_doc["version"],
        }
        self._deep_update(context, overrides or {})
        return context

    @staticmethod
    def _deep_update(target: dict[str, Any], patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                StockEngine._deep_update(target[key], value)
            else:
                target[key] = copy.deepcopy(value)

    # ------------------------------------------------------------------
    # Eligibility and score
    # ------------------------------------------------------------------
    @staticmethod
    def _item_departments(profile: dict[str, Any]) -> set[str]:
        return {profile["department"], *profile.get("secondary_departments", [])}

    def eligible(self, item_id: str, context: dict[str, Any], special: bool = False) -> bool:
        item = self.items_by_id[item_id]
        profile = self.commercial_by_id[item_id]
        if item_id in set(context.get("excluded_item_ids", [])):
            return False

        manufacturers = set(self.manufacturers_by_item.get(item_id, []))
        if manufacturers & set(context.get("refused_manufacturers", [])):
            return False

        allowed_departments = set(context.get("primary_departments", [])) | set(
            context.get("secondary_departments", [])
        )
        if allowed_departments and not (self._item_departments(profile) & allowed_departments):
            return False

        shop_channels = set(context.get("channel_weights", {}))
        item_channels = set(profile.get("market_channels", []))
        if shop_channels and item_channels and not (shop_channels & item_channels):
            return False

        # Unique objects are cycle-specific discoveries, not persistent assortment lines.
        if profile.get("product_identity") == "unique" and not special:
            return False

        # A zero or negative explicit identity appetite is not a hard exclusion; only a
        # deliberately extreme refusal is. This keeps specialists capable of surprises.
        if context.get("identity_weights", {}).get(profile.get("product_identity"), 0) <= -100:
            return False

        # Keep non-stockable catalogue placeholders out if they have no usable item ID/name.
        return bool(item.get("id") and item.get("name"))

    @staticmethod
    def _common_prefix(a: list[str], b: list[str]) -> int:
        count = 0
        for left, right in zip(a, b):
            if left != right:
                break
            count += 1
        return count

    def _speciality_score(self, profile: dict[str, Any], context: dict[str, Any]) -> float:
        candidate = list(profile.get("classification_path", []))
        best = 0.0
        depth_scores = self.model["speciality_depth_scores"]
        for preferred in context.get("preferred_classification_paths", []):
            path = preferred.get("path", []) if isinstance(preferred, dict) else preferred
            multiplier = float(preferred.get("weight", 1.0)) if isinstance(preferred, dict) else 1.0
            common = self._common_prefix(candidate, list(path))
            score = sum(depth_scores[:common]) * multiplier
            best = max(best, score)
        return best

    def _price_tier(self, item: dict[str, Any]) -> str | None:
        raw = item.get("price_tier") or item.get("cost_tier") or item.get("price_category")
        if raw is None:
            return None
        text = str(raw).strip().lower()
        for tier in self.model["price_score"]["tier_order"]:
            if text == tier.lower():
                return tier
        return None

    def score(self, item_id: str, context: dict[str, Any]) -> dict[str, Any]:
        item = self.items_by_id[item_id]
        profile = self.commercial_by_id[item_id]
        components: dict[str, float] = {"base": float(self.model["base_score"])}

        item_departments = self._item_departments(profile)
        primary = set(context.get("primary_departments", []))
        secondary = set(context.get("secondary_departments", []))
        if profile["department"] in primary:
            components["department"] = float(self.model["department_scores"]["primary"])
        elif item_departments & primary:
            components["department"] = float(self.model["department_scores"]["primary"]) * 0.8
        elif item_departments & secondary:
            components["department"] = float(self.model["department_scores"]["secondary"])
        else:
            components["department"] = 0.0

        components["speciality"] = self._speciality_score(profile, context)

        channel_scores = [
            float(context.get("channel_weights", {}).get(channel, 0))
            for channel in profile.get("market_channels", [])
        ]
        components["market_channel"] = clamp(
            max(channel_scores, default=0.0), 0.0, float(self.model["channel_score_cap"])
        )

        affinity = 0.0
        preferences = context.get("affinity_preferences", {})
        for group in ("audience", "use", "character"):
            group_prefs = preferences.get(group, {})
            for tag in profile.get("affinity_tags", {}).get(group, []):
                affinity += float(group_prefs.get(tag, 0))
        components["affinity"] = clamp(
            affinity,
            -float(self.model["affinity_score_cap"]),
            float(self.model["affinity_score_cap"]),
        )

        brand_values = [
            float(context.get("brand_affinities", {}).get(mfr, 0))
            for mfr in self.manufacturers_by_item.get(item_id, [])
        ]
        brand = max(brand_values, default=0.0)
        components["manufacturer"] = clamp(
            brand,
            -float(self.model["brand_score_cap"]),
            float(self.model["brand_score_cap"]),
        )

        identity = profile.get("product_identity")
        identity_score = float(context.get("identity_weights", {}).get(identity, 0))
        components["product_identity"] = clamp(
            identity_score,
            -float(self.model["identity_score_cap"]),
            float(self.model["identity_score_cap"]),
        )

        price_cfg = self.model["price_score"]
        tier_order = price_cfg["tier_order"]
        item_tier = self._price_tier(item)
        center = context.get("price_tier_center")
        if item_tier in tier_order and center in tier_order:
            distance = abs(tier_order.index(item_tier) - tier_order.index(center))
            components["price_band"] = max(
                float(price_cfg["min_score"]),
                float(price_cfg["max_bonus"]) - distance * float(price_cfg["distance_penalty"]),
            )
        else:
            components["price_band"] = 0.0

        supply = profile.get("supply_profile", "regular")
        capability = context.get("supply_capability", "ordinary")
        supply_matrix = self.model["supply_scores"].get(capability)
        if supply_matrix is None:
            raise ValueError(f"unknown supply capability: {capability}")
        components["supply"] = float(supply_matrix.get(supply, 0))

        total = sum(components.values())
        return {
            "item_id": item_id,
            "name": item.get("name"),
            "score": round(total, 3),
            "components": {key: round(value, 3) for key, value in components.items()},
        }

    def candidate_scores(self, context: dict[str, Any], special: bool = False) -> list[dict[str, Any]]:
        rows = []
        for item in self.items:
            if self.eligible(item["id"], context, special=special):
                rows.append(self.score(item["id"], context))
        return rows

    # ------------------------------------------------------------------
    # Persistent assortment
    # ------------------------------------------------------------------
    def _saturation_penalty(
        self, item_id: str, selected_ids: list[str]
    ) -> float:
        profile = self.commercial_by_id[item_id]
        path = profile.get("classification_path", [])
        leaf_count = 0
        parent_count = 0
        for chosen_id in selected_ids:
            chosen = self.commercial_by_id[chosen_id].get("classification_path", [])
            if path and chosen == path:
                leaf_count += 1
            elif len(path) > 1 and len(chosen) > 1 and path[:-1] == chosen[:-1]:
                parent_count += 1
        cfg = self.model["saturation"]
        return min(
            float(cfg["max_penalty"]),
            leaf_count * float(cfg["same_leaf_penalty"])
            + parent_count * float(cfg["same_parent_penalty"]),
        )

    def _pick_assortment_item(
        self,
        rng: random.Random,
        available: list[dict[str, Any]],
        selected_ids: list[str],
        role: str,
    ) -> dict[str, Any] | None:
        if not available:
            return None
        cfg = self.model["role_selection"][role]
        adjusted = []
        weights = []
        for row in available:
            score = float(row["score"]) - self._saturation_penalty(row["item_id"], selected_ids)
            adjusted.append(score)
            base = max(0.0, score - float(cfg["minimum_score"]) + 1.0)
            weights.append(base ** float(cfg["score_power"]) if base > 0 else 0.0)
        if sum(weights) <= 0:
            best_index = max(range(len(available)), key=lambda idx: adjusted[idx])
            return available[best_index]
        return weighted_choice(rng, available, weights)

    def build_assortment(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        rng = random.Random(f"{context['seed']}:assortment:{self.model['version']}")
        scores = self.candidate_scores(context, special=False)
        available = list(scores)
        selected_ids: list[str] = []
        assortment: list[dict[str, Any]] = []
        breadth = self.model["breadth_profiles"][context["breadth_profile"]]

        for role in ("core", "regular", "occasional"):
            for _ in range(int(breadth[role])):
                picked = self._pick_assortment_item(rng, available, selected_ids, role)
                if picked is None:
                    break
                available = [row for row in available if row["item_id"] != picked["item_id"]]
                selected_ids.append(picked["item_id"])
                assortment.append(
                    {
                        "shop_id": context["id"],
                        "item_id": picked["item_id"],
                        "role": role,
                        "affinity_score": picked["score"],
                        "introduced_cycle": 0,
                        "last_stocked_cycle": None,
                        "active": True,
                    }
                )
        return assortment

    # ------------------------------------------------------------------
    # Cycle stock
    # ------------------------------------------------------------------
    def _presence_probability(self, role: str, profile: dict[str, Any]) -> float:
        base = float(self.model["presence_by_role"][role])
        supply = profile.get("supply_profile", "regular")
        adjust = float(self.model["presence_supply_adjustment"].get(supply, 0))
        return clamp(base + adjust, 0.05, 1.0)

    def _quantity(self, rng: random.Random, profile: dict[str, Any], context: dict[str, Any]) -> int | None:
        qprofile = profile.get("quantity_profile", "singular")
        if qprofile == "continuous":
            return None
        bounds = self.model["quantity_ranges"].get(qprofile)
        if bounds is None:
            return 1
        low, high = int(bounds[0]), int(bounds[1])
        raw = rng.randint(low, high)
        multiplier = float(self.model["depth_profiles"][context["depth_profile"]])
        return max(1, int(round(raw * multiplier)))

    def _condition(self, rng: random.Random, profile: dict[str, Any], context: dict[str, Any]) -> str | None:
        allowed = list(profile.get("allowed_conditions", []))
        if not allowed:
            return None
        if allowed == ["not_applicable"] or (
            "not_applicable" in allowed and profile.get("default_condition") == "not_applicable"
        ):
            return None
        allowed = [value for value in allowed if value != "not_applicable"]
        if not allowed:
            return None
        weights = [float(context.get("condition_weights", {}).get(value, 0)) for value in allowed]
        if sum(weights) <= 0:
            default = profile.get("default_condition")
            return default if default in allowed else allowed[0]
        return weighted_choice(rng, allowed, weights)

    @staticmethod
    def _base_price(item: dict[str, Any]) -> float | None:
        for key in ("price_min", "price", "cost_value", "cost"):
            value = numeric(item.get(key))
            if value is not None:
                high = numeric(item.get("price_max")) if key == "price_min" else None
                if high is not None and high >= value:
                    return (value + high) / 2.0
                return value
        return None

    def _asking_price(
        self,
        rng: random.Random,
        item: dict[str, Any],
        condition: str | None,
        context: dict[str, Any],
    ) -> float | None:
        base = self._base_price(item)
        if base is None:
            return None
        style = float(self.model["pricing_styles"].get(context.get("pricing_style", "fair"), 1.0))
        condition_factor = float(self.model["condition_price_factors"].get(condition or "not_applicable", 1.0))
        jitter = float(self.model.get("price_jitter", 0.0))
        factor = style * condition_factor * (1.0 + rng.uniform(-jitter, jitter))
        price = max(0.01, base * factor)
        return round(price, 2) if price < 10 else float(round(price))

    def _visibility(
        self,
        rng: random.Random,
        profile: dict[str, Any],
        role: str,
        context: dict[str, Any],
    ) -> str:
        channels = set(profile.get("market_channels", []))
        shop_channels = set(context.get("channel_weights", {}))
        clandestine = bool(channels & {"grey_market", "black_market"}) and not bool(
            channels & {"retail", "corporate", "institutional"}
        )
        if "black_market" in shop_channels and clandestine:
            return weighted_choice(rng, ["public", "ask", "hidden"], [1, 6, 3])
        if role == "special" and profile.get("supply_profile") in {"scarce", "bespoke", "unique"}:
            return weighted_choice(rng, ["public", "ask", "hidden"], [4, 5, 1])
        return "public"

    def _stock_row(
        self,
        rng: random.Random,
        context: dict[str, Any],
        item_id: str,
        role: str,
        cycle: int,
    ) -> dict[str, Any]:
        item = self.items_by_id[item_id]
        profile = self.commercial_by_id[item_id]
        condition = self._condition(rng, profile, context)
        quantity = self._quantity(rng, profile, context)
        sid = str(uuid.uuid5(NAMESPACE, f"stock:{context['id']}:{cycle}:{item_id}:{role}"))
        return {
            "id": sid,
            "shop_id": context["id"],
            "item_id": item_id,
            "quantity": quantity,
            "condition": condition,
            "asking_price": self._asking_price(rng, item, condition, context),
            "price_modifier": self.model["pricing_styles"].get(context.get("pricing_style", "fair"), 1.0),
            "visibility": self._visibility(rng, profile, role, context),
            "status": "in_stock",
            "assortment_role": role,
            "added_cycle": cycle,
            "stock_reason": role,
        }

    def _pick_specials(
        self,
        rng: random.Random,
        context: dict[str, Any],
        excluded_ids: set[str],
        cycle: int,
    ) -> list[dict[str, Any]]:
        special_range = context.get("specials") or [
            self.model["specials"]["default_min"], self.model["specials"]["default_max"]
        ]
        wanted = rng.randint(int(special_range[0]), int(special_range[1]))
        candidates = [
            row for row in self.candidate_scores(context, special=True)
            if row["item_id"] not in excluded_ids
        ]
        chosen: list[dict[str, Any]] = []
        rarity_bonus = {
            "ubiquitous": 0,
            "regular": 1,
            "specialist": 4,
            "scarce": 8,
            "bespoke": 10,
            "unique": 14,
        }
        for _ in range(min(wanted, len(candidates))):
            weights = []
            for row in candidates:
                profile = self.commercial_by_id[row["item_id"]]
                score = max(float(self.model["specials"]["score_floor"]), float(row["score"]))
                score += rarity_bonus.get(profile.get("supply_profile"), 0)
                weights.append(score ** 0.7)
            picked = weighted_choice(rng, candidates, weights)
            chosen.append(self._stock_row(rng, context, picked["item_id"], "special", cycle))
            candidates = [row for row in candidates if row["item_id"] != picked["item_id"]]
        return chosen

    def initial_stock(
        self, context: dict[str, Any], assortment: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        rng = random.Random(f"{context['seed']}:stock:0:{self.model['version']}")
        stock: list[dict[str, Any]] = []
        stocked_ids: set[str] = set()
        for line in assortment:
            if not line.get("active", True):
                continue
            profile = self.commercial_by_id[line["item_id"]]
            if rng.random() <= self._presence_probability(line["role"], profile):
                row = self._stock_row(rng, context, line["item_id"], line["role"], 0)
                stock.append(row)
                stocked_ids.add(line["item_id"])
                line["last_stocked_cycle"] = 0
        stock.extend(self._pick_specials(rng, context, stocked_ids | {r["item_id"] for r in assortment}, 0))
        return stock

    def generate(self, context: dict[str, Any]) -> dict[str, Any]:
        assortment = self.build_assortment(context)
        stock = self.initial_stock(context, assortment)
        return {
            "format_version": "0.1.0",
            "engine_version": self.model["version"],
            "shop": copy.deepcopy(context),
            "assortment": assortment,
            "stock": stock,
            "state": {"stock_cycle": 0},
            "history": [],
        }

    # ------------------------------------------------------------------
    # Restock a persisted state without rebuilding its assortment
    # ------------------------------------------------------------------
    def restock(self, bundle: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(bundle)
        context = result["shop"]
        old_cycle = int(result.get("state", {}).get("stock_cycle", 0))
        cycle = old_cycle + 1
        rng = random.Random(f"{context['seed']}:stock:{cycle}:{self.model['version']}")

        assortment_by_item = {
            row["item_id"]: row for row in result.get("assortment", []) if row.get("active", True)
        }
        regular_stock: dict[str, dict[str, Any]] = {}
        surviving_specials: list[dict[str, Any]] = []
        for row in result.get("stock", []):
            item_id = row["item_id"]
            role = row.get("assortment_role") or row.get("stock_reason")
            if role == "special":
                quantity = row.get("quantity")
                if row.get("status") == "in_stock" and (quantity is None or quantity > 0):
                    surviving_specials.append(row)
                continue
            if item_id in assortment_by_item:
                regular_stock[item_id] = row

        new_stock: list[dict[str, Any]] = []
        history = result.setdefault("history", [])
        for item_id, line in assortment_by_item.items():
            profile = self.commercial_by_id[item_id]
            existing = regular_stock.get(item_id)
            present = existing is not None and existing.get("status") == "in_stock" and (
                existing.get("quantity") is None or existing.get("quantity", 0) > 0
            )
            probability = self._presence_probability(line["role"], profile)

            if present:
                # Existing unsold stock persists. Core and regular lines may be topped up;
                # occasional lines are mostly left alone until depleted.
                if line["role"] == "core":
                    top_up_chance = 0.85
                elif line["role"] == "regular":
                    top_up_chance = 0.55
                else:
                    top_up_chance = 0.20
                if existing.get("quantity") is not None and rng.random() < top_up_chance:
                    target = self._quantity(rng, profile, context)
                    if target is not None and target > existing["quantity"]:
                        delta = target - existing["quantity"]
                        existing["quantity"] = target
                        existing["status"] = "in_stock"
                        existing["asking_price"] = self._asking_price(
                            rng, self.items_by_id[item_id], existing.get("condition"), context
                        )
                        history.append({
                            "cycle": cycle,
                            "event_type": "replenished",
                            "item_id": item_id,
                            "quantity_delta": delta,
                        })
                new_stock.append(existing)
                line["last_stocked_cycle"] = cycle
                continue

            if rng.random() <= probability:
                row = self._stock_row(rng, context, item_id, line["role"], cycle)
                new_stock.append(row)
                line["last_stocked_cycle"] = cycle
                history.append({
                    "cycle": cycle,
                    "event_type": "restocked",
                    "item_id": item_id,
                    "quantity_delta": row.get("quantity"),
                })
            elif existing is not None:
                existing["quantity"] = 0 if existing.get("quantity") is not None else None
                existing["status"] = "sold"
                new_stock.append(existing)

        excluded = set(assortment_by_item) | {row["item_id"] for row in surviving_specials}
        new_specials = self._pick_specials(rng, context, excluded, cycle)
        for row in new_specials:
            history.append({
                "cycle": cycle,
                "event_type": "special_arrival",
                "item_id": row["item_id"],
                "quantity_delta": row.get("quantity"),
            })

        result["stock"] = new_stock + surviving_specials + new_specials
        result.setdefault("state", {})["stock_cycle"] = cycle
        return result

    # ------------------------------------------------------------------
    # Human-friendly summary
    # ------------------------------------------------------------------
    def summarize(self, bundle: dict[str, Any]) -> dict[str, Any]:
        role_counts = Counter(row["role"] for row in bundle.get("assortment", []))
        stock_role_counts = Counter(
            row.get("assortment_role") or row.get("stock_reason") for row in bundle.get("stock", [])
            if row.get("status") == "in_stock"
        )
        departments = Counter(
            self.commercial_by_id[row["item_id"]]["department"]
            for row in bundle.get("stock", [])
            if row.get("status") == "in_stock"
        )
        return {
            "shop_id": bundle["shop"]["id"],
            "archetype_id": bundle["shop"]["archetype_id"],
            "stock_cycle": bundle.get("state", {}).get("stock_cycle", 0),
            "assortment_roles": dict(sorted(role_counts.items())),
            "in_stock_roles": dict(sorted(stock_role_counts.items())),
            "in_stock_departments": dict(sorted(departments.items())),
            "stock_lines": sum(1 for row in bundle.get("stock", []) if row.get("status") == "in_stock"),
        }


def command_generate(engine: StockEngine, args: argparse.Namespace) -> None:
    overrides = load_json(Path(args.context_overrides)) if args.context_overrides else None
    context = engine.make_context(args.archetype, args.seed, args.shop_id, overrides)
    bundle = engine.generate(context)
    Path(args.output).write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(engine.summarize(bundle), ensure_ascii=False, indent=2))


def command_restock(engine: StockEngine, args: argparse.Namespace) -> None:
    bundle = load_json(Path(args.input))
    result = engine.restock(bundle)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(engine.summarize(result), ensure_ascii=False, indent=2))


def command_score(engine: StockEngine, args: argparse.Namespace) -> None:
    overrides = load_json(Path(args.context_overrides)) if args.context_overrides else None
    context = engine.make_context(args.archetype, args.seed, args.shop_id, overrides)
    rows = engine.candidate_scores(context, special=args.special)
    rows.sort(key=lambda row: (-row["score"], row["item_id"]))
    print(json.dumps(rows[: args.limit], ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vend-R persistent stocking engine")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="create persistent assortment + cycle-0 stock")
    generate.add_argument("--archetype", required=True)
    generate.add_argument("--seed", required=True)
    generate.add_argument("--shop-id")
    generate.add_argument("--context-overrides", help="JSON patch for the realized stocking context")
    generate.add_argument("--output", required=True)
    generate.set_defaults(func=command_generate)

    restock = sub.add_parser("restock", help="advance a saved stocking bundle by one cycle")
    restock.add_argument("--input", required=True)
    restock.add_argument("--output", required=True)
    restock.set_defaults(func=command_restock)

    score = sub.add_parser("score", help="inspect candidate scores for a stocking context")
    score.add_argument("--archetype", required=True)
    score.add_argument("--seed", default="score-preview")
    score.add_argument("--shop-id")
    score.add_argument("--context-overrides")
    score.add_argument("--special", action="store_true")
    score.add_argument("--limit", type=int, default=25)
    score.set_defaults(func=command_score)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    engine = StockEngine()
    args.func(engine, args)


if __name__ == "__main__":
    main()
