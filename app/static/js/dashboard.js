/**
 * Dashboard: crew selector, the stacked-sessions art, and the evidence behind it.
 * Owner: Member 3 (Frontend & UX).
 *
 * Data: GET /api/readiness (everyone, for the selector) and
 *       GET /api/readiness/<id> (one person, with trend + per-feature deviations).
 * Shapes: docs/DATA_CONTRACT.md.
 */
import { api, bandChip, esc, timeAgo } from "./common.js";
import { createRidgeline } from "./ridgeline.js";
import { tokens } from "./tokens.js";

const $ = (id) => document.getElementById(id);
const list = $("crew-list");
const detail = $("detail");
const art = createRidgeline($("ridge"), $("art-axis"), $("art-readout"));
let chart = null;
let selectedId = null;

const SEVERITY = { RED: 3, YELLOW: 2 };
const markClass = (r) => `m-${(r.band || "calibrating").toLowerCase()}`;

function item(entry) {
  const r = entry.readiness;
  const p = entry.profile;
  const score = r.status === "SCORED"
    ? r.score.toFixed(2)
    : `${r.baseline_n}/${r.baseline_needed}`;
  return `
    <button class="crew-item" data-id="${esc(p.id)}" aria-pressed="false">
      <span class="mark ${markClass(r)}" aria-hidden="true"></span>
      <span class="who">${esc(p.display_name)}</span>
      <span class="chipcell">${bandChip(r)}</span>
      <span class="role">${esc(p.mission_role)}</span>
      <span class="score">${esc(score)}</span>
    </button>`;
}

function mark(id) {
  list.querySelectorAll(".crew-item").forEach((el) => {
    const on = el.dataset.id === id;
    el.setAttribute("aria-pressed", String(on));
  });
}

// ---- score-over-time chart: hairline, no fills ----
function renderTrend(trend) {
  const T = tokens();
  const points = trend.filter((t) => t.score !== null);
  const cutoffs = {
    id: "cutoffs",
    beforeDatasetsDraw(c) {
      const { ctx, chartArea: a, scales: { y } } = c;
      ctx.save();
      ctx.strokeStyle = T.line; ctx.setLineDash([2, 4]); ctx.lineWidth = 1;
      [1, 2].forEach((v) => {
        const py = y.getPixelForValue(v);
        ctx.beginPath(); ctx.moveTo(a.left, py); ctx.lineTo(a.right, py); ctx.stroke();
      });
      ctx.restore();
    },
  };
  const bandColor = { GREEN: T.GREEN, YELLOW: T.YELLOW, RED: T.RED };
  if (chart) chart.destroy();
  Chart.defaults.font.family = T.font;
  Chart.defaults.color = T.muted;
  chart = new Chart($("trend-chart"), {
    type: "line",
    data: {
      labels: points.map((t) => new Date(t.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })),
      datasets: [{
        data: points.map((t) => t.score),
        borderColor: T.ink, borderWidth: 1.5, tension: 0,
        pointBackgroundColor: points.map((t) => bandColor[t.band]),
        pointBorderWidth: 0, pointRadius: 4,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      scales: {
        y: { min: 0, max: 3, ticks: { stepSize: 1, font: { size: 11 } }, grid: { display: false }, border: { display: false } },
        x: { ticks: { font: { size: 11 }, maxRotation: 0, autoSkip: true }, grid: { display: false }, border: { color: T.line } },
      },
      plugins: { legend: { display: false }, tooltip: { displayColors: false, backgroundColor: T.surface, borderColor: T.line, borderWidth: 1 } },
    },
    plugins: [cutoffs],
  });
}

const fmt = (value, unit) => (unit === "ms" ? `${Math.round(value)} ms` : `${Math.round(value * 10) / 10}`);

function renderDetail(data) {
  const p = data.profile;
  const r = data.readiness;
  detail.hidden = false;
  $("detail-name").textContent = p.display_name;
  $("detail-meta").textContent =
    `${p.mission_role} · baseline ${r.baseline_n} session${r.baseline_n === 1 ? "" : "s"} · confidence ${r.confidence}` +
    (data.latest_session?.data_quality === "low" ? " · latest session low quality" : "");
  $("detail-chip").innerHTML = bandChip(r);
  $("detail-advisory").textContent = r.advisory;
  $("detail-disclaimer").textContent = r.disclaimer;
  const review = data.baseline_review;
  $("detail-review").hidden = !review;
  if (review) {
    $("detail-review-text").textContent = review.message;
    $("detail-review-note").textContent = "Accepting restarts this person's baseline from these sessions. It is a human decision, stored with a timestamp (the prototype has no user accounts, so not who).";
    $("detail-accept").dataset.profile = p.id;
  }
  $("detail-reasons").innerHTML = r.reasons.length
    ? r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")
    : `<li class="muted">No signal is notably different from usual.</li>`;
  $("detail-evidence").innerHTML = r.deviations.map((d) => `
    <tr>
      <td>${esc(d.label)}</td>
      <td class="num">${fmt(d.value, d.unit)}</td>
      <td class="num">${fmt(d.baseline_median, d.unit)}</td>
      <td class="num">${d.z >= 0 ? "+" : "−"}${Math.abs(d.z).toFixed(1)} SD</td>
      <td class="num">${d.deviation.toFixed(2)}</td>
    </tr>`).join("") || `<tr><td colspan="5" class="muted">Not enough baseline sessions yet.</td></tr>`;
  renderTrend(data.trend);
}

$("detail-accept").addEventListener("click", async (e) => {
  const id = e.currentTarget.dataset.profile;
  if (!id || !confirm("Accept the flagged sessions as this person's new normal? Their baseline will restart from these sessions, and until it has enough sessions it will show CALIBRATING.")) return;
  try {
    await api(`/api/readiness/${encodeURIComponent(id)}/accept-new-normal`, { method: "POST" });
    await select(id);
  } catch (err) {
    $("detail-review-note").textContent = `Could not accept: ${err.message}`;
  }
});

async function select(id) {
  selectedId = id;
  mark(id);
  history.replaceState(null, "", `?crew=${encodeURIComponent(id)}`);
  try {
    const data = await api(`/api/readiness/${encodeURIComponent(id)}`);
    if (id !== selectedId) return;            // a faster click won; ignore this response
    art.setSessions(data.trend, data.readiness.band);
    renderDetail(data);
  } catch (err) {
    detail.hidden = false;
    $("detail-advisory").textContent = `Could not load: ${err.message}`;
  }
}

async function init() {
  try {
    const { crew } = await api("/api/readiness");
    list.innerHTML = crew.map(item).join("");
    list.querySelectorAll(".crew-item").forEach((el) =>
      el.addEventListener("click", () => select(el.dataset.id)));
    const wanted = new URLSearchParams(location.search).get("crew");
    // default: whoever most needs a human's attention
    const byNeed = [...crew].sort((a, b) =>
      (SEVERITY[b.readiness.band] || 0) - (SEVERITY[a.readiness.band] || 0));
    select(crew.some((c) => c.profile.id === wanted) ? wanted : byNeed[0].profile.id);
  } catch (err) {
    list.innerHTML = `<p class="error small">Could not load crew: ${esc(err.message)}</p>`;
  }
}

init();
