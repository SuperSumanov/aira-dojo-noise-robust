#!/usr/bin/env python3
"""Train-only run-OOF discovery for Target-Graph Connected Augmentation (TGCA).

The four arms share the same endpoint universe, outer physical-run folds, code view,
TF-IDF vocabulary, solver, and evaluation rows.  They differ only in the training-edge
augmentation specified by ``tgca_protocol_v1.json``.  No frozen/test/held pair path is
accepted by this program.
"""

from __future__ import annotations

import argparse
import bisect
import collections
import csv
import hashlib
import itertools
import json
import math
import os
import platform
import random
import shutil
import subprocess
import time
import warnings
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


PROTOCOL = "tgca_v11_train_oof_discovery_v1"
ARMS = (
    "sibling_only",
    "sibling_reweight_control",
    "uniform_crossrun_control",
    "tgca",
)
MODEL_SEED = 887
EDGE_SEED = 20_260_814
BOOTSTRAP_SEED = 20_260_815
BOOTSTRAP_REPS = 10_000
OUTER_FOLDS = 5
GAP_UPPERS = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf)
EPSILON = 1e-12
SCORE_ATOL = 1e-10
TASK_SUPPORT_MIN_PAIRS = 20
EXPECTED = {
    "pairs": 4_263,
    "runs": 333,
    "tasks": 23,
    "parents": 2_293,
    "endpoints": 5_499,
}


class IntegrityError(RuntimeError):
    pass


