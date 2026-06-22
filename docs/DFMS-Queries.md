# DFMS-Queries.md
**Dairy Farm Management System — Query Specification**
Version: 0.1 | Status: DRAFT | Author: Mash | Date: 2026-06-21

---

## Purpose

This document defines every read query DFMS must answer. Queries drive the Owner Dashboard, Kiosk projections, background jobs, and API read endpoints. Each query is specified precisely enough that five independent developers produce identical results.

**Dependencies:** DFMS-Glossary.md, DFMS-Business-Rules.md, DFMS-Domain-Events.md, DFMS-Roles-and-Clients.md.

**Conventions:**
- All queries are scoped to `farm_id` from authenticated token (BR-026)
- Dates use Farm `timezone` unless stated otherwise
- `today` = current calendar date in Farm timezone
- `yesterday` = `today - 1 day`
- Volumes in litres, one decimal place
- Money in KES, two decimal places

**Query ID format:** `Q-NNN`

**Implementation Phase:** Phase when query must be operational (see DFMS-Implementation-Phases.md).

---

## 1. Query Response Envelope

All dashboard API read endpoints return:

```json
{
  "query_id": "Q-001",
  "farm_id": "uuid",
  "as_of": "2026-06-21T06:00:00+03:00",
  "data": { }
}
```

List queries include `count` and `items[]`. Aggregate queries include computed scalars.

---

## 2. Morning Intelligence (Composite)

### Q-001 — Morning Intelligence View

**Purpose:** Single query powering the Owner's first screen. Answers: "What do I need to act on today?"

**Cadence:** On demand (Owner login); cached 5 minutes

**Phase:** 1 (partial) → 8 (complete)

**Inputs:**

| Parameter | Type | Default |
|-----------|------|---------|
| `reference_date` | date | `today` |

**Composition:** Aggregates results from Q-002, Q-003, Q-004, Q-005, Q-010, Q-011, Q-012, Q-020, Q-021, Q-030, Q-040, Q-041. Does not reimplement their logic — calls sub-queries.

**Output:**

```json
{
  "critical_alerts": [],
  "attention_required": [],
  "todays_schedule": [],
  "production_summary": { }
}
```

**UI:** Owner Dashboard §4.1 — full viewport on login.

---

## 3. Alert & Attention Queries

### Q-002 — Critical Alerts

**Purpose:** Items requiring immediate action.

**Phase:** 1 → 8

**Algorithm:** Union of:
1. Q-010 where `priority = CRITICAL` and `resolved = false`
2. Q-011 where `withdrawal_end_date = today`
3. Q-012 where `due_date < now - 24h` and `completed_at IS NULL`
4. Phase 2+: Q-030 overdue pregnancy checks > 7 days

**Output item schema:**

```json
{
  "alert_type": "MISSED_MILKING",
  "priority": "CRITICAL",
  "entity_type": "ANIMAL",
  "entity_tag": "118",
  "message": "Cow 118: Midday milking missed — still not recorded",
  "action_hint": "Verify cow was milked or record now",
  "created_at": "2026-06-21T14:30:00+03:00"
}
```

**Sort:** `priority DESC`, `created_at ASC`

---

### Q-003 — Attention Required

**Purpose:** Items needing Owner review today, not immediately critical.

**Phase:** 1 → 8

**Algorithm:** Union of:
1. Q-010 where `priority = HIGH` and `resolved = false`
2. Q-020 — unreviewed observations
3. Q-021 — pending flagged records (last 24h)
4. Q-040 — feed types with days remaining < 14
5. Q-041 — open cows past 80 DIM (BR-008)

**Sort:** `priority DESC`, `created_at ASC`

---

### Q-010 — Active Notifications

**Purpose:** List notifications for a Farm.

**Phase:** 1

**Inputs:**

| Parameter | Type | Default |
|-----------|------|---------|
| `resolved` | boolean | `false` |
| `priority` | enum | all |
| `type` | enum | all |
| `since` | datetime | null |

**Data sources:** `notifications` projection ← `NotificationCreated` events

