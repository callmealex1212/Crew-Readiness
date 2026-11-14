"""The interval code must give the SAME point estimates as the plain evaluator, and intervals that make sense."""
from ml.evaluate import evaluate, evaluate_ci, incumbent_detector


def test_point_estimates_match_the_plain_evaluator():
    a = evaluate(incumbent_detector, shape="step", magnitude=0.15, length=5, n_people=40, seed=3, alert_threshold=1.0)
    b = evaluate_ci(incumbent_detector, shape="step", magnitude=0.15, length=5, n_people=40, seed=3, alert_threshold=1.0, n_boot=100)
    assert abs(a.detection_rate - b["detection"]) < 1e-12 and abs(a.false_alert_rate - b["false_alerts"]) < 1e-12


def test_intervals_contain_the_estimate_and_are_ordered():
    b = evaluate_ci(incumbent_detector, shape="step", magnitude=0.15, length=5, n_people=40, seed=4, n_boot=200)
    for key, lo_hi in (("detection", b["detection_ci"]), ("false_alerts", b["false_alerts_ci"])):
        assert lo_hi[0] <= b[key] <= lo_hi[1] + 1e-9 and lo_hi[0] < lo_hi[1]


def test_more_people_give_a_tighter_interval():
    small = evaluate_ci(incumbent_detector, shape="step", magnitude=0.15, length=5, n_people=20, seed=5, n_boot=200)
    big = evaluate_ci(incumbent_detector, shape="step", magnitude=0.15, length=5, n_people=120, seed=5, n_boot=200)
    assert (big["detection_ci"][1] - big["detection_ci"][0]) < (small["detection_ci"][1] - small["detection_ci"][0])
