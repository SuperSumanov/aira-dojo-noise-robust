from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from phase1 import audit_target522_linear_contrast_rank as rank_audit
from phase1 import project_target522_rank_stage_a_compatibility as projector
from phase1 import verify_target522_linear_contrast_rank as rank_verifier
from phase1 import verify_target522_rank_stage_a_projection as projection_verifier


ROOT = Path(__file__).resolve().parents[2]
COMPATIBILITY_FILE = ROOT / "phase1/target522_linear_contrast_rank_stage_a_compatibility_v1.json"
RANK_PROTOCOL_FILE = ROOT / "phase1/target522_linear_contrast_rank_audit_v1.json"
STAGE_EXECUTION_FILE = ROOT / "phase1/vertex_cost_contrast_target522_execution_v2.json"
STAGE_COMPATIBILITY_FILE = ROOT / "phase1/target522_selection_container_compatibility_v1.json"
EXECUTION_FILE = ROOT / "phase1/target522_linear_contrast_rank_execution_v2.json"
RUNNER = ROOT / "phase1/scripts/run_target522_linear_contrast_rank_audit_compat_v2_20260902.sh"
MONITOR = ROOT / "phase1/scripts/monitor_target522_linear_contrast_rank_audit_compat_v2_20260902.sh"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_ratio(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def graph(pairs: int, endpoints: int, parents: int, runs: int, marker: str) -> dict:
    return {
        "pairs": pairs,
        "endpoints": endpoints,
        "parents": parents,
        "physical_runs": runs,
        "tasks": 5,
        "maximum_single_task_pair_share": exact_ratio(1, 5),
        "maximum_single_run_pair_share": exact_ratio(1, 10),
        "orientation_free_graph_sha256": marker * 64,
    }


def stage_a_v2() -> dict:
    compatibility = json.loads(COMPATIBILITY_FILE.read_text(encoding="utf-8"))
    bridge = compatibility["stage_a_execution_bridge"]
    return {
        "protocol": bridge["public_protocol"],
        "status": "COMPLETE",
        "protocol_sha256": bridge["scientific_protocol_sha256"],
        "selection_container_compatibility_sha256": bridge[
            "selection_container_compatibility_sha256"
        ],
        "analysis_source_commit": bridge["compatible_execution_source_commit"],
        "candidate_snapshot_sha256": "c" * 64,
        "selection_container": {
            "outer_sha256sums_sha256": bridge["outer_selection_sha256sums_sha256"],
            "core_projection_sha256sums_sha256": "d" * 64,
            "manifest_bound_auxiliary_receipt_count": 6,
        },
        "append_only": True,
        "pair_file_bindings": {
            "structural_pair_files_equal_exact_observed_sibling_cliques": True,
        },
        "run_partition": {"algorithm": "fixture", "overlap": 0},
        "acquisition_graph": graph(120, 110, 10, 20, "a"),
        "evaluation_graph": graph(96, 86, 6, 15, "b"),
        "support_gates": {"a": True, "b": True},
        "scope": {
            "outcome_blind_code_and_topology_only": True,
            "label_grade_gap_prediction_accuracy_utility_runtime_used": False,
            "prospective_values_read": False,
            "first960_closure_opened": False,
            "raw_identities_publicly_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "classification": "fixture-not-inspected-by-projector",
        "checkpoints": [],
        "uniform_baseline": {},
        "vccd": {},
        "yield_baseline": {},
        "yield_floors": {},
        "yield_solver": {},
        "yield_witness_gates": {},
        "arm_metrics": {},
        "private_selection_sha256": "e" * 64,
    }


def frozen_inputs() -> tuple[dict, str, dict, str]:
    compatibility = json.loads(COMPATIBILITY_FILE.read_text(encoding="utf-8"))
    protocol = json.loads(RANK_PROTOCOL_FILE.read_text(encoding="utf-8"))
    return compatibility, digest(COMPATIBILITY_FILE), protocol, digest(RANK_PROTOCOL_FILE)


def project(stage: dict | None = None) -> tuple[dict, dict]:
    compatibility, compatibility_sha, protocol, protocol_sha = frozen_inputs()
    return projector.validate_and_project(
        compatibility,
        compatibility_sha,
        protocol,
        protocol_sha,
        stage or stage_a_v2(),
        "f" * 64,
    )


def test_projection_is_exact_and_byte_frozen_rank_accepts_it() -> None:
    compatibility, compatibility_sha, protocol, protocol_sha = frozen_inputs()
    stage = stage_a_v2()
    projected, receipt = project(stage)
    assert set(stage) - set(projected) == {
        "selection_container",
        "selection_container_compatibility_sha256",
    }
    assert projected["analysis_source_commit"] == protocol["frozen_stage_a"]["source_commit"]
    assert receipt["other_top_level_changes"] == 0
    projected_sha = hashlib.sha256(projector.canonical_bytes(projected)).hexdigest()
    result = rank_audit.build(protocol, protocol_sha, projected, projected_sha)
    verified = rank_verifier.verify(
        protocol,
        protocol_sha,
        projected,
        projected_sha,
        result,
        "1" * 64,
    )
    assert verified["status"] == "INDEPENDENT_RECONSTRUCTION_EXACT"
    independent = projection_verifier.verify(
        compatibility,
        compatibility_sha,
        protocol,
        protocol_sha,
        stage,
        "f" * 64,
        projected,
        projected_sha,
        receipt,
        "2" * 64,
    )
    assert independent["status"] == "INDEPENDENT_PROJECTION_RECONSTRUCTION_EXACT"


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda stage: stage.update(unexpected="x"), "top-level schema drift"),
        (
            lambda stage: stage["selection_container"].update(
                outer_sha256sums_sha256="0" * 64
            ),
            "outer selection manifest drift",
        ),
        (lambda stage: stage.update(endpoint_ids=["forbidden"]), "top-level schema drift"),
        (lambda stage: stage.update(analysis_source_commit="0" * 40), "execution source drift"),
    ],
)
def test_projection_fails_closed_on_unapproved_drift(mutation, match: str) -> None:
    stage = stage_a_v2()
    mutation(stage)
    with pytest.raises(ValueError, match=match):
        project(stage)


