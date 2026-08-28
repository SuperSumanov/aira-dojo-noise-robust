from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from phase1 import audit_prospective_fuzzy_code_clones as producer_fingerprint
from phase1 import audit_tree_content_lineage_forward_target522 as producer
from phase1 import audit_tree_within_stratum_forward_target522 as snapshot_producer
from phase1 import verify_prospective_fuzzy_code_clones as verifier_fingerprint
from phase1 import verify_tree_content_lineage_forward_target522 as verifier
from phase1 import verify_tree_within_stratum_forward_target522 as snapshot_verifier
from phase1.tests import test_tree_within_stratum_forward_target522_audit as selection_helpers


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "tree_content_lineage_forward_target522_v1.json"
PRODUCER = ROOT / "phase1" / "audit_tree_content_lineage_forward_target522.py"
VERIFIER = ROOT / "phase1" / "verify_tree_content_lineage_forward_target522.py"
SELECTION_PROTOCOL = ROOT / "phase1" / "tree_linearization_within_stratum_forward_target522_v2.json"
SELECTION_MONITOR = (
    ROOT / "phase1" / "scripts" / "latch_tree_within_stratum_forward_target522_20260828.sh"
)
RUNNER = (
    ROOT
    / "phase1"
    / "scripts"
    / "run_tree_content_lineage_forward_target522_formal_20260828.sh"
)
MONITOR = (
    ROOT
    / "phase1"
    / "scripts"
    / "monitor_tree_content_lineage_forward_target522_formal_20260828.sh"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def rich_code(seed: int, mutation: int | None = None) -> str:
    operators = ["+", "-", "*", "//", "%", "**", "^", "&", "|"]
    state = seed
    sequence: list[str] = []
    for _index in range(48):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        sequence.append(operators[state % len(operators)])
    if mutation is not None:
        offset = mutation % len(sequence)
        sequence[offset] = operators[(operators.index(sequence[offset]) + 1) % len(operators)]
    lines = ["def solve(data):", "    value = data"]
    lines.extend(f"    value = value {operator} data" for operator in sequence)
    lines.append("    return value")
    return "\n".join(lines) + "\n"


def card(
    identity: str,
    run: str,
    task: str,
    parent: str,
    depth: int,
    code: str,
) -> dict:
    return {
        "card_id": identity,
        "task": task,
        "run_id": run,
        "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "lineage": {
            "depth": depth,
            "step": depth,
            "n_siblings": 2,
            "op": "draft" if depth == 0 else "debug",
            "parent": parent,
        },
        "generation_started_at_utc": "2026-08-28T00:00:00Z",
        "source_sha256": "a" * 64,
    }


def synthetic_cards() -> tuple[dict[str, dict], dict[str, frozenset[int]]]:
    payloads = [
        card("parent-a", "run-secret", "task-secret", "missing-a", 0, rich_code(11)),
        card("parent-b", "run-secret", "task-secret", "missing-b", 0, rich_code(29)),
        card("child-a", "run-secret", "task-secret", "parent-a", 1, rich_code(11, 7)),
        card("child-b", "run-secret", "task-secret", "parent-b", 1, rich_code(29, 13)),
    ]
    cards = {
        row["card_id"]: {
            "run": row["run_id"],
            "task": row["task"],
            "parent": row["lineage"]["parent"],
            "depth": row["lineage"]["depth"],
        }
        for row in payloads
    }
    fingerprints = {
        row["card_id"]: producer_fingerprint.identifier_erased_token_shingles(row["code"])
        for row in payloads
    }
    assert all(value is not None for value in fingerprints.values())
    return cards, fingerprints  # type: ignore[return-value]


def relaxed_protocol() -> dict:
    value = protocol()
    value["parent_recovery_estimands"]["task_breadth_minimum_edges"] = 1
    value["parent_recovery_estimands"]["physical_run_breadth_minimum_edges"] = 1
    return value


