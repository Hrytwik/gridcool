# GridCool (Hackathon Build)

GridCool is a demo-safe demand-response VPP for Chennai AC fleets.

Monorepo:
- `frontend/` - Vite + React + Tailwind mission-control dashboard
- `backend/` - FastAPI + WebSockets + simulation + ML forecasting + APScheduler + Mongo (best effort)

## Run locally

Copy env:

```bash
cp .env.example .env
```

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --app-dir . --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

Open `http://localhost:5173/`.

## Key backend flows

- **WebSocket snapshot v1** at `/ws/dashboard` remains backward-compatible.
- **ML forecast endpoint** at `/ml/predict` returns 12-hour load/stress forecast.
- **Demo-safe fallback**: missing/corrupt ML artifacts automatically use simulation forecast.
- **Scheduler orchestration**:
  - forecast cache refresh every `ML_FORECAST_REFRESH_MINUTES`
  - auto-dispatch check every minute in a 60-120 minute peak window
- **Manual overrides win**:
  - `/demo/force-stress` always overrides ML stress while active
  - `/demo/trigger-dispatch` works independent of auto-dispatch cooldown

## Demo endpoints

- `POST /demo/force-stress` - force stress score for N minutes
- `POST /demo/trigger-dispatch` - start dispatch immediately
- `POST /demo/enroll-building` - enroll a building (appears on map)

## Thermal APIs

- `GET /thermal/buildings/{building_id}` - thermal summary for one building
- `GET /thermal/fleet` - all fingerprints + fleet summary
- `POST /thermal/recalibrate/{building_id}` - trigger recalibration

## ML + dataset foundation

### Dataset generation

Generate Chennai hourly dataset:

```bash
cd backend
python -m app.ml.generate_synthetic_chennai_load --seed 42 --year 2025
```

Output: `backend/data/chennai_hourly_load.csv`

Schema:
- `timestamp, hour_of_day, day_of_week, month, is_weekend, is_holiday, season`
- `temp_c, feels_like_c, humidity, wind_speed, cloud_cover`
- `heatwave_flag, event_flag`
- `load_mw, load_mw_lag_24h, stress_score, is_stress_event`

### Model training

```bash
cd backend
python -m app.ml.train_forecast --data backend/data/chennai_hourly_load.csv
```

Artifacts saved under `ML_ARTIFACT_DIR` (default `backend/artifacts/ml`):
- `load_forecast_xgb.joblib`
- `load_forecast_meta.json`

### Predict API

`GET /ml/predict?horizon_hours=12`

Returns:
- `generated_at`
- `horizon_hours`
- `forecast_load_mw`
- `forecast_stress_score`
- `peak_hour_index`
- `peak_in_minutes`
- `artifact_status` (`loaded|missing|error`)
- `source` (`ml|sim_fallback`)

## Dataset sources and references

The project dataset is **synthetic but weather-grounded** and calibrated using public references:

1. **OpenWeatherMap (Chennai historical weather)**
   - Source for hourly weather features (`temp`, `feels_like`, `humidity`, `wind_speed`, `clouds`)
   - API docs: [One Call API 3.0](https://openweathermap.org/api/one-call-3)

2. **Public India/Tamil Nadu load references (calibration references)**
   - Used to shape realistic demand ranges/curves (daily peaks, seasonal shifts), not copied directly as target labels
   - UCI/Kaggle style references mentioned in the project brief:
     - Tamil Nadu Electricity Board hourly readings (UCI/Kaggle variants)
     - Hourly Load India - Electrical Load Forecasting (Kaggle)

## Phase 2 orchestration notes

- Scheduler and Mongo writes are best-effort and should not crash the demo.
- Credits ledger entries are written to:
  - `credits_ledger`
  - `dispatch_events`
- MirAIe integration seam exists at `backend/app/integrations/miraie_adapter.py`:
  - `DemoMiraieAdapter` (active, deterministic)
  - `RealMiraieAdapterStub` (safe stub for future production wiring)

## Tests and verification

Run backend checks:

```bash
cd backend
pytest
python -m compileall app
python scripts/verify_phase2.py
```

Run frontend build:

```bash
cd frontend
npm run build
```
