from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "phase1"
    / "scripts"
    / "run_vertex_cost_contrast_target522_selection_formal_20260830.sh"
)
MONITOR = (
    ROOT
    / "phase1"
    / "scripts"
    / "monitor_vertex_cost_contrast_target522_selection_formal_20260830.sh"
)
CONTRACT = ROOT / "phase1" / "vertex_cost_contrast_target522_execution_v1.json"
SELECTION = (
    "/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/"
    "latch-42f1044-after-887-v2"
)


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_execution_contract_binds_every_runtime_source() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["protocol"] == "vertex-cost-contrast-target522-stage-a-execution-v1"
    assert contract["status"] == "FROZEN_BEFORE_TARGET522_CANDIDATE"
    assert contract["activation"]["first960_closure_required_for_stage_a"] is False
    assert contract["activation"]["first960_closure_required_for_any_fit"] is True
    bindings = contract["bindings"]
    for binding in bindings.values():
        path = ROOT / binding["path"]
        assert path.is_file()
        assert sha(path) == binding["sha256"]
    scientific = contract["scientific_protocol"]
    assert sha(ROOT / scientific["path"]) == scientific["sha256"]


def test_formal_runner_has_exact_sources_and_full_preflight() -> None:
    text = source(RUNNER)
    assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", text)) == 13
    assert "if [[ $# -ne 10 ]]" in text
    assert SELECTION in text
    for name in (
        "execution_sha",
        "protocol_sha",
        "producer_sha",
        "verifier_sha",
        "test_sha",
        "runner_sha",
        "monitor_sha",
        "selection_manifest_sha",
    ):
        assert name in text
    assert 'cmp "$0" "$worktree/$runner_rel"' in text
    assert 'merge-base --is-ancestor "$expected_commit" fork/phase1-value-critic' in text


def test_formal_runner_requires_byte_exact_producer_private_and_verifier_replays() -> None:
    text = source(RUNNER)
    assert "producer_a.json" in text and "producer_b.json" in text
    assert "private_a.json" in text and "private_b.json" in text
    assert "verifier_a.json" in text and "verifier_b.json" in text
    assert 'cmp "$output/producer_a.json" "$output/producer_b.json"' in text
    assert 'cmp "$output/private_a.json" "$output/private_b.json"' in text
    assert 'cmp "$output/verifier_a.json" "$output/verifier_b.json"' in text
    assert "verify_vertex_cost_contrast_target522_selection" in text
    assert "--private-selection" in text
    assert "stat -c '%a'" in text


def test_formal_runner_is_outcome_blind_cpu_only_and_trace_audited() -> None:
    text = source(RUNNER)
    assert 'timeout 1800s "$python_bin" -m pytest -q phase1/tests' in text
    assert "strace -ff -tt -yy -e trace=file,network" in text
    assert "producer_forbidden_path_hits=0" in text
    assert "verifier_network_hits=0" in text
    assert "first960_closure_opened=false" in text
    assert "gpu_paid_api_model_fit_base_update=0/0/0/0" in text
    assert "freeze_vertex_cost_contrast_target522_selection" in text
    assert "LogisticRegression" not in text
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


def test_monitor_proves_pre_candidate_start_and_reads_no_candidate_before_complete() -> None:
    text = source(MONITOR)
    assert "if [[ $# -ne 10 ]]" in text
    assert SELECTION in text
    assert 'test ! -e "$selection/candidate.tsv"' in text
    assert 'test ! -e "$selection/READY"' in text
    assert 'test ! -e "$selection/COMPLETE"' in text
    activation = text.index('if test -f "$selection/COMPLETE"')
    first_selection_hash = text.index('sha256sum "$selection/SHA256SUMS"')
    assert activation < first_selection_hash
    prefix = text[:activation]
    assert 'cat "$selection/' not in prefix
    assert 'jq ' not in prefix


def test_monitor_is_bounded_resumable_hash_bound_and_fit_gated() -> None:
    text = source(MONITOR)
    assert "[[ $mode == start || $mode == resume ]]" in text
    assert "for poll in $(seq 0 720)" in text
    assert "INTERRUPTED_RC" in text
    assert 'rm -f "$root/INTERRUPTED_RC" "$root/TIMEOUT_RC"' in text
    assert 'git -C "$repo" show "${source_commit}:${runner_rel}" >"$root/formal_runner.sh"' in text
    assert 'bash "$root/formal_runner.sh"' in text
    assert 'test -f "$formal_output/COMPLETE"' in text
    assert "first960_closure_opened=false" in text
    assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", text)) == 13


def test_execution_chain_has_no_retired_direction_or_accelerator_hook() -> None:
    text = source(RUNNER) + source(MONITOR)
    for retired in ("multifidelity", "probe-first", "lookahead"):
        assert retired not in text.lower()
    assert "gpu_paid_api_model_fit_base_update=0/0/0/0" in text
    assert "sbatch" not in text
    assert "nvidia-smi" not in text
