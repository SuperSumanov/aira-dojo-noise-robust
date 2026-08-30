from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import prospective_score_pipeline as pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER_DIR = REPO_ROOT / "phase1" / "results" / "fixed_decision_scorer_v11_20260814"
ENDPOINT_DENYLIST = SCORER_DIR / "precutoff_endpoint_denylist.csv"
ACTIVATED_AT = "2026-08-13T22:19:17.348021Z"


def write_json(path: Path, value: object) -> str:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="",
    )
    return pipeline.sha256(path)


def write_jsonl(path: Path, rows: list[dict]) -> str:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="",
    )
    return pipeline.sha256(path)


def future_rows(tag: str, source_sha: str | None = None) -> list[dict]:
    source = source_sha or hashlib.sha256(f"journal-{tag}".encode()).hexdigest()
    rows = []
    for suffix, op in (("a", "draft"), ("b", "debug")):
        code = f"print('synthetic prospective {tag} {suffix}')\n"
        rows.append(
            {
                "card_id": f"zz-future-{tag}-{suffix}",
                "task": "synthetic-prospective-task",
                "run_id": f"journal:{source}",
                "code": code,
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "lineage": {
                    "depth": 1,
                    "step": 1 if suffix == "a" else 2,
                    "n_siblings": 2,
                    "op": op,
                    "parent": f"root-{tag}",
                },
                "generation_started_at_utc": "2026-08-14T00:00:00Z",
                "source_sha256": source,
            }
        )
    return rows


def make_intake(
    root: Path,
    tag: str,
    rows: list[dict],
    *,
    archive_sha: str | None = None,
    legacy: bool = False,
) -> tuple[Path, str]:
    intake = root / f"intake-{tag}"
    intake.mkdir()
    archive = archive_sha or hashlib.sha256(f"archive-{tag}".encode()).hexdigest()
    archive_manifest = intake / "archive_manifest.tsv"
    archive_manifest.write_text(
        f"name\tsize\tsha256\nsynthetic-{tag}.tar.gz\t123\t{archive}\n",
        encoding="utf-8",
        newline="",
    )
    archive_manifest_sha = pipeline.sha256(archive_manifest)
    manifest_sha = write_jsonl(intake / "eligible_blind_manifest.jsonl", rows)

    if rows:
        source = rows[0]["source_sha256"]
        run_id = rows[0]["run_id"]
        generation = rows[0]["generation_started_at_utc"]
        endpoints = len(rows)
        eligible = True
    else:
        source = hashlib.sha256(f"old-journal-{tag}".encode()).hexdigest()
        run_id = f"journal:{source}"
        generation = "2026-08-13T20:00:00Z"
        endpoints = 1
        eligible = False
    provenance = [
        {
            "archive_name": f"synthetic-{tag}.tar.gz",
            "archive_sha256": archive,
            "eligible": eligible,
            "empty_code_nodes_excluded": 0,
            "endpoints": endpoints,
            "flow_status": "scoreable",
            "generation_started_at_utc": generation,
            "journal_member": f"synthetic-{tag}/checkpoint/journal.jsonl",
            "journal_mtime": 1,
            "journal_sha256": source,
            "run_id": run_id,
            "task": "synthetic-prospective-task",
        }
    ]
    if not legacy:
        provenance[0]["competition_id_source"] = "explicit_journal"
    provenance_sha = write_json(intake / "source_provenance.json", provenance)
    # Deliberately invalid content: opening this file would fail the guarded tests.
    (intake / "label_vault.jsonl").write_text("DO_NOT_OPEN\n", encoding="utf-8")
    empty_sha = hashlib.sha256(b"").hexdigest()
    inventory = {
        "archives": 1,
        "discovered_run_roots": 1,
        "eligible_endpoints": len(rows),
        "eligible_runs": 1 if rows else 0,
        "eligible_structural_pairs": 1 if len(rows) == 2 else 0,
        "eligible_tasks": 1 if rows else 0,
        "empty_code_nodes_excluded": 0,
        "endpoints": endpoints,
        "live_only_runs_excluded": 0,
        "no_scoreable_code_runs": 0,
        "runs": 1,
        "structural_pairs": 1 if endpoints == 2 else 0,
        "tasks": 1,
    }
    if not legacy:
        inventory["archive_consensus_fallback_runs"] = 0
    configuration = (
        {}
        if legacy
        else {
            "archive_consensus_fallback_protocol": pipeline.ARCHIVE_CONSENSUS_PROTOCOL,
            "archive_consensus_fallback_protocol_sha256": (
                pipeline.ARCHIVE_CONSENSUS_PROTOCOL_SHA256
            ),
        }
    )
    summary = {
        "activated_at_utc": ACTIVATED_AT,
        "blindness": {
            "label_values_printed": False,
            "labels_used_for_endpoint_selection": False,
            "labels_used_for_run_selection": False,
            "metrics_computed": [],
        },
        "configuration": configuration,
        "git_commit": (
            pipeline.LEGACY_INTAKE_GIT_COMMIT
            if legacy
            else pipeline.git_commit(REPO_ROOT)
        ),
        "inputs": {
            "archive_manifest_sha256": archive_manifest_sha,
            "drop_dir": str(root),
            "freeze_receipt_sha256": pipeline.ACTIVE_RECEIPT_SHA256,
            "precutoff_endpoint_denylist_sha256": pipeline.PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
        },
        "inventory": inventory,
        "outputs": {
            "all_blind_views_sha256": empty_sha,
            "archive_audits_sha256": empty_sha,
            "eligible_blind_manifest_sha256": manifest_sha,
            "eligible_structural_pairs_sha256": empty_sha,
            "label_vault_sha256": hashlib.sha256(b"opaque synthetic vault").hexdigest(),
            "source_provenance_sha256": provenance_sha,
            "structural_pairs_sha256": empty_sha,
        },
        "protocol": pipeline.INTAKE_PROTOCOL,
        "security": {
            "env_members_read": False,
            "live_event_journal_members_read": False,
            "precutoff_endpoint_id_overlap": 0,
            "precutoff_code_sha256_overlap": 0,
        },
        "selection_rule": "physical run root creation_time strictly after scorer activation",
        "software": {},
        "source_sha256": (
            pipeline.LEGACY_INTAKE_SOURCE_SHA256
            if legacy
            else pipeline.sha256(REPO_ROOT / "phase1" / "prospective_drop_intake.py")
        ),
        "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
    }
    summary_sha = write_json(intake / "summary.json", summary)
    return intake, summary_sha


