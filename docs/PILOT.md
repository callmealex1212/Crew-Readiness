# Pilot protocol (task F1): a small pilot with deliberate perturbations

**What this is:** a small pilot with 5 to 8 volunteers on one laptop. It checks two things on real people: how much a
person's own timing varies from session to session (to compare with our simulator, task C4), and whether the prototype
flags sessions that we *deliberately* disturbed. **What it is not:** a validation, a clinical study, or anything about
health, fatigue or fitness for duty. We report it as "a small pilot with deliberate perturbations", with its size, every time.

Time needed: about 30 minutes per volunteer (12 sessions of about one minute, plus a practice run and short breaks).
With 5 volunteers, plan about 3 hours of laptop time.

## 1. Before the first volunteer (operator, once)

1. Use **one laptop, one keyboard, one keyboard layout** for everyone. Note them once in the sheet header (section 5).
   Same chair and room if you can. Close other apps; turn off notifications.
2. Use a **separate pilot database**, so `reset-demo` can never wipe it and the demo stays as it is.
   Run every command below in the same terminal, from the repo root, with the venv active:

   ```bash
   export CREW_DB_PATH=instance/pilot.sqlite3          # Windows PowerShell: $env:CREW_DB_PATH="instance/pilot.sqlite3"
   python run.py                                       # http://127.0.0.1:5050, leave it running
   ```

   (Run it locally. The hosted copy resets its database and must not be used.) The first start also loads the fictional demo
   crew into this database; that is fine, the export ignores them.
3. Create one pseudonymous profile per volunteer, **in a second terminal with the same `CREW_DB_PATH`**:

   ```bash
   flask --app run add-profile pilot-01 "Volunteer 01" Volunteer
   flask --app run add-profile pilot-02 "Volunteer 02" Volunteer
   ```

   **The id must be `pilot-` plus two digits** (`pilot-01` to `pilot-99`), and the display name must not be a real name.
   The export only accepts ids of that form, so a real name typed by mistake cannot reach the CSV.
4. Keep the list that links pseudonyms to real people **on paper only**, never in the repo, a chat or a photo. Shred it after the hackathon.

## 2. With each volunteer

1. **Consent first.** Read the consent text (section 4) with them. If they agree, tick consent in the sheet. If not, stop; nothing is recorded.
2. **Assign the perturbation.** Odd pseudonyms (`pilot-01`, `-03`, ...) use **non-dominant hand**; even ones (`pilot-02`, `-04`, ...)
   use **counting backwards**. The same perturbation for all three perturbed sessions of one person.
3. **Practice run (not recorded).** Open http://127.0.0.1:5050/monitor, choose their pseudonym, **Start task**, type the
   checklist, then press **Discard** on the review screen. This takes the "first time I see this" slowness out of the baseline.
4. **Twelve recorded sessions**, in this order, with about a minute's break between them:

   | Session | Condition | What the volunteer does |
   |---|---|---|
   | 1-8 | normal | Type the checklist at their own normal pace, dominant hand(s), as usual |
   | 9-11 | **perturbed** | *Non-dominant hand:* type with the non-dominant hand only. *Counting backwards:* count backwards out loud by 3 from a number you give (for example 300, then 250, then 200) while typing |
   | 12 | normal | Back to normal |

   Each session: `/monitor`, choose the pseudonym, **Start task**, type each confirmation phrase and press Enter, then
   **Submit timing features** on the review screen. Tick the row in the sheet **only after** the result screen appears.
   If something goes wrong (an interruption, a crash), press **Discard**, note the issue code, and redo that session; a
   discarded session is not stored and does not count.
5. **Do not discuss the result screen** (GREEN, YELLOW, RED) during the pilot; press **Run again**. Seeing a flag could change how they type.
6. Never type a real name into any field, and do not add free-text notes to the sheet (use the issue codes).

## 3. After the last volunteer (operator)

```bash
python scripts/export_pilot.py --db instance/pilot.sqlite3     # --db is optional when CREW_DB_PATH is still set
```

This writes `docs/pilot/pilot_sessions.csv`: one row per submitted session, with the pseudonym, the session number (1 to 12, in
the order sessions were submitted) and the nine aggregate timing numbers. **Nothing else**: no names, no roles, no timestamps,
no typed text (typed text is never stored at all). `tests/test_pilot_export.py` checks this. Check that every person shows 12 sessions
in the script's summary; if not, fix the sheet before anything else. If a volunteer withdraws, re-run with `--exclude pilot-NN`.

