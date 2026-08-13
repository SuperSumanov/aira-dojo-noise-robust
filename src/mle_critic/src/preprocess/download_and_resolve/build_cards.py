"""Build a run-grouped Card dataset from aira-dojo journals.

Every journal node is retained, including the root, empty-code nodes, and unlabeled nodes. The
output is one JSON object whose keys combine ``dojo_config.json["id"]`` and the date part of
``metadata.launch_time`` and whose values are the ordered Cards from the corresponding run.

Usage:
    python -m src.preprocess.download_and_resolve.build_cards RUNS_ROOT OUTPUT.json
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re

from .cards import TaskInfo, parse_journal, save_cards

# competition_id -> featurizer task type (only affects the type one-hot in card_features)
TASK_TYPE = {
    "spaceship-titanic": "tabular",
    "playground-series-s3e18": "tabular",
    "nomad2018-predict-transparent-conductors": "tabular",
    "tabular-playground-series-may-2022": "tabular",
    "tabular-playground-series-dec-2021": "tabular",
    "aerial-cactus-identification": "image-cls",
    "aptos2019-blindness-detection": "image-cls",
    "dog-breed-identification": "image-cls",
    "dogs-vs-cats-redux-kernels-edition": "image-cls",
    "histopathologic-cancer-detection": "image-cls",
    "leaf-classification": "image-cls",
    "denoising-dirty-documents": "image-cls",
    "ranzcr-clip-catheter-line-classification": "image-cls",
    "chaii-hindi-and-tamil-question-answering": "nlp",
    "spooky-author-identification": "nlp",
    "random-acts-of-pizza": "nlp",
    "google-quest-challenge": "nlp",
    "text-normalization-challenge-english-language": "nlp",
    "text-normalization-challenge-russian-language": "nlp",
    "tweet-sentiment-extraction": "nlp",
    "learning-agency-lab-automated-essay-scoring-2": "nlp",
    "us-patent-phrase-to-phrase-matching": "nlp",
    "kuzushiji-recognition": "image-cls",
    "petfinder-pawpularity-score": "image-cls",
    "whale-categorization-playground": "image-cls",
    "mlsp-2013-birds": "image-cls",
}


def _read_competition_id(journal_path: str):
    """Return the first competition id recorded in a journal, or None if none can be read."""
    try:
        with open(journal_path) as journal_file:
            for line in journal_file:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                metric_info = json.loads(stripped_line).get("metric_info") or {}
                if metric_info.get("competition_id"):
                    return metric_info["competition_id"]
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _read_run_config(journal_path: str) -> dict:
    """Read the dojo_config.json beside the journal's parent directory."""
    run_directory = os.path.dirname(os.path.dirname(journal_path))
    config_path = os.path.join(run_directory, "dojo_config.json")
    try:
        with open(config_path) as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read run config for journal {journal_path}: {config_path}") from error

    run_id = config.get("id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError(f"Missing non-empty string 'id' in {config_path}")
    return config


def _make_run_key(run_config: dict) -> str:
    """Build ``<id>__<YYYY-MM-DD>`` from the run config."""
    launch_time = (run_config.get("metadata") or {}).get("launch_time")
    if not isinstance(launch_time, str):
        raise ValueError("Missing string 'metadata.launch_time' in dojo_config.json")

    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", launch_time)
    if date_match is None:
        raise ValueError(f"Invalid metadata.launch_time: {launch_time!r}")
    launch_date = date_match.group(1)
    try:
        datetime.date.fromisoformat(launch_date)
    except ValueError as error:
        raise ValueError(f"Invalid date in metadata.launch_time: {launch_time!r}") from error
    return f"{run_config['id']}__{launch_date}"


def build(runs_root: str, out_path: str, tasks=None):
    # checkpoint/journal.jsonl is the single authoritative source for every run.
    journal_paths = sorted(
        glob.glob(
            os.path.join(runs_root, "**", "checkpoint", "journal.jsonl"),
            recursive=True,
        )
    )

    cards_by_run_id = {}
    scanned_journal_count = 0
    total_card_count = 0
    for journal_path in journal_paths:
        run_config = _read_run_config(journal_path)
        run_key = _make_run_key(run_config)
        competition_id = _read_competition_id(journal_path)
        if competition_id is None:
            competition_id = (run_config.get("task") or {}).get("name")
        if not isinstance(competition_id, str) or not competition_id:
            raise ValueError(
                f"Cannot determine competition id from journal or dojo_config.json: {journal_path}"
            )
        if tasks and competition_id not in tasks:
            continue
        scanned_journal_count += 1
        if run_key in cards_by_run_id:
            raise ValueError(
                f"Duplicate run key {run_key!r}: the id/launch-date pair must identify one run"
            )
        task = TaskInfo(
            name=competition_id,
            type=TASK_TYPE.get(competition_id, "tabular"),
            metric="",
            desc=competition_id,
        )
        run_cards = parse_journal(journal_path, task)
        cards_by_run_id[run_key] = run_cards
        total_card_count += len(run_cards)

    save_cards(cards_by_run_id, out_path)
    print(
        f"[build_cards] {total_card_count} cards from {scanned_journal_count} runs -> {out_path}"
    )
    return cards_by_run_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs_root")
    parser.add_argument("out_path")
    parser.add_argument("--tasks", default=None, help="comma-separated competition_ids to keep")
    arguments = parser.parse_args()
    selected_tasks = set(arguments.tasks.split(",")) if arguments.tasks else None
    build(arguments.runs_root, arguments.out_path, selected_tasks)


if __name__ == "__main__":
    main()
