"""The rarity experiment's pieces must be right, and its calibration claim must hold on a small run."""
import numpy as np

from ml.calibration import ALPHAS, part_a, rarity


def test_rarity_is_a_rank_among_own_past_scores():
    past = [0.2, 0.4, 0.1, 0.3, 0.5, 0.2, 0.3, 0.4]
    assert rarity(past + [0.9], 8) == 1 / 9                      # higher than all 8 past: smallest possible p
    assert rarity(past + [0.0], 8) == 1.0                        # lower than all: not rare at all
    assert rarity(past + [0.3], 8) == (1 + 5) / 9                # five past scores are >= 0.3 (ties count as "at least as high")


def test_rarity_says_nothing_without_enough_history_or_a_score():
    assert rarity([0.2] * 4 + [0.9], 4) is None                  # fewer than the minimum past sessions
    assert rarity([None] * 10 + [0.9], 10) is None               # past scores that were never computed do not count
    assert rarity([0.2] * 10 + [None], 10) is None


def test_false_alert_rate_is_at_most_the_target_on_event_free_people():
    rates, n = part_a(n_people=120, seed=3)
    assert n > 1500
    for a in ALPHAS:
        assert rates[a] <= a + 0.03, (a, rates[a])               # conservative by construction; small slack for sampling noise
