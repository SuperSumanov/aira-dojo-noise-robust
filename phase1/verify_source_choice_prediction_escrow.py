#!/usr/bin/env python3
"""Independent structural verifier for label-free source-choice prediction escrow."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "source-choice-prediction-escrow-v1"
MODEL_SCHEMA = "source-choice-decision-group-v2"
CLUSTER_SCHEMA = "source-choice-cluster-manifest-v1"
TRAIN_FIELDS = {
    "schema_version", "group_id", "task", "source_size", "candidates",
    "winner_candidate_sha256",
}
TARGET_FIELDS = TRAIN_FIELDS - {"winner_candidate_sha256"}
CANDIDATE_FIELDS = {
    "candidate_id_sha256", "code", "code_sha256", "operator", "step", "depth",
}
CLUSTER_FIELDS = {
    "schema_version", "group_id", "role", "task", "run_id_sha256",
    "parent_id_sha256", "source_size",
}
ARMS = (
    "min_candidate_sha", "max_step_then_min_sha", "max_code_length_then_min_sha",
    "tfidf_pairwise_lr",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def object_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {path.name}") from exc
    need(isinstance(value, dict), f"non-object JSON: {path.name}")
    return value


def rows_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("rb") as handle:
        for number, line in enumerate(handle, 1):
            need(line.endswith(b"\n"), f"unterminated JSONL row {number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"invalid JSONL row {number}") from exc
            need(isinstance(value, dict) and canonical(value) + b"\n" == line, f"non-canonical row {number}")
            rows.append(value)
    need(bool(rows), f"empty JSONL: {path.name}")
    return rows


def valid_hash(value: Any, where: str) -> str:
    need(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"bad hash: {where}")
    return value


def valid_int(value: Any, where: str) -> int:
    need(not isinstance(value, bool) and isinstance(value, int), f"bad integer: {where}")
    return value


def bind(path: Path, receipt: dict[str, Any], where: str) -> None:
    need(path.is_file(), f"missing input: {where}")
    need(path.stat().st_size == receipt["bytes"], f"input bytes differ: {where}")
    need(digest(path) == receipt["sha256"], f"input SHA differs: {where}")


def control(group: dict[str, Any], arm: str) -> list[str]:
    values = group["candidates"]
    if arm == "min_candidate_sha":
        return sorted(item["candidate_id_sha256"] for item in values)
    if arm == "max_step_then_min_sha":
        return [
            item["candidate_id_sha256"]
            for item in sorted(values, key=lambda x: (-x["step"], x["candidate_id_sha256"]))
        ]
    if arm == "max_code_length_then_min_sha":
        return [
            item["candidate_id_sha256"]
            for item in sorted(values, key=lambda x: (-len(x["code"]), x["candidate_id_sha256"]))
        ]
    raise VerificationError(f"unknown control: {arm}")


def parse_groups(
    path: Path,
    role: str,
    receipt: dict[str, Any],
    clusters: dict[str, dict[str, Any]],
    seen_candidates: set[str],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    bind(path, receipt, role)
    rows = rows_jsonl(path)
    need(len(rows) == receipt["rows"], f"row count differs: {role}")
    expected_fields = TRAIN_FIELDS if role == "train" else TARGET_FIELDS
    groups = {}
    candidates = set()
    for row in rows:
        need(set(row) == expected_fields and row.get("schema_version") == MODEL_SCHEMA, f"schema differs: {role}")
        group_id = valid_hash(row.get("group_id"), f"{role} group")
        need(group_id not in groups and group_id in clusters, f"group closure: {role}")
        cluster = clusters[group_id]
        source_size = valid_int(row.get("source_size"), f"{role} source size")
        values = row.get("candidates")
        need(
            cluster["role"] == role and row.get("task") == cluster["task"]
            and source_size == cluster["source_size"]
            and isinstance(values, list) and len(values) == source_size,
            f"metadata closure: {role}",
        )
        ids = []
        for item in values:
            need(isinstance(item, dict) and set(item) == CANDIDATE_FIELDS, "candidate fields")
            candidate_id = valid_hash(item.get("candidate_id_sha256"), "candidate")
            code = item.get("code")
            need(candidate_id not in seen_candidates and candidate_id not in candidates, "candidate repeats")
            need(isinstance(code, str) and code, "empty code")
            need(hashlib.sha256(code.encode()).hexdigest() == item.get("code_sha256"), "code hash differs")
            need(item.get("operator") in {"Draft", "Improve"}, "operator differs")
            valid_int(item.get("step"), "step")
            valid_int(item.get("depth"), "depth")
            ids.append(candidate_id)
            candidates.add(candidate_id)
        need(ids == sorted(ids) and len(ids) == len(set(ids)), "candidate order differs")
        if role == "train":
            need(row["winner_candidate_sha256"] in set(ids), "train winner closure")
        groups[group_id] = row
    seen_candidates.update(candidates)
    return groups, candidates


def close(left: Any, right: Any, where: str) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        need(set(left) == set(right), f"mapping keys differ: {where}")
        for key in left:
            close(left[key], right[key], f"{where}.{key}")
    elif isinstance(left, list) and isinstance(right, list):
        need(len(left) == len(right), f"list length differs: {where}")
        for index, (a, b) in enumerate(zip(left, right)):
            close(a, b, f"{where}[{index}]")
    elif isinstance(left, float) or isinstance(right, float):
        need(math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-12), f"float differs: {where}")
    else:
        need(left == right, f"value differs: {where}")


def verify(
    protocol_path: Path,
    train_path: Path,
    frozen_path: Path,
    extension_path: Path,
    cluster_path: Path,
    activation_verification_path: Path,
    activation_result_commit_path: Path,
    result: Path,
) -> dict[str, Any]:
    protocol = object_json(protocol_path)
    need(protocol.get("protocol") == PROTOCOL, "protocol differs")
    need(protocol["outputs"]["arms"] == list(ARMS), "arms differ")
    paths = {
        "train_model": train_path, "frozen_model": frozen_path,
        "extension_model": extension_path, "cluster_manifest": cluster_path,
    }
    for key, path in paths.items():
        bind(path, protocol["inputs"][key], key)
    cluster_rows = rows_jsonl(cluster_path)
    clusters = {}
    for row in cluster_rows:
        need(set(row) == CLUSTER_FIELDS and row.get("schema_version") == CLUSTER_SCHEMA, "cluster schema")
        group_id = valid_hash(row.get("group_id"), "cluster group")
        need(group_id not in clusters and row.get("role") in {"train", "frozen", "extension"}, "cluster identity")
        valid_hash(row.get("run_id_sha256"), "cluster run")
        valid_hash(row.get("parent_id_sha256"), "cluster parent")
        need(isinstance(row.get("task"), str) and row["task"], "cluster task")
        need(valid_int(row.get("source_size"), "cluster source size") >= 2, "cluster source size")
        clusters[group_id] = row
    need(len(clusters) == protocol["inputs"]["cluster_manifest"]["rows"], "cluster count")
    seen = set()
    train, train_candidates = parse_groups(train_path, "train", protocol["inputs"]["train_model"], clusters, seen)
    frozen, frozen_candidates = parse_groups(frozen_path, "frozen", protocol["inputs"]["frozen_model"], clusters, seen)
    extension, extension_candidates = parse_groups(
        extension_path, "extension", protocol["inputs"]["extension_model"], clusters, seen
    )
    expected = protocol["expected"]
    census = {
        "train_groups": len(train), "train_candidates": len(train_candidates),
        "frozen_groups": len(frozen), "frozen_candidates": len(frozen_candidates),
        "extension_groups": len(extension), "extension_candidates": len(extension_candidates),
        "tasks": len({row["task"] for row in list(train.values()) + list(frozen.values()) + list(extension.values())}),
    }
    for key, value in census.items():
        need(value == expected[key], f"census differs: {key}")
    train_clusters = [clusters[key] for key in train]
    frozen_clusters = [clusters[key] for key in frozen]
    need(
        len({x["run_id_sha256"] for x in train_clusters} & {x["run_id_sha256"] for x in frozen_clusters})
        == expected["train_frozen_run_overlap"],
        "run overlap differs",
    )
    need(
        len({x["parent_id_sha256"] for x in train_clusters} & {x["parent_id_sha256"] for x in frozen_clusters})
        == expected["train_frozen_parent_overlap"],
        "parent overlap differs",
    )

    activation_verification = object_json(activation_verification_path)
    activation = protocol["activation"]
    need(activation_verification.get("status") == activation["required_independent_verification_status"], "activation status")
    need(activation_verification.get("verdict") in activation["allowed_verdicts"], "activation verdict")
    need(activation_verification.get("producer_imported") is False, "activation imported producer")
    need(activation_verification.get("model_refit_by_verifier") is False, "activation verifier refit")
    need(
        activation_verification.get("frozen_or_extension_model_read") is False
        and activation_verification.get("frozen_or_extension_label_vault_read") is False,
        "activation crossed frozen boundary",
    )
    valid_hash(activation_verification.get("summary_sha256"), "activation summary")
    result_commit = activation_result_commit_path.read_text(encoding="utf-8").strip()
    need(result_commit == activation["required_formal_result_commit"], "activation result commit")
    expected_activation = {
        "verdict": activation_verification["verdict"],
        "formal_result_commit": result_commit,
        "formal_summary_sha256": activation_verification["summary_sha256"],
        "independent_verification_sha256": digest(activation_verification_path),
    }

    manifest = object_json(result / "sha256_manifest.json")
    need(set(manifest) == {"predictions.csv", "model_receipt.json", "summary.json"}, "result manifest names")
    for name, expected_hash in manifest.items():
        need(digest(result / name) == expected_hash, f"result SHA differs: {name}")
    summary = object_json(result / "summary.json")
    need(summary.get("status") == "SOURCE_CHOICE_PREDICTION_ESCROW_COMPLETE", "summary status")
    close(summary["activation"], expected_activation, "activation")
    close(summary["census"], census, "census")
    need(summary["frozen_or_extension_label_vault_read"] is False, "label vault read")
    need(summary["frozen_or_extension_metric_computed"] is False, "metric computed")
    need(summary["search_or_quality_utility_claimed"] is False, "utility claimed")
    need(
        summary["input_sha256"] == {key: value["sha256"] for key, value in protocol["inputs"].items()},
        "input summary",
    )
    need(
        summary["outputs"] == {
            "predictions.csv": digest(result / "predictions.csv"),
            "model_receipt.json": digest(result / "model_receipt.json"),
        },
        "output summary",
    )

    model_receipt = object_json(result / "model_receipt.json")
    close(summary["model_receipt"], model_receipt, "model receipt")
    need(model_receipt["train_groups"] == len(train), "model train groups")
    need(model_receipt["target_groups"] == len(frozen) + len(extension), "model target groups")
    need(model_receipt["train_candidates"] == len(train_candidates), "model train candidates")
    need(
        model_receipt["target_candidates"] == len(frozen_candidates) + len(extension_candidates),
        "model target candidates",
    )
    need(model_receipt["winner_loser_relations"] > 0, "model relations")
    need(
        model_receipt["oriented_fit_rows"] == 2 * model_receipt["winner_loser_relations"],
        "model orientation",
    )
    need(math.isclose(model_receipt["fit_weight_sum"], len(train), rel_tol=0, abs_tol=1e-9), "model weights")
    need(
        0 < model_receipt["vocabulary_size"] <= protocol["model"]["vectorizer"]["max_features"],
        "model vocabulary",
    )
    need(
        0 < model_receipt["lr_iterations"] < protocol["model"]["logistic_regression"]["max_iter"],
        "model iterations",
    )
    valid_hash(model_receipt["coefficient_sha256"], "model coefficient")

    prediction_fields = {
        "role", "arm", "group_id", "task", "run_id_sha256", "source_size",
        "selected_candidate_sha256", "ranking_candidate_sha256_json", "raw_model_scores_json",
    }
    targets = {**frozen, **extension}
    roles = {group_id: "frozen" for group_id in frozen} | {
        group_id: "extension" for group_id in extension
    }
    seen_predictions = set()
    with (result / "predictions.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        need(set(reader.fieldnames or []) == prediction_fields, "prediction fields")
        for raw in reader:
            group_id, arm, role = raw["group_id"], raw["arm"], raw["role"]
            need(group_id in targets and arm in ARMS and role == roles[group_id], "prediction identity")
            key = role, arm, group_id
            need(key not in seen_predictions, "duplicate prediction")
            seen_predictions.add(key)
            group = targets[group_id]
            candidate_ids = {item["candidate_id_sha256"] for item in group["candidates"]}
            try:
                ranking = json.loads(raw["ranking_candidate_sha256_json"])
            except json.JSONDecodeError as exc:
                raise VerificationError("invalid ranking JSON") from exc
            need(
                isinstance(ranking, list) and len(ranking) == group["source_size"]
                and set(ranking) == candidate_ids,
                "ranking closure",
            )
            need(raw["selected_candidate_sha256"] == ranking[0], "selected candidate differs")
            need(
                raw["task"] == group["task"]
                and raw["run_id_sha256"] == clusters[group_id]["run_id_sha256"],
                "prediction metadata",
            )
            need(int(raw["source_size"]) == group["source_size"], "prediction source size")
            if arm == "tfidf_pairwise_lr":
                try:
                    scores = json.loads(raw["raw_model_scores_json"])
                except json.JSONDecodeError as exc:
                    raise VerificationError("invalid score JSON") from exc
                need(isinstance(scores, list) and len(scores) == len(ranking), "score coverage")
                need(
                    all(
                        not isinstance(value, bool) and isinstance(value, (int, float))
                        and math.isfinite(value)
                        for value in scores
                    ),
                    "non-finite score",
                )
                paired = list(zip(scores, ranking))
                need(
                    paired == sorted(paired, key=lambda item: (-item[0], item[1])),
                    "score/ranking order",
                )
            else:
                need(
                    raw["raw_model_scores_json"] == "" and ranking == control(group, arm),
                    "control prediction differs",
                )
    expected_rows = (len(frozen) + len(extension)) * len(ARMS)
    need(len(seen_predictions) == expected_rows == summary["prediction_rows"], "prediction coverage")
    return {
        "protocol": "independent-source-choice-prediction-escrow-verifier-v1",
        "status": "INDEPENDENT_SOURCE_CHOICE_PREDICTION_ESCROW_VERIFIED",
        "producer_imported": False,
        "model_refit_by_verifier": False,
        "labels_or_outcomes_read": False,
        "prediction_rows": expected_rows,
        "groups": len(frozen) + len(extension),
        "summary_sha256": digest(result / "summary.json"),
        "activation_verdict": activation_verification["verdict"],
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--train-model", required=True)
    value.add_argument("--frozen-model", required=True)
    value.add_argument("--extension-model", required=True)
    value.add_argument("--cluster-manifest", required=True)
    value.add_argument("--activation-verification", required=True)
    value.add_argument("--activation-result-commit", required=True)
    value.add_argument("--result", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = verify(
            Path(args.protocol).resolve(), Path(args.train_model).resolve(),
            Path(args.frozen_model).resolve(), Path(args.extension_model).resolve(),
            Path(args.cluster_manifest).resolve(), Path(args.activation_verification).resolve(),
            Path(args.activation_result_commit).resolve(), Path(args.result).resolve(),
        )
        output = Path(args.output).resolve()
        need(not output.exists(), "verification output exists")
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(json.dumps(result, indent=2, sort_keys=True).encode() + b"\n")
        os.replace(temporary, output)
        print(result["status"])
        return 0
    except VerificationError as exc:
        print(f"SOURCE_CHOICE_PREDICTION_ESCROW_VERIFICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
