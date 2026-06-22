# DFMS-Roles-and-Clients.md
**Dairy Farm Management System — Roles, Clients & Workflows**
Version: 0.3 | Status: DRAFT | Author: Mash | Date: 2026-06-21

---

## Purpose

This document specifies the human roles in DFMS, the client applications each role uses, and the exact workflows each role follows for every operational task. This document must be consistent with DFMS-Glossary.md. Any term used here that is not in the Glossary must be added to the Glossary first.

**Test:** If five developers read this document, they should produce Kiosk UIs and Owner Dashboards that look and behave nearly identically — without any further conversation.

**Business Rules:** All rules referenced here use the global `BR-NNN` registry defined in DFMS-Glossary.md Appendix D.

---

## 1. Roles Summary

| Role | v1 Account | Primary Client | Access Level |
|------|-----------|----------------|--------------|
| Farm Owner | Yes — full admin | Owner Dashboard (web) | Full |
| Worker | Yes — Worker ID + PIN | Kiosk (desktop browser) | Operational entry only |
| Veterinarian | No permanent account | Kiosk — Vet Visit mode (supervised) | Single-visit entry only |

**Not in v1 implementation (specified in domain, built later):**
- Manager role
- Vet permanent account
- Multi-farm owner aggregated dashboard

---

## 2. Client Applications

### 2.1 Kiosk Client

**What it is:** A React web application running in fullscreen/kiosk-mode browser on a dedicated farm desktop computer. The primary and authoritative data entry point for all Worker operations.

**Where it runs:** On the Farm LAN, connected to the Farm Server. Does not require internet access. The Kiosk must function fully when internet is down (BR-007).

**Who uses it:** Workers (primary). Vets (in supervised Vet Visit mode). Owner may access Owner Dashboard via separate login on another device; the Kiosk Worker UI and Owner Dashboard are separate applications.

**Design principles:**
- Large tap/click targets (minimum 60×60px for primary actions)
- Minimal taps — any standard entry completable in under 10 seconds
- No typing required for standard entries — only numeric input (volumes, doses) and optional text (observation notes)
- All selectable items presented as tiles, not dropdowns
- English v1; Swahili toggle planned for implementation Phase 2+
- Low literacy assumption: use icons alongside all text labels
- Bold colour contrast (WCAG AA minimum)

**Hardware assumption:** Desktop computer with standard monitor (minimum 1024×768). Mouse or touch screen both supported. No barcode scanner or RFID reader in v1 — Animal Tag selected by tapping from a pre-loaded list.

**v1 deployment:** One Kiosk (`device_id: KIOSK-01`) in the milking parlour.

### 2.2 Owner Dashboard

**What it is:** A web application accessible via browser, both on the Farm LAN and remotely via cloud (when internet is available).

**Who uses it:** Farm Owner only.

**Design principles:**
- Data-dense — owner is comfortable with information
- Mobile-responsive (owner checks on phone from field or home)
- Analytics-first: trends, flags, alerts, reports
- No simplified UI — owner needs full detail

### 2.3 Mobile App (Future)

**Not in implementation Phase 1.** The API is designed from day one to support mobile clients. When built, the mobile app serves as an alternative Worker entry point for field scenarios and an Owner portal.

**Architecture constraint:** All Kiosk commands use the same API endpoints the future mobile app will use. There are no Kiosk-specific API routes.

---

## 3. Worker Role — Kiosk Workflows

### 3.1 Authentication

**Flow:**
1. Kiosk displays idle screen: "Enter Worker ID"
2. Worker taps their 3–4 digit Worker ID on a numeric keypad (large buttons)
3. Worker enters 4-digit PIN
4. On success: Kiosk shows Worker home screen with worker's name displayed
5. On failure (3 attempts): Kiosk locks for 5 minutes, displays "Contact supervisor"

**Session management (BR-013):**
- Auto-logout after 15 minutes of inactivity
- Manual logout button always visible on home screen
- All commands during session are tagged: `worker_id`, `device_id`, `recorded_at`
- On auto-logout: return to idle screen; next Worker must re-authenticate

**PIN reset (BR-018):** Owner only, via Owner Dashboard Worker Management.

**Worker home screen — 5 actions only:**

