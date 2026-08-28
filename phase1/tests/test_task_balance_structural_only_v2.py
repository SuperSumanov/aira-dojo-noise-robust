from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_task_balance_accrual_guard_v2 import (
    BalanceGuardV2Error,
    build_guard,
)
from phase1.task_balance_guard_forward_validation_v2 import (
    ForwardV2Error,
    build_forward,
)
from phase1.task_balance_guard_forward_validation_v3 import (
    ForwardV3Error,
    build_forward as build_forward_v3,
)
from phase1.verify_task_balance_accrual_guard_v2 import verify as verify_guard
from phase1.verify_task_balance_guard_forward_validation_v2 import (
    verify as verify_forward,
)
from phase1.verify_task_balance_guard_forward_validation_v3 import (
    verify as verify_forward_v3,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_ledger(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _row(run_id: str, task: str, endpoints: int, timestamp: str) -> dict[str, object]:
    return {
        "drop_id": "drop-" + run_id,
        "endpoints": endpoints,
        "flow_status": "scoreable",
        "generation_started_at_utc": timestamp,
        "run_id": run_id,
        "source_sha256": hashlib.sha256(run_id.encode()).hexdigest(),
        "task": task,
    }


def _make_source(
    root: Path,
    snapshot: str,
    rows: list[dict[str, object]],
    pair_counts: dict[str, int],
) -> tuple[Path, str, Path, str]:
    directory = root / snapshot / "accumulator"
    directory.mkdir(parents=True)
    ledger = directory / "provisional_first960_runs.jsonl"
    _write_ledger(ledger, rows)
    ledger_sha = _sha(ledger)
    run_counts = {task: 0 for task in pair_counts}
    endpoint_counts = {task: 0 for task in pair_counts}
    for row in rows:
        task = str(row["task"])
        run_counts[task] += 1
        endpoint_counts[task] += int(row["endpoints"])
    pairs = sum(pair_counts.values())
    dominant = max(pair_counts.values())
    summary = directory / "summary.json"
    _write_json(
        summary,
        {
            "protocol": "prospective_accumulator_v1",
            "status": "PROSPECTIVE_COHORT_COLLECTING",
            "closure": {
                "all_scheduled_runs_uploaded": None,
                "outcomes_read": None,
                "provided": False,
            },
            "outputs": {"provisional_first960_runs_sha256": ledger_sha},
            "security": {
                "label_vault_opened": False,
                "outcome_files_opened": [],
                "scorer_prediction_files_opened": [],
            },
            "task_support": {
                "provisional_first960": {
                    "runs": len(rows),
                    "endpoints": sum(endpoint_counts.values()),
                    "structural_pairs": pairs,
                    "tasks": len(pair_counts),
                    "run_counts": run_counts,
                    "endpoint_counts": endpoint_counts,
                    "structural_pair_counts": pair_counts,
                    "dominant_structural_pair_task_share": dominant / pairs,
                }
            },
        },
    )
    return summary, _sha(summary), ledger, ledger_sha


def _fixture(
    tmp_path: Path, *, expanded_task_pairs: int | None = None
) -> dict[str, object]:
    baseline_snapshot = "a" * 64
    current_snapshot = "b" * 64
    baseline_rows = [
        _row("run-a0", "task-a", 3, "2026-01-01T00:00:00Z"),
        _row("run-b0", "task-b", 2, "2026-01-02T00:00:00Z"),
    ]
    current_rows = [
        *baseline_rows,
        _row("run-a1", "task-a", 4, "2026-01-03T00:00:00Z"),
        _row("run-b1", "task-b", 5, "2026-01-04T00:00:00Z"),
    ]
    current_pair_counts = {"task-a": 71, "task-b": 35}
    if expanded_task_pairs is not None:
        current_rows.append(
            _row("run-c0", "task-c", 6, "2026-01-05T00:00:00Z")
        )
        current_pair_counts["task-c"] = expanded_task_pairs
    baseline = _make_source(
        tmp_path, baseline_snapshot, baseline_rows, {"task-a": 70, "task-b": 30}
    )
    current = _make_source(
        tmp_path, current_snapshot, current_rows, current_pair_counts
    )
    baseline_summary, baseline_summary_sha, baseline_ledger, baseline_ledger_sha = baseline
    current_summary, current_summary_sha, current_ledger, current_ledger_sha = current
    gate = tmp_path / "gate.json"
    _write_json(
        gate,
        {
            "protocol": "prospective_structural_gate_independent_verifier_v5",
            "status": "CONFIRMATORY_COHORT_COLLECTING",
            "snapshot_sha256": baseline_snapshot,
            "inputs": {
                "accumulator_summary_sha256": baseline_summary_sha,
                "provisional_runs_sha256": baseline_ledger_sha,
            },
            "security": {
                "label_vault_opened": False,
                "outcome_files_opened": [],
                "scorer_prediction_files_opened": [],
            },
            "cross_checks_against_accumulator": {"all": True},
            "independent_inventory": {
                "provisional_first960": {
                    "runs": 2,
                    "endpoints": 5,
                    "structural_pairs": 100,
                    "tasks": 2,
                    "dominant_pair_task_count": 70,
                    "dominant_pair_task_share": 0.7,
                }
            },
            "gate": {"maximum_dominant_pair_task_share": 0.25},
        },
    )
    guard = build_guard(
        gate,
        _sha(gate),
        baseline_summary,
        baseline_summary_sha,
        baseline_ledger,
        baseline_ledger_sha,
        baseline_snapshot,
    )
    guard_path = tmp_path / "guard.json"
    _write_json(guard_path, guard)
    guard_sha = _sha(guard_path)
    verification = verify_guard(
        gate,
        _sha(gate),
        baseline_summary,
        baseline_summary_sha,
        baseline_ledger,
        baseline_ledger_sha,
        baseline_snapshot,
        guard_path,
        guard_sha,
    )
    verification_path = tmp_path / "guard_verification.json"
    _write_json(verification_path, verification)
    common = tmp_path / "common.json"
    _write_json(
        common,
        {
            "protocol": "prediction-receipt-common-support-v1",
            "status": "INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED",
            "snapshot_sha256": current_snapshot,
            "pairs": sum(current_pair_counts.values()),
            "same_canonical_pair_population_certified": True,
            "candidate_exact": True,
            "candidate_sha256": "c" * 64,
            "prediction_pair_files_opened": False,
            "prediction_values_accessed": False,
            "producer_imported": False,
            "prospective_outcomes_read": False,
            "effect_metrics_computed": [],
        },
    )
    return locals()


def test_structural_only_guard_and_forward_chain(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    guard = json.loads(Path(fx["guard_path"]).read_text(encoding="utf-8"))
    assert guard["inputs"] == {
        "structural_gate_sha256": _sha(Path(fx["gate"])),
        "accumulator_summary_sha256": fx["baseline_summary_sha"],
        "provisional_first960_runs_sha256": fx["baseline_ledger_sha"],
    }
    assert "coverage_matrix_sha256" not in json.dumps(guard)
    assert guard["exact_integer_envelope"]["imbalance_debt_numerator"] == 180
    forward = build_forward(
        Path(fx["guard_path"]),
        fx["guard_sha"],
        Path(fx["verification_path"]),
        _sha(Path(fx["verification_path"])),
        Path(fx["baseline_summary"]),
        fx["baseline_summary_sha"],
        Path(fx["baseline_ledger"]),
        fx["baseline_ledger_sha"],
        fx["baseline_snapshot"],
        Path(fx["current_summary"]),
        fx["current_summary_sha"],
        Path(fx["current_ledger"]),
        fx["current_ledger_sha"],
        fx["current_snapshot"],
        Path(fx["common"]),
        _sha(Path(fx["common"])),
    )
    assert forward["protocol"] == "task_balance_guard_forward_validation_v2"
    assert forward["status"] == "STRUCTURAL_ONLY_FORWARD_ACCOUNTING_EXACT"
    assert "task_universe_contract" not in forward["source_validation"]
    assert "added_tasks" not in forward["chronology_audit"]
    assert "new_task_zero_extension_explicit" not in forward[
        "frozen_guard_forward_result"
    ]
    assert "same_snapshot_v2_kill_rescued" not in forward["claim_boundary"]
    assert forward["frozen_guard_forward_result"]["observed_current_debt"] == 178
    assert forward["frozen_guard_forward_result"]["debt_delta"] == -2
    assert forward["source_validation"]["prediction_matrix_input_used"] is False
    forward_path = tmp_path / "forward.json"
    _write_json(forward_path, forward)
    receipt = verify_forward(
        Path(fx["guard_path"]),
        fx["guard_sha"],
        Path(fx["verification_path"]),
        _sha(Path(fx["verification_path"])),
        Path(fx["baseline_summary"]),
        fx["baseline_summary_sha"],
        Path(fx["baseline_ledger"]),
        fx["baseline_ledger_sha"],
        fx["baseline_snapshot"],
        Path(fx["current_summary"]),
        fx["current_summary_sha"],
        Path(fx["current_ledger"]),
        fx["current_ledger_sha"],
        fx["current_snapshot"],
        Path(fx["common"]),
        _sha(Path(fx["common"])),
        forward_path,
        _sha(forward_path),
    )
    assert receipt["status"] == "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_FORWARD_PASS"


def test_guard_rejects_summary_not_bound_by_independent_gate(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    summary_path = Path(fx["baseline_summary"])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["task_support"]["provisional_first960"]["structural_pair_counts"] = {
        "task-a": 69,
        "task-b": 31,
    }
    summary["task_support"]["provisional_first960"][
        "dominant_structural_pair_task_share"
    ] = 0.69
    _write_json(summary_path, summary)
    with pytest.raises(BalanceGuardV2Error, match="structural gate source binding"):
        build_guard(
            Path(fx["gate"]),
            _sha(Path(fx["gate"])),
            summary_path,
            _sha(summary_path),
            Path(fx["baseline_ledger"]),
            fx["baseline_ledger_sha"],
            fx["baseline_snapshot"],
        )


def test_forward_rejects_prediction_access_receipt(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    common = Path(fx["common"])
    value = json.loads(common.read_text(encoding="utf-8"))
    value["prediction_values_accessed"] = True
    _write_json(common, value)
    with pytest.raises(ForwardV2Error, match="prediction_values_accessed"):
        build_forward(
            Path(fx["guard_path"]),
            fx["guard_sha"],
            Path(fx["verification_path"]),
            _sha(Path(fx["verification_path"])),
            Path(fx["baseline_summary"]),
            fx["baseline_summary_sha"],
            Path(fx["baseline_ledger"]),
            fx["baseline_ledger_sha"],
            fx["baseline_snapshot"],
            Path(fx["current_summary"]),
            fx["current_summary_sha"],
            Path(fx["current_ledger"]),
            fx["current_ledger_sha"],
            fx["current_snapshot"],
            common,
            _sha(common),
        )


def test_guard_rejects_ledger_with_unapproved_field(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    ledger = Path(fx["baseline_ledger"])
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    rows[0]["prediction"] = 0.9
    _write_ledger(ledger, rows)
    summary = Path(fx["baseline_summary"])
    value = json.loads(summary.read_text(encoding="utf-8"))
    value["outputs"]["provisional_first960_runs_sha256"] = _sha(ledger)
    _write_json(summary, value)
    gate = Path(fx["gate"])
    gate_value = json.loads(gate.read_text(encoding="utf-8"))
    gate_value["inputs"]["accumulator_summary_sha256"] = _sha(summary)
    gate_value["inputs"]["provisional_runs_sha256"] = _sha(ledger)
    _write_json(gate, gate_value)
    with pytest.raises(BalanceGuardV2Error, match="ledger row schema"):
        build_guard(
            gate,
            _sha(gate),
            summary,
            _sha(summary),
            ledger,
            _sha(ledger),
            fx["baseline_snapshot"],
        )


def test_v2_preserves_the_frozen_same_task_universe_kill(tmp_path: Path) -> None:
    fx = _fixture(tmp_path, expanded_task_pairs=4)
    with pytest.raises(ForwardV2Error, match="task universe changed"):
        build_forward(
            Path(fx["guard_path"]),
            fx["guard_sha"],
            Path(fx["verification_path"]),
            _sha(Path(fx["verification_path"])),
            Path(fx["baseline_summary"]),
            fx["baseline_summary_sha"],
            Path(fx["baseline_ledger"]),
            fx["baseline_ledger_sha"],
            fx["baseline_snapshot"],
            Path(fx["current_summary"]),
            fx["current_summary_sha"],
            Path(fx["current_ledger"]),
            fx["current_ledger_sha"],
            fx["current_snapshot"],
            Path(fx["common"]),
            _sha(Path(fx["common"])),
        )


def test_v3_zero_extends_a_monotone_new_task_and_is_independently_verified(
    tmp_path: Path,
) -> None:
    fx = _fixture(tmp_path, expanded_task_pairs=4)
    forward = build_forward_v3(
        Path(fx["guard_path"]),
        fx["guard_sha"],
        Path(fx["verification_path"]),
        _sha(Path(fx["verification_path"])),
        Path(fx["baseline_summary"]),
        fx["baseline_summary_sha"],
        Path(fx["baseline_ledger"]),
        fx["baseline_ledger_sha"],
        fx["baseline_snapshot"],
        Path(fx["current_summary"]),
        fx["current_summary_sha"],
        Path(fx["current_ledger"]),
        fx["current_ledger_sha"],
        fx["current_snapshot"],
        Path(fx["common"]),
        _sha(Path(fx["common"])),
    )
    assert forward["protocol"] == "task_balance_guard_forward_validation_v3"
    chronology = forward["chronology_audit"]
    assert {
        key: chronology[key]
        for key in (
            "baseline_tasks",
            "current_tasks",
            "added_tasks",
            "removed_tasks",
            "task_identities_emitted",
        )
    } == {
        "baseline_tasks": 2,
        "current_tasks": 3,
        "added_tasks": 1,
        "removed_tasks": 0,
        "task_identities_emitted": True,
    }
    result = forward["frozen_guard_forward_result"]
    assert result["pair_increments_by_task"] == {
        "task-a": 1,
        "task-b": 5,
        "task-c": 4,
    }
    assert result["new_task_zero_extension_explicit"] is True
    assert result["added_task_count"] == 1
    forward_path = tmp_path / "forward-v3.json"
    _write_json(forward_path, forward)
    receipt = verify_forward_v3(
        Path(fx["guard_path"]),
        fx["guard_sha"],
        Path(fx["verification_path"]),
        _sha(Path(fx["verification_path"])),
        Path(fx["baseline_summary"]),
        fx["baseline_summary_sha"],
        Path(fx["baseline_ledger"]),
        fx["baseline_ledger_sha"],
        fx["baseline_snapshot"],
        Path(fx["current_summary"]),
        fx["current_summary_sha"],
        Path(fx["current_ledger"]),
        fx["current_ledger_sha"],
        fx["current_snapshot"],
        Path(fx["common"]),
        _sha(Path(fx["common"])),
        forward_path,
        _sha(forward_path),
    )
    assert receipt["status"] == (
        "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_FORWARD_V3_PASS"
    )
    assert receipt["checks"]["task_universe_monotone_expansion_exact"] is True
    assert receipt["recomputed"]["added_tasks"] == 1


def test_v3_still_rejects_a_new_dominant_task(tmp_path: Path) -> None:
    fx = _fixture(tmp_path, expanded_task_pairs=90)
    with pytest.raises(ForwardV3Error, match="dominant task changed"):
        build_forward_v3(
            Path(fx["guard_path"]),
            fx["guard_sha"],
            Path(fx["verification_path"]),
            _sha(Path(fx["verification_path"])),
            Path(fx["baseline_summary"]),
            fx["baseline_summary_sha"],
            Path(fx["baseline_ledger"]),
            fx["baseline_ledger_sha"],
            fx["baseline_snapshot"],
            Path(fx["current_summary"]),
            fx["current_summary_sha"],
            Path(fx["current_ledger"]),
            fx["current_ledger_sha"],
            fx["current_snapshot"],
            Path(fx["common"]),
            _sha(Path(fx["common"])),
        )


def test_v3_verifier_does_not_import_either_forward_producer() -> None:
    verifier_v3 = (
        Path(__file__).parents[1]
        / "verify_task_balance_guard_forward_validation_v3.py"
    ).read_text(encoding="utf-8")
    verifier_v2 = (
        Path(__file__).parents[1]
        / "verify_task_balance_guard_forward_validation_v2.py"
    ).read_text(encoding="utf-8")
    assert "from phase1.task_balance_guard_forward_validation_v3" not in verifier_v3
    assert "import phase1.task_balance_guard_forward_validation_v3" not in verifier_v3
    assert "from phase1.task_balance_guard_forward_validation_v2" not in verifier_v2
    assert "import phase1.task_balance_guard_forward_validation_v2" not in verifier_v2
