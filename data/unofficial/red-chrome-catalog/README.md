# The RED Chrome Catalog — unofficial staging pack

This directory stages catalogue/reference data extracted from the user-supplied RTF of **The RED Chrome Catalog** by Dusk. The source identifies itself as unofficial/homebrew content and not approved or endorsed by R. Talsorian Games.

It is intentionally **not merged into the canonical RTG v1.24 shards** while the main official set is still being curated. Provisional `RCC-` IDs are local to this source pack and can later be mapped to final `VENDR-` IDs by an import/materialization step.

## Contents

- `source.json` — provenance, source type, namespace, and pack counts.
- `items.part01.json` … `items.part04.json` — 84 genuinely new staged products: 73 main entries and 11 separately purchasable embedded SKUs.
- `manifest.json` — part list, row counts, and checksums for the staged item files.
- `manufacturers.json` — one new manufacturer candidate plus explicit aliases to existing Catalogger manufacturers.
- `relationships.json` — compatibility/add-on links and four cases deliberately not imported as new canonical products.

## Deliberate exclusions / resolutions

- **Eagletech “Scorpion” Repeating Crossbow** is retained as an alternate-source version of the existing official Eagletech Scorpion rather than a second canonical identity.
- **EMP-4X extra battery packs** point to the existing `Battery Pack` product.
- **Pursuit Security replacement nets** point to the existing `Net Launcher Net` product.
- **Spare Parachute** is represented as a 50eb add-on price on `Parachute`, not another item identity.

The target official IDs in those cross-source relationships are intentionally left unresolved until the main official catalogue stabilizes.
