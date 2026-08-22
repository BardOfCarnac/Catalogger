# Night City 2045 ontology-tail audit

This report describes the vocabulary that emerged from direct source review of the Night City 2045 Vend-R world fixtures. Rare values are not automatically errors. The purpose is to distinguish genuine special cases from accidental schema fragmentation before schema normalization and district/category gap analysis.

## Corpus after the two source-review passes

- **43 source-reviewed fixture files**
- **226 reviewed world entities**
- **103/103 original canon-named CORE_RETAIL audit profiles reviewed**
- **49/49 RETAIL_CAPABLE audit candidates represented by exact entity ID**

The machine-readable audit is produced by `scripts/audit_world_ontology.py` and written to `build/reports/night-city-2045-ontology-audit.json` during CI.

## Entity types

| entity_type | count |
|---|---:|
| service | 54 |
| hybrid | 50 |
| seller | 33 |
| local_vendor | 32 |
| container | 28 |
| event_market | 13 |
| channel | 8 |
| context | 8 |

The second review pass strengthens the earlier conclusion: the high-level type vocabulary is small and reusable. The former low-frequency `channel` and `context` types have both grown from 3 to 8, showing that they were real recurring concepts rather than accidental singletons.

`hybrid` is now the second most common type. That is useful evidence that entity type alone should not encode every aspect of commercial behavior; commerce capabilities need to be composable.

## Commercial modes

| commercial_mode | count |
|---|---:|
| service_only | 55 |
| *(none)* | 38 |
| local_wares_and_service | 31 |
| catalog_stock | 29 |
| local_wares | 29 |
| catalog_and_service | 12 |
| catalog_and_local_wares | 7 |
| distribution_channel | 5 |
| event_market | 5 |
| catalog_and_local_wares_and_service | 3 |
| context_and_service | 3 |
| local_wares_and_event | 2 |
| rotating_vendor_channel | 2 |
| catalog_and_event | 1 |
| catalog_and_local_context | 1 |
| event_container | 1 |
| event_context | 1 |
| event_stock_channel | 1 |

This remains the clearest ontology fault line. The source review created several more examples of distribution, local wares and services without needing new high-level entity types, while the residual one-off mode strings are overwhelmingly combinations of independent capabilities.

**Recommendation:** stop growing `commercial_mode` as a combinatorial enum. Treat catalogue stock, local wares, services, event commerce, distribution and context as orthogonal capabilities. Keep existing mode strings only for compatibility/editorial readability while the capability representation becomes authoritative.

## Stock policies

| stock_policy | count |
|---|---:|
| *(none)* | 170 |
| CHILDREN_ONLY | 27 |
| NO_STOCK | 12 |
| EVENT_ONLY | 11 |
| NO_STATIC_INVENTORY | 6 |

The earlier suspicion around `NO_STATIC_INVENTORY` has changed materially. It was a singleton before the RETAIL_CAPABLE review and now occurs six times because distribution and rotating-vendor structures repeatedly need to exist without pretending to own a permanent shelf.

This means the concept is real, although it may still be better represented as a property of event/channel behavior rather than as a sibling to `NO_STOCK`.

## Provenance

| provenance | count |
|---|---:|
| CANON_NAMED | 218 |
| CANON_IMPLIED | 8 |

The implied records are primarily structural helpers for source-explicit but unnamed things: rotating/concession channels, occasional events and other relationships where the source establishes the thing but does not give it a formal canonical name.

## Field usage and the specialist tail

Frequently used commerce fields now include:

- `parent_entity_id` — 113
- `services` — 106
- `local_offerings` — 76
- `stock_policy` — 56
- `stocking` — 54
- `catalogue_note` — 44
- `proprietor` — 17
- `schedule` — 17
- `event_profile` — 8
- `distribution` — 5
- `access_model` — 3
- `supply_relationships` — 3

Remaining one-use fields include `access`, `customer_pricing`, `local_context`, `proprietors`, `purchase_policy`, and `vendor_rotation`.

The earlier `access` versus `access_model` mismatch remains an obvious normalization target. The new plural `proprietors` used by Faisal’s Customs is another schema-shape question: multiple operators are a legitimate fact, but singular/plural storage should be standardized rather than allowed to drift. `customer_pricing`, `purchase_policy`, supply and rotation data still look like legitimate specialist data that should live in reusable policy/relationship objects.

