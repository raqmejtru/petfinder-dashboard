# Petfinder Donor Intelligence Dashboard

**Goal**: surface metrics (adoption rate, time-to-adoption, seniors share, impact index) for shelters/rescues using Petfinder data.

## Quick start (local)
1) `cp .env.example .env` and fill values.
2) `docker compose up -d db` (or run SQLite by leaving DATABASE_URL to default).
3) Create venv and install: `pip install -e .[dev]`.
4) API: `uvicorn backend.app.main:app --reload` → http://localhost:8000/health
5) Frontend: `python frontend/app.py` → http://localhost:8050
6) ETL dry run: `python -m etl.run`

## Next
- Implement Petfinder client + ingestion tables
- Add Alembic migration for initial schema
- Render/Railway deployment
