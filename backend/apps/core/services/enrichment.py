import hashlib
import math


def estimate_bandwidth_gbps(task: dict) -> tuple[float, str]:
    """Derive a stable estimate when the source dataset has no bandwidth feature."""
    value = task.get("bw") or task.get("bandwidth_gbps")
    if value is not None:
        return max(0.25, float(value)), "provided"

    memory = max(1.0, float(task.get("mem", task.get("memory_gb", 1))))
    compute = max(0.1, float(task.get("cs", task.get("compute_size", 1))))
    archetype = str(task.get("archetype", task.get("id", "workload"))).lower()
    estimate = 0.5 + 0.16 * math.sqrt(memory) + 0.035 * math.sqrt(compute)
    if any(token in archetype for token in ("etl", "data", "pipeline", "web", "api")):
        estimate *= 1.35

    digest = hashlib.sha256(archetype.encode("utf-8")).digest()
    stable_adjustment = 0.9 + (digest[0] / 255) * 0.2
    return round(min(10.0, max(0.5, estimate * stable_adjustment)), 2), "estimated"


def normalize_workload(task: dict) -> dict:
    bandwidth, source = estimate_bandwidth_gbps(task)
    return {
        "external_id": str(task["id"]),
        "archetype": str(task.get("archetype", task["id"])).replace("_", "-"),
        "compute_size": float(task.get("cs", 1)),
        "memory_gb": float(task.get("mem", 1)),
        "bandwidth_gbps": bandwidth,
        "bandwidth_source": source,
        "max_parallelism": max(1, int(task.get("mu", 1))),
        "security_level": max(1, int(task.get("TS", 1))),
        "interruptible": bool(task.get("intr", 0)),
        "specialty_processor": bool(task.get("sp", 0)),
        "data_gravity": bool(task.get("dg", 0)),
        "data_gravity_size_gb": float(task.get("dgs", 0)),
        "required_reliability": float(task.get("rel", 0.95)),
        "affinity": str(task.get("aff", "ANY")),
        "predecessors": list(task.get("predecessors", [])),
        "forecast_job_arrivals": max(0, int(task.get("forecast_job_arrivals", 0))),
        "raw_payload": task,
    }

