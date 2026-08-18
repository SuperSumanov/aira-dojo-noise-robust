import json
import re
from pathlib import Path


PHASE1 = Path(__file__).resolve().parents[1]


def test_score_channel_orientation_supplement_is_result_blind_and_consistent():
    supplement = json.loads(
        (PHASE1 / "score_channel_metric_orientation_supplement_20260818.json").read_text(
            encoding="utf-8"
        )
    )
    legacy = json.loads((PHASE1 / "task_orientation.json").read_text(encoding="utf-8"))
    assert supplement["protocol"] == "score-channel-metric-orientation-source-v1"
    assert supplement["created_before_replay_outcomes"] is True
    assert supplement["outcomes_read"] is False
    assert len(supplement["tasks"]) == 11
    for task, row in supplement["tasks"].items():
        assert set(row) == {
            "lower_is_better", "orientation", "leaderboard_rows", "leaderboard_sha256"
        }
        assert type(row["lower_is_better"]) is bool
        assert row["orientation"] == (-1 if row["lower_is_better"] else 1)
        assert type(row["leaderboard_rows"]) is int and row["leaderboard_rows"] > 0
        assert re.fullmatch(r"[0-9a-f]{64}", row["leaderboard_sha256"])
        if task in legacy:
            assert row["lower_is_better"] is legacy[task]
    for key, value in supplement["source"].items():
        if key.endswith("sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", value)
