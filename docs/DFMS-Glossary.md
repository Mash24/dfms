# DFMS-Glossary.md
**Dairy Farm Management System — Canonical Glossary**
Version: 0.3 | Status: DRAFT | Author: Mash | Date: 2026-06-21

---

## Purpose

This document defines every domain term used across all DFMS specification documents. No later document (Domain Events, Business Rules, Queries, API Spec, Data Model) may introduce a term without it first being defined here. If a term is ambiguous in this document, it is ambiguous everywhere.

**Rule:** When a later specification document uses a term that is not in this glossary, it must be added here before that document is finalised.

---

## 0. Core Modelling Concepts

### Command
An instruction issued by a user (or system) requesting a change to farm state. Commands are imperative and may succeed or fail validation.

Examples: `RegisterAnimal`, `RecordMilking`, `RecordTreatment`.

A successful Command always emits one or more Domain Events. A failed Command emits no Domain Events.

### Domain Event
An immutable fact representing something that has happened. Domain Events are named in past tense. Events cannot be edited or deleted. Corrections are recorded as new events (e.g. `CorrectionRecorded`); the original event is preserved.

Examples: `AnimalRegistered`, `MilkingRecorded`, `TreatmentRecorded`.

Current operational state is always derived by projecting Domain Event history — never by mutating status fields.

### Projection
A read model derived from Domain Event history. Projections may be recalculated from events at any time. Examples: current Animal Group membership, active Withdrawal Period, saleable milk pool.

---

## 1. Farm & Organisation

### Farm
A single physical dairy operation managed as one unit. Has a unique `farm_id`. All entities belong to exactly one Farm. Multi-tenancy is supported from day one — a Farm is the top-level isolation boundary.

**Milking configuration (per Farm):**
- `three_session_threshold_litres` — default `15.0`; Animals above this 7-day average get 3-session schedule
- `milking_windows` — start/end times per session (`MORNING`, `MIDDAY`, `EVENING`); see Milking Window
- `timezone` — IANA timezone for all local-time calculations

### Tenant
Synonymous with Farm for multi-tenancy purposes. Each Farm is an independent tenant with isolated data.

### Farm Unit
A named subdivision of a Farm (e.g. "Main Shed", "Paddock A"). Used for location tracking. An Animal may be assigned to a Farm Unit at any point in time. A Farm Unit is not a Group.

### Field
A named area of agricultural land on a Farm used for fodder production or grazing. Attributes: name, area (hectares or acres), crop type, plant date, expected harvest date, actual harvest date (when recorded). A Field may be the source of one or more Feed Batches (e.g. silage from Maize Field 2025).

---

## 2. People & Roles

### Farm Owner
The person with full administrative access to the DFMS for a given Farm. Can view all data, approve flagged records, manage workers, configure the system, and access financial reports. Typically accesses the system via the Owner Dashboard (web).

### Worker
A farm employee responsible for daily operational tasks: milking, feeding, health observation, and task completion. Accesses the system exclusively via the Kiosk Client using a Worker ID and PIN. Workers do not see financial data, analytics, or flagged record reviews.

### Worker ID
A short numeric identifier (3–4 digits) assigned to each Worker by the Farm Owner. Used for Kiosk authentication. Not an email address.

### PIN
A 4-digit numeric code assigned to a Worker for Kiosk login. Stored as a bcrypt hash. Never stored in plaintext. PIN reset is Owner-only (BR-018).

### Kiosk Session
An authenticated session on a Kiosk device, established when a Worker successfully enters their Worker ID and PIN. Expires after 15 minutes of inactivity or on explicit logout (BR-013). All commands issued during a session are tagged with the Worker ID and Device ID.

### Veterinarian (Vet)
A licensed animal health professional who visits the farm to examine and treat animals. Does not hold a permanent DFMS account in v1. Vet actions are recorded via the Vet Visit mode on the Kiosk, either by the Vet directly (supervised) or by the Worker or Owner from a paper record.

