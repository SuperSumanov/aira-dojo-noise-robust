from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path

import pytest

from phase1.score_channel_future_cohort import CohortError, produce
from phase1.verify_score_channel_future_cohort import VerificationError, verify


REPO = Path(__file__).parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_sha(marker: int) -> str:
    return f"{marker:064x}"[-64:]


def journal_sha(marker: int) -> str:
    return hashlib.sha256(f"journal-{marker}".encode()).hexdigest()


def write_source(source: Path, relative: str, size: int, mtime_ns: int) -> Path:
    path = source / Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes([size % 251]) * size)
    os.utime(path, ns=(mtime_ns, mtime_ns))
    assert path.stat().st_size == size
    assert path.stat().st_mtime_ns == mtime_ns
    return path


def protocol_file(
    root: Path,
    archives: list[tuple[str, int, int]],
    *,
    target: int,
    cutoff: int = 100,
) -> tuple[Path, str]:
    value = {
        "protocol": "score-channel-future-identifiability-cohort-v1",
        "status": "FROZEN_OUTCOME_UNREAD_WAITING_COHORT",
        "initial_archives": [
            {"relative_path": name, "size_bytes": size, "mtime_ns": mtime}
            for name, size, mtime in archives
        ],
        "cohort_closure": {
            "start_after_archive_mtime_ns": cutoff,
            "archive_order": [
                "mtime_ns ascending",
                "relative_path UTF-8 byte ascending",
            ],
            "accepted_unique_physical_run_target": target,
            "include_complete_boundary_archive": True,
            "structurally_rejected_archive_counts_toward_target": False,
            "partial_archive_salvage_allowed": False,
            "label_or_score_may_affect_closure": False,
            "append_only_survival_required": True,
        },
        "scope": {
            "gpu_jobs_authorized": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_update": False,
        },
    }
    path = root / "protocol.json"
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return path, digest(path)


def provenance_row(
    relative: str,
    archive_digest: str,
    marker: int,
    *,
    task: str | None = None,
    journal_digest: str | None = None,
) -> dict:
    journal = journal_digest or journal_sha(marker)
    return {
        "run_id": f"journal:{journal}",
        "task": task or f"task-{marker % 3}",
        "generation_started_at_utc": f"2026-08-22T12:{marker % 60:02d}:00Z",
        "eligible": True,
        "archive_name": Path(relative).name,
        "archive_sha256": archive_digest,
        "journal_member": f"run-{marker}/journal.jsonl",
        "journal_mtime": marker,
        "journal_sha256": journal,
        "flow_status": "scoreable",
        "endpoints": 2,
        "empty_code_nodes_excluded": 0,
    }


def make_intake(
    state: Path,
    relative: str,
    marker: int,
    run_markers: list[int],
    size: int,
    *,
    duplicate_journal: str | None = None,
) -> dict:
    archive_digest = archive_sha(marker)
    drop_id = f"drop-{marker}"
    intake = state / "intakes" / drop_id
    intake.mkdir(parents=True)
    provenance = [
        provenance_row(
            relative,
            archive_digest,
            run_marker,
            journal_digest=duplicate_journal,
        )
        for run_marker in run_markers
    ]
    provenance.sort(
        key=lambda row: (
            row["generation_started_at_utc"], row["journal_sha256"], row["run_id"]
        )
    )
    provenance_path = intake / "source_provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = intake / "archive_manifest.tsv"
    manifest.write_text(
        "name\tsize\tsha256\n"
        f"{Path(relative).name}\t{size}\t{archive_digest}\n",
        encoding="utf-8",
    )
    summary = {
        "protocol": "prospective_drop_intake_v1",
        "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
        "configuration": {
            "archive_selection": "explicit_names",
            "selected_archive_names": [Path(relative).name],
        },
        "security": {
            "credential_shaped_journals": 0,
            "env_members_extracted": False,
            "env_members_read": False,
            "journal_scanned_before_json": True,
            "live_event_journal_members_read": False,
            "precutoff_code_sha256_overlap": 0,
            "precutoff_endpoint_id_overlap": 0,
            "raw_journals_written": False,
        },
        "blindness": {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
            "label_values_printed": False,
            "metrics_computed": [],
        },
        "inputs": {"archive_manifest_sha256": digest(manifest)},
        "outputs": {"source_provenance_sha256": digest(provenance_path)},
        "inventory": {"runs": len(provenance)},
    }
    summary_path = intake / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Deliberately invalid outcome-bearing files: successful tests prove neither module opens them.
    (intake / "label_vault.jsonl").write_text("not-json-and-must-not-be-opened\n", encoding="utf-8")
    return {
        "archive_relative_path": relative,
        "archive_sha256": archive_digest,
        "archive_size": size,
        "committed_at_utc": "2026-08-22T18:00:00Z",
        "drop_id": drop_id,
        "intake_dir": str(intake.resolve()),
        "intake_summary_sha256": digest(summary_path),
        "score_dir": str((state / "scores" / drop_id).resolve()),
        "score_summary_sha256": archive_sha(marker + 1000),
    }


