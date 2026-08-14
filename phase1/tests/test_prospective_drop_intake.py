from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from phase1.cards import TaskInfo, parse_journal, parse_journal_nodes
from phase1.fixed_decision_scorer import load_blind_manifest, parse_utc
from phase1.prospective_drop_intake import IntakeError, build


START = 1_780_000_000.0


def journal_nodes(code_suffix: str = "") -> list[dict]:
    metric = {
        "competition_id": "spaceship-titanic",
        "is_lower_better": False,
        "gold_threshold": 0.9,
        "silver_threshold": 0.8,
        "bronze_threshold": 0.7,
    }
    return [
        {
            "step": 0,
            "id": "root",
            "code": "",
            "parents": [],
            "creation_time": START,
            "exec_time": 0,
            "exit_code": 0,
            "metric_info": {},
        },
        {
            "step": 1,
            "id": "left",
            "code": f"print('left{code_suffix}')",
            "parents": [0],
            "creation_time": START + 1,
            "exec_time": 3.0,
            "exit_code": 0,
            "operators_used": ["draft"],
            "metric_info": {**metric, "score": 0.82, "validation_score": 0.80},
        },
        {
            "step": 2,
            "id": "right",
            "code": "print('right')",
            "parents": [0],
            "creation_time": START + 2,
            "exec_time": 4.0,
            "exit_code": 0,
            "operators_used": ["improve"],
            "metric_info": {**metric, "score": 0.78, "validation_score": 0.76},
        },
    ]


def journal_blob(nodes: list[dict]) -> bytes:
    return ("\n".join(json.dumps(node, sort_keys=True) for node in nodes) + "\n").encode()


def add_bytes(handle: tarfile.TarFile, name: str, blob: bytes, *, mtime: int = int(START + 30)):
    info = tarfile.TarInfo(name)
    info.size = len(blob)
    info.mtime = mtime
    handle.addfile(info, io.BytesIO(blob))


def make_archive(
    path: Path,
    *,
    live_blob: bytes | None = None,
    journal: bytes | None = None,
    unsafe_name: str | None = None,
    include_checkpoint: bool = True,
    include_live: bool = True,
) -> None:
    blob = journal if journal is not None else journal_blob(journal_nodes())
    root = "drop/run_seed_1"
    with tarfile.open(path, "w:gz") as handle:
        if include_checkpoint:
            add_bytes(handle, f"{root}/checkpoint/journal.jsonl", blob)
        if include_live:
            add_bytes(handle, f"{root}/json/JOURNAL.jsonl", blob if live_blob is None else live_blob)
        fake_secret = "sk" + "-" + "x" * 32
        add_bytes(handle, f"{root}/env_variables.json", json.dumps({"API_KEY": fake_secret}).encode())
        if unsafe_name is not None:
            add_bytes(handle, unsafe_name, b"unsafe")


