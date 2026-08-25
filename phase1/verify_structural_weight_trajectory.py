#!/usr/bin/env python3
"""Independently verify the outcome-blind structural-weight trajectory artifact.

This module intentionally does not import the producer implementation.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any


EXPECTED_PROTOCOL = "prospective_structural_weight_trajectory_v1"
EXPECTED_STATUS = "OUTCOME_BLIND_STRUCTURAL_WEIGHT_TRAJECTORY_READY"
MILESTONES = [120, 160, 200, 240, 260, 280, 300, 320, 339]
LATE = [260, 280, 300, 320, 339]
BASELINE = 240
HEX = frozenset("0123456789abcdef")


class VerificationError(RuntimeError):
    """Raised when independent reconstruction disagrees with the artifact."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_bytes(path: Path, expected: str | None = None) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"unsafe or absent input: {path.name}")
    raw = path.read_bytes()
    if expected is not None and digest(raw) != expected:
        raise VerificationError(f"hash mismatch: {path.name}")
    return raw


def object_file(path: Path, expected: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(file_bytes(path, expected))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"JSON object required: {path.name}")
    return value


def rows_file(path: Path, expected: str) -> list[dict[str, Any]]:
    try:
        lines = file_bytes(path, expected).decode("utf-8").splitlines()
        values = [json.loads(line) for line in lines if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSONL: {path.name}") from exc
    if any(not isinstance(value, dict) for value in values):
        raise VerificationError(f"JSONL object rows required: {path.name}")
    return values


def is_hash(value: Any, length: int = 64) -> bool:
    return isinstance(value, str) and len(value) == length and set(value) <= HEX


def assert_close(expected: Any, observed: Any, label: str) -> None:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if expected != observed:
            raise VerificationError(f"mismatch at {label}")
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(observed, (int, float)) or isinstance(observed, bool):
            raise VerificationError(f"numeric type mismatch at {label}")
        if isinstance(expected, int) and isinstance(observed, int):
            if expected != observed:
                raise VerificationError(f"integer mismatch at {label}")
        elif not math.isclose(float(expected), float(observed), rel_tol=1e-12, abs_tol=1e-12):
            raise VerificationError(f"numeric mismatch at {label}: {expected} != {observed}")
        return
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise VerificationError(f"list mismatch at {label}")
        for index, (left, right) in enumerate(zip(expected, observed)):
            assert_close(left, right, f"{label}[{index}]")
        return
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise VerificationError(f"object keys mismatch at {label}")
        for key in sorted(expected):
            assert_close(expected[key], observed[key], f"{label}.{key}")
        return
    raise VerificationError(f"unsupported comparison type at {label}")


def inspect_inputs(root: Path, artifact: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    snapshot = artifact["snapshot_sha256"]
    if root.is_symlink() or not root.is_dir() or root.name != snapshot or not is_hash(snapshot):
        raise VerificationError("snapshot root identity mismatch")
    manifest_raw = file_bytes(root / "SHA256SUMS", snapshot)
    manifest: dict[str, str] = {}
    for line in manifest_raw.decode("utf-8").splitlines():
        checksum, relative = line.split(maxsplit=1)
        manifest[relative.lstrip("* ").replace("\\", "/")] = checksum
    inputs = artifact.get("inputs")
    if not isinstance(inputs, dict):
        raise VerificationError("artifact input bindings missing")
    required = {
        "accumulator/summary.json": inputs.get("accumulator_summary_sha256"),
        "accumulator/provisional_first960_runs.jsonl": inputs.get(
            "provisional_first960_runs_sha256"
        ),
        "intake_registry.jsonl": inputs.get("intake_registry_sha256"),
    }
    for relative, expected in required.items():
        if not is_hash(expected) or manifest.get(relative) != expected:
            raise VerificationError(f"snapshot binding mismatch: {relative}")
        file_bytes(root / relative, expected)
    accumulator = object_file(root / "accumulator" / "summary.json", required["accumulator/summary.json"])
    security = accumulator.get("security")
    if (
        accumulator.get("protocol") != "prospective_accumulator_v1"
        or not isinstance(security, dict)
        or security.get("label_vault_opened") is not False
        or security.get("outcome_files_opened") != []
        or security.get("scorer_prediction_files_opened") != []
    ):
        raise VerificationError("accumulator blindness contract failed")
    runs = rows_file(
        root / "accumulator" / "provisional_first960_runs.jsonl",
        required["accumulator/provisional_first960_runs.jsonl"],
    )
    registry = rows_file(root / "intake_registry.jsonl", required["intake_registry.jsonl"])
    if len(runs) != 339:
        raise VerificationError("frozen trajectory verifier expects exactly 339 runs")
    if len(registry) != accumulator.get("inventory", {}).get("drops"):
        raise VerificationError("drop count mismatch")

    state_root = root.parents[1].resolve()
    intake_bindings = inputs.get("intakes")
    if not isinstance(intake_bindings, dict):
        raise VerificationError("intake hash map missing")
    records: dict[str, dict[str, Any]] = {}
    pair_identities: set[tuple[str, str, str, str, str]] = set()
    pair_parents: dict[str, set[str]] = collections.defaultdict(set)
    pair_counts: collections.Counter[str] = collections.Counter()
    seen_drops: set[str] = set()
    for entry in registry:
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise VerificationError("registry row schema mismatch")
        drop = entry["drop_id"]
        if drop in seen_drops or drop not in intake_bindings:
            raise VerificationError("duplicate or unbound drop")
        seen_drops.add(drop)
        directory = Path(entry["intake_dir"])
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or directory.resolve().parent != (state_root / "intakes").resolve()
        ):
            raise VerificationError("unsafe intake directory")
        binding = intake_bindings[drop]
        if entry["summary_sha256"] != binding.get("summary_sha256"):
            raise VerificationError("intake summary binding mismatch")
        summary = object_file(directory / "summary.json", entry["summary_sha256"])
        if (
            summary.get("protocol") != "prospective_drop_intake_v1"
            or summary.get("blindness", {}).get("label_values_printed") is not False
            or summary.get("blindness", {}).get("metrics_computed") != []
        ):
            raise VerificationError("intake blindness contract failed")
        provenance_sha = binding.get("source_provenance_sha256")
        pairs_sha = binding.get("eligible_structural_pairs_sha256")
        if (
            summary.get("outputs", {}).get("source_provenance_sha256") != provenance_sha
            or summary.get("outputs", {}).get("eligible_structural_pairs_sha256") != pairs_sha
        ):
            raise VerificationError("intake structural binding mismatch")
        provenance = json.loads(file_bytes(directory / "source_provenance.json", provenance_sha))
        pairs = rows_file(directory / "eligible_structural_pairs.jsonl", pairs_sha)
        eligible_here: set[str] = set()
        for row in provenance:
            if row.get("eligible") is not True:
                continue
            run_id = row.get("run_id")
            if run_id in records:
                raise VerificationError("eligible run repeated")
            records[run_id] = {
                "task": row["task"],
                "endpoints": row["endpoints"],
                "drop_id": drop,
                "generation_started_at_utc": row["generation_started_at_utc"],
                "source_sha256": row["journal_sha256"],
            }
            eligible_here.add(run_id)
        for pair in pairs:
            identity = tuple(pair[key] for key in ("task", "run_id", "parent", "left", "right"))
            if identity in pair_identities or pair["run_id"] not in eligible_here:
                raise VerificationError("invalid or duplicate eligible pair")
            pair_identities.add(identity)
            pair_counts[pair["run_id"]] += 1
            pair_parents[pair["run_id"]].add(pair["parent"])
    if set(intake_bindings) != seen_drops:
        raise VerificationError("artifact binds an unused intake")

    previous: tuple[str, str, str] | None = None
    selected = set()
    for row in runs:
        run_id = row["run_id"]
        source = row["source_sha256"]
        key = (row["generation_started_at_utc"], source, run_id)
        if run_id in selected or previous is not None and key < previous:
            raise VerificationError("run order or uniqueness failure")
        if run_id not in records:
            raise VerificationError("selected run absent from provenance")
        record = records[run_id]
        expected_identity = {
            "task": row["task"],
            "endpoints": row["endpoints"],
            "drop_id": row["drop_id"],
            "generation_started_at_utc": row["generation_started_at_utc"],
            "source_sha256": source,
        }
        if record != expected_identity:
            raise VerificationError("selected run identity mismatch")
        record["pairs"] = pair_counts[run_id]
        record["parents"] = len(pair_parents[run_id])
        previous = key
        selected.add(run_id)
    return runs, records


def concentration(values: dict[str, int]) -> dict[str, Any] | None:
    names = [name for name in sorted(values) if values[name] > 0]
    total = sum(values[name] for name in names)
    if not total:
        return None
    shares = [values[name] / total for name in names]
    hhi = sum(share**2 for share in shares)
    entropy = -sum(share * math.log(share) for share in shares)
    ordered = sorted(values[name] for name in names)
    n = len(ordered)
    gini = sum((2 * rank - n - 1) * count for rank, count in enumerate(ordered, 1)) / (
        n * total
    )
    maximum = max(values[name] for name in names)
    return {
        "positive_tasks": n,
        "total_weight": total,
        "maximum_share": maximum / total,
        "dominant_tasks": [name for name in names if values[name] == maximum],
        "top3_share": sum(sorted(shares, reverse=True)[:3]),
        "hhi": hhi,
        "inverse_hhi_descriptive_diversity": 1 / hhi,
        "shannon_entropy": entropy,
        "exponential_shannon_descriptive_diversity": math.exp(entropy),
        "gini": gini,
    }


def proportions(values: dict[str, int], names: list[str]) -> dict[str, float] | None:
    total = sum(values.get(name, 0) for name in names)
    return {name: values.get(name, 0) / total for name in names} if total else None


def tv(left: dict[str, float], right: dict[str, float]) -> float:
    return sum(abs(left.get(name, 0) - right.get(name, 0)) for name in sorted(set(left) | set(right))) / 2


def summarize(rows: list[dict[str, Any]], records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    counters = {name: collections.Counter() for name in ("runs", "endpoints", "decision_parents", "structural_pairs")}
    decision_runs = 0
    for row in rows:
        record = records[row["run_id"]]
        task = record["task"]
        counters["runs"][task] += 1
        counters["endpoints"][task] += record["endpoints"]
        counters["decision_parents"][task] += record["parents"]
        counters["structural_pairs"][task] += record["pairs"]
        decision_runs += record["pairs"] > 0
    names = sorted(counters["runs"])
    distributions = {name: proportions(counters[name], names) for name in counters}
    run_dist = distributions["runs"]
    return {
        "inventory": {
            "runs": len(rows),
            "tasks": len(names),
            "endpoints": sum(counters["endpoints"].values()),
            "decision_parents": sum(counters["decision_parents"].values()),
            "structural_pairs": sum(counters["structural_pairs"].values()),
            "finite_decision_runs": decision_runs,
            "pair_tasks": sum(count > 0 for count in counters["structural_pairs"].values()),
        },
        "concentration": {name: concentration(dict(counters[name])) for name in counters},
        "weighting_shift_tv": {
            f"runs_to_{name}": tv(run_dist, distributions[name]) if distributions[name] else None
            for name in ("endpoints", "decision_parents", "structural_pairs")
        },
        "counts": {name: {task: counters[name][task] for task in names} for name in counters},
    }


def compact(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in ("inventory", "concentration", "weighting_shift_tv")}


def product_distribution(run: dict[str, int], yields: dict[str, float], names: list[str]) -> dict[str, float]:
    weights = {name: run.get(name, 0) * yields[name] for name in names}
    total = sum(weights.values())
    return {name: weights[name] / total for name in names}


def run_distribution(run: dict[str, int], names: list[str]) -> dict[str, float]:
    total = sum(run.get(name, 0) for name in names)
    return {name: run.get(name, 0) / total for name in names}


def decompose(base: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    r0, r1 = base["counts"]["runs"], current["counts"]["runs"]
    p0, p1 = base["counts"]["structural_pairs"], current["counts"]["structural_pairs"]
    names = sorted(set(r0) | set(r1))
    y1 = {name: p1.get(name, 0) / r1[name] for name in names}
    y0 = {name: p0.get(name, 0) / r0[name] if r0.get(name, 0) else y1[name] for name in names}

    def four(metric):
        values = {
            "m00": metric(r0, y0),
            "m10": metric(r1, y0),
            "m01": metric(r0, y1),
            "m11": metric(r1, y1),
        }
        composition = ((values["m10"] - values["m00"]) + (values["m11"] - values["m01"])) / 2
        yield_part = ((values["m01"] - values["m00"]) + (values["m11"] - values["m10"])) / 2
        delta = values["m11"] - values["m00"]
        return {
            "baseline": values["m00"],
            "current": values["m11"],
            "total_delta": delta,
            "run_composition_contribution": composition,
            "opportunity_yield_contribution": yield_part,
            "opportunity_yield_fraction_of_positive_delta": yield_part / delta if delta > 0 else None,
            "additivity_residual": delta - composition - yield_part,
            "path_values": values,
            "new_task_baseline_yield_convention": "current_observed_yield",
        }

    def hhi_metric(run, yields):
        values = product_distribution(run, yields, names)
        return sum(values[name] ** 2 for name in names)

    def tv_metric(run, yields):
        return tv(run_distribution(run, names), product_distribution(run, yields, names))

    midpoint = []
    for name in names:
        delta = p1.get(name, 0) - p0.get(name, 0)
        composition = (r1.get(name, 0) - r0.get(name, 0)) * (y0[name] + y1[name]) / 2
        yield_part = (y1[name] - y0[name]) * (r0.get(name, 0) + r1.get(name, 0)) / 2
        midpoint.append(
            {
                "task": name,
                "pair_count_delta": delta,
                "run_composition_count_contribution": composition,
                "opportunity_yield_count_contribution": yield_part,
                "additivity_residual": delta - composition - yield_part,
            }
        )
    return {
        "pair_hhi": four(hhi_metric),
        "run_to_pair_total_variation": four(tv_metric),
        "midpoint_pair_count_by_task": midpoint,
    }


def task_yields(base: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    names = sorted(set(base["counts"]["runs"]) | set(current["counts"]["runs"]))
    total_runs = sum(current["counts"]["runs"].values())
    total_pairs = sum(current["counts"]["structural_pairs"].values())
    output = []
    for name in names:
        row: dict[str, Any] = {"task": name}
        for label, scope in (("baseline", base), ("current", current)):
            r = scope["counts"]["runs"].get(name, 0)
            e = scope["counts"]["endpoints"].get(name, 0)
            d = scope["counts"]["decision_parents"].get(name, 0)
            p = scope["counts"]["structural_pairs"].get(name, 0)
            row[label] = {
                "runs": r,
                "endpoints": e,
                "decision_parents": d,
                "structural_pairs": p,
                "endpoints_per_run": e / r if r else None,
                "decision_parents_per_run": d / r if r else None,
                "pairs_per_run": p / r if r else None,
            }
        run_share = current["counts"]["runs"].get(name, 0) / total_runs
        pair_share = current["counts"]["structural_pairs"].get(name, 0) / total_pairs
        row["current_pair_share_over_run_share"] = pair_share / run_share
        output.append(row)
    return output


def reconstruct_claim_sections(
    runs: list[dict[str, Any]], records: dict[str, dict[str, Any]], scopes: dict[int, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    base, current = scopes[BASELINE], scopes[len(runs)]
    base_run_hhi = base["concentration"]["runs"]["hhi"]
    base_pair_hhi = base["concentration"]["structural_pairs"]["hhi"]
    current_pair_hhi = current["concentration"]["structural_pairs"]["hhi"]
    pair_delta = current_pair_hhi - base_pair_hhi
    late = []
    for n in LATE:
        point = scopes[n]
        late.append(
            {
                "prefix_runs": n,
                "inversion_vs_first240": point["concentration"]["runs"]["hhi"] <= base_run_hhi
                and point["concentration"]["structural_pairs"]["hhi"] > base_pair_hhi,
            }
        )
    additions = runs[BASELINE:]
    drop_rows = []
    for drop in sorted({row["drop_id"] for row in additions}):
        kept = runs[:BASELINE] + [row for row in additions if row["drop_id"] != drop]
        value = summarize(kept, records)
        hhi = value["concentration"]["structural_pairs"]["hhi"]
        drop_rows.append(
            {
                "drop_id": drop,
                "removed_added_runs": sum(row["drop_id"] == drop for row in additions),
                "remaining_runs": len(kept),
                "run_hhi_delta_vs_first240": value["concentration"]["runs"]["hhi"] - base_run_hhi,
                "pair_hhi_delta_vs_first240": hhi - base_pair_hhi,
                "attribution_fraction_of_positive_pair_hhi_delta": (
                    (current_pair_hhi - hhi) / pair_delta if pair_delta > 0 else None
                ),
            }
        )
    maximum_drop = max(
        [max(0.0, row["attribution_fraction_of_positive_pair_hhi_delta"]) for row in drop_rows]
        or [0.0]
    )
    dominant = current["concentration"]["structural_pairs"]["dominant_tasks"]
    if len(dominant) != 1:
        raise VerificationError("pair-dominant task tie")
    dominant_task = dominant[0]
    task_rows = []
    for task in sorted(current["counts"]["runs"]):
        base_value = summarize([row for row in runs[:BASELINE] if row["task"] != task], records)
        current_value = summarize([row for row in runs if row["task"] != task], records)
        run_delta = current_value["concentration"]["runs"]["hhi"] - base_value["concentration"]["runs"]["hhi"]
        loo_pair_delta = current_value["concentration"]["structural_pairs"]["hhi"] - base_value["concentration"]["structural_pairs"]["hhi"]
        task_rows.append(
            {
                "removed_task": task,
                "is_current_pair_dominant_task": task == dominant_task,
                "run_hhi_delta": run_delta,
                "pair_hhi_delta": loo_pair_delta,
                "inversion_retained": run_delta <= 0 and loo_pair_delta > 0,
            }
        )
    mechanism = decompose(base, current)
    retained = sum(row["inversion_retained"] for row in task_rows)
    dominant_retained = next(
        row["inversion_retained"] for row in task_rows if row["is_current_pair_dominant_task"]
    )
    pair_decomp = mechanism["pair_hhi"]
    tv_decomp = mechanism["run_to_pair_total_variation"]
    gates = {
        "G1_temporal_persistence": {
            "pass": sum(row["inversion_vs_first240"] for row in late) >= 4,
            "required": "at_least_4_of_5_late_checkpoints",
            "observed": sum(row["inversion_vs_first240"] for row in late),
            "checkpoints": late,
        },
        "G2_no_single_drop_artifact": {
            "pass": pair_delta > 0 and maximum_drop < 0.5,
            "required": "maximum_positive_single_drop_attribution_below_0.5",
            "observed": maximum_drop,
        },
        "G3_single_task_robustness": {
            "pass": retained / len(task_rows) >= 0.8 and dominant_retained,
            "required": "at_least_80_percent_task_deletions_and_dominant_task_deletion_retain_inversion",
            "retained": retained,
            "total": len(task_rows),
            "fraction": retained / len(task_rows),
            "dominant_task": dominant_task,
            "dominant_task_deletion_retained": dominant_retained,
        },
        "G4_yield_is_primary_mechanism": {
            "pass": pair_decomp["total_delta"] > 0
            and tv_decomp["total_delta"] > 0
            and pair_decomp["opportunity_yield_fraction_of_positive_delta"] >= 0.5
            and tv_decomp["opportunity_yield_fraction_of_positive_delta"] >= 0.5,
            "required": "yield_fraction_at_least_0.5_for_pair_hhi_and_run_to_pair_tv",
            "pair_hhi_yield_fraction": pair_decomp["opportunity_yield_fraction_of_positive_delta"],
            "run_to_pair_tv_yield_fraction": tv_decomp["opportunity_yield_fraction_of_positive_delta"],
        },
    }
    return drop_rows, task_rows, mechanism, gates


def verify(
    snapshot_root: Path,
    artifact_path: Path,
    expected_artifact_sha256: str,
    producer_source: Path,
    expected_producer_source_sha256: str,
    protocol_spec: Path,
    expected_protocol_spec_sha256: str,
) -> dict[str, Any]:
    artifact_raw = file_bytes(artifact_path, expected_artifact_sha256)
    artifact = json.loads(artifact_raw)
    if artifact.get("protocol") != EXPECTED_PROTOCOL or artifact.get("status") != EXPECTED_STATUS:
        raise VerificationError("artifact protocol or status mismatch")
    file_bytes(producer_source, expected_producer_source_sha256)
    file_bytes(protocol_spec, expected_protocol_spec_sha256)
    if (
        artifact.get("reproducibility", {}).get("source_sha256")
        != expected_producer_source_sha256
        or artifact.get("inputs", {}).get("protocol_spec_sha256")
        != expected_protocol_spec_sha256
    ):
        raise VerificationError("source or protocol binding mismatch")
    runs, records = inspect_inputs(snapshot_root, artifact)
    scopes = {index: summarize(runs[:index], records) for index in range(1, len(runs) + 1)}
    expected_trajectory = [
        {"prefix_runs": index, **compact(scopes[index])} for index in range(1, len(runs) + 1)
    ]
    expected_milestones = [
        {"prefix_runs": index, **compact(scopes[index])} for index in MILESTONES
    ]
    drop_rows, task_rows, mechanism, gates = reconstruct_claim_sections(runs, records, scopes)
    assert_close(expected_trajectory, artifact.get("full_prefix_trajectory"), "full_prefix_trajectory")
    assert_close(expected_milestones, artifact.get("milestones"), "milestones")
    assert_close(compact(scopes[BASELINE]), artifact.get("baseline_first240"), "baseline_first240")
    assert_close(compact(scopes[len(runs)]), artifact.get("current_prefix"), "current_prefix")
    assert_close(task_yields(scopes[BASELINE], scopes[len(runs)]), artifact.get("current_task_yield_table"), "current_task_yield_table")
    assert_close(mechanism, artifact.get("mechanism_decomposition"), "mechanism_decomposition")
    assert_close(drop_rows, artifact.get("leave_one_added_drop_out"), "leave_one_added_drop_out")
    assert_close(task_rows, artifact.get("leave_one_task_out"), "leave_one_task_out")
    assert_close(gates, artifact.get("claim_gates"), "claim_gates")
    expected_security = {
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
    }
    assert_close(expected_security, artifact.get("security"), "security")
    return {
        "protocol": "independent_prospective_structural_weight_trajectory_v1",
        "status": "INDEPENDENT_STRUCTURAL_WEIGHT_TRAJECTORY_PASS",
        "trajectory_sha256": expected_artifact_sha256,
        "producer_source_sha256": expected_producer_source_sha256,
        "protocol_spec_sha256": expected_protocol_spec_sha256,
        "snapshot_sha256": artifact["snapshot_sha256"],
        "checks": {
            "snapshot_and_intake_hashes_reopened": True,
            "all_339_prefixes_recomputed": True,
            "all_milestones_recomputed": True,
            "task_yields_recomputed": True,
            "shapley_and_midpoint_decompositions_recomputed": True,
            "drop_and_task_deletions_recomputed": True,
            "all_claim_gates_recomputed": True,
            "security_contract_exact": True,
        },
        "recomputed_key_findings": {
            "runs": len(runs),
            "pairs": scopes[len(runs)]["inventory"]["structural_pairs"],
            "claim_gates": {name: value["pass"] for name, value in gates.items()},
        },
        "security": {
            "label_outcome_prediction_or_raw_archive_opened": False,
            "gpu_or_api_calls": 0,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise VerificationError("unsafe verification output path")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--expect-trajectory-sha256", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--expect-producer-source-sha256", required=True)
    parser.add_argument("--protocol-spec", required=True, type=Path)
    parser.add_argument("--expect-protocol-spec-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            args.snapshot_root.resolve(),
            args.trajectory.resolve(),
            args.expect_trajectory_sha256,
            args.producer_source.resolve(),
            args.expect_producer_source_sha256,
            args.protocol_spec.resolve(),
            args.expect_protocol_spec_sha256,
        )
        write_new(args.output.resolve(), result)
        print(json.dumps(result["recomputed_key_findings"], sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, ValueError, ZeroDivisionError) as exc:
        print(f"STRUCTURAL_WEIGHT_TRAJECTORY_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
