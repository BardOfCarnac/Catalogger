#!/usr/bin/env python3
import gzip, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = json.loads((DATA / "catalog/manifest.json").read_text(encoding="utf-8"))

def load_table(name):
    meta = MANIFEST["tables"][name]
    rows=[]
    for part in meta["parts"]:
        path=ROOT/part["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest()==part["sha256"], f"checksum mismatch: {part['path']}"
        with gzip.open(path,"rt",encoding="utf-8") as f:
            chunk=json.load(f)
        assert len(chunk)==part["rows"], f"row count mismatch: {part['path']}"
        rows.extend(chunk)
    assert len(rows)==meta["rows"], f"table row count mismatch: {name}"
    return rows

def load(rel):
    with open(DATA/rel,encoding="utf-8") as f: return json.load(f)

items=load_table("items")
classes=load_table("item-classifications")
item_sources=load_table("item-sources")
item_mfrs=load_table("item-manufacturers")
manufacturers=load("catalog/manufacturers.json")
sources=load("catalog/sources.json")
redirects=load("audit/id-redirects.json")

def unique(rows,key,label):
    vals=[r[key] for r in rows]
    assert len(vals)==len(set(vals)), f"duplicate {label}"
unique(items,"id","item IDs")
unique(manufacturers,"id","manufacturer IDs")
unique(sources,"code","source codes")
item_ids={r["id"] for r in items}; mfr_ids={r["id"] for r in manufacturers}; source_codes={r["code"] for r in sources}
for r in item_mfrs: assert r["item_id"] in item_ids and r["manufacturer_id"] in mfr_ids, r
for r in classes: assert r["item_id"] in item_ids and r["vendr_department"], r
for r in item_sources: assert r["item_id"] in item_ids and r["source_code"] in source_codes, r
for r in redirects: assert r["canonical_vendr_id"] in item_ids and r["retired_vendr_id"] not in item_ids, r
assert len(items)==1275
print(f"OK: {len(items)} items, {len(manufacturers)} manufacturers, {len(item_sources)} item-source links")
