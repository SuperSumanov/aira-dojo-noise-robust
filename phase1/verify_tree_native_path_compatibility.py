#!/usr/bin/env python3
"""Independent, non-importing verifier for the tree-native path certificate."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_NAME = "tree-native-path-compatibility-contract-v1"
RECEIPT_PROTOCOL = "tree-native-path-compatibility-certificate-v1"
VERIFY_PROTOCOL = "independent-tree-native-path-compatibility-verification-v1"
PASS = "VERIFIED_LOSSLESS_TREE_NATIVE_PATH_COMPATIBILITY"
FAIL = "TREE_NATIVE_PATH_COMPATIBILITY_GATE_FAIL"
BLIND_FIELDS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_FIELDS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_FIELDS = {
    "run_id", "task", "drop_id", "flow_status", "endpoints",
    "generation_started_at_utc", "source_sha256",
}
SHA64 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")
CREDENTIAL_RE = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|"
    rb"AIza[0-9A-Za-z_-]{20,}|Bearer[ \t]+[A-Za-z0-9._~-]{16,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerificationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_file(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe hash input: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def object_at(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON input: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"object expected: {path.name}")
    return value


def rows_at(path: Path) -> Iterable[dict[str, Any]]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSONL input: {path.name}")
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            check(bool(line.strip()), f"blank JSONL row: {path.name}:{line_number}")
            value = json.loads(line)
            check(isinstance(value, dict), f"object row expected: {path.name}:{line_number}")
            yield value


def canonical_digest(value: Any) -> str:
    return digest_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def sha_text(value: Any, label: str) -> str:
    check(isinstance(value, str) and SHA64.fullmatch(value) is not None, f"invalid {label}")
    return value


def bounded(repo_root: Path, binding: dict[str, Any], label: str) -> Path:
    check(isinstance(binding, dict), f"missing {label} binding")
    relative = binding.get("path")
    expected = sha_text(binding.get("sha256"), f"{label} SHA")
    check(isinstance(relative, str) and relative, f"invalid {label} path")
    candidate = (repo_root / relative).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"{label} path escapes repository") from error
    check(digest_file(candidate) == expected, f"{label} SHA mismatch")
    return candidate


def load_contract(
    path: Path, expected_sha: str, repo_root: Path
) -> tuple[dict[str, Any], dict[str, Path]]:
    check(digest_file(path) == expected_sha, "protocol SHA mismatch")
    value = object_at(path)
    check(value.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    check(
        value.get("status") == "OUTCOME_BLIND_CONTRACT_FROZEN_BEFORE_COMPATIBILITY_CERTIFICATE",
        "protocol status mismatch",
    )
    check(value.get("ordered_classification") == [PASS, FAIL], "classification order mismatch")
    compatibility = value.get("path_compatibility_view", {})
    check(
        compatibility.get("canonical_mass_numerator") == 1
        and compatibility.get("canonical_mass_denominator") == "edge_multiplicity",
        "mass rule mismatch",
    )
    bindings = value.get("upstream_bindings")
    check(isinstance(bindings, dict), "upstream bindings missing")
    paths = {
        name: bounded(repo_root, bindings[name], name)
        for name in ("linearization_receipt", "linearization_producer", "predictor_estimand_panel")
    }
    return value, paths


def independently_load_population(
    state_root: Path, snapshot_root: Path, protocol: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    state = state_root.resolve()
    snapshot = snapshot_root.resolve()
    fixed = protocol["fixed_snapshot"]
    snapshot_sha = sha_text(fixed.get("sha256"), "snapshot SHA")
    check(snapshot.parent == state / "snapshots" and snapshot.name == snapshot_sha, "snapshot binding mismatch")
    latest = state / "LATEST"
    check(latest.is_file() and not latest.is_symlink(), "unsafe LATEST")
    check(latest.read_text(encoding="utf-8").strip() == snapshot_sha, "LATEST mismatch")

    registry_path = snapshot / "intake_registry.jsonl"
    accumulator_dir = snapshot / "accumulator"
    summary_path = accumulator_dir / "summary.json"
    run_path = accumulator_dir / "provisional_runs.jsonl"
    summary = object_at(summary_path)
    check(summary.get("protocol") == "prospective_accumulator_v1", "accumulator protocol mismatch")
    security = summary.get("security")
    check(
        isinstance(security, dict)
        and security.get("label_vault_opened") is False
        and security.get("outcome_files_opened") == []
        and security.get("scorer_prediction_files_opened") == [],
        "accumulator blindness mismatch",
    )
    check(summary.get("closure", {}).get("provided") is False, "closure mismatch")
    check(
        summary.get("inputs", {}).get("registry_sha256") == digest_file(registry_path),
        "registry digest mismatch",
    )
    check(
        summary.get("outputs", {}).get("provisional_runs_sha256") == digest_file(run_path),
        "run ledger digest mismatch",
    )
    expected_summaries = summary.get("inputs", {}).get("intake_summaries")
    check(isinstance(expected_summaries, dict), "intake summary map missing")

    cards: dict[str, dict[str, Any]] = {}
    run_owner: dict[str, str] = {}
    drops: set[str] = set()
    bound_pairs: list[tuple[str, str]] = []
    registry = list(rows_at(registry_path))
    for registry_row in registry:
        check(set(registry_row) == {"drop_id", "intake_dir", "summary_sha256"}, "registry schema mismatch")
        drop = registry_row["drop_id"]
        check(isinstance(drop, str) and drop and drop not in drops, "duplicate drop")
        drops.add(drop)
        intake = Path(registry_row["intake_dir"]).resolve()
        check(intake.parent == state / "intakes" and intake.name == drop, "intake directory mismatch")
        summary_sha = sha_text(registry_row["summary_sha256"], "intake summary SHA")
        intake_summary_path = intake / "summary.json"
        check(digest_file(intake_summary_path) == summary_sha, "intake summary digest mismatch")
        check(expected_summaries.get(drop) == summary_sha, "unbound intake summary")
        intake_summary = object_at(intake_summary_path)
        outputs = intake_summary.get("outputs")
        intake_security = intake_summary.get("security")
        blindness = intake_summary.get("blindness")
        check(
            all(isinstance(item, dict) for item in (outputs, intake_security, blindness)),
            "intake contract missing",
        )
        check(
            intake_security.get("env_members_read") is False
            and intake_security.get("live_event_journal_members_read") is False
            and blindness.get("labels_used_for_run_selection") is False
            and blindness.get("labels_used_for_endpoint_selection") is False
            and blindness.get("metrics_computed") == [],
            "intake blindness mismatch",
        )
        manifest_sha = sha_text(outputs.get("eligible_blind_manifest_sha256"), "manifest SHA")
        manifest_path = intake / "eligible_blind_manifest.jsonl"
        manifest_raw = manifest_path.read_bytes()
        check(digest_bytes(manifest_raw) == manifest_sha, "manifest digest mismatch")
        check(CREDENTIAL_RE.search(manifest_raw) is None, "credential-shaped manifest bytes")
        bound_pairs.append((summary_sha, manifest_sha))
        for row in rows_at(manifest_path):
            check(set(row) == BLIND_FIELDS, "blind schema mismatch")
            lineage = row.get("lineage")
            check(isinstance(lineage, dict) and set(lineage) == LINEAGE_FIELDS, "lineage schema mismatch")
            identifier, task, run = row["card_id"], row["task"], row["run_id"]
            code, parent = row["code"], lineage["parent"]
            check(
                all(isinstance(item, str) and item for item in (identifier, task, run, code, parent))
                and identifier not in cards,
                "invalid blind endpoint",
            )
            check(hashlib.sha256(code.encode()).hexdigest() == row["code_sha256"], "code digest mismatch")
            sha_text(row["source_sha256"], "source SHA")
            for field in ("depth", "step", "n_siblings"):
                number = lineage[field]
                check(isinstance(number, int) and not isinstance(number, bool) and number >= 0, "lineage integer mismatch")
            check(isinstance(lineage["op"], str) and lineage["op"], "lineage operation mismatch")
            prior = run_owner.setdefault(run, drop)
            check(prior == drop, "run spans drops")
            cards[identifier] = {
                "task": task,
                "run": run,
                "parent": parent,
                "depth": lineage["depth"],
            }

    runs: dict[str, dict[str, Any]] = {}
    for row in rows_at(run_path):
        check(set(row) == RUN_FIELDS, "run schema mismatch")
        run = row.get("run_id")
        check(isinstance(run, str) and run and run not in runs, "duplicate run")
        check(row.get("flow_status") == "scoreable", "run is not scoreable")
        check(row.get("drop_id") == run_owner.get(run), "run owner mismatch")
        check(isinstance(row.get("task"), str) and row["task"], "run task mismatch")
        check(isinstance(row.get("endpoints"), int) and row["endpoints"] > 0, "run endpoint mismatch")
        runs[run] = row

    card_counts = collections.Counter(row["run"] for row in cards.values())
    check(set(card_counts) == set(runs), "run/card population mismatch")
    for run, row in runs.items():
        check(card_counts[run] == row["endpoints"], "run/card count mismatch")
    for row in cards.values():
        check(runs[row["run"]]["task"] == row["task"], "run/card task mismatch")

    expected = {
        "runs": fixed["provisional_first960_runs"],
        "endpoints": fixed["eligible_endpoints"],
        "tasks": fixed["tasks"],
    }
    actual = {
        "runs": len(runs),
        "endpoints": len(cards),
        "tasks": len({row["task"] for row in cards.values()}),
    }
    check(actual == expected, "fixed population mismatch")
    inventory = summary.get("inventory", {})
    check(
        inventory.get("provisional_first960_runs") == expected["runs"]
        and inventory.get("provisional_first960_endpoints") == expected["endpoints"],
        "accumulator inventory mismatch",
    )
    check(
        summary.get("task_support", {}).get("provisional_first960", {}).get("tasks")
        == expected["tasks"],
        "accumulator task count mismatch",
    )
    bindings = {
        "registry_sha256": digest_file(registry_path),
        "accumulator_summary_sha256": digest_file(summary_path),
        "provisional_runs_sha256": digest_file(run_path),
        "intake_summary_manifest_multiset_sha256": canonical_digest(sorted(bound_pairs)),
        "intake_count": len(registry),
    }
    return cards, runs, bindings


def rational(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def independently_reconstruct(cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    children: dict[str, list[str]] = {identifier: [] for identifier in cards}
    parent_of: dict[str, str] = {}
    roots: set[str] = set()
    for child, row in cards.items():
        parent = row["parent"]
        if parent not in cards:
            roots.add(child)
        else:
            check(parent != child, "self-parent edge")
            check(cards[parent]["run"] == row["run"], "cross-run edge")
            check(cards[parent]["task"] == row["task"], "cross-task edge")
            parent_of[child] = parent
            children[parent].append(child)
    for values in children.values():
        values.sort()
    check(bool(roots), "no fragment roots")

    root_for: dict[str, str] = {}
    for start in sorted(cards):
        chain: list[str] = []
        seen: set[str] = set()
        cursor = start
        while cursor in parent_of:
            check(cursor not in seen, "cycle detected")
            seen.add(cursor)
            chain.append(cursor)
            cursor = parent_of[cursor]
        check(cursor in roots, "node does not terminate at a fragment root")
        root_for[start] = cursor
        for node in chain:
            root_for[node] = cursor
    check(len(root_for) == len(cards), "root assignment incomplete")

    leaves = sorted(identifier for identifier, values in children.items() if not values)
    paths: list[tuple[str, ...]] = []
    occurrence_edges: list[str] = []
    for leaf in leaves:
        backwards = [leaf]
        cursor = leaf
        while cursor in parent_of:
            cursor = parent_of[cursor]
            backwards.append(cursor)
        path = tuple(reversed(backwards))
        check(path[0] == root_for[leaf], "path root mismatch")
        check(len(path) == len(set(path)), "path repeats a node")
        check(
            all(parent_of.get(child) == parent for parent, child in zip(path, path[1:])),
            "path is not contiguous",
        )
        check(len({cards[node]["task"] for node in path}) == 1, "path crosses tasks")
        check(len({cards[node]["run"] for node in path}) == 1, "path crosses runs")
        paths.append(path)
        occurrence_edges.extend(path[1:])
    paths.sort(key=lambda path: (root_for[path[0]], path[-1], path))

    multiplicity = collections.Counter(occurrence_edges)
    canonical_edges = sorted(parent_of)
    check(set(multiplicity) == set(canonical_edges), "canonical edge coverage mismatch")
    edge_mass: dict[str, Fraction] = collections.defaultdict(Fraction)
    task_mass: dict[str, Fraction] = collections.defaultdict(Fraction)
    run_mass: dict[str, Fraction] = collections.defaultdict(Fraction)
    depth_mass: dict[int, Fraction] = collections.defaultdict(Fraction)
    for edge in occurrence_edges:
        weight = Fraction(1, multiplicity[edge])
        edge_mass[edge] += weight
        task_mass[cards[edge]["task"]] += weight
        run_mass[cards[edge]["run"]] += weight
        depth_mass[cards[edge]["depth"]] += weight
    canonical_task = collections.Counter(cards[edge]["task"] for edge in canonical_edges)
    canonical_run = collections.Counter(cards[edge]["run"] for edge in canonical_edges)
    canonical_depth = collections.Counter(cards[edge]["depth"] for edge in canonical_edges)
    task_expected = {key: Fraction(value) for key, value in canonical_task.items()}
    run_expected = {key: Fraction(value) for key, value in canonical_run.items()}
    depth_expected = {key: Fraction(value) for key, value in canonical_depth.items()}
    total_mass = sum(edge_mass.values(), Fraction())
    per_edge_exact = all(edge_mass[edge] == 1 for edge in canonical_edges)
    task_exact = task_mass == task_expected
    run_exact = run_mass == run_expected
    depth_exact = depth_mass == depth_expected
    sibling_groups = [values for values in children.values() if values]
    histogram = collections.Counter(str(value) for value in multiplicity.values())
    gates = {
        "every_path_occurrence_references_canonical_edge": all(
            edge in parent_of for edge in occurrence_edges
        ),
        "every_canonical_edge_covered": set(multiplicity) == set(canonical_edges),
        "edge_occurrence_count_equals_multiplicity": sum(multiplicity.values())
        == len(occurrence_edges),
        "per_edge_inverse_mass_exactly_one": per_edge_exact,
        "total_inverse_mass_equals_unique_edges": total_mass == len(canonical_edges),
        "task_mass_exactly_recovers_unique_edges": task_exact,
        "physical_run_mass_exactly_recovers_unique_edges": run_exact,
        "depth_mass_exactly_recovers_unique_edges": depth_exact,
        "paths_contiguous_and_acyclic": all(
            len(path) == len(set(path))
            and all(parent_of.get(child) == parent for parent, child in zip(path, path[1:]))
            for path in paths
        ),
        "paths_fragment_task_and_run_bound": all(
            len({root_for[node] for node in path}) == 1
            and len({cards[node]["task"] for node in path}) == 1
            and len({cards[node]["run"] for node in path}) == 1
            for path in paths
        ),
        "sibling_groups_equal_edges_grouped_by_parent": sum(map(len, sibling_groups))
        == len(canonical_edges),
    }
    return {
        "inventory": {
            "eligible_endpoints": len(cards),
            "observed_unique_edges": len(canonical_edges),
            "observed_fragments": len(roots),
            "fragment_roots": len(roots),
            "fragment_leaves": len(paths),
            "single_node_fragments": sum(not children[root] for root in roots),
            "physical_runs": len({row["run"] for row in cards.values()}),
            "tasks": len({row["task"] for row in cards.values()}),
            "observed_sibling_groups": len(sibling_groups),
            "multi_child_observed_sibling_groups": sum(len(group) >= 2 for group in sibling_groups),
            "maximum_observed_sibling_group_size": max(map(len, sibling_groups), default=0),
        },
        "path_compatibility": {
            "path_records": len(paths),
            "edge_occurrences": len(occurrence_edges),
            "duplicate_edge_occurrences": len(occurrence_edges) - len(canonical_edges),
            "edge_multiplicity_histogram": dict(
                sorted(histogram.items(), key=lambda item: int(item[0]))
            ),
            "single_node_paths_retained": sum(len(path) == 1 for path in paths),
            "single_node_paths_have_zero_edge_occurrences": True,
        },
        "exact_recovery": {
            "arithmetic": "fractions.Fraction exact rational",
            "canonical_total_edge_mass": len(canonical_edges),
            "recovered_total_edge_mass": rational(total_mass),
            "edge_count_checked": len(canonical_edges),
            "task_clusters_checked": len(canonical_task),
            "physical_run_clusters_checked": len(canonical_run),
            "depth_clusters_checked": len(canonical_depth),
            "maximum_per_edge_mass_error": {"numerator": 0, "denominator": 1}
            if per_edge_exact else None,
            "task_mass_exact": task_exact,
            "physical_run_mass_exact": run_exact,
            "depth_mass_exact": depth_exact,
        },
        "recovery_gates": gates,
    }


def upstream_reconciliation(metrics: dict[str, Any], upstream: dict[str, Any]) -> dict[str, bool]:
    inventory = metrics["inventory"]
    path = metrics["path_compatibility"]
    old_inventory = upstream.get("inventory", {})
    old_path = upstream.get("linearization", {})
    return {
        "upstream_status_complete": upstream.get("status")
        == "OUTCOME_BLIND_TREE_LINEARIZATION_WEIGHT_AUDIT_COMPLETE",
        "upstream_population_exact": all(
            inventory[field] == old_inventory.get(field)
            for field in (
                "eligible_endpoints", "observed_unique_edges", "observed_fragments",
                "fragment_roots", "fragment_leaves", "single_node_fragments",
                "physical_runs", "tasks",
            )
        ),
        "upstream_path_count_exact": path["path_records"]
        == old_path.get("root_to_leaf_trajectory_count"),
        "upstream_occurrence_count_exact": path["edge_occurrences"]
        == old_path.get("branch_linearized_edge_occurrences"),
        "upstream_duplicate_count_exact": path["duplicate_edge_occurrences"]
        == old_path.get("duplicate_edge_occurrences"),
        "upstream_multiplicity_histogram_exact": path["edge_multiplicity_histogram"]
        == old_path.get("edge_multiplicity", {}).get("histogram"),
    }


def expected_receipt(
    protocol: dict[str, Any],
    protocol_sha: str,
    source_commit: str,
    producer_source_sha: str,
    input_bindings: dict[str, Any],
    upstream: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    upstream_checks = upstream_reconciliation(metrics, upstream)
    all_gates = {
        **metrics["recovery_gates"],
        **upstream_checks,
        "input_bindings_equal_upstream": input_bindings == upstream.get("input_bindings"),
        "upstream_snapshot_equal_fixed": upstream.get("snapshot_sha256")
        == protocol["fixed_snapshot"]["sha256"],
        "predictor_estimand_remains_authoritative": protocol["upstream_bindings"]
        ["predictor_estimand_panel"].get("remains_authoritative") is True,
        "identity_free_aggregate_only": True,
    }
    classification = PASS if all(all_gates.values()) else FAIL
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": "OUTCOME_BLIND_TREE_NATIVE_PATH_COMPATIBILITY_CERTIFICATE_COMPLETE",
        "classification": classification,
        "snapshot_sha256": protocol["fixed_snapshot"]["sha256"],
        "protocol_sha256": protocol_sha,
        "source_commit": source_commit,
        "producer_source_sha256": producer_source_sha,
        "input_bindings": input_bindings,
        "upstream_bindings": {
            name: {"sha256": protocol["upstream_bindings"][name]["sha256"], "verified": True}
            for name in (
                "linearization_receipt", "linearization_producer", "predictor_estimand_panel"
            )
        },
        "inventory": metrics["inventory"],
        "path_compatibility": metrics["path_compatibility"],
        "exact_recovery": metrics["exact_recovery"],
        "verification_gates": all_gates,
        "all_verification_gates_passed": all(all_gates.values()),
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "identity_code_or_per_path_values_written": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def verify(
    state_root: Path,
    snapshot_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    repo_root: Path,
    receipt_path: Path,
    receipt_sha: str,
    producer_source: Path,
    producer_source_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    check(SHA40.fullmatch(source_commit) is not None, "invalid source commit")
    check(digest_file(receipt_path) == receipt_sha, "receipt SHA mismatch")
    check(digest_file(producer_source) == producer_source_sha, "producer source SHA mismatch")
    protocol, paths = load_contract(protocol_path.resolve(), protocol_sha, repo_root.resolve())
    upstream = object_at(paths["linearization_receipt"])
    required = protocol["upstream_bindings"]["linearization_receipt"]["required_classification"]
    check(upstream.get("classification") == required, "upstream classification mismatch")
    estimand = object_at(paths["predictor_estimand_panel"])
    check(
        estimand.get("protocol") == "decision-predictor-estimand-panel-v1"
        and estimand.get("status") == "FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE",
        "estimand panel mismatch",
    )
    cards, _runs, input_bindings = independently_load_population(
        state_root, snapshot_root, protocol
    )
    metrics = independently_reconstruct(cards)
    expected = expected_receipt(
        protocol,
        protocol_sha,
        source_commit,
        producer_source_sha,
        input_bindings,
        upstream,
        metrics,
    )
    observed = object_at(receipt_path)
    check(observed == expected, "receipt does not match independent reconstruction")
    check(observed["classification"] == PASS, "certificate did not pass")
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": "INDEPENDENT_TREE_NATIVE_PATH_COMPATIBILITY_PASS",
        "snapshot_sha256": protocol["fixed_snapshot"]["sha256"],
        "protocol_sha256": protocol_sha,
        "receipt_sha256": receipt_sha,
        "source_commit": source_commit,
        "producer_source_sha256": producer_source_sha,
        "classification": observed["classification"],
        "inventory": observed["inventory"],
        "path_compatibility": observed["path_compatibility"],
        "exact_recovery": observed["exact_recovery"],
        "all_verification_gates_passed": True,
        "security": {
            "imports_producer": False,
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "identity_code_or_per_path_values_written": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--producer-source", required=True)
    parser.add_argument("--producer-source-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = verify(
        Path(args.state_root),
        Path(args.snapshot_root),
        Path(args.protocol),
        args.protocol_sha256,
        Path(args.repo_root),
        Path(args.receipt),
        args.receipt_sha256,
        Path(args.producer_source),
        args.producer_source_sha256,
        args.source_commit,
    )
    output = Path(args.output)
    check(not output.exists(), f"output exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(result["status"])


if __name__ == "__main__":
    main()