def write_snapshot(state: Path, transactions: list[dict]) -> str:
    stage = state / "stage"
    if stage.exists():
        stage = state / f"stage-{len(list((state / 'snapshots').glob('*'))) if (state / 'snapshots').exists() else 1}"
    stage.mkdir(parents=True)
    blob = b"".join(
        (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
        for row in transactions
    )
    (stage / "transactions.jsonl").write_bytes(blob)
    manifest = f"{hashlib.sha256(blob).hexdigest()}  transactions.jsonl\n".encode()
    (stage / "SHA256SUMS").write_bytes(manifest)
    snapshot_sha = hashlib.sha256(manifest).hexdigest()
    snapshot = state / "snapshots" / snapshot_sha
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    stage.rename(snapshot)
    (state / "LATEST").write_text(snapshot_sha + "\n", encoding="ascii")
    return snapshot_sha


def entry(source_path: Path, size: int, mtime_ns: int, *, committed=None, rejected=None) -> dict:
    return {
        "path": str(source_path.resolve()),
        "size": size,
        "mtime_ns": mtime_ns,
        "present": True,
        "baseline": False,
        "committed_archive_sha256": committed,
        "rejected_archive_sha256": rejected,
    }


def write_observations(state: Path, source: Path, entries: dict[str, dict]) -> None:
    value = {
        "protocol": "prospective_archive_observer_v1",
        "source_root": str(source.resolve()),
        "entries": entries,
    }
    (state / "observations.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def fixture_state(
    tmp_path: Path,
    statuses: list[str],
    run_groups: list[list[int]],
    *,
    target: int,
) -> tuple[Path, str, Path, Path, list[dict], dict[str, dict]]:
    state, source = tmp_path / "state", tmp_path / "source"
    state.mkdir()
    archives = [
        (f"0821/archive-{index}.tar.gz", 10 + index, (200 + index) * 1_000_000_000)
        for index in range(len(statuses))
    ]
    protocol, protocol_sha = protocol_file(tmp_path, archives, target=target, cutoff=100)
    transactions: list[dict] = []
    entries: dict[str, dict] = {}
    for index, ((relative, size, mtime_ns), status, runs) in enumerate(
        zip(archives, statuses, run_groups), 1
    ):
        path = write_source(source, relative, size, mtime_ns)
        if status == "committed":
            transaction = make_intake(state, relative, index, runs, size)
            transactions.append(transaction)
            entries[relative] = entry(
                path, size, mtime_ns, committed=transaction["archive_sha256"]
            )
        elif status == "rejected":
            entries[relative] = entry(
                path, size, mtime_ns, rejected=archive_sha(index + 500)
            )
        elif status == "pending":
            entries[relative] = entry(path, size, mtime_ns)
        else:
            raise AssertionError(status)
    write_snapshot(state, transactions)
    write_observations(state, source, entries)
    return protocol, protocol_sha, state, source, transactions, entries


def run_and_verify(
    protocol: Path,
    protocol_sha: str,
    state: Path,
    source: Path,
    output: Path,
    *,
    previous: Path | None = None,
) -> tuple[dict, dict]:
    summary = produce(
        protocol, protocol_sha, state, source, REPO, output, previous
    )
    receipt = verify(
        protocol,
        protocol_sha,
        state,
        source,
        REPO,
        output,
        output.parent / f"{output.name}.verification.json",
        previous,
    )
    return summary, receipt


def test_collecting_uses_only_settled_prefix_and_skips_rejection(tmp_path: Path):
    protocol, protocol_sha, state, source, _, _ = fixture_state(
        tmp_path,
        ["committed", "rejected", "pending"],
        [[1, 2], [], []],
        target=3,
    )
    summary, receipt = run_and_verify(
        protocol, protocol_sha, state, source, tmp_path / "cohort"
    )
    assert summary["status"] == "FUTURE_COHORT_COLLECTING"
    assert summary["inventory"]["selected_physical_runs"] == 2
    assert summary["closure"]["structurally_rejected_in_settled_prefix"] == 1
    assert summary["closure"]["pending_head"]["archive_relative_path"].endswith(
        "archive-2.tar.gz"
    )
    assert summary["blindness"]["label_vault_opened"] is False
    assert summary["blindness"]["score_directory_opened"] is False
    assert receipt["status"] == "PASS_COLLECTING_TRUTH_UNREAD"


def test_boundary_archive_is_included_whole_and_verified(tmp_path: Path):
    protocol, protocol_sha, state, source, _, _ = fixture_state(
        tmp_path,
        ["committed", "rejected", "committed"],
        [[1, 2], [], [3, 4]],
        target=3,
    )
    summary, receipt = run_and_verify(
        protocol, protocol_sha, state, source, tmp_path / "cohort"
    )
    assert summary["status"] == "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
    assert summary["inventory"]["selected_physical_runs"] == 4
    assert summary["closure"]["boundary_archive"].endswith("archive-2.tar.gz")
    archives = [
        json.loads(line)
        for line in (tmp_path / "cohort" / "cohort_archives.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["physical_runs"] for row in archives] == [2, 2]
    assert receipt["status"] == "PASS_IDENTITY_CLOSED_TRUTH_UNREAD"


def test_settled_archive_after_pending_gap_fails_closed(tmp_path: Path):
    protocol, protocol_sha, state, source, _, _ = fixture_state(
        tmp_path,
        ["pending", "committed"],
        [[], [2]],
        target=3,
    )
    with pytest.raises(CohortError, match="settled item after an unresolved gap"):
        produce(protocol, protocol_sha, state, source, REPO, tmp_path / "cohort")


def test_duplicate_physical_run_across_archives_fails(tmp_path: Path):
    protocol, protocol_sha, state, source, transactions, entries = fixture_state(
        tmp_path,
        ["committed", "committed"],
        [[1], [2]],
        target=3,
    )
    duplicate = journal_sha(1)
    second = make_intake(
        state,
        "0821/archive-1.tar.gz",
        22,
        [2],
        11,
        duplicate_journal=duplicate,
    )
    # Preserve the frozen archive content identity while replacing its intake sidecar.
    second["archive_sha256"] = transactions[1]["archive_sha256"]
    manifest = Path(second["intake_dir"]) / "archive_manifest.tsv"
    manifest.write_text(
        "name\tsize\tsha256\narchive-1.tar.gz\t11\t"
        f"{transactions[1]['archive_sha256']}\n",
        encoding="utf-8",
    )
    provenance_path = Path(second["intake_dir"]) / "source_provenance.json"
    rows = json.loads(provenance_path.read_text(encoding="utf-8"))
    rows[0]["archive_sha256"] = transactions[1]["archive_sha256"]
    provenance_path.write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary_path = Path(second["intake_dir"]) / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["inputs"]["archive_manifest_sha256"] = digest(manifest)
    summary["outputs"]["source_provenance_sha256"] = digest(provenance_path)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    second["intake_summary_sha256"] = digest(summary_path)
    second["archive_sha256"] = transactions[1]["archive_sha256"]
    second["drop_id"] = "drop-2-replacement"
    transactions[1] = second
    write_snapshot(state, transactions)
    entries["0821/archive-1.tar.gz"]["committed_archive_sha256"] = transactions[1][
        "archive_sha256"
    ]
    write_observations(state, source, entries)
    with pytest.raises(CohortError, match="physical run appears in multiple"):
        produce(protocol, protocol_sha, state, source, REPO, tmp_path / "cohort")


def test_previous_collecting_output_must_survive_as_exact_prefix(tmp_path: Path):
    protocol, protocol_sha, state, source, transactions, entries = fixture_state(
        tmp_path,
        ["committed", "pending"],
        [[1, 2], []],
        target=5,
    )
    first = tmp_path / "cohort-a"
    run_and_verify(protocol, protocol_sha, state, source, first)

    second_transaction = make_intake(
        state, "0821/archive-1.tar.gz", 2, [3, 4], 11
    )
    transactions.append(second_transaction)
    entries["0821/archive-1.tar.gz"]["committed_archive_sha256"] = second_transaction[
        "archive_sha256"
    ]
    write_snapshot(state, transactions)
    write_observations(state, source, entries)
    second = tmp_path / "cohort-b"
    summary, receipt = run_and_verify(
        protocol, protocol_sha, state, source, second, previous=first
    )
    assert summary["closure"]["append_only_previous"]["exact_prefix_survived"] is True
    assert summary["inventory"]["selected_physical_runs"] == 4
    assert receipt["append_only_previous_reconstructed"] is True


def test_verifier_rejects_tampered_cohort_rows(tmp_path: Path):
    protocol, protocol_sha, state, source, _, _ = fixture_state(
        tmp_path, ["committed"], [[1, 2]], target=3
    )
    output = tmp_path / "cohort"
    produce(protocol, protocol_sha, state, source, REPO, output)
    with (output / "cohort_runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{}\n")
    with pytest.raises(VerificationError, match="schema mismatch"):
        verify(
            protocol,
            protocol_sha,
            state,
            source,
            REPO,
            output,
            tmp_path / "receipt.json",
        )


def test_protocol_or_initial_metadata_change_fails(tmp_path: Path):
    protocol, protocol_sha, state, source, _, _ = fixture_state(
        tmp_path, ["pending"], [[]], target=3
    )
    with pytest.raises(CohortError, match="protocol SHA mismatch"):
        produce(protocol, "f" * 64, state, source, REPO, tmp_path / "bad-hash")
    archive = source / "0821" / "archive-0.tar.gz"
    os.utime(archive, ns=(999_000_000_000, 999_000_000_000))
    with pytest.raises(CohortError, match="source archive metadata differs"):
        produce(protocol, protocol_sha, state, source, REPO, tmp_path / "bad-metadata")


def test_file_open_trace_excludes_archives_labels_code_and_scores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    protocol, protocol_sha, state, source, _, _ = fixture_state(
        tmp_path, ["committed"], [[1, 2]], target=3
    )
    opened: list[Path] = []
    original_open = Path.open

    def audited_open(self: Path, *args, **kwargs):
        opened.append(self.resolve())
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", audited_open)
    run_and_verify(protocol, protocol_sha, state, source, tmp_path / "cohort")
    forbidden = [
        path
        for path in opened
        if path.suffixes[-2:] == [".tar", ".gz"]
        or path.name == "label_vault.jsonl"
        or "scores" in path.parts
        or "all_blind_views.jsonl" == path.name
        or "eligible_blind_manifest.jsonl" == path.name
    ]
    assert forbidden == []


def test_independent_verifier_does_not_import_producer():
    tree = ast.parse(
        (REPO / "phase1" / "verify_score_channel_future_cohort.py").read_text(
            encoding="utf-8"
        )
    )
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )
    assert "phase1.score_channel_future_cohort" not in imported


def test_formal_runner_has_full_preflight_and_forbidden_open_audit():
    script = (
        REPO / "phase1" / "scripts" / "run_score_channel_future_cohort_20260823.sh"
    ).read_text(encoding="utf-8")
    for number in range(1, 14):
        assert f"PREFLIGHT_{number:02d}_" in script
    assert "producer x2 independent verifier x2" in script
    assert "forbidden_open_count" in script
    assert "GPU=0; API=0; model-fit=0" in script
