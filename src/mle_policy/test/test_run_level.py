import json

import pytest

from src.mle_policy.src.data import groupdata
from src.mle_policy.src.data.aggregate_groups import RunFilters, aggregate
from src.mle_policy.src.data.assign_splits import assign_dataset_splits
from src.mle_policy.src.data.journal import read_run_meta
from src.mle_policy.src.data.run_level.big_journal import iter_journal_paths, iter_samples
from src.mle_policy.src.data.build_batch_groups import build_batch
from src.mle_policy.src.data.to_grpo import to_grpo
from src.mle_policy.src.data.to_sft import to_sft


def make_node(node_builder, step, *, metric=None, score=None, buggy=False, maximize=True, prompt=None):
    node = node_builder(
        step,
        calls=[("draft" if step == 0 else "debug", prompt or f"prompt-{step}", f"completion-{step}")],
        buggy=buggy,
        score=score,
        is_lower_better=not maximize,
    )
    node["metric"] = metric
    node["metric_maximize"] = maximize
    return node


def export_journal(run_dir):
    path = run_dir / "json" / "JOURNAL.jsonl"
    path.parent.mkdir()
    nodes = [json.loads(line) for line in (run_dir / "checkpoint" / "journal.jsonl").read_text().splitlines()]
    with path.open("w") as handle:
        for node in nodes:
            info = node.pop("metric_info")
            node.update({f"metric_info/{key}": value for key, value in info.items()})
            handle.write(json.dumps({"data": node}) + "\n")
    return path


@pytest.mark.parametrize("exported", [False, True])
@pytest.mark.parametrize("maximize,metrics", [(True, [0.5, 0.9, 0.9, 0.1]), (False, [0.5, 0.1, 0.1, 0.9])])
def test_reward_selects_metric_not_score_and_keeps_entire_journal(
    tmp_path, node_builder, run_writer, exported, maximize, metrics
):
    nodes = [
        make_node(node_builder, step, metric=metric, score=score, maximize=maximize)
        for step, (metric, score) in enumerate(zip(metrics, [0.8, 0.6, 0.7, 0.9], strict=True))
    ]
    nodes.append(make_node(node_builder, 4, metric=100 if maximize else -100, score=1, buggy=True, maximize=maximize))
    run_dir = run_writer(tmp_path, "run", nodes)
    journal = export_journal(run_dir) if exported else run_dir / "checkpoint" / "journal.jsonl"
    samples = list(iter_samples(journal, read_run_meta(run_dir), "batch", tmp_path))
    assert len(samples) == 5
    assert len({sample["episode_id"] for sample in samples}) == 1
    assert len({sample["group_id"] for sample in samples}) == 1
    for sample in samples:
        assert sample["episode_terminal_step"] == 1
        assert sample["episode_score"] == 0.6
        assert sample["episode_metric"] == metrics[1]
        assert sample["episode_reward"] == pytest.approx((0.6 - 0.5) / 0.3)
        assert sample["episode_metric_reward"] == pytest.approx((metrics[1] - 0.5) / 0.3)
    assert samples[-1]["node_score"] is None


def test_prefers_export_and_does_not_duplicate_checkpoint(tmp_path, node_builder, run_writer):
    run_dir = run_writer(tmp_path, "run", [make_node(node_builder, 0, metric=0.6, score=0.7)])
    exported = export_journal(run_dir)
    assert list(iter_journal_paths(tmp_path)) == [exported]


def test_all_calls_share_label_even_when_selected_node_has_no_calls(tmp_path, node_builder, run_writer):
    root = make_node(node_builder, 0, buggy=True)
    root["operators_used"].append("analysis")
    root["operators_metrics"].append({
        "prompt_messages": [{"role": "user", "content": "analyze failure"}],
        "completion_text": "analysis",
    })
    best = make_node(node_builder, 1, metric=0.8, score=0.7)
    best["operators_used"] = []
    best["operators_metrics"] = []
    run_dir = run_writer(tmp_path, "run", [root, best])
    samples = list(iter_samples(export_journal(run_dir), read_run_meta(run_dir), "batch"))
    assert len(samples) == 2
    assert len({sample["sample_id"] for sample in samples}) == 2
    assert {sample["episode_terminal_step"] for sample in samples} == {1}
    assert {sample["episode_score"] for sample in samples} == {0.7}