### Vet Name
A free-text field optionally captured at time of treatment entry. Not a system account. Used for audit trail only.

---

## 3. Animals

### Animal
Any bovine on the farm assigned a unique `animal_tag`. Includes Cows, Heifers, Calves, and Bulls. An Animal is created by exactly one `AnimalRegistered` event (BR-015). Its lifecycle is tracked entirely through subsequent events — current status is always derived, never stored as a static field.

### Animal Registered
The sole creation event for an Animal record. Every Animal enters the system via `AnimalRegistered`. This event is emitted by:

1. **`RegisterAnimal` command** — Owner registers an animal entering the farm (typically a purchase).
2. **`RecordCalving` command** (side effect) — one `AnimalRegistered` event per live calf born.

`AnimalPurchased` is a separate event recording acquisition details; it always accompanies `AnimalRegistered` when the source is a purchase. It is never a substitute for `AnimalRegistered`.

### Animal Purchased
A Domain Event recording that an Animal entered the farm via purchase. Fields include purchase date and purchase price. Always emitted together with `AnimalRegistered` when the Owner uses `RegisterAnimal` for a purchased animal. Not used for calves born on farm (those are created via `RecordCalving`).

### Animal Tag
The unique identifier for an Animal within a Farm. Typically matches the physical ear tag number. Format: alphanumeric, up to 20 characters. Example: `"KE-101"`, `"027"`. Must be unique per Farm at time of `AnimalRegistered`.

### Cow
A female bovine that has calved at least once. A Heifer becomes a Cow immediately upon the recording of her first `CalvingRecorded` event.

### Heifer
A female bovine that has not yet calved and has been weaned. Becomes a Cow upon her first `CalvingRecorded` event.

### Calf
A bovine that has not yet been weaned. A female Calf becomes a Heifer after a `WeaningRecorded` event. A male Calf retained for breeding becomes a Bull after `WeaningRecorded`; a male Calf not retained is sold or culled via `AnimalSold` or `AnimalDied` without becoming a Bull.

### Weaning Recorded
A Domain Event marking the transition of a Calf out of the calf stage. After `WeaningRecorded`, a female becomes a Heifer; a male retained for breeding becomes a Bull.

### Bull
A male bovine used for natural service. Tracked as an Animal but not part of the milking or reproduction pipeline beyond service records. Becomes a Bull after `WeaningRecorded` if retained for breeding.

### In-Calf
An Animal with a confirmed Pregnancy (see below). Status is derived from the most recent `PregnancyConfirmed` event with no subsequent `PregnancyLost` or `CalvingRecorded` event.

### Dry Cow
A Cow currently not in active Lactation — i.e., after a `DryOffRecorded` event and before the next `CalvingRecorded` event.

### Lactating Cow
A Cow with an open Lactation Cycle — i.e., after the first `MilkingRecorded` event of a Lactation Cycle and before a `DryOffRecorded` or `CalvingRecorded` event closes it.

### Active Animal
Any Animal on the farm that has not been sold or died. Derived from the absence of `AnimalSold` and `AnimalDied` events (BR-001).

### Sold Animal
An Animal for which an `AnimalSold` event has been recorded. A Sold Animal cannot receive new operational events (BR-001).

### Dead Animal
An Animal for which an `AnimalDied` event has been recorded. Cannot receive new operational events (BR-001).

---

## 4. Reproduction

### Breeding Event
Any recorded act of attempting conception in a female Animal: either Artificial Insemination (AI) or Natural Service (NS). Records: date, method (AI/NS), sire ID or bull ID, inseminator name (optional). Outcome is not stored on the Breeding Event — it is recorded via subsequent `PregnancyConfirmed` or `PregnancyNotConfirmed` events.

### Artificial Insemination (AI)
A Breeding Event using stored semen from a named sire, administered by an AI Technician.

