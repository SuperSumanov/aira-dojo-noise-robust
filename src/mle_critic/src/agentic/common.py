"""Shared data contract; no training dependencies."""
import re
from pathlib import Path

TASKS = frozenset({
    "AI4Code", "google-quest-challenge", "learning-agency-lab-automated-essay-scoring-2",
    "spooky-author-identification", "petfinder-pawpularity-score", "whale-categorization-playground",
    "chaii-hindi-and-tamil-question-answering", "dog-breed-identification",
    "random-acts-of-pizza", "tweet-sentiment-extraction",
})


def public_path(root, task):
    if task not in TASKS:
        raise ValueError(f"Unsupported task: {task!r}")
    root = Path(root).resolve()
    path = (root / task / "prepared/public").resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_dir():
        raise ValueError("Public data escaped configured root")
    return path


def final_answer(text):
    # Only the final assistant turn is supplied, never tool observations.
    if "<tool_call>" in text:
        return None
    answers = re.findall(r"\\boxed\{([^{}]*)\}", text)
    if not answers or any(a not in ("A", "B") for a in answers) or len(set(answers)) != 1:
        return None
    return answers[-1]
