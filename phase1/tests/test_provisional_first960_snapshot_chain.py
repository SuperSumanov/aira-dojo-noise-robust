from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import verify_provisional_first960_snapshot_chain as chain
from phase1 import verify_wl_graph_escrow_append as legacy_wl


PRIOR_SHA = "1" * 64
CURRENT_SHA = "2" * 64
SCORER_COMMIT = "3" * 40
ROOT = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def run_row(run: str, generation: str) -> dict:
    source = hashlib.sha256(run.encode()).hexdigest()
    return {
        "run_id": run,
        "task": f"task-{run}",
        "drop_id": f"drop-{run}",
        "flow_status": "scoreable",
        "endpoints": 2,
        "generation_started_at_utc": generation,
        "source_sha256": source,
    }


def write_snapshot(root: Path, all_rows: list[dict], *, closed: bool = False) -> None:
    all_rows = sorted(all_rows, key=lambda row: (row["generation_started_at_utc"], row["source_sha256"], row["run_id"]))
    selected = all_rows[: chain.COHORT_RUN_TARGET]
    all_path = root / "accumulator" / "provisional_runs.jsonl"
    first_path = root / "accumulator" / "provisional_first960_runs.jsonl"
    write_jsonl(all_path, all_rows)
    write_jsonl(first_path, selected)
    write_json(
        root / "accumulator" / "summary.json",
        {
            "inventory": {
                "eligible_runs": len(all_rows),
                "provisional_first960_runs": len(selected),
            },
            "outputs": {
                "provisional_runs_sha256": sha(all_path),
                "provisional_first960_runs_sha256": sha(first_path),
            },
            "closure": {
                "provided": closed,
                "all_scheduled_runs_uploaded": True if closed else None,
                "outcomes_read": False if closed else None,
            },
            "security": {
                "label_vault_opened": False,
                "outcome_files_opened": [],
                "scorer_prediction_files_opened": [],
            },
        },
    )


def endpoint(identifier: str, run: str, value: float) -> dict[str, str]:
    row = {
        "card_id": identifier,
        "task": f"task-{run}",
        "run_id": run,
        "parent": f"parent-{run}",
        "code_sha256": hashlib.sha256(identifier.encode()).hexdigest(),
        "generation_started_at_utc": "2026-08-21T01:00:00Z",
        "temporal_stratum": "strict_post_activation_primary",
    }
    row.update(
        {arm: format(value + index / 10, ".17g") for index, arm in enumerate(legacy_wl.ARMS)}
    )
    return row


def wl_pair(left: dict[str, str], right: dict[str, str]) -> dict:
    row = {
        "task": left["task"],
        "run_id": left["run_id"],
        "parent": left["parent"],
        "left": left["card_id"],
        "right": right["card_id"],
        "temporal_stratum": left["temporal_stratum"],
        "pair_key_sha256": hashlib.sha256(
            "\0".join((left["card_id"], right["card_id"])).encode()
        ).hexdigest(),
    }
    for arm in legacy_wl.ARMS:
        margin = float(left[arm]) - float(right[arm])
        row[f"{arm}_margin_left_minus_right"] = margin
        row[f"{arm}_selected"] = left["card_id"] if margin > 0 else right["card_id"]
    return row


