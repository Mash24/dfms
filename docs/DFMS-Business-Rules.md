# DFMS-Business-Rules.md
**Dairy Farm Management System — Business Rules**
Version: 0.2 | Status: DRAFT | Author: Mash | Date: 2026-06-21

---

## Purpose

This document is the authoritative registry of all Business Rules (BR) in DFMS. Every rule has a unique `BR-NNN` identifier. Rules are referenced by Domain Events, API validations, UI behaviour, and dashboard queries.

**Dependencies:** DFMS-Glossary.md (terms), DFMS-Domain-Events.md (commands), DFMS-Roles-and-Clients.md (workflows).

**Rule format:** Each entry includes Statement, Rationale, Enforcement, Examples, and Related Commands/Events.

**Index:** BR-001–BR-019 are canonical (see DFMS-Glossary.md Appendix D). BR-020+ are supporting rules introduced here; they will be merged into the Glossary index at v0.3.

---

## 1. Animal Lifecycle Rules

### BR-001 — Inactive Animals Cannot Receive Operational Events

**Statement:** An Animal with an `AnimalSold` or `AnimalDied` event must not accept any new operational commands. The Animal is immediately removed from all Worker selection lists (milking, feeding, observations, vet visit).

**Rationale:** Sold and dead animals are historical records. Allowing new milk or treatment entries creates data integrity failures and corrupts production and financial reports.

**Enforcement:**
- API: reject operational commands with `ANIMAL_INACTIVE` (HTTP 422)
- Operational commands: `RecordMilking`, `RecordFeedGroupAllocation`, `RecordFeedAnimalAllocation`, `RecordObservation`, `RecordTreatment`, `RecordVaccination`, `RecordBreeding`, `MoveAnimalToGroup`
- Kiosk: inactive animals excluded from all tile grids
- Owner Dashboard: inactive animals visible in history/search only; greyed badge `SOLD` or `DEAD`

**Allowed after sale/death:** `CorrectionRecorded` on historical events only; no new domain events for the animal.

**Examples:**
- Cow 101 sold on 1 June → Worker cannot record milk for Cow 101 on 2 June
- Owner may still view Cow 101 timeline and linked financial records

**Related events:** `AnimalSold`, `AnimalDied`

---

### BR-015 — AnimalRegistered Is the Sole Creation Event

**Statement:** Every Animal enters DFMS via exactly one `AnimalRegistered` event. There is no alternate creation path. `AnimalPurchased` records acquisition details but is not a creation event. Calves born on farm are created when `RecordCalving` emits `AnimalRegistered` per live calf.

**Rationale:** Two creation paths cause schema divergence, duplicate tags, and broken parentage links.

**Enforcement:**
- `RegisterAnimal` (Owner) → emits `AnimalRegistered` + `AnimalPurchased` + `AnimalGroupChanged`
- `RecordCalving` (Owner, Phase 5) → emits `CalvingRecorded` + one `AnimalRegistered` per calf
- Database: no `INSERT` into animals table without corresponding `AnimalRegistered` event
- API: no endpoint that creates an animal without going through command handlers

**Examples:**
- Purchased heifer: Owner runs `RegisterAnimal` → `AnimalRegistered` + `AnimalPurchased`
- Calf born on farm: Owner runs `RecordCalving` with 1 live female calf → `AnimalRegistered` for calf (no `AnimalPurchased`)

**Related commands:** `RegisterAnimal`, `RecordCalving`

---

### BR-006 — Animal Group Membership Is Time-Series

**Statement:** An Animal's group assignment is recorded as `AnimalGroupChanged` events with `start_date` and `end_date`. Current group is the membership with `end_date = null`. Historical memberships are never deleted or overwritten.

**Rationale:** Feed cost allocation, production reporting, and audit require knowing which group an animal belonged to on any past date. A static `group_id` on the Animal record cannot answer "which group was Cow 27 in on 15 March?"

**Enforcement:**
- `MoveAnimalToGroup` closes previous membership (`end_date = today`) and opens new membership
- `RegisterAnimal` opens initial membership
- Queries for historical group: filter memberships where `start_date ≤ target_date ≤ end_date OR (end_date IS NULL AND start_date ≤ target_date)`
- Database: no `group_id` column on animals table

