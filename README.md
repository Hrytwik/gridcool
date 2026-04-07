# GridCool (Hackathon Build)

Monorepo:
- `frontend/` — Vite + React + Tailwind mission-control dashboard
- `backend/` — FastAPI + WebSockets + demo-mode simulation layer + MongoDB (Motor)

## Run locally

Copy envs:

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

## Demo endpoints (DEMO_MODE)

- `POST /demo/force-stress` — force stress score for N minutes
- `POST /demo/trigger-dispatch` — start dispatch immediately
- `POST /demo/enroll-building` — enroll a building (appears on map)

## Buildings API

- `GET /buildings` — list buildings (demo fleet + newly enrolled)
- `GET /buildings/{building_id}` — building details

## Thermal fingerprinting (Phase 1)

GridCool infers per-building thermal characteristics passively from MirAIe AC telemetry (no surveys):
- RC model parameters: `rc_r`, `rc_c`
- Flexibility window (minutes) the AC can be off while staying within comfort band
- Construction type classifier (India typologies): `top_floor`, `ground_floor`, `corner_unit`, `mid_floor`
- Calibration flow: new buildings show **Calibrating…** then become **Fingerprinted ✓** (demo: ~8s)

Thermal APIs:
- `GET /thermal/buildings/{building_id}` — full thermal fingerprint
- `GET /thermal/fleet` — all fingerprints + fleet summary
- `POST /thermal/recalibrate/{building_id}` — trigger recalibration (demo: instant)

