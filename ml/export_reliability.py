"""
Write app/reliability_data.json (task R2). Every number comes from this run; nothing is typed in.

    python -m ml.export_reliability            # full run: 1000 hostile payloads, 6 people x 700 days x 3 a day, clock jump
    python -m ml.export_reliability --quick    # a short run for development (marked "quick" in the file; never ship it)

The file records the machine it ran on, because timings depend on it. Rendered by the Reliability section of /evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import soak  # noqa: E402

OUT = ROOT / "app" / "reliability_data.json"
COMMAND = "python -m ml.export_reliability"
EXTRA_FUZZ_SEEDS = (1, 2, 3, 4, 5)

LIMITS = ("Run once on a general-purpose computer (see 'machine'), on simulated data. Not flight hardware, not radiation-tested, "
          "no failing disk or full storage, no concurrent users, no real crew data. Timings depend on the machine.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="short development run (not for shipping)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    days = 20 if a.quick else 700

    main_fuzz = soak.fuzz(1000)
    extra = [soak.fuzz(1000, seed=s) for s in EXTRA_FUZZ_SEEDS]
    data = {
        "generated_by": COMMAND + (" --quick" if a.quick else ""),
        "quick": a.quick,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "machine": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
                    "cpus": os.cpu_count()},
        "fault_injection": main_fuzz,
        "fault_injection_extra_seeds": {
            "seeds": list(EXTRA_FUZZ_SEEDS), "payloads": 1000 * len(EXTRA_FUZZ_SEEDS),
            "crashes": sum(r["crashes"] for r in extra),
            "crash_examples": [dict(e, seed=s) for s, r in zip(EXTRA_FUZZ_SEEDS, extra) for e in r["crash_examples"]][:10],
        },
        "soak": soak.soak(people=6, days=days, per_day=3),
        "clock_jump": soak.clock_jump(),
        "limits": LIMITS,
    }
    a.out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")
    print(json.dumps({k: data[k] for k in ("fault_injection_extra_seeds", "soak", "clock_jump")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
