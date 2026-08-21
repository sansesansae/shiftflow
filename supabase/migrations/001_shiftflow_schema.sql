-- ShiftFlow Supabase schema
-- Run this in Supabase SQL Editor after creating the project.

create extension if not exists pgcrypto;

create table if not exists public.stores (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  brand text not null,
  name text not null,
  city text not null,
  district text not null,
  address text not null,
  business_type text not null default 'restaurant',
  opening_time time not null,
  closing_time time not null,
  status text not null default 'active'
    check (status in ('active', 'paused', 'closed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.employees (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  store_id uuid not null references public.stores(id) on delete cascade,
  name text not null,
  role text not null,
  skills jsonb not null default '[]'::jsonb,
  weekly_hour_limit integer not null default 40
    check (weekly_hour_limit >= 0),
  scheduled_hours numeric(5, 2) not null default 0
    check (scheduled_hours >= 0),
  can_close boolean not null default false,
  can_float boolean not null default false,
  phone text,
  status text not null default 'active'
    check (status in ('active', 'inactive', 'on_leave')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.shift_templates (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  name text not null,
  start_time time not null,
  end_time time not null,
  default_roles jsonb not null default '[]'::jsonb,
  priority text not null default 'normal'
    check (priority in ('low', 'normal', 'high', 'urgent')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.shifts (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  store_id uuid not null references public.stores(id) on delete cascade,
  template_id uuid references public.shift_templates(id) on delete set null,
  shift_date date not null,
  start_time time not null,
  end_time time not null,
  required_role text not null,
  required_count integer not null default 1
    check (required_count >= 0),
  assigned_count integer not null default 0
    check (assigned_count >= 0),
  status text not null default 'open'
    check (status in ('draft', 'open', 'filled', 'cancelled')),
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint shifts_assigned_not_over_required
    check (assigned_count <= required_count)
);

create table if not exists public.shift_assignments (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  shift_id uuid not null references public.shifts(id) on delete cascade,
  employee_id uuid not null references public.employees(id) on delete cascade,
  assignment_status text not null default 'assigned'
    check (assignment_status in ('assigned', 'confirmed', 'cancelled', 'no_show')),
  source text not null default 'manual'
    check (source in ('manual', 'assistant', 'import', 'system')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (shift_id, employee_id)
);

create table if not exists public.shift_change_records (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  store_id uuid not null references public.stores(id) on delete cascade,
  shift_id uuid references public.shifts(id) on delete set null,
  request_type text not null
    check (request_type in ('swap', 'cover', 'cancel', 'modify', 'absence')),
  original_employee_id uuid references public.employees(id) on delete set null,
  target_employee_id uuid references public.employees(id) on delete set null,
  reason text not null,
  risk_flags jsonb not null default '[]'::jsonb,
  approval_status text not null default 'pending'
    check (approval_status in ('pending', 'approved', 'rejected', 'cancelled')),
  requested_by text not null default 'manager',
  requested_at timestamptz not null default now(),
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  store_id uuid references public.stores(id) on delete set null,
  title text,
  channel text not null default 'web'
    check (channel in ('web', 'api', 'internal')),
  langfuse_session_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.chat_feedback (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references public.chat_sessions(id) on delete set null,
  langfuse_trace_id text,
  user_message text,
  assistant_message text,
  rating integer check (rating in (-1, 0, 1)),
  issue_type text
    check (issue_type in ('wrong_data', 'bad_reasoning', 'unsafe_action', 'unclear_copy', 'other')),
  comment text,
  status text not null default 'open'
    check (status in ('open', 'reviewing', 'fixed', 'wont_fix')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null,
  role text not null
    check (role in ('store_manager', 'area_manager', 'ops_admin')),
  status text not null default 'active'
    check (status in ('active', 'disabled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_store_permissions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.user_profiles(id) on delete cascade,
  store_id uuid references public.stores(id) on delete cascade,
  permission text not null
    check (permission in ('read', 'write', 'approve', 'admin')),
  scope text not null default 'store'
    check (scope in ('store', 'area', 'all')),
  status text not null default 'active'
    check (status in ('active', 'disabled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint permissions_store_required_for_store_scope
    check (scope <> 'store' or store_id is not null),
  unique (user_id, store_id, permission, scope)
);

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  user_id uuid references public.user_profiles(id) on delete set null,
  action text not null,
  store_id uuid references public.stores(id) on delete set null,
  shift_id uuid references public.shifts(id) on delete set null,
  employee_id uuid references public.employees(id) on delete set null,
  payload jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  source text not null default 'web'
    check (source in ('web', 'api', 'assistant', 'system')),
  created_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_stores_updated_at on public.stores;
create trigger set_stores_updated_at
before update on public.stores
for each row execute function public.set_updated_at();

drop trigger if exists set_employees_updated_at on public.employees;
create trigger set_employees_updated_at
before update on public.employees
for each row execute function public.set_updated_at();

drop trigger if exists set_shift_templates_updated_at on public.shift_templates;
create trigger set_shift_templates_updated_at
before update on public.shift_templates
for each row execute function public.set_updated_at();

drop trigger if exists set_shifts_updated_at on public.shifts;
create trigger set_shifts_updated_at
before update on public.shifts
for each row execute function public.set_updated_at();

drop trigger if exists set_shift_assignments_updated_at on public.shift_assignments;
create trigger set_shift_assignments_updated_at
before update on public.shift_assignments
for each row execute function public.set_updated_at();

drop trigger if exists set_shift_change_records_updated_at on public.shift_change_records;
create trigger set_shift_change_records_updated_at
before update on public.shift_change_records
for each row execute function public.set_updated_at();

drop trigger if exists set_chat_sessions_updated_at on public.chat_sessions;
create trigger set_chat_sessions_updated_at
before update on public.chat_sessions
for each row execute function public.set_updated_at();

drop trigger if exists set_chat_feedback_updated_at on public.chat_feedback;
create trigger set_chat_feedback_updated_at
before update on public.chat_feedback
for each row execute function public.set_updated_at();

drop trigger if exists set_user_profiles_updated_at on public.user_profiles;
create trigger set_user_profiles_updated_at
before update on public.user_profiles
for each row execute function public.set_updated_at();

drop trigger if exists set_user_store_permissions_updated_at on public.user_store_permissions;
create trigger set_user_store_permissions_updated_at
before update on public.user_store_permissions
for each row execute function public.set_updated_at();

create index if not exists idx_stores_status on public.stores(status);
create index if not exists idx_employees_store_id on public.employees(store_id);
create index if not exists idx_employees_status on public.employees(status);
create index if not exists idx_shifts_store_date on public.shifts(store_id, shift_date);
create index if not exists idx_shifts_status on public.shifts(status);
create index if not exists idx_assignments_shift_id on public.shift_assignments(shift_id);
create index if not exists idx_assignments_employee_id on public.shift_assignments(employee_id);
create index if not exists idx_change_records_store_id on public.shift_change_records(store_id);
create index if not exists idx_chat_sessions_store_id on public.chat_sessions(store_id);
create index if not exists idx_chat_feedback_trace_id on public.chat_feedback(langfuse_trace_id);
create index if not exists idx_user_profiles_role on public.user_profiles(role);
create index if not exists idx_permissions_user_store on public.user_store_permissions(user_id, store_id);
create index if not exists idx_permissions_scope on public.user_store_permissions(scope, status);
create unique index if not exists idx_permissions_unique_all_scope
on public.user_store_permissions(user_id, permission, scope)
where store_id is null and scope = 'all';
create index if not exists idx_audit_logs_user_id on public.audit_logs(user_id);
create index if not exists idx_audit_logs_store_id on public.audit_logs(store_id);
create index if not exists idx_audit_logs_created_at on public.audit_logs(created_at);

alter table public.stores enable row level security;
alter table public.employees enable row level security;
alter table public.shift_templates enable row level security;
alter table public.shifts enable row level security;
alter table public.shift_assignments enable row level security;
alter table public.shift_change_records enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.chat_feedback enable row level security;
alter table public.user_profiles enable row level security;
alter table public.user_store_permissions enable row level security;
alter table public.audit_logs enable row level security;

-- Demo policy: browser clients can read dashboard data only.
-- Server-side writes should use the Supabase service role key from the Render backend.
drop policy if exists "public_read_active_stores" on public.stores;
create policy "public_read_active_stores"
on public.stores for select
using (status = 'active');

drop policy if exists "public_read_active_employees" on public.employees;
create policy "public_read_active_employees"
on public.employees for select
using (status = 'active');

drop policy if exists "public_read_shift_templates" on public.shift_templates;
create policy "public_read_shift_templates"
on public.shift_templates for select
using (true);

drop policy if exists "public_read_shifts" on public.shifts;
create policy "public_read_shifts"
on public.shifts for select
using (status <> 'cancelled');

drop policy if exists "public_read_assignments" on public.shift_assignments;
create policy "public_read_assignments"
on public.shift_assignments for select
using (assignment_status <> 'cancelled');

drop policy if exists "public_read_change_records" on public.shift_change_records;
create policy "public_read_change_records"
on public.shift_change_records for select
using (true);

-- Authenticated users can read only their own profile and permission grants.
-- Server-side writes and audit inserts should still use the service role key.
drop policy if exists "users_read_own_profile" on public.user_profiles;
create policy "users_read_own_profile"
on public.user_profiles for select
to authenticated
using (id = auth.uid());

drop policy if exists "users_read_own_permissions" on public.user_store_permissions;
create policy "users_read_own_permissions"
on public.user_store_permissions for select
to authenticated
using (user_id = auth.uid());

-- These operational logs are server-readable only in this demo.
-- The service role bypasses RLS; browser clients should not read them directly.
drop policy if exists "server_only_audit_logs" on public.audit_logs;
create policy "server_only_audit_logs"
on public.audit_logs for select
to authenticated
using (false);

drop policy if exists "server_only_chat_sessions" on public.chat_sessions;
create policy "server_only_chat_sessions"
on public.chat_sessions for select
to authenticated
using (false);

drop policy if exists "server_only_chat_feedback" on public.chat_feedback;
create policy "server_only_chat_feedback"
on public.chat_feedback for select
to authenticated
using (false);
