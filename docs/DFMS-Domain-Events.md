# DFMS-Domain-Events.md
**Dairy Farm Management System — Domain Events Specification**
Version: 0.2 | Status: DRAFT | Author: Mash | Date: 2026-06-21

---

## Purpose

This document specifies every Command in DFMS: its inputs, validations, emitted Domain Events, side effects, and failure modes. It is the authoritative behavioural specification. Database schema, API endpoints, and UI flows are derived from this document.

**Dependencies:** DFMS-Glossary.md (terms), DFMS-Roles-and-Clients.md (who issues commands).

**Conventions:**
- Commands are imperative: `RegisterAnimal`, `RecordMilking`
- Events are past tense: `AnimalRegistered`, `MilkingRecorded`
- All IDs are UUID v4 unless noted
- All timestamps are UTC stored; displayed in Farm timezone
- Every successful command records: `farm_id`, `issued_by` (user/worker ID), `issued_at`, `device_id` (if Kiosk)

---

## Command Index

| Command | Issued By | Client | Implementation Phase |
|---------|-----------|--------|---------------------|
| `RegisterAnimal` | Owner | Owner Dashboard | 1 |
| `RecordMilking` | Worker | Kiosk | 1 |
| `RecordFeedGroupAllocation` | Worker | Kiosk | 1 |
| `RecordObservation` | Worker | Kiosk | 1 |
| `RecordTreatment` | Worker | Kiosk (Vet Visit) | 1 |

---

## 1. RegisterAnimal

### Purpose
Create a new Animal record for an animal entering the farm. This is the **only** Owner-initiated path for registering purchased animals. Calves born on farm are created via `RecordCalving` (Phase 2), which also emits `AnimalRegistered`.

### Issued By
Farm Owner only.

### Input

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `animal_tag` | string | yes | Unique within farm; max 20 chars |
| `name` | string | no | Display name |
| `sex` | enum | yes | `FEMALE`, `MALE` |
| `breed` | string | yes | Free text or farm breed list |
| `date_of_birth` | date | yes | ISO 8601 |
| `dam_tag` | string | no | Must reference existing Animal if provided |
| `sire_tag` | string | no | Reference or free text |
| `purchase_date` | date | yes | Date animal arrived on farm |
| `purchase_price` | decimal | no | KES, two decimal places |
| `initial_group` | enum | yes | `LACTATING_COWS`, `DRY_COWS`, `HEIFERS`, `CALVES` |
| `notes` | string | no | Max 500 chars |

### Validations

| ID | Rule | Failure Code |
|----|------|--------------|
| V-RA-001 | `animal_tag` must be unique within farm | `DUPLICATE_TAG` |
| V-RA-002 | `date_of_birth` must not be in the future | `INVALID_DOB` |
| V-RA-003 | `purchase_date` must not be in the future | `INVALID_PURCHASE_DATE` |
| V-RA-004 | If `dam_tag` provided, dam must exist and be Active | `DAM_NOT_FOUND` |
| V-RA-005 | `purchase_price` if provided must be ≥ 0 | `INVALID_PRICE` |

### Events Emitted (on success)

#### 1. `AnimalRegistered`
```json
{
  "event_type": "AnimalRegistered",
  "animal_id": "uuid",
  "animal_tag": "101",
  "farm_id": "uuid",
  "sex": "FEMALE",
  "breed": "Friesian",
  "date_of_birth": "2024-03-15",
  "dam_id": "uuid | null",
  "sire_reference": "string | null",
  "registered_at": "2026-06-21T08:00:00Z",
  "registered_by": "owner_user_id"
}
```

#### 2. `AnimalPurchased`
Always emitted with `RegisterAnimal` for this command path.
```json
{
  "event_type": "AnimalPurchased",
  "animal_id": "uuid",
  "farm_id": "uuid",
  "purchase_date": "2026-06-20",
  "purchase_price": 85000.00,
  "purchased_at": "2026-06-21T08:00:00Z",
  "recorded_by": "owner_user_id"
}
```

