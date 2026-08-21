#!/usr/bin/env python3
"""Outcome-gated, no-refit sensitivity audit for recovered source candidates."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np


PROTOCOL = "source-choice-provenance-sensitivity-v1"
RAW_SCHEMA = "source-choice-group-v2"
MODEL_SCHEMA = "source-choice-decision-group-v2"
RAW_GROUP_FIELDS = {
    "schema_version", "group_id", "role", "task", "run_id_sha256",
    "parent_id_sha256", "source_size", "candidates", "winner_candidate_sha256",
}
RAW_CANDIDATE_FIELDS = {
    "candidate_id_sha256", "code", "code_sha256", "operator", "step", "depth",
    "provenance", "source_journal_sha256",
}
MODEL_GROUP_FIELDS = {
    "schema_version", "group_id", "task", "source_size", "candidates",
    "winner_candidate_sha256",
}
MODEL_CANDIDATE_FIELDS = {
    "candidate_id_sha256", "code", "code_sha256", "operator", "step", "depth",
}
PREDICTION_FIELDS = {
    "split", "fold", "arm", "group_id", "task", "run_id_sha256", "source_size",
    "selected_candidate_sha256", "hit", "winner_rank",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
OPERATOR_MAP = {"draft": "Draft", "improve": "Improve"}


class SensitivityError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise SensitivityError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def object_json(path: Path, where: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SensitivityError(f"invalid JSON: {where}") from exc
    need(isinstance(value, dict), f"non-object JSON: {where}")
    return value


def canonical_jsonl(path: Path, where: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise SensitivityError(f"missing JSONL: {where}") from exc
    with handle:
        for number, line in enumerate(handle, 1):
            need(line.endswith(b"\n"), f"unterminated JSONL: {where}:{number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SensitivityError(f"invalid JSONL: {where}:{number}") from exc
            need(
                isinstance(value, dict) and canonical(value) + b"\n" == line,
                f"non-canonical JSONL: {where}:{number}",
            )
            rows.append(value)
    need(bool(rows), f"empty JSONL: {where}")
    return rows


def valid_hash(value: Any, where: str) -> str:
    need(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"invalid SHA: {where}")
    return value


def valid_int(value: Any, where: str) -> int:
    need(not isinstance(value, bool) and isinstance(value, int), f"invalid integer: {where}")
    return value


def load_protocol(path: Path) -> dict[str, Any]:
    value = object_json(path, "protocol")
    need(value.get("protocol") == PROTOCOL, "protocol name differs")
    need(
        set(value) == {"protocol", "activation", "inputs", "support", "analysis", "gate", "interpretation", "scope"},
        "protocol fields differ",
    )
    activation = value["activation"]
    need(
        set(activation) == {
            "required_formal_result_commit", "required_independent_verification_status",
            "allowed_verdicts", "blocked_verdict",
        },
        "activation fields differ",
    )
    need(
        isinstance(activation["required_formal_result_commit"], str)
        and HEX40.fullmatch(activation["required_formal_result_commit"]) is not None,
        "invalid Git commit: formal result commit",
    )
    need(
        activation["allowed_verdicts"] == ["GO_CROSS_TASK", "GO_RUN_ONLY"]
        and activation["blocked_verdict"] == "NO_NARROW_POSITIVE",
        "activation verdict contract differs",
    )
    inputs = value["inputs"]
    need(
        set(inputs) == {
            "raw_train_groups_sha256", "decision_view_train_sha256",
            "expected_oof_protocol", "expected_oof_split", "expected_oof_arm",
        },
        "input fields differ",
    )
    valid_hash(inputs["raw_train_groups_sha256"], "raw train receipt")
    valid_hash(inputs["decision_view_train_sha256"], "decision train receipt")
    need(inputs["expected_oof_split"] == "task_loto", "OOF split differs")
    need(inputs["expected_oof_arm"] == "tfidf_pairwise_lr", "OOF arm differs")
    analysis = value["analysis"]
    need(
        analysis.get("model_refit") is False
        and analysis.get("predictions_reused_without_change") is True
        and analysis.get("primary_bootstrap_unit") == "task"
        and analysis.get("task_sign_test") == "one_sided_exact_positive_ignoring_exact_zero"
        and isinstance(analysis.get("bootstrap_replicates"), int)
        and analysis["bootstrap_replicates"] > 0
        and isinstance(analysis.get("bootstrap_seed"), int),
        "analysis contract differs",
    )
    support = value["support"]
    need(
        set(support) == {
            "train_groups", "card_candidates", "journal_recovered_candidates",
            "all_card_groups", "all_card_tasks", "all_card_source_size_counts",
            "mixed_groups", "mixed_tasks", "mixed_source_size_counts",
            "all_winners_have_card_provenance", "minimum_all_card_groups",
            "minimum_all_card_tasks",
        },
        "support fields differ",
    )
    gate = value["gate"]
    need(
        set(gate) == {
            "minimum_absolute_all_card_task_macro_delta",
            "maximum_one_sided_task_sign_p", "pass", "outcomes",
        }
        and gate["minimum_absolute_all_card_task_macro_delta"] >= 0
        and 0 < gate["maximum_one_sided_task_sign_p"] < 1
        and gate["outcomes"] == [
            "ROBUST_BEYOND_RECOVERY_MIX", "RECOVERY_MIX_SENSITIVE",
            "ABORT_SUPPORT_OR_BINDING",
        ],
        "gate contract differs",
    )
    scope = value["scope"]
    need(
        scope.get("train_only") is True
        and scope.get("frozen_or_extension_model_read") is False
        and scope.get("frozen_or_extension_label_vault_read") is False
        and scope.get("new_model_or_hyperparameter") is False
        and scope.get("gpu") == 0
        and scope.get("api_calls") == 0
        and scope.get("base_llm_updated") is False,
        "scope differs",
    )
    return value


def marker(path: Path, expected: str, where: str) -> None:
    try:
        observed = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SensitivityError(f"missing marker: {where}") from exc
    need(observed == expected, f"marker differs: {where}")


def bind_root_manifest(root: Path, relative_names: list[str]) -> None:
    """Bind only the scientific receipts needed here, not large trace files."""
    manifest = root / "SHA256SUMS"
    need(manifest.is_file(), f"missing root manifest: {root.name}")
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        need(match is not None, f"malformed root manifest: {root.name}")
        name = match.group(2).removeprefix("./")
        need(name not in entries, f"duplicate root manifest name: {name}")
        entries[name] = match.group(1)
    for name in relative_names:
        path = root / name
        need(name in entries and path.is_file() and digest(path) == entries[name], f"root receipt differs: {name}")


def bind_result_manifest(result: Path) -> dict[str, Any]:
    manifest = object_json(result / "sha256_manifest.json", "OOF result manifest")
    need(set(manifest) == {"predictions.csv", "per_task.csv", "fold_receipts.json", "summary.json"}, "OOF result manifest names differ")
    for name, expected in manifest.items():
        need(isinstance(expected, str) and HEX64.fullmatch(expected) is not None, "bad OOF result hash")
        need((result / name).is_file() and digest(result / name) == expected, f"OOF result hash differs: {name}")
    summary = object_json(result / "summary.json", "OOF summary")
    need(
        summary.get("outputs") == {
            "predictions.csv": manifest["predictions.csv"],
            "per_task.csv": manifest["per_task.csv"],
            "fold_receipts.json": manifest["fold_receipts.json"],
        },
        "OOF summary output receipts differ",
    )
    return summary


def bind_activation(
    protocol: dict[str, Any], oof_root: Path, verification_root: Path
) -> tuple[Path, str, dict[str, Any]]:
    marker(oof_root / "COMPLETE", "SOURCE_CHOICE_OOF_TFIDF_FORMAL_COMPLETE", "OOF COMPLETE")
    marker(
        verification_root / "COMPLETE",
        "SOURCE_CHOICE_OOF_TFIDF_INDEPENDENT_VERIFICATION_COMPLETE",
        "verification COMPLETE",
    )
    commit = protocol["activation"]["required_formal_result_commit"]
    marker(oof_root / "control_commit.txt", commit, "OOF control commit")
    marker(verification_root / "result_commit.txt", commit, "verification result commit")
    need((oof_root / "result_reproducibility.diff").read_bytes() == b"", "OOF replicas differ")
    need(
        (verification_root / "verification_reproducibility.diff").read_bytes() == b"",
        "verification replicas differ",
    )
    need((oof_root / "producer_a.stderr").stat().st_size == 0, "OOF producer A stderr nonempty")
    need((oof_root / "producer_b.stderr").stat().st_size == 0, "OOF producer B stderr nonempty")
    need((verification_root / "verifier_a.stderr").stat().st_size == 0, "verifier A stderr nonempty")
    need((verification_root / "verifier_b.stderr").stat().st_size == 0, "verifier B stderr nonempty")
    marker(oof_root / "trace_audit.txt", "forbidden_scientific_model_or_vault_path_hits=0", "OOF trace audit")
    marker(verification_root / "trace_audit.txt", "forbidden_scientific_model_or_vault_path_hits=0", "verification trace audit")
    marker(oof_root / "credential_filename_hits.txt", "0", "OOF credential filename audit")
    marker(oof_root / "credential_content_hits.txt", "0", "OOF credential content audit")
    marker(verification_root / "credential_filename_hits.txt", "0", "verification credential filename audit")
    marker(verification_root / "credential_content_hits.txt", "0", "verification credential content audit")
    bind_root_manifest(
        oof_root,
        [
            "COMPLETE", "control_commit.txt", "result_reproducibility.diff",
            "result_a/predictions.csv", "result_a/summary.json", "result_a/sha256_manifest.json",
            "result_b/summary.json", "trace_audit.txt", "credential_filename_hits.txt",
            "credential_content_hits.txt",
        ],
    )
    bind_root_manifest(
        verification_root,
        [
            "COMPLETE", "result_commit.txt", "verification_a.json", "verification_b.json",
            "verification_reproducibility.diff", "trace_audit.txt",
            "credential_filename_hits.txt", "credential_content_hits.txt",
        ],
    )
    result = oof_root / "result_a"
    summary = bind_result_manifest(result)
    other_summary = object_json(oof_root / "result_b" / "summary.json", "OOF replica B summary")
    need(summary == other_summary, "OOF summary replicas differ")
    verification = object_json(verification_root / "verification_a.json", "independent verification")
    verification_b = object_json(verification_root / "verification_b.json", "independent verification B")
    need(verification == verification_b, "independent verification replicas differ")
    activation = protocol["activation"]
    verdict = verification.get("verdict")
    need(
        verification.get("status") == activation["required_independent_verification_status"]
        and verification.get("producer_imported") is False
        and verification.get("model_refit_by_verifier") is False,
        "independent verification semantics differ",
    )
    need(verdict in activation["allowed_verdicts"], f"sensitivity audit not activated: {verdict}")
    need(
        summary.get("protocol") == protocol["inputs"]["expected_oof_protocol"]
        and summary.get("status") == "SOURCE_CHOICE_OOF_TFIDF_COMPLETE"
        and summary.get("verdict") == verdict
        and verification.get("summary_sha256") == digest(result / "summary.json"),
        "OOF summary/verification binding differs",
    )
    return result / "predictions.csv", str(verdict), verification


def bind_exact_sign_audit(
    protocol: dict[str, Any],
    audit_root: Path,
    predictions_path: Path,
    activation_verdict: str,
    oof_root: Path,
) -> dict[str, Any]:
    marker(
        audit_root / "COMPLETE",
        "SOURCE_CHOICE_OOF_EXACT_SIGN_AUDIT_FORMAL_COMPLETE",
        "exact-sign COMPLETE",
    )
    marker(
        audit_root / "result_commit.txt",
        protocol["activation"]["required_formal_result_commit"],
        "exact-sign result commit",
    )
    audit_commit = (audit_root / "audit_commit.txt").read_text(encoding="utf-8").strip()
    need(HEX40.fullmatch(audit_commit) is not None, "exact-sign audit commit differs")
    need((audit_root / "audit_reproducibility.diff").read_bytes() == b"", "exact-sign replicas differ")
    need((audit_root / "audit_a.stderr").stat().st_size == 0, "exact-sign A stderr nonempty")
    need((audit_root / "audit_b.stderr").stat().st_size == 0, "exact-sign B stderr nonempty")
    marker(audit_root / "trace_audit.txt", "forbidden_scientific_model_or_vault_path_hits=0", "exact-sign trace audit")
    marker(audit_root / "credential_filename_hits.txt", "0", "exact-sign credential filename audit")
    marker(audit_root / "credential_content_hits.txt", "0", "exact-sign credential content audit")
    bind_root_manifest(
        audit_root,
        [
            "COMPLETE", "audit_commit.txt", "result_commit.txt", "audit_a.json", "audit_b.json",
            "audit_reproducibility.diff", "trace_audit.txt",
            "credential_filename_hits.txt", "credential_content_hits.txt",
        ],
    )
    audit = object_json(audit_root / "audit_a.json", "exact-sign audit")
    audit_b = object_json(audit_root / "audit_b.json", "exact-sign audit B")
    need(audit == audit_b, "exact-sign audit replicas differ")
    summary_path = oof_root / "result_a" / "summary.json"
    need(
        audit.get("protocol") == "source-choice-oof-exact-sign-audit-v1"
        and audit.get("status") == "SOURCE_CHOICE_OOF_EXACT_SIGN_AUDIT_COMPLETE"
        and audit.get("reported_verdict") == activation_verdict
        and audit.get("exact_sign_verdict") in protocol["activation"]["allowed_verdicts"]
        and audit.get("summary_sha256") == digest(summary_path)
        and audit.get("predictions_sha256") == digest(predictions_path)
        and audit.get("model_refit") is False
        and audit.get("frozen_or_extension_model_read") is False
        and audit.get("frozen_or_extension_label_vault_read") is False,
        "exact-sign activation binding differs",
    )
    audit["audit_commit"] = audit_commit
    return audit


def load_bound_groups(
    raw_path: Path, model_path: Path, protocol: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    need(digest(raw_path) == protocol["inputs"]["raw_train_groups_sha256"], "raw train SHA differs")
    need(digest(model_path) == protocol["inputs"]["decision_view_train_sha256"], "decision train SHA differs")
    raw_rows = canonical_jsonl(raw_path, "raw train")
    model_rows = canonical_jsonl(model_path, "decision train")
    need(len(raw_rows) == len(model_rows), "raw/model row count differs")
    raw_by_id: dict[str, dict[str, Any]] = {}
    model_by_id: dict[str, dict[str, Any]] = {}
    candidate_ids: set[str] = set()
    provenance_counts: collections.Counter[str] = collections.Counter()
    subset_counts: collections.Counter[str] = collections.Counter()
    subset_tasks: dict[str, set[str]] = collections.defaultdict(set)
    subset_sizes: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    for number, raw in enumerate(raw_rows, 1):
        need(set(raw) == RAW_GROUP_FIELDS and raw.get("schema_version") == RAW_SCHEMA, f"raw group schema: {number}")
        need(raw.get("role") == "train", f"raw role differs: {number}")
        group_id = valid_hash(raw.get("group_id"), "raw group")
        need(group_id not in raw_by_id, "duplicate raw group")
        valid_hash(raw.get("run_id_sha256"), "raw run")
        valid_hash(raw.get("parent_id_sha256"), "raw parent")
        need(isinstance(raw.get("task"), str) and raw["task"], "raw task differs")
        source_size = valid_int(raw.get("source_size"), "raw source size")
        candidates = raw.get("candidates")
        need(isinstance(candidates, list) and source_size >= 2 and len(candidates) == source_size, "raw arity differs")
        current_ids = []
        provenance = []
        for candidate_number, candidate in enumerate(candidates, 1):
            need(isinstance(candidate, dict) and set(candidate) == RAW_CANDIDATE_FIELDS, f"raw candidate schema: {number}:{candidate_number}")
            candidate_id = valid_hash(candidate.get("candidate_id_sha256"), "raw candidate")
            need(candidate_id not in candidate_ids, "candidate identity reused")
            candidate_ids.add(candidate_id)
            current_ids.append(candidate_id)
            code = candidate.get("code")
            need(isinstance(code, str) and code and hashlib.sha256(code.encode()).hexdigest() == candidate.get("code_sha256"), "raw code hash differs")
            item_provenance = candidate.get("provenance")
            need(item_provenance in {"card", "journal_recovered"}, "candidate provenance differs")
            journal = candidate.get("source_journal_sha256")
            need(
                (item_provenance == "card" and journal is None)
                or (item_provenance == "journal_recovered" and isinstance(journal, str) and HEX64.fullmatch(journal) is not None),
                "journal provenance closure differs",
            )
            provenance.append(item_provenance)
            provenance_counts[item_provenance] += 1
        need(current_ids == sorted(current_ids), "raw candidate order differs")
        winner = valid_hash(raw.get("winner_candidate_sha256"), "raw winner")
        need(winner in set(current_ids), "winner outside raw group")
        winner_row = next(item for item in candidates if item["candidate_id_sha256"] == winner)
        need(winner_row["provenance"] == "card", "winner is not card provenance")
        provenance_set = set(provenance)
        subset = "all_card" if provenance_set == {"card"} else "mixed"
        need(subset == "all_card" or provenance_set == {"card", "journal_recovered"}, "unsupported provenance composition")
        subset_counts[subset] += 1
        subset_tasks[subset].add(raw["task"])
        subset_sizes[subset][source_size] += 1
        raw_by_id[group_id] = raw

    for number, model in enumerate(model_rows, 1):
        need(set(model) == MODEL_GROUP_FIELDS and model.get("schema_version") == MODEL_SCHEMA, f"model group schema: {number}")
        group_id = valid_hash(model.get("group_id"), "model group")
        need(group_id not in model_by_id and group_id in raw_by_id, "model group closure differs")
        raw = raw_by_id[group_id]
        need(
            model["task"] == raw["task"]
            and model["source_size"] == raw["source_size"]
            and model["winner_candidate_sha256"] == raw["winner_candidate_sha256"],
            "raw/model group identity differs",
        )
        need(len(model["candidates"]) == len(raw["candidates"]), "raw/model candidate count differs")
        for raw_candidate, model_candidate in zip(raw["candidates"], model["candidates"]):
            need(isinstance(model_candidate, dict) and set(model_candidate) == MODEL_CANDIDATE_FIELDS, "model candidate schema differs")
            expected = {
                key: raw_candidate[key]
                for key in ("candidate_id_sha256", "code", "code_sha256", "step", "depth")
            }
            operator = OPERATOR_MAP.get(str(raw_candidate["operator"]).casefold())
            need(operator is not None, "raw operator outside fixed projection")
            expected["operator"] = operator
            need(model_candidate == expected, "raw/model candidate projection differs")
        model_by_id[group_id] = model
    need(set(raw_by_id) == set(model_by_id), "raw/model group coverage differs")

    support = {
        "train_groups": len(raw_by_id),
        "card_candidates": provenance_counts["card"],
        "journal_recovered_candidates": provenance_counts["journal_recovered"],
        "all_card_groups": subset_counts["all_card"],
        "all_card_tasks": len(subset_tasks["all_card"]),
        "all_card_source_size_counts": {str(key): value for key, value in sorted(subset_sizes["all_card"].items())},
        "mixed_groups": subset_counts["mixed"],
        "mixed_tasks": len(subset_tasks["mixed"]),
        "mixed_source_size_counts": {str(key): value for key, value in sorted(subset_sizes["mixed"].items())},
        "all_winners_have_card_provenance": True,
    }
    expected_support = protocol["support"]
    for key in support:
        need(support[key] == expected_support[key], f"support census differs: {key}")
    return raw_by_id, model_by_id, support


def load_predictions(
    path: Path, raw: dict[str, dict[str, Any]], protocol: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        need(set(reader.fieldnames or []) == PREDICTION_FIELDS, "prediction fields differ")
        for observed in reader:
            if observed["split"] != protocol["inputs"]["expected_oof_split"] or observed["arm"] != protocol["inputs"]["expected_oof_arm"]:
                continue
            group_id = observed["group_id"]
            need(group_id in raw and group_id not in seen, "prediction group closure differs")
            seen.add(group_id)
            group = raw[group_id]
            candidates = {item["candidate_id_sha256"]: item for item in group["candidates"]}
            selected = observed["selected_candidate_sha256"]
            need(selected in candidates, "selected candidate outside group")
            hit = int(observed["hit"])
            rank = int(observed["winner_rank"])
            source_size = int(observed["source_size"])
            need(hit in {0, 1} and hit == int(selected == group["winner_candidate_sha256"]), "prediction hit differs")
            need(1 <= rank <= group["source_size"], "winner rank outside arity")
            need(
                observed["task"] == group["task"]
                and observed["run_id_sha256"] == group["run_id_sha256"]
                and source_size == group["source_size"],
                "prediction metadata differs",
            )
            provenance = [item["provenance"] for item in group["candidates"]]
            subset = "all_card" if set(provenance) == {"card"} else "mixed"
            rows.append({
                "group_id": group_id,
                "task": group["task"],
                "source_size": source_size,
                "hit": hit,
                "winner_rank": rank,
                "selected_candidate_sha256": selected,
                "selected_provenance": candidates[selected]["provenance"],
                "card_candidates": provenance.count("card"),
                "subset": subset,
            })
    need(seen == set(raw), "task-LOTO TF-IDF prediction coverage differs")
    rows.sort(key=lambda item: item["group_id"])
    return rows


def exact_sign(values: list[Fraction]) -> dict[str, Any]:
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    zero = sum(value == 0 for value in values)
    n = positive + negative
    p = 1.0 if n == 0 else sum(math.comb(n, item) for item in range(positive, n + 1)) / (2 ** n)
    return {"positive": positive, "negative": negative, "zero": zero, "one_sided_p": p}


def task_bootstrap(values: dict[str, list[float]], reps: int, seed: int) -> dict[str, Any]:
    points = np.asarray([np.mean(values[key]) for key in sorted(values)], dtype=np.float64)
    need(len(points) > 0, "no task clusters")
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(points), size=(reps, len(points)))
    estimates = np.mean(points[sampled], axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": float(np.mean(points)), "ci95": [float(low), float(high)],
        "clusters": len(points), "replicates": reps, "seed": seed,
    }


def summarize_subset(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    need(bool(rows), "empty analysis subset")
    by_task: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_task[row["task"]].append(row)
    task_delta = {
        task: [item["hit"] - 1.0 / item["source_size"] for item in selected]
        for task, selected in by_task.items()
    }
    task_points = [
        sum(
            (Fraction(item["hit"], 1) - Fraction(1, item["source_size"]) for item in by_task[task]),
            Fraction(0, 1),
        )
        / len(by_task[task])
        for task in sorted(by_task)
    ]
    analysis = protocol["analysis"]
    bootstrap = task_bootstrap(task_delta, analysis["bootstrap_replicates"], analysis["bootstrap_seed"])
    return {
        "groups": len(rows),
        "tasks": len(by_task),
        "micro_accuracy": float(np.mean([row["hit"] for row in rows])),
        "micro_uniform_expected_accuracy": float(np.mean([1.0 / row["source_size"] for row in rows])),
        "micro_delta": float(np.mean([row["hit"] - 1.0 / row["source_size"] for row in rows])),
        "task_macro_accuracy": float(np.mean([np.mean([row["hit"] for row in by_task[key]]) for key in sorted(by_task)])),
        "task_macro_uniform_expected_accuracy": float(np.mean([np.mean([1.0 / row["source_size"] for row in by_task[key]]) for key in sorted(by_task)])),
        "task_macro_delta": bootstrap["point"],
        "task_clustered_delta": bootstrap,
        "task_sign": exact_sign(task_points),
        "winner_mrr": float(np.mean([1.0 / row["winner_rank"] for row in rows])),
    }


def strata(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, Any], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[(row["subset"], row[key])].append(row)
    output = []
    for (subset, value), selected in sorted(grouped.items(), key=lambda item: (item[0][0], str(item[0][1]))):
        output.append({
            "subset": subset,
            key: value,
            "groups": len(selected),
            "accuracy": float(np.mean([row["hit"] for row in selected])),
            "uniform_expected_accuracy": float(np.mean([1.0 / row["source_size"] for row in selected])),
            "delta": float(np.mean([row["hit"] - 1.0 / row["source_size"] for row in selected])),
            "selected_card_rate": float(np.mean([row["selected_provenance"] == "card" for row in selected])),
            "card_only_uniform_expected_accuracy": float(np.mean([1.0 / row["card_candidates"] for row in selected])),
        })
    return output


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    need(not path.exists(), f"refusing to overwrite: {path.name}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n")
    os.replace(temporary, path)


def analyze(
    protocol_path: Path,
    raw_path: Path,
    model_path: Path,
    oof_root: Path,
    verification_root: Path,
    exact_sign_audit_root: Path,
    output: Path,
) -> dict[str, Any]:
    need(not output.exists(), "output directory exists")
    protocol = load_protocol(protocol_path)
    predictions_path, activation_verdict, verification = bind_activation(protocol, oof_root, verification_root)
    exact_sign_audit = bind_exact_sign_audit(
        protocol, exact_sign_audit_root, predictions_path, activation_verdict, oof_root
    )
    raw, _, support = load_bound_groups(raw_path, model_path, protocol)
    rows = load_predictions(predictions_path, raw, protocol)
    all_card = [row for row in rows if row["subset"] == "all_card"]
    mixed = [row for row in rows if row["subset"] == "mixed"]
    need(len(all_card) == support["all_card_groups"] and len(mixed) == support["mixed_groups"], "subset coverage differs")
    primary = summarize_subset(all_card, protocol)
    secondary_mixed = summarize_subset(mixed, protocol)
    secondary_mixed["card_only_uniform_micro_expected_accuracy"] = float(
        np.mean([1.0 / row["card_candidates"] for row in mixed])
    )
    secondary_mixed["selected_card_rate"] = float(
        np.mean([row["selected_provenance"] == "card" for row in mixed])
    )
    selected_provenance = collections.Counter(row["selected_provenance"] for row in rows)
    selected_provenance_mixed = collections.Counter(row["selected_provenance"] for row in mixed)
    expected_support = protocol["support"]
    support_pass = (
        support["all_card_groups"] >= expected_support["minimum_all_card_groups"]
        and support["all_card_tasks"] >= expected_support["minimum_all_card_tasks"]
        and support["all_winners_have_card_provenance"] is True
    )
    gate = protocol["gate"]
    gate_checks = {
        "support_pass": support_pass,
        "delta_at_least_minimum": primary["task_macro_delta"] >= gate["minimum_absolute_all_card_task_macro_delta"],
        "task_ci_low_above_zero": primary["task_clustered_delta"]["ci95"][0] > 0,
        "task_sign_p_below_maximum": primary["task_sign"]["one_sided_p"] < gate["maximum_one_sided_task_sign_p"],
    }
    if not support_pass:
        verdict = "ABORT_SUPPORT_OR_BINDING"
    elif all(gate_checks.values()):
        verdict = "ROBUST_BEYOND_RECOVERY_MIX"
    else:
        verdict = "RECOVERY_MIX_SENSITIVE"
    need(verdict in gate["outcomes"], "verdict outside protocol")

    per_task = strata(rows, "task")
    per_size = strata(rows, "source_size")
    output.mkdir(parents=True)
    per_task_path = output / "per_task.csv"
    per_size_path = output / "per_source_size.csv"
    fields_task = [
        "subset", "task", "groups", "accuracy", "uniform_expected_accuracy", "delta",
        "selected_card_rate", "card_only_uniform_expected_accuracy",
    ]
    fields_size = [
        "subset", "source_size", "groups", "accuracy", "uniform_expected_accuracy", "delta",
        "selected_card_rate", "card_only_uniform_expected_accuracy",
    ]
    write_csv(per_task_path, per_task, fields_task)
    write_csv(per_size_path, per_size, fields_size)
    summary = {
        "protocol": PROTOCOL,
        "status": "SOURCE_CHOICE_PROVENANCE_SENSITIVITY_COMPLETE",
        "verdict": verdict,
        "activation_oof_verdict": activation_verdict,
        "activation_independent_verification_status": verification["status"],
        "activation_exact_sign_verdict": exact_sign_audit["exact_sign_verdict"],
        "activation_exact_sign_audit_commit": exact_sign_audit["audit_commit"],
        "formal_result_commit": protocol["activation"]["required_formal_result_commit"],
        "input_sha256": {
            "raw_train_groups": digest(raw_path),
            "decision_view_train": digest(model_path),
            "oof_predictions": digest(predictions_path),
            "independent_verification": digest(verification_root / "verification_a.json"),
            "exact_sign_audit": digest(exact_sign_audit_root / "audit_a.json"),
        },
        "support": support,
        "primary_all_card": primary,
        "secondary_mixed": secondary_mixed,
        "model_selected_provenance": {
            "all_groups_counts": dict(sorted(selected_provenance.items())),
            "all_groups_card_rate": float(np.mean([row["selected_provenance"] == "card" for row in rows])),
            "mixed_groups_counts": dict(sorted(selected_provenance_mixed.items())),
            "mixed_groups_card_rate": secondary_mixed["selected_card_rate"],
        },
        "gate": gate,
        "gate_checks": gate_checks,
        "scope": protocol["scope"],
        "model_refit": False,
        "prediction_rankings_changed": False,
        "frozen_or_extension_model_read": False,
        "frozen_or_extension_label_vault_read": False,
        "claim_boundary": protocol["interpretation"],
        "outputs": {
            "per_task.csv": digest(per_task_path),
            "per_source_size.csv": digest(per_size_path),
        },
    }
    summary_path = output / "summary.json"
    write_json(summary_path, summary)
    manifest = {
        path.name: digest(path) for path in (per_task_path, per_size_path, summary_path)
    }
    write_json(output / "sha256_manifest.json", manifest)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--raw-train", required=True)
    value.add_argument("--decision-train", required=True)
    value.add_argument("--oof-root", required=True)
    value.add_argument("--independent-verification-root", required=True)
    value.add_argument("--exact-sign-audit-root", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = analyze(
            Path(args.protocol).resolve(), Path(args.raw_train).resolve(),
            Path(args.decision_train).resolve(), Path(args.oof_root).resolve(),
            Path(args.independent_verification_root).resolve(),
            Path(args.exact_sign_audit_root).resolve(), Path(args.output).resolve(),
        )
        print(f"{result['status']} verdict={result['verdict']}")
        return 0
    except (SensitivityError, OSError, ValueError) as exc:
        print(f"SOURCE_CHOICE_PROVENANCE_SENSITIVITY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
