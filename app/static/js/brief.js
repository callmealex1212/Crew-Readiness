/**
 * Printable readiness brief: renders GET /api/mission for a human reviewer. The wording and levels come from the server
 * (app/mission.py); this file only lays them out. Nothing is stored.
 */
import { api, bandChip, esc } from "./common.js";

const $ = (id) => document.getElementById(id);

async function load() {
  const m = await api("/api/mission");
  $("brief-name").textContent = m.name;
  $("brief-op").textContent = `Critical operation: ${m.critical_operation}`;
  $("tminus").textContent = `T-${m.t_minus_hours}h`;
  $("brief-when").textContent = `Prepared ${new Date().toLocaleString()}. Advisory only.`;

  const adv = m.advisory;
  const cls = { NOMINAL: "green", CHECK_IN: "yellow", REVIEW: "red" }[adv.level] || "calibrating";
  $("brief-advisory").innerHTML = `<p><span class="chip chip-${cls}">${esc(adv.level.replace("_", " "))}</span></p>
    <ul class="reasons">${adv.messages.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    ${adv.suggested_actions.length ? `<h3 class="cap">Suggested</h3><ul class="reasons">${adv.suggested_actions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;

  const w = m.watchdog;
  $("brief-watchdog").innerHTML = `<p><span class="chip chip-${w.level === "OK" ? "green" : "yellow"}">${w.level === "OK" ? "ALL CHECKED IN" : "CHECK-IN OVERDUE"}</span>
    <span class="muted small">longest agreed gap ${esc(String(w.interval_hours))} hours</span></p>
    ${w.messages.length ? `<ul class="reasons">${w.messages.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${w.suggested_actions.length ? `<ul class="reasons">${w.suggested_actions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;

  const crit = m.assignments.filter((a) => a.critical);
  $("brief-critical").innerHTML = crit.map((a) => `
    <div class="brief-person">
      <h3 class="cap">${esc(a.role)}: ${esc(a.display_name)}</h3>
      <p>${bandChip(a)} <span class="muted small">confidence ${esc(String(a.confidence).toLowerCase())}</span></p>
      ${a.responsiveness && a.responsiveness.summary ? `<p class="small"><strong>Reaction check:</strong> ${esc(a.responsiveness.summary)}</p>` : ""}
      ${a.reasons.length ? `<ul class="reasons">${a.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`
        : `<p class="muted small">${a.status === "SCORED" ? "Nothing stands out against their own usual pattern." : "No baseline yet, so there is nothing to compare with."}</p>`}
    </div>`).join("") || '<p class="muted">No critical roles in this scenario.</p>';

  $("brief-other").innerHTML = m.assignments.filter((a) => !a.critical).map((a) =>
    `<tr><td>${esc(a.role)}</td><td>${esc(a.display_name)}</td><td>${bandChip(a)}</td></tr>`).join("");
}

$("brief-print").addEventListener("click", () => window.print());
load().catch((err) => { $("brief-advisory").innerHTML = `<p class="error">Could not load: ${esc(err.message)}</p>`; });
