-- Vend-R persistent shop/state schema
-- Shop identity is stable. Stock and shop state are mutable.

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

create table if not exists stock (
  id uuid primary key,
  shop_id uuid not null references shops(id) on delete cascade,
  item_id text not null references items(id),
  quantity integer not null default 1 check (quantity >= 0),
  condition text,
  asking_price numeric,
  price_modifier numeric not null default 1,
  visibility text not null default 'public' check (visibility in ('public','ask','hidden')),
  status text not null default 'in_stock' check (status in ('in_stock','reserved','sold','incoming')),
  added_cycle integer,
  stock_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists stock_shop_idx on stock(shop_id);
create index if not exists stock_item_idx on stock(item_id);

create table if not exists shop_state (
  shop_id uuid primary key references shops(id) on delete cascade,
  stock_cycle integer not null default 0,
  last_restocked timestamptz,
  next_restock timestamptz,
  cash_on_hand numeric,
  temporary_conditions jsonb not null default '[]'::jsonb,
  generation_state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists stock_history (
  id bigserial primary key,
  shop_id uuid not null references shops(id) on delete cascade,
  stock_id uuid,
  item_id text references items(id),
  event_type text not null,
  quantity_delta integer,
  price numeric,
  metadata jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

create index if not exists stock_history_shop_time_idx on stock_history(shop_id, occurred_at desc);
