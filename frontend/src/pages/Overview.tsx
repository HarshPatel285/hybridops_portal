import { useEffect, useMemo, useState } from "react";
import { CircleCheck, CircleDollarSign, ClipboardCheck, Database, Leaf, Play } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { KpiCard } from "../components/KpiCard";
import { Panel } from "../components/Panel";
import { api } from "../services/api";
import type { OptimizationRun, OverviewData, Scenario } from "../types";

const colors: Record<string, string> = { MF: "#1267e8", PR: "#08abc1", PU: "#7538df" };
const names: Record<string, string> = { MF: "Mainframe", PR: "Private Cloud", PU: "Public Cloud" };

export function Overview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState<number>();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    const [overview, scenarioRows] = await Promise.all([api.overview(), api.scenarios()]);
    setData(overview);
    setScenarios(scenarioRows);
    setScenarioId((current) => current || scenarioRows.find((s) => s.is_default)?.id || scenarioRows[0]?.id);
  };

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const runOptimization = async () => {
    if (!scenarioId) return;
    setRunning(true);
    setError("");
    try {
      await api.syncCore();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Optimization failed");
    } finally {
      setRunning(false);
    }
  };

  const outlook = useMemo(() => {
    if (!data) return [];
    const carbonByHour = new Map<number, number[]>();
    data.carbon_series.forEach((point) => {
      const values = carbonByHour.get(point.horizon_hours) || [];
      values.push(point.intensity_gco2_kwh);
      carbonByHour.set(point.horizon_hours, values);
    });
    const workloadBase = data.workload_series.reduce((sum, row) => sum + row.compute_size, 0);
    const arrivalsBase = data.workload_series.reduce((sum, row) => sum + row.forecast_job_arrivals, 0);
    return Array.from({ length: 24 }, (_, index) => {
      const hour = index + 1;
      const carbonValues = carbonByHour.get(hour) || [240 + Math.abs(12 - hour) * 9];
      return {
        hour: `${String(hour).padStart(2, "0")}:00`,
        demand: Math.round(workloadBase),
        arrivals: Math.round(arrivalsBase),
        carbon: Math.round(carbonValues.reduce((a, b) => a + b, 0) / carbonValues.length)
      };
    });
  }, [data]);

  if (!data) {
    return <div className="loading-state">{error || "Loading HybridOps decision center..."}</div>;
  }

  const run: OptimizationRun | null = data.latest_run;
  const distribution = Object.entries(run?.result_payload.placement_by_kind || {})
    .map(([kind, value]) => ({ kind, name: names[kind], value }));
  const total = distribution.reduce((sum, row) => sum + row.value, 0) || 1;

  return (
    <div className="overview-page">
      <div className="page-title-row">
        <div>
          <h1>Hybrid Infrastructure Decision Center</h1>
          <p>Forecast-driven placement across mainframe, private cloud, and public cloud</p>
        </div>
        <div className="scenario-actions">
          <label>
            <span>Scenario</span>
            <select value={scenarioId || ""} onChange={(event) => setScenarioId(Number(event.target.value))}>
              {scenarios.map((scenario) => <option key={scenario.id} value={scenario.id}>{scenario.name}</option>)}
            </select>
          </label>
          <button className="primary-button" onClick={runOptimization} disabled={running}>
            <Play size={17} fill="currentColor" />
            {running ? "Synchronizing..." : "Refresh Core Results"}
          </button>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="kpi-grid">
        <KpiCard icon={<CircleDollarSign />} label="Projected Cost" value={run?.total_cost != null ? `$${run.total_cost.toFixed(2)}` : "Not run"} detail="Verified core result" />
        <KpiCard icon={<Leaf />} label="Carbon Emissions" value={run?.total_carbon_g != null ? `${(run.total_carbon_g / 1000).toFixed(2)} kgCO2e` : "Not run"} detail="Time- and region-aware" tone="cyan" />
        <KpiCard icon={<ClipboardCheck />} label="Workloads Scheduled" value={`${run?.workload_count || 0} / ${data.workloads}`} detail={run?.result_payload.constraints_satisfied ? "All constraints satisfied" : "Awaiting verified result"} tone="purple" />
        <KpiCard
          icon={<CircleCheck />}
          label="Solver Status"
          value={run?.status || "Not run"}
          detail={run?.solve_seconds != null
            ? `MIP gap ${run.mip_gap != null ? `${(run.mip_gap * 100).toFixed(2)}%` : "n/a"} · ${run.solve_seconds.toFixed(2)} sec`
            : "No solver result loaded"}
          tone="green"
        />
      </div>

      <div className="dashboard-grid">
        <Panel title="Forecast Totals & 24-Hour Carbon Outlook" className="outlook-panel">
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={265}>
              <LineChart data={outlook}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e6ebf3" />
                <XAxis dataKey="hour" tick={{ fontSize: 11 }} interval={3} />
                <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line yAxisId="left" type="monotone" dataKey="demand" name="Forecast compute total" stroke="#1267e8" strokeWidth={2.2} dot={false} />
                <Line yAxisId="left" type="monotone" dataKey="arrivals" name="Forecast arrivals total" stroke="#7438ed" strokeWidth={2} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="carbon" name="Carbon intensity" stroke="#159447" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Recommended Placement" className="placement-panel">
          <div className="placement-content">
            <ResponsiveContainer width="47%" height={230}>
              <PieChart>
                <Pie data={distribution} dataKey="value" nameKey="name" innerRadius={52} outerRadius={87} paddingAngle={1}>
                  {distribution.map((row) => <Cell key={row.kind} fill={colors[row.kind]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="placement-legend">
              {distribution.map((row) => (
                <div key={row.kind}>
                  <span className="legend-dot" style={{ background: colors[row.kind] }} />
                  <span>{row.name}</span>
                  <strong>{Math.round(row.value / total * 100)}%</strong>
                </div>
              ))}
              <hr />
              <small>Infrastructure Utilization</small>
              {Object.entries(run?.result_payload.placement_summary || run?.result_payload.utilization_percent || {}).slice(0, 5).map(([id, value], index) => (
                <div className="util-row" key={id}>
                  <span>{id}</span>
                  <div><i style={{ width: `${Math.min(100, Number(value) / Math.max(1, data.workloads) * 100)}%`, background: Object.values(colors)[index % 3] }} /></div>
                  <strong>{Number(value)}</strong>
                </div>
              ))}
            </div>
          </div>
        </Panel>
      </div>

      <div className="decision-insight">
        <Leaf size={19} />
        <strong>Decision insight:</strong>
        <span>Flexible workloads are shifted toward the lowest-carbon regional windows while respecting security, reliability, capacity, affinity, and deadline constraints.</span>
      </div>

      <div className="pipeline-strip">
        {[
          ["Workload forecast", data.pipeline.workload.ready, data.pipeline.workload.source],
          ["Carbon forecast", data.pipeline.carbon.ready, data.pipeline.carbon.source],
          ["MILP result", data.pipeline.optimization.ready, data.pipeline.optimization.core_run_id],
        ].map(([label, ready, detail]) => (
          <div key={String(label)}>
            {ready ? <CircleCheck size={19} /> : <Database size={19} />}
            <span><strong>{label}</strong><small>{detail || "Not synchronized"}</small></span>
          </div>
        ))}
      </div>

      <div className="dashboard-grid bottom-grid">
        <Panel title="Optimized Task Schedule">
          <div className="schedule-table">
            <div className="schedule-head"><span>Task</span><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
            {(run?.placements || []).slice(0, 6).map((placement) => (
              <div className="schedule-row" key={placement.id}>
                <span>{placement.workload_name || placement.workload_id}</span>
                <div className="schedule-track">
                  <i
                    style={{
                      left: `${placement.start_hour / 24 * 100}%`,
                      width: `${Math.max(5, placement.duration_hours / 24 * 100)}%`,
                      background: colors[placement.environment_kind]
                    }}
                  >{placement.environment_id}</i>
                </div>
              </div>
            ))}
            {!run?.placements?.length && <div className="empty-inline">Run optimization to generate the task schedule.</div>}
          </div>
        </Panel>

        <Panel title="Regional Carbon Forecast">
          <div className="region-list">
            {Array.from(new Set(data.carbon_series.map((row) => row.region_code))).slice(0, 3).map((region, index) => {
              const rows = data.carbon_series.filter((row) => row.region_code === region);
              const average = rows.reduce((sum, row) => sum + row.intensity_gco2_kwh, 0) / Math.max(1, rows.length);
              return (
                <div className="region-row" key={region}>
                  <div className={`region-symbol region-${index}`}><Leaf size={17} /></div>
                  <div className="region-name"><strong>{region}</strong><span>{rows[0]?.region_label}</span></div>
                  <strong className={`region-value value-${index}`}>{Math.round(average)} <small>gCO2e/kWh</small></strong>
                  <div className="sparkline">
                    <ResponsiveContainer width="100%" height={48}>
                      <AreaChart data={rows}>
                        <Area type="monotone" dataKey="intensity_gco2_kwh" stroke={["#159447", "#7538df", "#f18a00"][index]} fill="transparent" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
    </div>
  );
}
