import pytest

from apps.core.models import DataImport, WorkloadForecast
from apps.core.services.importers import import_workload_payload


@pytest.mark.django_db
def test_workload_import_stores_raw_and_normalized_data():
    payload = {
        "metadata": {"forecast_horizon_hours": 24},
        "tasks": [{"id": "t1", "cs": 9, "mem": 4, "mu": 2, "TS": 1}],
    }
    record = import_workload_payload(payload)
    workload = WorkloadForecast.objects.get()
    assert DataImport.objects.count() == 1
    assert record.raw_payload == payload
    assert workload.compute_size == 9
    assert workload.bandwidth_source == "estimated"

