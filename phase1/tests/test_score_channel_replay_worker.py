import hashlib
import json
from pathlib import Path

import pytest

import phase1.score_channel_replay_worker as worker
from phase1.score_channel_replay_worker import (
    APPROVAL_PROTOCOL,
    MANIFEST_SCHEMA,
    ReplayError,
    artifact_stats,
    load_approval,
    load_manifest,
    parse_val,
    verify_environment,
)


SOURCE_COMMIT = "a" * 40


def write_jsonl(path: Path, rows: list[dict]) -> str:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_row(code: str = "print('ok')") -> dict:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "card_id": "task__card",
        "competition": "task",
        "task": "task",
        "run_id": "journal:" + "1" * 64,
        "parent": "task__parent",
        "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "source_intake": "intake",
        "selection_rank_in_run": 1,
        "shard_id": 2,
        "cap_seconds": 120,
    }


def approval(path: Path, shard_sha: str) -> str:
    value = {
        "protocol": APPROVAL_PROTOCOL,
        "approved": True,
        "cap_seconds": 120,
        "gpus_per_shard": 1,
        "shards": 4,
        "base_llm_update": False,
        "llm_api_calls": 0,
        "worker_source_commit": SOURCE_COMMIT,
        "online_hf": True,
        "fresh_workspace_per_candidate": True,
        "container_image_path": "/frozen/image.sif",
        "container_image_size": 1,
        "container_image_mtime_ns": 1,
        "data_dir": "/frozen/data",
        "grader_path": "/frozen/mlebench",
        "grader_sha256": "6" * 64,
        "shard_sha256": {"2": shard_sha},
        "replay_manifest_sha256": "2" * 64,
        "replay_summary_sha256": "3" * 64,
        "planned_candidate_replays": 10,
        "cap_upper_bound_gpu_hours": 1.0,
        "user_approval_recorded_at_utc": "2026-08-18T00:00:00Z",
    }
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_and_approval_are_hash_and_shard_bound(tmp_path: Path):
    manifest = tmp_path / "shard.jsonl"
    manifest_sha = write_jsonl(manifest, [manifest_row()])
    rows, shard, actual = load_manifest(manifest, manifest_sha)
    assert len(rows) == 1 and shard == 2 and actual == manifest_sha

    receipt = tmp_path / "approval.json"
    receipt_sha = approval(receipt, manifest_sha)
    value, actual_approval = load_approval(
        receipt, receipt_sha, manifest_sha, shard, SOURCE_COMMIT
    )
    assert value["approved"] is True and actual_approval == receipt_sha


def test_manifest_rejects_code_sha_and_credentials(tmp_path: Path):
    bad_sha = manifest_row()
    bad_sha["code_sha256"] = "0" * 64
    path = tmp_path / "bad_sha.jsonl"
    digest = write_jsonl(path, [bad_sha])
    with pytest.raises(ReplayError, match="code SHA mismatch"):
        load_manifest(path, digest)

    secret = manifest_row("token = '" + "sk-" + "a" * 22 + "'")
    path = tmp_path / "secret.jsonl"
    digest = write_jsonl(path, [secret])
    with pytest.raises(ReplayError, match="credential-shaped"):
        load_manifest(path, digest)


def test_approval_rejects_wrong_shard_binding(tmp_path: Path):
    receipt = tmp_path / "approval.json"
    receipt_sha = approval(receipt, "4" * 64)
    with pytest.raises(ReplayError, match="does not bind"):
        load_approval(receipt, receipt_sha, "5" * 64, 2, SOURCE_COMMIT)


def test_parser_prefers_last_keyed_over_bare():
    text = "score=0.99\nvalidation auc: 0.71\nCV F1 = 0.73\nscore=0.01"
    assert parse_val(text) == (0.73, "keyed")
    assert parse_val("nothing useful") == (None, None)


def test_artifact_stats_hashes_header_and_counts_unterminated_last_line(tmp_path: Path):
    submission = tmp_path / "submission.csv"
    submission.write_bytes(b"id,pred\r\n1,0.5\n2,0.7")
    size, digest, lines, header_digest = artifact_stats(submission)
    assert size == len(submission.read_bytes())
    assert digest == hashlib.sha256(submission.read_bytes()).hexdigest()
    assert lines == 3
    assert header_digest == hashlib.sha256(b"id,pred").hexdigest()


def test_environment_is_bound_to_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    image = tmp_path / "image.sif"
    image.write_bytes(b"image")
    data = tmp_path / "data"
    data.mkdir()
    grader = tmp_path / "mlebench"
    grader.write_bytes(b"grader")
    monkeypatch.setattr(worker, "SIF", image)
    value = {
        "container_image_path": str(image),
        "container_image_size": image.stat().st_size,
        "container_image_mtime_ns": image.stat().st_mtime_ns,
        "data_dir": str(data),
        "grader_path": str(grader),
        "grader_sha256": hashlib.sha256(grader.read_bytes()).hexdigest(),
    }
    verify_environment(value, data, grader)
    value["grader_sha256"] = "0" * 64
    with pytest.raises(ReplayError, match="runtime environment differs"):
        verify_environment(value, data, grader)
