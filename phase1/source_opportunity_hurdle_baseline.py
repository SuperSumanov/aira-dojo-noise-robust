#!/usr/bin/env python3
"""Train-role to frozen-role scoreability→quality baseline for source opportunities.

The producer scans only allowlisted extracted journals.  Every journal is credential
scanned before JSON decoding.  Raw code is used in memory and is never written.
"""

from __future__ import annotations

import argparse
import ast
import collections
import csv
import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import sklearn
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler


PROTOCOL = "source-opportunity-hurdle-baseline-v1"
SEED = 20260815
BOOTSTRAP_REPETITIONS = 5000
HEX40 = re.compile(r"[0-9a-f]{40}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|"
    rb"-----?BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----?)"
)
IMPORT_RX = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.M)
MODEL_WORDS = (
    "lightgbm", "xgboost", "catboost", "randomforest", "logisticregression",
    "ridge", "svc", "torch", "transformers", "bert", "resnet",
    "efficientnet", "timm", "keras", "sklearn",
)
CV_WORDS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_WORDS = (
    "fit_transform(test", "fit(test", ".append(test", "concat([train, test",
    "pd.concat([train,test",
)
ROLES = ("train", "frozen", "extension")
ARMS = (
    "quality_static", "quality_tfidf", "scoreability_static",
    "scoreability_tfidf", "hurdle_static", "hurdle_tfidf",
)


class BaselineError(RuntimeError):
    pass


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise BaselineError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def required_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise BaselineError(f"invalid text: {where}")
    return value