#### 3. `AnimalGroupChanged`
```json
{
  "event_type": "AnimalGroupChanged",
  "animal_id": "uuid",
  "farm_id": "uuid",
  "group": "HEIFERS",
  "previous_group": null,
  "effective_at": "2026-06-20",
  "recorded_at": "2026-06-21T08:00:00Z",
  "recorded_by": "owner_user_id"
}
```

### Side Effects

| Effect | Detail |
|--------|--------|
| Audit trail | Full command + all events logged |
| Expense (optional) | If `purchase_price` provided, system prompts Owner to create linked Expense — not automatic in v1 |
| Projections | Animal appears in Active Animal list; current group membership set |

### Failures
On any validation failure: no events emitted. HTTP 422 with failure code and field errors.

### Notes
- `AnimalRegistered` is the sole creation event (BR-015)
- `RegisterAnimal` is never used for calves born on farm — those are created by `RecordCalving` in Phase 2

---

## 2. RecordMilking

### Purpose
Record milk volume for one Animal in one milking session. Sessions are `MORNING`, `MIDDAY`, or `EVENING`. Which sessions apply to an Animal on a given day is determined by its **Milking Schedule** projection (BR-023).

### Issued By
Worker (Kiosk).

### Input

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `animal_tag` | string | yes | Must be Active Lactating Cow |
| `session` | enum | yes | `MORNING`, `MIDDAY`, `EVENING` |
| `volume_litres` | decimal | yes | One decimal place; ≥ 0 |
| `recorded_at` | datetime | yes | Defaults to now; backdating up to 24h (BR-019) |
| `worker_id` | string | yes | From Kiosk session |
| `device_id` | string | yes | From Kiosk device |

### Validations

| ID | Rule | Failure Code |
|----|------|--------------|
| V-RM-001 | Animal must exist and be Active | `ANIMAL_NOT_FOUND` |
| V-RM-002 | Animal must be Lactating (derived) | `ANIMAL_NOT_LACTATING` |
| V-RM-003 | `volume_litres` ≥ 0 | `INVALID_VOLUME` |
| V-RM-004 | `volume_litres` > 60 → hard block | `VOLUME_IMPLAUSIBLE` (BR-009) |
| V-RM-005 | `recorded_at` not more than 24h in past | `BACKDATE_LIMIT_EXCEEDED` |
| V-RM-006 | `recorded_at` not in the future | `FUTURE_DATE` |
| V-RM-007 | Duplicate: same animal + session + calendar date → update, not duplicate | See idempotency (BR-029) |
| V-RM-008 | `session` must be in Animal's Milking Schedule for `milking_date` | `SESSION_NOT_SCHEDULED` (BR-027) |

**Soft validation (does not block):**
- `volume_litres` > 2× 7-day rolling average → save with `flagged: true` (BR-003)
- `recorded_at` outside Milking Window for `session` → save with `outside_window: true` (BR-021)

**Withdrawal:** No validation block. Animals in withdrawal may be milked (BR-005).

### Events Emitted (on success)

#### 1. `MilkingRecorded`
```json
{
  "event_type": "MilkingRecorded",
  "event_id": "uuid",
  "animal_id": "uuid",
  "animal_tag": "101",
  "farm_id": "uuid",
  "lactation_cycle_id": "uuid",
  "session": "MORNING",
  "volume_litres": 12.5,
  "recorded_at": "2026-06-21T05:30:00Z",
  "milking_date": "2026-06-21",
  "worker_id": "W-002",
  "device_id": "KIOSK-01",
  "flagged": false,
  "outside_window": false,
  "saleable": true
}
```

`saleable` is `false` if Animal has active Withdrawal Period at `recorded_at`; derived at write time from Withdrawal projection.

#### 2. `FlaggedRecordCreated` (conditional)
Emitted when soft validation triggers (BR-003 and/or BR-021).

**Reason codes:**
- `VOLUME_ABOVE_2X_AVERAGE` (BR-003)
- `OUTSIDE_MILKING_WINDOW` (BR-021)

