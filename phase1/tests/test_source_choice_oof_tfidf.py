import hashlib
import json
from pathlib import Path

from phase1 import source_choice_oof_tfidf as oof
from phase1 import verify_source_choice_oof_tfidf as verifier


def identity(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    path.write_bytes(b"".join(oof.canonical(row) + b"\n" for row in rows))


def fixture(tmp_path: Path):
    groups = []
    clusters = []
    for task_index in range(5):
        task = f"task-{task_index}"
        for run_index in range(2):
            stem = f"{task}-{run_index}"
            winner_code = f"print('winning_pattern {stem}')"
            loser_code = f"print('losing_pattern {stem}')"
            winner = {
                "candidate_id_sha256": identity(stem + "-winner"),
                "code": winner_code,
                "code_sha256": identity(winner_code),
                "operator": "Improve",
                "step": 2,
                "depth": 1,
            }
            loser = {
                "candidate_id_sha256": identity(stem + "-loser"),
                "code": loser_code,
                "code_sha256": identity(loser_code),
                "operator": "Improve",
                "step": 1,
                "depth": 1,
            }
            candidates = sorted([winner, loser], key=lambda row: row["candidate_id_sha256"])
            group_id = identity(stem + "-group")
            groups.append({
                "schema_version": oof.MODEL_SCHEMA,
                "group_id": group_id,
                "task": task,
                "source_size": 2,
                "candidates": candidates,
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
    groups.sort(key=lambda row: row["group_id"])
    clusters.sort(key=lambda row: row["group_id"])
    train = tmp_path / "train.jsonl"
    cluster = tmp_path / "cluster.jsonl"
    write_jsonl(train, groups)
    write_jsonl(cluster, clusters)
    protocol = {
        "protocol": oof.PROTOCOL_NAME,
        "inputs": {
            "train_model": {"sha256": oof.sha256_file(train), "bytes": train.stat().st_size, "rows": 10},
            "cluster_manifest": {"sha256": oof.sha256_file(cluster), "bytes": cluster.stat().st_size, "rows": 10},
        },
        "expected_train": {
            "groups": 10,
            "candidate_slots": 20,
            "tasks": 5,
            "runs": 10,
            "unique_candidate_ids": 20,
            "cross_run_code_hashes": 0,
            "cross_task_code_hashes": 0,
            "source_size_counts": {"2": 10},
        },
        "splits": {
            "primary": {"name": "task_loto", "unit": "task", "folds": 5},
            "secondary": {
                "name": "run_grouped_5fold",
                "unit": "physical_run",
                "folds": 2,
                "assignment_seed": 20260822,
                "assignment": "within_task_descending_run_load_then_global_load_then_sha_tie",
            },
        },
        "model": {
            "name": "tfidf_pairwise_lr",
            "code_prefix_chars": 20000,
            "vectorizer": {
                "analyzer": "char_wb",
                "ngram_min": 3,
                "ngram_max": 5,
                "max_features": 500,
                "min_df": 1,
                "sublinear_tf": True,
                "dtype": "float64",
            },
            "pair_construction": "winner_minus_each_loser_plus_exact_negative_orientation",
            "group_weight": "each_choice_set_total_weight_one",
            "logistic_regression": {"C": 0.5, "solver": "lbfgs", "max_iter": 200, "random_state": 0},
        },
        "controls": list(oof.ARMS[:3]) + [oof.ARMS[4]],
        "metrics": {
            "primary": "task_macro_top1_delta_over_exact_uniform",
            "secondary": ["micro_top1_delta_over_exact_uniform"],
            "bootstrap_replicates": 1000,
            "task_bootstrap_seed": 20260822,
            "run_bootstrap_seed": 20260823,
            "task_sign_test": "one_sided_exact_positive_ignoring_exact_zero",
        },
        "gate": {
            "minimum_absolute_task_macro_delta": 0.03,
            "maximum_one_sided_task_sign_p": 0.05,
            "cross_task": "fixed",
            "run_only": "fixed",
            "outcomes": ["GO_CROSS_TASK", "GO_RUN_ONLY", "NO_NARROW_POSITIVE"],
        },
        "scope": {
            "train_model_only": True,
            "cluster_manifest_for_split_and_inference_only": True,
            "frozen_or_extension_model_read": False,
            "frozen_or_extension_label_vault_read": False,
            "hyperparameter_search": False,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updated": False,
        },
    }
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    return protocol_path, train, cluster


def test_synthetic_oof_recovers_cross_task_signal(tmp_path: Path):
    protocol, train, cluster = fixture(tmp_path)
    output = tmp_path / "output"
    result = oof.analyze(protocol, train, cluster, output)
    assert result["verdict"] == "GO_CROSS_TASK"
    assert result["models_fitted"] == 7
    assert result["metrics"]["task_loto"]["tfidf_pairwise_lr"]["micro_accuracy"] == 1.0
    assert result["metrics"]["run_grouped_5fold"]["winner_oracle"]["micro_accuracy"] == 1.0
    assert sum(1 for _ in (output / "predictions.csv").open(encoding="utf-8")) == 101
    checked = verifier.verify(protocol, train, cluster, output)
    assert checked["status"] == "INDEPENDENT_SOURCE_CHOICE_OOF_TFIDF_VERIFIED"
    assert checked["producer_imported"] is False
    assert checked["verdict"] == "GO_CROSS_TASK"
