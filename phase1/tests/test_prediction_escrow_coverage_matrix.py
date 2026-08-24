from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import phase1.prediction_escrow_coverage_matrix as builder
import phase1.verify_prediction_escrow_coverage_matrix as verifier


SNAPSHOT = "1" * 64


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> str:
    raw = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: dict[str, object]) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def wl_row(index: int, *, stratum: str = "outcome_unread_support_only") -> dict[str, object]:
    left, right = f"left-{index}", f"right-{index}"
    row: dict[str, object] = {
        "left": left,
        "pair_key_sha256": f"{index + 1:064x}",
        "parent": f"parent-{index}",
        "right": right,
        "run_id": f"run-{index // 2}",
        "task": f"task-{index % 2}",
        "temporal_stratum": stratum,
    }
    for offset, arm in enumerate(builder.WL_ARMS, 1):
        row[f"{arm}_margin_left_minus_right"] = 0.1 * offset
        row[f"{arm}_selected"] = left
    return row


def transition_row(
    index: int,
    *,
    stratum: str = "support_only",
    reverse: bool = False,
) -> dict[str, object]:
    left, right = f"left-{index}", f"right-{index}"
    if reverse:
        left, right = right, left
    strict = stratum == "strict_effect_eligible"
    return {
        "pair_id": f"{index + 101:064x}",
        "task": f"task-{index % 2}",
        "run_id": f"run-{index // 2}",
        "parent": f"parent-{index}",
        "left": left,
        "right": right,
        "generation_started_at_utc": "2026-08-20T00:00:00Z",
        "temporal_stratum": stratum,
        "parent_source_present": True,
        "left_code_sha256": "a" * 64,
        "right_code_sha256": "b" * 64,
        "parent_code_sha256": "c" * 64,
        "training_endpoint_id_overlap": False,
        "training_run_id_overlap": False,
        "training_code_sha_overlap": False,
        "source_novel": True,
        "finite_all_arms": True,
        "nontie_all_arms": True,
        "strict_effect_eligible": strict,
        "child_code": 0.2,
        "transition_only": -0.1,
        "child_plus_transition": 0.3,
    }


