from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase1 import audit_cross_client_transfer_support as support


def card(card_id: str, client: str, task: str, code: str) -> dict:
    return {
        "id": card_id,
        "client": client,
        "hardware": "h100",
        "time_limit": 100,
        "execution_timeout": 10,
        "task": {"name": task},
        "code": code,
    }


def write_inputs(root: Path) -> tuple[Path, Path]:
    cards = {
        "r1": [card("a", "c1", "t", "print(1)"), card("b", "c1", "t", "print(2)")],
        "r2": [card("c", "c2", "t", "print(3)"), card("d", "c2", "t", "print(4)")],
    }
    cards_path = root / "cards.json"
    cards_path.write_text(json.dumps(cards), encoding="utf-8")
    pairs_path = root / "pairs.jsonl"
    pairs_path.write_text(
        json.dumps({"better": "a", "worse": "b", "intask_split": "train"}) + "\n"
        + json.dumps({"better": "c", "worse": "d", "intask_split": "train"}) + "\n",
        encoding="utf-8",
    )
    return cards_path, pairs_path


def test_orientation_is_removed_from_structural_pool(tmp_path: Path) -> None:
    cards_path, pairs_path = write_inputs(tmp_path)
    cards, runs = support.load_cards(cards_path)
    pairs = support.load_pairs(pairs_path, cards)
    assert pairs[0]["endpoint_a"] == "a"
    assert pairs[0]["endpoint_b"] == "b"
    assert "better" not in pairs[0] and "worse" not in pairs[0]
    summary, pool = support.derive(cards, runs, pairs)
    assert summary["status"] == "INSUFFICIENT_CROSS_CLIENT_TRANSFER_SUPPORT"
    assert pool == []


def test_duplicate_unordered_pair_fails_closed(tmp_path: Path) -> None:
    cards_path, pairs_path = write_inputs(tmp_path)
    with pairs_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"better": "b", "worse": "a", "intask_split": "train"}) + "\n")
    cards, _ = support.load_cards(cards_path)
    with pytest.raises(support.AuditError, match="duplicate unordered"):
        support.load_pairs(pairs_path, cards)


def test_cross_environment_pair_is_not_exact(tmp_path: Path) -> None:
    cards_path, pairs_path = write_inputs(tmp_path)
    payload = json.loads(cards_path.read_text(encoding="utf-8"))
    payload["r2"][0]["hardware"] = "a100"
    payload["r2"][1]["hardware"] = "a100"
    cards_path.write_text(json.dumps(payload), encoding="utf-8")
    pairs_path.write_text(json.dumps({"better": "a", "worse": "c", "intask_split": "train"}) + "\n", encoding="utf-8")
    cards, runs = support.load_cards(cards_path)
    pairs = support.load_pairs(pairs_path, cards)
    assert pairs[0]["same_environment"] is False
    summary, _ = support.derive(cards, runs, pairs)
    assert summary["inventory"]["same_client_same_environment_pairs"] == 0
