"""
Benchmark harness. A Detector sees a person's PAST sessions and today's features and returns a score,
or None while it is still calibrating. An alert is `score >= alert_threshold`.

  detector(history: list[dict], today: dict) -> float | None

The incumbent (median/MAD, as shipped) is `incumbent_detector`. Any candidate model is scored by the
same code on the same simulated people, so the comparison is fair.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.baseline import compute_baseline, select_baseline_sessions
from app.features import FEATURE_NAMES
from app.scoring import score_session
from app.tasks import DEFAULT_TASK_TYPE

from .synth import Event, PopulationSpec, simulate_person

Detector = Callable[[list, dict], "float | None"]


def incumbent_detector(history: list, today: dict) -> "float | None":
    """The product's current logic: median/MAD baseline over recent sessions, weighted deviation score."""
    baseline = compute_baseline(select_baseline_sessions(history), FEATURE_NAMES, DEFAULT_TASK_TYPE)
    view = score_session({n: today[n] for n in FEATURE_NAMES}, baseline, today["data_quality"])
    return view.score if view.status == "SCORED" else None


def _alerts(detector: Detector, sessions: list, threshold: float) -> list:
    """Per session: True/False alert, or None if the detector abstained (calibrating)."""
    out = []
    for i, s in enumerate(sessions):
        score = detector(sessions[:i], s)
        out.append(None if score is None else score >= threshold)
    return out


@dataclass
class Result:
    magnitude: float
    n_people: int
    detection_rate: float        # share of event sessions that raised an alert
    first_alert_rate: float      # share of people who got at least one alert during the event
    median_delay: "float | None"  # sessions from event start to first alert (people who were alerted)
    false_alert_rate: float      # alerts per normal scored session (event-free people AND pre-event sessions)


def evaluate(detector: Detector, *, shape: str, magnitude: float, length: int, start: int = 15,
             n_sessions: int = 40, n_people: int = 200, alert_threshold: float = 1.0, seed: int = 0,
             pop: PopulationSpec = PopulationSpec()) -> Result:
    rng = np.random.default_rng(seed)
    ev = Event(shape=shape, start=start, length=length, magnitude=magnitude)
    hit = ev_total = alerted_people = 0
    delays, fa, normal = [], 0, 0
    for _ in range(n_people):
        sessions, truth = simulate_person(rng, n_sessions, pop, events=(ev,))
        alerts = _alerts(detector, sessions, alert_threshold)
        first = None
        for i, (a, t) in enumerate(zip(alerts, truth)):
            if a is None:
                continue
            if t > 0:
                ev_total += 1
                hit += bool(a)
                if a and first is None:
                    first = i - start
            elif i < start:   # pre-event only, so later contamination is not counted as a false alarm
                normal += 1
                fa += bool(a)
        alerted_people += first is not None
        if first is not None:
            delays.append(first)
    return Result(magnitude, n_people, hit / max(ev_total, 1), alerted_people / n_people,
                  float(np.median(delays)) if delays else None, fa / max(normal, 1))


def evaluate_ci(detector: Detector, *, shape: str, magnitude: float, length: int, start: int = 15, n_sessions: int = 40,
                n_people: int = 200, alert_threshold: float = 1.0, seed: int = 0, pop: PopulationSpec = PopulationSpec(),
                n_boot: int = 1000) -> dict:
    """Same simulation and the same point estimates as `evaluate`, plus 95 % bootstrap intervals over PEOPLE (not sessions):
    resample the simulated people with replacement and recompute the pooled rates."""
    rng = np.random.default_rng(seed)
    ev = Event(shape=shape, start=start, length=length, magnitude=magnitude)
    rows = []                                          # per person: event hits, event sessions, false alerts, normal sessions
    for _ in range(n_people):
        sessions, truth = simulate_person(rng, n_sessions, pop, events=(ev,))
        alerts = _alerts(detector, sessions, alert_threshold)
        h = n_ev = fa = n_norm = 0
        for i, (a, t) in enumerate(zip(alerts, truth)):
            if a is None:
                continue
            if t > 0:
                n_ev += 1; h += bool(a)
            elif i < start:
                n_norm += 1; fa += bool(a)
        rows.append((h, n_ev, fa, n_norm))
    r = np.array(rows, dtype=float)
    det = r[:, 0].sum() / max(r[:, 1].sum(), 1)
    far = r[:, 2].sum() / max(r[:, 3].sum(), 1)
    boot = np.random.default_rng(seed + 10_000)
    dets, fars = [], []
    for _ in range(n_boot):
        s = r[boot.integers(0, len(r), len(r))]
        dets.append(s[:, 0].sum() / max(s[:, 1].sum(), 1)); fars.append(s[:, 2].sum() / max(s[:, 3].sum(), 1))
    q = lambda v: [round(float(np.quantile(v, .025)), 4), round(float(np.quantile(v, .975)), 4)]
    return {"detection": float(det), "false_alerts": float(far), "detection_ci": q(dets), "false_alerts_ci": q(fars)}
