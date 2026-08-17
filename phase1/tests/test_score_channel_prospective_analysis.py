import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from phase1.score_channel_prospective_analysis import (
    exact_run_sign,
    expected_hit,
    produce,
    summarize,
)
from phase1.verify_score_channel_prospective_analysis import verify


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return _digest(path)


def _jsonl(path: Path, rows: list[dict]) -> str:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    return _digest(path)


def test_expected_top1_credit_handles_signal_and_truth_ties():
    assert expected_hit({"a": 1.0, "b": 1.0}, {"a": 2.0, "b": 1.0}) == 0.5
    assert expected_hit({"a": 2.0, "b": 1.0}, {"a": 2.0, "b": 2.0}) == 1.0


def test_exact_run_sign_aggregates_parents_before_counting():
    rows = [
        {"run_id": "r1", "delta": 1.0},
        {"run_id": "r1", "delta": -0.5},
        {"run_id": "r2", "delta": -1.0},
        {"run_id": "r3", "delta": 0.0},
    ]
    value = exact_run_sign(rows)
    assert value == {
        "positive": 1,
        "negative": 1,
        "tied": 1,
        "informative": 2,
        "exact_p_two_sided": 1.0,
    }


def test_summary_go_and_kill_rules_are_frozen():
    selected = [
        {"run_id": f"r{i}", "parent_id": f"p{i}", "candidate_card_ids": [f"a{i}", f"b{i}"]}
        for i in range(8)
    ]
    replay = [{"card_id": card} for row in selected for card in row["candidate_card_ids"]]
    results = {
        card: {"sub_score": 1.0, "val_how": "keyed"}
        for row in selected for card in row["candidate_card_ids"]
    }
    rows = [
        {
            "run_id": f"r{i}", "parent_id": f"p{i}", "task": f"t{i % 2}",
            "external_top1_credit": 1.0, "stdout_top1_credit": 0.0, "delta": 1.0,
        }
        for i in range(8)
    ]
    go = summarize(rows, selected, replay, results, 100, 20260813)
    assert go["status"] == "SCORE_CHANNEL_MECHANISM_GO"
    killed_rows = [{**row, "external_top1_credit": 0.0, "stdout_top1_credit": 1.0, "delta": -1.0} for row in rows]
    killed = summarize(killed_rows, selected, replay, results, 100, 20260813)
    assert killed["status"] == "SCORE_CHANNEL_MECHANISM_KILL"


