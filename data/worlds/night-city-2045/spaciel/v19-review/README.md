# Spaciel V19 — POI registration staging (31 October 2026)

**Status: isolated review branch. No changes to Supabase, the main branch, or the working Spaciel viewer.**

## What is safe to use now

- `spaciel_v19_approved_525_identity_enriched.geojson` — the **525 positions approved in the earlier V19 visual inspection**, with their geometry and atlas positions **byte-for-byte unchanged as values**. Location IDs and original book-map metadata have been linked where possible. This is the default visual layer.
- `spaciel_v19_approved_525_unchanged.geojson` — untouched baseline copy of the original provisional data.
- `spaciel_v19_source_608_candidate_compact.geojson` — **608 original sourcebook marker manifestations** in a separate, optional **candidate** V19 layer. Do **not** substitute this for the approved 525 automatically. These features use planar `[world_x_m, world_z_m]` without height; height sampling is needed for 3D.
- `spaciel_v19_reconciliation_report.json` — record-by-record identity joins and unpaired locations.
- `spaciel_v19_icon_taxonomy_56.json` — the seven existing icon families / 56 subtypes. There is still **no verified per-location crosswalk**.

## Audited counts

| Metric | Count |
| --- | ---: |
| Previously approved visual markers | 525 |
| Recovered sourcebook marker manifestations | 608 |
| Exact on the *original PDF master map* | 556 |
| Approximate Playland placement on the master | 52 |
| Proposed source-to-approved one-to-one joins | 522 |
| Exact matching catalogue IDs | 469 |
| Further exact marker/name or unique-name joins (provisional) | 53 |
| Unpaired sourcebook markers | 86 |
| Unpaired approved legacy markers | 3 |
| Existing versus recovered ID discrepancies retained for review | 10 |
| Approved coordinate changes | 0 |

Important: the 608 source markers include repeated entity IDs representing distinct map manifestations; these must not be collapsed. Duplicate source IDs: `NC2045-LOC-UNIVERSITY-DISTRICT-108-THE-CELLS` (3); `NC2045-LOC-EXECUTIVE-ZONE-234-THE-ESTATES` (12).

The recovered source candidates differ significantly from the older approved dataset. The median difference among linked points is approximately **208 atlas pixels**. This means we have **not** independently validated the converted 608-point layer against the user's visual approval. Original-source-exact does not mean V19-exact.

## Integration contract

1. Load `spaciel_v19_approved_525_identity_enriched.geojson` as the default V19 markers layer.
2. Preserve every approved `geometry.coordinates`, `v19_atlas_x_px`, and `v19_atlas_y_px` value.
3. Maintain `properties.place_id` separately from `properties.recovered_source_place_id`. The latter is not an approved replacement when an identity conflict is flagged.
4. Use generic fallback markers while icon family/subtype IDs are null. The 56-subtype taxonomy file is a classification schema, not a completed assignment map.
5. The 608 source candidates may be toggled on for comparison. Do not move approved pins or enable source-only candidates by default.
6. Only accept candidate source locations after visual alignment, identity check, and V19 terrain-height sampling.
7. Road-graph snapping may establish a routing access point, but **must not relocate the display marker**.

## QA exceptions

The source-only candidates are concentrated in: Playland by the Sea Lands (52), Outskirts (20), The Hot Zone (11), University District (3).

Three older legacy records called *The Cells* remain unpaired because the previously published 525 set contains three duplicates with ambiguous marker identifiers. The source also contains multiple manifestations for *The Cells* and *The Estates*.

No subtype assignments, database updates, live-site modifications, or irreversible merges were performed.
