import json

import pytest

from src.mle_policy.src.data import groupdata
from src.mle_policy.src.data.aggregate_groups import aggregate
from src.mle_policy.src.data.assign_splits import assign_dataset_splits, assign_splits
from src.mle_policy.src.data.build_batch_groups import build_batch
from src.mle_policy.src.data.to_dpo import to_dpo
from src.mle_policy.src.data.to_grpo import to_grpo
from src.mle_policy.src.data.to_sft import to_sft


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_groups_never_cross_batches(tmp_path, node_builder, run_writer):
    # Same prompt in two different batches: the grouping must keep them apart.
    for batch in ("batch-one", "batch-two"):
        run_writer(
            tmp_path / batch,
            "run-a",
            [node_builder(1, calls=[("draft", "same prompt", "solution")], buggy=False, score=0.6)],
        )
    build_batch(tmp_path / "batch-one", tmp_path / "out" / "one", verbose=False)
    build_batch(tmp_path / "batch-two", tmp_path / "out" / "two", verbose=False)
    one = read_jsonl(tmp_path / "out" / "one" / groupdata.GROUPS_FILE)
    two = read_jsonl(tmp_path / "out" / "two" / groupdata.GROUPS_FILE)
    assert len(one) == len(two) == 1
    assert one[0]["group_id"] != two[0]["group_id"]


def test_episode_is_the_smallest_group_member(tmp_path, node_builder, run_writer):
    run_writer(
        tmp_path / "batch",
        "run-a",
        [
            node_builder(1, calls=[("draft", "root input", "broken")], buggy=True),
            node_builder(2, calls=[("debug", "different debug input", "fixed")], buggy=False, score=0.8, parents=(1,)),
        ],
    )
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)

    groups = read_jsonl(tmp_path / "out" / groupdata.GROUPS_FILE)
    samples = read_jsonl(tmp_path / "out" / groupdata.SAMPLES_FILE)
    assert len(groups) == 1
    assert groups[0]["size"] == 1
    assert len(groups[0]["members"][0]["sample_ids"]) == 2
    assert {sample["group_id"] for sample in samples} == {groups[0]["group_id"]}
    assert groups[0]["members"][0]["sample_id"] == samples[0]["sample_id"]


def test_groups_never_cross_environments(tmp_path, node_builder, run_writer):
    # Two seeds of the same prompt, but one ran with different hardware/limits.
    run_writer(
        tmp_path / "batch",
        "run-a",
        [node_builder(1, calls=[("draft", "same prompt", "solution")], buggy=False, score=0.6)],
        hardware="A100",
    )
    run_writer(
        tmp_path / "batch",
        "run-b",
        [node_builder(1, calls=[("draft", "same prompt", "solution")], buggy=False, score=0.7)],
        hardware="RTX 3090",
    )
    manifest = build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    assert manifest["environment_mixed"] is True
    groups = read_jsonl(tmp_path / "out" / groupdata.GROUPS_FILE)
    assert len(groups) == 2
    assert all(group["size"] == 1 for group in groups)


def test_same_environment_across_seeds_is_grouped(tmp_path, node_builder, run_writer):
    # The useful case: two seeds of one experiment set answering the same prompt,
    # where the first draft of the second seed only ran after a debug step.
    run_writer(
        tmp_path / "batch",
        "run-a",
        [node_builder(1, calls=[("draft", "same prompt", "clean")], buggy=False, score=0.9)],
    )
    run_writer(
        tmp_path / "batch",
        "run-b",
        [
            node_builder(1, calls=[("draft", "same prompt", "broken")], buggy=True),
            node_builder(2, calls=[("debug", "fixing it", "clean")], buggy=False, score=0.6, parents=(1,)),
        ],
    )
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    groups = read_jsonl(tmp_path / "out" / groupdata.GROUPS_FILE)
    (draft_group,) = [group for group in groups if group["size"] == 2]
    rewards = {member["run_dir"]: member["episode_reward"] for member in draft_group["members"]}
    assert rewards["run-a"] == pytest.approx((0.9 - 0.5) / 0.3)
    assert rewards["run-b"] == pytest.approx((0.6 - 0.5) / 0.3)
    assert all(member["episode_resolved"] for member in draft_group["members"])


