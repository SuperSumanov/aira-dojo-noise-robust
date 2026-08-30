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

from phase1 import audit_target522_linear_contrast_rank as audit
from phase1 import verify_target522_linear_contrast_rank as verifier


SOURCE_COMMIT = "4fc9c3e4c9629ac86960a9cca198569e6a80ee2c"
SCIENTIFIC_SHA = "b3df170ebb4ae097549cb0225142e94aebfa481aea6c79815f1be2af687d9e1d"
PROTOCOL_SHA = "1" * 64
STAGE_SHA = "2" * 64
ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_target522_linear_contrast_rank_audit_formal_20260830.sh"
MONITOR = ROOT / "phase1/scripts/monitor_target522_linear_contrast_rank_audit_formal_20260830.sh"
PROTOCOL_FILE = ROOT / "phase1/target522_linear_contrast_rank_audit_v1.json"
EXECUTION_FILE = ROOT / "phase1/target522_linear_contrast_rank_execution_v1.json"


def protocol() -> dict:
    return {
        "protocol": "target522-linear-contrast-rank-audit-v1",
        "status": "FROZEN_AFTER_DISCLOSED_HISTORICAL_EXPLORATION_BEFORE_TARGET522_CANDIDATE",
        "freeze_observation": {
            "target522_candidate_present": False,
            "target522_ready_present": False,
            "target522_complete_present": False,
            "candidate_profile_or_identity_opened": False,
            "prospective_values_read": False,
        },
        "frozen_stage_a": {
            "source_commit": SOURCE_COMMIT,
            "scientific_protocol_sha256": SCIENTIFIC_SHA,
        },
        "confirmation_gates": {
            "material_pair_rows_per_rank_numerator": 6,
            "material_pair_rows_per_rank_denominator": 5,
            "maximum_single_task_pair_share_numerator": 7,
            "maximum_single_task_pair_share_denominator": 20,
            "acquisition": {
                "minimum_pairs": 100,
                "minimum_physical_runs": 20,
                "minimum_tasks": 5,
            },
            "evaluation": {
                "minimum_pairs": 80,
                "minimum_physical_runs": 15,
                "minimum_tasks": 5,
            },
        },
    }


