import type { AssignmentResult, ForecastSummary, LaborForecast, MetricsImportResult, Store, StoreShift, StoreStaff } from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export async function fetchStores(): Promise<Store[]> {
  return apiGet<Store[]>("/stores");
}

export async function fetchStoreShifts(
  storeId: string,
  options: { status?: string; shiftDate?: string } = {}
): Promise<StoreShift[]> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.shiftDate) params.set("shift_date", options.shiftDate);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<StoreShift[]>(`/stores/${encodeURIComponent(storeId)}/shifts${suffix}`);
}

export async function fetchStoreStaff(storeId: string): Promise<StoreStaff[]> {
  return apiGet<StoreStaff[]>(`/stores/${encodeURIComponent(storeId)}/staff`);
}

export async function fetchForecastSummary(storeId?: string): Promise<ForecastSummary> {
  const suffix = storeId ? `?store_id=${encodeURIComponent(storeId)}` : "";
  return apiGet<ForecastSummary>(`/forecasts/summary${suffix}`);
}

export async function fetchStoreForecasts(
  storeId: string,
  options: { forecastDate?: string } = {}
): Promise<LaborForecast[]> {
  const params = new URLSearchParams();
  if (options.forecastDate) params.set("forecast_date", options.forecastDate);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<LaborForecast[]>(`/stores/${encodeURIComponent(storeId)}/forecasts${suffix}`);
}

export async function importStoreMetricsCsv(params: {
  storeId: string;
  csvText: string;
  writeToken: string;
  accessToken?: string;
}): Promise<MetricsImportResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Shift-Write-Token": params.writeToken,
  };
  if (params.accessToken) {
    headers.Authorization = `Bearer ${params.accessToken}`;
  }

  const res = await fetch(
    `${API_BASE_URL}/stores/${encodeURIComponent(params.storeId)}/metrics/import-csv`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({ csv_text: params.csvText }),
    }
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`导入失败 ${res.status}: ${detail}`);
  }
  return res.json();
}

export async function assignStoreShift(params: {
  storeId: string;
  shiftId: string;
  employeeId: string;
  writeToken: string;
  accessToken?: string;
  reason?: string;
}): Promise<AssignmentResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Shift-Write-Token": params.writeToken,
  };
  if (params.accessToken) {
    headers.Authorization = `Bearer ${params.accessToken}`;
  }

  const res = await fetch(
    `${API_BASE_URL}/stores/${encodeURIComponent(params.storeId)}/shifts/${encodeURIComponent(params.shiftId)}/assignments`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        employee_id: params.employeeId,
        requested_by: "demo-manager",
        reason: params.reason ?? "页面确认补位",
      }),
    }
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`补位失败 ${res.status}: ${detail}`);
  }
  return res.json();
}

// Fetch ChatKit thread state for the Agent panel
export async function fetchThreadState(threadId: string) {
  try {
    const res = await fetch(`/chatkit/state?thread_id=${encodeURIComponent(threadId)}`);
    if (!res.ok) throw new Error(`State API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.error("Error fetching thread state:", err);
    return null;
  }
}

export async function fetchBootstrapState() {
  try {
    const res = await fetch(`/chatkit/bootstrap`);
    if (!res.ok) throw new Error(`Bootstrap API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.error("Error bootstrapping state:", err);
    return null;
  }
}
