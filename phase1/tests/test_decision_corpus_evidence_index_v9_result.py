from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from phase1 import build_decision_corpus_evidence_index_v9 as builder
from phase1 import verify_decision_corpus_evidence_index_v9 as verifier


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "phase1" / "results" / "decision_corpus_evidence_index_v9_20260829_f108812"
FORMAL = PACKAGE / "formal"
PROTOCOL = ROOT / "phase1" / "decision_corpus_evidence_index_v9_protocol_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def manifest(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        assert match is not None
        name = match.group(2).removeprefix("./")
        assert name not in rows
        rows[name] = match.group(1)
    return rows


def test_compact_package_manifest_is_complete() -> None:
    path = PACKAGE / "MANIFEST.sha256"
    expected = manifest(path)
    actual = {
        member.relative_to(PACKAGE).as_posix()
        for member in PACKAGE.rglob("*")
        if member.is_file() and member.name != "MANIFEST.sha256"
    }
    assert len(expected) == 24
    assert set(expected) == actual
    for name, expected_sha in expected.items():
        assert digest(PACKAGE / name) == expected_sha
    assert digest(path) == "1c2c6e09a59211e8dadd404c8c859f2aa4e6f5ed977383e08a8fd38089a08642"


def test_published_index_rebuilds_and_independent_verifier_matches() -> None:
    published = load(FORMAL / "index.json")
    rebuilt = builder.build_index(ROOT, PROTOCOL)
    assert published == rebuilt
    published_verification = load(FORMAL / "independent_verification.json")
    rebuilt_verification = verifier.verify_candidate(ROOT, PROTOCOL, FORMAL / "index.json")
    assert published_verification == rebuilt_verification


def test_formal_and_postflight_bindings_are_exact() -> None:
    bindings = load(PACKAGE / "source_bindings.json")
    summary = load(FORMAL / "formal_summary.json")
    assert bindings["formal_source_commit"] == summary["source_commit"] == (
        "f10881237447501a1b3b51213a267865bd854d17"
    )
    assert digest(PROTOCOL) == bindings["protocol_sha256"]
    assert digest(FORMAL / "index.json") == bindings["formal"]["index_sha256"]
    assert digest(FORMAL / "independent_verification.json") == bindings["formal"][
        "independent_verification_sha256"
    ]
    assert digest(FORMAL / "formal_summary.json") == bindings["formal"]["formal_summary_sha256"]
    assert digest(FORMAL / "remote_SHA256SUMS.txt") == bindings["formal"]["manifest_sha256"]
    assert digest(PACKAGE / "postflight" / "remote_SHA256SUMS.txt") == bindings["postflight"][
        "manifest_sha256"
    ]


def test_limited_support_and_security_boundaries_are_published() -> None:
    summary = load(FORMAL / "formal_summary.json")
    index = load(FORMAL / "index.json")
    verification = load(FORMAL / "independent_verification.json")
    assert summary["index_status"] == index["status"] == (
        "PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960"
    )
    assert index["source_v8_index"]["entries_replaced"] == 1
    assert index["source_v8_index"]["entries_preserved_without_modification"] == 15
    assert index["lineage_repair"]["all_support_gates_passed"] is False
    assert index["lineage_repair"]["failed_support_gate"] == (
        "frozen:b2.maximum_single_run_pair_share"
    )
    assert verification["all_aggregate_fields_equal"] is True
    assert verification["imports_builder"] is False
    assert summary["credential_content_scanner_rc"] == 1
    assert summary["forbidden_open_hits"] == 0
    assert summary["network_calls"] == 0
    assert summary["prospective_values_read"] is False
    assert summary["raw_senior_archives_opened"] is False
    assert summary["row_level_release_created"] is False
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]


def test_failure_history_is_not_silently_dropped() -> None:
    assert (PACKAGE / "failure_history" / "r1" / "FAILED_RC").read_text().strip() == "128"
    assert "'myfork' does not appear" in (
        PACKAGE / "failure_history" / "r1" / "fetch.stderr"
    ).read_text(encoding="utf-8")
    assert (PACKAGE / "failure_history" / "r2" / "FAILED_RC").read_text().strip() == "143"
    assert "FORMAL_INTERRUPTED_BY_RESOURCE_GUARD" in (
        PACKAGE / "failure_history" / "r2" / "INTERRUPTED_RESOURCE_GUARD"
    ).read_text(encoding="utf-8")
    assert "FORMAL_SECURITY_GATE_INVALIDATED" in (
        PACKAGE / "failure_history" / "r3" / "INVALIDATED"
    ).read_text(encoding="utf-8")
