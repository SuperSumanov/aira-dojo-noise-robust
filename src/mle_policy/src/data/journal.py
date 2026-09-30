"""Read AIRA-Dojo journals and turn them into policy-training samples.

A journal has one line per search-tree node.  Each node records, for every LLM
call it made, the chat prompt that went out and the completion that came back
(``node["operators_metrics"]``).  We turn every call into a *sample*: the prompt,
the completion, and the outcome of the process that the completion started.

Three things about the journal format are easy to get wrong:

* ``parents`` / ``children`` hold **step numbers, not node ids**, and every node
  has at most one parent.
* a node that failed to run is not a dead end.  The solver debugs it right away,
  so the process a proposal starts usually ends several steps later.  We call
  that the node's **episode**.
* a ``debug`` node only ever has one ``debug`` child, so the episode is a
  straight path and does not need a search.

The reward of a sample comes from the *episode*, not from the node: every step
of one debug process shares the score of the runnable solution it ended in.  A
node that never becomes runnable has no reward.  Grouping is also episode
aware: all calls in one episode stay together, and episodes are compared only
when their root steps received the same input.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterator

# Operators whose completion is the solution the node gets scored for.
CODE_OPERATORS = ("draft", "debug", "improve", "crossover")

# The only non-deterministic part of a rendered prompt: draft/debug/improve/
# crossover all do ``random.shuffle(cfg.available_packages)`` before rendering.
PACKAGES_RE_V1 = re.compile(r"(the following packages installed: )([^\n]+?)(\. If you need)")
PACKAGES_RE_V2 = re.compile(r"(the following packages installed: )([^\n]+?)(\. Use only these installed packages)")

# Search memory changes after every sibling is evaluated.  It is useful to the
# model, but should not make otherwise identical decision points separate groups.
# Stop at the next template section; never consume the following data overview.
PREVIOUS_IMPROVEMENT_IDEAS_RE = re.compile(
    r"(?ms)^# PREVIOUSLY EXPLORED IMPROVEMENT IDEAS[ \t]*\n.*?(?=^# DATA OVERVIEW[ \t]*$)"
)
PREVIOUS_IDEAS_RE = re.compile(
    r"(?ms)^# PREVIOUSLY EXPLORED IDEAS[ \t]*\n.*?(?=^# DATA OVERVIEW[ \t]*$)"
)

DEFAULT_JOURNAL_GLOB = "**/journal.jsonl"

# Run settings that decide whether two runs are the same experiment.  The
# environment is part of the group key, so runs that differ in any of these are
# never grouped together even when their prompts happen to line up.
ENV_FIELDS = (
    "task",
    "hardware",
    "time_limit_secs",
    "execution_timeout",
    "num_children",
    "clients",
)


def stable_id(*parts: str) -> str:
    """Return a short deterministic id for the given key parts."""
    return hashlib.blake2b("\x1f".join(parts).encode("utf-8"), digest_size=16).hexdigest()


def canonicalize_packages(text: str) -> str:
    """Sort the shuffled package list inside a rendered prompt."""

    def replace(match: re.Match[str]) -> str:
        packages = re.findall(r"`([^`]+)`", match.group(2))
        if not packages:
            return match.group(0)
        listing = ", ".join(f"`{name}`" for name in sorted(set(packages)))
        return f"{match.group(1)}{listing}{match.group(3)}"

    text = PACKAGES_RE_V1.sub(replace, text)
    text = PACKAGES_RE_V2.sub(replace, text)
    return text


def canonical_prompt(messages: list[dict[str, Any]], normalize_packages: bool) -> list[dict[str, Any]]:
    """Return the prompt in the form the training data should carry."""
    if not normalize_packages:
        return [{"role": message["role"], "content": message["content"]} for message in messages]
    return [
        {"role": message["role"], "content": canonicalize_packages(message["content"])} for message in messages
    ]


def prompt_key(messages: list[dict[str, Any]], normalize_packages: bool) -> str:
    """Hash roles and contents after removing the changing search-memory section."""
    prompt = canonical_prompt(messages, normalize_packages)
    for message in prompt:
        message["content"] = PREVIOUS_IDEAS_RE.sub("", message["content"])
        message["content"] = PREVIOUS_IMPROVEMENT_IDEAS_RE.sub("", message["content"])
    blob = json.dumps(prompt, ensure_ascii=False, sort_keys=True)
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=16).hexdigest()


def find_run_dir(journal_path: Path) -> Path:
    """Walk up from a journal to the run directory that owns it."""
    for candidate in journal_path.parents:
        if (candidate / "dojo_config.json").is_file():
            return candidate
    raise ValueError(f"No dojo_config.json in any parent of {journal_path}")


def read_run_meta(run_dir: Path) -> dict[str, Any]:
    """Read the environment of one run from its ``dojo_config.json``."""
    config_path = run_dir / "dojo_config.json"
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    task_name = config.get("task", {}).get("name")
    if not isinstance(task_name, str) or not task_name:
        raise ValueError(f"Missing task.name in {config_path}")

    solver = config.get("solver", {})
    operators = solver.get("operators", {})
    clients: set[str] = set()
    providers: set[str] = set()
    for operator in operators.values():
        client = operator.get("llm", {}).get("client") if isinstance(operator, dict) else None
        if not isinstance(client, dict):
            continue
        if client.get("model_id"):
            clients.add(str(client["model_id"]))
        if client.get("provider"):
            providers.add(str(client["provider"]))

    hardware = None
    env_path = run_dir / "env_variables.json"
    if env_path.is_file():
        with env_path.open(encoding="utf-8") as handle:
            hardware = json.load(handle).get("HARDWARE")

    metadata = config.get("metadata", {})
    meta = {
        "task": task_name,
        "run_id": config.get("id") or run_dir.name,
        "seed": metadata.get("seed"),
        "launch_time": metadata.get("launch_time"),
        "clients": sorted(clients),
        "providers": sorted(providers),
        "hardware": hardware,
        "time_limit_secs": solver.get("time_limit_secs"),
        "execution_timeout": solver.get("execution_timeout"),
        "num_children": solver.get("num_children"),
    }
    meta["env_signature"] = stable_id(json.dumps({key: meta[key] for key in ENV_FIELDS}, sort_keys=True))
    return meta


def iter_journal_paths(root: Path, pattern: str = DEFAULT_JOURNAL_GLOB) -> Iterator[Path]:
    """Yield every journal below *root*, or *root* itself when it is a file."""
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        raise ValueError(f"Input path does not exist: {root}")
    yield from sorted(root.glob(pattern))


def read_nodes(journal_path: Path) -> list[dict[str, Any]]:
    """Read one journal, validating the parts the pipeline depends on."""
    nodes: list[dict[str, Any]] = []
    with journal_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                node = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON in {journal_path}:{line_number}") from error
            calls = node.get("operators_metrics") or []
            operators = node.get("operators_used") or []
            if len(calls) != len(operators):
                raise ValueError(
                    f"{journal_path}:{line_number}: {len(calls)} operator calls but "
                    f"{len(operators)} operator names"
                )
            nodes.append(node)
    return nodes


def node_operator(node: dict[str, Any]) -> str | None:
    """The operator that produced this node, e.g. ``draft`` or ``debug``."""
    operators = node.get("operators_used") or []
    return operators[0] if operators else None


def resolve_episodes(nodes: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Map every step to the debug episode it belongs to.

    An episode starts at a node whose operator is not ``debug`` (a proposal) and
    follows the single ``debug`` child while the current node is broken.  It ends
    at the first node that ran, or at the node where debugging stopped without a
    runnable result.  ``terminal_step`` is ``None`` in the second case, which
    means the whole episode has no reward.
    """
    by_step: dict[int, dict[str, Any]] = {}
    for node in nodes:
        if node.get("step") is not None:
            by_step[node["step"]] = node
    debug_child: dict[int, int] = {}
    for step in sorted(by_step):
        node = by_step[step]
        for parent in node.get("parents") or []:
            if parent in by_step and node_operator(node) == "debug":
                debug_child[parent] = step

    def walk_up(step: int) -> int:
        seen = {step}
        current = step
        while node_operator(by_step[current]) == "debug":
            parents = by_step[current].get("parents") or []
            if not parents or parents[0] in seen or parents[0] not in by_step:
                return current
            seen.add(parents[0])
            current = parents[0]
        return current

    episodes: dict[int, dict[str, Any]] = {}
    for step in by_step:
        root_step = walk_up(step)
        current = step
        visited = {step}
        while by_step[current].get("is_buggy", True):
            following = debug_child.get(current)
            if following is None or following in visited:
                current = None
                break
            visited.add(following)
            current = following
        episodes[step] = {
            "root_step": root_step,
            "terminal_step": current,
            "steps_to_terminal": len(visited),
        }
    return episodes