def write_wl_artifact(root: Path, snapshot: str, endpoints: list[dict[str, str]]) -> str:
    root.mkdir(parents=True)
    pairs = [wl_pair(endpoints[index], endpoints[index + 1]) for index in range(0, len(endpoints), 2)]
    endpoint_path = root / "endpoint_scores.csv"
    with endpoint_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=legacy_wl.ENDPOINT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(endpoints)
    pair_path = root / "pair_predictions.jsonl"
    pair_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in pairs),
        encoding="utf-8",
    )
    summary = {
        "status": "PROSPECTIVE_WL_GRAPH_PREDICTION_ESCROW_COMPLETE",
        "protocol": "prospective-wl-graph-escrow-v1",
        "source_commit": SCORER_COMMIT,
        "source_file_sha256": {"phase1/scorer.py": "4" * 64},
        "activation": {"receipt_sha256": "5" * 64, "activated_at_utc": "2026-08-21T00:00:00Z"},
        "inputs": {
            "snapshot_sha256": snapshot,
            "protocol_sha256": "6" * 64,
            "bundle_sha256": "7" * 64,
            "bundle_summary_sha256": "8" * 64,
            "bundle_verification_sha256": "9" * 64,
        },
        "inventory": {
            "endpoints": len(endpoints),
            "runs": len({row["run_id"] for row in endpoints}),
            "tasks": len({row["task"] for row in endpoints}),
            "pairs": len(pairs),
            "run_strata": {"strict_post_activation_primary": len({row["run_id"] for row in endpoints})},
            "pair_strata": {"strict_post_activation_primary": len(pairs)},
            "ties": {arm: 0 for arm in legacy_wl.ARMS},
        },
        "outputs": {
            "endpoint_scores_sha256": sha(endpoint_path),
            "pair_predictions_sha256": sha(pair_path),
        },
        "scope": {
            "prospective_outcomes_read": False,
            "temporal_label_vault_read": False,
            "v11_frozen_or_extension_read": False,
            "effect_metrics_computed": [],
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }
    write_json(root / "summary.json", summary)
    write_json(
        root / "sha256_manifest.json",
        {
            name: sha(root / name)
            for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")
        },
    )
    return sha(root / "summary.json")


def write_wl_independent(path: Path, artifact: Path, snapshot: str) -> None:
    summary = json.loads((artifact / "summary.json").read_text())
    write_json(
        path,
        {
            "status": "INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED",
            "artifact_summary_sha256": sha(artifact / "summary.json"),
            "snapshot_sha256": snapshot,
            "endpoints": summary["inventory"]["endpoints"],
            "pairs": summary["inventory"]["pairs"],
            "prospective_outcomes_read": False,
            "effect_metrics_computed": [],
            "maximum_absolute_score_difference": {arm: 0.0 for arm in legacy_wl.ARMS},
        },
    )


def transition_pair(run: str, left: str, right: str) -> dict:
    task = f"task-{run}"
    parent = f"parent-{run}"
    key = hashlib.sha256("\0".join((task, run, parent, left, right)).encode()).hexdigest()
    return {
        "pair_id": key,
        "task": task,
        "run_id": run,
        "parent": parent,
        "left": left,
        "right": right,
        "generation_started_at_utc": "2026-08-21T01:00:00Z",
        "temporal_stratum": "strict_future",
        "parent_source_present": True,
        "left_code_sha256": hashlib.sha256(left.encode()).hexdigest(),
        "right_code_sha256": hashlib.sha256(right.encode()).hexdigest(),
        "parent_code_sha256": hashlib.sha256(parent.encode()).hexdigest(),
        "training_endpoint_id_overlap": False,
        "training_run_id_overlap": False,
        "training_code_sha_overlap": False,
        "source_novel": True,
        "finite_all_arms": True,
        "nontie_all_arms": True,
        "strict_effect_eligible": True,
        "child_code": 0.1,
        "transition_only": 0.2,
        "child_plus_transition": 0.3,
    }


def write_transition_artifact(root: Path, snapshot: str, rows: list[dict], *, prior_used: bool) -> str:
    root.mkdir(parents=True)
    pairs_path = root / "pairs.jsonl"
    write_jsonl(pairs_path, rows)
    fixed_inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in chain.TRANSITION_FIXED_INPUTS}
    fixed_inputs["snapshot_sha256"] = snapshot
    summary = {
        "append": {
            "prior_pairs": 0,
            "prior_summary_sha256": None,
            "prior_used": prior_used,
            "survival_exact": True,
        },
        "inputs": fixed_inputs,
        "model_refit": {"fit_receipts": {"fixed": True}, "maximum_training_reference_difference": 0.0},
        "outputs": {"pairs": "pairs.jsonl", "pairs_sha256": sha(pairs_path)},
        "protocol": "prospective-transition-future-escrow-v1",
        "scope": {
            "api_calls": 0,
            "base_llm_updates": 0,
            "effect_metrics_computed": [],
            "gpu": 0,
            "prospective_outcomes_read": False,
        },
        "snapshot": {"snapshot_sha256": snapshot},
        "source_commit": SCORER_COMMIT,
        "source_file_sha256": {"phase1/scorer.py": "a" * 64},
        "status": "TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT",
        "support": {
            "inventory": {"all_pairs": len(rows)},
            "status": "TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT",
        },
        "transition_scoring": {},
    }
    write_json(root / "summary.json", summary)
    return sha(root / "summary.json")


def write_transition_independent(path: Path, artifact: Path) -> None:
    summary = json.loads((artifact / "summary.json").read_text())
    write_json(
        path,
        {
            "status": "INDEPENDENT_PROSPECTIVE_TRANSITION_FUTURE_ESCROW_VERIFIED",
            "artifact_summary_sha256": sha(artifact / "summary.json"),
            "maximum_future_margin_difference": 0.0,
            "maximum_training_reference_difference": 0.0,
            "pairs": summary["support"]["inventory"]["all_pairs"],
            "scope": {"prospective_outcomes_read": False, "effect_metrics_computed": []},
        },
    )