```json
{
  "event_type": "FlaggedRecordCreated",
  "flagged_record_id": "uuid",
  "source_event_id": "uuid",
  "source_event_type": "MilkingRecorded",
  "reason": "OUTSIDE_MILKING_WINDOW",
  "expected_range": "05:00 - 09:00",
  "actual_value": "10:30",
  "farm_id": "uuid",
  "created_at": "2026-06-21T07:30:00Z"
}
```

#### 3. `NotificationResolved` (conditional)
If a `MISSED_MILKING` notification exists for this (`animal_id`, `session`, `milking_date`), it is auto-resolved when `MilkingRecorded` is submitted (even if late/flagged).

### Side Effects

| Effect | Detail |
|--------|--------|
| Lactation Cycle | If no open Lactation Cycle exists and Animal has prior `CalvingRecorded`, open new cycle on first `MilkingRecorded` post-calving (BR-020) |
| Daily yield projection | Recalculate Daily Milk Yield for animal + date |
| Saleable milk projection | Update farm saleable milk pool for milking_date |
| Missed milking notification | Auto-resolve if pending (BR-022) |
| Audit trail | Command + events logged |

### Kiosk Behaviour

1. Pre-select `session` from current time and Milking Window (BR-021)
2. If current time falls outside all windows → prompt "Which session are you recording?"
3. Display only Active Lactating Cows whose **Milking Schedule for today** includes the selected session (BR-023, BR-027)
4. Show session indicator on tile: `2×` or `3×` (optional badge for 3-session cows)
5. Green tick on cows already recorded for this session today

### Background Jobs (related)

| Job | Schedule | Purpose |
|-----|----------|---------|
| `recalculate_milking_schedules` | Daily 00:05 farm time | Write tomorrow's Milking Schedule (BR-023) |
| `check_missed_milkings` | At each window close | Emit `MISSED_MILKING` notifications (BR-022) |
| `escalate_missed_milkings` | Window close + 30 min | Upgrade to CRITICAL if still missing (BR-022) |

### Idempotency
One `MilkingRecorded` per (`animal_id`, `session`, `milking_date`) — BR-029. If Worker re-submits for same combination, system emits correction flow if volume differs, or returns existing record if identical.

### Failures
| Code | HTTP | Worker Experience |
|------|------|-------------------|
| `VOLUME_IMPLAUSIBLE` | 422 | Hard block with message |
| `SESSION_NOT_SCHEDULED` | 422 | "Cow 104 is not milked at Midday" — should not occur if Kiosk filters correctly |
| `ANIMAL_NOT_LACTATING` | 422 | "Cow 101 is not lactating" |
| All others | 422 | Error message on Kiosk |

---

## 3. RecordFeedGroupAllocation

### Purpose
Record feed distributed to an Animal Group (silage, hay, water).

### Issued By
Worker (Kiosk).

### Input

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `feed_type` | enum | yes | `SILAGE`, `HAY`, `WATER`, `OTHER` |
| `animal_group` | enum | yes | `LACTATING_COWS`, `DRY_COWS`, `HEIFERS`, `CALVES` |
| `quantity` | decimal | yes | kg or litres per Feed Type unit |
| `session` | enum | yes | `MORNING`, `EVENING` |
| `recorded_at` | datetime | yes | Defaults to now; backdating up to 24h (BR-019) |
| `feed_batch_id` | uuid | no | If omitted, FIFO depletion from oldest batch |
| `worker_id` | string | yes | From session |
| `device_id` | string | yes | From device |

### Validations

| ID | Rule | Failure Code |
|----|------|--------------|
| V-RF-001 | `quantity` > 0 | `INVALID_QUANTITY` |
| V-RF-002 | `animal_group` must have ≥ 1 Active member | `EMPTY_GROUP` |
| V-RF-003 | `feed_type` must not be `DAIRY_MEAL` or `MINERAL_SUPPLEMENT` — use `RecordFeedAnimalAllocation` | `WRONG_COMMAND` |
| V-RF-004 | If `feed_batch_id` provided, batch must exist with sufficient quantity | `INSUFFICIENT_STOCK` |
| V-RF-005 | `recorded_at` not more than 24h in past | `BACKDATE_LIMIT_EXCEEDED` |

**Soft validation:**
- `quantity` > 3× group's 7-day average for same feed type + session → `flagged: true`