**Types:** `MISSED_MILKING`, `HEALTH_OBSERVATION`, `WITHDRAWAL_STARTED`, `WITHDRAWAL_ENDING`, `LOW_FEED_STOCK`, `LOW_DRUG_STOCK`, `OPEN_COW_OVERDUE`, `DRY_PERIOD_OUT_OF_RANGE`, `INCOMPLETE_MILKING_DAY` (deprecated — use MISSED_MILKING)

**Output item:**

```json
{
  "notification_id": "uuid",
  "type": "MISSED_MILKING",
  "priority": "HIGH",
  "entity_type": "ANIMAL",
  "entity_id": "uuid",
  "entity_tag": "118",
  "message": "Cow 118: Midday milking not recorded",
  "due_date": null,
  "resolved": false,
  "created_at": "2026-06-21T14:00:00+03:00"
}
```

---

### Q-020 — Unreviewed Health Observations

**Purpose:** Worker-reported issues awaiting Owner acknowledgement (BR-016).

**Phase:** 1

**Algorithm:**
```
SELECT FROM observations
WHERE farm_id = :farm_id
  AND reviewed_at IS NULL
ORDER BY
  CASE observation_type
    WHEN 'INJURY' THEN 1
    WHEN 'SWOLLEN_UDDER' THEN 1
    WHEN 'NOT_EATING' THEN 2
    ELSE 3
  END,
  recorded_at DESC
```

**Output item:**

```json
{
  "observation_id": "uuid",
  "animal_tag": "101",
  "observation_type": "LIMPING",
  "notes": null,
  "photo_url": "/attachments/uuid",
  "recorded_by_worker": "John (W-002)",
  "recorded_at": "2026-06-20T16:45:00+03:00"
}
```

---

### Q-021 — Pending Flagged Records

**Purpose:** Statistical anomalies and late entries awaiting Owner review.

**Phase:** 1

**Algorithm:**
```
SELECT FROM flagged_records
WHERE farm_id = :farm_id
  AND status = 'PENDING'
  AND created_at >= now() - interval '24 hours'
ORDER BY created_at DESC
```

**Output item:**

```json
{
  "flagged_record_id": "uuid",
  "reason": "VOLUME_ABOVE_2X_AVERAGE",
  "source_event_type": "MilkingRecorded",
  "animal_tag": "118",
  "worker_id": "W-002",
  "device_id": "KIOSK-01",
  "expected_range": "8.0 - 16.0",
  "actual_value": 25.0,
  "recorded_at": "2026-06-21T05:30:00+03:00"
}
```

**Reason codes:** `VOLUME_ABOVE_2X_AVERAGE` (BR-003), `OUTSIDE_MILKING_WINDOW` (BR-021), `FEED_ABOVE_3X_AVERAGE`

---

## 4. Milking & Production Queries

### Q-030 — Milk Production Today

**Purpose:** How much milk was produced today, by session.

**Cadence:** Real-time

**Phase:** 1

**Inputs:**

| Parameter | Type | Default |
|-----------|------|---------|
| `date` | date | `today` |

**Algorithm:**
```
FOR EACH session IN (MORNING, MIDDAY, EVENING):
  total_litres[session] = SUM(milking_records.volume_litres)
    WHERE milking_date = :date AND session = :session

  saleable_litres[session] = SUM(volume_litres)
    WHERE milking_date = :date AND session = :session AND saleable = true

  cows_recorded[session] = COUNT(DISTINCT animal_id)
    WHERE milking_date = :date AND session = :session

  cows_scheduled[session] = COUNT(animals)
    FROM milking_schedules
    WHERE schedule_date = :date AND sessions CONTAINS :session
```

**Output:**