def test_missing_selected_score_does_not_select_another_solution(tmp_path, node_builder, run_writer):
    run_dir = run_writer(tmp_path, "run", [
        make_node(node_builder, 0, metric=0.8),
        make_node(node_builder, 1, metric=0.7, score=0.9),
    ])
    samples = list(iter_samples(run_dir / "checkpoint" / "journal.jsonl", read_run_meta(run_dir), "batch"))
    assert samples[0]["episode_terminal_step"] == 0
    assert samples[0]["episode_score"] is None
    assert samples[0]["episode_reward"] is None


@pytest.mark.parametrize("metric", [None, float("nan"), float("inf")])
def test_no_usable_metric_is_unresolved(tmp_path, node_builder, run_writer, metric):
    run_writer(tmp_path / "batch", "run", [make_node(node_builder, 0, metric=metric, score=0.9)])
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False, run_level=True)
    member = groupdata.read_groups(tmp_path / "out")[0]["members"][0]
    assert not member["episode_resolved"]
    assert member["episode_reward"] is None
    assert member["episode_metric_reward"] is None


def test_inconsistent_metric_direction_raises(tmp_path, node_builder, run_writer):
    run_dir = run_writer(tmp_path, "run", [
        make_node(node_builder, 0, metric=0.7, score=0.7),
        make_node(node_builder, 1, metric=0.8, score=0.8, maximize=False),
    ])
    with pytest.raises(ValueError, match="inconsistent metric_maximize"):
        list(iter_samples(run_dir / "checkpoint" / "journal.jsonl", read_run_meta(run_dir), "batch"))


def test_journal_members_feed_existing_pipeline(tmp_path, node_builder, run_writer):
    batch_dir = tmp_path / "batch"
    for run_id, score, metric in [("run-a", 0.7, 0.6), ("run-b", 0.9, 0.8), ("run-c", None, None)]:
        nodes = [
            make_node(node_builder, 0, buggy=True, prompt=f"different initial prompt {run_id}"),
            make_node(node_builder, 1, score=score, metric=metric, buggy=score is None),
            make_node(node_builder, 2, buggy=True),
        ]
        run_dir = run_writer(batch_dir, run_id, nodes)
        if run_id != "run-c":
            export_journal(run_dir)
    built = tmp_path / "built"
    manifest = build_batch(batch_dir, built, verbose=False, run_level=True)
    assert manifest["episodes"] == 3
    assert manifest["samples"] == 9
    assert manifest["episodes_resolved"] == 2
    groups = groupdata.read_groups(built)
    assert len(groups) == 1
    assert groups[0]["size"] == 3
    assert all(len(member["sample_ids"]) == 3 for member in groups[0]["members"])
    dataset = tmp_path / "dataset"
    aggregate([built], dataset, verbose=False)
    assign_dataset_splits(dataset, split_by="run", val_fraction=0, verbose=False)
    assert to_sft(dataset, tmp_path / "sft", verbose=False)["rows"] == 3
    for use_metric in (False, True):
        output = tmp_path / f"grpo-{use_metric}"
        assert to_grpo(dataset, output, use_metric_reward=use_metric, verbose=False)["rows"] == 9
        rows = [json.loads(line) for line in (output / "grpo.jsonl").read_text().splitlines()]
        for episode_id in {row["episode_id"] for row in rows}:
            assert len({row["advantage"] for row in rows if row["episode_id"] == episode_id}) == 1
    filtered = tmp_path / "filtered"
    with pytest.raises(ValueError, match="No runs matched"):
        aggregate([built], filtered, filters=RunFilters(client=("not-this-model",)), verbose=False)


def test_environments_stay_separate(tmp_path, node_builder, run_writer):
    for run_id, hardware in [("run-a", "A100"), ("run-b", "H100")]:
        run_writer(tmp_path / "batch", run_id, [make_node(node_builder, 0, metric=0.7, score=0.7)], hardware=hardware)
    manifest = build_batch(tmp_path / "batch", tmp_path / "out", verbose=False, run_level=True)
    assert manifest["groups"] == 2
    assert manifest["environment_mixed"]
