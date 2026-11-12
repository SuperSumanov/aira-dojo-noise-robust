"""In-memory episode selection, source references, and output tree links.

Input: node dictionaries read from a big journal's data fields.
Output: Episode objects or rebuilt node lists. No filesystem input/output.
"""

from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import dataclass

from ..journal import has_training_outcome


@dataclass(frozen=True)
class Episode:
    root: int
    steps: tuple[int, ...]
    terminal: int | None


def operator(node: dict) -> str | None:
    """Return the first recorded operator, or None for context nodes without an operator."""
    return next(iter(node.get("operators_used", [])), None)


def metric(node: dict) -> float | None:
    """Return a finite training metric, or None when the node has no usable outcome."""
    value = node.get("metric")
    if not has_training_outcome(node) or isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return float(value) if math.isfinite(value) else None


def better(candidate: dict, baseline: dict) -> bool:
    """Compare usable CV metrics in their shared optimization direction, requiring strict improvement."""
    candidate_metric, baseline_metric = metric(candidate), metric(baseline)
    if candidate_metric is None or baseline_metric is None:
        return False
    maximize = baseline.get("metric_maximize")
    if not isinstance(maximize, bool) or candidate.get("metric_maximize") != maximize:
        raise ValueError("Missing or inconsistent CV metric direction")
    return candidate_metric > baseline_metric if maximize else candidate_metric < baseline_metric


def validate(nodes: list[dict]) -> None:
    """Check unique node identifiers, valid earlier parents, and matching operator and call counts."""
    by_step = {node["step"]: node for node in nodes}
    if len(by_step) != len(nodes) or len({node["id"] for node in nodes}) != len(nodes):
        raise ValueError("Duplicate node step or id")
    for node in nodes:
        parents = node.get("parents", [])
        if len(parents) > 1 or any(parent not in by_step or parent >= node["step"] for parent in parents):
            raise ValueError(f"Invalid parent at step {node['step']}: {parents}")
        if len(node.get("operators_used", [])) != len(node.get("operators_metrics", [])):
            raise ValueError(f"Operator/call count mismatch at step {node['step']}")


def episodes(nodes: list[dict]) -> list[Episode]:
    """Collect proposals and their debug chains, identifying resolved terminals and rejecting ambiguous chains."""
    validate(nodes)
    children: dict[int, list[int]] = {node["step"]: [] for node in nodes}
    by_step = {node["step"]: node for node in nodes}
    for node in nodes:
        for parent in node.get("parents", []):
            children[parent].append(node["step"])
    result = []
    for node in nodes:
        if operator(node) in (None, "debug"):
            continue
        path = [node["step"]]
        while not has_training_outcome(by_step[path[-1]]):
            following = [step for step in children[path[-1]] if operator(by_step[step]) == "debug"]
            if len(following) > 1:
                raise ValueError(f"Branching debug chain at {path[-1]}")
            if not following:
                break
            path.append(following[0])
        terminal = path[-1] if has_training_outcome(by_step[path[-1]]) else None
        result.append(Episode(node["step"], tuple(path), terminal))
    covered = {step for episode in result for step in episode.steps}
    if any(operator(node) == "debug" and node["step"] not in covered for node in nodes):
        raise ValueError("Debug node outside a proposal episode")
    return result


def synthetic_id(*parts: str) -> str:
    """Derive a stable synthetic identifier from source references."""
    return hashlib.blake2b(":".join(("hindsight", *parts)).encode(), digest_size=16).hexdigest()


def rebuild_links(nodes: list[dict]) -> list[dict]:
    """Copy and sort nodes, rebuild child links and running-best references, then validate the tree."""
    by_step = {node["step"]: copy.deepcopy(node) for node in nodes}
    result = [by_step[step] for step in sorted(by_step)]
    best = None
    for node in result:
        node["children"] = []
        if metric(node) is not None and (best is None or better(node, best)):
            best = node
        if "current_best_node" in node:
            node["current_best_node"] = best["step"] if best is not None else result[0]["step"]
    for node in result:
        for parent in node["parents"]:
            by_step[parent]["children"].append(node["step"])
    validate(result)
    return result
