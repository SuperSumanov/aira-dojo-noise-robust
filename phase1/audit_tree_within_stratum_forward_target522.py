#!/usr/bin/env python3
"""Outcome-blind Target-522 audit on a disjoint forward physical-run increment."""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import os
import platform
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from phase1 import decompose_tree_linearization_within_strata as math_impl


PROTOCOL_NAME = "tree-linearization-within-stratum-forward-target522-v2"
RECEIPT_PROTOCOL = "tree-linearization-within-stratum-forward-target522-receipt-v2"
RECEIPT_STATUS = "OUTCOME_BLIND_FORWARD_INCREMENT_AUDIT_COMPLETE"
MONITOR_SCRIPT = "phase1/scripts/latch_tree_within_stratum_forward_target522_20260828.sh"
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
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
RUN_KEYS = {
    "run_id",
    "task",
    "drop_id",
    "flow_status",
    "endpoints",
    "generation_started_at_utc",
    "source_sha256",
}
OBSERVED_HEADER = (
    "snapshot_sha256\truns\tendpoints\ttasks\tsummary_sha256\tregistry_sha256\t"
    "runs_sha256\tobserved_at_utc"
)
CREDENTIAL_RE = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    rb"AIza[0-9A-Za-z_-]{30,}|Bearer[ \t]+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class ForwardAuditError(RuntimeError):
    """Raised when any frozen selection, population, or exact gate fails integrity."""


@dataclass
class BlindSnapshot:
    snapshot_sha256: str
    cards: dict[str, dict[str, Any]]
    card_payloads: dict[str, dict[str, Any]]
    card_raw_rows: dict[str, bytes]
    runs: dict[str, dict[str, Any]]
    run_raw_rows: dict[str, bytes]
    registry_raw_rows: tuple[bytes, ...]
    bindings: dict[str, Any]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardAuditError(message)


def valid_sha(value: Any, label: str) -> str:
    require(isinstance(value, str) and SHA_RE.fullmatch(value) is not None, f"invalid {label}")
    return value


def valid_integer(value: Any, label: str, minimum: int = 0) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool) and value >= minimum,
        f"invalid {label}",
    )
    return value


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def read_rows_raw(path: Path) -> list[tuple[dict[str, Any], bytes]]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSONL: {path}")
    rows: list[tuple[dict[str, Any], bytes]] = []
    with path.open("rb") as handle:
        for number, raw in enumerate(handle, 1):
            require(bool(raw.strip()), f"blank JSONL row: {path.name}:{number}")
            value = json.loads(raw.decode("utf-8"))
            require(isinstance(value, dict), f"non-object JSONL row: {path.name}:{number}")
            rows.append((value, raw))
    return rows


def validate_snapshot_graph(cards: dict[str, dict[str, Any]]) -> None:
    parent_of: dict[str, str] = {}
    for card_id, card in cards.items():
        parent = card["parent"]
        if parent not in cards:
            continue
        require(parent != card_id, "snapshot self-parent edge")
        require(cards[parent]["run"] == card["run"], "snapshot parent edge crosses physical runs")
        require(cards[parent]["task"] == card["task"], "snapshot parent edge crosses tasks")
        parent_of[card_id] = parent
    state: dict[str, int] = {}
    for start in cards:
        trail: list[str] = []
        cursor = start
        while cursor in parent_of and state.get(cursor, 0) == 0:
            state[cursor] = 1
            trail.append(cursor)
            cursor = parent_of[cursor]
        require(state.get(cursor, 0) != 1, "snapshot graph contains a cycle")
        for node in trail:
            state[node] = 2


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    actual = sha256_file(path)
    require(actual == expected_sha, "protocol SHA mismatch")
    protocol = read_object(path)
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(
        protocol.get("status")
        == "OUTCOME_BLIND_PROTOCOL_AMENDED_BEFORE_TARGET522_SELECTION_OR_INCREMENT_PROFILE",
        "protocol status mismatch",
    )
    amendment = protocol.get("pre_candidate_integrity_amendment")
    require(isinstance(amendment, dict), "missing pre-candidate amendment")
    require(amendment.get("candidate_snapshot_identity_seen") is False, "candidate seen before amendment")
    require(amendment.get("increment_profile_seen") is False, "profile seen before amendment")
    require(
        amendment.get("scientific_population_estimand_thresholds_or_classification_changed") is False,
        "scientific contract changed in integrity amendment",
    )
    return protocol, actual


