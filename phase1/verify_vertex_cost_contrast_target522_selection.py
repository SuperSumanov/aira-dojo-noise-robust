#!/usr/bin/env python3
"""Independent verifier for outcome-blind Target-522 vertex-cost selections."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
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
PUBLIC_PROTOCOL = "vertex-cost-contrast-target522-selection-public-v1"
PRIVATE_PROTOCOL = "vertex-cost-contrast-target522-selection-private-v1"
VERIFICATION_PROTOCOL = "vertex-cost-contrast-target522-selection-verification-v1"
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class IndependentVerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentVerificationError(message)


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
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name")
    require(
        protocol.get("status") == "FROZEN_BEFORE_TARGET522_CANDIDATE_PROFILE_OR_VALUES",
        "protocol status",
    )
    freeze = protocol.get("freeze_state") or {}
    require(freeze.get("target522_candidate_present") is False, "candidate seen before freeze")
    require(freeze.get("prospective_values_read") is False, "values seen before freeze")
    require(protocol["release_gate"]["selection_stage_may_read_outcomes"] is False, "release gate")
    return protocol, actual


def verify_runtime_sources(repo_root: Path, protocol: dict[str, Any]) -> None:
    root = repo_root.resolve()
    require(root.is_dir() and not repo_root.is_symlink(), "unsafe repo root")
    bindings = protocol["freeze_state"]["runtime_dependencies"]
    require(isinstance(bindings, list) and bindings, "runtime dependencies")
    seen: set[str] = set()
    for row in bindings:
        require(set(row) == {"path", "sha256"}, "dependency schema")
        relative, expected = row["path"], row["sha256"]
        require(
            isinstance(relative, str)
            and relative.startswith("phase1/")
            and ".." not in Path(relative).parts
            and isinstance(expected, str)
            and SHA_RE.fullmatch(expected) is not None
            and relative not in seen,
            "dependency binding",
        )
        seen.add(relative)
        candidate = (root / relative).resolve()
        require(candidate.is_relative_to(root), "dependency escapes repo")
        require(file_sha(candidate) == expected, "dependency SHA mismatch")


def verify_program_binding(repo_root: Path, protocol: dict[str, Any]) -> None:
    root = repo_root.resolve()
    binding = protocol["freeze_state"]["independent_selection_verifier"]
    path = (root / binding["path"]).resolve()
    require(path.is_relative_to(root), "verifier escapes repo")
    require(file_sha(path) == binding["sha256"], "verifier SHA mismatch")


def run_key(salt: str, task: str, run: str) -> tuple[str, str]:
    digest = hashlib.sha256("\0".join((salt, task, run)).encode("utf-8")).hexdigest()
    return digest, run


def independent_partition(
    runs: Mapping[str, Mapping[str, Any]], salt: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    by_task: dict[str, list[str]] = defaultdict(list)
    for run in sorted(runs):
        task = runs[run].get("task")
        require(isinstance(task, str) and task, "run task")
        by_task[task].append(run)
    train: list[str] = []
    test: list[str] = []
    for task in sorted(by_task):
        ordered = sorted(by_task[task], key=lambda run: run_key(salt, task, run))
        if len(ordered) == 1:
            target = train if int(run_key(salt, task, ordered[0])[0][:16], 16) % 5 < 3 else test
            target.extend(ordered)
        else:
            count = min(len(ordered) - 1, max(1, (2 * len(ordered)) // 5))
            test.extend(ordered[:count])
            train.extend(ordered[count:])
    require(train and test, "empty independent partition")
    require(set(train).isdisjoint(test) and set(train) | set(test) == set(runs), "partition closure")
    return tuple(sorted(train)), tuple(sorted(test))


def independent_subgraph(graph: Any, runs: Sequence[str]) -> Any:
    allowed = set(runs)
    edges = [edge for edge in graph.edges if edge.run in allowed]
    return graph_source.graph_from_edges(edges)


def profile(graph: Any) -> dict[str, Any]:
    tasks = Counter(edge.task for edge in graph.edges)
    runs = Counter(edge.run for edge in graph.edges)
    pairs = len(graph.edges)
    return {
        "pairs": pairs,
        "endpoints": len(graph.nodes),
        "parents": len({edge.parent for edge in graph.edges}),
        "physical_runs": len(runs),
        "tasks": len(tasks),
        "maximum_single_task_pair_share": forward.ratio(max(tasks.values(), default=0), max(1, pairs)),
        "maximum_single_run_pair_share": forward.ratio(max(runs.values(), default=0), max(1, pairs)),
        "orientation_free_graph_sha256": graph_source.graph_fingerprint(graph),
    }


def independent_support(acquisition: dict[str, Any], evaluation: dict[str, Any], protocol: dict[str, Any]) -> dict[str, bool]:
    spec = protocol["support_gates_before_selection"]
    result: dict[str, bool] = {}
    for label, observed in (("acquisition", acquisition), ("evaluation", evaluation)):
        for field in ("pairs", "endpoints", "physical_runs", "tasks"):
            result[f"minimum_{label}_{field}"] = observed[field] >= spec[f"minimum_{label}_{field}"]
        share = observed["maximum_single_task_pair_share"]
        result[f"maximum_{label}_single_task_pair_share"] = (
            share["numerator"] * spec["maximum_single_task_pair_share_denominator"]
            <= share["denominator"] * spec["maximum_single_task_pair_share_numerator"]
        )
    return result


def independent_checkpoints(graph: Any, protocol: dict[str, Any]) -> list[int]:
    spec = protocol["selection"]
    denominator = int(spec["budget_fraction_denominator"])
    result = [
        (len(graph.nodes) * int(numerator)) // denominator
        for numerator in spec["trajectory_numerators"]
    ]
    require(result == sorted(set(result)) and len(result) == 6 and result[0] >= 2, "checkpoint closure")
    return result


def independent_groups(graph: Any) -> list[ParentGroup]:
    grouped: dict[str, dict[str, Any]] = {}
    for edge in graph.edges:
        row = grouped.setdefault(
            edge.parent,
            {"task": edge.task, "run": edge.run, "endpoints": set(), "pairs": set()},
        )
        require(row["task"] == edge.task and row["run"] == edge.run, "parent context")
        row["endpoints"].update(edge.endpoints)
        row["pairs"].add(edge.endpoints)
    result = []
    for parent in sorted(grouped):
        row = grouped[parent]
        endpoints = tuple(sorted(row["endpoints"]))
        require(len(row["pairs"]) == math.comb(len(endpoints), 2), "independent clique closure")
        result.append(ParentGroup(parent, row["task"], row["run"], endpoints))
    require(result, "empty independent groups")
    return result


def independent_vccd(
    graph: Any,
    payloads: Mapping[str, Mapping[str, Any]],
    maximum_budget: int,
    protocol: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    spec = protocol["selection"]["vccd"]
    vectors = {}
    code_hashes = []
    for endpoint in sorted(graph.nodes):
        row = payloads.get(endpoint)
        require(isinstance(row, Mapping), "missing payload")
        code, expected = row.get("code"), row.get("code_sha256")
        require(
            isinstance(code, str)
            and isinstance(expected, str)
            and hashlib.sha256(code.encode("utf-8")).hexdigest() == expected,
            "code binding",
        )
        vectors[endpoint] = code_hash_feature(
            code,
            dimension=int(spec["dimension"]),
            ngram_min=int(spec["character_ngram_range"][0]),
            ngram_max=int(spec["character_ngram_range"][1]),
            max_chars=int(spec["maximum_characters"]),
        )
        code_hashes.append(expected)
    selected = select_vertex_cost_contrasts(
        independent_groups(graph),
        vectors,
        budget=maximum_budget,
        ridge=float(spec["ridge"]),
        task_share_denominator=int(spec["task_terminal_share_denominator"]),
        run_share_denominator=int(spec["run_terminal_share_denominator"]),
    )
    return list(selected.selected_endpoints), {
        "terminal_information_logdet_gain": selected.information_logdet_gain,
        "terminal_numerical_feature_rank": selected.numerical_feature_rank,
        "terminal_task_endpoint_cap": selected.task_cap,
        "terminal_run_endpoint_cap": selected.run_cap,
        "bound_code_sha256_multiset_sha256": canonical_sha(sorted(code_hashes)),
    }


def selected_sets(rows: Any, budgets: Sequence[int]) -> list[set[str]]:
    require(isinstance(rows, list) and len(rows) == len(budgets), "selection row count")
    result: list[set[str]] = []
    previous: set[str] = set()
    for row, budget in zip(rows, budgets):
        require(set(row) == {"budget", "endpoint_ids"} and row["budget"] == budget, "selection row schema")
        identifiers = row["endpoint_ids"]
        require(identifiers == sorted(set(identifiers)) and len(identifiers) == budget, "selection exact budget")
        current = set(identifiers)
        require(previous <= current, "selection not nested")
        result.append(current)
        previous = current
    return result


def metrics(graph: Any, sets: Sequence[set[str]], budgets: Sequence[int]) -> list[dict[str, Any]]:
    return [
        forward.metrics_for_selection(graph, selected, budget)
        for selected, budget in zip(sets, budgets)
    ]


def no_public_identities(public: dict[str, Any], graph: Any) -> bool:
    rendered = canonical_bytes(public).decode("utf-8")
    identities = set(graph.nodes)
    identities.update(edge.parent for edge in graph.edges)
    identities.update(edge.task for edge in graph.edges)
    identities.update(edge.run for edge in graph.edges)
    return not any(json.dumps(value, ensure_ascii=False) in rendered for value in identities)


def verify(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    require(COMMIT_RE.fullmatch(args.source_commit) is not None, "source commit")
    verify_runtime_sources(args.repo_root, protocol)
    verify_program_binding(args.repo_root, protocol)
    public = forward.target.read_object(args.public_result.resolve())
    require(public.get("protocol") == PUBLIC_PROTOCOL and public.get("status") == "COMPLETE", "public result")
    require(public.get("protocol_sha256") == protocol_sha, "public protocol binding")
    require(public.get("analysis_source_commit") == args.source_commit, "public source binding")

    selection, candidate, increment_cards, increment_runs, append_only = forward.selection_and_increment(
        args.state_root.resolve(), args.selection_root.resolve(), args.repo_root.resolve(), protocol
    )
    graph, pair_bindings = forward.structural_pair_graph(
        args.state_root.resolve(), candidate, increment_cards, increment_runs
    )
    acquisition_runs, evaluation_runs = independent_partition(
        increment_runs, protocol["population"]["run_split_salt"]
    )
    acquisition_graph = independent_subgraph(graph, acquisition_runs)
    evaluation_graph = independent_subgraph(graph, evaluation_runs)
    acquisition_profile = profile(acquisition_graph)
    evaluation_profile = profile(evaluation_graph)
    gates = independent_support(acquisition_profile, evaluation_profile, protocol)
    split = {
        "acquisition_run_ids": list(acquisition_runs),
        "evaluation_run_ids": list(evaluation_runs),
    }
    require(public["candidate_snapshot_sha256"] == selection["candidate_snapshot_sha256"], "candidate binding")
    require(public["append_only"] == append_only, "append-only receipt")
    require(public["pair_file_bindings"] == pair_bindings, "pair binding")
    require(public["acquisition_graph"] == acquisition_profile, "acquisition profile")
    require(public["evaluation_graph"] == evaluation_profile, "evaluation profile")
    require(public["support_gates"] == gates, "support gates")
    require(public["run_partition"]["partition_sha256"] == canonical_sha(split), "split fingerprint")
    require(no_public_identities(public, graph), "public identity leak")

    if not all(gates.values()):
        require(
            public["classification"] == "VCCD_TARGET522_SELECTION_LIMITED_SUPPORT"
            and public["private_selection_sha256"] is None
            and not args.private_selection.exists(),
            "limited support disposition",
        )
        return {
            "protocol": VERIFICATION_PROTOCOL,
            "status": "VERIFIED",
            "classification": public["classification"],
            "protocol_sha256": protocol_sha,
            "public_result_sha256": file_sha(args.public_result.resolve()),
            "private_selection_sha256": None,
            "prospective_values_read": False,
        }

    private_path = args.private_selection.resolve()
    require(
        private_path.is_file()
        and (os.name == "nt" or private_path.stat().st_mode & 0o077 == 0),
        "private selection mode",
    )
    private = forward.target.read_object(private_path)
    require(private.get("protocol") == PRIVATE_PROTOCOL, "private protocol")
    require(private.get("protocol_sha256") == protocol_sha, "private protocol binding")
    require(private.get("analysis_source_commit") == args.source_commit, "private source binding")
    require(private.get("candidate_snapshot_sha256") == selection["candidate_snapshot_sha256"], "private candidate")
    require(file_sha(private_path) == public["private_selection_sha256"], "private SHA")
    require(private["run_partition"] == split, "private run partition")

    budgets = independent_checkpoints(acquisition_graph, protocol)
    require(private["checkpoints"] == public["checkpoints"] == budgets, "checkpoint binding")
    arms = private["arms"]
    require(set(arms) == {"exact_b_uniform_edge", "vertex_cost_contrast_design", "yield_guarded_breadth"}, "arm set")
    uniform_sets = selected_sets(arms["exact_b_uniform_edge"], budgets)
    vccd_sets = selected_sets(arms["vertex_cost_contrast_design"], budgets)
    require(all(values <= set(acquisition_graph.nodes) for values in uniform_sets + vccd_sets), "selection outside acquisition")
    require(all(not values & set(evaluation_graph.nodes) for values in uniform_sets + vccd_sets), "evaluation endpoint selected")

    uniform_seed, uniform_order, uniform_summary = endpoint_smoke.representative_uniform_seed(acquisition_graph, budgets)
    require(
        [set(uniform_order[:budget]) for budget in budgets] == uniform_sets
        and uniform_summary == public["uniform_baseline"]
        and uniform_seed == uniform_summary["representative_seed"],
        "uniform reconstruction",
    )
    vccd_order, vccd_summary = independent_vccd(
        acquisition_graph, candidate.card_payloads, budgets[-1], protocol
    )
    require([set(vccd_order[:budget]) for budget in budgets] == vccd_sets, "VCCD reconstruction")
    require(vccd_summary == public["vccd"], "VCCD summary")

    arm_metrics = {
        "exact_b_uniform_edge": metrics(acquisition_graph, uniform_sets, budgets),
        "vertex_cost_contrast_design": metrics(acquisition_graph, vccd_sets, budgets),
        "yield_guarded_breadth": None,
    }
    baseline, _yield_floors, _integrated = forward.exact_baseline(acquisition_graph, budgets)
    floors = forward.fixed_floors(baseline, budgets)
    require(public["yield_baseline"] == baseline and public["yield_floors"] == floors, "yield baseline")
    if arms["yield_guarded_breadth"] is None:
        require(public["classification"] == "VCCD_TARGET522_SELECTION_READY_YIELD_BASELINE_UNAVAILABLE", "yield unavailable class")
        require(public["yield_solver"]["status"] != "FEASIBLE_WITNESS", "missing feasible yield witness")
    else:
        yield_sets = selected_sets(arms["yield_guarded_breadth"], budgets)
        require(all(values <= set(acquisition_graph.nodes) for values in yield_sets), "yield outside acquisition")
        yield_metrics = metrics(acquisition_graph, yield_sets, budgets)
        integrated = {
            field: sum(int(row[field]) for row in yield_metrics)
            for field in ("closed_edges", "tasks", "physical_runs")
        }
        certificate = {"metrics": yield_metrics, "integrated": integrated}
        yield_gates = forward.gates_for_witness(certificate, baseline, floors)
        require(all(yield_gates.values()) and yield_gates == public["yield_witness_gates"], "yield certificate")
        require(public["classification"] == "VCCD_TARGET522_SELECTION_READY_THREE_ARMS", "three-arm class")
        arm_metrics["yield_guarded_breadth"] = yield_metrics
    require(arm_metrics == public["arm_metrics"], "arm metrics")
    require(private["selection_fingerprint_sha256"] == canonical_sha(arms), "selection fingerprint")
    require(private.get("prospective_values_read") is False, "private values read")
    return {
        "protocol": VERIFICATION_PROTOCOL,
        "status": "VERIFIED",
        "classification": public["classification"],
        "protocol_sha256": protocol_sha,
        "public_result_sha256": file_sha(args.public_result.resolve()),
        "private_selection_sha256": file_sha(private_path),
        "candidate_snapshot_sha256": selection["candidate_snapshot_sha256"],
        "run_partition_recomputed": True,
        "uniform_order_recomputed": True,
        "vccd_order_recomputed": True,
        "yield_witness_constraints_recomputed": arms["yield_guarded_breadth"] is not None,
        "prospective_values_read": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }


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
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--selection-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--public-result", type=Path, required=True)
    parser.add_argument("--private-selection", type=Path, required=True)
    parser.add_argument("--verification-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(args)
    write_exclusive(args.verification_output.resolve(), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "classification": result["classification"],
                "protocol_sha256": result["protocol_sha256"],
                "verification_output_sha256": file_sha(args.verification_output.resolve()),
                "prospective_values_read": result["prospective_values_read"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
