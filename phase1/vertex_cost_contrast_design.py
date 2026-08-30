#!/usr/bin/env python3
"""Outcome-blind vertex-cost design for sibling-derived pair labels.

Executing an endpoint reveals one scalar outcome.  Pair labels inside a sibling
clique are then derived from the executed outcomes, so C(k, 2) materialized rows
contain at most k - 1 independent contrasts.  This module selects paid endpoint
vertices by D-optimal gain in that contrast space.  It intentionally accepts no
labels, grades, predictions, or utilities.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import itertools
import math
from typing import Mapping, Sequence
import zlib

import numpy as np


class ContrastDesignError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContrastDesignError(message)


@dataclass(frozen=True)
class ParentGroup:
    parent: str
    task: str
    run: str
    endpoints: tuple[str, ...]


@dataclass(frozen=True)
class CandidateAction:
    kind: str
    parent: str
    endpoints: tuple[str, ...]
    cost: int
    gain: float
    rate: float
    tie_key: str


@dataclass(frozen=True)
class DesignResult:
    selected_endpoints: tuple[str, ...]
    steps: tuple[dict[str, object], ...]
    contrast_vectors: tuple[np.ndarray, ...]
    information_logdet_gain: float
    numerical_feature_rank: int
    task_cap: int
    run_cap: int


def code_hash_feature(
    code: str,
    *,
    dimension: int = 128,
    ngram_min: int = 3,
    ngram_max: int = 5,
    max_chars: int = 20_000,
) -> np.ndarray:
    """Return a deterministic, corpus-free signed hashed Unicode-char feature."""

    require(isinstance(code, str), "code must be text")
    require(dimension >= 2, "feature dimension")
    require(1 <= ngram_min <= ngram_max, "ngram range")
    require(max_chars >= ngram_max, "max_chars")
    payload = code[:max_chars]
    counts: Counter[tuple[int, int]] = Counter()
    for width in range(ngram_min, ngram_max + 1):
        for offset in range(max(0, len(payload) - width + 1)):
            gram = payload[offset : offset + width].encode("utf-8")
            bucket_hash = zlib.crc32(gram, 0x13579BDF) & 0xFFFFFFFF
            sign_hash = zlib.crc32(gram, 0x2468ACE0) & 0xFFFFFFFF
            counts[(bucket_hash % dimension, 1 if sign_hash & 1 else -1)] += 1
    feature = np.zeros(dimension, dtype=np.float64)
    for (index, sign), count in counts.items():
        feature[index] += sign * (1.0 + math.log(count))
    norm = float(np.linalg.norm(feature))
    if norm > 0.0:
        feature /= norm
    return feature


def rank_normalized_pair_weight(clique_size: int) -> float:
    """Per-pair weight making a complete clique total exactly k - 1."""

    require(clique_size >= 2, "clique size")
    return 2.0 / float(clique_size)


def raw_pair_count(selected_by_parent: Mapping[str, Sequence[str]]) -> int:
    return sum(len(values) * (len(values) - 1) // 2 for values in selected_by_parent.values())


def contrast_rank_count(selected_by_parent: Mapping[str, Sequence[str]]) -> int:
    return sum(max(0, len(values) - 1) for values in selected_by_parent.values())


def _action_key(kind: str, parent: str, endpoints: Sequence[str]) -> str:
    payload = "\0".join((kind, parent, *sorted(endpoints))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_inputs(
    groups: Sequence[ParentGroup],
    features: Mapping[str, np.ndarray],
    budget: int,
) -> tuple[dict[str, ParentGroup], dict[str, str], dict[str, np.ndarray], int]:
    require(groups, "empty groups")
    parents: dict[str, ParentGroup] = {}
    endpoint_parent: dict[str, str] = {}
    feature_vectors: dict[str, np.ndarray] = {}
    dimension: int | None = None
    for group in groups:
        require(
            all(isinstance(value, str) and value for value in (group.parent, group.task, group.run)),
            "invalid group identity",
        )
        require(group.parent not in parents, "duplicate parent")
        endpoints = tuple(sorted(group.endpoints))
        require(
            len(endpoints) >= 2
            and len(set(endpoints)) == len(endpoints)
            and all(isinstance(endpoint, str) and endpoint for endpoint in endpoints),
            "invalid sibling group",
        )
        require(endpoints == group.endpoints, "endpoints must be sorted")
        parents[group.parent] = group
        for endpoint in endpoints:
            require(endpoint not in endpoint_parent, "endpoint belongs to multiple parents")
            require(endpoint in features, "missing endpoint feature")
            vector = np.asarray(features[endpoint], dtype=np.float64)
            require(vector.ndim == 1 and vector.size > 0, "feature shape")
            require(np.isfinite(vector).all(), "nonfinite feature")
            if dimension is None:
                dimension = int(vector.size)
            require(vector.size == dimension, "feature dimension mismatch")
            feature_vectors[endpoint] = vector.copy()
            endpoint_parent[endpoint] = group.parent
    require(set(features) == set(endpoint_parent), "unexpected endpoint features")
    require(1 <= budget <= len(endpoint_parent), "budget outside endpoint population")
    assert dimension is not None
    return parents, endpoint_parent, feature_vectors, dimension


def select_vertex_cost_contrasts(
    groups: Sequence[ParentGroup],
    features: Mapping[str, np.ndarray],
    *,
    budget: int,
    ridge: float = 1.0,
    task_share_denominator: int = 5,
    run_share_denominator: int = 10,
) -> DesignResult:
    """Construct one exact-budget nested endpoint order without outcome access.

    An unopened parent is a two-endpoint action.  Extending an opened parent is
    a one-endpoint action whose rank-one scatter update is
    sqrt(k/(k+1)) * (x_new - mean_old).  Candidate actions maximize D-optimal
    marginal log-determinant gain per newly executed endpoint.  Fixed terminal
    task/run caps prevent one task or physical run from absorbing the budget.
    """

    parents, endpoint_parent, feature_vectors, dimension = _validate_inputs(groups, features, budget)
    require(ridge > 0.0 and math.isfinite(ridge), "ridge")
    require(task_share_denominator >= 2 and run_share_denominator >= 2, "share denominator")
    task_cap = max(2, (budget + task_share_denominator - 1) // task_share_denominator)
    run_cap = max(2, (budget + run_share_denominator - 1) // run_share_denominator)

    selected: list[str] = []
    selected_set: set[str] = set()
    selected_by_parent: dict[str, list[str]] = defaultdict(list)
    task_counts: Counter[str] = Counter()
    run_counts: Counter[str] = Counter()
    inverse = np.eye(dimension, dtype=np.float64) / ridge
    logdet_gain = 0.0
    contrast_vectors: list[np.ndarray] = []
    steps: list[dict[str, object]] = []

    def admissible(group: ParentGroup, cost: int) -> bool:
        return (
            len(selected) + cost <= budget
            and task_counts[group.task] + cost <= task_cap
            and run_counts[group.run] + cost <= run_cap
        )

    def vector_gain(vector: np.ndarray) -> float:
        leverage = float(vector @ inverse @ vector)
        require(leverage >= -1e-10 and math.isfinite(leverage), "invalid leverage")
        return math.log1p(max(0.0, leverage))

    def extension_vector(parent: str, endpoint: str) -> np.ndarray:
        existing = selected_by_parent[parent]
        require(existing, "extension requires open parent")
        mean = np.mean([feature_vectors[value] for value in existing], axis=0)
        factor = math.sqrt(len(existing) / (len(existing) + 1.0))
        return factor * (feature_vectors[endpoint] - mean)

    def candidates() -> list[CandidateAction]:
        actions: list[CandidateAction] = []
        remaining = budget - len(selected)
        for parent, group in sorted(parents.items()):
            existing = selected_by_parent[parent]
            unseen = [value for value in group.endpoints if value not in selected_set]
            if not unseen:
                continue
            if existing:
                if not admissible(group, 1):
                    continue
                for endpoint in unseen:
                    gain = vector_gain(extension_vector(parent, endpoint))
                    actions.append(
                        CandidateAction(
                            "extend_parent",
                            parent,
                            (endpoint,),
                            1,
                            gain,
                            gain,
                            _action_key("extend_parent", parent, (endpoint,)),
                        )
                    )
            elif remaining >= 2 and admissible(group, 2):
                for left, right in itertools.combinations(unseen, 2):
                    vector = math.sqrt(0.5) * (feature_vectors[right] - feature_vectors[left])
                    gain = vector_gain(vector)
                    actions.append(
                        CandidateAction(
                            "open_parent_pair",
                            parent,
                            (left, right),
                            2,
                            gain,
                            gain / 2.0,
                            _action_key("open_parent_pair", parent, (left, right)),
                        )
                    )
        return actions

    def append_endpoint(endpoint: str, action: CandidateAction, position: int) -> None:
        nonlocal inverse, logdet_gain
        require(endpoint not in selected_set, "duplicate selection")
        parent = endpoint_parent[endpoint]
        group = parents[parent]
        before = selected_by_parent[parent]
        update: np.ndarray | None = None
        marginal = 0.0
        if before:
            update = extension_vector(parent, endpoint)
            projected = inverse @ update
            leverage = float(update @ projected)
            leverage = max(0.0, leverage)
            inverse = inverse - np.outer(projected, projected) / (1.0 + leverage)
            marginal = math.log1p(leverage)
            logdet_gain += marginal
            contrast_vectors.append(update.copy())
        selected.append(endpoint)
        selected_set.add(endpoint)
        selected_by_parent[parent].append(endpoint)
        task_counts[group.task] += 1
        run_counts[group.run] += 1
        pairs = raw_pair_count(selected_by_parent)
        rank = contrast_rank_count(selected_by_parent)
        require(rank == len(contrast_vectors), "contrast accounting mismatch")
        steps.append(
            {
                "step": len(selected),
                "endpoint": endpoint,
                "action_kind": action.kind,
                "action_cost": action.cost,
                "action_position": position,
                "action_tie_key": action.tie_key,
                "marginal_logdet_gain": marginal,
                "cumulative_logdet_gain": logdet_gain,
                "raw_induced_pair_count": pairs,
                "contrast_rank_count": rank,
                "maximum_task_endpoints": max(task_counts.values()),
                "maximum_run_endpoints": max(run_counts.values()),
            }
        )

    while len(selected) < budget:
        actions = candidates()
        if actions:
            action = min(actions, key=lambda item: (-item.rate, -item.gain, item.tie_key))
        else:
            fillers: list[tuple[str, str]] = []
            for endpoint, parent in sorted(endpoint_parent.items()):
                if endpoint in selected_set:
                    continue
                group = parents[parent]
                if admissible(group, 1):
                    fillers.append((_action_key("exact_budget_fill", parent, (endpoint,)), endpoint))
            require(fillers, "anti-dominance caps make exact budget infeasible")
            tie_key, endpoint = min(fillers)
            action = CandidateAction(
                "exact_budget_fill",
                endpoint_parent[endpoint],
                (endpoint,),
                1,
                0.0,
                0.0,
                tie_key,
            )
        ordered = tuple(sorted(action.endpoints, key=lambda value: _action_key("endpoint", action.parent, (value,))))
        before_gain = logdet_gain
        for position, endpoint in enumerate(ordered, start=1):
            append_endpoint(endpoint, action, position)
        observed_gain = logdet_gain - before_gain
        require(math.isclose(observed_gain, action.gain, rel_tol=1e-9, abs_tol=1e-10), "action gain drift")

    require(len(selected) == budget and len(selected_set) == budget, "exact budget")
    require(max(task_counts.values()) <= task_cap, "task cap")
    require(max(run_counts.values()) <= run_cap, "run cap")
    rank = int(np.linalg.matrix_rank(np.vstack(contrast_vectors))) if contrast_vectors else 0
    return DesignResult(
        tuple(selected),
        tuple(steps),
        tuple(contrast_vectors),
        logdet_gain,
        rank,
        task_cap,
        run_cap,
    )