def load_blind_snapshot(state_root: Path, snapshot_sha256: str) -> BlindSnapshot:
    snapshot_sha = valid_sha(snapshot_sha256, "snapshot SHA")
    state = state_root.resolve()
    require(state.is_dir() and not state_root.is_symlink(), "unsafe state root")
    snapshot_raw = state / "snapshots" / snapshot_sha
    require(snapshot_raw.is_dir() and not snapshot_raw.is_symlink(), "unsafe snapshot root")
    snapshot = snapshot_raw.resolve()
    require(snapshot.parent == state / "snapshots" and snapshot.name == snapshot_sha, "snapshot path mismatch")

    registry_path = snapshot / "intake_registry.jsonl"
    summary_path = snapshot / "accumulator" / "summary.json"
    runs_path = snapshot / "accumulator" / "provisional_runs.jsonl"
    summary = read_object(summary_path)
    require(summary.get("protocol") == "prospective_accumulator_v1", "accumulator protocol mismatch")
    security = summary.get("security")
    require(
        isinstance(security, dict)
        and security.get("label_vault_opened") is False
        and security.get("outcome_files_opened") == []
        and security.get("scorer_prediction_files_opened") == [],
        "accumulator is not outcome blind",
    )
    require(summary.get("closure", {}).get("provided") is False, "unexpected closure state")
    registry_sha = sha256_file(registry_path)
    runs_sha = sha256_file(runs_path)
    require(summary.get("inputs", {}).get("registry_sha256") == registry_sha, "registry binding mismatch")
    require(
        summary.get("outputs", {}).get("provisional_runs_sha256") == runs_sha,
        "run-ledger binding mismatch",
    )
    expected_summaries = summary.get("inputs", {}).get("intake_summaries")
    require(isinstance(expected_summaries, dict), "intake summary bindings missing")

    cards: dict[str, dict[str, Any]] = {}
    card_payloads: dict[str, dict[str, Any]] = {}
    card_raw_rows: dict[str, bytes] = {}
    run_owner: dict[str, str] = {}
    seen_drops: set[str] = set()
    binding_sequence: list[tuple[str, str]] = []
    registry_rows = read_rows_raw(registry_path)
    for entry, _raw_entry in registry_rows:
        require(set(entry) == {"drop_id", "intake_dir", "summary_sha256"}, "registry schema mismatch")
        drop_id = entry.get("drop_id")
        require(
            isinstance(drop_id, str) and bool(drop_id) and drop_id not in seen_drops,
            "invalid or duplicate drop",
        )
        seen_drops.add(drop_id)
        intake_raw = Path(entry["intake_dir"])
        require(not intake_raw.is_symlink(), "symlink intake")
        intake = intake_raw.resolve()
        require(intake.parent == state / "intakes" and intake.name == drop_id, "intake path mismatch")
        summary_sha = valid_sha(entry.get("summary_sha256"), "intake summary SHA")
        intake_summary_path = intake / "summary.json"
        require(sha256_file(intake_summary_path) == summary_sha, "intake summary SHA mismatch")
        require(expected_summaries.get(drop_id) == summary_sha, "intake summary not accumulator-bound")
        intake_summary = read_object(intake_summary_path)
        outputs = intake_summary.get("outputs")
        intake_security = intake_summary.get("security")
        blindness = intake_summary.get("blindness")
        require(
            all(isinstance(item, dict) for item in (outputs, intake_security, blindness)),
            "intake contract missing",
        )
        require(
            intake_security.get("env_members_read") is False
            and intake_security.get("live_event_journal_members_read") is False
            and blindness.get("labels_used_for_run_selection") is False
            and blindness.get("labels_used_for_endpoint_selection") is False
            and blindness.get("metrics_computed") == [],
            "intake blindness contract failed",
        )
        manifest_sha = valid_sha(outputs.get("eligible_blind_manifest_sha256"), "manifest SHA")
        manifest_path = intake / "eligible_blind_manifest.jsonl"
        require(manifest_path.is_file() and not manifest_path.is_symlink(), "unsafe blind manifest")
        manifest_raw = manifest_path.read_bytes()
        require(sha256_bytes(manifest_raw) == manifest_sha, "blind manifest SHA mismatch")
        require(CREDENTIAL_RE.search(manifest_raw) is None, "credential-shaped bytes in blind manifest")
        binding_sequence.append((summary_sha, manifest_sha))
        for row, raw_row in read_rows_raw(manifest_path):
            require(set(row) == BLIND_KEYS, "blind manifest schema mismatch")
            lineage = row.get("lineage")
            require(isinstance(lineage, dict) and set(lineage) == LINEAGE_KEYS, "lineage schema mismatch")
            card_id, task, run_id = row.get("card_id"), row.get("task"), row.get("run_id")
            code, parent = row.get("code"), lineage.get("parent")
            require(
                all(isinstance(value, str) and bool(value) for value in (card_id, task, run_id, code, parent))
                and card_id not in cards,
                "invalid or duplicate endpoint",
            )
            require(sha256_bytes(code.encode()) == valid_sha(row.get("code_sha256"), "code SHA"), "code SHA mismatch")
            valid_sha(row.get("source_sha256"), "endpoint source SHA")
            require(
                isinstance(row.get("generation_started_at_utc"), str)
                and bool(row["generation_started_at_utc"]),
                "invalid endpoint generation time",
            )
            for key in ("depth", "step", "n_siblings"):
                valid_integer(lineage.get(key), f"lineage {key}")
            require(isinstance(lineage.get("op"), str) and bool(lineage["op"]), "invalid lineage op")
            owner = run_owner.setdefault(run_id, drop_id)
            require(owner == drop_id, "physical run spans intake drops")
            cards[card_id] = {
                "task": task,
                "run": run_id,
                "parent": parent,
                "depth": lineage["depth"],
            }
            card_payloads[card_id] = row
            card_raw_rows[card_id] = raw_row

    require(set(expected_summaries) == seen_drops, "accumulator has unregistered intake bindings")
    runs: dict[str, dict[str, Any]] = {}
    run_raw_rows: dict[str, bytes] = {}
    run_rows = read_rows_raw(runs_path)
    for row, raw_row in run_rows:
        require(set(row) == RUN_KEYS, "run-ledger schema mismatch")
        run_id = row.get("run_id")
        require(isinstance(run_id, str) and bool(run_id) and run_id not in runs, "invalid or duplicate run")
        require(row.get("flow_status") == "scoreable", "non-scoreable provisional run")
        require(row.get("drop_id") == run_owner.get(run_id), "run/drop mismatch")
        require(isinstance(row.get("task"), str) and bool(row["task"]), "invalid run task")
        valid_integer(row.get("endpoints"), "run endpoint count", minimum=1)
        valid_sha(row.get("source_sha256"), "run source SHA")
        require(
            isinstance(row.get("generation_started_at_utc"), str)
            and bool(row["generation_started_at_utc"]),
            "invalid run generation time",
        )
        runs[run_id] = row
        run_raw_rows[run_id] = raw_row

    by_run = collections.Counter(card["run"] for card in cards.values())
    require(set(by_run) == set(runs), "card/run population mismatch")
    for run_id, row in runs.items():
        require(by_run[run_id] == row["endpoints"], "run endpoint count mismatch")
    for card in cards.values():
        require(runs[card["run"]]["task"] == card["task"], "card/run task mismatch")
    validate_snapshot_graph(cards)

    observed = {
        "runs": len(runs),
        "endpoints": len(cards),
        "tasks": len({card["task"] for card in cards.values()}),
    }
    inventory = summary.get("inventory", {})
    require(
        inventory.get("provisional_first960_runs") == observed["runs"]
        and inventory.get("provisional_first960_endpoints") == observed["endpoints"],
        "accumulator inventory mismatch",
    )
    require(
        summary.get("task_support", {}).get("provisional_first960", {}).get("tasks")
        == observed["tasks"],
        "accumulator task count mismatch",
    )
    return BlindSnapshot(
        snapshot_sha256=snapshot_sha,
        cards=cards,
        card_payloads=card_payloads,
        card_raw_rows=card_raw_rows,
        runs=runs,
        run_raw_rows=run_raw_rows,
        registry_raw_rows=tuple(raw for _row, raw in registry_rows),
        bindings={
            "snapshot_sha256": snapshot_sha,
            "registry_sha256": registry_sha,
            "accumulator_summary_sha256": sha256_file(summary_path),
            "provisional_runs_sha256": runs_sha,
            "intake_summary_manifest_sequence_sha256": canonical_sha(binding_sequence),
            "intake_count": len(registry_rows),
            **observed,
        },
    )


