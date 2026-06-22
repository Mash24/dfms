# DFMS-Implementation-Phases.md
**Dairy Farm Management System — Compiled Build Phases**
Version: 1.0 | Status: DRAFT | Author: Mash | Date: 2026-06-21

---

## Purpose

This document is the **authoritative implementation roadmap** for DFMS. It compiles two independent phase plans (feature-vertical and client-layer) into a single sequence.

**Two rules govern this document:**

1. **Specification describes the complete system.** Phases describe what gets built when — not what gets designed. The data model is always full-domain; only UI and API surface grow incrementally.

2. **Compilation rule:** When two source plans disagree, take the **earlier or stricter gate**. Ambiguity is not resolved by averaging.

**Product name:** DFMS (Dairy Farm Management System).

---

## Phase Map (Overview)

| Phase | Name | Goal |
|-------|------|------|
| **0** | Domain Definition & Specification | Eliminate ambiguity — no code |
| **1** | Farm Server Foundation | Stack runs; auth works; one command round-trips |
| **2** | Animal Registry | Every animal exists digitally |
| **3** | Kiosk Worker Flows | Replace worker notebooks (milk, feed, health) |
| **4** | Owner Dashboard Core | Owner can run the farm from the dashboard |
| **5** | Breeding & Reproduction | Breeding notebook retired |
| **6** | Tasks, Notifications & Inventory | Operational discipline + stock tracking |
| **7** | Financial System | Farm economics visible |
| **8** | Analytics & Intelligence | Records become decisions |
| **9** | Cloud & Remote Access | Farm visible when owner is away |
| **10** | Field Hardening — First Real Cow | 30 days of real farm data |
| **11** | Mobile App | Field client; same API |
| **12** | Sensor Integration | Reduce manual entry |
| **13** | Commercial Readiness | Second farm onboards without code changes |
| **14** | Production Launch | DFMS is the system of record |

---

## Phase 0 — Domain Definition & System Specification

**Goal:** Eliminate ambiguity. Five developers can independently design database, APIs, Kiosk, and Dashboard and arrive at nearly identical systems.

**Gate (hard):** No Phase 1 code until `DFMS-Domain-Events.md` and `DFMS-Business-Rules.md` are complete. API Spec and Data Model may be drafted in parallel with Phase 1 once those two exist.

### Deliverables

| Document | Status | Notes |
|----------|--------|-------|
| `DFMS-Glossary.md` | ✅ v0.2 | Canonical terms, BR index |
| `DFMS-Roles-and-Clients.md` | ✅ v0.2 | Kiosk + Owner workflows |
| `DFMS-Domain-Events.md` | 🟡 v0.1 | 5 of ~20 commands specified |
| `DFMS-Business-Rules.md` | ✅ v0.2 | BR-001–BR-030 |
| `DFMS-Queries.md` | ✅ v0.1 | Formal dashboard query definitions |
| `DFMS-API-Spec.md` | ❌ | OpenAPI; all endpoints |
| `DFMS-Data-Model.md` | ❌ | PostgreSQL schema — **written last** |
| `DFMS-System-Architecture.md` | ❌ | Farm Server, LAN, cloud, Celery, MinIO |

### Questions that must be fully answered

- What is an Animal? *(Glossary ✅)*
- What events can happen to an Animal? *(Domain Events — partial)*
- What is a Lactation? *(Glossary ✅)*
- What is a Withdrawal Period? *(Glossary ✅)*
- What is a Notification? *(Glossary ✅)*
- What is a Task? *(Glossary ✅)*
- What does a Worker see? *(Roles ✅)*
- What does an Owner see? *(Roles ✅ — queries pending)*

### Exit Criteria

- [ ] All eight documents exist and are internally consistent
- [ ] Every command in Domain Events has: inputs, validations, events, side effects, failures
- [ ] Every BR-NNN rule has full text with examples
- [ ] Every Morning Intelligence section maps to a formal query in DFMS-Queries.md
- [ ] Two independent reviewers find no ambiguous terms

**Current position:** Phase 0 in progress. Next: complete Domain Events (remaining commands), then Business Rules.

---

## Phase 1 — Farm Server Foundation

