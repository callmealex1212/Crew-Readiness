"""
Synthetic crews with INJECTED events, so every session has a ground-truth label.

Nothing here is real data. Every population number and every effect of an event is an
ILLUSTRATIVE ASSUMPTION (see PopulationSpec and EffectModel). Decision 2 in docs/ML_PLAN.md
asks the team to justify them from literature; until then, results must be labelled
"synthetic, illustrative assumptions".

An Event has NO defaults on purpose: its shape, size and length are the team's decision.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.features import FEATURE_NAMES


@dataclass(frozen=True)
class Event:
    shape: str        # "step" (constant for `length` sessions) | "ramp" (0 -> 1 over `length`) | "spike" (one session)
    start: int        # session index (0-based) where the event begins
    length: int       # sessions affected (ignored for "spike", which is 1)
    magnitude: float  # fractional slowdown at full strength, e.g. 0.10 = 10 % slower

    def strength(self, i: int) -> float:
        """0..1 multiplier of `magnitude` at session i."""
        if self.shape == "spike":
            return 1.0 if i == self.start else 0.0
        if not (self.start <= i < self.start + self.length):
            return 0.0
        if self.shape == "step":
            return 1.0
        if self.shape == "ramp":
            return (i - self.start + 1) / self.length
        raise ValueError(f"unknown shape {self.shape!r}")


@dataclass(frozen=True)
class PopulationSpec:
    """How people differ from each other. Illustrative; mirrors the demo crew in app/seed.py."""
    iki_ms: tuple[float, float] = (145.0, 230.0)       # per-person typical value drawn uniformly from this range
    iki_cv: float = 0.07                               # session-to-session variability (fraction of typical)
    iqr_ratio: float = 0.40                            # IQR as a fraction of iki
    pause_rate: tuple[float, float] = (0.4, 1.2)       # expected pauses per session
    resp_ms: tuple[float, float] = (1100.0, 1800.0)
    resp_cv: float = 0.11
    pause_overdispersion: float = 0.0                  # 0 = Poisson pauses; >0 = burstier (gamma-mixed rate, variance = mean*(1+od*mean))
    noise_sigma: float = 0.0                          # people differ in how erratic they are: per-person multiplier exp(N(0, sigma)) on the noise; 0 = everyone alike
    learning_per_session: float = 0.0                  # slow drift: fractional change per session (negative = getting faster)


@dataclass(frozen=True)
class EffectModel:
    """What an event does to the features. ASSUMPTION: a slowdown f scales timing and adds pauses."""
    pause_gain: float = 3.0   # pause rate is multiplied by (1 + pause_gain * f)


TASK_CHARS, TASK_ITEMS = 121, 7


def simulate_person(rng: np.random.Generator, n: int, pop: PopulationSpec = PopulationSpec(),
                    events: tuple[Event, ...] = (), effect: EffectModel = EffectModel()):
    """Return (sessions, truth). sessions: list of feature dicts. truth[i]: summed event strength at i (0 = normal)."""
    iki0 = rng.uniform(*pop.iki_ms)
    noise = float(np.exp(rng.normal(0.0, pop.noise_sigma))) if pop.noise_sigma > 0 else 1.0
    pause0 = rng.uniform(*pop.pause_rate)
    resp0 = rng.uniform(*pop.resp_ms)
    sessions, truth = [], []
    for i in range(n):
        f = sum(e.magnitude * e.strength(i) for e in events)
        drift = (1.0 + pop.learning_per_session) ** i
        iki = max(40.0, rng.normal(iki0, noise * pop.iki_cv * iki0) * drift) * (1 + f)
        iqr = max(5.0, rng.normal(pop.iqr_ratio * iki0, 0.15 * pop.iqr_ratio * iki0) * drift) * (1 + f)
        resp = max(300.0, rng.normal(resp0, noise * pop.resp_cv * resp0) * drift) * (1 + f)
        rate = pause0 * (1 + effect.pause_gain * f)
        if pop.pause_overdispersion > 0:
            rate *= rng.gamma(1 / pop.pause_overdispersion, pop.pause_overdispersion)
        pauses = int(rng.poisson(rate))
        pause_total = float(sum(2000 + rng.exponential(1200) for _ in range(pauses)))
        corrections = int(rng.poisson(2))
        keys = TASK_CHARS + 2 * corrections
        sessions.append({
            "keystroke_count": keys, "iki_median_ms": round(iki, 1), "iki_iqr_ms": round(iqr, 1),
            "pause_count": pauses, "pause_total_ms": round(pause_total, 1),
            "checklist_response_median_ms": round(resp, 1),
            "task_duration_ms": round(keys * iki + pause_total + TASK_ITEMS * resp + rng.normal(4000, 500), 1),
            "correction_count": corrections, "retry_count": int(rng.poisson(0.2)),
            "data_quality": "ok",
        })
        truth.append(f)
    assert set(FEATURE_NAMES) <= set(sessions[0])
    return sessions, truth
