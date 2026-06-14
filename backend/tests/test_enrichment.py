from apps.core.services.enrichment import estimate_bandwidth_gbps, normalize_workload


def test_provided_bandwidth_is_preserved():
    value, source = estimate_bandwidth_gbps({"id": "task", "bw": 4})
    assert value == 4
    assert source == "provided"


def test_bandwidth_estimate_is_stable():
    task = {"id": "t1", "archetype": "etl-pipeline-large", "cs": 21.14, "mem": 32}
    first = estimate_bandwidth_gbps(task)
    second = estimate_bandwidth_gbps(task)
    assert first == second
    assert first[0] > 0
    assert first[1] == "estimated"


def test_normalization_preserves_raw_payload():
    task = {"id": "t1", "cs": 5, "mem": 2, "mu": 1, "TS": 2}
    normalized = normalize_workload(task)
    assert normalized["external_id"] == "t1"
    assert normalized["raw_payload"] == task