**Goal:** Build the skeleton. Stack runs on Farm LAN. Auth works. One dairy command round-trips to the database.

**Source compilation:** ChatGPT Phase 1 (architecture) + Claude Phase 1 (Farm Server). Gate: Claude's round-trip test is stricter — use it.

### Repository Structure

```text
dfms/
├── backend/           # FastAPI, SQLAlchemy, Alembic, Celery workers
├── frontend-kiosk/    # React — Worker UI
├── frontend-owner/    # React — Owner Dashboard
├── docs/              # DFMS-*.md specifications
└── infra/             # Docker Compose, deployment scripts
```

### Infrastructure (Docker Compose on Farm Server)

| Service | Purpose |
|---------|---------|
| PostgreSQL | Primary data store |
| Redis | Celery broker |
| MinIO | S3-compatible photo storage (LAN) |
| Backend | FastAPI application |
| Celery worker | Async jobs (notifications, sync) |

### Backend

- FastAPI application skeleton
- SQLAlchemy models + Alembic migrations (from `DFMS-Data-Model.md`)
- Command handler pattern — one handler per command
- Domain event store table — append-only
- `device_id` tagging on all Kiosk commands
- Health check: `GET /health` — Kiosk pings to detect Farm Server availability

### Authentication

| Actor | Method | Notes |
|-------|--------|-------|
| Owner | Email + password → JWT | Full access |
| Worker | Worker ID + PIN → session token | Kiosk only; bcrypt PIN hash |
| Vet | No account | v1 — via Worker session |

### Seed Script

Creates: one Farm, one Owner account, one Worker (ID + PIN), one Kiosk device (`KIOSK-01`).

### Exit Criteria

- [ ] `docker compose up` starts full stack on Farm LAN
- [ ] Owner can log in; Worker can authenticate on Kiosk (PIN)
- [ ] `RecordMilking` command round-trips: Kiosk → API → event store → response with `event_id`
- [ ] No dairy UI beyond auth screens required

**Not in Phase 1:** Kiosk workflows, Owner dashboard, analytics, cloud.

---

## Phase 2 — Animal Registry

**Goal:** Every animal on the farm exists digitally. Foundation for all production records.

**Source compilation:** ChatGPT Phase 2. Must complete **before** Kiosk milking (animals must exist to milk).

### Commands

| Command | Client |
|---------|--------|
| `RegisterAnimal` | Owner Dashboard |
| `RecordAnimalSale` → `AnimalSold` | Owner Dashboard |
| `RecordAnimalDeath` → `AnimalDied` | Owner Dashboard |
| `MoveAnimalToGroup` → `AnimalGroupChanged` | Owner Dashboard |

### Owner Screens

- Animal List (filter: Active, group, type)
- Animal Profile (immutable facts + derived status badges)
- Animal Registration form
- Animal timeline (event history — basic)

### Domain Rules Enforced

- BR-015: `AnimalRegistered` is sole creation event
- BR-001: Sold/dead animals removed from active lists
- BR-006: Group membership is time-series

### Exit Criteria

- [ ] Entire launch herd registered with correct tags, groups, purchase data
- [ ] Group membership history queryable by date
- [ ] Sold/dead animals blocked from new operational commands

---

## Phase 3 — Kiosk Worker Flows

**Goal:** Replace worker notebooks. A Worker with basic literacy completes a full morning round without training.

**Source compilation:** ChatGPT Phases 3–5 (milk, feed, health) merged into one Kiosk phase. Claude Phase 2 (all five buttons + offline queue). **Offline queue included here** (not deferred to Phase 10 — earlier gate wins).

### Commands

| Command | Kiosk Action |
|---------|--------------|
| `RecordMilking` | Record Milk |
| `RecordFeedGroupAllocation` | Record Feed (group path) |
| `RecordFeedAnimalAllocation` | Record Feed (dairy meal / supplement path) |
| `RecordObservation` | Report Issue |
| `RecordTreatment` | Vet Visit |
| `RecordVaccination` | Vet Visit |
| `CompleteTask` | My Tasks |

### Kiosk Features

