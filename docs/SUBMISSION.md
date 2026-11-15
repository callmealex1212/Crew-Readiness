# Submission copy (NASA Space Apps 2026): one paste-ready block per Project page field

Davud fills the two placeholders below, nothing else. Every number here comes from a result file and a test checks it:
`app/results_data.json` (simulated benchmark, `tests/test_submission.py`), `docs/pilot/pilot_report.json` (the volunteer pilot),
`app/nasa_results.json` and `docs/ML_RESULTS.md` (`tests/test_nasa_eval.py`). The Use of SI, NASA Data and References blocks are
copied from `docs/AI_USE.md`, `docs/NASA_DATA.md` and `docs/REFERENCES.md`, and a test checks they match.

- Team: `[TEAM NAME]`
- Challenge: `[EXACT CHALLENGE TITLE FROM THE NASA SPACE APPS LIST]` (the challenge "Create Health Monitoring Software for Astronauts on Space Missions")
- Link to Final Project: https://github.com/Davuddevelop/Crew-Readiness (code, docs, results) · live demo copy: https://crew-readiness-mu.vercel.app (its database resets itself; the app runs fully offline from the repository)
- Link to Project Demo: the 7-slide deck (task N2), shared publicly; check the link in a private window before submitting.

## Project Name
Crew Readiness

## High-Level Project Summary
Crew Readiness is offline, privacy-first software that lets crew members see whether they are working the way they usually do,
before a critical operation such as docking. During a routine checklist it records only timing (how quickly and steadily someone
types and responds), never what is typed. Each check-in is compared with that person's own baseline, not a population average, and
any change is explained in plain words. The crew member sees their own status first, can add a short reaction check and private
notes that never leave the device, and decides whether to involve a reviewer. A watchdog flags missed check-ins, and the software
tests its own health. It answers the challenge with a passive behavioural indicator that astronauts can evaluate and act on
themselves, beside physiological monitoring, not instead of it. It matters because long missions bring isolation, heavy workload and
communication delays, so crews need early, private self-checks that work without Earth. It is decision support, not diagnosis,
tested on simulated data, a two-volunteer pilot and NASA bed-rest data, never on astronauts.

## Detailed Project Description

**What it does and how it works.** A working prototype of on-board decision support. It notices when a crew member is working
differently from their own usual pattern and puts that change in front of the person first, then a human reviewer.
1. *Check-in:* a short routine checklist; the person reads each step and types its fixed confirmation phrase. No sensors, wearables
   or extra tests.
2. *Timing only:* the browser keeps timestamps, not keys, and computes nine aggregate numbers (time between keystrokes and its
   spread, pauses of 2 s or more, time to start each step, corrections). The person sees exactly these numbers before anything is
   saved. Typed text, key identities and keystroke timelines never leave the device, and the server rejects them.
3. *Their own baseline:* each check-in is compared with that person's earlier sessions (median and robust spread), never with a
   population average. Pause counts use a per-person count model, so one ordinary pause does not look alarming.
4. *A plain answer:* GREEN, YELLOW or RED, with reasons in words ("a count this high would be expected about 1 session in 9") and a
   suggested action: a short check-in, nothing more.
5. *The person first:* "My check-in" shows the crew member their own status before anyone else, with an optional reaction check
   compared with their own earlier checks, and private notes (sleep, how they feel) that stay in their browser only.
6. *The reviewer:* the Mission view, the dashboard and a printable brief show each role's status, a missed check-in watchdog
   ("look in on them in person"; it says nothing is necessarily wrong) and a review panel. If a change is real and lasting (new
   gloves, a different device), a human accepts it as the new normal; the software never decides that itself.
7. *Built for isolation:* it runs entirely on one computer with no internet, checks its own health (database, scoring on a known
   example, clock, no outside network) and backs up and restores its data with a checksum.

**Benefits.** It uses work the crew already does, so it costs no extra time. Personal baselines suit people who differ and keep
false alarms low; crew time is scarce, and too many alarms teach people to ignore them. Privacy by design: nine numbers, never
text, and the crew member sees them first. It explains itself in plain language and always leaves the decision to a human. It works
fully offline, which suits missions with long communication delays.

**What we hope to achieve.** A private, low-effort self-check that helps a crew member and their team decide when to pause and talk
before a critical operation, beside existing health monitoring. The same idea applies on Earth to safety-critical work such as
aviation, control rooms and remote stations. Next: real repeated-session data from crews or analog missions, agreeing with domain
experts what false-alert rate a crew would accept, and task types beyond a typed checklist.

