/**
 * Reaction-time attention check: TASK A-1 (Member 4, or Member 3 if we are three).
 *
 * SPEC (agree changes with the team lead first):
 *   - 10 trials.
 *   - Each trial: wait a RANDOM foreperiod of 1500-4000 ms (random so people
 *     can't anticipate the rhythm), then light up #rt-stage.
 *   - Response = click on #rt-stage OR Space key.
 *   - Reaction time = performance.now() at response - performance.now() at stimulus.
 *   - Response BEFORE the stimulus = premature (count it, restart that trial's wait).
 *   - No response within 1500 ms after the stimulus = miss.
 *   - Responses faster than 100 ms after stimulus are physiologically implausible:
 *     treat them as premature. (Think about why!)
 *   - Summary: median RT of valid trials (null if none), premature_count, miss_count.
 *   - POST to /api/attention:
 *       { profile_id, trials: 10, median_rt_ms, premature_count, miss_count }
 *   - Show the summary with the label "Illustrative reaction-time check. Not a medical test."
 *
 * HINTS:
 *   - Model it as a small state machine: idle -> waiting -> stimulus -> (next | done).
 *   - Keep ONE timer handle and clear it on every state change, or you'll get ghost trials.
 *   - Reuse `median` from ./capture.js and `api` from ./common.js.
 *
 * STRETCH: compare the result with the person's own previous attention results.
 */
import { api, esc } from "./common.js";
import { median } from "./capture.js";

const select = document.getElementById("profile-select");
const startBtn = document.getElementById("rt-start");
const stage = document.getElementById("rt-stage");
const message = document.getElementById("rt-message");
const result = document.getElementById("rt-result");

const TRIALS = 10;
const FOREPERIOD_MIN_MS = 1500;
const FOREPERIOD_MAX_MS = 4000;
const RESPONSE_WINDOW_MS = 1500;
const MIN_VALID_RT_MS = 100;

let state = "idle";
let timer = null;
let trial = 0;
let stimulusAt = null;
let validRts = [];
let prematureCount = 0;
let missCount = 0;

function clearTimer() {
  if (timer !== null) window.clearTimeout(timer);
  timer = null;
}

function setMessage(text) {
  message.textContent = text;
}

function foreperiod() {
  return FOREPERIOD_MIN_MS + Math.random() * (FOREPERIOD_MAX_MS - FOREPERIOD_MIN_MS);
}

function resetStage() {
  stage.classList.remove("rt-go");
  stage.setAttribute("aria-pressed", "false");
}

function waitForStimulus(note = "") {
  clearTimer();
  resetStage();
  state = "waiting";
  setMessage(note || `Trial ${trial + 1} of ${TRIALS}. Wait for the box to light up.`);
  timer = window.setTimeout(showStimulus, foreperiod());
}

function showStimulus() {
  state = "stimulus";
  stimulusAt = performance.now();
  stage.classList.add("rt-go");
  stage.setAttribute("aria-pressed", "true");
  setMessage("NOW — click this box or press Space.");
  timer = window.setTimeout(recordMiss, RESPONSE_WINDOW_MS);
}

function recordPremature() {
  prematureCount += 1;
  waitForStimulus(`Too early. Trial ${trial + 1} of ${TRIALS} will restart.`);
}

function nextTrial() {
  trial += 1;
  if (trial === TRIALS) finish();
  else waitForStimulus();
}

function recordMiss() {
  clearTimer();
  resetStage();
  missCount += 1;
  nextTrial();
}

function respond() {
  if (state === "waiting") {
    recordPremature();
    return;
  }
  if (state !== "stimulus") return;

  const reactionTime = performance.now() - stimulusAt;
  clearTimer();
  resetStage();
  if (reactionTime < MIN_VALID_RT_MS) {
    recordPremature();
    return;
  }
  validRts.push(reactionTime);
  nextTrial();
}

function formatMilliseconds(value) {
  return `${Math.round(value)} ms`;
}

async function finish() {
  clearTimer();
  state = "submitting";
  resetStage();
  const medianRt = validRts.length ? median(validRts) : null;
  setMessage("Saving the illustrative result…");
  try {
    await api("/api/attention", {
      method: "POST",
      body: JSON.stringify({
        profile_id: select.value,
        trials: TRIALS,
        median_rt_ms: medianRt,
        premature_count: prematureCount,
        miss_count: missCount,
      }),
    });
    state = "done";
    const medianText = medianRt === null ? "No valid response time" : `Median response time: ${formatMilliseconds(medianRt)}`;
    result.textContent = `${medianText}. Premature responses: ${prematureCount}. Missed trials: ${missCount}. Illustrative reaction-time check. Not a medical test.`;
    result.hidden = false;
    setMessage("Check complete. Your result has been saved.");
    startBtn.textContent = "Start again (10 trials)";
    startBtn.disabled = false;
    select.disabled = false;
  } catch (err) {
    state = "idle";
    setMessage(`Could not save the result: ${err.message}. Please try again.`);
    startBtn.textContent = "Try again (10 trials)";
    startBtn.disabled = false;
    select.disabled = false;
  }
}

async function loadProfiles() {
  const { profiles } = await api("/api/profiles");
  select.innerHTML = profiles
    .map((p) => `<option value="${esc(p.id)}">${esc(p.display_name)} (${esc(p.mission_role)})</option>`)
    .join("");
  const preselect = new URLSearchParams(location.search).get("crew");
  if (preselect) select.value = preselect;
  startBtn.disabled = false;
}

startBtn.addEventListener("click", () => {
  clearTimer();
  trial = 0;
  validRts = [];
  prematureCount = 0;
  missCount = 0;
  result.hidden = true;
  startBtn.disabled = true;
  select.disabled = true;
  stage.focus();
  waitForStimulus();
});

stage.addEventListener("click", respond);
document.addEventListener("keydown", (event) => {
  if (event.code !== "Space" || (state !== "waiting" && state !== "stimulus")) return;
  event.preventDefault();
  respond();
});

loadProfiles().catch((err) => {
  select.innerHTML = `<option>Error: ${esc(err.message)}</option>`;
});
