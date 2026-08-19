import itertools
import json
from argparse import Namespace
from pathlib import Path

from phase1.audit_senior_augmented_train_dev_support import run, sha256_file
from phase1.verify_senior_augmented_train_dev_support import verify


def test_support_artifact_round_trip(tmp_path: Path) -> None:
    cards: dict[str, list[dict[str, object]]] = {}
    all_runs: list[str] = []
    hold: list[str] = []
    pairs: list[dict[str, object]] = []
    for task_index in range(2):
        task = f"task-{task_index}"
        run_ids = [f"{task}-run-{index}" for index in range(7)]
        all_runs.extend(run_ids)
        hold.extend(run_ids[-2:])
        for run_id in run_ids:
            card_id = f"{run_id}-card"
            cards[run_id] = [
                {
                    "id": card_id,
                    "task": {"name": task},
                    "client": "model",
                    "hardware": "gpu",
                    "time_limit": 100,
                    "execution_timeout": 10,
                    "code": "frame.to_csv('submission.csv')",
                    "label": None,
                }
            ]
        for left, right in itertools.combinations(run_ids[:5], 2):
            pairs.append(
                {
                    "better": f"{left}-card",
                    "worse": f"{right}-card",
                    "intask_split": "train",
                }
            )
        pairs.append(
            {
                "better": f"{run_ids[-2]}-card",
                "worse": f"{run_ids[-1]}-card",
                "intask_split": "test",
            }
        )

    cards_path = tmp_path / "cards.json"
    pairs_path = tmp_path / "pairs.jsonl"
    split_path = tmp_path / "split.json"
    cards_path.write_text(json.dumps(cards), encoding="utf-8")
    pairs_path.write_text("".join(json.dumps(row) + "\n" for row in pairs), encoding="utf-8")
    split_path.write_text(json.dumps({"all": all_runs, "hold": hold}), encoding="utf-8")
    output = tmp_path / "artifact"
    args = Namespace(
        cards=str(cards_path),
        expect_cards_sha256=sha256_file(cards_path),
        pairs=str(pairs_path),
        expect_pairs_sha256=sha256_file(pairs_path),
        runsplit=str(split_path),
        expect_runsplit_sha256=sha256_file(split_path),
        source_commit="0" * 40,
        senior_source_commit="1" * 40,
        output=str(output),
    )
    assert run(args) == 0
    result = verify(Namespace(artifact=str(output)))
    assert result["status"] == "INDEPENDENT_TRAIN_DEV_SUPPORT_ARTIFACT_VERIFIED"
    assert result["runs"] == 14
    assert result["pairs"] == 22
