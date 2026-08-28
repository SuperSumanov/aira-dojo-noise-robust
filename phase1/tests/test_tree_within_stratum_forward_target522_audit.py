from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from phase1 import audit_tree_within_stratum_forward_target522 as producer
from phase1 import verify_tree_within_stratum_forward_target522 as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "phase1" / "tree_linearization_within_stratum_forward_target522_v2.json"
MONITOR_PATH = (
    ROOT / "phase1" / "scripts" / "latch_tree_within_stratum_forward_target522_20260828.sh"
)
PRODUCER_PATH = ROOT / "phase1" / "audit_tree_within_stratum_forward_target522.py"
VERIFIER_PATH = ROOT / "phase1" / "verify_tree_within_stratum_forward_target522.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol() -> dict:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def write_json(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return digest(path)


def write_jsonl(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    return digest(path)


def card(identifier: str, run: str, task: str, parent: str, depth: int) -> dict:
    code = f"print('{identifier}')"
    return {
        "card_id": identifier,
        "task": task,
        "run_id": run,
        "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "lineage": {
            "depth": depth,
            "step": depth,
            "n_siblings": 1,
            "op": "draft" if depth == 0 else "debug",
            "parent": parent,
        },
        "generation_started_at_utc": "2026-08-28T00:00:00Z",
        "source_sha256": "a" * 64,
    }


def run_row(identifier: str, task: str, drop: str, endpoints: int) -> dict:
    return {
        "run_id": identifier,
        "task": task,
        "drop_id": drop,
        "flow_status": "scoreable",
        "endpoints": endpoints,
        "generation_started_at_utc": "2026-08-28T00:00:00Z",
        "source_sha256": "b" * 64,
    }


def make_intake(state: Path, drop: str, rows: list[dict]) -> tuple[dict, str]:
    intake = state / "intakes" / drop
    manifest_sha = write_jsonl(intake / "eligible_blind_manifest.jsonl", rows)
    summary = {
        "outputs": {"eligible_blind_manifest_sha256": manifest_sha},
        "security": {"env_members_read": False, "live_event_journal_members_read": False},
        "blindness": {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
            "metrics_computed": [],
        },
    }
    summary_sha = write_json(intake / "summary.json", summary)
    return {
        "drop_id": drop,
        "intake_dir": str(intake.resolve()),
        "summary_sha256": summary_sha,
    }, summary_sha