```json
{
  "date": "2026-06-21",
  "sessions": {
    "MORNING": {
      "total_litres": 142.5,
      "saleable_litres": 138.0,
      "cows_recorded": 12,
      "cows_scheduled": 12,
      "complete": true
    },
    "MIDDAY": {
      "total_litres": 48.0,
      "saleable_litres": 48.0,
      "cows_recorded": 4,
      "cows_scheduled": 4,
      "complete": false
    },
    "EVENING": {
      "total_litres": 0,
      "saleable_litres": 0,
      "cows_recorded": 0,
      "cows_scheduled": 12,
      "complete": false
    }
  },
  "daily_total_litres": 190.5,
  "daily_saleable_litres": 186.0
}
```

**UI:** Production Summary (Q-001); Kiosk header optional.

---

### Q-031 — Milk Production Yesterday (Summary)

**Purpose:** Production summary for Morning Intelligence.

**Phase:** 1

**Algorithm:**
```
yesterday_total = Q-030(date = yesterday).daily_total_litres
yesterday_saleable = Q-030(date = yesterday).daily_saleable_litres
last_week_same_day = Q-030(date = yesterday - 7 days).daily_total_litres

percent_change = ((yesterday_total - last_week_same_day) / last_week_same_day) * 100
  IF last_week_same_day > 0 ELSE null

zero_milk_cows = Active Lactating Cows
  WHERE SUM(milking_records.volume_litres for yesterday) = 0 OR no records
```

**Output:**

```json
{
  "date": "2026-06-20",
  "total_litres": 185.0,
  "saleable_litres": 180.5,
  "vs_last_week_percent": -3.2,
  "active_lactating_count": 12,
  "zero_milk_cows": [
    { "animal_tag": "104", "name": null }
  ]
}
```

---

### Q-032 — Animals Scheduled For Session (Kiosk)

**Purpose:** Which cows the Worker should milk for the selected session.

**Phase:** 1

**Inputs:**

| Parameter | Type | Required |
|-----------|------|----------|
| `session` | enum | yes |
| `date` | date | `today` |

**Algorithm:**
```
SELECT animals
WHERE farm_id = :farm_id
  AND is_active = true
  AND is_lactating = true
  AND milking_schedules.schedule_date = :date
  AND :session IN milking_schedules.sessions

LEFT JOIN milking_records
  ON animal_id AND session = :session AND milking_date = :date

RETURN animal_tag, name, already_recorded (record IS NOT NULL),
       withdrawal_active, three_session (sessions count = 3),
       suggested_volume (avg same-session volume last 3 days)
```

**Output item:**

```json
{
  "animal_tag": "118",
  "name": null,
  "already_recorded": false,
  "withdrawal_active": false,
  "three_session_cow": true,
  "suggested_volume_litres": 17.5,
  "seven_day_average": 16.2
}
```

**UI:** Kiosk Record Milk — Step 2 animal tiles (BR-023, BR-027).

---

### Q-033 — Animals With Production Decline

**Purpose:** Which cows are becoming a problem — milk trend declining.

**Cadence:** Daily (nightly job + on-demand)

**Phase:** 8

**Algorithm:**
```
FOR EACH Active Lactating Cow WITH >= 14 days of milking records:
  daily_totals = SUM(volume_litres) GROUP BY milking_date
    ORDER BY milking_date DESC LIMIT 7

  IF len(daily_totals) >= 5:
    first_half_avg = AVG(daily_totals[0:3])   -- most recent 3 days
    second_half_avg = AVG(daily_totals[4:7])  -- prior 4 days

    decline_percent = ((second_half_avg - first_half_avg) / second_half_avg) * 100

    IF decline_percent >= 15:
      INCLUDE with flag PRODUCTION_DECLINE
```

**Output item:**

```json
{
  "animal_tag": "118",
  "seven_day_trend_litres": [22.0, 20.0, 18.0, 16.0, 15.5, 14.0, 13.5],
  "decline_percent": 18.2,
  "flag": "PRODUCTION_DECLINE",
  "message": "Cow 118: milk down 18% vs 7-day average"
}
```

**UI:** Q-001 Attention Required (Phase 8); dedicated Animal Performance view.

---

### Q-034 — Animal Milk History

**Purpose:** Per-cow milking history for timeline and charts.

**Phase:** 1

**Inputs:** `animal_tag`, `from_date`, `to_date`

