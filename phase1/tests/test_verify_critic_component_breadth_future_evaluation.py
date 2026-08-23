from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from phase1 import verify_critic_component_breadth_future_evaluation as verifier


ROOT = Path(__file__).parents[2]
PROTOCOL = ROOT / "phase1" / "critic_component_breadth_future_evaluation_v1.json"
VERIFIER_SOURCE = ROOT / "phase1" / "verify_critic_component_breadth_future_evaluation.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_parent(index: int, *, task_count: int = 50, candidates: int = 2) -> dict:
    card_ids = [f"card-{index:03d}-{position}" for position in range(candidates)]
    return {
        "schema_version": verifier.SELECTED_ROW_SCHEMA,
        "task": f"task-{index % task_count:02d}",
        "run_id": f"run-{index:03d}",
        "parent_id": f"parent-{index:03d}",
        "source_intake": "synthetic-drop",
        "selection_rank_in_run": 1,
        "selection_key_sha256": f"{index + 1:064x}",
        "candidate_card_ids": card_ids,
        "candidate_count": len(card_ids),
        "candidate_identity_sha256": verifier.sha_text(verifier.compact(card_ids)),
    }


def prediction_row(
    parent: dict, *, broad: float, concentrated: float, random: float
) -> dict:
    left, right = parent["candidate_card_ids"]
    row = {
        "task": parent["task"],
        "run_id": parent["run_id"],
        "parent": parent["parent_id"],
        "left": left,
        "right": right,
        "pair_key_sha256": verifier.sha_text(f"{left}\0{right}"),
    }
    margins = {"broad": broad, "concentrated": concentrated, "random": random}
    for seed in verifier.SEEDS:
        for arm in verifier.ARMS:
            key = f"{arm}_s{seed}"
            margin = margins[arm]
            row[f"{key}_margin_left_minus_right"] = margin
            row[f"{key}_selected"] = left if margin > 0 else right if margin < 0 else "tie"
    return row


@pytest.fixture(scope="module")
def positive_case() -> tuple[dict, list[dict], dict[str, dict], list[dict], dict]:
    protocol = verifier.load_evaluation_protocol(PROTOCOL, verifier.EVALUATION_PROTOCOL_SHA256)
    selected = [selected_parent(index) for index in range(200)]
    vault = {
        card: {
            "graded": 1.0 if card.endswith("-0") else 0.0,
            "y_norm": 1.0 if card.endswith("-0") else 0.0,
        }
        for parent in selected
        for card in parent["candidate_card_ids"]
    }
    predictions = [
        prediction_row(parent, broad=2.0, concentrated=-2.0, random=0.0)
        for parent in selected
    ]
    statistics = verifier.recompute_statistics(selected, vault, predictions, protocol)
    return protocol, selected, vault, predictions, statistics


def summary_arguments() -> argparse.Namespace:
    return argparse.Namespace(
        repo_root=ROOT,
        expect_prediction_summary_sha256="1" * 64,
        expect_prediction_manifest_sha256="2" * 64,
        expect_cohort_summary_sha256="3" * 64,
        expect_selected_parents_sha256="4" * 64,
    )