- Fullscreen shell, Worker ID + PIN, 15-min auto-logout (BR-013)
- Record Milk: session toggle, animal tiles, stepper, validation (BR-003, BR-009)
- Record Feed: feed type tiles, group/animal routing (BR-010), stepper
- Report Issue: issue type tiles, optional photo (BR-017)
- Vet Visit: animal summary, treatment form, withdrawal display (BR-005, BR-011)
- My Tasks: read-only list, mark done
- **Local command queue (IndexedDB)** — queue when Farm Server down; replay on reconnect (BR-014)
- Offline banner when Farm Server unreachable

### Exit Criteria

- [ ] Worker with no system knowledge completes full morning milking round in **under 5 minutes**
- [ ] Every entry appears correctly in event store
- [ ] Offline queue survives Farm Server restart; no commands lost
- [ ] Milk notebook can be retired for daily recording

---

## Phase 4 — Owner Dashboard Core

**Goal:** Owner can run daily farm operations from the dashboard without developer assistance.

**Source compilation:** Claude Phase 3. Operational Owner workflows not yet in Kiosk.

### Dashboard Views

| View | Purpose |
|------|---------|
| Morning Intelligence (basic) | Yesterday's milk, unreviewed observations, flagged records |
| Flagged Records Review | Approve or correct (→ `CorrectionRecorded`) |
| Unreviewed Observations | Acknowledge worker reports (BR-016) |
| Animal Management | Full registry from Phase 2 |
| Worker Management | Add/deactivate Worker, reset PIN (BR-018) |
| Milk Sale entry | With withdrawal period check (BR-005) |

### Commands Added

| Command | Notes |
|---------|-------|
| `RecordMilkSale` | Owner only; blocks withdrawal milk |
| `CorrectionRecorded` | Owner corrects flagged entries |

### Exit Criteria

- [ ] Owner reviews flagged records and observations daily
- [ ] Owner records milk sales with withdrawal enforcement
- [ ] All Kiosk commands produce consistent derived state on Dashboard
- [ ] No derived status stored as columns — all computed from events

---

## Phase 5 — Breeding & Reproduction

**Goal:** Manage herd growth digitally. Breeding notebook retired.

**Source compilation:** ChatGPT Phase 6.

### Commands

| Command | Events |
|---------|--------|
| `RecordObservation` (IN_HEAT) | Already in Phase 3; now drives breeding alerts |
| `RecordBreeding` | `BreedingRecorded` |
| `RecordPregnancyCheck` | `PregnancyConfirmed` or `PregnancyNotConfirmed` |
| `RecordCalving` | `CalvingRecorded` + `AnimalRegistered` per calf |
| `RecordDryOff` | `DryOffRecorded` |
| `RecordWeaning` | `WeaningRecorded` |

### Features

- ECD calculation (breeding date + 283 days)
- Open cow tracking
- Pregnancy status on Animal timeline
- Calving creates calf `AnimalRegistered` automatically (BR-015)

### Dashboard

- Due for AI
- Due to calve (ECD within 7 days)
- Pregnancy status summary
- Dry period tracking (BR-002)

### Exit Criteria

- [ ] Full breeding cycle recordable: heat → AI → pregnancy check → calving
- [ ] Calf auto-registered on calving
- [ ] Dry-off closes lactation cycle correctly

---

## Phase 6 — Tasks, Notifications & Inventory

**Goal:** Operational discipline and stock tracking. Workers operate from DFMS task list.

**Source compilation:** ChatGPT Phases 4 (feed inventory), 5 (drug inventory), 7 (tasks/notifications).

### Commands

| Command | Purpose |
|---------|---------|
| `CreateTask` | Owner creates manual task |
| `CompleteTask` | Worker marks done (Kiosk — already built) |
| `DismissNotification` | Owner resolves alert |
| `CreateFeedBatch` / `ReceiveFeed` | Feed inventory |
| `AddInventoryItem` / `ConsumeInventory` | Drug and consumable stock |

### Features

- System-generated tasks from domain events (calving → schedule first milking; AI → pregnancy check due)
- Notification engine: types, priorities, resolved state
- Feed Batch management with FIFO depletion
- Drug inventory linked to `RecordTreatment`
- Field entity linked to Feed Batch source
- Days of Feed Remaining calculation
- Low stock alerts (feed + drugs)

### Exit Criteria

