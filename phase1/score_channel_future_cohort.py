#!/usr/bin/env python3
"""Build the frozen future score-channel cohort from outcome-free sidecars only."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "score-channel-future-identifiability-cohort-v1"
OUTPUT_PROTOCOL = "score-channel-future-identity-cohort-v1"
FROZEN_PROTOCOL_SHA256 = (
    "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
)
OBSERVER_PROTOCOL = "prospective_archive_observer_v1"
INTAKE_PROTOCOL = "prospective_drop_intake_v1"
SHA256_RX = re.compile(r"[0-9a-f]{64}")
TRANSACTION_KEYS = {
    "archive_relative_path",
    "archive_sha256",
    "archive_size",
    "committed_at_utc",
    "drop_id",
    "intake_dir",
    "intake_summary_sha256",
    "score_dir",
    "score_summary_sha256",
}
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
RUN_OUTPUT_KEYS = {
    "archive_relative_path",
    "archive_sha256",
    "drop_id",
    "endpoints",
    "flow_status",
    "generation_started_at_utc",
    "journal_sha256",
    "run_id",
    "task",
}
ARCHIVE_OUTPUT_KEYS = {
    "archive_relative_path",
    "archive_sha256",
    "archive_size",
    "cumulative_unique_physical_runs",
    "drop_id",
    "intake_summary_sha256",
    "mtime_ns",
    "physical_runs",
    "source_provenance_sha256",
}


class CohortError(RuntimeError):
    """Fail-closed cohort integrity error."""


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def canonical_jsonl(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode(
            "utf-8"
        )
        for row in rows
    )


def object_file(path: Path, label: str, opened: list[str]) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CohortError(f"{label} is not a regular file")
    opened.append(path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CohortError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise CohortError(f"{label} is not an object")
    return value


def valid_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RX.fullmatch(value.lower()) is None:
        raise CohortError(f"invalid {label}")
    return value.lower()


def safe_relative(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or value.count("/") != 1
        or not value.endswith(".tar.gz")
        or any(character in value for character in "\r\n\t")
        or Path(value).is_absolute()
        or ".." in Path(value).parts
    ):
        raise CohortError(f"invalid {label}")
    return value


def repo_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise CohortError("cannot resolve source commit")
    return value


def validate_protocol(path: Path, expected_sha: str, opened: list[str]) -> dict[str, Any]:
    if valid_sha(expected_sha, "expected protocol SHA") != sha256(path):
        raise CohortError("protocol SHA mismatch")
    value = object_file(path, "future cohort protocol", opened)
    if value.get("protocol") != PROTOCOL or value.get("status") != "FROZEN_OUTCOME_UNREAD_WAITING_COHORT":
        raise CohortError("future cohort protocol/status mismatch")
    closure = value.get("cohort_closure") or {}
    if (
        closure.get("archive_order")
        != ["mtime_ns ascending", "relative_path UTF-8 byte ascending"]
        or not isinstance(closure.get("start_after_archive_mtime_ns"), int)
        or not isinstance(closure.get("accepted_unique_physical_run_target"), int)
        or closure.get("accepted_unique_physical_run_target", 0) <= 0
        or closure.get("include_complete_boundary_archive") is not True
        or closure.get("structurally_rejected_archive_counts_toward_target") is not False
        or closure.get("partial_archive_salvage_allowed") is not False
        or closure.get("label_or_score_may_affect_closure") is not False
        or closure.get("append_only_survival_required") is not True
    ):
        raise CohortError("cohort closure contract mismatch")
    initial = value.get("initial_archives")
    if not isinstance(initial, list) or not initial:
        raise CohortError("initial archive bindings missing")
    normalized: list[tuple[int, bytes, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(initial, 1):
        if not isinstance(row, dict) or set(row) != {"relative_path", "size_bytes", "mtime_ns"}:
            raise CohortError(f"initial archive schema mismatch at row {index}")
        relative = safe_relative(row["relative_path"], "initial archive path")
        if relative in seen:
            raise CohortError("duplicate initial archive path")
        if any(
            isinstance(row[key], bool) or not isinstance(row[key], int) or row[key] < 0
            for key in ("size_bytes", "mtime_ns")
        ):
            raise CohortError("invalid initial archive metadata")
        if row["mtime_ns"] <= closure["start_after_archive_mtime_ns"]:
            raise CohortError("initial archive does not follow frozen cutoff")
        seen.add(relative)
        normalized.append((row["mtime_ns"], relative.encode("utf-8"), relative))
    if normalized != sorted(normalized):
        raise CohortError("initial archive bindings are not in frozen order")
    scope = value.get("scope") or {}
    if (
        scope.get("gpu_jobs_authorized") != 0
        or scope.get("api_calls") != 0
        or scope.get("model_fits") != 0
        or scope.get("base_llm_update") is not False
    ):
        raise CohortError("protocol scope is not CPU-only")
    return value


def manifest_hashes(path: Path, opened: list[str]) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise CohortError("snapshot manifest missing")
    opened.append(path.name)
    rows: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None or match.group(2) in rows:
            raise CohortError(f"invalid snapshot manifest line {number}")
        rows[match.group(2)] = match.group(1)
    if "transactions.jsonl" not in rows:
        raise CohortError("snapshot manifest omits transactions")
    return rows


def parse_transactions(blob: bytes) -> list[dict[str, Any]]:
    try:
        lines = blob.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise CohortError("transaction registry is not UTF-8") from error
    rows: list[dict[str, Any]] = []
    seen_path: set[str] = set()
    seen_sha: set[str] = set()
    seen_drop: set[str] = set()
    for number, line in enumerate(lines, 1):
        if not line:
            raise CohortError(f"blank transaction line {number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise CohortError(f"invalid transaction JSON line {number}") from error
        if not isinstance(row, dict) or set(row) != TRANSACTION_KEYS:
            raise CohortError(f"transaction schema mismatch at line {number}")
        relative = safe_relative(row["archive_relative_path"], "transaction path")
        archive_sha = valid_sha(row["archive_sha256"], "transaction archive SHA")
        valid_sha(row["intake_summary_sha256"], "transaction intake SHA")
        valid_sha(row["score_summary_sha256"], "transaction score SHA")
        if (
            isinstance(row["archive_size"], bool)
            or not isinstance(row["archive_size"], int)
            or row["archive_size"] < 0
            or not isinstance(row["drop_id"], str)
            or not row["drop_id"]
            or not Path(row["intake_dir"]).is_absolute()
            or not Path(row["score_dir"]).is_absolute()
        ):
            raise CohortError(f"invalid transaction metadata at line {number}")
        if relative in seen_path or archive_sha in seen_sha or row["drop_id"] in seen_drop:
            raise CohortError(f"duplicate transaction identity at line {number}")
        seen_path.add(relative)
        seen_sha.add(archive_sha)
        seen_drop.add(row["drop_id"])
        rows.append(row)
    return rows


def load_latest(state_root: Path, opened: list[str]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    latest_path = state_root / "LATEST"
    if latest_path.is_symlink() or not latest_path.is_file():
        raise CohortError("LATEST is missing")
    opened.append(latest_path.name)
    snapshot_sha = valid_sha(latest_path.read_text(encoding="ascii").strip(), "LATEST SHA")
    snapshot = state_root / "snapshots" / snapshot_sha
    manifest = snapshot / "SHA256SUMS"
    if sha256(manifest) != snapshot_sha:
        raise CohortError("snapshot manifest hash does not match LATEST")
    hashes = manifest_hashes(manifest, opened)
    transactions_path = snapshot / "transactions.jsonl"
    if transactions_path.is_symlink() or not transactions_path.is_file():
        raise CohortError("transaction registry missing")
    opened.append(transactions_path.name)
    blob = transactions_path.read_bytes()
    if sha256_bytes(blob) != hashes["transactions.jsonl"]:
        raise CohortError("transaction registry hash mismatch")
    return parse_transactions(blob), {
        "latest_sha256": snapshot_sha,
        "latest_file_sha256": sha256(latest_path),
        "snapshot_manifest_sha256": sha256(manifest),
        "transactions_sha256": sha256_bytes(blob),
    }


def verify_observations(
    observations: dict[str, Any],
    source_root: Path,
    protocol: dict[str, Any],
) -> tuple[list[tuple[int, bytes, str, dict[str, Any]]], dict[str, dict[str, Any]]]:
    if observations.get("protocol") != OBSERVER_PROTOCOL:
        raise CohortError("observation protocol mismatch")
    if Path(str(observations.get("source_root"))).resolve() != source_root.resolve():
        raise CohortError("observation source root mismatch")
    entries = observations.get("entries")
    if not isinstance(entries, dict):
        raise CohortError("observation entries missing")
    initial = {row["relative_path"]: row for row in protocol["initial_archives"]}
    for relative, frozen in initial.items():
        entry = entries.get(relative)
        if not isinstance(entry, dict):
            raise CohortError(f"frozen initial archive absent: {relative}")
        if entry.get("size") != frozen["size_bytes"] or entry.get("mtime_ns") != frozen["mtime_ns"]:
            raise CohortError(f"frozen initial archive metadata changed: {relative}")
    cutoff = protocol["cohort_closure"]["start_after_archive_mtime_ns"]
    ordered: list[tuple[int, bytes, str, dict[str, Any]]] = []
    normalized: dict[str, dict[str, Any]] = {}
    for raw_relative, raw_entry in entries.items():
        relative = safe_relative(raw_relative, "observation path")
        if not isinstance(raw_entry, dict):
            raise CohortError("observation entry is not an object")
        if raw_entry.get("present") is not True:
            if raw_entry.get("committed_archive_sha256") or raw_entry.get("rejected_archive_sha256"):
                raise CohortError(f"settled archive disappeared: {relative}")
            continue
        for key in ("size", "mtime_ns"):
            if isinstance(raw_entry.get(key), bool) or not isinstance(raw_entry.get(key), int) or raw_entry[key] < 0:
                raise CohortError(f"invalid observation {key}: {relative}")
        archive_path = source_root / Path(relative)
        archive_parent = source_root / Path(relative).parent
        if archive_parent.is_symlink() or archive_path.is_symlink() or not archive_path.is_file():
            raise CohortError(f"source archive is not a regular file: {relative}")
        resolved = archive_path.resolve()
        if resolved.parent != archive_parent.resolve():
            raise CohortError(f"source archive escapes root: {relative}")
        stat = archive_path.stat()
        if stat.st_size != raw_entry["size"] or stat.st_mtime_ns != raw_entry["mtime_ns"]:
            raise CohortError(f"source archive metadata differs from observation: {relative}")
        committed = raw_entry.get("committed_archive_sha256")
        rejected = raw_entry.get("rejected_archive_sha256")
        if committed is not None:
            valid_sha(committed, "committed archive SHA")
        if rejected is not None:
            valid_sha(rejected, "rejected archive SHA")
        if committed is not None and rejected is not None:
            raise CohortError(f"archive is both committed and rejected: {relative}")
        normalized[relative] = raw_entry
        if raw_entry["mtime_ns"] > cutoff:
            if raw_entry.get("baseline") is not False:
                raise CohortError(f"future archive is marked baseline: {relative}")
            ordered.append((raw_entry["mtime_ns"], relative.encode("utf-8"), relative, raw_entry))
    ordered.sort(key=lambda item: (item[0], item[1]))
    return ordered, normalized


def verify_intake_summary(summary: dict[str, Any], transaction: dict[str, Any]) -> None:
    if summary.get("protocol") != INTAKE_PROTOCOL or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE":
        raise CohortError("intake protocol/status mismatch")
    configuration = summary.get("configuration") or {}
    if (
        configuration.get("archive_selection") != "explicit_names"
        or configuration.get("selected_archive_names")
        != [Path(transaction["archive_relative_path"]).name]
    ):
        raise CohortError("intake explicit archive binding mismatch")
    security = summary.get("security") or {}
    expected_security = {
        "credential_shaped_journals": 0,
        "env_members_extracted": False,
        "env_members_read": False,
        "journal_scanned_before_json": True,
        "live_event_journal_members_read": False,
        "precutoff_code_sha256_overlap": 0,
        "precutoff_endpoint_id_overlap": 0,
        "raw_journals_written": False,
    }
    for key, expected in expected_security.items():
        if security.get(key) != expected:
            raise CohortError(f"unsafe intake flag: {key}")
    blindness = summary.get("blindness") or {}
    expected_blindness = {
        "label_values_printed": False,
        "labels_used_for_endpoint_selection": False,
        "labels_used_for_run_selection": False,
        "metrics_computed": [],
    }
    for key, expected in expected_blindness.items():
        if blindness.get(key) != expected:
            raise CohortError(f"intake blindness mismatch: {key}")


def load_archive_runs(
    transaction: dict[str, Any],
    state_root: Path,
    opened: list[str],
) -> tuple[list[dict[str, Any]], str, str]:
    intake_dir = Path(transaction["intake_dir"])
    if intake_dir.is_symlink() or not intake_dir.is_dir():
        raise CohortError("intake directory is unavailable")
    if intake_dir.resolve().parent != (state_root / "intakes").resolve():
        raise CohortError("intake directory is outside the production state")
    summary_path = intake_dir / "summary.json"
    if sha256(summary_path) != valid_sha(transaction["intake_summary_sha256"], "intake summary SHA"):
        raise CohortError("intake summary SHA mismatch")
    summary = object_file(summary_path, "intake summary", opened)
    verify_intake_summary(summary, transaction)
    inputs, outputs = summary.get("inputs") or {}, summary.get("outputs") or {}
    manifest_sha = valid_sha(inputs.get("archive_manifest_sha256"), "archive manifest SHA")
    provenance_sha = valid_sha(outputs.get("source_provenance_sha256"), "source provenance SHA")

    manifest_path = intake_dir / "archive_manifest.tsv"
    if manifest_path.is_symlink() or not manifest_path.is_file() or sha256(manifest_path) != manifest_sha:
        raise CohortError("intake archive manifest SHA mismatch")
    opened.append(manifest_path.name)
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    expected_manifest = {
        "name": Path(transaction["archive_relative_path"]).name,
        "size": str(transaction["archive_size"]),
        "sha256": transaction["archive_sha256"],
    }
    if rows != [expected_manifest]:
        raise CohortError("intake archive manifest does not bind transaction")

    provenance_path = intake_dir / "source_provenance.json"
    if provenance_path.is_symlink() or not provenance_path.is_file() or sha256(provenance_path) != provenance_sha:
        raise CohortError("source provenance SHA mismatch")
    opened.append(provenance_path.name)
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CohortError("cannot read source provenance") from error
    if not isinstance(provenance, list):
        raise CohortError("source provenance is not a list")
    expected_order = sorted(
        provenance,
        key=lambda row: (
            str(row.get("generation_started_at_utc")),
            str(row.get("journal_sha256")),
            str(row.get("run_id")),
        ),
    )
    if provenance != expected_order:
        raise CohortError("source provenance is not canonically ordered")
    safe_rows: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    archive_name = Path(transaction["archive_relative_path"]).name
    for number, row in enumerate(provenance, 1):
        if not isinstance(row, dict) or set(row) != PROVENANCE_KEYS:
            raise CohortError(f"source provenance schema mismatch at row {number}")
        journal_sha = valid_sha(row.get("journal_sha256"), "journal SHA")
        run_id, task = row.get("run_id"), row.get("task")
        if (
            run_id != f"journal:{journal_sha}"
            or run_id in seen_runs
            or not isinstance(task, str)
            or not task
            or row.get("archive_name") != archive_name
            or row.get("archive_sha256") != transaction["archive_sha256"]
            or not isinstance(row.get("eligible"), bool)
            or row.get("flow_status") not in {"scoreable", "no_scoreable_code"}
        ):
            raise CohortError(f"invalid source provenance identity at row {number}")
        for key in ("journal_mtime", "endpoints", "empty_code_nodes_excluded"):
            if isinstance(row.get(key), bool) or not isinstance(row.get(key), int) or row[key] < 0:
                raise CohortError(f"invalid source provenance {key} at row {number}")
        if row["flow_status"] != ("scoreable" if row["endpoints"] else "no_scoreable_code"):
            raise CohortError(f"source provenance flow mismatch at row {number}")
        if not isinstance(row.get("generation_started_at_utc"), str) or not row["generation_started_at_utc"]:
            raise CohortError(f"invalid generation timestamp at row {number}")
        seen_runs.add(run_id)
        safe_rows.append(
            {
                "archive_relative_path": transaction["archive_relative_path"],
                "archive_sha256": transaction["archive_sha256"],
                "drop_id": transaction["drop_id"],
                "endpoints": row["endpoints"],
                "flow_status": row["flow_status"],
                "generation_started_at_utc": row["generation_started_at_utc"],
                "journal_sha256": journal_sha,
                "run_id": run_id,
                "task": task,
            }
        )
    inventory = summary.get("inventory") or {}
    if inventory.get("runs") != len(safe_rows):
        raise CohortError("intake run inventory mismatch")
    return safe_rows, sha256(summary_path), provenance_sha


def load_jsonl(path: Path, expected_keys: set[str], label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise CohortError(f"{label} is missing")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise CohortError(f"blank {label} row {number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise CohortError(f"invalid {label} row {number}") from error
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise CohortError(f"{label} schema mismatch at row {number}")
        rows.append(row)
    return rows


def verify_previous(
    previous_dir: Path | None,
    protocol_sha: str,
    current_archives: list[dict[str, Any]],
    current_runs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if previous_dir is None:
        return None
    summary_path = previous_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        not isinstance(summary, dict)
        or summary.get("protocol") != OUTPUT_PROTOCOL
        or (summary.get("inputs") or {}).get("protocol_sha256") != protocol_sha
    ):
        raise CohortError("previous cohort summary contract mismatch")
    outputs = summary.get("outputs") or {}
    archives_path, runs_path = previous_dir / "cohort_archives.jsonl", previous_dir / "cohort_runs.jsonl"
    if (
        sha256(archives_path) != valid_sha(outputs.get("cohort_archives_sha256"), "previous archive SHA")
        or sha256(runs_path) != valid_sha(outputs.get("cohort_runs_sha256"), "previous run SHA")
    ):
        raise CohortError("previous cohort output SHA mismatch")
    previous_archives = load_jsonl(archives_path, ARCHIVE_OUTPUT_KEYS, "previous archives")
    previous_runs = load_jsonl(runs_path, RUN_OUTPUT_KEYS, "previous runs")
    if current_archives[: len(previous_archives)] != previous_archives:
        raise CohortError("previous archive assignment is not an exact prefix")
    if current_runs[: len(previous_runs)] != previous_runs:
        raise CohortError("previous run assignment is not an exact prefix")
    if summary.get("status") == "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD" and (
        current_archives != previous_archives or current_runs != previous_runs
    ):
        raise CohortError("closed previous cohort changed")
    return {
        "previous_summary_sha256": sha256(summary_path),
        "previous_status": summary.get("status"),
        "previous_archives": len(previous_archives),
        "previous_runs": len(previous_runs),
        "exact_prefix_survived": True,
    }


def write_output(path: Path, rows: list[dict[str, Any]]) -> str:
    path.write_bytes(canonical_jsonl(rows))
    return sha256(path)


def produce(
    protocol_path: Path,
    expected_protocol_sha: str,
    state_root: Path,
    source_root: Path,
    repo_root: Path,
    out_dir: Path,
    previous_dir: Path | None = None,
) -> dict[str, Any]:
    if out_dir.exists():
        raise CohortError(f"refusing to overwrite output: {out_dir}")
    opened: list[str] = []
    protocol = validate_protocol(protocol_path, expected_protocol_sha, opened)
    transactions, snapshot_inputs = load_latest(state_root, opened)
    observations_path = state_root / "observations.json"
    observations = object_file(observations_path, "archive observations", opened)
    ordered_observations, observation_entries = verify_observations(
        observations, source_root, protocol
    )
    transaction_by_path = {row["archive_relative_path"]: row for row in transactions}
    cutoff = protocol["cohort_closure"]["start_after_archive_mtime_ns"]
    future_transactions = [
        row
        for row in transactions
        if observation_entries.get(row["archive_relative_path"], {}).get("mtime_ns", -1) > cutoff
    ]
    for transaction in future_transactions:
        relative = transaction["archive_relative_path"]
        entry = observation_entries.get(relative)
        if entry is None:
            raise CohortError(f"future transaction has no observation: {relative}")
        if (
            entry.get("committed_archive_sha256") != transaction["archive_sha256"]
            or entry.get("rejected_archive_sha256") is not None
            or entry.get("size") != transaction["archive_size"]
        ):
            raise CohortError(f"future transaction/observation mismatch: {relative}")

    settled: list[tuple[int, bytes, str, dict[str, Any]]] = []
    pending_index: int | None = None
    rejected_before_pending = 0
    for index, item in enumerate(ordered_observations):
        relative, entry = item[2], item[3]
        committed = entry.get("committed_archive_sha256")
        rejected = entry.get("rejected_archive_sha256")
        if committed is None and rejected is None:
            pending_index = index
            break
        if committed is not None:
            transaction = transaction_by_path.get(relative)
            if transaction is None or transaction["archive_sha256"] != committed:
                raise CohortError(f"settled committed archive lacks transaction: {relative}")
        else:
            rejected_before_pending += 1
        settled.append(item)
    if pending_index is not None:
        for item in ordered_observations[pending_index + 1 :]:
            entry = item[3]
            if entry.get("committed_archive_sha256") is not None or entry.get("rejected_archive_sha256") is not None:
                raise CohortError("archive order contains a settled item after an unresolved gap")

    accepted: list[tuple[int, bytes, str, dict[str, Any], dict[str, Any]]] = []
    for item in settled:
        transaction = transaction_by_path.get(item[2])
        if transaction is not None:
            accepted.append((*item, transaction))

    target = protocol["cohort_closure"]["accepted_unique_physical_run_target"]
    all_seen_runs: set[str] = set()
    selected_runs: list[dict[str, Any]] = []
    selected_archives: list[dict[str, Any]] = []
    intake_summary_shas: dict[str, str] = {}
    provenance_shas: dict[str, str] = {}
    boundary: str | None = None
    for mtime_ns, _, relative, entry, transaction in accepted:
        archive_runs, summary_sha, provenance_sha = load_archive_runs(
            transaction, state_root, opened
        )
        for row in archive_runs:
            if row["run_id"] in all_seen_runs:
                raise CohortError("physical run appears in multiple future archives")
            all_seen_runs.add(row["run_id"])
        selected_runs.extend(archive_runs)
        intake_summary_shas[transaction["drop_id"]] = summary_sha
        provenance_shas[transaction["drop_id"]] = provenance_sha
        selected_archives.append(
            {
                "archive_relative_path": relative,
                "archive_sha256": transaction["archive_sha256"],
                "archive_size": entry["size"],
                "cumulative_unique_physical_runs": len(selected_runs),
                "drop_id": transaction["drop_id"],
                "intake_summary_sha256": summary_sha,
                "mtime_ns": mtime_ns,
                "physical_runs": len(archive_runs),
                "source_provenance_sha256": provenance_sha,
            }
        )
        if len(selected_runs) >= target:
            boundary = relative
            break

    status = (
        "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        if boundary is not None
        else "FUTURE_COHORT_COLLECTING"
    )
    previous = verify_previous(
        previous_dir,
        valid_sha(expected_protocol_sha, "expected protocol SHA"),
        selected_archives,
        selected_runs,
    )
    task_counts = collections.Counter(row["task"] for row in selected_runs)
    pending_head = (
        None
        if pending_index is None
        else {
            "archive_relative_path": ordered_observations[pending_index][2],
            "mtime_ns": ordered_observations[pending_index][0],
        }
    )

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    try:
        archives_sha = write_output(temporary / "cohort_archives.jsonl", selected_archives)
        runs_sha = write_output(temporary / "cohort_runs.jsonl", selected_runs)
        summary = {
            "protocol": OUTPUT_PROTOCOL,
            "status": status,
            "source_commit": repo_commit(repo_root),
            "inputs": {
                "protocol_sha256": valid_sha(expected_protocol_sha, "expected protocol SHA"),
                "observations_sha256": sha256(observations_path),
                **snapshot_inputs,
                "intake_summary_sha256": dict(sorted(intake_summary_shas.items())),
                "source_provenance_sha256": dict(sorted(provenance_shas.items())),
            },
            "closure": {
                "accepted_unique_physical_run_target": target,
                "boundary_archive": boundary,
                "complete_boundary_archive_included": boundary is not None,
                "remaining_runs_to_target": max(0, target - len(selected_runs)),
                "settled_archive_prefix": len(settled),
                "accepted_archives_in_cohort": len(selected_archives),
                "structurally_rejected_in_settled_prefix": rejected_before_pending,
                "pending_head": pending_head,
                "append_only_previous": previous,
            },
            "inventory": {
                "observed_future_archives": len(ordered_observations),
                "future_transactions": len(future_transactions),
                "selected_archives": len(selected_archives),
                "selected_physical_runs": len(selected_runs),
                "selected_tasks": len(task_counts),
                "per_task_selected_runs": dict(sorted(task_counts.items())),
            },
            "integrity": {
                "initial_archive_bindings_pass": True,
                "archive_order": "mtime_ns_then_relative_path_utf8_bytes",
                "settled_prefix_only": True,
                "partial_archive_salvage": False,
                "unique_physical_runs": len(all_seen_runs) == len(selected_runs),
            },
            "blindness": {
                "raw_archive_payload_opened": False,
                "blind_code_view_opened": False,
                "label_vault_opened": False,
                "score_directory_opened": False,
                "score_or_outcome_opened": False,
                "truth_support_computed": False,
                "replay_submission_authorized": False,
                "opened_basenames": sorted(set(opened)),
            },
            "outputs": {
                "cohort_archives_sha256": archives_sha,
                "cohort_runs_sha256": runs_sha,
            },
            "implementation": {
                "python": platform.python_version(),
                "script_sha256": sha256(Path(__file__)),
            },
        }
        (temporary / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, out_dir)
    except Exception:
        for child in temporary.iterdir():
            child.unlink()
        temporary.rmdir()
        raise
    return summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument(
        "--expect-protocol-sha256", default=FROZEN_PROTOCOL_SHA256
    )
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--previous-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        summary = produce(
            args.protocol,
            args.expect_protocol_sha256,
            args.state_root,
            args.source_root,
            args.repo_root,
            args.out_dir,
            args.previous_dir,
        )
    except (CohortError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FUTURE_COHORT_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": summary["status"],
                "selected_archives": summary["inventory"]["selected_archives"],
                "selected_physical_runs": summary["inventory"]["selected_physical_runs"],
                "remaining_runs": summary["closure"]["remaining_runs_to_target"],
                "truth_support_computed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