### Natural Service (NS)
A Breeding Event using an on-farm Bull.

### AI Technician
The person performing an AI procedure. Recorded by name (free text) on the Breeding Event. Not a system account.

### Heat
The observable fertile period of a female Animal. Duration: approximately 12–18 hours. Detected by worker observation and recorded as an `ObservationRecorded` event with type `IN_HEAT`. Not stored as a status field — derived from observation events.

### Pregnancy Check
A veterinary examination to confirm or deny pregnancy following a Breeding Event. Results in either `PregnancyConfirmed` or `PregnancyNotConfirmed` event.

### Pregnancy
The state of a female Animal between a `PregnancyConfirmed` event and either a `CalvingRecorded` or `PregnancyLost` event. An Animal is considered "In-Calf" when a Pregnancy is open.

### Pregnancy Lost
A Domain Event recording loss of a previously confirmed pregnancy before calving. Closes the open Pregnancy.

### Expected Calving Date (ECD)
Calculated as: date of the Breeding Event that led to `PregnancyConfirmed` + 283 days. Stored as a derived value on the Pregnancy projection. If multiple breedings preceded confirmation, the breeding event linked at `PregnancyConfirmed` is used.

### Calving
The act of giving birth. Recorded as a `CalvingRecorded` event. Closes the active Pregnancy. A Heifer becomes a Cow upon `CalvingRecorded`. Does not automatically open a Lactation Cycle — lactation begins at first `MilkingRecorded` (see Lactation Cycle).

### Calving Difficulty
A classification recorded at time of `CalvingRecorded`: `EASY`, `ASSISTED`, `DIFFICULT`, `CAESAREAN`.

### Open Cow
A female Cow that is Active and not currently In-Calf. "Open" means not confirmed pregnant. Breeding urgency (e.g. days in milk thresholds) is determined by Business Rules, not by the Open Cow definition itself.

---

## 5. Lactation

### Lactation Cycle
A single continuous period of milk production for a Cow. Begins at the first `MilkingRecorded` event after a `CalvingRecorded` event. Ends at a `DryOffRecorded` event or the next `CalvingRecorded` event (whichever occurs first).

**Critical definition note:** Lactation does NOT begin at calving. It begins at first milking. The colostrum period (typically 3–5 days post-calving) exists before commercial milk recording begins. Colostrum is tracked separately via a `ColostralMilkRecorded` event and is never included in Lactation Cycle totals.

### Colostrum Period
The period from `CalvingRecorded` until the first standard `MilkingRecorded` event. Milk during this period is recorded via `ColostralMilkRecorded` and excluded from commercial milk totals and Lactation Cycle calculations.

### Dry-Off
The deliberate cessation of milking for a Cow prior to the next calving. Recorded as a `DryOffRecorded` event. Closes the active Lactation Cycle. The period between `DryOffRecorded` and the next `CalvingRecorded` is the Dry Period.

### Dry Period
The interval between `DryOffRecorded` and the next `CalvingRecorded`. Target: 60 days. Alerts are generated if actual dry period falls outside 45–75 days (BR-002).

### Lactation Number
The count of completed or active Lactation Cycles for a given Cow. Derived from the number of `CalvingRecorded` events. A first-calf heifer is in Lactation 1.

### Milking Session
A single milking event for one Animal. Valid session values: `MORNING`, `MIDDAY`, `EVENING`. The sessions required for an Animal on a given day are defined by its **Milking Schedule** — not fixed system-wide.

### Milking Schedule
The set of sessions assigned to a lactating Animal for a specific calendar date. A **projection** recalculated nightly and stored per Animal per day.

| 7-day rolling average Daily Milk Yield | Sessions |
|----------------------------------------|----------|
| ≤ threshold (default 15L) | `MORNING`, `EVENING` |
| > threshold (default 15L) | `MORNING`, `MIDDAY`, `EVENING` |