### Events Emitted (on success)

#### 1. `FeedGroupAllocationRecorded`
```json
{
  "event_type": "FeedGroupAllocationRecorded",
  "event_id": "uuid",
  "farm_id": "uuid",
  "feed_type": "SILAGE",
  "animal_group": "LACTATING_COWS",
  "quantity": 120.0,
  "unit": "kg",
  "session": "MORNING",
  "feed_batch_id": "uuid",
  "recorded_at": "2026-06-21T06:00:00Z",
  "allocation_date": "2026-06-21",
  "worker_id": "W-002",
  "device_id": "KIOSK-01",
  "flagged": false
}
```

#### 2. `FeedBatchDepleted` (conditional)
Emitted when a Feed Batch quantity reaches zero.
```json
{
  "event_type": "FeedBatchDepleted",
  "feed_batch_id": "uuid",
  "farm_id": "uuid",
  "feed_type": "SILAGE",
  "depleted_at": "2026-06-21T06:00:00Z"
}
```

#### 3. `FlaggedRecordCreated` (conditional)
Same structure as milking; reason: `FEED_ABOVE_3X_AVERAGE`.

#### 4. `NotificationCreated` (conditional)
If Days of Feed Remaining for this Feed Type drops below 14 after depletion:
```json
{
  "event_type": "NotificationCreated",
  "notification_id": "uuid",
  "farm_id": "uuid",
  "type": "LOW_FEED_STOCK",
  "priority": "HIGH",
  "entity_type": "FEED_BATCH",
  "entity_id": "uuid",
  "message": "Silage: 12 days remaining",
  "resolved": false,
  "created_at": "2026-06-21T06:00:00Z"
}
```

### Side Effects

| Effect | Detail |
|--------|--------|
| Feed Batch quantity | Decrease by `quantity` (FIFO if no batch specified) |
| Days of Feed Remaining | Recalculate for Feed Type |
| Feed cost allocation | Group cost = quantity × batch unit cost; used in Feed Cost Per Litre |
| Audit trail | Full log |

### Failures
`WRONG_COMMAND` if Worker selected dairy meal — Kiosk should route to `RecordFeedAnimalAllocation` before API call.

---

## 4. RecordObservation

### Purpose
Record a worker-observed health or behaviour issue. Does not administer treatment.

### Issued By
Worker (Kiosk).

### Input

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `animal_tag` | string | yes | Any Active Animal |
| `observation_type` | enum | yes | `NOT_EATING`, `LIMPING`, `LOW_MILK`, `IN_HEAT`, `INJURY`, `SWOLLEN_UDDER`, `UNUSUAL_BEHAVIOUR`, `OTHER` |
| `notes` | string | no | Required if type is `OTHER`; max 500 chars |
| `photo_attachment_id` | uuid | no | Uploaded separately; stored on Farm Server (BR-017) |
| `recorded_at` | datetime | yes | Defaults to now |
| `worker_id` | string | yes | From session |
| `device_id` | string | yes | From device |

### Validations

| ID | Rule | Failure Code |
|----|------|--------------|
| V-RO-001 | Animal must exist and be Active | `ANIMAL_NOT_FOUND` |
| V-RO-002 | If `observation_type` is `OTHER`, `notes` required | `NOTES_REQUIRED` |
| V-RO-003 | `recorded_at` not in the future | `FUTURE_DATE` |

### Events Emitted (on success)

#### 1. `ObservationRecorded`
```json
{
  "event_type": "ObservationRecorded",
  "event_id": "uuid",
  "animal_id": "uuid",
  "animal_tag": "101",
  "farm_id": "uuid",
  "observation_type": "LIMPING",
  "notes": null,
  "photo_attachment_id": "uuid | null",
  "recorded_at": "2026-06-21T07:15:00Z",
  "worker_id": "W-002",
  "device_id": "KIOSK-01"
}
```

