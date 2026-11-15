# NASA data and resources used (task N1)

> **Terms status: being confirmed with the NASA Life Sciences Portal (NLSP) help desk. Davud to update this line.**
> The archive marks this dataset "All datasets are publicly available" and it downloads without a login, but we found no stated
> licence. Until the terms are confirmed, the raw files stay out of this repository, NASA and the DOI are credited wherever a number
> appears, and all results live in one file, `app/nasa_results.json`: delete it and the Evidence page section disappears.

## Paste-ready answer (for the "NASA Data" field)

We used NASA Life Sciences Data Archive data as a core part of our evidence: the WinSCAT test battery (Flight Analog) dataset,
UTMB bed-rest Campaign 3, DOI 10.83263/sbne-th55
(https://nlsp.nasa.gov/explore/data/details/80ee3231-7c42-5be4-b6c2-b8c788feeb50?dataType=EXPERIMENTS). Healthy volunteers in 90 days
of head-down-tilt bed rest, a ground analog of spaceflight, took the WinSCAT test battery (the same subtests as on the ISS) about 12
times each. Our product compares each person with their own usual pattern instead of one threshold for everyone; this dataset lets us
test that idea on real repeated measures from a NASA study. On 24 people, most of the variation in WinSCAT response times was between
people rather than within one person (an intraclass correlation of 65 % to 87 % across four measures), which is why a personal
baseline is the right frame. At the same 1-in-20 alert budget, judged on people the cutoff was not fitted on, the own-baseline rule
kept its budget before bed rest (5.1 %) and flagged none of the bed-rest sessions, consistent with the original study's finding of no
consistent decrement. This checks our method on NASA data; it is not validation of the product and says nothing about health. Results
are produced by `ml/nasa_eval.py` and shown on our Evidence page with every limit. Terms of use are being confirmed with the NASA Life
Sciences Portal; the raw files are not redistributed.

Other NASA resources: the "Man and Machine" photograph (Image Credit: NASA, https://www.nasa.gov/image-article/man-machine/), whose
spacesuit glove appears on our landing page; and, as background only, NASA's Reaction Self Test record (NTRS 20090029851,
https://ntrs.nasa.gov/citations/20090029851) and the Human Research Program Behavioral Health evidence report (NTRS 20250001454,
https://ntrs.nasa.gov/citations/20250001454). No NASA logo is used and no endorsement is implied.

## The dataset
- **What:** NASA Life Sciences Data Archive, *Neurocognitive Assessment (WinSCAT) (Cognitive Assessment Tool for Windows) (Flight
  Analog)*, UTMB bed-rest Campaign 3. Healthy volunteers in 90 days of head-down-tilt bed rest (a ground analog of spaceflight)
  took the WinSCAT test battery about 12 times each: six times before bed rest, four during, two after. The archive describes the
  subtests as the same ones used on the International Space Station.
- **DOI:** 10.83263/sbne-th55
- **Page:** https://nlsp.nasa.gov/explore/data/details/80ee3231-7c42-5be4-b6c2-b8c788feeb50?dataType=EXPERIMENTS
- **File used:** the Campaign 3 zip from that page's Download button (SHA-256 recorded in `app/nasa_results.json`), downloaded
  2026-11-14. How it was found: `docs/DATA_SEARCH.md`.

## How we used it (a core part of the evidence)
Our product compares each person with their **own** usual pattern instead of one threshold for everyone. Our other evidence is
simulated, plus a two-volunteer check. This dataset lets us test that idea on **real repeated measures from a NASA study**:

1. **How much of the variation is between people?** For each WinSCAT median response time, the intraclass correlation (ICC) on
   sessions before bed rest: the share of all variation that is *between* people rather than within one person. A large share
   means one threshold for everyone mostly measures who someone is, not how they are doing today; that is the case for
   personal baselines.
2. **Own baseline against one threshold for everyone, at the same alert budget (1 in 20), judged on people the cutoff was not
   fitted on.** Both rules score a session with the product's per-measure rule (robust z, spread floored at 5 % of the median,
   slower only, capped at 4), averaged over four response times. The own-baseline rule compares a person with their own sessions
   before bed rest; the population rule with everyone else's. Reported: sessions flagged before bed rest (no change induced) and
   during bed rest, with intervals from resampling people.
3. **Why one combined score:** flagging a session when *any* of five measures moves, against one measure at a time.

Run it yourself: download the zip from the page above, unzip it, then
`python -m ml.nasa_eval <unzipped MR085G_Campaign_3_WinSCAT folder> --zip <zip>`. It writes aggregates and counts only; no session,
date or subject number leaves the script (`tests/test_nasa_eval.py` checks this on a synthetic fixture).

## Results
Every number is in `app/nasa_results.json`, written by the command above, and rendered on the Evidence page; a test ties the
numbers on this page to that file.

- **Between-person share of variation (ICC), before bed rest, 24 people** (95 % intervals in brackets): running memory
  response time **87 %** (79 % to 92 %), mathematics **79 %** (62 % to 86 %), match to sample **71 %** (50 % to 80 %),
  code substitution (delayed) **65 %** (49 % to 77 %).
- **Sessions flagged at a 1-in-20 budget, on held-out people:** before bed rest, own baseline **5.1 %** (1.7 % to 8.6 %), one
  threshold for everyone **4.2 %** (0.0 % to 10.3 %). During bed rest, own baseline **0.0 %** (0.0 % to 0.0 %), one threshold
  **1.1 %** (0.0 % to 3.6 %).
- **Any of five measures:** **40 %** of sessions during and after bed rest flagged, against 8 % to 15 % for one measure at a time.

**What the results show, plainly.** The strong finding is the first one: most of the variation in response time is between
people, so a per-person baseline is the right frame for this kind of signal. The own-baseline rule kept its stated alert budget on
people it had not seen. It did **not** flag more than the population rule during bed rest; both flagged almost nothing, which fits
the original study's finding of no consistent decrement, and a practice effect (people get faster at the test over time) pushes in
the same direction. Per person, with only about five normal sessions each, one flag is already 20 %, so person-level counts
(in the file) are mostly chance.

## Limits
The full list is inside `app/nasa_results.json` and on the Evidence page. In short: WinSCAT is not our typing task; sessions are days
to weeks apart; each baseline has only about five sessions; there is a practice effect; this checks the **method** on real NASA
repeated measures and is **not** validation of the product, not on astronauts or crews; it says nothing about health, fatigue, illness
or fitness for duty; a flag means "differs from this person's own pattern", never impairment.

## Every NASA resource the project uses
| Resource | Link | What we did with it |
|---|---|---|
| WinSCAT bed-rest data (NASA Life Sciences Data Archive), DOI 10.83263/sbne-th55 | https://nlsp.nasa.gov/explore/data/details/80ee3231-7c42-5be4-b6c2-b8c788feeb50?dataType=EXPERIMENTS | Ran our method on it (above); results in `app/nasa_results.json`, shown on the Evidence page |
| "Man and Machine", NASA photograph, 16 March 2012 (Image Credit: NASA) | https://www.nasa.gov/image-article/man-machine/ | The spacesuit glove from it is one of the two hands on the landing page, credited on the page; details and checksum in `docs/ASSETS.md` |
| Reaction Self Test record, NASA Technical Reports Server 20090029851 ("Psychomotor Vigilance Self Test on ISS (Reaction Self Test on Expeditions 21 and 22)") | https://ntrs.nasa.gov/citations/20090029851 | Background only: cited on the Privacy & limits page as an example of NASA using response speed as a behavioural indicator |
| NASA Human Research Program evidence report, "Risk of Adverse Cognitive or Behavioral Changes and Psychiatric Disorders..." (2025), NTRS 20250001454 | https://ntrs.nasa.gov/citations/20250001454 | Background only: framing of behavioural health monitoring as a NASA risk area (`docs/SOURCES.md`) |

No NASA logo, insignia or mission identifier is used anywhere in the project. Nothing here implies endorsement by NASA.