- Threshold is configurable per Farm (`three_session_threshold_litres`, default `15.0`).
- Schedule changes apply from the **following calendar day** when an Animal crosses the threshold (BR-023). No Owner confirmation required.
- The Worker never configures sessions. The Kiosk shows only Animals scheduled for the selected session.
- Non-lactating Animals have no Milking Schedule.

### Milking Window
The configured local-time range during which a session entry is considered on-time. Configurable per Farm. Default:

| Session | Window (farm local time) |
|---------|--------------------------|
| `MORNING` | 05:00 – 09:00 |
| `MIDDAY` | 11:00 – 14:00 |
| `EVENING` | 16:00 – 20:00 |

Entries outside the window for the claimed session are **accepted** with `outside_window: true` and flagged for Owner review (BR-021). Entries for a session not on the Animal's Milking Schedule are **rejected** (BR-027).

### Daily Milk Yield
The sum of all `MilkingRecorded` volumes for a single Animal on a single calendar date (farm timezone). Unit: litres, to one decimal place.

### 7-Day Rolling Average Yield
Average Daily Milk Yield over the previous 7 calendar days with at least one milking record. Used for anomaly detection (BR-003). Days with no record are excluded from the average; if fewer than 3 days have records, the average is marked unreliable.

### Saleable Milk
Milk volume eligible for inclusion in a Milk Sale. Calculated as total `MilkingRecorded` volume minus milk recorded during active Withdrawal Periods for the contributing animals. Milk continues to be recorded during withdrawal (BR-005); it is excluded from saleable totals only.

### Milk Sale
A recorded transaction where milk is sold to a buyer. Fields: date, buyer name, litres, price per litre, total amount. Milk Sales are entered by the Owner, not Workers. This is the basis for all revenue calculations. There is no global milk price — price is recorded per transaction (BR-004). Milk Sale litres cannot exceed saleable milk available for the period (BR-005).

---

## 6. Feed & Inventory

### Feed Type
A named category of feed: `SILAGE`, `HAY`, `DAIRY_MEAL`, `WATER`, `MINERAL_SUPPLEMENT`, `OTHER`. Each Feed Type has a unit of measurement (kg for solids, litres for water).

### Feed Batch
A specific physical stock of a Feed Type, with a quantity, unit cost, purchase date, and optional source Field. A Feed Batch is consumed by Feed Allocations until depleted. Multiple Feed Batches of the same Feed Type may coexist.

### Inventory Item
The general term for any trackable stock item on the farm: drugs, vaccines, consumables, and equipment. Feed is tracked via Feed Batches, not Inventory Items. Each Inventory Item has a current quantity derived from purchase events minus consumption events.

### Inventory Transaction
An immutable record of inventory quantity change: `PURCHASE`, `CONSUMPTION`, `ADJUSTMENT`. Consumption is triggered by Treatment and Vaccination events.

### Feed Group Allocation
A recorded feeding event for a named Animal Group: Feed Type, quantity in kg or litres, date, session (MORNING/EVENING), Worker ID. Used for bulk feeds (silage, hay, water) distributed to a group.

### Feed Animal Allocation
A recorded feeding event for a single Animal: Feed Type, quantity, date, session, Worker ID. Used for individual supplements (e.g. dairy meal, which varies by production level). This is a separate entity from Feed Group Allocation and must not be conflated (BR-010).

**Critical distinction:** Dairy meal allocation is per-animal because the quantity is proportional to individual milk output. Silage and hay are per-group. The Worker sees both via the same "Record Feed" screen, but they emit different commands and are stored differently.

### Days of Feed Remaining
Calculated as:
```
Current quantity of Feed Type in stock
÷ 7-day average daily consumption of that Feed Type
```
Where 7-day average excludes days with zero consumption only if the farm was not operating (owner-flagged). Unit: days, rounded to one decimal place.

