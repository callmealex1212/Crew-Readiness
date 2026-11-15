# Data Contract (v1)

> **This is the integration contract.** Frontend (Member 3), scoring (Member 2) and the mission view (Team Lead) all depend on it.
> **Changing anything here needs Team Lead approval** and the same PR must update `app/features.py`, `app/schema.sql`, and the tests.

Source of truth in code: [`app/features.py`](../app/features.py) · [`app/schema.sql`](../app/schema.sql) · [`app/scoring.py`](../app/scoring.py)

---

## 1. Privacy invariants (non-negotiable)

| # | Invariant | Enforced by |
|---|-----------|-------------|
| P1 | Typed text never leaves the browser | `capture.js` stores timestamps and counters only; input is compared client-side and cleared |
| P2 | Key identities are never stored or sent | `capture.js` classifies a key as char/correction/ignore and discards it |
| P3 | The server accepts **only** the listed features; unknown fields → HTTP 400 | `validate_session_payload` + `tests/test_features.py` |
| P4 | The database has no column that could hold text | `schema.sql` |
| P5 | Capture runs only during the task, with a visible indicator | `monitor.js` (`● Monitoring active`) |
| P6 | Demo data is fictional and labelled `synthetic` | `seed.py`, `profiles.kind`, `sessions.source` |

If you ever find yourself wanting to send something that is not in §3, stop and talk to the Team Lead.

---

## 2. Entities

### Profile
| Field | Type | Notes |
|---|---|---|
| `id` | string slug | e.g. `plt-okafor` |
| `display_name` | string | fictional (demo) or pseudonym (team_test), **never a real name** |
| `mission_role` | string | Commander, Pilot, Flight Engineer, Mission Specialist |
| `kind` | `demo` \| `team_test` | demo = fictional + synthetic data; team_test = teammate doing real validation sessions |

### Session (one completed monitored task)
| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `profile_id` | string | FK → profile |
| `task_type` | string | versioned, currently only `docking_checklist_v1` |
| `created_at` | ISO-8601 UTC | **set by server**, not client |
| `source` | `live` \| `synthetic` | |
| `data_quality` | `ok` \| `low` | `low` = stored and shown, but excluded from baselines and lowers confidence |
| `quality_notes` | string \| null | why it is `low` |
| *features* | see §3 | |

### Baseline (computed on demand, not stored)
| Field | Meaning |
|---|---|
| `n` | number of sessions it was built from |
| `ready` | `n >= 5` (`MIN_BASELINE_SESSIONS`) |
| `features[name].median` | personal typical value |
| `features[name].spread` | robust SD = 1.4826 × MAD |

Built from: the person's **earlier** sessions on the **same task_type**, `data_quality == ok`, most recent **20**.
A session is never part of its own baseline.

### Readiness view (computed)
| Field | Values |
|---|---|
| `status` | `SCORED` \| `CALIBRATING` \| `INSUFFICIENT_DATA` |
| `band` | `GREEN` \| `YELLOW` \| `RED` \| `null` (only when SCORED) |
| `score` | weighted deviation in robust-SD units, `null` unless SCORED |
| `confidence` | `NONE` \| `LOW` \| `MEDIUM` \| `HIGH` |
| `baseline_n`, `baseline_needed` | e.g. 2 / 5 → show "2/5 baseline sessions" |
| `group_scores` | `{typing, pauses, checklist}` |
| `deviations[]` | per feature: `value, baseline_median, spread_used, z, deviation, label, unit, group` (sorted, largest first) |
| `reasons[]` | plain-language strings, only for deviation ≥ 1.0 |
| `advisory` | one sentence for a human reviewer |
| `disclaimer` | always shown |
| `baseline_review` | `null`, or `{excluded_sessions, message}` when the latest unbroken run of sessions was scored >= 1.5 against the person's baseline and is therefore **not used to learn what is normal** (a reviewer can accept it) |
| `model` | which scoring model produced the view: `nb-pause-v2` (pause count by per-person negative binomial; pause time shown as context, not scored) or `robust-mad-v1`. See docs/ML_RESULTS.md |

### Attention result (stretch, task A-1)
`profile_id, session_id?, trials, median_rt_ms|null, premature_count, miss_count`

---

## 3. Session features (computed in the browser by `capture.js`)

Pause threshold: a gap **≥ 2000 ms** between two keys *inside one checklist item*.
Gaps *between* items are not typing; they are captured as response time.

