#!/usr/bin/env python3
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


snapshot = Path(sys.argv[1]).resolve()
producer = Path(sys.argv[2]).resolve()
report_path = Path(sys.argv[3]).resolve()
cutoff = dt.datetime.fromisoformat("2026-08-12T21:31:21+00:00")
rows = []
intakes = sorted(path for path in snapshot.iterdir() if path.is_dir())
for intake in intakes:
    summary_path = intake / "summary.json"
    provenance_path = intake / "source_provenance.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    security = summary.get("security") or {}
    blindness = summary.get("blindness") or {}
    if not (
        summary.get("protocol") == "prospective_drop_intake_v1"
        and security.get("env_members_read") is False
        and security.get("env_members_extracted") is False
        and security.get("raw_journals_written") is False
        and security.get("credential_shaped_journals") == 0
        and blindness.get("label_values_printed") is False
        and blindness.get("labels_used_for_run_selection") is False
        and blindness.get("metrics_computed") == []
        and (summary.get("outputs") or {}).get("source_provenance_sha256")
        == digest(provenance_path)
    ):
        raise SystemExit(f"safe sidecar contract failed: {intake.name}")
    for raw in json.loads(provenance_path.read_text(encoding="utf-8")):
        started = dt.datetime.fromisoformat(
            raw["generation_started_at_utc"].replace("Z", "+00:00")
        )
        if started > cutoff:
            rows.append(
                {
                    "archive_name": raw["archive_name"],
                    "archive_sha256": raw["archive_sha256"],
                    "generation_started_at_utc": started.astimezone(
                        dt.timezone.utc
                    ).isoformat().replace("+00:00", "Z"),
                    "journal_sha256": raw["journal_sha256"],
                    "run_id": raw["run_id"],
                    "task": raw["task"],
                }
            )
if len({row["run_id"] for row in rows}) != len(rows):
    raise SystemExit("duplicate run ID")
if len({row["journal_sha256"] for row in rows}) != len(rows):
    raise SystemExit("duplicate journal SHA")
rows.sort(key=lambda row: (row["generation_started_at_utc"], row["journal_sha256"]))
producer_rows = [
    json.loads(line)
    for line in (producer / "eligible_runs.jsonl").read_text(encoding="utf-8").splitlines()
]
if producer_rows != rows:
    raise SystemExit("producer eligible rows disagree with independent reconstruction")
summary = json.loads((producer / "summary.json").read_text(encoding="utf-8"))
counts = collections.Counter(row["task"] for row in rows)
dominant_task, dominant_runs = counts.most_common(1)[0]
dominant_share = dominant_runs / len(rows)
expected_gate = len(rows) >= 150 and dominant_share <= 0.25
if not (
    summary["counts"]["eligible_post_mechanism_runs"] == len(rows)
    and summary["counts"]["tasks"] == len(counts)
    and summary["task_balance"]["per_task"] == dict(sorted(counts.items()))
    and summary["task_balance"]["dominant_task"] == dominant_task
    and summary["task_balance"]["dominant_runs"] == dominant_runs
    and summary["task_balance"]["dominant_share"] == dominant_share
    and summary["gates"]["run_gate_pass"] is expected_gate
    and summary["gates"]["replay_submission_authorized"] is False
    and summary["blindness"]["score_or_outcome_opened"] is False
):
    raise SystemExit("producer summary disagrees with independent reconstruction")
receipt = {
    "dominant_runs": dominant_runs,
    "dominant_share": dominant_share,
    "dominant_task": dominant_task,
    "eligible_runs": len(rows),
    "eligible_runs_sha256": digest(producer / "eligible_runs.jsonl"),
    "intakes": len(intakes),
    "labels_or_outcomes_read": False,
    "per_task": dict(sorted(counts.items())),
    "producer_summary_sha256": digest(producer / "summary.json"),
    "protocol": "score_channel_eligibility_independent_verify_v1",
    "remaining_to_150": max(0, 150 - len(rows)),
    "run_gate_pass": expected_gate,
    "tasks": len(counts),
}
report_path.write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(receipt, sort_keys=True))