def parse_key_values(path: Path) -> dict[str, str]:
    require(path.is_file() and not path.is_symlink(), f"unsafe key-value file: {path}")
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        require("=" in line, f"invalid key-value row: {path.name}:{number}")
        key, value = line.split("=", 1)
        require(bool(key) and key not in values, f"duplicate key: {path.name}:{number}")
        values[key] = value
    return values


def verify_sha256sums(root: Path) -> dict[str, str]:
    manifest_path = root / "SHA256SUMS"
    require(manifest_path.is_file() and not manifest_path.is_symlink(), "unsafe SHA256SUMS")
    entries: dict[str, str] = {}
    for number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  \./([A-Za-z0-9._-]+)", line)
        require(match is not None, f"invalid SHA256SUMS row {number}")
        digest, name = match.groups()
        require(name not in entries, "duplicate SHA256SUMS member")
        entries[name] = digest
    actual = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS", "COMPLETE"}
    }
    require(set(entries) == actual, "SHA256SUMS membership mismatch")
    for name, expected in entries.items():
        require(sha256_file(root / name) == expected, f"selection member hash mismatch: {name}")
    return entries


def parse_observed(path: Path) -> list[dict[str, Any]]:
    require(path.is_file() and not path.is_symlink(), "unsafe observed journal")
    lines = path.read_text(encoding="utf-8").splitlines()
    require(bool(lines) and lines[0] == OBSERVED_HEADER, "observed journal header mismatch")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous_runs = -1
    for number, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        require(len(fields) == 8, f"observed journal width mismatch: {number}")
        snapshot, runs, endpoints, tasks, summary_sha, registry_sha, runs_sha, observed_at = fields
        valid_sha(snapshot, "observed snapshot SHA")
        require(snapshot not in seen, "duplicate observed snapshot")
        seen.add(snapshot)
        require(all(text.isdigit() for text in (runs, endpoints, tasks)), "non-integer observed count")
        counts = [int(runs), int(endpoints), int(tasks)]
        require(all(value > 0 for value in counts), "non-positive observed count")
        require(counts[0] >= previous_runs, "observed run count regressed")
        previous_runs = counts[0]
        rows.append(
            {
                "snapshot_sha256": snapshot,
                "runs": counts[0],
                "endpoints": counts[1],
                "tasks": counts[2],
                "summary_sha256": valid_sha(summary_sha, "observed summary SHA"),
                "registry_sha256": valid_sha(registry_sha, "observed registry SHA"),
                "runs_sha256": valid_sha(runs_sha, "observed runs SHA"),
                "observed_at_utc": observed_at,
                "raw_first_seven": "\t".join(fields[:7]),
            }
        )
    require(bool(rows), "empty observed journal")
    return rows


