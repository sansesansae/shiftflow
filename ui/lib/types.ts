export interface Message {
  id: string
  content: string
  role: "user" | "assistant"
  agent?: string
  timestamp: Date
  status?: "info" | "success" | "warning" | "blocked"
  traceId?: string
  traceUrl?: string
  feedbackSubmitted?: "up" | "down" | null
}

export interface Agent {
  name: string
  description: string
  handoffs: string[]
  tools: string[]
  /** List of input guardrail identifiers for this agent */
  input_guardrails: string[]
}

export type EventType =
  | "message"
  | "handoff"
  | "tool_call"
  | "tool_output"
  | "context_update"
  | "progress_update"

export interface AgentEvent {
  id: string
  type: EventType
  agent: string
  content: string
  timestamp: Date
  metadata?: {
    source_agent?: string
    target_agent?: string
    tool_name?: string
    tool_args?: Record<string, any>
    tool_result?: any
    context_key?: string
    context_value?: any
    changes?: Record<string, any>
    icon?: string
  }
}

export interface GuardrailCheck {
  id: string
  name: string
  input: string
  reasoning: string
  passed: boolean
  timestamp: Date
}

export interface Store {
  id: string
  brand: string
  name: string
  city: string
  district: string
  address: string
  business_type: string
  opening_time: string
  closing_time: string
  status: string
}

export interface StoreShift {
  id: string
  store_id: string
  template_id: string
  template_name: string
  shift_date: string
  start_time: string
  end_time: string
  required_role: string
  required_count: number
  assigned_count: number
  open_count: number
  status: string
  note?: string | null
}

export interface StoreStaff {
  id: string
  store_id: string
  name: string
  role: string
  skills: string[]
  weekly_hour_limit: number
  scheduled_hours: number
  can_close: boolean
  can_float: boolean
  phone: string
  status: string
}

export interface AssignmentResult {
  ok: boolean
  assignment_id: string
  change_record_id: string
  shift_id: string
  employee_id: string
  assigned_count: number
  status: string
  risk_flags: string[]
}

export interface LaborForecast {
  id: string
  store_id: string
  store_name: string
  forecast_date: string
  hour: number
  role: string
  model_name: string
  model_version: string
  predicted_labor_hours: number
  baseline_labor_hours: number
  actual_labor_hours: number | null
  deviation_rate: number | null
  absolute_error: number | null
  status: "pending" | "evaluated" | "badcase" | string
  confidence: string
  features: Record<string, any>
  notes?: string | null
}

export interface ForecastSummary {
  store_count: number
  forecast_count: number
  evaluated_count: number
  badcase_count: number
  total_predicted_labor_hours: number
  total_actual_labor_hours: number
  average_abs_deviation_rate: number
  model_name: string
  model_version: string
  next_focus: LaborForecast[]
}

export interface MetricsImportResult {
  ok: boolean
  imported_count: number
  forecast_count: number
  badcase_count: number
  message: string
  required_columns: string[]
}