def _official_score(node: dict[str, Any], has_result: bool) -> float | None:
    """Official score of the node's submission, or ``None``.

    Only trustworthy for nodes that actually ran: when a node fails, the grader
    re-scores whatever ``submission.csv`` the previous node left behind, so the
    field repeats the earlier value.  See the docs.
    """
    if not has_result:
        return None
    score = (node.get("metric_info") or {}).get("score")
    return None if score is None else float(score)


def reward_from_score(score: float | None, metric_info: dict[str, Any]) -> float | None:
    """Normalise an official score against the competition's own thresholds.

    ``reward = (score - median_threshold) / (gold_threshold - median_threshold)``
    so ``0`` is the Kaggle median and ``1`` is the gold threshold.  The direction
    cancels out of the ratio, so lower-is-better competitions need no special
    case.  Missing or degenerate thresholds yield ``None``; the raw score stays
    in the sample for any other normalisation downstream.
    """
    if score is None:
        return None
    median = metric_info.get("median_threshold")
    gold = metric_info.get("gold_threshold")
    if median is None or gold is None:
        return None
    span = float(gold) - float(median)
    if abs(span) < 1e-12:
        return None
    sign = -1.0 if metric_info.get("is_lower_better") else 1.0
    return (sign * score - sign * float(median)) / (sign * span)


