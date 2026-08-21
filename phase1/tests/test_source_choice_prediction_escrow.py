import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import source_choice_oof_tfidf as oof
from phase1 import source_choice_prediction_escrow as escrow


def identity(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    path.write_bytes(b"".join(oof.canonical(row) + b"\n" for row in rows))


def candidate(stem: str, kind: str, step: int):
    code = f"print('{kind}_pattern {stem}')"
    return {
        "candidate_id_sha256": identity(f"{stem}-{kind}"),
        "code": code,
        "code_sha256": identity(code),
        "operator": "Improve",
        "step": step,
        "depth": 1,
    }


def fixture(tmp_path: Path):
    train_groups = []
    target_groups = {"frozen": [], "extension": []}
    clusters = []
    for task_index in range(5):
        task = f"task-{task_index}"
        for run_index in range(2):
            stem = f"{task}-train-{run_index}"
            winner = candidate(stem, "winning", 2)
            loser = candidate(stem, "losing", 1)
            group_id = identity(stem + "-group")
            train_groups.append({
                "schema_version": oof.MODEL_SCHEMA,
                "group_id": group_id,
                "task": task,
                "source_size": 2,
                "candidates": sorted([winner, loser], key=lambda row: row["candidate_id_sha256"]),
                "winner_candidate_sha256": winner["candidate_id_sha256"],
            })
            clusters.append({
                "schema_version": oof.CLUSTER_SCHEMA,
                "group_id": group_id,
                "role": "train",
                "task": task,
                "run_id_sha256": identity(stem + "-run"),
                "parent_id_sha256": identity(stem + "-parent"),
                "source_size": 2,
            })
    for role, task_index in (("frozen", 0), ("extension", 1)):
        task = f"task-{task_index}"
        stem = f"{task}-{role}"
        values = sorted(
            [candidate(stem, "winning", 2), candidate(stem, "losing", 1)],
            key=lambda row: row["candidate_id_sha256"],
        )
        group_id = identity(stem + "-group")
        target_groups[role].append({
            "schema_version": oof.MODEL_SCHEMA,
            "group_id": group_id,
            "task": task,
            "source_size": 2,
            "candidates": values,
        })
        clusters.append({
            "schema_version": oof.CLUSTER_SCHEMA,
            "group_id": group_id,
            "role": role,
            "task": task,
            "run_id_sha256": identity(stem + "-run"),
            "parent_id_sha256": identity(stem + "-parent"),
            "source_size": 2,
        })
    train_groups.sort(key=lambda row: row["group_id"])
    clusters.sort(key=lambda row: row["group_id"])
    train = tmp_path / "train.jsonl"
    frozen = tmp_path / "frozen.jsonl"
    extension = tmp_path / "extension.jsonl"
    cluster = tmp_path / "cluster.jsonl"
    write_jsonl(train, train_groups)
    write_jsonl(frozen, target_groups["frozen"])
    write_jsonl(extension, target_groups["extension"])
    write_jsonl(cluster, clusters)

    model = {
        "name": "tfidf_pairwise_lr",
        "code_prefix_chars": 20000,
        "vectorizer": {
            "analyzer": "char_wb", "ngram_min": 3, "ngram_max": 5,
            "max_features": 500, "min_df": 1, "sublinear_tf": True, "dtype": "float64",
        },
        "pair_construction": "winner_minus_each_loser_plus_exact_negative_orientation",
        "group_weight": "each_choice_set_total_weight_one",
        "logistic_regression": {"C": 0.5, "solver": "lbfgs", "max_iter": 200, "random_state": 0},
    }
    inputs = {
        "train_model": {"sha256": oof.sha256_file(train), "bytes": train.stat().st_size, "rows": 10},
        "cluster_manifest": {"sha256": oof.sha256_file(cluster), "bytes": cluster.stat().st_size, "rows": 12},
    }
    oof_protocol = {
        "protocol": oof.PROTOCOL_NAME,
        "inputs": inputs,
        "expected_train": {
            "groups": 10, "candidate_slots": 20, "tasks": 5, "runs": 10,
            "unique_candidate_ids": 20, "cross_run_code_hashes": 0,
            "cross_task_code_hashes": 0, "source_size_counts": {"2": 10},
        },
        "splits": {
            "primary": {"name": "task_loto", "unit": "task", "folds": 5},
            "secondary": {
                "name": "run_grouped_5fold", "unit": "physical_run", "folds": 2,
                "assignment_seed": 20260822,
                "assignment": "within_task_descending_run_load_then_global_load_then_sha_tie",
            },
        },
        "model": model,
        "controls": list(oof.ARMS[:3]) + [oof.ARMS[4]],
        "metrics": {
            "primary": "task_macro_top1_delta_over_exact_uniform",
            "secondary": ["micro_top1_delta_over_exact_uniform"], "bootstrap_replicates": 100,
            "task_bootstrap_seed": 20260822, "run_bootstrap_seed": 20260823,
            "task_sign_test": "one_sided_exact_positive_ignoring_exact_zero",
        },
        "gate": {
            "minimum_absolute_task_macro_delta": 0.03, "maximum_one_sided_task_sign_p": 0.05,
            "cross_task": "fixed", "run_only": "fixed",
            "outcomes": ["GO_CROSS_TASK", "GO_RUN_ONLY", "NO_NARROW_POSITIVE"],
        },
        "scope": {
            "train_model_only": True, "cluster_manifest_for_split_and_inference_only": True,
            "frozen_or_extension_model_read": False,
            "frozen_or_extension_label_vault_read": False, "hyperparameter_search": False,
            "gpu": 0, "api_calls": 0, "base_llm_updated": False,
        },
    }
    oof_protocol_path = tmp_path / "oof_protocol.json"
    write_json(oof_protocol_path, oof_protocol)

    required_commit = "1" * 40
    escrow_inputs = {
        "train_model": {**inputs["train_model"], "winner_labels_present": True},
        "frozen_model": {
            "sha256": oof.sha256_file(frozen), "bytes": frozen.stat().st_size,
            "rows": 1, "winner_labels_present": False,
        },
        "extension_model": {
            "sha256": oof.sha256_file(extension), "bytes": extension.stat().st_size,
            "rows": 1, "winner_labels_present": False,
        },
        "cluster_manifest": inputs["cluster_manifest"],
    }
    escrow_protocol = {
        "protocol": escrow.PROTOCOL_NAME,
        "activation": {
            "required_formal_result_commit": required_commit,
            "required_independent_verification_status": "INDEPENDENT_SOURCE_CHOICE_OOF_TFIDF_VERIFIED",
            "allowed_verdicts": ["GO_CROSS_TASK", "GO_RUN_ONLY"],
            "blocked_verdict": "NO_NARROW_POSITIVE",
            "fail_closed_if_receipt_or_binding_differs": True,
        },
        "inputs": escrow_inputs,
        "expected": {
            "train_groups": 10, "train_candidates": 20, "frozen_groups": 1,
            "frozen_candidates": 2, "extension_groups": 1, "extension_candidates": 2,
            "tasks": 5, "train_frozen_run_overlap": 0, "train_frozen_parent_overlap": 0,
        },
        "model": {
            **model, "must_equal_oof_protocol_model_byte_for_byte": True,
            "oof_protocol": "synthetic", "hyperparameter_search": False,
        },
        "outputs": {
            "roles": ["frozen", "extension"], "arms": list(escrow.PREDICTION_ARMS),
            "one_row_per_role_arm_group": True, "include_full_candidate_ranking": True,
            "include_raw_model_scores": True, "include_winner_or_outcome": False,
            "producer_replicas": 2, "producer_outputs_must_be_byte_identical": True,
            "independent_structural_verifier_replicas": 2, "read_only_immutable_seal": True,
        },
        "claim_boundary": {
            "prediction_only": True, "frozen_or_extension_label_vault_read": False,
            "frozen_or_extension_metric_computed": False, "search_or_quality_utility_claimed": False,
            "causal_claimed": False, "new_task_transfer_claimed": False,
            "unblinding_requires_separate_result_blind_protocol_and_user_decision": True,
        },
        "resources": {"cpu_model_fits_per_producer": 1, "gpu": 0, "api_calls": 0, "base_llm_updated": False},
    }
    escrow_protocol_path = tmp_path / "escrow_protocol.json"
    write_json(escrow_protocol_path, escrow_protocol)
    verification = {
        "status": "INDEPENDENT_SOURCE_CHOICE_OOF_TFIDF_VERIFIED",
        "verdict": "GO_CROSS_TASK", "producer_imported": False,
        "model_refit_by_verifier": False, "summary_sha256": identity("summary"),
        "frozen_or_extension_model_read": False,
        "frozen_or_extension_label_vault_read": False,
    }
    verification_path = tmp_path / "verification.json"
    write_json(verification_path, verification)
    commit_path = tmp_path / "result_commit.txt"
    commit_path.write_text(required_commit + "\n", encoding="utf-8")
    return (
        escrow_protocol_path, oof_protocol_path, train, frozen, extension, cluster,
        verification_path, commit_path,
    )


def test_prediction_escrow_seals_label_free_rankings(tmp_path: Path):
    args = fixture(tmp_path)
    output = tmp_path / "output"
    summary = escrow.predict(*args, output)
    assert summary["status"] == "SOURCE_CHOICE_PREDICTION_ESCROW_COMPLETE"
    assert summary["prediction_rows"] == 8
    assert summary["frozen_or_extension_label_vault_read"] is False
    with (output / "predictions.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    learned = [row for row in rows if row["arm"] == "tfidf_pairwise_lr"]
    assert len(learned) == 2
    assert all(len(json.loads(row["ranking_candidate_sha256_json"])) == 2 for row in learned)
    assert all(len(json.loads(row["raw_model_scores_json"])) == 2 for row in learned)
    assert "winner" not in (output / "predictions.csv").read_text(encoding="utf-8")


def test_prediction_escrow_blocks_no_positive_verdict(tmp_path: Path):
    args = list(fixture(tmp_path))
    verification = json.loads(args[-2].read_text(encoding="utf-8"))
    verification["verdict"] = "NO_NARROW_POSITIVE"
    write_json(args[-2], verification)
    with pytest.raises(oof.OOFError, match="does not activate"):
        escrow.predict(*args, tmp_path / "blocked")
