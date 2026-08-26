from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "archive_content_alias_disposition_8579_20260827_9b7640a"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _manifest(name: str) -> dict[str, str]:
    rows = {}
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        assert match is not None
        rows[match.group(2)] = match.group(1)
    return rows


def _kv(name: str) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
    )


def test_alias_postflight_summary_and_independent_receipts_agree() -> None:
    summary = _json("formal_summary.json")
    verification = _json("fresh_post_verification.json")
    partition = _json("fresh_partition_independent_verification.json")
    assert summary["status"] == "ARCHIVE_CONTENT_ALIAS_POSTFLIGHT_V2_PASS"
    assert summary["snapshot_sha256"] == verification["snapshot_sha256"]
    assert summary["source_commit"] == verification["source_commit"]
    assert summary["alias_registry_sha256"] == verification["registry_sha256"]
    assert summary["declared_aliases"] == verification["alias_count"] == 8
    assert summary["byte_identical_aliases"] == verification["byte_identical_aliases"] == 8
    assert summary["alias_total_bytes"] == verification["alias_total_bytes"] == 183409093
    assert summary["transaction_count"] == verification["transaction_count"] == 86
    assert verification["canonical_transactions"] == 8
    assert verification["new_transactions_created"] == 0
    assert verification["expected_disposition"] == "applied"
    assert verification["outcomes_read"] is False
    assert verification["archive_payloads_extracted"] is False
    assert partition["status"] == "INDEPENDENT_ARCHIVE_DISPOSITION_PARTITION_PASS"
    assert partition["recomputed_counts"] == summary["partition_counts"]
    assert partition["recomputed_reason_counts"][
        "ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION"
    ] == 8
    assert partition["outcomes_or_predictions_read"] is False
    assert summary["formal_v1_complete"] is False
    assert summary["v1_broad_runner_filename_hits"] == 6
    assert summary["v1_forbidden_open_or_openat_hits"] == 0
    assert summary["fresh_forbidden_open_or_openat_hits"] == 0
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]


def test_selected_public_artifacts_match_remote_postflight_manifest() -> None:
    rows = _manifest("remote_postflight_SHA256SUMS")
    mapping = {
        "fresh_partition_independent_verification.json": "fresh_partition_independent_verification.json",
        "fresh_post_verification.json": "fresh_post_verification.json",
        "operation_summary.txt": "operation_summary.txt",
        "preflight_13.txt": "preflight_13.txt",
        "semantic_gate_check.stdout": "semantic_gate_check.stdout",
        "v1_runner_stat_only_hits.txt": "v1_runner_stat_only_hits.txt",
        "v1_trace_access_audit.tsv": "v1_trace_access_audit.tsv",
    }
    for remote_name, local_name in mapping.items():
        assert _sha(ROOT / local_name) == rows[remote_name]
    manifest_line = (ROOT / "remote_postflight_manifest_sha256.txt").read_text(
        encoding="utf-8"
    ).strip()
    assert manifest_line.startswith(
        "1fa3c81c257316d2c2886ddbd36f72e60f1d8ed85f889450916e4d59de3a8625  "
    )


def test_public_monitor_and_live_recovery_receipts_are_bound() -> None:
    public_manifest = _manifest("public_monitor_postpush_SHA256SUMS")
    intake_manifest = _manifest("intake_deploy_SHA256SUMS")
    transition_manifest = _manifest("transition_relaunch_SHA256SUMS")
    assert _sha(ROOT / "public_monitor_postpush_SHA256SUMS") == (
        "3629dced0880863332319b6328aba515930444594d63a15733bf3fac95bcf5e0"
    )
    assert _sha(ROOT / "intake_deploy_SHA256SUMS") == (
        "17ac353cc74142410a0926bbbed9a13ad9c4eccbe6e37dbca277261282b28923"
    )
    assert _sha(ROOT / "transition_relaunch_SHA256SUMS") == (
        "baa8621fa1d09aec89fb7804112b0965340a91ed81f6fdb28e87effe27b96969"
    )
    assert _sha(ROOT / "public_monitor_postpush_summary.txt") == public_manifest[
        "operation_summary.txt"
    ]
    assert intake_manifest["operation_summary.txt"] == (
        "9baf9895dd71c946571c6e56bdcd86f4f18f87303d9de0b19c7bc6a2b75af434"
    )
    assert _sha(ROOT / "intake_deployment_log_segment.txt") == intake_manifest[
        "deployment_log_segment.txt"
    ]
    assert transition_manifest["operation_summary.txt"] == (
        "0c3faa0f4f3c7635de72e8be0a9222c62740bfe8a1d397d87d67b0c2cbb41668"
    )
    assert _sha(ROOT / "transition_relaunch_log_segment.txt") == transition_manifest[
        "relaunch_log_segment.txt"
    ]

    public = _kv("public_monitor_postpush_summary.txt")
    intake = _kv("intake_deploy_summary.txt")
    transition = _kv("transition_relaunch_summary.txt")
    assert public["status"] == "PUBLIC_ALIAS_MONITOR_POSTPUSH_PASS"
    assert public["focused_tests"].startswith("32 passed")
    assert public["full_tests"].startswith("1196 passed")
    assert public["commit_filename_secret_hits"] == "0"
    assert public["commit_blob_secret_hits"] == "0"
    assert intake["status"] == "ALIAS_BOUND_INTAKE_DEPLOY_PASS"
    assert intake["latest_before"] == intake["latest_after"]
    assert intake["transactions_before"] == intake["transactions_after"] == "86"
    assert intake["transactions_before_sha256"] == intake[
        "transactions_after_sha256"
    ]
    assert intake["poll0_rc"] == "0"
    poll = (ROOT / "intake_deployment_log_segment.txt").read_text(encoding="utf-8")
    assert "archives=246 baseline=128 ready=0 rejected=20 transactions=86" in poll
    assert transition["status"] == "TRANSITION_SNAPSHOT_CHAIN_RELAUNCH_PASS"
    assert transition["prior_snapshot"] == intake["latest_after"]
    assert transition["outcomes_read"] == "false"
    assert transition["effect_metrics_computed"] == "false"


def test_public_package_manifest_is_complete() -> None:
    expected = {}
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        assert match is not None
        expected[match.group(2)] = match.group(1)
    actual = {
        path.name: _sha(path)
        for path in ROOT.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == actual
