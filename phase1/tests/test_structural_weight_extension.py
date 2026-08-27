from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1 import build_structural_weight_extension as producer
from phase1 import build_structural_weight_trajectory as core
from phase1 import verify_structural_weight_extension as verifier


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_inputs(count: int = 404):
    tasks = tuple(f"task-{index:02d}" for index in range(31))
    added_nonzero = [index for index in range(240, 404) if index % 31 != 0]
    nonzero_rank = {index: rank for rank, index in enumerate(added_nonzero)}
    runs = []
    records = {}
    for index in range(count):
        task = tasks[index % len(tasks)]
        if index < 240:
            pair_count = 1
        elif index % 31 == 0:
            pair_count = 141 if index != 403 else 137
        else:
            pair_count = 12 if nonzero_rank[index] < 64 else 11
        run_id = f"run-{index:03d}"
        runs.append(
            {
                "run_id": run_id,
                "task": task,
                "drop_id": f"drop-{index // 16:03d}",
            }
        )
        records[run_id] = {
            "task": task,
            "endpoints": pair_count + 20 + (index < 346),
            "parents": 1,
            "pairs": pair_count,
        }
    receipts = {
        "input_hashes": {
            "snapshot_manifest_sha256": "b" * 64,
            "accumulator_summary_sha256": "c" * 64,
            "provisional_first960_runs_sha256": "d" * 64,
            "intake_registry_sha256": "e" * 64,
            "intakes": {},
        }
    }
    return runs, records, receipts


def protocol_file(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / producer.PROTOCOL_BASENAME
    path.write_text("frozen before 404-run extension\n", encoding="utf-8", newline="\n")
    return path, digest(path)


def test_builds_deterministic_404_run_extension(tmp_path: Path, monkeypatch) -> None:
    data = synthetic_inputs()
    monkeypatch.setattr(producer.core, "load_structural_inputs", lambda *_: data)
    protocol, protocol_sha = protocol_file(tmp_path)
    first = producer.build_result(
        tmp_path / producer.EXPECTED_SNAPSHOT,
        producer.EXPECTED_SNAPSHOT,
        "a" * 40,
        protocol,
        protocol_sha,
    )
    second = producer.build_result(
        tmp_path / producer.EXPECTED_SNAPSHOT,
        producer.EXPECTED_SNAPSHOT,
        "a" * 40,
        protocol,
        protocol_sha,
    )
    assert first == second
    assert first["status"] == producer.STATUS
    assert first["current_first404"]["inventory"]["runs"] == 404
    assert len(first["full_prefix_trajectory"]) == 404
    assert [row["prefix_runs"] for row in first["milestones"]] == list(producer.MILESTONES)
    assert first["known_before_protocol_freeze"]["current_hhi_trajectory_decomposition_and_deletions_known"] is False
    assert first["security"]["label_vault_opened"] is False
    assert first["security"]["model_fits"] == 0


def test_independent_claim_reconstruction_matches_producer(tmp_path: Path, monkeypatch) -> None:
    runs, records, receipts = synthetic_inputs()
    monkeypatch.setattr(producer.core, "load_structural_inputs", lambda *_: (runs, records, receipts))
    protocol, protocol_sha = protocol_file(tmp_path)
    result = producer.build_result(
        tmp_path / producer.EXPECTED_SNAPSHOT,
        producer.EXPECTED_SNAPSHOT,
        "a" * 40,
        protocol,
        protocol_sha,
    )
    scopes = {index: verifier.independent.summarize(runs[:index], records) for index in range(1, 405)}
    drop_rows, task_rows, mechanism, gates, sensitivity = verifier.reconstruct_claim_sections(
        runs, records, scopes
    )
    verifier.independent.assert_close(drop_rows, result["leave_one_added_drop_out"], "drops")
    verifier.independent.assert_close(task_rows, result["leave_one_task_out"], "tasks")
    verifier.independent.assert_close(mechanism, result["mechanism_decomposition"], "mechanism")
    verifier.independent.assert_close(gates, result["claim_gates"], "gates")
    verifier.independent.assert_close(sensitivity, result["version_sensitivity"], "sensitivity")


def test_rejects_non_404_population(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(producer.core, "load_structural_inputs", lambda *_: synthetic_inputs(403))
    protocol, protocol_sha = protocol_file(tmp_path)
    with pytest.raises(core.TrajectoryError, match="exactly 404 runs"):
        producer.build_result(
            tmp_path / producer.EXPECTED_SNAPSHOT,
            producer.EXPECTED_SNAPSHOT,
            "a" * 40,
            protocol,
            protocol_sha,
        )


def test_rejects_protocol_hash_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(producer.core, "load_structural_inputs", lambda *_: synthetic_inputs())
    protocol, protocol_sha = protocol_file(tmp_path)
    protocol.write_text("changed after freeze\n", encoding="utf-8", newline="\n")
    with pytest.raises(core.TrajectoryError, match="protocol specification hash mismatch"):
        producer.build_result(
            tmp_path / producer.EXPECTED_SNAPSHOT,
            producer.EXPECTED_SNAPSHOT,
            "a" * 40,
            protocol,
            protocol_sha,
        )


def test_rejects_non_preregistered_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(producer.core, "load_structural_inputs", lambda *_: synthetic_inputs())
    protocol, protocol_sha = protocol_file(tmp_path)
    with pytest.raises(core.TrajectoryError, match="preregistered ad0b"):
        producer.build_result(tmp_path / ("b" * 64), "b" * 64, "a" * 40, protocol, protocol_sha)


def test_verifier_does_not_import_extension_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "import build_structural_weight_extension" not in source
    assert "from phase1.build_structural_weight_extension" not in source


def test_full_verifier_rejects_interpretation_tampering(tmp_path: Path, monkeypatch) -> None:
    runs, records, receipts = synthetic_inputs()
    monkeypatch.setattr(producer.core, "load_structural_inputs", lambda *_: (runs, records, receipts))
    monkeypatch.setattr(verifier.independent, "inspect_inputs", lambda *_args, **_kwargs: (runs, records))
    protocol, protocol_sha = protocol_file(tmp_path)
    source = Path(producer.__file__)
    source_sha = digest(source)
    source_commit = "a" * 40
    result = producer.build_result(
        tmp_path / producer.EXPECTED_SNAPSHOT,
        producer.EXPECTED_SNAPSHOT,
        source_commit,
        protocol,
        protocol_sha,
    )
    artifact = tmp_path / "trajectory.json"
    artifact.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    receipt = verifier.verify(
        tmp_path / producer.EXPECTED_SNAPSHOT,
        artifact,
        digest(artifact),
        source,
        source_sha,
        source_commit,
        protocol,
        protocol_sha,
    )
    assert receipt["status"] == "INDEPENDENT_STRUCTURAL_WEIGHT_EXTENSION_PASS"

    result["interpretation_contract"]["search_utility_claim"] = True
    artifact.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(verifier.independent.VerificationError, match="interpretation_contract"):
        verifier.verify(
            tmp_path / producer.EXPECTED_SNAPSHOT,
            artifact,
            digest(artifact),
            source,
            source_sha,
            source_commit,
            protocol,
            protocol_sha,
        )