**What we measured.** On simulated data, a benchmark of simulated crews with injected changes (300 simulated people per row):
- **Fewer false alarms.** At the product's alert level, false alerts on normal sessions fall from about **13.0 %** to about **4.7 %**.
- **A trade-off, shown openly.** Detection also falls at that level: for a 10 % slowdown, **0.42** to **0.35** of affected sessions flagged.
- **Better at matched false-alert rates.** At a fixed 5 % false-alert rate, for a 10 % slowdown: **0.24** to **0.36** when pauses are
  Poisson-like, **0.22** to **0.29** when they are very bursty.
- **A flaw we found and fixed.** In a sustained 20 % slowdown, a baseline that keeps learning absorbs the change and detection fell
  from 0.88 to 0.07 by the fifteenth affected session; keeping flagged sessions out of the baseline held it at 0.40.
- **New equipment, handled by a human.** After a person accepts a lasting change, repeated alerts fall from **27 %** to **11 %** of
  sessions, and a later real slowdown is flagged **60 %** of the time against **54 %**.

A very small volunteer check (two people, not validation):
**5 of 6** sessions recorded as changed were flagged, and **0 of 8** normal sessions were. On NASA bed-rest data (24 people; see the NASA Data field): most of the variation in response time is between people
(an intraclass correlation of 65 % to 87 %), and at a 1-in-20 budget on held-out people the own-baseline rule kept its budget
before bed rest (5.1 %).

**What we did not validate.** Almost no real people: two volunteers in our own pilot, and a NASA bed-rest dataset used to check the
method on a different task (a cognitive test battery), not our product; no astronauts or crews, nothing in space. Our own simulator
makes the benchmark partly circular. The gains are modest and partly a trade of sensitivity for fewer false alerts. Thresholds are
illustrative. Nothing here detects fatigue or illness, clears anyone for duty, or is approved or endorsed by NASA.

**Tools, languages, hardware and software.** Python, Flask, SQLite and NumPy on the server; HTML, CSS and plain JavaScript in the
browser, with Chart.js and three self-hosted fonts, so nothing loads from the internet. pytest for automated tests (including
privacy and claims checks), Playwright browser checks for layout, keyboard use and phone width, Git and GitHub, and Vercel for the
hosted demo copy. Hardware: an ordinary laptop and keyboard; no sensors. AI coding assistance: see the next field.

**How it is creative.** A passive behavioural signal from ordinary procedure work, against each person's own pattern instead of a
fixed threshold; a count model for pauses; keeping flagged sessions out of the baseline, with a human accepting a genuine new normal;
the crew member's own view first; publishing what did not work (a "personal rarity" alert rule was calibrated but detected less, so
we did not ship it); and a "stacked sessions" picture of a person's history, inspired by the 1970 pulsar plot.

**Factors we considered.** Privacy (nine aggregate numbers; no column for text; tests enforce it); honest claims (it detects changes in
interaction timing, not fatigue, illness or fitness for duty); false alarms and human judgement (a flag suggests a conversation);
confounders (keyboard, language, time of day, sleep and practice all change timing, and the product says so); accessibility
(keyboard use, contrast, phone width); and licences for every image, font and dataset.

## Use of Super Intelligence (SI)
Yes. We used AI coding assistants as tools; the idea and every decision were the team's.

- **Who decided what.** The team lead set the direction before any code was written: decision support that compares each person
  only with their own usual pattern, a human always decides, privacy first, and no claims about health. The team lead made every
  product and claim decision, and ran the volunteer pilot with a teammate. The volunteers' sessions are real; the AI did not
  produce any pilot data. It did help check the pilot files and correct one volunteer's session labels to match what was
  recorded (stated in the pilot data pull request).
- **What the AI did.** An AI coding assistant (Claude, by Anthropic, used through Claude Code) wrote much of the code, the tests and
  the documentation, and proposed some features that the team lead reviewed and approved. A second Claude Code session, run by our
  teammate Alex, wrote the attention check, the Privacy & limits page, keyboard and phone fixes, the pilot tooling, the NASA data
  search and the NASA bed-rest analysis script, the self-test and the backup tool. AI also helped draft submission text, which the
  team edited.
- **Images, audio, video.** The product contains **no AI-generated image**. An earlier AI-generated logo was removed on 2026-11-15
  and replaced by a mark drawn in code. The other images are a public-domain painting and a NASA photograph (see References).
  There is no AI-generated audio or video.
- **Code and data.** AI-written code is acknowledged here, at the top of the README and in the page metadata
  (`<meta name="ai-assistance">`). Every number shown is produced by code from a result file (simulated benchmark, the volunteer
  pilot, the NASA bed-rest analysis), not typed by hand or by an AI.
- **Inside the product.** The running app calls no AI service. Its "machine learning" is classical statistics (robust medians, a
  count model, bootstrap intervals).
- **No NASA branding** (logos, insignia, mission identifiers) appears in any generated content.

## NASA Data
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

## Space Agency Partner Data and Other References
**Space agency data:** NASA only (see the NASA Data field). No data from the 2026 Space Agency Partners was used.

