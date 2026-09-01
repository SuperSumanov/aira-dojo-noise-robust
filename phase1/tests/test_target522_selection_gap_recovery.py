import hashlib
import importlib
import inspect
import json
from pathlib import Path

import pytest


producer = importlib.import_module("phase1.recover_target522_selection_gap")
verifier = importlib.import_module("phase1.verify_target522_selection_gap_recovery")


HEADER = "snapshot_sha256\truns\tendpoints\ttasks\tsummary_sha256\tregistry_sha256\truns_sha256\tobserved_at_utc\n"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def make_snapshot(state: Path, index: int, runs: int) -> dict:
    snapshot = hashlib.sha256(f"snapshot-{index}".encode()).hexdigest()
    root = state / "snapshots" / snapshot
    (root / "accumulator").mkdir(parents=True)
    registry = root / "intake_registry.jsonl"
    run_file = root / "accumulator" / "provisional_runs.jsonl"
    registry.write_text(f'{{"ordinal":{index}}}\n', encoding="utf-8")
    run_file.write_text(f'{{"count":{runs}}}\n', encoding="utf-8")
    summary = {
        "protocol": "prospective_accumulator_v1",
        "closure": {"provided": False},
        "security": {
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
        "inputs": {"registry_sha256": sha(registry)},
        "outputs": {"provisional_runs_sha256": sha(run_file)},
        "inventory": {
            "provisional_first960_runs": runs,
            "provisional_first960_endpoints": runs * 10,
        },
        "task_support": {"provisional_first960": {"tasks": 4 + index}},
    }
    summary_path = root / "accumulator" / "summary.json"
    write_json(summary_path, summary)
    return {
        "snapshot_sha256": snapshot,
        "summary_sha256": sha(summary_path),
        "registry_sha256": sha(registry),
        "runs_sha256": sha(run_file),
    }


def fixture(tmp_path: Path, final_runs: int = 501):
    state = tmp_path / "state"
    selection = tmp_path / "selection"
    state.mkdir()
    selection.mkdir()
    (selection / "protocol.json").write_text("{}\n", encoding="utf-8")
    (selection / "source_script.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (selection / "preflight_13.txt").write_text(
        "03_source_commit=" + "a" * 40 + "; PASS\n"
        "04_protocol_sha256=" + sha(selection / "protocol.json") + "; PASS\n",
        encoding="utf-8",
    )
    predecessor = hashlib.sha256(b"predecessor").hexdigest()
    old = selection / "observed.tsv"
    old.write_text(
        HEADER + f"{predecessor}\t494\t4940\t4\t{'1'*64}\t{'2'*64}\t{'3'*64}\t2026-08-31T13:25:17Z\n",
        encoding="utf-8",
    )
    (selection / "TIMEOUT_RC").write_text("124\n", encoding="utf-8")
    counts = [495, 496, 497, 498, 499, 500, final_runs]
    successors = [make_snapshot(state, index, count) for index, count in enumerate(counts)]
    latest = successors[-1]["snapshot_sha256"]
    (state / "LATEST").write_text(latest + "\n", encoding="utf-8")
    protocol = {
        "protocol": "target522-selection-gap-recovery-v1",
        "version": 1,
        "frozen_at_utc": "2026-09-01T00:30:00Z",
        "status": "FROZEN_BEFORE_SUCCESSOR_RUN_COUNTS_READ",
        "selection_root": str(selection),
        "state_root": str(state),
        "selection_source_commit": "a" * 40,
        "selection_protocol_sha256": sha(selection / "protocol.json"),
        "selection_source_script_sha256": sha(selection / "source_script.sh"),
        "old_observed_sha256": sha(old),
        "old_observed_lines": 2,
        "timeout_rc": 124,
        "last_observed_snapshot_sha256": predecessor,
        "last_observed_runs": 494,
        "target_runs": 522,
        "current_latest_sha256": latest,
        "ordered_successors": successors,
    }
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    return protocol_path, protocol, state, selection


def test_producer_and_independent_verifier_pass_and_are_deterministic(tmp_path: Path):
    protocol_path, _, _, _ = fixture(tmp_path)
    first = tmp_path / "a"
    second = tmp_path / "b"
    producer.write(first, *producer.analyze(protocol_path))
    producer.write(second, *producer.analyze(protocol_path))
    assert (first / "observed_extension.tsv").read_bytes() == (second / "observed_extension.tsv").read_bytes()
    assert (first / "summary.json").read_bytes() == (second / "summary.json").read_bytes()
    receipt = verifier.verify(protocol_path, first)
    assert receipt["status"] == "TARGET522_GAP_RECOVERY_INDEPENDENT_PASS"
    assert receipt["final_runs"] == 501
    assert receipt["remaining_runs"] == 21


def test_possible_skipped_crossing_fails_closed(tmp_path: Path):
    protocol_path, _, _, _ = fixture(tmp_path, final_runs=522)
    with pytest.raises(producer.RecoveryError, match="skipped Target-522"):
        producer.analyze(protocol_path)


def test_successor_hash_drift_fails_closed(tmp_path: Path):
    protocol_path, protocol, _, _ = fixture(tmp_path)
    protocol["ordered_successors"][2]["summary_sha256"] = "0" * 64
    write_json(protocol_path, protocol)
    with pytest.raises(producer.RecoveryError, match="summary_sha256 mismatch"):
        producer.analyze(protocol_path)


def test_old_observed_drift_fails_closed(tmp_path: Path):
    protocol_path, _, _, selection = fixture(tmp_path)
    with (selection / "observed.tsv").open("a", encoding="utf-8") as handle:
        handle.write("drift\n")
    with pytest.raises(producer.RecoveryError, match="old observed hash drift"):
        producer.analyze(protocol_path)


def test_current_latest_drift_fails_closed(tmp_path: Path):
    protocol_path, _, state, _ = fixture(tmp_path)
    (state / "LATEST").write_text("f" * 64 + "\n", encoding="utf-8")
    with pytest.raises(producer.RecoveryError, match="current LATEST mismatch"):
        producer.analyze(protocol_path)


def test_forbidden_candidate_marker_fails_closed(tmp_path: Path):
    protocol_path, _, _, selection = fixture(tmp_path)
    (selection / "candidate.tsv").write_text("private\n", encoding="utf-8")
    with pytest.raises(producer.RecoveryError, match="forbidden selection marker"):
        producer.analyze(protocol_path)


def test_independent_verifier_rejects_output_tamper(tmp_path: Path):
    protocol_path, _, _, _ = fixture(tmp_path)
    output = tmp_path / "output"
    producer.write(output, *producer.analyze(protocol_path))
    with (output / "observed_extension.tsv").open("a", encoding="utf-8") as handle:
        handle.write("tamper\n")
    with pytest.raises(verifier.VerificationError, match="output manifest mismatch"):
        verifier.verify(protocol_path, output)


def test_verifier_does_not_import_producer():
    source = inspect.getsource(verifier)
    assert "recover_target522_selection_gap" not in source
