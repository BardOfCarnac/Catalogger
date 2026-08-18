# Night City 2045 ontology-tail audit

This report describes the vocabulary that emerged from direct source review of the Night City 2045 Vend-R world fixtures. It is descriptive first: rare values are not automatically errors. The purpose is to distinguish genuine special cases from accidental schema fragmentation before the RETAIL_CAPABLE promotion and gap-analysis phase.

## Corpus

- 25 source-reviewed fixture files
- 169 reviewed world entities
- 103/103 original canon-named CORE_RETAIL audit profiles source-reviewed

The machine-readable audit is produced by `scripts/audit_world_ontology.py` and written to `build/reports/night-city-2045-ontology-audit.json` during CI.

## Entity types

| entity_type | count |
|---|---:|
| service | 42 |
| seller | 31 |
| hybrid | 27 |
| local_vendor | 27 |
| container | 25 |
| event_market | 11 |
| channel | 3 |
| context | 3 |

**Reading:** the high-level type vocabulary is not suffering from singleton proliferation. The smallest types (`channel`, `context`) still occur three times each. The suspicious part is instead semantic overlap: `hybrid` is a common catch-all, while `seller` versus `local_vendor` partly reflects whether Catalogger can model the stock rather than a different kind of in-world entity.

## Commercial modes

| commercial_mode | count |
|---|---:|
| service_only | 42 |
| *(none)* | 32 |
| catalog_stock | 27 |
| local_wares | 25 |
| local_wares_and_service | 12 |
| catalog_and_service | 9 |
| catalog_and_local_wares | 6 |
| catalog_and_local_wares_and_service | 3 |
| event_market | 3 |
| local_wares_and_event | 2 |
| catalog_and_event | 1 |
| catalog_and_local_context | 1 |
| context_and_service | 1 |
| distribution_channel | 1 |
| event_container | 1 |
| event_context | 1 |
| event_stock_channel | 1 |
| rotating_vendor_channel | 1 |

This is the clearest ontology fault line. Eight mode names are singletons and a ninth occurs only twice. Most are combinations of independent capabilities rather than genuinely different entity classes.

**Recommendation:** stop growing `commercial_mode` as a combinatorial enum. Treat the useful primitives as orthogonal capabilities: catalogue stock, local wares, services, event behaviour, distribution, and context-only state. Existing mode strings can remain as compatibility/editorial labels while a capability representation becomes authoritative.

## Stock policies

| stock_policy | count |
|---|---:|
| *(none)* | 127 |
| CHILDREN_ONLY | 24 |
| EVENT_ONLY | 9 |
| NO_STOCK | 8 |
| NO_STATIC_INVENTORY | 1 |

`CHILDREN_ONLY`, `EVENT_ONLY`, and `NO_STOCK` have clear recurring meanings. `NO_STATIC_INVENTORY` occurs only for Old Ironworks Street Carts and substantially overlaps the idea already expressed by rotating/event/channel behaviour.

**Recommendation:** review `NO_STATIC_INVENTORY` for folding into channel/event behaviour rather than keeping a one-off stock-policy value.

## Provenance

| provenance | count |
|---|---:|
| CANON_NAMED | 166 |
| CANON_IMPLIED | 3 |

The reviewed corpus is deliberately overwhelmingly canon-named. The three implied records are structural helpers rather than evidence that the source-review pass has started inventing ordinary businesses.

## Audit-decision vocabulary

There are many one-off audit-decision strings. The recurrent values are useful (`CONFIRMED_BUT_NARROWED` 19, `CONFIRMED_CONTAINER` 16, `CORRECT_TO_LOCAL_WARES` 8, `PRESERVE_NAMED_SERVICE_CHILD` 8, `CONFIRMED_SERVICE_ONLY` 7), but the tail contains dozens of exact one-use phrases such as hard-brand-gate variants, page-correction variants, split-event variants, recovered-source variants, and source-localization variants.

This is not a world-ontology problem: the strings are an editorial history of how each audit row was corrected.

**Recommendation:** preserve the current strings for provenance, but do not make them a controlled application enum. If machine analysis is needed, add structured fields such as:

