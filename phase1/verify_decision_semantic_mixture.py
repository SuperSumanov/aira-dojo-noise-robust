"""Independent full-refit verifier for Decision Semantic Mixture v1.

This module intentionally does not import the producer.  It independently
loads the fixed inputs, refits all three heads, reconstructs every reported
metric/gate, and compares the aggregate-only artifact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import sklearn
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


PROTOCOL = "decision-semantic-mixture-discovery-v1"
VERIFY_PROTOCOL = "independent-decision-semantic-mixture-discovery-v1"
STATUS = "INDEPENDENT_DECISION_SEMANTIC_MIXTURE_VERIFIED"
SENIOR = "baf6bddefe62b769b2fab699ff5805dd627dc69f"
IDENTITIES = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "merged": ("c62dae814f7834b9beb3457d63fb60963636a31a811b216616e6912681bba2f4", 2858161),
    "draft": ("84adc361226899d4fd7b1a17cef3bf27884e76ec591566c7a4470fd525a94de7", 1714459),
    "improve": ("c2a062a81b7aa12457d4cb6a66aa102f8623bdfbb2961dd7d443c2c3e16ab516", 1143702),
}
PAIR_KEYS = {
    "better", "budget", "clears_tau", "gap_raw", "intask_split", "loto_fold",
    "parent", "set_size", "src", "task", "worse",
}
SECRET_RX = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerifyError(RuntimeError):
    """Independent verification failed."""


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def secure_identity(path: Path, role: str) -> None:
    expected_hash, expected_bytes = IDENTITIES[role]
    if path.stat().st_size != expected_bytes or file_hash(path) != expected_hash:
        raise VerifyError(f"{role} input identity mismatch")
    overlap = b""
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1 << 20)
            if not chunk:
                break
            candidate = overlap + chunk
            if SECRET_RX.search(candidate):
                raise VerifyError(f"credential-shaped {role} content")
            overlap = candidate[-512:]


def pairs(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for number, text in enumerate(stream, 1):
            value = json.loads(text)
            if (
                not text.strip()
                or not isinstance(value, dict)
                or set(value) != PAIR_KEYS
                or value.get("intask_split") not in {"train", "test"}
                or value.get("src") != "decision"
                or not isinstance(value.get("gap_raw"), (int, float))
                or isinstance(value.get("gap_raw"), bool)
                or not math.isfinite(value["gap_raw"])
                or value["gap_raw"] <= 0
            ):
                raise VerifyError(f"pair row malformed: {path.name}:{number}")
            result.append(value)
    return result


def identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    endpoints = sorted((str(row["better"]), str(row["worse"])))
    return str(row["task"]), str(row["parent"]), endpoints[0], endpoints[1]


def serialized(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def selected(rows: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["intask_split"] == role]


def load_card_features(
    path: Path, wanted: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise VerifyError("cards are not grouped by run")
    code: dict[str, str] = {}
    run_of: dict[str, str] = {}
    config: dict[str, tuple[Any, ...]] = {}
    every_id: set[str] = set()
    total = 0
    for run_id, group in grouped.items():
        if not isinstance(run_id, str) or not isinstance(group, list):
            raise VerifyError("invalid card group")
        for card in group:
            total += 1
            if not isinstance(card, dict):
                raise VerifyError("card is not an object")
            card_id = card.get("id")
            if not isinstance(card_id, str) or card_id in every_id:
                raise VerifyError("duplicate card identity")
            every_id.add(card_id)
            if card_id not in wanted:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            fields = (
                task, card.get("client"), card.get("hardware"),
                card.get("time_limit"), card.get("execution_timeout"),
            )
            if (
                not isinstance(card.get("code"), str)
                or not all(isinstance(item, str) for item in fields[:3])
                or not all(isinstance(item, int) for item in fields[3:])
            ):
                raise VerifyError("relevant card fields invalid")
            code[card_id] = card["code"]
            run_of[card_id] = run_id
            config[card_id] = fields
    if set(code) != wanted:
        raise VerifyError("pair endpoints absent from cards")
    return code, run_of, config, {
        "run_groups": len(grouped), "cards": total, "needed_cards": len(wanted),
        "duplicate_card_ids": total - len(every_id),
    }


def independent_integrity(
    merged: list[dict[str, Any]],
    draft: list[dict[str, Any]],
    improve: list[dict[str, Any]],
    run_of: dict[str, str],
    config: dict[str, tuple[Any, ...]],
    card_inventory: dict[str, int],
) -> dict[str, Any]:
    groups = {"merged": merged, "draft": draft, "improve": improve}
    duplicate = {name: len(rows) - len({identity(row) for row in rows}) for name, rows in groups.items()}
    bad_task = bad_config = 0
    for row in [*merged, *draft, *improve]:
        left, right = config[row["better"]], config[row["worse"]]
        bad_task += left[0] != row["task"] or right[0] != row["task"]
        bad_config += left != right
    training, testing = selected(merged, "train"), selected(merged, "test")
    train_cards = {row[key] for row in training for key in ("better", "worse")}
    test_cards = {row[key] for row in testing for key in ("better", "worse")}
    train_runs = {run_of[item] for item in train_cards}
    test_runs = {run_of[item] for item in test_cards}
    count_map = {
        "card_run_groups": card_inventory["run_groups"],
        "cards": card_inventory["cards"],
        "merged_train": len(training), "merged_test": len(testing),
        "draft_train": len(selected(draft, "train")), "draft_test": len(selected(draft, "test")),
        "improve_train": len(selected(improve, "train")), "improve_test": len(selected(improve, "test")),
    }
    expected_counts = {
        "card_run_groups": 676, "cards": 31742, "merged_train": 5596, "merged_test": 960,
        "draft_train": 3552, "draft_test": 343, "improve_train": 2044, "improve_test": 617,
    }
    checks = {
        "expected_pair_counts": count_map == expected_counts,
        "merged_is_exact_component_union": Counter(map(serialized, merged))
        == Counter(map(serialized, [*draft, *improve])),
        "draft_improve_pair_identity_disjoint": not {identity(row) for row in draft}.intersection(
            identity(row) for row in improve
        ),
        "pair_identity_unique": all(value == 0 for value in duplicate.values()),
        "task_matches_cards": bad_task == 0,
        "exact_execution_config_within_every_pair": bad_config == 0,
        "train_test_endpoint_disjoint": not train_cards.intersection(test_cards),
        "train_test_physical_run_disjoint": not train_runs.intersection(test_runs),
    }
    if not all(checks.values()):
        raise VerifyError("independent integrity failure")
    return {
        "checks": checks, "counts": count_map, "duplicate_pair_identities": duplicate,
        "task_mismatches": bad_task, "execution_config_mismatches": bad_config,
        "train_endpoints": len(train_cards), "test_endpoints": len(test_cards),
        "train_runs": len(train_runs), "test_runs": len(test_runs),
        "train_test_endpoint_overlap": 0, "train_test_run_overlap": 0,
    }


def row_indices(rows: list[dict[str, Any]], index: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    left = np.array([index[row["better"]] for row in rows], dtype=np.int64)
    right = np.array([index[row["worse"]] for row in rows], dtype=np.int64)
    return left, right


def train(
    features: sparse.csr_matrix, rows: list[dict[str, Any]], index: dict[str, int]
) -> LogisticRegression:
    better, worse = row_indices(rows, index)
    delta = features[better] - features[worse]
    x = sparse.vstack([delta, -delta], format="csr")
    y = np.r_[np.ones(len(rows), dtype=np.int8), np.zeros(len(rows), dtype=np.int8)]
    head = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0)
    head.fit(x, y)
    if int(head.n_iter_[0]) >= 1500 or not np.isfinite(head.coef_).all():
        raise VerifyError("head convergence failure")
    return head


def score(
    head: LogisticRegression,
    features: sparse.csr_matrix,
    rows: list[dict[str, Any]],
    index: dict[str, int],
) -> np.ndarray:
    better, worse = row_indices(rows, index)
    output = np.asarray(head.decision_function(features[better] - features[worse]), dtype=np.float64)
    if not np.isfinite(output).all():
        raise VerifyError("non-finite verifier margin")
    return output


def qstats(array: np.ndarray) -> dict[str, float | None]:
    labels = ("q00", "q10", "q25", "q50", "q75", "q90", "q100")
    if len(array) == 0:
        return {label: None for label in labels}
    values = np.quantile(array, [0, .1, .25, .5, .75, .9, 1], method="linear")
    return dict(zip(labels, map(float, values)))


def compute_metrics(
    test: list[dict[str, Any]], types: list[str], predictions: dict[str, np.ndarray]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output: dict[str, Any] = {}
    task_rows: list[dict[str, Any]] = []
    for subset in ("merged", "draft", "improve"):
        mask = np.array([subset == "merged" or kind == subset for kind in types], dtype=bool)
        rows = [row for row, include in zip(test, mask) if include]
        task_list = sorted({row["task"] for row in rows})
        output[subset] = {}
        for arm in ("pooled", "specialist", "semantic_mix"):
            margin = predictions[arm][mask]
            correct = margin > 0
            per_task = [
                float(np.mean([flag for row, flag in zip(rows, correct) if row["task"] == task]))
                for task in task_list
            ]
            output[subset][arm] = {
                "pairs": len(rows), "tasks": len(task_list),
                "parents": len({(row["task"], row["parent"]) for row in rows}),
                "micro_accuracy": float(np.mean(correct)),
                "task_macro_accuracy": float(np.mean(per_task)),
                "ties": int(np.sum(margin == 0)), "margin_quantiles": qstats(margin),
            }
        for task in task_list:
            task_mask = np.array([row["task"] == task for row in rows], dtype=bool)
            record: dict[str, Any] = {"subset": subset, "task": task, "pairs": int(task_mask.sum())}
            for arm in ("pooled", "specialist", "semantic_mix"):
                record[f"{arm}_accuracy"] = float(np.mean((predictions[arm][mask][task_mask]) > 0))
            record["semantic_mix_minus_pooled"] = (
                record["semantic_mix_accuracy"] - record["pooled_accuracy"]
            )
            task_rows.append(record)
    return output, task_rows


def infer(
    test: list[dict[str, Any]], tasks: list[dict[str, Any]], predictions: dict[str, np.ndarray]
) -> tuple[dict[str, Any], dict[str, Any]]:
    merged = [row for row in tasks if row["subset"] == "merged"]
    task_delta = np.array([row["semantic_mix_minus_pooled"] for row in merged], dtype=float)
    rng = np.random.default_rng(20260821)
    draws = rng.integers(0, len(task_delta), (20000, len(task_delta)))
    task_values = task_delta[draws].mean(axis=1)
    task_interval = np.quantile(task_values, [.025, .975], method="linear")
    task_receipt = {
        "estimand": "merged_task_macro_delta", "point": float(task_delta.mean()),
        "ci95": list(map(float, task_interval)), "clusters": len(task_delta),
        "replicates": 20000, "seed": 20260821,
    }
    pair_delta = (predictions["semantic_mix"] > 0).astype(float) - (
        predictions["pooled"] > 0
    ).astype(float)
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, value in zip(test, pair_delta):
        grouped[(row["task"], row["parent"])].append(float(value))
    blocks = [np.array(grouped[key], dtype=float) for key in sorted(grouped)]
    generator = np.random.default_rng(20260822)
    samples = np.empty(20000)
    for repeat in range(20000):
        take = generator.integers(0, len(blocks), len(blocks))
        samples[repeat] = sum(blocks[i].sum() for i in take) / sum(len(blocks[i]) for i in take)
    parent_interval = np.quantile(samples, [.025, .975], method="linear")
    parent_receipt = {
        "estimand": "merged_pair_micro_delta_parent_clustered",
        "point": float(pair_delta.mean()), "ci95": list(map(float, parent_interval)),
        "clusters": len(blocks), "replicates": 20000, "seed": 20260822,
    }
    return task_receipt, parent_receipt


def rebuild(
    code: dict[str, str], merged: list[dict[str, Any]], draft: list[dict[str, Any]], improve: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    train_all, test = selected(merged, "train"), selected(merged, "test")
    all_ids = sorted({row[key] for row in merged for key in ("better", "worse")})
    train_ids = sorted({row[key] for row in train_all for key in ("better", "worse")})
    location = {identifier: position for position, identifier in enumerate(all_ids)}
    tfidf = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=30000,
        min_df=3, sublinear_tf=True, dtype=np.float64,
    )
    tfidf.fit([code[identifier][:20000] for identifier in train_ids])
    matrix = tfidf.transform([code[identifier][:20000] for identifier in all_ids]).tocsr()
    heads = {
        "pooled": train(matrix, train_all, location),
        "draft": train(matrix, selected(draft, "train"), location),
        "improve": train(matrix, selected(improve, "train"), location),
    }
    base = score(heads["pooled"], matrix, test, location)
    draft_scores = score(heads["draft"], matrix, test, location)
    improve_scores = score(heads["improve"], matrix, test, location)
    draft_test = {identity(row) for row in selected(draft, "test")}
    improve_test = {identity(row) for row in selected(improve, "test")}
    types: list[str] = []
    specialist = np.empty(len(test), dtype=float)
    for position, row in enumerate(test):
        key = identity(row)
        if key in draft_test and key not in improve_test:
            types.append("draft")
            specialist[position] = draft_scores[position]
        elif key in improve_test and key not in draft_test:
            types.append("improve")
            specialist[position] = improve_scores[position]
        else:
            raise VerifyError("semantic test partition mismatch")
    prediction = {"pooled": base, "specialist": specialist, "semantic_mix": .5 * base + .5 * specialist}
    metrics, task_rows = compute_metrics(test, types, prediction)
    task_inference, parent_inference = infer(test, task_rows, prediction)
    supported = [row for row in task_rows if row["subset"] == "merged" and row["pairs"] >= 10]
    signs = Counter(
        "positive" if row["semantic_mix_minus_pooled"] > 0 else
        "negative" if row["semantic_mix_minus_pooled"] < 0 else "zero"
        for row in supported
    )
    consistency = {
        "minimum_pairs": 10, "tasks": len(supported), "positive": signs["positive"],
        "zero": signs["zero"], "negative": signs["negative"],
        "positive_fraction": signs["positive"] / len(supported) if supported else 0.0,
    }
    effects = {
        "merged_task_macro": metrics["merged"]["semantic_mix"]["task_macro_accuracy"]
        - metrics["merged"]["pooled"]["task_macro_accuracy"],
        "merged_micro": metrics["merged"]["semantic_mix"]["micro_accuracy"]
        - metrics["merged"]["pooled"]["micro_accuracy"],
        "draft_micro": metrics["draft"]["semantic_mix"]["micro_accuracy"]
        - metrics["draft"]["pooled"]["micro_accuracy"],
        "improve_micro": metrics["improve"]["semantic_mix"]["micro_accuracy"]
        - metrics["improve"]["pooled"]["micro_accuracy"],
    }
    gates = {
        "merged_task_macro_delta_ge_0_010": effects["merged_task_macro"] >= .010,
        "task_bootstrap_ci_lower_gt_0": task_inference["ci95"][0] > 0,
        "supported_tasks_ge_15": len(supported) >= 15,
        "supported_task_positive_fraction_ge_0_60": consistency["positive_fraction"] >= .60,
        "draft_micro_delta_ge_minus_0_005": effects["draft_micro"] >= -.005,
        "improve_micro_delta_ge_minus_0_005": effects["improve_micro"] >= -.005,
    }
    return {
        "representation": {
            "train_only_endpoints": len(train_ids), "all_decision_endpoints": len(all_ids),
            "features": len(tfidf.vocabulary_), "matrix_rows": matrix.shape[0],
            "matrix_columns": matrix.shape[1], "matrix_nnz": int(matrix.nnz),
            "code_prefix_chars": 20000,
            "vectorizer": {"analyzer": "char_wb", "ngram_range": [3, 5], "max_features": 30000,
                           "min_df": 3, "sublinear_tf": True, "dtype": "float64"},
        },
        "heads": {
            "pooled_train_pairs": len(train_all), "draft_train_pairs": len(selected(draft, "train")),
            "improve_train_pairs": len(selected(improve, "train")),
            "logistic": {"C": .5, "max_iter": 1500, "solver": "lbfgs", "random_state": 0},
            "iterations": {name: int(heads[name].n_iter_[0]) for name in ("pooled", "draft", "improve")},
        },
        "metrics": metrics, "primary_inference": task_inference,
        "secondary_parent_inference": parent_inference,
        "supported_task_consistency": consistency, "effect_deltas": effects, "gates": gates,
        "status": "DISCOVERY_UNLOCK_FUTURE_CONFIRMATION" if all(gates.values()) else "DISCOVERY_NO_UNLOCK",
    }, task_rows


def csv_rows(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            result.append(
                {
                    "subset": row["subset"], "task": row["task"], "pairs": int(row["pairs"]),
                    "pooled_accuracy": float(row["pooled_accuracy"]),
                    "specialist_accuracy": float(row["specialist_accuracy"]),
                    "semantic_mix_accuracy": float(row["semantic_mix_accuracy"]),
                    "semantic_mix_minus_pooled": float(row["semantic_mix_minus_pooled"]),
                }
            )
    return result


def verify(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(__file__).resolve().parent.parent
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if commit != args.source_commit or args.senior_commit != SENIOR:
        raise VerifyError("source commit mismatch")
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip():
        raise VerifyError("dirty verifier worktree")
    paths = {name: getattr(args, name).resolve(strict=True) for name in IDENTITIES}
    for name, path in paths.items():
        secure_identity(path, name)
    artifact = args.artifact.resolve(strict=True)
    manifest = json.loads((artifact / "artifact_manifest.json").read_text(encoding="utf-8"))
    expected_manifest = {
        "per_task.csv": file_hash(artifact / "per_task.csv"),
        "summary.json": file_hash(artifact / "summary.json"),
    }
    if manifest != expected_manifest:
        raise VerifyError("artifact manifest mismatch")
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    merged, draft, improve = (pairs(paths[name]) for name in ("merged", "draft", "improve"))
    wanted = {row[key] for row in [*merged, *draft, *improve] for key in ("better", "worse")}
    code, run_of, config, inventory = load_card_features(paths["cards"], wanted)
    integrity = independent_integrity(merged, draft, improve, run_of, config, inventory)
    rebuilt, tasks = rebuild(code, merged, draft, improve)
    checks = {
        "protocol": summary.get("protocol") == PROTOCOL,
        "source_commit": summary.get("source_commit") == commit,
        "senior_commit": summary.get("senior_source_commit") == SENIOR,
        "inputs": summary.get("inputs") == {
            name: {"sha256": IDENTITIES[name][0], "bytes": IDENTITIES[name][1]}
            for name in sorted(IDENTITIES)
        },
        "card_inventory": summary.get("card_inventory") == inventory,
        "integrity": summary.get("integrity") == integrity,
        "representation": summary.get("representation") == rebuilt["representation"],
        "heads": summary.get("heads") == rebuilt["heads"],
        "metrics": summary.get("metrics") == rebuilt["metrics"],
        "primary_inference": summary.get("primary_inference") == rebuilt["primary_inference"],
        "secondary_parent_inference": summary.get("secondary_parent_inference")
        == rebuilt["secondary_parent_inference"],
        "task_consistency": summary.get("supported_task_consistency")
        == rebuilt["supported_task_consistency"],
        "effects": summary.get("effect_deltas") == rebuilt["effect_deltas"],
        "gates": summary.get("gates") == rebuilt["gates"],
        "status": summary.get("status") == rebuilt["status"],
        "per_task": csv_rows(artifact / "per_task.csv") == tasks,
        "scope": summary.get("scope") == {
            "retrospective_test_previously_seen": True, "prospective_state_or_vault_read": False,
            "checkpoint_read": False, "api_calls": 0, "gpu_hours": 0, "base_llm_updates": 0,
            "features_use_code_only": True, "credential_shape_matches": 0,
        },
        "producer_source": summary.get("reproducibility", {}).get("source_sha256")
        == file_hash(args.producer_source.resolve(strict=True)),
    }
    if not all(checks.values()):
        raise VerifyError("aggregate mismatch: " + ",".join(name for name, ok in checks.items() if not ok))
    return {
        "protocol": VERIFY_PROTOCOL, "status": STATUS, "source_commit": commit,
        "artifact_summary_sha256": file_hash(artifact / "summary.json"),
        "verification": checks, "all_pass": True,
        "observed": {
            "scientific_status": rebuilt["status"],
            "merged_task_macro_delta": rebuilt["effect_deltas"]["merged_task_macro"],
            "task_ci95": rebuilt["primary_inference"]["ci95"],
            "passed_gates": sum(rebuilt["gates"].values()), "total_gates": len(rebuilt["gates"]),
        },
        "scope": {"producer_imported": False, "prospective_vault_read": False, "gpu_hours": 0, "api_calls": 0},
        "reproducibility": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                            "verifier_source_sha256": file_hash(Path(__file__).resolve())},
    }


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in IDENTITIES:
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--senior-commit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = args()
    if arguments.output.exists():
        print("DECISION_SEMANTIC_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(arguments)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(json_bytes(receipt))
    except (VerifyError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DECISION_SEMANTIC_VERIFY_ERROR: {error}", file=sys.stderr)
        return 1
    print(
        STATUS,
        f"scientific_status={receipt['observed']['scientific_status']}",
        f"delta={receipt['observed']['merged_task_macro_delta']:.17g}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