**Algorithm:** Return all `MilkingRecorded` events in range, grouped by date and session.

**Output item per record:**

```json
{
  "milking_date": "2026-06-20",
  "session": "MORNING",
  "volume_litres": 12.5,
  "flagged": false,
  "outside_window": false,
  "saleable": true,
  "worker_id": "W-002"
}
```

---

## 5. Feed Queries

### Q-040 — Days Of Feed Remaining

**Purpose:** Feed runway — how many days until stockout per Feed Type.

**Phase:** 6 (basic in Phase 1 if manual batch entry exists)

**Algorithm (per Feed Type):**
```
current_stock = SUM(feed_batches.quantity_remaining)
  WHERE feed_type = :type

daily_consumption_7d = SUM(allocations.quantity)
  WHERE feed_type = :type
  AND allocation_date >= today - 7 days
  DIVIDED BY count of days with consumption > 0

days_remaining = current_stock / daily_consumption_7d
  IF daily_consumption_7d > 0 ELSE null

alert = days_remaining < 14
```

**Output item:**

```json
{
  "feed_type": "SILAGE",
  "current_stock_kg": 4800.0,
  "daily_consumption_7d_kg": 104.0,
  "days_remaining": 46.2,
  "alert": false
}
```

**UI:** Q-001 Attention Required when `alert = true`; Inventory view.

---

### Q-042 — Feed Efficiency By Group

**Purpose:** Feed cost per litre for a lactating group over a period.

**Phase:** 8

**Inputs:** `animal_group`, `from_date`, `to_date`

**Algorithm:**
```
feed_cost = SUM(group_allocations.quantity * batch.unit_cost)
  FOR animals in group during period
  PLUS SUM(animal_allocations.quantity * batch.unit_cost)
    FOR animals in group

milk_litres = SUM(milking_records.volume_litres)
  FOR animals in group during period

cost_per_litre = feed_cost / milk_litres IF milk_litres > 0
```

**Output:**

```json
{
  "animal_group": "LACTATING_COWS",
  "period": { "from": "2026-06-01", "to": "2026-06-20" },
  "feed_cost_kes": 42000.00,
  "milk_litres": 2200.0,
  "cost_per_litre_kes": 19.09
}
```

---

## 6. Health & Withdrawal Queries

### Q-011 — Active Withdrawal Periods

**Purpose:** Animals whose milk cannot be sold.

**Phase:** 1

**Algorithm:**
```
SELECT FROM withdrawal_periods
WHERE farm_id = :farm_id
  AND end_date >= today
ORDER BY end_date ASC
```

**Output item:**

```json
{
  "animal_tag": "103",
  "drug_name": "Oxytetracycline",
  "start_date": "2026-06-21",
  "end_date": "2026-06-28",
  "ends_today": false,
  "days_remaining": 7
}
```

**UI:** Critical Alerts when `ends_today = true`; Vet Visit summary; Milk Sale validation.

---

### Q-043 — Withdrawal Periods Expiring Soon

**Purpose:** Withdrawals ending in the next N days.

**Phase:** 1

**Inputs:** `within_days` default `7`

**Algorithm:** Q-011 where `end_date BETWEEN today AND today + within_days`

---

### Q-044 — Animal Health Summary (Kiosk Vet Visit)

**Purpose:** Read-only summary before treatment entry.

**Phase:** 1

**Inputs:** `animal_tag`

**Output:**

```json
{
  "animal_tag": "103",
  "breed": "Friesian × Jersey",
  "last_calving_date": "2026-03-12",
  "lactation_number": 2,
  "days_in_milk": 101,
  "recent_treatments": [
    {
      "date": "2026-05-20",
      "drug_name": "Oxytetracycline",
      "dose": "10 ml",
      "withdrawal_end_date": "2026-05-27",
      "clear": true
    }
  ],
  "withdrawal_active": false
}
```

---

## 7. Reproduction Queries (Phase 5+)

### Q-050 — Animals Due For AI

**Purpose:** Who should be bred in the next 7 days.