**Data**
- NASA Life Sciences Data Archive, WinSCAT test battery (Flight Analog) dataset, UTMB bed-rest Campaign 3, DOI 10.83263/sbne-th55
  (full title in `docs/NASA_DATA.md`), https://nlsp.nasa.gov/explore/data/details/80ee3231-7c42-5be4-b6c2-b8c788feeb50?dataType=EXPERIMENTS.
  Marked "All datasets are publicly available" by the archive; terms being confirmed with the NLSP help desk. Raw files not redistributed.
- Two volunteers (pseudonyms) in our own small pilot, with consent; aggregate timing numbers only (`docs/pilot/`).
- All other data in the app is synthetic, generated by our own code.

**Images**
- Michelangelo, *The Creation of Adam* (c. 1508-1512), Wikimedia Commons reproduction "Michelangelo - Creation of Adam (cropped).jpg",
  https://commons.wikimedia.org/wiki/File:Michelangelo_-_Creation_of_Adam_(cropped).jpg. Public domain (PD-Art / PD-old-auto-expired).
  Cut out and recoloured.
- "Man and Machine", NASA photograph, 16 March 2012, https://www.nasa.gov/image-article/man-machine/. Image Credit: NASA; NASA media
  usage guidelines (no endorsement implied, no NASA logos). We use only the spacesuit glove, cut out and recoloured.
- The Crew Readiness mark, favicon and share card: drawn by the team in code; MIT. No AI-generated image is used.

**Fonts (self-hosted, licence files in `app/static/fonts/`)**
- Instrument Sans, Copyright 2022 The Instrument Sans Project Authors: SIL Open Font License 1.1.
- Instrument Serif, Copyright 2022 The Instrument Serif Project Authors: SIL Open Font License 1.1.
- JetBrains Mono, Copyright 2020 The JetBrains Mono Project Authors: SIL Open Font License 1.1.

**Code libraries in the product**
- Python (PSF License); Flask 3.1 (BSD-3-Clause) with its dependencies Werkzeug (BSD-3-Clause), Jinja2 (BSD), MarkupSafe
  (BSD-3-Clause), click (BSD-3-Clause), itsdangerous (BSD) and blinker (MIT); NumPy (BSD-3-Clause, with bundled parts under 0BSD,
  MIT and Zlib); SQLite (public domain).
- Chart.js v4.4.1, vendored in `app/static/vendor/chart.umd.js` (c) 2023 Chart.js Contributors: MIT.

**Development and testing tools (not shipped in the product)**
- pytest (MIT); Playwright for Node (Apache-2.0) with its Chromium browser, for layout, keyboard and flow checks; Node.js (MIT).
- For rebuilding the landing images only (`scripts/assets/`): Pillow (MIT-CMU) and OpenCV, `opencv-python-headless` (Apache 2.0).
- Git and GitHub (version control); Vercel (hosting of the demo copy).
- AI coding assistant: Claude, by Anthropic, used through Claude Code (see the Use of SI field and `docs/AI_USE.md`).

**Text cited as background (not copied; one line each in `docs/SOURCES.md`, with how each informed us)**
- NASA Technical Reports Server 20090029851, "Psychomotor Vigilance Self Test on ISS (Reaction Self Test on Expeditions 21 and 22)",
  https://ntrs.nasa.gov/citations/20090029851.
- Dev SI, Whiting SE, Nelson GA, et al. NASA Human Research Program Behavioral Health evidence report, 2025 (full title in
  `docs/SOURCES.md`), https://ntrs.nasa.gov/citations/20250001454.
- Basner M, Savitt A, Moore TM, et al. *Development and Validation of the Cognition Test Battery for Spaceflight.* Aerospace Medicine
  and Human Performance 2015;86(11):942-952, doi:10.3357/AMHP.4343.2015.
- Basner M, Dinges DF. *Maximizing Sensitivity of the Psychomotor Vigilance Test (PVT) to Sleep Loss.* Sleep 2011;34(5):581-591,
  doi:10.1093/sleep/34.5.581 (source of the attention check's 100 ms false-start rule).
- Giancardo L, Sánchez-Ferro A, Arroyo-Gallego T, et al. *Computer keyboard interaction as an indicator of early Parkinson's disease.*
  Scientific Reports 2016;6:34468, doi:10.1038/srep34468 (CC BY 4.0).
- "Sleep deficiency in spaceflight is associated with degraded neurobehavioral functions and elevated stress in astronauts on six month
  missions aboard the International Space Station", cited on the Privacy & limits page; https://read.qxmd.com/read/35023565 (a person
  is still to open and check this one; see `docs/TASKS.md`).
- Design idea only, no artwork or code used: Harold D. Craft Jr.'s 1970 stacked plot of pulsar CP 1919, the inspiration for the
  "stacked sessions" chart.