def metric_shell(
    exact_recovery: Fraction,
    no_depth_recovery: Fraction,
    flat_f1: Fraction,
) -> dict:
    mode = {
        "unique_top_recovery": producer.exact(exact_recovery),
        "unique_top_lift_over_uniform_random": producer.exact(Fraction(3, 5)),
        "exhaustive_wrong_parent_false_acceptance_rate": producer.exact(Fraction(1, 100)),
        "unique_top_breadth": {
            "task": {
                "fraction_at_or_above_17_over_20": producer.exact(Fraction(4, 5)),
                "maximum_edge_contribution_share": producer.exact(Fraction(1, 5)),
            },
            "physical_run": {
                "fraction_at_or_above_17_over_20": producer.exact(Fraction(4, 5)),
                "maximum_edge_contribution_share": producer.exact(Fraction(1, 10)),
            },
        },
    }
    return {
        "parent_recovery_modes": {
            "exact_preceding_depth": mode,
            "same_run_without_depth": {
                "unique_top_recovery": producer.exact(no_depth_recovery)
            },
        },
        "flat_pair_graph": {
            "same_population_oracle": {"maximum_f1": producer.exact(flat_f1)}
        },
    }


def test_protocol_discloses_development_and_freezes_exact_gates() -> None:
    value, actual = producer.load_protocol(PROTOCOL, digest(PROTOCOL))
    second, second_sha = verifier.protocol_file(PROTOCOL, digest(PROTOCOL))
    assert value == second
    assert actual == second_sha == digest(PROTOCOL)
    assert value["freeze_state"]["target522_candidate_snapshot_identity_seen"] is False
    assert value["development_evidence_seen_before_freeze"]["exact_depth_unique_top_recovery"] == "9196/9739"
    assert value["strong_content_concordance_gates"] == {
        "minimum_exact_depth_unique_top_recovery": "9/10",
        "minimum_exact_depth_lift_over_uniform_random": "1/2",
        "maximum_exhaustive_wrong_parent_false_acceptance": "1/50",
        "minimum_task_fraction_at_or_above_breadth_reference": "3/4",
        "minimum_physical_run_fraction_at_or_above_breadth_reference": "3/4",
        "maximum_single_task_edge_contribution_share": "2/5",
        "maximum_single_physical_run_edge_contribution_share": "1/5",
    }


def test_new_verifier_does_not_import_new_producer() -> None:
    source = VERIFIER.read_text(encoding="utf-8")
    assert "import audit_tree_content_lineage_forward_target522" not in source
    assert "from phase1 import audit_tree_content_lineage_forward_target522" not in source
    assert digest(PRODUCER) != digest(VERIFIER)


def test_identifier_erased_fingerprint_is_independent_and_exact() -> None:
    first = rich_code(11, 3)
    second = rich_code(11, 3).replace("value", "renamed").replace("data", "samples")
    producer_value = producer_fingerprint.identifier_erased_token_shingles(first)
    verifier_value = verifier_fingerprint.identifier_erased_shingles(second)
    assert producer_value is not None
    assert producer_value == verifier_value


def test_three_parent_candidate_modes_match_independent_implementation() -> None:
    cards, fingerprints = synthetic_cards()
    by_run = {"run-secret": sorted(cards)}
    edges = [("child-a", "parent-a"), ("child-b", "parent-b")]
    value = relaxed_protocol()
    for mode in ("exact_preceding_depth", "any_shallower_depth", "same_run_without_depth"):
        first = producer.evaluate_mode(mode, cards, fingerprints, by_run, edges, value)
        second = verifier.independent_mode(mode, cards, fingerprints, by_run, edges, value)
        assert first == second
        assert first["eligible_parent_edges"] == 2
        assert first["ambiguous_parent_edges"] == 2
        assert first["unique_top_recovery"] == producer.exact(Fraction(1, 1))
        rendered = json.dumps(first, sort_keys=True)
        assert "task-secret" not in rendered
        assert "run-secret" not in rendered


