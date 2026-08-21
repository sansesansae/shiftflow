# ShiftFlow Auth and Store Permissions

This is the first production-oriented access model for ShiftFlow writes.

## Modes

- Demo mode: `REQUIRE_SUPABASE_AUTH_FOR_WRITES=0`
  - The backend only checks `SHIFT_WRITE_TOKEN`.
  - Useful for a private demo.

- Protected mode: `REQUIRE_SUPABASE_AUTH_FOR_WRITES=1`
  - The backend checks `SHIFT_WRITE_TOKEN`.
  - The backend also requires `Authorization: Bearer <supabase_access_token>`.
  - The user must have an active profile and store write permission.

## Tables

- `user_profiles`: maps Supabase Auth users to product roles.
- `user_store_permissions`: grants read/write/approve/admin access to stores.
- `audit_logs`: records important write actions.

## Roles

- `store_manager`: can operate assigned stores only.
- `area_manager`: can operate multiple assigned stores.
- `ops_admin`: can operate all stores.

## Create a Store Manager Grant

After creating a user in Supabase Auth, copy the user's `auth.users.id`.

```sql
insert into public.user_profiles (id, display_name, role, status)
values (
  'AUTH_USER_ID_HERE',
  '店长演示账号',
  'store_manager',
  'active'
)
on conflict (id) do update set
  display_name = excluded.display_name,
  role = excluded.role,
  status = excluded.status;

insert into public.user_store_permissions (user_id, store_id, permission, scope, status)
select
  'AUTH_USER_ID_HERE',
  id,
  'write',
  'store',
  'active'
from public.stores
where external_id = 'store_001'
on conflict (user_id, store_id, permission, scope) do update set
  status = excluded.status;
```

## Create an Ops Admin Grant

```sql
insert into public.user_profiles (id, display_name, role, status)
values (
  'AUTH_USER_ID_HERE',
  '总部运营演示账号',
  'ops_admin',
  'active'
)
on conflict (id) do update set
  display_name = excluded.display_name,
  role = excluded.role,
  status = excluded.status;

insert into public.user_store_permissions (user_id, store_id, permission, scope, status)
values (
  'AUTH_USER_ID_HERE',
  null,
  'admin',
  'all',
  'active'
)
on conflict (user_id, store_id, permission, scope) do update set
  status = excluded.status;
```

## Frontend Setup

The UI includes an email/password sign-in panel for protected write actions.

Set these frontend environment variables in local `.env.local` and Vercel:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-or-publishable-key
```

When the user is logged in, write requests include:

- `X-Shift-Write-Token`: the demo write protection token entered by the operator.
- `Authorization: Bearer <supabase_access_token>`: the logged-in user's Supabase access token.

To fully enable protected mode, set this backend environment variable in Render:

```bash
REQUIRE_SUPABASE_AUTH_FOR_WRITES=1
```