def parse_roots(values: Sequence[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise BaselineError("root must be ALIAS=PATH")
        alias, raw = value.split("=", 1)
        if not re.fullmatch(r"[a-z0-9_]+", alias) or alias in roots:
            raise BaselineError("invalid or duplicate root alias")
        path = Path(raw).resolve()
        if not path.is_dir():
            raise BaselineError(f"missing root: {alias}")
        roots[alias] = path
    if not roots:
        raise BaselineError("no journal roots")
    return roots


def canonical_journals(root: Path) -> list[Path]:
    by_run: dict[Path, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.name.lower() != "journal.jsonl":
            continue
        run_dir = path.parent.parent
        current = by_run.get(run_dir)
        if current is None or (
            "checkpoint" in path.parts and "checkpoint" not in current.parts
        ):
            by_run[run_dir] = path
    return [by_run[key] for key in sorted(by_run, key=lambda item: item.as_posix())]


def load_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BaselineError(f"invalid cards JSON line {line_number}") from exc
            if not isinstance(row, dict):
                raise BaselineError(f"invalid card row {line_number}")
            card_id = required_text(row.get("id"), f"card id line {line_number}")
            if card_id in cards:
                raise BaselineError(f"duplicate card id: {card_id}")
            cards[card_id] = row
    if not cards:
        raise BaselineError("empty cards")
    return cards


def load_identity(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    totals = collections.Counter()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BaselineError(f"invalid identity JSON line {line_number}") from exc
            if not isinstance(row, dict):
                raise BaselineError(f"invalid identity row {line_number}")
            if not row.get("source_incomplete"):
                continue
            role = required_text(row.get("role"), f"identity role line {line_number}")
            if role not in ROLES:
                raise BaselineError(f"invalid identity role line {line_number}")
            totals[role] += 1
            if row.get("exact_identity_recoverable") is True:
                rows.append(row)
    return rows, dict(totals)


def load_missing_status(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BaselineError(f"invalid status JSON line {line_number}") from exc
            if not isinstance(row, dict):
                raise BaselineError(f"invalid status row {line_number}")
            child = required_text(row.get("child_id"), f"status child line {line_number}")
            if child in rows:
                raise BaselineError(f"duplicate status child: {child}")
            rows[child] = row
    return rows


def build_parent_targets(
    cards: dict[str, dict[str, Any]], identity_rows: Sequence[dict[str, Any]]
) -> tuple[list[dict[str, Any]], set[str]]:
    parents: list[dict[str, Any]] = []
    targets: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for row in identity_rows:
        role = required_text(row.get("role"), "identity role")
        parent = required_text(row.get("parent"), "identity parent")
        key = (role, parent)
        if key in seen:
            raise BaselineError(f"duplicate identity parent: {key}")
        seen.add(key)
        if parent not in cards:
            raise BaselineError(f"recoverable parent absent from cards: {parent}")
        lineage = cards[parent].get("lineage")
        if not isinstance(lineage, dict):
            raise BaselineError(f"parent lineage missing: {parent}")
        children = lineage.get("children_ids")
        if not isinstance(children, list) or not children:
            raise BaselineError(f"parent children missing: {parent}")
        if len(children) != len(set(children)) or not all(
            isinstance(child, str) and child for child in children
        ):
            raise BaselineError(f"invalid parent children: {parent}")
        expected_size = int(row.get("source_declared_size"))
        if len(children) != expected_size:
            raise BaselineError(f"source size mismatch: {parent}")
        retained = sorted(child for child in children if child in cards)
        missing = sorted(set(children) - set(retained))
        if missing != sorted(row.get("missing_child_ids") or []):
            raise BaselineError(f"missing identity mismatch: {parent}")
        task = required_text((cards[parent].get("task") or {}).get("name"), "parent task")
        run_id = required_text(cards[parent].get("run_id"), "parent run")
        parents.append(
            {
                "role": role,
                "parent": parent,
                "task": task,
                "run_id": run_id,
                "children": tuple(children),
                "retained": frozenset(retained),
                "missing": frozenset(missing),
            }
        )
        targets.update(children)
    return parents, targets


def decode_journal(blob: bytes, where: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BaselineError(f"journal not UTF-8: {where}") from exc
    nodes: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            node = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BaselineError(f"invalid journal JSON {where}:{line_number}") from exc
        if not isinstance(node, dict):
            raise BaselineError(f"journal row not object {where}:{line_number}")
        nodes.append(node)
    task = next(
        (
            str((node.get("metric_info") or {})["competition_id"])
            for node in nodes
            if isinstance(node.get("metric_info"), dict)
            and (node.get("metric_info") or {}).get("competition_id")
        ),
        None,
    )
    if not nodes or not task:
        raise BaselineError(f"journal has no nodes/task: {where}")
    return task, nodes


def classify_node(node: dict[str, Any]) -> tuple[str, bool, bool]:
    exit_code = node.get("exit_code")
    metric = node.get("metric_info")
    metric = metric if isinstance(metric, dict) else {}
    grade_present = metric.get("score") is not None
    threshold_present = any(
        metric.get(f"{name}_threshold") is not None
        for name in ("gold", "silver", "bronze")
    )
    exec_ok = exit_code == 0
    scoreable = bool(exec_ok and grade_present and threshold_present)
    if isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0:
        category = "EXECUTION_ERROR"
    elif exit_code == 0 and not grade_present:
        category = "OFFICIAL_GRADE_ABSENT"
    elif exit_code == 0 and grade_present and not threshold_present:
        category = "NORMALIZATION_METADATA_ABSENT"
    elif scoreable:
        category = "SCOREABLE"
    else:
        category = "EXECUTION_STATUS_UNKNOWN"
    return category, exec_ok, scoreable


def node_card_id(task: str, node: dict[str, Any]) -> str:
    raw = node.get("id", node.get("step"))
    return f"{task}__{raw}"


def scan_journals(
    roots: dict[str, Path], targets: set[str]
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    hits: dict[str, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    root_stats: dict[str, Any] = {}
    credential_hashes: list[str] = []
    for alias, root in sorted(roots.items()):
        journals = canonical_journals(root)
        parsed = matched = malformed = credentials = 0
        for journal in journals:
            blob = journal.read_bytes()
            relative = journal.relative_to(root).as_posix()
            path_hash = sha256_bytes(f"{alias}:{relative}".encode())
            if CREDENTIAL.search(blob):
                credentials += 1
                credential_hashes.append(path_hash)
                continue
            try:
                task, nodes = decode_journal(blob, path_hash)
            except BaselineError:
                malformed += 1
                continue
            parsed += 1
            by_step = {node.get("step"): node for node in nodes}
            journal_sha = sha256_bytes(blob)
            journal_matched = False
            for node in nodes:
                child = node_card_id(task, node)
                if child not in targets:
                    continue
                parents = node.get("parents") or []
                parent_id = None
                if isinstance(parents, list) and len(parents) == 1 and parents[0] in by_step:
                    parent_id = node_card_id(task, by_step[parents[0]])
                code = node.get("code")
                code = code if isinstance(code, str) else ""
                operators = node.get("operators_used") or []
                operator = operators[0] if isinstance(operators, list) and operators else "Draft"
                category, exec_ok, scoreable = classify_node(node)
                record = {
                    "parent_id": parent_id,
                    "code": code,
                    "code_sha256": sha256_bytes(code.encode("utf-8")),
                    "operator": str(operator).capitalize(),
                    "step": int(node.get("step") or 0),
                    "depth": int(node.get("depth") or len(parents)),
                    "category": category,
                    "exec_ok": exec_ok,
                    "scoreable": scoreable,
                    "source_journal_sha256": journal_sha,
                }
                previous = hits[child].get(journal_sha)
                if previous is not None and previous != record:
                    raise BaselineError(f"same journal SHA conflicts for child: {child}")
                hits[child][journal_sha] = record
                journal_matched = True
            if journal_matched:
                matched += 1
        root_stats[alias] = {
            "canonical_journals": len(journals),
            "parsed_journals": parsed,
            "target_matching_journals": matched,
            "credential_shape_journals_skipped": credentials,
            "malformed_journals_skipped": malformed,
        }
    return hits, {
        "roots": root_stats,
        "credential_path_sha256": sorted(credential_hashes),
    }


def static_features(code: str, task: str, operator: str, step: int, depth: int) -> dict[str, Any]:
    low = code.lower()
    imports = set(IMPORT_RX.findall(code))
    features: dict[str, Any] = {
        "task": task,
        "operator": operator,
        "code_len": float(len(code)),
        "n_lines": float(code.count("\n")),
        "n_imports": float(len(imports)),
        "step": float(step),
        "depth": float(depth),
        "n_cv": float(sum(low.count(word) for word in CV_WORDS)),
        "n_seed": float(low.count("seed") + low.count("random_state")),
        "n_ensemble": float(
            low.count("ensemble") + low.count("blend") + low.count("stack") + low.count("mean(")
        ),
        "n_earlystop": float(low.count("early_stop")),
        "n_hpsearch": float(
            low.count("optuna") + low.count("gridsearch") + low.count("param_grid")
            + low.count("hyperopt")
        ),
        "n_augment": float(low.count("augment") + low.count("transform")),
        "n_try": float(low.count("try:")),
        "n_print": float(low.count("print(")),
        "n_comment": float(code.count("#")),
        "n_fold_int": float(max(
            [int(value) for value in re.findall(r"n_splits\s*=\s*(\d+)", code)] or [0]
        )),
        "n_epoch_int": float(max(
            [int(value) for value in re.findall(r"epochs?\s*=\s*(\d+)", code)] or [0]
        )),
        "risk_leak": float(sum(low.count(word) for word in RISK_WORDS)),
        "has_gpu": float("cuda" in low),
        "ast_parse_ok": float(_ast_parse_ok(code)),
    }
    for word in MODEL_WORDS:
        features[f"m_{word}"] = float(word in low)
    return features


def _ast_parse_ok(code: str) -> bool:
    try:
        ast.parse(code)
    except (SyntaxError, ValueError, TypeError, MemoryError):
        return False
    return True


def resolve_candidates(
    cards: dict[str, dict[str, Any]],
    parents: Sequence[dict[str, Any]],
    missing_status: dict[str, dict[str, Any]],
    hits: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    candidates: list[dict[str, Any]] = []
    parent_rows: list[dict[str, Any]] = []
    integrity = collections.Counter()
    for parent in parents:
        local: list[dict[str, Any]] = []
        reasons: set[str] = set()
        for child in parent["children"]:
            sources = hits.get(child, {})
            if not sources:
                reasons.add("SOURCE_JOURNAL_NOT_FOUND")
                continue
            if len(sources) != 1:
                integrity["source_journal_collisions"] += 1
                reasons.add("SOURCE_JOURNAL_COLLISION")
                continue
            record = next(iter(sources.values()))
            if record["parent_id"] != parent["parent"]:
                integrity["journal_parent_mismatches"] += 1
                reasons.add("JOURNAL_PARENT_MISMATCH")
                continue
            if not record["code"]:
                reasons.add("CODE_ABSENT")
                continue
            retained = child in parent["retained"]
            if retained:
                card_code = cards[child].get("code")
                card_code = card_code if isinstance(card_code, str) else ""
                if sha256_bytes(card_code.encode("utf-8")) != record["code_sha256"]:
                    integrity["retained_code_sha_mismatches"] += 1
                    reasons.add("RETAINED_CODE_SHA_MISMATCH")
                    continue
                if not record["scoreable"] or record["category"] != "SCOREABLE":
                    integrity["retained_status_mismatches"] += 1
                    reasons.add("RETAINED_STATUS_MISMATCH")
                    continue
                y_norm = finite((cards[child].get("label") or {}).get("y_norm"))
                if y_norm is None or not 0.0 <= y_norm <= 1.0:
                    reasons.add("RETAINED_QUALITY_INVALID")
                    continue
                utility = y_norm
            else:
                status = missing_status.get(child)
                if status is None or status.get("status") != "UNIQUE_NODE_RECOVERED":
                    reasons.add("MISSING_STATUS_UNRESOLVED")
                    continue
                if status.get("expected_parent_id") != parent["parent"] or not status.get("parent_match"):
                    integrity["status_parent_mismatches"] += 1
                    reasons.add("STATUS_PARENT_MISMATCH")
                    continue
                if status.get("source_journal_sha256") != record["source_journal_sha256"]:
                    integrity["status_journal_sha_mismatches"] += 1
                    reasons.add("STATUS_JOURNAL_SHA_MISMATCH")
                    continue
                if status.get("category") != record["category"]:
                    integrity["status_category_mismatches"] += 1
                    reasons.add("STATUS_CATEGORY_MISMATCH")
                    continue
                y_norm = None
                utility = 0.0
            local.append(
                {
                    "role": parent["role"],
                    "parent": parent["parent"],
                    "task": parent["task"],
                    "run_id": parent["run_id"],
                    "child_id": child,
                    "retained": retained,
                    "category": record["category"],
                    "exec_ok": bool(record["exec_ok"]),
                    "scoreable": bool(record["scoreable"]),
                    "utility": utility,
                    "y_norm": y_norm,
                    "code": record["code"],
                    "code_sha256": record["code_sha256"],
                    "source_journal_sha256": record["source_journal_sha256"],
                    "static": static_features(
                        record["code"], parent["task"], record["operator"],
                        record["step"], record["depth"],
                    ),
                }
            )
        eligible = not reasons and len(local) == len(parent["children"])
        parent_rows.append(
            {
                "role": parent["role"],
                "parent": parent["parent"],
                "task": parent["task"],
                "run_id": parent["run_id"],
                "source_size": len(parent["children"]),
                "eligible": eligible,
                "exclusion_reasons": sorted(reasons),
            }
        )
        if eligible:
            candidates.extend(local)
    return candidates, parent_rows, dict(integrity)


def parent_weights(rows: Sequence[dict[str, Any]]) -> np.ndarray:
    counts = collections.Counter(row["parent"] for row in rows)
    return np.array([1.0 / counts[row["parent"]] for row in rows], dtype=np.float64)


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in ("role", "parent", "task", "run_id", "child_id", "code", "static")
    }


def fit_and_score(
    train_rows: Sequence[dict[str, Any]], score_rows: Sequence[dict[str, Any]]
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    if not train_rows or not score_rows:
        raise BaselineError("empty fit or score rows")
    if any(row["role"] != "train" for row in train_rows):
        raise BaselineError("non-train row reached fit")
    y_scoreable = np.array([int(row["scoreable"]) for row in train_rows], dtype=np.int64)
    if set(y_scoreable.tolist()) != {0, 1}:
        raise BaselineError("train scoreability labels lack both classes")
    train_positive = [row for row in train_rows if row["scoreable"]]
    y_quality = np.array([float(row["y_norm"]) for row in train_positive], dtype=np.float64)
    if not len(y_quality) or not np.isfinite(y_quality).all():
        raise BaselineError("invalid train quality labels")
    vectorizer = DictVectorizer(sparse=True, sort=True)
    x_static_train = vectorizer.fit_transform([row["static"] for row in train_rows])
    x_static_score = vectorizer.transform([row["static"] for row in score_rows])
    scaler = StandardScaler(with_mean=False)
    x_static_train = scaler.fit_transform(x_static_train)
    x_static_score = scaler.transform(x_static_score)
    positive_indices = [index for index, row in enumerate(train_rows) if row["scoreable"]]
    w_feas = parent_weights(train_rows)
    w_quality = parent_weights(train_positive)

    static_feas = LogisticRegression(
        C=1.0, max_iter=4000, solver="liblinear", random_state=SEED
    ).fit(x_static_train, y_scoreable, sample_weight=w_feas)
    static_quality = Ridge(alpha=10.0, solver="lsqr").fit(
        x_static_train[positive_indices], y_quality, sample_weight=w_quality
    )

    tfidf = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=30000,
        min_df=3, sublinear_tf=True,
    )
    x_tfidf_train = tfidf.fit_transform([row["code"][:20000] for row in train_rows])
    x_tfidf_score = tfidf.transform([row["code"][:20000] for row in score_rows])
    tfidf_feas = LogisticRegression(
        C=1.0, max_iter=4000, solver="liblinear", random_state=SEED
    ).fit(x_tfidf_train, y_scoreable, sample_weight=w_feas)
    tfidf_quality = Ridge(alpha=10.0, solver="lsqr").fit(
        x_tfidf_train[positive_indices], y_quality, sample_weight=w_quality
    )

    static_p = static_feas.predict_proba(x_static_score)[:, 1]
    tfidf_p = tfidf_feas.predict_proba(x_tfidf_score)[:, 1]
    static_q = static_quality.predict(x_static_score)
    tfidf_q = tfidf_quality.predict(x_tfidf_score)
    scores: dict[str, dict[str, float]] = {}
    for index, row in enumerate(score_rows):
        scores[row["child_id"]] = {
            "quality_static": float(static_q[index]),
            "quality_tfidf": float(tfidf_q[index]),
            "scoreability_static": float(static_p[index]),
            "scoreability_tfidf": float(tfidf_p[index]),
            "hurdle_static": float(static_p[index] * np.clip(static_q[index], 0.0, 1.0)),
            "hurdle_tfidf": float(tfidf_p[index] * np.clip(tfidf_q[index], 0.0, 1.0)),
        }
    diagnostics = {
        "fit_roles": sorted({row["role"] for row in train_rows}),
        "train_candidates": len(train_rows),
        "train_positive_candidates": len(train_positive),
        "score_candidates": len(score_rows),
        "static_features": len(vectorizer.feature_names_),
        "tfidf_features": len(tfidf.get_feature_names_out()),
        "tfidf_vocabulary_sha256": sha256_bytes(
            "\n".join(tfidf.get_feature_names_out()).encode("utf-8")
        ),
        "parameters": {
            "seed": SEED,
            "static_vectorizer": "DictVectorizer(sort=true)+StandardScaler(with_mean=false)",
            "quality": {"model": "Ridge", "alpha": 10.0, "solver": "lsqr"},
            "scoreability": {
                "model": "LogisticRegression", "C": 1.0,
                "max_iter": 4000, "solver": "liblinear",
            },
            "tfidf": {
                "analyzer": "char_wb", "ngram_range": [3, 5],
                "max_features": 30000, "min_df": 3, "sublinear_tf": True,
                "max_chars": 20000,
            },
        },
    }
    return scores, diagnostics


def tie_mean(values: Sequence[tuple[float, float]]) -> float:
    if not values:
        raise BaselineError("empty tie set")
    maximum = max(score for score, _ in values)
    selected = [value for score, value in values if abs(score - maximum) <= 1e-12]
    return float(np.mean(selected))


def parent_metrics(
    rows: Sequence[dict[str, Any]], scores: dict[str, dict[str, float]], role: str
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        if row["role"] == role:
            grouped[row["parent"]].append(row)
    output: list[dict[str, Any]] = []
    for parent, selected in sorted(grouped.items()):
        base = {
            "role": role,
            "parent": parent,
            "task": selected[0]["task"],
            "run_id": selected[0]["run_id"],
            "source_size": len(selected),
            "random_expected_scoreability": float(np.mean([row["scoreable"] for row in selected])),
            "random_expected_utility": float(np.mean([row["utility"] for row in selected])),
            "oracle_scoreability": float(max(row["scoreable"] for row in selected)),
            "oracle_utility": float(max(row["utility"] for row in selected)),
        }
        for arm in ARMS:
            base[f"{arm}_scoreability"] = tie_mean(
                [(scores[row["child_id"]][arm], float(row["scoreable"])) for row in selected]
            )
            base[f"{arm}_utility"] = tie_mean(
                [(scores[row["child_id"]][arm], float(row["utility"])) for row in selected]
            )
        output.append(base)
    return output


def cluster_ci(
    rows: Sequence[dict[str, Any]], field: str, cluster: str,
    repetitions: int = BOOTSTRAP_REPETITIONS, seed: int = SEED,
) -> list[float]:
    groups: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row[cluster])].append(float(row[field]))
    keys = sorted(groups)
    if not keys:
        raise BaselineError("empty bootstrap groups")
    rng = random.Random(seed)
    samples = []
    for _ in range(repetitions):
        values = [value for key in (rng.choice(keys) for _ in keys) for value in groups[key]]
        samples.append(float(np.mean(values)))
    samples.sort()
    low = samples[int(0.025 * repetitions)]
    high = samples[min(repetitions - 1, int(0.975 * repetitions))]
    return [low, high]


def comparison(
    rows: Sequence[dict[str, Any]], left: str, right: str, metric: str
) -> dict[str, Any]:
    field = f"delta__{left}__{right}__{metric}"
    copied = []
    for row in rows:
        value = float(row[f"{left}_{metric}"] - row[f"{right}_{metric}"])
        row[field] = value
        copied.append(row)
    by_task: dict[str, list[float]] = collections.defaultdict(list)
    for row in copied:
        by_task[row["task"]].append(row[field])
    supported = {task: values for task, values in by_task.items() if len(values) >= 5}
    return {
        "left": left,
        "right": right,
        "metric": metric,
        "overall": float(np.mean([row[field] for row in copied])),
        "task_cluster_ci95": cluster_ci(copied, field, "task"),
        "run_cluster_ci95": cluster_ci(copied, field, "run_id"),
        "parent_ci95": cluster_ci(copied, field, "parent"),
        "task_macro": float(np.mean([np.mean(values) for values in by_task.values()])),
        "supported_tasks": len(supported),
        "supported_task_nonnegative_share": (
            float(sum(np.mean(values) >= 0.0 for values in supported.values()) / len(supported))
            if supported else None
        ),
        "per_task": {
            task: {"parents": len(values), "mean": float(np.mean(values))}
            for task, values in sorted(by_task.items())
        },
    }


def summarize_construction(
    parent_rows: Sequence[dict[str, Any]], totals: dict[str, int], integrity: dict[str, int]
) -> dict[str, Any]:
    roles: dict[str, Any] = {}
    for role in ROLES:
        selected = [row for row in parent_rows if row["role"] == role]
        eligible = [row for row in selected if row["eligible"]]
        reasons = collections.Counter(
            reason for row in selected for reason in row["exclusion_reasons"]
        )
        roles[role] = {
            "source_incomplete_parents": totals.get(role, 0),
            "exact_identity_recoverable_parents": len(selected),
            "eligible_parents": len(eligible),
            "eligible_coverage_of_exact_incomplete": len(eligible) / len(selected) if selected else None,
            "tasks": len({row["task"] for row in eligible}),
            "runs": len({row["run_id"] for row in eligible}),
            "exclusion_reasons": dict(sorted(reasons.items())),
        }
    integrity_keys = (
        "source_journal_collisions", "journal_parent_mismatches",
        "retained_code_sha_mismatches", "retained_status_mismatches",
        "status_parent_mismatches", "status_journal_sha_mismatches",
        "status_category_mismatches",
    )
    criteria = {
        "all_integrity_mismatches_eq_0": all(integrity.get(key, 0) == 0 for key in integrity_keys),
        "train_eligible_parents_ge_350": roles["train"]["eligible_parents"] >= 350,
        "train_tasks_ge_12": roles["train"]["tasks"] >= 12,
        "frozen_eligible_parents_ge_100": roles["frozen"]["eligible_parents"] >= 100,
        "frozen_tasks_ge_8": roles["frozen"]["tasks"] >= 8,
        "train_coverage_ge_0_60": (roles["train"]["eligible_coverage_of_exact_incomplete"] or 0) >= 0.60,
        "frozen_coverage_ge_0_60": (roles["frozen"]["eligible_coverage_of_exact_incomplete"] or 0) >= 0.60,
    }
    return {
        "roles": roles,
        "integrity": {key: integrity.get(key, 0) for key in integrity_keys},
        "criteria": criteria,
        "construction_gate_pass": all(criteria.values()),
    }


def summarize_results(
    parent_rows: Sequence[dict[str, Any]], comparisons: dict[str, Any]
) -> dict[str, Any]:
    frozen = list(parent_rows)
    arms = {}
    for arm in ARMS:
        arms[arm] = {
            "scoreability": float(np.mean([row[f"{arm}_scoreability"] for row in frozen])),
            "utility": float(np.mean([row[f"{arm}_utility"] for row in frozen])),
        }
    baselines = {
        name: {
            "scoreability": float(np.mean([row[f"{name}_scoreability"] for row in frozen])),
            "utility": float(np.mean([row[f"{name}_utility"] for row in frozen])),
        }
        for name in ("random_expected", "oracle")
    }
    headline_s = comparisons["hurdle_tfidf_vs_quality_tfidf_scoreability"]
    headline_u = comparisons["hurdle_tfidf_vs_quality_tfidf_utility"]
    feasibility = comparisons["scoreability_tfidf_vs_random_expected_scoreability"]
    method_gate = {
        "scoreability_delta_ge_0_02": headline_s["overall"] >= 0.02,
        "utility_delta_ge_0_02": headline_u["overall"] >= 0.02,
        "scoreability_task_ci_low_gt_0": headline_s["task_cluster_ci95"][0] > 0.0,
        "utility_task_ci_low_gt_0": headline_u["task_cluster_ci95"][0] > 0.0,
        "supported_task_utility_nonnegative_share_ge_0_60": (
            headline_u["supported_task_nonnegative_share"] is not None
            and headline_u["supported_task_nonnegative_share"] >= 0.60
        ),
    }
    feasibility_gate = {
        "scoreability_delta_ge_0_03": feasibility["overall"] >= 0.03,
        "scoreability_task_ci_low_gt_0": feasibility["task_cluster_ci95"][0] > 0.0,
    }
    if all(method_gate.values()):
        status = "VERIFIED_POSITIVE_HURDLE_METHOD"
    elif all(feasibility_gate.values()):
        status = "VERIFIED_BENCHMARK_USEFUL_SCOREABILITY_SIGNAL"
    else:
        status = "VERIFIED_FAILURE_CENSORED_MECHANISM_ONLY"
    return {
        "status": status,
        "frozen_parents": len(frozen),
        "frozen_tasks": len({row["task"] for row in frozen}),
        "frozen_runs": len({row["run_id"] for row in frozen}),
        "arms": arms,
        "baselines": baselines,
        "comparisons": comparisons,
        "method_positive_gate": method_gate,
        "method_positive_claim_allowed": all(method_gate.values()),
        "benchmark_useful_feasibility_gate": feasibility_gate,
        "benchmark_useful_feasibility_claim_allowed": all(feasibility_gate.values()),
    }


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n")


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8", newline="\n")
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run(args: argparse.Namespace) -> int:
    if not isinstance(args.source_commit, str) or not HEX40.fullmatch(args.source_commit):
        raise BaselineError("source commit must be full lowercase SHA-1")
    cards_path = Path(args.cards).resolve()
    identity_path = Path(args.identity_registry).resolve()
    status_path = Path(args.status_registry).resolve()
    for path in (cards_path, identity_path, status_path):
        if not path.is_file():
            raise BaselineError(f"missing input: {path.name}")
        scan_file(path)
    roots = parse_roots(args.root)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise BaselineError("output path already exists")

    cards = load_cards(cards_path)
    identity_rows, totals = load_identity(identity_path)
    missing_status = load_missing_status(status_path)
    parents, targets = build_parent_targets(cards, identity_rows)
    hits, journal_inventory = scan_journals(roots, targets)
    candidates, construction_parents, integrity = resolve_candidates(
        cards, parents, missing_status, hits
    )
    construction = summarize_construction(construction_parents, totals, integrity)
    summary: dict[str, Any] = {
        "protocol": PROTOCOL,
        "source_commit": args.source_commit,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "input_sha256": {
            "cards": sha256_file(cards_path),
            "identity_registry": sha256_file(identity_path),
            "status_registry": sha256_file(status_path),
        },
        "scope": {
            "journal_numeric_grade_magnitude_used": False,
            "records_raw_code_or_stdout": False,
            "reads_pair_orientation": False,
            "reads_first960_or_prospective_outcomes": False,
            "train_roles_used_for_fit": ["train"],
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
        "construction": construction,
        "journal_inventory": journal_inventory,
        "runtime": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "sklearn": sklearn.__version__,
        },
    }
    parent_metric_rows: list[dict[str, Any]] = []
    score_rows_out: list[dict[str, Any]] = []
    if construction["construction_gate_pass"]:
        train_rows = [row for row in candidates if row["role"] == "train"]
        all_public = [public_row(row) for row in candidates]
        scores, diagnostics = fit_and_score(train_rows, all_public)
        score_rows_out = [
            {
                "role": row["role"], "parent": row["parent"], "task": row["task"],
                "run_id": row["run_id"], "child_id": row["child_id"],
                "retained": row["retained"], "category": row["category"],
                "exec_ok": row["exec_ok"], "scoreable": row["scoreable"],
                "utility": format(float(row["utility"]), ".17g"),
                "code_sha256": row["code_sha256"],
                **{arm: format(scores[row["child_id"]][arm], ".17g") for arm in ARMS},
            }
            for row in candidates
        ]
        blind_projection = [
            {key: value for key, value in row.items() if key not in {"category", "exec_ok", "scoreable", "utility"}}
            for row in score_rows_out
        ]
        blind_scores_sha = sha256_bytes(b"".join(canonical_json(row) for row in blind_projection))
        parent_metric_rows = parent_metrics(candidates, scores, "frozen")
        comparisons = {
            "hurdle_tfidf_vs_quality_tfidf_scoreability": comparison(
                parent_metric_rows, "hurdle_tfidf", "quality_tfidf", "scoreability"
            ),
            "hurdle_tfidf_vs_quality_tfidf_utility": comparison(
                parent_metric_rows, "hurdle_tfidf", "quality_tfidf", "utility"
            ),
            "hurdle_static_vs_quality_static_scoreability": comparison(
                parent_metric_rows, "hurdle_static", "quality_static", "scoreability"
            ),
            "hurdle_static_vs_quality_static_utility": comparison(
                parent_metric_rows, "hurdle_static", "quality_static", "utility"
            ),
            "scoreability_tfidf_vs_random_expected_scoreability": comparison(
                parent_metric_rows, "scoreability_tfidf", "random_expected", "scoreability"
            ),
            "scoreability_static_vs_random_expected_scoreability": comparison(
                parent_metric_rows, "scoreability_static", "random_expected", "scoreability"
            ),
        }
        summary["model"] = diagnostics
        summary["blind_scores_sha256_before_frozen_evaluation"] = blind_scores_sha
        summary["results"] = summarize_results(parent_metric_rows, comparisons)
        summary["status"] = summary["results"]["status"]
    else:
        summary["status"] = "CONSTRUCTION_GATE_FAILED"

    staging.mkdir(parents=True)
    write_json(staging / "summary.json", summary)
    write_csv(staging / "construction_per_parent.csv", [
        {**row, "exclusion_reasons": ";".join(row["exclusion_reasons"])}
        for row in construction_parents
    ])
    write_csv(staging / "candidate_scores.csv", score_rows_out)
    write_csv(staging / "frozen_per_parent.csv", parent_metric_rows)
    (staging / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8", newline="\n")
    manifest = {
        path.name: sha256_file(path)
        for path in sorted(staging.iterdir()) if path.is_file()
    }
    write_json(staging / "sha256_manifest.json", manifest)
    for path in staging.iterdir():
        scan_file(path)
    staging.replace(output)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--cards", required=True)
    value.add_argument("--identity-registry", required=True)
    value.add_argument("--status-registry", required=True)
    value.add_argument("--root", action="append", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except BaselineError as exc:
        print(f"SOURCE_OPPORTUNITY_HURDLE_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