def test_independent_verifier_rejects_projection_or_receipt_tamper() -> None:
    compatibility, compatibility_sha, protocol, protocol_sha = frozen_inputs()
    stage = stage_a_v2()
    projected, receipt = project(stage)
    projected_sha = hashlib.sha256(projector.canonical_bytes(projected)).hexdigest()
    tampered = copy.deepcopy(projected)
    tampered["analysis_source_commit"] = stage["analysis_source_commit"]
    with pytest.raises(ValueError, match="projection reconstruction mismatch"):
        projection_verifier.verify(
            compatibility,
            compatibility_sha,
            protocol,
            protocol_sha,
            stage,
            "f" * 64,
            tampered,
            hashlib.sha256(projector.canonical_bytes(tampered)).hexdigest(),
            receipt,
            "2" * 64,
        )
    receipt["other_top_level_changes"] = 1
    with pytest.raises(ValueError, match="projection receipt mismatch"):
        projection_verifier.verify(
            compatibility,
            compatibility_sha,
            protocol,
            protocol_sha,
            stage,
            "f" * 64,
            projected,
            projected_sha,
            receipt,
            "2" * 64,
        )


def test_projector_cli_is_deterministic_and_exclusive(tmp_path: Path) -> None:
    stage_path = tmp_path / "stage.json"
    stage_path.write_text(json.dumps(stage_a_v2()), encoding="utf-8")
    stage_sha = digest(stage_path)
    common = [
        sys.executable,
        "-m",
        "phase1.project_target522_rank_stage_a_compatibility",
        "--compatibility",
        str(COMPATIBILITY_FILE),
        "--compatibility-sha256",
        digest(COMPATIBILITY_FILE),
        "--rank-protocol",
        str(RANK_PROTOCOL_FILE),
        "--rank-protocol-sha256",
        digest(RANK_PROTOCOL_FILE),
        "--stage-a-public",
        str(stage_path),
        "--stage-a-public-sha256",
        stage_sha,
    ]
    projected_a = tmp_path / "projected_a.json"
    receipt_a = tmp_path / "receipt_a.json"
    projected_b = tmp_path / "projected_b.json"
    receipt_b = tmp_path / "receipt_b.json"
    subprocess.run(
        common
        + ["--projected-output", str(projected_a), "--receipt-output", str(receipt_a)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        common
        + ["--projected-output", str(projected_b), "--receipt-output", str(receipt_b)],
        check=True,
        capture_output=True,
    )
    assert projected_a.read_bytes() == projected_b.read_bytes()
    assert receipt_a.read_bytes() == receipt_b.read_bytes()
    failed = subprocess.run(
        common
        + ["--projected-output", str(projected_a), "--receipt-output", str(receipt_a)],
        capture_output=True,
    )
    assert failed.returncode != 0


def test_compatibility_file_binds_unchanged_science_and_stage_v2() -> None:
    compatibility = json.loads(COMPATIBILITY_FILE.read_text(encoding="utf-8"))
    assert compatibility["rank_scientific_protocol"]["sha256"] == digest(RANK_PROTOCOL_FILE)
    bridge = compatibility["stage_a_execution_bridge"]
    assert bridge["execution_protocol_v2_sha256"] == digest(STAGE_EXECUTION_FILE)
    assert bridge["selection_container_compatibility_sha256"] == digest(
        STAGE_COMPATIBILITY_FILE
    )
    protocol = json.loads(RANK_PROTOCOL_FILE.read_text(encoding="utf-8"))
    assert bridge["frozen_scientific_source_commit"] == protocol["frozen_stage_a"][
        "source_commit"
    ]
    assert bridge["scientific_protocol_sha256"] == protocol["frozen_stage_a"][
        "scientific_protocol_sha256"
    ]


def test_v2_shells_parse_and_keep_results_out_of_monitor_receipt() -> None:
    for path in (RUNNER, MONITOR):
        if os.name != "nt":
            subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True)
        source = path.read_text(encoding="utf-8")
        assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", source)) == 13
        assert "sbatch" not in source
        assert "nvidia-smi" not in source
        assert "gpu_paid_api_model_fit_base_update=0/0/0/0" in source
        assert "formal-05458c4-selection-v2" in source
        assert '"$stage_a/private_a.json"' not in source
    runner = RUNNER.read_text(encoding="utf-8")
    assert "phase1.project_target522_rank_stage_a_compatibility" in runner
    assert "phase1.verify_target522_rank_stage_a_projection" in runner
    assert "phase1.audit_target522_linear_contrast_rank" in runner
    assert "phase1.verify_target522_linear_contrast_rank" in runner
    assert 'cmp "$output/stage_a_projected_a.json" "$output/stage_a_projected_b.json"' in runner
    assert 'cmp "$output/result_a.json" "$output/result_b.json"' in runner
    assert 'timeout 1800s "$python_bin" -m pytest -q phase1/tests' in runner
    assert "strace -ff -tt -yy -e trace=file,network" in runner
    assert "classification_emitted=false" in runner
    monitor = MONITOR.read_text(encoding="utf-8")
    activation = monitor.index('if test -f "$stage_a/COMPLETE"')
    prefix = monitor[:activation]
    assert "producer_a.json" not in prefix
    assert "result_a.json" not in prefix
    assert "classification=$(" not in monitor
    assert "rank_classification_emitted=false" in monitor
    assert "for poll in $(seq 0 720)" in monitor


def test_v2_execution_binds_every_source_and_unchanged_science() -> None:
    execution = json.loads(EXECUTION_FILE.read_text(encoding="utf-8"))
    assert execution["protocol"] == "target522-linear-contrast-rank-execution-v2"
    assert execution["scientific_protocol"]["sha256"] == digest(RANK_PROTOCOL_FILE)
    assert execution["scientific_protocol"]["changed_from_v1"] is False
    assert execution["scientific_protocol"]["threshold_partition_decision_rule_changed"] is False
    assert execution["stage_a_compatibility"]["sha256"] == digest(COMPATIBILITY_FILE)
    for binding in execution["bindings"].values():
        assert digest(ROOT / binding["path"]) == binding["sha256"]
    assert execution["reporting"]["runner_stdout_contains_rank_classification"] is False
    assert execution["reporting"]["monitor_ready_contains_rank_classification"] is False
    assert execution["resources"] == {
        "gpu": 0,
        "paid_api_calls": 0,
        "model_fits": 0,
        "base_updates": 0,
        "cpu": "one thread; expected under ten seconds excluding fresh full tests",
    }
