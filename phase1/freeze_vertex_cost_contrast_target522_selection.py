#!/usr/bin/env python3
"""Freeze outcome-blind Target-522 acquisition/evaluation and endpoint selections."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping, Sequence

from phase1 import confirm_yield_guarded_breadth_forward_target522 as forward
from phase1 import endpoint_budget_label_efficiency_smoke as endpoint_smoke
from phase1 import falsify_historical_run_split_breadth_pareto as graph_source
from phase1.vertex_cost_contrast_design import (
    ParentGroup,
    code_hash_feature,
    select_vertex_cost_contrasts,
)


PROTOCOL_NAME = "vertex-cost-contrast-target522-effect-v1"
COMPATIBILITY_PROTOCOL = "target522-selection-container-compatibility-v1"
PUBLIC_PROTOCOL = "vertex-cost-contrast-target522-selection-public-v1"
PRIVATE_PROTOCOL = "vertex-cost-contrast-target522-selection-private-v1"
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class SelectionFreezeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SelectionFreezeError(message)


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


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path: Path) -> str:
    return forward.file_sha(path)


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    require(SHA_RE.fullmatch(expected_sha) is not None, "invalid protocol SHA")
    actual = file_sha(path)
    require(actual == expected_sha, "protocol SHA mismatch")
    protocol = forward.target.read_object(path)
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(
        protocol.get("status") == "FROZEN_BEFORE_TARGET522_CANDIDATE_PROFILE_OR_VALUES",
        "protocol status mismatch",
    )
    freeze = protocol.get("freeze_state") or {}
    require(freeze.get("target522_candidate_present") is False, "candidate seen before freeze")
    require(freeze.get("prospective_values_read") is False, "prospective values seen before freeze")
    require(
        freeze.get("first960_accrual_closure_complete") is False,
        "unexpected first-960 closure at freeze",
    )
    require(
        protocol["release_gate"]["selection_stage_may_read_outcomes"] is False,
        "selection stage outcome access",
    )
    require(
        protocol["release_gate"]["effect_stage_requires_first960_accrual_closure"] is True,
        "missing first-960 closure gate",
    )
    return protocol, actual


def load_compatibility(
    path: Path,
    expected_sha: str,
    protocol_path: Path,
    protocol_sha: str,
    selection_root: Path,
) -> tuple[dict[str, Any], str]:
    require(SHA_RE.fullmatch(expected_sha) is not None, "invalid compatibility SHA")
    actual = file_sha(path)
    require(actual == expected_sha, "compatibility SHA mismatch")
    compatibility = forward.target.read_object(path)
    require(compatibility.get("protocol") == COMPATIBILITY_PROTOCOL, "compatibility protocol")
    require(
        compatibility.get("status")
        == "FROZEN_AFTER_STRUCTURAL_CLOSURE_BEFORE_CANDIDATE_PROFILE_OR_VALUES",
        "compatibility status",
    )
    scientific = compatibility.get("scientific_protocol") or {}
    require(
        scientific.get("path") == "phase1/vertex_cost_contrast_target522_effect_v1.json"
        and scientific.get("sha256") == protocol_sha
        and file_sha(protocol_path) == protocol_sha,
        "compatibility scientific protocol binding",
    )
    container = compatibility.get("selection_container") or {}
    require(
        container.get("root") == str(selection_root.resolve()),
        "compatibility selection root",
    )
    require(
        SHA_RE.fullmatch(str(container.get("sha256sums_sha256", ""))) is not None,
        "compatibility selection manifest SHA",
    )
    core = container.get("core_basenames")
    auxiliary = container.get("manifest_bound_auxiliary_basenames")
    require(
        isinstance(core, list)
        and isinstance(auxiliary, list)
        and len(core) == len(set(core))
        and len(auxiliary) == len(set(auxiliary))
        and not (set(core) & set(auxiliary))
        and all(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9._-]+", name) for name in core + auxiliary),
        "compatibility basename schema",
    )
    scope = compatibility.get("scope") or {}
    require(
        scope.get("candidate_identity_or_profile_read_to_define_fix") is False
        and scope.get("prospective_values_read") is False
        and scope.get("scientific_threshold_arm_budget_or_estimand_changed") is False,
        "compatibility scope",
    )
    return compatibility, actual


def _replacement_map(compatibility: dict[str, Any]) -> dict[str, dict[str, str]]:
    rows = compatibility["replacement_bindings"]["runtime_dependencies"]
    require(isinstance(rows, list), "replacement dependency list")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        require(
            set(row) == {"path", "old_sha256", "new_sha256"}
            and isinstance(row["path"], str)
            and row["path"].startswith("phase1/")
            and SHA_RE.fullmatch(row["old_sha256"]) is not None
            and SHA_RE.fullmatch(row["new_sha256"]) is not None
            and row["path"] not in result,
            "replacement dependency binding",
        )
        result[row["path"]] = row
    return result


def verify_runtime_sources(
    repo_root: Path, protocol: dict[str, Any], compatibility: dict[str, Any] | None = None
) -> None:
    root = repo_root.resolve()
    require(root.is_dir() and not repo_root.is_symlink(), "unsafe repo root")
    dependencies = protocol["freeze_state"]["runtime_dependencies"]
    require(isinstance(dependencies, list) and dependencies, "runtime dependencies")
    observed: set[str] = set()
    replacements = _replacement_map(compatibility) if compatibility is not None else {}
    for binding in dependencies:
        require(set(binding) == {"path", "sha256"}, "runtime dependency schema")
        relative, expected = binding["path"], binding["sha256"]
        require(
            isinstance(relative, str)
            and relative.startswith("phase1/")
            and ".." not in Path(relative).parts
            and isinstance(expected, str)
            and SHA_RE.fullmatch(expected) is not None
            and relative not in observed,
            "runtime dependency binding",
        )
        observed.add(relative)
        candidate = (root / relative).resolve()
        require(candidate.is_relative_to(root), "runtime dependency escapes repo")
        replacement = replacements.get(relative)
        if replacement is not None:
            require(replacement["old_sha256"] == expected, "replacement old dependency SHA")
            expected = replacement["new_sha256"]
        require(file_sha(candidate) == expected, "runtime dependency SHA mismatch")
    require(set(replacements) <= observed, "replacement dependency absent from scientific protocol")


def verify_program_binding(
    repo_root: Path, protocol: dict[str, Any], compatibility: dict[str, Any] | None = None
) -> None:
    root = repo_root.resolve()
    binding = protocol["freeze_state"]["selection_exporter"]
    if compatibility is not None:
        replacement = compatibility["replacement_bindings"]["selection_exporter"]
        require(
            replacement.get("path") == binding["path"]
            and replacement.get("old_sha256") == binding["sha256"]
            and SHA_RE.fullmatch(str(replacement.get("new_sha256", ""))) is not None,
            "selection exporter replacement binding",
        )
        binding = {"path": replacement["path"], "sha256": replacement["new_sha256"]}
    path = (root / binding["path"]).resolve()
    require(path.is_relative_to(root), "selection exporter escapes repo")
    require(file_sha(path) == binding["sha256"], "selection exporter SHA mismatch")


def compatible_selection_and_increment(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol: dict[str, Any],
    compatibility: dict[str, Any],
) -> tuple[dict[str, Any], Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = selection_root.resolve()
    container = compatibility["selection_container"]
    require(root.is_dir() and not selection_root.is_symlink(), "unsafe outer selection root")
    require(file_sha(root / "SHA256SUMS") == container["sha256sums_sha256"], "outer manifest SHA")
    target_protocol, target_protocol_sha = forward.original_target_protocol(repo_root, protocol)
    core = tuple(target_protocol["security"]["selection_support_input_basenames"])
    require(core == tuple(container["core_basenames"]), "core basename contract")
    auxiliary = tuple(container["manifest_bound_auxiliary_basenames"])
    actual = {path.name for path in root.iterdir()}
    require(actual == set(core) | set(auxiliary), "outer selection basename set")
    require(all(path.is_file() and not path.is_symlink() for path in root.iterdir()), "unsafe outer member")
    outer_hashes = forward.target.verify_sha256sums(root)
    require(set(auxiliary) <= set(outer_hashes), "auxiliary receipt missing from outer manifest")

    projection: Path
    with tempfile.TemporaryDirectory(prefix="target522-core-selection-") as temporary:
        projection = Path(temporary)
        os.chmod(projection, 0o700)
        for name in core:
            if name in {"SHA256SUMS", "COMPLETE"}:
                continue
            destination = projection / name
            destination.write_bytes((root / name).read_bytes())
            os.chmod(destination, 0o600)
        manifest_names = sorted(set(core) - {"SHA256SUMS", "COMPLETE"})
        manifest_text = "".join(f"{outer_hashes[name]}  ./{name}\n" for name in manifest_names)
        (projection / "SHA256SUMS").write_text(manifest_text, encoding="utf-8", newline="\n")
        (projection / "COMPLETE").write_bytes(b"")
        os.chmod(projection / "SHA256SUMS", 0o600)
        os.chmod(projection / "COMPLETE", 0o600)
        selection = forward.target.verify_selection(
            projection, repo_root, target_protocol, target_protocol_sha
        )
    require(not projection.exists(), "temporary core projection was not removed")

    selection["outer_selection_sha256sums_sha256"] = container["sha256sums_sha256"]
    selection["core_projection_sha256sums_sha256"] = selection[
        "selection_support_sha256sums_sha256"
    ]
    expected_selection_root = protocol["freeze_state"]["target522_selection_root"]
    require(str(root) == expected_selection_root, "selection root mismatch")
    monitor_binding = protocol["freeze_state"]["target522_selection_monitor"]
    require(
        selection["selection_monitor_source_sha256"] == monitor_binding["sha256"],
        "selection package monitor SHA mismatch",
    )
    baseline = forward.target.load_blind_snapshot(
        state_root, selection["baseline_snapshot_sha256"]
    )
    candidate = forward.target.load_blind_snapshot(
        state_root, selection["candidate_snapshot_sha256"]
    )
    increment_cards, increment_runs, append_only = forward.target.disjoint_increment(
        baseline, candidate, target_protocol
    )
    require(
        len(increment_runs) >= protocol["population"]["physical_run_increment_minimum"],
        "increment below frozen minimum",
    )
    return selection, candidate, increment_cards, increment_runs, append_only


def salted_run_key(salt: str, task: str, run: str) -> str:
    return hashlib.sha256("\0".join((salt, task, run)).encode("utf-8")).hexdigest()


def partition_runs(
    runs: Mapping[str, Mapping[str, Any]], salt: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Deterministically assign complete physical runs within task, without outcomes."""

    require(isinstance(salt, str) and salt, "split salt")
    by_task: dict[str, list[str]] = defaultdict(list)
    for run, row in runs.items():
        task = row.get("task")
        require(
            isinstance(run, str)
            and bool(run)
            and isinstance(task, str)
            and bool(task),
            "run split identity",
        )
        by_task[task].append(run)
    acquisition: set[str] = set()
    evaluation: set[str] = set()
    for task, task_runs in sorted(by_task.items()):
        ordered = sorted(task_runs, key=lambda run: (salted_run_key(salt, task, run), run))
        if len(ordered) == 1:
            bucket = int(salted_run_key(salt, task, ordered[0])[:16], 16) % 5
            (acquisition if bucket < 3 else evaluation).add(ordered[0])
            continue
        evaluation_count = min(len(ordered) - 1, max(1, 2 * len(ordered) // 5))
        evaluation.update(ordered[:evaluation_count])
        acquisition.update(ordered[evaluation_count:])
    population = set(runs)
    require(acquisition and evaluation, "empty run partition")
    require(not acquisition & evaluation, "run split overlap")
    require(acquisition | evaluation == population, "run split not exhaustive")
    return tuple(sorted(acquisition)), tuple(sorted(evaluation))


def subgraph(graph: Any, run_ids: Sequence[str]) -> Any:
    run_set = set(run_ids)
    return graph_source.graph_from_edges([edge for edge in graph.edges if edge.run in run_set])


def graph_profile(graph: Any) -> dict[str, Any]:
    tasks = Counter(edge.task for edge in graph.edges)
    runs = Counter(edge.run for edge in graph.edges)
    pairs = len(graph.edges)
    return {
        "pairs": pairs,
        "endpoints": len(graph.nodes),
        "parents": len({edge.parent for edge in graph.edges}),
        "physical_runs": len(runs),
        "tasks": len(tasks),
        "maximum_single_task_pair_share": forward.ratio(
            max(tasks.values(), default=0), max(1, pairs)
        ),
        "maximum_single_run_pair_share": forward.ratio(
            max(runs.values(), default=0), max(1, pairs)
        ),
        "orientation_free_graph_sha256": graph_source.graph_fingerprint(graph),
    }


def checkpoints(graph: Any, protocol: dict[str, Any]) -> list[int]:
    selection = protocol["selection"]
    denominator = int(selection["budget_fraction_denominator"])
    values = [
        math.floor(len(graph.nodes) * int(numerator) / denominator)
        for numerator in selection["trajectory_numerators"]
    ]
    require(values == sorted(set(values)) and len(values) == 6 and values[0] >= 2, "budget closure")
    return values


def parent_groups(graph: Any) -> list[ParentGroup]:
    grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for edge in graph.edges:
        grouped[(edge.parent, edge.task, edge.run)].update(edge.endpoints)
    parents: set[str] = set()
    result: list[ParentGroup] = []
    for (parent, task, run), endpoints in sorted(grouped.items()):
        require(parent not in parents, "parent spans task or run")
        parents.add(parent)
        values = tuple(sorted(endpoints))
        require(len(values) >= 2, "singleton parent")
        expected = {
            edge.endpoints
            for edge in graph.edges
            if edge.parent == parent and edge.task == task and edge.run == run
        }
        require(len(expected) == len(values) * (len(values) - 1) // 2, "parent is not a clique")
        result.append(ParentGroup(parent, task, run, values))
    require(result, "empty parent groups")
    return result


def vccd_order(
    graph: Any,
    card_payloads: Mapping[str, Mapping[str, Any]],
    maximum_budget: int,
    protocol: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    groups = parent_groups(graph)
    feature_spec = protocol["selection"]["vccd"]
    features = {}
    code_hashes = []
    for endpoint in graph.nodes:
        payload = card_payloads.get(endpoint)
        require(isinstance(payload, Mapping), "missing endpoint payload")
        code = payload.get("code")
        code_sha = payload.get("code_sha256")
        require(
            isinstance(code, str)
            and isinstance(code_sha, str)
            and hashlib.sha256(code.encode("utf-8")).hexdigest() == code_sha,
            "endpoint code binding",
        )
        features[endpoint] = code_hash_feature(
            code,
            dimension=int(feature_spec["dimension"]),
            ngram_min=int(feature_spec["character_ngram_range"][0]),
            ngram_max=int(feature_spec["character_ngram_range"][1]),
            max_chars=int(feature_spec["maximum_characters"]),
        )
        code_hashes.append(code_sha)
    result = select_vertex_cost_contrasts(
        groups,
        features,
        budget=maximum_budget,
        ridge=float(feature_spec["ridge"]),
        task_share_denominator=int(feature_spec["task_terminal_share_denominator"]),
        run_share_denominator=int(feature_spec["run_terminal_share_denominator"]),
    )
    return list(result.selected_endpoints), {
        "terminal_information_logdet_gain": result.information_logdet_gain,
        "terminal_numerical_feature_rank": result.numerical_feature_rank,
        "terminal_task_endpoint_cap": result.task_cap,
        "terminal_run_endpoint_cap": result.run_cap,
        "bound_code_sha256_multiset_sha256": canonical_sha(sorted(code_hashes)),
    }


def entries(order: Sequence[str], values: Sequence[int]) -> list[dict[str, Any]]:
    require(len(order) >= values[-1] and len(set(order)) == len(order), "invalid endpoint order")
    return [
        {"budget": int(budget), "endpoint_ids": sorted(order[: int(budget)])}
        for budget in values
    ]


def support_gates(
    acquisition: dict[str, Any], evaluation: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, bool]:
    gates = protocol["support_gates_before_selection"]
    acq_task = acquisition["maximum_single_task_pair_share"]
    eval_task = evaluation["maximum_single_task_pair_share"]
    return {
        "minimum_acquisition_pairs": acquisition["pairs"] >= gates["minimum_acquisition_pairs"],
        "minimum_acquisition_endpoints": acquisition["endpoints"] >= gates["minimum_acquisition_endpoints"],
        "minimum_acquisition_physical_runs": acquisition["physical_runs"]
        >= gates["minimum_acquisition_physical_runs"],
        "minimum_acquisition_tasks": acquisition["tasks"] >= gates["minimum_acquisition_tasks"],
        "maximum_acquisition_single_task_pair_share": acq_task["numerator"]
        * gates["maximum_single_task_pair_share_denominator"]
        <= acq_task["denominator"] * gates["maximum_single_task_pair_share_numerator"],
        "minimum_evaluation_pairs": evaluation["pairs"] >= gates["minimum_evaluation_pairs"],
        "minimum_evaluation_endpoints": evaluation["endpoints"] >= gates["minimum_evaluation_endpoints"],
        "minimum_evaluation_physical_runs": evaluation["physical_runs"]
        >= gates["minimum_evaluation_physical_runs"],
        "minimum_evaluation_tasks": evaluation["tasks"] >= gates["minimum_evaluation_tasks"],
        "maximum_evaluation_single_task_pair_share": eval_task["numerator"]
        * gates["maximum_single_task_pair_share_denominator"]
        <= eval_task["denominator"] * gates["maximum_single_task_pair_share_numerator"],
    }


def public_has_no_identities(public: dict[str, Any], graph: Any) -> bool:
    rendered = canonical_bytes(public).decode("utf-8")
    identities = set(graph.nodes)
    identities.update(edge.parent for edge in graph.edges)
    identities.update(edge.task for edge in graph.edges)
    identities.update(edge.run for edge in graph.edges)
    return not any(json.dumps(value, ensure_ascii=False) in rendered for value in identities)


def build(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any] | None]:
    protocol, protocol_sha = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    compatibility, compatibility_sha = load_compatibility(
        args.compatibility.resolve(),
        args.compatibility_sha256,
        args.protocol.resolve(),
        protocol_sha,
        args.selection_root.resolve(),
    )
    require(COMMIT_RE.fullmatch(args.source_commit) is not None, "source commit")
    verify_runtime_sources(args.repo_root, protocol, compatibility)
    verify_program_binding(args.repo_root, protocol, compatibility)
    selection, candidate, increment_cards, increment_runs, append_only = compatible_selection_and_increment(
        args.state_root.resolve(),
        args.selection_root.resolve(),
        args.repo_root.resolve(),
        protocol,
        compatibility,
    )
    full_graph, pair_bindings = forward.structural_pair_graph(
        args.state_root.resolve(), candidate, increment_cards, increment_runs
    )
    split_salt = protocol["population"]["run_split_salt"]
    acquisition_runs, evaluation_runs = partition_runs(increment_runs, split_salt)
    acquisition_graph = subgraph(full_graph, acquisition_runs)
    evaluation_graph = subgraph(full_graph, evaluation_runs)
    acquisition_profile = graph_profile(acquisition_graph)
    evaluation_profile = graph_profile(evaluation_graph)
    gates = support_gates(acquisition_profile, evaluation_profile, protocol)
    split_private = {
        "acquisition_run_ids": list(acquisition_runs),
        "evaluation_run_ids": list(evaluation_runs),
    }
    split_sha = canonical_sha(split_private)
    public: dict[str, Any] = {
        "protocol": PUBLIC_PROTOCOL,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "selection_container_compatibility_sha256": compatibility_sha,
        "analysis_source_commit": args.source_commit,
        "candidate_snapshot_sha256": selection["candidate_snapshot_sha256"],
        "selection_container": {
            "outer_sha256sums_sha256": selection["outer_selection_sha256sums_sha256"],
            "core_projection_sha256sums_sha256": selection[
                "core_projection_sha256sums_sha256"
            ],
            "manifest_bound_auxiliary_receipt_count": len(
                compatibility["selection_container"]["manifest_bound_auxiliary_basenames"]
            ),
        },
        "append_only": append_only,
        "pair_file_bindings": pair_bindings,
        "run_partition": {
            "algorithm": protocol["population"]["run_split_algorithm"],
            "acquisition_physical_runs": len(acquisition_runs),
            "evaluation_physical_runs": len(evaluation_runs),
            "overlap": 0,
            "partition_sha256": split_sha,
        },
        "acquisition_graph": acquisition_profile,
        "evaluation_graph": evaluation_profile,
        "support_gates": gates,
        "scope": {
            "outcome_blind_code_and_topology_only": True,
            "label_grade_gap_prediction_accuracy_utility_runtime_used": False,
            "prospective_values_read": False,
            "first960_closure_opened": False,
            "raw_identities_publicly_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }
    if not all(gates.values()):
        public.update(
            {
                "classification": "VCCD_TARGET522_SELECTION_LIMITED_SUPPORT",
                "checkpoints": None,
                "arm_metrics": None,
                "yield_solver": None,
                "private_selection_sha256": None,
            }
        )
        require(public_has_no_identities(public, full_graph), "public identity leak")
        return public, None

    values = checkpoints(acquisition_graph, protocol)
    uniform_seed, uniform_order, uniform_summary = endpoint_smoke.representative_uniform_seed(
        acquisition_graph, values
    )
    baseline, yield_floors, _integrated = forward.exact_baseline(acquisition_graph, values)
    floors = forward.fixed_floors(baseline, values)
    solver, yield_private = forward.solve_private(
        acquisition_graph,
        values,
        yield_floors,
        int(floors["integrated_closed_edges"]),
        int(floors["integrated_tasks"]),
        int(floors["integrated_physical_runs"]),
        int(floors["terminal_parents"]),
        float(protocol["selection"]["yield_guarded"]["solver_time_limit_seconds"]),
    )
    yield_gates = None
    yield_entries = None
    if solver["status"] == "FEASIBLE_WITNESS":
        require(yield_private is not None, "missing yield witness")
        yield_gates = forward.gates_for_witness(solver, baseline, floors)
        require(all(yield_gates.values()), "yield witness gate")
        yield_entries = yield_private["selected_endpoint_ids_by_checkpoint"]
    else:
        require(yield_private is None, "unexpected yield witness")

    vccd, vccd_summary = vccd_order(
        acquisition_graph,
        candidate.card_payloads,
        values[-1],
        protocol,
    )
    arm_entries: dict[str, Any] = {
        "exact_b_uniform_edge": entries(uniform_order, values),
        "vertex_cost_contrast_design": entries(vccd, values),
        "yield_guarded_breadth": yield_entries,
    }
    arm_metrics = {
        arm: (
            None
            if selection_entries is None
            else [
                forward.metrics_for_selection(
                    acquisition_graph, set(entry["endpoint_ids"]), int(entry["budget"])
                )
                for entry in selection_entries
            ]
        )
        for arm, selection_entries in arm_entries.items()
    }
    private = {
        "protocol": PRIVATE_PROTOCOL,
        "protocol_sha256": protocol_sha,
        "selection_container_compatibility_sha256": compatibility_sha,
        "analysis_source_commit": args.source_commit,
        "candidate_snapshot_sha256": selection["candidate_snapshot_sha256"],
        "run_partition": split_private,
        "checkpoints": values,
        "fit_checkpoint_numerators": protocol["selection"]["fit_checkpoint_numerators"],
        "arms": arm_entries,
        "selection_fingerprint_sha256": canonical_sha(arm_entries),
        "raw_identities_publicly_emitted": False,
        "prospective_values_read": False,
    }
    public.update(
        {
            "classification": (
                "VCCD_TARGET522_SELECTION_READY_THREE_ARMS"
                if yield_entries is not None
                else "VCCD_TARGET522_SELECTION_READY_YIELD_BASELINE_UNAVAILABLE"
            ),
            "checkpoints": values,
            "uniform_baseline": uniform_summary,
            "vccd": vccd_summary,
            "yield_baseline": baseline,
            "yield_floors": floors,
            "yield_solver": solver,
            "yield_witness_gates": yield_gates,
            "arm_metrics": arm_metrics,
            "private_selection_sha256": canonical_sha(private),
        }
    )
    require(uniform_seed == uniform_summary["representative_seed"], "uniform seed drift")
    require(public_has_no_identities(public, full_graph), "public identity leak")
    return public, private


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--compatibility", type=Path, required=True)
    parser.add_argument("--compatibility-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--selection-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    public, private = build(args)
    if private is not None:
        write_exclusive(args.private_output.resolve(), private)
        require(
            file_sha(args.private_output.resolve()) == public["private_selection_sha256"],
            "private write hash",
        )
    else:
        require(not args.private_output.exists(), "unexpected private output")
    write_exclusive(args.public_output.resolve(), public)
    print(
        json.dumps(
            {
                "status": public["status"],
                "classification": public["classification"],
                "protocol_sha256": public["protocol_sha256"],
                "public_output_sha256": file_sha(args.public_output.resolve()),
                "private_selection_present": private is not None,
                "scope": public["scope"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
