from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_structural_gate_utility_certificate_formal_20260902.sh"


def text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_runner_binds_protocol_and_nine_inputs() -> None:
    source = text()
    assert "bb4091ff0585c288d0fb99614125e82148338d6871872ae023a1c41913c60308" in source
    block = source.split("readonly -a input_relatives=(", 1)[1].split("\n)", 1)[0]
    assert len([line for line in block.splitlines() if line.strip()]) == 9
    assert 'test "$(wc -l <"${formal_root}/input_hashes_before.txt")" = "${#input_relatives[@]}"' in source


def test_runner_has_full_preflight_reproducibility_and_security_chain() -> None:
    source = text()
    assert "preflight_13.txt" in source
    assert "focused_tests.txt" in source
    assert "full_tests.txt" in source
    assert source.count("for suffix in a b") == 2
    assert "trace=openat" in source
    assert "trace=network" in source
    assert "forbidden_open_hits.txt" in source
    assert "artifact_filename_scan.txt" in source
    assert "artifact_content_scan.txt" in source
    assert "input_hashes_before.txt" in source
    assert "input_hashes_after.txt" in source
    assert "SHA256SUMS" in source
    assert "COMPLETE" in source
    assert "FAILED_RC" in source


def test_runner_keeps_resources_and_claim_boundary_fixed() -> None:
    source = text()
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "BLIS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        assert f"export {name}=1" in source
    assert "counts_as_distinct_claim_evidence=false" in source
    assert "gpu_api_model_fit_base_update=0/0/0/0" in source
    assert "prospective_label_grade_outcome_prediction_values_read=false" in source
    assert "raw_senior_archives_opened=false" in source
    assert "row_level_release_created=false" in source


def test_runner_uses_fresh_exact_clean_worktree_and_no_network_fetch() -> None:
    source = text()
    assert "worktree add --detach" in source
    assert "GIT_LFS_SKIP_SMUDGE=1" in source
    assert 'rev-parse HEAD)" = "${source_commit}"' in source
    assert "status --porcelain --untracked-files=all" in source
    assert " git -C \"${source_repo}\" fetch " not in source
