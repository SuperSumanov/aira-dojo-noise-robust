import json

import pytest

from dojo.analysis_utils.journal_to_fig import aggregate_folder, find_journals, read_journal


@pytest.mark.parametrize("is_lower_better, sign", [(True, -1), (False, 1), (None, 1)])
def test_read_journal_uses_data_and_flattened_metrics(tmp_path, is_lower_better, sign):
    path = tmp_path / "JOURNAL.jsonl"
    nodes = [
        {"creation_time": 100, "metric": None},
        {
            "creation_time": 160,
            "metric": 2.0,
            "metric_info/score": 3.0,
            "metric_info/is_lower_better": is_lower_better,
        },
    ]
    path.write_text(
        "\n".join(json.dumps({"timestamp": 999, "step": index, "data": node}) for index, node in enumerate(nodes))
        + "\nunfinished JSON",
        encoding="utf-8",
    )

    assert read_journal(path) == [
        {"creation_time": 100, "metric": None, "score": None},
        {"creation_time": 160, "metric": sign * 2.0, "score": sign * 3.0},
    ]


def test_aggregate_includes_runs_without_checkpoint_journal(tmp_path):
    journal_paths = []
    for run_name, nodes in [
        ("failed", [{"creation_time": 100, "metric": None}, {"creation_time": 160, "metric": None}]),
        (
            "completed",
            [
                {"creation_time": 200, "metric": None},
                {"creation_time": 260, "metric": 2.0, "metric_info/score": 3.0},
            ],
        ),
    ]:
        path = tmp_path / run_name / "json" / "JOURNAL.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("\n".join(json.dumps({"data": node}) for node in nodes), encoding="utf-8")
        journal_paths.append(path)
    checkpoint = tmp_path / "completed" / "checkpoint" / "journal.jsonl"
    checkpoint.parent.mkdir()
    checkpoint.write_text("{}\n", encoding="utf-8")

    assert find_journals(tmp_path) == sorted(journal_paths)
    times, curves = aggregate_folder(tmp_path, interval=60)
    assert times == [0, 60]
    for name, values in curves.items():
        assert values == [None, 2.0 if "metric" in name else 3.0]