**Examples:**
- Cow 27 moved from `HEIFERS` to `LACTATING_COWS` on 1 May → two membership rows; query on 15 April returns `HEIFERS`; query on 15 May returns `LACTATING_COWS`

**Related events:** `AnimalGroupChanged`

---

## 2. Lactation & Milk Production Rules

### BR-003 — Unusual Milk Volume Is Flagged, Not Blocked

**Statement:** When `RecordMilking` records a volume greater than 2× the Animal's 7-day rolling average yield, the entry is saved and a `FlaggedRecordCreated` event is emitted. The Worker sees a one-tap confirmation prompt; the entry is not blocked.

**Rationale:** Workers must never be punished for data entry. Unusual volumes may be real (recovery after illness, new calver peaking). The Owner reviews flags — the system catches errors without stopping farm work.

**Enforcement:**
- Calculate 7-day rolling average per Glossary (exclude days with no record; mark unreliable if < 3 days of data)
- If `volume_litres > 2 × average` and average is reliable → `flagged: true` on `MilkingRecorded` + `FlaggedRecordCreated`
- If average is unreliable (fewer than 3 days) → do not flag; no penalty for new calvers or recently registered animals
- Kiosk: "Unusual volume — confirm?" → one tap saves
- Owner Dashboard: appears in Flagged Records Review

**Examples:**
- Cow 101 average 12L, Worker enters 26L → saved, flagged
- Cow 102 new calver, only 2 days of data → entered 18L, not flagged (unreliable average)

**Related commands:** `RecordMilking`

---

### BR-009 — Implausible Milk Volume Is Hard-Blocked

**Statement:** A single milking session volume greater than 60 litres must be rejected. The command fails; no `MilkingRecorded` event is emitted.

**Rationale:** 60L exceeds biological maximum for any dairy breed in a single session. Values above this are data entry errors (decimal misplaced, wrong cow selected) and must not enter the system even as flagged records.

**Enforcement:**
- API validation V-RM-004: `volume_litres > 60` → `VOLUME_IMPLAUSIBLE` (HTTP 422)
- Kiosk: hard block with message "Volume too high — check entry"
- No override on Kiosk; Owner may enter correction via Dashboard if genuinely required (extremely rare — requires `CorrectionRecorded` with note)

**Examples:**
- Worker enters 120L (meant 12.0L) → blocked
- Worker enters 45L for high-producing cow → allowed (may also trigger BR-003 soft flag)

**Related commands:** `RecordMilking`

---

### BR-020 — Lactation Begins at First Milking, Not Calving

**Statement:** A Lactation Cycle opens on the first `MilkingRecorded` event after a `CalvingRecorded` event. It does not open at calving. Milk recorded during the colostrum period uses `ColostralMilkRecorded` (Phase 5) and is excluded from lactation totals and saleable milk.

**Rationale:** Colostrum is not commercial milk. Farmers often delay commercial milking 3–5 days post-calving. Tying lactation to calving corrupts days-in-milk and production averages.

**Enforcement:**
- First `MilkingRecorded` after `CalvingRecorded` assigns `lactation_cycle_id` and opens cycle
- `DryOffRecorded` or next `CalvingRecorded` closes open cycle
- Colostrum events excluded from Daily Milk Yield and saleable pool

**Related events:** `CalvingRecorded`, `MilkingRecorded`, `DryOffRecorded`, `ColostralMilkRecorded`

---

### BR-021 — Milking Outside Window Is Flagged, Not Blocked

**Statement:** A `MilkingRecorded` event submitted outside the configured Milking Window for its session is accepted and saved with `outside_window: true`. A `FlaggedRecordCreated` event is emitted for Owner review. The entry is not blocked — a Worker running late must not lose the record.

**Rationale:** Farm work does not always fit neat time boxes. Blocking late entries forces paper workarounds. Flagging preserves accountability without stopping operations.

**Enforcement:**
- Compare `recorded_at` (farm local time) against Farm's Milking Window for the claimed `session`
- If outside window → `outside_window: true` on `MilkingRecorded` + `FlaggedRecordCreated` reason `OUTSIDE_MILKING_WINDOW`
- Kiosk: if current time outside all windows, prompt "Which session are you recording?" and flag if outside that session's window
- Owner Dashboard: appears in Flagged Records Review

**Examples:**
- Worker records MORNING session at 10:30 (window ends 09:00) → saved, flagged
- Worker records MORNING session at 07:00 → saved, not flagged