#### 2. `NotificationCreated`
Always emitted (BR-016). Observations create Notifications, not Flagged Records.
```json
{
  "event_type": "NotificationCreated",
  "notification_id": "uuid",
  "farm_id": "uuid",
  "type": "HEALTH_OBSERVATION",
  "priority": "MEDIUM",
  "entity_type": "ANIMAL",
  "entity_id": "uuid",
  "entity_tag": "101",
  "message": "Cow 101: Limping reported by John",
  "due_date": null,
  "resolved": false,
  "created_at": "2026-06-21T07:15:00Z"
}
```

**Priority overrides:**
- `INJURY`, `SWOLLEN_UDDER` → `HIGH`
- `IN_HEAT` → `LOW` (informational for breeding pipeline, Phase 2)

### Side Effects

| Effect | Detail |
|--------|--------|
| Owner Dashboard | Notification appears in Attention Required |
| Heat tracking | If `IN_HEAT`, projection updated for breeding alerts (Phase 2) |
| Audit trail | Full log |
| No inventory change | Observations do not deplete drugs |
| No withdrawal | Observations do not create withdrawal periods |

### Failures
Standard 422 responses. No partial success.

---

## 5. RecordTreatment

### Purpose
Record administration of a drug to an Animal. Creates a Withdrawal Period.

### Issued By
Worker (Kiosk, Vet Visit mode). Owner may also issue via Dashboard (paper fallback entry).

### Input

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `animal_tag` | string | yes | Active Animal |
| `drug_id` | uuid | yes | Must exist in inventory |
| `dose` | decimal | yes | Must be > 0 |
| `dose_unit` | enum | yes | `ML`, `G`, `DOSES` |
| `route` | enum | yes | `INJECTION`, `ORAL`, `TOPICAL` |
| `withdrawal_days` | integer | yes | Days milk/meat withheld |
| `diagnosis` | string | no | Max 500 chars |
| `vet_name` | string | no | Free text |
| `recorded_at` | datetime | yes | Backdating up to 48h (BR-019) |
| `worker_id` | string | yes | From session |
| `device_id` | string | yes | From device |

### Validations

| ID | Rule | Failure Code |
|----|------|--------------|
| V-RT-001 | Animal must exist and be Active | `ANIMAL_NOT_FOUND` |
| V-RT-002 | `drug_id` must exist | `DRUG_NOT_FOUND` |
| V-RT-003 | `dose` > 0 | `INVALID_DOSE` |
| V-RT-004 | `withdrawal_days` ≥ 0 | `INVALID_WITHDRAWAL` |
| V-RT-005 | `route` must be valid enum | `INVALID_ROUTE` |
| V-RT-006 | If drug tracked in inventory, sufficient stock for dose | `INSUFFICIENT_STOCK` |
| V-RT-007 | `recorded_at` not more than 48h in past | `BACKDATE_LIMIT_EXCEEDED` |
| V-RT-008 | `recorded_at` not in the future | `FUTURE_DATE` |

All fields in BR-011 are mandatory except `diagnosis` and `vet_name`.

### Events Emitted (on success)

#### 1. `TreatmentRecorded`
```json
{
  "event_type": "TreatmentRecorded",
  "event_id": "uuid",
  "animal_id": "uuid",
  "animal_tag": "103",
  "farm_id": "uuid",
  "drug_id": "uuid",
  "drug_name": "Oxytetracycline",
  "dose": 10.0,
  "dose_unit": "ML",
  "route": "INJECTION",
  "withdrawal_days": 7,
  "withdrawal_end_date": "2026-06-28",
  "diagnosis": "Mastitis",
  "vet_name": "Dr. Kamau",
  "recorded_at": "2026-06-21T09:00:00Z",
  "treatment_date": "2026-06-21",
  "worker_id": "W-002",
  "device_id": "KIOSK-01"
}
```

#### 2. `InventoryConsumed`
```json
{
  "event_type": "InventoryConsumed",
  "transaction_id": "uuid",
  "farm_id": "uuid",
  "inventory_item_id": "uuid",
  "quantity": 10.0,
  "unit": "ML",
  "reason": "TREATMENT",
  "source_event_id": "uuid",
  "recorded_at": "2026-06-21T09:00:00Z"
}
```

