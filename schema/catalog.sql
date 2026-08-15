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

create table if not exists item_classifications (
  item_id text not null references items(id) on delete cascade,
  source_category text not null,
  source_subcategory text,
  vendr_department text not null,
  vendr_class text,
  is_primary boolean not null default false,
  primary key (item_id, source_category, source_subcategory, vendr_department)
);

create table if not exists tags (
  id text primary key,
  label text not null,
  description text
);

create table if not exists item_tags (
  item_id text not null references items(id) on delete cascade,
  tag_id text not null references tags(id) on delete cascade,
  weight numeric not null default 1,
  primary key (item_id, tag_id)
);

create table if not exists item_id_redirects (
  retired_item_id text primary key,
  canonical_item_id text not null references items(id),
  reason text
);
