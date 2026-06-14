export type Scenario = {
  id: number;
  name: string;
  strategy: string;
  forecast_horizon_hours: number;
  deadline_hours: number;
  cost_target: number;
  carbon_target_g: number;
  is_default: boolean;
};

export type Placement = {
  id: number;
  workload_id: string;
  workload_name: string;
  environment_id: string;
  environment_kind: "MF" | "PR" | "PU";
  region: string;
  start_hour: number;
  duration_hours: number;
  end_hour: number;
  cost: number;
  carbon_g: number;
};

export type OptimizationRun = {
  id: number;
  scenario: number;
  scenario_name: string;
  status: string;
  objective_value: number | null;
  mip_gap: number | null;
  solve_seconds: number | null;
  total_cost: number | null;
  total_carbon_g: number | null;
  workload_count: number;
  result_payload: {
    placement_by_kind?: Record<string, number>;
    placement_by_region?: Record<string, number>;
    utilization_percent?: Record<string, number>;
    placement_summary?: Record<string, number>;
    constraints_satisfied?: boolean;
    core_run_id?: string;
    source?: string;
    solver?: Record<string, number | string | boolean>;
    kpis?: Record<string, number>;
    cost_breakdown?: Record<string, number>;
    diagnostics?: string[];
  };
  placements: Placement[];
  created_at: string;
  error_message?: string;
};

export type CarbonPoint = {
  region_code: string;
  region_label: string;
  horizon_hours: number;
  forecast_timestamp: string;
  intensity_gco2_kwh: number;
};

export type WorkloadPoint = {
  external_id: string;
  archetype: string;
  compute_size: number;
  memory_gb: number;
  forecast_job_arrivals: number;
};

export type OverviewData = {
  workloads: number;
  average_compute: number;
  regions: number;
  carbon_series: CarbonPoint[];
  workload_series: WorkloadPoint[];
  latest_run: OptimizationRun | null;
  environment_summary: { kind: string; count: number }[];
  pipeline: {
    workload: {
      ready: boolean;
      source: string | null;
      checksum: string | null;
      generated_at: string | null;
      models_selected: Record<string, string>;
      model_performance: Record<string, string | number>[];
    };
    carbon: {
      ready: boolean;
      source: string | null;
      checksum: string | null;
      generated_at: string | null;
      model_performance: Record<string, string | number>[];
    };
    optimization: {
      ready: boolean;
      core_run_id: string | null;
      source: string | null;
    };
  };
};