### Silage Pit
A named physical storage structure for silage on the farm. Has a capacity (tonnes) and a current estimated quantity. Quantity is updated by Feed Batch additions and Feed Group Allocations. Distinct from Field — a Field is where crop is grown; a Silage Pit is where harvested silage is stored.

---

## 7. Health & Treatments

### Treatment
A recorded veterinary intervention on a single Animal: drug name, dose, route of administration (oral/injection/topical), date, Vet Name (optional), recorded by Worker ID. Always generates a Withdrawal Period via `TreatmentRecorded`.

### Drug
A named veterinary medicine tracked in inventory. Has a default Withdrawal Period in days. Drugs are tracked as Inventory Items and are depleted by `TreatmentRecorded` events.

### Withdrawal Period
The interval after a Treatment during which milk from the treated Animal must not be sold, and the Animal must not be slaughtered for meat. Calculated as: treatment date + withdrawal days.

**Milk recording during withdrawal:** Milking continues normally. Workers record milk via `RecordMilking` without restriction. Milk produced during an active Withdrawal Period is marked as non-saleable and excluded from the saleable milk pool (BR-005). The Kiosk does not block milk entry during withdrawal.

**Milk sale during withdrawal:** The Owner Dashboard blocks Milk Sale allocation of litres attributable to animals in active withdrawal.

### Vaccination
A preventive health intervention using a vaccine. Recorded via `RecordVaccination` command, emitting `VaccinationRecorded`. Generates a vaccination schedule reminder for booster doses.

### Health Observation
A worker-recorded note about an Animal's condition. Not a Treatment. Fields: Animal Tag, observation type (enumerated: `NOT_EATING`, `LIMPING`, `LOW_MILK`, `IN_HEAT`, `INJURY`, `SWOLLEN_UDDER`, `UNUSUAL_BEHAVIOUR`, `OTHER`), optional photo, optional text note, date/time, Worker ID. Does not affect inventory or generate a Withdrawal Period. Creates a Notification for Owner review (BR-016) — not a Flagged Record.

### Vet Visit
A structured data entry session on the Kiosk initiated to record a veterinarian's examination and treatment of one or more Animals. Uses the Vet Visit mode. May result in one or more `RecordTreatment` or `RecordVaccination` commands.

---

## 8. Tasks, Notifications & Workflow

### Task
A named operational action assigned to a Worker with a due date. Can be: system-generated (e.g. "AI due for Cow 27 — 15 June") or manually created by the Owner. Tasks appear on the Worker's task list. Completion is recorded via `CompleteTask` command.

### System-Generated Task
A Task automatically created by the system as a side effect of a Domain Event (e.g. `CalvingRecorded` → creates "Schedule first milking" task).

### Notification
A system-generated alert requiring awareness or action by the Owner. Fields: type, priority, related entity (animal_tag or other reference), due date (optional), message, resolved flag, created_at.

Notifications are created as side effects of Domain Events. Examples: `ObservationRecorded` → health observation notification; `TreatmentRecorded` → withdrawal ending soon; low inventory alert.

Notifications are distinct from Flagged Records. Notifications surface on the Owner Dashboard Morning Intelligence view.

### Flagged Record
A data entry that falls outside expected statistical bounds (e.g. unusual milk volume, unusual feed amount) and requires Owner review. Created automatically by validation rules. Does not block the Worker — the entry is saved. Appears in Flagged Records Review on the Owner Dashboard. A Flagged Record can be approved or corrected via `CorrectionRecorded`.

Health Observations are **not** Flagged Records.

### Correction Recorded
A Domain Event recording that an Owner corrected a previously saved entry. The original event is preserved unchanged. `CorrectionRecorded` references the original event ID and contains the corrected values.

---

## 9. Groups

### Animal Group
A named collection of Animals used for feed management and reporting. Examples: `LACTATING_COWS`, `DRY_COWS`, `HEIFERS`, `CALVES`. An Animal has at most one **current** Group Membership at any point in time.

