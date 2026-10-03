create table if not exists public.vendr_stock_observations (
  world_key text not null default 'public-2045',
  entity_id text not null,
  generation bigint not null default 0 check (generation >= 0),
  state_at timestamptz not null default now(),
  snapshot jsonb not null default '[]'::jsonb,
  model_version text not null default 'lazy-1.0',
  updated_at timestamptz not null default now(),
  primary key (world_key, entity_id),
  check (jsonb_typeof(snapshot) = 'array')
);

alter table public.vendr_stock_observations enable row level security;

comment on table public.vendr_stock_observations is
  'Current resolved Vend-R stock snapshots only. A row is created when a shop is first observed and is replaced in place by lazy catch-up transitions. No intermediate ebb/flow history is stored.';

create or replace function public.vendr_apply_snapshot_purchase(
  p_world_key text,
  p_entity_id text,
  p_item_id text,
  p_quantity integer
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_world text := coalesce(nullif(p_world_key,''),'public-2045');
  v_snapshot jsonb;
  v_generation bigint;
  v_current integer;
  v_new integer;
begin
  if p_quantity is null or p_quantity < 1 then
    raise exception 'quantity must be at least 1' using errcode='22023';
  end if;

  select snapshot, generation into v_snapshot, v_generation
  from public.vendr_stock_observations
  where world_key=v_world and entity_id=p_entity_id
  for update;

  if not found then
    raise exception 'shop stock has not been resolved yet' using errcode='P0001';
  end if;

  select (elem->>'quantity')::integer into v_current
  from jsonb_array_elements(v_snapshot) elem
  where elem->>'item_id'=p_item_id limit 1;

  if not found then
    raise exception 'item is not in current stock' using errcode='P0001';
  end if;

  if v_current is null then
    return jsonb_build_object(
      'ok',true,'depletes',false,'entity_id',p_entity_id,'item_id',p_item_id,
      'quantity_purchased',p_quantity,'remaining',null,'generation',v_generation
    );
  end if;

  if p_quantity > v_current then
    raise exception 'insufficient stock' using errcode='P0001';
  end if;

  v_new := v_current - p_quantity;

  select jsonb_agg(
    case
      when elem->>'item_id'=p_item_id then
        jsonb_set(
          jsonb_set(elem,'{quantity}',to_jsonb(v_new),true),
          '{status}',to_jsonb(case when v_new>0 then 'in_stock' else 'sold' end::text),true
        )
      else elem
    end
    order by ord
  )
  into v_snapshot
  from jsonb_array_elements(v_snapshot) with ordinality x(elem,ord);

  update public.vendr_stock_observations
  set snapshot=v_snapshot, updated_at=now()
  where world_key=v_world and entity_id=p_entity_id;

  return jsonb_build_object(
    'ok',true,'depletes',true,'entity_id',p_entity_id,'item_id',p_item_id,
    'quantity_purchased',p_quantity,'remaining',v_new,'generation',v_generation
  );
end;
$$;

revoke all on function public.vendr_apply_snapshot_purchase(text,text,text,integer) from public;
revoke all on function public.vendr_apply_snapshot_purchase(text,text,text,integer) from anon;
revoke all on function public.vendr_apply_snapshot_purchase(text,text,text,integer) from authenticated;
grant execute on function public.vendr_apply_snapshot_purchase(text,text,text,integer) to service_role;


-- Disable the superseded depletion write path without dropping its empty table yet.
comment on table public.vendr_stock_depletion is
  'DEPRECATED by lazy-1.0. Retained temporarily as an empty migration relic; production Vend-R stock state lives in vendr_stock_observations.';

revoke execute on function public.vendr_apply_purchase(text,text,text,bigint,integer,integer,numeric,text,jsonb) from service_role;
revoke execute on function public.vendr_apply_purchase_v2(text,text,text,bigint,integer,integer,integer,numeric,text,jsonb) from service_role;
