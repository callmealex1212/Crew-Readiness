# Submission copy (NASA Space Apps 2026)

Fill the remaining `[PLACEHOLDERS]` (team name, challenge title, AI tool name); everything else is drawn from the product and `docs/ML_RESULTS.md`. Numbers are checked against
`app/results_data.json` by `tests/test_submission.py`, so they cannot drift. Every result is on **simulated** data.

- Team: `[TEAM NAME]`
- Challenge: `[EXACT CHALLENGE TITLE FROM THE NASA SPACE APPS LIST]`
- Links: https://github.com/Davuddevelop/Crew-Readiness · live: https://crew-readiness-mu.vercel.app (its database resets itself; run it locally for the demo)

## Project name
Crew Readiness

## One-line summary
A privacy-first second look before a critical operation: it compares how each crew member works with their *own* usual pattern and puts the difference in front of a human. It never reads what is typed and never decides.

## Short description (about 150 words)
People differ: 220 ms between keystrokes is normal for one person and a large change for another, so a fixed population threshold fits nobody well. Crew Readiness builds a personal baseline from a few routine checklist sessions, using only aggregate timing numbers computed in the browser. Typed text, key identities and raw keystroke timelines never leave the device, and the server rejects them. Before a critical operation, it flags changes from a person's own pattern with a plain-language reason ("a count this high would be expected about 1 session in 9") and a suggested human check-in. Flagged sessions are kept out of the baseline so a sustained change is not learned as normal, and a human decides when a genuine new normal is accepted. It is decision support: it detects changes in interaction timing, not fatigue, illness or fitness for duty.

## Positioning (what this is, and is not)
A prototype of on-board decision support for crews doing computer-based procedure work, **tested only on simulated data**. Space is the motivating context, not something we have tested: no astronaut or space-analogue data, a typed checklist as a stand-in task, and untested real conditions (tablets, gloves, shared devices, microgravity, a changing keyboard or time of day). Real use would need crew consent and clear rules on who sees what. One property that does suit the setting: it runs fully offline and sends nothing off the device.

## What we did validate (on simulated data only)
We built a benchmark of simulated crews with injected changes whose timing and size we know, and measured two scoring methods on the same people (300 simulated people per row, 40 sessions each).

- **Fewer false alarms.** At the alert level the product uses, false alerts on normal sessions fall from about **13.0 %** to about **4.7 %** (a drop of roughly 60 %).
- **A trade-off, shown openly.** Detection also falls at that level: for a 10 % slowdown, **0.42** to **0.35** of affected sessions flagged.
- **Better at matched false-alert rates.** Holding false alerts fixed at 5 %, the new model detects more at every size we tried (for a 10 % slowdown: **0.24** to **0.36** when pauses are Poisson-like, **0.22** to **0.29** when they are very bursty).
- **A flaw we found and fixed.** In a sustained 20 % slowdown, the old method absorbed the change into the person's baseline and detection fell from 0.88 to **0.07** by the fifteenth affected session; keeping flagged sessions out of the baseline held it at **0.40** with no extra false alerts.
- **Robust to a wrong assumption.** The result barely depends on the burstiness we assume for pausing, because the model learns it per person.

All of it is reproducible with commands in `docs/ML_RESULTS.md`, and the product's Evidence page renders the same numbers from the benchmark's output file.

## What we did not validate
- **No real people.** We have no data from astronauts, crews or volunteers. The crew in the demo is fictional and its data synthetic.
- **No licensed public dataset.** We searched and found none with enough repeated sessions per person and a licence we could cite (details in `docs/ML_RESULTS.md`), so we did not use one.
- **Our own simulator.** We wrote the simulator and the model, so the benchmark is partly circular. We reduced that (several burstiness levels, a wrong-assumption test) but cannot remove it.
- **Modest gains.** The improvement is real and reproducible, not a breakthrough, and part of it is a trade of sensitivity for fewer false alerts.
- **Not scored any more:** total pause time, so one very long pause can go unflagged. It is displayed as context.
- **Human acceptance of a new normal** depends on a reviewer's judgement and is not benchmarked.
- **No clinical or operational claim.** Thresholds are illustrative. Nothing here detects fatigue or illness, clears anyone for duty, or is approved or endorsed by NASA.

## Data and privacy
Only nine aggregate timing numbers per session are stored (counts and durations). The database has no column for text or key identities, and tests check that the server rejects them. Monitoring runs only inside the task, with a visible indicator and a preview of exactly what will be sent. Accepting a new normal stores a timestamp, not who (the prototype has no accounts).

## Credits and licences
- Landing imagery: Michelangelo, *The Creation of Adam* (public domain, Wikimedia Commons reproduction); spacesuit glove from NASA's 2012 *Man and Machine* photograph (credit NASA; NASA media guidelines apply, no endorsement implied). Sources, checksums and an open verification step: `docs/ASSETS.md`.
- Instrument Sans, Instrument Serif and JetBrains Mono typefaces (SIL Open Font License 1.1), self-hosted. Chart.js (MIT), vendored. The stacked-sessions chart form was inspired by Harold D. Craft Jr.'s 1970 pulsar plot (idea only; no artwork or code used).
- Tooling: Flask, SQLite, NumPy. Built with AI coding assistance (Claude); the team reviewed and owns the decisions recorded in `docs/PLAN.md` and `docs/ML_PLAN.md`. The logo was generated with an AI image tool (`[TOOL NAME]`, see `docs/ASSETS.md`); the product's other art is drawn in code or comes from the public-domain and NASA sources above.

## What we would do next
Validate on real repeated-session data with a licence we can cite, decide with domain experts what false-alert rate a crew would accept, and add task types beyond a typed checklist.