class DisjointSet:
    def __init__(self, values: Iterable[str]):
        self.parent = {value: value for value in values}
        self.size = {value: 1 for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        while parent != self.parent[parent]:
            parent = self.parent[parent]
        while value != parent:
            next_value = self.parent[value]
            self.parent[value] = parent
            value = next_value
        return parent

    def union(self, left: str, right: str) -> bool:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return False
        if self.size[left_root] < self.size[right_root] or (
            self.size[left_root] == self.size[right_root] and left_root > right_root
        ):
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        self.size[left_root] += self.size[right_root]
        return True

    def component_sizes(self) -> list[int]:
        counts = collections.Counter(self.find(value) for value in self.parent)
        return sorted(counts.values(), reverse=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(f"append-only output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> str:
    if path.exists():
        raise FileExistsError(f"append-only output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    os.replace(temporary, path)
    return sha256(path)


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str] | None = None) -> str:
    if path.exists():
        raise FileExistsError(f"append-only output already exists: {path}")
    if not rows:
        raise IntegrityError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fieldnames = list(fields or rows[0].keys())
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)
    return sha256(path)


def reject_forbidden_path(path: Path, label: str) -> None:
    tokens = [token for token in ("frozen", "test", "held") if token in path.name.lower()]
    if tokens:
        raise IntegrityError(f"{label} path contains forbidden token(s): {tokens}")


def finite_float(value: Any, label: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError) as error:
        raise IntegrityError(f"non-numeric {label}: {value!r}") from error
    if not math.isfinite(converted):
        raise IntegrityError(f"non-finite {label}: {value!r}")
    return converted


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def code_view(code: str) -> str:
    if len(code) <= 20_000:
        return code
    return code[:5_000] + "\n# <FIXED_HEAD_TAIL_TRUNCATION>\n" + code[-15_000:]


def gap_bin(gap: float) -> int:
    if not math.isfinite(gap) or gap < 0:
        raise IntegrityError(f"invalid gap: {gap}")
    return bisect.bisect_right(GAP_UPPERS, gap)


def stable_key(*values: object) -> str:
    text = "\t".join(str(value) for value in values)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def orient_pair(
    first: str,
    second: str,
    grades: dict[str, float],
    lower_is_better: bool,
) -> tuple[str, str, float] | None:
    first_grade, second_grade = grades[first], grades[second]
    if first_grade == second_grade:
        return None
    first_wins = first_grade < second_grade if lower_is_better else first_grade > second_grade
    better, worse = (first, second) if first_wins else (second, first)
    return better, worse, round(abs(first_grade - second_grade), 6)


def load_rows_and_folds(
    pairs_path: Path,
    fold_path: Path,
    expected_pairs_sha: str,
    expected_fold_sha: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    reject_forbidden_path(pairs_path, "training pairs")
    reject_forbidden_path(fold_path, "fold manifest")
    if sha256(pairs_path) != expected_pairs_sha.lower():
        raise IntegrityError("training pair SHA mismatch")
    if sha256(fold_path) != expected_fold_sha.lower():
        raise IntegrityError("fold manifest SHA mismatch")
    pair_rows = [
        json.loads(line)
        for line in pairs_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    with fold_path.open(encoding="utf-8", newline="") as handle:
        fold_rows = list(csv.DictReader(handle))
    if len(pair_rows) != len(fold_rows):
        raise IntegrityError("pair/fold row count mismatch")
    rows: list[dict[str, Any]] = []
    endpoints: dict[str, dict[str, Any]] = {}
    run_folds: dict[str, int] = {}
    unordered: set[tuple[str, str]] = set()
    for index, (pair, fold_row) in enumerate(zip(pair_rows, fold_rows)):
        if pair.get("intask_split") != "train" or int(pair.get("budget", -1)) != 0:
            raise IntegrityError(f"non-train budget-zero pair at row {index}")
        if int(fold_row.get("row_index", -1)) != index:
            raise IntegrityError(f"non-contiguous fold row at {index}")
        identity = {
            "task": str(pair["task"]),
            "run": str(pair["run_id"]),
            "parent": str(pair["parent"]),
            "better": str(pair["better"]),
            "worse": str(pair["worse"]),
        }
        for key, value in identity.items():
            if str(fold_row.get(key)) != value:
                raise IntegrityError(f"pair/fold identity mismatch at {index}: {key}")
        fold = int(fold_row["fold"])
        if fold not in range(OUTER_FOLDS):
            raise IntegrityError(f"invalid fold at row {index}: {fold}")
        previous_fold = run_folds.setdefault(identity["run"], fold)
        if previous_fold != fold:
            raise IntegrityError(f"physical run spans outer folds: {identity['run']}")
        better, worse = identity["better"], identity["worse"]
        canonical = tuple(sorted((better, worse)))
        if better == worse or canonical in unordered:
            raise IntegrityError(f"duplicate/reverse/degenerate pair at row {index}")
        unordered.add(canonical)
        gap = finite_float(pair.get("gap_raw"), f"pair gap {index}")
        if gap <= 0:
            raise IntegrityError(f"non-positive pair gap at row {index}")
        row = {"row_index": index, **identity, "gap_raw": gap, "fold": fold}
        rows.append(row)
        for key in ("better", "worse"):
            card_id = identity[key]
            metadata = {
                "task": identity["task"],
                "run": identity["run"],
                "parent": identity["parent"],
                "fold": fold,
            }
            previous = endpoints.setdefault(card_id, metadata)
            if previous != metadata:
                raise IntegrityError(f"endpoint metadata inconsistency: {card_id}")
    audit = {
        "pairs": len(rows),
        "runs": len(run_folds),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({row["parent"] for row in rows}),
        "endpoints": len(endpoints),
        "fold_counts": dict(sorted(collections.Counter(row["fold"] for row in rows).items())),
        "score_columns_retained": 0,
        "run_fold_overlap": 0,
    }
    if any(audit[key] != value for key, value in EXPECTED.items()):
        raise IntegrityError(f"unexpected train support: {audit}")
    return rows, endpoints, audit


def load_cards(
    path: Path,
    endpoints: dict[str, dict[str, Any]],
    expected_sha: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    reject_forbidden_path(path, "source cards")
    wanted = set(endpoints)
    found: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256()
    corpus_rows = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            corpus_rows += 1
            card = json.loads(raw_line)
            card_id = str(card["id"])
            if card_id not in wanted:
                continue
            if card_id in found:
                raise IntegrityError(f"duplicate selected card: {card_id}")
            metadata = endpoints[card_id]
            code = str(card.get("code") or "")
            lineage = card.get("lineage") or {}
            if not code:
                raise IntegrityError(f"empty selected code: {card_id}")
            if task_name(card.get("task")) != metadata["task"]:
                raise IntegrityError(f"selected task mismatch: {card_id}")
            if str(card.get("run_id")) != metadata["run"]:
                raise IntegrityError(f"selected run mismatch: {card_id}")
            if str(lineage.get("parent_id")) != metadata["parent"]:
                raise IntegrityError(f"selected parent mismatch: {card_id}")
            grade = finite_float((card.get("label") or {}).get("graded"), f"grade {card_id}")
            found[card_id] = {
                **metadata,
                "code": code,
                "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                "grade": grade,
            }
    actual_sha = digest.hexdigest()
    if actual_sha != expected_sha.lower():
        raise IntegrityError(f"cards SHA mismatch: {actual_sha}")
    if set(found) != wanted:
        raise IntegrityError(f"selected card coverage mismatch: {len(found)} != {len(wanted)}")
    return found, {
        "cards_sha256": actual_sha,
        "corpus_rows_scanned": corpus_rows,
        "selected_endpoints": len(found),
        "retained_fields": ["id", "task", "run", "parent", "code", "code_sha256", "graded"],
        "post_execution_fields_retained": 0,
        "non_allowlisted_cards_retained": 0,
    }


def load_orientation(path: Path, expected_sha: str, tasks: set[str]) -> dict[str, bool]:
    reject_forbidden_path(path, "task orientation")
    if sha256(path) != expected_sha.lower():
        raise IntegrityError("task orientation SHA mismatch")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not tasks <= set(raw) or any(not isinstance(raw[task], bool) for task in tasks):
        raise IntegrityError("missing or invalid task orientation")
    return {task: bool(raw[task]) for task in tasks}


def validate_orientations(
    rows: Sequence[dict[str, Any]],
    cards: dict[str, dict[str, Any]],
    orientation: dict[str, bool],
) -> None:
    grades = {card_id: float(card["grade"]) for card_id, card in cards.items()}
    for row in rows:
        oriented = orient_pair(row["better"], row["worse"], grades, orientation[row["task"]])
        if oriented is None or oriented[:2] != (row["better"], row["worse"]):
            raise IntegrityError(f"sibling orientation mismatch: {row['row_index']}")
        if not math.isclose(oriented[2], row["gap_raw"], rel_tol=0.0, abs_tol=EPSILON):
            raise IntegrityError(f"sibling gap mismatch: {row['row_index']}")


def fold_isolation(
    fold: int,
    rows: Sequence[dict[str, Any]],
    cards: dict[str, dict[str, Any]],
) -> dict[str, int]:
    fit_rows = [row for row in rows if row["fold"] != fold]
    valid_rows = [row for row in rows if row["fold"] == fold]
    fit_runs = {row["run"] for row in fit_rows}
    valid_runs = {row["run"] for row in valid_rows}
    fit_ids = {row[key] for row in fit_rows for key in ("better", "worse")}
    valid_ids = {row[key] for row in valid_rows for key in ("better", "worse")}
    fit_codes = {cards[card_id]["code_sha256"] for card_id in fit_ids}
    valid_codes = {cards[card_id]["code_sha256"] for card_id in valid_ids}
    overlaps = {
        "run_overlap": len(fit_runs & valid_runs),
        "endpoint_overlap": len(fit_ids & valid_ids),
        "raw_code_sha_overlap": len(fit_codes & valid_codes),
    }
    if any(overlaps.values()):
        raise IntegrityError(f"outer-fold leakage at fold {fold}: {overlaps}")
    return {
        "fit_pairs": len(fit_rows),
        "valid_pairs": len(valid_rows),
        "fit_runs": len(fit_runs),
        "valid_runs": len(valid_runs),
        "fit_endpoints": len(fit_ids),
        "valid_endpoints": len(valid_ids),
        **overlaps,
    }


def crossrun_candidates(
    fit_ids: Sequence[str],
    cards: dict[str, dict[str, Any]],
    orientation: dict[str, bool],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    grouped: dict[str, list[str]] = collections.defaultdict(list)
    for card_id in fit_ids:
        grouped[str(cards[card_id]["task"])].append(card_id)
    grades = {card_id: float(cards[card_id]["grade"]) for card_id in fit_ids}
    candidates: list[dict[str, Any]] = []
    same_run = ties = 0
    for task in sorted(grouped):
        for first, second in itertools.combinations(sorted(grouped[task]), 2):
            if cards[first]["run"] == cards[second]["run"]:
                same_run += 1
                continue
            oriented = orient_pair(first, second, grades, orientation[task])
            if oriented is None:
                ties += 1
                continue
            better, worse, gap = oriented
            candidates.append(
                {
                    "task": task,
                    "better": better,
                    "worse": worse,
                    "gap_raw": gap,
                    "gap_bin": gap_bin(gap),
                    "left": min(first, second),
                    "right": max(first, second),
                }
            )
    return candidates, {
        "finite_crossrun_candidates": len(candidates),
        "same_run_pairs_excluded": same_run,
        "raw_grade_ties_excluded": ties,
    }


def select_augmentations(
    fold: int,
    base_edges: Sequence[dict[str, Any]],
    candidates: Sequence[dict[str, Any]],
    fit_ids: Sequence[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    base_by_task: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    target_by_cell: collections.Counter[tuple[str, int]] = collections.Counter()
    base_degree: collections.Counter[str] = collections.Counter()
    dsu = DisjointSet(fit_ids)
    for edge in base_edges:
        task = str(edge["task"])
        base_by_task[task].append(edge)
        target_by_cell[(task, gap_bin(float(edge["gap_raw"])))] += 1
        base_degree[str(edge["better"])] += 1
        base_degree[str(edge["worse"])] += 1
        dsu.union(str(edge["better"]), str(edge["worse"]))

    candidates_by_cell: dict[tuple[str, int], list[dict[str, Any]]] = collections.defaultdict(list)
    candidates_by_task: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for edge in candidates:
        candidates_by_cell[(str(edge["task"]), int(edge["gap_bin"]))].append(edge)
        candidates_by_task[str(edge["task"])].append(edge)

    tgca: list[dict[str, Any]] = []
    cell_audit: dict[str, dict[str, int]] = {}
    for task, bin_index in sorted(target_by_cell):
        target = int(target_by_cell[(task, bin_index)])
        pool = candidates_by_cell.get((task, bin_index), [])
        actual_target = min(target, len(pool))
        ordered = sorted(
            pool,
            key=lambda edge: (
                max(base_degree[edge["left"]], base_degree[edge["right"]]),
                base_degree[edge["left"]] + base_degree[edge["right"]],
                stable_key(EDGE_SEED, fold, "tgca", task, bin_index, edge["left"], edge["right"]),
            ),
        )
        selected_keys: set[tuple[str, str]] = set()
        bridge_count = 0
        for edge in ordered:
            if len(selected_keys) >= actual_target:
                break
            key = (str(edge["left"]), str(edge["right"]))
            if dsu.find(key[0]) != dsu.find(key[1]):
                selected_keys.add(key)
                dsu.union(*key)
                bridge_count += 1
                tgca.append(dict(edge))
        if len(selected_keys) < actual_target:
            for edge in ordered:
                if len(selected_keys) >= actual_target:
                    break
                key = (str(edge["left"]), str(edge["right"]))
                if key in selected_keys:
                    continue
                selected_keys.add(key)
                dsu.union(*key)
                tgca.append(dict(edge))
        if len(selected_keys) != actual_target:
            raise IntegrityError(f"TGCA cell selection count mismatch: {(task, bin_index)}")
        cell_audit[f"{task}|{bin_index}"] = {
            "sibling_target": target,
            "candidate_population": len(pool),
            "selected": actual_target,
            "bridges_at_selection": bridge_count,
        }

    tgca_by_task = collections.Counter(str(edge["task"]) for edge in tgca)
    reweight: list[dict[str, Any]] = []
    uniform: list[dict[str, Any]] = []
    for task in sorted(base_by_task):
        count = int(tgca_by_task[task])
        originals = sorted(
            base_by_task[task],
            key=lambda edge: stable_key(
                EDGE_SEED, fold, "reweight", task, edge["row_index"]
            ),
        )
        population = sorted(
            candidates_by_task[task],
            key=lambda edge: stable_key(
                EDGE_SEED, fold, "uniform", task, edge["left"], edge["right"]
            ),
        )
        if count > len(originals) or count > len(population):
            raise IntegrityError(f"control population too small for {task}: {count}")
        for edge in originals[:count]:
            duplicate = dict(edge)
            duplicate["gap_bin"] = gap_bin(float(edge["gap_raw"]))
            duplicate["left"] = min(str(edge["better"]), str(edge["worse"]))
            duplicate["right"] = max(str(edge["better"]), str(edge["worse"]))
            reweight.append(duplicate)
        uniform.extend(dict(edge) for edge in population[:count])

    selections = {
        "sibling_only": [],
        "sibling_reweight_control": reweight,
        "uniform_crossrun_control": uniform,
        "tgca": tgca,
    }
    for task, count in tgca_by_task.items():
        observed = {
            arm: sum(str(edge["task"]) == task for edge in selections[arm])
            for arm in ARMS[1:]
        }
        if any(value != count for value in observed.values()):
            raise IntegrityError(f"per-task control count mismatch for {task}: {observed}")
    if len(reweight) != len(uniform) or len(uniform) != len(tgca):
        raise IntegrityError("global control count mismatch")
    return selections, {
        "fold": fold,
        "base_edges": len(base_edges),
        "augmentation_rows": len(tgca),
        "augmentation_by_task": dict(sorted(tgca_by_task.items())),
        "tgca_cells": cell_audit,
        "counts_exact": True,
    }


def graph_components(nodes: Sequence[str], edges: Sequence[tuple[str, str]]) -> dict[str, Any]:
    dsu = DisjointSet(nodes)
    unique = {tuple(sorted((left, right))) for left, right in edges if left != right}
    for left, right in unique:
        dsu.union(left, right)
    sizes = dsu.component_sizes()
    return {
        "nodes": len(nodes),
        "unique_edges": len(unique),
        "components": len(sizes),
        "largest_component_nodes": sizes[0] if sizes else 0,
        "largest_component_share": sizes[0] / len(nodes) if nodes else 0.0,
        "unique_edge_list": sorted(unique),
    }


def normalized_algebraic_connectivity(
    nodes: Sequence[str], edges: Sequence[tuple[str, str]], components: int
) -> float:
    if len(nodes) < 2 or components != 1:
        return 0.0
    from scipy import sparse
    from scipy.sparse import csgraph
    from scipy.sparse.linalg import eigsh

    position = {node: index for index, node in enumerate(nodes)}
    unique = sorted({tuple(sorted(edge)) for edge in edges if edge[0] != edge[1]})
    row: list[int] = []
    col: list[int] = []
    for left, right in unique:
        row.extend((position[left], position[right]))
        col.extend((position[right], position[left]))
    adjacency = sparse.csr_matrix((np.ones(len(row)), (row, col)), shape=(len(nodes), len(nodes)))
    laplacian = csgraph.laplacian(adjacency, normed=True)
    if len(nodes) <= 64:
        values = np.linalg.eigvalsh(laplacian.toarray())[:2]
    else:
        initial = np.linspace(1.0, 2.0, len(nodes), dtype=np.float64)
        values = np.sort(eigsh(laplacian, k=2, which="SM", v0=initial, tol=1e-9)[0])
    result = float(max(0.0, values[1]))
    if not math.isfinite(result) or result > 2.0 + 1e-8:
        raise IntegrityError(f"invalid normalized algebraic connectivity: {result}")
    return result


def graph_statistics(
    fold: int,
    base_edges: Sequence[dict[str, Any]],
    selections: dict[str, list[dict[str, Any]]],
    fit_ids: Sequence[str],
    cards: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    nodes_by_task: dict[str, list[str]] = collections.defaultdict(list)
    base_by_task: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for card_id in fit_ids:
        nodes_by_task[str(cards[card_id]["task"])].append(card_id)
    for edge in base_edges:
        base_by_task[str(edge["task"])].append(edge)
    output: list[dict[str, Any]] = []
    for arm in ARMS:
        additions_by_task: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for edge in selections[arm]:
            additions_by_task[str(edge["task"])].append(edge)
        for task in sorted(nodes_by_task):
            nodes = sorted(nodes_by_task[task])
            base = base_by_task[task]
            additions = additions_by_task[task]
            graph_edges = [(str(edge["better"]), str(edge["worse"])) for edge in base]
            if arm != "sibling_reweight_control":
                graph_edges.extend(
                    (str(edge["better"]), str(edge["worse"])) for edge in additions
                )
            components = graph_components(nodes, graph_edges)
            gap_counts = collections.Counter(int(edge["gap_bin"]) for edge in additions)
            output.append(
                {
                    "fold": fold,
                    "task": task,
                    "arm": arm,
                    "nodes": components["nodes"],
                    "base_edges": len(base),
                    "augmentation_rows": len(additions),
                    "unique_edges": components["unique_edges"],
                    "components": components["components"],
                    "largest_component_nodes": components["largest_component_nodes"],
                    "largest_component_share": components["largest_component_share"],
                    "normalized_algebraic_connectivity": normalized_algebraic_connectivity(
                        nodes, components["unique_edge_list"], components["components"]
                    ),
                    "augmentation_gap_bins": json.dumps(dict(sorted(gap_counts.items()))),
                }
            )
    return output


def symmetric_design(differences: Any) -> tuple[Any, np.ndarray]:
    from scipy import sparse

    design = sparse.vstack([differences, -differences], format="csr")
    labels = np.concatenate(
        [np.ones(differences.shape[0], dtype=np.int8), np.zeros(differences.shape[0], dtype=np.int8)]
    )
    return design, labels


def fit_fold_models(
    fit_ids: Sequence[str],
    valid_ids: Sequence[str],
    cards: dict[str, dict[str, Any]],
    base_edges: Sequence[dict[str, Any]],
    selections: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    started = time.monotonic()
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        dtype=np.float64,
        max_features=30_000,
        min_df=3,
        ngram_range=(3, 5),
        sublinear_tf=True,
    )
    fit_matrix = vectorizer.fit_transform([code_view(str(cards[card_id]["code"])) for card_id in fit_ids])
    valid_matrix = vectorizer.transform([code_view(str(cards[card_id]["code"])) for card_id in valid_ids])
    position = {card_id: index for index, card_id in enumerate(fit_ids)}
    scores: dict[str, dict[str, float]] = {}
    diagnostics: dict[str, Any] = {}
    for arm in ARMS:
        training_edges = [*base_edges, *selections[arm]]
        better = np.asarray([position[str(edge["better"])] for edge in training_edges])
        worse = np.asarray([position[str(edge["worse"])] for edge in training_edges])
        differences = fit_matrix[better] - fit_matrix[worse]
        design, labels = symmetric_design(differences)
        arm_started = time.monotonic()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = LogisticRegression(
                C=0.5,
                fit_intercept=False,
                max_iter=2_000,
                random_state=MODEL_SEED,
                solver="liblinear",
                tol=1e-6,
            ).fit(design, labels)
        convergence = [
            str(item.message)
            for item in caught
            if issubclass(item.category, ConvergenceWarning)
        ]
        if convergence:
            raise IntegrityError(f"convergence warning for {arm}: {convergence}")
        values = np.asarray(valid_matrix @ model.coef_.reshape(-1), dtype=np.float64).reshape(-1)
        if not np.isfinite(values).all():
            raise IntegrityError(f"non-finite endpoint scores for {arm}")
        scores[arm] = dict(zip(valid_ids, map(float, values)))
        diagnostics[arm] = {
            "accepted": True,
            "training_edges": len(training_edges),
            "training_rows_symmetric": int(design.shape[0]),
            "iterations": int(model.n_iter_[0]),
            "coefficient_norm": float(np.linalg.norm(model.coef_)),
            "elapsed_s": time.monotonic() - arm_started,
        }
    diagnostics["shared_vectorizer"] = {
        "fit_endpoints": len(fit_ids),
        "valid_endpoints": len(valid_ids),
        "vocabulary": len(vectorizer.vocabulary_),
        "vocabulary_sha256": json_digest(
            sorted((term, int(index)) for term, index in vectorizer.vocabulary_.items())
        ),
        "idf_sha256": hashlib.sha256(np.asarray(vectorizer.idf_, dtype="<f8").tobytes()).hexdigest(),
        "truncated_fit_codes": sum(len(str(cards[card_id]["code"])) > 20_000 for card_id in fit_ids),
        "truncated_valid_codes": sum(len(str(cards[card_id]["code"])) > 20_000 for card_id in valid_ids),
        "elapsed_total_s": time.monotonic() - started,
    }
    return scores, diagnostics


def edge_manifest_rows(
    fold: int, selections: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for arm in ARMS[1:]:
        for index, edge in enumerate(selections[arm]):
            output.append(
                {
                    "fold": fold,
                    "arm": arm,
                    "edge_index": index,
                    "task": edge["task"],
                    "better": edge["better"],
                    "worse": edge["worse"],
                    "gap_raw": float(edge["gap_raw"]),
                    "gap_bin": int(edge["gap_bin"]),
                    "left": edge["left"],
                    "right": edge["right"],
                    "source_row_index": edge.get("row_index"),
                }
            )
    return output


def run_fold(
    fold: int,
    rows: Sequence[dict[str, Any]],
    cards: dict[str, dict[str, Any]],
    orientation: dict[str, bool],
    output_dir: Path,
    checkpoint_key: str,
) -> tuple[dict[str, dict[str, float]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    final = output_dir / "checkpoints" / f"fold_{fold}"
    if final.exists():
        summary = json.loads((final / "fold_summary.json").read_text(encoding="utf-8"))
        if summary.get("status") != "FOLD_COMPLETE" or summary.get("checkpoint_key") != checkpoint_key:
            raise IntegrityError(f"invalid existing fold checkpoint: {fold}")
        for name, digest in summary["output_sha256"].items():
            if sha256(final / name) != digest:
                raise IntegrityError(f"fold checkpoint SHA mismatch: {fold}/{name}")
        with np.load(final / "valid_scores.npz", allow_pickle=False) as payload:
            ids = [str(value) for value in payload["card_ids"].tolist()]
            scores = {
                arm: dict(zip(ids, map(float, np.asarray(payload[arm], dtype=np.float64))))
                for arm in ARMS
            }
        edge_rows = [
            json.loads(line)
            for line in (final / "selected_edges.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        with (final / "graph_stats.csv").open(encoding="utf-8", newline="") as handle:
            graph_rows = list(csv.DictReader(handle))
        return scores, summary, edge_rows, graph_rows

    fit_rows = [dict(row) for row in rows if int(row["fold"]) != fold]
    valid_rows = [dict(row) for row in rows if int(row["fold"]) == fold]
    isolation = fold_isolation(fold, rows, cards)
    fit_ids = sorted({row[key] for row in fit_rows for key in ("better", "worse")})
    valid_ids = sorted({row[key] for row in valid_rows for key in ("better", "worse")})
    candidates, candidate_audit = crossrun_candidates(fit_ids, cards, orientation)
    selections, selection_audit = select_augmentations(
        fold, fit_rows, candidates, fit_ids
    )
    graph_rows = graph_statistics(fold, fit_rows, selections, fit_ids, cards)
    scores, diagnostics = fit_fold_models(
        fit_ids, valid_ids, cards, fit_rows, selections
    )
    if any(set(scores[arm]) != set(valid_ids) for arm in ARMS):
        raise IntegrityError(f"valid score coverage mismatch at fold {fold}")
    edges = edge_manifest_rows(fold, selections)

    checkpoint_root = output_dir / "checkpoints"
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    for stale in checkpoint_root.glob(f".fold_{fold}.tmp.*"):
        if stale.resolve().parent != checkpoint_root.resolve() or not stale.is_dir():
            raise IntegrityError(f"unsafe stale checkpoint path: {stale}")
        shutil.rmtree(stale)
    temporary = checkpoint_root / f".fold_{fold}.tmp.{os.getpid()}"
    temporary.mkdir(parents=True)
    score_path = temporary / "valid_scores.npz"
    np.savez_compressed(
        score_path,
        card_ids=np.asarray(valid_ids),
        **{arm: np.asarray([scores[arm][card_id] for card_id in valid_ids]) for arm in ARMS},
    )
    edge_sha = write_jsonl(temporary / "selected_edges.jsonl", edges)
    graph_sha = write_csv(temporary / "graph_stats.csv", graph_rows)
    summary = {
        "status": "FOLD_COMPLETE",
        "protocol": PROTOCOL,
        "checkpoint_key": checkpoint_key,
        "fold": fold,
        "isolation": isolation,
        "candidate_audit": candidate_audit,
        "selection_audit": selection_audit,
        "diagnostics": diagnostics,
        "output_sha256": {
            "valid_scores.npz": sha256(score_path),
            "selected_edges.jsonl": edge_sha,
            "graph_stats.csv": graph_sha,
        },
    }
    atomic_json(temporary / "fold_summary.json", summary)
    os.replace(temporary, final)
    return scores, summary, edges, graph_rows


def tie_hit(margin: float) -> float:
    if margin > EPSILON:
        return 1.0
    if margin < -EPSILON:
        return 0.0
    return 0.5


def quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def cluster_summary(
    records: Sequence[dict[str, Any]], key: str, seed: int
) -> dict[str, Any]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for record in records:
        grouped[str(record[key])].append(float(record["value"]))
    means = {name: sum(values) / len(values) for name, values in sorted(grouped.items())}
    population = list(means.values())
    if not population:
        raise IntegrityError("empty cluster summary")
    rng = random.Random(seed)
    draws = [
        sum(population[rng.randrange(len(population))] for _ in population) / len(population)
        for _ in range(BOOTSTRAP_REPS)
    ]
    return {
        "clusters": len(population),
        "estimate": sum(population) / len(population),
        "ci95": [quantile(draws, 0.025), quantile(draws, 0.975)],
        "per_cluster": means,
        "repetitions": BOOTSTRAP_REPS,
        "seed": seed,
    }


def summarize_records(records: Sequence[dict[str, Any]], seed_offset: int) -> dict[str, Any]:
    values = [float(record["value"]) for record in records]
    return {
        "overall": sum(values) / len(values),
        "records": len(records),
        "run": cluster_summary(records, "run", BOOTSTRAP_SEED + seed_offset),
        "task": cluster_summary(records, "task", BOOTSTRAP_SEED + seed_offset + 1),
    }


def metric_records(
    rows: Sequence[dict[str, Any]], scores: dict[str, float], seed_offset: int
) -> dict[str, Any]:
    pair_records = [
        {
            "name": str(row["row_index"]),
            "run": row["run"],
            "task": row["task"],
            "value": tie_hit(scores[row["better"]] - scores[row["worse"]]),
        }
        for row in rows
    ]
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["parent"])].append(row)
    top1_records: list[dict[str, Any]] = []
    utility_records: list[dict[str, Any]] = []
    incomplete = 0
    for parent, parent_rows in sorted(grouped.items()):
        candidates = {row[key] for row in parent_rows for key in ("better", "worse")}
        denominator = sum(float(row["gap_raw"]) for row in parent_rows)
        if denominator <= 0:
            raise IntegrityError(f"non-positive utility denominator: {parent}")
        utility = sum(
            float(row["gap_raw"])
            * tie_hit(scores[row["better"]] - scores[row["worse"]])
            for row in parent_rows
        ) / denominator
        common = {
            "name": parent,
            "run": parent_rows[0]["run"],
            "task": parent_rows[0]["task"],
        }
        utility_records.append({**common, "value": utility})
        if len(parent_rows) != len(candidates) * (len(candidates) - 1) // 2:
            incomplete += 1
            continue
        losses = collections.Counter({candidate: 0 for candidate in candidates})
        for row in parent_rows:
            losses[row["worse"]] += 1
        true_top = {candidate for candidate, value in losses.items() if value == min(losses.values())}
        maximum = max(scores[candidate] for candidate in candidates)
        predicted = {
            candidate for candidate in candidates if abs(scores[candidate] - maximum) <= EPSILON
        }
        top1_records.append({**common, "value": len(predicted & true_top) / len(predicted)})
    return {
        "pair": summarize_records(pair_records, seed_offset),
        "top1": {
            **summarize_records(top1_records, seed_offset + 10),
            "complete_parents": len(top1_records),
            "incomplete_parents": incomplete,
        },
        "utility": {
            **summarize_records(utility_records, seed_offset + 20),
            "definition": "mean_parent(sum(gap_raw*hit)/sum(gap_raw))",
        },
        "_pair_records": pair_records,
        "_top1_records": top1_records,
        "_utility_records": utility_records,
    }


def paired_delta(
    left: Sequence[dict[str, Any]],
    right: Sequence[dict[str, Any]],
    seed_offset: int,
) -> dict[str, Any]:
    left_map = {str(record["name"]): record for record in left}
    right_map = {str(record["name"]): record for record in right}
    if set(left_map) != set(right_map):
        raise IntegrityError("paired metric support mismatch")
    records = []
    for name in sorted(left_map):
        if any(left_map[name][key] != right_map[name][key] for key in ("run", "task")):
            raise IntegrityError(f"paired cluster mismatch: {name}")
        records.append(
            {
                "name": name,
                "run": left_map[name]["run"],
                "task": left_map[name]["task"],
                "value": float(left_map[name]["value"]) - float(right_map[name]["value"]),
            }
        )
    return summarize_records(records, seed_offset)


def stripped(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if not key.startswith("_")}


def make_gates(
    metrics: dict[str, dict[str, Any]],
    comparisons: dict[str, dict[str, Any]],
    rows: Sequence[dict[str, Any]],
    integrity: dict[str, bool],
) -> dict[str, Any]:
    sibling = comparisons["tgca_minus_sibling_only"]
    reweight = comparisons["tgca_minus_sibling_reweight_control"]
    pair_counts = collections.Counter(str(row["task"]) for row in rows)
    supported = sorted(task for task, count in pair_counts.items() if count >= TASK_SUPPORT_MIN_PAIRS)
    utility_task_delta = sibling["utility"]["task"]["per_cluster"]
    supported_deltas = {task: float(utility_task_delta[task]) for task in supported}
    nonnegative = sum(value >= 0.0 for value in supported_deltas.values())
    dominant_share = max(pair_counts.values()) / len(rows)

    def positive_both(delta: dict[str, Any]) -> bool:
        return delta["run"]["ci95"][0] > 0.0 and delta["task"]["ci95"][0] > 0.0

    conditions = {
        "tgca_minus_sibling_utility_effect": (
            sibling["utility"]["overall"] >= 0.02
            and positive_both(sibling["utility"])
        ),
        "tgca_minus_reweight_utility_effect": (
            reweight["utility"]["overall"] >= 0.015
            and positive_both(reweight["utility"])
        ),
        "tgca_minus_sibling_top1_effect": (
            sibling["top1"]["overall"] >= 0.02
            and positive_both(sibling["top1"])
        ),
        "supported_tasks_ge_15": len(supported) >= 15,
        "dominant_task_share_le_025": dominant_share <= 0.25,
        "nonnegative_task_utility_share_ge_060": (
            nonnegative / len(supported) >= 0.60 if supported else False
        ),
        "integrity_all": all(integrity.values()),
    }
    return {
        "conditions": conditions,
        "all": all(conditions.values()),
        "task_support_min_pairs": TASK_SUPPORT_MIN_PAIRS,
        "supported_tasks": len(supported),
        "supported_task_names": supported,
        "dominant_task_share": dominant_share,
        "nonnegative_task_utility": nonnegative,
        "nonnegative_task_utility_share": nonnegative / len(supported) if supported else 0.0,
        "supported_task_utility_deltas": supported_deltas,
    }


def write_predictions(
    path: Path,
    rows: Sequence[dict[str, Any]],
    scores: dict[str, dict[str, float]],
) -> str:
    fields = ["row_index", "task", "run", "parent", "better", "worse", "gap_raw", "fold"]
    for arm in ARMS:
        fields.extend(
            [f"{arm}_better_score", f"{arm}_worse_score", f"{arm}_margin", f"{arm}_hit"]
        )
    emitted = []
    for row in rows:
        output = dict(row)
        for arm in ARMS:
            better_score = scores[arm][row["better"]]
            worse_score = scores[arm][row["worse"]]
            margin = better_score - worse_score
            output.update(
                {
                    f"{arm}_better_score": repr(better_score),
                    f"{arm}_worse_score": repr(worse_score),
                    f"{arm}_margin": repr(margin),
                    f"{arm}_hit": repr(tie_hit(margin)),
                }
            )
        emitted.append(output)
    return write_csv(path, emitted, fields)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--fold-oof", required=True, type=Path)
    parser.add_argument("--orientation", required=True, type=Path)
    parser.add_argument("--protocol-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-fold-oof-sha256", required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--wall-cap-s", required=True, type=float)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    started = time.monotonic()
    if args.wall_cap_s <= 0:
        raise IntegrityError("wall cap must be positive")
    for label, path in (
        ("training pairs", args.pairs),
        ("source cards", args.cards),
        ("fold manifest", args.fold_oof),
        ("task orientation", args.orientation),
    ):
        reject_forbidden_path(path, label)
    if sha256(args.protocol_json) != args.expect_protocol_sha256.lower():
        raise IntegrityError("protocol JSON SHA mismatch")
    protocol = json.loads(args.protocol_json.read_text(encoding="utf-8"))
    if protocol.get("protocol") != PROTOCOL or protocol.get("status") != "OUTCOME_BLIND_FROZEN":
        raise IntegrityError("protocol JSON status mismatch")
    if (args.output_dir / "summary.json").exists():
        raise FileExistsError("append-only output already finalized")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows, endpoint_metadata, row_audit = load_rows_and_folds(
        args.pairs,
        args.fold_oof,
        args.expect_pairs_sha256,
        args.expect_fold_oof_sha256,
    )
    cards, card_audit = load_cards(args.cards, endpoint_metadata, args.expect_cards_sha256)
    orientation = load_orientation(
        args.orientation,
        args.expect_orientation_sha256,
        {row["task"] for row in rows},
    )
    validate_orientations(rows, cards, orientation)
    commit = subprocess.check_output(
        ["git", "-C", str(args.repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    input_hashes = {
        "pairs": args.expect_pairs_sha256.lower(),
        "cards": args.expect_cards_sha256.lower(),
        "fold_oof": args.expect_fold_oof_sha256.lower(),
        "orientation": args.expect_orientation_sha256.lower(),
        "protocol": args.expect_protocol_sha256.lower(),
    }
    checkpoint_key = json_digest(
        {"protocol": PROTOCOL, "commit": commit, "inputs": input_hashes, "arms": ARMS}
    )

    all_scores: dict[str, dict[str, float]] = {arm: {} for arm in ARMS}
    fold_summaries = []
    all_edges: list[dict[str, Any]] = []
    all_graph_rows: list[dict[str, Any]] = []
    for fold in range(OUTER_FOLDS):
        if time.monotonic() - started >= args.wall_cap_s:
            raise TimeoutError(f"wall cap reached before fold {fold}")
        fold_scores, fold_summary, edges, graph_rows = run_fold(
            fold, rows, cards, orientation, args.output_dir, checkpoint_key
        )
        for arm in ARMS:
            overlap = set(all_scores[arm]) & set(fold_scores[arm])
            if overlap:
                raise IntegrityError(f"OOF endpoint duplicate for {arm}: {sorted(overlap)[:3]}")
            all_scores[arm].update(fold_scores[arm])
        fold_summaries.append(fold_summary)
        all_edges.extend(edges)
        all_graph_rows.extend(graph_rows)
        print(
            "FOLD_COMPLETE",
            fold,
            f"augment={fold_summary['selection_audit']['augmentation_rows']}",
            f"elapsed_s={time.monotonic() - started:.3f}",
            flush=True,
        )

    expected_ids = set(cards)
    if any(set(all_scores[arm]) != expected_ids for arm in ARMS):
        raise IntegrityError("OOF score coverage mismatch")
    predictions_sha = write_predictions(args.output_dir / "oof_predictions.csv", rows, all_scores)
    edges_sha = write_jsonl(args.output_dir / "selected_edges.jsonl", all_edges)
    graph_sha = write_csv(args.output_dir / "graph_stats.csv", all_graph_rows)
    fit_run_rows = []
    for fold_summary in fold_summaries:
        for arm in ARMS:
            diagnostic = fold_summary["diagnostics"][arm]
            fit_run_rows.append(
                {
                    "protocol": PROTOCOL,
                    "git_commit": commit,
                    "fold": fold_summary["fold"],
                    "arm": arm,
                    "model_seed": MODEL_SEED,
                    "edge_seed": EDGE_SEED,
                    "fit_pairs": fold_summary["isolation"]["fit_pairs"],
                    "valid_pairs": fold_summary["isolation"]["valid_pairs"],
                    "training_edges": diagnostic["training_edges"],
                    "training_rows_symmetric": diagnostic["training_rows_symmetric"],
                    "iterations": diagnostic["iterations"],
                    "coefficient_norm": diagnostic["coefficient_norm"],
                    "elapsed_s": diagnostic["elapsed_s"],
                    "accepted": diagnostic["accepted"],
                }
            )
    fit_runs_sha = write_csv(args.output_dir / "fit_runs.csv", fit_run_rows)

    raw_metrics = {
        arm: metric_records(rows, all_scores[arm], index * 100)
        for index, arm in enumerate(ARMS)
    }
    metrics = {arm: stripped(raw_metrics[arm]) for arm in ARMS}
    comparisons = {}
    for index, control in enumerate(ARMS[:-1]):
        comparisons[f"tgca_minus_{control}"] = {
            "pair": paired_delta(
                raw_metrics["tgca"]["_pair_records"],
                raw_metrics[control]["_pair_records"],
                1_000 + index * 100,
            ),
            "top1": paired_delta(
                raw_metrics["tgca"]["_top1_records"],
                raw_metrics[control]["_top1_records"],
                1_010 + index * 100,
            ),
            "utility": paired_delta(
                raw_metrics["tgca"]["_utility_records"],
                raw_metrics[control]["_utility_records"],
                1_020 + index * 100,
            ),
        }

    isolation = [summary["isolation"] for summary in fold_summaries]
    control_exact = all(summary["selection_audit"]["counts_exact"] for summary in fold_summaries)
    integrity = {
        "support_exact": all(row_audit[key] == value for key, value in EXPECTED.items()),
        "five_folds_complete": len(fold_summaries) == OUTER_FOLDS,
        "fit_valid_run_overlap_zero": all(item["run_overlap"] == 0 for item in isolation),
        "fit_valid_endpoint_overlap_zero": all(item["endpoint_overlap"] == 0 for item in isolation),
        "fit_valid_raw_code_overlap_zero": all(item["raw_code_sha_overlap"] == 0 for item in isolation),
        "control_counts_exact": control_exact,
        "all_models_converged": all(
            fold["diagnostics"][arm]["accepted"] for fold in fold_summaries for arm in ARMS
        ),
        "oof_score_coverage_exact": all(set(all_scores[arm]) == expected_ids for arm in ARMS),
        "frozen_read_false": True,
        "temporal_vault_read_false": True,
    }
    gates = make_gates(metrics, comparisons, rows, integrity)
    status = (
        "TGCA_DISCOVERY_INVALID"
        if not all(integrity.values())
        else "TGCA_DISCOVERY_UNLOCK"
        if gates["all"]
        else "TGCA_DISCOVERY_NO_UNLOCK"
    )
    per_task_rows = []
    for task in sorted({row["task"] for row in rows}):
        output: dict[str, Any] = {
            "task": task,
            "validation_pairs": sum(row["task"] == task for row in rows),
        }
        for arm in ARMS:
            output[f"{arm}_pair"] = raw_metrics[arm]["pair"]["task"]["per_cluster"][task]
            output[f"{arm}_top1"] = raw_metrics[arm]["top1"]["task"]["per_cluster"].get(task)
            output[f"{arm}_utility"] = raw_metrics[arm]["utility"]["task"]["per_cluster"][task]
        output["tgca_minus_sibling_utility"] = (
            output["tgca_utility"] - output["sibling_only_utility"]
        )
        per_task_rows.append(output)
    per_task_sha = write_csv(args.output_dir / "per_task.csv", per_task_rows)

    summary = {
        "status": status,
        "protocol": PROTOCOL,
        "git_commit": commit,
        "checkpoint_key": checkpoint_key,
        "inputs": input_hashes,
        "input_audits": {"rows": row_audit, "cards": card_audit},
        "folds": fold_summaries,
        "metrics": metrics,
        "comparisons": comparisons,
        "integrity": integrity,
        "gates": gates,
        "outputs": {
            "oof_predictions_sha256": predictions_sha,
            "selected_edges_sha256": edges_sha,
            "graph_stats_sha256": graph_sha,
            "fit_runs_sha256": fit_runs_sha,
            "per_task_sha256": per_task_sha,
        },
        "runtime": {
            "elapsed_s": time.monotonic() - started,
            "wall_cap_s": args.wall_cap_s,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "scikit_learn": __import__("sklearn").__version__,
        },
        "resources": {"gpu_count": 0, "api_calls": 0, "base_llm_updates": 0},
        "frozen_read": False,
        "temporal_vault_read": False,
    }
    atomic_json(args.output_dir / "summary.json", summary)
    print(
        status,
        f"utility_delta={comparisons['tgca_minus_sibling_only']['utility']['overall']:.12f}",
        f"top1_delta={comparisons['tgca_minus_sibling_only']['top1']['overall']:.12f}",
        f"elapsed_s={summary['runtime']['elapsed_s']:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
