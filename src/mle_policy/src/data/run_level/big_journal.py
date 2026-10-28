"""Read one journal as one policy-training episode, retaining every LLM call."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterator

from ..journal import (
    CODE_OPERATORS,
    find_run_dir,
    node_operator,
    prompt_key,
    reward_from_score,
    stable_id,
)


def iter_journal_paths(root: Path) -> Iterator[Path]:
    """Select one journal per run, preferring the complete JSON export."""
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        raise ValueError(f"Input path does not exist: {root}")
    by_run: dict[Path, Path] = {}
    for name in ("journal.jsonl", "JOURNAL.jsonl"):
        for journal in sorted(root.rglob(name)):
            run_dir = find_run_dir(journal)
            previous = by_run.get(run_dir)
            if previous is not None and previous.name == name:
                raise ValueError(f"Multiple {name} files in {run_dir}: {previous}, {journal}")
            by_run[run_dir] = journal
    yield from sorted(by_run.values())


def read_nodes(journal_path: Path) -> list[dict[str, Any]]:
    """Read checkpoint rows or flattened ``JOURNAL.jsonl`` data rows."""
    nodes = []
    with journal_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON in {journal_path}:{line_number}") from error
            node = record.get("data", record)
            if not isinstance(node, dict):
                raise ValueError(f"{journal_path}:{line_number}: node must be an object")
            if len(node.get("operators_metrics") or []) != len(node.get("operators_used") or []):
                raise ValueError(f"{journal_path}:{line_number}: operator calls and names differ in length")
            nodes.append(node)
    return nodes


def metric_info(node: dict[str, Any]) -> dict[str, Any]:
    """Extract grader fields from either supported journal format."""
    if "metric_info" in node:
        return node["metric_info"] or {}
    return {key.split("/", 1)[1]: value for key, value in node.items() if key.startswith("metric_info/")}


def finite_value(value: Any) -> float | None:
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def select_best_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Match Dojo: best non-buggy metric, first recorded node wins a tie."""
    best = None
    best_metric = None
    direction = None
    for node in nodes:
        if node.get("is_buggy", True):
            continue
        value = finite_value(node.get("metric"))
        if value is None:
            continue
        maximize = node.get("metric_maximize")
        if not isinstance(maximize, bool):
            raise ValueError(f"Step {node['step']} has a finite metric but no boolean metric_maximize")
        if direction is not None and maximize != direction:
            raise ValueError("Journal contains inconsistent metric_maximize directions")
        direction = maximize
        if best_metric is None or (value > best_metric if maximize else value < best_metric):
            best, best_metric = node, value
    return best


def iter_samples(
    journal_path: Path,
    run_meta: dict[str, Any],
    batch_key: str,
    batch_dir: Path | None = None,
    normalize_packages: bool = True,
) -> Iterator[dict[str, Any]]:
    """Attach the metric-selected solution's outcome to every call in the run."""
    run_dir = find_run_dir(journal_path)
    run_dir_label = str(run_dir.relative_to(batch_dir)) if batch_dir is not None else str(run_dir)
    nodes = read_nodes(journal_path)
    call_nodes = [node for node in nodes if node.get("operators_metrics")]
    if not call_nodes:
        return
    root = call_nodes[0]
    root_step = root["step"]
    root_messages = root["operators_metrics"][0].get("prompt_messages")
    if not isinstance(root_messages, list) or not root_messages:
        raise ValueError(f"{journal_path}: root call has no prompt_messages")
    root_key = prompt_key(root_messages, normalize_packages)
    best = select_best_node(nodes)
    best_info = metric_info(best) if best is not None else {}
    episode_score = finite_value(best_info.get("score")) if best is not None else None
    episode_metric = finite_value(best["metric"]) if best is not None else None
    episode_reward = reward_from_score(episode_score, best_info)
    episode_metric_reward = reward_from_score(episode_metric, best_info)
    run_id = run_meta["run_id"]
    env_signature = run_meta["env_signature"]
    episode_id = stable_id(batch_key, run_dir_label, run_id, "journal")
    group_id = stable_id(batch_key, env_signature, "journal")

    for node_index, node in enumerate(nodes):
        calls = node.get("operators_metrics") or []
        has_result = not node.get("is_buggy", True)
        info = metric_info(node)
        node_score = finite_value(info.get("score")) if has_result else None
        node_metric = finite_value(node.get("metric")) if has_result else None
        for index, call in enumerate(calls):
            messages = call.get("prompt_messages")
            completion = call.get("completion_text")
            if not isinstance(messages, list) or not messages:
                raise ValueError(f"{journal_path}: step {node['step']} call {index} has no prompt_messages")
            if not isinstance(completion, str):
                raise ValueError(f"{journal_path}: step {node['step']} call {index} has no completion_text")
            if any(
                not isinstance(message, dict)
                or not isinstance(message.get("content"), str)
                or not isinstance(message.get("role"), str)
                for message in messages
            ):
                raise ValueError(f"{journal_path}: step {node['step']} call {index} has a malformed message")
            operator = node["operators_used"][index]
            usage = call.get("usage") or {}
            yield {
                "sample_id": stable_id(episode_id, str(node["id"]), str(index)),
                "group_id": group_id,
                "prompt_key": prompt_key(messages, normalize_packages),
                "episode_root_prompt_key": root_key,
                "prompt": [{"role": message["role"], "content": message["content"]} for message in messages],
                "completion": completion,
                "batch": batch_key,
                "env_signature": env_signature,
                "task": run_meta["task"],
                "run_id": run_id,
                "run_dir": run_dir_label,
                "seed": run_meta["seed"],
                "clients": run_meta["clients"],
                "providers": run_meta["providers"],
                "node_id": str(node["id"]),
                "node_step": node["step"],
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
                "node_metric": node_metric,
                "node_reward": reward_from_score(node_score, info),
                "episode_id": episode_id,
                "episode_root_step": root_step,
                "episode_terminal_step": best["step"] if best is not None else None,
                "steps_to_terminal": len(nodes) - node_index,
                "episode_score": episode_score,
                "episode_metric": episode_metric,
                "episode_reward": episode_reward,
                "episode_metric_reward": episode_metric_reward,
                "is_lower_better": bool(info.get("is_lower_better")),
                "above_median": info.get("above_median"),
                "any_medal": info.get("any_medal"),
                "source_path": str(journal_path),
            }


def iter_episodes(
    journal_path: Path,
    run_meta: dict[str, Any],
    batch_key: str,
    batch_dir: Path | None = None,
    normalize_packages: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield the journal's single episode, including calls after the best node."""
    samples = list(iter_samples(journal_path, run_meta, batch_key, batch_dir, normalize_packages))
    if not samples:
        raise ValueError(f"{journal_path}: journal contains no recorded model calls")
    root = samples[0]
    yield {
        **{key: root[key] for key in (
            "episode_id", "group_id", "task", "batch", "run_id", "run_dir", "episode_root_step",
            "episode_terminal_step", "episode_score", "episode_metric", "episode_reward", "episode_metric_reward",
        )},
        "episode_resolved": root["episode_terminal_step"] is not None,
        "samples": samples,
        "root_sample_id": root["sample_id"],
        "root_operator": root["operator"],
        "root_node_has_result": root["node_has_result"],
        "root_node_reward": root["node_reward"],
    }
