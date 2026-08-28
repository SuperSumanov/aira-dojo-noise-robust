#!/usr/bin/env python3
"""Certify a tree-native canonical view plus a lossless path compatibility view.

The formal receipt is aggregate-only.  Identity-bearing nodes, edges and paths
exist only in memory and are never written by this program.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_NAME = "tree-native-path-compatibility-contract-v1"
RECEIPT_PROTOCOL = "tree-native-path-compatibility-certificate-v1"
PASS = "VERIFIED_LOSSLESS_TREE_NATIVE_PATH_COMPATIBILITY"
FAIL = "TREE_NATIVE_PATH_COMPATIBILITY_GATE_FAIL"
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
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


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe hash input: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON input: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path.name}")
    return value


def read_rows(path: Path) -> Iterable[dict[str, Any]]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSONL input: {path.name}")
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL row: {path.name}:{line_number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"non-object JSONL row: {path.name}:{line_number}")
            yield value


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def valid_sha(value: Any, label: str) -> str:
    require(isinstance(value, str) and SHA64.fullmatch(value) is not None, f"invalid {label}")
    return value


def resolve_bound_file(repo_root: Path, item: dict[str, Any], label: str) -> Path:
    require(isinstance(item, dict), f"missing {label} binding")
    expected = valid_sha(item.get("sha256"), f"{label} SHA")
    relative = item.get("path")
    require(isinstance(relative, str) and relative, f"missing {label} path")
    candidate = (repo_root / relative).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError as error:
        raise ContractError(f"{label} path escapes repository") from error
    require(sha256_file(candidate) == expected, f"{label} SHA mismatch")
    return candidate


def load_protocol(path: Path, expected_sha: str, repo_root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    actual_sha = sha256_file(path)
    require(actual_sha == expected_sha, "protocol SHA mismatch")
    value = read_object(path)
    require(value.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(
        value.get("status")
        == "OUTCOME_BLIND_CONTRACT_FROZEN_BEFORE_COMPATIBILITY_CERTIFICATE",
        "protocol status mismatch",
    )
    require(value.get("ordered_classification") == [PASS, FAIL], "classification order mismatch")
    require(
        value.get("required_certificate", {}).get("identity_free_aggregate_only_before_closure")
        is True,
        "identity-free certificate requirement missing",
    )
    require(
        value.get("path_compatibility_view", {}).get("canonical_mass_numerator") == 1
        and value.get("path_compatibility_view", {}).get("canonical_mass_denominator")
        == "edge_multiplicity",
        "inverse-multiplicity rule mismatch",
    )
    bindings = value.get("upstream_bindings")
    require(isinstance(bindings, dict), "upstream bindings missing")
    paths = {
        name: resolve_bound_file(repo_root, bindings[name], name)
        for name in ("linearization_receipt", "linearization_producer", "predictor_estimand_panel")
    }
    return value, paths


def verify_blind_manifest(path: Path, expected_sha: str) -> bytes:
    require(path.is_file() and not path.is_symlink(), "unsafe blind manifest")
    raw = path.read_bytes()
    require(sha256_bytes(raw) == expected_sha, "blind manifest SHA mismatch")
    require(CREDENTIAL_RE.search(raw) is None, "credential-shaped bytes in blind manifest")
    return raw


def load_population(
    state_root: Path, snapshot_root: Path, protocol: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    state = state_root.resolve()
    snapshot = snapshot_root.resolve()
    fixed = protocol["fixed_snapshot"]
    snapshot_sha = valid_sha(fixed.get("sha256"), "snapshot SHA")
    require(snapshot.parent == state / "snapshots" and snapshot.name == snapshot_sha, "snapshot path mismatch")
    latest = state / "LATEST"
    require(latest.is_file() and not latest.is_symlink(), "unsafe LATEST")
    require(latest.read_text(encoding="utf-8").strip() == snapshot_sha, "LATEST mismatch")

    registry_path = snapshot / "intake_registry.jsonl"
    accumulator_root = snapshot / "accumulator"
    accumulator_summary_path = accumulator_root / "summary.json"
    runs_path = accumulator_root / "provisional_runs.jsonl"
    accumulator = read_object(accumulator_summary_path)
    require(accumulator.get("protocol") == "prospective_accumulator_v1", "accumulator protocol mismatch")
    security = accumulator.get("security")
    require(
        isinstance(security, dict)
        and security.get("label_vault_opened") is False
        and security.get("outcome_files_opened") == []
        and security.get("scorer_prediction_files_opened") == [],
        "accumulator blindness mismatch",
    )
    require(accumulator.get("closure", {}).get("provided") is False, "closure state mismatch")
    require(
        accumulator.get("inputs", {}).get("registry_sha256") == sha256_file(registry_path),
        "registry SHA mismatch",
    )
    require(
        accumulator.get("outputs", {}).get("provisional_runs_sha256") == sha256_file(runs_path),
        "run ledger SHA mismatch",
    )
    expected_summaries = accumulator.get("inputs", {}).get("intake_summaries")
    require(isinstance(expected_summaries, dict), "intake summary bindings missing")

    cards: dict[str, dict[str, Any]] = {}
    run_drop: dict[str, str] = {}
    seen_drops: set[str] = set()
    binding_rows: list[tuple[str, str]] = []
    registry = list(read_rows(registry_path))
    for registry_row in registry:
        require(set(registry_row) == {"drop_id", "intake_dir", "summary_sha256"}, "registry schema mismatch")
        drop_id = registry_row["drop_id"]
        require(isinstance(drop_id, str) and drop_id and drop_id not in seen_drops, "duplicate intake drop")
        seen_drops.add(drop_id)
        intake = Path(registry_row["intake_dir"]).resolve()
        require(intake.parent == state / "intakes" and intake.name == drop_id, "intake path mismatch")
        summary_sha = valid_sha(registry_row["summary_sha256"], "intake summary SHA")
        intake_summary_path = intake / "summary.json"
        require(sha256_file(intake_summary_path) == summary_sha, "intake summary SHA mismatch")
        require(expected_summaries.get(drop_id) == summary_sha, "intake summary not accumulator-bound")
        intake_summary = read_object(intake_summary_path)
        outputs = intake_summary.get("outputs")
        intake_security = intake_summary.get("security")
        blindness = intake_summary.get("blindness")
        require(
            all(isinstance(item, dict) for item in (outputs, intake_security, blindness)),
            "intake blindness contract missing",
        )
        require(
            intake_security.get("env_members_read") is False
            and intake_security.get("live_event_journal_members_read") is False
            and blindness.get("labels_used_for_run_selection") is False
            and blindness.get("labels_used_for_endpoint_selection") is False
            and blindness.get("metrics_computed") == [],
            "intake blindness mismatch",
        )
        manifest_sha = valid_sha(outputs.get("eligible_blind_manifest_sha256"), "manifest SHA")
        manifest_path = intake / "eligible_blind_manifest.jsonl"
        verify_blind_manifest(manifest_path, manifest_sha)
        binding_rows.append((summary_sha, manifest_sha))
        for row in read_rows(manifest_path):
            require(set(row) == BLIND_KEYS, "blind manifest schema mismatch")
            lineage = row.get("lineage")
            require(isinstance(lineage, dict) and set(lineage) == LINEAGE_KEYS, "blind lineage schema mismatch")
            card_id, task, run_id = row["card_id"], row["task"], row["run_id"]
            code, parent = row["code"], lineage["parent"]
            require(
                all(isinstance(item, str) and item for item in (card_id, task, run_id, code, parent))
                and card_id not in cards,
                "invalid or duplicate blind endpoint",
            )
            require(hashlib.sha256(code.encode()).hexdigest() == row["code_sha256"], "code SHA mismatch")
            valid_sha(row["source_sha256"], "source SHA")
            for field in ("depth", "step", "n_siblings"):
                number = lineage[field]
                require(
                    isinstance(number, int) and not isinstance(number, bool) and number >= 0,
                    "invalid lineage integer",
                )
            require(isinstance(lineage["op"], str) and lineage["op"], "invalid lineage operator")
            require(run_drop.setdefault(run_id, drop_id) == drop_id, "run spans intake drops")
            cards[card_id] = {
                "task": task,
                "run": run_id,
                "parent": parent,
                "depth": lineage["depth"],
            }

    runs: dict[str, dict[str, Any]] = {}
    for row in read_rows(runs_path):
        require(set(row) == RUN_KEYS, "provisional run schema mismatch")
        run_id = row.get("run_id")
        require(isinstance(run_id, str) and run_id and run_id not in runs, "invalid provisional run")
        require(row.get("flow_status") == "scoreable", "non-scoreable provisional run")
        require(row.get("drop_id") == run_drop.get(run_id), "run/drop mismatch")
        require(isinstance(row.get("task"), str) and row["task"], "invalid run task")
        require(isinstance(row.get("endpoints"), int) and row["endpoints"] > 0, "invalid endpoint count")
        runs[run_id] = row

    by_run = collections.Counter(card["run"] for card in cards.values())
    require(set(by_run) == set(runs), "card/run population mismatch")
    for run_id, row in runs.items():
        require(by_run[run_id] == row["endpoints"], "run endpoint count mismatch")
    for card in cards.values():
        require(runs[card["run"]]["task"] == card["task"], "card/run task mismatch")

    expected = {
        "runs": fixed["provisional_first960_runs"],
        "endpoints": fixed["eligible_endpoints"],
        "tasks": fixed["tasks"],
    }
    observed = {
        "runs": len(runs),
        "endpoints": len(cards),
        "tasks": len({card["task"] for card in cards.values()}),
    }
    require(observed == expected, "fixed population count mismatch")
    inventory = accumulator.get("inventory", {})
    require(
        inventory.get("provisional_first960_runs") == expected["runs"]
        and inventory.get("provisional_first960_endpoints") == expected["endpoints"],
        "accumulator population mismatch",
    )
    require(
        accumulator.get("task_support", {}).get("provisional_first960", {}).get("tasks")
        == expected["tasks"],
        "accumulator task support mismatch",
    )
    bindings = {
        "registry_sha256": sha256_file(registry_path),
        "accumulator_summary_sha256": sha256_file(accumulator_summary_path),
        "provisional_runs_sha256": sha256_file(runs_path),
        "intake_summary_manifest_multiset_sha256": canonical_sha(sorted(binding_rows)),
        "intake_count": len(registry),
    }
    return cards, runs, bindings


def fraction_record(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def construct_internal_views(cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build identity-bearing views in memory for certification and synthetic tests."""
    children: dict[str, list[str]] = {card_id: [] for card_id in cards}
    parent_map: dict[str, str] = {}
    roots: list[str] = []
    for child_id, child in cards.items():
        parent_id = child["parent"]
        if parent_id not in cards:
            roots.append(child_id)
            continue
        require(parent_id != child_id, "self-parent edge")
        require(cards[parent_id]["run"] == child["run"], "observed edge crosses physical runs")
        require(cards[parent_id]["task"] == child["task"], "observed edge crosses tasks")
        parent_map[child_id] = parent_id
        children[parent_id].append(child_id)
    for values in children.values():
        values.sort()
    roots.sort()
    require(bool(roots), "observed graph has no fragment roots")

    fragment_of: dict[str, str] = {}
    topological: list[str] = []
    queue = collections.deque((root, root) for root in roots)
    while queue:
        node, root = queue.popleft()
        require(node not in fragment_of, "observed graph contains a cycle or duplicate traversal")
        fragment_of[node] = root
        topological.append(node)
        queue.extend((child, root) for child in children[node])
    require(len(topological) == len(cards), "observed graph contains a cycle or unrooted component")

    descendant_leaves: dict[str, int] = {}
    for node in reversed(topological):
        descendant_leaves[node] = (
            1 if not children[node] else sum(descendant_leaves[child] for child in children[node])
        )

    paths: list[tuple[str, ...]] = []
    for root in roots:
        stack: list[tuple[str, tuple[str, ...]]] = [(root, (root,))]
        while stack:
            node, prefix = stack.pop()
            if not children[node]:
                paths.append(prefix)
            else:
                for child in reversed(children[node]):
                    stack.append((child, prefix + (child,)))
    paths.sort(key=lambda path: (fragment_of[path[0]], path[-1], path))

    canonical_edges = [
        {
            "edge_id": child,
            "parent": parent_map[child],
            "child": child,
            "task": cards[child]["task"],
            "run": cards[child]["run"],
            "depth": cards[child]["depth"],
            "fragment": fragment_of[child],
            "multiplicity": descendant_leaves[child],
        }
        for child in sorted(parent_map)
    ]
    edge_occurrences: list[dict[str, Any]] = []
    for path_index, path in enumerate(paths):
        require(len(path) == len(set(path)), "path repeats a node")
        first = cards[path[0]]
        for position, (parent, child) in enumerate(zip(path, path[1:])):
            require(parent_map.get(child) == parent, "path is not parent-child contiguous")
            require(cards[child]["task"] == first["task"], "path crosses tasks")
            require(cards[child]["run"] == first["run"], "path crosses physical runs")
            multiplicity = descendant_leaves[child]
            edge_occurrences.append(
                {
                    "path_index": path_index,
                    "path_position": position,
                    "edge_id": child,
                    "task": cards[child]["task"],
                    "run": cards[child]["run"],
                    "depth": cards[child]["depth"],
                    "multiplicity": multiplicity,
                    "mass": Fraction(1, multiplicity),
                }
            )

    sibling_groups = [
        {
            "parent": parent,
            "task": cards[parent]["task"],
            "run": cards[parent]["run"],
            "children": tuple(children[parent]),
        }
        for parent in sorted(children)
        if children[parent]
    ]
    return {
        "children": children,
        "parent_map": parent_map,
        "roots": roots,
        "fragment_of": fragment_of,
        "descendant_leaves": descendant_leaves,
        "paths": paths,
        "canonical_edges": canonical_edges,
        "edge_occurrences": edge_occurrences,
        "sibling_groups": sibling_groups,
    }