**Related commands:** `RecordMilking`

---

### BR-022 — Missed Scheduled Milking Generates Alert

**Statement:** At the close of each Milking Window, the system checks every Active Lactating Animal scheduled for that session on that calendar date. Any Animal with no `MilkingRecorded` event for that (`animal_id`, `session`, `milking_date`) generates a `NotificationCreated` with priority `HIGH`. If still unresolved 30 minutes after window close, priority escalates to `CRITICAL`.

**Rationale:** The system must compare what **should** have happened to what **did** happen. Missed milkings affect udder health and production tracking.

**Enforcement:**
- Celery job `check_missed_milkings` runs at each window close time (per Farm config)
- Query: Animals where `MilkingSchedule.sessions` contains `session` AND no matching `MilkingRecorded`
- Emit `NotificationCreated` type `MISSED_MILKING`, priority `HIGH`
- Follow-up job at window_close + 30 min: if still no record, update notification to `CRITICAL`
- Notification resolved automatically when late `MilkingRecorded` is submitted, or manually by Owner

**Examples:**
- Cow 101 on 3-session schedule, MIDDAY window closes 14:00, no entry → HIGH alert at 14:00, CRITICAL at 14:30
- Cow 102 on 2-session schedule → no MIDDAY check ever runs for this cow

**Related events:** `MilkingRecorded`, `NotificationCreated`

---

### BR-023 — Milking Schedule Recalculated Nightly

**Statement:** Each Active Lactating Animal's Milking Schedule for the **following calendar day** is recalculated nightly based on 7-day rolling average Daily Milk Yield. If average > `three_session_threshold_litres` (default 15L), schedule is `MORNING`, `MIDDAY`, `EVENING`. Otherwise `MORNING`, `EVENING`. Threshold is configurable per Farm. Schedule changes take effect the next calendar day automatically — no Owner confirmation.

**Rationale:** High-producing cows require three milkings for udder health and yield. The threshold must be automatic so Workers never configure sessions manually.

**Enforcement:**
- Celery job `recalculate_milking_schedules` runs nightly at 00:05 farm local time
- Writes `milking_schedules` projection: (`animal_id`, `schedule_date`, `sessions[]`, `basis_average`, `threshold_used`)
- Kiosk reads projection for today's date when filtering animals per session
- When cow crosses threshold upward on night of 20 June → 3-session schedule applies from 21 June
- When cow crosses threshold downward → 2-session schedule applies from next day; MIDDAY entries blocked from that day

**Examples:**
- Cow 118 averages 16.2L over 7 days on 20 June night job → 21 June schedule: MORNING, MIDDAY, EVENING
- Cow 104 averages 11.8L → 21 June schedule: MORNING, EVENING only

**Related:** Milking Schedule (Glossary), BR-027

---

### BR-027 — Session Not On Schedule Is Hard-Blocked

**Statement:** `RecordMilking` for a session not included in the Animal's Milking Schedule for that calendar date must be rejected. No event is emitted.

**Rationale:** Prevents MIDDAY entries for 2-session cows — the primary data integrity risk in a dynamic schedule model.

**Enforcement:**
- API validation V-RM-008: `session` not in `MilkingSchedule.sessions` for (`animal_id`, `milking_date`) → `SESSION_NOT_SCHEDULED` (HTTP 422)
- Kiosk: Animal not shown in tile grid for sessions not on its schedule — Worker cannot select it
- API remains the enforcement backstop for offline queue replay

**Examples:**
- Cow 104 on 2-session schedule → `RecordMilking` with `session: MIDDAY` rejected
- Cow 118 on 3-session schedule → MIDDAY allowed

**Related commands:** `RecordMilking`

---

### BR-029 — One Milking Record Per Animal Per Session Per Day

**Statement:** At most one `MilkingRecorded` event exists per (`animal_id`, `session`, `milking_date`). Re-submission for the same combination updates the record via correction flow if volume differs, or returns the existing record if identical. Applies to all sessions including `MIDDAY`.

**Rationale:** Prevents duplicate entries from double-tap or sync replay. Workers may correct a session entry same-day.

**Enforcement:**
- Unique constraint on projection table: (`animal_id`, `session`, `milking_date`)
- Kiosk shows green tick on already-recorded cows; tapping allows correction
- Offline queue deduplication by client-generated idempotency key