def wl_fixture(tmp_path: Path, *, churn: bool = True) -> argparse.Namespace:
    prior_snapshot = tmp_path / "prior-snapshot"
    current_snapshot = tmp_path / "current-snapshot"
    old_1 = run_row("old-1", "2026-08-21T01:00:00Z")
    old_2 = run_row("old-2", "2026-08-21T02:00:00Z")
    new = run_row("new", "2026-08-21T00:30:00Z" if churn else "2026-08-21T03:00:00Z")
    write_snapshot(prior_snapshot, [old_1, old_2])
    write_snapshot(current_snapshot, [old_1, old_2, new])
    old1 = [endpoint("a", "old-1", 2.0), endpoint("b", "old-1", 1.0)]
    old2 = [endpoint("c", "old-2", 2.0), endpoint("d", "old-2", 1.0)]
    new_rows = [endpoint("e", "new", 2.0), endpoint("f", "new", 1.0)]
    prior_artifact = tmp_path / "prior-artifact"
    current_artifact = tmp_path / "current-artifact"
    prior_summary = write_wl_artifact(prior_artifact, PRIOR_SHA, old1 + old2)
    current_summary = write_wl_artifact(
        current_artifact,
        CURRENT_SHA,
        new_rows + old1 if churn else old1 + old2,
    )
    independent = tmp_path / "independent.json"
    write_wl_independent(independent, current_artifact, CURRENT_SHA)
    return argparse.Namespace(
        family="wl_graph",
        prior_snapshot_root=prior_snapshot,
        current_snapshot_root=current_snapshot,
        expect_prior_snapshot_sha256=PRIOR_SHA,
        expect_current_snapshot_sha256=CURRENT_SHA,
        prior_artifact=prior_artifact,
        current_artifact=current_artifact,
        expect_prior_summary_sha256=prior_summary,
        expect_current_summary_sha256=current_summary,
        current_independent_verification=independent,
    )


@pytest.fixture(autouse=True)
def small_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chain, "COHORT_RUN_TARGET", 2)


def test_accepts_exact_churn_and_marks_support_provisional(tmp_path: Path) -> None:
    receipt = chain.verify(wl_fixture(tmp_path))
    assert receipt["cohort_churn"]["added_runs"] == 1
    assert receipt["cohort_churn"]["removed_runs"] == 1
    assert receipt["prediction_intersection"]["endpoints"] == {
        "prior": 4,
        "current": 4,
        "common": 2,
        "prior_only": 2,
        "current_only": 2,
        "common_rows_exact": True,
    }
    assert receipt["closure"]["support_gate_is_provisional_until_closure"] is True


def test_accepts_snapshot_advance_with_unchanged_prefix(tmp_path: Path) -> None:
    receipt = chain.verify(wl_fixture(tmp_path, churn=False))
    assert receipt["cohort_churn"]["added_runs"] == 0
    assert receipt["cohort_churn"]["removed_runs"] == 0
    assert receipt["prediction_intersection"]["pairs"]["common"] == 2


def test_legacy_append_verifier_rejects_valid_churn(tmp_path: Path) -> None:
    args = wl_fixture(tmp_path)
    legacy_args = argparse.Namespace(
        prior_artifact=args.prior_artifact,
        current_artifact=args.current_artifact,
        current_independent_verification=args.current_independent_verification,
        expect_scorer_commit=SCORER_COMMIT,
        expect_prior_summary_sha256=args.expect_prior_summary_sha256,
        expect_prior_snapshot_sha256=PRIOR_SHA,
        expect_current_snapshot_sha256=CURRENT_SHA,
        trace=[],
        scan_root=[],
    )
    with pytest.raises(legacy_wl.AppendVerificationError, match="not a subset"):
        legacy_wl.verify(legacy_args)


