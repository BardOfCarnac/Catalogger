# Connected Vend-R demo API

The browser receives presentation-friendly rows; the persisted Catalogger bundle remains server-side under `build/vendr-demo-state/`.

## Read

- `GET /api/health`
- `GET /api/shops`
- `GET /api/shops/<entity_id>` — materializes an unopened stock-owning seller once, then reads the saved bundle on later requests.
- `GET /api/search?q=Agent` — returns live offers from materialized shops and plausible scored sellers from unopened shops without materializing them.

Aggregate/container places return their location plan and child IDs without creating a fake parent inventory.

## Mutate world state

`POST /api/shops/<entity_id>/purchase`

```json
{"item_id":"VENDR-0001","quantity":1}
```

The current stock row is decremented and a `sold` lifecycle event is appended. The persistent assortment is not regenerated.

`POST /api/shops/<entity_id>/restock` advances the saved lifecycle one stock cycle. Event-market bundles reject this operation; a new event ID represents a new market event.

`POST /api/shops/<entity_id>/conditions` accepts one of the temporary supply conditions already controlled by Catalogger, such as `shortage`, `surplus`, `disrupted_supply`, `fresh_delivery`, `liquidation`, or `hot_merchandise`.

`POST /api/shops/<entity_id>/clear-conditions` clears temporary conditions.

`POST /api/reset` clears only the local demo-world bundle files.

This API is a vertical-slice seam, not the eventual public/authenticated campaign API. The saved JSON maps onto Catalogger's documented shop / assortment / stock / state / history model for later PostgreSQL/Supabase hosting.