| Feature | Type | Range | Definition |
|---|---|---|---|
| `keystroke_count` | int | 1–5000 | character + correction presses (not Shift/Enter/arrows; key-repeat ignored). Data quality only, not scored |
| `iki_median_ms` | float | 20–3000 | median inter-key interval, pauses excluded |
| `iki_iqr_ms` | float | 0–3000 | Q3 − Q1 of the same intervals (rhythm variability) |
| `pause_count` | int | 0–500 | number of within-item gaps ≥ 2000 ms |
| `pause_total_ms` | float | 0–3.6M | sum of those gaps |
| `checklist_response_median_ms` | float | 0–120000 | median over items of (item shown → first key) |
| `task_duration_ms` | float | 1000–3.6M | start → last item confirmed. Not scored (it double-counts the others) |
| `correction_count` | int | 0–2000 | Backspace/Delete presses. Not scored yet |
| `retry_count` | int | 0–500 | confirmations submitted that did not match. Not scored yet |

Data quality = `low` if `keystroke_count < 80` or `retry_count > 5`.

---

## 4. Scoring v1 (illustrative prototype logic)

```
for each scored feature f:
    spread  = max(baseline.spread_f, 0.05 × |baseline.median_f|, floor_f)
    z_f     = (value_f − baseline.median_f) / spread
    d_f     = clip(max(0, z_f), 0, 4)          # only "slower / more pausing" counts

typing    = mean(d_iki_median, d_iki_iqr)       weight 0.40
pauses    = mean(d_pause_count, d_pause_total)  weight 0.30
checklist = d_checklist_response                weight 0.30

score = 0.4·typing + 0.3·pauses + 0.3·checklist
band  = GREEN if score < 1.0, YELLOW if < 2.0, else RED
```

Floors: iki 10 ms, iqr 10 ms, pause_count 1, pause_total 1000 ms, checklist 150 ms.

Confidence: `n < 5 → NONE`, `5–9 → LOW`, `10–14 → MEDIUM`, `≥ 15 → HIGH`; `low` quality drops one level (min LOW).

**Every number above is a demo choice, not a validated or NASA-approved limit.** Member 2 owns this section and records any change in the decisions log in `docs/PLAN.md`.

---

## 5. HTTP API

All JSON. Errors: `{"error": "<code>", "message": "<human text>"}`.

| Method | Path | Body / notes | Success |
|---|---|---|---|
| GET | `/api/health` | | `200 {status, version, profiles}` |
| GET | `/api/profiles` | | `200 {profiles: [Profile]}` |
| GET | `/api/tasks/<task_type>` | checklist definition | `200 {task_type, title, intro, items[]}` |
| POST | `/api/sessions` | `{profile_id, task_type, features{…all 9…}}` | `201 {session_id, …ProfileReadiness}` · `400` contract violation · `404` unknown profile |
| GET | `/api/readiness` | latest readiness for every profile (no trend) | `200 {crew: [ProfileReadiness]}` |
| GET | `/api/readiness/<profile_id>` | includes `trend` (last 14 sessions, oldest first; see **Trend point** below) | `200 ProfileReadiness` |
| POST | `/api/attention` | `{profile_id, session_id?, trials, median_rt_ms, premature_count, miss_count}` | `201 {id}` |
| GET | `/api/mission` | scenario + assignments joined with readiness + `advisory` + `watchdog` | `200` |
| GET | `/api/selftest` | health of the monitor (task R1): database write/read/rollback, scoring on a fixed hand-worked fixture (1.2 YELLOW), clock sanity, no page loads from another host, app version. Reads nothing about any person; its test row is rolled back | `200 {ok, checked_at, version, checks: [{id, name, ok, detail}], does_not_show}` (always 200; `ok` carries the result) |

`/api/mission` also returns each assignment's `last_check_in` (ISO-8601 UTC of its latest submitted session, or `null`) and a `watchdog`
(plan v3, H2; docs/PLAN.md D-9), separate from `advisory` and never changing it:
```json
{"interval_hours": 36, "level": "OK" | "OVERDUE",
 "overdue": [{"role": "Comms and log", "display_name": "Tomas Ibarra", "hours_since": 74}],
 "clock_check": [{"role": "...", "display_name": "...", "reason": "future" | "unreadable"}],
 "messages": ["..."], "suggested_actions": ["..."]}
```
`hours_since` is `null` when the person has never checked in. A time in the future is a `clock_check`, never overdue.