def certificate_metrics(cards: dict[str, dict[str, Any]], views: dict[str, Any]) -> dict[str, Any]:
    edges = views["canonical_edges"]
    occurrences = views["edge_occurrences"]
    paths = views["paths"]
    roots = views["roots"]
    children = views["children"]
    multiplicity_by_edge = {row["edge_id"]: row["multiplicity"] for row in edges}
    occurrence_count = collections.Counter(row["edge_id"] for row in occurrences)
    edge_mass: dict[str, Fraction] = collections.defaultdict(Fraction)
    task_mass: dict[str, Fraction] = collections.defaultdict(Fraction)
    run_mass: dict[str, Fraction] = collections.defaultdict(Fraction)
    depth_mass: dict[int, Fraction] = collections.defaultdict(Fraction)
    for row in occurrences:
        edge_mass[row["edge_id"]] += row["mass"]
        task_mass[row["task"]] += row["mass"]
        run_mass[row["run"]] += row["mass"]
        depth_mass[row["depth"]] += row["mass"]

    canonical_task = collections.Counter(row["task"] for row in edges)
    canonical_run = collections.Counter(row["run"] for row in edges)
    canonical_depth = collections.Counter(row["depth"] for row in edges)
    histogram = collections.Counter(str(row["multiplicity"]) for row in edges)
    edge_references_valid = all(row["edge_id"] in multiplicity_by_edge for row in occurrences)
    all_edges_covered = set(occurrence_count) == set(multiplicity_by_edge)
    count_matches = all(
        occurrence_count[edge] == multiplicity for edge, multiplicity in multiplicity_by_edge.items()
    )
    per_edge_mass_exact = all(edge_mass[edge] == 1 for edge in multiplicity_by_edge)
    total_mass = sum((row["mass"] for row in occurrences), Fraction())
    task_exact = task_mass == {key: Fraction(value) for key, value in canonical_task.items()}
    run_exact = run_mass == {key: Fraction(value) for key, value in canonical_run.items()}
    depth_exact = depth_mass == {key: Fraction(value) for key, value in canonical_depth.items()}
    sibling_links = sum(len(row["children"]) for row in views["sibling_groups"])
    contiguous_paths = all(
        all(views["parent_map"].get(child) == parent for parent, child in zip(path, path[1:]))
        for path in paths
    )
    path_bound = all(
        len({cards[node]["task"] for node in path}) == 1
        and len({cards[node]["run"] for node in path}) == 1
        and len(path) == len(set(path))
        for path in paths
    )
    gates = {
        "every_path_occurrence_references_canonical_edge": edge_references_valid,
        "every_canonical_edge_covered": all_edges_covered,
        "edge_occurrence_count_equals_multiplicity": count_matches,
        "per_edge_inverse_mass_exactly_one": per_edge_mass_exact,
        "total_inverse_mass_equals_unique_edges": total_mass == len(edges),
        "task_mass_exactly_recovers_unique_edges": task_exact,
        "physical_run_mass_exactly_recovers_unique_edges": run_exact,
        "depth_mass_exactly_recovers_unique_edges": depth_exact,
        "paths_contiguous_and_acyclic": contiguous_paths,
        "paths_fragment_task_and_run_bound": path_bound,
        "sibling_groups_equal_edges_grouped_by_parent": sibling_links == len(edges),
    }
    return {
        "inventory": {
            "eligible_endpoints": len(cards),
            "observed_unique_edges": len(edges),
            "observed_fragments": len(roots),
            "fragment_roots": len(roots),
            "fragment_leaves": len(paths),
            "single_node_fragments": sum(not children[root] for root in roots),
            "physical_runs": len({card["run"] for card in cards.values()}),
            "tasks": len({card["task"] for card in cards.values()}),
            "observed_sibling_groups": len(views["sibling_groups"]),
            "multi_child_observed_sibling_groups": sum(
                len(row["children"]) >= 2 for row in views["sibling_groups"]
            ),
            "maximum_observed_sibling_group_size": max(
                (len(row["children"]) for row in views["sibling_groups"]), default=0
            ),
        },
        "path_compatibility": {
            "path_records": len(paths),
            "edge_occurrences": len(occurrences),
            "duplicate_edge_occurrences": len(occurrences) - len(edges),
            "edge_multiplicity_histogram": dict(
                sorted(histogram.items(), key=lambda item: int(item[0]))
            ),
            "single_node_paths_retained": sum(len(path) == 1 for path in paths),
            "single_node_paths_have_zero_edge_occurrences": True,
        },
        "exact_recovery": {
            "arithmetic": "fractions.Fraction exact rational",
            "canonical_total_edge_mass": len(edges),
            "recovered_total_edge_mass": fraction_record(total_mass),
            "edge_count_checked": len(edges),
            "task_clusters_checked": len(canonical_task),
            "physical_run_clusters_checked": len(canonical_run),
            "depth_clusters_checked": len(canonical_depth),
            "maximum_per_edge_mass_error": {"numerator": 0, "denominator": 1}
            if per_edge_mass_exact else None,
            "task_mass_exact": task_exact,
            "physical_run_mass_exact": run_exact,
            "depth_mass_exact": depth_exact,
        },
        "recovery_gates": gates,
    }


