#!/usr/bin/env python3
"""Build an outcome-blind trajectory and decomposition of benchmark task weights."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import statistics
import sys
from pathlib import Path
from typing import Any, Callable


PROTOCOL = "prospective_structural_weight_trajectory_v1"
STATUS = "OUTCOME_BLIND_STRUCTURAL_WEIGHT_TRAJECTORY_READY"
MILESTONES = (120, 160, 200, 240, 260, 280, 300, 320, 339)
BASELINE_RUNS = 240
LATE_CHECKPOINTS = (260, 280, 300, 320, 339)
SHA256_CHARS = frozenset("0123456789abcdef")
RUN_KEYS = {
    "run_id",
    "task",
    "generation_started_at_utc",
    "source_sha256",
    "drop_id",
    "flow_status",
    "endpoints",
}
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}


class TrajectoryError(RuntimeError):
    """Raised when an input or structural invariant fails closed."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= SHA256_CHARS


def valid_git_commit(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and set(value) <= SHA256_CHARS


def regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise TrajectoryError(f"input is absent, non-regular, or symlinked: {path.name}")


def read_json(path: Path, expected_sha256: str | None = None) -> Any:
    regular_file(path)
    raw = path.read_bytes()
    if expected_sha256 is not None and sha256_bytes(raw) != expected_sha256:
        raise TrajectoryError(f"input hash mismatch: {path.name}")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrajectoryError(f"cannot parse JSON: {path.name}") from exc


def read_jsonl(path: Path, expected_sha256: str) -> list[dict[str, Any]]:
    regular_file(path)
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_sha256:
        raise TrajectoryError(f"input hash mismatch: {path.name}")
    output: list[dict[str, Any]] = []
    try:
        text = raw.decode("utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TrajectoryError(f"non-object JSONL row: {path.name}:{line_number}")
            output.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrajectoryError(f"cannot parse JSONL: {path.name}") from exc
    return output


def read_snapshot_manifest(snapshot_root: Path, expected_snapshot: str) -> dict[str, str]:
    if snapshot_root.is_symlink() or not snapshot_root.is_dir():
        raise TrajectoryError("snapshot root is absent, non-directory, or symlinked")
    if snapshot_root.name != expected_snapshot or not valid_sha256(expected_snapshot):
        raise TrajectoryError("snapshot identity mismatch")
    manifest = snapshot_root / "SHA256SUMS"
    regular_file(manifest)
    raw = manifest.read_bytes()
    if sha256_bytes(raw) != expected_snapshot:
        raise TrajectoryError("snapshot SHA256SUMS is not bound by the snapshot identity")
    entries: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not valid_sha256(parts[0]):
            raise TrajectoryError("malformed snapshot SHA256SUMS")
        relative = parts[1].lstrip("* ").replace("\\", "/")
        if relative in entries or relative.startswith("/") or ".." in Path(relative).parts:
            raise TrajectoryError("unsafe or duplicate snapshot manifest path")
        entries[relative] = parts[0]
    return entries


def bound_snapshot_file(snapshot_root: Path, entries: dict[str, str], relative: str) -> Path:
    expected = entries.get(relative)
    if not valid_sha256(expected):
        raise TrajectoryError(f"snapshot manifest omits required file: {relative}")
    path = snapshot_root / relative
    regular_file(path)
    if sha256_file(path) != expected:
        raise TrajectoryError(f"snapshot file hash mismatch: {relative}")
    return path


def safe_intake_dir(snapshot_root: Path, value: Any) -> Path:
    if not isinstance(value, str):
        raise TrajectoryError("intake path is not a string")
    directory = Path(value)
    state_root = snapshot_root.parents[1].resolve()
    expected_parent = (state_root / "intakes").resolve()
    if directory.is_symlink() or not directory.is_dir():
        raise TrajectoryError("intake directory is absent or unsafe")
    resolved = directory.resolve()
    if resolved.parent != expected_parent:
        raise TrajectoryError("intake directory escapes the fixed state/intakes root")
    return resolved


def validate_accumulator_security(summary: dict[str, Any]) -> None:
    security = summary.get("security")
    if (
        summary.get("protocol") != "prospective_accumulator_v1"
        or not isinstance(security, dict)
        or security.get("label_vault_opened") is not False
        or security.get("outcome_files_opened") != []
        or security.get("scorer_prediction_files_opened") != []
    ):
        raise TrajectoryError("accumulator is not an outcome-blind receipt")


def validate_intake_summary(summary: dict[str, Any]) -> None:
    blindness = summary.get("blindness")
    security = summary.get("security")
    if (
        summary.get("protocol") != "prospective_drop_intake_v1"
        or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE"
        or not isinstance(blindness, dict)
        or blindness.get("label_values_printed") is not False
        or blindness.get("labels_used_for_endpoint_selection") is not False
        or blindness.get("labels_used_for_run_selection") is not False
        or blindness.get("metrics_computed") != []
        or not isinstance(security, dict)
        or security.get("env_members_read") is not False
    ):
        raise TrajectoryError("intake is not a valid outcome-blind receipt")


def load_structural_inputs(
    snapshot_root: Path,
    expected_snapshot: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    manifest = read_snapshot_manifest(snapshot_root, expected_snapshot)
    summary_path = bound_snapshot_file(snapshot_root, manifest, "accumulator/summary.json")
    runs_path = bound_snapshot_file(
        snapshot_root, manifest, "accumulator/provisional_first960_runs.jsonl"
    )
    registry_path = bound_snapshot_file(snapshot_root, manifest, "intake_registry.jsonl")
    summary = read_json(summary_path, manifest["accumulator/summary.json"])
    if not isinstance(summary, dict):
        raise TrajectoryError("accumulator summary is not an object")
    validate_accumulator_security(summary)
    outputs = summary.get("outputs")
    inputs = summary.get("inputs")
    inventory = summary.get("inventory")
    if not all(isinstance(value, dict) for value in (outputs, inputs, inventory)):
        raise TrajectoryError("accumulator bindings are missing")
    run_sha = outputs.get("provisional_first960_runs_sha256")
    if run_sha != manifest["accumulator/provisional_first960_runs.jsonl"]:
        raise TrajectoryError("accumulator run hash disagrees with snapshot manifest")
    if inputs.get("registry_sha256") != manifest["intake_registry.jsonl"]:
        raise TrajectoryError("accumulator registry hash disagrees with snapshot manifest")

    runs = read_jsonl(runs_path, run_sha)
    if len(runs) != inventory.get("provisional_first960_runs"):
        raise TrajectoryError("provisional run inventory mismatch")
    if len(runs) < max(MILESTONES):
        raise TrajectoryError("snapshot does not contain every frozen milestone")
    seen_runs: set[str] = set()
    previous_key: tuple[str, str, str] | None = None
    for row in runs:
        if set(row) != RUN_KEYS:
            raise TrajectoryError("provisional run schema mismatch")
        run_id = row["run_id"]
        task = row["task"]
        source_sha = row["source_sha256"]
        if (
            not isinstance(run_id, str)
            or not run_id
            or run_id in seen_runs
            or not isinstance(task, str)
            or not task
            or not valid_sha256(source_sha)
            or run_id != f"journal:{source_sha}"
            or not isinstance(row["endpoints"], int)
            or isinstance(row["endpoints"], bool)
            or row["endpoints"] <= 0
        ):
            raise TrajectoryError("invalid provisional run identity")
        key = (row["generation_started_at_utc"], source_sha, run_id)
        if not all(isinstance(item, str) and item for item in key):
            raise TrajectoryError("invalid chronological run key")
        if previous_key is not None and key < previous_key:
            raise TrajectoryError("provisional runs are not chronological")
        previous_key = key
        seen_runs.add(run_id)

    registry = read_jsonl(registry_path, manifest["intake_registry.jsonl"])
    if len(registry) != inventory.get("drops"):
        raise TrajectoryError("intake registry inventory mismatch")
    run_records: dict[str, dict[str, Any]] = {}
    pair_sets: dict[str, set[tuple[str, str, str]]] = collections.defaultdict(set)
    input_hashes: dict[str, Any] = {
        "snapshot_manifest_sha256": expected_snapshot,
        "accumulator_summary_sha256": manifest["accumulator/summary.json"],
        "provisional_first960_runs_sha256": run_sha,
        "intake_registry_sha256": manifest["intake_registry.jsonl"],
        "intakes": {},
    }
    seen_drops: set[str] = set()
    for registry_row in registry:
        if set(registry_row) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise TrajectoryError("intake registry schema mismatch")
        drop_id = registry_row["drop_id"]
        summary_sha = registry_row["summary_sha256"]
        if not isinstance(drop_id, str) or not drop_id or drop_id in seen_drops:
            raise TrajectoryError("invalid or duplicate drop ID")
        if not valid_sha256(summary_sha):
            raise TrajectoryError("invalid intake summary hash")
        seen_drops.add(drop_id)
        intake_dir = safe_intake_dir(snapshot_root, registry_row["intake_dir"])
        intake_summary = read_json(intake_dir / "summary.json", summary_sha)
        if not isinstance(intake_summary, dict):
            raise TrajectoryError("intake summary is not an object")
        validate_intake_summary(intake_summary)
        intake_outputs = intake_summary.get("outputs")
        intake_inventory = intake_summary.get("inventory")
        if not isinstance(intake_outputs, dict) or not isinstance(intake_inventory, dict):
            raise TrajectoryError("intake output bindings are missing")
        provenance_sha = intake_outputs.get("source_provenance_sha256")
        pair_sha = intake_outputs.get("eligible_structural_pairs_sha256")
        if not valid_sha256(provenance_sha) or not valid_sha256(pair_sha):
            raise TrajectoryError("intake structural hashes are invalid")
        provenance = read_json(intake_dir / "source_provenance.json", provenance_sha)
        pairs = read_jsonl(intake_dir / "eligible_structural_pairs.jsonl", pair_sha)
        if not isinstance(provenance, list):
            raise TrajectoryError("source provenance is not a list")
        eligible_in_drop: set[str] = set()
        for record in provenance:
            if not isinstance(record, dict) or not isinstance(record.get("eligible"), bool):
                raise TrajectoryError("invalid source provenance record")
            if not record["eligible"]:
                continue
            run_id = record.get("run_id")
            if not isinstance(run_id, str) or run_id in run_records:
                raise TrajectoryError("duplicate eligible run across intakes")
            if (
                run_id != f"journal:{record.get('journal_sha256')}"
                or not isinstance(record.get("task"), str)
                or not isinstance(record.get("endpoints"), int)
                or record["endpoints"] <= 0
            ):
                raise TrajectoryError("invalid eligible provenance identity")
            run_records[run_id] = {
                "run_id": run_id,
                "task": record["task"],
                "generation_started_at_utc": record["generation_started_at_utc"],
                "source_sha256": record["journal_sha256"],
                "drop_id": drop_id,
                "flow_status": record["flow_status"],
                "endpoints": record["endpoints"],
            }
            eligible_in_drop.add(run_id)
        if len(eligible_in_drop) != intake_inventory.get("eligible_runs"):
            raise TrajectoryError("eligible run count disagrees with intake summary")
        if len(pairs) != intake_inventory.get("eligible_structural_pairs"):
            raise TrajectoryError("eligible pair count disagrees with intake summary")
        seen_pairs: set[tuple[str, str, str, str, str]] = set()
        for pair in pairs:
            if set(pair) != PAIR_KEYS:
                raise TrajectoryError("structural pair schema mismatch")
            task, run_id, parent, left, right = (
                pair["task"], pair["run_id"], pair["parent"], pair["left"], pair["right"]
            )
            if not all(isinstance(value, str) and value for value in (task, run_id, parent, left, right)):
                raise TrajectoryError("invalid structural pair identity")
            if run_id not in eligible_in_drop or run_records[run_id]["task"] != task or left >= right:
                raise TrajectoryError("structural pair does not match eligible provenance")
            identity = (task, run_id, parent, left, right)
            if identity in seen_pairs:
                raise TrajectoryError("duplicate structural pair")
            seen_pairs.add(identity)
            pair_sets[run_id].add((parent, left, right))
        input_hashes["intakes"][drop_id] = {
            "summary_sha256": summary_sha,
            "source_provenance_sha256": provenance_sha,
            "eligible_structural_pairs_sha256": pair_sha,
        }

    selected_ids = {row["run_id"] for row in runs}
    if not selected_ids <= set(run_records):
        raise TrajectoryError("provisional run is absent from intake provenance")
    for row in runs:
        if row != run_records[row["run_id"]]:
            raise TrajectoryError("provisional run identity disagrees with intake provenance")
    selected_pairs = sum(len(pair_sets[run_id]) for run_id in selected_ids)
    selected_endpoints = sum(run_records[run_id]["endpoints"] for run_id in selected_ids)
    if (
        selected_pairs != inventory.get("provisional_first960_structural_pairs")
        or selected_endpoints != inventory.get("provisional_first960_endpoints")
    ):
        raise TrajectoryError("provisional structural inventory mismatch")
    for run_id, record in run_records.items():
        record["pairs"] = len(pair_sets[run_id])
        record["parents"] = len({identity[0] for identity in pair_sets[run_id]})
    return runs, run_records, {"summary": summary, "input_hashes": input_hashes}


def concentration(counts: dict[str, int]) -> dict[str, Any] | None:
    keys = [key for key in sorted(counts) if counts[key] > 0]
    total = sum(counts[key] for key in keys)
    if total <= 0:
        return None
    shares = [counts[key] / total for key in keys]
    hhi = sum(value * value for value in shares)
    entropy = -sum(value * math.log(value) for value in shares)
    ascending = sorted(counts[key] for key in keys)
    n = len(ascending)
    gini_numerator = sum((2 * index - n - 1) * value for index, value in enumerate(ascending, 1))
    maximum = max(counts[key] for key in keys)
    dominant = [key for key in keys if counts[key] == maximum]
    return {
        "positive_tasks": n,
        "total_weight": total,
        "maximum_share": maximum / total,
        "dominant_tasks": dominant,
        "top3_share": sum(sorted(shares, reverse=True)[:3]),
        "hhi": hhi,
        "inverse_hhi_descriptive_diversity": 1.0 / hhi,
        "shannon_entropy": entropy,
        "exponential_shannon_descriptive_diversity": math.exp(entropy),
        "gini": gini_numerator / (n * total),
    }


def distribution(counts: dict[str, int], keys: list[str]) -> dict[str, float] | None:
    total = sum(counts.get(key, 0) for key in keys)
    if total <= 0:
        return None
    return {key: counts.get(key, 0) / total for key in keys}


def total_variation(left: dict[str, float], right: dict[str, float]) -> float:
    keys = sorted(set(left) | set(right))
    return 0.5 * sum(abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in keys)


def scope_summary(rows: list[dict[str, Any]], run_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise TrajectoryError("scope cannot be empty")
    run_counts: collections.Counter[str] = collections.Counter()
    endpoint_counts: collections.Counter[str] = collections.Counter()
    parent_counts: collections.Counter[str] = collections.Counter()
    pair_counts: collections.Counter[str] = collections.Counter()
    decision_runs = 0
    for row in rows:
        record = run_records[row["run_id"]]
        task = record["task"]
        run_counts[task] += 1
        endpoint_counts[task] += record["endpoints"]
        parent_counts[task] += record["parents"]
        pair_counts[task] += record["pairs"]
        decision_runs += record["pairs"] > 0
    keys = sorted(run_counts)
    distributions = {
        "runs": distribution(run_counts, keys),
        "endpoints": distribution(endpoint_counts, keys),
        "decision_parents": distribution(parent_counts, keys),
        "structural_pairs": distribution(pair_counts, keys),
    }
    run_dist = distributions["runs"]
    if run_dist is None:
        raise TrajectoryError("run distribution is empty")
    shifts = {}
    for name in ("endpoints", "decision_parents", "structural_pairs"):
        value = distributions[name]
        shifts[f"runs_to_{name}"] = total_variation(run_dist, value) if value else None
    return {
        "inventory": {
            "runs": len(rows),
            "tasks": len(keys),
            "endpoints": sum(endpoint_counts.values()),
            "decision_parents": sum(parent_counts.values()),
            "structural_pairs": sum(pair_counts.values()),
            "finite_decision_runs": decision_runs,
            "pair_tasks": sum(value > 0 for value in pair_counts.values()),
        },
        "concentration": {
            "runs": concentration(dict(run_counts)),
            "endpoints": concentration(dict(endpoint_counts)),
            "decision_parents": concentration(dict(parent_counts)),
            "structural_pairs": concentration(dict(pair_counts)),
        },
        "weighting_shift_tv": shifts,
        "counts": {
            "runs": {key: run_counts[key] for key in keys},
            "endpoints": {key: endpoint_counts[key] for key in keys},
            "decision_parents": {key: parent_counts[key] for key in keys},
            "structural_pairs": {key: pair_counts[key] for key in keys},
        },
    }


def compact_scope(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "inventory": scope["inventory"],
        "concentration": scope["concentration"],
        "weighting_shift_tv": scope["weighting_shift_tv"],
    }


def task_table(baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    keys = sorted(set(baseline["counts"]["runs"]) | set(current["counts"]["runs"]))
    current_runs = current["counts"]["runs"]
    current_pairs = current["counts"]["structural_pairs"]
    total_runs = sum(current_runs.values())
    total_pairs = sum(current_pairs.values())
    output = []
    for task in keys:
        row: dict[str, Any] = {"task": task}
        for label, scope in (("baseline", baseline), ("current", current)):
            runs = scope["counts"]["runs"].get(task, 0)
            endpoints = scope["counts"]["endpoints"].get(task, 0)
            parents = scope["counts"]["decision_parents"].get(task, 0)
            pairs = scope["counts"]["structural_pairs"].get(task, 0)
            row[label] = {
                "runs": runs,
                "endpoints": endpoints,
                "decision_parents": parents,
                "structural_pairs": pairs,
                "endpoints_per_run": endpoints / runs if runs else None,
                "decision_parents_per_run": parents / runs if runs else None,
                "pairs_per_run": pairs / runs if runs else None,
            }
        run_share = current_runs.get(task, 0) / total_runs
        pair_share = current_pairs.get(task, 0) / total_pairs if total_pairs else 0.0
        row["current_pair_share_over_run_share"] = pair_share / run_share if run_share else None
        output.append(row)
    return output


def normalize_product(run_counts: dict[str, int], yields: dict[str, float], keys: list[str]) -> dict[str, float]:
    weights = {key: run_counts.get(key, 0) * yields[key] for key in keys}
    total = sum(weights.values())
    if total <= 0:
        raise TrajectoryError("counterfactual pair distribution has zero support")
    return {key: weights[key] / total for key in keys}


def normalize_runs(run_counts: dict[str, int], keys: list[str]) -> dict[str, float]:
    total = sum(run_counts.get(key, 0) for key in keys)
    if total <= 0:
        raise TrajectoryError("counterfactual run distribution has zero support")
    return {key: run_counts.get(key, 0) / total for key in keys}


def distribution_hhi(values: dict[str, float]) -> float:
    return sum(values[key] * values[key] for key in sorted(values))


def shapley_decomposition(
    run0: dict[str, int],
    run1: dict[str, int],
    pair0: dict[str, int],
    pair1: dict[str, int],
    metric: Callable[[dict[str, int], dict[str, float], list[str]], float],
) -> dict[str, Any]:
    keys = sorted(set(run0) | set(run1))
    yield1 = {key: pair1.get(key, 0) / run1[key] for key in keys}
    yield0 = {
        key: pair0.get(key, 0) / run0[key] if run0.get(key, 0) else yield1[key]
        for key in keys
    }
    m00 = metric(run0, yield0, keys)
    m10 = metric(run1, yield0, keys)
    m01 = metric(run0, yield1, keys)
    m11 = metric(run1, yield1, keys)
    composition = 0.5 * ((m10 - m00) + (m11 - m01))
    opportunity_yield = 0.5 * ((m01 - m00) + (m11 - m10))
    delta = m11 - m00
    return {
        "baseline": m00,
        "current": m11,
        "total_delta": delta,
        "run_composition_contribution": composition,
        "opportunity_yield_contribution": opportunity_yield,
        "opportunity_yield_fraction_of_positive_delta": opportunity_yield / delta if delta > 0 else None,
        "additivity_residual": delta - composition - opportunity_yield,
        "path_values": {"m00": m00, "m10": m10, "m01": m01, "m11": m11},
        "new_task_baseline_yield_convention": "current_observed_yield",
    }


def pair_hhi_metric(run_counts: dict[str, int], yields: dict[str, float], keys: list[str]) -> float:
    return distribution_hhi(normalize_product(run_counts, yields, keys))


def run_pair_tv_metric(run_counts: dict[str, int], yields: dict[str, float], keys: list[str]) -> float:
    return total_variation(normalize_runs(run_counts, keys), normalize_product(run_counts, yields, keys))


def decomposition(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    run0 = baseline["counts"]["runs"]
    run1 = current["counts"]["runs"]
    pair0 = baseline["counts"]["structural_pairs"]
    pair1 = current["counts"]["structural_pairs"]
    keys = sorted(set(run0) | set(run1))
    yield1 = {key: pair1.get(key, 0) / run1[key] for key in keys}
    yield0 = {
        key: pair0.get(key, 0) / run0[key] if run0.get(key, 0) else yield1[key]
        for key in keys
    }
    midpoint = []
    for key in keys:
        delta_pairs = pair1.get(key, 0) - pair0.get(key, 0)
        composition = (run1.get(key, 0) - run0.get(key, 0)) * (yield0[key] + yield1[key]) / 2
        opportunity_yield = (yield1[key] - yield0[key]) * (run0.get(key, 0) + run1.get(key, 0)) / 2
        midpoint.append(
            {
                "task": key,
                "pair_count_delta": delta_pairs,
                "run_composition_count_contribution": composition,
                "opportunity_yield_count_contribution": opportunity_yield,
                "additivity_residual": delta_pairs - composition - opportunity_yield,
            }
        )
    return {
        "pair_hhi": shapley_decomposition(run0, run1, pair0, pair1, pair_hhi_metric),
        "run_to_pair_total_variation": shapley_decomposition(
            run0, run1, pair0, pair1, run_pair_tv_metric
        ),
        "midpoint_pair_count_by_task": midpoint,
    }


def build_result(
    snapshot_root: Path,
    expected_snapshot: str,
    source_commit: str,
    protocol_spec: Path,
    expected_protocol_spec_sha256: str,
) -> dict[str, Any]:
    if not valid_git_commit(source_commit):
        raise TrajectoryError("source commit is not a full lowercase Git SHA")
    if protocol_spec.name != "First960_结构权重时序分解_结果前冻结.md":
        raise TrajectoryError("unexpected protocol specification basename")
    regular_file(protocol_spec)
    if sha256_file(protocol_spec) != expected_protocol_spec_sha256:
        raise TrajectoryError("protocol specification hash mismatch")
    runs, run_records, receipts = load_structural_inputs(snapshot_root, expected_snapshot)
    trajectory = []
    scopes: dict[int, dict[str, Any]] = {}
    for index in range(1, len(runs) + 1):
        scope = scope_summary(runs[:index], run_records)
        scopes[index] = scope
        trajectory.append({"prefix_runs": index, **compact_scope(scope)})
    baseline = scopes[BASELINE_RUNS]
    current = scopes[len(runs)]
    milestone_rows = [
        {"prefix_runs": milestone, **compact_scope(scopes[milestone])}
        for milestone in MILESTONES
    ]
    mechanism = decomposition(baseline, current)

    base_run_hhi = baseline["concentration"]["runs"]["hhi"]
    base_pair_hhi = baseline["concentration"]["structural_pairs"]["hhi"]
    current_pair_hhi = current["concentration"]["structural_pairs"]["hhi"]
    pair_delta = current_pair_hhi - base_pair_hhi
    late = []
    for milestone in LATE_CHECKPOINTS:
        point = scopes[milestone]
        inversion = (
            point["concentration"]["runs"]["hhi"] <= base_run_hhi
            and point["concentration"]["structural_pairs"]["hhi"] > base_pair_hhi
        )
        late.append({"prefix_runs": milestone, "inversion_vs_first240": inversion})

    added_rows = runs[BASELINE_RUNS:]
    added_drops = sorted({row["drop_id"] for row in added_rows})
    drop_loo = []
    for drop_id in added_drops:
        kept = runs[:BASELINE_RUNS] + [row for row in added_rows if row["drop_id"] != drop_id]
        scope = scope_summary(kept, run_records)
        loo_pair_hhi = scope["concentration"]["structural_pairs"]["hhi"]
        attribution = (current_pair_hhi - loo_pair_hhi) / pair_delta if pair_delta > 0 else None
        drop_loo.append(
            {
                "drop_id": drop_id,
                "removed_added_runs": sum(row["drop_id"] == drop_id for row in added_rows),
                "remaining_runs": len(kept),
                "run_hhi_delta_vs_first240": scope["concentration"]["runs"]["hhi"] - base_run_hhi,
                "pair_hhi_delta_vs_first240": loo_pair_hhi - base_pair_hhi,
                "attribution_fraction_of_positive_pair_hhi_delta": attribution,
            }
        )
    positive_drop_attributions = [
        max(0.0, row["attribution_fraction_of_positive_pair_hhi_delta"])
        for row in drop_loo
        if row["attribution_fraction_of_positive_pair_hhi_delta"] is not None
    ]
    maximum_drop_attribution = max(positive_drop_attributions, default=0.0)

    tasks = sorted(current["counts"]["runs"])
    dominant_tasks = current["concentration"]["structural_pairs"]["dominant_tasks"]
    if len(dominant_tasks) != 1:
        raise TrajectoryError("current pair-dominant task is tied")
    dominant_task = dominant_tasks[0]
    task_loo = []
    for task in tasks:
        base_kept = [row for row in runs[:BASELINE_RUNS] if row["task"] != task]
        current_kept = [row for row in runs if row["task"] != task]
        base_scope = scope_summary(base_kept, run_records)
        current_scope = scope_summary(current_kept, run_records)
        run_delta = (
            current_scope["concentration"]["runs"]["hhi"]
            - base_scope["concentration"]["runs"]["hhi"]
        )
        loo_pair_delta = (
            current_scope["concentration"]["structural_pairs"]["hhi"]
            - base_scope["concentration"]["structural_pairs"]["hhi"]
        )
        task_loo.append(
            {
                "removed_task": task,
                "is_current_pair_dominant_task": task == dominant_task,
                "run_hhi_delta": run_delta,
                "pair_hhi_delta": loo_pair_delta,
                "inversion_retained": run_delta <= 0 and loo_pair_delta > 0,
            }
        )
    retained = sum(row["inversion_retained"] for row in task_loo)
    dominant_retained = next(
        row["inversion_retained"] for row in task_loo if row["is_current_pair_dominant_task"]
    )

    pair_hhi_decomp = mechanism["pair_hhi"]
    tv_decomp = mechanism["run_to_pair_total_variation"]
    gates = {
        "G1_temporal_persistence": {
            "pass": sum(row["inversion_vs_first240"] for row in late) >= 4,
            "required": "at_least_4_of_5_late_checkpoints",
            "observed": sum(row["inversion_vs_first240"] for row in late),
            "checkpoints": late,
        },
        "G2_no_single_drop_artifact": {
            "pass": pair_delta > 0 and maximum_drop_attribution < 0.5,
            "required": "maximum_positive_single_drop_attribution_below_0.5",
            "observed": maximum_drop_attribution,
        },
        "G3_single_task_robustness": {
            "pass": retained / len(task_loo) >= 0.8 and dominant_retained,
            "required": "at_least_80_percent_task_deletions_and_dominant_task_deletion_retain_inversion",
            "retained": retained,
            "total": len(task_loo),
            "fraction": retained / len(task_loo),
            "dominant_task": dominant_task,
            "dominant_task_deletion_retained": dominant_retained,
        },
        "G4_yield_is_primary_mechanism": {
            "pass": (
                pair_hhi_decomp["total_delta"] > 0
                and tv_decomp["total_delta"] > 0
                and pair_hhi_decomp["opportunity_yield_fraction_of_positive_delta"] >= 0.5
                and tv_decomp["opportunity_yield_fraction_of_positive_delta"] >= 0.5
            ),
            "required": "yield_fraction_at_least_0.5_for_pair_hhi_and_run_to_pair_tv",
            "pair_hhi_yield_fraction": pair_hhi_decomp[
                "opportunity_yield_fraction_of_positive_delta"
            ],
            "run_to_pair_tv_yield_fraction": tv_decomp[
                "opportunity_yield_fraction_of_positive_delta"
            ],
        },
    }
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "snapshot_sha256": expected_snapshot,
        "known_before_protocol_freeze": {
            "first240_to_current_endpoint_inversion_already_known": True,
            "trajectory_decomposition_and_deletion_results_known": False,
            "analysis_is_descriptive_not_a_preregistered_predictor_effect_test": True,
        },
        "inputs": {
            **receipts["input_hashes"],
            "protocol_spec_sha256": expected_protocol_spec_sha256,
        },
        "reproducibility": {
            "source_commit": source_commit,
            "source_sha256": sha256_file(Path(__file__)),
            "python_version": platform.python_version(),
            "randomness_used": False,
            "milestones": list(MILESTONES),
            "baseline_runs": BASELINE_RUNS,
            "late_checkpoints": list(LATE_CHECKPOINTS),
        },
        "milestones": milestone_rows,
        "full_prefix_trajectory": trajectory,
        "baseline_first240": compact_scope(baseline),
        "current_prefix": compact_scope(current),
        "current_task_yield_table": task_table(baseline, current),
        "mechanism_decomposition": mechanism,
        "leave_one_added_drop_out": drop_loo,
        "leave_one_task_out": task_loo,
        "claim_gates": gates,
        "interpretation_contract": {
            "all_gates_passed": all(gate["pass"] for gate in gates.values()),
            "inverse_hhi_is_statistical_effective_sample_size": False,
            "raw_pair_count_is_independent_sample_size": False,
            "predictor_accuracy_claim": False,
            "method_superiority_claim": False,
            "search_utility_claim": False,
        },
        "security": {
            "opened_basenames": [
                "SHA256SUMS",
                "summary.json",
                "provisional_first960_runs.jsonl",
                "intake_registry.jsonl",
                "source_provenance.json",
                "eligible_structural_pairs.jsonl",
            ],
            "eligible_blind_manifest_opened": False,
            "label_vault_opened": False,
            "outcome_grade_winner_orientation_opened": False,
            "score_or_prediction_values_opened": False,
            "raw_archive_or_journal_bytes_opened": False,
            "gpu_calls": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise TrajectoryError("refusing to overwrite output")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise TrajectoryError("output parent is absent or unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--expect-snapshot-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--protocol-spec", required=True, type=Path)
    parser.add_argument("--expect-protocol-spec-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_result(
            args.snapshot_root.resolve(),
            args.expect_snapshot_sha256,
            args.source_commit,
            args.protocol_spec.resolve(),
            args.expect_protocol_spec_sha256,
        )
        write_new(args.output.resolve(), result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "runs": result["current_prefix"]["inventory"]["runs"],
                    "pairs": result["current_prefix"]["inventory"]["structural_pairs"],
                    "claim_gates": {
                        key: value["pass"] for key, value in result["claim_gates"].items()
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (TrajectoryError, OSError, ValueError, ZeroDivisionError) as exc:
        print(f"STRUCTURAL_WEIGHT_TRAJECTORY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
