# Spaciel — one-line location bubble descriptions

## Display

Spaciel's location bubble should show the location name, existing icon/category styling, and **only one optional short description**. Do not put the full Vend-R blurb, inventory, commercial tags, or a missing-data placeholder in the compact bubble.

## Single shared source

- Join on the stable **entity_id** of the location. Never fuzzy-match names, district, page number or coordinates.
- Vend-R remains the editing authority for merchant descriptions; Spaciel reads the same field directly or consumes a regenerated, **read-only** export.
- For the saved Night City 2045 v1.3 snapshot, prefer **stock_profiles.short_description**. The copies held in places.short_description are different older drafts; do not silently merge them.
- For non-merchant locations, the same short_description field should belong to the shared place entity, not a fabricated shop record.
- Copy alone never creates a pin. Chain templates, reference entities and mobile/distributed markets still need spatial eligibility and registration.

## Copy and fallback rules

- Aim for 8–15 words in a single sentence. Say what is distinctive about the location; avoid generic boilerplate.
- Do not infer opening hours, inventories, services or map coordinates from the copy.
- When short_description is null or absent, simply omit that line. Keep the name and category visible.
- Keep source references, editorial status and provenance in the data layer, not in this small bubble.
- Descriptions should be original factual summaries, not pasted sourcebook prose.

## Integration checks

1. Uniqueness check every entity_id, and report unmatched map pins; no name fallback.
2. Verify the actual Spaciel point IDs against the 528 canonical mapped entries before switching on the copy layer.
3. Do not touch pin coordinates, placement, icon type/colour, roads, terrain or clustering as part of this work.
4. Test missing copy and long copy on mobile and desktop.
5. Future edits flow from Vend-R to a shared feed and into Spaciel, never back from a Spaciel-authored duplicate.

## Source snapshot audit — not live production

The saved Vend-R v1.3 dataset has **714** place entities and **150** shop profiles. Of the profiles, **144** match place entity IDs and have short copy; **6** are global references/templates. The overlapping 144 pairs of place-copy and shop-profile-copy are **all different drafts**. In the MAPPED_528 subset, **76** locations have shop-profile short copy and **452** have no prepared short description.

The accessible Spaciel GitHub repository currently does not contain the operating map icon/coordinate feed, and the ShopKeep Supabase project was inactive at audit. This document is preparation, **not** a claim of deployed popup integration.