def make_receipt(path: Path, activated_at: str) -> str:
    path.write_text(
        json.dumps(
            {
                "status": "PROSPECTIVE_SCORER_ACTIVE",
                "protocol": "prospective_decision_v1",
                "activated_at_utc": activated_at,
            }
        ),
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def args_for(drop: Path, receipt: Path, output: Path, receipt_sha: str) -> argparse.Namespace:
    denylist = receipt.parent / "precutoff_endpoint_denylist.csv"
    if not denylist.exists():
        with denylist.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=("card_id", "code_sha256"), lineterminator="\n")
            writer.writeheader()
            writer.writerow({"card_id": "old-card", "code_sha256": "f" * 64})
    denylist_sha = hashlib.sha256(denylist.read_bytes()).hexdigest()
    return argparse.Namespace(
        drop_dir=drop,
        archive_name=None,
        freeze_receipt=receipt,
        precutoff_endpoint_denylist=denylist,
        out_dir=output,
        repo_root=Path(__file__).parents[2],
        expect_freeze_receipt_sha256=receipt_sha,
        _expect_precutoff_endpoint_denylist_sha256=denylist_sha,
        _expect_precutoff_endpoints=1,
        max_archive_bytes=8 * 1024 * 1024,
        max_total_archive_bytes=16 * 1024 * 1024,
        max_member_bytes=1024 * 1024,
        max_members_per_archive=128,
        max_total_member_bytes_per_archive=8 * 1024 * 1024,
        max_total_journal_bytes=8 * 1024 * 1024,
        max_archives=16,
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_intake_never_reads_or_extracts_env_and_emits_fixed_scorer_schema(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    make_archive(drop / "task.tar.gz")
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    output = tmp_path / "intake"

    assert build(args_for(drop, receipt, output, receipt_sha)) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    blind = read_jsonl(output / "eligible_blind_manifest.jsonl")
    pairs = read_jsonl(output / "eligible_structural_pairs.jsonl")
    assert summary["inventory"] == {
        "archives": 1,
        "discovered_run_roots": 1,
        "runs": 1,
        "live_only_runs_excluded": 0,
        "tasks": 1,
        "endpoints": 2,
        "structural_pairs": 1,
        "eligible_runs": 1,
        "eligible_tasks": 1,
        "eligible_endpoints": 2,
        "eligible_structural_pairs": 1,
        "no_scoreable_code_runs": 0,
        "empty_code_nodes_excluded": 0,
    }
    assert summary["security"]["env_members_read"] is False
    assert summary["security"]["env_members_extracted"] is False
    assert len(blind) == 2 and len(pairs) == 1
    assert [row["card_id"] for row in blind] == sorted(row["card_id"] for row in blind)
    assert all(set(row) == {
        "card_id", "task", "run_id", "code", "code_sha256", "lineage",
        "generation_started_at_utc", "source_sha256"
    } for row in blind)
    assert not any("env_variables" in path.name for path in output.rglob("*"))
    output_blob = b"".join(path.read_bytes() for path in output.rglob("*") if path.is_file())
    assert ("sk" + "-" + "x" * 32).encode() not in output_blob

    loaded, audit = load_blind_manifest(
        output / "eligible_blind_manifest.jsonl",
        summary["outputs"]["eligible_blind_manifest_sha256"],
        set(),
        parse_utc("2026-01-01T00:00:00Z"),
    )
    assert len(loaded) == 2 and audit["runs"] == 1


def test_preactivation_run_is_preserved_but_not_eligible(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    make_archive(drop / "task.tar.gz")
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2030-01-01T00:00:00Z")
    output = tmp_path / "intake"

    build(args_for(drop, receipt, output, receipt_sha))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["inventory"]["runs"] == 1
    assert summary["inventory"]["eligible_runs"] == 0
    assert len(read_jsonl(output / "all_blind_views.jsonl")) == 2
    assert read_jsonl(output / "eligible_blind_manifest.jsonl") == []


def test_unlabeled_code_is_scored_and_not_selected_by_label_availability(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    nodes = journal_nodes()
    nodes.append(
        {
            "step": 3,
            "id": "unlabeled",
            "code": "print('still-score-me')",
            "parents": [0],
            "creation_time": START + 3,
            "exec_time": 2.0,
            "exit_code": 1,
            "operators_used": ["debug"],
            "metric_info": {"competition_id": "spaceship-titanic"},
        }
    )
    make_archive(drop / "task.tar.gz", journal=journal_blob(nodes))
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    output = tmp_path / "intake"

    build(args_for(drop, receipt, output, receipt_sha))
    blind = read_jsonl(output / "eligible_blind_manifest.jsonl")
    vault = read_jsonl(output / "label_vault.jsonl")
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert len(blind) == 3
    assert summary["inventory"]["eligible_structural_pairs"] == 3
    unlabeled = next(row for row in vault if row["card_id"].endswith("__unlabeled"))
    assert unlabeled["graded"] is None and unlabeled["y_norm"] is None
    assert summary["blindness"]["labels_used_for_endpoint_selection"] is False


def test_completed_run_without_scoreable_code_remains_in_flow_audit(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    nodes = journal_nodes()
    nodes[1]["code"] = ""
    nodes[2]["code"] = ""
    make_archive(drop / "task.tar.gz", journal=journal_blob(nodes))
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    output = tmp_path / "intake"

    build(args_for(drop, receipt, output, receipt_sha))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    provenance = json.loads((output / "source_provenance.json").read_text(encoding="utf-8"))
    assert summary["inventory"]["runs"] == 1
    assert summary["inventory"]["eligible_runs"] == 1
    assert summary["inventory"]["eligible_endpoints"] == 0
    assert summary["inventory"]["no_scoreable_code_runs"] == 1
    assert provenance[0]["flow_status"] == "no_scoreable_code"
    assert provenance[0]["endpoints"] == 0


def test_non_tree_parent_order_fails_closed(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    nodes = journal_nodes()
    nodes[1]["parents"] = [2]
    make_archive(drop / "task.tar.gz", journal=journal_blob(nodes))
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    output = tmp_path / "intake"

    with pytest.raises(IntakeError, match="parent step must precede"):
        build(args_for(drop, receipt, output, receipt_sha))
    assert not output.exists()


def test_distinct_live_event_log_is_not_read_and_checkpoint_remains_authoritative(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    make_archive(
        drop / "task.tar.gz",
        live_blob=journal_blob(journal_nodes(code_suffix="different")),
    )
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    output = tmp_path / "intake"

    build(args_for(drop, receipt, output, receipt_sha))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["inventory"]["runs"] == 1
    assert summary["security"]["live_event_journal_members_read"] is False
    assert all("different" not in row["code"] for row in read_jsonl(output / "all_blind_views.jsonl"))


def test_live_only_incomplete_run_is_audited_and_excluded(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    make_archive(drop / "completed.tar.gz")
    make_archive(
        drop / "live-only.tar.gz",
        journal=journal_blob(journal_nodes(code_suffix="live-only")),
        include_checkpoint=False,
        include_live=True,
    )
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    output = tmp_path / "intake"

    build(args_for(drop, receipt, output, receipt_sha))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["inventory"]["discovered_run_roots"] == 2
    assert summary["inventory"]["runs"] == 1
    assert summary["inventory"]["live_only_runs_excluded"] == 1


def test_explicit_archive_selection_is_exact_and_auditable(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    make_archive(drop / "selected.tar.gz")
    make_archive(
        drop / "late.tar.gz",
        journal=journal_blob(journal_nodes(code_suffix="late")),
    )
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    arguments = args_for(drop, receipt, tmp_path / "intake", receipt_sha)
    arguments.archive_name = ["selected.tar.gz"]

    build(arguments)
    summary = json.loads((arguments.out_dir / "summary.json").read_text(encoding="utf-8"))
    with (arguments.out_dir / "archive_manifest.tsv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        manifest = list(csv.DictReader(handle, delimiter="\t"))
    assert summary["inventory"]["archives"] == 1
    assert summary["configuration"]["archive_selection"] == "explicit_names"
    assert summary["configuration"]["selected_archive_names"] == ["selected.tar.gz"]
    assert [row["name"] for row in manifest] == ["selected.tar.gz"]
    assert all("late" not in row["code"] for row in read_jsonl(
        arguments.out_dir / "all_blind_views.jsonl"
    ))


@pytest.mark.parametrize(
    "names,match",
    [
        (["selected.tar.gz", "selected.tar.gz"], "must be unique"),
        (["../selected.tar.gz"], "safe tar.gz basename"),
        (["missing.tar.gz"], "is missing"),
    ],
)
def test_explicit_archive_selection_fails_closed(
    tmp_path: Path, names: list[str], match: str
):
    drop = tmp_path / "drop"
    drop.mkdir()
    make_archive(drop / "selected.tar.gz")
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    arguments = args_for(drop, receipt, tmp_path / "intake", receipt_sha)
    arguments.archive_name = names

    with pytest.raises(IntakeError, match=match):
        build(arguments)
    assert not arguments.out_dir.exists()


def test_credential_in_journal_fails_before_json_parse(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    nodes = journal_nodes()
    nodes[1]["code"] = " " + "sk" + "-" + "y" * 32
    make_archive(drop / "task.tar.gz", journal=journal_blob(nodes))
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    output = tmp_path / "intake"

    with pytest.raises(IntakeError, match="before JSON parse"):
        build(args_for(drop, receipt, output, receipt_sha))
    assert not output.exists()


def test_unsafe_tar_member_fails_closed(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    make_archive(drop / "task.tar.gz", unsafe_name="../escape.txt")
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    output = tmp_path / "intake"

    with pytest.raises(IntakeError, match="unsafe tar member path"):
        build(args_for(drop, receipt, output, receipt_sha))
    assert not output.exists()


def test_precutoff_endpoint_or_code_overlap_fails_closed(tmp_path: Path):
    drop = tmp_path / "drop"
    drop.mkdir()
    make_archive(drop / "task.tar.gz")
    receipt = tmp_path / "receipt.json"
    receipt_sha = make_receipt(receipt, "2026-01-01T00:00:00Z")
    arguments = args_for(drop, receipt, tmp_path / "intake", receipt_sha)
    code_sha = hashlib.sha256("print('left')".encode()).hexdigest()
    with arguments.precutoff_endpoint_denylist.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("card_id", "code_sha256"), lineterminator="\n")
        writer.writeheader()
        writer.writerow({"card_id": "spaceship-titanic__left", "code_sha256": code_sha})
    arguments._expect_precutoff_endpoint_denylist_sha256 = hashlib.sha256(
        arguments.precutoff_endpoint_denylist.read_bytes()
    ).hexdigest()

    with pytest.raises(IntakeError, match="pre-cutoff endpoint/code overlap"):
        build(arguments)
    assert not arguments.out_dir.exists()


def test_in_memory_parser_matches_file_parser(tmp_path: Path):
    nodes = journal_nodes()
    path = tmp_path / "journal.jsonl"
    path.write_bytes(journal_blob(nodes))
    task = TaskInfo(name="spaceship-titanic", type="tabular", metric="", desc="spaceship-titanic")
    memory = [card.to_json() for card in parse_journal_nodes(nodes, task)]
    filesystem = [card.to_json() for card in parse_journal(str(path), task)]
    assert memory == filesystem
