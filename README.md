# GridCool (Hackathon Build)

Monorepo:
- `frontend/` — Vite + React + Tailwind mission-control dashboard
- `backend/` — FastAPI + WebSockets + demo-mode simulation layer

## Run locally

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

