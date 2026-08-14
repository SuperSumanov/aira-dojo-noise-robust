import json

from src.mle_critic.src.preprocess.download_and_resolve.build_runsplit import (
    extend_runsplit,
    update_runsplit,
)
from src.mle_critic.src.preprocess.download_and_resolve.cards import (
    Card,
    TaskInfo,
    save_cards,
)


def make_run(task_name):
    return [Card(id=f"{task_name}-card", task=TaskInfo(name=task_name))]


def test_extend_preserves_old_assignments_and_only_assigns_new_runs():
    task_by_run_id = {
        "old-train": "task-a",
        "old-test": "task-a",
        **{f"new-{index}": "task-a" for index in range(10)},
    }

    held, assigned, new_runs, counts = extend_runsplit(
        task_by_run_id,
        old_held_out_runs={"old-test", "stale-test"},
        old_assigned_runs={"old-train", "old-test", "stale-train", "stale-test"},
        seed=7,
    )

    assert "old-test" in held
    assert "old-train" not in held
    assert {"stale-train", "stale-test"} <= assigned
    assert "stale-test" in held
    assert new_runs == {f"new-{index}" for index in range(10)}
    assert counts == {"task-a": (10, 2)}
    assert len(held & new_runs) == 2


def test_missing_split_rebuilds_all_current_runs(tmp_path):
    cards_path = tmp_path / "cards.json"
    split_path = tmp_path / "runsplit.json"
    save_cards(
        {f"run-{index}": make_run("task-a") for index in range(10)},
        str(cards_path),
    )

    summary = update_runsplit(cards_path, split_path, seed=7)
    payload = json.loads(split_path.read_text())

    assert summary["new_runs"] == 10
    assert len(payload["all"]) == 10
    assert len(payload["hold"]) == 2


def test_disjoint_new_batch_keeps_previous_split(tmp_path):
    cards_path = tmp_path / "cards.json"
    split_path = tmp_path / "runsplit.json"
    save_cards({"new-run": make_run("task-a")}, str(cards_path))
    split_path.write_text(
        json.dumps({"hold": ["old-test"], "all": ["old-train", "old-test"]})
    )

    update_runsplit(cards_path, split_path, seed=7)

    payload = json.loads(split_path.read_text())
    assert set(payload["all"]) == {"old-train", "old-test", "new-run"}
    assert {"old-test", "new-run"} <= set(payload["hold"])
