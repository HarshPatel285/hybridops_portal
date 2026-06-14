import hashlib
import json
from datetime import datetime, timedelta, timezone

from django.db import transaction
from django.utils.dateparse import parse_datetime

from ..models import CarbonForecast, DataImport, InfrastructureEnvironment, WorkloadForecast
from .enrichment import normalize_workload


def _checksum(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@transaction.atomic
def import_workload_payload(payload: dict, source_name: str = "workload-forecast.json") -> DataImport:
    checksum = _checksum(payload)
    existing = DataImport.objects.filter(kind=DataImport.Kind.WORKLOAD, checksum=checksum).first()
    if existing:
        return existing
    record = DataImport.objects.create(
        kind=DataImport.Kind.WORKLOAD,
        source_name=source_name,
        checksum=checksum,
        raw_payload=payload,
        metadata={
            **payload.get("metadata", {}),
            "model_performance": payload.get("model_performance", []),
        },
    )
    for task in payload.get("tasks", []):
        WorkloadForecast.objects.create(data_import=record, **normalize_workload(task))
    return record


@transaction.atomic
def import_carbon_payload(payload: dict, source_name: str = "carbon-forecast.json") -> DataImport:
    checksum = _checksum(payload)
    existing = DataImport.objects.filter(kind=DataImport.Kind.CARBON, checksum=checksum).first()
    if existing:
        return existing
    record = DataImport.objects.create(
        kind=DataImport.Kind.CARBON,
        source_name=source_name,
        checksum=checksum,
        raw_payload=payload,
        metadata={
            **payload.get("metadata", {}),
            "model_performance": payload.get("model_performance", []),
        },
    )
    rows = payload.get("multi_horizon_1_to_24h_forecasts") or payload.get("forecasts") or []
    now = datetime.now(timezone.utc)
    for row in rows:
        horizon = int(row.get("forecast_horizon_hours", 1))
        timestamp = parse_datetime(str(row.get("forecast_timestamp_utc", ""))) or now + timedelta(hours=horizon)
        CarbonForecast.objects.create(
            data_import=record,
            region_code=str(row.get("zone", row.get("region", "UNKNOWN"))),
            region_label=str(row.get("zone_label", row.get("region", "Unknown"))),
            forecast_timestamp=timestamp,
            horizon_hours=horizon,
            intensity_gco2_kwh=float(
                row.get("predicted_carbon_intensity_gco2eq_per_kwh", row.get("carbon_intensity", 0))
            ),
            model_name=str(row.get("model", "")),
            confidence=row.get("confidence"),
            renewable_availability=row.get("renewable_availability"),
            raw_payload=row,
        )
    return record


@transaction.atomic
def import_infrastructure_payload(payload: dict) -> DataImport:
    checksum = _checksum(payload)
    record = DataImport.objects.filter(kind=DataImport.Kind.INFRASTRUCTURE, checksum=checksum).first()
    if not record:
        record = DataImport.objects.create(
            kind=DataImport.Kind.INFRASTRUCTURE,
            source_name=payload.get("instance_name", "infrastructure.json"),
            checksum=checksum,
            raw_payload=payload,
            metadata={"globals": payload.get("globals", {}), "metadata": payload.get("metadata", {})},
        )
    region_cycle = {"MF": ["EU", "US"], "PR": ["EU", "US", "APAC"], "PU": ["EU", "US", "APAC"]}
    kind_counts = {"MF": 0, "PR": 0, "PU": 0}
    for env_id, env in payload.get("environments", {}).items():
        kind = env["kind"]
        index = kind_counts[kind]
        kind_counts[kind] += 1
        region = env.get("GEO") or env.get("region") or region_cycle[kind][index % len(region_cycle[kind])]
        types = env.get("types", {})
        cpu = sum(float(t.get("core", 1)) * int(t.get("slots", 1)) for t in types.values())
        memory = sum(float(t.get("ram", 1)) * int(t.get("slots", 1)) for t in types.values())
        sample_type = next(iter(types.values()), {})
        cost = (
            sample_type.get("pr_MIPS")
            or sample_type.get("pr_PR")
            or sample_type.get("pr_OD")
            or 0.12
        )
        InfrastructureEnvironment.objects.update_or_create(
            external_id=env_id,
            defaults={
                "name": env.get("display_name", f"{env_id} · {region}"),
                "kind": kind,
                "region": region,
                "security_rating": int(env.get("RS", 3)),
                "reliability": float(env.get("rho", 0.99)),
                "power_kw": float(env.get("power_kW", env.get("P", 3))),
                "pue": float(env.get("PUE_default", 1.2)),
                "capacity_cpu": max(1, cpu),
                "capacity_memory_gb": max(1, memory),
                "cost_per_compute_hour": float(cost),
                "instance_types": types,
                "raw_payload": env,
            },
        )
    return record