**Related commands:** `RecordMilking`, `CorrectionRecorded`

---

## 3. Withdrawal & Health Rules

### BR-005 — Withdrawal Blocks Sale, Not Recording

**Statement:** During an active Withdrawal Period, milk from the treated Animal:
1. **May** be recorded via `RecordMilking` — milking is not blocked on Kiosk
2. **Must** be marked `saleable: false` on the `MilkingRecorded` event
3. **Must** be excluded from the farm saleable milk pool
4. **Must** be blocked from `RecordMilkSale` allocation for that Animal until withdrawal end date

Meat: the Animal must not be recorded as sold for slaughter during active withdrawal (blocked on `RecordAnimalSale`).

**Rationale:** Cows continue to produce milk during treatment. The milk is discarded or fed to calves — it is not withheld in the udder. Blocking recording would force paper workarounds and break production tracking.

**Enforcement:**
- `TreatmentRecorded` → `WithdrawalPeriodStarted` with `end_date = treatment_date + withdrawal_days`
- `MilkingRecorded.saleable` computed at write time from active withdrawal projection
- `RecordMilkSale`: validate no litres allocated from non-saleable milk; per-animal attribution if batch sale
- Kiosk: optional small icon on cow tile during withdrawal; no block on entry
- Vet Visit save screen: display withdrawal end date prominently

**Examples:**
- Cow 103 treated 21 June, 7-day withdrawal → milk recorded 22–27 June with `saleable: false`; Owner cannot include Cow 103 milk in sale until 28 June

**Related events:** `TreatmentRecorded`, `WithdrawalPeriodStarted`, `MilkingRecorded`

---

### BR-011 — Treatment Requires Mandatory Fields

**Statement:** `RecordTreatment` must capture: Animal (tag), Drug, Dose (> 0), Route (`INJECTION`, `ORAL`, `TOPICAL`), and Withdrawal Days (≥ 0). Diagnosis and Vet Name are optional.

**Rationale:** Incomplete treatment records invalidate withdrawal compliance and drug audit trails. Vets may omit diagnosis; they cannot omit drug and dose.

**Enforcement:**
- API validations V-RT-002 through V-RT-005
- Kiosk Vet Visit form: cannot save until all mandatory fields complete
- `withdrawal_days = 0` allowed for drugs with no milk withhold (e.g. some vitamins) — still explicit

**Related commands:** `RecordTreatment`

---

### BR-016 — Observations Create Notifications, Not Flagged Records

**Statement:** `ObservationRecorded` always emits `NotificationCreated`. It never emits `FlaggedRecordCreated`. Health observations appear in Owner Dashboard "Unreviewed Observations", not in "Flagged Records Review".

**Rationale:** Observations are intentional worker reports, not statistical anomalies. Conflating them with flagged milk volumes confuses Owner review workflows.

**Enforcement:**
- `RecordObservation` handler: always create Notification
- Priority: `INJURY`, `SWOLLEN_UDDER` → HIGH; `IN_HEAT` → LOW; others → MEDIUM
- Owner actions: [Mark Reviewed] or [Escalate to Treatment] — escalation issues separate `RecordTreatment` command

**Related commands:** `RecordObservation`

---

## 4. Feed & Inventory Rules

### BR-010 — Feed Allocations Stored Separately by Type

**Statement:** `RecordFeedGroupAllocation` and `RecordFeedAnimalAllocation` are distinct commands, stored in separate tables/projections, and must not be merged.

**Rationale:** Group feeds (silage, hay, water) and individual supplements (dairy meal) have different cost allocation logic and different UI flows. Merging them breaks feed-cost-per-litre calculations.

**Enforcement:**
- Kiosk routes by feed type: `SILAGE`, `HAY`, `WATER` → group command; `DAIRY_MEAL`, `MINERAL_SUPPLEMENT` → animal command
- API: `WRONG_COMMAND` if feed type mismatches command
- Database: separate tables `feed_group_allocations` and `feed_animal_allocations`

**Related commands:** `RecordFeedGroupAllocation`, `RecordFeedAnimalAllocation`

---

### BR-030 — Feed Batch FIFO Depletion

**Statement:** When `RecordFeedGroupAllocation` or `RecordFeedAnimalAllocation` does not specify `feed_batch_id`, the system depletes from the oldest Feed Batch of that Feed Type with remaining quantity (FIFO by `date_received`).

