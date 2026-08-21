PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stores (
  id TEXT PRIMARY KEY,
  brand TEXT NOT NULL,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  district TEXT NOT NULL,
  address TEXT NOT NULL,
  business_type TEXT NOT NULL,
  opening_time TEXT NOT NULL,
  closing_time TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  skills TEXT NOT NULL,
  weekly_hour_limit INTEGER NOT NULL,
  scheduled_hours INTEGER NOT NULL,
  can_close INTEGER NOT NULL DEFAULT 0,
  can_float INTEGER NOT NULL DEFAULT 0,
  phone TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shift_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  default_roles TEXT NOT NULL,
  priority TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shifts (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  template_id TEXT NOT NULL REFERENCES shift_templates(id),
  shift_date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  required_role TEXT NOT NULL,
  required_count INTEGER NOT NULL,
  assigned_count INTEGER NOT NULL,
  status TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shift_assignments (
  id TEXT PRIMARY KEY,
  shift_id TEXT NOT NULL REFERENCES shifts(id),
  employee_id TEXT NOT NULL REFERENCES employees(id),
  assignment_status TEXT NOT NULL,
  source TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shift_change_records (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  shift_id TEXT NOT NULL REFERENCES shifts(id),
  request_type TEXT NOT NULL,
  original_employee_id TEXT REFERENCES employees(id),
  target_employee_id TEXT REFERENCES employees(id),
  reason TEXT NOT NULL,
  risk_flags TEXT NOT NULL,
  approval_status TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS hourly_store_metrics (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  metric_date TEXT NOT NULL,
  hour INTEGER NOT NULL CHECK (hour >= 0 AND hour <= 23),
  role TEXT NOT NULL,
  order_count INTEGER NOT NULL,
  sales_amount REAL NOT NULL,
  weather TEXT NOT NULL,
  temperature REAL NOT NULL,
  is_weekend INTEGER NOT NULL DEFAULT 0,
  is_holiday INTEGER NOT NULL DEFAULT 0,
  promotion_flag INTEGER NOT NULL DEFAULT 0,
  actual_labor_hours REAL NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (store_id, metric_date, hour, role)
);

CREATE TABLE IF NOT EXISTS labor_forecasts (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  forecast_date TEXT NOT NULL,
  hour INTEGER NOT NULL CHECK (hour >= 0 AND hour <= 23),
  role TEXT NOT NULL,
  model_name TEXT NOT NULL,
  model_version TEXT NOT NULL,
  predicted_labor_hours REAL NOT NULL,
  baseline_labor_hours REAL NOT NULL,
  confidence TEXT NOT NULL,
  features TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (store_id, forecast_date, hour, role, model_version)
);

CREATE TABLE IF NOT EXISTS forecast_evaluations (
  id TEXT PRIMARY KEY,
  forecast_id TEXT NOT NULL REFERENCES labor_forecasts(id),
  actual_labor_hours REAL NOT NULL,
  deviation_rate REAL NOT NULL,
  absolute_error REAL NOT NULL,
  status TEXT NOT NULL,
  notes TEXT,
  evaluated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_employees_store_id ON employees(store_id);
CREATE INDEX IF NOT EXISTS idx_shifts_store_date ON shifts(store_id, shift_date);
CREATE INDEX IF NOT EXISTS idx_assignments_shift_id ON shift_assignments(shift_id);
CREATE INDEX IF NOT EXISTS idx_change_records_store_id ON shift_change_records(store_id);
CREATE INDEX IF NOT EXISTS idx_hourly_metrics_store_date ON hourly_store_metrics(store_id, metric_date);
CREATE INDEX IF NOT EXISTS idx_labor_forecasts_store_date ON labor_forecasts(store_id, forecast_date);
CREATE INDEX IF NOT EXISTS idx_forecast_evaluations_forecast_id ON forecast_evaluations(forecast_id);
