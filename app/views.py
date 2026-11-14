"""HTML pages. Deliberately thin: each page loads its data from /api/* with JavaScript."""
import json
from pathlib import Path

from flask import Blueprint, render_template

from .tasks import DEFAULT_TASK_TYPE, TASKS

bp = Blueprint("views", __name__)


@bp.get("/")
def home():
    return render_template("landing.html", active="home")


@bp.get("/me")
def me():
    """Crew-first view: a person's own status, in plain words, before anyone else's."""
    return render_template("me.html", active="me")


@bp.get("/dashboard")
def dashboard():
    return render_template("dashboard.html", active="dashboard")


@bp.get("/monitor")
def monitor():
    return render_template("monitor.html", active="monitor",
                           task_type=DEFAULT_TASK_TYPE, task=TASKS[DEFAULT_TASK_TYPE])


@bp.get("/attention")
def attention():
    return render_template("attention.html", active="attention")


@bp.get("/brief")
def brief():
    """One printable page for the human who reviews a flagged crew before a critical operation."""
    return render_template("brief.html", active="mission")


@bp.get("/mission")
def mission():
    return render_template("mission.html", active="mission")


@bp.get("/about")
def about():
    return render_template("about.html", active="about")


@bp.get("/replay")
def replay():
    return render_template("replay.html", active="replay")


RESULTS_FILE = Path(__file__).with_name("results_data.json")
RELIABILITY_FILE = Path(__file__).with_name("reliability_data.json")   # written by `python -m ml.export_reliability` (task R2)
PILOT_FILE = Path(__file__).resolve().parents[1] / "docs" / "pilot" / "pilot_report.json"   # written by `python -m ml.pilot_report`; absent until the pilot is run


@bp.get("/evidence")
def evidence():
    """The ML benchmark, rendered from results_data.json (written by `python -m ml.export_results`)."""
    try:
        data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    try:
        pilot = json.loads(PILOT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pilot = None                    # no pilot yet: the page says nothing about one
    try:
        reliability = json.loads(RELIABILITY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        reliability = None              # no run yet: the page says nothing about reliability
    return render_template("evidence.html", active="evidence", data=data, pilot=pilot, reliability=reliability)
