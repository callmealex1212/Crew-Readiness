# Crew Readiness

**NASA Space Apps 2026.** A privacy-conscious prototype that flags **changes in a crew member's task interaction timing**, compared with **their own** baseline, for **human review** before a critical operation.

> **AI assistance.** Built with AI coding assistants, used as tools. The team lead set the direction (compare each person only
> with themselves, a human decides, privacy first), made every product and claim decision, and ran the volunteer pilot with a
> teammate. Claude (by Anthropic, through Claude Code) wrote much of the code, tests and documentation and proposed some features
> the team lead approved; a second Claude Code session, run by teammate Alex, wrote the pilot tooling, the NASA data search and
> analysis, the self-test and the backup. No AI-generated image is in the product, and the running app calls no AI service.
> Full account: [`docs/AI_USE.md`](docs/AI_USE.md).

> **Positioning.** A prototype of on-board decision support for crews doing computer-based procedure work, **tested on simulated data and one very small volunteer check (see `docs/pilot/`)**. It has not been used by or tested with astronauts, and real conditions (tablets, gloves, shared devices, microgravity) are untested.

> ⚠️ **Prototype.** Fictional crew, synthetic demo data, illustrative thresholds. It detects changes in interaction timing; it does **not** detect fatigue, diagnose anything, or clear anyone for duty.

---

## The problem
Before high-stakes operations such as manual docking, mission teams want early, low-burden signals that someone may benefit from a check-in. Dedicated tests interrupt work and can't run continuously, and population "norms" ignore that every person types and works differently.

## Our approach
1. **Passive:** timing is captured during routine (simulated) checklist work; no extra test.
2. **Private by design:** the browser reduces keystrokes to **9 aggregate numbers**; text and key identities never leave the device, and the server rejects anything else.
3. **Personal:** each session is compared only with **the same person's** previous sessions (robust median/MAD baseline). No score until enough data exists (**CALIBRATING**).
4. **Explainable:** a GREEN / YELLOW / RED band with plain-language reasons and an evidence table, plus a **confidence** level based on data sufficiency.
5. **Human in the loop:** the mission view *suggests* a check-in or second verification. It never assigns or grounds anyone.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py                                       # → http://127.0.0.1:5050
python -m pytest                                    # tests
```

The first run creates `instance/crew_readiness.sqlite3` with four fictional crew members. Pages: `/` landing, `/dashboard`, `/monitor`, `/attention`, `/mission`, `/about`.
Reset any time: `flask --app run reset-demo`.

## Deploy (Vercel)
`index.py` is the Vercel entrypoint and `vercel.json` copies `app/static` into `public/` at build time.
Connect the repo to a Vercel project (framework preset: Flask) and it deploys on every push to `main`.

**Known limitation of the hosted build:** serverless functions can only write to `/tmp`, and that
SQLite file is private to one function instance and is lost when the instance is recycled. Every
instance re-seeds the same fictional crew, so the dashboard, mission and about pages look the same
everywhere, but a session submitted through the hosted *Monitoring* page is **not durable** and may not
appear on the next request. For the live-capture demo use `python run.py` locally. Making hosted data
durable needs an external database (decision D-8 in [docs/PLAN.md](docs/PLAN.md)).

## Demo walkthrough
1. **Mission:** docking at T-6h; the primary pilot shows YELLOW.
2. **Monitoring:** pick a crew member, read what is and isn't recorded, complete the checklist. Before submitting, the app shows the **exact JSON** that leaves the browser.
3. **Dashboard:** click a crew card → advisory, reasons, trend vs. own baseline, and evidence table.
4. **Attention check** *(in progress)*: short illustrative reaction-time task for added context.

## Architecture

```
Browser (capture.js)  ──9 aggregate numbers──▶  Flask API (strict allowlist)
                                                   │
                                SQLite (aggregates only) ◀── store.py
                                                   │
                     baseline.py (median + MAD of own past sessions)
                                                   │
                scoring.py (robust z → weighted score → band + reasons)
                                                   │
                         Dashboard · Mission view (human decides)
```

Python 3.10+ · Flask · SQLite · NumPy · vanilla JS · Chart.js and fonts vendored (works offline).
Visual design (Swiss grid, single typeface) and its rationale: [docs/DESIGN.md](docs/DESIGN.md). Add `?grid` to any URL to see the layout grid.
Full details: [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md).

## Data handling
- Stored per session: inter-key interval median and IQR, pause count and total, checklist response median, task duration, correction and retry counts, keystroke count.
- **Never stored or transmitted:** typed text, which keys were pressed, raw keystroke timelines, passwords.
- Capture runs only inside the task, with a visible "Monitoring active" indicator.
- The demo uses fictional profiles with synthetic data, labelled as such. Pseudonymous `team_test` profiles exist for future feasibility sessions; **none have been run yet** (`docs/TEST_LOG.md` is an empty template).

## Scoring (illustrative)
Per feature: `z = (today − personal median) / robust spread`; only the "slower / more pausing" direction counts; capped at 4.
**Pause count** is scored differently: a per-person count model (own average and own burstiness) gives how often a count this high
would be expected, converted to the same scale; total pause time is shown but not scored. Groups: typing 40 %, pauses 30 %,
checklist response 30 %. Bands: < 1.0 GREEN, < 2.0 YELLOW, ≥ 2.0 RED.
A session scored 1.5 or more is **kept out of the person's baseline** (so a sustained change is not learned as normal) until a human
accepts it as the new normal on the dashboard. Set `CREW_PAUSE_MODEL=robust` to run the original scoring for comparison.
**These are demo choices, not validated or NASA-approved limits.**

## Evidence (simulated only)
`/evidence` and `/replay` show how the scoring behaves on **simulated** crews, including where it is worse. Details, commands and
every limit: [docs/ML_RESULTS.md](docs/ML_RESULTS.md). Demo script: [docs/DEMO.md](docs/DEMO.md). Submission copy: [docs/SUBMISSION.md](docs/SUBMISSION.md).

## Limitations
- **No validation on real people.** Results come from simulated crews only (benchmark, `docs/ML_RESULTS.md`); this is **not** clinical or operational validation.
- We wrote both the simulator and the model, so the benchmark is partly circular; gains are modest and come with a detection trade-off (stated on the Evidence page).
- Timing is affected by keyboard, language, practice, task difficulty, time of day, sleep and more.
- An unusual session means unusual **behaviour**, not a cause.

## Sources and acknowledgements
- Images: Michelangelo, *The Creation of Adam* (public domain); spacesuit glove from NASA's 2012 *Man and Machine* photograph (credit NASA, no endorsement implied); the mark is drawn by the team in code (no AI-generated image is used). Sources, licences and open checks: [docs/ASSETS.md](docs/ASSETS.md).
- Design: Swiss / International Typographic style; the stacked-sessions chart form was inspired by Harold D. Craft Jr.'s 1970 pulsar plot (idea only). Instrument Sans, Instrument Serif and JetBrains Mono typefaces, SIL OFL 1.1.
- **NASA research:** we have **not** yet reviewed NASA's human-research literature and cite none; we claim no NASA findings (task R-2 is open).
Chart.js © Chart.js contributors, MIT License.

## Team
See [docs/PLAN.md](docs/PLAN.md) for roles, timeline and decisions, and [docs/TEAM_GUIDE.md](docs/TEAM_GUIDE.md) to start contributing.