Then fill the sheet (`docs/pilot/session_sheet.csv`, section 5) and run `python scripts/check_pilot_ready.py` until it prints
**READY**: it names, per pseudonym, every session missing from the export and every sheet row still lacking a consent or issue code.
Commit the CSV and the filled sheet to `docs/pilot/`. **Do not edit any number in the CSV.** If a session went wrong, say so in the sheet's issue code; the analysis (task C4) decides what to do with it.

Then run the analysis (it needs both files and refuses if they disagree):

```bash
python -m ml.pilot_report      # reads docs/pilot/pilot_sessions.csv and docs/pilot/session_sheet.csv, writes docs/pilot/pilot_report.json
```

It prints false alerts on the normal sessions, detection on the perturbed ones (split by perturbation), and whether real
variability matches what the simulator assumes. Intervals are wide on purpose (a few people; sessions of one person are not
independent). If it says the simulator assumptions are off by more than 1.5x, `suggest_population()` gives the numbers to put into
`ml/export_results.py`; re-run the benchmark and say in the docs that the figures moved for that reason. `tests/test_pilot_report.py`
checks the code on a **synthetic** stand-in pilot; no number from that may be quoted as a pilot result.

## 4. Consent text (read aloud, plain language)

> This is a small test of a student prototype for the NASA Space Apps hackathon. It is not a medical test and it says nothing
> about your health, tiredness or abilities.
>
> You will type a short, fixed checklist about twelve times, about one minute each. Three times we will ask you to type
> differently on purpose: with your other hand, or while counting backwards out loud.
>
> **What is recorded:** nine numbers per session about timing, such as the time between key presses, the number of pauses
> and how many corrections you made. **What is never recorded:** what you type, which keys you press, your name, or anything
> outside this task. You can see exactly what is sent on the screen before every session is stored.
>
> You get a code name (for example pilot-03). Only the code name and the timing numbers are kept. The numbers may be published
> with our project in a public code repository, under your code name. The list linking your name to your code name stays on
> paper and is destroyed after the hackathon.
>
> Taking part is voluntary. You can stop at any time without giving a reason, and you can ask us to remove your numbers before
> we publish them by contacting **[CONTACT]** before **[DEADLINE FOR WITHDRAWAL]**. You must be 18 or older to take part.
>
> Do you agree to take part?

The team fills **[CONTACT]** and **[DEADLINE FOR WITHDRAWAL]** before the first volunteer, and the operator reads the final text.

## 5. Session-order sheet

`docs/pilot/session_sheet.csv` is already laid out for `pilot-01` to `pilot-08`, 12 sessions each, with the **planned** condition and
perturbation from this protocol. Consent and issue are left **blank on purpose**: the operator fills them for every session that
happened, deletes the rows of anyone who did not take part, and changes a condition only if that is what really happened.
Codes only, no free text, no names. A printable one-page version of the whole evening: `docs/pilot/CHECKLIST.md`.

Sheet header (once, in the commit message or at the top of the PR): laptop model, keyboard (built-in or external, layout), date.

| Column | Values |
|---|---|
| `pseudonym` | `pilot-01` ... `pilot-08` |
| `consent` | `yes` (only people who said yes have rows at all) |
| `session_number` | `1` to `12`, the order the sessions were submitted |
| `condition` | `normal` or `perturbed` |
| `perturbation` | `none`, `non_dominant_hand` or `counting_backwards` |
| `issue` | `none`, `redone` (an earlier attempt was discarded), `interrupted` (something happened but the session was kept), `other` |

Example (one volunteer, abbreviated):

| pseudonym | consent | session_number | condition | perturbation | issue |
|---|---|---|---|---|---|
| pilot-01 | yes | 1 | normal | none | none |
| ... | | | | | |
| pilot-01 | yes | 9 | perturbed | non_dominant_hand | none |
| pilot-01 | yes | 10 | perturbed | non_dominant_hand | redone |
| pilot-01 | yes | 11 | perturbed | non_dominant_hand | none |
| pilot-01 | yes | 12 | normal | none | none |

## 6. Limits to state with the results

- Small: 5 to 8 people, 12 sessions each, all in one sitting. Real day-to-day variation (sleep, time of day, mood) is not covered.
- The perturbations are artificial. Flagging them shows the prototype notices a deliberate change in typing, not that it notices
  anything about health.
- One laptop and keyboard, mostly a team's friends and colleagues: not a representative sample of anyone, least of all crews.
- Practice still matters after one practice run: people get faster over the first sessions.