def ratio(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def profile(pairs: int, endpoints: int, parents: int, runs: int, marker: str) -> dict:
    return {
        "pairs": pairs,
        "endpoints": endpoints,
        "parents": parents,
        "physical_runs": runs,
        "tasks": 5,
        "maximum_single_task_pair_share": ratio(1, 5),
        "maximum_single_run_pair_share": ratio(1, 10),
        "orientation_free_graph_sha256": marker * 64,
    }


def stage_a() -> dict:
    return {
        "protocol": "vertex-cost-contrast-target522-selection-public-v1",
        "status": "COMPLETE",
        "protocol_sha256": SCIENTIFIC_SHA,
        "analysis_source_commit": SOURCE_COMMIT,
        "candidate_snapshot_sha256": "c" * 64,
        "pair_file_bindings": {
            "structural_pair_files_equal_exact_observed_sibling_cliques": True,
        },
        "run_partition": {"overlap": 0},
        "support_gates": {"a": True, "b": True},
        "acquisition_graph": profile(120, 110, 10, 20, "a"),
        "evaluation_graph": profile(96, 86, 6, 15, "b"),
        "scope": {
            "outcome_blind_code_and_topology_only": True,
            "label_grade_gap_prediction_accuracy_utility_runtime_used": False,
            "prospective_values_read": False,
            "first960_closure_opened": False,
            "raw_identities_publicly_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def build(stage: dict | None = None) -> dict:
    return audit.build(protocol(), PROTOCOL_SHA, stage or stage_a(), STAGE_SHA)


def test_both_disjoint_graphs_confirm_exact_threshold() -> None:
    result = build()
    assert result["classification"] == "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_CONFIRMED"
    assert result["graphs"]["acquisition"]["incidence_rank"] == 100
    assert result["graphs"]["acquisition"]["redundant_pair_rows"] == 20
    assert result["graphs"]["acquisition"]["pair_rows_per_incidence_rank"] == ratio(6, 5)
    assert result["graphs"]["acquisition"]["redundant_pair_row_share"] == ratio(1, 6)
    assert result["scope"]["prospective_values_read"] is False


def test_one_graph_below_threshold_does_not_confirm() -> None:
    stage = stage_a()
    stage["evaluation_graph"] = profile(95, 86, 6, 15, "b")
    result = build(stage)
    assert result["classification"] == "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_NOT_CONFIRMED"
    assert result["graphs"]["evaluation"]["all_gates_pass"] is False


def test_failed_stage_support_is_limited_not_negative() -> None:
    stage = stage_a()
    stage["support_gates"]["b"] = False
    result = build(stage)
    assert result["classification"] == "TARGET522_LINEAR_CONTRAST_RANK_AUDIT_LIMITED_SUPPORT"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda stage: stage["pair_file_bindings"].update(
            structural_pair_files_equal_exact_observed_sibling_cliques=False
        ),
        lambda stage: stage["run_partition"].update(overlap=1),
        lambda stage: stage["scope"].update(prospective_values_read=True),
        lambda stage: stage.update(analysis_source_commit="0" * 40),
    ],
)
def test_integrity_drift_fails_closed(mutation) -> None:
    stage = stage_a()
    mutation(stage)
    with pytest.raises(ValueError):
        build(stage)


def test_independent_verifier_reconstructs_exact_result() -> None:
    stage = stage_a()
    result = build(stage)
    receipt = verifier.verify(
        protocol(), PROTOCOL_SHA, stage, STAGE_SHA, result, "3" * 64
    )
    assert receipt["status"] == "INDEPENDENT_RECONSTRUCTION_EXACT"
    assert receipt["graphs_reconstructed"] == 2
    assert receipt["prospective_values_read"] is False


def test_independent_verifier_rejects_numeric_tamper() -> None:
    stage = stage_a()
    result = build(stage)
    result["graphs"]["evaluation"]["incidence_rank"] += 1
    with pytest.raises(ValueError, match="graph reconstruction"):
        verifier.verify(protocol(), PROTOCOL_SHA, stage, STAGE_SHA, result, "3" * 64)


def test_share_decimal_or_reduction_drift_fails_closed() -> None:
    stage = stage_a()
    stage["acquisition_graph"]["maximum_single_task_pair_share"]["decimal_17g"] = "0.21"
    with pytest.raises(ValueError, match="decimal"):
        build(stage)
    stage = stage_a()
    stage["evaluation_graph"]["maximum_single_run_pair_share"] = ratio(2, 20)
    with pytest.raises(ValueError, match="not reduced"):
        build(stage)


def test_independent_verifier_rejects_boundary_or_extra_identity_tamper() -> None:
    stage = stage_a()
    result = build(stage)
    result["interpretation_boundary"]["not_claimed"].remove("effective sample size")
    with pytest.raises(ValueError, match="interpretation exclusions"):
        verifier.verify(protocol(), PROTOCOL_SHA, stage, STAGE_SHA, result, "3" * 64)
    result = build(stage)
    result["endpoint_ids"] = ["forbidden"]
    with pytest.raises(ValueError, match="result schema"):
        verifier.verify(protocol(), PROTOCOL_SHA, stage, STAGE_SHA, result, "3" * 64)


def test_cli_outputs_are_deterministic_and_exclusive(tmp_path) -> None:
    protocol_path = tmp_path / "protocol.json"
    stage_path = tmp_path / "stage.json"
    protocol_path.write_text(json.dumps(protocol()), encoding="utf-8")
    stage_path.write_text(json.dumps(stage_a()), encoding="utf-8")
    protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    stage_sha = hashlib.sha256(stage_path.read_bytes()).hexdigest()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    command = [
        sys.executable,
        "-m",
        "phase1.audit_target522_linear_contrast_rank",
        "--protocol",
        str(protocol_path),
        "--protocol-sha256",
        protocol_sha,
        "--stage-a-public",
        str(stage_path),
        "--stage-a-public-sha256",
        stage_sha,
    ]
    subprocess.run(command + ["--output", str(first)], check=True, capture_output=True)
    subprocess.run(command + ["--output", str(second)], check=True, capture_output=True)
    assert first.read_bytes() == second.read_bytes()
    failed = subprocess.run(command + ["--output", str(first)], capture_output=True)
    assert failed.returncode != 0

    claimed_sha = hashlib.sha256(first.read_bytes()).hexdigest()
    receipt = tmp_path / "receipt.json"
    verify_command = [
        sys.executable,
        "-m",
        "phase1.verify_target522_linear_contrast_rank",
        "--protocol",
        str(protocol_path),
        "--protocol-sha256",
        protocol_sha,
        "--stage-a-public",
        str(stage_path),
        "--stage-a-public-sha256",
        stage_sha,
        "--claimed-result",
        str(first),
        "--claimed-result-sha256",
        claimed_sha,
        "--output",
        str(receipt),
    ]
    completed = subprocess.run(verify_command, check=True, capture_output=True, text=True)
    assert "INDEPENDENT_RECONSTRUCTION_EXACT" in completed.stdout
    assert json.loads(receipt.read_text())["prospective_values_read"] is False


def test_result_contains_no_stage_identity_collections() -> None:
    result = build()
    serialized = json.dumps(result, sort_keys=True)
    assert "endpoint_ids" not in serialized
    assert "run_ids" not in serialized
    assert "parent_ids" not in serialized
    assert "task_ids" not in serialized


def test_formal_shell_sources_parse_and_have_full_preflight() -> None:
    for path in (RUNNER, MONITOR):
        if os.name != "nt":
            subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True)
        source = path.read_text(encoding="utf-8")
        assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", source)) == 13
        assert "gpu_paid_api_model_fit_base_update=0/0/0/0" in source
        assert "sbatch" not in source
        assert "nvidia-smi" not in source


