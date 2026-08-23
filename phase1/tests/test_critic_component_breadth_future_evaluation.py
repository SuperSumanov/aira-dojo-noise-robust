from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import evaluate_critic_component_breadth_future_escrow as evaluator


ROOT = Path(__file__).parents[2]
PROTOCOL = ROOT / "phase1" / "critic_component_breadth_future_evaluation_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_parent(index: int, *, task_count: int = 50, candidates: int = 2) -> dict:
    ids = [f"card-{index}-{position}" for position in range(candidates)]
    return {
        "schema_version": "score-channel-future-selected-parent-v1",
        "task": f"task-{index % task_count:02d}",
        "run_id": f"run-{index}",
        "parent_id": f"parent-{index}",
        "source_intake": "drop",
        "selection_rank_in_run": 1,
        "selection_key_sha256": f"{index + 1:064x}",
        "candidate_card_ids": ids,
        "candidate_count": len(ids),
        "candidate_identity_sha256": hashlib.sha256(
            json.dumps(ids, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def prediction_row(parent: dict, *, broad: float, concentrated: float, random: float) -> dict:
    left, right = parent["candidate_card_ids"]
    row = {
        "task": parent["task"],
        "run_id": parent["run_id"],
        "parent": parent["parent_id"],
        "left": left,
        "right": right,
        "pair_key_sha256": hashlib.sha256(f"{left}\0{right}".encode()).hexdigest(),
    }
    margins = {"broad": broad, "concentrated": concentrated, "random": random}
    for seed in evaluator.SEEDS:
        for arm in evaluator.ARMS:
            key = f"{arm}_s{seed}"
            margin = margins[arm]
            row[f"{key}_margin_left_minus_right"] = margin
            row[f"{key}_selected"] = left if margin > 0 else right if margin < 0 else "tie"
    return row


def test_protocol_is_exact_and_pretruth() -> None:
    protocol = evaluator.load_protocol(PROTOCOL, evaluator.PROTOCOL_SHA256)
    assert digest(PROTOCOL) == evaluator.PROTOCOL_SHA256
    assert protocol["status"] == "PREREGISTERED_OUTCOME_EVALUATOR_BEFORE_FUTURE_TRUTH_OPEN"
    assert protocol["output_contract"]["pair_level_truth_orientations_written"] is False


def test_support_and_positive_rule_pass_on_balanced_synthetic() -> None:
    protocol = evaluator.load_protocol(PROTOCOL, evaluator.PROTOCOL_SHA256)
    selected = [selected_parent(index) for index in range(200)]
    vault = {
        card: {
            "graded": 1.0 if card.endswith("-0") else 0.0,
            "y_norm": 1.0 if card.endswith("-0") else 0.0,
        }
        for parent in selected
        for card in parent["candidate_card_ids"]
    }
    predictions = evaluator.pair_map(
        [prediction_row(parent, broad=2.0, concentrated=-2.0, random=0.0) for parent in selected]
    )
    support = evaluator.support_census(selected, vault, protocol)
    assert support["gates"]["all_pass"] is True
    assert support["counts"]["raw_nontied_selected_parents"] == 200
    rows = evaluator.task_metrics(selected, vault, predictions, "graded")
    summary, loto = evaluator.summarize_metrics(rows, protocol, primary=True)
    assert summary["broad_minus_concentrated_accuracy"] == 1.0
    assert summary["task_cluster_bootstrap_ci95"] == [1.0, 1.0]
    assert summary["positive_conditions"]["all_pass"] is True
    assert len(loto) == 50


def test_parent_macro_precedes_task_macro() -> None:
    first = selected_parent(0, task_count=1)
    second = selected_parent(1, task_count=1, candidates=3)
    selected = [first, second]
    vault = {
        card: {"graded": float(10 - position), "y_norm": float(10 - position)}
        for parent in selected
        for position, card in enumerate(parent["candidate_card_ids"])
    }
    rows = []
    for parent in selected:
        for left_index in range(len(parent["candidate_card_ids"])):
            for right_index in range(left_index + 1, len(parent["candidate_card_ids"])):
                left = parent["candidate_card_ids"][left_index]
                right = parent["candidate_card_ids"][right_index]
                correct = parent is first
                base = prediction_row(
                    {**parent, "candidate_card_ids": [left, right]},
                    broad=1.0 if correct else -1.0,
                    concentrated=1.0,
                    random=1.0,
                )
                rows.append(base)
    metrics = evaluator.task_metrics(selected, vault, evaluator.pair_map(rows), "graded")
    broad = next(
        row for row in metrics if row["arm"] == "broad" and row["selection_seed"] == evaluator.SEEDS[0]
    )
    assert broad["informative_parents"] == 2
    assert broad["informative_pairs"] == 4
    assert broad["parent_macro_accuracy"] == 0.5


def test_prediction_tie_credit_and_stable_log_loss() -> None:
    assert evaluator.pair_credit(0.0, 1.0) == 0.5
    assert evaluator.pair_credit(1.0, 1.0) == 1.0
    assert evaluator.pair_credit(-1.0, 1.0) == 0.0
    assert evaluator.pair_log_loss(1000.0, 1.0) >= 0.0
    assert evaluator.pair_log_loss(-1000.0, 1.0) == pytest.approx(1000.0)


def test_prediction_authentication_failure_precedes_truth_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject(*_args, **_kwargs):
        raise evaluator.EvaluationError("prediction tamper")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("truth was opened before prediction authentication")

    monkeypatch.setattr(evaluator, "validate_prediction", reject)
    monkeypatch.setattr(evaluator, "load_selected_and_truth", forbidden)
    args = argparse.Namespace(
        protocol=PROTOCOL,
        expect_protocol_sha256=evaluator.PROTOCOL_SHA256,
        prediction_dir=tmp_path / "prediction",
        expect_prediction_summary_sha256="0" * 64,
        expect_prediction_manifest_sha256="1" * 64,
        base_protocol=ROOT / "phase1" / "score_channel_future_identifiability_protocol_v1.json",
        cohort_dir=tmp_path / "cohort",
        expect_cohort_summary_sha256="2" * 64,
        state_root=tmp_path / "state",
        selected_parents=tmp_path / "selected",
        expect_selected_parents_sha256="3" * 64,
        repo_root=ROOT,
        output=tmp_path / "output",
    )
    with pytest.raises(evaluator.EvaluationError, match="prediction tamper"):
        evaluator.evaluate(args)


def test_insufficient_support_writes_no_effect_or_task_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = selected_parent(0)
    left, right = parent["candidate_card_ids"]
    prediction = prediction_row(parent, broad=1.0, concentrated=-1.0, random=0.0)
    prediction_summary = {"outputs": {"pair_predictions_sha256": "4" * 64}}
    vault = {
        left: {"graded": 1.0, "y_norm": 1.0},
        right: {"graded": 0.0, "y_norm": 0.0},
    }
    monkeypatch.setattr(
        evaluator, "validate_prediction", lambda *_args, **_kwargs: ([prediction], prediction_summary)
    )
    monkeypatch.setattr(
        evaluator,
        "load_selected_and_truth",
        lambda *_args, **_kwargs: ([parent], vault, {"intake_summary_sha256": {}}),
    )
    monkeypatch.setattr(evaluator, "repository_head", lambda _repo: "5" * 40)
    args = argparse.Namespace(
        protocol=PROTOCOL,
        expect_protocol_sha256=evaluator.PROTOCOL_SHA256,
        prediction_dir=tmp_path / "prediction",
        expect_prediction_summary_sha256="0" * 64,
        expect_prediction_manifest_sha256="1" * 64,
        base_protocol=ROOT / "phase1" / "score_channel_future_identifiability_protocol_v1.json",
        cohort_dir=tmp_path / "cohort",
        expect_cohort_summary_sha256="2" * 64,
        state_root=tmp_path / "state",
        selected_parents=tmp_path / "selected",
        expect_selected_parents_sha256="3" * 64,
        repo_root=ROOT,
        output=tmp_path / "output",
    )
    summary = evaluator.evaluate(args)
    assert summary["status"] == evaluator.STATUS_INSUFFICIENT
    assert summary["effects"] is None
    assert summary["scope"]["primary_effect_computed"] is False
    assert not (args.output / "task_metrics.jsonl").exists()
    assert not (args.output / "leave_one_task_out.jsonl").exists()


def test_cli_accepts_no_label_vault_argument() -> None:
    source = (ROOT / "phase1" / "evaluate_critic_component_breadth_future_escrow.py").read_text(
        encoding="utf-8"
    )
    assert "--label-vault" not in source


def test_evaluator_rejects_byte_identical_protocol_from_an_alternate_path(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "copied-protocol.json"
    copied.write_bytes(PROTOCOL.read_bytes())
    args = argparse.Namespace(
        repo_root=ROOT,
        protocol=copied,
        base_protocol=ROOT / "phase1" / "score_channel_future_identifiability_protocol_v1.json",
    )
    with pytest.raises(evaluator.EvaluationError, match="source/input path binding"):
        evaluator.bind_repository_sources(args)
