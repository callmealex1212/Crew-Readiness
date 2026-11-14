# ML results: per-person count model for pauses

**Status: measured on SYNTHETIC data only.** Nothing here is evidence about real crews. Every population number and
every event effect is an illustrative assumption (`ml/synth.py`). Reproduce everything with the commands below.

## The question
Today's scoring compares each feature to the person's own median using robust z-scores (median/MAD). We found
that this raises a false alert on about 12-13 % of *normal* sessions (it varies a little with the simulated people) at the YELLOW cutoff, and that **78 % of those
alerts come from `pause_total_ms`**: pauses are small counts (usually 0 or 1), the MAD is often 0, and one ordinary
pause then looks huge. See `python -m ml.diagnose_false_alerts`.

## The change (`app/pause_model.py`)
Score **pause count** with a per-person negative binomial: mean from their own history (shrunk toward a prior),
burstiness estimated from their own history (shrunk, then widened for uncertainty in the mean). Report how
surprising today's count is as a tail probability, turned into the same deviation scale as other features.
**Known loss:** pause *time* (one very long pause) is shown as context but is no longer scored.

## Results (`python -m ml.compare 0.0|0.5|1.5`)
Detection of event sessions at a **fixed 5 % false-alert rate**, 5-session step event, 300 simulated people per cell.

| Slowdown | Pause burstiness | Median/MAD (before) | Gamma-Poisson | Negative binomial (now) |
|---|---|---|---|---|
| 6 % | none | 0.14 | 0.17 | 0.18 |
| 10 % | none | 0.24 | 0.34 | 0.36 |
| 15 % | none | 0.42 | 0.57 | 0.59 |
| 10 % | high (od 1.5) | 0.22 | 0.26 | 0.29 |
| 15 % | high (od 1.5) | 0.39 | 0.47 | 0.53 |

## At the shipped alert level (YELLOW at score >= 1.0, no matching)
`python -m ml.export_results`, 300 simulated people per row, 5-session step event, synthetic.

| Slowdown | Detected before | Detected now | False alerts before | False alerts now |
|---|---|---|---|---|
| 6 % | 0.26 | 0.18 | 11.9 % | 4.7 % |
| 10 % | 0.42 | 0.35 | 13.0 % | 4.7 % |
| 15 % | 0.62 | 0.58 | 12.7 % | 4.8 % |

**This is a trade-off, not a free win.** False alerts fall by about 60 %, and detection also falls (by 0.04 to 0.08).
The fixed-false-alert table above is the fair comparison (the new model is better at every matched rate). The product's
cutoff of 1.0 now sits at a more conservative point on the curve; whether that is the right point is a decision for
the team (decision 3 in `docs/ML_PLAN.md`: what false-alert rate is acceptable to a crew). Lowering the cutoff trades the
false-alert reduction back for detection. After the change, the remaining false alerts are spread evenly across
features (checklist 35 %, typing rhythm 26 %, pauses 20 %, typing variability 19 %), so no single feature dominates.

## Experiment: a flagged session poisons the baseline (not shipped)
`python -m ml.experiment_contamination`. Today every OK session joins the person's baseline, including flagged ones. In a
**sustained** 15-session slowdown the baseline absorbs the change and the alerts fade. Detection by position in the event
(alert at 1.0; synthetic; 300 people):

| Slowdown | Policy | Session 1 | 3 | 5 | 8 | 11 | 15 | False alerts |
|---|---|---|---|---|---|---|---|---|
| 20 % | keep all (today) | 0.88 | 0.78 | 0.67 | 0.41 | 0.21 | **0.07** | 4.5 % |
| 20 % | exclude flagged (score >= 1.5) | 0.88 | 0.83 | 0.80 | 0.71 | 0.59 | **0.40** | 4.6 % |
| 10 % | keep all (today) | 0.40 | 0.35 | 0.26 | 0.19 | 0.11 | 0.08 | 5.6 % |
| 10 % | exclude flagged | 0.41 | 0.37 | 0.28 | 0.22 | 0.16 | 0.10 | 5.8 % |

Catch: excluding flagged sessions forever would also lock out a *genuine new normal* (new keyboard, practice effect), so
the alerts would never stop. A re-admission rule or a human "accept as the new normal" action is required; that is a design
decision (decision 4 in `docs/ML_PLAN.md`). **Implemented** (team lead chose "exclude + human accepts"): flagged sessions are excluded; a reviewer can accept the run, which restarts the baseline from it. The simulation measures only the exclusion; the human-acceptance step is not benchmarked, because it depends on a person's judgement.

## Experiment: personal "rarity" as an alert rule (negative result; not shipped)
`python -m ml.calibration`. Idea: rank today's score among the person's own recent past scores (a conformal p-value, window 20, at least
8 past sessions) and alert when `p <= alpha`. In theory the false-alert rate is at most `alpha` whatever the shape of the person's noise.

- **Calibration holds, conservatively** (400 simulated people, 10,800 sessions, no events): target 0.20, 0.10, 0.05 gave observed
  0.180, 0.083, 0.030 (everyone alike) and 0.174, 0.080, 0.028 (people differ in how erratic they are).
- **But it detects less than a plain population threshold at the same observed false-alert rate.** For a 10 % slowdown: 0.50 vs 0.61 at
  a 16 % false-alert rate and 0.26 vs 0.36 at 6 %; for a 20 % slowdown: 0.76 vs 0.94 and 0.40 vs 0.85. Making people differ in how erratic
  they are changed this very little. At `alpha = 0.05` it can almost never fire, because with 8 to 20 past sessions the smallest possible
  p-value is about 1/(n+1).
