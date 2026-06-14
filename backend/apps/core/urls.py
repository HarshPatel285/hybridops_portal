from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("workloads", views.WorkloadViewSet, basename="workload")
router.register("carbon", views.CarbonViewSet, basename="carbon")
router.register("environments", views.EnvironmentViewSet)
router.register("scenarios", views.ScenarioViewSet)
router.register("runs", views.RunViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("health/", views.health),
    path("overview/", views.overview),
    path("imports/workloads/", views.import_workloads),
    path("imports/carbon/", views.import_carbon),
    path("imports/infrastructure/", views.import_infrastructure),
    path("sync/core/", views.sync_core),
    path("exports/<str:kind>/", views.export_artifact),
]