- [ ] Worker morning starts with DFMS task list
- [ ] Treatment depletes drug inventory automatically
- [ ] Feed runway visible on Owner Dashboard
- [ ] No paper treatment or feed inventory books required

---

## Phase 7 — Financial System

**Goal:** Know farm profitability. Economics visible in one place.

**Source compilation:** ChatGPT Phase 8.

### Commands

| Command | Purpose |
|---------|---------|
| `RecordExpense` | Feed, health, labour, equipment |
| `RecordIncome` | Non-milk income |
| `RecordMilkSale` | Enhanced — full revenue tracking (BR-004) |
| `RecordAnimalSale` | Animal sale revenue + `AnimalSold` |

### Dashboard

- Revenue by period
- Expenses by category
- Feed costs
- Drug costs
- Monthly net margin

### Exit Criteria

- [ ] Owner can answer: "What did we spend this month?" and "What did we earn?"
- [ ] Milk revenue calculated from per-transaction prices only (no global price table)

---

## Phase 8 — Analytics & Intelligence Layer

**Goal:** DFMS actively influences decisions. Morning Intelligence fully operational.

**Source compilation:** ChatGPT Phase 9 + Claude Phase 4.

### Features

| Feature | Business Rule |
|---------|---------------|
| 7-day rolling average yield per animal | BR-003 |
| Cost per litre (monthly) | Derived |
| Feed cost per litre (monthly) | Derived |
| Open cow alert (80+ days in milk, not bred) | BR-008 |
| Dry period alert (outside 45–75 days) | BR-002 |
| Withdrawal enforcement on Milk Sale | BR-005 |
| Production decline detection | Yield trend vs baseline |
| ROI per cow | Revenue − allocated costs |
| Feed efficiency by group | Feed cost ÷ milk per group |
| Morning Intelligence View — complete | All sections from Roles doc §4.1 |

### Exit Criteria

- [ ] Owner opens dashboard each morning; system surfaces what needs attention without manual querying
- [ ] "Which cow needs attention?" answered automatically
- [ ] "How many days of silage remain?" answered automatically
- [ ] DFMS influences at least one real decision per week on the farm

---

## Phase 9 — Cloud & Remote Access

**Goal:** Farm doesn't disappear when owner leaves the property.

**Source compilation:** Claude Phase 5.

### Features

- Async cloud sync — Farm Server → cloud PostgreSQL replica (Celery export or logical replication)
- Remote Owner Dashboard via cloud read layer
- Nightly off-site PostgreSQL backup
- Photo sync to cloud S3
- Farm Server health monitoring — alert if offline > 30 minutes

### Exit Criteria

- [ ] Owner checks Morning Intelligence from phone away from farm
- [ ] Farm Kiosk operations unaffected when cloud is unreachable (BR-007)
- [ ] Nightly backup verified restorable

---

## Phase 10 — Field Hardening: First Real Cow

**Goal:** Software meets a real farm. Thirty consecutive days of clean operational data.

**Source compilation:** Claude Phase 6 + ChatGPT Phase 13 (early milestones). **Mandatory gate before Phase 11 or 13.**

This is not a development phase in the traditional sense. It is a **validation checkpoint** with the first live animal.

### Milestones

1. First animal arrives (`RegisterAnimal` — in-calf heifer)
2. First milking recorded on Kiosk by real Worker (not developer)
3. First feed allocation recorded
4. First health observation or treatment recorded
5. First calving recorded (when it happens)
6. First breeding cycle completed
7. **30 consecutive days** — no missing milking sessions, no abandoned data entry mid-flow

### Activities

- End-to-end test of every Kiosk workflow with actual Worker
- Identify and fix every friction point in real use
- Measure: seconds per milking entry, error rate, Worker abandonment rate
- Owner dashboard accuracy audit — does it reflect physical reality?

### Exit Criteria

- [ ] 30 consecutive days of complete milking data
- [ ] Worker uses Kiosk without developer present
- [ ] Owner trusts dashboard over notebook
- [ ] Zero critical bugs open

**Gate:** Phase 11 (Mobile) and Phase 13 (Commercial) do not start until Phase 10 exit criteria are met.

---

## Phase 11 — Mobile App

**Goal:** Second client for field scenarios. Same API, no Kiosk-specific routes.