**Phase:** 5

**Algorithm:**
```
INCLUDE Active female Cows WHERE:
  NOT in_calf
  AND (
    IN_HEAT observation in last 18 hours
    OR (open AND days_in_milk > 60 AND no breeding in last 21 days)
  )
```

**Output item:**

```json
{
  "animal_tag": "102",
  "reason": "HEAT_OBSERVED",
  "heat_observed_at": "2026-06-21T05:00:00+03:00",
  "days_in_milk": 95
}
```

---

### Q-051 — Expected Calvings

**Purpose:** Animals due to calve within N days.

**Phase:** 5

**Inputs:** `within_days` default `14`

**Algorithm:**
```
SELECT FROM pregnancies
WHERE status = OPEN
  AND ecd BETWEEN today AND today + within_days
ORDER BY ecd ASC
```

**Output item:**

```json
{
  "animal_tag": "089",
  "ecd": "2026-07-05",
  "days_until": 14,
  "lactation_number": 3
}
```

---

### Q-041 — Open Cows Past Breeding Threshold

**Purpose:** Cows overdue for breeding (BR-008).

**Phase:** 5 (alert logic); shown in Q-001 from Phase 5

**Algorithm:**
```
Active Lactating Cows
WHERE NOT in_calf
  AND days_in_milk > 80
  AND no PregnancyConfirmed since last CalvingRecorded
```

**Output item:**

```json
{
  "animal_tag": "117",
  "days_in_milk": 92,
  "last_breeding_date": null,
  "message": "Cow 117: 92 days in milk, not confirmed pregnant"
}
```

---

### Q-052 — Reproduction Pipeline Summary

**Purpose:** Open cows count, due for AI, expected calvings — single snapshot.

**Phase:** 5

**Output:**

```json
{
  "open_cows_count": 4,
  "due_for_ai": 2,
  "expected_calving_7d": 1,
  "in_calf_count": 8
}
```

---

## 8. Task & Labour Queries

### Q-012 — Overdue Tasks

**Purpose:** Work not completed on time.

**Phase:** 1 (manual tasks) → 6 (system-generated)

**Algorithm:**
```
SELECT FROM tasks
WHERE farm_id = :farm_id
  AND completed_at IS NULL
  AND due_date < now() - interval '24 hours'
ORDER BY due_date ASC
```

**Output item:**

```json
{
  "task_id": "uuid",
  "title": "Vaccinate calves",
  "assigned_worker_id": "W-002",
  "due_date": "2026-06-19",
  "overdue_hours": 36
}
```

---

### Q-060 — Worker Tasks Today (Kiosk)

**Purpose:** Worker's task list on Kiosk.

**Phase:** 1

**Inputs:** `worker_id`, `date` default `today`

**Algorithm:**
```
SELECT FROM tasks
WHERE (assigned_worker_id = :worker_id OR assigned_worker_id IS NULL)
  AND due_date <= :date
  AND (completed_at IS NULL OR completed_at::date = :date)
ORDER BY completed_at NULLS FIRST, due_date ASC
```

**Output item:**

```json
{
  "task_id": "uuid",
  "title": "Feed Group: Lactating Cows — Silage",
  "completed": false,
  "due_by": "07:30",
  "overdue": true
}
```

---

### Q-061 — Worker Activity Log

**Purpose:** What did workers actually do? (Owner audit view)

**Phase:** 1

**Inputs:** `worker_id`, `date`

**Algorithm:** Union of all domain events where `worker_id` matches, for the given date. Include event type, animal_tag (if applicable), summary, timestamp, attachment count.

**Output item:**

```json
{
  "worker_id": "W-002",
  "worker_name": "John",
  "date": "2026-06-20",
  "activities": [
    { "type": "MilkingRecorded", "count": 24, "summary": "12 cows, morning & evening" },
    { "type": "FeedGroupAllocationRecorded", "count": 2 },
    { "type": "ObservationRecorded", "count": 1, "attachments": 1 }
  ]
}
```

---