def summary(kind: str, pairs_sha: str) -> dict[str, object]:
    output_field = "pair_predictions_sha256" if kind == "wl" else "pairs_sha256"
    return {
        "inputs": {"snapshot_sha256": SNAPSHOT},
        "outputs": {output_field: pairs_sha},
        "scope": {
            "prospective_outcomes_read": False,
            "effect_metrics_computed": [],
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }


def fixture(tmp_path: Path):
    wl_path = tmp_path / "wl.jsonl"
    transition_path = tmp_path / "transition.jsonl"
    wl_sha = write_jsonl(
        wl_path,
        [
            wl_row(0),
            wl_row(1, stratum="outcome_unread_strict_effect_eligible"),
            wl_row(2),
        ],
    )
    transition_sha = write_jsonl(
        transition_path,
        [transition_row(0, reverse=True), transition_row(1, stratum="strict_effect_eligible")],
    )
    wl_summary = tmp_path / "wl_summary.json"
    transition_summary = tmp_path / "transition_summary.json"
    wl_summary_sha = write_json(wl_summary, summary("wl", wl_sha))
    transition_summary_sha = write_json(
        transition_summary, summary("transition", transition_sha)
    )
    return (
        wl_path,
        wl_sha,
        wl_summary,
        wl_summary_sha,
        transition_path,
        transition_sha,
        transition_summary,
        transition_summary_sha,
    )


def build(args):
    return builder.build_matrix(*args, SNAPSHOT)


def test_overlap_is_outcome_blind_and_orientation_invariant(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    result = build(args)
    assert result["formal_status"] == "OUTCOME_BLIND_PREDICTION_COVERAGE_VERIFIED"
    assert result["arms"]["total"] == 7
    assert result["inventory"]["wl"]["pairs"] == 3
    assert result["inventory"]["transition"]["pairs"] == 2
    assert result["overlap"]["intersection_pairs"] == 2
    assert result["overlap"]["union_pairs"] == 3
    assert result["overlap"]["reversed_left_right_orientation"] == 1
    assert result["overlap"]["pairs_per_stratum"] == {
        "strict_effect_eligible": 1,
        "support_only": 1,
    }
    assert result["access_attestation"]["prediction_values_aggregated"] is False


def test_independent_verifier_rederives_core_matrix(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    matrix = build(args)
    verified = verifier.verify(matrix, args[0].read_bytes(), args[4].read_bytes())
    assert verified["formal_status"] == "INDEPENDENT_COVERAGE_VERIFICATION_PASS"
    assert verified["recomputed"]["intersection_pairs"] == 2
    assert verified["recomputed"]["tasks_in_intersection"] == 2


def test_duplicate_pair_fails_closed(tmp_path: Path) -> None:
    args = list(fixture(tmp_path))
    rows = [wl_row(0), wl_row(0)]
    args[1] = write_jsonl(args[0], rows)
    args[3] = write_json(args[2], summary("wl", args[1]))
    with pytest.raises(builder.CoverageError, match="duplicate canonical"):
        build(tuple(args))


def test_nonfinite_and_outside_selection_fail_closed(tmp_path: Path) -> None:
    args = list(fixture(tmp_path))
    row = wl_row(0)
    row["step_only_lr_margin_left_minus_right"] = float("nan")
    args[1] = write_jsonl(args[0], [row])
    args[3] = write_json(args[2], summary("wl", args[1]))
    with pytest.raises(builder.CoverageError, match="non-finite"):
        build(tuple(args))

    row = wl_row(0)
    row["step_only_lr_selected"] = "outside"
    args[1] = write_jsonl(args[0], [row])
    args[3] = write_json(args[2], summary("wl", args[1]))
    with pytest.raises(builder.CoverageError, match="outside pair"):
        build(tuple(args))


def test_summary_scope_and_snapshot_fail_closed(tmp_path: Path) -> None:
    args = list(fixture(tmp_path))
    bad = summary("wl", args[1])
    bad["scope"]["prospective_outcomes_read"] = True
    args[3] = write_json(args[2], bad)
    with pytest.raises(builder.CoverageError, match="blind scope"):
        build(tuple(args))

    bad = summary("wl", args[1])
    bad["inputs"]["snapshot_sha256"] = "2" * 64
    args[3] = write_json(args[2], bad)
    with pytest.raises(builder.CoverageError, match="expected snapshot"):
        build(tuple(args))


def test_tampered_matrix_is_rejected_independently(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    matrix = build(args)
    matrix["overlap"]["intersection_pairs"] = 3
    with pytest.raises(verifier.VerificationError, match="overlap mismatch"):
        verifier.verify(matrix, args[0].read_bytes(), args[4].read_bytes())


def test_write_once_is_immutable(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    output = tmp_path / "matrix.json"
    builder.write_once(output, build(args))
    with pytest.raises(builder.CoverageError, match="already exists"):
        builder.write_once(output, build(args))


def test_formal_runner_sources_environment_before_nounset() -> None:
    runner = (
        Path(__file__).parents[1]
        / "scripts"
        / "run_prediction_escrow_coverage_f109_20260825.sh"
    ).read_text(encoding="utf-8")
    first_set = next(line for line in runner.splitlines() if line.startswith("set -"))
    assert "u" not in first_set.removeprefix("set -").split()[0]
    assert runner.index("source /uac/y24/yzyang4/env_setup.sh") < runner.index("\nset -u\n")


def test_formal_runner_does_not_write_shared_remote_tracking_ref() -> None:
    runner = (
        Path(__file__).parents[1]
        / "scripts"
        / "run_prediction_escrow_coverage_f109_20260825.sh"
    ).read_text(encoding="utf-8")
    assert "ls-remote fork refs/heads/phase1-value-critic" in runner
    assert "fetch --no-write-fetch-head fork \"$release_head\"" in runner
    assert "fetch fork phase1-value-critic" not in runner
    assert 'merge-base --is-ancestor "$control_commit" "$release_head"' in runner
