import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase1.score_channel_orientation_receipt import OrientationError, load_sources, produce
from phase1.verify_score_channel_orientation_receipt import rebuild


PHASE1 = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> str:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_orientation_receipt_roundtrip_is_result_blind(tmp_path: Path):
    selection = tmp_path / "selection"
    selection.mkdir()
    rows = []
    for index, task in enumerate(("AI4Code", "dog-breed-identification")):
        rows.append({
            "schema_version": "score-channel-parent-selection-row-v1",
            "task": task,
            "run_id": f"run-{index}",
            "parent_id": f"parent-{index}",
            "source_intake": f"intake-{index}",
            "selection_rank_in_run": 1,
            "selection_key_sha256": f"{index + 1:064x}",
            "candidate_card_ids": [f"card-{index}-a", f"card-{index}-b"],
            "candidate_count": 2,
            "candidate_identity_sha256": f"{index + 10:064x}",
        })
    parent_sha = write_jsonl(selection / "selected_parents.jsonl", rows)
    write_json(selection / "summary.json", {
        "protocol": "score-channel-parent-selection-v1",
        "status": "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING",
        "gates": {"parent_gate_pass": True},
        "counts": {"selected_parents": 2},
        "outputs": {"selected_parents_sha256": parent_sha},
    })
    out = tmp_path / "orientation.json"
    source_root = Path(
        subprocess.run(
            ["git", "-C", str(PHASE1), "rev-parse", "--show-toplevel"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    )
    value = produce(
        selection,
        PHASE1 / "task_orientation.json",
        PHASE1 / "score_channel_metric_orientation_supplement_20260818.json",
        source_root,
        out,
    )
    assert value["outcomes_read"] is False
    assert value["orientation"] == {"AI4Code": 1, "dog-breed-identification": -1}
    receipt_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    verified = rebuild(SimpleNamespace(
        selection_dir=selection,
        legacy=PHASE1 / "task_orientation.json",
        supplement=PHASE1 / "score_channel_metric_orientation_supplement_20260818.json",
        orientation=out,
        expect_orientation_sha256=receipt_sha,
    ))
    assert verified["status"] == "VERIFIED_SCORE_CHANNEL_TASK_ORIENTATION"
    assert verified["producer_imported"] is False


def test_orientation_sources_reject_conflicting_overlap(tmp_path: Path):
    legacy = tmp_path / "legacy.json"
    supplement = tmp_path / "supplement.json"
    write_json(legacy, {"task": False})
    write_json(supplement, {
        "protocol": "score-channel-metric-orientation-source-v1",
        "created_before_replay_outcomes": True,
        "outcomes_read": False,
        "tasks": {
            "task": {
                "lower_is_better": True,
                "orientation": -1,
                "leaderboard_rows": 2,
                "leaderboard_sha256": "a" * 64,
            }
        },
    })
    with pytest.raises(OrientationError, match="conflict"):
        load_sources(legacy, supplement)
