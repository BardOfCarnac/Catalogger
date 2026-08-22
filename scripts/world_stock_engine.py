#!/usr/bin/env python3
"""Source-constrained extension of the Vend-R stocking engine.

The base stock engine deliberately keeps shop archetypes broad. Canonical world locations
sometimes state narrower facts than an archetype can express (for example, a stall that
sells only sidearms and light armor). This layer adds hard, persisted eligibility constraints
without changing the catalogue or pretending those constraints are universal rarity rules.
"""
from __future__ import annotations

from typing import Any

from stock_engine import StockEngine


class WorldStockEngine(StockEngine):
    """StockEngine with optional hard constraints for source-defined sellers.

    Supported realized-context keys:
      allowed_item_ids
        Absolute whitelist. If present and non-empty, every other catalogue item is refused.

      included_item_ids
        Explicit exceptions to ``allowed_classification_prefixes``. This is useful when a
        source describes a narrow class that the catalogue taxonomy cannot currently express,
        such as "light armor" inside the broader Armor classification.

      allowed_classification_prefixes
        One or more classification-path prefixes. An item must match at least one prefix unless
        it is present in ``included_item_ids``.

      excluded_classification_prefixes
        Hard path exclusions applied after the allow-prefix test.

      min_base_price / max_base_price
        Optional hard catalogue-price bounds. These are seller constraints, not price rarity.

      pinned_assortment
        Explicit catalogue lines that must survive the random assortment pass. Each entry is
        ``{"item_id": ..., "role": "core|regular|occasional"}``. This expresses a source
        requirement such as "the stall carries light armor" while keeping the rest stochastic.
    """

    @staticmethod
    def _path_has_prefix(path: list[str], prefix: list[str]) -> bool:
        return len(path) >= len(prefix) and path[: len(prefix)] == prefix

    def eligible(self, item_id: str, context: dict[str, Any], special: bool = False) -> bool:
        if not super().eligible(item_id, context, special=special):
            return False

        item = self.items_by_id[item_id]
        profile = self.commercial_by_id[item_id]
        path = list(profile.get("classification_path", []))

        allowed_item_ids = set(context.get("allowed_item_ids", []))
        if allowed_item_ids and item_id not in allowed_item_ids:
            return False

        included_item_ids = set(context.get("included_item_ids", []))
        allowed_prefixes = [list(prefix) for prefix in context.get("allowed_classification_prefixes", [])]
        if allowed_prefixes and item_id not in included_item_ids:
            if not any(self._path_has_prefix(path, prefix) for prefix in allowed_prefixes):
                return False

        excluded_prefixes = [list(prefix) for prefix in context.get("excluded_classification_prefixes", [])]
        if any(self._path_has_prefix(path, prefix) for prefix in excluded_prefixes):
            return False

        base_price = self._base_price(item)
        min_price = context.get("min_base_price")
        max_price = context.get("max_base_price")
        if min_price is not None and base_price is not None and base_price < float(min_price):
            return False
        if max_price is not None and base_price is not None and base_price > float(max_price):
            return False

        return True

    def build_assortment(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        assortment = super().build_assortment(context)
        pins = list(context.get("pinned_assortment", []))
        if not pins:
            return assortment

        pinned_ids = {row["item_id"] for row in pins}
        present = {row["item_id"] for row in assortment}
        valid_roles = {"core", "regular", "occasional"}

        for pin in pins:
            item_id = pin["item_id"]
            role = pin.get("role", "regular")
            if role not in valid_roles:
                raise ValueError(f"invalid pinned assortment role: {role}")
            if item_id in present:
                continue
            if not self.eligible(item_id, context, special=False):
                raise ValueError(f"pinned item is not eligible for source-defined shop: {item_id}")

            replacement_index = next(
                (
                    index
                    for index in range(len(assortment) - 1, -1, -1)
                    if assortment[index]["role"] == role
                    and assortment[index]["item_id"] not in pinned_ids
                ),
                None,
            )
            row = {
                "shop_id": context["id"],
                "item_id": item_id,
                "role": role,
                "affinity_score": self.score(item_id, context)["score"],
                "introduced_cycle": 0,
                "last_stocked_cycle": None,
                "active": True,
            }
            if replacement_index is None:
                assortment.append(row)
            else:
                present.discard(assortment[replacement_index]["item_id"])
                assortment[replacement_index] = row
            present.add(item_id)

        return assortment
