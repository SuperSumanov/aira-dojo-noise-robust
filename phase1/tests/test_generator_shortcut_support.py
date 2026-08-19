import argparse
import hashlib
import json
from pathlib import Path

from phase1.audit_generator_shortcut_support import run
from phase1.verify_generator_shortcut_support import verify


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_support_audit_is_outcome_blind_and_deterministic(tmp_path: Path) -> None:
    cards = {}
    pairs = []
    clients = ("alpha", "beta")
    for task_index in range(6):
        task = f"task-{task_index}"
        for client_index, client in enumerate(clients):
            for run_index in range(30):
                run_id = f"{task}-{client}-{run_index}"
                first = f"{run_id}-a"
                second = f"{run_id}-b"
                cards[run_id] = [
                    {
                        "id": first,
                        "task": {"name": task},
                        "client": client,
                        "hardware": "gpu",
                        "time_limit": 100,
                        "execution_timeout": 10,
                        "code": "secret outcome is deliberately ignored",
                        "label": {"graded": task_index + client_index},
                    },
                    {
                        "id": second,
                        "task": {"name": task},
                        "client": client,
                        "hardware": "gpu",
                        "time_limit": 100,
                        "execution_timeout": 10,
                        "code": "also ignored",
                        "label": {"graded": -999},
                    },
                ]
                pairs.append({"better": first, "worse": second, "intask_split": "train"})
        for index in range(30):
            left_run = f"{task}-alpha-{index}"
            right_run = f"{task}-beta-{index}"
            pairs.append(
                {
                    "better": f"{left_run}-a",
                    "worse": f"{right_run}-a",
                    "intask_split": "train",
                }
            )

    cards_path = tmp_path / "cards.json"
    pairs_path = tmp_path / "pairs.jsonl"
    cards_path.write_text(json.dumps(cards), encoding="utf-8")
    pairs_path.write_text("".join(json.dumps(row) + "\n" for row in pairs), encoding="utf-8")

    def args(output: Path) -> argparse.Namespace:
        return argparse.Namespace(
            cards=str(cards_path),
            expect_cards_sha256=digest(cards_path),
            pairs=str(pairs_path),
            expect_pairs_sha256=digest(pairs_path),
            source_commit="a" * 40,
            senior_source_commit="b" * 40,
            output=str(output),
        )

    assert run(args(tmp_path / "a")) == 0
    assert run(args(tmp_path / "b")) == 0
    assert (tmp_path / "a" / "summary.json").read_bytes() == (tmp_path / "b" / "summary.json").read_bytes()
    summary = json.loads((tmp_path / "a" / "summary.json").read_text())
    assert summary["scope"]["numeric_grade_used"] is False
    assert summary["pools"]["cross_client_same_environment"]["pairs"] == 180
    assert summary["pools"]["same_client"]["pairs"] == 360
    verify_args = argparse.Namespace(
        cards=str(cards_path),
        expect_cards_sha256=digest(cards_path),
        pairs=str(pairs_path),
        expect_pairs_sha256=digest(pairs_path),
        artifact=str(tmp_path / "a"),
        output=str(tmp_path / "verify.json"),
    )
    assert verify(verify_args) == 0
    assert json.loads((tmp_path / "verify.json").read_text())["pools_reproduced"] is True


def test_support_audit_rejects_duplicate_unordered_pair(tmp_path: Path) -> None:
    cards = {
        "run": [
            {"id": "a", "task": {"name": "t"}, "client": "c", "hardware": "g", "time_limit": 1, "execution_timeout": 1},
            {"id": "b", "task": {"name": "t"}, "client": "c", "hardware": "g", "time_limit": 1, "execution_timeout": 1},
        ]
    }
    cards_path = tmp_path / "cards.json"
    pairs_path = tmp_path / "pairs.jsonl"
    cards_path.write_text(json.dumps(cards), encoding="utf-8")
    pairs_path.write_text(
        json.dumps({"better": "a", "worse": "b", "intask_split": "train"})
        + "\n"
        + json.dumps({"better": "b", "worse": "a", "intask_split": "train"})
        + "\n",
        encoding="utf-8",
    )
    try:
        run(
            argparse.Namespace(
                cards=str(cards_path),
                expect_cards_sha256=digest(cards_path),
                pairs=str(pairs_path),
                expect_pairs_sha256=digest(pairs_path),
                source_commit="a" * 40,
                senior_source_commit="b" * 40,
                output=str(tmp_path / "out"),
            )
        )
    except RuntimeError as exc:
        assert "duplicate unordered train pair" in str(exc)
    else:
        raise AssertionError("duplicate pair was accepted")
