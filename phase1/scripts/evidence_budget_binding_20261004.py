"""Posthoc budget-boundary description of CLOSED, already-public trajectories.

No fit, generation, raw prediction access or new outcome query. This does not
estimate the effect of relaxing a cap or reallocate the historical budget.
Run from any directory; output is create-exclusive and optional.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "results/executable_evidence_20261004"
INPUTS = {
    "actions.csv": "959f418d278f0a9dc289cec2c1835f61749203644f0c9e0fd59d9aaec2e2daa2",
    "runs.csv": "2824c004bcf79b4fd47e31dc9a1aaa26c605ebff8e305876b62aced4b5774b68",
}


def boolean(value):
    if value not in ("True", "False"):
        raise ValueError("missing or invalid boolean")
    return value == "True"


def completed_after_last_permitted_call(run, final):
    # This class is observational, not a causal claim that another call helps.
    return (run["worker_status"] == "completed"
            and not boolean(run["budget_exhausted"])
            and int(run["calls_completed"]) == int(run["max_calls"])
            and boolean(final["returned"]))


def analyze():
    data = {}
    for name, expected in INPUTS.items():
        path = ROOT / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
        with path.open(newline="", encoding="utf-8") as stream:
            data[name] = list(csv.DictReader(stream))
    runs, actions = data["runs.csv"], data["actions.csv"]
    assert len(runs) == 18 and len(actions) == 126
    assert {int(r["index"]) for r in runs} == set(range(18))
    assert {int(a["index"]) for a in actions} == set(range(18))
    rows = []
    for run in runs:
        aa = sorted((a for a in actions if a["index"] == run["index"]),
                    key=lambda a: int(a["step"]))
        assert [int(a["step"]) for a in aa] == list(range(7))
        assert boolean(run["closed"])
        for a in aa:
            assert all(a[k] == run[k] for k in ("task", "arm", "seed"))
        times = [float(a["elapsed_seconds"]) for a in aa if boolean(a["returned"])]
        assert times == sorted(times) and all(0 <= t <= 720 for t in times)
        valid = [float(a["metric"]) for a in aa if boolean(a["valid"])]
        assert valid and all(math.isfinite(x) for x in valid)
        choose = min if run["task"] == "spooky-author-identification" else max
        assert run["task"] in ("spooky-author-identification", "random-acts-of-pizza")
        assert abs(choose(valid) - float(run["selected"])) <= 1e-12
        complete = completed_after_last_permitted_call(run, aa[-1])
        slack = float(run["run_seconds"]) - float(aa[-1]["elapsed_seconds"]) if complete else None
        assert slack is None or slack >= 0
        rows.append(dict(index=int(run["index"]), task=run["task"], arm=run["arm"],
                         seed=int(run["seed"]),
                         finished_after_final_permitted_call=complete,
                         worker_deadline_flag=boolean(run["budget_exhausted"]),
                         slack_after_final_score_seconds=slack,
                         retained_is_observed_best=True))
    groups = []
    for task in sorted({r["task"] for r in rows}):
        rr = [r for r in rows if r["task"] == task]
        vals = sorted(r["slack_after_final_score_seconds"] for r in rr
                      if r["finished_after_final_permitted_call"])
        groups.append(dict(task=task, assigned=len(rr),
                           finished_after_final_permitted_call=len(vals),
                           worker_deadline_flagged=sum(r["worker_deadline_flag"] for r in rr),
                           observed_slack_values=vals,
                           median_observed_slack_seconds=statistics.median(vals) if vals else None))
    return dict(posthoc=True, source_commit="fdb98cda959d6804c72e077fb6d58421ca97b5cf",
                input_sha256=INPUTS,
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                assigned=len(rows), observed_best_retention_passes=len(rows), groups=groups, rows=rows,
                scope="Two developer tasks, one selected root each. Not new independent runs. "
                      "Slack is cap minus elapsed time recorded AFTER scoring the final permitted action, "
                      "not allocation waste or end-to-end speedup. Missing final returns remain null. "
                      "Dual caps were common and valid; this is not a withdrawal of the negative result. "
                      "Relaxed-cap performance is unobserved. Over the fixed observed candidate set, "
                      "reranking alone cannot exceed the already retained best; filtering may save cost "
                      "but its value through new candidates requires a new experiment.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze()
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, allow_nan=False))