def test_unique_top_treats_a_tie_as_failure_and_never_accepts_tied_wrong_parent() -> None:
    cards = {
        "a": {"run": "r", "task": "t", "parent": "missing", "depth": 0},
        "b": {"run": "r", "task": "t", "parent": "missing", "depth": 0},
        "c": {"run": "r", "task": "t", "parent": "a", "depth": 1},
    }
    fingerprints = {
        "a": frozenset({1, 2, 3}),
        "b": frozenset({1, 2, 3}),
        "c": frozenset({1, 2, 3}),
    }
    value = relaxed_protocol()
    first = producer.evaluate_mode(
        "exact_preceding_depth", cards, fingerprints, {"r": ["a", "b", "c"]}, [("c", "a")], value
    )
    second = verifier.independent_mode(
        "exact_preceding_depth", cards, fingerprints, {"r": ["c", "b", "a"]}, [("c", "a")], value
    )
    assert first == second
    assert first["optimistic_top_tie_recovery"] == producer.exact(Fraction(1, 1))
    assert first["unique_top_recovery"] == producer.exact(Fraction(0, 1))
    assert first["wrong_alternatives_accepted_as_unique_top"] == 0


def test_flat_pair_oracle_and_fixed_threshold_match_independent_sweep() -> None:
    cards, fingerprints = synthetic_cards()
    by_run = {"run-secret": sorted(cards)}
    first = producer.flat_pair_graph(cards, fingerprints, by_run, 2)
    second = verifier.independent_flat_graph(cards, fingerprints, by_run, 2)
    assert first == second
    assert first["within_run_fingerprinted_pairs"] == 6


def test_ordered_classification_matches_for_all_four_paths() -> None:
    value = protocol()
    cases = [
        (metric_shell(Fraction(19, 20), Fraction(1, 2), Fraction(1, 2)), True,
         "FORWARD_HIERARCHY_CONTENT_PARENT_CONCORDANCE_CERTIFICATE"),
        (metric_shell(Fraction(19, 20), Fraction(4, 5), Fraction(1, 2)), True,
         "FORWARD_CONTENT_PARENT_CONCORDANCE_WITHOUT_HIERARCHY_COMPLEMENTARITY"),
        (metric_shell(Fraction(17, 20), Fraction(1, 2), Fraction(1, 2)), True,
         "FORWARD_PARENT_CONCORDANCE_PROFILE_BELOW_STRONG_GATE"),
        (metric_shell(Fraction(19, 20), Fraction(1, 2), Fraction(1, 2)), False,
         "FORWARD_PARENT_CONCORDANCE_GATE_FAIL"),
    ]
    for metrics, hard_pass, expected in cases:
        hard = {"synthetic": hard_pass}
        first = producer.classify(metrics, value, hard)
        second = verifier.independent_classification(metrics, value, hard)
        assert first == second
        assert first[0] == expected