**Rationale:** Ensures accurate batch costing and prevents silent negative inventory on old batches.

**Enforcement:**
- Command handler selects batch automatically
- `INSUFFICIENT_STOCK` if total stock across batches < requested quantity
- `FeedBatchDepleted` event when batch reaches zero

**Related commands:** `RecordFeedGroupAllocation`, `RecordFeedAnimalAllocation`

---

## 5. Financial Rules

### BR-004 — No Global Milk Price

**Statement:** DFMS must not store a global or default milk price per litre. All milk revenue is recorded per `MilkSale` transaction with explicit `price_per_litre` and `litres`. Historical revenue reports use transaction prices, not a retroactively applied rate.

**Rationale:** Kenyan dairy prices vary by month and buyer. A global price corrupts historical profit reports when prices change.

**Enforcement:**
- No `milk_price` configuration table
- `RecordMilkSale` requires `price_per_litre` per transaction
- Reports: `revenue = SUM(litres × price_per_litre)` per transaction

**Examples:**
- January sales at 48 KES/L, February at 52 KES/L → February report uses 52, not current price applied to January

**Related commands:** `RecordMilkSale`

---

## 6. Reproduction Rules (Phase 5+)

### BR-002 — Dry Period Length Alert

**Statement:** The target dry period is 60 days before calving. If the actual dry period (from `DryOffRecorded` to next `CalvingRecorded`) is shorter than 45 days or longer than 75 days, the system creates a `NotificationCreated` alert for the Owner.

**Rationale:** Short dry periods risk mastitis and poor colostrum; excessively long dry periods reduce lifetime productivity.

**Enforcement:**
- Calculated on `CalvingRecorded` when previous `DryOffRecorded` exists
- `dry_days = calving_date - dry_off_date`
- If `dry_days < 45` or `dry_days > 75` → notification type `DRY_PERIOD_OUT_OF_RANGE`

**Related events:** `DryOffRecorded`, `CalvingRecorded`

---

### BR-008 — Open Cow Breeding Alert

**Statement:** A Cow that is Active, Lactating, not In-Calf, and has exceeded 80 days in milk since the most recent `CalvingRecorded` without a subsequent `PregnancyConfirmed` event triggers an Owner alert.

**Rationale:** Days in milk beyond 80 without confirmed pregnancy indicates missed breeding opportunity — direct economic loss.

**Enforcement:**
- Daily Celery job evaluates all Active Lactating Cows not In-Calf
- `days_in_milk = today - calving_date_of_current_lactation`
- If `days_in_milk > 80` and no open pregnancy → `NotificationCreated` type `OPEN_COW_OVERDUE`

**Note:** This is an alert threshold, not the definition of "Open Cow" (see Glossary).

**Related events:** `CalvingRecorded`, `PregnancyConfirmed`

---

### BR-024 — Expected Calving Date Calculation

**Statement:** Expected Calving Date (ECD) = date of the Breeding Event linked at `PregnancyConfirmed` + 283 days.

**Rationale:** Standard bovine gestation length. ECD drives calving approach alerts and dry-off planning.

**Enforcement:**
- Set on `PregnancyConfirmed` event payload
- Recalculated only if pregnancy confirmation is corrected (new `CorrectionRecorded` — rare)

**Related events:** `BreedingRecorded`, `PregnancyConfirmed`

---

## 7. Client & Infrastructure Rules

### BR-007 — Farm LAN Independence

**Statement:** All Worker commands must succeed when the Farm LAN is operational, regardless of internet connectivity. Internet is required only for cloud backup, remote Owner Dashboard access, and software updates.

**Rationale:** Rural farms have unreliable internet. Milking happens twice daily regardless of connectivity.

**Enforcement:**
- Kiosk → Farm Server only on LAN; no cloud API calls on critical path
- Cloud sync is async Celery job; failure does not affect Kiosk
- Health check `GET /health` on Farm Server, not cloud

**Related:** BR-014

---

### BR-012 — Kiosk Worker UI Restrictions

**Statement:** The Kiosk Worker session must not display: financial data, analytics, cost per litre, flagged record review, animal registration, breeding management, or system configuration.

**Rationale:** Workers need five actions only. Financial and analytical data is irrelevant to milking and creates confusion and misuse risk.