def make_snapshot(
    state: Path,
    snapshot: str,
    registry: list[dict],
    intake_summaries: dict[str, str],
    runs: list[dict],
    tasks: int,
) -> None:
    root = state / "snapshots" / snapshot
    registry_sha = write_jsonl(root / "intake_registry.jsonl", registry)
    runs_sha = write_jsonl(root / "accumulator" / "provisional_runs.jsonl", runs)
    endpoints = sum(row["endpoints"] for row in runs)
    summary = {
        "protocol": "prospective_accumulator_v1",
        "security": {
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
        "closure": {"provided": False},
        "inputs": {
            "registry_sha256": registry_sha,
            "intake_summaries": intake_summaries,
        },
        "outputs": {"provisional_runs_sha256": runs_sha},
        "inventory": {
            "provisional_first960_runs": len(runs),
            "provisional_first960_endpoints": endpoints,
        },
        "task_support": {"provisional_first960": {"tasks": tasks}},
    }
    write_json(root / "accumulator" / "summary.json", summary)


def synthetic_snapshots(tmp_path: Path) -> tuple[Path, str, str]:
    state = tmp_path / "state"
    baseline_sha = "1" * 64
    candidate_sha = "2" * 64
    baseline_cards = [
        card("old-root", "old-run", "task-0", "missing", 0),
        card("old-child", "old-run", "task-0", "old-root", 1),
    ]
    base_registry, base_summary = make_intake(state, "drop-old", baseline_cards)
    baseline_runs = [run_row("old-run", "task-0", "drop-old", 2)]
    make_snapshot(
        state,
        baseline_sha,
        [base_registry],
        {"drop-old": base_summary},
        baseline_runs,
        tasks=1,
    )

    new_cards: list[dict] = []
    new_runs: list[dict] = []
    for index in range(87):
        run = f"new-run-{index:03d}"
        task = f"task-{index % 8}"
        root = f"new-root-{index:03d}"
        fork = f"new-fork-{index:03d}"
        new_cards.extend(
            [
                card(root, run, task, "missing", 0),
                card(fork, run, task, root, 1),
                card(f"new-left-{index:03d}", run, task, fork, 2),
                card(f"new-right-{index:03d}", run, task, fork, 2),
            ]
        )
        new_runs.append(run_row(run, task, "drop-new", 4))
    new_registry, new_summary = make_intake(state, "drop-new", new_cards)
    make_snapshot(
        state,
        candidate_sha,
        [base_registry, new_registry],
        {"drop-old": base_summary, "drop-new": new_summary},
        baseline_runs + new_runs,
        tasks=8,
    )
    return state, baseline_sha, candidate_sha


def make_selection(
    tmp_path: Path,
    include_earlier_crossing: bool = False,
    *,
    spec: dict | None = None,
    protocol_path: Path = PROTOCOL_PATH,
    monitor_path: Path = MONITOR_PATH,
    baseline_observation: tuple | None = None,
    candidate_observation: tuple | None = None,
) -> Path:
    spec = protocol() if spec is None else spec
    root = tmp_path / "selection"
    root.mkdir()
    baseline = spec["freeze_state"]["baseline_snapshot_sha256"]
    default_baseline = (
        baseline,
        spec["freeze_state"]["baseline_counts"]["provisional_first960_runs"],
        spec["freeze_state"]["baseline_counts"]["eligible_endpoints"],
        spec["freeze_state"]["baseline_counts"]["tasks"],
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "2026-08-28T00:00:00Z",
    )
    baseline_observation = default_baseline if baseline_observation is None else baseline_observation
    default_candidate = (
        "c" * 64,
        spec["activation_rule"]["target_total_physical_runs"],
        13000,
        34,
        "d" * 64,
        "e" * 64,
        "f" * 64,
        "2026-08-28T00:00:02Z",
    )
    candidate_observation = default_candidate if candidate_observation is None else candidate_observation
    candidate = candidate_observation[0]
    summary_sha, registry_sha, runs_sha = candidate_observation[4:7]
    (root / "protocol.json").write_bytes(protocol_path.read_bytes())
    (root / "source_script.sh").write_bytes(monitor_path.read_bytes())
    (root / "monitor.lock").write_bytes(b"")
    (root / "monitor.pid").write_text("12345\n", encoding="utf-8", newline="\n")
    (root / "preflight_13.txt").write_text(
        "".join(f"{index:02d}_check=PASS\n" for index in range(1, 14)),
        encoding="utf-8",
        newline="\n",
    )
    observed = [baseline_observation]
    if include_earlier_crossing:
        observed.append(
            (
                "b" * 64,
                spec["activation_rule"]["target_total_physical_runs"] + 1,
                12900,
                34,
                "4" * 64,
                "5" * 64,
                "6" * 64,
                "2026-08-28T00:00:01Z",
            )
        )
    if include_earlier_crossing:
        candidate_observation = (
            candidate_observation[0],
            max(
                candidate_observation[1],
                spec["activation_rule"]["target_total_physical_runs"] + 2,
            ),
            *candidate_observation[2:],
        )
    observed.append(candidate_observation)
    (root / "observed.tsv").write_text(
        producer.OBSERVED_HEADER
        + "\n"
        + "".join("\t".join(map(str, row)) + "\n" for row in observed),
        encoding="utf-8",
        newline="\n",
    )
    candidate_row = observed[-1]
    (root / "candidate.tsv").write_text(
        "\t".join(map(str, candidate_row[:7])) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    candidate_runs = candidate_row[1]
    ready = {
        "status": "TARGET522_FIRST_OBSERVED_CROSSING_READY",
        "completed_at_utc": "2026-08-28T00:00:30Z",
        "source_commit": "4" * 40,
        "protocol_sha256": digest(protocol_path),
        "baseline_snapshot_sha256": baseline,
        "baseline_runs": str(baseline_observation[1]),
        "candidate_snapshot_sha256": candidate,
        "candidate_runs": str(candidate_runs),
        "candidate_endpoints": str(candidate_row[2]),
        "candidate_tasks": str(candidate_row[3]),
        "disjoint_increment_runs": str(candidate_runs - baseline_observation[1]),
        "candidate_summary_sha256": summary_sha,
        "candidate_registry_sha256": registry_sha,
        "candidate_runs_sha256": runs_sha,
        "manual_snapshot_choice": "false",
        "earlier_observed_target_crossing_skipped": "false",
        "profile_values_read_for_selection": "false",
        "prospective_outcomes_or_prediction_values_read": "false",
        "raw_senior_archives_opened": "false",
        "gpu_api_model_fit_base_update": "0/0/0/0",
    }
    (root / "READY").write_text(
        "".join(f"{key}={value}\n" for key, value in ready.items()),
        encoding="utf-8",
        newline="\n",
    )
    log_rows = [
        f"2026-08-28T00:00:03Z candidate_latched poll=1 snapshot={candidate} runs={candidate_runs}"
    ]
    log_rows.extend(
        f"2026-08-28T00:00:{3 + stable:02d}Z waiting poll={stable} latest={candidate} "
        f"runs={candidate_runs} candidate={candidate} stable={stable}"
        for stable in range(1, 6)
    )
    (root / "monitor.log").write_text(
        "\n".join(log_rows) + "\n", encoding="utf-8", newline="\n"
    )
    (root / "security_scan_receipt.txt").write_text(
        "boundary_aware_credential_file_hits=0\ncredential_filename_hits=0\n",
        encoding="utf-8",
        newline="\n",
    )
    members = sorted(
        path for path in root.iterdir() if path.name not in {"SHA256SUMS", "COMPLETE"}
    )
    (root / "SHA256SUMS").write_text(
        "".join(f"{digest(path)}  ./{path.name}\n" for path in members),
        encoding="utf-8",
        newline="\n",
    )
    (root / "COMPLETE").write_bytes(b"")
    assert {path.name for path in root.iterdir()} == set(
        spec["security"]["selection_support_input_basenames"]
    )
    return root


def relaxed_math_protocol() -> dict:
    spec = protocol()
    hard = spec["hard_integrity_and_support_gates"]
    hard["minimum_conditionable_tasks_in_increment"] = 1
    hard["minimum_conditionable_physical_runs_in_increment"] = 1
    gates = spec["strong_positive_gates"]
    gates["minimum_task_canonical_standardized_within_tv"] = "1/10"
    gates["minimum_physical_run_canonical_standardized_within_tv"] = "1/10"
    gates["minimum_task_fraction_at_or_above_conditional_tv_reference"] = "0"
    gates["minimum_physical_run_fraction_at_or_above_conditional_tv_reference"] = "0"
    gates["maximum_single_task_canonical_contribution_share"] = "1"
    gates["maximum_single_physical_run_canonical_contribution_share"] = "1"
    return spec


def test_protocol_hash_and_pre_candidate_amendment_are_bound() -> None:
    expected = digest(PROTOCOL_PATH)
    first, first_sha = producer.load_protocol(PROTOCOL_PATH, expected)
    second, second_sha = verifier.protocol_file(PROTOCOL_PATH, expected)
    assert first == second
    assert first_sha == second_sha == expected
    amendment = first["pre_candidate_integrity_amendment"]
    assert amendment["candidate_snapshot_identity_seen"] is False
    assert amendment["increment_profile_seen"] is False
    assert amendment["scientific_population_estimand_thresholds_or_classification_changed"] is False


def test_selection_package_is_independently_reconstructed(tmp_path: Path) -> None:
    selection_root = make_selection(tmp_path)
    spec = protocol()
    protocol_sha = digest(PROTOCOL_PATH)
    first = producer.verify_selection(selection_root, ROOT, spec, protocol_sha)
    second = verifier.inspect_selection(
        selection_root,
        PROTOCOL_PATH,
        MONITOR_PATH,
        spec,
        protocol_sha,
    )
    assert first["baseline_snapshot_sha256"] == second["baseline"]
    assert first["candidate_snapshot_sha256"] == second["candidate"] == "c" * 64
    assert first["candidate_counts"] == second["candidate_counts"]
    assert first["selection_support_sha256sums_sha256"] == second["manifest_sha256"]
    assert first["selection_monitor_source_sha256"] == second["monitor_source_sha256"]
    assert first["checks"] == second["checks"]


def test_hash_valid_selection_with_an_earlier_crossing_fails_closed(tmp_path: Path) -> None:
    selection_root = make_selection(tmp_path, include_earlier_crossing=True)
    spec = protocol()
    protocol_sha = digest(PROTOCOL_PATH)
    with pytest.raises(producer.ForwardAuditError, match="first observed crossing"):
        producer.verify_selection(selection_root, ROOT, spec, protocol_sha)
    with pytest.raises(verifier.ForwardVerificationError, match="first crossing"):
        verifier.inspect_selection(
            selection_root,
            PROTOCOL_PATH,
            MONITOR_PATH,
            spec,
            protocol_sha,
        )


def test_two_snapshot_readers_do_not_require_latest_and_agree(tmp_path: Path) -> None:
    state, baseline_sha, candidate_sha = synthetic_snapshots(tmp_path)
    first_baseline = producer.load_blind_snapshot(state, baseline_sha)
    first_candidate = producer.load_blind_snapshot(state, candidate_sha)
    second_baseline = verifier.collect_snapshot(state, baseline_sha)
    second_candidate = verifier.collect_snapshot(state, candidate_sha)
    assert first_baseline.bindings == second_baseline.bindings
    assert first_candidate.bindings == second_candidate.bindings
    assert first_baseline.cards == second_baseline.graph_cards
    assert first_candidate.cards == second_candidate.graph_cards


def test_disjoint_increment_is_complete_and_byte_append_only(tmp_path: Path) -> None:
    state, baseline_sha, candidate_sha = synthetic_snapshots(tmp_path)
    spec = protocol()
    first_baseline = producer.load_blind_snapshot(state, baseline_sha)
    first_candidate = producer.load_blind_snapshot(state, candidate_sha)
    second_baseline = verifier.collect_snapshot(state, baseline_sha)
    second_candidate = verifier.collect_snapshot(state, candidate_sha)
    first_cards, first_runs, first_checks = producer.disjoint_increment(
        first_baseline, first_candidate, spec
    )
    second_cards, second_runs, second_checks = verifier.incremental_population(
        second_baseline, second_candidate, spec
    )
    assert first_cards == second_cards
    assert first_runs == second_runs
    assert first_checks == second_checks
    assert first_checks["increment_runs"] == 87
    assert first_checks["increment_endpoints"] == 348
    assert all("old" not in identifier for identifier in first_cards)


def test_old_row_byte_drift_fails_both_implementations(tmp_path: Path) -> None:
    state, baseline_sha, candidate_sha = synthetic_snapshots(tmp_path)
    spec = protocol()
    first_baseline = producer.load_blind_snapshot(state, baseline_sha)
    first_candidate = producer.load_blind_snapshot(state, candidate_sha)
    second_baseline = verifier.collect_snapshot(state, baseline_sha)
    second_candidate = verifier.collect_snapshot(state, candidate_sha)
    first_candidate.card_raw_rows["old-root"] += b" "
    second_candidate.card_lines["old-root"] += b" "
    with pytest.raises(producer.ForwardAuditError, match="old endpoint bytes"):
        producer.disjoint_increment(first_baseline, first_candidate, spec)
    with pytest.raises(verifier.ForwardVerificationError, match="old card bytes"):
        verifier.incremental_population(second_baseline, second_candidate, spec)


def test_full_snapshot_cross_run_parent_and_cycle_fail_closed() -> None:
    cross_run = {
        "root": {"task": "task", "run": "run-a", "parent": "missing", "depth": 0},
        "child": {"task": "task", "run": "run-b", "parent": "root", "depth": 1},
    }
    with pytest.raises(producer.ForwardAuditError, match="crosses physical runs"):
        producer.validate_snapshot_graph(cross_run)
    with pytest.raises(verifier.ForwardVerificationError, match="cross-run"):
        verifier.independently_validate_snapshot_graph(cross_run)
    cycle = {
        "a": {"task": "task", "run": "run", "parent": "b", "depth": 0},
        "b": {"task": "task", "run": "run", "parent": "a", "depth": 1},
    }
    with pytest.raises(producer.ForwardAuditError, match="cycle"):
        producer.validate_snapshot_graph(cycle)
    with pytest.raises(verifier.ForwardVerificationError, match="cycle"):
        verifier.independently_validate_snapshot_graph(cycle)


def test_exact_math_and_classification_match_without_decimal_gates() -> None:
    edges = [
        ("task-a", "run-a", 4),
        ("task-a", "run-a", 1),
        ("task-b", "run-b", 4),
        ("task-b", "run-b", 1),
    ]
    spec = relaxed_math_protocol()
    first = producer.math_impl.summarize_edges(edges, producer.math_protocol(spec))
    second = verifier.independent_math.independently_summarize(
        edges, verifier.adapted_math_protocol(spec)
    )
    assert first["inventory"] == second["inventory"]
    assert first["overall_edge_total_variation"] == second["overall_edge_total_variation"]
    assert first["partitions"] == second["partitions"]
    assert first["provisional_axis_strength"] == second["axis_strength"]
    hard = {"synthetic": True}
    assert producer.classify(first, spec, hard) == (
        "FORWARD_INCREMENT_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
    )
    assert verifier.independent_classification(second, spec, hard) == (
        "FORWARD_INCREMENT_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
    )
    hard["synthetic"] = False
    assert producer.classify(first, spec, hard) == "FORWARD_INCREMENT_WITHIN_STRATUM_GATE_FAIL"
    assert (
        verifier.independent_classification(second, spec, hard)
        == "FORWARD_INCREMENT_WITHIN_STRATUM_GATE_FAIL"
    )


def test_verifier_does_not_import_new_producer_and_outputs_no_identifiers() -> None:
    source = VERIFIER_PATH.read_text(encoding="utf-8")
    assert "import audit_tree_within_stratum_forward_target522" not in source
    assert "from phase1 import audit_tree_within_stratum_forward_target522" not in source
    assert digest(PRODUCER_PATH) != digest(VERIFIER_PATH)
    edges = [
        ("task-secret", "run-secret", 3),
        ("task-secret", "run-secret", 1),
    ]
    spec = relaxed_math_protocol()
    summary = producer.math_impl.summarize_edges(edges, producer.math_protocol(spec))
    rendered = json.dumps(summary, sort_keys=True)
    assert "task-secret" not in rendered
    assert "run-secret" not in rendered


def test_fraction_thresholds_not_decimal_strings_determine_gate() -> None:
    spec = protocol()
    gates = spec["strong_positive_gates"]
    assert Fraction(gates["minimum_task_canonical_standardized_within_tv"]) == Fraction(1, 5)
    assert Fraction(gates["minimum_physical_run_canonical_standardized_within_tv"]) == Fraction(3, 20)
    assert spec["hard_integrity_and_support_gates"]["decimal_strings_are_descriptive_only"] is True
    producer_source = PRODUCER_PATH.read_text(encoding="utf-8")
    verifier_source = VERIFIER_PATH.read_text(encoding="utf-8")
    assert '"decimal_17g"' not in producer_source
    assert '"decimal_17g"' not in verifier_source


def test_end_to_end_producer_and_independent_verifier_match(tmp_path: Path) -> None:
    state, baseline_sha, candidate_sha = synthetic_snapshots(tmp_path)
    baseline = producer.load_blind_snapshot(state, baseline_sha)
    candidate = producer.load_blind_snapshot(state, candidate_sha)
    spec = copy.deepcopy(protocol())
    spec["freeze_state"]["baseline_snapshot_sha256"] = baseline_sha
    spec["freeze_state"]["baseline_counts"] = {
        "provisional_first960_runs": baseline.bindings["runs"],
        "eligible_endpoints": baseline.bindings["endpoints"],
        "tasks": baseline.bindings["tasks"],
    }
    spec["activation_rule"]["target_total_physical_runs"] = candidate.bindings["runs"]
    spec["activation_rule"]["minimum_disjoint_increment_physical_runs"] = 87
    hard = spec["hard_integrity_and_support_gates"]
    hard["candidate_total_runs_at_least"] = candidate.bindings["runs"]
    hard["disjoint_increment_runs_at_least"] = 87
    hard["minimum_observed_unique_edges_in_increment"] = 261
    hard["minimum_parent_present_endpoint_fraction_in_increment"] = "3/4"
    hard["minimum_conditionable_tasks_in_increment"] = 8
    hard["minimum_conditionable_physical_runs_in_increment"] = 60

    fake_repo = tmp_path / "repo"
    fake_protocol = (
        fake_repo / "phase1" / "tree_linearization_within_stratum_forward_target522_v2.json"
    )
    fake_monitor = (
        fake_repo
        / "phase1"
        / "scripts"
        / "latch_tree_within_stratum_forward_target522_20260828.sh"
    )
    fake_math = fake_repo / "phase1" / "decompose_tree_linearization_within_strata.py"
    write_json(fake_protocol, spec)
    fake_monitor.parent.mkdir(parents=True, exist_ok=True)
    fake_monitor.write_bytes(MONITOR_PATH.read_bytes())
    fake_math.write_bytes((ROOT / "phase1" / "decompose_tree_linearization_within_strata.py").read_bytes())
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
    selection = make_selection(
        tmp_path,
        spec=spec,
        protocol_path=fake_protocol,
        monitor_path=fake_monitor,
        baseline_observation=baseline_observation,
        candidate_observation=candidate_observation,
    )
    source_commit = "9" * 40
    protocol_sha = digest(fake_protocol)
    receipt = producer.build_receipt(
        state,
        selection,
        fake_repo,
        fake_protocol,
        protocol_sha,
        source_commit,
    )
    assert receipt["classification"] == (
        "FORWARD_INCREMENT_RUN_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
    )
    assert receipt["pre_registered_gate"]["all_hard_gates_passed"] is True
    rendered = json.dumps(receipt, sort_keys=True)
    assert "new-run" not in rendered
    assert "new-root" not in rendered
    receipt_path = tmp_path / "receipt.json"
    producer.write_once(receipt_path, receipt)
    verification = verifier.verify(
        state,
        selection,
        fake_repo,
        fake_protocol,
        protocol_sha,
        receipt_path,
        digest(receipt_path),
        PRODUCER_PATH,
        digest(PRODUCER_PATH),
        source_commit,
    )
    assert verification["status"] == "INDEPENDENT_FORWARD_INCREMENT_AUDIT_PASS"
    assert verification["classification"] == receipt["classification"]
    assert verification["all_hard_gates_passed"] is True