```
┌─────────────────────────────────────────────────────┐
│  DFMS                        John (W-002)  [Logout] │
├─────────────────────────────────────────────────────┤
│                                                     │
│   ┌───────────────┐    ┌───────────────┐            │
│   │  🥛           │    │  🌾           │            │
│   │  Record Milk  │    │  Record Feed  │            │
│   └───────────────┘    └───────────────┘            │
│                                                     │
│   ┌───────────────┐    ┌───────────────┐            │
│   │  🩺           │    │  📋           │            │
│   │  Report Issue │    │  My Tasks     │            │
│   └───────────────┘    └───────────────┘            │
│                                                     │
│   ┌───────────────┐                                 │
│   │  👨‍⚕️          │                                 │
│   │  Vet Visit    │                                 │
│   └───────────────┘                                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

No other options. No navigation. No reports. No financial data (BR-012).

---

### 3.2 Record Milk

**Command issued:** `RecordMilking`

**Trigger:** Worker taps "Record Milk"

**Step 1 — Select session:**
```
Which milking?

┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  🌅 Morning  │   │  ☀️ Midday   │   │  🌙 Evening  │
│  05:00-09:00 │   │  11:00-14:00 │   │  16:00-20:00 │
└──────────────┘   └──────────────┘   └──────────────┘
```
System pre-selects session from current time and Milking Window (BR-021). If current time falls outside all windows → prompt "Which session are you recording?" (entry will be flagged if outside window).

Only Animals on a **3-session Milking Schedule** appear when Midday is selected (BR-023, BR-027). Cows on 2-session schedule are not shown for Midday — prevents invalid entries.

**Step 2 — Select Animal:**
Display Active Lactating Cows **scheduled for the selected session today** as large tiles. Tiles ordered by tag number. Already-recorded cows for this session show a green tick — worker can still tap to correct.

```
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│ 101  │ │ 102✓ │ │ 118³ │ │ 104  │
└──────┘ └──────┘ └──────┘ └──────┘
```
`³` = 3-session cow (optional badge). Cow 118 on 3× schedule; Cow 104 on 2× schedule — Cow 104 not shown if Midday selected.

Cows in active Withdrawal Period are shown normally — milking is not blocked (BR-005).

**Step 3 — Enter volume:**
```
Cow 101 — Morning Milk

    [  −  ]   [ 12.5 L ]   [  +  ]

  (Steps: 0.5 L)

          [ ✓ Save ]
```

Pre-filled with cow's previous same-session volume (last 3 days average for that session). Worker adjusts up/down.

**Validation (client-side, immediate):**
- Volume < 0: blocked, not allowed
- Volume = 0: confirmation prompt "Record zero milk for Cow 101?" (may indicate illness)
- Volume > 2× cow's 7-day average: prompt "Unusual volume — confirm?" — one tap confirms, record saved with `flagged: true` (BR-003)
- Volume > 60L: hard block (BR-009)
- Outside Milking Window: save with confirmation "Late entry — confirm?" → `outside_window: true` (BR-021)
- Wrong session for cow: prevented by tile filter (BR-027); API backstop if bypassed

**Backdating:** Milk entries may be backdated up to 24 hours (BR-019).

**After save:** Return to Animal selection. Next unrecorded cow is auto-highlighted. Worker continues until all scheduled cows for session are done, then taps "Done — Back to Home."

**Missed milking accountability (BR-022):** If Worker does not record a scheduled cow before window close, Owner receives HIGH alert; CRITICAL if still missing 30 minutes later. Late entry auto-resolves the alert.

**Target time:** Under 10 seconds per cow after session selection.

---

### 3.3 Record Feed

**Command issued:** `RecordFeedGroupAllocation` or `RecordFeedAnimalAllocation` (separate commands, same screen flow)

**Trigger:** Worker taps "Record Feed"

**Step 1 — Select feed type:**
```
What are you feeding?

┌─────────┐  ┌─────────┐  ┌─────────┐
│ Silage  │  │   Hay   │  │  Water  │
└─────────┘  └─────────┘  └─────────┘
┌─────────┐  ┌─────────┐
│  Dairy  │  │ Mineral │
│  Meal   │  │  Supp.  │
└─────────┘  └─────────┘
```

**Step 2 — Select recipient:**

- If Silage, Hay, or Water selected → Show Animal Groups (tiles): `Lactating Cows`, `Dry Cows`, `Heifers`, `Calves`
  → Issues `RecordFeedGroupAllocation`

- If Dairy Meal or Mineral Supplement selected → Show individual Animal tiles (Lactating Cows only for dairy meal)
  → Issues `RecordFeedAnimalAllocation`

**Step 3 — Enter amount:**
```
Silage → Lactating Cows

Morning Feed

    [  −  ]   [ 120 kg ]   [  +  ]

  (Steps: 5 kg for silage/hay, 0.1 kg for dairy meal)

          [ ✓ Save ]
