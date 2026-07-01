#!/usr/bin/env bash
# Does aira-dojo's external grading return a numeric score for spaceship-titanic?
# Grades sample_submission.csv directly. If score is None / it crashes -> grading is the
# reason working solutions get metric=None (mismarked buggy).
source ~/env_setup.sh
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
"$PY" - <<'PYEOF'
from pathlib import Path
import tempfile, traceback
DATA = "/research/d7/spc/yzyang4/mle-bench-data"
COMP = "spaceship-titanic"
sub = Path(DATA) / COMP / "prepared/public/sample_submission.csv"
print("submission exists:", sub.exists())
out = tempfile.mkdtemp()
try:
    from dojo.tasks.mlebench import evaluate
    score, report = evaluate.evaluate_submission(
        submission_path=sub, data_dir=Path(DATA), competition_id=COMP, results_output_dir=Path(out)
    )
    print("GRADE_OK score=", score)
    print("report type:", type(report))
    if isinstance(report, dict):
        print("report keys:", list(report.keys()))
        for k in ("score", "test_score", "metric", "gold_medal", "above_median"):
            if k in report:
                print(f"  report[{k}]=", report[k])
    # also test parse_report (what aux_eval_info ends up being)
    try:
        from dojo.tasks.mlebench.task import parse_report
        aux = parse_report(report)
        print("parse_report aux keys:", list(aux.keys()) if isinstance(aux, dict) else type(aux))
        print("aux.get('score')=", aux.get("score") if isinstance(aux, dict) else "n/a")
    except Exception as e:
        print("parse_report import/call failed:", e)
except Exception as e:
    print("GRADE_FAILED:", repr(e))
    traceback.print_exc()
PYEOF
echo "DIAG_GRADE_DONE"
