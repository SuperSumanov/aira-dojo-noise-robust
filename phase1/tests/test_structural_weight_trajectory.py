from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_structural_weight_trajectory import (
    STATUS,
    TrajectoryError,
    build_result,
    decomposition,
)
from phase1.verify_structural_weight_trajectory import verify


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> str:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return digest(path)


def write_jsonl(path: Path, rows: list[dict]) -> str:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    return digest(path)


def make_fixture(tmp_path: Path) -> tuple[Path, str, Path, str]:
    state = tmp_path / "state"
    intakes = state / "intakes"
    snapshots = state / "snapshots"
    intakes.mkdir(parents=True)
    snapshots.mkdir()
    runs = []
    by_drop: dict[str, list[dict]] = {}
    pairs_by_drop: dict[str, list[dict]] = {}
    for index in range(339):
        task = "task-a" if index % 2 == 0 else "task-b"
        if index >= 240 and index % 11 == 0:
            task = "task-new"
        drop_id = f"drop-{index // 40:02d}"
        source_sha = hashlib.sha256(f"run-{index}".encode()).hexdigest()
        run_id = f"journal:{source_sha}"
        pair_count = 1 if index < 240 or task != "task-b" else 8
        endpoints = max(2, pair_count + 1)
        started = f"2026-08-{13 + index // 24:02d}T{index % 24:02d}:00:00Z"
        run = {
            "run_id": run_id,
            "task": task,
            "generation_started_at_utc": started,
            "source_sha256": source_sha,
            "drop_id": drop_id,
            "flow_status": "scoreable",
            "endpoints": endpoints,
        }
        runs.append(run)
        by_drop.setdefault(drop_id, []).append(
            {
                "run_id": run_id,
                "task": task,
                "generation_started_at_utc": started,
                "eligible": True,
                "archive_name": f"{drop_id}.tar.gz",
                "archive_sha256": hashlib.sha256(drop_id.encode()).hexdigest(),
                "journal_member": f"{drop_id}/checkpoint/journal.jsonl",
                "journal_mtime": index,
                "journal_sha256": source_sha,
                "flow_status": "scoreable",
                "endpoints": endpoints,
                "empty_code_nodes_excluded": 0,
            }
        )
        for pair_index in range(pair_count):
            left = f"{run_id}-left-{pair_index:02d}"
            right = f"{run_id}-right-{pair_index:02d}"
            pairs_by_drop.setdefault(drop_id, []).append(
                {
                    "task": task,
                    "run_id": run_id,
                    "parent": f"parent-{pair_index:02d}",
                    "left": left,
                    "right": right,
                }
            )

    registry_rows = []
    for drop_id in sorted(by_drop):
        directory = intakes / drop_id
        directory.mkdir()
        provenance_sha = write_json(directory / "source_provenance.json", by_drop[drop_id])
        pair_sha = write_jsonl(directory / "eligible_structural_pairs.jsonl", pairs_by_drop[drop_id])
        # Deliberately invalid content: the producer must never open this file.
        (directory / "label_vault.jsonl").write_text("not-json\n", encoding="utf-8")
        summary = {
            "protocol": "prospective_drop_intake_v1",
            "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
            "blindness": {
                "label_values_printed": False,
                "labels_used_for_endpoint_selection": False,
                "labels_used_for_run_selection": False,
                "metrics_computed": [],
            },
            "security": {"env_members_read": False},
            "inventory": {
                "eligible_runs": len(by_drop[drop_id]),
                "eligible_structural_pairs": len(pairs_by_drop[drop_id]),
            },
            "outputs": {
                "source_provenance_sha256": provenance_sha,
                "eligible_structural_pairs_sha256": pair_sha,
            },
        }
        summary_sha = write_json(directory / "summary.json", summary)
        registry_rows.append(
            {"drop_id": drop_id, "intake_dir": str(directory), "summary_sha256": summary_sha}
        )

    staging = snapshots / "staging"
    (staging / "accumulator").mkdir(parents=True)
    registry_sha = write_jsonl(staging / "intake_registry.jsonl", registry_rows)
    runs_sha = write_jsonl(staging / "accumulator" / "provisional_first960_runs.jsonl", runs)
    pair_total = sum(len(value) for value in pairs_by_drop.values())
    accumulator = {
        "protocol": "prospective_accumulator_v1",
        "status": "PROSPECTIVE_COHORT_COLLECTING",
        "inputs": {"registry_sha256": registry_sha},
        "outputs": {"provisional_first960_runs_sha256": runs_sha},
        "inventory": {
            "drops": len(registry_rows),
            "provisional_first960_runs": len(runs),
            "provisional_first960_endpoints": sum(row["endpoints"] for row in runs),
            "provisional_first960_structural_pairs": pair_total,
        },
        "security": {
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
    }
    write_json(staging / "accumulator" / "summary.json", accumulator)
    manifest_rows = []
    for relative in (
        "accumulator/provisional_first960_runs.jsonl",
        "accumulator/summary.json",
        "intake_registry.jsonl",
    ):
        manifest_rows.append(f"{digest(staging / relative)}  {relative}\n")
    (staging / "SHA256SUMS").write_text("".join(manifest_rows), encoding="utf-8", newline="\n")
    snapshot = digest(staging / "SHA256SUMS")
    snapshot_root = snapshots / snapshot
    staging.rename(snapshot_root)

    protocol = tmp_path / "First960_结构权重时序分解_结果前冻结.md"
    protocol.write_text("frozen before trajectory\n", encoding="utf-8", newline="\n")
    return snapshot_root, snapshot, protocol, digest(protocol)


def test_builds_deterministic_outcome_blind_trajectory(tmp_path: Path) -> None:
    root, snapshot, protocol, protocol_sha = make_fixture(tmp_path)
    result = build_result(root, snapshot, "a" * 40, protocol, protocol_sha)

    assert result["status"] == STATUS
    assert result["current_prefix"]["inventory"]["runs"] == 339
    assert len(result["full_prefix_trajectory"]) == 339
    assert [row["prefix_runs"] for row in result["milestones"]] == [
        120,
        160,
        200,
        240,
        260,
        280,
        300,
        320,
        339,
    ]
    assert result["security"]["label_vault_opened"] is False
    assert result["security"]["eligible_blind_manifest_opened"] is False
    for metric in result["mechanism_decomposition"].values():
        if isinstance(metric, dict):
            assert abs(metric["additivity_residual"]) < 1e-12


def test_rejects_structural_pair_hash_tampering(tmp_path: Path) -> None:
    root, snapshot, protocol, protocol_sha = make_fixture(tmp_path)
    first_intake = sorted((root.parents[1] / "intakes").iterdir())[0]
    with (first_intake / "eligible_structural_pairs.jsonl").open("a", encoding="utf-8") as file:
        file.write("{}\n")
    with pytest.raises(TrajectoryError, match="input hash mismatch"):
        build_result(root, snapshot, "a" * 40, protocol, protocol_sha)


def test_new_task_midpoint_convention_is_exact() -> None:
    baseline = {
        "counts": {
            "runs": {"old": 2},
            "structural_pairs": {"old": 2},
        }
    }
    current = {
        "counts": {
            "runs": {"new": 1, "old": 3},
            "structural_pairs": {"new": 5, "old": 6},
        }
    }
    result = decomposition(baseline, current)
    new_row = next(row for row in result["midpoint_pair_count_by_task"] if row["task"] == "new")
    assert new_row["run_composition_count_contribution"] == 5
    assert new_row["opportunity_yield_count_contribution"] == 0
    assert new_row["additivity_residual"] == 0


def test_rejects_nonblind_accumulator(tmp_path: Path) -> None:
    root, snapshot, protocol, protocol_sha = make_fixture(tmp_path)
    # The snapshot manifest prevents rewriting the receipt and laundering its hash.
    summary_path = root / "accumulator" / "summary.json"
    value = json.loads(summary_path.read_text(encoding="utf-8"))
    value["security"]["label_vault_opened"] = True
    write_json(summary_path, value)
    with pytest.raises(TrajectoryError, match="snapshot file hash mismatch"):
        build_result(root, snapshot, "a" * 40, protocol, protocol_sha)


def test_independent_verifier_reconstructs_every_claim_section(tmp_path: Path) -> None:
    root, snapshot, protocol, protocol_sha = make_fixture(tmp_path)
    result = build_result(root, snapshot, "a" * 40, protocol, protocol_sha)
    artifact = tmp_path / "trajectory.json"
    artifact_sha = write_json(artifact, result)
    producer = Path(__file__).parents[1] / "build_structural_weight_trajectory.py"

    receipt = verify(
        root,
        artifact,
        artifact_sha,
        producer,
        digest(producer),
        protocol,
        protocol_sha,
    )
    assert receipt["status"] == "INDEPENDENT_STRUCTURAL_WEIGHT_TRAJECTORY_PASS"
    assert receipt["checks"]["all_339_prefixes_recomputed"] is True
