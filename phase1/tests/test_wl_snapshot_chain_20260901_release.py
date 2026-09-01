from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1" / "results" / "wl_snapshot_chain_20260901_e9e12c63"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_copied_source_files_match_remote_manifest() -> None:
    source_manifest = {}
    for line in (RESULT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        source_manifest[relative.removeprefix("./")] = expected

    copied_from_manifest = {
        "COMPLETE",
        "independent_verifier.rc.txt",
        "independent_verifier.time.txt",
        "matrix.txt",
        "monitor_receipt.json",
        "preflight13.txt",
        "producer.rc.txt",
        "producer.time.txt",
        "security.txt",
        "snapshot_chain.rc.txt",
        "snapshot_chain_receipt.json",
        "snapshot_chain.time.txt",
    }
    for name in copied_from_manifest:
        assert sha256(RESULT / name) == source_manifest[name]

    summary = json.loads((RESULT / "structural_summary.json").read_text())
    assert sha256(RESULT / "SHA256SUMS") == summary["source_manifest_sha256"]
    assert (
        sha256(RESULT / "manifest_verification.txt")
        == summary["manifest_verification_sha256"]
    )

    for subdir, manifest_sha in (
        (
            "postpush_v1_failure",
            summary["postpush_verification"]["v1_remote_manifest_sha256"],
        ),
        (
            "postpush_v2",
            summary["postpush_verification"]["v2_remote_manifest_sha256"],
        ),
    ):
        root = RESULT / subdir
        manifest_path = root / "SHA256SUMS"
        assert sha256(manifest_path) == manifest_sha
        manifest = {}
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            manifest[relative.removeprefix("./")] = expected
        for path in root.iterdir():
            if path.is_file() and path.name not in {"SHA256SUMS", "COMPLETE"}:
                assert sha256(path) == manifest[path.name]

    assert sha256(RESULT / "postpush_v2" / "COMPLETE") == hashlib.sha256(b"").hexdigest()


def test_structural_summary_reconstructs_receipts() -> None:
    summary = json.loads((RESULT / "structural_summary.json").read_text())
    monitor = json.loads((RESULT / "monitor_receipt.json").read_text())
    chain = json.loads((RESULT / "snapshot_chain_receipt.json").read_text())

    assert summary["status"] == chain["status"]
    assert summary["current_snapshot_sha256"] == monitor["snapshot_sha256"]
    assert summary["current_snapshot_sha256"] == chain["snapshots"]["current"]["sha256"]
    assert summary["prior_snapshot_sha256"] == chain["snapshots"]["prior"]["sha256"]
    assert summary["prior_runs"] == chain["snapshots"]["prior"]["all_runs"] == 494
    assert summary["current_runs"] == chain["snapshots"]["current"]["all_runs"] == 517
    assert summary["added_runs"] == monitor["added_runs"] == 23
    assert summary["removed_runs"] == monitor["removed_runs"] == 0
    assert summary["common_pairs"] == monitor["common_pairs"] == 3230
    assert summary["current_pairs"] == chain["prediction_intersection"]["pairs"]["current"] == 3325
    assert summary["current_endpoints"] == chain["prediction_intersection"]["endpoints"]["current"] == 13581
    assert chain["scope"]["prospective_outcomes_read"] is False
    assert chain["scope"]["prediction_values_printed"] is False
    assert chain["scope"]["effect_metrics_computed"] == []
    assert summary["scope"]["outcomes_read"] is False
    assert summary["scope"]["prediction_values_read"] is False
    assert summary["scope"]["effect_metrics_computed"] == []

    postpush = summary["postpush_verification"]
    assert postpush["exact_commit"] == "cbb22c5bce60b6eb592a10da4bf9672212d7866a"
    assert postpush["v1_status"] == "EXECUTION_HARNESS_CWD_FAILURE"
    assert postpush["v1_scientific_or_release_code_changed"] is False
    assert (postpush["v1_focused_passed"], postpush["v1_full_passed_before_cwd_failures"], postpush["v1_full_failed_from_wrong_cwd"]) == (6, 1919, 16)
    assert postpush["v2_complete"] is True
    assert (postpush["v2_focused_passed"], postpush["v2_full_passed"], postpush["v2_warnings"]) == (6, 1935, 48)
    assert (RESULT / "postpush_v2" / "focused.stdout.txt").read_text().strip().endswith("6 passed in 0.16s")
    assert "1935 passed, 48 warnings in 122.59s" in (RESULT / "postpush_v2" / "full.stdout.txt").read_text()


def test_release_omits_value_bearing_artifacts_and_credentials() -> None:
    names = {path.name for path in RESULT.rglob("*") if path.is_file()}
    assert {
        "endpoint_scores.csv",
        "pair_predictions.jsonl",
        "summary.json",
        "independent_verification.json",
    }.isdisjoint(names)
    assert not any("strace" in name or "command" in name for name in names)

    forbidden_keys = {
        "accuracy",
        "effect_size",
        "margin",
        "maximum_absolute_score_difference",
        "selected",
        "utility",
    }
    for path in RESULT.glob("*.json"):
        stack = [json.loads(path.read_text(encoding="utf-8"))]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                assert forbidden_keys.isdisjoint(item)
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)

    credential = re.compile(r"(?:sk|api)[-_][A-Za-z0-9._-]{12,}", re.IGNORECASE)
    for path in RESULT.rglob("*"):
        if path.is_file():
            assert credential.search(path.read_text(encoding="utf-8", errors="ignore")) is None
