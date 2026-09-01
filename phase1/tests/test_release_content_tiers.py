import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_release_content_tiers import build, canonical_bytes
from phase1.verify_release_content_tiers import verify


SHA = "0" * 64


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol() -> dict:
    return json.loads(
        (Path(__file__).resolve().parents[1] / "release_content_tier_protocol_v1.json")
        .read_text(encoding="utf-8")
    )


def fixture(tmp_path: Path) -> tuple[Path, dict, dict]:
    cards = tmp_path / "cards.jsonl"
    rows = [
        {
            "id": "raw-hit-card-id",
            "task": {"name": "covered"},
            "code": "private-source-value-123456789",
            "obs": {"stdout_tail": "stdout-hit-value-123456789"},
        },
        {
            "id": "raw-safe-card-id",
            "task": {"name": "covered"},
            "code": "safe-but-not-cleared-value-123456789",
            "obs": {"stdout_tail": "safe-output-value-123456789"},
        },
        {
            "id": "raw-unscanned-card-id",
            "task": {"name": "unscanned"},
            "code": "unscanned-source-value-123456789",
            "obs": {"stdout_tail": "unscanned-output-value-123456789"},
        },
    ]
    write_jsonl(cards, rows)
    hit_hash = hashlib.sha256(rows[0]["id"].encode()).hexdigest()
    summary = {
        "protocol": "release-content-scan-v1",
        "status": "PARTIAL_COVERAGE_MATCHES_REQUIRE_REVIEW",
        "input": {"cards_sha256": file_sha(cards), "cards_rows": 3},
        "coverage": {"tasks_total": 2, "tasks_scanned": 1},
        "totals": {"matched_patterns": 1, "affected_card_sum_across_tasks": 1},
        "tasks": {
            "covered": {
                "cards": 2,
                "prepared_text_available": True,
                "affected_cards": 1,
                "affected_card_fields": {
                    "code_literal_or_comment": 1,
                    "stdout_tail": 0,
                },
            },
            "unscanned": {
                "cards": 1,
                "prepared_text_available": False,
                "affected_cards": None,
                "affected_card_fields": None,
            },
        },
    }
    private = {
        "protocol": "release-content-scan-private-manifest-v1",
        "cards_sha256": file_sha(cards),
        "hits": [
            {
                "task": "covered",
                "card_id_sha256": hit_hash,
                "field": "code_literal_or_comment",
                "matched_span_sha256": ["1" * 64],
            }
        ],
    }
    return cards, summary, private


def build_fixture(tmp_path: Path) -> tuple[Path, dict, dict, dict, dict, dict]:
    cards, summary, private = fixture(tmp_path)
    frozen = protocol()
    frozen["freeze_observation"].update({
        "global_tasks_scanned": 1,
        "global_tasks_total": 2,
        "global_matched_patterns": 1,
        "global_affected_card_sum_across_tasks": 1,
    })
    public, tier_private = build(
        frozen, SHA, summary, SHA, private, SHA, cards, file_sha(cards)
    )
    return cards, summary, private, public, tier_private, frozen


def test_frozen_protocol_precedes_task_and_card_disposition() -> None:
    value = protocol()
    assert value["status"] == "FROZEN_AFTER_GLOBAL_SCAN_COUNTS_BEFORE_TASK_OR_CARD_DISPOSITION_READ"
    freeze = value["freeze_observation"]
    assert freeze["global_tasks_scanned"] == 23
    assert freeze["global_tasks_total"] == 25
    assert freeze["task_level_scan_summary_opened"] is False
    assert freeze["private_card_hash_hit_manifest_opened"] is False
    assert value["decision_rule"]["post_result_rule_change_allowed"] is False


