from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1" / "results" / "provisional_first960_snapshot_chain_f21a76c_20260826"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_result_manifest_is_exact() -> None:
    rows = [line.split("  ", 1) for line in (RESULT / "SHA256SUMS").read_text().splitlines()]
    assert len(rows) == 8
    for expected, name in rows:
        assert sha256(RESULT / name) == expected


def test_formal_and_deployment_receipts_preserve_exact_boundaries() -> None:
    source = json.loads((RESULT / "source_formal_summary_7017387.json").read_text())
    formal = json.loads((RESULT / "monitor_replay_formal_summary_f21a76c.json").read_text())
    postpush = json.loads((RESULT / "postpush_receipt_9db2d9f.json").read_text())
    chain = json.loads((RESULT / "monitor_replay_chain_receipt_f21a76c.json").read_text())
    deployed = (RESULT / "deployment_receipt.txt").read_text()
    assert source["focused_passed"] == 24 and source["full_passed"] == 1089
    assert formal["focused_passed"] == 25 and formal["full_passed"] == 1090
    assert formal["producer_prior_used"] is False
    assert formal["producer_pairs_identical_to_legacy_current"] is True
    assert (formal["added_runs"], formal["removed_runs"]) == (4, 0)
    assert (formal["common_pairs"], formal["current_only_pairs"]) == (2728, 27)
    assert formal["outcomes_read"] is False and formal["effect_metrics_computed"] == []
    assert postpush["commit"] == "9db2d9f965b342853bd1ce944dd84051f898ccc9"
    assert (postpush["focused_passed"], postpush["full_passed"]) == (11, 1093)
    assert postpush["public_result_manifest_entries_verified"] == 7
    assert postpush["outcomes_read"] is False and postpush["prediction_values_printed"] is False
    assert chain["closure"] == {
        "final_first960_identity": False,
        "support_gate_is_provisional_until_closure": True,
    }
    assert chain["scope"]["prediction_values_printed"] is False
    assert "new_monitor_pid=2320379" in deployed
    assert "formal_manifest_sha256=06b0aaeb40a5c1206a093745b35fe1e0ae89857fa066960e069cb3aa758179e0" in deployed


def test_public_result_contains_no_prediction_values_or_effect_claim() -> None:
    forbidden_keys = {
        "child_code",
        "transition_only",
        "child_plus_transition",
        "margin",
        "selected",
        "accuracy",
        "effect_size",
    }
    for path in RESULT.glob("*.json"):
        value = json.loads(path.read_text())
        stack = [value]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                assert forbidden_keys.isdisjoint(item)
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
    readme = (RESULT / "README.md").read_text(encoding="utf-8")
    assert "不是 predictor accuracy" in readme
    assert "362→366" in readme and "没有 removal" in readme
    assert "没有 `COMPLETE`" in readme