def test_formal_runner_repeats_public_only_analysis_and_independent_verification() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "if [[ $# -ne 10 ]]" in source
    assert "result_a.json" in source and "result_b.json" in source
    assert "verification_a.json" in source and "verification_b.json" in source
    assert 'cmp "$output/result_a.json" "$output/result_b.json"' in source
    assert 'cmp "$output/verification_a.json" "$output/verification_b.json"' in source
    assert "phase1.audit_target522_linear_contrast_rank" in source
    assert "phase1.verify_target522_linear_contrast_rank" in source
    assert 'timeout 1800s "$python_bin" -m pytest -q phase1/tests' in source
    assert "strace -ff -tt -yy -e trace=file,network" in source
    assert 'sha256sum -c "$stage_a/SHA256SUMS"' not in source
    assert '"$stage_a/producer_a.json"' in source
    assert '"$stage_a/private_a.json"' not in source


def test_monitor_reads_no_stage_profile_before_complete_and_is_resumable() -> None:
    source = MONITOR.read_text(encoding="utf-8")
    assert "if [[ $# -ne 10 ]]" in source
    assert "[[ $mode == start || $mode == resume ]]" in source
    assert "for poll in $(seq 0 720)" in source
    activation = source.index('if test -f "$stage_a/COMPLETE"')
    prefix = source[:activation]
    assert "producer_a.json" not in prefix
    assert "result_a.json" not in prefix
    assert 'bash "$root/formal_runner.sh"' in source[activation:]
    assert "INTERRUPTED_RC" in source


def test_frozen_protocol_and_execution_bind_exact_sources() -> None:
    scientific = json.loads(PROTOCOL_FILE.read_text(encoding="utf-8"))
    execution = json.loads(EXECUTION_FILE.read_text(encoding="utf-8"))
    assert scientific["protocol"] == "target522-linear-contrast-rank-audit-v1"
    assert (
        scientific["status"]
        == "FROZEN_AFTER_DISCLOSED_HISTORICAL_EXPLORATION_BEFORE_TARGET522_CANDIDATE"
    )
    assert set(scientific["confirmation_gates"]) == {
        "material_pair_rows_per_rank_numerator",
        "material_pair_rows_per_rank_denominator",
        "maximum_single_task_pair_share_numerator",
        "maximum_single_task_pair_share_denominator",
        "acquisition",
        "evaluation",
    }
    for binding in scientific["source_bindings"].values():
        path = ROOT / binding["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]
    assert execution["scientific_protocol"]["sha256"] == hashlib.sha256(
        PROTOCOL_FILE.read_bytes()
    ).hexdigest()
    for binding in execution["bindings"].values():
        path = ROOT / binding["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]
