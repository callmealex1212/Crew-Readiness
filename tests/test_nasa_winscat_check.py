"""F4: the WinSCAT feasibility script applies the product's per-measure rule correctly (made-up rows, no NASA data in the repo)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("winscat", ROOT / "scripts" / "nasa_winscat_check.py")
w = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w)

HEADER = "ID,Campaign,Subject,Test,Run,Test_Phase,BR_Day,Date,Time,CPTRT,CPTA,CPTL,MTHRT,MTHA,MTSRT,MTSA,CDDRT,CDDA\n"


def row(run, phase, cptrt, test="Nasa1"):
    return f"{run},CX,1,{test},{run},{phase},1,1/1/2000,10:00:00,{cptrt},95,0,1400,90,1500,100,800,100\n"


def test_deviation_matches_the_product_rule():
    assert w.deviation(110, 100, 0, +1) == 2.0            # spread floored at 5 % of the median
    assert w.deviation(90, 100, 10, +1) == 0.0            # faster than usual is never a deviation
    assert w.deviation(80, 100, 5, -1) == 4.0             # lower accuracy counts, capped at 4


def test_run_one_is_practice_and_a_slow_later_session_is_flagged(tmp_path, capsys):
    body = HEADER + row(1, "PRE_TEST", 900, "Nasa1p")      # practice: very slow, must not shape the baseline
    body += "".join(row(r, "PRE_TEST", 400 + r) for r in range(2, 7))
    body += row(7, "IN_TEST", 404) + row(8, "IN_TEST", 520)
    (tmp_path / "MR085G_Campaign_X_WinSCAT_CXA_0001").write_text(body)
    (tmp_path / "MR085G_Campaign_X_WinSCAT_All").write_text(body)   # a summary file, not a person
    assert w.main(tmp_path) == 0
    out = capsys.readouterr().out
    assert "1 (of 1 files)" in out
    assert "flagged on CPTRT :   1 / 2" in out
