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


def _read_hardware(journal_path: str) -> str:
    """Read ``HARDWARE`` from the env_variables.json beside dojo_config.json."""
    run_directory = os.path.dirname(os.path.dirname(journal_path))
    env_variables_path = os.path.join(run_directory, "env_variables.json")
    try:
        with open(env_variables_path) as env_variables_file:
            env_variables = json.load(env_variables_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Cannot read environment variables for journal {journal_path}: "
            f"{env_variables_path}"
        ) from error

    hardware = env_variables.get("HARDWARE")
    if not isinstance(hardware, str) or not hardware:
        raise ValueError(f"Missing non-empty string 'HARDWARE' in {env_variables_path}")
    return hardware


def _read_solver_metadata(run_config: dict, journal_path: str) -> tuple:
    """Extract the Card-level solver metadata required for one run."""
    try:
        solver = run_config["solver"]
        time_limit = solver["time_limit_secs"]
        execution_timeout = solver["execution_timeout"]
        client = solver["operators"]["draft"]["llm"]["client"]["model_id"]
    except (KeyError, TypeError) as error:
        raise ValueError(
            f"Missing required solver metadata in dojo_config.json for journal "
            f"{journal_path}: {error}"
        ) from error

    if not isinstance(time_limit, (int, float)) or isinstance(time_limit, bool):
        raise ValueError(f"Invalid solver.time_limit_secs for journal {journal_path}")
    if not isinstance(execution_timeout, (int, float)) or isinstance(execution_timeout, bool):
        raise ValueError(f"Invalid solver.execution_timeout for journal {journal_path}")
    if not isinstance(client, str) or not client:
        raise ValueError(
            f"Invalid solver.operators.draft.llm.client.model_id for journal {journal_path}"
        )
    return time_limit, execution_timeout, client


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


def _validate_integer_range(
    name: str, value_range: tuple[int, int] | None
) -> tuple[int, int] | None:
    if value_range is None:
        return None
    if len(value_range) != 2 or any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in value_range
    ):
        raise ValueError(f"{name} must contain exactly two integers")
    lower, upper = value_range
    if lower > upper:
        raise ValueError(f"{name} lower bound must not exceed its upper bound")
    return lower, upper


def _validate_date_range(
    date_range: tuple[str, str] | None,
) -> tuple[datetime.date, datetime.date] | None:
    if date_range is None:
        return None
    if len(date_range) != 2 or any(
        not isinstance(value, str) for value in date_range
    ):
        raise ValueError("date must contain exactly two ISO date strings")
    try:
        lower, upper = (datetime.date.fromisoformat(value) for value in date_range)
    except ValueError as error:
        raise ValueError("date values must use YYYY-MM-DD format") from error
    if lower > upper:
        raise ValueError("date lower bound must not exceed its upper bound")
    return lower, upper


def _run_matches_filters(
    run_key: str,
    *,
    run_time_limit: float,
    run_execution_timeout: float,
    run_client: str,
    run_hardware: str,
    time_limit: tuple[int, int] | None,
    execution_timeout: tuple[int, int] | None,
    client: str | None,
    hardware: str | None,
    date_range: tuple[datetime.date, datetime.date] | None,
) -> bool:
    """Return whether one run satisfies all requested collection filters."""
    if time_limit is not None and not (
        time_limit[0] <= run_time_limit <= time_limit[1]
    ):
        return False
    if execution_timeout is not None and not (
        execution_timeout[0] <= run_execution_timeout <= execution_timeout[1]
    ):
        return False
    if client is not None and client not in run_client:
        return False
    if hardware is not None and hardware not in run_hardware:
        return False
    if date_range is not None:
        run_date = datetime.date.fromisoformat(run_key.rsplit("__", 1)[1])
        if not date_range[0] <= run_date <= date_range[1]:
            return False
    return True


