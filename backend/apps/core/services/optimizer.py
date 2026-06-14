import os
import time
from collections import defaultdict

from django.db import transaction

from ..models import (
    CarbonForecast,
    InfrastructureEnvironment,
    OptimizationRun,
    TaskPlacement,
    WorkloadForecast,
)


def _latest_workloads():
    latest_import = (
        WorkloadForecast.objects.order_by("-data_import__created_at")
        .values_list("data_import_id", flat=True)
        .first()
    )
    return list(WorkloadForecast.objects.filter(data_import_id=latest_import).order_by("id"))


def _carbon_lookup():
    rows = CarbonForecast.objects.order_by("region_code", "horizon_hours", "-data_import__created_at")
    result = {}
    for row in rows:
        result.setdefault((row.region_code, row.horizon_hours), row.intensity_gco2_kwh)
    return result


def _allowed(task, env):
    if env.security_rating < task.security_level or env.reliability < task.required_reliability:
        return False
    if task.affinity == "MF" and env.kind != "MF":
        return False
    if task.affinity == "CL" and env.kind == "MF":
        return False
    return task.memory_gb <= env.capacity_memory_gb


def _duration(task, env):
    # Calibrated to the baseline compute-size scale, which is not a raw wall-clock hour.
    performance = max(1.0, env.capacity_cpu / 2)
    return max(0.25, task.compute_size / (performance * max(1, task.max_parallelism)))


def _weights(scenario):
    if scenario.strategy == "cost":
        return 4.0, 0.5, 1.0
    if scenario.strategy == "carbon":
        return 0.5, 4.0, 1.0
    if scenario.strategy == "sla":
        return 1.0, 1.0, 4.0
    return scenario.cost_weight, scenario.carbon_weight, scenario.risk_weight


def _gurobi_env(gp):
    access = os.getenv("GUROBI_WLSACCESSID")
    secret = os.getenv("GUROBI_WLSSECRET")
    license_id = os.getenv("GUROBI_LICENSEID")
    if access and secret and license_id:
        return gp.Env(params={
            "WLSACCESSID": access,
            "WLSSECRET": secret,
            "LICENSEID": int(license_id),
        })
    return None


