-- Vend-R / Catalogger canonical catalogue schema
-- Portable PostgreSQL; intended to be usable directly in Supabase later.

create table if not exists source_books (
  code text primary key,
  title text not null
);

create table if not exists manufacturers (
  id text primary key,
  name text not null unique
);

create table if not exists items (
  id text primary key,
  name text not null,
  display_name text not null,
  context_qualifier text,
  primary_department text,
  currency text,
  price_min numeric,
  price_max numeric,
  price_tier text,
  price_basis text,
  cost_kind text,
  cost_raw text,
  cost_parse_note text,
  source_index_page integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists item_sources (
  item_id text not null references items(id) on delete cascade,
  source_code text not null references source_books(code),
  page text,
  raw_reference text,
  primary key (item_id, source_code, page)
);

create table if not exists item_manufacturers (
  item_id text not null references items(id) on delete cascade,
  manufacturer_id text not null references manufacturers(id),
  primary key (item_id, manufacturer_id)
);

-- Source provenance plus the first-pass Vend-R classification currently attached
-- to the canonical catalogue. Commercial profiles below are derived separately.
create table if not exists item_classifications (
  item_id text not null references items(id) on delete cascade,
  source_category text not null,
  source_subcategory text,
  vendr_department text not null,
  vendr_class text,
  is_primary boolean not null default false,
  primary key (item_id, source_category, source_subcategory, vendr_department)
);

create table if not exists item_commercial_profiles (
  item_id text primary key references items(id) on delete cascade,
  product_identity text not null check (product_identity in ('generic','branded','bespoke','unique')),
  product_identity_origin text not null check (product_identity_origin in (
    'exact-curation','item-override','manufacturer','explicit-generic','trademark',
    'source-bucket','default-generic'
  )),
  product_identity_version text not null,
  department text not null,
  classification_path jsonb not null default '[]'::jsonb,
  commodity_kind text not null check (commodity_kind in (
    'durable_good','consumable','installed_good','component','vehicle',
    'software','service','subscription','property','virtual_good'
  )),
  quantity_profile text not null check (quantity_profile in (
    'singular','low_stock','normal_stock','high_stock','bulk','continuous'
  )),
  default_condition text not null check (default_condition in (
    'new','used','refurbished','damaged','salvaged','not_applicable'
  )),
  supply_profile text not null check (supply_profile in (
    'ubiquitous','regular','specialist','scarce','bespoke','unique'
  )),
  requires_item_curation boolean not null default false,
  profile_version text not null,
  taxonomy_version text not null
);

create table if not exists item_allowed_conditions (
  item_id text not null references item_commercial_profiles(item_id) on delete cascade,
  condition text not null check (condition in (
    'new','used','refurbished','damaged','salvaged','not_applicable'
  )),
  primary key (item_id, condition)
);

create table if not exists item_market_channels (
  item_id text not null references item_commercial_profiles(item_id) on delete cascade,
  channel text not null check (channel in (
    'retail','specialist','corporate','institutional','street','pawn','nomad',
    'grey_market','black_market','direct_order'
  )),
  primary key (item_id, channel)
);

create table if not exists item_secondary_departments (
  item_id text not null references item_commercial_profiles(item_id) on delete cascade,
  department text not null,
  primary key (item_id, department)
);

create table if not exists tags (
  id text not null,
  tag_type text not null check (tag_type in ('audience','use','character')),
  label text not null,
  description text,
  primary key (tag_type, id)
);

create table if not exists item_tags (
  item_id text not null references items(id) on delete cascade,
  tag_type text not null,
  tag_id text not null,
  weight numeric not null default 1,
  primary key (item_id, tag_type, tag_id),
  foreign key (tag_type, tag_id) references tags(tag_type, id) on delete cascade
);

create table if not exists item_id_redirects (
  retired_item_id text primary key,
  canonical_item_id text not null references items(id),
  reason text
);
