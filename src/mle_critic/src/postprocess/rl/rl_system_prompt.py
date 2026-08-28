"""Build task-specific system prompts for the RL judger."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[5]
AUGMENTED_DATA_DIR = PROJECT_ROOT / "data" / "augmented_mle_critic"
DEFAULT_GAP_FILTER = AUGMENTED_DATA_DIR / "gap_filter.json"
DEFAULT_OUTPUT = AUGMENTED_DATA_DIR / "rl_judger_system_prompts.json"

FIXED_PREFIX = (
    "You are a Kaggle Grandmaster judging two submissions to a high-stakes competition.\n"
    "Carefully consider the task description, the available data, the available compute resources, and the actual quality of two submissions.\n"
    "Your goal is to determine which submission will achieve better performance on the test set. Please first provide a detailed analysis of the strengths and weaknesses of each submission, and then make a final decision on which submission is likely to perform better.\n"
    "Be specific about each step of the submissions, including data processing and feature engineering, the modeling and optimization methods.\n"
    "We will label the submissions as Submission A and Submission B. Please wrap your final decision in \\boxed{}. For example, if you think Submission A is better, you would write: \\boxed{A}.\n"
    "We will provide two documents, task description and data overview, please read it carefully to have a good understanding of the competition."
    "Then, we will also provide the specification on constraints and available compute resources, which should be taken into account. Finally, two solutions will be provided in the user's message."
)


def _read_task_name(journal_path: Path) -> str:
    config_path = journal_path.parent.parent / "dojo_config.json"
    try:
        with config_path.open(encoding="utf-8") as file:
            task_name = json.load(file)["task"]["name"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"Cannot read task name from {config_path}") from error
    if not isinstance(task_name, str) or not task_name:
        raise ValueError(f"Invalid task name in {config_path}")
    return task_name


def _prompt_content(node: dict[str, Any]) -> str | None:
    metrics = node.get("operators_metrics")
    if not isinstance(metrics, list):
        return None
    for metric in metrics:
        if not isinstance(metric, dict) or not isinstance(metric.get("prompt_messages"), list):
            continue
        messages = metric["prompt_messages"]
        users = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        systems = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
        selected = users or systems
        if selected and isinstance(selected[-1].get("content"), str):
            return selected[-1]["content"]
    return None


def _extract_between(content: str, start: str, end: str, path: Path) -> str:
    begin = content.find(start)
    if begin < 0:
        raise ValueError(f"Missing marker {start!r} in {path}")
    finish = content.find(end, begin + len(start))
    if finish < 0:
        raise ValueError(f"Missing marker {end!r} in {path}")
    # Boundary headings are supplied once by the assembled prompt, so keep
    # only the text between them here.
    return content[begin + len(start) : finish].strip()


def _competition_instructions(content: str, path: Path) -> str:
    return _extract_between(
        content, "COMPETITION INSTRUCTIONS", "# PREVIOUSLY EXPLORED IDEAS", path
    )


def _find_initial_content(task_name: str, journal_paths: list[Path]) -> tuple[str, Path]:
    for path in journal_paths:
        if _read_task_name(path) != task_name:
            continue
        try:
            with path.open(encoding="utf-8") as file:
                for line_number, line in enumerate(file, 1):
                    if not line.strip():
                        continue
                    try:
                        node = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise ValueError(f"Invalid JSON in {path}:{line_number}") from error
                    if isinstance(node, dict) and node.get("step") == 1:
                        content = _prompt_content(node)
                        if content is not None:
                            return content, path
        except OSError as error:
            raise ValueError(f"Cannot read journal {path}") from error
    raise ValueError(f"No step-1 prompt found for task {task_name!r}")


def build_prompts(
    runs_root: Path,
    gap_filter_path: Path = DEFAULT_GAP_FILTER,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, str]:
    """Build and save one judger system prompt for every configured task."""
    with gap_filter_path.open(encoding="utf-8") as file:
        tasks = json.load(file)
    if not isinstance(tasks, dict):
        raise ValueError(f"Expected an object mapping task names in {gap_filter_path}")
    journal_paths = sorted(runs_root.glob("**/checkpoint/journal.jsonl"))
    if not journal_paths:
        raise ValueError(f"No checkpoint/journal.jsonl files found below {runs_root}")
    prompts = {}
    for task_name in tasks:
        if not isinstance(task_name, str) or not task_name:
            raise ValueError(f"Invalid task name in {gap_filter_path}: {task_name!r}")
        content, path = _find_initial_content(task_name, journal_paths)
        competition = _competition_instructions(content, path)
        prompts[task_name] = (
            f"{FIXED_PREFIX}\n\n"
            f"# COMPETITION INSTRUCTIONS\n{competition}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(prompts, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return prompts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--gap-filter", type=Path, default=DEFAULT_GAP_FILTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    prompts = build_prompts(args.runs_root, args.gap_filter, args.output)
    print(f"[rl_system_prompt] wrote {len(prompts)} task prompts -> {args.output}")


if __name__ == "__main__":
    main()
