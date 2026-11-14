/**
 * Mission view: renders GET /api/mission.
 * The advisory logic lives on the server (app/mission.py, task L-1).
 * Owner: Team Lead.
 */
import { api, bandChip, esc } from "./common.js";

const $ = (id) => document.getElementById(id);

async function load() {
  const m = await api("/api/mission");
  $("mission-name").textContent = m.name;
  $("mission-op").textContent = `Critical operation: ${m.critical_operation}`;
  $("tminus").textContent = `T-${m.t_minus_hours}h`;

  $("assignments").innerHTML = m.assignments.map((a) => `
    <tr class="${a.critical ? "critical-row" : ""}">
      <td>${esc(a.role)}</td>
      <td><a href="/dashboard?crew=${encodeURIComponent(a.profile_id)}">${esc(a.display_name)}</a></td>
      <td>${a.critical ? "Yes" : "No"}</td>
      <td>${bandChip(a)}</td>
      <td>${esc(a.confidence)}</td>
      <td class="small">${esc(a.reasons[0] || "None")}</td>
    </tr>`).join("");

  const adv = m.advisory;
  const levelClass = { NOMINAL: "green", CHECK_IN: "yellow", REVIEW: "red" }[adv.level] || "calibrating";
  $("advisory").innerHTML = `
    <p><span class="chip chip-${levelClass}">${esc(adv.level)}</span></p>
    <ul class="reasons">${adv.messages.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    ${adv.suggested_actions.length
      ? `<h3 class="cap">Suggested actions</h3><ul class="reasons">${adv.suggested_actions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`
      : ""}`;
}

load().catch((err) => {
  $("assignments").innerHTML = `<tr><td colspan="6" class="error">Could not load: ${esc(err.message)}</td></tr>`;
});