#### 3. `WithdrawalPeriodStarted`
```json
{
  "event_type": "WithdrawalPeriodStarted",
  "withdrawal_id": "uuid",
  "animal_id": "uuid",
  "farm_id": "uuid",
  "source_event_id": "uuid",
  "start_date": "2026-06-21",
  "end_date": "2026-06-28",
  "drug_name": "Oxytetracycline",
  "created_at": "2026-06-21T09:00:00Z"
}
```

#### 4. `NotificationCreated`
```json
{
  "event_type": "NotificationCreated",
  "notification_id": "uuid",
  "farm_id": "uuid",
  "type": "WITHDRAWAL_STARTED",
  "priority": "HIGH",
  "entity_type": "ANIMAL",
  "entity_id": "uuid",
  "entity_tag": "103",
  "message": "Cow 103: withdrawal until 28 Jun — milk not for sale",
  "due_date": "2026-06-28",
  "resolved": false,
  "created_at": "2026-06-21T09:00:00Z"
}
```

#### 5. `NotificationCreated` (scheduled)
Celery job schedules notification for withdrawal end date:
```json
{
  "event_type": "NotificationCreated",
  "type": "WITHDRAWAL_ENDING",
  "priority": "MEDIUM",
  "message": "Cow 103: withdrawal ends tomorrow",
  "due_date": "2026-06-27"
}
```

### Side Effects

| Effect | Detail |
|--------|--------|
| Withdrawal projection | Animal milk marked non-saleable until `end_date` (BR-005) |
| Milking | `RecordMilking` continues to work; `saleable: false` on milk events during withdrawal |
| Milk Sale | Owner Dashboard blocks allocating this animal's milk to sales during withdrawal |
| Inventory | Drug stock reduced |
| Low stock alert | If drug quantity below threshold → `NotificationCreated` type `LOW_DRUG_STOCK` |
| Audit trail | Full log |

### Failures
| Code | Worker Experience |
|------|-------------------|
| `INSUFFICIENT_STOCK` | "Not enough Oxytetracycline in stock. Contact owner." |
| `ANIMAL_NOT_FOUND` | Error with animal tag |
| Others | Standard Kiosk error |

---

## Appendix A — Event Catalogue (v0.1)

Events introduced by the five Phase 1 commands:

| Event | Emitted By Command |
|-------|-------------------|
| `AnimalRegistered` | `RegisterAnimal` |
| `AnimalPurchased` | `RegisterAnimal` |
| `AnimalGroupChanged` | `RegisterAnimal` |
| `MilkingRecorded` | `RecordMilking` |
| `FlaggedRecordCreated` | `RecordMilking`, `RecordFeedGroupAllocation` |
| `FeedGroupAllocationRecorded` | `RecordFeedGroupAllocation` |
| `FeedBatchDepleted` | `RecordFeedGroupAllocation` |
| `ObservationRecorded` | `RecordObservation` |
| `TreatmentRecorded` | `RecordTreatment` |
| `InventoryConsumed` | `RecordTreatment` |
| `WithdrawalPeriodStarted` | `RecordTreatment` |
| `NotificationCreated` | `RecordObservation`, `RecordTreatment`, `RecordFeedGroupAllocation` |

Events to be specified in subsequent versions: `CalvingRecorded`, `AnimalRegistered` (via calving), `BreedingRecorded`, `PregnancyConfirmed`, `DryOffRecorded`, `AnimalSold`, `AnimalDied`, `CorrectionRecorded`, `VaccinationRecorded`, `FeedAnimalAllocationRecorded`, `TaskCompleted`, `MilkSaleRecorded`, `ExpenseRecorded`.

---

## Appendix B — Standard Failure Response

All commands return errors in this format:

```json
{
  "success": false,
  "error_code": "VOLUME_IMPLAUSIBLE",
  "message": "Volume exceeds maximum plausible yield for a single session.",
  "field": "volume_litres",
  "details": {}
}
```

HTTP status codes:
- `422` — validation failure
- `401` — unauthenticated
- `403` — wrong role for command
- `409` — conflict (duplicate, insufficient stock)
- `500` — server error; Kiosk queues command if offline (BR-014)

---

*End of DFMS-Domain-Events.md v0.1*
