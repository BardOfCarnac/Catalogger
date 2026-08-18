# Night City 2045 RETAIL_CAPABLE triage

This is the mechanical first pass over the v0.2 commercial audit's `RETAIL_CAPABLE` classification. It is **not** a source-review verdict and must not be used to generate persistent stock by itself.

## Coverage against the reviewed world layer

The v0.2 audit contains **49 RETAIL_CAPABLE candidates**:

- 6 are already represented by exact entity ID in source-reviewed fixtures.
- 43 are not yet represented.
- 0 currently match only by same-name/different-ID fallback.

Already represented:

| Candidate | District | p. | Reviewed as |
|---|---|---:|---|
| Continental Brands Office | Downtown | 82 | container |
| SK Securities | Heywood Docks | 243 | context |
| The Little Red Book | Little China | 99 | service |
| Canalside Plaza | New Westbrook | 214 | container |
| Honest Hiro's Used Cars | Old Japantown | 131 | local_vendor |
| Dream Forest Development | Pacifica Playground | 278 | container |

This is a useful warning about the old classification. Five of the six previously encountered `RETAIL_CAPABLE` rows did **not** resolve into ordinary shelf-stock shops. Source review may turn a candidate into a container, service, context record, local-only seller, event, child business, or no Vend-R commerce at all.

## Remaining queue by district

| District | remaining |
|---|---:|
| Port of Night City | 5 |
| South Night City | 4 |
| Watson Development | 4 |
| Downtown | 3 |
| Kabuki | 3 |
| Old Combat Zone | 3 |
| Old Japantown | 3 |
| Pacifica Playground | 3 |
| The Glen | 3 |
| Charter Hill | 2 |
| Little Europe | 2 |
| Upper Marina | 2 |
| Heywood Docks | 1 |
| Heywood Industrial Zone | 1 |
| Little China | 1 |
| New Westbrook | 1 |
| Playland by the Sea Lands | 1 |
| Rancho Coronado | 1 |

## The 43 not-yet-represented candidates

| District | p. | Candidate | Audit evidence |
|---|---:|---|---|
| Charter Hill | 227 | DRGS 247 | Flashmap listing |
| Charter Hill | 229 | Your Next Big Crèche | Explicit retail language in entry |
| Downtown | 84 | Gilded Phoenix Arcade | Explicit retail language in entry |
| Downtown | 85 | Guns & Dolls | Flashmap listing |
| Downtown | 85 | Jade Blossom Spa | Explicit retail language in entry |
| Heywood Docks | 243 | Warehouse 13 | Explicit retail language in entry |
| Heywood Industrial Zone | 262 | Ziggurat Warehouses | Explicit retail language in entry |
| Kabuki | 202 | Delphi X | Flashmap listing |
| Kabuki | 203 | Houou | Flashmap listing |
| Kabuki | 203 | Matsura Food Products | Explicit retail language in entry |
| Little China | 98 | Ling Po Imports | Named business embedded inside parent location |
| Little Europe | 57 | Chopper's | Flashmap listing |
| Little Europe | 62 | Short Circuit | Flashmap listing |
| New Westbrook | 218 | Rocklin Augmentics Campus | Flashmap listing |
| Old Combat Zone | 169 | Flasher's Corner | Explicit retail language in entry |
| Old Combat Zone | 169 | Jesse James' Kosher Deli | Flashmap listing |
| Old Combat Zone | 171 | The Underground | Explicit retail language in entry |
| Old Japantown | 130 | The Cutting Edge | Flashmap listing |
| Old Japantown | 132 | Lovely Drone Heroes Café | Flashmap listing |
| Old Japantown | 133 | Neo Galaxy Cards and Comics | Explicit retail language in entry |
| Pacifica Playground | 276 | The Ascension | Flashmap listing |
| Pacifica Playground | 282 | The XX (The Twenty) | Explicit retail language in entry |
| Pacifica Playground | 282 | Volkodav Racetrack | Flashmap listing |
| Playland by the Sea Lands | 306 | Classique Corsets | Explicit retail language in entry |
| Port of Night City | 150 | The Amber Room | Flashmap listing |
| Port of Night City | 154 | Maritime Supply | Explicit retail language in entry |
| Port of Night City | 154 | Medical Technologies | Flashmap listing |
| Port of Night City | 155 | Rusty's Dive Shack | Flashmap listing |
| Port of Night City | 155 | The Yard | Explicit retail language in entry |
| Rancho Coronado | 289 | The Henhouse | Explicit retail language in entry |
| South Night City | 140 | The Boneyard | Explicit retail language in entry |
| South Night City | 142 | GunMart | Explicit retail language in entry |
| South Night City | 144 | MindNutz Lover | Flashmap listing |
| South Night City | 144 | Savage Docs | Flashmap listing |
| The Glen | 116 | Air | Flashmap listing |
| The Glen | 121 | Hall of Justice | Explicit retail language in entry |
| The Glen | 122 | Merrill, Asukaga & Finch Offices | Explicit retail language in entry |
| Upper Marina | 71 | The Forge | Explicit retail language in entry |
| Upper Marina | 76 | Ziggurat Corporate Terrace | Explicit retail language in entry |
| Watson Development | 188 | Faisal's Customs | Explicit retail language in entry |
| Watson Development | 192 | Old Black Rum Pub | Flashmap listing |
| Watson Development | 193 | Red Oktober | Flashmap listing |
| Watson Development | 195 | Whammer Arena | Explicit retail language in entry |

## Review rule

Each candidate should pass through the same gate as the completed CORE_RETAIL census:

1. Read the source entry directly.
2. Decide whether the named thing is actually a seller, a containing place, a service/hospitality business, a market/event, an organization/channel, or context only.
3. Recover named child outlets/services when the source supports them.
4. Use catalogue stock only when Catalogger represents the actual merchandise cleanly.
5. Keep source-specific wares local when a generic assortment would invent the wrong stock.
6. Do not infer categories merely because the old audit scanner did.

Only after this 43-record pass should district/category gap analysis be treated as evidence for canon-implied or Vend-R-original businesses.
