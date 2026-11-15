# Plan v3: simpler to use, closer to health, reliable enough for space (11 pm to 11 am)

Status: **DRAFT for Davud to approve.** Nothing here is built yet. Rules in `AGENTS.md` still apply (privacy, honest claims, no network, one grid).

## Where we are (honest)
Strong build, honest evidence, but: eight nav items that cross over (Monitoring, Attention, Replay, Dashboard...), health relevance is
argued rather than shown, and "reliability for space" is a claim, not a measurement. Estimated now: creativity 7.5, relevance 7.5,
impact 6.5, validity 8 (two volunteers), execution 8.5.

## What we will NOT do: "consciousness monitoring"
We cannot measure consciousness, and saying we do would be a clinical claim we cannot back, which costs validity points with any judge
who knows medicine. What we CAN build, and defend, are the two things that idea is really about:
1. **Responsiveness**: does this person respond as quickly and steadily as *they usually do*? (a short reaction check, compared with their own history)
2. **A missed check-in watchdog**: if someone has not checked in for longer than the agreed interval, someone should look in on them.
Both are named for what they are. Neither diagnoses anything.

## The plan: three blocks, nine items

### Block S: simplify (no feature removed, every URL keeps working)
| ID | What | Owner | Time | Risk |
|---|---|---|---|---|
| S1 | **Three doors.** Nav shrinks from 8 items to 4: *My check-in*, *Reviewer*, *Evidence*, *About*. Landing has two clear buttons: "I'm crew: check in" and "I'm a reviewer". Monitoring, Attention, Dashboard, Replay and the Brief stay, but are reached from inside those doors, not from the top bar | Claude | 2.5 h | low |
| S2 | **One check-in flow.** `/me` shows one button, *Start check-in*: the typed checklist, then an optional 30-second responsiveness check, then your own result. The crew member is carried through, never asked twice | Claude | 3 h | medium |

### Block H: closer to health (honest names, no diagnosis)
| ID | What | Owner | Time | Risk |
|---|---|---|---|---|
| H1 | **Responsiveness against your own baseline.** The reaction check already stores median response, early presses and misses. Compare each new check with the person's own earlier checks (same robust method as typing), in plain words: "usual 310 ms, today 390 ms". Shown on My status, Dashboard and the Brief. Tested on simulated people only; labelled not validated | Claude | 3 h | medium |
| H2 | **Missed check-in watchdog.** Mission gets an agreed check-in interval. Someone with no check-in for longer shows OVERDUE with the suggestion "look in on them in person"; it says nothing is necessarily wrong. Uses timestamps we already store | Claude | 2.5 h | low |
| H3 | **Private notes that never leave the device.** Optional "sleep last night" and "how alert I feel" on My status, kept in the browser only (never sent, never stored by the server), shown next to the person's own pattern, with a one-line "copy a summary to tell my reviewer or medical officer" they choose to use | Claude | 2 h | low (privacy rule kept: the server never sees it) |

### Block R: reliability for space (measured, not claimed)
| ID | What | Owner | Time | Risk |
|---|---|---|---|---|
| R1 | **"Health of the monitor" self-test.** A `/status` page and `flask selftest`: database writable, scoring gives the known answer on a fixed fixture, clock sane, no outside network, app version. The software checks itself | friend + Codex | 2 h | low |
| R2 | **Fault injection and a two-year soak.** 1000 malformed or hostile inputs: 0 crashes. Six simulated crew, 700 days, 3 sessions a day: scoring time per call, database size, memory. Numbers go into `app/reliability_data.json` (its own file, so no clash) and an Evidence "Reliability" section. Honest limit: run on an ordinary laptop, not flight hardware | friend + Codex, reviewed by Claude | 3 h | low |
| R3 | **Backup and restore.** `flask export-backup` / `import-backup` with a checksum; a corrupted file is refused. Tested | friend + Codex | 1.5 h | low |

### Block E: real evidence (humans)
| ID | What | Owner | Time |
|---|---|---|---|
| E1 | **Real gloves.** Davud and Alex each: 8 normal checklist sessions, then 5 with thin gloves (or oven mitts), accept the new normal on the dashboard, then 4 more. This turns the equipment story from simulated into a small real one. Claude adds the analysis once the CSV exists | Davud + Alex (40 min each); Claude analysis 1.5 h | 3 h total |
| E2 | **More volunteers** in the morning, 25 minutes each, using the existing runbook. Even 2 more changes "2 people" into "4 people" | Davud + Alex | open |

## Schedule (Baku time)
| When | What |
|---|---|
| 23:00 to 23:30 | Davud reviews this plan and answers the five questions below |
| 23:30 to 02:30 | Claude: S1, then H2 (fast, high value). friend + Codex: R1 and R3. Davud + Alex: E1 (gloves), the data may arrive while we build |
| 02:30 to 05:00 | Claude: S2, H1, H3, then E1 analysis. friend + Codex: R2 |
| **05:00** | **Feature freeze.** After this only fixes |
| 05:00 to 06:00 | Claude: full QA (tests, grid, keyboard, smoke, claims scan), merge order, deploy check. Humans: rest |
| 07:00 to 10:00 | Humans: record the demo (a new script will be ready by 06:00), rehearse twice, extra volunteers if wanted |
| 10:00 to 11:00 | Final smoke on the live URL, fill the placeholders, submit early |

**Cut order if we run late (cut from the top, never from the bottom):** H3, R3, S2 (keep S1), R2's soak (keep the fuzz), H1. **Never cut:** H2, R1, E1 analysis, QA, the claims scan, submission.

## Honest expected effect
| | Now | If all of it lands |
|---|---|---|
| Creativity | 7.5 | 8 (the watchdog, device-only notes, a real gloves test) |
| Relevance to space and health | 7.5 | 8 to 8.5 (responsiveness, watchdog, on-board self-test) |
| Impact | 6.5 | 7.5 |
| Validity and honesty | 8 | 8.5 (reliability measured; a real gloves test) |
| Reliability and execution | 8.5 | 9 |
Overall about 8 to 8.3. That makes a top 3 plausible, not likely to be certain. The plan is risky mainly because of time, not because of
claims: every item has an honest name and a stated limit.

## Risks and how we limit them
- **Scope creep and tiredness:** one item per branch and PR, tests and grid check as the gate, hard freeze at 05:00, a cut order above.
- **Breaking something that works:** nothing is deleted, only reorganised; URLs keep working; smoke runs against every page.
- **Privacy:** H3 stays in the browser; H1 and H2 use data we already store (reaction results and session times). No typed text, no new server-side personal field.
- **Claims:** every new page goes through the claims scan; no fatigue, consciousness, illness or fitness wording; each says what it cannot tell.
- **Vercel limits:** merge in batches (two or three PRs at a time), not one by one.

## Five questions for Davud
1. Do you accept the rename: **responsiveness and a missed check-in watchdog** instead of "consciousness monitoring"?
2. Do you accept **H3** (notes that stay only in the browser)? If you want them on the server, that is a privacy-rule change, and we recommend no.
3. Do you accept the **nav cut from 8 items to 4**, with everything still reachable?
4. Can you and Alex do **E1 (gloves)** tonight, around 40 minutes each?
5. Do you agree with the **05:00 freeze** and sleeping between 05:30 and 07:00?
