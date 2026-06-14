import json
from collections import Counter
from pathlib import Path

from django.db import transaction
from django.utils.dateparse import parse_datetime

from ..models import (
    DataImport,
    InfrastructureEnvironment,
    OptimizationRun,
    Scenario,
    TaskPlacement,
    WorkloadForecast,
)
from .importers import (
    _checksum,
    import_carbon_payload,
    import_infrastructure_payload,
    import_workload_payload,
)


REQUIRED_ARTIFACTS = {
    "workload": Path("workload/instance_forecast_enriched.json"),
    "carbon": Path("carbon/carbon_forecast_optimization_input.json"),
    "instance": Path("optimizer/prepared_instance.json"),
    "result": Path("optimizer/optimization_result.json"),
}


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_artifact_directory(artifact_dir: Path) -> dict[str, Path]:
    paths = {name: artifact_dir / relative for name, relative in REQUIRED_ARTIFACTS.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required HybridOps core artifacts: " + ", ".join(missing))
    return paths


def _scenario_from_instance(instance: dict) -> Scenario:
    globals_ = instance.get("globals", {})
    goals = globals_.get("goal_targets", {})
    weights = globals_.get("goal_weights", {})
    Scenario.objects.filter(is_default=True).update(is_default=False)
    scenario, _ = Scenario.objects.update_or_create(
        name="Core Production Baseline",
        defaults={
            "description": "Configuration imported from the finalized HybridOps core prepared instance.",
            "strategy": Scenario.Strategy.BALANCED,
            "forecast_horizon_hours": 24,
            "deadline_hours": float(globals_.get("deadline", 72)),
            "cost_target": float(goals.get("cost", 650)),
            "carbon_target_g": float(goals.get("carbon", 85000)),
            "risk_target": float(goals.get("risk", 20)),
            "cost_weight": float(weights.get("cost", 1)),
            "carbon_weight": float(weights.get("carbon", 1)),
            "risk_weight": float(weights.get("risk", 1)),
            "regional_carbon_caps": globals_.get("regional_carbon_caps", {}),
            "administrator_config": {
                "source": "hybridops_core/prepared_instance.json",
                "carbon_region_map": {
                    env.get("GEO"): env.get("carbon_zone", env.get("GEO"))
                    for env in instance.get("environments", {}).values()
                    if env.get("GEO")
                },
                "bandwidth_policy": "use-core-estimate-when-source-feature-is-absent",
            },
            "is_default": True,
        },
    )
    return scenario


@transaction.atomic
def import_optimizer_result(result: dict, instance: dict) -> OptimizationRun:
    core_run_id = str(result.get("run_id", ""))
    existing = OptimizationRun.objects.filter(result_payload__core_run_id=core_run_id).first()
    if existing:
        return existing

    scenario = _scenario_from_instance(instance)
    solver = result.get("solver", {})
    kpis = result.get("kpis", {})
    status_name = str(solver.get("status", "failed")).lower()
    status = {
        "optimal": OptimizationRun.Status.OPTIMAL,
        "feasible": OptimizationRun.Status.FEASIBLE,
        "infeasible": OptimizationRun.Status.INFEASIBLE,
    }.get(status_name, OptimizationRun.Status.FAILED)
    placements = result.get("placements", [])
    placement_by_kind = dict(Counter(row.get("environment_kind") for row in placements))
    placement_by_region = dict(Counter(row.get("region") for row in placements))

    run = OptimizationRun.objects.create(
        scenario=scenario,
        status=status,
        solver=str(solver.get("name", "Gurobi")),
        objective_value=solver.get("objective_value"),
        mip_gap=solver.get("mip_gap"),
        solve_seconds=solver.get("runtime_seconds"),
        total_cost=kpis.get("total_cost"),
        total_carbon_g=kpis.get("total_carbon_gco2"),
        total_risk=kpis.get("spot_risk"),
        workload_count=int(result.get("instance", {}).get("task_count", len(placements))),
        input_snapshot={
            "prepared_instance_checksum": _checksum(instance),
            "environment_ids": list(instance.get("environments", {})),
            "workload_ids": [task.get("id") for task in instance.get("tasks", [])],
        },
        result_payload={
            **result,
            "core_run_id": core_run_id,
            "placement_by_kind": placement_by_kind,
            "placement_by_region": placement_by_region,
            "utilization_percent": {},
            "constraints_satisfied": status in {
                OptimizationRun.Status.OPTIMAL,
                OptimizationRun.Status.FEASIBLE,
            } and not result.get("diagnostics"),
            "source": "hybridops_core/optimization_result.json",
        },
        error_message="; ".join(map(str, result.get("diagnostics", []))),
    )
    generated_at = parse_datetime(str(result.get("generated_at_utc", "")))
    if generated_at:
        OptimizationRun.objects.filter(pk=run.pk).update(created_at=generated_at, updated_at=generated_at)
        run.refresh_from_db()

    workload_map = {
        row.external_id: row
        for row in WorkloadForecast.objects.filter(
            data_import_id=WorkloadForecast.objects.order_by("-data_import__created_at")
            .values_list("data_import_id", flat=True)
            .first()
        )
    }
    environment_map = {
        row.external_id: row for row in InfrastructureEnvironment.objects.all()
    }
    rows = []
    for placement in placements:
        workload = workload_map.get(str(placement.get("task_id")))
        environment = environment_map.get(str(placement.get("environment_id")))
        if not workload or not environment:
            continue
        start = float(placement.get("start_time_hours", 0))
        duration = float(placement.get("runtime_hours", 0))
        rows.append(TaskPlacement(
            run=run,
            workload=workload,
            environment=environment,
            start_hour=start,
            duration_hours=duration,
            end_hour=float(placement.get("finish_time_hours", start + duration)),
            pricing_mode=str(placement.get("pricing_mode") or "allocated"),
            constraint_notes=[
                f"instance_type={placement.get('instance_type')}",
                f"slot_id={placement.get('slot_id')}",
            ],
        ))
    TaskPlacement.objects.bulk_create(rows)
    return run


@transaction.atomic
def sync_core_artifacts(artifact_dir: Path) -> dict:
    paths = validate_artifact_directory(artifact_dir)
    workload = _read_json(paths["workload"])
    carbon = _read_json(paths["carbon"])
    instance = _read_json(paths["instance"])
    result = _read_json(paths["result"])

    workload_import = import_workload_payload(workload, paths["workload"].name)
    carbon_import = import_carbon_payload(carbon, paths["carbon"].name)
    infrastructure_import = import_infrastructure_payload(instance)
    run = import_optimizer_result(result, instance)

    return {
        "artifact_directory": str(artifact_dir),
        "workload_import_id": workload_import.id,
        "workloads": workload_import.workloads.count(),
        "carbon_import_id": carbon_import.id,
        "carbon_rows": carbon_import.carbon_rows.count(),
        "infrastructure_import_id": infrastructure_import.id,
        "environments": InfrastructureEnvironment.objects.count(),
        "optimization_run_id": run.id,
        "core_run_id": run.result_payload.get("core_run_id"),
        "status": run.status,
    }
