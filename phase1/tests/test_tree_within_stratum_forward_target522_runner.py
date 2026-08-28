from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "phase1"
    / "scripts"
    / "run_tree_within_stratum_forward_target522_formal_20260828.sh"
)
MONITOR = (
    ROOT
    / "phase1"
    / "scripts"
    / "monitor_tree_within_stratum_forward_target522_formal_20260828.sh"
)
SELECTION = (
    "/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/"
    "latch-42f1044-after-887-v2"
)


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_formal_runner_has_complete_preflight_and_exact_source_bindings() -> None:
    text = source(RUNNER)
    assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", text)) == 13
    assert "if [[ $# -ne 8 ]]" in text
    assert SELECTION in text
    for name in (
        "protocol_sha",
        "producer_sha",
        "verifier_sha",
        "test_sha",
        "runner_sha",
        "selection_manifest_sha",
    ):
        assert name in text
    assert 'cmp "$0" "$worktree/$runner_rel"' in text
    assert 'merge-base --is-ancestor "$expected_commit" fork/phase1-value-critic' in text


def test_formal_runner_requires_two_byte_identical_producers_and_verifiers() -> None:
    text = source(RUNNER)
    assert "producer_a.json" in text and "producer_b.json" in text
    assert "verifier_a.json" in text and "verifier_b.json" in text
    assert 'cmp "$output/producer_a.json" "$output/producer_b.json"' in text
    assert 'cmp "$output/verifier_a.json" "$output/verifier_b.json"' in text
    assert "--expect-receipt-sha256" in text
    assert "--expect-producer-source-sha256" in text


def test_formal_runner_uses_the_scoped_suite_and_security_traces() -> None:
    text = source(RUNNER)
    assert '"$python_bin" -m pytest -q phase1/tests' in text
    assert '"$python_bin" -m pytest -q\n' not in text
    assert "strace -ff -tt -yy -e trace=file,network" in text
    assert "producer_forbidden_path_hits=0" in text
    assert "verifier_network_hits=0" in text
    assert "prospective_label_grade_outcome_prediction_values_read=false" in text
    assert "gpu_api_model_fit_base_update=0/0/0/0" in text
    assert "sbatch" not in text
    assert "nvidia-smi" not in text


def test_formal_runner_is_append_only_and_marks_complete_last() -> None:
    text = source(RUNNER)
    assert 'test ! -e "$output"' in text
    assert 'test ! -e "$worktree"' in text
    assert 'printf \'%s\\n\' "$rc" >"$output/FAILED_RC"' in text
    manifest = text.index("xargs -0 sha256sum >SHA256SUMS")
    complete = text.index("touch COMPLETE", manifest)
    readonly = text.index('chmod -R a-w "$output"', complete)
    assert manifest < complete < readonly


def test_watcher_reads_no_candidate_content_before_complete() -> None:
    text = source(MONITOR)
    assert "if [[ $# -ne 9 ]]" in text
    assert SELECTION in text
    activation = text.index('if test -f "$selection/COMPLETE"')
    first_selection_hash = text.index('sha256sum "$selection/SHA256SUMS"')
    assert activation < first_selection_hash
    prefix = text[:activation]
    assert "$selection/READY" not in prefix
    assert "$selection/candidate.tsv" not in prefix
    assert "$selection/observed.tsv" not in prefix


def test_watcher_is_resumable_and_executes_only_the_hash_bound_runner() -> None:
    text = source(MONITOR)
    assert "[[ $mode == start || $mode == resume ]]" in text
    assert "INTERRUPTED_RC" in text
    assert 'rm -f "$root/INTERRUPTED_RC" "$root/TIMEOUT_RC"' in text
    assert 'git -C "$repo" show "${source_commit}:${runner_rel}" >"$root/formal_runner.sh"' in text
    assert 'test "$(sha256sum "$root/formal_runner.sh"' in text
    assert 'bash "$root/formal_runner.sh"' in text
    assert 'test -f "$formal_output/COMPLETE"' in text
    assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", text)) == 13


def test_watcher_is_cpu_only_and_has_no_legacy_direction_hooks() -> None:
    text = source(MONITOR)
    assert "gpu_api_model_fit_base_update=0/0/0/0" in text
    assert "sbatch" not in text
    assert "nvidia-smi" not in text
    for retired in ("hce", "multifidelity", "probe-first", "lookahead"):
        assert retired not in text.lower()
