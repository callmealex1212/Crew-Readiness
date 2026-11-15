/**
 * Health of the monitor (task R1): renders GET /api/selftest. Status is a word first (PASS / FAIL), colour second.
 */
import { api, esc } from "./common.js";

const $ = (id) => document.getElementById(id);

function chip(ok) {
  return `<span class="chip ${ok ? "chip-green" : "chip-red"}">${ok ? "PASS" : "FAIL"}</span>`;
}

(async () => {
  try {
    const r = await api("/api/selftest");
    const failed = r.checks.filter((c) => !c.ok).length;
    $("st-summary").textContent = r.ok
      ? `All ${r.checks.length} checks passed.`
      : `${failed} of ${r.checks.length} checks failed. See the reasons below.`;
    $("st-checks").innerHTML = r.checks.map((c) =>
      `<li>${chip(c.ok)} <strong>${esc(c.name)}.</strong> <span class="muted">${esc(c.detail)}</span></li>`).join("");
    $("st-meta").textContent = `Checked ${r.checked_at.replace("T", " ").replace("Z", " UTC")} · ${r.version}`;
    $("st-limits").textContent = r.does_not_show;
  } catch (err) {
    $("st-summary").textContent = `The self-test could not run: ${err.message}`;
  }
})();