**Enforcement:**
- Kiosk React app: Worker role route guard
- API: Worker JWT scope excludes Owner endpoints
- No financial endpoints callable with Worker token

**Related:** DFMS-Roles-and-Clients.md §3

---

### BR-013 — Kiosk Session Timeout

**Statement:** A Kiosk session expires after 15 minutes of inactivity. On expiry, the Kiosk returns to the Worker ID login screen. The next Worker must authenticate independently.

**Rationale:** Shared farm computer — session hijacking between workers corrupts audit trail (`worker_id` attribution).

**Enforcement:**
- Client-side inactivity timer resets on any touch/click
- Server-side session token expiry aligned to 15 minutes
- All commands rejected if session expired → redirect to login

**Related:** Kiosk Session (Glossary)

---

### BR-014 — Kiosk Offline Command Queue

**Statement:** When the Farm Server is unreachable, the Kiosk stores pending commands in local storage (IndexedDB) and displays an offline banner. Commands are replayed in order when connectivity restores. No command is discarded.

**Rationale:** Farm Server restarts, power blips, and maintenance must not lose milking data at the busiest moment of the day.

**Enforcement:**
- Kiosk: queue on network failure or `/health` timeout
- Each queued command has client-generated `idempotency_key`
- Replay uses same keys — server deduplicates (BR-021 pattern)
- Banner: "Offline — entries will sync when connected"
- If queue exceeds 24 hours old without sync → Owner notification type `KIOSK_SYNC_STALE`

**Related:** BR-007

---

### BR-017 — Photo Storage Local First

**Statement:** Photos attached to observations, tasks, or treatments are uploaded to MinIO on the Farm Server. Cloud replication is asynchronous. Photo upload must not require internet.

**Rationale:** Observations often occur in areas with no internet. Photos are evidence for Owner and vet review.

**Enforcement:**
- Kiosk uploads to `http://farm-server.local/minio/...`
- Celery job syncs to cloud S3 when internet available
- `photo_attachment_id` references Farm Server object; cloud copy is secondary URI

**Related commands:** `RecordObservation`, `CompleteTask`

---

### BR-018 — PIN Reset Owner Only

**Statement:** Worker PIN reset is performed by the Farm Owner via Owner Dashboard only. Workers cannot self-reset. There is no "forgot PIN" flow on Kiosk in v1.

**Rationale:** Self-reset on a shared device is a security risk. Owner is always available or delegable.

**Enforcement:**
- Kiosk lockout after 3 failed attempts → "Contact supervisor" for 5 minutes
- Owner Dashboard: Worker Management → Reset PIN → generates new 4-digit PIN shown once to Owner

---

### BR-019 — Backdating Limits

**Statement:**

| Command type | Maximum backdate |
|--------------|------------------|
| `RecordMilking`, `RecordFeedGroupAllocation`, `RecordFeedAnimalAllocation` | 24 hours |
| `RecordTreatment`, `RecordVaccination` | 48 hours |
| `RecordObservation` | 24 hours |
| Owner commands (`RegisterAnimal`, `RecordCalving`, etc.) | 7 days with confirmation |

Entries with `recorded_at` in the future are always rejected.

**Rationale:** Workers record in near-real-time; limited backdating accommodates end-of-shift corrections. Vet paper entries may arrive next day (48h). Owner has broader correction window with explicit audit.

**Enforcement:**
- API validation on every command with `recorded_at`
- Failure code: `BACKDATE_LIMIT_EXCEEDED`
- Kiosk: date picker not exposed to Workers — backdating only via timestamp adjustment on server when within window

---

## 8. Data Integrity Rules

### BR-025 — Corrections Preserve Original Events

**Statement:** No Domain Event is ever deleted or mutated. Owner corrections emit `CorrectionRecorded` referencing the original `event_id` and containing corrected field values. The original event remains in the event store permanently.

**Rationale:** Audit trail and regulatory compliance. Farmers must explain historical records to vets, buyers, and authorities.

**Enforcement:**
- No `DELETE` or `UPDATE` on event store table
- `CorrectionRecorded` supersedes original for projections only
- Animal timeline shows both original and correction with clear labelling

**Related events:** `CorrectionRecorded`, `FlaggedRecordCreated`

---

### BR-026 — Multi-Tenant Data Isolation

