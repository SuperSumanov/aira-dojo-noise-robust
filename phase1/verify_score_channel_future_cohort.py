#!/usr/bin/env python3
"""Independently reconstruct the future score-channel identity cohort."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "score-channel-future-identifiability-cohort-v1"
OUTPUT_PROTOCOL = "score-channel-future-identity-cohort-v1"
FROZEN_PROTOCOL_SHA256 = (
    "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
)
SHA_RX = re.compile(r"[0-9a-f]{64}")
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
ARCHIVE_KEYS = {
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
RUN_KEYS = {
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


class VerificationError(RuntimeError):
    """Independent verification failure."""


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def bytes_digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value.lower()) is None:
        raise VerificationError(f"invalid {label}")
    return value.lower()


def relative(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or value.count("/") != 1
        or not value.endswith(".tar.gz")
        or Path(value).is_absolute()
        or ".." in Path(value).parts
        or any(character in value for character in "\r\n\t")
    ):
        raise VerificationError(f"invalid {label}")
    return value


def object_path(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot parse {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def lines(path: Path, keys: set[str], label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is not a regular file")
    output: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise VerificationError(f"blank {label} row {number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise VerificationError(f"bad {label} row {number}") from error
        if not isinstance(row, dict) or set(row) != keys:
            raise VerificationError(f"{label} schema mismatch at row {number}")
        output.append(row)
    return output


def canonical_lines(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode(
            "utf-8"
        )
        for row in rows
    )


def current_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise VerificationError("cannot determine source commit")
    return value


def protocol_state(path: Path, expected_sha: str) -> dict[str, Any]:
    if digest(path) != sha(expected_sha, "protocol SHA"):
        raise VerificationError("protocol hash mismatch")
    value = object_path(path, "protocol")
    closure = value.get("cohort_closure") or {}
    if (
        value.get("protocol") != PROTOCOL
        or value.get("status") != "FROZEN_OUTCOME_UNREAD_WAITING_COHORT"
        or closure.get("archive_order")
        != ["mtime_ns ascending", "relative_path UTF-8 byte ascending"]
        or closure.get("include_complete_boundary_archive") is not True
        or closure.get("structurally_rejected_archive_counts_toward_target") is not False
        or closure.get("partial_archive_salvage_allowed") is not False
        or closure.get("label_or_score_may_affect_closure") is not False
        or closure.get("append_only_survival_required") is not True
        or not isinstance(closure.get("accepted_unique_physical_run_target"), int)
        or closure.get("accepted_unique_physical_run_target", 0) <= 0
    ):
        raise VerificationError("protocol closure contract mismatch")
    initial = value.get("initial_archives")
    if not isinstance(initial, list) or not initial:
        raise VerificationError("initial archive list missing")
    frozen_order: list[tuple[int, bytes]] = []
    seen: set[str] = set()
    for row in initial:
        if not isinstance(row, dict) or set(row) != {"relative_path", "size_bytes", "mtime_ns"}:
            raise VerificationError("initial archive row malformed")
        name = relative(row["relative_path"], "initial archive")
        if name in seen or any(
            isinstance(row.get(key), bool) or not isinstance(row.get(key), int) or row[key] < 0
            for key in ("size_bytes", "mtime_ns")
        ):
            raise VerificationError("initial archive identity malformed")
        seen.add(name)
        frozen_order.append((row["mtime_ns"], name.encode("utf-8")))
    if frozen_order != sorted(frozen_order):
        raise VerificationError("initial archive ordering mismatch")
    return value


def latest_transactions(state: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    latest = state / "LATEST"
    snapshot_sha = sha(latest.read_text(encoding="ascii").strip(), "LATEST")
    manifest = state / "snapshots" / snapshot_sha / "SHA256SUMS"
    if digest(manifest) != snapshot_sha:
        raise VerificationError("LATEST does not bind snapshot manifest")
    manifest_rows: dict[str, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None or match.group(2) in manifest_rows:
            raise VerificationError(f"snapshot manifest malformed at row {number}")
        manifest_rows[match.group(2)] = match.group(1)
    transaction_path = manifest.parent / "transactions.jsonl"
    blob = transaction_path.read_bytes()
    if bytes_digest(blob) != manifest_rows.get("transactions.jsonl"):
        raise VerificationError("transaction registry is not snapshot-bound")
    rows: list[dict[str, Any]] = []
    paths: set[str] = set()
    hashes: set[str] = set()
    drops: set[str] = set()
    for number, line in enumerate(blob.decode("utf-8").splitlines(), 1):
        if not line:
            raise VerificationError(f"blank transaction row {number}")
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != TRANSACTION_KEYS:
            raise VerificationError(f"transaction schema mismatch at row {number}")
        name = relative(row["archive_relative_path"], "transaction archive")
        archive_sha = sha(row["archive_sha256"], "transaction archive SHA")
        sha(row["intake_summary_sha256"], "intake summary SHA")
        sha(row["score_summary_sha256"], "score summary SHA")
        if (
            name in paths
            or archive_sha in hashes
            or row.get("drop_id") in drops
            or not isinstance(row.get("archive_size"), int)
            or isinstance(row.get("archive_size"), bool)
            or row["archive_size"] < 0
            or not isinstance(row.get("drop_id"), str)
            or not row["drop_id"]
            or not Path(str(row.get("intake_dir"))).is_absolute()
            or not Path(str(row.get("score_dir"))).is_absolute()
        ):
            raise VerificationError(f"transaction identity invalid at row {number}")
        paths.add(name)
        hashes.add(archive_sha)
        drops.add(row["drop_id"])
        rows.append(row)
    return rows, {
        "latest_sha256": snapshot_sha,
        "latest_file_sha256": digest(latest),
        "snapshot_manifest_sha256": digest(manifest),
        "transactions_sha256": bytes_digest(blob),
    }


def observation_order(
    state: Path,
    source: Path,
    protocol: dict[str, Any],
) -> tuple[list[tuple[int, bytes, str, dict[str, Any]]], dict[str, dict[str, Any]], str]:
    path = state / "observations.json"
    value = object_path(path, "observations")
    if value.get("protocol") != "prospective_archive_observer_v1":
        raise VerificationError("observer protocol mismatch")
    if Path(str(value.get("source_root"))).resolve() != source.resolve():
        raise VerificationError("observer source root mismatch")
    entries = value.get("entries")
    if not isinstance(entries, dict):
        raise VerificationError("observer entries missing")
    initial = {row["relative_path"]: row for row in protocol["initial_archives"]}
    for name, frozen in initial.items():
        entry = entries.get(name)
        if not isinstance(entry, dict) or entry.get("size") != frozen["size_bytes"] or entry.get("mtime_ns") != frozen["mtime_ns"]:
            raise VerificationError(f"initial archive binding failed: {name}")
    cutoff = protocol["cohort_closure"]["start_after_archive_mtime_ns"]
    normalized: dict[str, dict[str, Any]] = {}
    ordered: list[tuple[int, bytes, str, dict[str, Any]]] = []
    for raw_name, entry in entries.items():
        name = relative(raw_name, "observation archive")
        if not isinstance(entry, dict):
            raise VerificationError("observation entry malformed")
        if entry.get("present") is not True:
            if entry.get("committed_archive_sha256") or entry.get("rejected_archive_sha256"):
                raise VerificationError("settled observation is absent")
            continue
        for key in ("size", "mtime_ns"):
            if isinstance(entry.get(key), bool) or not isinstance(entry.get(key), int) or entry[key] < 0:
                raise VerificationError(f"observation {key} malformed")
        archive = source / Path(name)
        archive_parent = source / Path(name).parent
        if archive_parent.is_symlink() or archive.is_symlink() or not archive.is_file():
            raise VerificationError(f"source archive absent: {name}")
        stat = archive.stat()
        if stat.st_size != entry["size"] or stat.st_mtime_ns != entry["mtime_ns"]:
            raise VerificationError(f"source archive metadata mismatch: {name}")
        committed, rejected = entry.get("committed_archive_sha256"), entry.get("rejected_archive_sha256")
        if committed is not None:
            sha(committed, "committed archive SHA")
        if rejected is not None:
            sha(rejected, "rejected archive SHA")
        if committed is not None and rejected is not None:
            raise VerificationError("archive is both accepted and rejected")
        normalized[name] = entry
        if entry["mtime_ns"] > cutoff:
            if entry.get("baseline") is not False:
                raise VerificationError("future archive marked baseline")
            ordered.append((entry["mtime_ns"], name.encode("utf-8"), name, entry))
    ordered.sort(key=lambda item: (item[0], item[1]))
    return ordered, normalized, digest(path)


def intake_runs(
    transaction: dict[str, Any], state: Path
) -> tuple[list[dict[str, Any]], str, str]:
    intake = Path(transaction["intake_dir"])
    if intake.is_symlink() or not intake.is_dir() or intake.resolve().parent != (state / "intakes").resolve():
        raise VerificationError("intake directory contract mismatch")
    summary_path = intake / "summary.json"
    summary_sha = digest(summary_path)
    if summary_sha != transaction["intake_summary_sha256"]:
        raise VerificationError("intake summary transaction binding failed")
    summary = object_path(summary_path, "intake summary")
    config = summary.get("configuration") or {}
    if (
        summary.get("protocol") != "prospective_drop_intake_v1"
        or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE"
        or config.get("archive_selection") != "explicit_names"
        or config.get("selected_archive_names") != [Path(transaction["archive_relative_path"]).name]
    ):
        raise VerificationError("intake completion/archive contract mismatch")
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
    if any(security.get(key) != expected for key, expected in expected_security.items()):
        raise VerificationError("intake security contract failed")
    blindness = summary.get("blindness") or {}
    if blindness != {
        "labels_used_for_run_selection": False,
        "labels_used_for_endpoint_selection": False,
        "label_values_printed": False,
        "metrics_computed": [],
    }:
        raise VerificationError("intake blindness contract failed")
    inputs, outputs = summary.get("inputs") or {}, summary.get("outputs") or {}
    manifest = intake / "archive_manifest.tsv"
    if manifest.is_symlink() or digest(manifest) != sha(inputs.get("archive_manifest_sha256"), "archive manifest SHA"):
        raise VerificationError("archive manifest hash failed")
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle, delimiter="\t"))
    if manifest_rows != [{
        "name": Path(transaction["archive_relative_path"]).name,
        "size": str(transaction["archive_size"]),
        "sha256": transaction["archive_sha256"],
    }]:
        raise VerificationError("archive manifest transaction binding failed")
    provenance_path = intake / "source_provenance.json"
    provenance_sha = sha(outputs.get("source_provenance_sha256"), "provenance SHA")
    if provenance_path.is_symlink() or digest(provenance_path) != provenance_sha:
        raise VerificationError("provenance hash failed")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if not isinstance(provenance, list) or provenance != sorted(
        provenance,
        key=lambda row: (
            str(row.get("generation_started_at_utc")),
            str(row.get("journal_sha256")),
            str(row.get("run_id")),
        ),
    ):
        raise VerificationError("provenance ordering failed")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in provenance:
        if not isinstance(row, dict) or set(row) != PROVENANCE_KEYS:
            raise VerificationError("provenance schema failed")
        journal = sha(row.get("journal_sha256"), "journal SHA")
        run_id = row.get("run_id")
        task = row.get("task")
        if (
            run_id != f"journal:{journal}"
            or run_id in seen
            or not isinstance(task, str)
            or not task
            or row.get("archive_name") != Path(transaction["archive_relative_path"]).name
            or row.get("archive_sha256") != transaction["archive_sha256"]
            or not isinstance(row.get("eligible"), bool)
            or row.get("flow_status") not in {"scoreable", "no_scoreable_code"}
        ):
            raise VerificationError("provenance identity failed")
        for key in ("journal_mtime", "endpoints", "empty_code_nodes_excluded"):
            if isinstance(row.get(key), bool) or not isinstance(row.get(key), int) or row[key] < 0:
                raise VerificationError("provenance count failed")
        if row["flow_status"] != ("scoreable" if row["endpoints"] else "no_scoreable_code"):
            raise VerificationError("provenance flow status failed")
        seen.add(run_id)
        output.append({
            "archive_relative_path": transaction["archive_relative_path"],
            "archive_sha256": transaction["archive_sha256"],
            "drop_id": transaction["drop_id"],
            "endpoints": row["endpoints"],
            "flow_status": row["flow_status"],
            "generation_started_at_utc": row["generation_started_at_utc"],
            "journal_sha256": journal,
            "run_id": run_id,
            "task": task,
        })
    if (summary.get("inventory") or {}).get("runs") != len(output):
        raise VerificationError("intake run count failed")
    return output, summary_sha, provenance_sha


def previous_attestation(
    previous: Path | None,
    protocol_sha: str,
    archives: list[dict[str, Any]],
    runs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if previous is None:
        return None
    summary_path = previous / "summary.json"
    summary = object_path(summary_path, "previous summary")
    if summary.get("protocol") != OUTPUT_PROTOCOL or (summary.get("inputs") or {}).get("protocol_sha256") != protocol_sha:
        raise VerificationError("previous summary contract failed")
    prior_archives = lines(previous / "cohort_archives.jsonl", ARCHIVE_KEYS, "previous archives")
    prior_runs = lines(previous / "cohort_runs.jsonl", RUN_KEYS, "previous runs")
    outputs = summary.get("outputs") or {}
    if (
        digest(previous / "cohort_archives.jsonl") != sha(outputs.get("cohort_archives_sha256"), "previous archives SHA")
        or digest(previous / "cohort_runs.jsonl") != sha(outputs.get("cohort_runs_sha256"), "previous runs SHA")
        or archives[: len(prior_archives)] != prior_archives
        or runs[: len(prior_runs)] != prior_runs
    ):
        raise VerificationError("previous append-only prefix failed")
    if summary.get("status") == "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD" and (
        archives != prior_archives or runs != prior_runs
    ):
        raise VerificationError("previous closed cohort changed")
    return {
        "previous_summary_sha256": digest(summary_path),
        "previous_status": summary.get("status"),
        "previous_archives": len(prior_archives),
        "previous_runs": len(prior_runs),
        "exact_prefix_survived": True,
    }


def verify(
    protocol_path: Path,
    expected_protocol_sha: str,
    state: Path,
    source: Path,
    repo: Path,
    cohort: Path,
    receipt: Path,
    previous: Path | None = None,
) -> dict[str, Any]:
    if receipt.exists():
        raise VerificationError("refusing to overwrite verification receipt")
    protocol = protocol_state(protocol_path, expected_protocol_sha)
    transactions, snapshot_inputs = latest_transactions(state)
    ordered, observations, observations_sha = observation_order(state, source, protocol)
    transaction_by_path = {row["archive_relative_path"]: row for row in transactions}
    cutoff = protocol["cohort_closure"]["start_after_archive_mtime_ns"]
    future_transactions = [
        row for row in transactions
        if observations.get(row["archive_relative_path"], {}).get("mtime_ns", -1) > cutoff
    ]
    for transaction in future_transactions:
        entry = observations.get(transaction["archive_relative_path"])
        if (
            entry is None
            or entry.get("committed_archive_sha256") != transaction["archive_sha256"]
            or entry.get("rejected_archive_sha256") is not None
            or entry.get("size") != transaction["archive_size"]
        ):
            raise VerificationError("future transaction/observation binding failed")

    settled: list[tuple[int, bytes, str, dict[str, Any]]] = []
    pending: int | None = None
    rejected_count = 0
    for index, item in enumerate(ordered):
        committed = item[3].get("committed_archive_sha256")
        rejected = item[3].get("rejected_archive_sha256")
        if committed is None and rejected is None:
            pending = index
            break
        if committed is not None:
            transaction = transaction_by_path.get(item[2])
            if transaction is None or transaction["archive_sha256"] != committed:
                raise VerificationError("settled accepted archive lacks transaction")
        else:
            rejected_count += 1
        settled.append(item)
    if pending is not None and any(
        item[3].get("committed_archive_sha256") is not None
        or item[3].get("rejected_archive_sha256") is not None
        for item in ordered[pending + 1 :]
    ):
        raise VerificationError("settled archive follows unresolved ordering gap")

    target = protocol["cohort_closure"]["accepted_unique_physical_run_target"]
    expected_archives: list[dict[str, Any]] = []
    expected_runs: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    intake_shas: dict[str, str] = {}
    provenance_shas: dict[str, str] = {}
    boundary: str | None = None
    for mtime_ns, _, name, entry in settled:
        transaction = transaction_by_path.get(name)
        if transaction is None:
            continue
        archive_runs, summary_sha, provenance_sha = intake_runs(transaction, state)
        for row in archive_runs:
            if row["run_id"] in seen_runs:
                raise VerificationError("duplicate physical run across future archives")
            seen_runs.add(row["run_id"])
        expected_runs.extend(archive_runs)
        intake_shas[transaction["drop_id"]] = summary_sha
        provenance_shas[transaction["drop_id"]] = provenance_sha
        expected_archives.append({
            "archive_relative_path": name,
            "archive_sha256": transaction["archive_sha256"],
            "archive_size": entry["size"],
            "cumulative_unique_physical_runs": len(expected_runs),
            "drop_id": transaction["drop_id"],
            "intake_summary_sha256": summary_sha,
            "mtime_ns": mtime_ns,
            "physical_runs": len(archive_runs),
            "source_provenance_sha256": provenance_sha,
        })
        if len(expected_runs) >= target:
            boundary = name
            break
    expected_status = (
        "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        if boundary is not None
        else "FUTURE_COHORT_COLLECTING"
    )
    actual_archives_path = cohort / "cohort_archives.jsonl"
    actual_runs_path = cohort / "cohort_runs.jsonl"
    actual_archives = lines(actual_archives_path, ARCHIVE_KEYS, "cohort archives")
    actual_runs = lines(actual_runs_path, RUN_KEYS, "cohort runs")
    if actual_archives != expected_archives or actual_runs != expected_runs:
        raise VerificationError("cohort rows differ from independent reconstruction")
    if actual_archives_path.read_bytes() != canonical_lines(expected_archives) or actual_runs_path.read_bytes() != canonical_lines(expected_runs):
        raise VerificationError("cohort JSONL is not canonical")
    previous_value = previous_attestation(
        previous, sha(expected_protocol_sha, "protocol SHA"), expected_archives, expected_runs
    )
    summary_path = cohort / "summary.json"
    summary = object_path(summary_path, "cohort summary")
    task_counts = collections.Counter(row["task"] for row in expected_runs)
    pending_head = None if pending is None else {
        "archive_relative_path": ordered[pending][2], "mtime_ns": ordered[pending][0]
    }
    expected_inputs = {
        "protocol_sha256": sha(expected_protocol_sha, "protocol SHA"),
        "observations_sha256": observations_sha,
        **snapshot_inputs,
        "intake_summary_sha256": dict(sorted(intake_shas.items())),
        "source_provenance_sha256": dict(sorted(provenance_shas.items())),
    }
    if (
        summary.get("protocol") != OUTPUT_PROTOCOL
        or summary.get("status") != expected_status
        or summary.get("source_commit") != current_commit(repo)
        or summary.get("inputs") != expected_inputs
        or summary.get("closure") != {
            "accepted_unique_physical_run_target": target,
            "boundary_archive": boundary,
            "complete_boundary_archive_included": boundary is not None,
            "remaining_runs_to_target": max(0, target - len(expected_runs)),
            "settled_archive_prefix": len(settled),
            "accepted_archives_in_cohort": len(expected_archives),
            "structurally_rejected_in_settled_prefix": rejected_count,
            "pending_head": pending_head,
            "append_only_previous": previous_value,
        }
        or summary.get("inventory") != {
            "observed_future_archives": len(ordered),
            "future_transactions": len(future_transactions),
            "selected_archives": len(expected_archives),
            "selected_physical_runs": len(expected_runs),
            "selected_tasks": len(task_counts),
            "per_task_selected_runs": dict(sorted(task_counts.items())),
        }
    ):
        raise VerificationError("cohort summary reconstruction mismatch")
    outputs = summary.get("outputs") or {}
    if (
        digest(actual_archives_path) != sha(outputs.get("cohort_archives_sha256"), "cohort archive SHA")
        or digest(actual_runs_path) != sha(outputs.get("cohort_runs_sha256"), "cohort run SHA")
        or summary.get("integrity") != {
            "initial_archive_bindings_pass": True,
            "archive_order": "mtime_ns_then_relative_path_utf8_bytes",
            "settled_prefix_only": True,
            "partial_archive_salvage": False,
            "unique_physical_runs": True,
        }
    ):
        raise VerificationError("cohort output/integrity binding mismatch")
    blindness = summary.get("blindness") or {}
    for key in (
        "raw_archive_payload_opened",
        "blind_code_view_opened",
        "label_vault_opened",
        "score_directory_opened",
        "score_or_outcome_opened",
        "truth_support_computed",
        "replay_submission_authorized",
    ):
        if blindness.get(key) is not False:
            raise VerificationError(f"cohort blindness failed: {key}")
    expected_opened = {
        protocol_path.name,
        "LATEST",
        "SHA256SUMS",
        "transactions.jsonl",
        "observations.json",
    }
    if expected_archives:
        expected_opened.update(
            {"summary.json", "archive_manifest.tsv", "source_provenance.json"}
        )
    if blindness.get("opened_basenames") != sorted(expected_opened):
        raise VerificationError("producer opened-basename attestation mismatch")
    implementation = summary.get("implementation") or {}
    producer_path = repo / "phase1" / "score_channel_future_cohort.py"
    if implementation.get("script_sha256") != digest(producer_path):
        raise VerificationError("producer script hash mismatch")

    value = {
        "protocol": "score-channel-future-identity-cohort-independent-verifier-v1",
        "status": (
            "PASS_IDENTITY_CLOSED_TRUTH_UNREAD"
            if boundary is not None
            else "PASS_COLLECTING_TRUTH_UNREAD"
        ),
        "implementation_independent_of_producer": True,
        "producer_module_imported": False,
        "initial_archive_bindings_reconstructed": True,
        "snapshot_transaction_binding_reconstructed": True,
        "settled_prefix_reconstructed": True,
        "structural_rejections_excluded": True,
        "complete_boundary_archive_reconstructed": True,
        "append_only_previous_reconstructed": previous is not None,
        "selected_archives": len(expected_archives),
        "selected_physical_runs": len(expected_runs),
        "selected_tasks": len(task_counts),
        "cohort_summary_sha256": digest(summary_path),
        "cohort_archives_sha256": digest(actual_archives_path),
        "cohort_runs_sha256": digest(actual_runs_path),
        "raw_archive_payload_opened": False,
        "blind_code_view_opened": False,
        "label_vault_opened": False,
        "score_directory_opened": False,
        "score_or_outcome_opened": False,
        "truth_support_computed": False,
        "replay_submission_authorized": False,
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_name(receipt.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, receipt)
    return value


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", default=FROZEN_PROTOCOL_SHA256)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--previous-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        value = verify(
            args.protocol,
            args.expect_protocol_sha256,
            args.state_root,
            args.source_root,
            args.repo_root,
            args.cohort_dir,
            args.receipt,
            args.previous_dir,
        )
    except (VerificationError, OSError, ValueError, UnicodeError, json.JSONDecodeError) as error:
        print(f"FUTURE_COHORT_VERIFY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