def verify_selection(
    selection_root: Path,
    repo_root: Path,
    protocol: dict[str, Any],
    protocol_sha256: str,
) -> dict[str, Any]:
    root = selection_root.resolve()
    require(selection_root.is_dir() and not selection_root.is_symlink(), "unsafe selection root")
    allowed = set(protocol["security"]["selection_support_input_basenames"])
    members = list(root.iterdir())
    require(all(path.is_file() and not path.is_symlink() for path in members), "unsafe selection member")
    actual = {path.name for path in members}
    require(actual == allowed, "selection-support basename set mismatch")
    require((root / "COMPLETE").stat().st_size == 0, "COMPLETE marker is not empty")
    hashes = verify_sha256sums(root)
    require(sha256_file(root / "protocol.json") == protocol_sha256, "selection protocol SHA mismatch")

    protocol_path = repo_root.resolve() / "phase1" / "tree_linearization_within_stratum_forward_target522_v2.json"
    monitor_path = repo_root.resolve() / MONITOR_SCRIPT
    require(protocol_path.is_file() and not protocol_path.is_symlink(), "unsafe repository protocol")
    require(monitor_path.is_file() and not monitor_path.is_symlink(), "unsafe repository monitor source")
    require((root / "protocol.json").read_bytes() == protocol_path.read_bytes(), "selection protocol bytes mismatch")
    require((root / "source_script.sh").read_bytes() == monitor_path.read_bytes(), "selection source bytes mismatch")
    security_lines = (root / "security_scan_receipt.txt").read_text(encoding="utf-8").splitlines()
    require(
        security_lines == ["boundary_aware_credential_file_hits=0", "credential_filename_hits=0"],
        "selection security scan mismatch",
    )
    require((root / "monitor.lock").stat().st_size == 0, "monitor lock file is not empty")
    monitor_pid = (root / "monitor.pid").read_text(encoding="utf-8").strip()
    require(monitor_pid.isdigit() and int(monitor_pid) > 0, "invalid monitor PID receipt")
    preflight = (root / "preflight_13.txt").read_text(encoding="utf-8").splitlines()
    require(len(preflight) == 13 and all(line.endswith("PASS") for line in preflight), "preflight receipt mismatch")

    ready = parse_key_values(root / "READY")
    required_ready = {
        "status",
        "completed_at_utc",
        "source_commit",
        "protocol_sha256",
        "baseline_snapshot_sha256",
        "baseline_runs",
        "candidate_snapshot_sha256",
        "candidate_runs",
        "candidate_endpoints",
        "candidate_tasks",
        "disjoint_increment_runs",
        "candidate_summary_sha256",
        "candidate_registry_sha256",
        "candidate_runs_sha256",
        "manual_snapshot_choice",
        "earlier_observed_target_crossing_skipped",
        "profile_values_read_for_selection",
        "prospective_outcomes_or_prediction_values_read",
        "raw_senior_archives_opened",
        "gpu_api_model_fit_base_update",
    }
    require(set(ready) == required_ready, "READY schema mismatch")
    require(ready["status"] == "TARGET522_FIRST_OBSERVED_CROSSING_READY", "READY status mismatch")
    require(COMMIT_RE.fullmatch(ready["source_commit"]) is not None, "invalid selection source commit")
    require(ready["protocol_sha256"] == protocol_sha256, "READY protocol mismatch")
    baseline = protocol["freeze_state"]["baseline_snapshot_sha256"]
    target = protocol["activation_rule"]["target_total_physical_runs"]
    minimum_increment = protocol["activation_rule"]["minimum_disjoint_increment_physical_runs"]
    baseline_runs = protocol["freeze_state"]["baseline_counts"]["provisional_first960_runs"]
    require(ready["baseline_snapshot_sha256"] == baseline, "READY baseline mismatch")
    require(ready["baseline_runs"] == str(baseline_runs), "READY baseline count mismatch")
    candidate = valid_sha(ready["candidate_snapshot_sha256"], "candidate snapshot SHA")
    for key in ("candidate_runs", "candidate_endpoints", "candidate_tasks", "disjoint_increment_runs"):
        require(ready[key].isdigit() and int(ready[key]) > 0, f"invalid READY count: {key}")
    require(int(ready["candidate_runs"]) >= target, "candidate below target")
    require(int(ready["disjoint_increment_runs"]) >= minimum_increment, "candidate increment below target")
    require(
        int(ready["disjoint_increment_runs"]) == int(ready["candidate_runs"]) - baseline_runs,
        "READY increment arithmetic mismatch",
    )
    for key in ("candidate_summary_sha256", "candidate_registry_sha256", "candidate_runs_sha256"):
        valid_sha(ready[key], key)
    require(ready["manual_snapshot_choice"] == "false", "manual selection indicated")
    require(ready["earlier_observed_target_crossing_skipped"] == "false", "crossing skip indicated")
    require(ready["profile_values_read_for_selection"] == "false", "profile read during selection")
    require(
        ready["prospective_outcomes_or_prediction_values_read"] == "false",
        "prospective value read during selection",
    )
    require(ready["raw_senior_archives_opened"] == "false", "raw archive opened during selection")
    require(ready["gpu_api_model_fit_base_update"] == "0/0/0/0", "selection resource contract mismatch")

    observed = parse_observed(root / "observed.tsv")
    require(observed[0]["snapshot_sha256"] == baseline, "observed journal baseline mismatch")
    require(observed[0]["runs"] == baseline_runs, "observed baseline count mismatch")
    crossings = [row for row in observed if row["runs"] >= target]
    require(bool(crossings) and crossings[0]["snapshot_sha256"] == candidate, "candidate is not first observed crossing")
    candidate_rows = [row for row in observed if row["snapshot_sha256"] == candidate]
    require(len(candidate_rows) == 1, "candidate journal multiplicity mismatch")
    candidate_row = candidate_rows[0]
    candidate_tsv = (root / "candidate.tsv").read_text(encoding="utf-8").rstrip("\n")
    require(candidate_tsv == candidate_row["raw_first_seven"], "candidate.tsv mismatch")
    require(candidate_row["runs"] == int(ready["candidate_runs"]), "candidate run count mismatch")
    require(candidate_row["endpoints"] == int(ready["candidate_endpoints"]), "candidate endpoint count mismatch")
    require(candidate_row["tasks"] == int(ready["candidate_tasks"]), "candidate task count mismatch")
    require(candidate_row["summary_sha256"] == ready["candidate_summary_sha256"], "candidate summary hash mismatch")
    require(candidate_row["registry_sha256"] == ready["candidate_registry_sha256"], "candidate registry hash mismatch")
    require(candidate_row["runs_sha256"] == ready["candidate_runs_sha256"], "candidate runs hash mismatch")

    monitor_lines = (root / "monitor.log").read_text(encoding="utf-8").splitlines()
    latch_lines = [line for line in monitor_lines if " candidate_latched " in line]
    require(len(latch_lines) == 1 and f"snapshot={candidate}" in latch_lines[0], "candidate latch log mismatch")
    post_latch = monitor_lines[monitor_lines.index(latch_lines[0]) + 1 :]
    stable_values = []
    for line in post_latch:
        match = re.search(rf" candidate={re.escape(candidate)} stable=([0-9]+)$", line)
        if match:
            stable_values.append(int(match.group(1)))
    required_stability = protocol["activation_rule"]["candidate_must_be_hash_stable_for_consecutive_polls"]
    require(stable_values[-(required_stability - 1) :] == list(range(1, required_stability)), "stable poll log mismatch")
    return {
        "baseline_snapshot_sha256": baseline,
        "candidate_snapshot_sha256": candidate,
        "selection_source_commit": ready["source_commit"],
        "candidate_counts": {
            "runs": candidate_row["runs"],
            "endpoints": candidate_row["endpoints"],
            "tasks": candidate_row["tasks"],
        },
        "baseline_observation": observed[0],
        "candidate_observation": candidate_row,
        "selection_support_sha256sums_sha256": sha256_file(root / "SHA256SUMS"),
        "selection_monitor_source_sha256": hashes["source_script.sh"],
        "selection_member_hashes": hashes,
        "checks": {
            "complete_hash_bound_selection_package": True,
            "monitor_source_and_protocol_bytes_exact": True,
            "candidate_is_first_observed_target_crossing": True,
            "candidate_hash_stability_log_and_completion_exact": True,
            "selection_used_no_profile_or_prospective_values": True,
        },
    }


