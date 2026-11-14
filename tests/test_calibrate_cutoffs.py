"""Alert-budget calibration: the cutoff fitted on other people must hit the budget on held-out people."""
import numpy as np

from ml.calibrate_cutoffs import BUDGETS, expected_share_over_2x, heldout_calibration, null_scores, what_budget_is_the_shipped_cutoff


def test_held_out_false_alert_rate_matches_the_budget():
    people = null_scores(n_people=150, seed=5)
    for b in BUDGETS:
        r = heldout_calibration(people, b, n_boot=200)
        assert abs(r["observed"] - b) < 0.012, (b, r)                 # fitted on other people only (folds split by person)
        assert r["ci95"][0] <= r["observed"] <= r["ci95"][1]


def test_a_larger_budget_gives_a_lower_cutoff():
    people = null_scores(n_people=100, seed=6)
    cuts = [heldout_calibration(people, b, n_boot=50)["cutoff"] for b in sorted(BUDGETS, reverse=True)]
    assert cuts == sorted(cuts)                                       # 1 in 10 < 1 in 20 < 1 in 50


def test_chance_alone_benchmark_is_sane():
    people = [np.zeros(35)] * 10
    p = expected_share_over_2x(people, 0.05)
    assert 0.05 < p < 0.2                                              # about 0.11 for 35 sessions at a 5 % budget
    assert expected_share_over_2x(people, 0.0001) < 0.01               # almost nobody exceeds twice a tiny budget by chance


def test_shipped_cutoff_has_a_stated_budget():
    s = what_budget_is_the_shipped_cutoff(null_scores(n_people=100, seed=7))
    assert 10 < s["one_in"] < 60                                       # the shipped YELLOW stands for roughly one normal session in 20-30