**Statement:** Every entity and event is scoped to exactly one `farm_id`. No query, command, or API endpoint may return or modify data belonging to another Farm. `farm_id` is derived from authenticated user token, never from request body alone.

**Rationale:** Multi-tenancy from day one. Cross-farm data leakage is catastrophic for a commercial product.

**Enforcement:**
- Row-level security or mandatory `farm_id` filter on all queries
- JWT contains `farm_id` for Owner; Worker token contains `farm_id`
- Integration tests: cross-tenant access attempts must fail with 403

---

## 9. Rule Cross-Reference Matrix

| Rule | Commands | Events | UI Surface |
|------|----------|--------|------------|
| BR-001 | All operational | `AnimalSold`, `AnimalDied` | Kiosk tiles, API |
| BR-002 | — | `DryOffRecorded`, `CalvingRecorded` | Owner alerts |
| BR-003 | `RecordMilking` | `FlaggedRecordCreated` | Kiosk confirm, Owner review |
| BR-021 | `RecordMilking` | `FlaggedRecordCreated` | Kiosk, Owner review |
| BR-022 | — | `NotificationCreated` | Owner alerts |
| BR-023 | — | — | Nightly Celery job |
| BR-027 | `RecordMilking` | — | Kiosk filter, API block |
| BR-004 | `RecordMilkSale` | `MilkSaleRecorded` | Owner financial |
| BR-005 | `RecordMilking`, `RecordMilkSale` | `TreatmentRecorded`, `MilkingRecorded` | Kiosk, Owner sale |
| BR-006 | `MoveAnimalToGroup`, `RegisterAnimal` | `AnimalGroupChanged` | Projections |
| BR-007 | All Worker commands | — | Infrastructure |
| BR-008 | — | `CalvingRecorded` | Owner alerts |
| BR-009 | `RecordMilking` | — | Kiosk block |
| BR-010 | Feed commands | Feed allocation events | Kiosk routing |
| BR-011 | `RecordTreatment` | `TreatmentRecorded` | Vet Visit form |
| BR-012 | — | — | Kiosk route guard |
| BR-013 | All Kiosk | — | Kiosk session |
| BR-014 | All Kiosk | — | IndexedDB queue |
| BR-015 | `RegisterAnimal`, `RecordCalving` | `AnimalRegistered` | API only |
| BR-016 | `RecordObservation` | `NotificationCreated` | Owner observations |
| BR-017 | `RecordObservation` | — | MinIO |
| BR-018 | — | — | Owner Worker mgmt |
| BR-019 | All timed commands | — | API validation |

---

## 10. Complete Rule Index

| ID | Summary | Section |
|----|---------|---------|
| BR-001 | Inactive animals blocked | §1 |
| BR-002 | Dry period 45–75 day alert | §6 |
| BR-003 | Milk > 2× average flagged | §2 |
| BR-004 | No global milk price | §5 |
| BR-005 | Withdrawal blocks sale not recording | §3 |
| BR-006 | Group membership time-series | §1 |
| BR-007 | LAN independence | §7 |
| BR-008 | Open cow 80+ DIM alert | §6 |
| BR-009 | Milk > 60L hard block | §2 |
| BR-010 | Separate feed allocation storage | §4 |
| BR-011 | Treatment mandatory fields | §3 |
| BR-012 | Kiosk UI restrictions | §7 |
| BR-013 | 15 min session timeout | §7 |
| BR-014 | Offline command queue | §7 |
| BR-015 | AnimalRegistered sole creation | §1 |
| BR-016 | Observations → Notifications | §3 |
| BR-017 | Photos local first | §7 |
| BR-018 | PIN reset Owner only | §7 |
| BR-019 | Backdating limits | §7 |
| BR-020 | Lactation starts at first milking | §2 |
| BR-021 | Outside milking window flagged | §2 |
| BR-022 | Missed milking alerts | §2 |
| BR-023 | Milking schedule nightly recalc | §2 |
| BR-027 | Session not on schedule blocked | §2 |
| BR-029 | One milking per session per day | §2 |
| BR-030 | Feed batch FIFO | §4 |
| BR-024 | ECD = breeding + 283 days | §6 |
| BR-025 | Corrections preserve originals | §8 |
| BR-026 | Multi-tenant isolation | §8 |

---

*End of DFMS-Business-Rules.md v0.1*