def reconcile_upstream(metrics: dict[str, Any], upstream: dict[str, Any]) -> dict[str, bool]:
    inventory = metrics["inventory"]
    path = metrics["path_compatibility"]
    upstream_inventory = upstream.get("inventory", {})
    upstream_linear = upstream.get("linearization", {})
    return {
        "upstream_status_complete": upstream.get("status")
        == "OUTCOME_BLIND_TREE_LINEARIZATION_WEIGHT_AUDIT_COMPLETE",
        "upstream_population_exact": all(
            inventory[field] == upstream_inventory.get(field)
            for field in (
                "eligible_endpoints", "observed_unique_edges", "observed_fragments",
                "fragment_roots", "fragment_leaves", "single_node_fragments",
                "physical_runs", "tasks",
            )
        ),
        "upstream_path_count_exact": path["path_records"]
        == upstream_linear.get("root_to_leaf_trajectory_count"),
        "upstream_occurrence_count_exact": path["edge_occurrences"]
        == upstream_linear.get("branch_linearized_edge_occurrences"),
        "upstream_duplicate_count_exact": path["duplicate_edge_occurrences"]
        == upstream_linear.get("duplicate_edge_occurrences"),
        "upstream_multiplicity_histogram_exact": path["edge_multiplicity_histogram"]
        == upstream_linear.get("edge_multiplicity", {}).get("histogram"),
    }


