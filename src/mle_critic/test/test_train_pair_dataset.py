import json

import pytest

from src.mle_critic.src.train.dataset.pairs import read_cards, read_pairs


def card(card_id, task_name, code):
    return {
        "id": card_id,
        "task": {"name": task_name},
        "time_limit": 7200,
        "execution_timeout": 1200,
        "client": "openai/gpt-5",
        "hardware": "slurm/a100",
        "plan": "",
        "code": code,
        "obs": {},
        "lineage": {},
        "label": None,
    }


def test_read_cards_flattens_current_run_grouped_format(tmp_path):
    cards_path = tmp_path / "cards.json"
    pairs_path = tmp_path / "pairs.jsonl"
    cards_path.write_text(
        json.dumps(
            {
                "run-a__2026-08-01": [card("a", "task-a", "code-a")],
                "run-b__2026-08-02": [card("b", "task-b", "code-b")],
            }
        )
    )
    pairs_path.write_text(
        "\n".join(
            [
                json.dumps({"better": "a", "worse": "b"}),
                json.dumps({"better": "a", "worse": "missing"}),
            ]
        )
    )

    codes, tasks = read_cards(str(cards_path))
    pairs = read_pairs(str(pairs_path), codes)

    assert codes == {"a": "code-a", "b": "code-b"}
    assert tasks == {"a": "task-a", "b": "task-b"}
    assert pairs == [{"better": "a", "worse": "b"}]


def test_read_cards_rejects_old_flat_jsonl_format(tmp_path):
    cards_path = tmp_path / "cards.jsonl"
    cards_path.write_text(
        "\n".join(
            [
                json.dumps(card("a", "task", "code-a")),
                json.dumps(card("b", "task", "code-b")),
            ]
        )
    )

    with pytest.raises(ValueError):
        read_cards(str(cards_path))


def test_read_cards_rejects_duplicate_card_ids_across_runs(tmp_path):
    cards_path = tmp_path / "cards.json"
    cards_path.write_text(
        json.dumps(
            {
                "run-a__2026-08-01": [card("same", "task", "code-a")],
                "run-b__2026-08-02": [card("same", "task", "code-b")],
            }
        )
    )

    with pytest.raises(ValueError, match="Duplicate Card ID"):
        read_cards(str(cards_path))