def disjoint_increment(
    baseline: BlindSnapshot,
    candidate: BlindSnapshot,
    protocol: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    baseline_run_ids = set(baseline.runs)
    candidate_run_ids = set(candidate.runs)
    baseline_card_ids = set(baseline.cards)
    candidate_card_ids = set(candidate.cards)
    require(baseline_run_ids <= candidate_run_ids, "baseline runs are not a candidate subset")
    require(baseline_card_ids <= candidate_card_ids, "baseline endpoints are not a candidate subset")
    require(
        candidate.registry_raw_rows[: len(baseline.registry_raw_rows)] == baseline.registry_raw_rows,
        "registry is not an exact append-only prefix",
    )
    require(
        list(candidate.run_raw_rows)[: len(baseline.run_raw_rows)] == list(baseline.run_raw_rows),
        "run-ledger order is not append-only",
    )
    for run_id in baseline_run_ids:
        require(candidate.runs[run_id] == baseline.runs[run_id], "old run payload changed")
        require(candidate.run_raw_rows[run_id] == baseline.run_raw_rows[run_id], "old run bytes changed")
    for card_id in baseline_card_ids:
        require(candidate.card_payloads[card_id] == baseline.card_payloads[card_id], "old endpoint payload changed")
        require(candidate.card_raw_rows[card_id] == baseline.card_raw_rows[card_id], "old endpoint bytes changed")

    new_run_ids = candidate_run_ids - baseline_run_ids
    new_card_ids = candidate_card_ids - baseline_card_ids
    minimum = protocol["activation_rule"]["minimum_disjoint_increment_physical_runs"]
    require(len(new_run_ids) >= minimum, "disjoint run increment below target")
    require(
        all(candidate.cards[card_id]["run"] in new_run_ids for card_id in new_card_ids),
        "new endpoint belongs to an old run",
    )
    require(
        all(candidate.cards[card_id]["run"] not in new_run_ids for card_id in baseline_card_ids),
        "old endpoint belongs to a new run",
    )
    increment_cards = {card_id: candidate.cards[card_id] for card_id in new_card_ids}
    increment_runs = {run_id: candidate.runs[run_id] for run_id in new_run_ids}
    by_run = collections.Counter(card["run"] for card in increment_cards.values())
    require(set(by_run) == new_run_ids, "increment card/run set mismatch")
    for run_id, row in increment_runs.items():
        require(by_run[run_id] == row["endpoints"], "partial physical run in increment")
    return increment_cards, increment_runs, {
        "baseline_runs_exact_subset": True,
        "baseline_endpoints_exact_subset": True,
        "registry_exact_append_only_prefix": True,
        "run_ledger_exact_append_only_order": True,
        "old_run_payloads_and_bytes_unchanged": True,
        "old_endpoint_payloads_and_bytes_unchanged": True,
        "increment_contains_only_complete_new_physical_runs": True,
        "baseline_runs": len(baseline.runs),
        "candidate_runs": len(candidate.runs),
        "increment_runs": len(increment_runs),
        "baseline_endpoints": len(baseline.cards),
        "candidate_endpoints": len(candidate.cards),
        "increment_endpoints": len(increment_cards),
    }


def math_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    adapted = copy.deepcopy(protocol)
    gates = adapted["strong_positive_gates"]
    gates["minimum_task_canonical_standardized_within_tv_integrity_floor"] = gates[
        "minimum_task_canonical_standardized_within_tv"
    ]
    gates["minimum_physical_run_canonical_standardized_within_tv_integrity_floor"] = gates[
        "minimum_physical_run_canonical_standardized_within_tv"
    ]
    support = adapted["hard_integrity_and_support_gates"]
    support["minimum_conditionable_tasks"] = support["minimum_conditionable_tasks_in_increment"]
    support["minimum_conditionable_physical_runs"] = support[
        "minimum_conditionable_physical_runs_in_increment"
    ]
    return adapted


def classify(summary: dict[str, Any], protocol: dict[str, Any], hard: dict[str, bool]) -> str:
    if not all(hard.values()):
        result = "FORWARD_INCREMENT_WITHIN_STRATUM_GATE_FAIL"
    else:
        task_strong = summary["provisional_axis_strength"]["task"]
        run_strong = summary["provisional_axis_strength"]["physical_run"]
        task_tv = math_impl.exact_from_payload(
            summary["partitions"]["task"]["canonical_marginal_standardized_within_total_variation"],
            "task within TV",
        )
        run_tv = math_impl.exact_from_payload(
            summary["partitions"]["physical_run"]["canonical_marginal_standardized_within_total_variation"],
            "run within TV",
        )
        if task_strong and run_strong:
            result = "FORWARD_INCREMENT_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif task_strong:
            result = "FORWARD_INCREMENT_TASK_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif run_strong:
            result = "FORWARD_INCREMENT_RUN_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif task_tv > 0 or run_tv > 0:
            result = "FORWARD_INCREMENT_PROFILE_BELOW_STRONG_GATE"
        else:
            result = "FORWARD_INCREMENT_NO_OBSERVED_WITHIN_STRATUM_DISTORTION"
    require(result in protocol["ordered_classification"], "classification outside protocol")
    return result


def build_receipt(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha256: str,
    source_commit: str,
) -> dict[str, Any]:
    require(COMMIT_RE.fullmatch(source_commit) is not None, "invalid analysis source commit")
    protocol, actual_protocol_sha = load_protocol(protocol_path, protocol_sha256)
    selection = verify_selection(selection_root, repo_root, protocol, actual_protocol_sha)
    baseline = load_blind_snapshot(state_root, selection["baseline_snapshot_sha256"])
    candidate = load_blind_snapshot(state_root, selection["candidate_snapshot_sha256"])
    baseline_observation = selection["baseline_observation"]
    candidate_observation = selection["candidate_observation"]
    require(
        baseline.bindings["accumulator_summary_sha256"] == baseline_observation["summary_sha256"]
        and baseline.bindings["registry_sha256"] == baseline_observation["registry_sha256"]
        and baseline.bindings["provisional_runs_sha256"] == baseline_observation["runs_sha256"],
        "baseline observation bindings mismatch",
    )
    require(
        candidate.bindings["accumulator_summary_sha256"] == candidate_observation["summary_sha256"]
        and candidate.bindings["registry_sha256"] == candidate_observation["registry_sha256"]
        and candidate.bindings["provisional_runs_sha256"] == candidate_observation["runs_sha256"],
        "candidate observation bindings mismatch",
    )
    baseline_counts = protocol["freeze_state"]["baseline_counts"]
    require(
        baseline.bindings["runs"] == baseline_counts["provisional_first960_runs"]
        and baseline.bindings["endpoints"] == baseline_counts["eligible_endpoints"]
        and baseline.bindings["tasks"] == baseline_counts["tasks"],
        "baseline fixed counts mismatch",
    )
    require(candidate.bindings["runs"] == selection["candidate_counts"]["runs"], "candidate run count mismatch")
    require(
        candidate.bindings["endpoints"] == selection["candidate_counts"]["endpoints"],
        "candidate endpoint count mismatch",
    )
    require(candidate.bindings["tasks"] == selection["candidate_counts"]["tasks"], "candidate task count mismatch")

    increment_cards, increment_runs, append_only = disjoint_increment(baseline, candidate, protocol)
    try:
        edges, graph_inventory = math_impl.observed_edges(increment_cards)
        summary = math_impl.summarize_edges(edges, math_protocol(protocol))
    except math_impl.DecompositionError as error:
        raise ForwardAuditError(f"tree decomposition failed: {error}") from error
    parent_present = Fraction(len(edges), len(increment_cards))
    support = protocol["hard_integrity_and_support_gates"]
    hard = {
        **selection["checks"],
        "baseline_runs_and_endpoints_are_exact_subsets_of_candidate": True,
        "old_run_and_endpoint_rows_are_unchanged": True,
        "candidate_total_runs_at_least_target": len(candidate.runs)
        >= support["candidate_total_runs_at_least"],
        "disjoint_increment_runs_at_least_minimum": len(increment_runs)
        >= support["disjoint_increment_runs_at_least"],
        "candidate_accumulator_is_outcome_blind_and_unclosed": True,
        "observed_unique_edges_at_least_minimum": len(edges)
        >= support["minimum_observed_unique_edges_in_increment"],
        "parent_present_endpoint_fraction_at_least_minimum": parent_present
        >= Fraction(support["minimum_parent_present_endpoint_fraction_in_increment"]),
        "conditionable_tasks_at_least_minimum": summary["partitions"]["task"]["conditionable_groups"]
        >= support["minimum_conditionable_tasks_in_increment"],
        "conditionable_physical_runs_at_least_minimum": summary["partitions"]["physical_run"]["conditionable_groups"]
        >= support["minimum_conditionable_physical_runs_in_increment"],
        "all_gate_comparisons_use_exact_fractions": True,
        "decimal_strings_are_descriptive_only": True,
    }
    classification = classify(summary, protocol, hard)
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": RECEIPT_STATUS,
        "classification": classification,
        "protocol_sha256": actual_protocol_sha,
        "analysis_source_commit": source_commit,
        "selection_source_commit": selection["selection_source_commit"],
        "producer_source_sha256": sha256_file(Path(__file__)),
        "math_source_sha256": sha256_file(Path(math_impl.__file__)),
        "snapshot_bindings": {
            "baseline": baseline.bindings,
            "candidate": candidate.bindings,
            "selection_support": {
                "sha256sums_sha256": selection["selection_support_sha256sums_sha256"],
                "monitor_source_sha256": selection["selection_monitor_source_sha256"],
                "protocol_sha256": actual_protocol_sha,
            },
        },
        "append_only_and_increment": append_only,
        "inventory": {
            **summary["inventory"],
            **graph_inventory,
            "increment_endpoints": len(increment_cards),
            "increment_physical_runs": len(increment_runs),
            "increment_tasks": len({card["task"] for card in increment_cards.values()}),
            "parent_present_endpoints": len(edges),
            "parent_present_endpoint_fraction": math_impl.exact(parent_present),
        },
        "overall_edge_total_variation": summary["overall_edge_total_variation"],
        "partitions": summary["partitions"],
        "pre_registered_gate": {
            "hard_integrity_and_support": hard,
            "all_hard_gates_passed": all(hard.values()),
            "axis_strength": summary["provisional_axis_strength"],
            "fixed_thresholds": protocol["strong_positive_gates"],
        },
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "corpus_input_basenames": protocol["security"]["corpus_input_basenames"],
            "selection_support_input_basenames": protocol["security"][
                "selection_support_input_basenames"
            ],
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "randomness_used": False,
            "decimal_values_used_for_gates": False,
        },
    }


def write_once(path: Path, value: dict[str, Any]) -> None:
    require(not path.exists(), "refusing to overwrite output")
    require(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe output parent")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--selection-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = build_receipt(
            args.state_root,
            args.selection_root,
            args.repo_root,
            args.protocol,
            args.expect_protocol_sha256,
            args.source_commit,
        )
        write_once(args.out.resolve(), receipt)
    except (ForwardAuditError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 2
    print(receipt["classification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
