"""Parent-closed component OOF audit of code versus lineage static signal."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier


PROTOCOL = "critic-static-source-parent-closed-component-oof-v2"
FOLD_SEED = 20260823
TASK_SEED = 20260823
PARENT_SEED = 20260824
FOLDS = 5
BOOTSTRAP_REPS = 20_000
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
}
EXPECTED_COUNTS = {
    "pairs": 5240,
    "tasks": 28,
    "original_components": 168,
    "cross_component_parents": 16,
    "supercomponents": 152,
    "merged_supercomponents": 16,
    "maximum_original_components_per_supercomponent": 2,
}
LEARNED = ("gbm_code", "gbm_lineage", "gbm_all")
MODELS = ("random_hash", *LEARNED, "orientation_oracle")
LINEAGE_FEATURES = ("depth", "n_sibs", "step")

IMPORT_RX = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)
MODEL_WORDS = (
    "lightgbm", "xgboost", "catboost", "randomforest", "logisticregression",
    "ridge", "svc", "torch", "transformers", "bert", "resnet", "efficientnet",
    "timm", "keras", "sklearn",
)
CV_WORDS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_WORDS = (
    "fit_transform(test", "fit(test", ".append(test", "concat([train, test",
    "pd.concat([train,test",
)


class AuditError(RuntimeError):
    """Raised when a frozen OOF contract is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def array_sha(values: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def verify_identity(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    require(path.stat().st_size == expected_bytes, f"{role} byte count mismatch")
    require(sha256_file(path) == expected_hash, f"{role} SHA-256 mismatch")


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        left, right = sorted((row["better"], row["worse"]))
        values = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise AuditError("invalid pair identity") from error
    require(all(isinstance(value, str) and value for value in values), "empty pair identity")
    require(left != right, "self pair")
    return values


def read_rows(path: Path, split: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank row at {path.name}:{line_number}")
            row = json.loads(line)
            require(isinstance(row, dict), "pair row is not an object")
            key = pair_key(row)
            require(key not in seen, f"duplicate unordered pair in {path.name}")
            seen.add(key)
            require(row.get("intask_split") == split, f"unexpected split in {path.name}")
            rows.append(row)
    return rows


def feature_dict(card: dict[str, Any]) -> dict[str, float]:
    code = card.get("code")
    lineage = card.get("lineage")
    require(isinstance(code, str) and isinstance(lineage, dict), "needed card lacks code/lineage")
    low = code.lower()
    imports = set(IMPORT_RX.findall(code))
    features = {
        "code_len": float(len(code)),
        "n_lines": float(code.count("\n")),
        "n_imports": float(len(imports)),
        "depth": float(lineage.get("depth") or 0),
        "step": float(lineage.get("step") or 0),
        "n_sibs": float(lineage.get("n_siblings") or 0),
        "n_cv": float(sum(low.count(word) for word in CV_WORDS)),
        "n_seed": float(low.count("seed") + low.count("random_state")),
        "n_ensemble": float(
            low.count("ensemble") + low.count("blend") + low.count("stack") + low.count("mean(")
        ),
        "n_earlystop": float(low.count("early_stop")),
        "n_hpsearch": float(
            low.count("optuna") + low.count("gridsearch")
            + low.count("param_grid") + low.count("hyperopt")
        ),
        "n_augment": float(low.count("augment") + low.count("transform")),
        "n_try": float(low.count("try:")),
        "n_print": float(low.count("print(")),
        "n_comment": float(code.count("#")),
        "n_fold_int": float(
            max([int(value) for value in re.findall(r"n_splits\s*=\s*(\d+)", code)] or [0])
        ),
        "n_epoch_int": float(
            max([int(value) for value in re.findall(r"epochs?\s*=\s*(\d+)", code)] or [0])
        ),
        "risk_leak": float(sum(low.count(word) for word in RISK_WORDS)),
        "has_gpu": float("cuda" in low),
    }
    for word in MODEL_WORDS:
        features["m_" + word] = float(word in low)
    require(len(features) == 34, "feature inventory is not 34")
    return features


FEATURE_NAMES = tuple(sorted(feature_dict({"code": "", "lineage": {}})))
CODE_FEATURES = tuple(name for name in FEATURE_NAMES if name not in LINEAGE_FEATURES)
FEATURE_GROUPS = {
    "gbm_code": CODE_FEATURES,
    "gbm_lineage": LINEAGE_FEATURES,
    "gbm_all": FEATURE_NAMES,
}


def load_cards(
    path: Path, needed: set[str]
) -> tuple[dict[str, np.ndarray], dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(grouped, dict), "cards root is not grouped")
    vectors: dict[str, np.ndarray] = {}
    runs: dict[str, str] = {}
    tasks: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen: set[str] = set()
    total = 0
    for run_id, cards in grouped.items():
        require(isinstance(run_id, str) and isinstance(cards, list), "invalid grouped-card entry")
        for card in cards:
            total += 1
            require(isinstance(card, dict) and isinstance(card.get("id"), str), "invalid card")
            card_id = card["id"]
            require(card_id not in seen, "duplicate card id")
            seen.add(card_id)
            if card_id not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            config = (
                task,
                card.get("client"),
                card.get("hardware"),
                card.get("time_limit"),
                card.get("execution_timeout"),
            )
            require(
                all(isinstance(value, str) and value for value in config[:3])
                and all(isinstance(value, int) for value in config[3:]),
                "needed card lacks provenance",
            )
            values = feature_dict(card)
            vector = np.asarray([values[name] for name in FEATURE_NAMES], dtype=np.float64)
            require(np.isfinite(vector).all(), "non-finite static feature")
            vectors[card_id] = vector
            runs[card_id] = run_id
            tasks[card_id] = task
            configs[card_id] = config
    require(set(vectors) == needed, "pair endpoint missing from cards")
    return vectors, runs, tasks, configs, {
        "cards": total,
        "run_groups": len(grouped),
        "needed_cards": len(needed),
    }


class DisjointSet:
    def __init__(self, values: set[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            next_value = self.parent[value]
            self.parent[value] = root
            value = next_value
        return root

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            smaller, larger = sorted((left_root, right_root))
            self.parent[larger] = smaller


def validate_and_close_components(
    rows: list[dict[str, Any]],
    runs: dict[str, str],
    tasks: dict[str, str],
    configs: dict[str, tuple[Any, ...]],
) -> tuple[dict[str, str], dict[str, Any]]:
    original_components: set[str] = set()
    component_tasks: dict[str, str] = {}
    component_splits: dict[str, str] = {}
    endpoint_components: dict[str, set[str]] = defaultdict(set)
    run_components: dict[str, set[str]] = defaultdict(set)
    parent_components: dict[tuple[str, str], set[str]] = defaultdict(set)
    keys: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = pair_key(row)
        require(key not in keys, "duplicate unordered pair across train/dev")
        keys.add(key)
        component = row.get("pair_component_id")
        require(
            row.get("outer_intask_split") == "train"
            and row.get("train_dev_protocol") == "pair-graph-component-train-dev-split-v1"
            and row.get("train_dev_seed") == 20260821
            and row.get("train_dev_target_numerator") == 1
            and row.get("train_dev_target_denominator") == 10
            and isinstance(component, str)
            and re.fullmatch(r"[0-9a-f]{64}", component) is not None,
            "component split receipt mismatch",
        )
        original_components.add(component)
        previous_task = component_tasks.setdefault(component, row["task"])
        require(previous_task == row["task"], "component spans tasks")
        previous_split = component_splits.setdefault(component, row["intask_split"])
        require(previous_split == row["intask_split"], "original component crosses train/dev")
        for endpoint in (row["better"], row["worse"]):
            require(tasks[endpoint] == row["task"], "pair/card task mismatch")
            endpoint_components[endpoint].add(component)
            run_components[runs[endpoint]].add(component)
        require(configs[row["better"]] == configs[row["worse"]], "pair violates exact config")
        parent_components[(row["task"], row["parent"])].add(component)
    require(len(rows) == EXPECTED_COUNTS["pairs"], "combined pair count mismatch")
    require(len({row["task"] for row in rows}) == EXPECTED_COUNTS["tasks"], "task count mismatch")
    require(len(original_components) == EXPECTED_COUNTS["original_components"], "component count mismatch")
    require(all(len(values) == 1 for values in endpoint_components.values()), "endpoint crosses component")
    require(all(len(values) == 1 for values in run_components.values()), "run crosses component")
    crossing_parents = {key: values for key, values in parent_components.items() if len(values) > 1}
    require(
        len(crossing_parents) == EXPECTED_COUNTS["cross_component_parents"],
        "cross-component parent count mismatch",
    )

    dsu = DisjointSet(original_components)
    for values in parent_components.values():
        ordered = sorted(values)
        for component in ordered[1:]:
            dsu.union(ordered[0], component)
    members_by_root: dict[str, list[str]] = defaultdict(list)
    for component in sorted(original_components):
        members_by_root[dsu.find(component)].append(component)
    super_by_component: dict[str, str] = {}
    for members in members_by_root.values():
        super_id = hashlib.sha256(compact(members).encode()).hexdigest()
        for component in members:
            super_by_component[component] = super_id
    require(len(members_by_root) == EXPECTED_COUNTS["supercomponents"], "supercomponent count mismatch")
    require(
        sum(len(members) > 1 for members in members_by_root.values())
        == EXPECTED_COUNTS["merged_supercomponents"],
        "merged supercomponent count mismatch",
    )
    require(
        max(map(len, members_by_root.values()))
        == EXPECTED_COUNTS["maximum_original_components_per_supercomponent"],
        "unexpected closure width",
    )

    super_by_row: dict[str, str] = {}
    super_tasks: dict[str, set[str]] = defaultdict(set)
    endpoint_super: dict[str, set[str]] = defaultdict(set)
    run_super: dict[str, set[str]] = defaultdict(set)
    parent_super: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        super_id = super_by_component[row["pair_component_id"]]
        super_by_row[compact(pair_key(row))] = super_id
        super_tasks[super_id].add(row["task"])
        parent_super[(row["task"], row["parent"])].add(super_id)
        for endpoint in (row["better"], row["worse"]):
            endpoint_super[endpoint].add(super_id)
            run_super[runs[endpoint]].add(super_id)
    require(all(len(values) == 1 for values in super_tasks.values()), "supercomponent spans tasks")
    require(all(len(values) == 1 for values in endpoint_super.values()), "endpoint crosses supercomponent")
    require(all(len(values) == 1 for values in run_super.values()), "run crosses supercomponent")
    require(all(len(values) == 1 for values in parent_super.values()), "parent closure failed")
    return super_by_row, {
        "pairs": len(rows),
        "tasks": len({row["task"] for row in rows}),
        "parents": len(parent_super),
        "endpoints": len(endpoint_super),
        "runs": len(run_super),
        "original_components": len(original_components),
        "cross_component_parents_before_closure": len(crossing_parents),
        "supercomponents": len(members_by_root),
        "merged_supercomponents": sum(len(members) > 1 for members in members_by_root.values()),
        "maximum_original_components_per_supercomponent": max(map(len, members_by_root.values())),
        "all_endpoint_run_parent_supercomponent_unique": True,
        "supercomponent_membership_sha256": hashlib.sha256(
            compact(sorted((super_by_component[key], key) for key in super_by_component)).encode()
        ).hexdigest(),
    }


def assign_folds(rows: list[dict[str, Any]], super_by_row: dict[str, str]) -> tuple[np.ndarray, dict[str, Any]]:
    row_groups: dict[str, list[int]] = defaultdict(list)
    task_by_super: dict[str, str] = {}
    for index, row in enumerate(rows):
        super_id = super_by_row[compact(pair_key(row))]
        row_groups[super_id].append(index)
        previous = task_by_super.setdefault(super_id, row["task"])
        require(previous == row["task"], "supercomponent task mismatch")
    ordered = sorted(row_groups, key=lambda item: (-len(row_groups[item]), task_by_super[item], item))
    task_loads: dict[str, list[int]] = defaultdict(lambda: [0] * FOLDS)
    total_loads = [0] * FOLDS
    fold_by_super: dict[str, int] = {}
    for super_id in ordered:
        task = task_by_super[super_id]
        offset = int(hashlib.sha256(f"{FOLD_SEED}|{task}".encode()).hexdigest(), 16) % FOLDS
        tie_rank = {fold: (fold - offset) % FOLDS for fold in range(FOLDS)}
        fold = min(
            range(FOLDS),
            key=lambda candidate: (
                task_loads[task][candidate], total_loads[candidate], tie_rank[candidate]
            ),
        )
        weight = len(row_groups[super_id])
        fold_by_super[super_id] = fold
        task_loads[task][fold] += weight
        total_loads[fold] += weight
    fold_of_row = np.asarray(
        [fold_by_super[super_by_row[compact(pair_key(row))]] for row in rows], dtype=np.int8
    )
    require(set(fold_of_row.tolist()) == set(range(FOLDS)), "empty OOF fold")
    return fold_of_row, {
        "algorithm": "parent_closed_greedy_task_then_global_balance_v2",
        "seed": FOLD_SEED,
        "folds": FOLDS,
        "pair_counts": [int(np.sum(fold_of_row == fold)) for fold in range(FOLDS)],
        "supercomponent_counts": [
            len({super_by_row[compact(pair_key(row))] for row, value in zip(rows, fold_of_row) if value == fold})
            for fold in range(FOLDS)
        ],
        "assignment_sha256": hashlib.sha256(
            compact(sorted(fold_by_super.items())).encode()
        ).hexdigest(),
    }


def fold_isolation(
    rows: list[dict[str, Any]], fold_of_row: np.ndarray, runs: dict[str, str], super_by_row: dict[str, str]
) -> list[dict[str, Any]]:
    receipts = []
    for fold in range(FOLDS):
        eval_rows = [row for row, value in zip(rows, fold_of_row) if value == fold]
        fit_rows = [row for row, value in zip(rows, fold_of_row) if value != fold]
        require(fit_rows and eval_rows, "empty fit/eval fold")
        receipt: dict[str, Any] = {"fold": fold, "fit_pairs": len(fit_rows), "eval_pairs": len(eval_rows)}
        for name, mapper in (
            ("pair", lambda row: pair_key(row)),
            ("endpoint", lambda row: frozenset((row["better"], row["worse"]))),
            ("run", lambda row: frozenset((runs[row["better"]], runs[row["worse"]]))),
            ("parent", lambda row: (row["task"], row["parent"])),
            ("original_component", lambda row: row["pair_component_id"]),
            ("supercomponent", lambda row: super_by_row[compact(pair_key(row))]),
        ):
            fit_values: set[Any] = set()
            eval_values: set[Any] = set()
            for row in fit_rows:
                value = mapper(row)
                fit_values.update(value if isinstance(value, frozenset) else (value,))
            for row in eval_rows:
                value = mapper(row)
                eval_values.update(value if isinstance(value, frozenset) else (value,))
            overlap = len(fit_values & eval_values)
            receipt[f"{name}_overlap"] = overlap
            require(overlap == 0, f"{name} crosses fold {fold}")
        receipt["fit_tasks"] = len({row["task"] for row in fit_rows})
        receipt["eval_tasks"] = len({row["task"] for row in eval_rows})
        receipts.append(receipt)
    return receipts


def difference_matrix(rows: list[dict[str, Any]], vectors: dict[str, np.ndarray]) -> np.ndarray:
    return np.vstack([vectors[row["better"]] - vectors[row["worse"]] for row in rows])


def new_gbm() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        loss="log_loss",
        max_iter=300,
        learning_rate=0.08,
        max_leaf_nodes=31,
        max_depth=None,
        min_samples_leaf=20,
        l2_regularization=0.0,
        early_stopping=False,
        random_state=7,
    )


def oof_margins(
    differences: np.ndarray, fold_of_row: np.ndarray
) -> tuple[dict[str, np.ndarray], dict[str, list[dict[str, Any]]], dict[str, float]]:
    positions = {name: index for index, name in enumerate(FEATURE_NAMES)}
    margins = {name: np.full(len(differences), np.nan, dtype=np.float64) for name in LEARNED}
    receipts: dict[str, list[dict[str, Any]]] = {name: [] for name in LEARNED}
    anti_symmetry = {name: 0.0 for name in LEARNED}
    for name in LEARNED:
        indices = np.asarray([positions[feature] for feature in FEATURE_GROUPS[name]], dtype=np.int64)
        values = differences[:, indices]
        for fold in range(FOLDS):
            fit_mask = fold_of_row != fold
            eval_mask = ~fit_mask
            fit_values = values[fit_mask]
            fit_x = np.vstack((fit_values, -fit_values))
            fit_y = np.concatenate(
                (np.ones(len(fit_values), dtype=np.int8), np.zeros(len(fit_values), dtype=np.int8))
            )
            model = new_gbm().fit(fit_x, fit_y)
            require(model.n_iter_ == 300, "GBM iteration mismatch")
            eval_values = values[eval_mask]
            forward = 0.5 * (
                model.decision_function(eval_values) - model.decision_function(-eval_values)
            )
            reverse = 0.5 * (
                model.decision_function(-eval_values) - model.decision_function(eval_values)
            )
            require(np.isfinite(forward).all() and np.isfinite(reverse).all(), "non-finite OOF margin")
            maximum = float(np.max(np.abs(forward + reverse)))
            require(maximum <= 1e-12, "OOF margin is not antisymmetric")
            anti_symmetry[name] = max(anti_symmetry[name], maximum)
            margins[name][eval_mask] = forward
            receipts[name].append({
                "fold": fold,
                "fit_pairs": int(np.sum(fit_mask)),
                "eval_pairs": int(np.sum(eval_mask)),
                "features": list(FEATURE_GROUPS[name]),
                "feature_count": len(indices),
                "n_iter": int(model.n_iter_),
                "fit_matrix_sha256": array_sha(fit_values),
                "eval_margin_sha256": array_sha(forward),
                "anti_symmetry_max_abs": maximum,
            })
        require(np.isfinite(margins[name]).all(), "missing OOF prediction")
    return margins, receipts, anti_symmetry


def correctness(margins: np.ndarray) -> np.ndarray:
    require(np.isfinite(margins).all(), "non-finite margin in metric")
    return np.where(margins > 0, 1.0, np.where(margins < 0, 0.0, 0.5))


def quantiles(values: np.ndarray) -> dict[str, float]:
    points = np.quantile(values, [0, .1, .25, .5, .75, .9, 1], method="linear")
    return {
        name: float(value)
        for name, value in zip(("q00", "q10", "q25", "q50", "q75", "q90", "q100"), points)
    }


def task_interval(rows: list[dict[str, Any]], values: np.ndarray) -> dict[str, Any]:
    tasks = sorted({row["task"] for row in rows})
    means = np.asarray([
        np.mean([value for row, value in zip(rows, values) if row["task"] == task])
        for task in tasks
    ], dtype=np.float64)
    rng = np.random.default_rng(TASK_SEED)
    sampled = rng.integers(0, len(tasks), size=(BOOTSTRAP_REPS, len(tasks)))
    estimates = np.mean(means[sampled], axis=1)
    low, high = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "point": float(np.mean(means)),
        "ci95": [float(low), float(high)],
        "clusters": len(tasks),
        "replicates": BOOTSTRAP_REPS,
        "seed": TASK_SEED,
    }


def parent_interval(rows: list[dict[str, Any]], values: np.ndarray) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, value in zip(rows, values):
        grouped[(row["task"], row["parent"])].append(float(value))
    keys = sorted(grouped)
    arrays = [np.asarray(grouped[key], dtype=np.float64) for key in keys]
    rng = np.random.default_rng(PARENT_SEED)
    estimates = np.empty(BOOTSTRAP_REPS, dtype=np.float64)
    for index in range(BOOTSTRAP_REPS):
        sampled = rng.integers(0, len(arrays), size=len(arrays))
        estimates[index] = sum(float(np.sum(arrays[item])) for item in sampled) / sum(
            len(arrays[item]) for item in sampled
        )
    low, high = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "point": float(np.mean(values)),
        "ci95": [float(low), float(high)],
        "clusters": len(keys),
        "replicates": BOOTSTRAP_REPS,
        "seed": PARENT_SEED,
    }


def model_metrics(rows: list[dict[str, Any]], margins: np.ndarray) -> dict[str, Any]:
    credit = correctness(margins)
    task_result = task_interval(rows, credit)
    return {
        "pairs": len(rows),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({(row["task"], row["parent"]) for row in rows}),
        "coverage": float(np.mean(np.isfinite(margins))),
        "ties": int(np.sum(margins == 0)),
        "micro_accuracy": float(np.mean(credit)),
        "task_macro_accuracy": task_result["point"],
        "task_clustered": task_result,
        "parent_clustered": parent_interval(rows, credit),
        "margin_quantiles": quantiles(margins),
    }


def paired_summary(rows: list[dict[str, Any]], delta: np.ndarray) -> dict[str, Any]:
    task_result = task_interval(rows, delta)
    parent_result = parent_interval(rows, delta)
    task_means = {
        task: float(np.mean([value for row, value in zip(rows, delta) if row["task"] == task]))
        for task in sorted({row["task"] for row in rows})
    }
    loto = {
        task: float(np.mean([value for other, value in task_means.items() if other != task]))
        for task in task_means
    }
    return {
        "pair_micro_delta": float(np.mean(delta)),
        "task_macro_delta": task_result["point"],
        "task_clustered": task_result,
        "parent_clustered": parent_result,
        "per_task_delta": task_means,
        "leave_one_task_out_task_macro_delta": loto,
        "minimum_leave_one_task_out_task_macro_delta": min(loto.values()),
    }


def analyze(
    cards_path: Path, train_path: Path, dev_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        verify_identity(path, role)
    rows = read_rows(train_path, "train") + read_rows(dev_path, "dev")
    rows.sort(key=pair_key)
    needed = {row[side] for row in rows for side in ("better", "worse")}
    vectors, runs, tasks, configs, card_inventory = load_cards(cards_path, needed)
    super_by_row, integrity = validate_and_close_components(rows, runs, tasks, configs)
    fold_of_row, fold_summary = assign_folds(rows, super_by_row)
    isolation = fold_isolation(rows, fold_of_row, runs, super_by_row)
    differences = difference_matrix(rows, vectors)
    learned_margins, model_receipts, anti_symmetry = oof_margins(differences, fold_of_row)

    random_margin = []
    for row in rows:
        left, right = sorted((row["better"], row["worse"]))
        selected = (left, right)[zlib.crc32((left + "|" + right).encode()) & 1]
        random_margin.append(1.0 if selected == row["better"] else -1.0)
    margins = {
        "random_hash": np.asarray(random_margin, dtype=np.float64),
        **learned_margins,
        "orientation_oracle": np.ones(len(rows), dtype=np.float64),
    }
    metrics = {name: model_metrics(rows, margins[name]) for name in MODELS}
    code_credit = correctness(margins["gbm_code"])
    lineage_delta = code_credit - correctness(margins["gbm_lineage"])
    all_delta = code_credit - correctness(margins["gbm_all"])
    paired = {
        "code_minus_lineage": paired_summary(rows, lineage_delta),
        "code_minus_all": paired_summary(rows, all_delta),
    }
    random_task_ci = metrics["random_hash"]["task_clustered"]["ci95"]
    random_parent_ci = metrics["random_hash"]["parent_clustered"]["ci95"]
    gates = {
        "code_task_ci_above_half": metrics["gbm_code"]["task_clustered"]["ci95"][0] > .5,
        "code_parent_ci_above_half": metrics["gbm_code"]["parent_clustered"]["ci95"][0] > .5,
        "code_lineage_task_ci_above_zero": paired["code_minus_lineage"]["task_clustered"]["ci95"][0] > 0,
        "code_lineage_parent_ci_above_zero": paired["code_minus_lineage"]["parent_clustered"]["ci95"][0] > 0,
        "code_all_task_noninferior_one_point": paired["code_minus_all"]["task_clustered"]["ci95"][0] >= -.01,
        "code_all_parent_noninferior_one_point": paired["code_minus_all"]["parent_clustered"]["ci95"][0] >= -.01,
        "code_lineage_all_loto_positive": paired["code_minus_lineage"]["minimum_leave_one_task_out_task_macro_delta"] > 0,
        "random_task_ci_contains_half": random_task_ci[0] <= .5 <= random_task_ci[1],
        "random_parent_ci_contains_half": random_parent_ci[0] <= .5 <= random_parent_ci[1],
        "learned_full_coverage": all(metrics[name]["coverage"] == 1.0 for name in LEARNED),
        "learned_no_ties": all(metrics[name]["ties"] == 0 for name in LEARNED),
        "all_antisymmetric": max(anti_symmetry.values()) <= 1e-12,
        "orientation_oracle_exact": metrics["orientation_oracle"]["micro_accuracy"] == 1.0,
        "all_fold_isolation_zero": all(
            value == 0
            for receipt in isolation
            for key, value in receipt.items()
            if key.endswith("_overlap")
        ),
    }
    producer_effect_gates_pass = all(gates.values())
    feature_matrix = np.vstack([vectors[card_id] for card_id in sorted(vectors)])
    summary = {
        "protocol": PROTOCOL,
        "status": (
            "STATIC_CODE_SOURCE_CANDIDATE_PENDING_INDEPENDENT_VERIFICATION"
            if producer_effect_gates_pass
            else "STATIC_SOURCE_AUDIT_VALID_NO_NARROW_POSITIVE"
        ),
        "evidence_level": "retrospective_outer_train_parent_closed_component_oof_robustness",
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in ("cards", "train", "dev")
        },
        "forbidden_inputs_opened": {
            "test": False,
            "tfidf": False,
            "semantic": False,
            "prospective_outcome": False,
        },
        "card_inventory": card_inventory,
        "integrity": integrity,
        "folds": {**fold_summary, "isolation": isolation},
        "features": {
            "all_names": list(FEATURE_NAMES),
            "groups": {name: list(values) for name, values in FEATURE_GROUPS.items()},
            "matrix_sha256": array_sha(feature_matrix),
            "endpoint_order_sha256": hashlib.sha256(compact(sorted(vectors)).encode()).hexdigest(),
            "forbidden_post_execution_fields_used": False,
        },
        "models": {
            "parameters": {
                "loss": "log_loss", "max_iter": 300, "learning_rate": .08,
                "max_leaf_nodes": 31, "max_depth": None, "min_samples_leaf": 20,
                "l2_regularization": 0.0, "early_stopping": False, "random_state": 7,
            },
            "fold_receipts": model_receipts,
            "anti_symmetry_max_abs": anti_symmetry,
        },
        "metrics": metrics,
        "paired_deltas": paired,
        "gates": gates,
        "producer_effect_gates_pass": producer_effect_gates_pass,
        "pending_independent_verification": True,
        "narrow_positive_claim_allowed": False,
        "bootstrap": {
            "replicates": BOOTSTRAP_REPS,
            "task_seed": TASK_SEED,
            "parent_seed": PARENT_SEED,
        },
    }

    pair_rows: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []
    parent_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    for name in MODELS:
        credit = correctness(margins[name])
        for index, (row, margin, correct, fold) in enumerate(zip(rows, margins[name], credit, fold_of_row)):
            pair_rows.append({
                "model": name,
                "index": index,
                "source_split": row["intask_split"],
                "task": row["task"],
                "parent": row["parent"],
                "better": row["better"],
                "worse": row["worse"],
                "pair_component_id": row["pair_component_id"],
                "parent_closed_supercomponent_id": super_by_row[compact(pair_key(row))],
                "fold": int(fold),
                "margin": float(margin),
                "correct_credit": float(correct),
                "tie": bool(margin == 0),
            })
        for task in sorted({row["task"] for row in rows}):
            mask = np.asarray([row["task"] == task for row in rows])
            task_rows.append({
                "model": name,
                "task": task,
                "pairs": int(np.sum(mask)),
                "accuracy": float(np.mean(credit[mask])),
            })
        for task, parent in sorted({(row["task"], row["parent"]) for row in rows}):
            mask = np.asarray([row["task"] == task and row["parent"] == parent for row in rows])
            parent_rows.append({
                "model": name,
                "task": task,
                "parent": parent,
                "pairs": int(np.sum(mask)),
                "accuracy": float(np.mean(credit[mask])),
            })
        for fold in range(FOLDS):
            mask = fold_of_row == fold
            fold_rows.append({
                "model": name,
                "fold": fold,
                "pairs": int(np.sum(mask)),
                "tasks": len({row["task"] for row, keep in zip(rows, mask) if keep}),
                "accuracy": float(np.mean(credit[mask])),
            })
    return summary, pair_rows, task_rows, parent_rows, fold_rows


def write_outputs(
    output: Path,
    summary: dict[str, Any],
    pair_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
    parent_rows: list[dict[str, Any]],
    fold_rows: list[dict[str, Any]],
) -> None:
    require(not output.exists(), "output directory already exists")
    json.dumps(summary, allow_nan=False)
    for row in (*pair_rows, *task_rows, *parent_rows, *fold_rows):
        json.dumps(row, allow_nan=False)
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(canonical(summary))
    with (output / "per_pair.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in pair_rows:
            handle.write(compact(row) + "\n")
    for name, rows, fields in (
        ("per_task.csv", task_rows, ("model", "task", "pairs", "accuracy")),
        ("per_parent.csv", parent_rows, ("model", "task", "parent", "pairs", "accuracy")),
        ("per_fold.csv", fold_rows, ("model", "fold", "pairs", "tasks", "accuracy")),
    ):
        with (output / name).open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    manifest = {
        name: sha256_file(output / name)
        for name in ("summary.json", "per_pair.jsonl", "per_task.csv", "per_parent.csv", "per_fold.csv")
    }
    (output / "artifact_manifest.json").write_bytes(canonical(manifest))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze(args.cards, args.train, args.dev)
    write_outputs(args.output, *result)
    print(json.dumps(result[0], indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
