# CircleofNoms Consumer Vocabulary

Distribution-oriented vocabulary for Vend-R derived from three **Cyberpunk RED** homebrew random tables by **u/CircleofNoms**, hosted by **Dataterm**:

- *What's in this Vendit?*
- *What's in the Box?*
- *What's in Their Pockets?*

This is **not** a rules-item supplement and does not extend the canonical `VENDR-` catalogue. It provides mundane commercial product concepts and merchandising descriptors that a shop generator can use to instantiate ordinary stock.

## Release status

**Release candidate — creator permission for Vend-R redistribution pending.**

Dataterm states that it hosts CircleofNoms' material with permission. That establishes Dataterm's hosting provenance, but it is not treated here as permission granted to Vend-R. Before public redistribution, Vend-R should record affirmative permission from the creator or another rights-holder authorized to grant it.

## Contents

- `concepts.json` — 127 normalized consumer product concepts. Vend-R assigns economy tiers to 124 of them; three highly value-dependent curiosities remain deliberately unresolved.
- `official-links.json` — 15 source outcomes that should resolve to existing official Catalogger products rather than create duplicates.
- `descriptors.json` — 23 style/form/material/condition cues suitable for merchandising variants.
- `brand-profiles.json` — conservative consumer-brand profiles and affinities against the source-derived concepts.
- `filtering.json` — audit counts and the editorial boundary used for the cleanup.
- `source.json` — creator/host/source attribution and distribution state.
- `manifest.json` — pack counts and file inventory.
- `DISTRIBUTION.md` — release boundary and permission checklist.

The source tables themselves are **not reproduced** here. The pack stores normalized Vend-R vocabulary and attribution only.

Additional concepts created by Vend-R to fill gaps identified during this audit remain in the sibling `data/vocabulary/vendr-consumer-extension/` package so they are not misattributed to CircleofNoms.

## Vend-R pricing layer

Price tiers in `concepts.json` are **Vend-R editorial metadata**, not values supplied by CircleofNoms. They use the standard RED economy ladder and assume a typical retail unit. Signed celebrity memorabilia, a personal photo collection, and jewelry/gemstones remain unresolved because a single default tier would be misleading.
