import json

import pytest

from src.mle_policy.src.data import groupdata
from src.mle_policy.src.data.aggregate_groups import aggregate
from src.mle_policy.src.data.assign_splits import assign_dataset_splits, assign_splits
from src.mle_policy.src.data.build_batch_groups import build_batch
from src.mle_policy.src.data.operator_prompts import system_message
from src.mle_policy.src.data.to_grpo import to_grpo
from src.mle_policy.src.data.to_sft import to_sft


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def user_turn(row):
    """The user message of an SFT row: turn 0 is the operator's system message."""
    assert [message["role"] for message in row["messages"]] == ["system", "user", "assistant"]
    return row["messages"][1]["content"]


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

    grpo = to_grpo(merged, merged, verbose=False)
    assert grpo["groups"] == 1
    (row,) = read_jsonl(merged / "grpo.jsonl")
    assert [response["completion"] for response in row["responses"]] == ["good", "bad"]
    assert row["responses"][0]["reward"] > row["responses"][1]["reward"]
    assert [turn["role"] for turn in row["responses"][0]["messages"]] == ["assistant"]


def test_grpo_keeps_the_complete_episode_and_uses_earliest_group_prompt(
    tmp_path, node_builder, run_writer
):
    for run, root_completion, debug_prompt, debug_completion in (
        ("run-a", "root-a", "debug prompt a", "debug-a"),
        ("run-b", "root-b", "debug prompt b", "debug-b"),
    ):
        run_writer(
            tmp_path / "batch",
            run,
            [
                node_builder(1, calls=[("draft", "shared root", root_completion)], buggy=True),
                node_builder(
                    2,
                    calls=[("debug", debug_prompt, debug_completion)],
                    buggy=False,
                    score=0.6 if run == "run-a" else 0.55,
                    parents=(1,),
                ),
            ],
        )
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    assign_dataset_splits(tmp_path / "out", val_fraction=0.0, verbose=False)

    summary = to_grpo(tmp_path / "out", tmp_path / "out", verbose=False)
    assert summary["groups"] == 1
    (row,) = read_jsonl(tmp_path / "out" / "grpo.jsonl")
    assert row["prompt"][0]["content"] == "shared root"
    by_root = {response["sample_id"]: response for response in row["responses"]}
    assert all(len(response["messages"]) == 3 for response in by_root.values())
    assert {turn["content"] for response in by_root.values() for turn in response["messages"]} >= {
        "root-a",
        "debug-a",
        "root-b",
        "debug-b",
    }


def test_views_use_unresolved_episode_as_earliest_prompt(tmp_path, node_builder, run_writer):
    # The earliest episode is unresolved, but its prompt is still the group's
    # initial input and must be used for the two later resolved episodes.  The
    # SFT row drops the search memory from it; GRPO keeps the prompt as recorded
    # and is where the "earliest prompt" rule stays observable.
    run_writer(
        tmp_path / "batch",
        "run-earliest",
        [node_builder(0, calls=[("draft", "shared root\n# PREVIOUSLY EXPLORED IMPROVEMENT IDEAS\nold\n# DATA OVERVIEW\nsame", "bad")], buggy=True)],
    )
    for run, completion, score in (("run-a", "good-a", 0.9), ("run-b", "good-b", 0.8)):
        run_writer(
            tmp_path / "batch",
            run,
                [node_builder(1, calls=[("draft", "shared root\n# DATA OVERVIEW\nsame", completion)], buggy=False, score=score)],
        )
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    assign_dataset_splits(tmp_path / "out", val_fraction=0.0, verbose=False)

    to_sft(tmp_path / "out", tmp_path / "out", verbose=False)
    (sft_row,) = read_jsonl(tmp_path / "out" / "sft.jsonl")
    assert user_turn(sft_row) == "shared root\n# DATA OVERVIEW\nsame"

    to_grpo(tmp_path / "out", tmp_path / "out", verbose=False)
    (grpo_row,) = read_jsonl(tmp_path / "out" / "grpo.jsonl")
    assert grpo_row["prompt"][0]["content"].startswith("shared root\n# PREVIOUSLY")


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

    # SFT keeps the complete best episode, including its broken root and the
    # debug action that eventually ran.
    sft = to_sft(tmp_path / "out", tmp_path / "out", verbose=False)
    assert sft["rows"] == 2
    rows = read_jsonl(tmp_path / "out" / "sft.jsonl")
    assert [row["messages"][-1]["content"] for row in rows] == ["broken-but-recoverable", "clean"]