def test_rejects_changed_prediction_on_shared_run(tmp_path: Path) -> None:
    args = wl_fixture(tmp_path)
    endpoint_path = args.current_artifact / "endpoint_scores.csv"
    text = endpoint_path.read_text(encoding="utf-8").replace("a,task-old-1", "a,task-tampered", 1)
    endpoint_path.write_text(text, encoding="utf-8")
    summary = json.loads((args.current_artifact / "summary.json").read_text())
    summary["outputs"]["endpoint_scores_sha256"] = sha(endpoint_path)
    write_json(args.current_artifact / "summary.json", summary)
    write_json(
        args.current_artifact / "sha256_manifest.json",
        {name: sha(args.current_artifact / name) for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")},
    )
    args.expect_current_summary_sha256 = sha(args.current_artifact / "summary.json")
    write_wl_independent(args.current_independent_verification, args.current_artifact, CURRENT_SHA)
    with pytest.raises(chain.SnapshotChainError):
        chain.verify(args)


def test_rejects_mutated_prior_physical_run(tmp_path: Path) -> None:
    args = wl_fixture(tmp_path)
    path = args.current_snapshot_root / "accumulator" / "provisional_runs.jsonl"
    first_path = args.current_snapshot_root / "accumulator" / "provisional_first960_runs.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    next(row for row in rows if row["run_id"] == "old-1")["task"] = "changed"
    write_jsonl(path, rows)
    first_rows = [json.loads(line) for line in first_path.read_text().splitlines()]
    next(row for row in first_rows if row["run_id"] == "old-1")["task"] = "changed"
    write_jsonl(first_path, first_rows)
    summary_path = args.current_snapshot_root / "accumulator" / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["outputs"]["provisional_runs_sha256"] = sha(path)
    summary["outputs"]["provisional_first960_runs_sha256"] = sha(first_path)
    write_json(summary_path, summary)
    with pytest.raises(chain.SnapshotChainError, match="prior physical run row changed"):
        chain.verify(args)


def test_accepts_transition_churn_only_when_rebuilt_without_legacy_prior_gate(tmp_path: Path) -> None:
    prior_snapshot = tmp_path / "prior-snapshot"
    current_snapshot = tmp_path / "current-snapshot"
    old_1 = run_row("old-1", "2026-08-21T01:00:00Z")
    old_2 = run_row("old-2", "2026-08-21T02:00:00Z")
    new = run_row("new", "2026-08-21T00:30:00Z")
    write_snapshot(prior_snapshot, [old_1, old_2])
    write_snapshot(current_snapshot, [old_1, old_2, new])
    prior_artifact = tmp_path / "prior-transition"
    current_artifact = tmp_path / "current-transition"
    prior_summary = write_transition_artifact(
        prior_artifact,
        PRIOR_SHA,
        [transition_pair("old-1", "a", "b"), transition_pair("old-2", "c", "d")],
        prior_used=True,
    )
    current_summary = write_transition_artifact(
        current_artifact,
        CURRENT_SHA,
        [transition_pair("new", "e", "f"), transition_pair("old-1", "a", "b")],
        prior_used=False,
    )
    independent = tmp_path / "transition-independent.json"
    write_transition_independent(independent, current_artifact)
    args = argparse.Namespace(
        family="transition",
        prior_snapshot_root=prior_snapshot,
        current_snapshot_root=current_snapshot,
        expect_prior_snapshot_sha256=PRIOR_SHA,
        expect_current_snapshot_sha256=CURRENT_SHA,
        prior_artifact=prior_artifact,
        current_artifact=current_artifact,
        expect_prior_summary_sha256=prior_summary,
        expect_current_summary_sha256=current_summary,
        current_independent_verification=independent,
    )
    receipt = chain.verify(args)
    assert receipt["prediction_intersection"]["pairs"]["common"] == 1
    summary = json.loads((current_artifact / "summary.json").read_text())
    summary["append"]["prior_used"] = True
    write_json(current_artifact / "summary.json", summary)
    args.expect_current_summary_sha256 = sha(current_artifact / "summary.json")
    write_transition_independent(independent, current_artifact)
    with pytest.raises(chain.SnapshotChainError, match="must be independently rebuilt"):
        chain.verify(args)


def test_protocol_freezes_nonmonotone_prefix_and_no_unlock() -> None:
    value = json.loads(
        (ROOT / "phase1" / "provisional_first960_snapshot_chain_protocol_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert value["protocol"] == chain.PROTOCOL
    assert value["cohort_order"]["target_physical_runs"] == 960
    assert value["source_append_invariant"]["file_byte_prefix_required"] is False
    assert value["closure"]["effect_or_accuracy_unlock_before_closure"] is False
    assert value["closure"]["preclosure_support_gate_status"].startswith("provisional")


def test_transition_monitor_rebuilds_current_artifact_without_legacy_prior_gate() -> None:
    text = (
        ROOT / "phase1" / "scripts" / "monitor_transition_snapshot_chain_20260826.sh"
    ).read_text(encoding="utf-8")
    producer = text.split("  producer=(", 1)[1].split("  verifier=(", 1)[0]
    verifier = text.split("  verifier=(", 1)[1].split("  printf '%q ' \"${producer[@]}\"", 1)[0]
    chain_command = text.split("  chain_command=(", 1)[1].split("  printf '%q ' \"${chain_command[@]}\"", 1)[0]
    assert "--prior-artifact" not in producer
    assert "--prior-artifact" not in verifier
    assert "--prior-artifact" in chain_command
    assert "--current-artifact" in chain_command
    for variable in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
    ):
        assert f"export {variable}=1" in text
    assert "effect_metrics=0" in text
    assert "gpu_jobs=0" in text
    for variable in (
        "SNAPSHOT_CHAIN_LEGACY_MONITOR_ROOT",
        "SNAPSHOT_CHAIN_STATE_ROOT",
        "SNAPSHOT_CHAIN_OUTPUT_ROOT",
        "SNAPSHOT_CHAIN_MONITOR_ROOT",
    ):
        assert f"${{{variable}:-" in text
