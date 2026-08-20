"""Retrospective CPU discovery gate for Draft/Improve semantic heads.

The representation is fitted once on pooled decision-train endpoints.  Three
fixed logistic heads (pooled, Draft, Improve) produce a pooled baseline, a pure
specialist diagnostic, and the pre-registered 0.5 pooled + 0.5 specialist arm.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import scipy
import sklearn
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


PROTOCOL = "decision-semantic-mixture-discovery-v1"
SENIOR_COMMIT = "baf6bddefe62b769b2fab699ff5805dd627dc69f"
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "merged": ("c62dae814f7834b9beb3457d63fb60963636a31a811b216616e6912681bba2f4", 2858161),
    "draft": ("84adc361226899d4fd7b1a17cef3bf27884e76ec591566c7a4470fd525a94de7", 1714459),
    "improve": ("c2a062a81b7aa12457d4cb6a66aa102f8623bdfbb2961dd7d443c2c3e16ab516", 1143702),
}
EXPECTED_COUNTS = {
    "card_run_groups": 676,
    "cards": 31742,
    "merged_train": 5596,
    "merged_test": 960,
    "draft_train": 3552,
    "draft_test": 343,
    "improve_train": 2044,
    "improve_test": 617,
}
PAIR_FIELDS = {
    "better",
    "budget",
    "clears_tau",
    "gap_raw",
    "intask_split",
    "loto_fold",
    "parent",
    "set_size",
    "src",
    "task",
    "worse",
}
SECRET = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
ARMS = ("pooled", "specialist", "semantic_mix")
SUBSETS = ("merged", "draft", "improve")
TASK_BOOTSTRAP_SEED = 20260821
PARENT_BOOTSTRAP_SEED = 20260822
BOOTSTRAP_REPS = 20000


class DiscoveryError(RuntimeError):
    """Fail-closed protocol or integrity error."""


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def scan_secret(path: Path) -> None:
    tail = b""
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            window = tail + block
            if SECRET.search(window):
                raise DiscoveryError(f"credential-shaped content in {path.name}")
            tail = window[-512:]


def require_input(path: Path, role: str) -> None:
    expected_sha, expected_size = EXPECTED[role]
    if path.stat().st_size != expected_size or sha256(path) != expected_sha:
        raise DiscoveryError(f"fixed {role} input identity mismatch")
    scan_secret(path)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def read_pairs(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise DiscoveryError(f"blank pair row: {path.name}:{number}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != PAIR_FIELDS:
                raise DiscoveryError(f"pair schema mismatch: {path.name}:{number}")
            strings = (row["better"], row["worse"], row["task"], row["parent"], row["src"])
            if not all(isinstance(value, str) and value for value in strings):
                raise DiscoveryError(f"invalid pair identity: {path.name}:{number}")
            if row["better"] == row["worse"] or row["intask_split"] not in {"train", "test"}:
                raise DiscoveryError(f"invalid pair endpoints/split: {path.name}:{number}")
            if row["src"] != "decision" or not isinstance(row["set_size"], int) or row["set_size"] < 2:
                raise DiscoveryError(f"invalid decision semantics: {path.name}:{number}")
            gap = row["gap_raw"]
            if not isinstance(gap, (int, float)) or isinstance(gap, bool) or not math.isfinite(gap) or gap <= 0:
                raise DiscoveryError(f"invalid pair gap: {path.name}:{number}")
            rows.append(row)
    return rows


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    left, right = sorted((row["better"], row["worse"]))
    return row["task"], row["parent"], left, right


def row_key(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def task_name(card: dict[str, Any]) -> str | None:
    task = card.get("task")
    return task.get("name") if isinstance(task, dict) and isinstance(task.get("name"), str) else None


def load_cards(
    path: Path, needed: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[str, str, str, int, int]], dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DiscoveryError("cards root is not a run-grouped object")
    codes: dict[str, str] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[str, str, str, int, int]] = {}
    seen: set[str] = set()
    total = 0
    for run, cards in value.items():
        if not isinstance(run, str) or not isinstance(cards, list):
            raise DiscoveryError("invalid cards run group")
        for card in cards:
            total += 1
            if not isinstance(card, dict):
                raise DiscoveryError("non-object card")
            identifier = card.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                raise DiscoveryError("duplicate or invalid card ID")
            seen.add(identifier)
            if identifier not in needed:
                continue
            code = card.get("code")
            task = task_name(card)
            client, hardware = card.get("client"), card.get("hardware")
            time_limit, execution_timeout = card.get("time_limit"), card.get("execution_timeout")
            if (
                not isinstance(code, str)
                or not isinstance(task, str)
                or not isinstance(client, str)
                or not isinstance(hardware, str)
                or not isinstance(time_limit, int)
                or not isinstance(execution_timeout, int)
            ):
                raise DiscoveryError("relevant card feature/provenance missing")
            codes[identifier] = code
            runs[identifier] = run
            configs[identifier] = (task, client, hardware, time_limit, execution_timeout)
    missing = needed - codes.keys()
    if missing:
        raise DiscoveryError(f"missing {len(missing)} pair endpoint cards")
    return codes, runs, configs, {
        "run_groups": len(value),
        "cards": total,
        "needed_cards": len(needed),
        "duplicate_card_ids": total - len(seen),
    }


def split(rows: Iterable[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["intask_split"] == name]


def verify_integrity(
    merged: list[dict[str, Any]],
    draft: list[dict[str, Any]],
    improve: list[dict[str, Any]],
    runs: dict[str, str],
    configs: dict[str, tuple[str, str, str, int, int]],
    card_inventory: dict[str, Any],
    expected_counts: dict[str, int] = EXPECTED_COUNTS,
) -> dict[str, Any]:
    merged_counter = Counter(map(row_key, merged))
    component_counter = Counter(map(row_key, [*draft, *improve]))
    draft_keys = [pair_key(row) for row in draft]
    improve_keys = [pair_key(row) for row in improve]
    all_groups = {"merged": merged, "draft": draft, "improve": improve}
    duplicate_keys = {
        name: len(rows) - len({pair_key(row) for row in rows}) for name, rows in all_groups.items()
    }
    task_mismatches = config_mismatches = 0
    for row in [*merged, *draft, *improve]:
        left = configs[row["better"]]
        right = configs[row["worse"]]
        task_mismatches += left[0] != row["task"] or right[0] != row["task"]
        config_mismatches += left != right
    train_rows, test_rows = split(merged, "train"), split(merged, "test")
    train_endpoints = {row[key] for row in train_rows for key in ("better", "worse")}
    test_endpoints = {row[key] for row in test_rows for key in ("better", "worse")}
    train_runs = {runs[key] for key in train_endpoints}
    test_runs = {runs[key] for key in test_endpoints}
    counts = {
        "card_run_groups": card_inventory["run_groups"],
        "cards": card_inventory["cards"],
        "merged_train": len(train_rows),
        "merged_test": len(test_rows),
        "draft_train": len(split(draft, "train")),
        "draft_test": len(split(draft, "test")),
        "improve_train": len(split(improve, "train")),
        "improve_test": len(split(improve, "test")),
    }
    checks = {
        "expected_pair_counts": counts == expected_counts,
        "merged_is_exact_component_union": merged_counter == component_counter,
        "draft_improve_pair_identity_disjoint": not set(draft_keys).intersection(improve_keys),
        "pair_identity_unique": all(value == 0 for value in duplicate_keys.values()),
        "task_matches_cards": task_mismatches == 0,
        "exact_execution_config_within_every_pair": config_mismatches == 0,
        "train_test_endpoint_disjoint": not train_endpoints.intersection(test_endpoints),
        "train_test_physical_run_disjoint": not train_runs.intersection(test_runs),
    }
    if not all(checks.values()):
        raise DiscoveryError("integrity gate failed: " + ",".join(k for k, v in checks.items() if not v))
    return {
        "checks": checks,
        "counts": counts,
        "duplicate_pair_identities": duplicate_keys,
        "task_mismatches": task_mismatches,
        "execution_config_mismatches": config_mismatches,
        "train_endpoints": len(train_endpoints),
        "test_endpoints": len(test_endpoints),
        "train_runs": len(train_runs),
        "test_runs": len(test_runs),
        "train_test_endpoint_overlap": 0,
        "train_test_run_overlap": 0,
    }


def indices(rows: list[dict[str, Any]], positions: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    better = np.fromiter((positions[row["better"]] for row in rows), dtype=np.int64)
    worse = np.fromiter((positions[row["worse"]] for row in rows), dtype=np.int64)
    return better, worse


def fit_head(
    matrix: sparse.csr_matrix,
    rows: list[dict[str, Any]],
    positions: dict[str, int],
) -> LogisticRegression:
    better, worse = indices(rows, positions)
    differences = matrix[better] - matrix[worse]
    x = sparse.vstack((differences, -differences), format="csr")
    y = np.concatenate((np.ones(len(rows), dtype=np.int8), np.zeros(len(rows), dtype=np.int8)))
    model = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(x, y)
    if int(model.n_iter_[0]) >= 1500 or not np.isfinite(model.coef_).all() or not np.isfinite(model.intercept_).all():
        raise DiscoveryError("logistic head failed convergence/finite gate")
    return model


def margins(
    model: LogisticRegression,
    matrix: sparse.csr_matrix,
    rows: list[dict[str, Any]],
    positions: dict[str, int],
) -> np.ndarray:
    better, worse = indices(rows, positions)
    result = np.asarray(model.decision_function(matrix[better] - matrix[worse]), dtype=np.float64)
    if result.shape != (len(rows),) or not np.isfinite(result).all():
        raise DiscoveryError("invalid model margins")
    return result


def quantiles(values: np.ndarray) -> dict[str, float | None]:
    if not len(values):
        return {key: None for key in ("q00", "q10", "q25", "q50", "q75", "q90", "q100")}
    points = np.quantile(values, [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1], method="linear")
    return {key: float(value) for key, value in zip(("q00", "q10", "q25", "q50", "q75", "q90", "q100"), points)}


def arm_metrics(
    rows: list[dict[str, Any]], pair_types: list[str], arm_margins: dict[str, np.ndarray]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    aggregate: dict[str, Any] = {}
    per_task_rows: list[dict[str, Any]] = []
    for subset in SUBSETS:
        selected = np.asarray(
            [True if subset == "merged" else value == subset for value in pair_types], dtype=bool
        )
        subset_rows = [row for row, keep in zip(rows, selected) if keep]
        tasks = sorted({row["task"] for row in subset_rows})
        parents = {(row["task"], row["parent"]) for row in subset_rows}
        aggregate[subset] = {}
        for arm in ARMS:
            subset_margins = arm_margins[arm][selected]
            correct = subset_margins > 0
            task_accuracy = {
                task: float(
                    np.mean([flag for row, flag in zip(subset_rows, correct) if row["task"] == task])
                )
                for task in tasks
            }
            aggregate[subset][arm] = {
                "pairs": len(subset_rows),
                "tasks": len(tasks),
                "parents": len(parents),
                "micro_accuracy": float(np.mean(correct)),
                "task_macro_accuracy": float(np.mean(list(task_accuracy.values()))),
                "ties": int(np.sum(subset_margins == 0)),
                "margin_quantiles": quantiles(subset_margins),
            }
        for task in tasks:
            task_mask = np.asarray([row["task"] == task for row in subset_rows], dtype=bool)
            row: dict[str, Any] = {"subset": subset, "task": task, "pairs": int(np.sum(task_mask))}
            for arm in ARMS:
                values = arm_margins[arm][selected][task_mask] > 0
                row[f"{arm}_accuracy"] = float(np.mean(values))
            row["semantic_mix_minus_pooled"] = row["semantic_mix_accuracy"] - row["pooled_accuracy"]
            per_task_rows.append(row)
    return aggregate, per_task_rows


def task_bootstrap(per_task_rows: list[dict[str, Any]]) -> dict[str, Any]:
    merged = [row for row in per_task_rows if row["subset"] == "merged"]
    deltas = np.asarray([row["semantic_mix_minus_pooled"] for row in merged], dtype=np.float64)
    rng = np.random.default_rng(TASK_BOOTSTRAP_SEED)
    sampled = rng.integers(0, len(deltas), size=(BOOTSTRAP_REPS, len(deltas)))
    values = np.mean(deltas[sampled], axis=1)
    low, high = np.quantile(values, [0.025, 0.975], method="linear")
    return {
        "estimand": "merged_task_macro_delta",
        "point": float(np.mean(deltas)),
        "ci95": [float(low), float(high)],
        "clusters": len(deltas),
        "replicates": BOOTSTRAP_REPS,
        "seed": TASK_BOOTSTRAP_SEED,
    }


def parent_bootstrap(rows: list[dict[str, Any]], delta: np.ndarray) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, value in zip(rows, delta):
        grouped[(row["task"], row["parent"])].append(float(value))
    clusters = sorted(grouped)
    values = [np.asarray(grouped[key], dtype=np.float64) for key in clusters]
    rng = np.random.default_rng(PARENT_BOOTSTRAP_SEED)
    estimates = np.empty(BOOTSTRAP_REPS, dtype=np.float64)
    for index in range(BOOTSTRAP_REPS):
        selected = rng.integers(0, len(values), size=len(values))
        numerator = sum(float(np.sum(values[item])) for item in selected)
        denominator = sum(len(values[item]) for item in selected)
        estimates[index] = numerator / denominator
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "estimand": "merged_pair_micro_delta_parent_clustered",
        "point": float(np.mean(delta)),
        "ci95": [float(low), float(high)],
        "clusters": len(values),
        "replicates": BOOTSTRAP_REPS,
        "seed": PARENT_BOOTSTRAP_SEED,
    }


def analyze(
    codes: dict[str, str],
    merged: list[dict[str, Any]],
    draft: list[dict[str, Any]],
    improve: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    merged_train, merged_test = split(merged, "train"), split(merged, "test")
    draft_train = split(draft, "train")
    improve_train = split(improve, "train")
    needed = {row[key] for row in merged for key in ("better", "worse")}
    card_ids = sorted(needed)
    positions = {identifier: index for index, identifier in enumerate(card_ids)}
    train_ids = sorted({row[key] for row in merged_train for key in ("better", "worse")})
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=30000,
        min_df=3,
        sublinear_tf=True,
        dtype=np.float64,
    )
    vectorizer.fit([codes[identifier][:20000] for identifier in train_ids])
    matrix = vectorizer.transform([codes[identifier][:20000] for identifier in card_ids]).tocsr()
    pooled = fit_head(matrix, merged_train, positions)
    draft_head = fit_head(matrix, draft_train, positions)
    improve_head = fit_head(matrix, improve_train, positions)
    pooled_margin = margins(pooled, matrix, merged_test, positions)
    draft_margin = margins(draft_head, matrix, merged_test, positions)
    improve_margin = margins(improve_head, matrix, merged_test, positions)
    draft_test_keys = {pair_key(row) for row in split(draft, "test")}
    improve_test_keys = {pair_key(row) for row in split(improve, "test")}
    pair_types: list[str] = []
    for row in merged_test:
        key = pair_key(row)
        if key in draft_test_keys and key not in improve_test_keys:
            pair_types.append("draft")
        elif key in improve_test_keys and key not in draft_test_keys:
            pair_types.append("improve")
        else:
            raise DiscoveryError("test pair semantic identity is absent or ambiguous")
    specialist_margin = np.asarray(
        [draft_margin[index] if kind == "draft" else improve_margin[index] for index, kind in enumerate(pair_types)],
        dtype=np.float64,
    )
    arm_margin = {
        "pooled": pooled_margin,
        "specialist": specialist_margin,
        "semantic_mix": 0.5 * pooled_margin + 0.5 * specialist_margin,
    }
    metrics, per_task = arm_metrics(merged_test, pair_types, arm_margin)
    task_ci = task_bootstrap(per_task)
    correctness_delta = (arm_margin["semantic_mix"] > 0).astype(float) - (
        arm_margin["pooled"] > 0
    ).astype(float)
    parent_ci = parent_bootstrap(merged_test, correctness_delta)
    supported = [
        row for row in per_task if row["subset"] == "merged" and int(row["pairs"]) >= 10
    ]
    signs = Counter(
        "positive"
        if row["semantic_mix_minus_pooled"] > 0
        else "negative"
        if row["semantic_mix_minus_pooled"] < 0
        else "zero"
        for row in supported
    )
    merged_delta = (
        metrics["merged"]["semantic_mix"]["task_macro_accuracy"]
        - metrics["merged"]["pooled"]["task_macro_accuracy"]
    )
    draft_delta = (
        metrics["draft"]["semantic_mix"]["micro_accuracy"]
        - metrics["draft"]["pooled"]["micro_accuracy"]
    )
    improve_delta = (
        metrics["improve"]["semantic_mix"]["micro_accuracy"]
        - metrics["improve"]["pooled"]["micro_accuracy"]
    )
    positive_fraction = signs["positive"] / len(supported) if supported else 0.0
    gates = {
        "merged_task_macro_delta_ge_0_010": merged_delta >= 0.010,
        "task_bootstrap_ci_lower_gt_0": task_ci["ci95"][0] > 0,
        "supported_tasks_ge_15": len(supported) >= 15,
        "supported_task_positive_fraction_ge_0_60": positive_fraction >= 0.60,
        "draft_micro_delta_ge_minus_0_005": draft_delta >= -0.005,
        "improve_micro_delta_ge_minus_0_005": improve_delta >= -0.005,
    }
    return {
        "representation": {
            "train_only_endpoints": len(train_ids),
            "all_decision_endpoints": len(card_ids),
            "features": len(vectorizer.vocabulary_),
            "matrix_rows": matrix.shape[0],
            "matrix_columns": matrix.shape[1],
            "matrix_nnz": int(matrix.nnz),
            "code_prefix_chars": 20000,
            "vectorizer": {
                "analyzer": "char_wb",
                "ngram_range": [3, 5],
                "max_features": 30000,
                "min_df": 3,
                "sublinear_tf": True,
                "dtype": "float64",
            },
        },
        "heads": {
            "pooled_train_pairs": len(merged_train),
            "draft_train_pairs": len(draft_train),
            "improve_train_pairs": len(improve_train),
            "logistic": {"C": 0.5, "max_iter": 1500, "solver": "lbfgs", "random_state": 0},
            "iterations": {
                "pooled": int(pooled.n_iter_[0]),
                "draft": int(draft_head.n_iter_[0]),
                "improve": int(improve_head.n_iter_[0]),
            },
        },
        "metrics": metrics,
        "primary_inference": task_ci,
        "secondary_parent_inference": parent_ci,
        "supported_task_consistency": {
            "minimum_pairs": 10,
            "tasks": len(supported),
            "positive": signs["positive"],
            "zero": signs["zero"],
            "negative": signs["negative"],
            "positive_fraction": positive_fraction,
        },
        "effect_deltas": {
            "merged_task_macro": merged_delta,
            "merged_micro": metrics["merged"]["semantic_mix"]["micro_accuracy"]
            - metrics["merged"]["pooled"]["micro_accuracy"],
            "draft_micro": draft_delta,
            "improve_micro": improve_delta,
        },
        "gates": gates,
        "status": "DISCOVERY_UNLOCK_FUTURE_CONFIRMATION"
        if all(gates.values())
        else "DISCOVERY_NO_UNLOCK",
    }, per_task


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "subset",
        "task",
        "pairs",
        "pooled_accuracy",
        "specialist_accuracy",
        "semantic_mix_accuracy",
        "semantic_mix_minus_pooled",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.senior_commit != SENIOR_COMMIT:
        raise DiscoveryError("senior source commit mismatch")
    repo = Path(__file__).resolve().parent.parent
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if commit != args.source_commit:
        raise DiscoveryError("executing source commit mismatch")
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip():
        raise DiscoveryError("dirty scientific worktree")
    paths = {
        "cards": args.cards.resolve(strict=True),
        "merged": args.merged.resolve(strict=True),
        "draft": args.draft.resolve(strict=True),
        "improve": args.improve.resolve(strict=True),
    }
    for role, path in paths.items():
        require_input(path, role)
    merged, draft, improve = (read_pairs(paths[role]) for role in ("merged", "draft", "improve"))
    needed = {row[key] for row in [*merged, *draft, *improve] for key in ("better", "worse")}
    codes, runs, configs, card_inventory = load_cards(paths["cards"], needed)
    if card_inventory["run_groups"] != EXPECTED_COUNTS["card_run_groups"] or card_inventory["cards"] != EXPECTED_COUNTS["cards"]:
        raise DiscoveryError("fixed card inventory mismatch")
    integrity = verify_integrity(merged, draft, improve, runs, configs, card_inventory)
    result, per_task = analyze(codes, merged, draft, improve)
    result.update(
        {
            "protocol": PROTOCOL,
            "source_commit": commit,
            "senior_source_commit": SENIOR_COMMIT,
            "inputs": {
                role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
                for role in sorted(EXPECTED)
            },
            "card_inventory": card_inventory,
            "integrity": integrity,
            "scope": {
                "retrospective_test_previously_seen": True,
                "prospective_state_or_vault_read": False,
                "checkpoint_read": False,
                "api_calls": 0,
                "gpu_hours": 0,
                "base_llm_updates": 0,
                "features_use_code_only": True,
                "credential_shape_matches": 0,
            },
            "reproducibility": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "sklearn": sklearn.__version__,
                "source_sha256": sha256(Path(__file__).resolve()),
                "thread_env": {
                    key: os.environ.get(key)
                    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
                },
                "runtime_recorded_externally": True,
            },
        }
    )
    output = args.output
    if output.exists():
        raise DiscoveryError("refusing to overwrite output directory")
    output.mkdir(parents=True)
    write_csv(output / "per_task.csv", per_task)
    (output / "summary.json").write_bytes(canonical_json(result))
    manifest = {
        "per_task.csv": sha256(output / "per_task.csv"),
        "summary.json": sha256(output / "summary.json"),
    }
    (output / "artifact_manifest.json").write_bytes(canonical_json(manifest))
    return result


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--merged", required=True, type=Path)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--improve", required=True, type=Path)
    parser.add_argument("--senior-commit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        result = execute(arguments())
    except (DiscoveryError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DECISION_SEMANTIC_MIXTURE_ERROR: {error}")
        return 1
    print(
        "DECISION_SEMANTIC_MIXTURE_COMPLETE",
        f"status={result['status']}",
        f"delta={result['effect_deltas']['merged_task_macro']:.17g}",
        f"ci={result['primary_inference']['ci95']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