def test_conservative_whole_card_tiers_and_independent_reconstruction(tmp_path: Path) -> None:
    cards, summary, scan_private, public, tier_private, frozen = build_fixture(tmp_path)
    assert public["totals"] == {
        "cards": 3,
        "content_review_eligible_cards": 1,
        "structure_only_cards": 2,
        "structure_only_due_matched_pattern": 1,
        "structure_only_due_unscanned_task": 1,
        "content_review_eligible_fraction": {
            "numerator": 1,
            "denominator": 3,
            "decimal_17g": format(1 / 3, ".17g"),
        },
    }
    assert len(tier_private["rows"]) == 3
    withheld = [row for row in tier_private["rows"] if row["release_tier"] == "STRUCTURE_ONLY"]
    eligible = [row for row in tier_private["rows"] if row["release_tier"] == "CONTENT_REVIEW_ELIGIBLE"]
    assert len(withheld) == 2 and len(eligible) == 1
    assert all(row["withheld_fields"] == ["code", "obs.stdout_tail"] for row in withheld)
    assert eligible[0]["withheld_fields"] == []
    rendered_public = canonical_bytes(public).decode()
    rendered_private = canonical_bytes(tier_private).decode()
    for forbidden in (
        "raw-hit-card-id",
        "raw-safe-card-id",
        "raw-unscanned-card-id",
        "private-source-value",
        "stdout-hit-value",
        str(tmp_path),
    ):
        assert forbidden not in rendered_public
        assert forbidden not in rendered_private
    result = verify(
        frozen, SHA, summary, SHA, scan_private, SHA, cards, file_sha(cards),
        public, SHA, tier_private, SHA,
    )
    assert result["status"] == "INDEPENDENT_RECONSTRUCTION_EXACT"
    assert result["cards_reconstructed"] == 3
    assert result["private_tier_rows_reconstructed"] == 3
    assert result["structure_only_rows_reconstructed"] == 2


def test_verifier_rejects_public_tier_tampering(tmp_path: Path) -> None:
    cards, summary, scan_private, public, tier_private, frozen = build_fixture(tmp_path)
    public["totals"]["content_review_eligible_cards"] = 2
    with pytest.raises(ValueError, match="public totals"):
        verify(
            frozen, SHA, summary, SHA, scan_private, SHA, cards, file_sha(cards),
            public, SHA, tier_private, SHA,
        )


def test_unscanned_task_cannot_carry_private_scan_hits(tmp_path: Path) -> None:
    cards, summary, scan_private = fixture(tmp_path)
    scan_private["hits"][0]["task"] = "unscanned"
    scan_private["hits"][0]["card_id_sha256"] = hashlib.sha256(
        "raw-unscanned-card-id".encode()
    ).hexdigest()
    summary["tasks"]["covered"]["affected_cards"] = 0
    summary["tasks"]["covered"]["affected_card_fields"]["code_literal_or_comment"] = 0
    frozen = protocol()
    frozen["freeze_observation"].update({
        "global_tasks_scanned": 1,
        "global_tasks_total": 2,
        "global_matched_patterns": 1,
        "global_affected_card_sum_across_tasks": 1,
    })
    with pytest.raises(Exception, match="unscanned task has"):
        build(frozen, SHA, summary, SHA, scan_private, SHA, cards, file_sha(cards))


def test_formal_runner_pins_upstream_hashes_and_security_gates() -> None:
    runner = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_release_content_tier_v1_20260902.sh"
    ).read_text(encoding="utf-8")
    assert "formal-fc41932-r1" in runner
    for digest in (
        "9ba53816984850397eeaf0dd80cd685cae2df6d602a7ab17aa0893852e703927",
        "616e95f7cd85965d98975b6643b7bfe1cfe634a080ed3e8ca29776fda81388f7",
        "047a70b2ea189193d684aab41c04362035f4edd5119ddf90ace5b39342f1cf77",
        "16a8b7045a5cddf3941f49f6637ef4c3a78149a762407b68587ae300c0dfe235",
    ):
        assert digest in runner
    assert runner.count("-m phase1.build_release_content_tiers") == 2
    assert runner.count("-m phase1.verify_release_content_tiers") == 2
    assert 'cmp "${public_a}" "${public_b}"' in runner
    assert 'cmp "${private_a}" "${private_b}"' in runner
    assert 'cmp "${verify_a}" "${verify_b}"' in runner
    assert "prospective_hits=" in runner
    assert "network_hits=" in runner
    assert "credential_hits=" in runner
    assert "absolute_path_hits=" in runner
    assert "GIT_LFS_SKIP_SMUDGE=1" in runner