**Source compilation:** Claude Phase 7. Separated from Commercial (Phase 13) — different problem, different time.

### Deliverables

- React Native (or PWA) Worker app — same five actions as Kiosk
- Owner mobile app — Morning Intelligence, alerts, animal lookup
- Offline sync: mobile → Farm Server when in LAN range
- Swahili UI toggle (if not done earlier)

### Exit Criteria

- [ ] Worker records observation from paddock with no internet; syncs on return to LAN
- [ ] Owner checks alerts from phone
- [ ] No duplicate API endpoints vs Kiosk

---

## Phase 12 — Sensor Integration

**Goal:** Reduce manual entry. At least one physical device feeds DFMS automatically.

**Source compilation:** ChatGPT Phase 11.

### Infrastructure

- MQTT broker (Mosquitto)
- Device registry
- Ingestion pipeline → domain events

### Device Types (priority order)

1. Milk meters (auto `MilkingRecorded` with manual override)
2. Water consumption sensors
3. Weight scales
4. Environmental sensors (temperature, humidity)

### Exit Criteria

- [ ] At least one sensor produces valid domain events in production
- [ ] Manual entry remains available as fallback
- [ ] Sensor data and manual entry reconcilable

---

## Phase 13 — Commercial Readiness

**Goal:** A second farm onboards without code changes.

**Source compilation:** ChatGPT Phase 12 + Claude Phase 8.

### Features

- Multi-tenant isolation hardened and audited
- Self-service onboarding: Owner registers → creates Farm → adds Workers → activates Kiosk
- Subscription billing (SaaS) or license model (self-hosted)
- Data export (CSV/JSON) — farm owner can leave with their data
- Vet one-time token entry link (no app install)
- Privacy and data handling documentation
- User guides, admin guides, deployment guides

### Exit Criteria

- [ ] Dairy farmer in Kenya who has never spoken to you sets up DFMS, registers animals, takes first milking record in **under one hour**
- [ ] Second farm's data fully isolated from first
- [ ] No code changes required for second farm onboarding

---

## Phase 14 — Production Launch

**Goal:** DFMS is the system of record. No notebook contains information DFMS does not.

**Source compilation:** ChatGPT Phase 13 (completion).

### Success Metric

Every operational record — milk, feed, health, breeding, finance, inventory — lives in DFMS. Paper is backup only, never primary.

### Annual Milestone

First full year of farm data in DFMS enables: year-on-year comparison, breeding performance analysis, true cost-per-litre annual figure, ROI ranking across lactations.

---

## Compilation Notes

How this document resolved conflicts between source plans:

| Topic | ChatGPT | Claude | **Compiled decision** |
|-------|---------|--------|----------------------|
| Code before spec | Implied later | Hard gate Phase 0 | **No code before Domain Events + Business Rules** |
| Offline queue | Phase 10 | Phase 2 Kiosk | **Phase 3** (with Kiosk) |
| Animal registry vs milking | Animals first (Ph 2) | Milk in Kiosk (Ph 2) | **Phase 2 animals, Phase 3 milk** |
| Intelligence layer | Phase 9 | Phase 4 | **Phase 8** (after finance data exists) |
| Real cow validation | Phase 13 end | Phase 6 (30 days) | **Phase 10 — mandatory gate** |
| Mobile vs commercial | Combined late | Separate phases | **Phase 11 mobile, Phase 13 commercial** |
| Manager role | Not specified | Excluded v1 | **Excluded** |
| Product name | DFMS | FarmCore | **DFMS** |

---

## Current Status

```
Phase 0  ████████████░░░░░░░░  ~55%  (Glossary, Roles, Business Rules, Queries, partial Domain Events)
Phase 1  ░░░░░░░░░░░░░░░░░░░░   0%
Phase 2+ ░░░░░░░░░░░░░░░░░░░░   0%
```

**Immediate next actions (Phase 0):**
1. Complete `DFMS-Domain-Events.md` — remaining commands
2. Write `DFMS-System-Architecture.md`
3. Write `DFMS-API-Spec.md` and `DFMS-Data-Model.md` (can overlap with Phase 1 start)

---

*End of DFMS-Implementation-Phases.md v1.0*
