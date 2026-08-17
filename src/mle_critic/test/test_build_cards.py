import datetime
import json

from src.mle_critic.src.preprocess.download_and_resolve.build_cards import (
    _run_matches_filters,
    build,
)


def write_run(root, run_id, *, hardware):
    run_directory = root / run_id
    checkpoint_directory = run_directory / "checkpoint"
    checkpoint_directory.mkdir(parents=True)
    (run_directory / "dojo_config.json").write_text(
        json.dumps(
            {
                "id": run_id,
                "metadata": {"launch_time": "2026-08-01T12:00:00"},
                "task": {"name": "spaceship-titanic"},
                "solver": {
                    "time_limit_secs": 7200,
                    "execution_timeout": 1200,
                    "operators": {
                        "draft": {
                            "llm": {
                                "client": {"model_id": "openai/gpt-5"}
                            }
                        }
                    },
                },
            }
        )
    )
    (run_directory / "env_variables.json").write_text(
        json.dumps({"HARDWARE": hardware})
    )
    journal_nodes = [
        {
            "step": 0,
            "id": "root",
            "parents": [],
            "metric_info": {"competition_id": "spaceship-titanic"},
        },
        {
            "step": 1,
            "id": "bronze",
            "parents": [0],
            "metric_info": {
                "competition_id": "spaceship-titanic",
                "score": 0.5,
                "bronze_threshold": 0.4,
                "silver_threshold": 0.6,
                "gold_threshold": 0.8,
            },
        },
        {
            "step": 2,
            "id": "gold",
            "parents": [0],
            "metric_info": {
                "competition_id": "spaceship-titanic",
                "score": 0.9,
                "bronze_threshold": 0.4,
                "silver_threshold": 0.6,
                "gold_threshold": 0.8,
            },
        },
    ]
    (checkpoint_directory / "journal.jsonl").write_text(
        "\n".join(json.dumps(node) for node in journal_nodes) + "\n"
    )


def test_run_filters_are_inclusive_and_combined():
    matching_arguments = {
        "run_key": "run-a__2026-08-01",
        "run_time_limit": 7200,
        "run_execution_timeout": 1200,
        "run_client": "openai/gpt-5",
        "run_hardware": "slurm/a100",
        "time_limit": (7200, 7200),
        "execution_timeout": (1200, 1200),
        "client": "gpt-5",
        "hardware": "a100",
        "date_range": (
            datetime.date(2026, 8, 1),
            datetime.date(2026, 8, 1),
        ),
    }
    assert _run_matches_filters(**matching_arguments)

    mismatches = {
        "time_limit": (7201, 8000),
        "execution_timeout": (1201, 2000),
        "client": "claude",
        "hardware": "h100",
        "date_range": (
            datetime.date(2026, 8, 2),
            datetime.date(2026, 8, 3),
        ),
    }
    for field, mismatch in mismatches.items():
        arguments = {**matching_arguments, field: mismatch}
        assert not _run_matches_filters(**arguments)


def test_build_filters_runs_and_reports_medal_rates(tmp_path, capsys):
    write_run(tmp_path, "kept", hardware="slurm/a100")
    write_run(tmp_path, "excluded", hardware="slurm/h100")
    output_path = tmp_path / "cards.json"

    cards_by_run_id = build(
        str(tmp_path),
        str(output_path),
        time_limit=(7200, 7200),
        execution_timeout=(1200, 1200),
        client="gpt-5",
        hardware="a100",
        date=("2026-08-01", "2026-08-01"),
    )

    assert list(cards_by_run_id) == ["kept__2026-08-01"]
    assert len(cards_by_run_id["kept__2026-08-01"]) == 3
    output = capsys.readouterr().out
    assert "3 cards from 1 runs" in output
    assert "medal_rate=66.67% (2/3)" in output
    assert "gold_rate=33.33% (1/3)" in output
