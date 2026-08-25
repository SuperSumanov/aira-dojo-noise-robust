from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "phase1" / "scripts" / "run_prospective_continuous_intake_monitor_20260821.sh"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def assignments() -> dict[str, str]:
    return dict(
        re.findall(
            r"^([A-Z][A-Z0-9_]*)=([^\r\n]+)$",
            SCRIPT.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
    )


def test_all_repo_backed_rejection_registry_hashes_are_exact() -> None:
    values = assignments()
    prefixes = (
        "REGISTRY",
        "ADDITIONAL_REGISTRY",
        "EXTRA_0816_REGISTRY",
        "EXTRA_0817_REGISTRY",
        "EXTRA_0818_REGISTRY",
        "EXTRA_0820_REGISTRY",
        "EXTRA_0821_REGISTRY",
        "EXTRA_0822_REGISTRY",
        "EXTRA_0822_AI4CODE_REGISTRY",
        "EXTRA_0823_AI4CODE_REGISTRY",
        "EXTRA_0823_LMSYS_REGISTRY",
    )
    for prefix in prefixes:
        relative = values[f"{prefix}_REL"]
        expected = values[f"{prefix}_SHA"]
        assert re.fullmatch(r"[0-9a-f]{64}", expected)
        assert sha256(ROOT / relative) == expected


def test_extra_registry_arguments_remain_paired() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("--extra-structural-rejection-registry ") == 10
    assert text.count("--expect-extra-structural-rejection-registry-sha256 ") == 10


def test_0821_registry_is_verified_passed_and_receipted() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("${EXTRA_0821_REGISTRY_SHA}") == 3
    assert text.count("${extra_0821_registry}") == 2


def test_0822_registry_is_verified_passed_and_receipted() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("${EXTRA_0822_REGISTRY_SHA}") == 3
    assert text.count("${extra_0822_registry}") == 2


def test_0822_ai4code_registry_is_verified_passed_and_receipted() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("${EXTRA_0822_AI4CODE_REGISTRY_SHA}") == 3
    assert text.count("${extra_0822_ai4code_registry}") == 2


def test_0823_ai4code_registry_is_verified_passed_and_receipted() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("${EXTRA_0823_AI4CODE_REGISTRY_SHA}") == 3
    assert text.count("${extra_0823_ai4code_registry}") == 2

    values = assignments()
    registry_path = ROOT / values["EXTRA_0823_AI4CODE_REGISTRY_REL"]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["outcomes_read"] is False
    assert len(registry["entries"]) == 1
    entry = registry["entries"][0]
    assert entry["archive_relative_path"] == "0823/AI4Code-8seeds.tar.gz"
    assert entry["reason_code"] == "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE"

    receipt_path = registry_path.parent / entry["diagnostic_receipt_file"]
    assert sha256(receipt_path) == entry["diagnostic_receipt_sha256"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["outcomes_read"] is False
    assert receipt["journals"] == 4
    assert receipt["invalid_journals"] == 1
    assert receipt["task_identity_cardinality_counts"] == {
        "multiple": 0,
        "one": 3,
        "zero": 1,
    }


def test_0823_lmsys_registry_is_verified_passed_and_receipted() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("${EXTRA_0823_LMSYS_REGISTRY_SHA}") == 3
    assert text.count("${extra_0823_lmsys_registry}") == 2

    values = assignments()
    registry_path = ROOT / values["EXTRA_0823_LMSYS_REGISTRY_REL"]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["outcomes_read"] is False
    assert len(registry["entries"]) == 1
    entry = registry["entries"][0]
    assert entry["archive_relative_path"] == "0823/lmsys-chatbot-arena-8seeds.tar.gz"
    assert entry["reason_code"] == "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE"

    receipt_path = registry_path.parent / entry["diagnostic_receipt_file"]
    assert sha256(receipt_path) == entry["diagnostic_receipt_sha256"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["outcomes_read"] is False
    assert receipt["journals"] == 4
    assert receipt["invalid_journals"] == 4
    assert receipt["task_identity_cardinality_counts"] == {
        "multiple": 0,
        "one": 0,
        "zero": 4,
    }
