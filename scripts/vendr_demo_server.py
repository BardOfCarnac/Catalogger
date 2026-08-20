#!/usr/bin/env python3
"""Tiny same-origin HTTP/static server for the connected Vend-R demo."""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from night_city_stock import load_runtime
from vendr_demo_backend import (
    DEFAULT_PROFILES,
    DEFAULT_STATE,
    DEFAULT_WEB,
    DemoError,
    VendRDemoBackend,
    query_one,
    source_codes,
)

class Handler(BaseHTTPRequestHandler):
    server_version = "VendRDemo/0.1"

    @property
    def app(self) -> "VendRHTTPServer":
        return self.server  # type: ignore[return-value]

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[vend-r] " + (fmt % args) + "\n")

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise DemoError(HTTPStatus.BAD_REQUEST, "Invalid JSON request body") from exc
        if not isinstance(data, dict):
            raise DemoError(HTTPStatus.BAD_REQUEST, "JSON request body must be an object")
        return data

    def _route_parts(self, path: str) -> list[str]:
        return [unquote(part) for part in path.split("/") if part]

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        candidate = (self.app.web_root / relative).resolve()
        try:
            candidate.relative_to(self.app.web_root.resolve())
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.exists() or not candidate.is_file():
            candidate = self.app.web_root / "index.html"
        data = candidate.read_bytes()
        ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype in {"application/javascript", "application/json"} else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                self._json(HTTPStatus.OK, {"ok": True, "service": "vend-r-live-demo", "catalog_items": len(self.app.backend.engine.items), "profiles": len(self.app.backend.profiles), "state_dir": str(self.app.backend.state_dir)})
                return
            if parsed.path == "/api/shops":
                self._json(HTTPStatus.OK, {"shops": self.app.backend.list_shops(query_one(query, "district"))})
                return
            if parsed.path == "/api/search":
                q = query_one(query, "q", "") or ""
                self._json(HTTPStatus.OK, self.app.backend.search(q, requested_sources=source_codes(query_one(query, "sources")), requested_event_id=query_one(query, "event_id")))
                return
            parts = self._route_parts(parsed.path)
            if len(parts) == 3 and parts[:2] == ["api", "shops"]:
                entity_id = parts[2]
                payload = self.app.backend.shop_payload(entity_id, requested_sources=source_codes(query_one(query, "sources")), requested_event_id=query_one(query, "event_id"), materialize=(query_one(query, "materialize", "1") != "0"))
                self._json(HTTPStatus.OK, payload)
                return
            self._serve_static(parsed.path)
        except DemoError as exc:
            self._json(exc.status, {"error": exc.message, "details": exc.details})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "type": type(exc).__name__})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        parts = self._route_parts(parsed.path)
        try:
            if parsed.path == "/api/reset":
                count = self.app.backend.reset()
                self._json(HTTPStatus.OK, {"ok": True, "deleted_state_files": count})
                return
            if len(parts) == 4 and parts[:2] == ["api", "shops"]:
                entity_id, action = parts[2], parts[3]
                body = self._read_json()
                event_id = str(body.get("event_id") or query_one(query, "event_id") or "") or None
                if action == "purchase":
                    item_id = str(body.get("item_id") or "")
                    if not item_id:
                        raise DemoError(HTTPStatus.BAD_REQUEST, "item_id is required")
                    quantity = int(body.get("quantity") or 1)
                    self._json(HTTPStatus.OK, self.app.backend.purchase(entity_id, item_id, quantity, event_id))
                    return
                if action == "restock":
                    self._json(HTTPStatus.OK, self.app.backend.restock(entity_id, event_id))
                    return
                if action == "conditions":
                    kind = str(body.get("type") or "")
                    if not kind:
                        raise DemoError(HTTPStatus.BAD_REQUEST, "condition type is required")
                    target = body.get("target") if isinstance(body.get("target"), dict) else None
                    self._json(HTTPStatus.OK, self.app.backend.add_condition(entity_id, kind, target, event_id))
                    return
                if action == "clear-conditions":
                    self._json(HTTPStatus.OK, self.app.backend.clear_conditions(entity_id, event_id))
                    return
            raise DemoError(HTTPStatus.NOT_FOUND, "Unknown API route")
        except DemoError as exc:
            self._json(exc.status, {"error": exc.message, "details": exc.details})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "type": type(exc).__name__})


class VendRHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type[Handler], backend: VendRDemoBackend, web_root: Path) -> None:
        super().__init__(server_address, handler)
        self.backend = backend
        self.web_root = web_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the connected Vend-R / Catalogger vertical slice")
    parser.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    parser.add_argument("--web", default=str(DEFAULT_WEB))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE))
    parser.add_argument("--seed", default="vendr-demo-world-01")
    parser.add_argument("--event-id", default="rc-demo-night-01")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    profiles_path = Path(args.profiles).resolve()
    web_root = Path(args.web).resolve()
    state_dir = Path(args.state_dir).resolve()
    if not profiles_path.exists():
        raise SystemExit(f"Profile file not found: {profiles_path}")
    if not web_root.exists():
        raise SystemExit(f"Web root not found: {web_root}")
    bridge = load_runtime(profiles_path)
    backend = VendRDemoBackend(bridge, profiles_path, state_dir, args.seed, args.event_id)
    server = VendRHTTPServer((args.host, args.port), Handler, backend, web_root)
    print(f"Vend-R live demo: http://{args.host}:{args.port}/")
    print(f"Profiles: {profiles_path}")
    print(f"Persistent demo state: {state_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Vend-R demo.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
