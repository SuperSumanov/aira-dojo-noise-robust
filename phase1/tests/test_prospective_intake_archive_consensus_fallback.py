from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1/prospective_intake_archive_consensus_fallback_v1.json"


def test_fallback_protocol_is_strict_and_result_blind() -> None:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert value["status"] == "FROZEN_BEFORE_ARCHIVE_STEM_MATCH_READOUT"
    diagnostic = value["result_blind_diagnostic_v1"]
    assert diagnostic["checkpoint_journals"] == 4
    assert diagnostic["journals_with_zero_competition_ids"] == 2
    assert diagnostic["journals_with_one_competition_id"] == 2
    assert diagnostic["journals_with_more_than_one_competition_id"] == 0
    assert diagnostic["global_exact_distinct_competitions"] == 1
    assert diagnostic["labels_outcomes_predictions_accuracy_utility_read"] is False
    assert diagnostic["env_or_key_files_opened"] is False
    rule = value["strict_fallback_rule"]
    assert rule["journal_exact_competition_count_allowed"] == [0, 1]
    assert rule["archive_global_exact_distinct_competitions_must_equal"] == 1
    assert rule["global_normalized_competition_must_equal_normalized_archive_stem"] is True
    assert rule["only_zero-id_journals_may_inherit_archive_consensus"] is True
    assert rule["more_than_one_id_journal_fails_closed"] is True
    assert value["unread_at_freeze"]["archive_stem_match_boolean"] is True
    assert set(value["resources"].values()) == {0}
