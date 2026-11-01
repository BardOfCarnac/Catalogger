SPACIEL V19 — SOURCEBOOK SHORELINE CORRECTION (1 NOV 2026)
=================================================================

WHY
The previous 3D viewer used 525 district-fitted approximate positions, of which
65 lay over water according to the authoritative V19 coastline mask.
The original 556 sourcebook coordinates were subsequently recovered and
registered onto V19 using an image-matched book-to-atlas affine.

OPEN THE CORRECTED VIEWER
1. Download this branch as a ZIP from GitHub, then extract it.
2. Go into the extracted folder to:
     prototypes/spaciel/
3. Open in Chrome:
     Spaciel_V19_556_Sourcebook_Shoreline_Corrected.html
4. IMPORTANT: Keep the adjacent folder
     Spaciel_V19_WaterFix_Assets/
   in the same directory as the HTML file. It contains 17 local JS data
   segments required to render the original terrain, coastline, roads and buildings.
5. No internet connection, database credentials, or Supabase writes are required.

WHAT HAS CHANGED
- All 556 marker identities are mapped via recovered original book positions to V19.
- Ground heights are freshly sampled from V19's 50m terrain grid.
- 17 shoreline locations are displayed at a nearby stable-land icon anchor
  (maximum visual adjustment 79m); their canonical book positions remain intact.
- Three offshore sites (The Ascension, Flotsam and 107.3 Morro Rock Radio)
  are searchable but are not drawn by default over water.
- Four Outskirts sites beyond the base atlas image are likewise searchable
  but hidden by default.
- 549 visible markers and zero visible markers classified as water.
- 525 previous approximate positions remain retained as backup coordinates.

NOT CHANGED
Original terrain/triangulation, roads, 6,884 building groups, spectrum bar,
icon categories (270 specific, 286 neutral), search, bubble interactions,
and deferred Playland attractions.

DATA AND QA
    data/worlds/night-city-2045/spaciel/v19-review/
       spaciel_v19_556_sourcebook_shoreline_corrected.geojson
       spaciel_v19_556_shoreline_fix_audit.json

The GeoJSON's geometry is always the canonical sourcebook position in
V19 planar [world_x_m, world_z_m] coordinates; display_world_* properties
supply interface-only shoreline anchor coordinates.

DEPLOYMENT STATUS
Review build only. No changes to the live Spaciel app or Supabase.
Mathematical coastline and data checks passed; a full on-device browser
render has not been independently verified yet.
