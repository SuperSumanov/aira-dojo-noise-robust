from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_foreagent_loeo_graph_denoising_formal_20260830.sh"
ADDENDUM = ROOT / "phase1/foreagent_loeo_graph_denoising_execution_addendum_v2.json"


def test_lfs_skip_smudge_is_scoped_to_fresh_worktree_checkout() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    expected = (
        'GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach '
        '"$worktree" "$expected_commit"'
    )
    assert text.count(expected) == 1
    assert '\ngit -C "$repo" worktree add --detach' not in text


def test_execution_addendum_preserves_scientific_contract() -> None:
    value = json.loads(ADDENDUM.read_text(encoding="utf-8"))
    assert value["protocol"] == "foreagent-loeo-graph-denoising-execution-addendum-v2"
    assert value["parent_protocol_sha256"] == (
        "bcd25033e2340a0b98c362ae1fffb29fe39c5222ceb531e5112d4675d7be033c"
    )
    assert value["failed_attempt"]["exit_code"] == 128
    assert value["failed_attempt"]["result_files_created"] == 0
    assert value["scientific_changes"] == []
    assert value["resource_changes"] == []
