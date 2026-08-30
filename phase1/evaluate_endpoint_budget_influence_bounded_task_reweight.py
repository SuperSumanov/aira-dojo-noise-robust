#!/usr/bin/env python3
"""Frozen historical screen for influence-bounded task-density reweighting."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Iterator


PROTOCOL = "endpoint-budget-influence-bounded-task-reweight-v1"
STATUS = "FROZEN_AFTER_STRUCTURAL_WEIGHT_DIAGNOSTICS_BEFORE_ANY_REWEIGHTED_MODEL_FIT_OR_PREDICTION"
RESULT = "endpoint-budget-influence-bounded-task-reweight-result-v1"
PRIVATE = "endpoint-budget-influence-bounded-task-reweight-private-pairs-v1"
CELL = "endpoint-budget-influence-bounded-task-reweight-cell-v1"
OLD_SELECTION_PUBLIC = "endpoint-budget-label-efficiency-selection-public-v1"
OLD_SELECTION_PRIVATE = "endpoint-budget-label-efficiency-selection-private-v1"
OLD_FIT_RESULT = "endpoint-budget-label-efficiency-fit-result-v1"
OLD_FIT_PRIVATE = "endpoint-budget-label-efficiency-private-pair-witness-v1"
OLD_FIREWALL_RECEIPT = "endpoint-budget-train-only-firewall-receipt-v1"
OLD_FIREWALL_TOPOLOGY = "endpoint-budget-train-only-topology-v1"
OLD_FIREWALL_LABELS = "endpoint-budget-train-only-labels-v1"
FOLD_SALT = "endpoint-label-efficiency-v1"
NEW_ARM = "influence_bounded_task_reweight"
OLD_YIELD = "yield_guarded_breadth"
OLD_UNIFORM = "exact_b_uniform_edge"


class ReweightError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReweightError(message)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha_bytes(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def object_file(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def private_mode(path: Path) -> bool:
    return os.name == "nt" or path.stat().st_mode & 0o077 == 0


def identity_sha(kind: str, value: str) -> str:
    return hashlib.sha256((kind + "\0" + value).encode("utf-8")).hexdigest()


def run_fold(run: str) -> int:
    digest = hashlib.sha256((FOLD_SALT + "\0" + run).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 5


@dataclass(frozen=True)
class TopologyRow:
    endpoints: tuple[str, str]
    parent: str
    task: str
    run: str

    @property
    def key(self) -> tuple[tuple[str, str], str, str, str]:
        return self.endpoints, self.parent, self.task, self.run


@dataclass(frozen=True)
class LabelRow:
    first: str
    second: str
    parent: str
    task: str
    run: str

    @property
    def endpoints(self) -> tuple[str, str]:
        return tuple(sorted((self.first, self.second)))

    @property
    def key(self) -> tuple[tuple[str, str], str, str, str]:
        return self.endpoints, self.parent, self.task, self.run


def pair_identity_sha(row: LabelRow | TopologyRow) -> str:
    return sha_bytes(
        {
            "endpoints": list(row.endpoints),
            "parent": row.parent,
            "task": row.task,
            "physical_run": row.run,
        }
    )


class JsonObjectStream:
    """Incrementally yield key/value pairs from one top-level JSON object."""

    def __init__(self, path: Path, chunk_size: int = 1 << 20) -> None:
        require(path.is_file() and not path.is_symlink(), f"unsafe streamed JSON: {path}")
        self.handle = path.open(encoding="utf-8")
        self.chunk_size = chunk_size
        self.buffer = ""
        self.position = 0
        self.eof = False
        self.decoder = json.JSONDecoder()

    def close(self) -> None:
        self.handle.close()

    def _fill(self) -> None:
        if self.position:
            self.buffer = self.buffer[self.position :]
            self.position = 0
        text = self.handle.read(self.chunk_size)
        if text:
            self.buffer += text
        else:
            self.eof = True

    def _skip_space(self) -> None:
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position].isspace():
                self.position += 1
            if self.position < len(self.buffer) or self.eof:
                return
            self._fill()

    def _peek(self) -> str:
        self._skip_space()
        require(self.position < len(self.buffer), "unexpected JSON EOF")
        return self.buffer[self.position]

    def _consume(self, token: str) -> None:
        require(self._peek() == token, f"expected JSON token {token!r}")
        self.position += 1

    def _decode(self) -> Any:
        while True:
            self._skip_space()
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError as error:
                require(not self.eof, f"invalid streamed JSON: {error}")
                self._fill()
                continue
            self.position = end
            return value

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        self._fill()
        self._consume("{")
        first = True
        while True:
            if self._peek() == "}":
                self.position += 1
                break
            if not first:
                self._consume(",")
            key = self._decode()
            require(isinstance(key, str) and key, "invalid top-level run identity")
            self._consume(":")
            yield key, self._decode()
            first = False
        self._skip_space()
        while not self.eof:
            self._fill()
            self._skip_space()
        require(self.position == len(self.buffer), "trailing JSON content")


def parse_fraction(text: str) -> float:
    require(isinstance(text, str), "fraction string")
    return float(Fraction(text))


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    observed = file_sha(path)
    require(observed == expected_sha, "protocol SHA mismatch")
    value = object_file(path)
    require(value.get("protocol") == PROTOCOL, "protocol name")
    require(value.get("status") == STATUS, "protocol status")
    known = value["known_before_freeze"]
    require(known["influence_bounded_weight_values_seen"] is False, "weights previously seen")
    require(known["reweighted_model_fit_prediction_or_metric_seen"] is False, "prior reweighted result")
    require(known["prospective_first960_target300_target522_values_seen"] is False, "prospective readout")
    require(value["population"]["senior_test_rows_forbidden"] is True, "senior test scope")
    require(value["population"]["prospective_rows_forbidden"] is True, "prospective scope")
    require(value["resources"]["gpu"] == value["resources"]["paid_api_calls"] == 0, "resource scope")
    require(value["resources"]["base_model_updates"] == 0, "base update scope")
    require(value["resources"]["critic_model_fits"] == 2, "fit count")
    return value, observed


def verify_bound_file(path: Path, expected: str) -> None:
    require(file_sha(path) == expected, f"immutable SHA mismatch: {path}")


def load_source(
    protocol: dict[str, Any], source_root: Path
) -> tuple[list[TopologyRow], list[LabelRow], dict[str, Any], dict[str, Any]]:
    immutable = protocol["immutable_inputs"]
    require(str(source_root) == immutable["historical_formal_root"], "historical root binding")
    require(source_root.is_dir() and not source_root.is_symlink(), "historical root safety")
    for relative, digest in immutable["historical_artifacts"].items():
        verify_bound_file(source_root / relative, digest)

    receipt_path = source_root / "firewall_a/receipt.json"
    topology_path = source_root / "firewall_a/topology.json"
    labels_path = source_root / "firewall_a/labels.json"
    selection_public_path = source_root / "selection_a.public.json"
    selection_private_path = source_root / "selection_a.private.json"
    old_summary_path = source_root / "fit/summary.json"
    old_pairs_path = source_root / "fit/private_pairs.json"
    for path in (receipt_path, topology_path, labels_path, selection_private_path, old_pairs_path):
        require(private_mode(path), f"private mode: {path}")

    receipt = object_file(receipt_path)
    topology = object_file(topology_path)
    labels = object_file(labels_path)
    selection_public = object_file(selection_public_path)
    selection_private = object_file(selection_private_path)
    old_summary = object_file(old_summary_path)
    old_pairs = object_file(old_pairs_path)
    old_sha = immutable["historical_smoke_protocol"]["sha256"]
    old_commit = immutable["historical_smoke_source_commit"]
    require(
        receipt.get("protocol") == OLD_FIREWALL_RECEIPT
        and receipt.get("status") == "TRAIN_ONLY_FIREWALL_COMPLETE",
        "firewall receipt",
    )
    require(topology.get("protocol") == OLD_FIREWALL_TOPOLOGY, "topology protocol")
    require(labels.get("protocol") == OLD_FIREWALL_LABELS, "labels protocol")
    require(
        receipt.get("protocol_sha256")
        == topology.get("protocol_sha256")
        == labels.get("protocol_sha256")
        == old_sha,
        "old protocol binding",
    )
    require(
        receipt.get("source_commit")
        == topology.get("source_commit")
        == labels.get("source_commit")
        == old_commit,
        "old commit binding",
    )
    require(file_sha(topology_path) == receipt["topology_sha256"], "receipt topology SHA")
    require(file_sha(labels_path) == receipt["labels_sha256"], "receipt labels SHA")
    require(topology.get("all_source_rows_train") is True, "topology train-only")
    require(topology.get("pair_orientation_emitted") is False, "topology orientation")
    require(labels.get("all_source_rows_train") is True, "labels train-only")
    require(labels.get("senior_test_rows_emitted") == 0, "senior test rows")

    topology_rows: list[TopologyRow] = []
    for item in topology["rows"]:
        require(
            set(item) == {"u", "v", "parent", "task", "physical_run", "source_split"}
            and item["u"] < item["v"]
            and item["source_split"] == "train",
            "topology row",
        )
        topology_rows.append(
            TopologyRow((item["u"], item["v"]), item["parent"], item["task"], item["physical_run"])
        )
    label_rows: list[LabelRow] = []
    for item in labels["rows"]:
        require(
            set(item)
            == {"better", "worse", "parent", "task", "physical_run", "source_split", "relation"}
            and item["source_split"] == "train"
            and item["relation"] == "verified_direct_sibling",
            "label row",
        )
        label_rows.append(
            LabelRow(item["better"], item["worse"], item["parent"], item["task"], item["physical_run"])
        )
    require(len(topology_rows) == len(label_rows) == 539, "source row count")
    require({row.key for row in topology_rows} == {row.key for row in label_rows}, "topology-label closure")

    require(selection_public.get("protocol") == OLD_SELECTION_PUBLIC, "selection public protocol")
    require(
        selection_public.get("classification") == "ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_SELECTION_READY",
        "selection status",
    )
    require(selection_private.get("protocol") == OLD_SELECTION_PRIVATE, "selection private protocol")
    require(
        selection_public.get("protocol_sha256")
        == selection_private.get("protocol_sha256")
        == old_sha,
        "selection protocol SHA",
    )
    require(file_sha(selection_private_path) == selection_public["private_selection_sha256"], "selection private SHA")
    require(
        sha_bytes(selection_private["arms"]) == selection_private["selection_fingerprint_sha256"],
        "selection fingerprint",
    )
    require(old_summary.get("protocol") == OLD_FIT_RESULT and old_summary.get("status") == "COMPLETE", "old summary")
    require(old_pairs.get("protocol") == OLD_FIT_PRIVATE, "old pair witness")
    require(
        old_summary.get("protocol_sha256") == old_pairs.get("protocol_sha256") == old_sha,
        "old fit protocol binding",
    )
    require(file_sha(old_pairs_path) == old_summary["private_pair_witness_sha256"], "old pair witness SHA")
    require(old_summary.get("source_commit") == old_pairs.get("source_commit") == old_commit, "old fit commit")
    return topology_rows, label_rows, selection_private, old_pairs


def selections_by_budget(selection: dict[str, Any]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    previous: set[str] = set()
    for entry in selection["arms"][OLD_YIELD]:
        budget = int(entry["budget"])
        identifiers = entry["endpoint_ids"]
        require(identifiers == sorted(set(identifiers)), "selection endpoint ordering")
        current = set(identifiers)
        require(len(current) == budget and previous <= current, "nested exact selection")
        result[budget] = current
        previous = current
    require({96, 192} <= set(result), "fit budgets absent")
    return result


def load_codes(cards_root: Path, protocol: dict[str, Any], needed: set[str]) -> dict[str, str]:
    card_path = cards_root / "cards.safe.json"
    security_path = cards_root / "security_scan.json"
    immutable = protocol["immutable_inputs"]
    require(str(card_path) == immutable["senior_safe_cards"]["remote_path"], "safe card path")
    require(str(security_path) == immutable["senior_security_receipt"]["remote_path"], "security path")
    verify_bound_file(card_path, immutable["senior_safe_cards"]["sha256"])
    verify_bound_file(security_path, immutable["senior_security_receipt"]["sha256"])
    security = object_file(security_path)
    require(
        security.get("status") == "CREDENTIAL_SCAN_AND_REDACTION_PASS"
        and security.get("remaining_credential_hits") == 0
        and security.get("private_key_markers") == 0
        and security.get("json_parsed_before_scan") is False,
        "security receipt",
    )
    require(security.get("safe_sha256") == immutable["senior_safe_cards"]["sha256"], "safe card receipt")
    codes: dict[str, str] = {}
    stream = JsonObjectStream(card_path)
    try:
        for _run, cards in stream:
            require(isinstance(cards, list), "card run payload")
            for card in cards:
                identifier = card.get("id")
                if identifier in needed:
                    code = card.get("code")
                    require(code is None or isinstance(code, str), "code schema")
                    codes[identifier] = (code or "")[:20000]
    finally:
        stream.close()
    require(set(codes) == needed, "missing endpoint code")
    return codes


def influence_bounded_weights(
    all_train: list[TopologyRow], induced: list[TopologyRow], ess_minimum: float, influence_cap: float
) -> tuple[list[float], dict[str, Any]]:
    require(induced and 0 < ess_minimum <= 1 and 0 < influence_cap <= 1, "weight inputs")
    available = Counter(row.task for row in all_train)
    selected = Counter(row.task for row in induced)
    require(set(selected) <= set(available), "selected task support")
    raw_by_task = {task: available[task] / count for task, count in selected.items()}
    raw_mean = sum(selected[task] * raw_by_task[task] for task in selected) / len(induced)
    direct = [raw_by_task[row.task] / raw_mean for row in induced]
    require(math.isclose(sum(direct), len(induced), rel_tol=1e-12, abs_tol=1e-12), "direct mean")
    centered_sum_squares = sum((value - 1.0) ** 2 for value in direct)
    if centered_sum_squares == 0:
        lambda_ess = 1.0
    else:
        lambda_ess = math.sqrt(
            max(0.0, (len(induced) / ess_minimum - len(induced)) / centered_sum_squares)
        )
    maximum_direct = max(direct)
    if maximum_direct <= 1.0:
        lambda_influence = 1.0
    else:
        lambda_influence = (influence_cap * len(induced) - 1.0) / (maximum_direct - 1.0)
    shrinkage = max(0.0, min(1.0, lambda_ess, lambda_influence))
    weights = [1.0 + shrinkage * (value - 1.0) for value in direct]
    total = sum(weights)
    ess = total * total / sum(value * value for value in weights)
    maximum_share = max(weights) / total

    supported_total = sum(available[task] for task in selected)
    observed_share = {task: selected[task] / len(induced) for task in selected}
    target_share = {task: available[task] / supported_total for task in selected}
    weighted_mass: Counter[str] = Counter()
    for row, weight in zip(induced, weights):
        weighted_mass[row.task] += weight
    weighted_share = {task: weighted_mass[task] / total for task in selected}
    before_l1 = sum(abs(observed_share[task] - target_share[task]) for task in selected)
    after_l1 = sum(abs(weighted_share[task] - target_share[task]) for task in selected)
    support_fraction = supported_total / sum(available.values())
    receipt = {
        "induced_pairs": len(induced),
        "selected_tasks": len(selected),
        "outer_train_tasks": len(available),
        "selected_task_support_availability_fraction": support_fraction,
        "direct_density_ratio": {
            "minimum": min(direct),
            "maximum": max(direct),
            "effective_sample_size_fraction": (
                len(induced) * len(induced) / sum(value * value for value in direct) / len(induced)
            ),
            "maximum_single_pair_weight_share": max(direct) / sum(direct),
        },
        "lambda_bounds": {
            "effective_sample_size": lambda_ess,
            "maximum_single_pair_influence": lambda_influence,
            "one": 1.0,
        },
        "selected_lambda": shrinkage,
        "final_weight": {
            "minimum": min(weights),
            "maximum": max(weights),
            "mean": total / len(weights),
            "effective_sample_size": ess,
            "effective_sample_size_fraction": ess / len(weights),
            "maximum_single_pair_weight_share": maximum_share,
        },
        "task_distribution_l1": {
            "unweighted_to_availability": before_l1,
            "weighted_to_availability": after_l1,
        },
        "raw_task_identities_emitted": False,
    }
    return weights, receipt


def pair_arrays(probabilities: list[float]) -> dict[str, list[float]]:
    result = {"correct": [], "log_loss": [], "brier": [], "probability": probabilities}
    for probability in probabilities:
        clipped = min(max(float(probability), 1e-15), 1 - 1e-15)
        result["correct"].append(float(probability > 0.5))
        result["log_loss"].append(-math.log(clipped))
        result["brier"].append((1.0 - probability) ** 2)
    return result


def fit_one(
    selected: set[str],
    train_topology: list[TopologyRow],
    train_labels: list[LabelRow],
    eval_labels: list[LabelRow],
    codes: dict[str, str],
    ess_minimum: float,
    influence_cap: float,
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    import numpy as np
    from scipy.sparse import vstack
    from scipy.special import expit
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    induced_topology = [
        row for row in train_topology if row.endpoints[0] in selected and row.endpoints[1] in selected
    ]
    induced_keys = {row.key for row in induced_topology}
    induced_labels = [row for row in train_labels if row.key in induced_keys]
    require(len(induced_topology) == len(induced_labels) == len(induced_keys), "induced closure")
    structural_weights, weight_receipt = influence_bounded_weights(
        train_topology, induced_topology, ess_minimum, influence_cap
    )
    weight_by_key = {row.key: weight for row, weight in zip(induced_topology, structural_weights)}
    weights = [weight_by_key[row.key] for row in induced_labels]
    require(len(weights) == len(induced_labels), "label weight closure")

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=30000,
        min_df=3,
        sublinear_tf=True,
    )
    fit_started = time.perf_counter()
    train_ids = sorted(selected)
    vectorizer.fit([codes[item] for item in train_ids])
    train_matrix = vectorizer.transform([codes[item] for item in train_ids])
    train_position = {item: index for index, item in enumerate(train_ids)}
    positive = vstack(
        [
            train_matrix[train_position[row.first]] - train_matrix[train_position[row.second]]
            for row in induced_labels
        ],
        format="csr",
    )
    features = vstack([positive, -positive], format="csr")
    labels = np.concatenate((np.ones(len(induced_labels), dtype=int), np.zeros(len(induced_labels), dtype=int)))
    doubled_weights = np.concatenate((np.asarray(weights, dtype=float), np.asarray(weights, dtype=float)))
    model = LogisticRegression(
        C=0.5,
        max_iter=1500,
        solver="lbfgs",
        random_state=0,
    ).fit(features, labels, sample_weight=doubled_weights)
    fit_seconds = time.perf_counter() - fit_started

    query_started = time.perf_counter()
    eval_ids = sorted({item for row in eval_labels for item in (row.first, row.second)})
    eval_matrix = vectorizer.transform([codes[item] for item in eval_ids])
    eval_position = {item: index for index, item in enumerate(eval_ids)}
    differences = vstack(
        [
            eval_matrix[eval_position[row.first]] - eval_matrix[eval_position[row.second]]
            for row in eval_labels
        ],
        format="csr",
    )
    probabilities = expit(model.decision_function(differences)).tolist()
    query_seconds = time.perf_counter() - query_started
    arrays = pair_arrays(probabilities)
    metrics = {
        "selected_endpoints": len(selected),
        "induced_unique_train_pairs": len(induced_labels),
        "outer_eval_pairs": len(eval_labels),
        "outer_eval_tasks": len({row.task for row in eval_labels}),
        "pairwise_accuracy": sum(arrays["correct"]) / len(eval_labels),
        "log_loss": sum(arrays["log_loss"]) / len(eval_labels),
        "brier_score": sum(arrays["brier"]) / len(eval_labels),
        "fit_seconds": fit_seconds,
        "query_seconds": query_seconds,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "model_iterations": int(model.n_iter_[0]),
        "weight_receipt": weight_receipt,
    }
    return metrics, arrays


def old_arrays(old_pairs: dict[str, Any], eval_rows: list[LabelRow]) -> dict[tuple[str, int], dict[str, list[float]]]:
    wanted = {(arm, budget) for arm in (OLD_UNIFORM, OLD_YIELD) for budget in (96, 192)}
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in old_pairs["rows"]:
        key = (row["arm"], int(row["endpoint_budget"]))
        if key in wanted:
            grouped[key].append(row)
    require(set(grouped) == wanted, "old baseline cells")
    result = {}
    for key, rows in grouped.items():
        rows.sort(key=lambda row: int(row["pair_index"]))
        require([row["pair_index"] for row in rows] == list(range(len(eval_rows))), "old pair order")
        for witness, source in zip(rows, eval_rows):
            require(witness["pair_identity_sha256"] == pair_identity_sha(source), "old pair identity")
            require(witness["task_sha256"] == identity_sha("task", source.task), "old task identity")
            require(witness["physical_run_sha256"] == identity_sha("physical_run", source.run), "old run identity")
        probabilities = [float(row["probability_first_better"]) for row in rows]
        require(all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities), "old probability")
        result[key] = pair_arrays(probabilities)
    return result


def bootstrap_cluster(values: list[float], clusters: list[str], repetitions: int, seed: int) -> dict[str, Any]:
    import numpy as np

    require(len(values) == len(clusters) and values, "bootstrap inputs")
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, cluster in zip(values, clusters):
        grouped[cluster].append(float(value))
    keys = sorted(grouped)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(repetitions):
        sampled = rng.choice(len(keys), size=len(keys), replace=True)
        combined = [value for index in sampled for value in grouped[keys[int(index)]]]
        draws.append(float(np.mean(combined)))
    return {
        "point": float(np.mean(values)),
        "lo": float(np.quantile(draws, 0.025)),
        "hi": float(np.quantile(draws, 0.975)),
        "clusters": len(keys),
        "repetitions": repetitions,
    }


def bootstrap_task_macro(values: list[float], tasks: list[str], repetitions: int, seed: int) -> dict[str, Any]:
    import numpy as np

    grouped: dict[str, list[float]] = defaultdict(list)
    for value, task in zip(values, tasks):
        grouped[task].append(float(value))
    keys = sorted(grouped)
    means = [float(np.mean(grouped[key])) for key in keys]
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(repetitions):
        sampled = rng.choice(len(means), size=len(means), replace=True)
        draws.append(float(np.mean([means[int(index)] for index in sampled])))
    return {
        "point": float(np.mean(means)),
        "lo": float(np.quantile(draws, 0.025)),
        "hi": float(np.quantile(draws, 0.975)),
        "tasks": len(keys),
        "repetitions": repetitions,
    }


def task_macro(values: list[float], tasks: list[str]) -> float:
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, task in zip(values, tasks):
        grouped[task].append(value)
    return sum(sum(rows) / len(rows) for rows in grouped.values()) / len(grouped)


def compare_arrays(
    new: dict[str, list[float]], old: dict[str, list[float]], tasks: list[str], runs: list[str], repetitions: int, seed: int
) -> dict[str, Any]:
    deltas = {
        key: [new_value - old_value for new_value, old_value in zip(new[key], old[key])]
        for key in ("correct", "log_loss", "brier")
    }
    task_delta: dict[str, list[float]] = defaultdict(list)
    for value, task in zip(deltas["correct"], tasks):
        task_delta[task].append(value)
    task_means = {task: sum(values) / len(values) for task, values in task_delta.items()}
    signs = {
        "positive": sum(value > 0 for value in task_means.values()),
        "negative": sum(value < 0 for value in task_means.values()),
        "equal": sum(value == 0 for value in task_means.values()),
    }
    task_counts = Counter(tasks)
    dominant_count = max(task_counts.values())
    dominant = min(task for task, count in task_counts.items() if count == dominant_count)
    keep = [index for index, task in enumerate(tasks) if task != dominant]
    return {
        "pair_micro": {
            "pairwise_accuracy": sum(deltas["correct"]) / len(tasks),
            "log_loss": sum(deltas["log_loss"]) / len(tasks),
            "brier_score": sum(deltas["brier"]) / len(tasks),
        },
        "task_macro_accuracy": task_macro(deltas["correct"], tasks),
        "task_signs": signs,
        "drop_dominant_task_pair_micro_accuracy": sum(deltas["correct"][index] for index in keep) / len(keep),
        "task_clustered_pair_micro_accuracy_bootstrap": bootstrap_cluster(
            deltas["correct"], tasks, repetitions, seed
        ),
        "run_clustered_pair_micro_accuracy_bootstrap": bootstrap_cluster(
            deltas["correct"], runs, repetitions, seed + 1000
        ),
        "task_macro_accuracy_bootstrap": bootstrap_task_macro(
            deltas["correct"], tasks, repetitions, seed + 2000
        ),
    }


def write_json_exclusive(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not path.exists() and not path.is_symlink(), f"output exists: {path}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(canonical_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def write_checkpoint_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = path.parent / ".staging"
    staging.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=staging)
    temporary = Path(name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    protocol, protocol_sha = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    old_protocol_path = args.old_protocol.resolve()
    require(str(old_protocol_path).endswith(protocol["immutable_inputs"]["historical_smoke_protocol"]["path"]), "old protocol path")
    verify_bound_file(old_protocol_path, protocol["immutable_inputs"]["historical_smoke_protocol"]["sha256"])
    topology, labels, selection, old_pairs = load_source(protocol, args.source_root.resolve())
    train_topology = [row for row in topology if run_fold(row.run) != 0]
    eval_topology = [row for row in topology if run_fold(row.run) == 0]
    train_labels = [row for row in labels if run_fold(row.run) != 0]
    eval_labels = [row for row in labels if run_fold(row.run) == 0]
    require({row.key for row in train_topology} == {row.key for row in train_labels}, "train closure")
    require({row.key for row in eval_topology} == {row.key for row in eval_labels}, "eval closure")
    require(len(train_labels) == 401 and len(eval_labels) == 138, "fold sizes")
    train_endpoints = {item for row in train_topology for item in row.endpoints}
    eval_endpoints = {item for row in eval_topology for item in row.endpoints}
    train_runs = {row.run for row in train_topology}
    eval_runs_raw = {row.run for row in eval_topology}
    train_parents = {row.parent for row in train_topology}
    eval_parents = {row.parent for row in eval_topology}
    require(not (train_endpoints & eval_endpoints), "endpoint overlap")
    require(not (train_runs & eval_runs_raw), "run overlap")
    require(not (train_parents & eval_parents), "parent overlap")

    selections = selections_by_budget(selection)
    needed = set(eval_endpoints)
    for budget in (96, 192):
        needed.update(selections[budget])
    codes = load_codes(args.cards_root.resolve(), protocol, needed)
    baselines = old_arrays(old_pairs, eval_labels)
    tasks = [identity_sha("task", row.task) for row in eval_labels]
    runs = [identity_sha("physical_run", row.run) for row in eval_labels]
    ess_minimum = parse_fraction(protocol["model"]["sample_weight"]["effective_sample_size_fraction_minimum"])
    influence_cap = parse_fraction(protocol["model"]["sample_weight"]["maximum_single_pair_weight_share"])
    support_minimum = parse_fraction(
        protocol["structural_gates_before_model_fit"]["minimum_selected_task_support_availability_fraction"]
    )

    checkpoint_root = args.checkpoint_dir.resolve()
    require(not checkpoint_root.is_symlink(), "checkpoint symlink")
    checkpoint_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(private_mode(checkpoint_root), "checkpoint mode")
    expected_names = {f"{NEW_ARM}__{budget}.json" for budget in (96, 192)}
    observed_names = {path.name for path in checkpoint_root.iterdir() if path.name != ".staging"}
    require(observed_names <= expected_names, "unexpected checkpoint")

    arrays: dict[int, dict[str, list[float]]] = {}
    rows_out: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    for budget in (96, 192):
        path = checkpoint_root / f"{NEW_ARM}__{budget}.json"
        if path.exists():
            require(private_mode(path), "checkpoint file mode")
            cell = object_file(path)
            require(
                cell.get("protocol") == CELL
                and cell.get("source_commit") == args.source_commit
                and cell.get("protocol_sha256") == protocol_sha
                and cell.get("endpoint_budget") == budget
                and cell.get("arm") == NEW_ARM,
                "checkpoint binding",
            )
            metrics = cell["metrics"]
            pair_rows = cell["pair_rows"]
            probabilities = [float(row["probability_first_better"]) for row in pair_rows]
            current_arrays = pair_arrays(probabilities)
        else:
            metrics, current_arrays = fit_one(
                selections[budget],
                train_topology,
                train_labels,
                eval_labels,
                codes,
                ess_minimum,
                influence_cap,
            )
            receipt = metrics["weight_receipt"]
            require(
                receipt["selected_task_support_availability_fraction"] + 1e-12 >= support_minimum,
                "selected task support",
            )
            require(
                receipt["final_weight"]["effective_sample_size_fraction"] + 1e-12 >= ess_minimum,
                "ESS gate",
            )
            require(
                receipt["final_weight"]["maximum_single_pair_weight_share"] <= influence_cap + 1e-12,
                "influence gate",
            )
            require(
                receipt["task_distribution_l1"]["weighted_to_availability"]
                < receipt["task_distribution_l1"]["unweighted_to_availability"],
                "task L1 gate",
            )
            pair_rows = []
            for index, (row, probability) in enumerate(zip(eval_labels, current_arrays["probability"])):
                pair_rows.append(
                    {
                        "arm": NEW_ARM,
                        "endpoint_budget": budget,
                        "pair_index": index,
                        "pair_identity_sha256": pair_identity_sha(row),
                        "task_sha256": tasks[index],
                        "physical_run_sha256": runs[index],
                        "probability_first_better": probability,
                    }
                )
            cell = {
                "protocol": CELL,
                "protocol_sha256": protocol_sha,
                "source_commit": args.source_commit,
                "arm": NEW_ARM,
                "endpoint_budget": budget,
                "metrics": metrics,
                "pair_rows": pair_rows,
                "raw_identities_emitted": False,
            }
            write_checkpoint_atomic(path, cell)
        require(len(pair_rows) == len(eval_labels), "pair row count")
        for index, (witness, source) in enumerate(zip(pair_rows, eval_labels)):
            require(
                witness["pair_index"] == index
                and witness["pair_identity_sha256"] == pair_identity_sha(source)
                and witness["task_sha256"] == tasks[index]
                and witness["physical_run_sha256"] == runs[index],
                "new pair binding",
            )
        recomputed = {
            "pairwise_accuracy": sum(current_arrays["correct"]) / len(eval_labels),
            "log_loss": sum(current_arrays["log_loss"]) / len(eval_labels),
            "brier_score": sum(current_arrays["brier"]) / len(eval_labels),
        }
        require(
            all(math.isclose(float(metrics[key]), value, rel_tol=1e-12, abs_tol=1e-12) for key, value in recomputed.items()),
            "new aggregate metrics",
        )
        arrays[budget] = current_arrays
        private_rows.extend(pair_rows)
        rows_out.append(
            {
                "protocol": RESULT,
                "source_commit": args.source_commit,
                "protocol_sha256": protocol_sha,
                "outer_eval_fold": 0,
                "arm": NEW_ARM,
                "endpoint_budget": budget,
                "selected_endpoints": metrics["selected_endpoints"],
                "induced_unique_train_pairs": metrics["induced_unique_train_pairs"],
                "outer_eval_pairs": metrics["outer_eval_pairs"],
                "outer_eval_tasks": metrics["outer_eval_tasks"],
                "pairwise_accuracy": metrics["pairwise_accuracy"],
                "task_macro_accuracy": task_macro(current_arrays["correct"], tasks),
                "log_loss": metrics["log_loss"],
                "brier_score": metrics["brier_score"],
                "fit_seconds": metrics["fit_seconds"],
                "query_seconds": metrics["query_seconds"],
                "vocabulary_size": metrics["vocabulary_size"],
                "model_iterations": metrics["model_iterations"],
                "weight_lambda": metrics["weight_receipt"]["selected_lambda"],
                "weight_effective_sample_size_fraction": metrics["weight_receipt"]["final_weight"][
                    "effective_sample_size_fraction"
                ],
                "maximum_single_pair_weight_share": metrics["weight_receipt"]["final_weight"][
                    "maximum_single_pair_weight_share"
                ],
                "task_distribution_l1_before": metrics["weight_receipt"]["task_distribution_l1"][
                    "unweighted_to_availability"
                ],
                "task_distribution_l1_after": metrics["weight_receipt"]["task_distribution_l1"][
                    "weighted_to_availability"
                ],
                "gpu": 0,
                "api_calls": 0,
                "base_model_updates": 0,
            }
        )

    repetitions = int(protocol["metrics"]["bootstrap_repetitions"])
    base_seed = int(protocol["metrics"]["bootstrap_seed"])
    comparisons: dict[str, Any] = {}
    for budget in (96, 192):
        comparisons[str(budget)] = {
            "new_minus_old_yield": compare_arrays(
                arrays[budget], baselines[(OLD_YIELD, budget)], tasks, runs, repetitions, base_seed + budget
            ),
            "new_minus_uniform": compare_arrays(
                arrays[budget], baselines[(OLD_UNIFORM, budget)], tasks, runs, repetitions, base_seed + 10000 + budget
            ),
        }
    terminal_old = comparisons["192"]["new_minus_old_yield"]
    terminal_uniform = comparisons["192"]["new_minus_uniform"]
    structural_receipts = {
        str(budget): object_file(checkpoint_root / f"{NEW_ARM}__{budget}.json")["metrics"]["weight_receipt"]
        for budget in (96, 192)
    }
    advancement = {
        "structural_influence_gates_all_pass": all(
            receipt["selected_task_support_availability_fraction"] + 1e-12 >= support_minimum
            and receipt["final_weight"]["effective_sample_size_fraction"] + 1e-12 >= ess_minimum
            and receipt["final_weight"]["maximum_single_pair_weight_share"] <= influence_cap + 1e-12
            for receipt in structural_receipts.values()
        ),
        "task_distribution_l1_strictly_lower_at_both_budgets": all(
            receipt["task_distribution_l1"]["weighted_to_availability"]
            < receipt["task_distribution_l1"]["unweighted_to_availability"]
            for receipt in structural_receipts.values()
        ),
        "task_macro_accuracy_delta_new_minus_old_yield_strictly_positive_at_both_budgets": all(
            comparisons[str(budget)]["new_minus_old_yield"]["task_macro_accuracy"] > 0
            for budget in (96, 192)
        ),
        "terminal_pair_micro_accuracy_delta_new_minus_old_yield_nonnegative": terminal_old["pair_micro"][
            "pairwise_accuracy"
        ]
        >= 0,
        "terminal_log_loss_and_brier_delta_new_minus_old_yield_nonpositive": terminal_old["pair_micro"][
            "log_loss"
        ]
        <= 0
        and terminal_old["pair_micro"]["brier_score"] <= 0,
        "terminal_pair_micro_task_macro_and_drop_dominant_accuracy_delta_new_minus_uniform_nonnegative": (
            terminal_uniform["pair_micro"]["pairwise_accuracy"] >= 0
            and terminal_uniform["task_macro_accuracy"] >= 0
            and terminal_uniform["drop_dominant_task_pair_micro_accuracy"] >= 0
        ),
        "positive_task_count_at_least_negative_task_count_at_both_budgets": all(
            comparisons[str(budget)]["new_minus_old_yield"]["task_signs"]["positive"]
            >= comparisons[str(budget)]["new_minus_old_yield"]["task_signs"]["negative"]
            for budget in (96, 192)
        ),
    }
    classifications = protocol["advancement_gates_historical_development_only"]
    classification = classifications["if_all_gates_pass"] if all(advancement.values()) else classifications["if_any_gate_fails"]
    private_witness = {
        "protocol": PRIVATE,
        "protocol_sha256": protocol_sha,
        "source_commit": args.source_commit,
        "outer_eval_fold": 0,
        "outer_eval_pair_count": len(eval_labels),
        "arm_budget_count": 2,
        "rows": private_rows,
        "raw_identities_emitted": False,
    }
    summary = {
        "protocol": RESULT,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "source_commit": args.source_commit,
        "historical_source": {
            "root": str(args.source_root.resolve()),
            "old_protocol_sha256": protocol["immutable_inputs"]["historical_smoke_protocol"]["sha256"],
            "old_source_commit": protocol["immutable_inputs"]["historical_smoke_source_commit"],
            "old_private_pair_witness_sha256": protocol["immutable_inputs"]["historical_artifacts"][
                "fit/private_pairs.json"
            ],
        },
        "population": {
            "outer_train_pairs": len(train_labels),
            "outer_eval_pairs": len(eval_labels),
            "outer_eval_tasks": len(set(tasks)),
            "outer_eval_physical_runs": len(set(runs)),
            "train_eval_pair_overlap": 0,
            "train_eval_endpoint_overlap": 0,
            "train_eval_parent_overlap": 0,
            "train_eval_physical_run_overlap": 0,
            "historical_source_rows_intask_split_train_only": True,
            "senior_test_rows_used": False,
        },
        "structural_weight_receipts": structural_receipts,
        "model_rows": rows_out,
        "paired_comparisons": comparisons,
        "fit_checkpoints": {name: file_sha(checkpoint_root / name) for name in sorted(expected_names)},
        "private_pair_witness_sha256": sha_bytes(private_witness),
        "advancement_gates": advancement,
        "classification": classification,
        "scope": {
            "single_historical_outer_fold_development_only": True,
            "not_distribution_matched_selection_rescue": True,
            "confirmation_requires_rule_frozen_new_physical_runs": True,
            "prospective_first960_target300_target522_values_used": False,
            "public_identities_or_per_pair_predictions_emitted": False,
            "private_hashed_pair_witness_mode0600": True,
            "gpu_api_base_model_update": "0/0/0",
            "critic_model_fits": 2,
        },
    }
    identities = {item for row in topology for item in (*row.endpoints, row.parent, row.task, row.run)}
    public_text = canonical_bytes(summary).decode("utf-8")
    private_text = canonical_bytes(private_witness).decode("utf-8")
    require(not any(json.dumps(value, ensure_ascii=False) in public_text for value in identities), "public identity leak")
    require(not any(json.dumps(value, ensure_ascii=False) in private_text for value in identities), "private identity leak")
    return summary, rows_out, private_witness


def write_csv_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    require(rows, "CSV rows")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not path.exists() and not path.is_symlink(), f"output exists: {path}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        handle.write(buffer.getvalue())
        handle.flush()
        os.fsync(handle.fileno())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--old-protocol", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cards-root", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--runs-csv", type=Path, required=True)
    parser.add_argument("--private-pairs-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require(len(args.source_commit) == 40 and all(char in "0123456789abcdef" for char in args.source_commit), "source commit")
    summary, rows, private_witness = build(args)
    write_json_exclusive(args.private_pairs_output.resolve(), private_witness)
    require(file_sha(args.private_pairs_output.resolve()) == summary["private_pair_witness_sha256"], "private output SHA")
    write_json_exclusive(args.summary_output.resolve(), summary)
    write_csv_exclusive(args.runs_csv.resolve(), rows)
    print(
        canonical_bytes(
            {
                "classification": summary["classification"],
                "summary_sha256": file_sha(args.summary_output.resolve()),
                "runs_csv_sha256": file_sha(args.runs_csv.resolve()),
                "private_pairs_sha256": file_sha(args.private_pairs_output.resolve()),
                "scope": summary["scope"],
            }
        ).decode("utf-8"),
        end="",
    )


if __name__ == "__main__":
    main()
