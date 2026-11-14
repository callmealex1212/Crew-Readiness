# Next steps: two people, about 16 hours

Where we are: the product works and the story is honest (personal baseline, simulated evidence with its limits, a human decides).
What a judge can still see that looks unfinished: **three pages with TODO text**. Fix those first; everything else is polish.

Work on separate branches, small PRs, and run `pytest -q` and `node scripts/check_grid.js` before each one.
`AGENTS.md` has the ground rules for Codex.

## Block 1: close the visible gaps (first 4 hours)
| Who | Task | Done when |
|---|---|---|
| **Done** | **L-1: `mission_advisory()`** is implemented (by the assistant, as the Lead delegated). Rules and the three edge decisions are in `docs/PLAN.md` (D-5); **the Lead may overrule any of them**, and `tests/test_mission.py` changes with the decision. | The Mission page shows a real advisory instead of "TODO" |
| **Teammate** | **A-1: attention check** (`app/static/js/attention.js`, spec in `docs/TEAM_GUIDE.md`). A short reaction-time check, optional, results posted to `/api/attention`. | Page works end to end; no "Not implemented yet" |
| **Teammate** | **R-1: Privacy & limits page** (`app/templates/about.html`): retention and access (as a proposal), confounders (keyboard, language, time of day, sleep, practice), what we validated and did not (copy from `docs/SUBMISSION.md`). | No TODO box; every claim matches `docs/ML_RESULTS.md` |

## Block 2: make it solid (next 6 hours)
- **Teammate:** keyboard and focus pass on the new pages (Replay, Evidence, the Review panel), and a phone-width look at every page.
- **You:** fill the `[PLACEHOLDERS]` in `docs/SUBMISSION.md`; map our work to the exact challenge wording; check the NASA glove image page (task R-2 in `docs/ASSETS.md`).
- **Optional, only if there is time:** a small real pilot. 3 to 5 volunteers, pseudonyms only (`flask --app run add-profile`), about 6 short sessions each. Report it as "a small pilot, N people, not a validation". It makes the story more real, but do not rush it and do not claim more than it shows.

## Block 3: freeze and rehearse (last 5 hours)
- **No new features after T-5 h.** Only bug fixes.
- Read `docs/DEMO.md` aloud once, timed, with a stopwatch. Fix whatever is awkward.
- A captioned backup video can be regenerated with `node scripts/record_demo.js` (see `docs/DEMO.md`); add a voice-over if you want one.
- Run `python scripts/smoke.py <deployed URL>` the night before and again before submitting.
- Run the demo locally (`python run.py`); the hosted copy forgets its data.
- Final pass on claims: nothing about fatigue, illness, fitness for duty, or NASA approval. Submit with time to spare.

## If time runs short, cut in this order
Real pilot, then polish, then A-1 (hide the Attention link if it is not ready). Never cut: the TODO text on Mission and Privacy, the rehearsal, the submission.