### Animal Group Membership
A time-bounded record of an Animal's membership in a Group. Fields: animal_tag, group_name, start_date, end_date (null if current). Historical Group Membership is preserved — querying "which group was Cow 27 in on 15 March?" must always be answerable (BR-006).

**Critical note:** Group membership is NOT a static foreign key on the Animal record. It is a separate entity with a date range. Group changes are recorded via `AnimalGroupChanged` events.

---

## 10. System & Infrastructure

### Kiosk
A shared desktop computer on the farm running a browser-based worker client in fullscreen mode. The primary data entry point for Workers. Operates on the Farm LAN. Does not require internet access for core operations (BR-007). v1 deployment: one Kiosk device (`KIOSK-01`) in the milking parlour.

### Device ID
A unique identifier for each Kiosk device on a Farm. Assigned at setup. All commands are tagged with both Worker ID (who entered) and Device ID (which terminal was used).

### Farm LAN
The local area network on the farm connecting the Kiosk(s) to the local Farm Server. Operates independently of internet connectivity.

### Farm Server
A small always-on computer on the Farm LAN running the DFMS API and PostgreSQL database. All Kiosk commands are sent to the Farm Server. Internet connectivity is used only for cloud backup and remote Owner Dashboard access — it is never required for Kiosk operation.

### Kiosk Offline Queue
When the Farm Server is temporarily unavailable, the Kiosk stores pending commands locally (IndexedDB) and submits them when the server returns (BR-014). The Worker sees a "Syncing..." indicator; commands are not lost.

### Cloud Sync
An asynchronous background job that replicates Farm Server data to cloud storage when internet is available. Used for off-site backup and Owner Dashboard remote access. Never on the critical path for Worker data entry. Observation photos are stored on the Farm Server first; cloud sync is async (BR-017).

### Owner Dashboard
A web-based interface for the Farm Owner. Accessible remotely (via cloud) or on the Farm LAN. Displays analytics, flagged records, notifications, financial reports, and system configuration. Not available on the Kiosk Worker UI in v1.

---

## 11. Financial

### Expense
A financial outflow associated with farm operations. Fields: date, category (`FEED`, `HEALTH`, `LABOUR`, `EQUIPMENT`, `OTHER`), amount (KES), description, optional link to animal_tag or group. Recorded by Owner via `RecordExpense` command.

### Income
A financial inflow associated with farm operations. Fields: date, category (`MILK_SALE`, `ANIMAL_SALE`, `MANURE`, `OTHER`), amount (KES), description, optional link to animal_tag. Milk revenue is recorded via `Milk Sale` (a subtype of Income), not via a global price.

### Animal Sale
A recorded transaction where an Animal is sold. Emits `AnimalSold` event (which closes the Animal to further operational events) and an Income record with category `ANIMAL_SALE`. Recorded by Owner only.

### Cost Per Litre
Total farm operating Expenses for a period ÷ total litres sold in the same period. Calculated on demand. Not stored.

### Feed Cost Per Litre
Total feed cost allocated to lactating animals in a period ÷ total litres produced in the same period. Requires Feed Animal Allocation and Feed Group Allocation records with unit costs from Feed Batches.

---

## Appendix A — Specification vs Implementation Scope

**Specification documents describe the complete intended system.** Implementation is delivered in phases (see DFMS-Implementation-Phases.md when published). The data model and domain events are designed for the full system; only the built UI and API endpoints vary by phase.

The following are specified in the domain model but not built in implementation Phase 1:

- Breeding, pregnancy, and calving workflows (Phase 2)
- Full financial analytics (Phase 3)
- Sensor and MQTT ingestion (Phase 4)
- Dedicated mobile app (Phase 2+)
- Vet one-time token link (Phase 5)

---

## Appendix B — Units of Measurement

