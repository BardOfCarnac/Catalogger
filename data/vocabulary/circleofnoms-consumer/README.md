# CircleofNoms Consumer Vocabulary

Staging vocabulary for Vend-R derived from three **Cyberpunk RED** random tables by **u/CircleofNoms**, hosted by Dataterm:

- *What's in this Vendit?*
- *What's in the Box?*
- *What's in Their Pockets?*

This is **not** a rules-item supplement and does not extend the canonical `VENDR-` catalogue. It provides mundane commercial product concepts and merchandising descriptors that a shop generator can use to instantiate ordinary stock.

## Contents

- `concepts.json` — 127 normalized consumer product concepts.
- `official-links.json` — 15 source outcomes that should resolve to existing official Catalogger products rather than create duplicates.
- `descriptors.json` — 23 style/form/material/condition cues suitable for merchandising variants.
- `brand-profiles.json` — 20 consumer-relevant company profiles, 7 shopper-facing product-line/IP profiles, and concept affinities (`direct`, `adjacent`, `licensed_merch`; everything else defaults to `avoid`).
- `filtering.json` — audit counts and the editorial boundary used for the cleanup.
- `source.json` — creator/host/source attribution.
- `manifest.json` — pack counts and file inventory.

The brand layer is deliberately conservative: it extends known brands only within established or adjacent product domains and records several famous corporations as restrained rather than allowing arbitrary cross-category branding.

The source tables themselves are **not reproduced** here. The pack stores normalized Vend-R vocabulary and attribution only.
