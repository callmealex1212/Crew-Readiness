# Reliability (task R2): measured, not claimed

Numbers live in `app/reliability_data.json` and are rendered on `/evidence#reliability`; this page only says how they were made.
Regenerate with one command (about 15 to 20 minutes on a laptop-class machine): `python -m ml.export_reliability`. Never ship a
`--quick` file; `tests/test_reliability.py` refuses it.

| Part | What it does | Code |
|---|---|---|
| Fault injection | 1000 malformed or hostile requests (half to `POST /api/sessions`, half to `POST /api/attention`): wrong types, NaN, infinity, huge and negative numbers, missing, extra and nested fields, non-object bodies, broken JSON, huge strings, typed text in number fields. A crash is an HTTP 500 or an exception escaping the app. Then 5000 more with other random seeds, so one lucky seed cannot hide a bug | `scripts/soak.py` `fuzz` |
| Long mission | 6 simulated people (`ml/synth.py`), 700 days, 3 sessions a day: each session stored and scored exactly as `POST /api/sessions` does. Scoring time per call (median, p95, max, first and last 100), database size, peak process memory | `soak` |
| Clock jump | One person's 40 sessions stored with times moving forward, and again with times jumping 30 days backwards from session 26: crashes, and whether the answers match | `clock_jump` |

## What fault injection found (and what was done)
- **Fixed in `app/features.py`** (tested in `tests/test_reliability.py`): NaN or infinity in a count crashed the validator (`int(nan)`,
  `int(inf)`); a list or object as `task_type` raised `TypeError`; a lone Unicode surrogate in `profile_id` reached SQLite and raised
  `UnicodeEncodeError`. Each now gets a 400 with a reason.
- **Open, reported:** `POST /api/attention` (validated in `app/api.py`, outside this task's files) still passes a lone surrogate
  `profile_id` to SQLite. A strict expected-failure test marks it; fixing `app/api.py` makes that test pass, and it must then be un-marked.

## What it does not show
Flight hardware, radiation, a failing disk or full storage, many users at once, or real crew data. Timings depend on the machine,
which the file records.