- `review_action`: CONFIRM / NARROW / LOCALIZE / SPLIT / CORRECT / PROMOTE / RECOVER / REMOVE / DOWNGRADE / REHOME
- optional modifiers: page correction, hard category gate, brand/manufacturer gate, price ceiling, service split, event split, local-stock substitution, etc.

## Rare top-level fields

Fields occurring once or twice:

- `access` - 1 (Dream Forest Development)
- `customer_pricing` - 1 (Smithery)
- `distribution` - 1 (Northern Light Supplies)
- `local_context` - 1 (Snack & Shack)
- `purchase_policy` - 1 (Baskin Books)
- `supply_relationships` - 1 (Honest Hiro's Used Cars)
- `vendor_rotation` - 1 (Old Ironworks Street Carts)
- `access_model` - 2 (Post Exchange; Mrs. Suzuki's monthly Night Market)

The obvious schema inconsistency is `access` versus `access_model`; those should converge. The others look like legitimate specialist data, but they should probably live in typed capability/relationship objects rather than each becoming a new universal top-level field.

## Capability signatures

The common signatures are ordinary and reassuring:

- parented + services - 38
- container - 21
- local wares + parented - 18
- catalogue stock + parented - 17
- catalogue stock - 11
- local wares - 9
- event + parented + schedule - 8
- catalogue stock + parented + services - 6

Singleton signatures expose the interesting cases rather than a large population of unrelated object types. Examples include:

- Holliday Market rotating vendors - catalogue stock + distribution + parented
- Northern Light Supplies - distribution + explicit no stock
- Old Ironworks Street Carts - distribution + parented
- Mrs. Suzuki's monthly Night Market - event + explicit no stock + parented + schedule
- Torrell and Chiang's Market Stalls - event + parented
- Holliday Market - event + services
- Nakagawa Garage Tower - services only, unparented

This supports replacing combinatorial `commercial_mode` values with capability composition.

## Relationship-pattern tail

Common parent-child patterns:

- container -> service: 35
- container -> local_vendor: 18
- container -> seller: 18
- container -> hybrid: 8
- container -> event_market: 4
- hybrid -> event_market: 4

Rare patterns:

- container -> channel: 1 - Old Ironworks Street Carts
- container -> container: 1 - Roots of the Forest
- context -> local_vendor: 1 - Piccolo
- event_market -> channel: 1 - Holliday Market rotating vendors
- event_market -> service: 1 - Doc Spindler
- hybrid -> hybrid: 1 - Truvy's Salon
- hybrid -> service: 1 - Ojo
- seller -> event_market: 1 - Mrs. Suzuki's monthly Night Market
- seller -> local_vendor: 1 - Hot Dingo
- service -> event_market: 1 - Woodchipper's Night Market
- seller -> service: 2 - Estero Bay Barber Shop; COG Credit Union

The rare relationships reveal a more important modelling issue than their low counts: `parent_entity_id` currently carries several different meanings. Some are true spatial containment, but others mean association, operation, nearby recurring event, or a permanent business embedded in a rotating market.

**Recommendation:** retain `parent_entity_id` for hierarchy/legacy compatibility, but introduce typed entity relationships (`contained_in`, `appears_at`, `operated_by`, `service_point_for`, `market_event_at`, `associated_with`, etc.) before the world graph gets much larger. Woodchipper's Garage -> Night Market and Mrs. Suzuki's Bodega -> monthly Night Market are particularly strong examples: they are associations, not literal containment.

## Structural conclusions

The long tail does **not** suggest that Vend-R has dozens of fundamentally different commercial entity types. It suggests the opposite: a fairly small set of world objects is currently being described through several combinatorial labels.

The most promising normalization is therefore:

1. **World/spatial identity** - place, outlet/vendor, event, organization/channel, context/reference.
2. **Commerce capabilities** - catalogue stock, local wares, service, event commerce, distribution.
3. **Stock policy** - direct/default, children-only, event-only, no-stock (with rotating/no-static behaviour represented by the relevant capability).
4. **Typed relationships** - containment separated from association, operation, appearance and event location.
5. **Access/schedule/pricing/supply** - reusable policy objects rather than one-off top-level schema growth.
6. **Audit history** - editorial provenance, structurally separate from the runtime ontology.

No migration should be performed merely because a value is rare. This report is the inspection list for deciding which rare cases are genuinely exceptional and which are artefacts of the current representation.