## 9. Financial Queries (Phase 7–8)

### Q-070 — Farm Profitability Summary

**Purpose:** Revenue, expenses, net margin for a period.

**Phase:** 7

**Inputs:** `from_date`, `to_date`

**Algorithm:**
```
revenue = SUM(milk_sales.total_amount) + SUM(income.amount WHERE category != MILK_SALE)
expenses = SUM(expenses.amount) GROUP BY category
net = revenue - SUM(expenses)
```

**Output:**

```json
{
  "period": { "from": "2026-06-01", "to": "2026-06-30" },
  "revenue_kes": 210000.00,
  "expenses_kes": {
    "FEED": 88000.00,
    "HEALTH": 9000.00,
    "LABOUR": 35000.00,
    "OTHER": 2000.00
  },
  "net_kes": 78000.00
}
```

---

### Q-071 — Cost Per Litre

**Purpose:** Farm-wide cost efficiency for a period.

**Phase:** 8

**Algorithm:**
```
total_costs = SUM(expenses.amount) for period
litres_sold = SUM(milk_sales.litres) for period

cost_per_litre = total_costs / litres_sold
```

**Comparison:** Also return `previous_period_cost_per_litre` for same-length prior period.

**Output:**

```json
{
  "period": "2026-06",
  "cost_per_litre_kes": 19.45,
  "previous_period_cost_per_litre_kes": 20.10,
  "change_percent": -3.2,
  "feed_cost_percent_of_revenue": 41.9
}
```

---

### Q-072 — Animal ROI

**Purpose:** Which cow makes money? Lifetime or period margin per animal.

**Phase:** 8

**Inputs:** `from_date`, `to_date`

**Algorithm (per Active or historical Cow):**
```
revenue = allocated milk sales + animal sales
costs = allocated feed + health + purchase amortization (if configured)

margin = revenue - costs
```

**Output item:**

```json
{
  "animal_tag": "101",
  "revenue_kes": 26000.00,
  "costs_kes": 9500.00,
  "margin_kes": 16500.00,
  "rank": 1
}
```

**Sort:** `margin_kes DESC`

---

### Q-073 — Saleable Milk Available

**Purpose:** How many litres can be included in a Milk Sale today.

**Phase:** 4

**Algorithm:**
```
saleable_pool = SUM(milking_records.volume_litres)
  WHERE saleable = true
  AND NOT YET allocated to a milk_sale

MINUS active withdrawal attribution
```

**UI:** Record Milk Sale form — max litres hint.

---

## 10. Inventory Queries

### Q-080 — Inventory Below Threshold

**Purpose:** What will run out soon? (drugs, consumables, feed)

**Phase:** 6

**Algorithm:**
```
FOR EACH inventory_item AND feed_type:
  IF quantity < reorder_threshold → INCLUDE
  IF days_remaining < 14 (feed) → INCLUDE

  FOR drugs with dosing history:
    days_remaining = quantity / avg_daily_doses_7d
```

**Output item:**

```json
{
  "item_type": "DRUG",
  "name": "Alamycin",
  "quantity_remaining": 4,
  "unit": "DOSES",
  "days_remaining": null,
  "alert_message": "4 doses remaining"
}
```

---

## 11. Animal & Group Queries

### Q-090 — Animal Timeline

**Purpose:** Full chronological event history for one animal.

**Phase:** 2

**Inputs:** `animal_tag`

**Algorithm:** All domain events for `animal_id` ordered by `recorded_at ASC`.

**Output item:**

```json
{
  "event_type": "MilkingRecorded",
  "recorded_at": "2026-06-21T05:30:00+03:00",
  "summary": "Morning milk: 12.5L",
  "actor": "John (W-002)"
}
```

---

### Q-091 — Animal Group On Date

**Purpose:** Which group was an animal in on a specific date? (BR-006)

**Phase:** 2

**Inputs:** `animal_tag`, `date`

**Algorithm:**
```
SELECT group FROM animal_group_memberships
WHERE animal_id = :id
  AND start_date <= :date
  AND (end_date IS NULL OR end_date >= :date)
```