def test_primary_and_independent_verifier_match_end_to_end(tmp_path: Path):
    selection_dir = tmp_path / "selection"
    replay_dir = tmp_path / "replay"
    intake_root = tmp_path / "intakes"
    intake = intake_root / "drop"
    for path in (selection_dir, replay_dir, intake):
        path.mkdir(parents=True)

    selected = []
    vault = []
    replay = []
    for index in range(8):
        task = f"task{index % 2}"
        run = f"journal:{index:064x}"
        parent = f"{task}__parent{index}"
        cards = [f"{task}__a{index}", f"{task}__b{index}"]
        selected.append({
            "schema_version": "score-channel-parent-selection-row-v1",
            "task": task, "run_id": run, "parent_id": parent,
            "source_intake": "drop", "selection_rank_in_run": 1,
            "selection_key_sha256": f"{index + 100:064x}",
            "candidate_card_ids": cards, "candidate_count": 2,
            "candidate_identity_sha256": hashlib.sha256(
                json.dumps(cards, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        })
        for rank, card in enumerate(cards):
            vault.append({
                "card_id": card, "task": task, "run_id": run,
                "graded": float(1 - rank), "y_norm": float(1 - rank),
                "eligible_by_start_time": True,
            })
            code = f"print({index * 2 + rank})"
            replay.append({
                "schema_version": "score-channel-replay-candidate-v1",
                "card_id": card, "competition": task, "task": task,
                "run_id": run, "parent": parent, "code": code,
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "source_intake": "drop", "selection_rank_in_run": 1,
                "shard_id": index % 4, "cap_seconds": 120,
            })

    vault_sha = _jsonl(intake / "label_vault.jsonl", vault)
    intake_summary_sha = _json(intake / "summary.json", {
        "protocol": "prospective_drop_intake_v1",
        "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
        "outputs": {"label_vault_sha256": vault_sha},
    })
    selected_sha = _jsonl(selection_dir / "selected_parents.jsonl", selected)
    _json(selection_dir / "summary.json", {
        "protocol": "score-channel-parent-selection-v1",
        "status": "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING",
        "gates": {"parent_gate_pass": True},
        "inputs": {"intake_summary_sha256": {"drop": intake_summary_sha}},
        "outputs": {"selected_parents_sha256": selected_sha},
        "counts": {"selected_parents": 8, "selected_candidates": 16},
    })

    manifest_sha = _jsonl(replay_dir / "replay_manifest.jsonl", replay)
    shard_shas = {}
    shard_counts = {}
    for shard in range(4):
        subset = [row for row in replay if row["shard_id"] == shard]
        shard_shas[str(shard)] = _jsonl(replay_dir / f"shard_{shard}.jsonl", subset)
        shard_counts[str(shard)] = len(subset)
    replay_summary_sha = _json(replay_dir / "summary.json", {
        "protocol": "score-channel-replay-manifest-v1",
        "status": "REPLAY_MANIFEST_FROZEN_APPROVAL_PENDING",
        "matrix": {"cap_seconds": 120, "shards": 4},
        "budget": {"gpu_jobs_submitted": 0, "cap_upper_bound_gpu_hours": 16 * 120 / 3600},
        "inputs": {
            "parent_selection_summary_sha256": _digest(selection_dir / "summary.json"),
            "selected_parents_sha256": selected_sha,
        },
        "outputs": {"replay_manifest_sha256": manifest_sha, "shard_sha256": shard_shas},
        "counts": {
            "planned_candidate_replays": 16,
            "shard_candidate_replays": shard_counts,
        },
    })

    worker_commit = "a" * 40
    approval_path = tmp_path / "approval.json"
    approval_sha = _json(approval_path, {
        "protocol": "score-channel-replay-approval-v1", "approved": True,
        "cap_seconds": 120, "shards": 4, "gpus_per_shard": 1,
        "base_llm_update": False, "llm_api_calls": 0,
        "online_hf": True, "fresh_workspace_per_candidate": True,
        "container_image_path": "/frozen/image.sif",
        "container_image_size": 1, "container_image_mtime_ns": 1,
        "data_dir": "/frozen/data", "grader_path": "/frozen/mlebench",
        "grader_sha256": "6" * 64,
        "worker_source_commit": worker_commit,
        "replay_manifest_sha256": manifest_sha,
        "replay_summary_sha256": replay_summary_sha,
        "shard_sha256": shard_shas, "planned_candidate_replays": 16,
        "cap_upper_bound_gpu_hours": 16 * 120 / 3600,
        "user_approval_recorded_at_utc": "2026-08-18T00:00:00Z",
    })
    orientation_path = tmp_path / "orientation.json"
    orientation_sha = _json(orientation_path, {
        "protocol": "score-channel-task-orientation-v1",
        "outcomes_read": False,
        "orientation": {"task0": 1, "task1": 1},
    })

    result_paths = []
    result_shas = []
    for shard in range(4):
        rows = []
        for manifest in [row for row in replay if row["shard_id"] == shard]:
            success = "__a" in manifest["card_id"]
            rows.append({
                "schema_version": "score-channel-replay-result-row-v1",
                **{key: manifest[key] for key in (
                    "card_id", "competition", "task", "run_id", "parent",
                    "source_intake", "selection_rank_in_run", "shard_id",
                    "cap_seconds", "code_sha256",
                )},
                "rc": 0, "wall_seconds": 1.0,
                "stdout_val": 0.0 if success else 1.0, "val_how": "keyed",
                "stdout_bytes": 1, "stderr_bytes": 0,
                "stdout_sha256": "1" * 64, "stderr_sha256": "2" * 64,
                "sub_exists": True, "submission_bytes": 1,
                "submission_sha256": "3" * 64,
                "submission_line_count": 1,
                "submission_header_sha256": "5" * 64,
                "grader_rc": 0,
                "sub_score": 1.0 if success else 0.0,
                "grader_output_sha256": "4" * 64, "execution_attempts": 1,
                "manifest_sha256": shard_shas[str(shard)],
                "approval_sha256": approval_sha,
                "worker_source_commit": worker_commit,
            })
        path = tmp_path / f"results_{shard}.jsonl"
        result_paths.append(path)
        result_shas.append(_jsonl(path, rows))

    analysis_dir = tmp_path / "analysis"
    args = SimpleNamespace(
        selection_dir=selection_dir, replay_dir=replay_dir, intake_root=intake_root,
        approval=approval_path, expect_approval_sha256=approval_sha,
        orientation=orientation_path, expect_orientation_sha256=orientation_sha,
        result=result_paths, expect_result_sha256=result_shas,
        bootstraps=10_000, seed=20260813, out_dir=analysis_dir,
    )
    primary = produce(args)
    assert primary["status"] == "SCORE_CHANNEL_MECHANISM_GO"
    verified = verify(SimpleNamespace(
        selection_dir=selection_dir, replay_dir=replay_dir, intake_root=intake_root,
        approval=approval_path, expect_approval_sha256=approval_sha,
        orientation=orientation_path, expect_orientation_sha256=orientation_sha,
        result=result_paths, expect_result_sha256=result_shas,
        analysis_dir=analysis_dir,
    ))
    assert verified["status"] == "VERIFIED_SCORE_CHANNEL_PROSPECTIVE_ANALYSIS"
