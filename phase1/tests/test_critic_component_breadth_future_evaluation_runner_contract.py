from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "phase1"
    / "scripts"
    / "run_critic_component_breadth_future_evaluation_20260824.sh"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def assignment(name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=([^\s]+)$", text(), flags=re.MULTILINE)
    assert match is not None, name
    return match.group(1)


def hash_assignments() -> dict[str, str]:
    return dict(
        re.findall(
            r"^([a-z][a-z0-9_]*)=([0-9a-f]{64})$",
            text(),
            flags=re.MULTILINE,
        )
    )


def test_frozen_contract_and_implementation_hashes_match_sources() -> None:
    values = hash_assignments()
    expected = {
        "evaluation_contract_sha": ROOT
        / "phase1"
        / "critic_component_breadth_future_evaluation_v1.json",
        "prediction_contract_sha": ROOT
        / "phase1"
        / "critic_component_breadth_future_escrow_v1.json",
        "evaluator_sha": ROOT
        / "phase1"
        / "evaluate_critic_component_breadth_future_escrow.py",
        "evaluation_verifier_sha": ROOT
        / "phase1"
        / "verify_critic_component_breadth_future_evaluation.py",
        "base_protocol_sha": ROOT
        / "phase1"
        / "score_channel_future_identifiability_protocol_v1.json",
    }
    assert set(expected) <= set(values)
    for name, path in expected.items():
        assert values[name] == digest(path)


def test_zero_parameter_unpublished_runner_is_inert_before_external_access() -> None:
    source = text()
    assert assignment("control_commit") == "0" * 40
    assert "if [[ $# -ne 0 ]]" in source
    inert = source.index("evaluation runner is not published")
    assert inert < source.index("source /uac/y24/yzyang4/env_setup.sh")
    assert inert < source.index("base_repo=/research/")
    assert '"$1"' not in source and '"$2"' not in source and '"$3"' not in source
    assert "${1}" not in source and "${2}" not in source and "${3}" not in source


def test_fixed_anchor_prediction_and_dual_truth_roots_are_literal_release_bindings() -> None:
    assert assignment("first_closed_cohort_anchor") == (
        "/research/d7/spc/yzyang4/score-channel-future-identity-cohort/"
        "FIRST_CLOSED_COHORT_ANCHOR.json"
    )
    prediction = assignment("prediction_formal_root")
    dual = assignment("dual_truth_formal_root")
    assert prediction.startswith(
        "/research/d7/spc/yzyang4/critic-component-breadth-future/"
    )
    assert dual.startswith(
        "/research/d7/spc/yzyang4/score-channel-future-dual-truth/"
    )
    assert "UNPUBLISHED" in prediction and "UNPUBLISHED" in dual
    values = hash_assignments()
    assert values["first_closed_cohort_anchor_sha"] == "0" * 64
    assert values["prediction_bundle_sha256sums_sha"] == "0" * 64
    assert values["dual_truth_bundle_sha256sums_sha"] == "0" * 64
    assert "prediction_formal_root=${" not in text()
    assert "dual_truth_formal_root=${" not in text()


def test_prediction_then_dual_truth_predecessors_are_verified_before_evaluation() -> None:
    source = text()
    prediction_done = source.index("PREDICTION_FORMAL_PREDECESSOR_VERIFIED")
    dual_done = source.index("DUAL_TRUTH_FORMAL_PREDECESSOR_VERIFIED")
    evaluator = source.index(
        '"${clean_python[@]}" -m phase1.evaluate_critic_component_breadth_future_escrow'
    )
    assert prediction_done < dual_done < evaluator
    prediction_block = source[:prediction_done]
    assert 'verify_complete_bundle \\\n  "${prediction_formal_root}"' in prediction_block
    assert "FORMAL_FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE_TRUTH_UNREAD" in prediction_block
    assert "verification_1.json" in prediction_block
    assert "verification_2.json" in prediction_block
    assert "INDEPENDENT_SOURCE_REFIT_PASS" in prediction_block
    dual_block = source[prediction_done:dual_done]
    assert 'verify_complete_bundle \\\n  "${dual_truth_formal_root}"' in dual_block
    assert "SCORE_CHANNEL_FUTURE_DUAL_TRUTH_FORMAL_COMPLETE_REPLAY_UNAUTHORIZED" in dual_block
    assert "base_truth_a/selected_parents.jsonl" in dual_block
    assert "selected_parents_sha256" in dual_block
    assert "combined_decision.json" in dual_block


def test_two_evaluators_and_two_independent_verifiers_are_byte_checked() -> None:
    source = text()
    assert source.count("for replica in 1 2; do") == 2
    assert source.count(
        '"${clean_python[@]}" -m phase1.evaluate_critic_component_breadth_future_escrow'
    ) == 1
    assert source.count(
        '"${clean_python[@]}" -m phase1.verify_critic_component_breadth_future_evaluation'
    ) == 1
    assert 'diff -r "${result_dir}/evaluation_1" "${result_dir}/evaluation_2"' in source
    assert 'cmp "${result_dir}/verification_1.json" "${result_dir}/verification_2.json"' in source
    assert "outcome_evaluator_module_imported" in source


def test_preflight_has_exactly_twelve_items_and_runner_has_no_gpu_api_or_fit_launch() -> None:
    source = text()
    numbers = re.findall(r"^PREFLIGHT_(\d{2})_", source, flags=re.MULTILINE)
    assert numbers == [f"{number:02d}" for number in range(1, 13)]
    lowered = source.lower()
    for forbidden in (
        "sbatch ",
        "srun ",
        "qsub ",
        "curl ",
        "litellm",
        "openai",
        "-m phase1.critic_component_breadth_future_escrow",
        "-m phase1.score_channel_future_truth_support",
        "-m phase1.score_channel_future_raw_grade_support",
    ):
        assert forbidden not in lowered
    assert "gpu=0; api=0; new-model-fit=0; base-llm-update=0" in lowered
    assert "clean_python=(" in source
    assert "  env -i" in source
    assert "full_phase1_tests.stdout" in source
    assert "PREDICTION_SOURCE_PROVENANCE_VERIFIED" in source
    assert 'receipt.get("evaluator_source_sha256") != evaluator_sha' in source


def test_nonoverwrite_full_result_scan_and_complete_precede_final_sha() -> None:
    source = text()
    assert "-e ${result_dir} || -L ${result_dir}" in source
    assert 'mkdir "${result_dir}"' in source
    assert 'root.rglob("*")' in source
    assert "all_existing_result_files_scanned" in source
    assert "credential_scan_receipt.json" in source
    complete = source.index(
        "FORMAL_FUTURE_COMPONENT_BREADTH_EVALUATION_COMPLETE"
    )
    final_sha = source.rindex("> SHA256SUMS")
    assert complete < final_sha
    assert "find . -type f ! -name SHA256SUMS" in source[complete:]
    assert "sha256sum -c --strict SHA256SUMS" in source[complete:]
    assert 'chmod -R a-w "${result_dir}"' in source[final_sha:]


def test_unpublished_runner_exits_69_without_environment_or_inputs() -> None:
    if os.name != "posix":
        pytest.skip("inert shell execution is checked on the Linux experiment host")
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash unavailable")
    completed = subprocess.run(
        [bash, str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 69
    assert "not published" in completed.stderr
    with_argument = subprocess.run(
        [bash, str(SCRIPT), "unexpected"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert with_argument.returncode == 64


def test_shell_syntax() -> None:
    if os.name != "posix":
        pytest.skip("POSIX shell syntax is verified on the Linux experiment host")
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash unavailable")
    completed = subprocess.run(
        [bash, "-n", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
