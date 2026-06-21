# HybridOps Portal

HybridOps is the presentation and decision-support layer for the finalized
`hybridops_core` forecasting and MILP pipeline. It uses Django REST Framework,
React, PostgreSQL, and Gurobi. The portal does not retrain or modify the
authoritative workload and carbon models.

## Data contract

The portal synchronizes these real core artifacts:

```text
artifacts/workload/instance_forecast_enriched.json
artifacts/workload/model_comparison.csv
artifacts/workload/models/manifest.json
artifacts/carbon/carbon_forecast_optimization_input.json
artifacts/carbon/carbon_model_results.csv
artifacts/carbon/models/manifest.json
artifacts/optimizer/prepared_instance.json
artifacts/optimizer/optimization_result.json
```

Raw JSON payloads, checksums, normalized records, scenario configuration,
optimization runs, and placements are persisted in PostgreSQL. Model bundles
remain in the core project and are never sent to React.

## Run with Docker

### 1. Confirm the folder layout

The default Compose configuration expects:

```text
Project/
├── Final Submission/
│   └── hybridops_core/
│       └── artifacts/
└── HybridOps/
    ├── backend/
    ├── frontend/
    └── docker-compose.yml
```

If your core is elsewhere, set its absolute path in `.env`:

```env
HYBRIDOPS_CORE_DIR=/absolute/path/to/hybridops_core
```

### 2. Configure the environment

```bash
cd "/Users/harshpatel/Desktop/Harsh WorkSpace/UNFC/Term 5/Project/HybridOps"
cp .env.example .env
```

Set a strong `DJANGO_SECRET_KEY` and PostgreSQL password. Gurobi variables are
needed only for portal-created what-if runs; the verified core result can be
viewed without solving it again.

### 3. Start Docker Desktop

Wait until Docker Desktop reports that the engine is running.

### 4. Build and start

```bash
docker compose up --build
```

PostgreSQL is exposed on host port `5433` to avoid conflicts with a local
PostgreSQL server. Inside Docker it remains on port `5432`.

### 5. Open the system

- Portal: http://localhost:5173
- API: http://localhost:8000/api/
- Health check: http://localhost:8000/api/health/
- Django admin: http://localhost:8000/admin/

At startup Django runs migrations and synchronizes the mounted core artifacts.
Synchronization is idempotent and does not duplicate an unchanged run.

## Refresh after rerunning the core

After the core produces new artifacts, click **Refresh Core Results** on the
Overview page or run:

```bash
docker compose exec backend python manage.py sync_core_artifacts
```

## Local development

Start only PostgreSQL:

```bash
docker compose up -d db
```

Backend:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
export HYBRIDOPS_CORE_ARTIFACTS_DIR="/absolute/path/to/hybridops_core/artifacts"
cd backend
python manage.py migrate
python manage.py sync_core_artifacts
python manage.py runserver
```

Frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

## Portal workflow

1. **Overview** presents verified cost, carbon, workload count, solver status,
   placement distribution, schedule, regional carbon forecast, and artifact
   readiness.
2. **Workload Forecast** shows all forecast tasks and current model metrics.
3. **Carbon Intelligence** shows 24-hour regional forecasts and model metrics.
4. **Scenario Builder** stores alternative cost, carbon, and SLA preferences.
5. **Optimization Runs** retains the verified core run and subsequent history.
6. **Task Placement** lists each task, environment, region, pricing mode, and
   timing decision.
7. **Reports** exports the structured optimizer result as JSON.
8. **Admin Configuration** manages infrastructure metadata persisted in
   PostgreSQL.

## Verification

```bash
cd backend
pytest
```

```bash
cd frontend
npm run build
```

The finalized verified run should display:

```text
Status: Optimal
Tasks: 28 / 28
Total cost: 179.93
Carbon: 84.98 kgCO2e
Runtime: 10.06 seconds
Makespan: 31.65 hours
```
## Contact

**Harsh Patel**  
hsp498@gmail.com 
