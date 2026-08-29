from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import hashlib
import itertools
import json
from pathlib import Path

import pytest

from phase1 import confirm_yield_guarded_breadth_forward_target522 as producer
from phase1 import falsify_historical_run_split_breadth_pareto as graph_impl
from phase1 import verify_yield_guarded_breadth_forward_target522 as verifier
from phase1.tests import test_tree_within_stratum_forward_target522_audit as target_fixture


def synthetic_graph():
    engine = graph_impl.engine
    return graph_impl.graph_from_edges(
        [
            engine.Edge(
                f"u{index}",
                f"v{index}",
                f"p{index}",
                f"task{index % 4}",
                f"run{index}",
            )
            for index in range(12)
        ]
    )


def test_protocol_is_frozen_with_exact_budget_contract() -> None:
    path = Path("phase1/yield_guarded_breadth_forward_target522_v1.json")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    protocol, actual = producer.load_protocol(path, digest)
    assert actual == digest
    assert protocol["freeze_state"]["candidate_identity_counts_or_profile_seen"] is False
    assert "selected_endpoints equals" in protocol["acquisition"][
        "uniform_edge_exact_budget_contract"
    ]["required_invariant"]


def test_protocol_rejects_candidate_informed_freeze(tmp_path: Path) -> None:
    source = json.loads(
        Path("phase1/yield_guarded_breadth_forward_target522_v1.json").read_text(
            encoding="utf-8"
        )
    )
    source["freeze_state"]["candidate_identity_counts_or_profile_seen"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(producer.ForwardBreadthError, match="candidate seen"):
        producer.load_protocol(path, digest)


def test_exact_baseline_has_independent_implementation_agreement() -> None:
    graph = synthetic_graph()
    budgets = [18, 20, 22, 24]
    first, floors, integrated = producer.exact_baseline(graph, budgets)
    second = verifier.independent_baseline(graph, budgets)
    assert first == second
    assert floors == [
        second["by_budget_nearest_rank_median"][str(value)]["closed_edges"]
        for value in budgets
    ]
    assert integrated == second["integrated_trajectory_nearest_rank_median"]
    assert second["all_rows_exact_endpoint_budget"] is True


def test_private_solver_witness_recomputes_all_fixed_gates() -> None:
    graph = synthetic_graph()
    budgets = [18, 20, 22, 24]
    baseline, pointwise, _integrated = producer.exact_baseline(graph, budgets)
    floors = producer.fixed_floors(baseline, budgets)
    # This disjoint-edge fixture already saturates task/run breadth under the
    # random baseline, so a >1 breadth ratio is intentionally impossible.  The
    # test isolates exact-B/nesting/private-witness mechanics with nonbinding
    # breadth floors; separate production gates remain fixed by the protocol.
    floors["integrated_tasks"] = 0
    floors["integrated_physical_runs"] = 0
    public_solver, private = producer.solve_private(
        graph,
        budgets,
        pointwise,
        int(floors["integrated_closed_edges"]),
        int(floors["integrated_tasks"]),
        int(floors["integrated_physical_runs"]),
        int(floors["terminal_parents"]),
        30,
    )
    assert public_solver["status"] == "FEASIBLE_WITNESS"
    assert private is not None
    assert private["selection_fingerprint_sha256"] == verifier.canonical_sha(
        private["selected_endpoint_ids_by_checkpoint"]
    )
    metrics = []
    previous: set[str] = set()
    for entry in private["selected_endpoint_ids_by_checkpoint"]:
        current = set(entry["endpoint_ids"])
        assert previous <= current
        assert len(current) == entry["budget"]
        metrics.append(verifier.selection_metrics(graph, current, entry["budget"]))
        previous = current
    assert metrics == public_solver["metrics"]
    assert all(verifier.witness_gates(metrics, floors).values())


def test_independent_solver_encoding_matches_feasible_and_infeasible_status() -> None:
    pytest.importorskip("scipy")
    graph = synthetic_graph()
    budgets = [18, 20, 22, 24]
    baseline, _pointwise, _integrated = producer.exact_baseline(graph, budgets)
    floors = producer.fixed_floors(baseline, budgets)
    floors["integrated_tasks"] = 0
    floors["integrated_physical_runs"] = 0
    assert verifier.independent_solver_status(graph, budgets, floors, 30) == (
        "FEASIBLE_WITNESS"
    )
    impossible = copy.deepcopy(floors)
    impossible["pointwise_closed_edges"][0] = len(graph.edges) + 1
    assert verifier.independent_solver_status(graph, budgets, impossible, 30) == (
        "INFEASIBLE_PROVEN"
    )


def test_public_identity_guard_detects_endpoint_leak() -> None:
    graph = synthetic_graph()
    assert verifier.no_public_identities({"aggregate": 1}, graph)
    assert not verifier.no_public_identities({"bad_endpoint": "u0"}, graph)


def test_independent_verifier_does_not_import_shared_constraint_or_forward_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "develop_yield_guarded_breadth_feasibility_v2" not in source
    assert "confirm_yield_guarded_breadth_forward_target522" not in source


def add_structural_pairs_and_rebind(
    state: Path,
    baseline_sha: str,
    candidate_sha: str,
    *,
    candidate_tasks: int = 8,
) -> None:
    summaries: dict[str, str] = {}
    registries: dict[str, dict] = {}
    for drop in ("drop-old", "drop-new"):
        intake = state / "intakes" / drop
        cards = [
            json.loads(line)
            for line in (intake / "eligible_blind_manifest.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for row in cards:
            grouped[(row["task"], row["run_id"], row["lineage"]["parent"])].append(
                row["card_id"]
            )
        pairs = [
            {"task": task, "run_id": run, "parent": parent, "left": left, "right": right}
            for (task, run, parent), children in sorted(grouped.items())
            for left, right in itertools.combinations(sorted(children), 2)
        ]
        pair_sha = target_fixture.write_jsonl(
            intake / "eligible_structural_pairs.jsonl", pairs
        )
        summary = json.loads((intake / "summary.json").read_text(encoding="utf-8"))
        summary["outputs"]["eligible_structural_pairs_sha256"] = pair_sha
        summary_sha = target_fixture.write_json(intake / "summary.json", summary)
        summaries[drop] = summary_sha
        registries[drop] = {
            "drop_id": drop,
            "intake_dir": str(intake.resolve()),
            "summary_sha256": summary_sha,
        }
    baseline_root = state / "snapshots" / baseline_sha
    candidate_root = state / "snapshots" / candidate_sha
    baseline_runs = [
        json.loads(line)
        for line in (baseline_root / "accumulator" / "provisional_runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    candidate_runs = [
        json.loads(line)
        for line in (candidate_root / "accumulator" / "provisional_runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    target_fixture.make_snapshot(
        state,
        baseline_sha,
        [registries["drop-old"]],
        {"drop-old": summaries["drop-old"]},
        baseline_runs,
        tasks=1,
    )
    target_fixture.make_snapshot(
        state,
        candidate_sha,
        [registries["drop-old"], registries["drop-new"]],
        summaries,
        candidate_runs,
        tasks=candidate_tasks,
    )


def support_snapshots(tmp_path: Path) -> tuple[Path, str, str]:
    state, baseline_sha, candidate_sha = target_fixture.synthetic_snapshots(tmp_path)
    baseline_root = state / "snapshots" / baseline_sha
    baseline_registry = [
        json.loads(line)
        for line in (baseline_root / "intake_registry.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    baseline_runs = [
        json.loads(line)
        for line in (baseline_root / "accumulator" / "provisional_runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    baseline_summary = target_fixture.digest(state / "intakes" / "drop-old" / "summary.json")
    new_cards: list[dict] = []
    new_runs: list[dict] = []
    for index in range(87):
        run = f"support-run-{index:03d}"
        task = f"support-task-{index % 36:02d}"
        root = f"support-root-{index:03d}"
        left = f"support-left-{index:03d}"
        right = f"support-right-{index:03d}"
        new_cards.extend(
            [
                target_fixture.card(root, run, task, "missing", 0),
                target_fixture.card(left, run, task, root, 1),
                target_fixture.card(right, run, task, root, 1),
                target_fixture.card(f"{left}-a", run, task, left, 2),
                target_fixture.card(f"{left}-b", run, task, left, 2),
                target_fixture.card(f"{right}-a", run, task, right, 2),
                target_fixture.card(f"{right}-b", run, task, right, 2),
            ]
        )
        new_runs.append(target_fixture.run_row(run, task, "drop-new", 7))
    new_registry, new_summary = target_fixture.make_intake(
        state, "drop-new", new_cards
    )
    target_fixture.make_snapshot(
        state,
        candidate_sha,
        baseline_registry + [new_registry],
        {"drop-old": baseline_summary, "drop-new": new_summary},
        baseline_runs + new_runs,
        tasks=37,
    )
    add_structural_pairs_and_rebind(
        state, baseline_sha, candidate_sha, candidate_tasks=37
    )
    return state, baseline_sha, candidate_sha


def prepare_forward_fixture(
    tmp_path: Path, state: Path, baseline_sha: str, candidate_sha: str
) -> tuple[Path, Path, Path, str]:
    baseline = producer.target.load_blind_snapshot(state, baseline_sha)
    candidate = producer.target.load_blind_snapshot(state, candidate_sha)
    original = copy.deepcopy(target_fixture.protocol())
    original["freeze_state"]["baseline_snapshot_sha256"] = baseline_sha
    original["freeze_state"]["baseline_counts"] = {
        "provisional_first960_runs": baseline.bindings["runs"],
        "eligible_endpoints": baseline.bindings["endpoints"],
        "tasks": baseline.bindings["tasks"],
    }
    original["activation_rule"]["target_total_physical_runs"] = candidate.bindings["runs"]
    original["activation_rule"]["minimum_disjoint_increment_physical_runs"] = 87
    fake_repo = tmp_path / "repo"
    original_path = (
        fake_repo / "phase1" / "tree_linearization_within_stratum_forward_target522_v2.json"
    )
    monitor_path = (
        fake_repo
        / "phase1"
        / "scripts"
        / "latch_tree_within_stratum_forward_target522_20260828.sh"
    )
    target_fixture.write_json(original_path, original)
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_bytes(target_fixture.MONITOR_PATH.read_bytes())
    baseline_observation = (
        baseline_sha,
        baseline.bindings["runs"],
        baseline.bindings["endpoints"],
        baseline.bindings["tasks"],
        baseline.bindings["accumulator_summary_sha256"],
        baseline.bindings["registry_sha256"],
        baseline.bindings["provisional_runs_sha256"],
        "2026-08-28T00:00:00Z",
    )
    candidate_observation = (
        candidate_sha,
        candidate.bindings["runs"],
        candidate.bindings["endpoints"],
        candidate.bindings["tasks"],
        candidate.bindings["accumulator_summary_sha256"],
        candidate.bindings["registry_sha256"],
        candidate.bindings["provisional_runs_sha256"],
        "2026-08-28T00:00:02Z",
    )
    selection = target_fixture.make_selection(
        tmp_path,
        spec=original,
        protocol_path=original_path,
        monitor_path=monitor_path,
        baseline_observation=baseline_observation,
        candidate_observation=candidate_observation,
    )
    forward = json.loads(
        Path("phase1/yield_guarded_breadth_forward_target522_v1.json").read_text(
            encoding="utf-8"
        )
    )
    forward["freeze_state"]["baseline_snapshot_sha256"] = baseline_sha
    forward["freeze_state"]["target522_selection_root"] = str(selection.resolve())
    forward["freeze_state"]["target522_selection_protocol"] = {
        "path": "phase1/tree_linearization_within_stratum_forward_target522_v2.json",
        "sha256": target_fixture.digest(original_path),
    }
    forward["freeze_state"]["target522_selection_monitor"] = {
        "path": "phase1/scripts/latch_tree_within_stratum_forward_target522_20260828.sh",
        "sha256": target_fixture.digest(monitor_path),
    }
    forward["population"]["physical_run_increment_minimum"] = 87
    protocol_path = fake_repo / "phase1" / "yield_guarded_breadth_forward_target522_v1.json"
    protocol_sha = target_fixture.write_json(protocol_path, forward)
    return selection, fake_repo, protocol_path, protocol_sha


def test_end_to_end_limited_support_uses_two_independent_loaders(tmp_path: Path) -> None:
    state, baseline_sha, candidate_sha = target_fixture.synthetic_snapshots(tmp_path)
    add_structural_pairs_and_rebind(state, baseline_sha, candidate_sha)
    baseline = producer.target.load_blind_snapshot(state, baseline_sha)
    candidate = producer.target.load_blind_snapshot(state, candidate_sha)

    original = copy.deepcopy(target_fixture.protocol())
    original["freeze_state"]["baseline_snapshot_sha256"] = baseline_sha
    original["freeze_state"]["baseline_counts"] = {
        "provisional_first960_runs": baseline.bindings["runs"],
        "eligible_endpoints": baseline.bindings["endpoints"],
        "tasks": baseline.bindings["tasks"],
    }
    original["activation_rule"]["target_total_physical_runs"] = candidate.bindings["runs"]
    original["activation_rule"]["minimum_disjoint_increment_physical_runs"] = 87
    fake_repo = tmp_path / "repo"
    original_path = (
        fake_repo / "phase1" / "tree_linearization_within_stratum_forward_target522_v2.json"
    )
    monitor_path = (
        fake_repo
        / "phase1"
        / "scripts"
        / "latch_tree_within_stratum_forward_target522_20260828.sh"
    )
    target_fixture.write_json(original_path, original)
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_bytes(target_fixture.MONITOR_PATH.read_bytes())
    baseline_observation = (
        baseline_sha,
        baseline.bindings["runs"],
        baseline.bindings["endpoints"],
        baseline.bindings["tasks"],
        baseline.bindings["accumulator_summary_sha256"],
        baseline.bindings["registry_sha256"],
        baseline.bindings["provisional_runs_sha256"],
        "2026-08-28T00:00:00Z",
    )
    candidate_observation = (
        candidate_sha,
        candidate.bindings["runs"],
        candidate.bindings["endpoints"],
        candidate.bindings["tasks"],
        candidate.bindings["accumulator_summary_sha256"],
        candidate.bindings["registry_sha256"],
        candidate.bindings["provisional_runs_sha256"],
        "2026-08-28T00:00:02Z",
    )
    selection = target_fixture.make_selection(
        tmp_path,
        spec=original,
        protocol_path=original_path,
        monitor_path=monitor_path,
        baseline_observation=baseline_observation,
        candidate_observation=candidate_observation,
    )

    forward = json.loads(
        Path("phase1/yield_guarded_breadth_forward_target522_v1.json").read_text(
            encoding="utf-8"
        )
    )
    forward["freeze_state"]["baseline_snapshot_sha256"] = baseline_sha
    forward["freeze_state"]["target522_selection_root"] = str(selection.resolve())
    forward["freeze_state"]["target522_selection_protocol"] = {
        "path": "phase1/tree_linearization_within_stratum_forward_target522_v2.json",
        "sha256": target_fixture.digest(original_path),
    }
    forward["freeze_state"]["target522_selection_monitor"] = {
        "path": "phase1/scripts/latch_tree_within_stratum_forward_target522_20260828.sh",
        "sha256": target_fixture.digest(monitor_path),
    }
    forward["population"]["physical_run_increment_minimum"] = 87
    # The fixture has only 87 structural pairs, so the frozen 200-pair gate
    # must stop before baseline curves or a private witness are produced.
    protocol_path = fake_repo / "phase1" / "yield_guarded_breadth_forward_target522_v1.json"
    protocol_sha = target_fixture.write_json(protocol_path, forward)
    public_path = tmp_path / "public.json"
    private_path = tmp_path / "private.json"
    public, private = producer.build(
        argparse.Namespace(
            protocol=protocol_path,
            protocol_sha256=protocol_sha,
            source_commit="9" * 40,
            state_root=state,
            selection_root=selection,
            repo_root=fake_repo,
            public_output=public_path,
            private_output=private_path,
        )
    )
    assert private is None
    assert public["classification"] == (
        "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_LIMITED_SUPPORT"
    )
    assert public["graph_census"]["pairs"] == 87
    assert public["baseline"] is None
    assert "new-run" not in json.dumps(public, sort_keys=True)
    producer.write_exclusive(public_path, public)
    verification = verifier.verify(
        argparse.Namespace(
            protocol=protocol_path,
            protocol_sha256=protocol_sha,
            state_root=state,
            selection_root=selection,
            repo_root=fake_repo,
            public_result=public_path,
            private_witness=private_path,
            output=tmp_path / "verification.json",
        )
    )
    assert verification["classification"] == public["classification"]
    assert verification["boundary"]["forward_producer_imported"] is False
    assert verification["boundary"]["pair_graph_reconstructed"] is True


def test_end_to_end_supported_graph_writes_private_witness_and_recomputes_it(
    tmp_path: Path,
) -> None:
    pytest.importorskip("scipy")
    state, baseline_sha, candidate_sha = support_snapshots(tmp_path)
    selection, fake_repo, protocol_path, protocol_sha = prepare_forward_fixture(
        tmp_path, state, baseline_sha, candidate_sha
    )
    public_path = tmp_path / "supported-public.json"
    private_path = tmp_path / "supported-private.json"
    public, private = producer.build(
        argparse.Namespace(
            protocol=protocol_path,
            protocol_sha256=protocol_sha,
            source_commit="8" * 40,
            state_root=state,
            selection_root=selection,
            repo_root=fake_repo,
            public_output=public_path,
            private_output=private_path,
        )
    )
    assert all(public["support_gates"].values())
    assert public["graph_census"] == {
        "pairs": 261,
        "endpoints": 522,
        "parents": 261,
        "physical_runs": 87,
        "tasks": 36,
        "maximum_single_task_pair_share": producer.ratio(9, 261),
        "maximum_single_run_pair_share": producer.ratio(3, 261),
    }
    assert public["classification"] == (
        "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_JOINTLY_FEASIBLE"
    )
    assert private is not None
    assert "support-run" not in json.dumps(public, sort_keys=True)
    producer.write_exclusive(private_path, private)
    producer.write_exclusive(public_path, public)
    assert private_path.stat().st_mode & 0o077 == 0
    verification = verifier.verify(
        argparse.Namespace(
            protocol=protocol_path,
            protocol_sha256=protocol_sha,
            state_root=state,
            selection_root=selection,
            repo_root=fake_repo,
            public_result=public_path,
            private_witness=private_path,
            output=tmp_path / "supported-verification.json",
        )
    )
    assert verification["classification"] == public["classification"]
    assert verification["private_witness_recomputed"] is True
    assert verification["private_metrics"] == public["solver"]["metrics"]
    assert all(verification["witness_gates"].values())
