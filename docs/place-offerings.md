# Place-specific offerings

Vend-R now preserves some **place-level commercial detail** without forcing it into the
global item catalogue or into any current UI.

The first dataset is `data/places/nc2045-place-offerings.json`, audited directly from
*Night City 2045*. It currently contains 45 offerings attached to 43 stable Night City
place entity IDs.

## Why this exists

A named drink, local souvenir, venue-exclusive food item, or rental can be useful world
data without being a reusable catalogue product. Treating every such thing as a Vend-R
item would make bars and attractions behave like shops and would pollute the global
catalogue.

Each row therefore belongs first to a **place**, not to an app.

## Surface policy

- **Vend-R:** hidden by default. A place offering does not make a venue a shop.
- **Spatial:** hidden by default. Mapping a place does not require displaying its menu.
- **Limelife:** candidate consumer if Limelife grows into nightlife, venues, gigs,
  culture, reviews, or other social place-detail views.
- **Future services:** may consume the same rows without changing the source data.

## Catalogue links

`catalog_item_id` is normally null. It is populated only where the place offering is
also a reusable canonical product with its own rules identity. For example, the
Playland Lemon-Aid Rx offering points to `VENDR-1279`.

This lets a future interface say both “Lemon-Aid Rx is sold here” and “this is the
canonical Lemon-Aid Rx item” without duplicating either record.

## Provenance

The dataset stores compact index/reference facts such as offering name, price, place,
and source page. It does not reproduce sourcebook descriptive prose. Signature drinks
come from the *Night City 2045* Flashmaps index on p. 28; place pages are retained
separately for location provenance.

The data is deliberately static and source-backed. No current Vend-R or Spatial view
depends on it, so future product decisions can be made without migration pressure.
