#!/usr/bin/env python3
"""Vend-R persistence, source-filtering, restock events and inspection layer.

`stock_engine.py` owns catalogue eligibility/scoring/assortment mechanics. This module
turns those mechanics into a durable saved-shop contract: persistent target stock,
backorders, temporary supply conditions, source filters, event history and a plain
Markdown inspection report.
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from stock_engine import NAMESPACE, ROOT, StockEngine, clamp, load_json


BUNDLE_FORMAT_VERSION = "0.2.0"


class StockLifecycleEngine(StockEngine):
    def __init__(self) -> None:
        super().__init__()
        self.item_sources = self._load_item_sources()
        self.source_codes_by_item: dict[str, set[str]] = defaultdict(set)
        for row in self.item_sources:
            self.source_codes_by_item[row["item_id"]].add(row["source_code"])
        sources = load_json(ROOT / "data/catalog/sources.json")
        self.valid_source_codes = {row["code"] for row in sources}
        self.lifecycle = self.model["lifecycle"]

    def _load_item_sources(self) -> list[dict[str, Any]]:
        return self._load_manifest_table("item-sources")

    def _load_manifest_table(self, name: str) -> list[dict[str, Any]]:
        # Reuse the canonical shard loader without exposing a second data path.
        import gzip

        rows: list[dict[str, Any]] = []
        for part in self.manifest["tables"][name]["parts"]:
            with gzip.open(ROOT / part["path"], "rt", encoding="utf-8") as handle:
                rows.extend(json.load(handle))
        return rows

    # ------------------------------------------------------------------
    # Realized context and source filtering
    # ------------------------------------------------------------------
    def make_context(
        self,
        archetype_id: str,
        seed: str,
        shop_id: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().make_context(archetype_id, seed, shop_id, None)
        context["enabled_source_codes"] = None  # None means all catalogue sources.
        context["stocking_contract_version"] = BUNDLE_FORMAT_VERSION
        self._deep_update(context, overrides or {})
        enabled = context.get("enabled_source_codes")
        if enabled is not None:
            unknown = set(enabled) - self.valid_source_codes
            if unknown:
                raise ValueError(f"unknown source codes: {sorted(unknown)}")
            context["enabled_source_codes"] = sorted(set(enabled))
        return context

    def eligible(self, item_id: str, context: dict[str, Any], special: bool = False) -> bool:
        if not super().eligible(item_id, context, special=special):
            return False
        enabled = context.get("enabled_source_codes")
        if enabled is not None:
            if not (self.source_codes_by_item.get(item_id, set()) & set(enabled)):
                return False
        return True

    # ------------------------------------------------------------------
    # Persistent assortment contract
    # ------------------------------------------------------------------
    def _target_quantity(self, context: dict[str, Any], item_id: str, role: str) -> int | None:
        profile = self.commercial_by_id[item_id]
        rng = random.Random(
            f"{context['seed']}:target:{item_id}:{role}:{self.model['version']}"
        )
        base = self._quantity(rng, profile, context)
        if base is None:
            return None
        multiplier = float(self.lifecycle["target_multiplier_by_role"].get(role, 1.0))
        return max(1, int(round(base * multiplier)))

    def build_assortment(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        assortment = super().build_assortment(context)
        reorder_fraction = self.lifecycle["reorder_fraction_by_role"]
        for line in assortment:
            scored = self.score(line["item_id"], context)
            target = self._target_quantity(context, line["item_id"], line["role"])
            line["score_components"] = scored["components"]
            line["target_quantity"] = target
            line["reorder_point"] = (
                None
                if target is None
                else max(1, int(round(target * float(reorder_fraction[line["role"]]))))
            )
        return assortment

    def _initial_fill_quantity(
        self,
        rng: random.Random,
        line: dict[str, Any],
    ) -> int | None:
        target = line.get("target_quantity")
        if target is None:
            return None
        low, high = self.lifecycle["initial_fill_by_role"][line["role"]]
        return max(1, int(round(target * rng.uniform(float(low), float(high)))))

    def initial_stock(
        self, context: dict[str, Any], assortment: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        stock = super().initial_stock(context, assortment)
        by_item = {row["item_id"]: row for row in assortment}
        rng = random.Random(f"{context['seed']}:initial-fill:{self.model['version']}")
        for row in stock:
            if row.get("assortment_role") == "special":
                row.setdefault("metadata", {})
                continue
            line = by_item[row["item_id"]]
            row["quantity"] = self._initial_fill_quantity(rng, line)
            row.setdefault("metadata", {})
        return stock

    # ------------------------------------------------------------------
    # Events and temporary conditions
    # ------------------------------------------------------------------
    def _append_event(
        self,
        bundle: dict[str, Any],
        cycle: int,
        event_type: str,
        item_id: str | None = None,
        quantity_delta: int | None = None,
        price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        history = bundle.setdefault("history", [])
        event_id = str(
            uuid.uuid5(
                NAMESPACE,
                f"event:{bundle['shop']['id']}:{cycle}:{len(history)}:{event_type}:{item_id or '-'}",
            )
        )
        event = {
            "id": event_id,
            "cycle": cycle,
            "event_type": event_type,
            "item_id": item_id,
            "quantity_delta": quantity_delta,
            "price": price,
            "metadata": metadata or {},
        }
        history.append(event)
        return event

    def _condition_definition(self, entry: dict[str, Any]) -> dict[str, Any]:
        kind = entry.get("type")
        definitions = self.lifecycle["temporary_conditions"]
        if kind not in definitions:
            raise ValueError(f"unknown temporary condition: {kind}")
        return definitions[kind]

    def _condition_applies(self, item_id: str, entry: dict[str, Any]) -> bool:
        target = entry.get("target") or {}
        if not target:
            return True
        profile = self.commercial_by_id[item_id]
        item_depts = self._item_departments(profile)
        checks: list[bool] = []
        if target.get("departments"):
            checks.append(bool(item_depts & set(target["departments"])))
        if target.get("supply_profiles"):
            checks.append(profile.get("supply_profile") in set(target["supply_profiles"]))
        if target.get("market_channels"):
            checks.append(bool(set(profile.get("market_channels", [])) & set(target["market_channels"])))
        if target.get("manufacturer_ids"):
            checks.append(
                bool(
                    set(self.manufacturers_by_item.get(item_id, []))
                    & set(target["manufacturer_ids"])
                )
            )
        if target.get("item_ids"):
            checks.append(item_id in set(target["item_ids"]))
        return all(checks) if checks else True

    def _cycle_modifiers(self, item_id: str, state: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "presence_multiplier": 1.0,
            "quantity_multiplier": 1.0,
            "price_multiplier": 1.0,
            "top_up_multiplier": 1.0,
            "visibility_bias": None,
        }
        for entry in state.get("temporary_conditions", []):
            definition = self._condition_definition(entry)
            if not self._condition_applies(item_id, entry):
                continue
            for key in (
                "presence_multiplier",
                "quantity_multiplier",
                "price_multiplier",
                "top_up_multiplier",
            ):
                result[key] *= float(definition.get(key, 1.0))
            if definition.get("visibility_bias"):
                result["visibility_bias"] = definition["visibility_bias"]
        return result

    def _special_delta(self, state: dict[str, Any]) -> int:
        total = 0
        for entry in state.get("temporary_conditions", []):
            if entry.get("target"):
                continue
            total += int(self._condition_definition(entry).get("special_delta", 0))
        return total

    def _refresh_price(
        self,
        rng: random.Random,
        row: dict[str, Any],
        context: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        item = self.items_by_id[row["item_id"]]
        base = self._base_price(item)
        price = self._asking_price(rng, item, row.get("condition"), context)
        mods = self._cycle_modifiers(row["item_id"], state)
        if price is not None:
            price = max(0.01, price * float(mods["price_multiplier"]))
            row["asking_price"] = round(price, 2) if price < 10 else float(round(price))
        if base and row.get("asking_price") is not None:
            row["price_modifier"] = round(float(row["asking_price"]) / base, 4)

    def _apply_cycle_row_modifiers(
        self,
        rng: random.Random,
        row: dict[str, Any],
        context: dict[str, Any],
        state: dict[str, Any],
        target_quantity: int | None = None,
    ) -> None:
        mods = self._cycle_modifiers(row["item_id"], state)
        if target_quantity is not None:
            row["quantity"] = max(
                1, int(round(target_quantity * float(mods["quantity_multiplier"])))
            )
        elif row.get("quantity") is not None:
            row["quantity"] = max(
                1, int(round(row["quantity"] * float(mods["quantity_multiplier"])))
            )
        self._refresh_price(rng, row, context, state)
        if mods.get("visibility_bias") == "ask" and row.get("visibility") == "public":
            row["visibility"] = "ask"
        elif mods.get("visibility_bias") == "hidden":
            row["visibility"] = "hidden"
        row.setdefault("metadata", {})

    def _delivery_delay(self, rng: random.Random, item_id: str) -> int:
        supply = self.commercial_by_id[item_id].get("supply_profile", "regular")
        low, high = self.lifecycle["delivery_delay_by_supply"][supply]
        return rng.randint(int(low), int(high))

    def _incoming_row(
        self,
        rng: random.Random,
        context: dict[str, Any],
        state: dict[str, Any],
        line: dict[str, Any],
        cycle: int,
    ) -> dict[str, Any] | None:
        target = line.get("target_quantity")
        if target is None:
            return None
        row = self._stock_row(rng, context, line["item_id"], line["role"], cycle)
        self._apply_cycle_row_modifiers(rng, row, context, state, target)
        delay = self._delivery_delay(rng, line["item_id"])
        row["status"] = "incoming"
        row["metadata"] = {
            "ordered_cycle": cycle,
            "arrival_cycle": cycle + delay,
        }
        return row

    # ------------------------------------------------------------------
    # Durable bundle generation and validation
    # ------------------------------------------------------------------
    def generate(self, context: dict[str, Any]) -> dict[str, Any]:
        assortment = self.build_assortment(context)
        stock = self.initial_stock(context, assortment)
        bundle: dict[str, Any] = {
            "format_version": BUNDLE_FORMAT_VERSION,
            "engine_version": self.model["version"],
            "shop": copy.deepcopy(context),
            "assortment": assortment,
            "stock": stock,
            "state": {
                "stock_cycle": 0,
                "temporary_conditions": [],
                "last_cycle_events": [],
                "source_filter": {
                    "enabled_source_codes": copy.deepcopy(context.get("enabled_source_codes"))
                },
            },
            "history": [],
        }
        created = self._append_event(
            bundle,
            0,
            "assortment_created",
            metadata={
                "core": sum(1 for row in assortment if row["role"] == "core"),
                "regular": sum(1 for row in assortment if row["role"] == "regular"),
                "occasional": sum(1 for row in assortment if row["role"] == "occasional"),
            },
        )
        cycle_events = [created["id"]]
        for row in stock:
            event = self._append_event(
                bundle,
                0,
                "special_arrival" if row.get("assortment_role") == "special" else "initial_stock",
                item_id=row["item_id"],
                quantity_delta=row.get("quantity"),
                price=row.get("asking_price"),
                metadata={"role": row.get("assortment_role")},
            )
            cycle_events.append(event["id"])
        bundle["state"]["last_cycle_events"] = cycle_events
        self.validate_bundle(bundle)
        return bundle

    def validate_bundle(self, bundle: dict[str, Any]) -> None:
        if bundle.get("format_version") != BUNDLE_FORMAT_VERSION:
            raise ValueError(
                f"unsupported stocking bundle format: {bundle.get('format_version')!r}"
            )
        for key in ("shop", "assortment", "stock", "state", "history"):
            if key not in bundle:
                raise ValueError(f"stocking bundle missing {key}")
        context = bundle["shop"]
        enabled = context.get("enabled_source_codes")
        if enabled is not None:
            unknown = set(enabled) - self.valid_source_codes
            if unknown:
                raise ValueError(f"bundle contains unknown source codes: {sorted(unknown)}")
        seen: set[str] = set()
        for line in bundle["assortment"]:
            item_id = line["item_id"]
            if item_id in seen:
                raise ValueError(f"duplicate assortment item: {item_id}")
            seen.add(item_id)
            if line["role"] not in {"core", "regular", "occasional"}:
                raise ValueError(f"invalid assortment role: {line['role']}")
            if self.commercial_by_id[item_id].get("product_identity") == "unique":
                raise ValueError(f"unique item cannot be persistent assortment: {item_id}")
            target = line.get("target_quantity")
            reorder = line.get("reorder_point")
            if target is not None and (not isinstance(target, int) or target < 1):
                raise ValueError(f"bad target quantity: {item_id}")
            if reorder is not None and (
                not isinstance(reorder, int) or reorder < 1 or target is None or reorder > target
            ):
                raise ValueError(f"bad reorder point: {item_id}")
            if enabled is not None and not (
                self.source_codes_by_item.get(item_id, set()) & set(enabled)
            ):
                raise ValueError(f"assortment item outside source filter: {item_id}")
        for row in bundle["stock"]:
            if row["item_id"] not in self.items_by_id:
                raise ValueError(f"unknown stock item: {row['item_id']}")
            if row.get("status") not in {"in_stock", "reserved", "sold", "incoming"}:
                raise ValueError(f"bad stock status: {row.get('status')}")
            if row.get("assortment_role") not in {"core", "regular", "occasional", "special"}:
                raise ValueError(f"bad stock role: {row.get('assortment_role')}")
            if row.get("status") == "incoming":
                arrival = row.get("metadata", {}).get("arrival_cycle")
                if not isinstance(arrival, int):
                    raise ValueError(f"incoming stock missing arrival cycle: {row['item_id']}")
        event_ids = [row["id"] for row in bundle["history"]]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("duplicate stock-history event ID")
        for entry in bundle["state"].get("temporary_conditions", []):
            self._condition_definition(entry)

    # ------------------------------------------------------------------
    # Restock persisted state; never rebuild assortment
    # ------------------------------------------------------------------
    @staticmethod
    def _is_present(row: dict[str, Any] | None) -> bool:
        return bool(
            row
            and row.get("status") in {"in_stock", "reserved"}
            and (row.get("quantity") is None or row.get("quantity", 0) > 0)
        )

    def restock(self, bundle: dict[str, Any]) -> dict[str, Any]:
        self.validate_bundle(bundle)
        result = copy.deepcopy(bundle)
        context = result["shop"]
        state = result["state"]
        old_cycle = int(state.get("stock_cycle", 0))
        cycle = old_cycle + 1
        rng = random.Random(
            f"{context['seed']}:lifecycle:{cycle}:{self.model['version']}"
        )
        state["last_cycle_events"] = []

        for entry in state.get("temporary_conditions", []):
            event = self._append_event(
                result,
                cycle,
                "condition_active",
                metadata={"type": entry["type"], "target": entry.get("target")},
            )
            state["last_cycle_events"].append(event["id"])

        assortment_by_item = {
            row["item_id"]: row
            for row in result["assortment"]
            if row.get("active", True)
        }
        current_by_item: dict[str, dict[str, Any]] = {}
        incoming_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
        surviving_specials: list[dict[str, Any]] = []

        for row in result["stock"]:
            role = row.get("assortment_role") or row.get("stock_reason")
            if role == "special":
                if self._is_present(row):
                    surviving_specials.append(row)
                else:
                    event = self._append_event(
                        result,
                        cycle,
                        "special_departed",
                        item_id=row["item_id"],
                        metadata={"previous_status": row.get("status")},
                    )
                    state["last_cycle_events"].append(event["id"])
                continue
            if row.get("status") == "incoming":
                incoming_by_item[row["item_id"]].append(row)
            else:
                current_by_item[row["item_id"]] = row

        delivered_by_item: dict[str, dict[str, Any]] = {}
        pending_rows: list[dict[str, Any]] = []
        for item_id, rows in incoming_by_item.items():
            rows.sort(key=lambda row: row.get("metadata", {}).get("arrival_cycle", 10**9))
            delivered = False
            for row in rows:
                arrival = int(row.get("metadata", {}).get("arrival_cycle", cycle + 1))
                if not delivered and arrival <= cycle:
                    row["status"] = "in_stock"
                    row["added_cycle"] = cycle
                    row.setdefault("metadata", {})["delivered_cycle"] = cycle
                    self._refresh_price(rng, row, context, state)
                    delivered_by_item[item_id] = row
                    delivered = True
                    event = self._append_event(
                        result,
                        cycle,
                        "delivery_received",
                        item_id=item_id,
                        quantity_delta=row.get("quantity"),
                        price=row.get("asking_price"),
                    )
                    state["last_cycle_events"].append(event["id"])
                else:
                    pending_rows.append(row)

        new_stock: list[dict[str, Any]] = []
        top_up_chance = self.lifecycle["top_up_chance_by_role"]
        backorder_chance = self.lifecycle["backorder_chance_by_role"]

        for item_id, line in assortment_by_item.items():
            profile = self.commercial_by_id[item_id]
            existing = delivered_by_item.get(item_id) or current_by_item.get(item_id)
            pending = [row for row in pending_rows if row["item_id"] == item_id]
            mods = self._cycle_modifiers(item_id, state)

            if self._is_present(existing):
                if item_id in delivered_by_item:
                    line["last_stocked_cycle"] = cycle
                    new_stock.append(existing)
                    continue

                if existing.get("quantity") is not None:
                    target = line.get("target_quantity")
                    if target is not None:
                        target = max(
                            1,
                            int(round(target * float(mods["quantity_multiplier"]))),
                        )
                        reorder = line.get("reorder_point") or 1
                        chance = float(top_up_chance[line["role"]]) * float(
                            mods["top_up_multiplier"]
                        )
                        if existing["quantity"] <= reorder:
                            chance = max(chance, 0.90)
                        if existing["quantity"] < target and rng.random() < clamp(chance, 0, 1):
                            delta = target - existing["quantity"]
                            existing["quantity"] = target
                            self._refresh_price(rng, existing, context, state)
                            event = self._append_event(
                                result,
                                cycle,
                                "replenished",
                                item_id=item_id,
                                quantity_delta=delta,
                                price=existing.get("asking_price"),
                                metadata={"role": line["role"], "target_quantity": target},
                            )
                            state["last_cycle_events"].append(event["id"])
                new_stock.append(existing)
                line["last_stocked_cycle"] = cycle
                continue

            if pending:
                if existing is not None:
                    new_stock.append(existing)
                continue

            probability = clamp(
                self._presence_probability(line["role"], profile)
                * float(mods["presence_multiplier"]),
                0.02,
                1.0,
            )
            if rng.random() <= probability:
                row = self._stock_row(rng, context, item_id, line["role"], cycle)
                self._apply_cycle_row_modifiers(
                    rng,
                    row,
                    context,
                    state,
                    line.get("target_quantity"),
                )
                new_stock.append(row)
                line["last_stocked_cycle"] = cycle
                event = self._append_event(
                    result,
                    cycle,
                    "restocked",
                    item_id=item_id,
                    quantity_delta=row.get("quantity"),
                    price=row.get("asking_price"),
                    metadata={"role": line["role"]},
                )
                state["last_cycle_events"].append(event["id"])
                continue

            event = self._append_event(
                result,
                cycle,
                "supplier_failed",
                item_id=item_id,
                metadata={
                    "role": line["role"],
                    "supply_profile": profile.get("supply_profile"),
                    "presence_probability": round(probability, 4),
                },
            )
            state["last_cycle_events"].append(event["id"])
            if existing is not None:
                new_stock.append(existing)

            order_chance = float(backorder_chance[line["role"]])
            if rng.random() < order_chance:
                incoming = self._incoming_row(rng, context, state, line, cycle)
                if incoming is not None:
                    pending_rows.append(incoming)
                    event = self._append_event(
                        result,
                        cycle,
                        "backorder_placed",
                        item_id=item_id,
                        quantity_delta=incoming.get("quantity"),
                        metadata={
                            "role": line["role"],
                            "arrival_cycle": incoming["metadata"]["arrival_cycle"],
                        },
                    )
                    state["last_cycle_events"].append(event["id"])

        excluded = set(assortment_by_item) | {row["item_id"] for row in surviving_specials}
        special_context = copy.deepcopy(context)
        low, high = special_context.get("specials") or [
            self.model["specials"]["default_min"],
            self.model["specials"]["default_max"],
        ]
        delta = self._special_delta(state)
        special_context["specials"] = [max(0, int(low) + delta), max(0, int(high) + delta)]
        new_specials = self._pick_specials(rng, special_context, excluded, cycle)
        for row in new_specials:
            self._apply_cycle_row_modifiers(rng, row, context, state)
            event = self._append_event(
                result,
                cycle,
                "special_arrival",
                item_id=row["item_id"],
                quantity_delta=row.get("quantity"),
                price=row.get("asking_price"),
            )
            state["last_cycle_events"].append(event["id"])

        # Avoid duplicating an incoming row already converted to delivered stock.
        delivered_ids = {id(row) for row in delivered_by_item.values()}
        remaining_pending = [row for row in pending_rows if id(row) not in delivered_ids]
        result["stock"] = new_stock + remaining_pending + surviving_specials + new_specials
        state["stock_cycle"] = cycle
        self.validate_bundle(result)
        return result

    # ------------------------------------------------------------------
    # Human-readable inspection
    # ------------------------------------------------------------------
    @staticmethod
    def _md(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    def _stock_status_for_item(self, bundle: dict[str, Any], item_id: str) -> str:
        rows = [row for row in bundle["stock"] if row["item_id"] == item_id]
        if not rows:
            return "absent"
        labels = []
        for row in rows:
            qty = "∞" if row.get("quantity") is None else str(row.get("quantity", 0))
            if row.get("status") == "incoming":
                arrival = row.get("metadata", {}).get("arrival_cycle", "?")
                labels.append(f"incoming {qty} (cycle {arrival})")
            elif row.get("status") == "in_stock":
                labels.append(f"in stock {qty}")
            elif row.get("status") == "reserved":
                labels.append(f"reserved {qty}")
            else:
                labels.append("sold out")
        return "; ".join(labels)

    def inspection_markdown(self, bundle: dict[str, Any]) -> str:
        self.validate_bundle(bundle)
        shop = bundle["shop"]
        state = bundle["state"]
        enabled = shop.get("enabled_source_codes")
        source_text = "all catalogue sources" if enabled is None else ", ".join(enabled)
        conditions = state.get("temporary_conditions", [])
        condition_text = ", ".join(entry["type"] for entry in conditions) or "none"
        lines = [
            f"# Stock inspection — {self._md(shop.get('archetype_id'))}",
            "",
            f"- Shop ID: `{shop['id']}`",
            f"- Seed: `{shop['seed']}`",
            f"- Stock cycle: **{state.get('stock_cycle', 0)}**",
            f"- Source filter: {self._md(source_text)}",
            f"- Temporary conditions: {self._md(condition_text)}",
            "",
            "## Persistent assortment",
            "",
            "| Role | Item | Score | Target | Reorder | Current state | Score breakdown |",
            "|---|---|---:|---:|---:|---|---|",
        ]
        role_order = {"core": 0, "regular": 1, "occasional": 2}
        assortment = sorted(
            bundle["assortment"],
            key=lambda row: (role_order[row["role"]], -float(row.get("affinity_score", 0)), row["item_id"]),
        )
        for line in assortment:
            item = self.items_by_id[line["item_id"]]
            components = line.get("score_components") or self.score(line["item_id"], shop)["components"]
            breakdown = ", ".join(
                f"{key} {value:+g}" for key, value in components.items() if key != "base" and value
            ) or "base only"
            target = "∞" if line.get("target_quantity") is None else line["target_quantity"]
            reorder = "—" if line.get("reorder_point") is None else line["reorder_point"]
            lines.append(
                "| {role} | {item} | {score:g} | {target} | {reorder} | {state} | {breakdown} |".format(
                    role=self._md(line["role"]),
                    item=self._md(item["name"]),
                    score=float(line.get("affinity_score", 0)),
                    target=target,
                    reorder=reorder,
                    state=self._md(self._stock_status_for_item(bundle, line["item_id"])),
                    breakdown=self._md(breakdown),
                )
            )

        specials = [row for row in bundle["stock"] if row.get("assortment_role") == "special"]
        lines += ["", "## Specials", ""]
        if not specials:
            lines.append("None this cycle.")
        else:
            lines += [
                "| Item | Status | Qty | Condition | Asking price | Visibility |",
                "|---|---|---:|---|---:|---|",
            ]
            for row in specials:
                item = self.items_by_id[row["item_id"]]
                qty = "∞" if row.get("quantity") is None else row.get("quantity", 0)
                price = "—" if row.get("asking_price") is None else row["asking_price"]
                lines.append(
                    f"| {self._md(item['name'])} | {row.get('status')} | {qty} | "
                    f"{self._md(row.get('condition') or '—')} | {price} | {row.get('visibility')} |"
                )

        last_ids = set(state.get("last_cycle_events", []))
        events = [row for row in bundle["history"] if row["id"] in last_ids]
        lines += ["", "## Last cycle events", ""]
        if not events:
            lines.append("No recorded events.")
        else:
            for event in events:
                name = (
                    self.items_by_id[event["item_id"]]["name"]
                    if event.get("item_id") in self.items_by_id
                    else ""
                )
                detail = f" — {name}" if name else ""
                qty = event.get("quantity_delta")
                if qty is not None:
                    detail += f" ({qty:+d})"
                lines.append(f"- **{event['event_type']}**{self._md(detail)}")
        lines.append("")
        return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def _parse_sources(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def command_generate(engine: StockLifecycleEngine, args: argparse.Namespace) -> None:
    overrides = load_json(Path(args.context_overrides)) if args.context_overrides else {}
    if args.sources is not None:
        overrides["enabled_source_codes"] = _parse_sources(args.sources)
    context = engine.make_context(args.archetype, args.seed, args.shop_id, overrides)
    bundle = engine.generate(context)
    Path(args.output).write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(engine.summarize(bundle), ensure_ascii=False, indent=2))


def command_restock(engine: StockLifecycleEngine, args: argparse.Namespace) -> None:
    bundle = load_json(Path(args.input))
    if args.clear_conditions:
        bundle.setdefault("state", {})["temporary_conditions"] = []
    for kind in args.add_condition or []:
        bundle.setdefault("state", {}).setdefault("temporary_conditions", []).append({"type": kind})
    result = engine.restock(bundle)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(engine.summarize(result), ensure_ascii=False, indent=2))


def command_inspect(engine: StockLifecycleEngine, args: argparse.Namespace) -> None:
    bundle = load_json(Path(args.input))
    report = engine.inspection_markdown(bundle)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(args.output)
    else:
        print(report)


def command_validate(engine: StockLifecycleEngine, args: argparse.Namespace) -> None:
    engine.validate_bundle(load_json(Path(args.input)))
    print("OK")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vend-R persistent stocking lifecycle")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="create a durable cycle-0 stocking bundle")
    generate.add_argument("--archetype", required=True)
    generate.add_argument("--seed", required=True)
    generate.add_argument("--shop-id")
    generate.add_argument("--context-overrides")
    generate.add_argument("--sources", help="comma-separated source codes; omit for all")
    generate.add_argument("--output", required=True)
    generate.set_defaults(func=command_generate)

    restock = sub.add_parser("restock", help="advance a durable stocking bundle by one cycle")
    restock.add_argument("--input", required=True)
    restock.add_argument("--output", required=True)
    restock.add_argument("--add-condition", action="append", choices=[])
    restock.add_argument("--clear-conditions", action="store_true")
    restock.set_defaults(func=command_restock)

    inspect = sub.add_parser("inspect", help="render a plain Markdown stocking report")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--output")
    inspect.set_defaults(func=command_inspect)

    validate = sub.add_parser("validate", help="validate a saved stocking bundle")
    validate.add_argument("--input", required=True)
    validate.set_defaults(func=command_validate)
    return parser


def main() -> None:
    engine = StockLifecycleEngine()
    parser = build_parser()
    # Choices depend on the loaded model; inject them after parser creation.
    for action in parser._subparsers._group_actions:  # type: ignore[attr-defined]
        for choice in action.choices.values():
            for option in choice._actions:
                if option.dest == "add_condition":
                    option.choices = sorted(engine.lifecycle["temporary_conditions"])
    args = parser.parse_args()
    args.func(engine, args)


if __name__ == "__main__":
    main()
