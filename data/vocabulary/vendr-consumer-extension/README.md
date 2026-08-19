# Vend-R Consumer Extension

Editorial gap-fill vocabulary for mundane commerce in Vend-R.

This package extends the source-derived CircleofNoms consumer vocabulary without attributing newly invented categories to that source. It is **not** rules content and does not extend the canonical `VENDR-` catalogue.

## Scope

52 additional consumer concepts:

- 12 cosmetics and grooming concepts
- 13 ordinary apparel forms
- 7 consumer electronics/audio concepts
- 11 household/domestic concepts
- 5 pet-care concepts
- 4 family/childcare concepts

The package uses its own `VOC-VE-` namespace because these concepts are Vend-R editorial synthesis rather than extracted homebrew.

## Brand affinities

`brand-affinities.json` maps existing consumer-relevant Night City brands from the CircleofNoms pack's brand profiles onto the new concepts using the same conservative `direct`, `adjacent`, and `licensed_merch` vocabulary. Unlisted combinations default to `avoid`.

The mapping contains 131 explicit affinity edges across 17 existing brand/profile records and covers 49 of the 52 concepts.

Three concepts — vacuum/cleaning appliances, cookware, and crockery/dishes — intentionally have no established-brand match yet and should prefer generic, local, or generated brands.

## Files

- `concepts.json` — 52 editorial consumer concepts.
- `brand-affinities.json` — brand mappings for the new concepts.
- `provenance.json` — editorial origin and dependency notes.
- `manifest.json` — package counts and file inventory.
