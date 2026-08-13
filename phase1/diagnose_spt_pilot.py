#!/usr/bin/env python3
"""Post-outcome, read-only diagnostics for the frozen SPT pilot.

This does not alter or re-evaluate K0--K5.  It only classifies why a frozen
execution did or did not expose a probe/final artifact.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def score(event: object) -> float | None:
    if not isinstance(event, dict):
        return None
    grade = event.get("grade")
    value = grade.get("sub_score") if isinstance(grade, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def checkpoint(result: dict, cap: float) -> dict | None:
    rows = result.get("checkpoints") or []
    return next((row for row in rows if float(row.get("cap_s", -1)) == cap), None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    paths = sorted(args.results.glob("index_*/result.json"))
    if len(paths) != 18:
        raise RuntimeError(f"expected 18 results, got {len(paths)}")

    rows = []
    by_card: dict[str, list[dict]] = defaultdict(list)
    for path in paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        cp120 = checkpoint(result, 120.0) or {}
        cp600 = checkpoint(result, 600.0) or {}
        probe = result.get("probe")
        events = result.get("submission_events") or []
        final_logs = result.get("final_logs") or {}
        row = {
            "index": result["index"],
            "task": result["competition"],
            "card_id": result["card_id"],
            "arm": result["arm"],
            "tap_site_count": result["tap_site_count"],
            "final_rc": result.get("final_rc"),
            "wall_s": result.get("wall_s"),
            "submission_events": len(events),
            "last_submission_elapsed_s": events[-1].get("first_seen_elapsed_s") if events else None,
            "last_submission_score": score(events[-1]) if events else None,
            "probe_present": isinstance(probe, dict),
            "probe_elapsed_s": probe.get("first_seen_elapsed_s") if isinstance(probe, dict) else None,
            "probe_score": score(probe),
            "probe_markers": len(result.get("probe_markers") or []),
            "full_markers": len(result.get("full_markers") or []),
            "fallback_markers": result.get("fallback_marker_count"),
            "cp120_alive": cp120.get("process_alive"),
            "cp120_probe_markers": cp120.get("probe_marker_count"),
            "cp120_full_markers": cp120.get("full_marker_count"),
            "cp120_stdout_bytes": cp120.get("stdout_bytes"),
            "cp120_stderr_bytes": cp120.get("stderr_bytes"),
            "cp600_alive": cp600.get("process_alive"),
            "cp600_probe_markers": cp600.get("probe_marker_count"),
            "cp600_full_markers": cp600.get("full_marker_count"),
            "final_stdout_bytes": final_logs.get("stdout_bytes"),
            "final_stderr_bytes": final_logs.get("stderr_bytes"),
        }
        rows.append(row)
        by_card[result["card_id"]].append(row)

    cards = []
    for card_id, card_rows in sorted(by_card.items()):
        arms = {row["arm"]: row for row in card_rows}
        tap = arms["tap"]
        originals = [arms["original_a"], arms["original_b"]]
        if all(row["final_rc"] == -9 and row["submission_events"] == 0 for row in card_rows):
            diagnosis = "all_arms_timeout_before_final_artifact"
        elif all(row["final_rc"] == 0 and row["submission_events"] > 0 for row in originals):
            if tap["probe_present"]:
                diagnosis = "baseline_complete_tap_probe_present"
            else:
                diagnosis = "baseline_complete_tap_no_probe"
        elif tap["probe_present"]:
            diagnosis = "tap_probe_present_but_baseline_not_evaluable"
        else:
            diagnosis = "mixed_or_incomplete"
        cards.append(
            {
                "card_id": card_id,
                "task": tap["task"],
                "tap_site_count": tap["tap_site_count"],
                "diagnosis": diagnosis,
                "arm_indices": {name: arms[name]["index"] for name in sorted(arms)},
                "arm_final_rc": {name: arms[name]["final_rc"] for name in sorted(arms)},
                "arm_wall_s": {name: arms[name]["wall_s"] for name in sorted(arms)},
                "tap_probe_elapsed_s": tap["probe_elapsed_s"],
                "tap_probe_score": tap["probe_score"],
                "tap_probe_markers": tap["probe_markers"],
                "tap_full_markers": tap["full_markers"],
                "tap_fallback_markers": tap["fallback_markers"],
                "tap_cp120_probe_markers": tap["cp120_probe_markers"],
                "tap_cp120_stdout_bytes": tap["cp120_stdout_bytes"],
                "tap_cp120_stderr_bytes": tap["cp120_stderr_bytes"],
            }
        )

    report = {
        "schema_version": 1,
        "scope": "post-outcome diagnosis only; frozen K0--K5 unchanged",
        "execution_count": len(rows),
        "card_count": len(cards),
        "cards": cards,
        "executions": sorted(rows, key=lambda row: row["index"]),
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
