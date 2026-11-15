/**
 * Private notes on "My status" (plan v3, H3). PRIVACY BY CONSTRUCTION: these notes live only in this browser's localStorage.
 * This file makes NO network request of any kind (no fetch, no XMLHttpRequest, no beacon, no api() helper); a test checks that.
 * The numbers are never used in the person's status. "Copy a summary" puts text on the clipboard that the PERSON chooses to share.
 */
const $ = (id) => document.getElementById(id);
const KEEP = 30;
const key = () => `crew-readiness-notes-v1:${$("me-select").value}`;

function load() {
  try { const v = JSON.parse(localStorage.getItem(key()) || "[]"); return Array.isArray(v) ? v : []; } catch { return null; }   // null: storage unavailable
}
function save(list) {
  try { localStorage.setItem(key(), JSON.stringify(list.slice(-KEEP))); return true; } catch { return false; }
}
const say = (msg) => { $("notes-status").textContent = msg; };
const num = (v) => (v === "" || v === null || Number.isNaN(Number(v)) ? null : Number(v));

function render() {
  const list = load();
  if (list === null) { say("This browser is not letting the page save notes, so notes are switched off here."); $("notes-save").disabled = true; return; }
  $("notes-save").disabled = false;
  $("notes-rows").innerHTML = list.slice(-5).reverse().map((n) =>
    `<tr><td>${new Date(n.t).toLocaleString()}</td><td class="num">${n.sleep ?? "not said"}</td><td class="num">${n.feel ?? "not said"}</td></tr>`).join("");
  $("notes-table-wrap").hidden = list.length === 0;
}

function onSave() {
  const sleep = num($("notes-sleep").value), feel = num($("notes-feel").value);
  if (sleep !== null && (sleep < 0 || sleep > 24)) { say("Sleep hours must be between 0 and 24."); return; }
  if (sleep === null && feel === null) { say("Nothing to save: add the hours you slept or how you feel."); return; }
  const list = load() || [];
  list.push({ t: new Date().toISOString(), sleep, feel });
  say(save(list) ? "Saved on this device only. Nothing was sent." : "Could not save in this browser.");
  $("notes-sleep").value = ""; $("notes-feel").value = "";
  render();
}

function summary() {
  const sel = $("me-select"), who = sel.options[sel.selectedIndex]?.text || "this crew member";
  const list = load() || [], last = list[list.length - 1];
  const notes = last ? `slept ${last.sleep ?? "not said"} hours; feeling ${last.feel ?? "not said"} out of 9 (1 very low, 9 very high)` : "no note saved";
  return [`Check-in summary for ${who}, prepared by me on ${new Date().toLocaleString()}.`,
    `Typing: ${$("me-sentence").textContent.trim()}`, `Reaction check: ${$("me-resp-sentence").textContent.trim() || "none yet"}`,
    `My note: ${notes}.`,
    "This is my own summary. The software did not send it, it does not say why anything changed, and it is not a medical assessment."].join("\n");
}

async function onCopy() {
  const text = summary();
  try { await navigator.clipboard.writeText(text); say("Summary copied. Paste it where you choose to share it."); }
  catch {
    const ta = document.createElement("textarea"); ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove(); say(ok ? "Summary copied. Paste it where you choose to share it." : "Could not copy. Select the text above and copy it yourself.");
  }
}

function onClear() {
  try { localStorage.removeItem(key()); } catch { /* nothing to remove */ }
  say("Your notes on this device were deleted."); render();
}

$("notes-save").addEventListener("click", onSave);
$("notes-copy").addEventListener("click", onCopy);
$("notes-clear").addEventListener("click", onClear);
$("me-select").addEventListener("change", () => { say(""); render(); });
document.addEventListener("me:shown", render);      // fired once the person is chosen and their status has loaded
