# KORA Studio v0 (Mac Demo Scaffold)

KORA Studio v0 is a minimal local Execution Viewer demo for macOS development.
It includes a small FastAPI backend and a single-screen React UI.

## What This Demo Shows

- A simple execution-viewer style metro map with stage replay animation
- Real-time station replay via Server-Sent Events (SSE) from `/api/sse_run`
- A metrics panel fed by backend demo telemetry (`LLM calls`, `tokens`, `estimated cost`, `stage counts`)
- A local-only scaffold to iterate before wiring real runtime streaming

## Current API Wiring

- `POST /api/run`
  - body: `{"prompt": "...", "mode": "kora|direct", "adapter": "openai|mock"}`
  - currently frontend uses `mode="kora"` and `adapter="mock"` by default
  - executes a minimal TaskGraph via `run_graph()` and stores events in memory
- `GET /api/sse_run?run_id=<id>`
  - streams run events in sequence for metro-map animation

## Run Backend

From repo root:

```bash
cd studio/backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
uvicorn app.main:app --reload --port 8000
```

If importing `kora` fails, run from repo root context or set:
`PYTHONPATH=../..`

## Run Frontend

From repo root:

```bash
cd studio/frontend
npm install
npm run dev
```

Frontend: [http://localhost:5173](http://localhost:5173)
Backend: [http://localhost:8000](http://localhost:8000)

## Next Milestones

- Replace in-memory demo SSE with true live event streaming directly from active `run_graph()` execution
- Live runtime trigger from UI input
- Multi-run timeline and report comparison views