| Quantity | Unit | Notes |
|----------|------|-------|
| Milk volume | Litres (L) | One decimal place |
| Feed solids | Kilograms (kg) | One decimal place |
| Water | Litres (L) | Whole number sufficient |
| Drug dose | Millilitres (ml) or grams (g) | One decimal place |
| Money | KES (Kenyan Shilling) | Two decimal places |
| Days | Integer days | For periods, dry days, withdrawal |
| Time | 24-hour HH:MM | Local farm timezone |
| Field area | Hectares (ha) | Two decimal places |

---

## Appendix C — Status Derived vs Stored

All Animal statuses are **derived from event history**, not stored as fields:

| Status | Derived from |
|--------|-------------|
| Is Cow | Has at least one `CalvingRecorded` event |
| Is Heifer | Female, no `CalvingRecorded` event, `WeaningRecorded` exists |
| Is Calf | No `WeaningRecorded` event |
| Is Bull | Male, `WeaningRecorded` exists, retained for breeding |
| Is In-Calf | Open `PregnancyConfirmed` event exists |
| Is Lactating | Open Lactation Cycle exists (post first milking) |
| Is Dry | `CalvingRecorded` exists, `DryOffRecorded` closed last Lactation, no new `CalvingRecorded` |
| Is Active | No `AnimalSold` or `AnimalDied` event |
| Is Open | Active female Cow, not In-Calf |
| Has Withdrawal Active | `TreatmentRecorded` with withdrawal end date > today |

No column named `status`, `is_lactating`, `is_pregnant`, or similar may exist on the Animals table.

---

## Appendix D — Business Rules Registry (Authoritative Index)

All Business Rules use the `BR-NNN` format. No prefixes. Full rule text lives in DFMS-Business-Rules.md; this index is the canonical numbering.

| ID | Summary |
|----|---------|
| BR-001 | `AnimalSold` or `AnimalDied` → no new operational events; removed from Worker selection lists |
| BR-002 | Dry period outside 45–75 days → alert |
| BR-003 | Milk volume > 2× 7-day average → Flagged Record; not blocked |
| BR-004 | No global milk price; revenue from Milk Sale transactions only |
| BR-005 | Withdrawal blocks milk **sale**, not milk **recording**; non-saleable milk excluded from saleable pool |
| BR-006 | Animal Group Membership is time-series; history never deleted |
| BR-007 | Worker commands succeed on Farm LAN without internet |
| BR-008 | Open Cow past 80 days in milk without breeding → alert |
| BR-009 | Single-session milk volume > 60L → hard block |
| BR-010 | Feed Group Allocation and Feed Animal Allocation stored separately |
| BR-011 | Treatment must include: animal, drug, dose > 0, route, withdrawal days |
| BR-012 | Kiosk Worker UI must not display financial data, analytics, or flagged record review |
| BR-013 | Kiosk session expires after 15 minutes inactivity |
| BR-014 | Kiosk queues commands locally when Farm Server unavailable |
| BR-015 | `AnimalRegistered` is the sole Animal creation event |
| BR-016 | `ObservationRecorded` creates Notification, not Flagged Record |
| BR-017 | Photos stored on Farm Server first; cloud sync async |
| BR-018 | PIN reset: Owner only via Dashboard |
| BR-019 | Backdating: treatments up to 48h; milk/feed up to 24h |
| BR-020 | Lactation begins at first milking, not calving |
| BR-021 | Milking outside window → accepted, flagged |
| BR-022 | Missed scheduled milking → Notification; escalate after 30 min |
| BR-023 | Milking Schedule recalculated nightly; 15L threshold; effective next day |
| BR-024 | ECD = breeding date + 283 days |
| BR-025 | Corrections preserve original events |
| BR-026 | Multi-tenant `farm_id` isolation |
| BR-027 | Session not on Animal's schedule → hard block |
| BR-029 | One milking record per animal per session per day |
| BR-030 | Feed batch FIFO depletion |

---

*End of DFMS-Glossary.md v0.3*