- **Why:** 8 to 20 sessions are too few to rank against; the population threshold borrows strength from many people.
- **Decision (gate in `docs/PLAN_V2.md`):** personal rarity is not used to alert. Where the product already quotes "about 1 session in N"
  (the pause reason) that is a descriptive statement, not a calibrated alert. What we do instead: calibrate the **cutoff** to a stated
  false-alert budget on pooled normal sessions, and check it on held-out people (real pilot data when we have it; see `docs/TASKS.md` C1).
- **Assumptions:** same simulator and illustrative parameters as above; a window and minimum history we chose and did not tune.

## Intervals and the alert budget on the Evidence page
`python -m ml.export_results` now writes 95 % bootstrap intervals over simulated **people** (not sessions) for the operating-point table, and the held-out budget table below; `/evidence` renders both from `app/results_data.json`. Point estimates are unchanged (`tests/test_evaluate_ci.py` proves the interval code reproduces `evaluate`). Intervals say how much a result depends on which simulated people were drawn; they say nothing about real people.

## Alert-budget calibration, checked on held-out people (`python -m ml.calibrate_cutoffs`)
A **budget** of 1 in 20 means: on a normal session, about 1 in 20 would be flagged by chance. We fit the cutoff on the pooled normal-session
scores of some simulated people and measure the false-alert rate on **other** people (10 folds, split by person). 300 people, 10,500 normal sessions.

| Budget | Cutoff | Observed on held-out people | 95 % interval (bootstrap over people) |
|---|---|---|---|
| 1 in 10 | 0.82 | 10.0 % | 9.4 % to 10.6 % |
| 1 in 20 | 0.96 | 5.0 % | 4.6 % to 5.5 % |
| 1 in 50 | 1.14 | 2.0 % | 1.8 % to 2.3 % |

- **The shipped YELLOW cutoff (1.0) stands for about 1 normal session in 24** on simulated data (4.2 %); with people who differ in how erratic
  they are, about 1 in 25.
- **Individuals:** about 12 % of people see more than twice the budget at 1 in 20, but **chance alone gives about 10 %** (each person has only
  about 35 sessions), and the same holds at the other budgets. So in the simulation a pooled cutoff fits each person about equally well; the
  "worst person" figures are small-sample noise. **Real people may differ**, which is what the pilot is for (`docs/PLAN_V2.md`, W3 and W4).
- **Not claimed:** this says the *method* of choosing a cutoff for a budget works on simulated data. It says nothing about real crews.

## Robustness to a wrong assumption (`python -m ml.stress_prior`)
Assumed burstiness prior 0.05 / 0.5 / 2.0, against simulated people whose true burstiness is 0 / 0.5 / 1.5
(10 % slowdown, 5 % false alerts): detection stays 0.35-0.38 / 0.36-0.38 / 0.29 against 0.24 / 0.29 / 0.22 for
median/MAD. The prior washes out because burstiness is learned per person.

## Limits (say these out loud)
1. **Synthetic.** The simulator draws pauses from a Poisson-type process. Real pausing may differ. A public
   dataset check is still open (`docs/ML_PLAN.md`).
2. **Our own benchmark.** We wrote both the generator and the model. The overdispersion and prior tests reduce but do
   not remove that risk.
3. **Modest gains.** Roughly +0.1 detection at equal false alerts in the favourable case, +0.03 to +0.14 when pauses are
   very bursty. Not a breakthrough; a real, reproducible improvement with a stated mechanism.
4. **Not scored any more:** pause time. Long single pauses go unflagged by this model.
5. **Calibration of "1 session in N"** assumes the count model is right; it is an explanation aid, not a guarantee.
6. Detects changes in interaction timing against a person's own history. **Not** fatigue, illness or fitness for duty.

## Public dataset search (2026-11-14): no usable fit, dropped
The plan asked for one public dataset with repeated per-person task timings and a citable licence. What we found,
so nobody repeats it:
- **Sandbox network:** only Hugging Face and a few media hosts are reachable. Zenodo, OSF, PhysioNet, figshare, UCI,
  Kaggle and the CMU keystroke-dynamics page were not.
- **Hugging Face keystroke sets** (e.g. Aalto 136M features): one session per person, so there is no personal history,
  and most carry no licence tag, which means we cannot use them.
- **Closest candidate:** `Emulated-Inc/drowsy-driving-reaction-time-eeg`, a mirror of Cao et al. 2019 (*Scientific Data*
  6:19, doi:10.1038/s41597-019-0027-4), tagged CC BY 4.0. Lane-drift reaction times, 62 sessions. **At most 5 sessions per
  person (most have 2 or 3)**, below our 5-session minimum baseline; 20 sessions are EEG files without a trial table;
  the task is driving, and its framing is drowsiness, which is the claim this project avoids. Not used.
- **Consequence:** every number in this repository is synthetic. If a typing or reaction-time dataset with 10+ sessions
  per person and a licence appears (the CMU keystroke-dynamics benchmark is a plausible candidate; its terms are
  **unverified**), the first use is the false-alert rate on real people with no injected events.

## Replay page (`/replay`)
One simulated person, scored by the old and the current scoring side by side (`ml/scenario.py`, `GET /api/simulate`). Same
generator and the same scoring code as the benchmark, so it cannot show something the product does not do. It is an
illustration: single runs vary a lot (some show the new scoring flagging fewer affected sessions, and the page says so).
The 300-person results above are the evidence.

## Reproduce
```
.venv/bin/python -m ml.report_incumbent        # before: detection and false alerts
.venv/bin/python -m ml.diagnose_false_alerts   # why
.venv/bin/python -m ml.compare 0.5             # fixed-false-alert comparison
.venv/bin/python -m ml.stress_prior            # wrong-prior test
CREW_PAUSE_MODEL=robust python run.py          # run the product with the old scoring
```
