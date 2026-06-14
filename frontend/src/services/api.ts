import type { OptimizationRun, OverviewData, Scenario } from "../types";

export const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.error_message || `Request failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  overview: () => request<OverviewData>("/overview/"),
  scenarios: () => request<Scenario[]>("/scenarios/"),
  runs: () => request<OptimizationRun[]>("/runs/"),
  runScenario: (id: number) => request<OptimizationRun>(`/scenarios/${id}/run/`, { method: "POST" }),
  environments: () => request<any[]>("/environments/"),
  workloads: () => request<any[]>("/workloads/"),
  carbon: () => request<any[]>("/carbon/")
  ,
  syncCore: () => request<Record<string, unknown>>("/sync/core/", { method: "POST" }),
  exportUrl: (kind: "workload" | "carbon" | "optimization") => `${API}/exports/${kind}/`
};
