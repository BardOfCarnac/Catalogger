#!/usr/bin/env python3
"""Compare v0.2 RETAIL_CAPABLE audit candidates with reviewed world fixtures."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from world_fixture import normalize_document

ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = ROOT / "data" / "worlds" / "night-city-2045"
CANDIDATE_PATH = WORLD_DIR / "retail-capable-candidates.v0.2.json"


def reviewed_entities() -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for path in sorted(WORLD_DIR.glob("*.v1.json")):
        doc = normalize_document(json.loads(path.read_text(encoding="utf-8")))
        if doc.get("fixture_status") != "source_reviewed":
            continue
        for entity in doc["entities"]:
            row = dict(entity)
            row["fixture_file"] = path.name
            entities.append(row)
    return entities


def main() -> None:
    candidate_doc = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidates = candidate_doc["candidates"]
    reviewed = reviewed_entities()
    by_id = {row["entity_id"]: row for row in reviewed}
    by_name_district: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in reviewed:
        by_name_district.setdefault((row.get("name", ""), row.get("district", "")), []).append(row)

    exact = []
    renamed = []
    missing = []
    for candidate in candidates:
        match = by_id.get(candidate["entity_id"])
        if match:
            exact.append((candidate, match))
            continue
        same = by_name_district.get((candidate["name"], candidate["district"]), [])
        if same:
            renamed.append((candidate, same))
        else:
            missing.append(candidate)

    print(
        f"RETAIL_CAPABLE coverage: candidates={len(candidates)} exact_reviewed={len(exact)} "
        f"same_name_reviewed={len(renamed)} not_yet_represented={len(missing)}"
    )

    print("\n## Already represented by exact entity_id")
    for candidate, match in exact:
        print(
            f"{candidate['district']} p.{candidate['book_page']} | {candidate['name']} | "
            f"{match['entity_type']} | {match['fixture_file']}"
        )

    print("\n## Same name/district but different entity_id")
    for candidate, matches in renamed:
        detail = ", ".join(f"{m['entity_id']} ({m['fixture_file']})" for m in matches)
        print(f"{candidate['district']} p.{candidate['book_page']} | {candidate['name']} | {detail}")

    print("\n## Not yet represented")
    counts = Counter(row["district"] for row in missing)
    for district, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{district}: {count}")
    for candidate in sorted(missing, key=lambda row: (row["district"], row["book_page"], row["name"])):
        print(
            f"{candidate['district']} p.{candidate['book_page']} | {candidate['name']} | "
            f"{candidate['confidence']} | {candidate['evidence_basis']}"
        )


if __name__ == "__main__":
    main()
