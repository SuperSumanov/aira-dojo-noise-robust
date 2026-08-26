from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from phase1 import agentic_benchmark_checklist_crosswalk_v2_schema as schema
from phase1 import build_agentic_benchmark_checklist_crosswalk_v2 as builder
from phase1 import verify_agentic_benchmark_checklist_crosswalk_v2 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    REPO_ROOT
    / "phase1/results/agentic_benchmark_checklist_crosswalk_v2_20260826_c97371d"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        assert match is not None
        rows[match.group(2).removeprefix("./")] = match.group(1)
    return rows


def test_published_package_manifest_covers_every_payload() -> None:
    expected = manifest(RESULT / "SHA256SUMS")
    actual_files = {
        path.name for path in RESULT.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(expected) == actual_files
    assert len(expected) == 9
    for relative, expected_sha in expected.items():
        assert sha256(RESULT / relative) == expected_sha


def test_published_crosswalk_and_receipt_match_independent_migration() -> None:
    crosswalk = json.loads((RESULT / "crosswalk.json").read_text(encoding="utf-8"))
    assert crosswalk == builder.migrate(REPO_ROOT, REPO_ROOT / schema.SOURCE_PATH)
    receipt = json.loads(
        (RESULT / "independent_verification.json").read_text(encoding="utf-8")
    )
    assert receipt == verifier.verify_crosswalk(REPO_ROOT, RESULT / "crosswalk.json")


def test_formal_summary_binds_exact_payloads_and_conservative_counts() -> None:
    summary = json.loads((RESULT / "formal_summary.json").read_text(encoding="utf-8"))
    assert summary["source_commit"] == "c97371d7433b808933624b706a848a644991139c"
    assert summary["crosswalk_sha256"] == sha256(RESULT / "crosswalk.json")
    assert summary["independent_verification_sha256"] == sha256(
        RESULT / "independent_verification.json"
    )
    assert (summary["items"], summary["evidence_files"]) == (24, 29)
    assert (summary["removed_evidence_ids"], summary["added_clean_evidence_ids"]) == (
        6,
        11,
    )
    assert summary["status_counts"] == {
        "INHERITED_UPSTREAM": 5,
        "NOT_APPLICABLE": 1,
        "PARTIAL": 9,
        "PASS_LOCAL": 9,
    }
    assert summary["human_statuses_upgraded_during_migration"] is False
    assert summary["semantic_assessment_certified"] is False
    assert summary["aggregate_compliance_score_reported"] is False
    assert summary["source_v1_removed_evidence_or_forbidden_path_hits"] == 0


def test_remote_manifest_binds_all_copied_formal_files() -> None:
    remote = manifest(RESULT / "remote_formal_SHA256SUMS")
    mapping = {
        "crosswalk_a.json": "crosswalk.json",
        "verification_a.json": "independent_verification.json",
        "formal_summary.json": "formal_summary.json",
        "preflight_13.txt": "preflight_13.txt",
        "focused_tests.txt": "focused_tests.txt",
        "full_tests.txt": "full_tests.txt",
        "access_attestation.txt": "access_attestation.txt",
    }
    for remote_name, local_name in mapping.items():
        assert remote[remote_name] == sha256(RESULT / local_name)


def test_readme_does_not_turn_crosswalk_into_a_compliance_score() -> None:
    readme = (RESULT / "README.md").read_text(encoding="utf-8")
    assert "不计算 aggregate compliance score" in readme
    assert "不把 PARTIAL/INHERITED/NOT_APPLICABLE 转成 PASS" in readme
    assert "不是新的 predictor 效果" in readme
