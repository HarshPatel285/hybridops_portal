from rest_framework import serializers
from .models import (
    CarbonForecast,
    InfrastructureEnvironment,
    OptimizationRun,
    Scenario,
    TaskPlacement,
    WorkloadForecast,
)


class WorkloadSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkloadForecast
        fields = "__all__"


class CarbonSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonForecast
        fields = "__all__"


class EnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfrastructureEnvironment
        fields = "__all__"


class ScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scenario
        fields = "__all__"


class PlacementSerializer(serializers.ModelSerializer):
    workload_id = serializers.CharField(source="workload.external_id", read_only=True)
    workload_name = serializers.CharField(source="workload.archetype", read_only=True)
    environment_id = serializers.CharField(source="environment.external_id", read_only=True)
    environment_kind = serializers.CharField(source="environment.kind", read_only=True)
    region = serializers.CharField(source="environment.region", read_only=True)

    class Meta:
        model = TaskPlacement
        fields = "__all__"


class RunSerializer(serializers.ModelSerializer):
    placements = PlacementSerializer(many=True, read_only=True)
    scenario_name = serializers.CharField(source="scenario.name", read_only=True)

    class Meta:
        model = OptimizationRun
        fields = "__all__"

