import os
from pathlib import Path

from django.db.models import Avg, Count
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import CarbonForecast, DataImport, InfrastructureEnvironment, OptimizationRun, Scenario, WorkloadForecast
from .serializers import (
    CarbonSerializer,
    EnvironmentSerializer,
    RunSerializer,
    ScenarioSerializer,
    WorkloadSerializer,
)
from .services.importers import import_carbon_payload, import_infrastructure_payload, import_workload_payload
from .services.core_sync import sync_core_artifacts
from .services.optimizer import execute_optimization


def _latest_import_queryset(model):
    import_id = model.objects.order_by("-data_import__created_at").values_list("data_import_id", flat=True).first()
    return model.objects.filter(data_import_id=import_id) if import_id else model.objects.none()


class WorkloadViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WorkloadSerializer

    def get_queryset(self):
        return _latest_import_queryset(WorkloadForecast).order_by("external_id")


class CarbonViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CarbonSerializer

    def get_queryset(self):
        return _latest_import_queryset(CarbonForecast).order_by("region_code", "horizon_hours")


class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = InfrastructureEnvironment.objects.all().order_by("external_id")
    serializer_class = EnvironmentSerializer


class ScenarioViewSet(viewsets.ModelViewSet):
    queryset = Scenario.objects.all().order_by("-is_default", "name")
    serializer_class = ScenarioSerializer

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        scenario = self.get_object()
        run = OptimizationRun.objects.create(scenario=scenario)
        execute_optimization(run)
        return Response(RunSerializer(run).data, status=status.HTTP_201_CREATED)


class RunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OptimizationRun.objects.select_related("scenario").prefetch_related(
        "placements__workload", "placements__environment"
    ).order_by("-created_at")
    serializer_class = RunSerializer


@api_view(["POST"])
def import_workloads(request):
    record = import_workload_payload(request.data, request.query_params.get("source", "api-upload.json"))
    return Response({"import_id": record.id, "rows": record.workloads.count()}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def import_carbon(request):
    record = import_carbon_payload(request.data, request.query_params.get("source", "api-upload.json"))
    return Response({"import_id": record.id, "rows": record.carbon_rows.count()}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def import_infrastructure(request):
    record = import_infrastructure_payload(request.data)
    return Response({"import_id": record.id, "rows": InfrastructureEnvironment.objects.count()}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def overview(request):
    latest_run = OptimizationRun.objects.prefetch_related("placements__environment").order_by("-created_at").first()
    workloads = _latest_import_queryset(WorkloadForecast)
    carbon = _latest_import_queryset(CarbonForecast)
    workload_import = DataImport.objects.filter(kind=DataImport.Kind.WORKLOAD).order_by("-created_at").first()
    carbon_import = DataImport.objects.filter(kind=DataImport.Kind.CARBON).order_by("-created_at").first()
    response = {
        "workloads": workloads.count(),
        "average_compute": workloads.aggregate(value=Avg("compute_size"))["value"] or 0,
        "regions": carbon.values("region_code").distinct().count(),
        "carbon_series": list(carbon.values(
            "region_code", "region_label", "horizon_hours", "forecast_timestamp", "intensity_gco2_kwh"
        )),
        "workload_series": list(workloads.values(
            "external_id", "archetype", "compute_size", "memory_gb", "forecast_job_arrivals"
        )),
        "latest_run": RunSerializer(latest_run).data if latest_run else None,
        "environment_summary": list(
            InfrastructureEnvironment.objects.values("kind").annotate(count=Count("id"))
        ),
        "pipeline": {
            "workload": {
                "ready": bool(workload_import),
                "source": workload_import.source_name if workload_import else None,
                "checksum": workload_import.checksum if workload_import else None,
                "generated_at": workload_import.metadata.get("generated_at") if workload_import else None,
                "models_selected": workload_import.metadata.get("models_selected", {}) if workload_import else {},
                "model_performance": workload_import.metadata.get("model_performance", []) if workload_import else [],
            },
            "carbon": {
                "ready": bool(carbon_import),
                "source": carbon_import.source_name if carbon_import else None,
                "checksum": carbon_import.checksum if carbon_import else None,
                "generated_at": carbon_import.metadata.get("generated_at_utc") if carbon_import else None,
                "model_performance": carbon_import.metadata.get("model_performance", []) if carbon_import else [],
            },
            "optimization": {
                "ready": bool(latest_run),
                "core_run_id": latest_run.result_payload.get("core_run_id") if latest_run else None,
                "source": latest_run.result_payload.get("source") if latest_run else None,
            },
        },
    }
    return Response(response)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "database": "postgresql"})


@api_view(["POST"])
def sync_core(request):
    artifact_dir = Path(os.getenv("HYBRIDOPS_CORE_ARTIFACTS_DIR", "/core/artifacts"))
    try:
        return Response(sync_core_artifacts(artifact_dir))
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def export_artifact(request, kind):
    if kind == "workload":
        record = DataImport.objects.filter(kind=DataImport.Kind.WORKLOAD).order_by("-created_at").first()
        payload = record.raw_payload if record else None
    elif kind == "carbon":
        record = DataImport.objects.filter(kind=DataImport.Kind.CARBON).order_by("-created_at").first()
        payload = record.raw_payload if record else None
    elif kind == "optimization":
        run = OptimizationRun.objects.order_by("-created_at").first()
        payload = run.result_payload if run else None
    else:
        return Response({"detail": "Unknown artifact kind."}, status=status.HTTP_404_NOT_FOUND)
    if payload is None:
        return Response({"detail": "Artifact has not been synchronized."}, status=status.HTTP_404_NOT_FOUND)
    return Response(payload)
