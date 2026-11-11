# VigilSiddhi — A Vision AI Platform

Powered by Azkashine Software & Services Pvt. Ltd.

VigilSiddhi turns IP cameras into an always-on safety and hygiene supervisor. It runs on a PC at the
site (video never leaves the premises), detects violations with AI, alerts supervisors with photo
evidence, and reports trends. One codebase, one industry active at a time:

| Industry | What it checks |
|---|---|
| **Restaurant** | Hair cap, mask, gloves, apron · hand wash too short / skipped (zones) · tables not cleared |
| **Cement plant** | Safety helmet, hi-vis vest · restricted / danger area entry · conveyor spillage · cement bag counting |

**Install on a Windows PC:** see [INSTALL.md](INSTALL.md) — `install.bat` once, then `start.bat`.

## Project layout

| Folder | What |
|---|---|
| `backend/` | FastAPI server, detection engine (YOLO11-pose, SigLIP 2, YOLO-World), SQLite database, Alembic migrations |
| `backend/app/industries/` | One pack per industry: checks, zone types, rules, labels |
| `backend/scripts/` | `download_models.py`, `setup_demo.py` (demo cameras), `analyze_videos.py` (accuracy check) |
| `backend/data/demo*/` | Demo videos (AI-generated), their guides, prompts and expected results |
| `frontend/` | React + TypeScript web app (Vite, Tailwind) |

## Development

```
cd backend   ; .venv\Scripts\python.exe main.py        # API on http://127.0.0.1:8000
cd frontend  ; npm run dev                             # web app on http://127.0.0.1:5173
cd backend   ; .venv\Scripts\python.exe -m pytest      # backend tests
cd frontend  ; npx playwright test                     # end-to-end tests (own backend on :8001)
```

Not in the repository (see `.gitignore`): installed libraries, AI models (downloaded by
`backend/scripts/download_models.py`), the database and event photos.

Note: Ultralytics YOLO is AGPL-3.0 licensed — a closed-source commercial product needs an Ultralytics
Enterprise License (or a switch to permissively licensed models).
