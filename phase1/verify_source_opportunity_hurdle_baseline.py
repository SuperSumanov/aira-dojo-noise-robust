#!/usr/bin/env python3
"""Independent structural/statistical verifier for hurdle baseline artifacts.

This module intentionally does not import the producer.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Sequence


PROTOCOL = "source-opportunity-hurdle-baseline-v1"
SEED = 20260815
REPETITIONS = 5000
HEX40 = re.compile(r"[0-9a-f]{40}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|"
    rb"-----?BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----?)"
)
ARMS = (
    "quality_static", "quality_tfidf", "scoreability_static",
    "scoreability_tfidf", "hurdle_static", "hurdle_tfidf",
)
BASE_CANDIDATE_FIELDS = (
    "role", "parent", "task", "run_id", "child_id", "retained", "category",
    "exec_ok", "scoreable", "utility", "code_sha256",
)


class VerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def scan(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise VerificationError(f"credential-shaped bytes in {path.name}")
            overlap = payload[-256:]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {path.name}") from exc


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise VerificationError(f"invalid bool: {where}")


def parse_float(value: Any, where: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"invalid float: {where}") from exc
    if not math.isfinite(result):
        raise VerificationError(f"nonfinite float: {where}")
    return result


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def verify_producer_manifest(producer: Path) -> None:
    manifest = load_json(producer / "sha256_manifest.json")
    expected_names = {
        "summary.json", "construction_per_parent.csv", "candidate_scores.csv",
        "frozen_per_parent.csv", "command.txt",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_names:
        raise VerificationError("producer manifest schema mismatch")
    for name, expected in manifest.items():
        if not isinstance(expected, str) or sha256_file(producer / name) != expected:
            raise VerificationError(f"producer manifest mismatch: {name}")


def load_candidates(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    blind: list[dict[str, Any]] = []
    expected = set(BASE_CANDIDATE_FIELDS) | set(ARMS)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or []) != expected:
            raise VerificationError("candidate score fields mismatch")
        seen: set[str] = set()
        for line_number, raw in enumerate(reader, 2):
            child = raw["child_id"]
            if not child or child in seen:
                raise VerificationError(f"duplicate/empty child line {line_number}")
            seen.add(child)
            if raw["role"] not in {"train", "frozen", "extension"}:
                raise VerificationError(f"invalid role line {line_number}")
            retained = parse_bool(raw["retained"], f"retained line {line_number}")
            exec_ok = parse_bool(raw["exec_ok"], f"exec_ok line {line_number}")
            scoreable = parse_bool(raw["scoreable"], f"scoreable line {line_number}")
            utility = parse_float(raw["utility"], f"utility line {line_number}")
            if not 0.0 <= utility <= 1.0 or not re.fullmatch(r"[0-9a-f]{64}", raw["code_sha256"]):
                raise VerificationError(f"invalid utility/hash line {line_number}")
            category = raw["category"]
            if category == "SCOREABLE" and not (retained and exec_ok and scoreable):
                raise VerificationError(f"invalid SCOREABLE row {line_number}")
            if category == "EXECUTION_ERROR" and (exec_ok or scoreable or utility != 0.0):
                raise VerificationError(f"invalid execution-error row {line_number}")
            if category == "OFFICIAL_GRADE_ABSENT" and (
                not exec_ok or scoreable or utility != 0.0
            ):
                raise VerificationError(f"invalid grade-absent row {line_number}")
            scores = {arm: parse_float(raw[arm], f"{arm} line {line_number}") for arm in ARMS}
            for arm in ("scoreability_static", "scoreability_tfidf", "hurdle_static", "hurdle_tfidf"):
                if not 0.0 <= scores[arm] <= 1.0:
                    raise VerificationError(f"probability score out of range line {line_number}")
            rows.append(
                {
                    "role": raw["role"], "parent": raw["parent"], "task": raw["task"],
                    "run_id": raw["run_id"], "child_id": child, "retained": retained,
                    "category": category, "exec_ok": exec_ok, "scoreable": scoreable,
                    "utility": utility, "code_sha256": raw["code_sha256"], **scores,
                }
            )
            blind.append(
                {
                    "role": raw["role"], "parent": raw["parent"], "task": raw["task"],
                    "run_id": raw["run_id"], "child_id": child, "retained": retained,
                    "code_sha256": raw["code_sha256"], **{arm: raw[arm] for arm in ARMS},
                }
            )
    if not rows:
        raise VerificationError("empty candidate scores")
    return rows, blind


def tie_mean(values: Sequence[tuple[float, float]]) -> float:
    if not values:
        raise VerificationError("empty tie values")
    maximum = max(score for score, _ in values)
    selected = [value for score, value in values if abs(score - maximum) <= 1e-12]
    return sum(selected) / len(selected)


def rebuild_parent_rows(candidates: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in candidates:
        if row["role"] == "frozen":
            grouped[row["parent"]].append(row)
    output = []
    for parent, rows in sorted(grouped.items()):
        contexts = {(row["task"], row["run_id"]) for row in rows}
        if len(contexts) != 1:
            raise VerificationError(f"mixed parent context: {parent}")
        task, run_id = next(iter(contexts))
        value: dict[str, Any] = {
            "role": "frozen", "parent": parent, "task": task, "run_id": run_id,
            "source_size": len(rows),
            "random_expected_scoreability": sum(row["scoreable"] for row in rows) / len(rows),
            "random_expected_utility": sum(row["utility"] for row in rows) / len(rows),
            "oracle_scoreability": float(max(row["scoreable"] for row in rows)),
            "oracle_utility": max(row["utility"] for row in rows),
        }
        for arm in ARMS:
            value[f"{arm}_scoreability"] = tie_mean(
                [(row[arm], float(row["scoreable"])) for row in rows]
            )
            value[f"{arm}_utility"] = tie_mean([(row[arm], row["utility"]) for row in rows])
        output.append(value)
    if not output:
        raise VerificationError("no frozen parent rows")
    return output


def load_reported_parent_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise VerificationError("empty reported parent metrics")
    return rows


def compare_parent_rows(rebuilt: Sequence[dict[str, Any]], reported: Sequence[dict[str, str]]) -> None:
    if len(rebuilt) != len(reported):
        raise VerificationError("parent row count mismatch")
    reported_by_parent = {row["parent"]: row for row in reported}
    if len(reported_by_parent) != len(reported):
        raise VerificationError("duplicate reported parent")
    for expected in rebuilt:
        actual = reported_by_parent.get(expected["parent"])
        if actual is None or set(actual) != set(expected):
            raise VerificationError(f"parent schema/identity mismatch: {expected['parent']}")
        for key, value in expected.items():
            if isinstance(value, str):
                if actual[key] != value:
                    raise VerificationError(f"parent text mismatch: {key}")
            else:
                if abs(parse_float(actual[key], key) - float(value)) > 1e-12:
                    raise VerificationError(f"parent value mismatch: {key}")


def cluster_ci(rows: Sequence[dict[str, Any]], field: str, cluster: str) -> list[float]:
    groups: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row[cluster])].append(float(row[field]))
    keys = sorted(groups)
    rng = random.Random(SEED)
    samples = []
    for _ in range(REPETITIONS):
        values = [value for key in (rng.choice(keys) for _ in keys) for value in groups[key]]
        samples.append(sum(values) / len(values))
    samples.sort()
    return [samples[int(0.025 * REPETITIONS)], samples[int(0.975 * REPETITIONS)]]


def comparison(rows: Sequence[dict[str, Any]], left: str, right: str, metric: str) -> dict[str, Any]:
    field = f"delta__{left}__{right}__{metric}"
    for row in rows:
        row[field] = float(row[f"{left}_{metric}"] - row[f"{right}_{metric}"])
    by_task: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        by_task[row["task"]].append(row[field])
    supported = {task: values for task, values in by_task.items() if len(values) >= 5}
    return {
        "left": left, "right": right, "metric": metric,
        "overall": sum(row[field] for row in rows) / len(rows),
        "task_cluster_ci95": cluster_ci(rows, field, "task"),
        "run_cluster_ci95": cluster_ci(rows, field, "run_id"),
        "parent_ci95": cluster_ci(rows, field, "parent"),
        "task_macro": sum(sum(values) / len(values) for values in by_task.values()) / len(by_task),
        "supported_tasks": len(supported),
        "supported_task_nonnegative_share": (
            float(
                sum((sum(values) / len(values)) >= 0.0 for values in supported.values())
                / len(supported)
            )
            if supported else None
        ),
        "per_task": {
            task: {"parents": len(values), "mean": sum(values) / len(values)}
            for task, values in sorted(by_task.items())
        },
    }


def close(actual: Any, expected: Any, where: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise VerificationError(f"mapping mismatch: {where}")
        for key in expected:
            close(actual[key], expected[key], f"{where}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise VerificationError(f"list mismatch: {where}")
        for index, value in enumerate(expected):
            close(actual[index], value, f"{where}[{index}]")
    elif isinstance(expected, float):
        if abs(parse_float(actual, where) - expected) > 1e-12:
            raise VerificationError(f"float mismatch: {where}")
    elif actual != expected:
        raise VerificationError(f"value mismatch: {where}")


def reconstruct_results(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    comparisons = {
        "hurdle_tfidf_vs_quality_tfidf_scoreability": comparison(
            rows, "hurdle_tfidf", "quality_tfidf", "scoreability"
        ),
        "hurdle_tfidf_vs_quality_tfidf_utility": comparison(
            rows, "hurdle_tfidf", "quality_tfidf", "utility"
        ),
        "hurdle_static_vs_quality_static_scoreability": comparison(
            rows, "hurdle_static", "quality_static", "scoreability"
        ),
        "hurdle_static_vs_quality_static_utility": comparison(
            rows, "hurdle_static", "quality_static", "utility"
        ),
        "scoreability_tfidf_vs_random_expected_scoreability": comparison(
            rows, "scoreability_tfidf", "random_expected", "scoreability"
        ),
        "scoreability_static_vs_random_expected_scoreability": comparison(
            rows, "scoreability_static", "random_expected", "scoreability"
        ),
    }
    arms = {
        arm: {
            "scoreability": sum(row[f"{arm}_scoreability"] for row in rows) / len(rows),
            "utility": sum(row[f"{arm}_utility"] for row in rows) / len(rows),
        }
        for arm in ARMS
    }
    baselines = {
        base: {
            "scoreability": sum(row[f"{base}_scoreability"] for row in rows) / len(rows),
            "utility": sum(row[f"{base}_utility"] for row in rows) / len(rows),
        }
        for base in ("random_expected", "oracle")
    }
    hs = comparisons["hurdle_tfidf_vs_quality_tfidf_scoreability"]
    hu = comparisons["hurdle_tfidf_vs_quality_tfidf_utility"]
    fs = comparisons["scoreability_tfidf_vs_random_expected_scoreability"]
    method = {
        "scoreability_delta_ge_0_02": hs["overall"] >= 0.02,
        "utility_delta_ge_0_02": hu["overall"] >= 0.02,
        "scoreability_task_ci_low_gt_0": hs["task_cluster_ci95"][0] > 0.0,
        "utility_task_ci_low_gt_0": hu["task_cluster_ci95"][0] > 0.0,
        "supported_task_utility_nonnegative_share_ge_0_60": (
            hu["supported_task_nonnegative_share"] is not None
            and hu["supported_task_nonnegative_share"] >= 0.60
        ),
    }
    feasibility = {
        "scoreability_delta_ge_0_03": fs["overall"] >= 0.03,
        "scoreability_task_ci_low_gt_0": fs["task_cluster_ci95"][0] > 0.0,
    }
    status = (
        "VERIFIED_POSITIVE_HURDLE_METHOD" if all(method.values())
        else "VERIFIED_BENCHMARK_USEFUL_SCOREABILITY_SIGNAL"
        if all(feasibility.values()) else "VERIFIED_FAILURE_CENSORED_MECHANISM_ONLY"
    )
    result = {
        "status": status,
        "frozen_parents": len(rows),
        "frozen_tasks": len({row["task"] for row in rows}),
        "frozen_runs": len({row["run_id"] for row in rows}),
        "arms": arms, "baselines": baselines, "comparisons": comparisons,
        "method_positive_gate": method,
        "method_positive_claim_allowed": all(method.values()),
        "benchmark_useful_feasibility_gate": feasibility,
        "benchmark_useful_feasibility_claim_allowed": all(feasibility.values()),
    }
    return result, comparisons


def verify(args: argparse.Namespace) -> dict[str, Any]:
    artifact = Path(args.artifact).resolve()
    producer = artifact / "producer"
    if not artifact.is_dir() or not producer.is_dir():
        raise VerificationError("artifact/producer missing")
    if not HEX40.fullmatch(args.expected_commit):
        raise VerificationError("invalid expected commit")
    for path in artifact.rglob("*"):
        if path.is_file():
            scan(path)
    verify_producer_manifest(producer)
    summary = load_json(producer / "summary.json")
    if summary.get("protocol") != PROTOCOL or summary.get("source_commit") != args.expected_commit:
        raise VerificationError("protocol/source commit mismatch")
    if summary.get("status") == "CONSTRUCTION_GATE_FAILED":
        raise VerificationError("cannot verify model result after construction failure")
    if summary.get("construction", {}).get("construction_gate_pass") is not True:
        raise VerificationError("construction gate not true")
    if not all(summary["construction"]["criteria"].values()):
        raise VerificationError("construction criterion false")
    if summary.get("model", {}).get("fit_roles") != ["train"]:
        raise VerificationError("fit roles are not train-only")
    scope = summary.get("scope", {})
    required_false = (
        "journal_numeric_grade_magnitude_used", "records_raw_code_or_stdout",
        "reads_pair_orientation", "reads_first960_or_prospective_outcomes",
    )
    if any(scope.get(key) is not False for key in required_false):
        raise VerificationError("scope false attestation mismatch")
    if any(scope.get(key) != 0 for key in ("gpu", "api_calls", "base_llm_updates")):
        raise VerificationError("resource scope mismatch")

    candidates, blind = load_candidates(producer / "candidate_scores.csv")
    blind_sha = sha256_bytes(b"".join(canonical_json(row) for row in blind))
    if blind_sha != summary.get("blind_scores_sha256_before_frozen_evaluation"):
        raise VerificationError("blind score seal mismatch")
    rebuilt = rebuild_parent_rows(candidates)
    reconstructed, _ = reconstruct_results(rebuilt)
    reported = load_reported_parent_rows(producer / "frozen_per_parent.csv")
    compare_parent_rows(rebuilt, reported)
    close(summary.get("results"), reconstructed, "results")
    if summary.get("status") != reconstructed["status"]:
        raise VerificationError("top-level status mismatch")
    return {
        "protocol": "independent-source-opportunity-hurdle-verifier-v1",
        "status": reconstructed["status"],
        "source_commit": args.expected_commit,
        "producer_summary_sha256": sha256_file(producer / "summary.json"),
        "candidate_scores_sha256": sha256_file(producer / "candidate_scores.csv"),
        "blind_scores_sha256": blind_sha,
        "candidate_rows": len(candidates),
        "frozen_parents": len(rebuilt),
        "frozen_tasks": len({row["task"] for row in rebuilt}),
        "all_parent_metrics_rebuilt": True,
        "all_cluster_intervals_rebuilt": True,
        "all_gates_rebuilt": True,
        "imports_producer": False,
    }


def run(args: argparse.Namespace) -> int:
    receipt = Path(args.receipt).resolve()
    staging = receipt.with_name(receipt.name + f".tmp-{os.getpid()}")
    if receipt.exists() or staging.exists():
        raise VerificationError("receipt path already exists")
    value = verify(args)
    staging.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    scan(staging)
    staging.replace(receipt)
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--artifact", required=True)
    value.add_argument("--expected-commit", required=True)
    value.add_argument("--receipt", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except VerificationError as exc:
        print(f"HURDLE_VERIFICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
