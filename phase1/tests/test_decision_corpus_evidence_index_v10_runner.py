from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_decision_corpus_evidence_index_v10_formal_20260902.sh"
PROTOCOL = ROOT / "phase1/decision_corpus_evidence_index_v10_protocol_v1.json"


def source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_runner_binds_exact_protocol_and_fresh_commit_worktree() -> None:
    text = source()
    protocol_sha = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    assert f"readonly protocol_sha={protocol_sha}" in text
    assert "[[ $source_commit =~ ^[0-9a-f]{40}$ ]]" in text
    assert "test ! -e \"$formal_root\"" in text
    assert "test ! -e \"$worktree_root\"" in text
    assert "GIT_LFS_SKIP_SMUDGE=1" in text
    assert "worktree add --detach" in text
    assert "rm -" not in text


def test_runner_has_exact_thirteen_item_preflight() -> None:
    lines = re.findall(r"^([0-9]{2})_[^\n]+; PASS$", source(), flags=re.MULTILINE)
    assert lines == [f"{value:02d}" for value in range(1, 14)]
    assert 'test "$(wc -l <"$formal_root/preflight_13.txt")" = 13' in source()


def test_runner_binds_all_thirteen_public_inputs_before_and_after() -> None:
    text = source()
    block = re.search(r"readonly -a input_relatives=\(\n(?P<body>.*?)\n\)", text, flags=re.DOTALL)
    assert block is not None
    members = [line.strip() for line in block.group("body").splitlines() if line.strip()]
    assert len(members) == 13
    assert "write_input_hashes \"$formal_root/input_hashes_before.txt\"" in text
    assert "write_input_hashes \"$formal_root/input_hashes_after.txt\"" in text
    assert 'cmp "$formal_root/input_hashes_before.txt" "$formal_root/input_hashes_after.txt"' in text


def test_runner_executes_focused_full_and_deterministic_ab_checks() -> None:
    text = source()
    assert "phase1/tests/test_decision_corpus_evidence_index*.py" in text
    assert '"$python_bin" -m pytest -q phase1/tests' in text
    assert "build_decision_corpus_evidence_index_v10.py" in text
    assert "verify_decision_corpus_evidence_index_v10.py" in text
    assert 'cmp "$formal_root/index_a.json" "$formal_root/index_b.json"' in text
    assert 'cmp "$formal_root/verifier_a.json" "$formal_root/verifier_b.json"' in text


def test_runner_traces_forbidden_reads_and_network() -> None:
    text = source()
    assert "strace -f -qq -e trace=openat" in text
    assert "strace -f -qq -e trace=network" in text
    for forbidden in (
        "/prospective_decision_v1/",
        "/external/senior_data/",
        "decision_clean_b[0-9]",
        "cards_cur\\.jsonl",
    ):
        assert forbidden in text
    assert 'test ! -s "$formal_root/forbidden_open_hits.txt"' in text
    assert 'test ! -s "$formal_root/network_trace.txt"' in text


def test_runner_enforces_security_and_zero_compute_expansion() -> None:
    text = source()
    assert "umask 077" in text
    assert "gpu_api_model_fit_base_update=0/0/0/0" in text
    assert "prospective_label_grade_outcome_prediction_values_read=false" in text
    assert "raw_senior_archives_opened=false" in text
    assert "artifact_filename_scan.txt" in text
    assert "artifact_content_scan.txt" in text
    assert "chmod -R a-w \"$formal_root\"" in text


def test_runner_summary_cannot_count_reconstruction_as_distinct() -> None:
    text = source()
    assert '"duplicate_claims_counted_as_distinct": $duplicates_counted' in text
    assert '"shared_numeric_fields_crosschecked": $shared_fields' in text
    assert '"source_v9_entries_preserved_without_modification": 16' in text
    assert '"index_status": "PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960"' in text


def test_independent_verifier_does_not_import_builder() -> None:
    verifier = (
        ROOT / "phase1/verify_decision_corpus_evidence_index_v10.py"
    ).read_text(encoding="utf-8")
    assert "build_decision_corpus_evidence_index_v10" not in verifier
    assert "from phase1 import build" not in verifier
