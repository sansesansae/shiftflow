# ShiftFlow Supabase Setup

This folder contains the first production database schema for ShiftFlow.

## What This Schema Covers

- `stores`: restaurant locations, such as milk tea shops, fast food stores, and coffee shops.
- `employees`: staff profiles, roles, skills, hour limits, and whether they can close or float.
- `shift_templates`: reusable day-part templates, such as morning peak, lunch peak, evening peak, and closing.
- `shifts`: dated staffing demand for one store and one role.
- `shift_assignments`: who is assigned to each shift.
- `shift_change_records`: swaps, cover requests, absences, and schedule changes.
- `chat_sessions`: product conversation sessions.
- `chat_feedback`: user feedback and badcase labels for quality review.

## Create The Supabase Project

1. Open [Supabase Dashboard](https://supabase.com/dashboard/projects).
2. Click `New project`.
3. Recommended project name: `shiftflow`.
4. Choose a region close to your users.
5. Save the database password in a safe place.
6. Wait for project creation to finish.

## Create Tables

1. Open the Supabase project.
2. Go to `SQL Editor`.
3. Create a new query.
4. Paste the full contents of `supabase/migrations/001_shiftflow_schema.sql`.
5. Click `Run`.
6. Confirm the tables appear in `Table Editor`.

## Environment Variables Needed Later

Add these to the Render backend, not to the frontend:

```bash
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

Optional frontend read-only variables can be added later if we decide to query Supabase directly from the browser:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

For this product, the safer first version is:

- Frontend talks to Render backend.
- Render backend talks to Supabase with the service role key.
- The service role key never appears in browser code.

## Next Migration Step

After the tables are created, migrate the demo seed data from SQLite/JSON into Supabase, then update the backend repository layer from SQLite to Supabase.
