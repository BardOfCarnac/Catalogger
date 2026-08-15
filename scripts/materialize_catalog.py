#!/usr/bin/env python3
import gzip, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "data/catalog/manifest.json").read_text(encoding="utf-8"))
OUT = ROOT / "build/data"

for table, meta in MANIFEST["tables"].items():
    rows = []
    for part in meta["parts"]:
        with gzip.open(ROOT / part["path"], "rt", encoding="utf-8") as f:
            rows.extend(json.load(f))
    assert len(rows) == meta["rows"]
    area = "audit" if table in {"index-listings", "resolution-log"} else "catalog"
    target = OUT / area / f"{table}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target.relative_to(ROOT))