def iter_samples(
    journal_path: Path,
    run_meta: dict[str, Any],
    batch_key: str,
    batch_dir: Path | None = None,
    normalize_packages: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield one sample per recorded LLM call in *journal_path*.

    ``group_id`` is derived from the root step of the sample's episode, not
    from the call itself.  The call-level rows are kept because downstream
    views still need the prompt and completion for each action.
    """
    run_dir = find_run_dir(journal_path)
    run_dir_label = str(run_dir.relative_to(batch_dir)) if batch_dir is not None else str(run_dir)
    nodes = read_nodes(journal_path)
    episodes = resolve_episodes(nodes)
    by_step = {node["step"]: node for node in nodes}
    run_id = run_meta["run_id"]
    env_signature = run_meta["env_signature"]

    for node in nodes:
        calls = node.get("operators_metrics") or []
        if not calls:
            continue
        step = node.get("step")
        has_result = not node.get("is_buggy", True)
        metric_info = node.get("metric_info") or {}
        node_score = _official_score(node, has_result)

        episode = episodes.get(step, {"root_step": step, "terminal_step": None, "steps_to_terminal": 1})
        terminal_step = episode["terminal_step"]
        terminal = by_step.get(terminal_step) if terminal_step is not None else None
        episode_score = (
            _official_score(terminal, not terminal.get("is_buggy", True)) if terminal is not None else None
        )
        episode_reward = reward_from_score(episode_score, (terminal.get("metric_info") or {}) if terminal else {})

        root = by_step.get(episode["root_step"])
        root_calls = (root or {}).get("operators_metrics") or []
        root_messages = root_calls[0].get("prompt_messages") if root_calls else None
        if not isinstance(root_messages, list) or not root_messages:
            # A malformed/incomplete root is unusual, but using the first
            # recorded call keeps the episode available instead of silently
            # dropping it.
            root_messages = None

        for index, call in enumerate(calls):
            messages = call.get("prompt_messages")
            completion = call.get("completion_text")
            if not isinstance(messages, list) or not messages:
                raise ValueError(f"{journal_path}: {run_id} step {step} call {index} has no prompt_messages")
            if not isinstance(completion, str):
                raise ValueError(f"{journal_path}: {run_id} step {step} call {index} has no completion_text")
            for message in messages:
                if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                    raise ValueError(f"{journal_path}: {run_id} step {step} call {index} has a malformed message")

            key = prompt_key(messages, normalize_packages)
            root_key = prompt_key(root_messages, normalize_packages) if root_messages else key
            usage = call.get("usage") or {}
            operator = (node.get("operators_used") or [None] * len(calls))[index]
            yield {
                "sample_id": stable_id(run_id, str(node.get("id")), str(index)),
                "group_id": stable_id(batch_key, env_signature, root_key),
                "prompt_key": key,
                "episode_root_prompt_key": root_key,
                "prompt": [{"role": m["role"], "content": m["content"]} for m in messages],
                "completion": completion,
                "batch": batch_key,
                "env_signature": env_signature,
                "task": run_meta["task"],
                "run_id": run_id,
                "run_dir": run_dir_label,
                "seed": run_meta["seed"],
                "clients": run_meta["clients"],
                "providers": run_meta["providers"],
                "node_id": str(node.get("id")),
                "node_step": step,
                "node_operator": node_operator(node),
                "operator": operator,
                "operator_index": index,
                "is_code_operator": operator in CODE_OPERATORS,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "node_has_result": has_result,
                "node_is_buggy": bool(node.get("is_buggy", True)),
                "exit_code": node.get("exit_code"),
                "node_score": node_score,
                "node_reward": reward_from_score(node_score, metric_info),
                "episode_id": stable_id(run_id, f"episode-{episode['root_step']}"),
                "episode_root_step": episode["root_step"],
                "episode_terminal_step": terminal_step,
                "steps_to_terminal": episode["steps_to_terminal"],
                "episode_score": episode_score,
                "episode_reward": episode_reward,
                "is_lower_better": bool(metric_info.get("is_lower_better")),
                "above_median": metric_info.get("above_median"),
                "any_medal": metric_info.get("any_medal"),
                "source_path": str(journal_path),
            }


def iter_episodes(
    journal_path: Path,
    run_meta: dict[str, Any],
    batch_key: str,
    batch_dir: Path | None = None,
    normalize_packages: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield one record per episode, with all of its call-level samples.

    The episode is the smallest unit passed to grouping.  ``samples`` keeps
    the original call-level records so views can still train on individual
    actions, while ``root_sample_id`` identifies the action that is comparable
    across episodes in the same group.
    """
    episodes: dict[str, dict[str, Any]] = {}
    for sample in iter_samples(
        journal_path,
        run_meta,
        batch_key=batch_key,
        batch_dir=batch_dir,
        normalize_packages=normalize_packages,
    ):
        episode_id = sample["episode_id"]
        episode = episodes.setdefault(
            episode_id,
            {
                "episode_id": episode_id,
                "group_id": sample["group_id"],
                "task": sample["task"],
                "batch": sample["batch"],
                "run_id": sample["run_id"],
                "run_dir": sample["run_dir"],
                "episode_root_step": sample["episode_root_step"],
                "episode_terminal_step": sample["episode_terminal_step"],
                "episode_score": sample["episode_score"],
                "episode_reward": sample["episode_reward"],
                "episode_resolved": sample["episode_terminal_step"] is not None,
                "samples": [],
            },
        )
        if episode["group_id"] != sample["group_id"]:
            raise ValueError(f"Episode {episode_id} has inconsistent group ids")
        episode["samples"].append(sample)

    for episode in episodes.values():
        samples = episode["samples"]
        root_samples = [sample for sample in samples if sample["node_step"] == episode["episode_root_step"]]
        root_sample = root_samples[0] if root_samples else samples[0]
        episode["root_sample_id"] = root_sample["sample_id"]
        episode["root_operator"] = root_sample["operator"]
        episode["root_node_has_result"] = root_sample["node_has_result"]
        episode["root_node_reward"] = root_sample["node_reward"]
        yield episode