def test_to_sft_drops_the_search_memory_of_proposals_only(tmp_path, node_builder, run_writer):
    # draft/improve prompts list what the search already tried; that memory is
    # not part of the training target.  The debug prompt is the fix's context
    # (code + error) and must survive untouched.
    memory = "# PREVIOUSLY EXPLORED IMPROVEMENT IDEAS\n- tried a linear model\n\n"
    run_writer(
        tmp_path / "batch",
        "run-a",
        [
            node_builder(
                1,
                calls=[("improve", f"task\n{memory}# DATA OVERVIEW\ndraft me one", "broken")],
                buggy=True,
            ),
            node_builder(
                2,
                calls=[("debug", f"task\n{memory}# DATA OVERVIEW\ndraft me one\nTraceback: boom", "fixed")],
                buggy=False,
                score=0.9,
                parents=(1,),
            ),
        ],
    )
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    assign_dataset_splits(tmp_path / "out", val_fraction=0.0, verbose=False)
    to_sft(tmp_path / "out", tmp_path / "out", verbose=False)

    rows = {row["operator"]: row for row in read_jsonl(tmp_path / "out" / "sft.jsonl")}
    assert set(rows) == {"improve", "debug"}
    improve_prompt = user_turn(rows["improve"])
    assert "PREVIOUSLY EXPLORED" not in improve_prompt
    # only the memory section went away
    assert improve_prompt == "task\n# DATA OVERVIEW\ndraft me one"
    debug_prompt = user_turn(rows["debug"])
    assert debug_prompt.startswith(f"task\n{memory}# DATA OVERVIEW")


def test_to_sft_restores_the_operator_system_message(tmp_path, node_builder, run_writer):
    # The OpenAI-protocol clients recorded everything in one system turn, so the
    # operator's system message has to come back from its dojo config.
    run_writer(
        tmp_path / "batch",
        "run-a",
        [node_builder(1, calls=[("draft", "task description", "solution")], buggy=False, score=0.9)],
    )
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    assign_dataset_splits(tmp_path / "out", val_fraction=0.0, verbose=False)
    to_sft(tmp_path / "out", tmp_path / "out", verbose=False)

    (row,) = read_jsonl(tmp_path / "out" / "sft.jsonl")
    assert [message["role"] for message in row["messages"]] == ["system", "user", "assistant"]
    assert row["messages"][0]["content"] == system_message("draft")
    assert user_turn(row) == "task description"


def test_to_sft_keeps_a_recorded_system_message(tmp_path, node_builder, run_writer):
    # Runs that did record the conversation keep their own system message.
    node = node_builder(1, calls=[("draft", "ignored", "solution")], buggy=False, score=0.9)
    node["operators_metrics"][0]["prompt_messages"] = [
        {"role": "system", "content": "recorded system"},
        {"role": "user", "content": "task description"},
    ]
    run_writer(tmp_path / "batch", "run-a", [node])
    build_batch(tmp_path / "batch", tmp_path / "out", verbose=False)
    assign_dataset_splits(tmp_path / "out", val_fraction=0.0, verbose=False)
    to_sft(tmp_path / "out", tmp_path / "out", verbose=False)

    (row,) = read_jsonl(tmp_path / "out" / "sft.jsonl")
    assert [message["content"] for message in row["messages"]] == [
        "recorded system",
        "task description",
        "solution",
    ]


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
    assert user_turn(row) == package_prompt("`numpy`, `torch`")


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
