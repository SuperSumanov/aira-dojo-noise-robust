from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path

from phase1 import openrouter_full_context_live_v2 as live


PHASE1 = Path(__file__).resolve().parents[1]
OLD_HARDENING = PHASE1 / "openrouter_full_context_live_hardening_v2.json"
NEW_HARDENING = PHASE1 / "openrouter_full_context_live_hardening_v2_catalog_20260830.json"
OLD_RECEIPT = PHASE1 / "openrouter_full_context_smoke_launch_receipt_v2.json"
NEW_RECEIPT = PHASE1 / "openrouter_full_context_smoke_launch_receipt_v2_catalog_20260830.json"
CATALOG_RECEIPT = PHASE1 / "openrouter_full_context_catalog_refresh_20260830.json"
PROTOCOL = PHASE1 / "openrouter_full_context_judge_v1.json"
REPRESENTATION = PHASE1 / "openrouter_full_context_metric_omission_amendment_v2.json"
RUNNER = PHASE1 / "openrouter_full_context_live_v2.py"
ANALYZER = PHASE1 / "analyze_openrouter_full_context_smoke_v2.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_catalog_refresh_preserves_frozen_scientific_and_transport_contracts() -> None:
    old = load(OLD_HARDENING)
    new = load(NEW_HARDENING)
    assert sha256(OLD_HARDENING) == "01af5ff7656fe4131539729efa28383c45480b8ddc5b20dbfcddabc217eb5d60"
    assert sha256(OLD_RECEIPT) == "d3c58c4968ee37e8493ada9eedaff9c9826c980c67b047de62586337d9c8433a"
    for key in (
        "parent",
        "request_hardening",
        "resume_hardening",
        "cost_hardening",
        "response_hardening",
        "smoke_gates",
        "analysis",
        "scientific_boundary",
    ):
        assert new[key] == old[key]
    for key in (
        "account_limit_usd_reported_by_senior",
        "this_launch_phase",
        "this_launch_maximum_calls",
        "this_launch_cumulative_usd_stop",
        "credential_must_exist_only_in_remote_mode_0600_dotenv",
        "credential_value_must_never_enter_git_command_arguments_or_logs",
    ):
        assert new["authorization"][key] == old["authorization"][key]


def test_catalog_refresh_is_exactly_bound_and_only_deepseek_price_changed() -> None:
    receipt = load(CATALOG_RECEIPT)
    old = load(OLD_HARDENING)
    new = load(NEW_HARDENING)
    assert receipt["credential_used"] is False
    assert receipt["paid_api_calls"] == 0
    assert receipt["all_exact_ids_available"] is True
    assert new["catalog_refresh_receipt_sha256"] == sha256(CATALOG_RECEIPT)
    old_rows = {row["id"]: row for row in old["catalog_recheck"]["models"]}
    new_rows = {row["id"]: row for row in new["catalog_recheck"]["models"]}
    receipt_rows = {row["id"]: row for row in receipt["models"]}
    assert list(new_rows) == list(old_rows) == list(receipt_rows)
    for model, row in new_rows.items():
        source = receipt_rows[model]
        assert row["canonical_slug"] == source["canonical_slug"]
        assert row["context_length"] == source["context_length"]
        assert row["max_completion_tokens"] == source["max_completion_tokens"]
        assert row["prompt_usd_per_million_at_recheck"] == source["prompt_usd_per_million"]
        assert row["completion_usd_per_million_at_recheck"] == source["completion_usd_per_million"]
        if model != "deepseek/deepseek-v4-flash-0731":
            assert row == old_rows[model]
    deepseek = new_rows["deepseek/deepseek-v4-flash-0731"]
    assert deepseek["prompt_usd_per_million_at_recheck"] == "0.065"
    assert deepseek["completion_usd_per_million_at_recheck"] == "0.18"
    assert old_rows["deepseek/deepseek-v4-flash-0731"]["prompt_usd_per_million_at_recheck"] == "0.045"
    assert old_rows["deepseek/deepseek-v4-flash-0731"]["completion_usd_per_million_at_recheck"] == "0.09"


def test_existing_runner_accepts_refreshed_hardening_and_launch_receipt() -> None:
    new = load(NEW_HARDENING)
    observed, hardening_sha = live.load_hardening(
        NEW_HARDENING,
        sha256(NEW_HARDENING),
        sha256(PROTOCOL),
        sha256(REPRESENTATION),
        new["parent"]["private_panel_sha256"],
    )
    assert hardening_sha == sha256(NEW_HARDENING)
    models = live.frozen_models(observed)
    contract = live.provider_contract("deepseek/deepseek-v4-flash-0731", observed)
    assert contract["max_price"] == {"prompt": 0.065, "completion": 0.18}
    live.load_launch_receipt(
        NEW_RECEIPT,
        sha256(PROTOCOL),
        sha256(REPRESENTATION),
        hardening_sha,
        observed["parent"]["private_panel_sha256"],
        sha256(RUNNER),
        sha256(ANALYZER),
        "smoke",
        models,
        64,
        Decimal("2.00"),
    )
