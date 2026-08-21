# ShiftFlow seed data

This folder contains the first local data layer for the restaurant scheduling product.

## Files

- `schema.sql`: SQLite schema for stores, employees, shifts, assignments, and shift change records.
- `generate_seed_data.py`: Deterministic synthetic data generator. It uses only Python standard libraries and a fixed random seed.
- `shiftflow_seed.json`: Generated seed data for quick inspection or frontend prototyping.
- `shiftflow_seed.sqlite`: Generated local SQLite database for backend experiments.

## Tables

- `stores`: restaurant stores, including brand, city, district, address, opening time, and closing time.
- `employees`: store staff, roles, skills, weekly hour limits, scheduled hours, and whether they can close or float.
- `shift_templates`: reusable shift windows such as lunch peak, dinner peak, and closing shift.
- `shifts`: concrete shift demand by store, date, role, required headcount, assigned headcount, and status.
- `shift_assignments`: employees already assigned to shifts.
- `shift_change_records`: change, backfill, and swap records with reason, risk flags, and approval status.

## Regenerate

Run from `python-backend`:

```bash
python3.11 data/generate_seed_data.py
```

Expected current counts:

- `stores`: 6
- `employees`: 48
- `shift_templates`: 5
- `shifts`: 210
- `shift_assignments`: 277
- `shift_change_records`: 10

## Next step

The next backend step is to add read APIs such as:

- `GET /stores`
- `GET /stores/{store_id}/shifts`
- `GET /stores/{store_id}/staff`
- `GET /shift-change-records`
