create or replace function public.vendr_apply_purchase_v2(
  p_world_key text,
  p_entity_id text,
  p_item_id text,
  p_stock_cycle bigint,
  p_quantity integer,
  p_generated_quantity integer,
  p_effective_capacity integer,
  p_unit_price numeric default null,
  p_actor_key text default null,
  p_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.vendr_stock_depletion%rowtype;
  v_remaining integer;
begin
  if p_quantity is null or p_quantity < 1 then
    raise exception 'quantity must be at least 1' using errcode='22023';
  end if;
  if p_generated_quantity is null or p_generated_quantity < 1 then
    raise exception 'generated quantity must be at least 1' using errcode='22023';
  end if;
  if p_effective_capacity is null or p_effective_capacity < 0 then
    raise exception 'effective capacity must be non-negative' using errcode='22023';
  end if;
  if p_quantity > p_effective_capacity then
    raise exception 'insufficient stock' using errcode='P0001';
  end if;

  insert into public.vendr_stock_depletion(
    world_key, entity_id, item_id, stock_cycle,
    baseline_quantity, quantity_depleted, updated_at
  )
  values(
    coalesce(nullif(p_world_key,''),'public-2045'),
    p_entity_id, p_item_id, p_stock_cycle,
    p_generated_quantity, p_quantity, now()
  )
  on conflict (world_key, entity_id, item_id, stock_cycle)
  do update set
    quantity_depleted = public.vendr_stock_depletion.quantity_depleted + excluded.quantity_depleted,
    updated_at = now()
  where public.vendr_stock_depletion.quantity_depleted + excluded.quantity_depleted
        <= p_effective_capacity
  returning * into v_row;

  if not found then
    raise exception 'insufficient stock' using errcode='P0001';
  end if;

  v_remaining := greatest(0, p_effective_capacity - v_row.quantity_depleted);

  insert into public.vendr_stock_events(
    world_key, entity_id, item_id, stock_cycle, event_type,
    quantity_delta, unit_price, actor_key, metadata
  ) values (
    v_row.world_key, p_entity_id, p_item_id, p_stock_cycle, 'purchase',
    -p_quantity, p_unit_price, p_actor_key,
    coalesce(p_metadata,'{}'::jsonb) ||
    jsonb_build_object(
      'generated_quantity', p_generated_quantity,
      'effective_capacity', p_effective_capacity
    )
  );

  return jsonb_build_object(
    'ok', true,
    'world_key', v_row.world_key,
    'entity_id', p_entity_id,
    'item_id', p_item_id,
    'stock_cycle', p_stock_cycle,
    'quantity_purchased', p_quantity,
    'quantity_depleted', v_row.quantity_depleted,
    'remaining', v_remaining
  );
end;
$$;

revoke all on function public.vendr_apply_purchase_v2(text,text,text,bigint,integer,integer,integer,numeric,text,jsonb) from public;
revoke all on function public.vendr_apply_purchase_v2(text,text,text,bigint,integer,integer,integer,numeric,text,jsonb) from anon;
revoke all on function public.vendr_apply_purchase_v2(text,text,text,bigint,integer,integer,integer,numeric,text,jsonb) from authenticated;
grant execute on function public.vendr_apply_purchase_v2(text,text,text,bigint,integer,integer,integer,numeric,text,jsonb) to service_role;