## Capability signatures

The common signatures have become even more reassuring:

- parented + services — 42
- container — 23
- local wares + services — 22
- local wares + parented — 19
- catalogue stock + parented — 17
- catalogue stock — 13
- local wares — 12
- event + parented + schedule — 10
- services only — 9

The second pass also gives distribution enough examples to stop treating it as exceptional: `distribution + parented` occurs four times, in addition to other distribution combinations.

The remaining singleton signatures are interesting edge compositions rather than evidence for new classes: examples include a container with services, a standalone distribution channel, distribution plus local wares plus parentage, and a scheduled service.

## Relationship-pattern tail

Common parent-child patterns:

- container -> service: 37
- container -> local_vendor: 18
- container -> seller: 18
- container -> hybrid: 11
- hybrid -> event_market: 6
- container -> event_market: 4
- hybrid -> service: 3
- context -> channel: 2
- seller -> service: 2

Rare patterns now include:

- container -> channel — Old Ironworks Street Carts
- container -> container — Roots of the Forest
- context -> local_vendor — Piccolo
- event_market -> channel — Holliday Market rotating vendors
- event_market -> service — Doc Spindler
- hybrid -> channel — Faisal’s Customs Factory Output
- hybrid -> hybrid — Truvy’s Salon
- hybrid -> local_vendor — 80/20
- seller -> event_market — Mrs. Suzuki’s monthly Night Market
- seller -> local_vendor — Hot Dingo
- service -> channel — Jade Blossom Counterfeit Distribution
- service -> event_market — Woodchipper’s Night Market

The pattern is now clearer than before: `parent_entity_id` is carrying several meanings at once. Some links are spatial containment, but others express operation, association, service-within, distribution-from, or an event occurring at/near a persistent business.

**Recommendation:** retain `parent_entity_id` for hierarchy and compatibility, but add typed relationships such as `contained_in`, `appears_at`, `operated_by`, `service_point_for`, `distribution_from`, `market_event_at`, `associated_with` and `supplies`. This should happen before the graph is expanded with inferred/original businesses.

## Audit-decision vocabulary

The audit-decision tail has grown substantially because every source-review correction records what happened. That is useful editorial provenance but it is not runtime ontology.

Do not turn the exact strings into an application enum. If machine analysis is required, normalize them into a small `review_action` vocabulary such as CONFIRM / NARROW / LOCALIZE / SPLIT / CORRECT / PROMOTE / RECOVER / REMOVE / DOWNGRADE / REHOME, with structured modifiers for category gates, page corrections, event splits, local-stock substitution, price ceilings and similar details.

## What the RETAIL_CAPABLE pass taught us

The old audit contained 49 RETAIL_CAPABLE candidates. Six were already present in reviewed fixtures and the remaining 43 were directly reviewed. Those 43 candidate IDs expanded into 57 entities after children, events and channels were separated, but the whole pass produced only six new catalogue-stock entities — five candidate businesses plus the recovered child shop 2A.

This is strong evidence for the modelling direction:

- a commercial cue is not the same thing as a shop;
- a named place may contain commerce without owning stock itself;
- source-local wares are often more accurate than generic generated stock;
- event commerce and distribution channels deserve first-class representation;
- persistent businesses, temporary markets and supply relationships should be distinct graph objects/edges.

## Structural conclusions

The long tail does **not** suggest dozens of fundamentally different commercial entity types. It suggests a small set of world objects currently described through several overlapping labels and ad-hoc fields.

The next normalization should therefore separate:

1. **World/spatial identity** — place/container, seller/vendor, service, event, organization/channel, context/reference.
2. **Commerce capabilities** — catalogue stock, local wares, service, event commerce, distribution.
3. **Stock policy** — ordinary/direct, children-only, event-only, no-stock/no-static behavior.
4. **Typed relationships** — containment separated from association, operation, appearance, supply and event location.
5. **Access/schedule/pricing/supply** — reusable policy objects instead of one-off top-level schema growth.
6. **Audit history** — editorial provenance structurally separate from runtime ontology.

No migration should be performed merely because a value is rare. The completed source-review corpus is now large enough to design the normalized schema from observed cases rather than speculation.