```

Pre-filled with group's/animal's previous same-session amount.

**Validation:**
- Amount = 0: blocked
- Amount > 3× group's 7-day average: prompt "Unusual amount — confirm?" → Flagged Record

**Backdating:** Feed entries may be backdated up to 24 hours (BR-019).

**After save:** Return to home screen or prompt "Record another feed?"

---

### 3.4 Report Issue (Health Observation)

**Command issued:** `RecordObservation`

**Trigger:** Worker taps "Report Issue"

**Step 1 — Select Animal:**
All Active Animals as tiles (not just lactating). Includes calves and heifers.

**Step 2 — Select issue type:**
```
What did you notice?

┌────────────┐  ┌────────────┐  ┌────────────┐
│ Not Eating │  │  Limping   │  │  Low Milk  │
└────────────┘  └────────────┘  └────────────┘
┌────────────┐  ┌────────────┐  ┌────────────┐
│  In Heat   │  │   Injury   │  │  Swollen   │
│            │  │            │  │   Udder    │
└────────────┘  └────────────┘  └────────────┘
┌────────────┐
│   Other    │
└────────────┘
```

**Step 3 (optional) — Add photo:**
```
Add a photo? (optional)

[ 📷 Take Photo ]        [ Skip ]
```
Photo stored on Farm Server (BR-017). Cloud sync is async.

**Step 4 (optional, Other only) — Add note:**
If "Other" selected, a simple text field appears for a brief description.

**After save:**
```
✓ Issue reported for Cow 101
  Owner will be notified.

[ Report Another ]   [ Home ]
```

System creates a **Notification** on the Owner Dashboard (BR-016). This is **not** a Flagged Record. Unreviewed observations appear in Morning Intelligence under "Attention Required."

---

### 3.5 My Tasks

**Command issued:** `CompleteTask`

**Trigger:** Worker taps "My Tasks"

**Display:**
```
Today's Tasks

□  Feed Group: Lactating Cows — Silage
□  Check water troughs — Paddock A
✓  Evening feeding — Done (18:10, John)
```

Overdue tasks shown in red. Worker taps task → confirmation "Mark as done?" → task closed with timestamp and Worker ID.

**Note:** Task list is read-only from the Worker's view — Workers cannot create or delete tasks. That is Owner-only.

**Milking is not a Task.** Milking is recorded via the "Record Milk" action. Tasks cover ancillary work (feeding checks, cleaning, vaccinations scheduled by Owner).

---

### 3.6 Vet Visit Mode

**Commands issued:** `RecordTreatment`, `RecordVaccination`

**Trigger:** Worker taps "Vet Visit"

**Purpose:** Structured entry for veterinary treatments. Worker initiates; Vet may take over the screen briefly to complete the medical fields.

**Step 1 — Select Animal:**
All Active Animals as tiles.

**Step 2 — Show Animal Summary (read-only):**
```
Cow 103 — Friesian × Jersey

Last calving:    12 March 2026
Lactation:       #2, Day 101
Recent treatments:
  — 20 May: Oxytetracycline, 10ml
    Withdrawal ended: 27 May ✓ CLEAR
Current status:  No active withdrawal
```

Worker can hand device to Vet here.

**Step 3 — Record Treatment:**
```
Treatment Type

[ Illness/Injury ]     [ Vaccination ]

Drug:
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Oxytetracy-  │  │  Penicillin  │ │   Multivit   │
│  cline       │  │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
[ Other — type name ]

Dose:     [  −  ] [ 10 ml ] [  +  ]  (steps: 0.5ml)

Route:    [ Injection ]  [ Oral ]  [ Topical ]

Withdrawal (days):  [ 3 ]  [ 5 ]  [ 7 ]  [ 10 ]  [ Custom ]

Diagnosis / Notes (optional):
┌──────────────────────────────┐
│                              │
└──────────────────────────────┘

Vet Name (optional):
┌──────────────────────────────┐
│  Dr.                         │
└──────────────────────────────┘

[ ✓ Save Treatment ]
```

**Validation (BR-011):**
- Drug must be selected (not skipped)
- Dose must be > 0
- Withdrawal days must be selected
- If drug has inventory record: depletes stock by dose amount

**Backdating:** Treatment entries may be backdated up to 48 hours (BR-019).

**After save:**
```
✓ Treatment recorded — Cow 103
  Withdrawal ends: 28 June 2026
  Milk from Cow 103 must NOT be sold until 28 June.