def build(
    runs_root: str,
    out_path: str,
    tasks=None,
    time_limit: tuple[int, int] | None = None,
    execution_timeout: tuple[int, int] | None = None,
    client: str | None = None,
    hardware: str | None = None,
    date: tuple[str, str] | None = None,
):
    resolved_time_limit = _validate_integer_range("time_limit", time_limit)
    resolved_execution_timeout = _validate_integer_range(
        "execution_timeout", execution_timeout
    )
    resolved_date_range = _validate_date_range(date)
    if client is not None and not isinstance(client, str):
        raise ValueError("client must be a string")
    if hardware is not None and not isinstance(hardware, str):
        raise ValueError("hardware must be a string")

    # checkpoint/journal.jsonl is the single authoritative source for every run.
    journal_paths = sorted(
        glob.glob(
            os.path.join(runs_root, "**", "checkpoint", "journal.jsonl"),
            recursive=True,
        )
    )

    cards_by_run_id = {}
    counts_by_competition = {}
    scanned_journal_count = 0
    total_card_count = 0
    for journal_path in journal_paths:
        run_config = _read_run_config(journal_path)
        run_key = _make_run_key(run_config)
        time_limit_value, execution_timeout_value, client_value = (
            _read_solver_metadata(run_config, journal_path)
        )
        hardware_value = _read_hardware(journal_path)
        if not _run_matches_filters(
            run_key,
            run_time_limit=time_limit_value,
            run_execution_timeout=execution_timeout_value,
            run_client=client_value,
            run_hardware=hardware_value,
            time_limit=resolved_time_limit,
            execution_timeout=resolved_execution_timeout,
            client=client,
            hardware=hardware,
            date_range=resolved_date_range,
        ):
            continue

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
        run_cards = parse_journal(
            journal_path,
            task,
            time_limit=time_limit_value,
            execution_timeout=execution_timeout_value,
            client=client_value,
            hardware=hardware_value,
        )
        cards_by_run_id[run_key] = run_cards
        card_count = len(run_cards)
        total_card_count += card_count
        competition_counts = counts_by_competition.setdefault(
            competition_id,
            {"cards": 0, "runs": 0, "medals": 0, "golds": 0},
        )
        competition_counts["cards"] += card_count
        competition_counts["runs"] += 1
        for card in run_cards:
            medal_bucket = card.label.medal_bucket if card.label is not None else "none"
            if medal_bucket in {"bronze", "silver", "gold"}:
                competition_counts["medals"] += 1
            if medal_bucket == "gold":
                competition_counts["golds"] += 1

    save_cards(cards_by_run_id, out_path)
    print(
        f"[build_cards] {total_card_count} cards from {scanned_journal_count} runs -> {out_path}"
    )
    print("[build_cards] statistics by competition_id:")
    for competition_id in sorted(counts_by_competition):
        competition_counts = counts_by_competition[competition_id]
        card_count = competition_counts["cards"]
        medal_count = competition_counts["medals"]
        gold_count = competition_counts["golds"]
        medal_rate = medal_count / card_count if card_count else 0.0
        gold_rate = gold_count / card_count if card_count else 0.0
        print(
            f"[build_cards]   {competition_id}: "
            f"{card_count} cards from {competition_counts['runs']} runs, "
            f"medal_rate={medal_rate:.2%} ({medal_count}/{card_count}), "
            f"gold_rate={gold_rate:.2%} ({gold_count}/{card_count})"
        )
    return cards_by_run_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs_root")
    parser.add_argument("out_path")
    parser.add_argument("--tasks", default=None, help="comma-separated competition_ids to keep")
    parser.add_argument(
        "--time-limit",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        help="keep runs whose solver time limit is in the inclusive range",
    )
    parser.add_argument(
        "--execution-timeout",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        help="keep runs whose execution timeout is in the inclusive range",
    )
    parser.add_argument("--client", help="keep runs whose client contains this string")
    parser.add_argument(
        "--hardware", help="keep runs whose hardware contains this string"
    )
    parser.add_argument(
        "--date",
        "--date-range",
        dest="date",
        nargs=2,
        metavar=("START", "END"),
        help="keep runs in the inclusive YYYY-MM-DD launch-date range",
    )
    arguments = parser.parse_args()
    selected_tasks = set(arguments.tasks.split(",")) if arguments.tasks else None
    build(
        arguments.runs_root,
        arguments.out_path,
        selected_tasks,
        time_limit=tuple(arguments.time_limit) if arguments.time_limit else None,
        execution_timeout=(
            tuple(arguments.execution_timeout)
            if arguments.execution_timeout
            else None
        ),
        client=arguments.client,
        hardware=arguments.hardware,
        date=tuple(arguments.date) if arguments.date else None,
    )


if __name__ == "__main__":
    main()