def expected_output_summary(
    statistics: dict, monkeypatch: pytest.MonkeyPatch
) -> dict:
    monkeypatch.setattr(verifier, "repository_head", lambda _repo: "5" * 40)
    prediction_summary = {"outputs": {"pair_predictions_sha256": "6" * 64}}
    truth_inputs = {
        "intake_summary_sha256": {"synthetic-drop": "7" * 64},
        "eligible_parents_before_per_run_cap": 200,
        "runs_with_eligible_parent": 200,
    }
    return verifier.expected_summary(
        statistics, prediction_summary, truth_inputs, summary_arguments()
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(verifier.compact(row) + "\n")


def write_evaluation_artifact(
    directory: Path, summary: dict, task_rows: list[dict], loto_rows: list[dict]
) -> tuple[str, str]:
    directory.mkdir()
    (directory / "summary.json").write_bytes(verifier.canonical_bytes(summary))
    names = ["summary.json"]
    if task_rows:
        write_jsonl(directory / "task_metrics.jsonl", task_rows)
        write_jsonl(directory / "leave_one_task_out.jsonl", loto_rows)
        names.extend(("task_metrics.jsonl", "leave_one_task_out.jsonl"))
    manifest = {
        "protocol": f"{verifier.OUTPUT_PROTOCOL}-artifact-manifest-v1",
        "evaluation_protocol_sha256": verifier.EVALUATION_PROTOCOL_SHA256,
        "artifacts": {
            name: {
                "sha256": digest(directory / name),
                "bytes": (directory / name).stat().st_size,
            }
            for name in names
        },
    }
    manifest_path = directory / "artifact_manifest.json"
    manifest_path.write_bytes(verifier.canonical_bytes(manifest))
    return digest(directory / "summary.json"), digest(manifest_path)


def test_verifier_is_independent_and_parent_sha_binding_is_centralized() -> None:
    source = VERIFIER_SOURCE.read_text(encoding="utf-8")
    assert "import evaluate_critic_component_breadth_future_escrow" not in source
    assert "from phase1.evaluate_critic_component_breadth_future_escrow" not in source
    assert "--label-vault" not in source
    assert source.count(verifier.PARENT_PREDICTION_BINDING["contract_sha256"]) == 1
    assert digest(PROTOCOL) == verifier.EVALUATION_PROTOCOL_SHA256


def test_balanced_positive_case_recomputes_all_registered_statistics(
    positive_case: tuple[dict, list[dict], dict[str, dict], list[dict], dict],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _protocol, _selected, _vault, _predictions, statistics = positive_case
    assert statistics["status"] == verifier.STATUS_POSITIVE
    assert statistics["support"]["gates"]["all_pass"] is True
    assert statistics["support"]["counts"] == {
        "selected_parents": 200,
        "selected_candidates": 400,
        "raw_nontied_selected_parents": 200,
        "raw_nontied_pairs": 200,
        "selected_physical_runs_with_raw_nontied_parent": 200,
        "tasks_with_raw_nontied_selected_parent": 50,
    }
    primary = statistics["effects"]["primary_official_five_decimal_raw_grade"]
    assert primary["task_macro_accuracy"] == {
        "broad": 1.0,
        "concentrated": 0.0,
        "random": 0.5,
    }
    assert primary["broad_minus_concentrated_accuracy"] == 1.0
    assert primary["broad_minus_concentrated_accuracy_by_seed"] == {
        str(seed): 1.0 for seed in verifier.SEEDS
    }
    assert primary["task_cluster_bootstrap_ci95"] == [1.0, 1.0]
    assert primary["positive_conditions"]["all_pass"] is True
    assert statistics["effects"]["faithful_normalized_secondary"][
        "confirmatory_claim_allowed"
    ] is False
    assert statistics["effects"]["faithful_normalized_secondary"]["may_rescue_primary"] is False
    assert len(statistics["task_rows"]) == 50 * len(verifier.SEEDS) * len(verifier.ARMS) * 2
    assert len(statistics["loto_rows"]) == 100
    assert {row["effect"] for row in statistics["loto_rows"]} == {1.0}

    expected = expected_output_summary(statistics, monkeypatch)
    summary_sha, manifest_sha = write_evaluation_artifact(
        tmp_path / "positive",
        expected,
        statistics["task_rows"],
        statistics["loto_rows"],
    )
    hashes = verifier.validate_evaluation_artifact(
        tmp_path / "positive",
        summary_sha,
        manifest_sha,
        expected,
        statistics["task_rows"],
        statistics["loto_rows"],
    )
    assert hashes["summary.json"] == summary_sha


def test_pair_to_parent_to_task_aggregation_is_parent_macro() -> None:
    first = selected_parent(0, task_count=1)
    second = selected_parent(1, task_count=1, candidates=3)
    selected = [first, second]
    vault = {
        card: {"graded": float(10 - position), "y_norm": float(10 - position)}
        for parent in selected
        for position, card in enumerate(parent["candidate_card_ids"])
    }
    predictions: list[dict] = []
    for parent in selected:
        cards = parent["candidate_card_ids"]
        for left_index in range(len(cards)):
            for right_index in range(left_index + 1, len(cards)):
                pair_parent = {**parent, "candidate_card_ids": [cards[left_index], cards[right_index]]}
                predictions.append(
                    prediction_row(
                        pair_parent,
                        broad=1.0 if parent is first else -1.0,
                        concentrated=1.0,
                        random=0.0,
                    )
                )
    rows = verifier.task_metrics(
        selected, vault, verifier.prediction_map(predictions), "graded"
    )
    broad = next(
        row
        for row in rows
        if row["selection_seed"] == verifier.SEEDS[0] and row["arm"] == "broad"
    )
    assert broad["informative_parents"] == 2
    assert broad["informative_pairs"] == 4
    assert broad["parent_macro_accuracy"] == 0.5


def test_selected_parent_lottery_is_exact_and_grade_magnitude_blind() -> None:
    run = {"task": "task-a", "run_id": "run-a", "drop_id": "drop-a"}
    siblings = {
        ("task-a", "run-a", parent): {f"{parent}-left", f"{parent}-right"}
        for parent in ("parent-a", "parent-b", "parent-c")
    }
    vault = {
        card: {"graded": float(index + 1), "y_norm": None}
        for index, card in enumerate(sorted({card for cards in siblings.values() for card in cards}))
    }
    selected, eligible, runs_with = verifier.reconstruct_selected_parents(
        [run], siblings, vault, seed=20260813, max_parents=2
    )
    expected = sorted(
        (
            verifier.sha_text(f"20260813|run-a|{parent}"),
            parent,
        )
        for parent in ("parent-a", "parent-b", "parent-c")
    )[:2]
    assert eligible == 3
    assert runs_with == 1
    assert [(row["selection_key_sha256"], row["parent_id"]) for row in selected] == expected
    assert [row["selection_rank_in_run"] for row in selected] == [1, 2]
    assert all(
        row["candidate_identity_sha256"]
        == verifier.sha_text(verifier.compact(row["candidate_card_ids"]))
        for row in selected
    )

    rescaled_vault = {
        card: {**values, "graded": values["graded"] * 1000.0}
        for card, values in vault.items()
    }
    rescaled, _, _ = verifier.reconstruct_selected_parents(
        [run], siblings, rescaled_vault, seed=20260813, max_parents=2
    )
    assert rescaled == selected


def test_sha_bootstrap_type7_and_loto_primitives_are_deterministic() -> None:
    assert verifier.type7_quantile([0.0, 1.0, 2.0, 3.0], 0.25) == 0.75
    effects = {"task-a": -0.25, "task-b": 0.5, "task-c": 1.0}
    first = verifier.bootstrap_interval(effects, seed=17, replicates=31)
    second = verifier.bootstrap_interval(effects, seed=17, replicates=31)
    assert first == second
    assert all(math.isfinite(value) for value in first)


def test_support_failure_has_no_effects_or_metric_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol = verifier.load_evaluation_protocol(PROTOCOL, verifier.EVALUATION_PROTOCOL_SHA256)
    parent = selected_parent(0)
    left, right = parent["candidate_card_ids"]
    vault = {
        left: {"graded": 1.0, "y_norm": 1.0},
        right: {"graded": 0.0, "y_norm": 0.0},
    }
    statistics = verifier.recompute_statistics(
        [parent],
        vault,
        [prediction_row(parent, broad=1.0, concentrated=-1.0, random=0.0)],
        protocol,
    )
    assert statistics["status"] == verifier.STATUS_INSUFFICIENT
    assert statistics["support"]["gates"]["all_pass"] is False
    assert statistics["effects"] is None
    assert statistics["task_rows"] == []
    assert statistics["loto_rows"] == []

    expected = expected_output_summary(statistics, monkeypatch)
    assert expected["effects"] is None
    assert expected["scope"]["primary_effect_computed"] is False
    assert expected["scope"]["task_metrics_written"] is False
    summary_sha, manifest_sha = write_evaluation_artifact(
        tmp_path / "insufficient", expected, [], []
    )
    verifier.validate_evaluation_artifact(
        tmp_path / "insufficient",
        summary_sha,
        manifest_sha,
        expected,
        [],
        [],
    )
    assert not (tmp_path / "insufficient" / "task_metrics.jsonl").exists()
    assert not (tmp_path / "insufficient" / "leave_one_task_out.jsonl").exists()


def test_field_tamper_is_rejected_even_with_self_consistent_artifact_hashes(
    positive_case: tuple[dict, list[dict], dict[str, dict], list[dict], dict],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _protocol, _selected, _vault, _predictions, statistics = positive_case
    expected = expected_output_summary(statistics, monkeypatch)
    tampered = copy.deepcopy(expected)
    tampered["effects"]["primary_official_five_decimal_raw_grade"][
        "broad_minus_concentrated_accuracy"
    ] = 0.75
    summary_sha, manifest_sha = write_evaluation_artifact(
        tmp_path / "tampered",
        tampered,
        statistics["task_rows"],
        statistics["loto_rows"],
    )
    with pytest.raises(verifier.VerificationError, match="output numeric mismatch"):
        verifier.validate_evaluation_artifact(
            tmp_path / "tampered",
            summary_sha,
            manifest_sha,
            expected,
            statistics["task_rows"],
            statistics["loto_rows"],
        )


def test_prediction_tamper_fails_before_any_outcome_path_is_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome_opened = False

    def reject_prediction(*_args, **_kwargs):
        raise verifier.VerificationError("prediction tamper")

    def forbidden_outcome_open(*_args, **_kwargs):
        nonlocal outcome_opened
        outcome_opened = True
        raise AssertionError("outcome was opened before prediction authentication")

    monkeypatch.setattr(verifier, "authenticate_prediction_artifact", reject_prediction)
    monkeypatch.setattr(verifier, "reconstruct_outcomes_and_selection", forbidden_outcome_open)
    args = argparse.Namespace(
        protocol=PROTOCOL,
        expect_protocol_sha256=verifier.EVALUATION_PROTOCOL_SHA256,
        prediction_dir=tmp_path / "prediction",
        expect_prediction_summary_sha256="1" * 64,
        expect_prediction_manifest_sha256="2" * 64,
        base_protocol=ROOT / "phase1" / "score_channel_future_identifiability_protocol_v1.json",
        cohort_dir=tmp_path / "cohort",
        expect_cohort_summary_sha256="3" * 64,
        state_root=tmp_path / "state",
        selected_parents=tmp_path / "selected.jsonl",
        expect_selected_parents_sha256="4" * 64,
        repo_root=ROOT,
        evaluation_dir=tmp_path / "evaluation",
        expect_evaluation_summary_sha256="5" * 64,
        expect_evaluation_manifest_sha256="6" * 64,
        receipt=tmp_path / "receipt.json",
    )
    with pytest.raises(verifier.VerificationError, match="prediction tamper"):
        verifier.verify(args)
    assert outcome_opened is False
    assert not args.receipt.exists()


def test_verifier_rejects_byte_identical_protocol_from_an_alternate_path(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "copied-protocol.json"
    copied.write_bytes(PROTOCOL.read_bytes())
    args = argparse.Namespace(
        repo_root=ROOT,
        protocol=copied,
        base_protocol=ROOT / "phase1" / "score_channel_future_identifiability_protocol_v1.json",
    )
    with pytest.raises(verifier.VerificationError, match="source/input path binding"):
        verifier.bind_repository_sources(args)
