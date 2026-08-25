from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_structural_dependency_atlas import AtlasError, build_atlas
from phase1.verify_structural_dependency_atlas import (
    AtlasVerificationError,
    verify,
)


SOURCE = Path(__file__).parents[1] / "build_structural_dependency_atlas.py"


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> str:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return file_sha(path)


def support(
    run_counts: dict[str, int],
    endpoint_counts: dict[str, int],
    pair_counts: dict[str, int],
) -> dict:
    runs = sum(run_counts.values())
    endpoints = sum(endpoint_counts.values())
    pairs = sum(pair_counts.values())
    return {
        "runs": runs,
        "tasks": len(run_counts),
        "endpoints": endpoints,
        "structural_pairs": pairs,
        "run_counts": run_counts,
        "endpoint_counts": endpoint_counts,
        "structural_pair_counts": pair_counts,
        "dominant_run_task_share": max(run_counts.values()) / runs,
        "dominant_endpoint_task_share": max(endpoint_counts.values()) / endpoints,
        "dominant_structural_pair_task_share": max(pair_counts.values()) / pairs,
    }


def fixture(tmp_path: Path) -> tuple[Path, str, Path, str]:
    accumulator_path = tmp_path / "summary.json"
    accumulator = {
        "protocol": "prospective_accumulator_v1",
        "security": {
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
        "task_support": {
            "provisional_first240": support(
                {"task-a": 2, "task-b": 2},
                {"task-a": 4, "task-b": 4},
                {"task-a": 2, "task-b": 2},
            ),
            "provisional_first960": support(
                {"task-a": 2, "task-b": 2, "task-c": 2},
                {"task-a": 4, "task-b": 4, "task-c": 10},
                {"task-a": 1, "task-b": 1, "task-c": 8},
            ),
        },
    }
    accumulator_sha = write_json(accumulator_path, accumulator)
    gate_path = tmp_path / "structural_gate.json"
    gate = {
        "protocol": "prospective_structural_gate_independent_verifier_v5",
        "snapshot_sha256": "b" * 64,
        "inputs": {"accumulator_summary_sha256": accumulator_sha},
        "security": {
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
        "independent_inventory": {
            "provisional_first960": {
                "runs": 6,
                "tasks": 3,
                "endpoints": 18,
                "structural_pairs": 10,
                "pair_tasks": 3,
            }
        },
        "asset_quality": {
            "decision_support": {
                "decision_parent_groups": 8,
                "runs_with_finite_decision": 5,
                "tasks_with_finite_decision": 3,
                "median_pairs_per_decision_run": 2.0,
            }
        },
    }
    gate_sha = write_json(gate_path, gate)
    return accumulator_path, accumulator_sha, gate_path, gate_sha


def build_fixture_atlas(tmp_path: Path) -> tuple[Path, str, Path, str, Path, str]:
    accumulator_path, accumulator_sha, gate_path, gate_sha = fixture(tmp_path)
    atlas = build_atlas(
        accumulator_path,
        accumulator_sha,
        gate_path,
        gate_sha,
        "a" * 40,
    )
    atlas_path = tmp_path / "atlas.json"
    atlas_sha = write_json(atlas_path, atlas)
    return accumulator_path, accumulator_sha, gate_path, gate_sha, atlas_path, atlas_sha


def test_builder_recomputes_weighting_shift_and_dependency_funnel(tmp_path: Path) -> None:
    accumulator_path, accumulator_sha, gate_path, gate_sha = fixture(tmp_path)
    atlas = build_atlas(
        accumulator_path,
        accumulator_sha,
        gate_path,
        gate_sha,
        "a" * 40,
    )
    current = atlas["scopes"]["provisional_first960_prefix"]
    pair_stats = current["task_concentration_by_weighting"]["structural_pairs"]
    assert pair_stats["maximum_share"] == pytest.approx(0.8)
    assert pair_stats["inverse_hhi_descriptive_diversity"] == pytest.approx(1 / 0.66)
    shift = current["weighting_shift"]["runs_to_structural_pairs"]
    assert shift["total_variation_distance"] == pytest.approx(0.4666666666666667)
    assert shift["comparison_dominant_task_share_amplification"] == pytest.approx(2.4)
    assert shift["dominant_task_sets_overlap"] is True
    funnel = atlas["dependency_funnel"]
    assert funnel["pairs_above_one_per_parent_group"] == 2
    assert funnel["pairs_per_parent_group"] == pytest.approx(1.25)
    flags = atlas["chronological_comparison"]["descriptive_flags"]
    assert flags == {
        "run_max_share_fell_while_pair_max_share_rose": True,
        "pair_inverse_hhi_diversity_fell_despite_more_tasks": True,
    }
    assert atlas["security"]["prediction_values_read_or_aggregated"] is False


def test_builder_rejects_gate_that_does_not_bind_accumulator(tmp_path: Path) -> None:
    accumulator_path, accumulator_sha, gate_path, _ = fixture(tmp_path)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["inputs"]["accumulator_summary_sha256"] = "c" * 64
    gate_sha = write_json(gate_path, gate)
    with pytest.raises(AtlasError, match="does not bind"):
        build_atlas(
            accumulator_path,
            accumulator_sha,
            gate_path,
            gate_sha,
            "a" * 40,
        )


def test_builder_rejects_nonblind_accumulator(tmp_path: Path) -> None:
    accumulator_path, _, gate_path, _ = fixture(tmp_path)
    accumulator = json.loads(accumulator_path.read_text(encoding="utf-8"))
    accumulator["security"]["label_vault_opened"] = True
    accumulator_sha = write_json(accumulator_path, accumulator)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["inputs"]["accumulator_summary_sha256"] = accumulator_sha
    gate_sha = write_json(gate_path, gate)
    with pytest.raises(AtlasError, match="not outcome-blind"):
        build_atlas(
            accumulator_path,
            accumulator_sha,
            gate_path,
            gate_sha,
            "a" * 40,
        )


def test_independent_verifier_accepts_exact_atlas(tmp_path: Path) -> None:
    (
        accumulator_path,
        accumulator_sha,
        gate_path,
        gate_sha,
        atlas_path,
        atlas_sha,
    ) = build_fixture_atlas(tmp_path)
    receipt = verify(
        accumulator_path,
        accumulator_sha,
        gate_path,
        gate_sha,
        atlas_path,
        atlas_sha,
        SOURCE,
        file_sha(SOURCE),
    )
    assert receipt["status"] == "INDEPENDENT_STRUCTURAL_DEPENDENCY_ATLAS_PASS"
    assert all(receipt["checks"].values())
    assert receipt["recomputed_key_findings"]["current_pairs"] == 10


def test_independent_verifier_rejects_metric_tamper(tmp_path: Path) -> None:
    (
        accumulator_path,
        accumulator_sha,
        gate_path,
        gate_sha,
        atlas_path,
        _,
    ) = build_fixture_atlas(tmp_path)
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    atlas["scopes"]["provisional_first960_prefix"]["task_concentration_by_weighting"][
        "structural_pairs"
    ]["hhi"] = 0.1
    atlas_sha = write_json(atlas_path, atlas)
    with pytest.raises(AtlasVerificationError, match="numeric mismatch"):
        verify(
            accumulator_path,
            accumulator_sha,
            gate_path,
            gate_sha,
            atlas_path,
            atlas_sha,
            SOURCE,
            file_sha(SOURCE),
        )


def test_independent_verifier_rejects_wrong_producer_source_hash(tmp_path: Path) -> None:
    (
        accumulator_path,
        accumulator_sha,
        gate_path,
        gate_sha,
        atlas_path,
        atlas_sha,
    ) = build_fixture_atlas(tmp_path)
    with pytest.raises(AtlasVerificationError, match="producer source SHA mismatch"):
        verify(
            accumulator_path,
            accumulator_sha,
            gate_path,
            gate_sha,
            atlas_path,
            atlas_sha,
            SOURCE,
            "d" * 64,
        )
