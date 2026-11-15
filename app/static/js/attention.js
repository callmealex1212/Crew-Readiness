/**
 * Reaction-time attention check (task A-1). Optional, illustrative, not a medical test.
 *
 * SPEC:
 *   - 10 trials.
 *   - Each trial: wait a RANDOM foreperiod of 1500-4000 ms (random so people
 *     can't anticipate the rhythm), then light up #rt-stage.
 *   - Response = click on #rt-stage OR Space key.
 *   - Reaction time = performance.now() at response - performance.now() at stimulus.
 *   - Response BEFORE the stimulus = premature (count it, restart that trial's wait).
 *   - No response within 1500 ms after the stimulus = miss.
 *   - Responses faster than 100 ms after stimulus are physiologically implausible
 *     (faster than a person can see and react, so they were anticipated, not
 *     reactions): treat them as premature.
 *   - Summary: median RT of valid trials (null if none), premature_count, miss_count.
 *   - POST to /api/attention:
 *       { profile_id, trials: 10, median_rt_ms, premature_count, miss_count }
 *   - Show the summary with the label "Illustrative reaction-time check. Not a medical test."
 *
 * PRIVACY: only the four summary numbers above are sent. Individual reaction
 * times stay in this page's memory and are dropped when the check ends.
 *
 * DESIGN: a small state machine, idle -> waiting -> stimulus -> (waiting | done),
 * with ONE timer handle that is cleared on every state change (no ghost trials).
 * Escape cancels a run without sending anything.
 */
import { api, esc } from "./common.js";
import { median } from "./capture.js";

export const TRIALS = 10;
export const FOREPERIOD_MS = [1500, 4000];
export const MISS_AFTER_MS = 1500;
export const MIN_VALID_RT_MS = 100;

const select = document.getElementById("profile-select");
const startBtn = document.getElementById("rt-start");
const stage = document.getElementById("rt-stage");
const message = document.getElementById("rt-message");
const progress = document.getElementById("rt-progress");
const result = document.getElementById("rt-result");

let state = "idle";          // idle | waiting | stimulus | done
let timer = null;            // the only timer handle
let shownAt = 0;             // performance.now() when the stimulus appeared
let trial = 0;               // completed trials (valid or miss)
let rts = [];                // valid reaction times, in memory only
let premature = 0;
let misses = 0;

function clearTimer() {
  if (timer !== null) clearTimeout(timer);
  timer = null;
}

function say(text) { message.textContent = text; }

function showProgress() {
  progress.textContent = `Trial ${Math.min(trial + 1, TRIALS)} of ${TRIALS}`;
}

function setRunning(running) {
  startBtn.disabled = running;
  select.disabled = running;
  progress.hidden = !running;
}

function wait(note) {
  clearTimer();
  state = "waiting";
  stage.classList.remove("rt-go");
  showProgress();
  say(note || "Wait for the light…");
  const [lo, hi] = FOREPERIOD_MS;
  timer = setTimeout(showStimulus, lo + Math.random() * (hi - lo));
}

function showStimulus() {
  clearTimer();
  state = "stimulus";
  stage.classList.add("rt-go");
  say("Now!");
  shownAt = performance.now();
  timer = setTimeout(onMiss, MISS_AFTER_MS);
}

function onMiss() {
  misses += 1;
  nextTrial("Missed. Wait for the next light…");
}

function nextTrial(note) {
  trial += 1;
  if (trial >= TRIALS) finish();
  else wait(note);
}

function respond() {
  if (state === "waiting") {
    premature += 1;
    wait("Too early. Wait for the light…");
  } else if (state === "stimulus") {
    const rt = performance.now() - shownAt;
    if (rt < MIN_VALID_RT_MS) {
      premature += 1;
      wait("Too early. Wait for the light…");
    } else {
      rts.push(rt);
      nextTrial();
    }
  }
}

function start() {
  if (!select.value) return;
  clearTimer();
  trial = 0; rts = []; premature = 0; misses = 0;
  result.hidden = true;
  result.innerHTML = "";
  setRunning(true);
  stage.focus();
  wait();
}

function cancel() {
  clearTimer();
  state = "idle";
  stage.classList.remove("rt-go");
  setRunning(false);
  rts = [];
  say("Cancelled. Nothing was sent. Press Start to try again.");
  startBtn.focus();
}

async function finish() {
  clearTimer();
  state = "done";
  stage.classList.remove("rt-go");
  setRunning(false);
  const summary = {
    profile_id: select.value,
    trials: TRIALS,
    median_rt_ms: rts.length ? Math.round(median(rts)) : null,
    premature_count: premature,
    miss_count: misses,
  };
  rts = [];
  say("Done. Press Start to run it again.");
  let saved = "Saved.";
  try {
    const saved_resp = await api("/api/attention", { method: "POST", body: JSON.stringify(summary) }); summary.__resp = saved_resp.responsiveness;
  } catch (err) {
    saved = `Not saved: ${err.message}`;
  }
  renderResult(summary, saved);
  startBtn.focus();
}

function renderResult(s, saved) {
  const valid = s.trials - s.miss_count;
  const rt = s.median_rt_ms === null ? "no valid trials" : `${s.median_rt_ms} ms`;
  result.innerHTML = `
    <p><strong>Illustrative reaction-time check. Not a medical test.</strong></p>
    <ul class="reasons">
      <li>Median reaction time: <span class="num">${esc(rt)}</span></li>
      <li>Valid trials: <span class="num">${valid} of ${s.trials}</span></li>
      <li>Too early: <span class="num">${s.premature_count}</span></li>
      <li>Missed: <span class="num">${s.miss_count}</span></li>
    </ul>
    ${s.__resp ? `<p>${esc(s.__resp.summary)}</p>${(s.__resp.reasons || []).length ? `<ul class="reasons">${s.__resp.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}` : ""}
    <p class="fineprint">${esc(saved)} Only these four numbers are stored, as context for a human reviewer.</p>
    <p><a class="btn" href="/me?crew=${encodeURIComponent(select.value)}">Back to my status</a></p>`;
  result.hidden = false;
}

startBtn.addEventListener("click", start);

// pointerdown, not click: a click fires on release, which would add the
// press duration to every reaction time.
stage.addEventListener("pointerdown", (e) => {
  if (e.button !== 0) return;
  e.preventDefault();
  respond();
});

document.addEventListener("keydown", (e) => {
  if (state !== "waiting" && state !== "stimulus") return;
  if (e.key === "Escape") { e.preventDefault(); cancel(); return; }
  if (e.code !== "Space" && e.key !== " ") return;
  e.preventDefault(); // no page scroll, no button activation
  if (e.repeat) return; // holding Space down is not a new response
  respond();
});

// A hidden tab cannot see the light; don't count that as misses.
document.addEventListener("visibilitychange", () => {
  if (document.hidden && (state === "waiting" || state === "stimulus")) {
    cancel();
    say("Paused because the tab was hidden. Nothing was sent. Press Start to try again.");
  }
});

async function loadProfiles() {
  const { profiles } = await api("/api/profiles");
  select.innerHTML = profiles
    .map((p) => `<option value="${esc(p.id)}">${esc(p.display_name)} (${esc(p.mission_role)})</option>`)
    .join("");
  const preselect = new URLSearchParams(location.search).get("crew");
  if (preselect && profiles.some((p) => p.id === preselect)) select.value = preselect;
  startBtn.disabled = profiles.length === 0;
}

loadProfiles().catch((err) => {
  select.innerHTML = `<option value="">Error: ${esc(err.message)}</option>`;
});
