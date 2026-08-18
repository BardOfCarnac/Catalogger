# Night City 2045 RETAIL_CAPABLE source-review result

The v0.2 commercial audit contained **49 `RETAIL_CAPABLE` candidates**. This category was a discovery queue, not a canon shop taxonomy: it meant that an audit heuristic saw some plausible saleable activity and that the location deserved direct review.

The pass is now complete.

## Coverage

- **49/49 candidates represented by exact entity ID in source-reviewed fixtures**
- **0 remaining**
- **0 same-name/different-ID fallbacks**
- 6 candidates had already been encountered while source-reviewing the original CORE_RETAIL census
- the remaining 43 were reviewed directly against the purchased Night City 2045 source and modeled in 18 dedicated fixture files
- those 43 candidate reviews expanded into **57 world entities** after named children, event markets and distribution channels were separated from their parent records

The six candidates already encountered during the CORE_RETAIL pass were Continental Brands Office, SK Securities, The Little Red Book, Canalside Plaza, Honest Hiro’s Used Cars and Dream Forest Development. Five of those six had already demonstrated why `RETAIL_CAPABLE` could not be treated as “shop”: they resolved to containers, context or service structures, with Honest Hiro’s the sole straightforward vendor.

## What the remaining 43 became

The reviewed candidate records themselves resolved to:

| reviewed entity type | count |
|---|---:|
| hybrid | 20 |
| service | 8 |
| context | 5 |
| local_vendor | 4 |
| container | 3 |
| seller | 2 |
| channel | 1 |

Only **five of the 43 candidate IDs** received persistent generated Catalogger assortments: Maritime Supply, GunMart, Guns & Dolls, Matsura Food Products and The Cutting Edge. A sixth stock-bearing entity, **2A**, was recovered as a named child while reviewing Merrill, Asukaga & Finch Offices. Thus the 43-candidate review pass produced only **six catalogue-stock entities in total**.

That ratio is the central result of the exercise. Most apparent “retail” cues were better represented as source-local wares, hospitality or professional services, event commerce, logistics/distribution, containing places, or non-retail context.

## Representative corrections and recoveries

- **Port of Night City:** Rusty’s Dive Shack was corrected from a weapons-retail inference to a bar with a source-local specialty; The Yard became logistics context; Medical Technologies became irregular/local cyberware plus medical services; Maritime Supply retained a narrow generated general-equipment/fashion assortment plus source-local maritime technology.
- **South Night City:** The Boneyard became a community container; MindNutz Lover and Savage Docs became services; GunMart became an explicit weapons/ammunition/accessories megastore. The Crypt was recovered as a named child business.
- **Watson Development:** Faisal’s Customs became a source-local weapons workshop/seller with a separate factory-output distribution channel; two apparent retail rows were ordinary hospitality; Whammer Arena became a venue.
- **Downtown:** Gilded Phoenix Arcade became entertainment; Jade Blossom Spa was split from its concealed counterfeit distribution operation; Guns & Dolls retained a weapons shelf plus entertainment services.
- **Kabuki:** Delphi X became service-only; Houou retained its identity-shop activity as local wares/services; Matsura Food Products became a narrowly bounded food retailer.
- **Old Combat Zone:** Flasher’s Corner became opportunistic local trade plus information brokerage; Jesse James’ Kosher Deli became hospitality; The Underground became production/community context supplying an external retailer.
- **Old Japantown:** The Cutting Edge became a fashion boutique plus salon; Lovely Drone Heroes Café became hospitality/digital gifting; Neo Galaxy Cards and Comics remained focused source-local card/comic trade with its backroom activity separated conceptually from ordinary stock.
- **Pacifica Playground:** the Ascension, Volkodav Racetrack and the XX all resolved primarily to hospitality/entertainment; Pacifica Parties was recovered as a named child service.
- **The Glen:** Air became an oxygen bar; Hall of Justice became civic/ticketed-event context with a separate concession-vendor channel; Merrill, Asukaga & Finch became a container/service whose actual commercial children include the recovered 2A gun shop/range, Ebony Chair and Body Lotto Office.
- **Little Europe:** Chopper’s was separated from 80/20’s second-hand cyberware trade; Short Circuit was separated from the recurring 3-Piece’s Joint tech Night Market.
- **Upper Marina:** The Forge became access-controlled local salvage/refurbishment commerce; Ziggurat Corporate Terrace became housing context with Great River as its separate retail/delivery channel.
- **Heywood Docks / Industrial:** Warehouse 13 became a rental venue with a separate occasional Night Market; Ziggurat Warehouses became corporate operational storage.
- **Little China:** Ling Po Imports became an import/export channel rather than a public storefront.
- **New Westbrook:** Rocklin Augmentics Campus became a container; the Hidalgo Gallery was recovered as the public cyberware gallery/shop/install service.
- **Playland by the Sea Lands:** Classique Corsets became a focused source-local vintage-fashion vendor.
- **Rancho Coronado:** The Henhouse was corrected from former sporting-goods retail to its current roller-derby venue use.

## Review rule validated

The completed pass confirms the source-review gate used for the CORE_RETAIL census:

1. Read the source entry directly.
2. Decide what kind of world entity the named thing actually is before asking what it sells.
3. Recover named children, events and channels instead of forcing their commerce onto the parent.
4. Generate catalogue stock only where Catalogger cleanly represents the merchandise.
5. Keep source-specific, irregular, unique or condition-sensitive wares local when a generic assortment would invent the wrong business.
6. Treat flashmap and extraction classifications as discovery evidence, never as final commerce truth.

The mechanical audit `scripts/audit_retail_capable_candidates.py` now reports `candidates=49 exact_reviewed=49 same_name_reviewed=0 not_yet_represented=0` in CI.

The next useful coverage question is no longer “which RETAIL_CAPABLE rows remain?” It is **what commercial entities were never promoted into either CORE_RETAIL or RETAIL_CAPABLE at all**, followed by district/category gap analysis before any canon-implied or Vend-R-original businesses are generated.
