from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1 import repair_selective_execution_postflight as repair


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_completed_staging(tmp_path: Path) -> tuple[Path, Path]:
    final = tmp_path / "selective_execution_v11_20260814_fixture"
    staging = tmp_path / (final.name + ".staging")
    result = staging / "result"
    result.mkdir(parents=True)
    summary = {
        "protocol": repair.PROTOCOL,
        "verdict": "SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK",
        "frozen_or_first960_read": False,
        "policies": {"tri_unanimous_q20": {"selected": 3, "task_macro_accuracy": 0.5}},
    }
    summary_path = result / "summary.json"
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    verification = {
        "protocol": repair.PROTOCOL,
        "verification": repair.VERIFICATION,
        "producer_verdict": summary["verdict"],
        "frozen_or_first960_read": False,
        "summary_sha256": file_hash(summary_path),
    }
    (result / "independent_verify.json").write_text(json.dumps(verification), encoding="utf-8")
    (staging / "run.log").write_text("stable\n", encoding="utf-8")
    (staging / "SHA256SUMS").write_text("bad  run.log\n", encoding="utf-8")
    return staging, final


def test_postflight_repair_preserves_failure_and_promotes(tmp_path: Path) -> None:
    staging, final = make_completed_staging(tmp_path)
    receipt = repair.repair(staging, final, "repair-commit")
    assert not staging.exists()
    assert final.is_dir()
    assert (final / "SHA256SUMS.failed_self_reference").read_text() == "bad  run.log\n"
    assert (final / "SHA256SUMS").is_file()
    assert receipt["producer_rerun"] is False
    assert receipt["verifier_rerun"] is False


def test_postflight_repair_rejects_unverified_result(tmp_path: Path) -> None:
    staging, final = make_completed_staging(tmp_path)
    receipt_path = staging / "result" / "independent_verify.json"
    payload = json.loads(receipt_path.read_text())
    payload["verification"] = "FAIL"
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(repair.RepairError, match="did not pass"):
        repair.repair(staging, final, "repair-commit")