def make_end_to_end_world(tmp_path: Path) -> tuple[Path, Path, Path, dict, Path]:
    state = tmp_path / "state"
    baseline_sha = "1" * 64
    candidate_sha = "2" * 64
    old_cards = [
        card("old-a", "old-run", "task-old", "missing-a", 0, rich_code(3)),
        card("old-b", "old-run", "task-old", "old-a", 1, rich_code(3, 1)),
    ]
    old_registry, old_summary = selection_helpers.make_intake(state, "drop-old", old_cards)
    old_runs = [selection_helpers.run_row("old-run", "task-old", "drop-old", 2)]
    selection_helpers.make_snapshot(
        state, baseline_sha, [old_registry], {"drop-old": old_summary}, old_runs, tasks=1
    )

    new_cards: list[dict] = []
    new_runs: list[dict] = []
    for index in range(87):
        run = f"new-run-{index:03d}"
        task = f"task-{index % 8}"
        parent_a = f"parent-a-{index:03d}"
        parent_b = f"parent-b-{index:03d}"
        new_cards.extend(
            [
                card(parent_a, run, task, f"missing-a-{index:03d}", 0, rich_code(100 + 2 * index)),
                card(parent_b, run, task, f"missing-b-{index:03d}", 0, rich_code(101 + 2 * index)),
                card(f"child-a-{index:03d}", run, task, parent_a, 1, rich_code(100 + 2 * index, index)),
                card(f"child-b-{index:03d}", run, task, parent_b, 1, rich_code(101 + 2 * index, index + 7)),
            ]
        )
        new_runs.append(selection_helpers.run_row(run, task, "drop-new", 4))
    new_registry, new_summary = selection_helpers.make_intake(state, "drop-new", new_cards)
    selection_helpers.make_snapshot(
        state,
        candidate_sha,
        [old_registry, new_registry],
        {"drop-old": old_summary, "drop-new": new_summary},
        old_runs + new_runs,
        tasks=9,
    )

    fake_repo = tmp_path / "repo"
    selection_spec = selection_helpers.protocol()
    selection_spec["freeze_state"]["baseline_snapshot_sha256"] = baseline_sha
    selection_spec["freeze_state"]["baseline_counts"] = {
        "provisional_first960_runs": 1,
        "eligible_endpoints": 2,
        "tasks": 1,
    }
    selection_spec["activation_rule"]["target_total_physical_runs"] = 88
    selection_spec["activation_rule"]["minimum_disjoint_increment_physical_runs"] = 87
    fake_selection_protocol = (
        fake_repo / "phase1" / "tree_linearization_within_stratum_forward_target522_v2.json"
    )
    selection_helpers.write_json(fake_selection_protocol, selection_spec)
    fake_selection_monitor = (
        fake_repo / "phase1" / "scripts" / "latch_tree_within_stratum_forward_target522_20260828.sh"
    )
    fake_selection_monitor.parent.mkdir(parents=True, exist_ok=True)
    fake_selection_monitor.write_bytes(SELECTION_MONITOR.read_bytes())
    for relative in (
        "phase1/audit_tree_within_stratum_forward_target522.py",
        "phase1/verify_tree_within_stratum_forward_target522.py",
        "phase1/audit_prospective_fuzzy_code_clones.py",
        "phase1/verify_prospective_fuzzy_code_clones.py",
    ):
        target = fake_repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())

    baseline = snapshot_producer.load_blind_snapshot(state, baseline_sha)
    candidate = snapshot_producer.load_blind_snapshot(state, candidate_sha)
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
    selection = selection_helpers.make_selection(
        tmp_path,
        spec=selection_spec,
        protocol_path=fake_selection_protocol,
        monitor_path=fake_selection_monitor,
        baseline_observation=baseline_observation,
        candidate_observation=candidate_observation,
    )

    content_spec = protocol()
    content_spec["freeze_state"]["baseline_snapshot_sha256"] = baseline_sha
    content_spec["freeze_state"]["baseline_counts"] = {
        "provisional_first960_runs": 1,
        "eligible_endpoints": 2,
        "tasks": 1,
    }
    activation = content_spec["activation_rule"]
    activation["selection_protocol_sha256"] = digest(fake_selection_protocol)
    activation["selection_monitor_sha256"] = digest(fake_selection_monitor)
    activation["target_total_physical_runs"] = 88
    activation["minimum_disjoint_increment_physical_runs"] = 87
    estimands = content_spec["parent_recovery_estimands"]
    estimands["task_breadth_minimum_edges"] = 10
    estimands["physical_run_breadth_minimum_edges"] = 2
    support = content_spec["hard_integrity_and_support_gates"]
    support["candidate_total_runs_at_least"] = 88
    support["disjoint_increment_runs_at_least"] = 87
    support["minimum_fingerprint_eligible_parent_edges"] = 100
    support["minimum_ambiguous_exact_depth_parent_edges"] = 100
    support["minimum_enumerated_wrong_parent_alternatives"] = 100
    support["minimum_conditionable_tasks"] = 8
    support["minimum_conditionable_physical_runs"] = 60
    fake_content_protocol = fake_repo / "phase1" / "tree_content_lineage_forward_target522_v1.json"
    selection_helpers.write_json(fake_content_protocol, content_spec)
    return state, selection, fake_repo, content_spec, fake_content_protocol


