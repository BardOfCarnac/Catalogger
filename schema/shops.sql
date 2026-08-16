-- Vend-R persistent shop/state schema
-- Shop identity is stable. Assortment is persistent. Stock and shop state are mutable.

create table if not exists shop_archetypes (
  id text primary key,
  name text not null,
  definition jsonb not null,
  version integer not null default 1,
  active boolean not null default true
);

create table if not exists shops (
  id uuid primary key,
  name text not null,
  seed text not null,
  archetype_id text references shop_archetypes(id),
  district text,
  neighbourhood text,
  address_text text,
  latitude double precision,
  longitude double precision,
  primary_trade text,
  secondary_trades text[] not null default '{}',
  speciality_tags text[] not null default '{}',
  physical_form text,
  scale text,
  market_level text,
  legitimacy text,
  supply_model text,
  condition_bias text,
  pricing_style text,
  clientele text[] not null default '{}',
  proprietor jsonb,
  reputation text,
  distinctive_trait text,
  -- Realized stocking preferences are stored with the shop so later archetype
  -- template changes do not silently mutate an existing business.
  stocking_profile jsonb not null default '{}'::jsonb,
  generated_from_version text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists shop_brand_affinities (
  shop_id uuid not null references shops(id) on delete cascade,
  manufacturer_id text not null references manufacturers(id),
  affinity numeric not null default 0,
  note text,
  primary key (shop_id, manufacturer_id)
);

create table if not exists shop_services (
  shop_id uuid not null references shops(id) on delete cascade,
  service_key text not null,
  details jsonb,
  primary key (shop_id, service_key)
);

-- A shop's persistent relationship with products. Selling out does not remove a
-- core/regular/occasional line from the business; restocking works from this table.
create table if not exists shop_assortment (
  shop_id uuid not null references shops(id) on delete cascade,
  item_id text not null references items(id),
  role text not null check (role in ('core','regular','occasional')),
  affinity_score numeric,
  score_components jsonb not null default '{}'::jsonb,
  -- NULL target/reorder means finite quantity is not meaningful (for example a
  -- continuously available service/software offering).
  target_quantity integer check (target_quantity is null or target_quantity >= 1),
  reorder_point integer check (
    reorder_point is null or (
      reorder_point >= 1 and target_quantity is not null and reorder_point <= target_quantity
    )
  ),
  introduced_cycle integer not null default 0,
  last_stocked_cycle integer,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (shop_id, item_id)
);

create index if not exists shop_assortment_shop_role_idx on shop_assortment(shop_id, role);

create table if not exists stock (
  id uuid primary key,
  shop_id uuid not null references shops(id) on delete cascade,
  item_id text not null references items(id),
  -- NULL quantity means finite count does not apply (for example a continuously
  -- available service/software offering). Physical stock remains >= 0.
  quantity integer check (quantity is null or quantity >= 0),
  condition text,
  asking_price numeric,
  price_modifier numeric not null default 1,
  visibility text not null default 'public' check (visibility in ('public','ask','hidden')),
  status text not null default 'in_stock' check (status in ('in_stock','reserved','sold','incoming')),
  assortment_role text check (assortment_role in ('core','regular','occasional','special')),
  added_cycle integer,
  stock_reason text,
  -- Lifecycle metadata carries deterministic pending-order information such as
  -- ordered_cycle / arrival_cycle without overloading the canonical item record.
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists stock_shop_idx on stock(shop_id);
create index if not exists stock_item_idx on stock(item_id);
create index if not exists stock_shop_role_idx on stock(shop_id, assortment_role);
create index if not exists stock_shop_status_idx on stock(shop_id, status);

create table if not exists shop_state (
  shop_id uuid primary key references shops(id) on delete cascade,
  stock_cycle integer not null default 0,
  last_restocked timestamptz,
  next_restock timestamptz,
  cash_on_hand numeric,
  -- Entries use the controlled stocking condition vocabulary (shortage, surplus,
  -- disrupted_supply, fresh_delivery, liquidation, hot_merchandise) and may carry
  -- optional item/department/channel/manufacturer targets.
  temporary_conditions jsonb not null default '[]'::jsonb,
  generation_state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists stock_history (
  id bigserial primary key,
  shop_id uuid not null references shops(id) on delete cascade,
  stock_id uuid,
  item_id text references items(id),
  stock_cycle integer,
  event_type text not null,
  quantity_delta integer,
  price numeric,
  metadata jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

create index if not exists stock_history_shop_time_idx on stock_history(shop_id, occurred_at desc);
create index if not exists stock_history_shop_cycle_idx on stock_history(shop_id, stock_cycle);
