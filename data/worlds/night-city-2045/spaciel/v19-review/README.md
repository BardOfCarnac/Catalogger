# LATEST — OUTSKIRTS 20 BOOK-MAP ALIGNMENT (31 October 2026)

**Use these newest files for the Outskirts.** They supersede the earlier 31-marker *inverse-distance interpolation* experiment, which improperly pulled four east-of-frame book locations back inside the atlas.

- **[Outskirts 20 book-map aligned GeoJSON](spaciel_v19_outskirts_20_book_aligned_review.geojson)** — 20 original markers mapped by direct image-frame resizing (5,175×7,966 book master to 3,304×5,100 V19 atlas), then inverse V19 atlas UV transform into planar world X/Z.
- **[Combined approved 525 + aligned Outskirts 20 GeoJSON](spaciel_v19_approved525_plus_outskirts20_review545.geojson)** — 545 markers, existing 525 **unchanged**, new 20 carried as a separate layer with source and status.
- **[Outskirts QA and coordinates](spaciel_v19_outskirts_20_book_aligned_qa.json)** — all 20 locations with book source pages, map positions, terrain positions, and boundaries.

Book-to-atlas frame agreement is supported by visible matching coastline and road landmarks and the seven independently matched screenshot sourcebook dots; **a full pixel-level raster registration has not yet been run**, so review placement on the V19 image before promoting to the production database.

**16 new Outskirts points lie inside the V19 atlas bitmap; 4 lie beyond its eastern edge: Ingalls Farm, NorCal Marshal Station, Pol-Bud Cement Factory, Sunshine Motel. All 20 are still inside the modelled V19 terrain-grid extent.** They must not be clamped into the bitmap.

Old files `spaciel_v19_hot_zone_outskirts_31_review.geojson` and `spaciel_v19_approved525_plus_book31_review556.geojson` are **superseded for their Outskirts coordinate predictions**. The 11 Hot Zone locations remain separately staged, not included in the 545 production-candidate review. The 52 Playland attractions remain untouched.

No existing approved coordinates were moved. No Supabase/main branch changes. No terrain heights have yet been sampled for the new 20.

---

# Latest: 31 sourcebook locations staged (31 October 2026)

**Progress:** The 525 visually accepted V19 locations remain untouched. Each of them has now been linked to an original book-map manifestation, including all three markers for *The Cells*. An additional **11 Hot Zone + 20 Outskirts** sourcebook markers have been recovered and independently checked against the book's PDF image-placement calibration (worst roundoff error <0.001 source-master pixel). This validates their *book* positions, **not** their final V19 on-screen placement.

**New files:**
- [Combined 556 locations](./spaciel_v19_approved525_plus_book31_review556.geojson): 525 unchanged, visible by default; 31 additional candidates, hidden by default.
- [31-marker GeoJSON](./spaciel_v19_hot_zone_outskirts_31_review.geojson): per-marker source reference, exact master coordinate, provisional V19 prediction, alternate uniform-frame prediction, uncertainty metadata.
- [31-marker QA report](./spaciel_v19_hot_zone_outskirts_31_qa.json): full verification and position diagnostic list.
- [Approved 525, all identities reconciled](./spaciel_v19_approved_525_fully_reconciled.geojson).
- [23 district calibration transforms](./spaciel_v19_district_calibration_affines.json).

**Important limitation:** The 31 new positions on V19 were predicted using spatial interpolation of corrections from nearby approved locations. The Hot Zone is bracketed by several districts; the Outskirts are often well outside existing anchor coverage and their V19 coordinates are *not* precise enough to publish as approved. The four sourcebook marker coordinates for Ingalls Farm, NorCal Marshal Station, Pol-Bud Cement Factory and Sunshine Motel lie beyond the master raster edge yet remain valid book-map registrations. Original position fields are retained.

**Remaining sourcebook group:** 52 Playland attractions, intentionally excluded from this pass.

Nothing has been written to Supabase or the main branch.

---

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
