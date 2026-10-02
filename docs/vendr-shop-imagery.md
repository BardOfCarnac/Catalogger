# Vend-R shop imagery

Vend-R shop/profile pages may use a wide photographic hero strip behind the shop name.

The image system is intentionally separate from the catalogue taxonomy. A shop is assigned to a **visual family** based on what kind of photograph should represent the place, not what it sells.

Canonical mapping:

- `data/shops/night-city-2045-visual-profiles-v0.2.json`

## Image policy

- `pool`: choose a photograph from the assigned visual-family pool.
- `inherit`: template records do not get a photograph until a concrete branch/location exists.
- `none`: references, channels, or non-shop records do not get a shop hero photograph.

The v0.2 curated pass contains 150 stock profiles:\n\n- 144 pooled with explicit approved-image overrides\n- 2 inherit\n- 4 none

## Visual families

| family | profiles |
| --- | ---: |
| street-storefront | 14 |
| market-stall | 12 |
| showroom-boutique | 12 |
| food-retail | 11 |
| secondhand-clutter | 11 |
| market-complex | 10 |
| hospitality-interior | 8 |
| workshop-garage | 7 |
| large-complex | 6 |
| clinic-pharmacy | 5 |
| outdoor-camp | 5 |
| office-service | 2 |

Each family carries search-seed phrases for later Unsplash sourcing.

## Secondary image selectors

Each pooled profile also has:

- `visual_condition`: `polished`, `ordinary`, `worn`, or `rough`
- `visual_setting`: a more specific framing cue such as `food-shop`, `stall-or-booth`, `warehouse-or-import-yard`, or `clinic-or-medical-retail`

These fields guide image selection only. They are **not canonical claims** about the location.

## Stable assignment

Images should not change on every page load.

Use:\n\n1. explicit `image_override` if present;\n2. otherwise choose from the family pool with a stable hash of `entity_id`.\n\nThe curated v0.2 pass also avoids repeating the same approved photograph within a district.

Each image record should ultimately carry at least:

- image ID / provider ID
- photographer
- source URL
- family
- tags
- focal X/Y

The focal point is important because the intended use is a shallow, wide hero strip.

## Crop / presentation

The photograph should support the page rather than turn Vend-R into a glossy e-commerce site:

- use a wide shallow crop;
- place the shop name over the image;
- apply a strong tonal treatment for legibility;
- keep descriptive copy on cream where possible;
- treat photography as environmental context rather than product advertising.