`ProfileReadiness`:
```json
{
  "profile": {"id": "plt-okafor", "display_name": "Kai Okafor", "mission_role": "Pilot", "kind": "demo"},
  "task_type": "docking_checklist_v1",
  "latest_session": {"id": 15, "created_at": "…Z", "source": "synthetic", "data_quality": "ok", "quality_notes": null, "features": {…}},
  "readiness": {"status": "SCORED", "band": "YELLOW", "score": 1.22, "confidence": "MEDIUM", "…": "see §2"},
  "baseline": {"n": 14, "ready": true, "min_required": 5, "features": {"iki_median_ms": {"median": 188.1, "spread": 9.9}}},
  "trend": [{"session_id": 6, "created_at": "…Z", "source": "synthetic", "status": "SCORED", "band": "GREEN", "score": 0.7,
             "deviations": {"iki_median_ms": 0.4, "iki_iqr_ms": 0.0, "pause_count": 0.0, "pause_total_ms": 0.0, "checklist_response_median_ms": 1.1}}],
  "attention": null
}
```

**Trend point.** One entry per session, scored against only the sessions before it (same rule as the baseline).
`deviations` is the per-feature directional deviation that fed that session's score (0 = usual or faster, capped at 4,
same numbers as `readiness.deviations[].deviation`), or `null` while `status` is `CALIBRATING`. The dashboard's
stacked-sessions art draws exactly these numbers and nothing else (see `docs/DESIGN.md`).

---

### Backup file (task R3)
`flask --app run export-backup <file>` writes `{"sha256": <hex>, "payload": {"format": "crew-readiness-backup", "format_version": 1,
"tables": {"profiles": [...], "sessions": [...], "attention_results": [...]}}}`. The rows hold exactly the stored columns (`app/backup.py`
`SCHEMA`, checked against the live schema by a test); the checksum is SHA-256 of the canonical JSON of `payload`.
`flask --app run import-backup <file>` restores into an **empty** database only (`flask --app run reset-empty` first), all or nothing, and
refuses: a checksum mismatch; any unknown top-level field, table or column; a value of the wrong type or outside the feature contract;
NaN or infinity; free text in `quality_notes` other than the two notes the app writes. Not encrypted; the checksum catches damage, not forgery.

## 6. Versioning rules

* Changing checklist text, item count, or the pause threshold → **new task_type** (`docking_checklist_v2`). Old baselines must not mix with new sessions.
* Adding a feature → new column + `FEATURES` entry + range + tests + this file, in one PR.
* Changing scoring constants → allowed without a new version, but log it in `docs/PLAN.md` § Decisions and re-run `pytest` (the demo-protection tests will tell you if the pitch story broke).


## Baseline review (flagged sessions and accepting a new normal)

- A session scored >= `EXCLUDE_FROM_BASELINE` (1.5) does not join the person's baseline, so a sustained change is not absorbed
  and stops being flagged. Trend points carry `excluded_from_baseline` (bool). Evidence: `docs/ML_RESULTS.md`.
- `POST /api/readiness/<profile_id>/accept-new-normal` (no body): a human accepts the latest unbroken flagged run. Those sessions get
  `sessions.accepted_at` (UTC timestamp; no identity, the prototype has no accounts), count toward the baseline, and the baseline
  **restarts from the first accepted session** (fewer than 5 means CALIBRATING). 200 returns `accepted_session_ids` plus the readiness
  payload; 404 unknown profile; 409 nothing waiting for review.


## Responsiveness (plan v3, H1)
`GET /api/readiness/<id>` has `responsiveness`, and `POST /api/attention` returns `{id, responsiveness}`; `/api/mission` assignments carry it too.
```json
{"status": "SCORED" | "CALIBRATING" | "NO_RESPONSE" | "NONE", "level": "USUAL" | "SLOWER" | "MUCH_SLOWER" | null,
 "summary": "Your response time today (328 ms) is slower than your own usual (about 277 ms).", "reasons": ["..."],
 "baseline": {"n": 8, "median_rt_ms": 277.0, "spread_ms": 17.0}, "deviation": 3.1, "today": {"median_rt_ms": 328.0, "miss_count": 1, "trials": 10, "created_at": "...Z"}, "n_checks": 9}
```
Compared only with the same person's earlier checks (at least 5 valid ones, otherwise `CALIBRATING`). Cut-offs are illustrative and not validated; it never changes `readiness.band`.
