import pytest

from src.mle_policy.src.data.journal import (
    canonicalize_packages,
    iter_samples,
    prompt_key,
    read_nodes,
    read_run_meta,
    resolve_episodes,
    reward_from_score,
)

PACKAGE_LINE = (
    "**COMPUTE**: You have access to {hardware} with the appropriate drivers, and the following "
    "packages installed: {packages}. If you need to, feel free to use additional libraries."
)


def prompt_with_packages(packages, hardware="a GPU", task="spaceship-titanic"):
    return PACKAGE_LINE.format(hardware=hardware, packages=packages) + f"\n# TASK\n{task}"


def test_canonicalize_packages_sorts_and_dedupes():
    shuffled = prompt_with_packages("`torch`, `numpy`, `torch`")
    assert canonicalize_packages(shuffled).endswith(
        "packages installed: `numpy`, `torch`. If you need to, feel free to use additional libraries.\n"
        "# TASK\nspaceship-titanic"
    )
    assert canonicalize_packages("no package list here") == "no package list here"


def test_prompt_key_ignores_package_order_only_when_normalising():
    messages = [{"role": "system", "content": prompt_with_packages("`torch`, `numpy`")}]
    same = [{"role": "system", "content": prompt_with_packages("`numpy`, `torch`")}]
    other = [{"role": "system", "content": prompt_with_packages("`numpy`, `torch`", task="titanic")}]
    assert prompt_key(messages, True) == prompt_key(same, True)
    assert prompt_key(messages, False) != prompt_key(same, False)
    assert prompt_key(messages, True) != prompt_key(other, True)


def test_reward_is_direction_aware():
    higher = {"median_threshold": 0.5, "gold_threshold": 0.8, "is_lower_better": False}
    assert reward_from_score(0.9, higher) == pytest.approx((0.9 - 0.5) / 0.3)
    lower = {"median_threshold": 0.35, "gold_threshold": 0.28, "is_lower_better": True}
    # A log loss of 0.25 beats the 0.28 gold line by the same margin.
    assert reward_from_score(0.25, lower) == pytest.approx(1.4285714285714286)
    assert reward_from_score(0.40, lower) < 0
    assert reward_from_score(None, higher) is None
    assert reward_from_score(0.9, {}) is None
    assert reward_from_score(0.9, {"median_threshold": 0.5, "gold_threshold": 0.5}) is None


def test_episode_follows_the_debug_chain(node_builder):
    # 1 draft (broken) -> 2 debug (broken) -> 3 debug (runs, 0.6)
    nodes = [
        node_builder(1, calls=[("draft", "p", "broken draft")], buggy=True),
        node_builder(2, calls=[("debug", "p2", "still broken")], buggy=True, parents=(1,)),
        node_builder(3, calls=[("debug", "p3", "works")], buggy=False, score=0.6, parents=(2,)),
        # 4 draft (broken) but never debugged
        node_builder(4, calls=[("draft", "p", "another broken draft")], buggy=True),
    ]
    episodes = resolve_episodes(nodes)
    assert episodes[1] == {"root_step": 1, "terminal_step": 3, "steps_to_terminal": 3}
    assert episodes[2]["terminal_step"] == 3
    assert episodes[3] == {"root_step": 1, "terminal_step": 3, "steps_to_terminal": 1}
    assert episodes[4]["terminal_step"] is None
    assert episodes[4]["root_step"] == 4


def test_samples_carry_node_and_episode_outcomes(tmp_path, node_builder, run_writer):
    nodes = [
        node_builder(1, calls=[("draft", "same prompt", "broken")], buggy=True),
        node_builder(2, calls=[("debug", "another prompt", "still broken")], buggy=True, parents=(1,)),
        node_builder(3, calls=[("debug", "third prompt", "works")], buggy=False, score=0.6, parents=(2,)),
    ]
    run_writer(tmp_path / "batch", "run-a", nodes)
    journal = next((tmp_path / "batch" / "run-a" / "checkpoint").glob("journal.jsonl"))
    run_meta = read_run_meta(journal.parent.parent)

    samples = {sample["node_step"]: sample for sample in iter_samples(journal, run_meta, batch_key="b")}
    # The broken draft has no score of its own, but its debug process ended at 0.6.
    assert samples[1]["node_score"] is None
    assert samples[1]["episode_terminal_step"] == 3
    assert samples[1]["episode_score"] == 0.6
    assert samples[1]["episode_reward"] == pytest.approx((0.6 - 0.5) / 0.3)
    # The runnable end of the chain scores itself.
    assert samples[3]["node_score"] == 0.6
    assert samples[3]["episode_reward"] == pytest.approx(samples[1]["episode_reward"])
    assert samples[1]["episode_id"] == samples[2]["episode_id"] == samples[3]["episode_id"]


def test_official_score_is_ignored_for_broken_nodes(tmp_path, node_builder, run_writer):
    # A failed node keeps whatever score the previous submission got; it must not
    # be used as the node's own outcome.
    node = node_builder(1, calls=[("draft", "p", "broken")], buggy=True)
    node["metric_info"] = {"score": 0.99, "median_threshold": 0.5, "gold_threshold": 0.8}
    run_writer(tmp_path / "batch", "run-a", [node])
    journal = tmp_path / "batch" / "run-a" / "checkpoint" / "journal.jsonl"
    run_meta = read_run_meta(journal.parent.parent)

    (sample,) = list(iter_samples(journal, run_meta, batch_key="b"))
    assert sample["node_has_result"] is False
    assert sample["node_score"] is None
    assert sample["episode_score"] is None
    assert sample["episode_reward"] is None


def test_read_nodes_rejects_mismatched_operator_counts(tmp_path):
    journal = tmp_path / "journal.jsonl"
    journal.write_text('{"step": 1, "operators_used": ["draft"], "operators_metrics": []}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="operator calls"):
        read_nodes(journal)
