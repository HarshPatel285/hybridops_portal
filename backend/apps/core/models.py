from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DataImport(TimestampedModel):
    class Kind(models.TextChoices):
        WORKLOAD = "workload", "Workload forecast"
        CARBON = "carbon", "Carbon forecast"
        INFRASTRUCTURE = "infrastructure", "Infrastructure"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    source_name = models.CharField(max_length=255)
    checksum = models.CharField(max_length=64, blank=True)
    raw_payload = models.JSONField()
    metadata = models.JSONField(default=dict, blank=True)


class WorkloadForecast(TimestampedModel):
    external_id = models.CharField(max_length=160)
    archetype = models.CharField(max_length=160, blank=True)
    compute_size = models.FloatField(help_text="Baseline cs parameter")
    memory_gb = models.FloatField()
    bandwidth_gbps = models.FloatField(null=True, blank=True)
    bandwidth_source = models.CharField(max_length=32, default="provided")
    max_parallelism = models.PositiveIntegerField(default=1)
    security_level = models.PositiveSmallIntegerField(default=1)
    interruptible = models.BooleanField(default=False)
    specialty_processor = models.BooleanField(default=False)
    data_gravity = models.BooleanField(default=False)
    data_gravity_size_gb = models.FloatField(default=0)
    required_reliability = models.FloatField(default=0.95)
    affinity = models.CharField(max_length=16, default="ANY")
    predecessors = models.JSONField(default=list)
    forecast_job_arrivals = models.PositiveIntegerField(default=0)
    forecast_timestamp = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict)
    data_import = models.ForeignKey(DataImport, on_delete=models.CASCADE, related_name="workloads")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["data_import", "external_id"], name="unique_workload_per_import")
        ]


class CarbonForecast(TimestampedModel):
    region_code = models.CharField(max_length=64)
    region_label = models.CharField(max_length=160)
    forecast_timestamp = models.DateTimeField()
    horizon_hours = models.PositiveSmallIntegerField()
    intensity_gco2_kwh = models.FloatField()
    model_name = models.CharField(max_length=160, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    renewable_availability = models.FloatField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict)
    data_import = models.ForeignKey(DataImport, on_delete=models.CASCADE, related_name="carbon_rows")


class InfrastructureEnvironment(TimestampedModel):
    external_id = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=2, choices=[("MF", "Mainframe"), ("PR", "Private Cloud"), ("PU", "Public Cloud")])
    region = models.CharField(max_length=64)
    security_rating = models.PositiveSmallIntegerField(default=3)
    reliability = models.FloatField(default=0.99)
    power_kw = models.FloatField()
    pue = models.FloatField(default=1)
    capacity_cpu = models.FloatField()
    capacity_memory_gb = models.FloatField()
    cost_per_compute_hour = models.FloatField()
    enabled = models.BooleanField(default=True)
    instance_types = models.JSONField(default=dict)
    raw_payload = models.JSONField(default=dict)


class Scenario(TimestampedModel):
    class Strategy(models.TextChoices):
        BALANCED = "balanced", "Balanced"
        COST = "cost", "Minimize Cost"
        CARBON = "carbon", "Minimize Carbon"
        SLA = "sla", "SLA First"

    name = models.CharField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    strategy = models.CharField(max_length=32, choices=Strategy.choices, default=Strategy.BALANCED)
    forecast_horizon_hours = models.PositiveSmallIntegerField(default=24)
    deadline_hours = models.FloatField(default=72)
    cost_target = models.FloatField(default=800)
    carbon_target_g = models.FloatField(default=100000)
    risk_target = models.FloatField(default=20)
    cost_weight = models.FloatField(default=1)
    carbon_weight = models.FloatField(default=1)
    risk_weight = models.FloatField(default=1)
    regional_carbon_caps = models.JSONField(default=dict)
    administrator_config = models.JSONField(default=dict)
    is_default = models.BooleanField(default=False)


class OptimizationRun(TimestampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        OPTIMAL = "optimal", "Optimal"
        FEASIBLE = "feasible", "Feasible"
        INFEASIBLE = "infeasible", "Infeasible"
        FAILED = "failed", "Failed"

    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name="runs")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED)
    solver = models.CharField(max_length=64, default="Gurobi")
    objective_value = models.FloatField(null=True, blank=True)
    mip_gap = models.FloatField(null=True, blank=True)
    solve_seconds = models.FloatField(null=True, blank=True)
    total_cost = models.FloatField(null=True, blank=True)
    total_carbon_g = models.FloatField(null=True, blank=True)
    total_risk = models.FloatField(null=True, blank=True)
    workload_count = models.PositiveIntegerField(default=0)
    input_snapshot = models.JSONField(default=dict)
    result_payload = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)


class TaskPlacement(models.Model):
    run = models.ForeignKey(OptimizationRun, on_delete=models.CASCADE, related_name="placements")
    workload = models.ForeignKey(WorkloadForecast, on_delete=models.PROTECT)
    environment = models.ForeignKey(InfrastructureEnvironment, on_delete=models.PROTECT)
    start_hour = models.FloatField()
    duration_hours = models.FloatField()
    end_hour = models.FloatField()
    pricing_mode = models.CharField(max_length=32, blank=True)
    cost = models.FloatField(default=0)
    carbon_g = models.FloatField(default=0)
    risk = models.FloatField(default=0)
    constraint_notes = models.JSONField(default=list)

