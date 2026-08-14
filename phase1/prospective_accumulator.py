#!/usr/bin/env python3
"""Aggregate prospective intake artifacts without opening outcomes or label vaults."""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import itertools
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

from .endpoint_denylist import (
    PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
    PRECUTOFF_ENDPOINTS,
    load_endpoint_denylist,
)


PROTOCOL = "prospective_accumulator_v1"
INTAKE_PROTOCOL = "prospective_drop_intake_v1"
SCORER_PROTOCOL = "prospective_decision_v1"
FREEZE_RECEIPT_SHA256 = "cfab01a80536a50ef21c47ac269c7ce54a11a3b1f0b6daa5700873cbb02ce178"
FIRST_PILOT = 240
FIRST_CONFIRM = 960
SHA256_RX = re.compile(r"[0-9a-f]{64}")
REGISTRY_KEYS = {"drop_id", "intake_dir", "summary_sha256"}
BLIND_KEYS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "generation_started_at_utc",
    "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
PROVENANCE_KEYS = {
    "run_id",
    "task",
    "generation_started_at_utc",
    "eligible",
    "archive_name",
    "archive_sha256",
    "journal_member",
    "journal_mtime",
    "journal_sha256",
    "flow_status",
    "endpoints",
    "empty_code_nodes_excluded",
}
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}
ARCHIVE_AUDIT_KEYS = {
    "archive_name",
    "discovered_run_roots",
    "checkpoint_runs",
    "checkpoint_with_live_event_log",
    "checkpoint_without_live_event_log",
    "live_only_runs_excluded",
    "members",
    "declared_member_bytes",
}
CLOSURE_KEYS = {
    "status",
    "protocol",
    "closed_at_utc",
    "registry_sha256",
    "all_scheduled_runs_uploaded",
    "outcomes_read",
}