def build_receipt(
    state_root: Path,
    snapshot_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    repo_root: Path,
    source_commit: str,
) -> dict[str, Any]:
    require(SHA40.fullmatch(source_commit) is not None, "invalid source commit")
    repo = repo_root.resolve()
    protocol, paths = load_protocol(protocol_path.resolve(), protocol_sha, repo)
    upstream = read_object(paths["linearization_receipt"])
    required_classification = protocol["upstream_bindings"]["linearization_receipt"][
        "required_classification"
    ]
    require(upstream.get("classification") == required_classification, "upstream classification mismatch")
    estimand = read_object(paths["predictor_estimand_panel"])
    require(
        estimand.get("protocol") == "decision-predictor-estimand-panel-v1"
        and estimand.get("status") == "FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE",
        "predictor estimand binding mismatch",
    )
    cards, _runs, input_bindings = load_population(state_root, snapshot_root, protocol)
    views = construct_internal_views(cards)
    metrics = certificate_metrics(cards, views)
    upstream_checks = reconcile_upstream(metrics, upstream)
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
    require(classification in protocol["ordered_classification"], "classification outside protocol")
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": "OUTCOME_BLIND_TREE_NATIVE_PATH_COMPATIBILITY_CERTIFICATE_COMPLETE",
        "classification": classification,
        "snapshot_sha256": protocol["fixed_snapshot"]["sha256"],
        "protocol_sha256": protocol_sha,
        "source_commit": source_commit,
        "producer_source_sha256": sha256_file(Path(__file__)),
        "input_bindings": input_bindings,
        "upstream_bindings": {
            name: {
                "sha256": protocol["upstream_bindings"][name]["sha256"],
                "verified": True,
            }
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


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    require(not path.exists(), f"output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = build_receipt(
        Path(args.state_root),
        Path(args.snapshot_root),
        Path(args.protocol),
        args.protocol_sha256,
        Path(args.repo_root),
        args.source_commit,
    )
    write_receipt(Path(args.output), receipt)
    print(receipt["classification"])


if __name__ == "__main__":
    main()
