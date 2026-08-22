from __future__ import annotations

import hashlib
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
    )
    for prefix in prefixes:
        relative = values[f"{prefix}_REL"]
        expected = values[f"{prefix}_SHA"]
        assert re.fullmatch(r"[0-9a-f]{64}", expected)
        assert sha256(ROOT / relative) == expected


def test_extra_registry_arguments_remain_paired() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("--extra-structural-rejection-registry ") == 6
    assert text.count("--expect-extra-structural-rejection-registry-sha256 ") == 6


def test_0821_registry_is_verified_passed_and_receipted() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("${EXTRA_0821_REGISTRY_SHA}") == 3
    assert text.count("${extra_0821_registry}") == 2
