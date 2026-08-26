"""Outcome-blind lexical overlap audit from v11 train endpoints to first-960."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from phase1 import audit_prospective_fuzzy_code_clones as fuzzy
from phase1 import historical_train_future_overlap_schema as schema
from phase1 import prospective_fuzzy_clone_schema as fuzzy_schema


class OverlapAuditError(RuntimeError):
    """Raised when a frozen input, blindness, or reproduction gate fails."""


def require_dependency_contract() -> None:
    """Fail closed if the reused tokenizer/shingler drifts from this preregistration."""

    observed = (
        fuzzy_schema.SHINGLE_SIZE,
        fuzzy_schema.SHINGLE_HASH_BITS,
        fuzzy_schema.MIN_DISTINCT_SHINGLES,
        fuzzy_schema.PRIMARY_JACCARD_NUMERATOR,
        fuzzy_schema.PRIMARY_JACCARD_DENOMINATOR,
        fuzzy_schema.STRICT_JACCARD_NUMERATOR,
        fuzzy_schema.STRICT_JACCARD_DENOMINATOR,
    )
    expected = (
        schema.SHINGLE_SIZE,
        schema.SHINGLE_HASH_BITS,
        schema.MIN_DISTINCT_SHINGLES,
        schema.PRIMARY_NUMERATOR,
        schema.PRIMARY_DENOMINATOR,
        schema.STRICT_NUMERATOR,
        schema.STRICT_DENOMINATOR,
    )
    if observed != expected:
        raise OverlapAuditError("fuzzy dependency contract drift")


@dataclass(frozen=True)
class Record:
    card_id: str
    run_id: str
    task: str
    shingles: frozenset[int]


@dataclass(frozen=True)
class Edge:
    historical: int
    prospective: int
    intersection: int
    union: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_lf_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise OverlapAuditError(
                    f"invalid JSONL: {path.name}:{line_number}"
                ) from error
            if not isinstance(value, dict):
                raise OverlapAuditError(f"non-object JSONL: {path.name}:{line_number}")
            yield value


def load_historical_train(repo_root: Path) -> tuple[list[fuzzy.CodeRecord], dict[str, Any]]:
    endpoint_identity: dict[str, tuple[str, str]] = {}
    runs: set[str] = set()
    tasks: set[str] = set()
    parents: set[str] = set()
    total_rows = 0
    pair_hashes: dict[str, str] = {}
    pair_rows: dict[str, int] = {}

    for relative, expected_sha, expected_rows in schema.HISTORICAL_PAIR_FILES:
        path = repo_root / relative
        actual_sha = normalized_lf_sha256(path)
        if actual_sha != expected_sha:
            raise OverlapAuditError(f"historical pair SHA mismatch: {relative}")
        rows = 0
        for row in read_jsonl(path):
            required = {"better", "worse", "run_id", "task", "parent"}
            if not required.issubset(row):
                raise OverlapAuditError(f"historical pair schema mismatch: {relative}")
            run_id = row["run_id"]
            task = row["task"]
            parent = row["parent"]
            if not all(isinstance(value, str) for value in (run_id, task, parent)):
                raise OverlapAuditError("historical identity type mismatch")
            for key in ("better", "worse"):
                card_id = row[key]
                if not isinstance(card_id, str):
                    raise OverlapAuditError("historical endpoint type mismatch")
                previous = endpoint_identity.setdefault(card_id, (run_id, task))
                if previous != (run_id, task):
                    raise OverlapAuditError("historical endpoint identity conflict")
            runs.add(run_id)
            tasks.add(task)
            parents.add(parent)
            rows += 1
            total_rows += 1
        if rows != expected_rows:
            raise OverlapAuditError(f"historical pair row mismatch: {relative}")
        pair_hashes[relative] = actual_sha
        pair_rows[relative] = rows

    expected_counts = (
        schema.HISTORICAL_UNION_ROWS,
        schema.HISTORICAL_UNION_ENDPOINTS,
        schema.HISTORICAL_UNION_RUNS,
        schema.HISTORICAL_UNION_TASKS,
        schema.HISTORICAL_UNION_PARENTS,
    )
    observed_counts = (
        total_rows,
        len(endpoint_identity),
        len(runs),
        len(tasks),
        len(parents),
    )
    if observed_counts != expected_counts:
        raise OverlapAuditError("historical train union count mismatch")

    cards_path = repo_root / schema.HISTORICAL_CARDS_PATH
    if sha256_file(cards_path) != schema.HISTORICAL_CARDS_SHA256:
        raise OverlapAuditError("historical cards SHA mismatch")
    selected: dict[str, fuzzy.CodeRecord] = {}
    seen_card_ids: set[str] = set()
    for row in read_jsonl(cards_path):
        card_id = row.get("id")
        if not isinstance(card_id, str) or card_id in seen_card_ids:
            raise OverlapAuditError("historical cards ID mismatch")
        seen_card_ids.add(card_id)
        if card_id not in endpoint_identity:
            continue
        task = row.get("task")
        if not isinstance(task, dict) or not isinstance(task.get("name"), str):
            raise OverlapAuditError("historical task schema mismatch")
        run_id = row.get("run_id")
        code = row.get("code")
        if not isinstance(run_id, str) or not isinstance(code, str):
            raise OverlapAuditError("historical card code/run mismatch")
        if endpoint_identity[card_id] != (run_id, task["name"]):
            raise OverlapAuditError("historical pair/card identity mismatch")
        selected[card_id] = fuzzy.CodeRecord(card_id, run_id, task["name"], "", code)
    if set(selected) != set(endpoint_identity):
        raise OverlapAuditError("historical train endpoints missing from cards")
    return [selected[key] for key in sorted(selected)], {
        "cards_path": schema.HISTORICAL_CARDS_PATH,
        "cards_sha256": schema.HISTORICAL_CARDS_SHA256,
        "pair_normalized_lf_sha256": pair_hashes,
        "pair_rows": pair_rows,
        "union_rows": total_rows,
        "union_endpoints": len(endpoint_identity),
        "union_runs": len(runs),
        "union_tasks": len(tasks),
        "union_parents": len(parents),
        "historical_label_or_observation_fields_used": False,
    }


def fingerprint(records: list[fuzzy.CodeRecord]) -> tuple[list[Record], dict[str, Any]]:
    values: list[Record] = []
    token_failures = 0
    too_short = 0
    for record in records:
        tokens = fuzzy.normalized_tokens(record.code)
        if tokens is None:
            token_failures += 1
            continue
        shingle_values = fuzzy.shingles_from_tokens(tokens)
        if shingle_values is None:
            too_short += 1
            continue
        values.append(Record(record.card_id, record.run_id, record.task, shingle_values))
    return values, {
        "input_endpoints": len(records),
        "fingerprinted_endpoints": len(values),
        "tokenization_failures": token_failures,
        "too_short_or_low_distinct_shingles": too_short,
        "coverage": len(values) / len(records) if records else None,
    }


def prefix(values: frozenset[int], frequency: collections.Counter[int]) -> list[int]:
    ordered = sorted(values, key=lambda item: (frequency[item], item))
    required = math.ceil(schema.PRIMARY_NUMERATOR * len(ordered) / schema.PRIMARY_DENOMINATOR)
    return ordered[: len(ordered) - required + 1]


def bipartite_join(
    historical: list[Record], prospective: list[Record]
) -> tuple[list[Edge], int]:
    frequency: collections.Counter[int] = collections.Counter()
    for record in historical:
        frequency.update(record.shingles)
    for record in prospective:
        frequency.update(record.shingles)
    index: dict[int, list[int]] = collections.defaultdict(list)
    for historical_index, record in enumerate(historical):
        for value in prefix(record.shingles, frequency):
            index[value].append(historical_index)
    candidates: set[int] = set()
    for prospective_index, record in enumerate(prospective):
        for value in prefix(record.shingles, frequency):
            for historical_index in index[value]:
                historical_size = len(historical[historical_index].shingles)
                prospective_size = len(record.shingles)
                shorter, longer = sorted((historical_size, prospective_size))
                if schema.PRIMARY_DENOMINATOR * shorter < schema.PRIMARY_NUMERATOR * longer:
                    continue
                candidates.add((historical_index << 32) | prospective_index)
    edges = []
    for packed in sorted(candidates):
        historical_index = packed >> 32
        prospective_index = packed & 0xFFFFFFFF
        left = historical[historical_index].shingles
        right = prospective[prospective_index].shingles
        intersection = len(left & right)
        union = len(left) + len(right) - intersection
        if fuzzy.threshold_passes(
            intersection,
            union,
            schema.PRIMARY_NUMERATOR,
            schema.PRIMARY_DENOMINATOR,
        ):
            edges.append(Edge(historical_index, prospective_index, intersection, union))
    return edges, len(candidates)


def brute_force(historical: list[Record], prospective: list[Record]) -> list[Edge]:
    edges = []
    for historical_index, historical_record in enumerate(historical):
        for prospective_index, prospective_record in enumerate(prospective):
            intersection = len(historical_record.shingles & prospective_record.shingles)
            union = (
                len(historical_record.shingles)
                + len(prospective_record.shingles)
                - intersection
            )
            if fuzzy.threshold_passes(
                intersection,
                union,
                schema.PRIMARY_NUMERATOR,
                schema.PRIMARY_DENOMINATOR,
            ):
                edges.append(Edge(historical_index, prospective_index, intersection, union))
    return edges


def edge_signature(edges: list[Edge]) -> str:
    rows = sorted(
        f"{edge.historical}:{edge.prospective}:{edge.intersection}:{edge.union}"
        for edge in edges
    )
    return sha256_text("\n".join(rows))


def aggregate(
    historical: list[Record], prospective: list[Record], edges: list[Edge]
) -> dict[str, Any]:
    historical_members: set[int] = set()
    prospective_members: set[int] = set()
    cross_task_historical: set[int] = set()
    cross_task_prospective: set[int] = set()
    same_task_pairs = 0
    cross_task_pairs = 0
    digest_rows = []
    total_nodes = len(historical) + len(prospective)
    parent = list(range(total_nodes))
    size = [1] * total_nodes

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left == right:
            return
        if size[left] < size[right]:
            left, right = right, left
        parent[right] = left
        size[left] += size[right]

    for edge in edges:
        left = historical[edge.historical]
        right = prospective[edge.prospective]
        historical_members.add(edge.historical)
        prospective_members.add(edge.prospective)
        if left.task == right.task:
            same_task_pairs += 1
        else:
            cross_task_pairs += 1
            cross_task_historical.add(edge.historical)
            cross_task_prospective.add(edge.prospective)
        union(edge.historical, len(historical) + edge.prospective)
        first, second = sorted((left.card_id, right.card_id))
        digest_rows.append(
            sha256_text(
                f"{first}\x00{second}\x00{edge.intersection}\x00{edge.union}"
            )
        )

    component_members: dict[int, set[int]] = collections.defaultdict(set)
    for index in historical_members:
        component_members[find(index)].add(index)
    for index in prospective_members:
        node = len(historical) + index
        component_members[find(node)].add(node)
    component_rows = []
    for members in component_members.values():
        tasks = set()
        for node in members:
            if node < len(historical):
                tasks.add(historical[node].task)
            else:
                tasks.add(prospective[node - len(historical)].task)
        component_rows.append((len(members), len(tasks)))
    large_components = sum(
        endpoints >= schema.LARGE_COMPONENT_MIN_ENDPOINTS
        and tasks >= schema.LARGE_COMPONENT_MIN_TASKS
        for endpoints, tasks in component_rows
    )
    digest_payload = "\n".join(sorted(digest_rows))
    if digest_payload:
        digest_payload += "\n"
    return {
        "near_duplicate_pairs": len(edges),
        "same_task_pairs": same_task_pairs,
        "cross_task_pairs": cross_task_pairs,
        "historical_affected_endpoints": len(historical_members),
        "historical_affected_fraction": len(historical_members) / len(historical),
        "prospective_affected_endpoints": len(prospective_members),
        "prospective_affected_fraction": len(prospective_members) / len(prospective),
        "cross_task_historical_affected_endpoints": len(cross_task_historical),
        "cross_task_historical_affected_fraction": len(cross_task_historical)
        / len(historical),
        "cross_task_prospective_affected_endpoints": len(cross_task_prospective),
        "cross_task_prospective_affected_fraction": len(cross_task_prospective)
        / len(prospective),
        "components": len(component_rows),
        "largest_component_endpoints": max((row[0] for row in component_rows), default=0),
        "largest_component_tasks": max((row[1] for row in component_rows), default=0),
        "large_multitask_components": large_components,
        "edge_digest_sha256": sha256_text(digest_payload),
        "edge_identities_emitted": False,
    }


def audit(
    repo_root: Path,
    state_root: Path,
    snapshot_root: Path,
    source_commit: str,
) -> dict[str, Any]:
    require_dependency_contract()
    historical_code, historical_inputs = load_historical_train(repo_root)
    future_code, future_inputs = fuzzy.load_cohort(
        state_root, snapshot_root, schema.FROZEN_COHORT_RUN_TARGET
    )
    historical, historical_fingerprint = fingerprint(historical_code)
    prospective, prospective_fingerprint = fingerprint(future_code)
    if not historical or not prospective:
        raise OverlapAuditError("empty fingerprinted side")
    historical_runs = {record.run_id for record in historical_code}
    prospective_runs = {record.run_id for record in future_code}
    if historical_runs.intersection(prospective_runs):
        raise OverlapAuditError("historical and prospective physical runs overlap")

    primary_edges, candidates = bipartite_join(historical, prospective)
    strict_edges = [
        edge
        for edge in primary_edges
        if fuzzy.threshold_passes(
            edge.intersection,
            edge.union,
            schema.STRICT_NUMERATOR,
            schema.STRICT_DENOMINATOR,
        )
    ]
    primary = aggregate(historical, prospective, primary_edges)
    strict = aggregate(historical, prospective, strict_edges)

    historical_subset = sorted(
        historical, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    prospective_subset = sorted(
        prospective, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    subset_join, _ = bipartite_join(historical_subset, prospective_subset)
    subset_brute = brute_force(historical_subset, prospective_subset)
    self_check = edge_signature(subset_join) == edge_signature(subset_brute)

    gates = {
        "historical_fingerprint_coverage": historical_fingerprint["coverage"]
        >= schema.MIN_HISTORICAL_COVERAGE,
        "prospective_fingerprint_coverage": prospective_fingerprint["coverage"]
        >= schema.MIN_PROSPECTIVE_COVERAGE,
        "prospective_affected_fraction": primary["prospective_affected_fraction"]
        <= schema.MAX_PROSPECTIVE_AFFECTED_FRACTION,
        "cross_task_prospective_affected_fraction": primary[
            "cross_task_prospective_affected_fraction"
        ]
        <= schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION,
        "large_multitask_components": primary["large_multitask_components"]
        <= schema.MAX_LARGE_MULTITASK_COMPONENTS,
        "bipartite_join_self_check": self_check,
    }
    return {
        "protocol": schema.PROTOCOL,
        "status": "PROVISIONAL_HISTORICAL_TRAIN_FUTURE_OVERLAP_AUDIT_COMPLETE",
        "source_commit": source_commit,
        "source_sha256": sha256_file(Path(__file__)),
        "schema_sha256": sha256_file(Path(schema.__file__).resolve()),
        "fuzzy_dependency_sha256": sha256_file(Path(fuzzy.__file__).resolve()),
        "fuzzy_schema_dependency_sha256": sha256_file(
            Path(fuzzy_schema.__file__).resolve()
        ),
        "dependency_contract": {
            "shingle_size": schema.SHINGLE_SIZE,
            "shingle_hash_bits": schema.SHINGLE_HASH_BITS,
            "minimum_distinct_shingles": schema.MIN_DISTINCT_SHINGLES,
            "primary_jaccard": [schema.PRIMARY_NUMERATOR, schema.PRIMARY_DENOMINATOR],
            "strict_jaccard": [schema.STRICT_NUMERATOR, schema.STRICT_DENOMINATOR],
            "matched": True,
        },
        "snapshot_sha256": snapshot_root.resolve().name,
        "historical_scope": historical_inputs,
        "prospective_scope": {
            "target_runs": schema.FROZEN_COHORT_RUN_TARGET,
            "observed_runs": len(prospective_runs),
            "observed_endpoints": len(future_code),
            "closure_provided": False,
            "inputs": future_inputs,
        },
        "historical_fingerprinting": historical_fingerprint,
        "prospective_fingerprinting": prospective_fingerprint,
        "physical_run_sets_disjoint": True,
        "primary_jaccard_0_85": {
            "threshold_numerator": schema.PRIMARY_NUMERATOR,
            "threshold_denominator": schema.PRIMARY_DENOMINATOR,
            "candidate_pairs_exactly_checked": candidates,
            **primary,
        },
        "strict_jaccard_0_95": {
            "threshold_numerator": schema.STRICT_NUMERATOR,
            "threshold_denominator": schema.STRICT_DENOMINATOR,
            **strict,
        },
        "bipartite_join_self_check": {
            "historical_documents": len(historical_subset),
            "prospective_documents": len(prospective_subset),
            "brute_force_pairs": len(historical_subset) * len(prospective_subset),
            "join_edge_digest": edge_signature(subset_join),
            "brute_force_edge_digest": edge_signature(subset_brute),
            "passed": self_check,
        },
        "pre_registered_gate": {
            "checks": gates,
            "strong_low_historical_train_future_overlap_support": all(gates.values()),
            "thresholds": {
                "minimum_historical_coverage": schema.MIN_HISTORICAL_COVERAGE,
                "minimum_prospective_coverage": schema.MIN_PROSPECTIVE_COVERAGE,
                "maximum_prospective_affected_fraction": schema.MAX_PROSPECTIVE_AFFECTED_FRACTION,
                "maximum_cross_task_prospective_affected_fraction": (
                    schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION
                ),
                "maximum_large_multitask_components": schema.MAX_LARGE_MULTITASK_COMPONENTS,
            },
        },
        "interpretation_contract": {
            "lexical_train_future_overlap_only": True,
            "semantic_or_pretraining_contamination_absence_proven": False,
            "historical_label_or_observation_fields_used": False,
            "prospective_outcomes_read": False,
            "predictor_effect_computed": False,
            "closure_rerun_required": True,
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "python_executable": str(Path(sys.executable).resolve()),
            "randomness_used": False,
        },
        "security": {
            "prospective_label_vault_opened": False,
            "prospective_outcome_files_opened": [],
            "prediction_values_read": False,
            "code_or_identity_values_emitted": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise OverlapAuditError(f"output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    head = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != args.source_commit:
        raise OverlapAuditError("source commit binding failed")
    dependency_paths = (
        Path(__file__).resolve(),
        Path(schema.__file__).resolve(),
        Path(fuzzy.__file__).resolve(),
        Path(fuzzy_schema.__file__).resolve(),
    )
    for dependency_path in dependency_paths:
        source_relative = dependency_path.relative_to(repo_root).as_posix()
        committed_blob = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", f"{head}:{source_relative}"],
            text=True,
        ).strip()
        worktree_blob = subprocess.check_output(
            ["git", "-C", str(repo_root), "hash-object", str(dependency_path)],
            text=True,
        ).strip()
        if committed_blob != worktree_blob:
            raise OverlapAuditError(f"source blob binding failed: {source_relative}")
    result = audit(repo_root, args.state_root, args.snapshot_root, args.source_commit)
    atomic_json(args.output, result)
    print(
        result["status"],
        f"historical={result['historical_scope']['union_endpoints']}",
        f"prospective={result['prospective_scope']['observed_endpoints']}",
        "prospective_outcomes_read=false",
    )


if __name__ == "__main__":
    main()