def score_args(intake: Path, summary_sha: str, out_dir: Path, tag: str) -> argparse.Namespace:
    return argparse.Namespace(
        drop_id=tag,
        repo_root=REPO_ROOT,
        intake_dir=intake,
        expect_intake_summary_sha256=summary_sha,
        scorer_dir=SCORER_DIR,
        precutoff_endpoint_denylist=ENDPOINT_DENYLIST,
        out_dir=out_dir,
        max_endpoints=100,
    )


def registry_args(registry: Path, out_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        repo_root=REPO_ROOT,
        registry=registry,
        out_dir=out_dir,
        max_drops=10,
        max_endpoints=100,
    )


def write_registry(path: Path, entries: list[dict]) -> None:
    write_jsonl(path, entries)


def registry_entry(tag: str, intake: Path, score_dir: Path) -> dict:
    return {
        "drop_id": tag,
        "intake_dir": str(intake),
        "intake_summary_sha256": pipeline.sha256(intake / "summary.json"),
        "score_dir": str(score_dir),
        "score_summary_sha256": pipeline.sha256(score_dir / "summary.json"),
    }


def guard_label_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.open

    def guarded(self: Path, *args, **kwargs):
        if self.name == "label_vault.jsonl":
            raise AssertionError("label vault was opened")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


def require_sklearn() -> None:
    pytest.importorskip("sklearn")


def test_nonempty_active_bundle_roundtrip_and_registry(tmp_path: Path, monkeypatch):
    require_sklearn()
    intake, summary_sha = make_intake(tmp_path, "drop-a", future_rows("drop-a"))
    score_dir = tmp_path / "scores-a"
    guard_label_vault(monkeypatch)
    assert pipeline.score_drop(score_args(intake, summary_sha, score_dir, "drop-a")) == 0
    transaction = json.loads((score_dir / "summary.json").read_text(encoding="utf-8"))
    assert transaction["status"] == "BLIND_DROP_SCORING_COMPLETE"
    assert transaction["security"]["label_vault_opened"] is False
    nested = json.loads((score_dir / "scores" / "summary.json").read_text(encoding="utf-8"))
    assert nested["outputs"]["blind_scores"] == "blind_scores.csv"
    assert nested["audit"]["endpoints"] == 2

    registry = tmp_path / "registry.jsonl"
    write_registry(registry, [registry_entry("drop-a", intake, score_dir)])
    registry_out = tmp_path / "registry-out"
    assert pipeline.validate_registry(registry_args(registry, registry_out)) == 0
    result = json.loads((registry_out / "summary.json").read_text(encoding="utf-8"))
    assert result["status"] == "PROSPECTIVE_SCORE_REGISTRY_VERIFIED"
    assert result["inventory"]["eligible_endpoints"] == 2
    assert result["security"]["label_vault_opened"] is False