---

### Q-092 — Active Animals List

**Purpose:** Filtered animal registry for Owner and Kiosk.

**Phase:** 2

**Inputs:** `group`, `status_filter` (lactating, dry, heifer, calf), `active_only` default `true`

---

## 12. Query ↔ UI Mapping

| UI Surface | Queries |
|------------|---------|
| Morning Intelligence (Q-001) | Q-002, Q-003, Q-031, Q-052 (Ph5) |
| Flagged Records Review | Q-021 |
| Unreviewed Observations | Q-020 |
| Kiosk — Record Milk | Q-032 |
| Kiosk — My Tasks | Q-060 |
| Kiosk — Vet Visit summary | Q-044 |
| Financial View | Q-070, Q-071 |
| Animal Performance | Q-033, Q-072, Q-034 |
| Inventory View | Q-040, Q-080 |
| Record Milk Sale | Q-073, Q-011 |

---

## 13. Query ↔ Implementation Phase

| Phase | Queries required |
|-------|------------------|
| 1 | Q-001 (partial), Q-002, Q-003, Q-010, Q-020, Q-021, Q-030, Q-031, Q-032, Q-034, Q-011, Q-012, Q-060, Q-044 |
| 2 | Q-090, Q-091, Q-092 |
| 4 | Q-073 |
| 5 | Q-041, Q-050, Q-051, Q-052 |
| 6 | Q-040, Q-080 |
| 7 | Q-070 |
| 8 | Q-001 (complete), Q-033, Q-042, Q-071, Q-072 |

---

## 14. Original Decision Queries — Mapping

The ten operational questions from project design map to:

| Question | Query ID(s) |
|----------|-------------|
| What requires attention today? | **Q-001** |
| Which cows are becoming a problem? | **Q-033** |
| Reproduction pipeline | **Q-052** |
| Days of feed remaining | **Q-040** |
| Feed efficiency | **Q-042** |
| Profitability this month | **Q-070** |
| Which cow makes money? | **Q-072** |
| What will run out soon? | **Q-080** |
| Outstanding work | **Q-012**, **Q-060** |
| What did workers do? | **Q-061** |

---

## 15. Query Index

| ID | Name | Phase |
|----|------|-------|
| Q-001 | Morning Intelligence View | 1/8 |
| Q-002 | Critical Alerts | 1 |
| Q-003 | Attention Required | 1 |
| Q-010 | Active Notifications | 1 |
| Q-011 | Active Withdrawal Periods | 1 |
| Q-012 | Overdue Tasks | 1 |
| Q-020 | Unreviewed Observations | 1 |
| Q-021 | Pending Flagged Records | 1 |
| Q-030 | Milk Production Today | 1 |
| Q-031 | Milk Production Yesterday | 1 |
| Q-032 | Animals Scheduled For Session | 1 |
| Q-033 | Production Decline Detection | 8 |
| Q-034 | Animal Milk History | 1 |
| Q-040 | Days Of Feed Remaining | 6 |
| Q-041 | Open Cows Past Breeding Threshold | 5 |
| Q-042 | Feed Efficiency By Group | 8 |
| Q-043 | Withdrawal Periods Expiring Soon | 1 |
| Q-044 | Animal Health Summary | 1 |
| Q-050 | Animals Due For AI | 5 |
| Q-051 | Expected Calvings | 5 |
| Q-052 | Reproduction Pipeline Summary | 5 |
| Q-060 | Worker Tasks Today | 1 |
| Q-061 | Worker Activity Log | 1 |
| Q-070 | Farm Profitability Summary | 7 |
| Q-071 | Cost Per Litre | 8 |
| Q-072 | Animal ROI | 8 |
| Q-073 | Saleable Milk Available | 4 |
| Q-080 | Inventory Below Threshold | 6 |
| Q-090 | Animal Timeline | 2 |
| Q-091 | Animal Group On Date | 2 |
| Q-092 | Active Animals List | 2 |

---

*End of DFMS-Queries.md v0.1*
