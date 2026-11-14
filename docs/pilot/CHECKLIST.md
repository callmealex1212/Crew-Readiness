# Pilot night: one-page checklist (print me)

Full protocol and consent text: `docs/PILOT.md`. A small pilot with deliberate perturbations, **not** a validation or a health test.

**Once, before anyone arrives**
- [ ] `[CONTACT]` and `[DEADLINE FOR WITHDRAWAL]` filled in the consent text (`docs/PILOT.md` section 4)
- [ ] One laptop, one keyboard, one layout; notifications off; note laptop and keyboard for the PR
- [ ] Terminal 1: `export CREW_DB_PATH=instance/pilot.sqlite3` then `python run.py` (PowerShell: `$env:CREW_DB_PATH="instance/pilot.sqlite3"`)
- [ ] Terminal 2, same `CREW_DB_PATH`: `flask --app run add-profile pilot-01 "Volunteer 01" Volunteer` ... up to `pilot-08`
- [ ] Paper list linking real names to pseudonyms: **paper only**, never typed anywhere

**Each volunteer (about 30 min)**
1. [ ] Read the consent text aloud. **No yes, no session.**
2. [ ] Perturbation: **odd** pseudonym = non-dominant hand; **even** = count backwards out loud by 3 (from 300, 250, 200)
3. [ ] Practice: `/monitor` > their pseudonym > Start task > type > **Discard** (not recorded)
4. [ ] 12 sessions, about 1 minute break between, **Submit timing features** each time; tick only after the result screen:

| Session | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | **9** | **10** | **11** | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Condition | n | n | n | n | n | n | n | n | **P** | **P** | **P** | n |
| Done | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Issue (code) | | | | | | | | | | | | |

n = normal, own hand(s), own pace. **P = perturbed.** Issue codes: `none`, `redone` (an attempt was discarded and repeated),
`interrupted` (kept despite a disturbance), `other`. Something went wrong? **Discard**, write `redone`, repeat the session.
5. [ ] Don't discuss GREEN/YELLOW/RED; press **Run again**. No real names, no free-text notes anywhere.

**After the last volunteer**
- [ ] `python scripts/export_pilot.py` (with `CREW_DB_PATH` still set) writes `docs/pilot/pilot_sessions.csv`
- [ ] In `docs/pilot/session_sheet.csv`: `consent` = `yes` and an `issue` code on every session that happened; **delete the rows of anyone who did not take part**; change a row's condition only if that is what really happened
- [ ] `python scripts/check_pilot_ready.py` until it says **READY** (it names each missing session per person)
- [ ] Never edit a number in the CSV. Commit both files to a branch (`feat/F2-pilot-data`), then `python -m ml.pilot_report`
