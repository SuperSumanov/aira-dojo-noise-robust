from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1.endpoint_denylist import (
    PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
    PRECUTOFF_ENDPOINTS,
    DenylistError,
    build,
    load_endpoint_denylist,
)
from phase1 import verify_endpoint_denylist


def write_cards(path: Path) -> str:
    rows = [
        {"id": "b", "code": "print('same')", "label": {"graded": 0.9}},
        {"id": "a", "code": "print('same')", "label": {"graded": 0.1}},
        {"id": "c", "code": "print('other')", "label": None},
    ]
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(text.encode()).hexdigest()


def test_build_is_sorted_label_free_and_roundtrips(tmp_path: Path):
    cards = tmp_path / "cards.jsonl"
    cards_sha = write_cards(cards)
    output = tmp_path / "denylist.csv"
    summary = tmp_path / "summary.json"
    args = argparse.Namespace(
        cards=cards,
        output=output,
        summary=summary,
        expect_cards_sha256=cards_sha,
        expect_endpoints=3,
    )
    assert build(args) == 0
    payload = output.read_text(encoding="utf-8")
    assert "graded" not in payload and "label" not in payload and "print" not in payload
    assert [line.split(",", 1)[0] for line in payload.splitlines()[1:]] == ["a", "b", "c"]
    ids, code_shas, audit = load_endpoint_denylist(output, hashlib.sha256(output.read_bytes()).hexdigest())
    assert ids == {"a", "b", "c"}
    assert len(code_shas) == 2
    assert audit == {"endpoint_ids": 3, "unique_code_sha256": 2}
    recorded = json.loads(summary.read_text(encoding="utf-8"))
    assert recorded["source_contains_label_fields"] is True
    assert recorded["selected_source_keys"] == ["id", "code"]
    assert recorded["labels_used"] is False
    assert recorded["label_values_printed"] is False


def test_independent_verifier_reconstructs_exact_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cards = tmp_path / "cards.jsonl"
    cards_sha = write_cards(cards)
    denylist = tmp_path / "denylist.csv"
    summary = tmp_path / "summary.json"
    build(
        argparse.Namespace(
            cards=cards,
            output=denylist,
            summary=summary,
            expect_cards_sha256=cards_sha,
            expect_endpoints=3,
        )
    )
    output = tmp_path / "verify.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify",
            "--cards", str(cards),
            "--denylist", str(denylist),
            "--summary", str(summary),
            "--output", str(output),
            "--expect-cards-sha256", cards_sha,
            "--expect-denylist-sha256", hashlib.sha256(denylist.read_bytes()).hexdigest(),
            "--expect-endpoints", "3",
        ],
    )
    assert verify_endpoint_denylist.main() == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "VERIFIED_PRECUTOFF_ENDPOINT_DENYLIST_COMPLETE"
    assert result["exact_rows"] is True


def test_loader_rejects_unsorted_or_hash_mismatch(tmp_path: Path):
    path = tmp_path / "denylist.csv"
    path.write_text(
        "card_id,code_sha256\n" + f"b,{'a' * 64}\n" + f"a,{'b' * 64}\n",
        encoding="utf-8",
        newline="\n",
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(DenylistError, match="unique and sorted"):
        load_endpoint_denylist(path, digest)
    with pytest.raises(DenylistError, match="SHA mismatch"):
        load_endpoint_denylist(path, "0" * 64)


def test_loader_rejects_inventory_mismatch(tmp_path: Path):
    path = tmp_path / "denylist.csv"
    path.write_text(
        "card_id,code_sha256\n" + f"a,{'a' * 64}\n",
        encoding="utf-8",
        newline="\n",
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(DenylistError, match="inventory mismatch"):
        load_endpoint_denylist(path, digest, expected_endpoints=2)


def test_committed_precutoff_contract_matches_frozen_constants():
    path = (
        Path(__file__).parents[1]
        / "results"
        / "fixed_decision_scorer_v11_20260814"
        / "precutoff_endpoint_denylist.csv"
    )
    card_ids, code_shas, audit = load_endpoint_denylist(
        path,
        PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
        PRECUTOFF_ENDPOINTS,
    )
    assert len(card_ids) == PRECUTOFF_ENDPOINTS
    assert len(code_shas) == 15_912
    assert audit == {"endpoint_ids": 16_012, "unique_code_sha256": 15_912}
