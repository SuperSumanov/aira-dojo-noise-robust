#!/usr/bin/env python3
"""Seal label-free source-choice rankings after an independently verified OOF GO."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import sklearn
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from phase1 import source_choice_oof_tfidf as oof


PROTOCOL_NAME = "source-choice-prediction-escrow-v1"
TARGET_GROUP_FIELDS = oof.GROUP_FIELDS - {"winner_candidate_sha256"}
PREDICTION_ARMS = oof.ARMS[:3] + ("tfidf_pairwise_lr",)


def bind(path: Path, receipt: dict[str, Any], where: str) -> None:
    oof.require(path.is_file(), f"missing input: {where}")
    oof.require(path.stat().st_size == receipt["bytes"], f"byte count differs: {where}")
    oof.require(oof.sha256_file(path) == receipt["sha256"], f"SHA differs: {where}")


def load_protocol(path: Path) -> dict[str, Any]:
    value = oof.read_json(path, "escrow protocol")
    oof.require(value.get("protocol") == PROTOCOL_NAME, "escrow protocol name differs")
    oof.require(
        set(value) == {
            "protocol", "activation", "inputs", "expected", "model", "outputs",
            "claim_boundary", "resources",
        },
        "escrow protocol fields differ",
    )
    oof.require(value["outputs"]["arms"] == list(PREDICTION_ARMS), "prediction arms differ")
    boundary = value["claim_boundary"]
    oof.require(boundary["frozen_or_extension_label_vault_read"] is False, "label scope differs")
    oof.require(boundary["frozen_or_extension_metric_computed"] is False, "metric scope differs")
    return value


def check_activation(
    protocol: dict[str, Any], verification_path: Path, result_commit_path: Path
) -> dict[str, Any]:
    verification = oof.read_json(verification_path, "independent activation verification")
    activation = protocol["activation"]
    oof.require(
        verification.get("status") == activation["required_independent_verification_status"],
        "independent verification status differs",
    )
    verdict = verification.get("verdict")
    oof.require(verdict in activation["allowed_verdicts"], "OOF verdict does not activate escrow")
    oof.require(verdict != activation["blocked_verdict"], "blocked OOF verdict")
    oof.require(verification.get("producer_imported") is False, "verification imported producer")
    oof.require(verification.get("model_refit_by_verifier") is False, "verification refit model")
    oof.require(
        verification.get("frozen_or_extension_model_read") is False
        and verification.get("frozen_or_extension_label_vault_read") is False,
        "activation verification crossed frozen boundary",
    )
    try:
        result_commit = result_commit_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise oof.OOFError("cannot read result commit receipt") from exc
    oof.require(
        result_commit == activation["required_formal_result_commit"],
        "formal result commit differs",
    )
    summary_sha = verification.get("summary_sha256")
    oof.valid_hash(summary_sha, "activation summary")
    return {
        "verdict": verdict,
        "formal_result_commit": result_commit,
        "formal_summary_sha256": summary_sha,
        "independent_verification_sha256": oof.sha256_file(verification_path),
    }


def shared_model(protocol: dict[str, Any], oof_protocol: dict[str, Any]) -> dict[str, Any]:
    expected = protocol["model"]
    observed = oof_protocol["model"]
    for key in (
        "name", "code_prefix_chars", "vectorizer", "pair_construction", "group_weight",
        "logistic_regression",
    ):
        oof.require(expected[key] == observed[key], f"escrow/OOF model differs: {key}")
    oof.require(expected["hyperparameter_search"] is False, "hyperparameter search enabled")
    return observed


def load_target_role(
    path: Path,
    role: str,
    receipt: dict[str, Any],
    clusters: dict[str, dict[str, Any]],
    seen_candidates: set[str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    bind(path, receipt, f"{role} model")
    rows = oof.read_canonical_jsonl(path, f"{role} model")
    oof.require(len(rows) == receipt["rows"], f"{role} row count differs")
    groups: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, Any]] = {}
    group_ids: set[str] = set()
    for number, row in enumerate(rows, 1):
        oof.require(
            set(row) == TARGET_GROUP_FIELDS and row.get("schema_version") == oof.MODEL_SCHEMA,
            f"{role} group schema {number}",
        )
        group_id = oof.valid_hash(row.get("group_id"), f"{role} group")
        oof.require(group_id not in group_ids, f"duplicate {role} group")
        group_ids.add(group_id)
        cluster = clusters.get(group_id)
        oof.require(cluster is not None and cluster["role"] == role, f"{role} cluster closure")
        task = row.get("task")
        source_size = oof.valid_int(row.get("source_size"), f"{role} source size")
        values = row.get("candidates")
        oof.require(
            isinstance(task, str) and task == cluster["task"]
            and source_size == cluster["source_size"]
            and isinstance(values, list) and len(values) == source_size,
            f"{role} group metadata differs",
        )
        ids = []
        for candidate in values:
            oof.require(isinstance(candidate, dict) and set(candidate) == oof.CANDIDATE_FIELDS, "candidate fields differ")
            candidate_id = oof.valid_hash(candidate.get("candidate_id_sha256"), f"{role} candidate")
            code = candidate.get("code")
            oof.require(candidate_id not in seen_candidates and candidate_id not in candidates, "candidate repeats across roles")
            oof.require(isinstance(code, str) and code, "empty target code")
            oof.require(hashlib.sha256(code.encode()).hexdigest() == candidate.get("code_sha256"), "target code hash differs")
            oof.require(candidate.get("operator") in {"Draft", "Improve"}, "target operator differs")
            oof.valid_int(candidate.get("step"), "target step")
            oof.valid_int(candidate.get("depth"), "target depth")
            candidates[candidate_id] = candidate
            ids.append(candidate_id)
        oof.require(ids == sorted(ids) and len(ids) == len(set(ids)), "target candidate order differs")
        groups.append(row)
    seen_candidates.update(candidates)
    return groups, candidates


def fit_full(
    train_groups: list[dict[str, Any]],
    target_groups: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, list[str]], dict[str, list[float]], dict[str, Any]]:
    train_ids = sorted(item["candidate_id_sha256"] for row in train_groups for item in row["candidates"])
    target_ids = sorted(item["candidate_id_sha256"] for row in target_groups for item in row["candidates"])
    oof.require(not (set(train_ids) & set(target_ids)), "train/target candidate overlap")
    all_ids = sorted(train_ids + target_ids)
    positions = {candidate_id: index for index, candidate_id in enumerate(all_ids)}
    vector = config["vectorizer"]
    prefix = config["code_prefix_chars"]
    tfidf = TfidfVectorizer(
        analyzer=vector["analyzer"],
        ngram_range=(vector["ngram_min"], vector["ngram_max"]),
        max_features=vector["max_features"],
        min_df=vector["min_df"],
        sublinear_tf=vector["sublinear_tf"],
        dtype=np.float64,
    )
    tfidf.fit((candidates[candidate_id]["code"][:prefix] for candidate_id in train_ids))
    matrix = tfidf.transform(
        (candidates[candidate_id]["code"][:prefix] for candidate_id in all_ids)
    ).tocsr()

    differences = []
    weights = []
    relations = 0
    for row in train_groups:
        winner = row["winner_candidate_sha256"]
        losers = [item["candidate_id_sha256"] for item in row["candidates"] if item["candidate_id_sha256"] != winner]
        weight = 1.0 / (2.0 * len(losers))
        for loser in losers:
            differences.append(matrix[positions[winner]] - matrix[positions[loser]])
            weights.append(weight)
            relations += 1
    difference = sparse.vstack(differences, format="csr")
    fit_x = sparse.vstack((difference, -difference), format="csr")
    fit_y = np.concatenate((np.ones(relations, dtype=np.int8), np.zeros(relations, dtype=np.int8)))
    fit_weight = np.asarray(weights + weights, dtype=np.float64)
    oof.require(abs(float(fit_weight.sum()) - len(train_groups)) < 1e-9, "full-fit weights differ")
    logistic = config["logistic_regression"]
    model = LogisticRegression(
        C=logistic["C"], solver=logistic["solver"], max_iter=logistic["max_iter"],
        random_state=logistic["random_state"],
    ).fit(fit_x, fit_y, sample_weight=fit_weight)
    oof.require(int(model.n_iter_[0]) < logistic["max_iter"], "full-fit LR did not converge")
    oof.require(np.isfinite(model.coef_).all() and np.isfinite(model.intercept_).all(), "non-finite model")

    rankings: dict[str, list[str]] = {}
    raw_scores: dict[str, list[float]] = {}
    for row in target_groups:
        ids = [item["candidate_id_sha256"] for item in row["candidates"]]
        values = model.decision_function(matrix[[positions[candidate_id] for candidate_id in ids]]).tolist()
        oof.require(np.isfinite(values).all(), "non-finite target score")
        ordered = sorted(zip(values, ids), key=lambda item: (-item[0], item[1]))
        rankings[row["group_id"]] = [candidate_id for _, candidate_id in ordered]
        score_by_id = dict(zip(ids, values))
        raw_scores[row["group_id"]] = [float(score_by_id[candidate_id]) for candidate_id in rankings[row["group_id"]]]
    coefficient = np.asarray(model.coef_, dtype="<f8").tobytes() + np.asarray(model.intercept_, dtype="<f8").tobytes()
    receipt = {
        "train_groups": len(train_groups), "target_groups": len(target_groups),
        "train_candidates": len(train_ids), "target_candidates": len(target_ids),
        "winner_loser_relations": relations, "oriented_fit_rows": 2 * relations,
        "fit_weight_sum": float(fit_weight.sum()), "vocabulary_size": len(tfidf.vocabulary_),
        "lr_iterations": int(model.n_iter_[0]),
        "coefficient_sha256": hashlib.sha256(coefficient).hexdigest(),
    }
    return rankings, raw_scores, receipt


def predict(
    protocol_path: Path,
    oof_protocol_path: Path,
    train_path: Path,
    frozen_path: Path,
    extension_path: Path,
    cluster_path: Path,
    activation_verification_path: Path,
    activation_result_commit_path: Path,
    output: Path,
) -> dict[str, Any]:
    oof.require(not output.exists(), "output directory exists")
    protocol = load_protocol(protocol_path)
    oof_protocol = oof.load_protocol(oof_protocol_path)
    model_config = shared_model(protocol, oof_protocol)
    activation = check_activation(protocol, activation_verification_path, activation_result_commit_path)
    train_groups, train_candidates, train_clusters, train_census = oof.load_data(
        train_path, cluster_path, oof_protocol
    )
    for key in ("train_model", "cluster_manifest"):
        for field in ("sha256", "bytes", "rows"):
            oof.require(
                protocol["inputs"][key][field] == oof_protocol["inputs"][key][field],
                f"escrow input differs: {key}:{field}",
            )
    cluster_rows = oof.read_canonical_jsonl(cluster_path, "cluster manifest")
    clusters = {row["group_id"]: row for row in cluster_rows}
    oof.require(len(clusters) == len(cluster_rows), "duplicate cluster group")
    for role, expected_groups in (
        ("train", protocol["expected"]["train_groups"]),
        ("frozen", protocol["expected"]["frozen_groups"]),
        ("extension", protocol["expected"]["extension_groups"]),
    ):
        oof.require(
            sum(row["role"] == role for row in cluster_rows) == expected_groups,
            f"cluster role count differs: {role}",
        )
    seen = set(train_candidates)
    frozen_groups, frozen_candidates = load_target_role(
        frozen_path, "frozen", protocol["inputs"]["frozen_model"], clusters, seen
    )
    extension_groups, extension_candidates = load_target_role(
        extension_path, "extension", protocol["inputs"]["extension_model"], clusters, seen
    )
    expected = protocol["expected"]
    observed = {
        "train_groups": len(train_groups), "train_candidates": len(train_candidates),
        "frozen_groups": len(frozen_groups), "frozen_candidates": len(frozen_candidates),
        "extension_groups": len(extension_groups), "extension_candidates": len(extension_candidates),
        "tasks": len({row["task"] for row in train_groups + frozen_groups + extension_groups}),
    }
    for key, value in observed.items():
        oof.require(value == expected[key], f"escrow census differs: {key}")
    train_runs = {item["run_id_sha256"] for item in train_clusters.values()}
    train_parents = {item["parent_id_sha256"] for item in train_clusters.values()}
    frozen_clusters = [clusters[row["group_id"]] for row in frozen_groups]
    oof.require(len(train_runs & {item["run_id_sha256"] for item in frozen_clusters}) == expected["train_frozen_run_overlap"], "train/frozen run overlap")
    oof.require(len(train_parents & {item["parent_id_sha256"] for item in frozen_clusters}) == expected["train_frozen_parent_overlap"], "train/frozen parent overlap")

    targets = frozen_groups + extension_groups
    candidates = {**train_candidates, **frozen_candidates, **extension_candidates}
    rankings, scores, model_receipt = fit_full(train_groups, targets, candidates, model_config)
    output.mkdir(parents=True)
    predictions_path = output / "predictions.csv"
    fields = [
        "role", "arm", "group_id", "task", "run_id_sha256", "source_size",
        "selected_candidate_sha256", "ranking_candidate_sha256_json", "raw_model_scores_json",
    ]
    rows = []
    role_groups = {"frozen": frozen_groups, "extension": extension_groups}
    for role in protocol["outputs"]["roles"]:
        for row in sorted(role_groups[role], key=lambda item: item["group_id"]):
            candidate_ids = {item["candidate_id_sha256"] for item in row["candidates"]}
            for arm in PREDICTION_ARMS:
                ranking = rankings[row["group_id"]] if arm == "tfidf_pairwise_lr" else oof.control_ranking(row, arm)
                oof.require(set(ranking) == candidate_ids, "prediction ranking closure differs")
                raw = scores[row["group_id"]] if arm == "tfidf_pairwise_lr" else None
                rows.append({
                    "role": role, "arm": arm, "group_id": row["group_id"], "task": row["task"],
                    "run_id_sha256": clusters[row["group_id"]]["run_id_sha256"],
                    "source_size": row["source_size"], "selected_candidate_sha256": ranking[0],
                    "ranking_candidate_sha256_json": json.dumps(ranking, separators=(",", ":")),
                    "raw_model_scores_json": "" if raw is None else json.dumps(raw, separators=(",", ":"), allow_nan=False),
                })
    with predictions_path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    receipt_path = output / "model_receipt.json"
    oof.write_json(receipt_path, model_receipt)
    summary = {
        "protocol": PROTOCOL_NAME,
        "status": "SOURCE_CHOICE_PREDICTION_ESCROW_COMPLETE",
        "activation": activation,
        "census": observed,
        "prediction_rows": len(rows),
        "model_receipt": model_receipt,
        "input_sha256": {key: value["sha256"] for key, value in protocol["inputs"].items()},
        "outputs": {
            "predictions.csv": oof.sha256_file(predictions_path),
            "model_receipt.json": oof.sha256_file(receipt_path),
        },
        "versions": {
            "python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "sklearn": sklearn.__version__,
        },
        "frozen_or_extension_label_vault_read": False,
        "frozen_or_extension_metric_computed": False,
        "search_or_quality_utility_claimed": False,
    }
    summary_path = output / "summary.json"
    oof.write_json(summary_path, summary)
    oof.write_json(
        output / "sha256_manifest.json",
        {path.name: oof.sha256_file(path) for path in (predictions_path, receipt_path, summary_path)},
    )
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--oof-protocol", required=True)
    value.add_argument("--train-model", required=True)
    value.add_argument("--frozen-model", required=True)
    value.add_argument("--extension-model", required=True)
    value.add_argument("--cluster-manifest", required=True)
    value.add_argument("--activation-verification", required=True)
    value.add_argument("--activation-result-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = predict(
            Path(args.protocol).resolve(), Path(args.oof_protocol).resolve(),
            Path(args.train_model).resolve(), Path(args.frozen_model).resolve(),
            Path(args.extension_model).resolve(), Path(args.cluster_manifest).resolve(),
            Path(args.activation_verification).resolve(),
            Path(args.activation_result_commit).resolve(), Path(args.output).resolve(),
        )
        print(result["status"])
        return 0
    except oof.OOFError as exc:
        print(f"SOURCE_CHOICE_PREDICTION_ESCROW_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