class AccumulatorError(RuntimeError):
    pass


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_utc(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AccumulatorError(f"invalid UTC timestamp: {value!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise AccumulatorError(f"timestamp is not explicit UTC: {value!r}")
    return parsed.astimezone(dt.timezone.utc)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def read_bytes(path: Path, opened: list[str]) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise AccumulatorError(f"required input is not a regular non-symlink file: {path}")
    opened.append(path.name)
    return path.read_bytes()


def read_json_value(path: Path, expected_sha: str, opened: list[str]) -> Any:
    blob = read_bytes(path, opened)
    if sha256_bytes(blob) != expected_sha.lower():
        raise AccumulatorError(f"SHA mismatch: {path.name}")
    return json.loads(blob.decode("utf-8"))


def read_json(path: Path, expected_sha: str, opened: list[str]) -> dict[str, Any]:
    value = read_json_value(path, expected_sha, opened)
    if not isinstance(value, dict):
        raise AccumulatorError(f"JSON root is not an object: {path.name}")
    return value


def read_jsonl(path: Path, expected_sha: str, opened: list[str]) -> list[dict[str, Any]]:
    blob = read_bytes(path, opened)
    if sha256_bytes(blob) != expected_sha.lower():
        raise AccumulatorError(f"SHA mismatch: {path.name}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(blob.decode("utf-8").splitlines(), 1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise AccumulatorError(f"JSONL row is not an object: {path.name}:{line_number}")
        rows.append(value)
    return rows


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> str:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    os.replace(temporary, path)
    return sha256(path)


def load_registry(path: Path, opened: list[str]) -> tuple[list[dict[str, Any]], str]:
    blob = read_bytes(path, opened)
    registry_sha = sha256_bytes(blob)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(blob.decode("utf-8").splitlines(), 1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or set(value) != REGISTRY_KEYS:
            raise AccumulatorError(f"registry schema mismatch at line {line_number}")
        drop_id = value["drop_id"]
        if not isinstance(drop_id, str) or not drop_id or any(c in drop_id for c in "\r\n\t"):
            raise AccumulatorError(f"invalid drop_id at line {line_number}")
        if drop_id in seen:
            raise AccumulatorError(f"duplicate drop_id at line {line_number}")
        intake_dir = value["intake_dir"]
        summary_sha = value["summary_sha256"]
        if not isinstance(intake_dir, str) or not Path(intake_dir).is_absolute():
            raise AccumulatorError(f"intake_dir must be absolute at line {line_number}")
        if not isinstance(summary_sha, str) or not SHA256_RX.fullmatch(summary_sha):
            raise AccumulatorError(f"invalid summary SHA at line {line_number}")
        seen.add(drop_id)
        rows.append(value)
    if not rows:
        raise AccumulatorError("empty intake registry")
    return rows, registry_sha


def validate_blind_rows(
    rows: list[dict[str, Any]],
    precutoff_ids: set[str],
    precutoff_code_shas: set[str],
) -> None:
    previous: str | None = None
    for line_number, row in enumerate(rows, 1):
        if set(row) != BLIND_KEYS:
            raise AccumulatorError(f"blind schema mismatch at row {line_number}")
        lineage = row["lineage"]
        if not isinstance(lineage, dict) or set(lineage) != LINEAGE_KEYS:
            raise AccumulatorError(f"blind lineage schema mismatch at row {line_number}")
        card_id, task, run_id = row["card_id"], row["task"], row["run_id"]
        if not all(isinstance(value, str) and value for value in (card_id, task, run_id)):
            raise AccumulatorError(f"invalid blind identity at row {line_number}")
        if any(c in card_id or c in task for c in "\r\n\t"):
            raise AccumulatorError(f"control whitespace in blind identity at row {line_number}")
        if previous is not None and card_id <= previous:
            raise AccumulatorError("blind card IDs must be strictly sorted and unique")
        previous = card_id
        if card_id in precutoff_ids:
            raise AccumulatorError(f"pre-cutoff endpoint ID in intake at row {line_number}")
        code = row["code"]
        if not isinstance(code, str) or not code:
            raise AccumulatorError(f"blind code must be non-empty string at row {line_number}")
        code_sha = sha256_bytes(code.encode("utf-8"))
        if row["code_sha256"] != code_sha:
            raise AccumulatorError(f"blind code SHA mismatch at row {line_number}")
        if code_sha in precutoff_code_shas:
            raise AccumulatorError(f"pre-cutoff exact code in intake at row {line_number}")
        source_sha = row["source_sha256"]
        if not isinstance(source_sha, str) or not SHA256_RX.fullmatch(source_sha):
            raise AccumulatorError(f"invalid blind source SHA at row {line_number}")
        if run_id != f"journal:{source_sha}":
            raise AccumulatorError(f"blind run/source mismatch at row {line_number}")
        parse_utc(str(row["generation_started_at_utc"]))
        for key in ("depth", "step", "n_siblings"):
            value = lineage[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AccumulatorError(f"invalid blind lineage {key} at row {line_number}")
        if lineage["depth"] < 1 or lineage["step"] < 1:
            raise AccumulatorError(f"blind lineage points to root at row {line_number}")
        if not isinstance(lineage["parent"], str) or not lineage["parent"]:
            raise AccumulatorError(f"missing blind parent at row {line_number}")
        if not isinstance(lineage["op"], str) or any(c in lineage["op"] for c in "\r\n\t"):
            raise AccumulatorError(f"invalid blind op at row {line_number}")


def validate_provenance(
    rows: list[dict[str, Any]], activated_at: dt.datetime
) -> dict[str, dict[str, Any]]:
    expected_order = sorted(
        rows,
        key=lambda row: (
            str(row.get("generation_started_at_utc")),
            str(row.get("journal_sha256")),
            str(row.get("run_id")),
        ),
    )
    if rows != expected_order:
        raise AccumulatorError("source provenance is not in canonical order")
    output: dict[str, dict[str, Any]] = {}
    for row_number, row in enumerate(rows, 1):
        if set(row) != PROVENANCE_KEYS:
            raise AccumulatorError(f"provenance schema mismatch at row {row_number}")
        run_id, task, journal_sha = row["run_id"], row["task"], row["journal_sha256"]
        if not all(isinstance(value, str) and value for value in (run_id, task, journal_sha)):
            raise AccumulatorError(f"invalid provenance identity at row {row_number}")
        if not SHA256_RX.fullmatch(journal_sha) or run_id != f"journal:{journal_sha}":
            raise AccumulatorError(f"provenance run/journal mismatch at row {row_number}")
        if run_id in output:
            raise AccumulatorError("duplicate run in source provenance")
        started = parse_utc(str(row["generation_started_at_utc"]))
        eligible = started > activated_at
        if not isinstance(row["eligible"], bool) or row["eligible"] != eligible:
            raise AccumulatorError(f"provenance eligibility mismatch at row {row_number}")
        if not isinstance(row["archive_sha256"], str) or not SHA256_RX.fullmatch(
            row["archive_sha256"]
        ):
            raise AccumulatorError(f"invalid archive SHA at row {row_number}")
        for key in ("journal_mtime", "endpoints", "empty_code_nodes_excluded"):
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AccumulatorError(f"invalid provenance {key} at row {row_number}")
        expected_flow = "scoreable" if row["endpoints"] else "no_scoreable_code"
        if row["flow_status"] != expected_flow:
            raise AccumulatorError(f"provenance flow status mismatch at row {row_number}")
        output[run_id] = row
    return output


def rebuild_pairs(blind_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    for row in blind_rows:
        grouped[(row["task"], row["run_id"], row["lineage"]["parent"])].append(row["card_id"])
    output: list[dict[str, Any]] = []
    for (task, run_id, parent), card_ids in sorted(grouped.items()):
        for left, right in itertools.combinations(sorted(set(card_ids)), 2):
            output.append(
                {"task": task, "run_id": run_id, "parent": parent, "left": left, "right": right}
            )
    return output


def validate_pairs(rows: list[dict[str, Any]]) -> None:
    for row_number, row in enumerate(rows, 1):
        if set(row) != PAIR_KEYS or not all(isinstance(row[key], str) for key in PAIR_KEYS):
            raise AccumulatorError(f"structural pair schema mismatch at row {row_number}")
        if not row["left"] < row["right"]:
            raise AccumulatorError(f"structural pair endpoints not canonical at row {row_number}")


def load_archive_manifest(
    path: Path, expected_sha: str, opened: list[str]
) -> list[dict[str, Any]]:
    blob = read_bytes(path, opened)
    if sha256_bytes(blob) != expected_sha.lower():
        raise AccumulatorError("archive manifest SHA mismatch")
    text = blob.decode("utf-8")
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    if tuple(reader.fieldnames or ()) != ("name", "size", "sha256"):
        raise AccumulatorError("archive manifest schema mismatch")
    rows = list(reader)
    if not rows or [row["name"] for row in rows] != sorted(row["name"] for row in rows):
        raise AccumulatorError("archive manifest must be non-empty and name-sorted")
    seen_names: set[str] = set()
    seen_shas: set[str] = set()
    for row_number, row in enumerate(rows, 2):
        if set(row) != {"name", "size", "sha256"}:
            raise AccumulatorError(f"archive manifest row mismatch at line {row_number}")
        if row["name"] in seen_names or any(c in row["name"] for c in "\r\n\t"):
            raise AccumulatorError(f"invalid duplicate archive name at line {row_number}")
        try:
            size = int(row["size"])
        except ValueError as error:
            raise AccumulatorError(f"invalid archive size at line {row_number}") from error
        if size < 0 or not SHA256_RX.fullmatch(row["sha256"]) or row["sha256"] in seen_shas:
            raise AccumulatorError(f"invalid duplicate archive bytes at line {row_number}")
        seen_names.add(row["name"])
        seen_shas.add(row["sha256"])
    return rows


def validate_archive_audits(
    rows: list[dict[str, Any]], archive_names: set[str]
) -> dict[str, int]:
    if {row.get("archive_name") for row in rows} != archive_names or len(rows) != len(archive_names):
        raise AccumulatorError("archive audit support mismatch")
    totals = collections.Counter()
    for row_number, row in enumerate(rows, 1):
        if set(row) != ARCHIVE_AUDIT_KEYS:
            raise AccumulatorError(f"archive audit schema mismatch at row {row_number}")
        for key in ARCHIVE_AUDIT_KEYS - {"archive_name"}:
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AccumulatorError(f"invalid archive audit {key} at row {row_number}")
            totals[key] += value
        if row["checkpoint_runs"] != (
            row["checkpoint_with_live_event_log"] + row["checkpoint_without_live_event_log"]
        ):
            raise AccumulatorError(f"archive checkpoint accounting mismatch at row {row_number}")
        if row["discovered_run_roots"] != row["checkpoint_runs"] + row["live_only_runs_excluded"]:
            raise AccumulatorError(f"archive run-root accounting mismatch at row {row_number}")
    return dict(totals)


def validate_intake(
    entry: dict[str, Any],
    activated_at: dt.datetime,
    precutoff_ids: set[str],
    precutoff_code_shas: set[str],
    expected_git_commit: str,
    expected_source_sha256: str,
    opened: list[str],
) -> dict[str, Any]:
    intake_dir = Path(entry["intake_dir"]).resolve()
    if not intake_dir.is_dir():
        raise AccumulatorError(f"intake directory missing: {entry['drop_id']}")
    summary = read_json(intake_dir / "summary.json", entry["summary_sha256"], opened)
    if summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE" or summary.get(
        "protocol"
    ) != INTAKE_PROTOCOL:
        raise AccumulatorError(f"intake status/protocol mismatch: {entry['drop_id']}")
    if summary.get("git_commit") != expected_git_commit:
        raise AccumulatorError(f"intake git commit mismatch: {entry['drop_id']}")
    if summary.get("source_sha256") != expected_source_sha256:
        raise AccumulatorError(f"intake source SHA mismatch: {entry['drop_id']}")
    if not isinstance(summary.get("configuration"), dict) or not isinstance(
        summary.get("software"), dict
    ):
        raise AccumulatorError(f"intake execution metadata missing: {entry['drop_id']}")
    if parse_utc(str(summary.get("activated_at_utc"))) != activated_at:
        raise AccumulatorError(f"intake activation mismatch: {entry['drop_id']}")
    inputs = summary.get("inputs") or {}
    if inputs.get("freeze_receipt_sha256") != FREEZE_RECEIPT_SHA256:
        raise AccumulatorError(f"intake receipt SHA mismatch: {entry['drop_id']}")
    if inputs.get("precutoff_endpoint_denylist_sha256") != PRECUTOFF_ENDPOINT_DENYLIST_SHA256:
        raise AccumulatorError(f"intake endpoint denylist SHA mismatch: {entry['drop_id']}")
    outputs = summary.get("outputs") or {}
    required_output_hashes = {
        "all_blind_views_sha256",
        "eligible_blind_manifest_sha256",
        "label_vault_sha256",
        "structural_pairs_sha256",
        "eligible_structural_pairs_sha256",
        "source_provenance_sha256",
        "archive_audits_sha256",
    }
    if not required_output_hashes <= set(outputs) or any(
        not isinstance(outputs[key], str) or not SHA256_RX.fullmatch(outputs[key])
        for key in required_output_hashes
    ):
        raise AccumulatorError(f"intake output hashes malformed: {entry['drop_id']}")
    security = summary.get("security") or {}
    required_security = {
        "env_members_read": False,
        "env_members_extracted": False,
        "live_event_journal_members_read": False,
        "journal_scanned_before_json": True,
        "credential_shaped_journals": 0,
        "raw_journals_written": False,
        "precutoff_endpoint_ids_checked": PRECUTOFF_ENDPOINTS,
        "precutoff_code_sha256_checked": len(precutoff_code_shas),
        "precutoff_endpoint_id_overlap": 0,
        "precutoff_code_sha256_overlap": 0,
    }
    if any(security.get(key) != value for key, value in required_security.items()):
        raise AccumulatorError(f"intake security gate mismatch: {entry['drop_id']}")
    blindness = summary.get("blindness") or {}
    if (
        blindness.get("labels_used_for_run_selection") is not False
        or blindness.get("labels_used_for_endpoint_selection") is not False
        or blindness.get("label_values_printed") is not False
        or blindness.get("metrics_computed") != []
    ):
        raise AccumulatorError(f"intake blindness gate mismatch: {entry['drop_id']}")

    archive_manifest = load_archive_manifest(
        intake_dir / "archive_manifest.tsv", inputs.get("archive_manifest_sha256", ""), opened
    )
    archive_audits = read_json_value(
        intake_dir / "archive_audits.json", outputs["archive_audits_sha256"], opened
    )
    if not isinstance(archive_audits, list):
        raise AccumulatorError(f"archive audits are not a list: {entry['drop_id']}")
    audit_totals = validate_archive_audits(
        archive_audits, {row["name"] for row in archive_manifest}
    )
    provenance_rows = read_json_value(
        intake_dir / "source_provenance.json", outputs["source_provenance_sha256"], opened
    )
    if not isinstance(provenance_rows, list):
        raise AccumulatorError(f"source provenance is not a list: {entry['drop_id']}")
    provenance = validate_provenance(provenance_rows, activated_at)
    all_blind = read_jsonl(
        intake_dir / "all_blind_views.jsonl", outputs["all_blind_views_sha256"], opened
    )
    eligible_blind = read_jsonl(
        intake_dir / "eligible_blind_manifest.jsonl",
        outputs["eligible_blind_manifest_sha256"],
        opened,
    )
    validate_blind_rows(all_blind, precutoff_ids, precutoff_code_shas)
    validate_blind_rows(eligible_blind, precutoff_ids, precutoff_code_shas)
    rows_by_run: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in all_blind:
        run = provenance.get(row["run_id"])
        if run is None or row["task"] != run["task"] or row["generation_started_at_utc"] != run[
            "generation_started_at_utc"
        ]:
            raise AccumulatorError(f"blind/provenance mismatch: {entry['drop_id']}")
        rows_by_run[row["run_id"]].append(row)
    for run_id, run in provenance.items():
        if len(rows_by_run.get(run_id, [])) != run["endpoints"]:
            raise AccumulatorError(f"run endpoint accounting mismatch: {entry['drop_id']}")
    expected_eligible = [row for row in all_blind if provenance[row["run_id"]]["eligible"]]
    if eligible_blind != expected_eligible:
        raise AccumulatorError(f"eligible blind subset mismatch: {entry['drop_id']}")

    all_pairs = read_jsonl(
        intake_dir / "structural_pairs.jsonl", outputs["structural_pairs_sha256"], opened
    )
    eligible_pairs = read_jsonl(
        intake_dir / "eligible_structural_pairs.jsonl",
        outputs["eligible_structural_pairs_sha256"],
        opened,
    )
    validate_pairs(all_pairs)
    validate_pairs(eligible_pairs)
    expected_pairs = rebuild_pairs(all_blind)
    if all_pairs != expected_pairs:
        raise AccumulatorError(f"structural pair reconstruction mismatch: {entry['drop_id']}")
    expected_eligible_pairs = [row for row in all_pairs if provenance[row["run_id"]]["eligible"]]
    if eligible_pairs != expected_eligible_pairs:
        raise AccumulatorError(f"eligible structural pair subset mismatch: {entry['drop_id']}")

    inventory = summary.get("inventory") or {}
    expected_inventory = {
        "archives": len(archive_manifest),
        "discovered_run_roots": audit_totals["discovered_run_roots"],
        "runs": len(provenance),
        "live_only_runs_excluded": audit_totals["live_only_runs_excluded"],
        "tasks": len({run["task"] for run in provenance.values()}),
        "endpoints": len(all_blind),
        "structural_pairs": len(all_pairs),
        "eligible_runs": sum(run["eligible"] for run in provenance.values()),
        "eligible_tasks": len({run["task"] for run in provenance.values() if run["eligible"]}),
        "eligible_endpoints": len(eligible_blind),
        "eligible_structural_pairs": len(eligible_pairs),
        "no_scoreable_code_runs": sum(
            run["flow_status"] == "no_scoreable_code" for run in provenance.values()
        ),
        "empty_code_nodes_excluded": sum(
            run["empty_code_nodes_excluded"] for run in provenance.values()
        ),
    }
    if inventory != expected_inventory or audit_totals["checkpoint_runs"] != len(provenance):
        raise AccumulatorError(f"intake inventory mismatch: {entry['drop_id']}")
    return {
        "drop_id": entry["drop_id"],
        "intake_dir": str(intake_dir),
        "summary_sha256": entry["summary_sha256"],
        "label_vault_sha256": outputs["label_vault_sha256"],
        "git_commit": summary.get("git_commit"),
        "source_sha256": summary.get("source_sha256"),
        "archive_shas": {row["sha256"] for row in archive_manifest},
        "provenance": provenance,
        "eligible_blind": eligible_blind,
        "eligible_pairs": eligible_pairs,
    }


def load_closure(
    path: Path | None,
    expected_sha: str | None,
    registry_sha: str,
    runs: list[dict[str, Any]],
    activated_at: dt.datetime,
    opened: list[str],
) -> tuple[dict[str, Any] | None, str | None]:
    if (path is None) != (expected_sha is None):
        raise AccumulatorError("closure path and expected SHA must be supplied together")
    if path is None:
        return None, None
    if path.name != "closure_receipt.json":
        raise AccumulatorError("closure receipt must use the frozen basename")
    if not SHA256_RX.fullmatch(str(expected_sha)):
        raise AccumulatorError("invalid expected closure SHA")
    receipt = read_json(path, str(expected_sha), opened)
    if set(receipt) != CLOSURE_KEYS:
        raise AccumulatorError("closure receipt schema mismatch")
    if (
        receipt["status"] != "PROSPECTIVE_ACCRUAL_CLOSED"
        or receipt["protocol"] != SCORER_PROTOCOL
        or receipt["registry_sha256"] != registry_sha
        or receipt["all_scheduled_runs_uploaded"] is not True
        or receipt["outcomes_read"] is not False
    ):
        raise AccumulatorError("closure receipt gate mismatch")
    closed_at = parse_utc(str(receipt["closed_at_utc"]))
    if closed_at <= activated_at:
        raise AccumulatorError("closure must be later than scorer activation")
    if closed_at > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise AccumulatorError("closure time is implausibly in the future")
    if any(parse_utc(run["generation_started_at_utc"]) > closed_at for run in runs):
        raise AccumulatorError("closure precedes an eligible run start")
    return receipt, str(expected_sha)


def task_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = collections.Counter(str(row["task"]) for row in rows)
    return dict(sorted(counts.items()))


def dominant_share(counts: dict[str, int]) -> float | None:
    total = sum(counts.values())
    return max(counts.values()) / total if total else None


def support_summary(
    runs: list[dict[str, Any]],
    endpoints: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    run_counts = task_counts(runs)
    endpoint_counts = task_counts(endpoints)
    pair_counts = task_counts(pairs)
    return {
        "runs": len(runs),
        "endpoints": len(endpoints),
        "structural_pairs": len(pairs),
        "tasks": len(run_counts),
        "run_counts": run_counts,
        "endpoint_counts": endpoint_counts,
        "structural_pair_counts": pair_counts,
        "dominant_run_task_share": dominant_share(run_counts),
        "dominant_endpoint_task_share": dominant_share(endpoint_counts),
        "dominant_structural_pair_task_share": dominant_share(pair_counts),
    }


def build(args: argparse.Namespace) -> int:
    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite accumulator output: {out_dir}")
    if args.max_drops <= 0 or args.max_endpoints <= 0 or args.max_structural_pairs <= 0:
        raise AccumulatorError("resource caps must be positive")
    opened: list[str] = []
    receipt = read_json(args.freeze_receipt, FREEZE_RECEIPT_SHA256, opened)
    if receipt.get("status") != "PROSPECTIVE_SCORER_ACTIVE" or receipt.get(
        "protocol"
    ) != SCORER_PROTOCOL:
        raise AccumulatorError("prospective scorer receipt is not active")
    activated_at = parse_utc(str(receipt["activated_at_utc"]))
    opened.append(args.precutoff_endpoint_denylist.name)
    precutoff_ids, precutoff_code_shas, denylist_audit = load_endpoint_denylist(
        args.precutoff_endpoint_denylist,
        PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
        PRECUTOFF_ENDPOINTS,
    )
    registry, registry_sha = load_registry(args.registry, opened)
    if len(registry) > args.max_drops:
        raise AccumulatorError("registry exceeds drop cap")
    for entry in registry:
        intake_dir = Path(entry["intake_dir"]).resolve()
        if out_dir == intake_dir or intake_dir in out_dir.parents:
            raise AccumulatorError("accumulator output must be outside every intake directory")
    current_commit = git_commit(args.repo_root)
    intake_source_sha = sha256(Path(__file__).with_name("prospective_drop_intake.py"))
    intakes = [
        validate_intake(
            entry,
            activated_at,
            precutoff_ids,
            precutoff_code_shas,
            current_commit,
            intake_source_sha,
            opened,
        )
        for entry in registry
    ]

    global_runs: dict[str, dict[str, Any]] = {}
    global_cards: dict[str, dict[str, Any]] = {}
    archive_owner: dict[str, str] = {}
    drop_for_run: dict[str, str] = {}
    sealed_vaults: list[dict[str, Any]] = []
    for intake in intakes:
        for archive_sha in intake["archive_shas"]:
            owner = archive_owner.setdefault(archive_sha, intake["drop_id"])
            if owner != intake["drop_id"]:
                raise AccumulatorError("source archive appears in multiple drops")
        for run_id, run in intake["provenance"].items():
            if run_id in global_runs:
                raise AccumulatorError("physical run appears in multiple drops")
            global_runs[run_id] = run
            drop_for_run[run_id] = intake["drop_id"]
        for row in intake["eligible_blind"]:
            if row["card_id"] in global_cards:
                raise AccumulatorError("eligible endpoint appears in multiple drops")
            global_cards[row["card_id"]] = row
        sealed_vaults.append(
            {
                "drop_id": intake["drop_id"],
                "intake_dir": intake["intake_dir"],
                "summary_sha256": intake["summary_sha256"],
                "label_vault_sha256": intake["label_vault_sha256"],
            }
        )
    eligible_runs = [run for run in global_runs.values() if run["eligible"]]
    eligible_runs.sort(
        key=lambda run: (
            run["generation_started_at_utc"],
            run["journal_sha256"],
            run["run_id"],
        )
    )
    if len(global_cards) > args.max_endpoints:
        raise AccumulatorError("eligible endpoints exceed cap")
    all_eligible_pairs = rebuild_pairs(list(global_cards.values()))
    if len(all_eligible_pairs) > args.max_structural_pairs:
        raise AccumulatorError("eligible structural pairs exceed cap")
    closure, closure_sha = load_closure(
        args.closure_receipt,
        args.expect_closure_receipt_sha256,
        registry_sha,
        eligible_runs,
        activated_at,
        opened,
    )

    identity_rows = [
        {
            "run_id": run["run_id"],
            "task": run["task"],
            "generation_started_at_utc": run["generation_started_at_utc"],
            "source_sha256": run["journal_sha256"],
            "drop_id": drop_for_run[run["run_id"]],
            "flow_status": run["flow_status"],
            "endpoints": run["endpoints"],
        }
        for run in eligible_runs
    ]
    provisional_240 = identity_rows[:FIRST_PILOT]
    provisional_960 = identity_rows[:FIRST_CONFIRM]
    provisional_240_ids = {row["run_id"] for row in provisional_240}
    provisional_960_ids = {row["run_id"] for row in provisional_960}
    provisional_240_blind = [
        row for row in global_cards.values() if row["run_id"] in provisional_240_ids
    ]
    provisional_960_blind = [
        row for row in global_cards.values() if row["run_id"] in provisional_960_ids
    ]
    provisional_240_pairs = rebuild_pairs(provisional_240_blind)
    provisional_960_pairs = rebuild_pairs(provisional_960_blind)
    if closure is None:
        status = (
            "PROSPECTIVE_COHORT_COLLECTING"
            if len(identity_rows) < FIRST_CONFIRM
            else "PROSPECTIVE_COHORT_AWAITING_CLOSURE"
        )
        frozen_rows: list[dict[str, Any]] | None = None
    elif len(identity_rows) < FIRST_CONFIRM:
        status = "CONFIRMATORY_COHORT_INCOMPLETE"
        frozen_rows = identity_rows
    else:
        status = "PROSPECTIVE_FIRST960_IDENTITY_FROZEN"
        frozen_rows = identity_rows[:FIRST_CONFIRM]

    temporary = out_dir.with_name(f"{out_dir.name}.tmp.{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"temporary accumulator output exists: {temporary}")
    temporary.mkdir(parents=True)
    output_hashes = {
        "provisional_runs_sha256": write_jsonl(temporary / "provisional_runs.jsonl", identity_rows),
        "provisional_first240_runs_sha256": write_jsonl(
            temporary / "provisional_first240_runs.jsonl", provisional_240
        ),
        "provisional_first960_runs_sha256": write_jsonl(
            temporary / "provisional_first960_runs.jsonl", provisional_960
        ),
        "sealed_vault_registry_sha256": write_jsonl(
            temporary / "sealed_vault_registry.jsonl", sealed_vaults
        ),
    }
    frozen_blind: list[dict[str, Any]] = []
    frozen_pairs: list[dict[str, Any]] = []
    if frozen_rows is not None:
        frozen_run_ids = {row["run_id"] for row in frozen_rows}
        frozen_blind = sorted(
            (row for row in global_cards.values() if row["run_id"] in frozen_run_ids),
            key=lambda row: row["card_id"],
        )
        frozen_pairs = rebuild_pairs(frozen_blind)
        output_hashes.update(
            {
                "frozen_runs_sha256": write_jsonl(temporary / "frozen_runs.jsonl", frozen_rows),
                "frozen_first240_runs_sha256": write_jsonl(
                    temporary / "frozen_first240_runs.jsonl", frozen_rows[:FIRST_PILOT]
                ),
                "frozen_blind_manifest_sha256": write_jsonl(
                    temporary / "frozen_blind_manifest.jsonl", frozen_blind
                ),
                "frozen_structural_pairs_sha256": write_jsonl(
                    temporary / "frozen_structural_pairs.jsonl", frozen_pairs
                ),
            }
        )

    code_counts = collections.Counter(row["code_sha256"] for row in global_cards.values())
    summary = {
        "status": status,
        "protocol": PROTOCOL,
        "git_commit": current_commit,
        "source_sha256": sha256(Path(__file__)),
        "inputs": {
            "registry_sha256": registry_sha,
            "freeze_receipt_sha256": FREEZE_RECEIPT_SHA256,
            "precutoff_endpoint_denylist_sha256": PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
            "closure_receipt_sha256": closure_sha,
            "intake_summaries": {
                intake["drop_id"]: intake["summary_sha256"] for intake in intakes
            },
            "intake_git_commits": {
                intake["drop_id"]: intake["git_commit"] for intake in intakes
            },
            "intake_source_sha256": {
                intake["drop_id"]: intake["source_sha256"] for intake in intakes
            },
        },
        "inventory": {
            "drops": len(intakes),
            "all_physical_runs": len(global_runs),
            "eligible_runs": len(identity_rows),
            "eligible_endpoints": len(global_cards),
            "eligible_structural_pairs": len(all_eligible_pairs),
            "eligible_tasks": len({row["task"] for row in identity_rows}),
            "provisional_first240_runs": len(provisional_240),
            "provisional_first240_endpoints": len(provisional_240_blind),
            "provisional_first240_structural_pairs": len(provisional_240_pairs),
            "provisional_first960_runs": len(provisional_960),
            "provisional_first960_endpoints": len(provisional_960_blind),
            "provisional_first960_structural_pairs": len(provisional_960_pairs),
            "frozen_runs": None if frozen_rows is None else len(frozen_rows),
            "frozen_endpoints": None if frozen_rows is None else len(frozen_blind),
            "frozen_structural_pairs": None if frozen_rows is None else len(frozen_pairs),
            "exact_code_duplicate_endpoints": sum(count - 1 for count in code_counts.values()),
            "unique_exact_code_sha256": len(code_counts),
        },
        "task_support": {
            "all_eligible": support_summary(
                identity_rows, list(global_cards.values()), all_eligible_pairs
            ),
            "provisional_first240": support_summary(
                provisional_240, provisional_240_blind, provisional_240_pairs
            ),
            "provisional_first960": support_summary(
                provisional_960, provisional_960_blind, provisional_960_pairs
            ),
            "frozen": None
            if frozen_rows is None
            else support_summary(frozen_rows, frozen_blind, frozen_pairs),
        },
        "closure": {
            "provided": closure is not None,
            "all_scheduled_runs_uploaded": None
            if closure is None
            else closure["all_scheduled_runs_uploaded"],
            "outcomes_read": None if closure is None else closure["outcomes_read"],
        },
        "security": {
            "precutoff_endpoint_ids_checked": denylist_audit["endpoint_ids"],
            "precutoff_code_sha256_checked": denylist_audit["unique_code_sha256"],
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
            "opened_basenames": sorted(set(opened)),
        },
        "outputs": output_hashes,
        "software": {"python": platform.python_version(), "platform": platform.platform()},
    }
    atomic_json(temporary / "summary.json", summary)
    os.replace(temporary, out_dir)
    print(
        status,
        f"eligible_runs={len(identity_rows)}",
        f"eligible_endpoints={len(global_cards)}",
        f"structural_pairs={len(all_eligible_pairs)}",
        "label_vault_opened=false",
        flush=True,
    )
    return 0


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--freeze-receipt", required=True, type=Path)
    parser.add_argument("--precutoff-endpoint-denylist", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--closure-receipt", type=Path)
    parser.add_argument("--expect-closure-receipt-sha256")
    parser.add_argument("--max-drops", type=int, default=512)
    parser.add_argument("--max-endpoints", type=int, default=2_000_000)
    parser.add_argument("--max-structural-pairs", type=int, default=20_000_000)
    return parser.parse_args()


def main() -> int:
    return build(arguments())


if __name__ == "__main__":
    raise SystemExit(main())
