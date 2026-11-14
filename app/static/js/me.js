/**
 * "My status": a person's own readiness, in plain words, before anyone else's.
 * Data: GET /api/profiles and GET /api/readiness/<id> (shapes: docs/DATA_CONTRACT.md). Nothing here is invented, and nothing
 * here says why a change happened or anything about health: it says what differs from the person's OWN usual pattern.
 */
import { api, bandChip, esc } from "./common.js";
import { createRidgeline } from "./ridgeline.js";

const $ = (id) => document.getElementById(id);
const art = createRidgeline($("me-ridge"), $("me-axis"), $("me-readout"));
const check = (id) => `<a href="/attention?crew=${encodeURIComponent(id)}">Take the optional one-minute reaction check</a> for extra context.`;

function sentence(r) {
  if (r.status === "INSUFFICIENT_DATA") return "No sessions yet. Do a checklist to start building your pattern.";
  if (r.status === "CALIBRATING") return `Still learning your usual pattern: ${r.baseline_n} of ${r.baseline_needed} sessions so far. No status is shown until then.`;
  return { GREEN: "Today looks like your usual pattern.", YELLOW: "Today differs a little from your usual pattern.", RED: "Today differs a lot from your usual pattern." }[r.band];
}

function actions(r, id) {
  if (r.status !== "SCORED") return ["Keep doing your checklists. Each one helps the software learn your usual pattern."];
  if (r.band === "GREEN") return ["Nothing to do. Each checklist you finish keeps your pattern up to date."];
  const a = [check(id)];
  a.push(r.band === "RED"
    ? "Consider letting your reviewer know and asking for a second pair of eyes before the critical operation. That choice is yours and theirs, not the software's."
    : "If you want, mention it to your reviewer. Whether to share is your choice.");
  return a;
}

async function show(id) {
  history.replaceState(null, "", `?crew=${encodeURIComponent(id)}`);
  try {
    const data = await api(`/api/readiness/${encodeURIComponent(id)}`);
    const r = data.readiness;
    $("me-body").hidden = false;
    $("me-chip").innerHTML = bandChip(r);
    $("me-sentence").textContent = sentence(r);
    $("me-meta").textContent = r.status === "SCORED"
      ? `Compared with your ${r.baseline_n} earlier session${r.baseline_n === 1 ? "" : "s"} (confidence ${r.confidence}).` : "";
    const why = r.status === "SCORED" ? r.reasons : [];
    $("me-reasons").innerHTML = why.length ? why.map((x) => `<li>${esc(x)}</li>`).join("")
      : `<li class="muted">${r.status === "SCORED" ? "Nothing is notably different from your usual." : "Nothing to compare yet."}</li>`;
    let acts = actions(r, id).map((x) => `<li>${x.startsWith("<a") ? x : esc(x)}</li>`);
    if (data.baseline_review) acts.unshift(`<li>${esc(data.baseline_review.message)} A reviewer can do that on the dashboard.</li>`);
    $("me-actions").innerHTML = acts.join("");
    art.setSessions(data.trend, r.band);
  } catch (err) {
    $("me-sentence").textContent = `Could not load: ${err.message}`;
    $("me-body").hidden = false;
  }
}

(async () => {
  try {
    const { profiles } = await api("/api/profiles");
    const sel = $("me-select");
    sel.innerHTML = profiles.map((p) => `<option value="${esc(p.id)}">${esc(p.display_name)} (${esc(p.mission_role)})</option>`).join("");
    const wanted = new URLSearchParams(location.search).get("crew");
    if (wanted && profiles.some((p) => p.id === wanted)) sel.value = wanted;
    sel.addEventListener("change", () => show(sel.value));
    show(sel.value);
  } catch (err) {
    $("me-select").innerHTML = `<option>Could not load: ${esc(err.message)}</option>`;
  }
})();
