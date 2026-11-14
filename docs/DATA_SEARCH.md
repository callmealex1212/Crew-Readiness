# NASA data feasibility (task F4)

**Question:** is there an openly licensed NASA dataset with repeated behavioural or performance measures per person (at least
8 sessions each) that our personal-baseline approach could run on? Time-boxed to 90 minutes; searched 2026-11-14 by the
teammate's coding agent. **Nothing here has been checked by a human yet.**

## Verdict: technically a clean fit, licence NOT confirmed (conditional go)

- **Found:** NASA Life Sciences Data Archive, *Neurocognitive Assessment (WinSCAT) (Cognitive Assessment Tool for Windows) (Flight
  Analog)*, DOI 10.83263/sbne-th55, experiment page <https://nlsp.nasa.gov/explore/data/details/80ee3231-7c42-5be4-b6c2-b8c788feeb50?dataType=EXPERIMENTS>.
  Real people in a 60 to 90-day head-down-tilt bed rest study (a ground analog of spaceflight) took the WinSCAT test battery, which
  the archive describes as the same subtests used on the International Space Station. Per person and session it gives median
  response times and accuracy for four subtests.
- **Fit:** UTMB Campaign 3 has 26 per-person files; **24 of them have 8 or more sessions** (most have 12: six before, four during and
  two after bed rest). That meets our 8-session bar. Campaign 1 (3 people, a different column layout) was not analysed.
- **Access:** the archive marks this experiment *"Data preservation is complete. All datasets are publicly available."* The files
  downloaded from the experiment page's "Download" button without a login or a data request (Campaign 3 zip: SHA-256
  `5ed6f27330a5b026d1bda1bef46eedec15adddfbf68b85caf9addc6710bb7c16`).
- **Licence: not found.** NLSP's guidelines page says *"Many pooled data from research studies are publicly available on this site"*
  but names no licence, and the portal's own entry in NASA's open-data catalogue (data.nasa.gov) says *"License not specified"*.
  NASA-produced data are often US Government works, but **we have not confirmed that for this dataset** (the study was run at the
  University of Texas Medical Branch). Our earlier rule (`docs/ML_RESULTS.md`) was that data without a licence we can cite is not used.
- **Therefore:** the raw files are **not** in this repository. The result below may be used in the product or the submission only
  after a person confirms the terms (for example by asking the NLSP help desk, or finding a stated licence or citation policy).
  Until then it is a feasibility note for the team.

## What we ran (exploratory, on real people)

`python scripts/nasa_winscat_check.py <unzipped Campaign 3 folder>`. Per person: the baseline is their own pre-bed-rest sessions,
with run 1 (first exposure to the test) dropped as practice; each session during and after bed rest is compared with it using the
product's per-measure rule (median and robust spread as in `app/baseline.py`, spread floored at 5 % of the median, one-sided,
capped at 4). A session is "flagged" on a measure when its deviation is 1.0 or more, the level at which the product writes a reason.

| Measure (WinSCAT) | Sessions flagged (23 people, 109 sessions during or after bed rest) |
|---|---|
| Running memory median response time (`CPTRT`) | 10 / 109 (9 %) |
| Mathematics median response time (`MTHRT`) | 9 / 109 (8 %) |
| Match to sample median response time (`MTSRT`) | 16 / 109 (15 %) |
| Code substitution (delayed) median response time (`CDDRT`) | 12 / 109 (11 %) |
| Running memory accuracy (`CPTA`, lower is worse) | 15 / 109 (14 %) |
| **At least one of the five** | **44 / 109 (40 %)** |

By phase: 36 of 78 sessions during bed rest and 8 of 31 after it were flagged on at least one measure.

**How to read it (and how not to):**
- The original study reports *no consistent decrements in cognitive performance across subjects or across time in bed rest*.
  So these flags are best read as **alerts where no change was induced on purpose**. They are not proven false alarms (bed rest,
  boredom or motivation may have changed something), and they say nothing about anyone's health.
- What it does suggest, on real people: one measure at a time, the per-measure rule flags roughly 1 session in 7 to 1 in 12;
  checking five measures and flagging on any of them flags 4 sessions in 10. That is the multiple-comparisons problem, and it
  supports what the product already does (one weighted score, calibrated to a stated false-alert budget, task C1b) rather than
  "alert if any measure moves".
- It is **not** our typing task, the sessions are days to weeks apart, and the baseline has only 5 sessions. It is a check of the
  method on real repeated measures, not a validation of the product.

## What was searched (in order) and why each was dropped

| Where | How | Found | Decision |
|---|---|---|---|
| NASA Open Science Data Repository (OSDR) | Search API, 18 terms (cognition, reaction time, psychomotor vigilance, behaviour, sleep, typing, keystroke, isolation, astronaut ...) | Human studies are all molecular (gene expression, proteins, blood) | No behavioural data |
| OSDR, Ames Life Sciences Data Archive part | Same search, `type=alsda` | Cognition, vigilance and behaviour studies are in mice, rats and flies | Not people |
| data.nasa.gov (CKAN API) | 8 queries | A rat analog of the psychomotor vigilance test (OSD-897); mouse cognition (OSD-776); *Flight Crew Physiological Data for Crew State Monitoring* (pilot EEG/ECG, few sessions per person, "License not specified", framed around attention states) | Animals, or physiology rather than task timing, and no licence |
| NASA Life Sciences Portal (NLSP), which now hosts LSDA | Its JSON API: all 2,676 experiments; 154 are human and mention cognition, vigilance, reaction time or attention; 19 of those are "All datasets are publicly available" | WinSCAT (above); also sleep-loss vigilance, bed rest performance testing, "Stability and Precision of Human Performance" (4 subjects) | WinSCAT is the cleanest fit; the others were not opened within the time box |
| Bed rest Campaign 11 neurocognitive study (Seidler) | NLSP record | 7 time points; "All datasets are privacy-protected. Data is available via data request" | Too few sessions; needs a formal request (months, per NLSP's own timeline) |

## Network notes (for whoever repeats this)

This environment initially blocked every NASA, PubMed and DOI host. A personal environment allowing osdr.nasa.gov,
visualization.osdr.nasa.gov, nlsp.nasa.gov, ntrs.nasa.gov, www.nasa.gov, data.nasa.gov and a few literature hosts was created for
this task. Still blocked: data.crosscite.org (DOI metadata, where a licence field might be listed); www.spaceappschallenge.org failed
its certificate check. NLSP pages need JavaScript; the files were downloaded through the page's own Download button in a headless browser.

## Next steps (for a human, in order)

1. Confirm the licence or terms of use for DOI 10.83263/sbne-th55 (NLSP help desk, or the DataCite record). Record the answer here.
2. If the terms allow it: re-run the script, and let task C4/W4 compare the real session-to-session spread with the simulator.
3. If they do not, or there is no answer before the freeze: keep this file as the record of the search and do not cite the numbers.
