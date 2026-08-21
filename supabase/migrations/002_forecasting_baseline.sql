-- ShiftFlow V2 forecasting baseline schema.

create table if not exists public.hourly_store_metrics (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  store_id uuid not null references public.stores(id) on delete cascade,
  metric_date date not null,
  hour integer not null check (hour between 0 and 23),
  role text not null,
  order_count integer not null default 0 check (order_count >= 0),
  sales_amount numeric(10, 2) not null default 0 check (sales_amount >= 0),
  weather text not null default 'clear',
  temperature numeric(5, 2),
  is_weekend boolean not null default false,
  is_holiday boolean not null default false,
  promotion_flag boolean not null default false,
  actual_labor_hours numeric(6, 2) not null default 0 check (actual_labor_hours >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (store_id, metric_date, hour, role)
);

create table if not exists public.labor_forecasts (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  store_id uuid not null references public.stores(id) on delete cascade,
  forecast_date date not null,
  hour integer not null check (hour between 0 and 23),
  role text not null,
  model_name text not null default 'same-weekday-hour-baseline',
  model_version text not null default 'v2-baseline-2026-08',
  predicted_labor_hours numeric(6, 2) not null check (predicted_labor_hours >= 0),
  baseline_labor_hours numeric(6, 2) not null check (baseline_labor_hours >= 0),
  confidence text not null default 'medium' check (confidence in ('low', 'medium', 'high')),
  features jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (store_id, forecast_date, hour, role, model_version)
);

create table if not exists public.forecast_evaluations (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  forecast_id uuid not null references public.labor_forecasts(id) on delete cascade,
  actual_labor_hours numeric(6, 2) not null check (actual_labor_hours >= 0),
  deviation_rate numeric(8, 4) not null,
  absolute_error numeric(6, 2) not null check (absolute_error >= 0),
  status text not null default 'evaluated'
    check (status in ('pending', 'evaluated', 'badcase')),
  notes text,
  evaluated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (forecast_id)
);

drop trigger if exists set_hourly_store_metrics_updated_at on public.hourly_store_metrics;
create trigger set_hourly_store_metrics_updated_at
before update on public.hourly_store_metrics
for each row execute function public.set_updated_at();

drop trigger if exists set_labor_forecasts_updated_at on public.labor_forecasts;
create trigger set_labor_forecasts_updated_at
before update on public.labor_forecasts
for each row execute function public.set_updated_at();

create index if not exists idx_hourly_metrics_store_date on public.hourly_store_metrics(store_id, metric_date);
create index if not exists idx_hourly_metrics_role_hour on public.hourly_store_metrics(role, hour);
create index if not exists idx_labor_forecasts_store_date on public.labor_forecasts(store_id, forecast_date);
create index if not exists idx_labor_forecasts_model_version on public.labor_forecasts(model_version);
create index if not exists idx_forecast_evaluations_status on public.forecast_evaluations(status);

alter table public.hourly_store_metrics enable row level security;
alter table public.labor_forecasts enable row level security;
alter table public.forecast_evaluations enable row level security;

-- Browser clients read V2 data through the backend. Keep these tables server-readable only.
drop policy if exists "server_only_hourly_store_metrics" on public.hourly_store_metrics;
create policy "server_only_hourly_store_metrics"
on public.hourly_store_metrics for select
to authenticated
using (false);

drop policy if exists "server_only_labor_forecasts" on public.labor_forecasts;
create policy "server_only_labor_forecasts"
on public.labor_forecasts for select
to authenticated
using (false);

drop policy if exists "server_only_forecast_evaluations" on public.forecast_evaluations;
create policy "server_only_forecast_evaluations"
on public.forecast_evaluations for select
to authenticated
using (false);

with active_stores as (
  select id, external_id, brand, name, business_type
  from public.stores
  where status = 'active'
),
forecast_seed as (
  select
    active_stores.id as store_id,
    active_stores.external_id as store_external_id,
    (date '2026-08-10' + day_offset)::date as forecast_date,
    slot.hour,
    slot.role,
    case
      when active_stores.business_type = '快餐店' then slot.base_hours + 0.50
      when active_stores.business_type = '奶茶店' then slot.base_hours + 0.25
      else slot.base_hours
    end as baseline_hours,
    case
      when slot.hour in (11, 12, 18, 19) then slot.base_hours + 0.75
      else slot.base_hours + 0.15
    end as predicted_hours,
    case
      when slot.hour in (18, 19) and day_offset in (4, 5) then slot.base_hours + 1.35
      when slot.hour = 22 then slot.base_hours - 0.35
      else slot.base_hours + 0.10
    end as actual_hours,
    day_offset
  from active_stores
  cross join generate_series(0, 6) as day_offset
  cross join (
    values
      (7, '值班经理', 1.00),
      (11, '收银', 2.00),
      (12, '调饮师', 2.25),
      (18, '后厨', 2.50),
      (19, '咖啡师', 2.25),
      (22, '值班经理', 1.25)
  ) as slot(hour, role, base_hours)
)
insert into public.hourly_store_metrics (
  external_id, store_id, metric_date, hour, role, order_count, sales_amount,
  weather, temperature, is_weekend, is_holiday, promotion_flag, actual_labor_hours
)
select
  'metric_' || store_external_id || '_' || forecast_date || '_' || hour || '_' || role,
  store_id,
  forecast_date,
  hour,
  role,
  (actual_hours * 28 + hour * 3)::integer,
  round((actual_hours * 28 + hour * 3) * 23.8, 2),
  case when day_offset in (4, 5) then 'rain' else 'clear' end,
  28 + (hour % 5),
  extract(isodow from forecast_date) in (6, 7),
  false,
  day_offset in (4, 5),
  round(actual_hours, 2)
from forecast_seed
on conflict (store_id, metric_date, hour, role) do update
set order_count = excluded.order_count,
    sales_amount = excluded.sales_amount,
    actual_labor_hours = excluded.actual_labor_hours,
    updated_at = now();

with active_stores as (
  select id, external_id, business_type
  from public.stores
  where status = 'active'
),
forecast_seed as (
  select
    active_stores.id as store_id,
    active_stores.external_id as store_external_id,
    (date '2026-08-10' + day_offset)::date as forecast_date,
    slot.hour,
    slot.role,
    case
      when active_stores.business_type = '快餐店' then slot.base_hours + 0.50
      when active_stores.business_type = '奶茶店' then slot.base_hours + 0.25
      else slot.base_hours
    end as baseline_hours,
    case
      when slot.hour in (11, 12, 18, 19) then slot.base_hours + 0.75
      else slot.base_hours + 0.15
    end as predicted_hours,
    case
      when slot.hour in (18, 19) and day_offset in (4, 5) then slot.base_hours + 1.35
      when slot.hour = 22 then slot.base_hours - 0.35
      else slot.base_hours + 0.10
    end as actual_hours,
    day_offset
  from active_stores
  cross join generate_series(0, 6) as day_offset
  cross join (
    values
      (7, '值班经理', 1.00),
      (11, '收银', 2.00),
      (12, '调饮师', 2.25),
      (18, '后厨', 2.50),
      (19, '咖啡师', 2.25),
      (22, '值班经理', 1.25)
  ) as slot(hour, role, base_hours)
)
insert into public.labor_forecasts (
  external_id, store_id, forecast_date, hour, role, model_name, model_version,
  predicted_labor_hours, baseline_labor_hours, confidence, features
)
select
  'forecast_' || store_external_id || '_' || forecast_date || '_' || hour || '_' || role,
  store_id,
  forecast_date,
  hour,
  role,
  'same-weekday-hour-baseline',
  'v2-baseline-2026-08',
  round(predicted_hours, 2),
  round(baseline_hours, 2),
  case when day_offset in (4, 5) then 'medium' else 'high' end,
  jsonb_build_object(
    'weekday', extract(isodow from forecast_date),
    'promotion_flag', day_offset in (4, 5),
    'weather', case when day_offset in (4, 5) then 'rain' else 'clear' end,
    'source', 'v2_seed_baseline'
  )
from forecast_seed
on conflict (store_id, forecast_date, hour, role, model_version) do update
set predicted_labor_hours = excluded.predicted_labor_hours,
    baseline_labor_hours = excluded.baseline_labor_hours,
    confidence = excluded.confidence,
    features = excluded.features,
    updated_at = now();

with forecast_seed as (
  select
    lf.id as forecast_id,
    lf.external_id as forecast_external_id,
    lf.predicted_labor_hours,
    hm.actual_labor_hours
  from public.labor_forecasts lf
  join public.hourly_store_metrics hm
    on hm.store_id = lf.store_id
   and hm.metric_date = lf.forecast_date
   and hm.hour = lf.hour
   and hm.role = lf.role
  where lf.model_version = 'v2-baseline-2026-08'
)
insert into public.forecast_evaluations (
  external_id, forecast_id, actual_labor_hours, deviation_rate, absolute_error, status, notes
)
select
  'eval_' || forecast_external_id,
  forecast_id,
  actual_labor_hours,
  round((actual_labor_hours - predicted_labor_hours) / nullif(predicted_labor_hours, 0), 4),
  round(abs(actual_labor_hours - predicted_labor_hours), 2),
  case
    when abs((actual_labor_hours - predicted_labor_hours) / nullif(predicted_labor_hours, 0)) >= 0.18
    then 'badcase'
    else 'evaluated'
  end,
  '静默试跑：用于观察预测工时与实际工时的偏差。'
from forecast_seed
on conflict (forecast_id) do update
set actual_labor_hours = excluded.actual_labor_hours,
    deviation_rate = excluded.deviation_rate,
    absolute_error = excluded.absolute_error,
    status = excluded.status,
    notes = excluded.notes,
    evaluated_at = now();