def test_zero_eligible_transaction_is_complete_without_nested_scores(tmp_path: Path, monkeypatch):
    intake, summary_sha = make_intake(tmp_path, "old-shadow", [])
    score_dir = tmp_path / "scores-empty"
    guard_label_vault(monkeypatch)
    pipeline.score_drop(score_args(intake, summary_sha, score_dir, "old-shadow"))
    transaction = json.loads((score_dir / "summary.json").read_text(encoding="utf-8"))
    assert transaction["status"] == "NO_ELIGIBLE_ENDPOINTS"
    assert transaction["outputs"]["blind_scores"] is None
    assert not (score_dir / "scores").exists()

    registry = tmp_path / "registry-empty.jsonl"
    write_registry(registry, [registry_entry("old-shadow", intake, score_dir)])
    registry_out = tmp_path / "registry-empty-out"
    pipeline.validate_registry(registry_args(registry, registry_out))
    result = json.loads((registry_out / "summary.json").read_text(encoding="utf-8"))
    assert result["inventory"]["eligible_endpoints"] == 0
    assert result["inventory"]["physical_runs"] == 1


def test_exact_legacy_intake_identity_and_schema_remain_valid(tmp_path: Path, monkeypatch):
    intake, summary_sha = make_intake(tmp_path, "legacy-shadow", [], legacy=True)
    score_dir = tmp_path / "scores-legacy"
    guard_label_vault(monkeypatch)
    assert pipeline.score_drop(
        score_args(intake, summary_sha, score_dir, "legacy-shadow")
    ) == 0
    summary = json.loads((score_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "NO_ELIGIBLE_ENDPOINTS"
    assert summary["inputs"]["intake_source_sha256"] == (
        pipeline.LEGACY_INTAKE_SOURCE_SHA256
    )


def test_extra_label_field_fails_before_formal_output(tmp_path: Path):
    rows = future_rows("leak")
    rows[0]["label"] = {"grade": 1.0}
    intake, summary_sha = make_intake(tmp_path, "leak", rows)
    out_dir = tmp_path / "must-not-exist"
    with pytest.raises(pipeline.PipelineError, match="schema mismatch"):
        pipeline.score_drop(score_args(intake, summary_sha, out_dir, "leak"))
    assert not out_dir.exists()


def test_registry_rejects_tampered_score_csv(tmp_path: Path):
    require_sklearn()
    intake, summary_sha = make_intake(tmp_path, "tamper", future_rows("tamper"))
    score_dir = tmp_path / "scores-tamper"
    pipeline.score_drop(score_args(intake, summary_sha, score_dir, "tamper"))
    score_csv = score_dir / "scores" / "blind_scores.csv"
    score_csv.write_text(score_csv.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    registry = tmp_path / "registry-tamper.jsonl"
    write_registry(registry, [registry_entry("tamper", intake, score_dir)])
    registry_out = tmp_path / "registry-tamper-out"
    with pytest.raises(pipeline.PipelineError, match="CSV SHA mismatch"):
        pipeline.validate_registry(registry_args(registry, registry_out))
    assert not registry_out.exists()


def test_registry_rejects_duplicate_physical_run_across_drops(tmp_path: Path):
    require_sklearn()
    shared_source = hashlib.sha256(b"shared-future-journal").hexdigest()
    intake_a, sha_a = make_intake(
        tmp_path, "dup-a", future_rows("dup-a", shared_source)
    )
    intake_b, sha_b = make_intake(
        tmp_path, "dup-b", future_rows("dup-b", shared_source)
    )
    score_a, score_b = tmp_path / "scores-dup-a", tmp_path / "scores-dup-b"
    pipeline.score_drop(score_args(intake_a, sha_a, score_a, "dup-a"))
    pipeline.score_drop(score_args(intake_b, sha_b, score_b, "dup-b"))
    registry = tmp_path / "registry-dup.jsonl"
    write_registry(
        registry,
        [
            registry_entry("dup-a", intake_a, score_a),
            registry_entry("dup-b", intake_b, score_b),
        ],
    )
    registry_out = tmp_path / "registry-dup-out"
    with pytest.raises(pipeline.PipelineError, match="physical run appears"):
        pipeline.validate_registry(registry_args(registry, registry_out))
    assert not registry_out.exists()
