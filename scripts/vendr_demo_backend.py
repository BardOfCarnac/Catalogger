#!/usr/bin/env python3
"""Stateful backend for the connected Vend-R / Catalogger demo."""
from __future__ import annotations

import json
import re
from http import HTTPStatus
from pathlib import Path
from typing import Any

from night_city_stock import (
    DELEGATING_MODES,
    EVENT_MODES,
    NO_STOCK_MODES,
    TEMPLATE_MODES,
    NightCityStockBridge,
    load_profiles,
    plan_profile,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILES = ROOT / "data/shops/night-city-2045-live-demo-profiles.json"
DEFAULT_WEB = ROOT / "web/vendr-live"
DEFAULT_STATE = ROOT / "build/vendr-demo-state"

def json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_save(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def safe_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "state"


def source_codes(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    rows = sorted({part.strip() for part in raw.split(",") if part.strip()})
    return rows or None


def query_one(query: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    values = query.get(key)
    return values[0] if values else default


class DemoError(Exception):
    def __init__(self, status: int, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details


class VendRDemoBackend:
    def __init__(
        self,
        bridge: NightCityStockBridge,
        profiles_path: Path,
        state_dir: Path,
        world_seed: str,
        default_event_id: str,
    ) -> None:
        self.bridge = bridge
        self.engine = bridge.engine
        self.profiles_path = profiles_path
        self.profiles = load_profiles(profiles_path)
        self.by_id = {str(row["entity_id"]): row for row in self.profiles}
        self.state_dir = state_dir
        self.world_seed = world_seed
        self.default_event_id = default_event_id
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def profile(self, entity_id: str) -> dict[str, Any]:
        try:
            return self.by_id[entity_id]
        except KeyError as exc:
            raise DemoError(HTTPStatus.NOT_FOUND, f"Unknown demo shop: {entity_id}") from exc

    def _event_id(self, profile: dict[str, Any], requested: str | None) -> str | None:
        mode = str(profile.get("stock_mode") or "").upper()
        if mode in EVENT_MODES:
            return requested or self.default_event_id
        return None

    def _bundle_key(self, profile: dict[str, Any], event_id: str | None = None) -> str:
        entity_id = str(profile["entity_id"])
        if event_id:
            return f"{entity_id}__event__{event_id}"
        return entity_id

    def state_path(self, profile: dict[str, Any], event_id: str | None = None) -> Path:
        return self.state_dir / f"{safe_part(self._bundle_key(profile, event_id))}.json"

    def is_materialized(self, profile: dict[str, Any], event_id: str | None = None) -> bool:
        return self.state_path(profile, event_id).exists()

    def load_bundle(self, profile: dict[str, Any], event_id: str | None = None) -> dict[str, Any] | None:
        path = self.state_path(profile, event_id)
        return json_load(path) if path.exists() else None

    def save_bundle(self, profile: dict[str, Any], bundle: dict[str, Any], event_id: str | None = None) -> None:
        self.engine.validate_bundle(bundle)
        json_save(self.state_path(profile, event_id), bundle)

    def _seed(self, profile: dict[str, Any], event_id: str | None = None) -> str:
        seed = f"{self.world_seed}:{profile['entity_id']}"
        return f"{seed}:{event_id}" if event_id else seed

    def _generate_bundle(self, profile: dict[str, Any], requested_sources: list[str] | None, event_id: str | None) -> dict[str, Any]:
        mode = str(profile.get("stock_mode") or "").upper()
        kwargs: dict[str, Any] = {"seed": self._seed(profile, event_id), "enabled_source_codes": requested_sources}
        if mode in EVENT_MODES:
            kwargs["event_id"] = event_id or self.default_event_id
        bundle = self.bridge.generate(str(profile["entity_id"]), **kwargs)
        self.save_bundle(profile, bundle, event_id)
        return bundle

    def materialize(self, profile: dict[str, Any], requested_sources: list[str] | None = None, requested_event_id: str | None = None) -> dict[str, Any]:
        plan = plan_profile(profile)
        mode = plan["stock_mode"]
        event_id = self._event_id(profile, requested_event_id)
        if mode in DELEGATING_MODES | NO_STOCK_MODES:
            raise DemoError(HTTPStatus.CONFLICT, f"{profile['name']} does not own shelf stock", plan)
        if mode in TEMPLATE_MODES:
            raise DemoError(HTTPStatus.CONFLICT, "Chain templates need a realized branch ID before stocking", plan)
        bundle = self.load_bundle(profile, event_id)
        if bundle is None:
            bundle = self._generate_bundle(profile, requested_sources, event_id)
        return bundle

    def _source_codes_for_item(self, item_id: str) -> list[str]:
        source_map = getattr(self.engine, "source_codes_by_item", {})
        return sorted(source_map.get(item_id, set()))

    def _stock_public_row(self, row: dict[str, Any]) -> dict[str, Any]:
        item_id = str(row["item_id"])
        item = self.engine.items_by_id.get(item_id, {})
        return {"stock_id": row.get("id"), "item_id": item_id, "name": item.get("name") or item_id, "quantity": row.get("quantity"), "condition": row.get("condition"), "asking_price": row.get("asking_price"), "visibility": row.get("visibility", "public"), "status": row.get("status", "in_stock"), "assortment_role": row.get("assortment_role") or row.get("stock_reason"), "source_codes": self._source_codes_for_item(item_id)}

    def _latest_events(self, bundle: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
        rows = list(bundle.get("history", []))[-limit:]
        result = []
        for row in rows:
            item = self.engine.items_by_id.get(row.get("item_id"), {})
            result.append({"id": row.get("id"), "cycle": row.get("cycle"), "event_type": row.get("event_type"), "item_id": row.get("item_id"), "item_name": item.get("name") if item else None, "quantity_delta": row.get("quantity_delta"), "price": row.get("price"), "metadata": row.get("metadata") or {}})
        return result

    def shop_payload(self, entity_id: str, requested_sources: list[str] | None = None, requested_event_id: str | None = None, materialize: bool = True) -> dict[str, Any]:
        profile = self.profile(entity_id)
        plan = plan_profile(profile)
        mode = plan["stock_mode"]
        event_id = self._event_id(profile, requested_event_id)
        payload: dict[str, Any] = {"entity_id": entity_id, "name": profile.get("name"), "district": profile.get("district"), "parent_name": profile.get("parent_name"), "book_page": profile.get("book_page"), "source_ref": profile.get("source_ref"), "stock_mode": mode, "plan": plan, "type": profile.get("demo_type") or profile.get("primary_archetype") or mode, "tags": profile.get("demo_tags") or "", "copy": profile.get("demo_copy") or profile.get("modelling_note") or "", "modelling_note": profile.get("modelling_note") or "", "children": profile.get("demo_children") or [], "event_id": event_id, "materialized": self.is_materialized(profile, event_id), "stock": [], "state": None, "source_contract": None, "events": []}
        if mode in DELEGATING_MODES | NO_STOCK_MODES | TEMPLATE_MODES:
            return payload
        bundle = self.load_bundle(profile, event_id)
        if bundle is None and materialize:
            bundle = self._generate_bundle(profile, requested_sources, event_id)
        if bundle is None:
            return payload
        payload["materialized"] = True
        payload["stock"] = [self._stock_public_row(row) for row in bundle.get("stock", [])]
        payload["stock"].sort(key=lambda r: (r["status"] != "in_stock", r["name"].casefold()))
        state = bundle.get("state", {})
        payload["state"] = {"stock_cycle": state.get("stock_cycle", 0), "temporary_conditions": state.get("temporary_conditions", []), "incoming_count": sum(1 for row in bundle.get("stock", []) if row.get("status") == "incoming"), "assortment_count": len(bundle.get("assortment", [])), "history_count": len(bundle.get("history", []))}
        payload["source_contract"] = bundle.get("shop", {}).get("enabled_source_codes")
        payload["events"] = self._latest_events(bundle)
        return payload

    def list_shops(self, district: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for profile in self.profiles:
            if district and str(profile.get("district", "")).casefold() != district.casefold():
                continue
            event_id = self._event_id(profile, None)
            plan = plan_profile(profile)
            rows.append({"entity_id": profile["entity_id"], "name": profile.get("name"), "district": profile.get("district"), "parent_name": profile.get("parent_name"), "book_page": profile.get("book_page"), "source_ref": profile.get("source_ref"), "stock_mode": plan["stock_mode"], "action": plan["action"], "owns_stock": plan["owns_stock"], "type": profile.get("demo_type") or profile.get("primary_archetype") or plan["stock_mode"], "tags": profile.get("demo_tags") or "", "copy": profile.get("demo_copy") or profile.get("modelling_note") or "", "materialized": self.is_materialized(profile, event_id), "event_id": event_id})
        rows.sort(key=lambda r: (str(r.get("district") or "").casefold(), str(r.get("name") or "").casefold()))
        return rows

    def purchase(self, entity_id: str, item_id: str, quantity: int, requested_event_id: str | None = None) -> dict[str, Any]:
        if quantity < 1:
            raise DemoError(HTTPStatus.BAD_REQUEST, "quantity must be at least 1")
        profile = self.profile(entity_id)
        event_id = self._event_id(profile, requested_event_id)
        bundle = self.materialize(profile, requested_event_id=event_id)
        candidates = [row for row in bundle.get("stock", []) if row.get("item_id") == item_id and row.get("status") == "in_stock"]
        if not candidates:
            raise DemoError(HTTPStatus.CONFLICT, "That item is not currently in stock")
        row = candidates[0]
        current = row.get("quantity")
        if current is None:
            raise DemoError(HTTPStatus.CONFLICT, "This line is continuous/service stock and is not individually decremented")
        current = int(current)
        if current < quantity:
            raise DemoError(HTTPStatus.CONFLICT, f"Only {current} currently available")
        row["quantity"] = current - quantity
        if row["quantity"] <= 0:
            row["quantity"] = 0
            row["status"] = "sold"
        cycle = int(bundle.get("state", {}).get("stock_cycle", 0))
        event = self.engine._append_event(bundle, cycle, "sold", item_id=item_id, quantity_delta=-quantity, price=row.get("asking_price"), metadata={"surface": "vendr-live-demo", "shop_entity_id": entity_id})
        bundle.setdefault("state", {}).setdefault("last_cycle_events", []).append(event["id"])
        self.save_bundle(profile, bundle, event_id)
        return self.shop_payload(entity_id, requested_event_id=event_id, materialize=False)

    def restock(self, entity_id: str, requested_event_id: str | None = None) -> dict[str, Any]:
        profile = self.profile(entity_id)
        event_id = self._event_id(profile, requested_event_id)
        if str(profile.get("stock_mode") or "").upper() in EVENT_MODES:
            raise DemoError(HTTPStatus.CONFLICT, "Event markets do not restock; start a new event ID instead")
        bundle = self.materialize(profile, requested_event_id=event_id)
        result = self.bridge.restock(bundle)
        self.save_bundle(profile, result, event_id)
        return self.shop_payload(entity_id, requested_event_id=event_id, materialize=False)

    def add_condition(self, entity_id: str, condition_type: str, target: dict[str, Any] | None = None, requested_event_id: str | None = None) -> dict[str, Any]:
        profile = self.profile(entity_id)
        event_id = self._event_id(profile, requested_event_id)
        bundle = self.materialize(profile, requested_event_id=event_id)
        definitions = self.engine.model.get("lifecycle", {}).get("temporary_conditions", {})
        if condition_type not in definitions:
            raise DemoError(HTTPStatus.BAD_REQUEST, f"Unknown stock condition: {condition_type}")
        entry: dict[str, Any] = {"type": condition_type}
        if target:
            entry["target"] = target
        bundle.setdefault("state", {}).setdefault("temporary_conditions", []).append(entry)
        self.save_bundle(profile, bundle, event_id)
        return self.shop_payload(entity_id, requested_event_id=event_id, materialize=False)

    def clear_conditions(self, entity_id: str, requested_event_id: str | None = None) -> dict[str, Any]:
        profile = self.profile(entity_id)
        event_id = self._event_id(profile, requested_event_id)
        bundle = self.materialize(profile, requested_event_id=event_id)
        bundle.setdefault("state", {})["temporary_conditions"] = []
        self.save_bundle(profile, bundle, event_id)
        return self.shop_payload(entity_id, requested_event_id=event_id, materialize=False)

    def _matching_items(self, q: str, limit: int = 12) -> list[dict[str, Any]]:
        folded = q.casefold().strip()
        if not folded:
            return []
        rows = []
        for item in self.engine.items:
            name = str(item.get("name") or "")
            f = name.casefold()
            if folded not in f:
                continue
            rank = 0 if f == folded else (1 if f.startswith(folded) else 2)
            rows.append((rank, len(name), name, item))
        rows.sort(key=lambda x: (x[0], x[1], x[2].casefold()))
        return [row[3] for row in rows[:limit]]

    def search(self, q: str, requested_sources: list[str] | None = None, requested_event_id: str | None = None) -> dict[str, Any]:
        items = self._matching_items(q)
        shop_name_matches = [row for row in self.list_shops() if q.casefold().strip() and q.casefold().strip() in str(row.get("name") or "").casefold()]
        offers: list[dict[str, Any]] = []
        for item in items:
            item_id = str(item["id"])
            for profile in self.profiles:
                plan = plan_profile(profile)
                mode = plan["stock_mode"]
                if mode in DELEGATING_MODES | NO_STOCK_MODES | TEMPLATE_MODES:
                    continue
                event_id = self._event_id(profile, requested_event_id)
                bundle = self.load_bundle(profile, event_id)
                if bundle is not None:
                    stock_rows = [row for row in bundle.get("stock", []) if row.get("item_id") == item_id and row.get("status") == "in_stock" and (row.get("quantity") is None or int(row.get("quantity", 0)) > 0)]
                    if stock_rows:
                        row = stock_rows[0]
                        offers.append({"kind": "available", "item_id": item_id, "item_name": item.get("name"), "shop_entity_id": profile["entity_id"], "shop_name": profile.get("name"), "district": profile.get("district"), "quantity": row.get("quantity"), "asking_price": row.get("asking_price"), "visibility": row.get("visibility", "public"), "event_id": event_id, "score": None})
                    continue
                try:
                    kwargs: dict[str, Any] = {"seed": self._seed(profile, event_id), "enabled_source_codes": requested_sources}
                    if mode in EVENT_MODES:
                        kwargs["event_id"] = event_id
                    context = self.bridge.make_context(str(profile["entity_id"]), **kwargs)
                except (ValueError, KeyError):
                    continue
                if self.engine.eligible(item_id, context, special=False):
                    scored = self.engine.score(item_id, context)
                    offers.append({"kind": "plausible", "item_id": item_id, "item_name": item.get("name"), "shop_entity_id": profile["entity_id"], "shop_name": profile.get("name"), "district": profile.get("district"), "quantity": None, "asking_price": None, "visibility": None, "event_id": event_id, "score": scored.get("score")})
        offers.sort(key=lambda r: (r["kind"] != "available", -(r["score"] or 0), str(r["shop_name"]).casefold()))
        return {"query": q, "items": [{"item_id": row["id"], "name": row.get("name")} for row in items], "shop_name_matches": shop_name_matches[:10], "offers": offers[:40], "note": "Plausible results are scored without materializing unopened shop inventories; opening a shop creates/persists its actual assortment."}

    def reset(self) -> int:
        count = 0
        for path in self.state_dir.glob("*.json"):
            path.unlink()
            count += 1
        return count
