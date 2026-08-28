from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from phase1 import build_historical_relation_integrity_contrast as producer
from phase1 import verify_historical_relation_integrity_contrast as independent


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "phase1/results/historical_relation_integrity_contrast_20260829_f66cbdf"
PROTOCOL = ROOT / "phase1/historical_relation_integrity_contrast_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_publication_manifest_is_complete_and_exact() -> None:
    manifest = PACKAGE / "MANIFEST.sha256"
    rows: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        assert match is not None
        digest, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        assert name not in rows
        assert sha256(PACKAGE / name) == digest
        rows[name] = digest
    actual = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file() and path.name != "MANIFEST.sha256"
    }
    assert set(rows) == actual
    assert len(rows) == 21
    assert sha256(manifest) == "36320ae5d8f43e26906a085e8c11bca1e4be5f8946b45acaec81fdf78efd5c1e"


def test_formal_summary_preserves_exact_readout_and_limitations() -> None:
    summary = read_json(PACKAGE / "formal/formal_summary.json")
    assert summary["source_commit"] == "f66cbdf10989da2e1242964259f31fb8d399db3e"
    assert summary["canonical_lineage_direct_rows"] == summary["canonical_rows"] == 8107
    assert summary["mixed_verified_direct_sibling_rows"] == 1270
    assert summary["mixed_rows"] == 7644
    assert summary["mixed_quarantine_rows"] == 6374
    assert (summary["referenced_run_overlap_before"], summary["referenced_run_overlap_after"]) == (96, 0)
    assert (
        summary["parent_partition_mismatch_cross_run_numerator"],
        summary["parent_partition_mismatch_cross_run_denominator"],
    ) == (743, 743)
    assert (summary["canonical_support_gates_passed"], summary["canonical_support_gates_total"]) == (35, 36)
    assert summary["canonical_failed_support_gate"] == "frozen:b2.maximum_single_run_pair_share"
    assert summary["gate_schemas_related_but_not_identical"] is True
    assert summary["descriptive_two_family_case_study_not_population_estimate"] is True


def test_published_contrast_rebuilds_and_independently_verifies() -> None:
    candidate_path = PACKAGE / "formal/contrast.json"
    candidate = read_json(candidate_path)
    rebuilt = producer.build_contrast(ROOT, PROTOCOL)
    assert candidate == rebuilt
    receipt = independent.verify_candidate(ROOT, PROTOCOL, candidate_path)
    published_verification = read_json(PACKAGE / "formal/independent_verification.json")
    assert receipt == published_verification
    assert sha256(candidate_path) == "96ce116570a6144b50c91bc39de99028614927c2c378d98dbd6a921eaed4a1b4"
    assert sha256(PACKAGE / "formal/independent_verification.json") == "1779e696251430347e2574915c2fd07c75e01004be925cd4beae088cc63c5ec2"


def test_postflight_binds_formal_manifest_and_public_source() -> None:
    bindings = read_json(PACKAGE / "source_bindings.json")
    postflight = (PACKAGE / "postflight/postflight.txt").read_text(encoding="utf-8")
    assert bindings["formal"]["manifest_sha256"] == "ab2b6fa69fa6705dbd442488067b63d0aea63eb6dc9c326a8bd0cef08087af54"
    assert bindings["postflight"]["manifest_sha256"] == "b50a9a2941b360d5ca40b1de8c3887512b4a9ef80ac1b1969e4864ab49f57b9e"
    assert "source_commit_public_on_fork_phase1_value_critic=true" in postflight
    assert "formal_manifest_all_members_ok=true" in postflight
    assert "formal_directory_files_read_only=true" in postflight


def test_scope_receipts_are_outcome_blind_and_aggregate_only() -> None:
    bindings = read_json(PACKAGE / "source_bindings.json")
    summary = read_json(PACKAGE / "formal/formal_summary.json")
    assert bindings["scope"]["aggregate_only"] is True
    assert bindings["scope"]["known_result_descriptive_synthesis"] is True
    assert bindings["scope"]["prospective_values_read"] is False
    assert bindings["scope"]["raw_senior_archives_opened"] is False
    assert bindings["scope"]["row_level_release_created"] is False
    assert bindings["scope"]["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    assert summary["forbidden_open_hits"] == 0
    assert summary["network_calls"] == 0
    assert summary["credential_filename_hits"] == 0
    assert summary["credential_content_hits"] == 0
