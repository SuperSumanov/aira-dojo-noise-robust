from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from phase1 import score_channel_future_raw_grade_support as producer
from phase1 import verify_score_channel_future_raw_grade_support as verifier
from phase1 import verify_score_channel_future_truth_support as base_verifier
from phase1.tests import test_score_channel_future_truth_support as fixture


REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "phase1" / "score_channel_future_raw_grade_support_protocol_v1.json"
BASE_PROTOCOL = REPO / "phase1" / "score_channel_future_identifiability_protocol_v1.json"


def test_extension_protocol_is_byte_frozen() -> None:
    assert fixture.digest(PROTOCOL) == producer.FROZEN_PROTOCOL_SHA256
    assert producer.FROZEN_PROTOCOL_SHA256 == verifier.FROZEN_PROTOCOL_SHA256


def extension_args(
    tmp_path: Path,
    state: Path,
    cohort: Path,
    cohort_sha: str,
    base_truth: Path,
    base_receipt: Path,
) -> SimpleNamespace:
    helper = tmp_path / "grade_helpers.py"
    helper.write_text("unused synthetic helper\n", encoding="utf-8")
    return SimpleNamespace(
        protocol=PROTOCOL,
        expect_protocol_sha256=producer.FROZEN_PROTOCOL_SHA256,
        base_protocol=BASE_PROTOCOL,
        expect_base_protocol_sha256=producer.BASE_PROTOCOL_SHA256,
        cohort_dir=cohort,
        expect_cohort_summary_sha256=cohort_sha,
        state_root=state,
        base_truth_dir=base_truth,
        expect_base_truth_summary_sha256=fixture.digest(base_truth / "summary.json"),
        expect_base_selected_sha256=fixture.digest(base_truth / "selected_parents.jsonl"),
        base_verification=base_receipt,
        expect_base_verification_sha256=fixture.digest(base_receipt),
        mlebench_repo=tmp_path,
        grade_helpers=helper,
        repo=REPO,
        out_dir=tmp_path / "raw-extension",
        extension_dir=tmp_path / "raw-extension",
        receipt=tmp_path / "raw-extension-verification.json",
    )


def build_base(
    tmp_path: Path,
    *,
    tie_run: int | None = None,
) -> tuple[Path, Path, str, Path, Path]:
    state, cohort, cohort_sha = fixture.build_fixture(tmp_path, tie_run=tie_run)
    base_truth, _ = fixture.run_producer(tmp_path, state, cohort, cohort_sha, "base-truth")
    base_receipt = tmp_path / "base-verification.json"
    base_verifier.verify(
        BASE_PROTOCOL,
        fixture.PROTOCOL_SHA,
        cohort,
        cohort_sha,
        state,
        base_truth,
        base_receipt,
    )
    return state, cohort, cohort_sha, base_truth, base_receipt


def patch_grader(monkeypatch: pytest.MonkeyPatch) -> None:
    result = (
        "507f92e1138bb6e40dac5c6ee7a6758e6424bf97",
        "7d55512a893699b2e17041f3cd3bd0c2aba955c73f50872b3c69238546b87005",
    )
    monkeypatch.setattr(producer, "verify_grader", lambda *_: result)
    monkeypatch.setattr(verifier, "verify_grader", lambda *_: result)


def test_raw_extension_passes_without_overwriting_base_y_norm_kill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, cohort, cohort_sha, base_truth, base_receipt = build_base(tmp_path, tie_run=0)
    args = extension_args(tmp_path, state, cohort, cohort_sha, base_truth, base_receipt)
    patch_grader(monkeypatch)
    summary = producer.produce(args)
    assert summary["base_y_norm_gate"]["status"] == "TRUTH_SUPPORT_KILL_NO_REPLAY_REQUEST"
    assert summary["base_y_norm_gate"]["status_overwritten_or_reversed"] is False
    assert summary["raw_grade_support"]["counts"]["raw_nontied_parents"] == 80
    assert summary["raw_grade_support"]["counts"]["tasks_with_raw_nontied_parent"] == 8
    assert summary["raw_grade_support"]["gates"]["all_pass"] is True
    assert summary["decision"]["raw_grade_separate_design_request_eligible"] is True
    assert summary["decision"]["replay_submission_authorized"] is False
    receipt = verifier.verify(args)
    assert receipt["status"] == "VERIFIED_RAW_GRADE_SUPPORT_ELIGIBLE_SEPARATE_DESIGN_REQUEST_ONLY"
    assert receipt["base_y_norm_status_unchanged"] is True
    assert receipt["extension_producer_module_imported"] is False
    assert receipt["base_producer_module_imported"] is False


def test_extension_is_byte_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, cohort, cohort_sha, base_truth, base_receipt = build_base(tmp_path)
    first = extension_args(tmp_path, state, cohort, cohort_sha, base_truth, base_receipt)
    patch_grader(monkeypatch)
    producer.produce(first)
    first_bytes = (first.out_dir / "summary.json").read_bytes()
    second = extension_args(tmp_path, state, cohort, cohort_sha, base_truth, base_receipt)
    second.out_dir = tmp_path / "raw-extension-second"
    second.extension_dir = second.out_dir
    producer.produce(second)
    assert first_bytes == (second.out_dir / "summary.json").read_bytes()


def test_off_grid_grade_fails_both_implementations() -> None:
    selected = [{"task": "task", "run_id": "run", "candidate_card_ids": ["a", "b"]}]
    vault = {
        "a": {"graded": 0.123456, "y_norm": 0.0},
        "b": {"graded": 0.2, "y_norm": 0.1},
    }
    frozen = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    with pytest.raises(producer.RawSupportError, match="five-decimal grid"):
        producer.aggregate_raw(selected, vault, frozen)
    with pytest.raises(verifier.RawSupportVerificationError, match="five-decimal grid"):
        verifier.raw_aggregate(selected, vault)


def test_candidate_reuse_fails_both_implementations() -> None:
    selected = [
        {"task": "task", "run_id": "run-1", "candidate_card_ids": ["a", "b"]},
        {"task": "task", "run_id": "run-2", "candidate_card_ids": ["b", "c"]},
    ]
    vault = {
        "a": {"graded": 0.1, "y_norm": 0.0},
        "b": {"graded": 0.2, "y_norm": 0.0},
        "c": {"graded": 0.3, "y_norm": 0.0},
    }
    frozen = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    with pytest.raises(producer.RawSupportError, match="reused selected candidate"):
        producer.aggregate_raw(selected, vault, frozen)
    with pytest.raises(verifier.RawSupportVerificationError, match="candidate reuse"):
        verifier.raw_aggregate(selected, vault)


def test_independent_verifier_rejects_tampered_raw_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, cohort, cohort_sha, base_truth, base_receipt = build_base(tmp_path)
    args = extension_args(tmp_path, state, cohort, cohort_sha, base_truth, base_receipt)
    patch_grader(monkeypatch)
    producer.produce(args)
    summary_path = args.extension_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["raw_grade_support"]["counts"]["raw_nontied_parents"] -= 1
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(verifier.RawSupportVerificationError, match="summary reconstruction mismatch"):
        verifier.verify(args)


def test_verifier_does_not_import_either_producer() -> None:
    source = (REPO / "phase1" / "verify_score_channel_future_raw_grade_support.py").read_text(encoding="utf-8")
    assert "import score_channel_future_raw_grade_support" not in source
    assert "import score_channel_future_truth_support" not in source