def test_aggregate_then_split_then_views(tmp_path, node_builder, run_writer):
    # batch-one: one prompt answered twice with different outcomes.
    run_writer(
        tmp_path / "batches" / "batch-one",
        "run-a",
        [node_builder(1, calls=[("draft", "shared", "good")], buggy=False, score=0.9)],
    )
    run_writer(
        tmp_path / "batches" / "batch-one",
        "run-b",
        [node_builder(1, calls=[("draft", "shared", "bad")], buggy=False, score=0.5)],
    )
    # batch-two: a different experiment set.
    run_writer(
        tmp_path / "batches" / "batch-two",
        "run-c",
        [node_builder(1, calls=[("draft", "other", "ok")], buggy=False, score=0.6)],
        task="titanic",
    )
    one = build_batch(tmp_path / "batches" / "batch-one", tmp_path / "out" / "one", verbose=False)
    two = build_batch(tmp_path / "batches" / "batch-two", tmp_path / "out" / "two", verbose=False)
    assert one["grpo_ready_groups"] == 1
    assert two["grpo_ready_groups"] == 0

    merged = tmp_path / "merged"
    aggregate([tmp_path / "out" / "one", tmp_path / "out" / "two"], merged, verbose=False)
    assert merged_manifest(merged)["groups"] == 2

    split_summary = assign_dataset_splits(merged, split_by="task", val_fraction=0.5, seed=0, verbose=False)
    splits = groupdata.read_splits(merged)
    assert set(split_summary["group_counts"]) == {"train", "val"}
    assert set(splits.values()) == {"train", "val"}

    sft = to_sft(merged, merged, verbose=False)
    assert sft["rows"] == 2
    sft_rows = {row["task"]: row for row in read_jsonl(merged / "sft.jsonl")}
    assert sft_rows["spaceship-titanic"]["messages"][-1]["content"] == "good"
    assert sft_rows["spaceship-titanic"]["reward"] == pytest.approx((0.9 - 0.5) / 0.3)

    dpo = to_dpo(merged, merged, verbose=False)
    assert dpo["pairs"] == 1
    (pair,) = read_jsonl(merged / "dpo.jsonl")
    assert pair["chosen"]["completion"] == "good"
    assert pair["rejected"]["completion"] == "bad"

    grpo = to_grpo(merged, merged, verbose=False)
    assert grpo["groups"] == 1
    (row,) = read_jsonl(merged / "grpo.jsonl")
    assert [response["completion"] for response in row["responses"]] == ["good", "bad"]
    assert row["responses"][0]["reward"] > row["responses"][1]["reward"]


def merged_manifest(path):
    return groupdata.read_manifest(path)


def test_broken_drafts_still_form_a_preference_pair(tmp_path, node_builder, run_writer):
    # Two seeds at the same draft prompt.  Both drafts are broken; only the
    # first one's debug process ended in a runnable solution.  That is exactly
    # the comparison the episode reward is meant to expose.
    run_writer(
        tmp_path / "batch",
        "run-a",
        [
            node_builder(1, calls=[("draft", "shared", "broken-but-recoverable")], buggy=True),
            node_builder(2, calls=[("debug", "fix", "clean")], buggy=False, score=0.9, parents=(1,)),
        ],
    )
    run_writer(
        tmp_path / "batch",
        "run-b",
        [node_builder(1, calls=[("draft", "shared", "broken-unrecoverable")], buggy=True)],
    )
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    assign_dataset_splits(tmp_path / "out", val_fraction=0.0, verbose=False)

    # SFT still refuses to imitate a draft that never ran; the only runnable
    # solution here is run-a's debug output.
    sft = to_sft(tmp_path / "out", tmp_path / "out", verbose=False)
    assert sft["rows"] == 1
    (row,) = read_jsonl(tmp_path / "out" / "sft.jsonl")
    assert row["messages"][-1]["content"] == "clean"

    # DPO pairs the two drafts and prefers the one whose process was recoverable.
    dpo = to_dpo(tmp_path / "out", tmp_path / "out", verbose=False)
    assert dpo["pairs"] == 1
    (pair,) = read_jsonl(tmp_path / "out" / "dpo.jsonl")
    assert pair["chosen"]["completion"] == "broken-but-recoverable"
    assert pair["chosen"]["reward"] == pytest.approx((0.9 - 0.5) / 0.3)
    assert pair["rejected"]["completion"] == "broken-unrecoverable"
    assert pair["rejected"]["reward"] is None
    assert pair["rejected"]["failed"] is True

    # ... and --require-node-result gives the conservative variant instead.
    conservative = to_dpo(tmp_path / "out", tmp_path / "out", require_node_result=True, verbose=False)
    assert conservative["pairs"] == 0


def test_views_carry_the_canonical_prompt(tmp_path, node_builder, run_writer):
    def package_prompt(packages):
        return (
            "**COMPUTE**: drivers installed, and the following packages installed: "
            f"{packages}. If you need to, feel free to add more."
        )

    run_writer(
        tmp_path / "batch",
        "run-a",
        [node_builder(1, calls=[("draft", package_prompt("`torch`, `numpy`"), "good")], buggy=False, score=0.9)],
    )
    run_writer(
        tmp_path / "batch",
        "run-b",
        [node_builder(1, calls=[("draft", package_prompt("`numpy`, `torch`"), "bad")], buggy=False, score=0.5)],
    )
    manifest = build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    assert manifest["multi_member_groups"] == 1

    assign_dataset_splits(tmp_path / "out", val_fraction=0.0, verbose=False)
    to_sft(tmp_path / "out", tmp_path / "out", verbose=False)
    (row,) = read_jsonl(tmp_path / "out" / "sft.jsonl")
    assert row["messages"][0]["content"] == package_prompt("`numpy`, `torch`")


def test_assign_splits_moves_whole_tasks_and_always_has_val():
    groups = [
        {"group_id": f"g{index}", "task": f"task-{index % 5}", "members": [{"run_dir": f"run-{index}"}]}
        for index in range(20)
    ]
    splits = assign_splits(groups, split_by="task", val_fraction=0.2, seed=0)
    val_tasks = {group["task"] for group in groups if splits[group["group_id"]] == "val"}
    train_tasks = {group["task"] for group in groups if splits[group["group_id"]] == "train"}
    assert val_tasks
    assert not (val_tasks & train_tasks)


def test_assign_splits_of_a_single_task_still_produces_val():
    groups = [
        {"group_id": f"g{index}", "task": "only-task", "members": [{"run_dir": f"run-{index}"}]}
        for index in range(4)
    ]
    assert set(assign_splits(groups, split_by="group", val_fraction=0.1, seed=0).values()) == {"train", "val"}
