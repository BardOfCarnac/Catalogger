# The RED Chrome Catalog — unofficial distribution pack

This directory contains normalized catalogue/reference data derived from **The RED Chrome Catalog** by **Dusk#1352 (/u/mitsayantan)**. It is an unofficial/homebrew source and is kept separate from Vend-R's official R. Talsorian Games datasets.

## Release status

**Release candidate — creator permission pending.**

The data has been shaped for distribution, but Vend-R should not publicly redistribute this pack until affirmative permission from the original homebrew creator is recorded in `source.json`. The original document is not bundled.

## Contents

- `source.json` — provenance, source type, namespace, distribution state, and pack counts.
- `items.part01.json` … `items.part04.json` — 84 normalized products: 73 main entries and 11 separately purchasable embedded SKUs.
- `manifest.json` — part list, row counts, checksums, and release status.
- `manufacturers.json` — one new manufacturer candidate plus explicit aliases to existing Catalogger manufacturers.
- `relationships.json` — compatibility/add-on links and four cases deliberately not imported as new canonical products.
- `DISTRIBUTION.md` — release boundary, attribution, and permission checklist.

## Distribution boundary

The pack stores indexing/reference metadata such as product name, category, price, manufacturer identity, and relationship data. It deliberately excludes the source document's descriptive rules prose and full stat blocks.

The `RCC-` namespace remains source-local. Vend-R should retain it as provenance even if imported records later receive internal canonical IDs.

## Deliberate exclusions / resolutions

- **Eagletech “Scorpion” Repeating Crossbow** is retained as an alternate-source version of the existing official Eagletech Scorpion rather than a second canonical identity.
- **EMP-4X extra battery packs** point to the existing `Battery Pack` product.
- **Pursuit Security replacement nets** point to the existing `Net Launcher Net` product.
- **Spare Parachute** is represented as a 50eb add-on price on `Parachute`, not another item identity.

The target official IDs in those cross-source relationships remain unresolved until the main official catalogue stabilizes.