@transaction.atomic
def execute_optimization(run: OptimizationRun) -> OptimizationRun:
    started = time.perf_counter()
    run.status = OptimizationRun.Status.RUNNING
    run.save(update_fields=["status", "updated_at"])
    tasks = _latest_workloads()
    envs = list(InfrastructureEnvironment.objects.filter(enabled=True).order_by("external_id"))
    carbon = _carbon_lookup()
    scenario = run.scenario

    if not tasks or not envs:
        run.status = OptimizationRun.Status.FAILED
        run.error_message = "Workload forecasts and infrastructure must be imported before optimization."
        run.save()
        return run

    try:
        import gurobipy as gp
        from gurobipy import GRB, quicksum

        model_env = _gurobi_env(gp)
        model = gp.Model("HybridOps", env=model_env) if model_env else gp.Model("HybridOps")
        model.Params.OutputFlag = 0
        model.Params.TimeLimit = float(os.getenv("OPTIMIZER_TIME_LIMIT_SECONDS", "60"))
        model.Params.MIPGap = float(os.getenv("OPTIMIZER_MIP_GAP", "0.01"))

        allowed = [(task.id, env.id) for task in tasks for env in envs if _allowed(task, env)]
        if any(not any(task.id == tid for tid, _ in allowed) for task in tasks):
            raise ValueError("At least one workload has no eligible environment.")

        x = model.addVars(allowed, vtype=GRB.BINARY, name="place")
        starts = model.addVars([task.id for task in tasks], lb=0, ub=scenario.deadline_hours, name="start")
        ends = model.addVars([task.id for task in tasks], lb=0, ub=scenario.deadline_hours, name="end")

        task_by_id = {task.id: task for task in tasks}
        env_by_id = {env.id: env for env in envs}
        external_to_id = {task.external_id: task.id for task in tasks}
        cost_terms, carbon_terms, risk_terms = [], [], []
        for task_id, env_id in allowed:
            task, env = task_by_id[task_id], env_by_id[env_id]
            duration = _duration(task, env)
            carbon_region = scenario.administrator_config.get("carbon_region_map", {}).get(env.region, env.region)
            intensity = carbon.get((carbon_region, 1), env.raw_payload.get("CI", 300))
            cost = duration * env.cost_per_compute_hour + (
                task.data_gravity_size_gb * 0.2 if task.data_gravity and env.kind != "MF" else 0
            )
            emissions = duration * env.power_kw * env.pue * intensity
            risk = (1 - env.reliability) * 100 + (2 if task.interruptible and env.kind == "PU" else 0)
            cost_terms.append(cost * x[task_id, env_id])
            carbon_terms.append(emissions * x[task_id, env_id])
            risk_terms.append(risk * x[task_id, env_id])

        for task in tasks:
            eligible = [env.id for env in envs if (task.id, env.id) in x]
            model.addConstr(quicksum(x[task.id, env_id] for env_id in eligible) == 1)
            model.addConstr(
                ends[task.id] == starts[task.id] + quicksum(
                    _duration(task, env_by_id[env_id]) * x[task.id, env_id] for env_id in eligible
                )
            )
            for predecessor in task.predecessors:
                pred_id = external_to_id.get(predecessor)
                if pred_id:
                    model.addConstr(starts[task.id] >= ends[pred_id])

        for env in envs:
            eligible_tasks = [task for task in tasks if (task.id, env.id) in x]
            model.addConstr(
                quicksum(task.memory_gb * x[task.id, env.id] for task in eligible_tasks)
                <= env.capacity_memory_gb
            )
            model.addConstr(
                quicksum(min(task.max_parallelism, task.compute_size) * x[task.id, env.id] for task in eligible_tasks)
                <= env.capacity_cpu
            )

        total_cost = quicksum(cost_terms)
        total_carbon = quicksum(carbon_terms)
        total_risk = quicksum(risk_terms)
        wc, wk, wr = _weights(scenario)
        model.setObjective(
            wc * total_cost / max(1, scenario.cost_target)
            + wk * total_carbon / max(1, scenario.carbon_target_g)
            + wr * total_risk / max(1, scenario.risk_target),
            GRB.MINIMIZE,
        )
        model.optimize()

        if model.SolCount == 0:
            run.status = OptimizationRun.Status.INFEASIBLE
            run.error_message = "The selected scenario has no feasible placement."
            run.solve_seconds = time.perf_counter() - started
            run.save()
            return run

        placements = []
        kind_counts = defaultdict(int)
        region_counts = defaultdict(int)
        utilization = defaultdict(float)
        for task in tasks:
            selected = next(env for env in envs if (task.id, env.id) in x and x[task.id, env.id].X > 0.5)
            duration = _duration(task, selected)
            carbon_region = scenario.administrator_config.get("carbon_region_map", {}).get(selected.region, selected.region)
            intensity = carbon.get((carbon_region, 1), selected.raw_payload.get("CI", 300))
            task_cost = duration * selected.cost_per_compute_hour
            task_carbon = duration * selected.power_kw * selected.pue * intensity
            placements.append(TaskPlacement(
                run=run,
                workload=task,
                environment=selected,
                start_hour=starts[task.id].X,
                duration_hours=duration,
                end_hour=ends[task.id].X,
                pricing_mode="on-demand" if selected.kind == "PU" else "allocated",
                cost=task_cost,
                carbon_g=task_carbon,
                risk=(1 - selected.reliability) * 100,
            ))
            kind_counts[selected.kind] += 1
            region_counts[selected.region] += 1
            utilization[selected.external_id] += task.memory_gb / selected.capacity_memory_gb * 100

        run.status = OptimizationRun.Status.OPTIMAL if model.Status == GRB.OPTIMAL else OptimizationRun.Status.FEASIBLE
        run.objective_value = model.ObjVal
        run.mip_gap = model.MIPGap
        run.solve_seconds = time.perf_counter() - started
        run.total_cost = total_cost.getValue()
        run.total_carbon_g = total_carbon.getValue()
        run.total_risk = total_risk.getValue()
        run.workload_count = len(tasks)
        run.input_snapshot = {
            "workload_ids": [task.external_id for task in tasks],
            "environment_ids": [env.external_id for env in envs],
            "scenario": scenario.name,
        }
        run.result_payload = {
            "placement_by_kind": dict(kind_counts),
            "placement_by_region": dict(region_counts),
            "utilization_percent": {key: round(value, 1) for key, value in utilization.items()},
            "constraints_satisfied": True,
        }
        run.save()
        TaskPlacement.objects.bulk_create(placements)
    except Exception as exc:
        run.status = OptimizationRun.Status.FAILED
        run.solve_seconds = time.perf_counter() - started
        run.error_message = str(exc)
        run.save()
    return run