def test_end_to_end_producer_and_independent_verifier_match(tmp_path: Path) -> None:
    state, selection, fake_repo, _spec, protocol_path = make_end_to_end_world(tmp_path)
    protocol_sha = digest(protocol_path)
    source_commit = "9" * 40
    receipt = producer.build_receipt(
        state, selection, fake_repo, protocol_path, protocol_sha, source_commit
    )
    assert receipt["pre_registered_gate"]["all_hard_gates_passed"] is True
    rendered = json.dumps(receipt, sort_keys=True)
    assert "new-run" not in rendered
    assert "task-0" not in rendered
    receipt_path = tmp_path / "receipt.json"
    producer.write_once(receipt_path, receipt)
    verification = verifier.verify(
        state,
        selection,
        fake_repo,
        protocol_path,
        protocol_sha,
        receipt_path,
        digest(receipt_path),
        PRODUCER,
        digest(PRODUCER),
        source_commit,
    )
    assert verification["status"] == "INDEPENDENT_FORWARD_CONTENT_LINEAGE_AUDIT_PASS"
    assert verification["classification"] == receipt["classification"]
    assert verification["checks"]["imports_new_producer"] is False


def test_snapshot_dependencies_are_bound_to_current_sources() -> None:
    value = protocol()["implementation_dependencies"]
    for role in ("snapshot_producer", "snapshot_verifier", "fingerprint_producer", "fingerprint_verifier"):
        assert digest(ROOT / value[f"{role}_module"]) == value[f"{role}_sha256"]
    assert digest(SELECTION_PROTOCOL) == protocol()["activation_rule"]["selection_protocol_sha256"]
    assert digest(SELECTION_MONITOR) == protocol()["activation_rule"]["selection_monitor_sha256"]


def test_gate_code_uses_fraction_payloads_not_decimal_displays() -> None:
    for path in (PRODUCER, VERIFIER):
        source = path.read_text(encoding="utf-8")
        classification = source[source.index("def classify") :] if path == PRODUCER else source[source.index("def independent_classification") :]
        assert '["decimal_17g"]' not in classification
    assert Fraction(protocol()["strong_content_concordance_gates"]["minimum_exact_depth_unique_top_recovery"]) == Fraction(9, 10)


def test_independent_snapshot_modules_remain_distinct() -> None:
    assert snapshot_producer.__file__ != snapshot_verifier.__file__


def test_formal_runner_is_fail_closed_and_result_blind() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "source /uac/y24/yzyang4/env_setup.sh" in source
    assert "export SLURM_CONF=/opt1/slurm/gpu-slurm.conf" in source
    assert "test -f \"$selection/COMPLETE\"" in source
    assert "strace -ff -tt -yy -e trace=file,network" in source
    assert "phase1/tests" in source
    assert "producer_a.json" in source and "producer_b.json" in source
    assert "verifier_a.json" in source and "verifier_b.json" in source
    assert "prospective_label_grade_outcome_prediction_values_read == false" in source
    assert "gpu_api_model_fit_base_update == [0,0,0,0]" in source
    assert "FAILED_RC" in source


def test_watcher_reads_only_selection_existence_before_completion() -> None:
    source = MONITOR.read_text(encoding="utf-8")
    loop = source[source.index("for poll in") :]
    before_activation, after_activation = loop.split('if test -f "$selection/COMPLETE"; then', 1)
    assert "candidate.tsv" not in before_activation
    assert "READY" not in before_activation
    assert "SHA256SUMS" not in before_activation
    assert "sha256sum \"$selection/SHA256SUMS\"" in after_activation
    assert "formal_runner.sh" in after_activation
    assert "sleep 30" in source
    assert "FAILED_RC" in source and "INTERRUPTED_RC" in source


def test_protocol_security_allowlists_match_selection_and_corpus_contracts() -> None:
    value = protocol()
    assert set(value["security"]["selection_support_input_basenames"]) == set(
        selection_helpers.protocol()["security"]["selection_support_input_basenames"]
    )
    assert set(value["security"]["corpus_input_basenames"]) == {
        "eligible_blind_manifest.jsonl",
        "intake_registry.jsonl",
        "provisional_runs.jsonl",
        "summary.json",
    }
