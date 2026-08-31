from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = (
    ROOT
    / "results"
    / "archive_disposition_longitudinal_replication_v2_20260831_43ce72a"
)
REMOTE_PREFIX = (
    "/research/d7/spc/yzyang4/prospective-archive-disposition/"
    "formal-43ce72a-taxonomy-v2-v1/public/"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_formal_archive_disposition_result_and_manifest() -> None:
    summary = json.loads((RESULT_ROOT / "formal_summary.json").read_text())
    result_a = RESULT_ROOT / "a" / "result.json"
    result_b = RESULT_ROOT / "b" / "result.json"
    verify_a = RESULT_ROOT / "a" / "independent_verification.json"
    verify_b = RESULT_ROOT / "b" / "independent_verification.json"
    result = json.loads(result_a.read_text())
    verification = json.loads(verify_a.read_text())

    assert result_a.read_bytes() == result_b.read_bytes()
    assert verify_a.read_bytes() == verify_b.read_bytes()
    assert summary["status"] == "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED"
    assert result["status"] == summary["status"]
    assert result["protocol"] == "archive_disposition_longitudinal_replication_v2"
    assert summary["result_sha256"] == _sha(result_a)
    assert summary["verification_sha256"] == _sha(verify_a)
    assert verification["status"] == (
        "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS"
    )
    assert verification["all_aggregate_fields_equal"] is True

    current = result["current"]
    assert current["structural_rejected_competitions"] == 6
    assert current["structural_mixed_disposition_competitions"] == 6
    assert current["structural_mixed_disposition_fraction"]["value"] == 1.0
    assert current["structural_rejected_archives"] == 13
    assert current["alias_quarantined_archives"] == 8
    assert current["payload_hash_partition_audit"] == {
        "accepted_unique_payload_hashes": 126,
        "alias_payload_hashes_overlapping_accepted": 8,
        "alias_unique_payload_hashes": 8,
        "distinct_alias_registry_hashes": 1,
        "distinct_postbaseline_payload_hashes": 139,
        "structural_payload_hashes_overlapping_accepted": 0,
        "structural_unique_payload_hashes": 13,
    }
    assert result["extension_beyond_historical_anchor"][
        "overall_settled_archives"
    ] == 57
    assert result["extension_beyond_historical_anchor"][
        "structural_target_settled_archives"
    ] == 49
    assert result["decision"]["strong_gate_passed"] is True
    assert result["access_attestation"][
        "labels_grades_outcomes_predictions_accuracy_or_utility_read"
    ] is False

    serialized = json.dumps(result, sort_keys=True)
    assert "/research/" not in serialized
    assert re.search(r"[0-9]{4}/[^\" ]+\.tar\.gz", serialized) is None

    manifest = RESULT_ROOT / "SHA256SUMS"
    assert _sha(manifest) == (RESULT_ROOT / "MANIFEST_SHA256").read_text().strip()
    rows = 0
    for line in manifest.read_text().splitlines():
        expected, remote_path = line.split("  ", 1)
        assert remote_path.startswith(REMOTE_PREFIX)
        local_path = RESULT_ROOT / remote_path.removeprefix(REMOTE_PREFIX)
        assert _sha(local_path) == expected
        rows += 1
    assert rows == 22


def test_v1_is_preserved_as_integrity_failure() -> None:
    failure = json.loads(
        (
            ROOT
            / "results"
            / "archive_disposition_longitudinal_replication_v1_20260831_5fb6a34"
            / "integrity_failure.json"
        ).read_text()
    )
    assert failure["status"] == "ARCHIVE_DISPOSITION_REPLICATION_INTEGRITY_FAIL"
    assert failure["result_emitted"] is False
    assert failure["accepted_rejected_competition_intersection_computed"] is False
    assert failure["labels_grades_outcomes_predictions_accuracy_or_utility_read"] is False
