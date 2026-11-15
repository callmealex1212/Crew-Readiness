"""
Smoke test for a RUNNING copy of the app (local or deployed). Standard library only.

    python scripts/smoke.py                                  # http://127.0.0.1:5050
    python scripts/smoke.py https://your-deployment.vercel.app

It is read-only except for one deliberately invalid POST (which must be rejected). Exit code 1 if anything fails, so it can
gate a submission. It checks what a judge would hit: every page loads, the data API has its contract, typed text is refused,
and the page text carries no claim we have ruled out.
"""
import json
import re
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5050").rstrip("/")
PAGES = ["/", "/me", "/dashboard", "/monitor", "/attention", "/mission", "/brief", "/replay", "/evidence", "/about", "/status"]
BANNED = ["detects fatigue", "% accurate", "nasa-approved and", "used by astronauts", "flight-proven", "tested in space"]
DENIES = re.compile(r"\bnot\b|\bno\b|\bnever\b|\bnothing\b|\bnor\b|\bwithout\b", re.I)
fails = []


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        fails.append(msg)


print(f"Smoke test: {BASE}")
try:
    get("/api/health")
except Exception as err:                      # connection refused, DNS failure, timeout
    print(f"Cannot reach {BASE}: {err}\nStart the app (python run.py) or pass the deployed URL as the first argument.")
    sys.exit(2)
for p in PAGES:
    status, html = get(p)
    check(status == 200, f"page {p} loads (HTTP {status})")
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html)).lower()
    for b in BANNED:     # a ruled-out claim is fine inside a sentence that DENIES it ("nothing here detects fatigue")
        bad_sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if b in s and not DENIES.search(s)]
        check(not bad_sentences, f"page {p} makes no claim '{b}'" + (f": {bad_sentences[0][:80]!r}" if bad_sentences else "")) if b in text else None
    own = re.sub(r"^https?://", "", BASE)
    others = {h for h in re.findall(r'(?:src|href)="https?://([^/"]+)', html) if h != own}
    check(not others, f"page {p} loads nothing from other hosts" + (f" (found {sorted(others)})" if others else ""))

status, body = get("/api/health")
check(status == 200 and '"ok"' in body, "API health is ok")
status, body = get("/api/readiness")
crew = json.loads(body).get("crew", []) if status == 200 else []
check(len(crew) >= 4, f"readiness lists the crew ({len(crew)} people)")
check(all("band" in c["readiness"] and "status" in c["readiness"] for c in crew), "every readiness has a status and a band field")
pilot = next((c for c in crew if c["profile"]["id"] == "plt-okafor"), None)
if pilot:
    s2, b2 = get("/api/readiness/plt-okafor")
    d = json.loads(b2) if s2 == 200 else {}
    check(d.get("readiness", {}).get("model") in ("nb-pause-v2", "robust-mad-v1"), "readiness says which scoring model produced it")
    check("baseline_review" in d, "readiness carries baseline_review (review flow)")
status, body = get("/api/simulate?scenario=step&seed=1")
check(status == 200 and json.loads(body).get("synthetic") is True, "replay simulation runs and is labelled synthetic")
status, body = get("/api/mission")
check(status == 200, "mission API responds")

bad = {"profile_id": "plt-okafor", "task_type": "docking_checklist_v1",
       "features": {"keystroke_count": 120, "iki_median_ms": 190, "iki_iqr_ms": 70, "pause_count": 1, "pause_total_ms": 2500,
                    "checklist_response_median_ms": 1500, "task_duration_ms": 45000, "correction_count": 2, "retry_count": 0,
                    "typed_text": "secret"}}
check(post("/api/sessions", bad) == 400, "a session carrying typed text is REJECTED (privacy rule)")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} CHECK(S) FAILED"))
sys.exit(1 if fails else 0)
