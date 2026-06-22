# DFMS — Dairy Farm Management System

Phase 1 scaffold: Farm Server on LAN with auth and `RecordMilking` command round-trip.

## Structure

```text
backend/           FastAPI + PostgreSQL + event store
frontend-kiosk/    React worker UI (stub)
frontend-owner/    React owner dashboard (stub)
docs/              Specification documents
infra/             Docker Compose
```

## Quick start (Docker)

```powershell
cd infra
docker compose up --build
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs  
Health: http://localhost:8000/health

### Seed credentials

| Role | Login |
|------|-------|
| Owner | `owner@dfms.local` / `owner123` |
| Worker | code `002` / PIN `1234` |
| Kiosk device | `KIOSK-01` |
| Sample cow | tag `101` |

## Test the Phase 1 gate

```powershell
# 1. Health check
curl http://localhost:8000/health

# 2. Worker login
curl -X POST http://localhost:8000/auth/worker/login `
  -H "Content-Type: application/json" `
  -d '{"worker_code":"002","pin":"1234","device_id":"KIOSK-01"}'

# 3. Record milking (replace TOKEN)
curl -X POST http://localhost:8000/commands/record-milking `
  -H "Authorization: Bearer TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"animal_tag":"101","session":"MORNING","volume_litres":12.5,"device_id":"KIOSK-01"}'
```

Expected: `200` with `MilkingRecorded` event in response.

## Local development (without Docker)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Start PostgreSQL locally, then:
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
```

## Phase 1 exit criteria

- [x] Docker Compose stack (PostgreSQL, Redis, MinIO, API)
- [x] Owner + Worker authentication
- [x] `RegisterAnimal` command
- [x] `RecordMilking` command → `domain_events` + `milking_records`
- [x] Milking schedule validation (2 vs 3 session)
- [ ] Kiosk UI (Phase 3)

## Specs

See `docs/` for glossary, business rules, domain events, and queries.
