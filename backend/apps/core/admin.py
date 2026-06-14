from django.contrib import admin
from .models import (
    CarbonForecast,
    DataImport,
    InfrastructureEnvironment,
    OptimizationRun,
    Scenario,
    TaskPlacement,
    WorkloadForecast,
)

admin.site.register([
    DataImport,
    WorkloadForecast,
    CarbonForecast,
    InfrastructureEnvironment,
    Scenario,
    OptimizationRun,
    TaskPlacement,
])