[ Treat Another Animal ]   [ Home ]
```

System emits `TreatmentRecorded` and creates a Withdrawal Period projection. Milk recording continues on Kiosk (BR-005). Milk Sale for this Animal's milk is blocked on Owner Dashboard until withdrawal ends.

**Fallback (paper-first):** If Vet prefers paper, Worker or Owner enters treatment from paper record using this same screen.

---

## 4. Farm Owner Role — Dashboard Workflows

The Owner Dashboard is a web application. Query definitions: **DFMS-Queries.md**. Owner workflows for breeding, calving, and dry-off are specified in DFMS-Domain-Events.md as commands become defined.

### 4.1 Morning Intelligence View

The first thing the Owner sees on login. Answers: "What do I need to act on today?"

**Critical Alerts (red):**
- Missed milking notifications at CRITICAL priority (BR-022)
- Animals with active Withdrawal Period ending today
- Tasks overdue by > 24 hours

**Attention Required (amber):**
- Missed milking notifications at HIGH priority (BR-022)
- Unreviewed Health Observations (Notifications from workers)
- Flagged Records from last 24 hours (unusual milk volumes, late entries outside window, unusual feed amounts)
- Days of Feed Remaining < 14 days for any Feed Type
- Open Cows past 80 days in milk without breeding (BR-008)

**Today's Schedule (blue):**
- Implementation Phase 2+: Animals due for AI, expected calvings, vaccination boosters

**Production Summary:**
- Yesterday's total milk (litres) — all recorded milk
- Yesterday's saleable milk (litres) — excluding withdrawal milk
- Yesterday vs same day last week (% change)
- Active lactating cows count
- Any cows with zero milk yesterday

### 4.2 Flagged Records Review

List of all Flagged Records pending owner review. For each:
- Which Worker recorded it, when, on which device
- The entered value vs expected range
- Action: [Approve as accurate] or [Correct entry]

Corrections emit `CorrectionRecorded` — the original event is preserved, never deleted.

### 4.3 Unreviewed Observations

Separate from Flagged Records. Lists Health Observations not yet acknowledged by Owner. Owner taps [Mark Reviewed] — does not imply the observation was wrong.

### 4.4 Animal Management

- Search/filter all Animals
- View individual Animal timeline (all events, chronological)
- **Register Animal** (`RegisterAnimal` command) — purchased animals; emits `AnimalRegistered` + `AnimalPurchased` (BR-015)
- Record Milk Sale (Owner only)
- Record animal sale (`RecordAnimalSale` → `AnimalSold`)
- Record animal death (`RecordAnimalDeath` → `AnimalDied`)
- Move Animal to Group (`MoveAnimalToGroup` → `AnimalGroupChanged`)
- Create manual tasks for Workers

Breeding, pregnancy check, calving, and dry-off commands: specified in DFMS-Domain-Events.md; built in implementation Phase 2.

### 4.5 Financial View

- Milk Sales history and revenue by period
- Expenses by category
- Cost per litre (calculated)
- Feed cost per litre (calculated)
- Implementation Phase 3+: per-animal ROI

### 4.6 Worker Management

- Add/remove Workers
- Set Worker PIN (BR-018)
- View Worker activity log
- Manage Kiosk devices (register Device ID)

---

## 5. Vet Role — Constraints Summary

| Constraint | Detail |
|-----------|--------|
| No permanent account in v1 | Vet does not log in |
| Entry method v1 | Vet Visit mode on Kiosk (Worker initiates, Vet may take screen) |
| Entry method fallback | Paper slip → Worker or Owner enters same day |
| Accountability | `vet_name` field (free text) + `recorded_by_worker_id` + timestamp |
| What Vet can record | Treatment, Vaccination, optional diagnosis note |
| What Vet cannot record | Milking, feeding, financial, worker management |
| Future | One-time token link for single-animal entry (no app required) |

---

## 6. Resolved Configuration Decisions (v0.2)

| Decision | Resolution |
|----------|------------|
| Kiosk device count at launch | One device: `KIOSK-01`, milking parlour |
| PIN reset | Owner only via Dashboard (BR-018) |
| Backdating limits | Treatments: 48h; milk/feed: 24h (BR-019) |
| Observation photo storage | Farm Server (MinIO on LAN); cloud sync async (BR-017) |
| Farm Server downtime | Kiosk local command queue; sync on reconnect (BR-014) |
| Product name in UI | DFMS |
| Observations vs Flagged Records | Separate — Notifications vs statistical flags (BR-016) |

---

*End of DFMS-Roles-and-Clients.md v0.2*
