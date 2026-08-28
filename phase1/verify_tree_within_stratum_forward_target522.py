#!/usr/bin/env python3
"""Non-importing verifier for the outcome-blind Target-522 forward audit."""

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
from typing import Any

from phase1 import verify_tree_linearization_within_stratum_decomposition as independent_math


PROTOCOL_NAME = "tree-linearization-within-stratum-forward-target522-v2"
RECEIPT_PROTOCOL = "tree-linearization-within-stratum-forward-target522-receipt-v2"
VERIFY_PROTOCOL = "independent-tree-linearization-within-stratum-forward-target522-verifier-v2"
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
CARD_FIELDS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "generation_started_at_utc",
    "source_sha256",
}
LINEAGE_FIELDS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_FIELDS = {
    "run_id",
    "task",
    "drop_id",
    "flow_status",
    "endpoints",
    "generation_started_at_utc",
    "source_sha256",
}
JOURNAL_HEADER = (
    "snapshot_sha256\truns\tendpoints\ttasks\tsummary_sha256\tregistry_sha256\t"
    "runs_sha256\tobserved_at_utc"
)
SECRET_SHAPE = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    rb"AIza[0-9A-Za-z_-]{30,}|Bearer[ \t]+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class ForwardVerificationError(RuntimeError):
    """Raised on an independently detected mismatch."""


@dataclass
class SnapshotView:
    sha256: str
    graph_cards: dict[str, dict[str, Any]]
    card_objects: dict[str, dict[str, Any]]
    card_lines: dict[str, bytes]
    run_objects: dict[str, dict[str, Any]]
    run_lines: dict[str, bytes]
    registry_lines: tuple[bytes, ...]
    bindings: dict[str, Any]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardVerificationError(message)


def sha_text(value: Any, label: str) -> str:
    check(isinstance(value, str) and SHA_PATTERN.fullmatch(value) is not None, f"bad {label}")
    return value


def integer(value: Any, label: str, minimum: int = 0) -> int:
    check(
        isinstance(value, int) and not isinstance(value, bool) and value >= minimum,
        f"bad {label}",
    )
    return value


def bytes_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1 << 20)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def object_file(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe object: {path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(parsed, dict), f"object expected: {path}")
    return parsed


def line_objects(path: Path) -> list[tuple[dict[str, Any], bytes]]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSONL: {path}")
    result: list[tuple[dict[str, Any], bytes]] = []
    for number, raw in enumerate(path.read_bytes().splitlines(keepends=True), 1):
        check(bool(raw.strip()), f"empty JSONL row: {path.name}:{number}")
        parsed = json.loads(raw.decode("utf-8"))
        check(isinstance(parsed, dict), f"row object expected: {path.name}:{number}")
        result.append((parsed, raw))
    return result


def independently_validate_snapshot_graph(cards: dict[str, dict[str, Any]]) -> None:
    children: dict[str, list[str]] = {identifier: [] for identifier in cards}
    parent_count = 0
    for identifier, card in cards.items():
        parent = card["parent"]
        if parent not in cards:
            continue
        check(parent != identifier, "snapshot self-parent")
        check(cards[parent]["run"] == card["run"], "snapshot cross-run parent")
        check(cards[parent]["task"] == card["task"], "snapshot cross-task parent")
        children[parent].append(identifier)
        parent_count += 1
    indegree = {
        identifier: int(cards[identifier]["parent"] in cards)
        for identifier in cards
    }
    queue = collections.deque(sorted(identifier for identifier, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        parent = queue.popleft()
        visited += 1
        for child in sorted(children[parent]):
            indegree[child] -= 1
            check(indegree[child] == 0, "snapshot parent multiplicity")
            queue.append(child)
    check(visited == len(cards), "snapshot graph cycle")
    check(sum(len(value) for value in children.values()) == parent_count, "snapshot edge accounting")


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return bytes_digest(raw)


def protocol_file(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    actual = file_digest(path)
    check(actual == expected_sha, "protocol digest mismatch")
    protocol = object_file(path)
    check(protocol.get("protocol") == PROTOCOL_NAME, "protocol identity mismatch")
    check(
        protocol.get("status")
        == "OUTCOME_BLIND_PROTOCOL_AMENDED_BEFORE_TARGET522_SELECTION_OR_INCREMENT_PROFILE",
        "protocol status mismatch",
    )
    amendment = protocol.get("pre_candidate_integrity_amendment")
    check(isinstance(amendment, dict), "integrity amendment missing")
    check(amendment.get("candidate_snapshot_identity_seen") is False, "candidate seen before amendment")
    check(amendment.get("increment_profile_seen") is False, "increment profile seen before amendment")
    check(
        amendment.get("scientific_population_estimand_thresholds_or_classification_changed") is False,
        "scientific contract changed",
    )
    return protocol, actual


def collect_snapshot(state_root: Path, snapshot_sha256: str) -> SnapshotView:
    snapshot_sha = sha_text(snapshot_sha256, "snapshot digest")
    state = state_root.resolve()
    check(state.is_dir() and not state_root.is_symlink(), "unsafe state root")
    raw_snapshot = state / "snapshots" / snapshot_sha
    check(raw_snapshot.is_dir() and not raw_snapshot.is_symlink(), "unsafe snapshot")
    snapshot = raw_snapshot.resolve()
    check(snapshot.parent == state / "snapshots" and snapshot.name == snapshot_sha, "snapshot path binding")

    registry_file = snapshot / "intake_registry.jsonl"
    summary_file = snapshot / "accumulator" / "summary.json"
    run_file = snapshot / "accumulator" / "provisional_runs.jsonl"
    summary = object_file(summary_file)
    check(summary.get("protocol") == "prospective_accumulator_v1", "accumulator protocol")
    security = summary.get("security")
    check(
        isinstance(security, dict)
        and security.get("label_vault_opened") is False
        and security.get("outcome_files_opened") == []
        and security.get("scorer_prediction_files_opened") == [],
        "accumulator blindness",
    )
    check(summary.get("closure", {}).get("provided") is False, "unexpected closure")
    registry_hash = file_digest(registry_file)
    run_hash = file_digest(run_file)
    check(summary.get("inputs", {}).get("registry_sha256") == registry_hash, "registry binding")
    check(summary.get("outputs", {}).get("provisional_runs_sha256") == run_hash, "run binding")
    expected_intakes = summary.get("inputs", {}).get("intake_summaries")
    check(isinstance(expected_intakes, dict), "intake map absent")

    graph_cards: dict[str, dict[str, Any]] = {}
    card_objects: dict[str, dict[str, Any]] = {}
    card_lines: dict[str, bytes] = {}
    run_to_drop: dict[str, str] = {}
    drops: set[str] = set()
    intake_bindings: list[tuple[str, str]] = []
    registry = line_objects(registry_file)
    for registry_object, _registry_line in registry:
        check(set(registry_object) == {"drop_id", "intake_dir", "summary_sha256"}, "registry fields")
        drop = registry_object.get("drop_id")
        check(isinstance(drop, str) and bool(drop) and drop not in drops, "duplicate drop")
        drops.add(drop)
        intake_source = Path(registry_object["intake_dir"])
        check(not intake_source.is_symlink(), "symlink intake")
        intake = intake_source.resolve()
        check(intake.parent == state / "intakes" and intake.name == drop, "intake binding")
        intake_summary_hash = sha_text(registry_object.get("summary_sha256"), "intake summary digest")
        intake_summary_file = intake / "summary.json"
        check(file_digest(intake_summary_file) == intake_summary_hash, "intake summary hash")
        check(expected_intakes.get(drop) == intake_summary_hash, "unbound intake summary")
        intake_summary = object_file(intake_summary_file)
        outputs = intake_summary.get("outputs")
        intake_security = intake_summary.get("security")
        blindness = intake_summary.get("blindness")
        check(all(isinstance(value, dict) for value in (outputs, intake_security, blindness)), "intake contract")
        check(
            intake_security.get("env_members_read") is False
            and intake_security.get("live_event_journal_members_read") is False
            and blindness.get("labels_used_for_run_selection") is False
            and blindness.get("labels_used_for_endpoint_selection") is False
            and blindness.get("metrics_computed") == [],
            "intake blindness",
        )
        manifest_hash = sha_text(outputs.get("eligible_blind_manifest_sha256"), "manifest digest")
        manifest_file = intake / "eligible_blind_manifest.jsonl"
        check(manifest_file.is_file() and not manifest_file.is_symlink(), "unsafe blind manifest")
        manifest_bytes = manifest_file.read_bytes()
        check(bytes_digest(manifest_bytes) == manifest_hash, "manifest hash")
        check(SECRET_SHAPE.search(manifest_bytes) is None, "credential-shaped blind bytes")
        intake_bindings.append((intake_summary_hash, manifest_hash))
        for card, raw_card in line_objects(manifest_file):
            check(set(card) == CARD_FIELDS, "card fields")
            lineage = card.get("lineage")
            check(isinstance(lineage, dict) and set(lineage) == LINEAGE_FIELDS, "lineage fields")
            identifier, task, run = card.get("card_id"), card.get("task"), card.get("run_id")
            code, parent = card.get("code"), lineage.get("parent")
            check(
                all(isinstance(value, str) and bool(value) for value in (identifier, task, run, code, parent))
                and identifier not in graph_cards,
                "bad or duplicate card",
            )
            check(bytes_digest(code.encode()) == sha_text(card.get("code_sha256"), "code digest"), "code hash")
            sha_text(card.get("source_sha256"), "card source digest")
            check(
                isinstance(card.get("generation_started_at_utc"), str)
                and bool(card["generation_started_at_utc"]),
                "bad card generation time",
            )
            for field in ("depth", "step", "n_siblings"):
                integer(lineage.get(field), f"lineage {field}")
            check(isinstance(lineage.get("op"), str) and bool(lineage["op"]), "bad lineage op")
            previous_drop = run_to_drop.setdefault(run, drop)
            check(previous_drop == drop, "run split over drops")
            graph_cards[identifier] = {
                "task": task,
                "run": run,
                "parent": parent,
                "depth": lineage["depth"],
            }
            card_objects[identifier] = card
            card_lines[identifier] = raw_card

    check(set(expected_intakes) == drops, "extra accumulator intake binding")
    run_objects: dict[str, dict[str, Any]] = {}
    run_lines: dict[str, bytes] = {}
    run_rows = line_objects(run_file)
    for run, raw_run in run_rows:
        check(set(run) == RUN_FIELDS, "run fields")
        identifier = run.get("run_id")
        check(isinstance(identifier, str) and bool(identifier) and identifier not in run_objects, "duplicate run")
        check(run.get("flow_status") == "scoreable", "non-scoreable run")
        check(run.get("drop_id") == run_to_drop.get(identifier), "run/drop binding")
        check(isinstance(run.get("task"), str) and bool(run["task"]), "bad run task")
        integer(run.get("endpoints"), "run endpoints", minimum=1)
        sha_text(run.get("source_sha256"), "run source digest")
        check(
            isinstance(run.get("generation_started_at_utc"), str)
            and bool(run["generation_started_at_utc"]),
            "bad run generation time",
        )
        run_objects[identifier] = run
        run_lines[identifier] = raw_run

    counts = collections.Counter(card["run"] for card in graph_cards.values())
    check(set(counts) == set(run_objects), "run/card identity mismatch")
    for run_id, run in run_objects.items():
        check(counts[run_id] == run["endpoints"], "run/card count")
    for card in graph_cards.values():
        check(run_objects[card["run"]]["task"] == card["task"], "run/card task")
    independently_validate_snapshot_graph(graph_cards)

    observed = {
        "runs": len(run_objects),
        "endpoints": len(graph_cards),
        "tasks": len({card["task"] for card in graph_cards.values()}),
    }
    inventory = summary.get("inventory", {})
    check(
        inventory.get("provisional_first960_runs") == observed["runs"]
        and inventory.get("provisional_first960_endpoints") == observed["endpoints"],
        "accumulator counts",
    )
    check(
        summary.get("task_support", {}).get("provisional_first960", {}).get("tasks")
        == observed["tasks"],
        "accumulator task count",
    )
    return SnapshotView(
        sha256=snapshot_sha,
        graph_cards=graph_cards,
        card_objects=card_objects,
        card_lines=card_lines,
        run_objects=run_objects,
        run_lines=run_lines,
        registry_lines=tuple(raw for _value, raw in registry),
        bindings={
            "snapshot_sha256": snapshot_sha,
            "registry_sha256": registry_hash,
            "accumulator_summary_sha256": file_digest(summary_file),
            "provisional_runs_sha256": run_hash,
            "intake_summary_manifest_sequence_sha256": canonical_digest(intake_bindings),
            "intake_count": len(registry),
            **observed,
        },
    )


def key_values(path: Path) -> dict[str, str]:
    check(path.is_file() and not path.is_symlink(), f"unsafe key-value input: {path}")
    result: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        key, separator, value = line.partition("=")
        check(separator == "=" and bool(key) and key not in result, f"bad key-value row {number}")
        result[key] = value
    return result


def selection_manifest(root: Path) -> dict[str, str]:
    lines = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    result: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        digest, separator, member = line.partition("  ./")
        check(separator == "  ./" and SHA_PATTERN.fullmatch(digest) is not None, f"bad hash row {number}")
        check(re.fullmatch(r"[A-Za-z0-9._-]+", member) is not None and member not in result, "bad hash member")
        result[member] = digest
    actual = {
        member.name
        for member in root.iterdir()
        if member.name not in {"SHA256SUMS", "COMPLETE"}
    }
    check(set(result) == actual, "hash-member set mismatch")
    for member, expected in result.items():
        check(file_digest(root / member) == expected, f"selection digest mismatch: {member}")
    return result


def observed_rows(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    check(bool(lines) and lines.pop(0) == JOURNAL_HEADER, "journal header")
    result: list[dict[str, Any]] = []
    prior = -1
    seen: set[str] = set()
    for line in lines:
        fields = line.split("\t")
        check(len(fields) == 8, "journal width")
        snapshot = sha_text(fields[0], "journal snapshot")
        check(snapshot not in seen, "duplicate journal snapshot")
        seen.add(snapshot)
        check(all(value.isdigit() for value in fields[1:4]), "journal count type")
        counts = [int(value) for value in fields[1:4]]
        check(all(value > 0 for value in counts) and counts[0] >= prior, "journal count ordering")
        prior = counts[0]
        result.append(
            {
                "snapshot_sha256": snapshot,
                "runs": counts[0],
                "endpoints": counts[1],
                "tasks": counts[2],
                "summary_sha256": sha_text(fields[4], "journal summary digest"),
                "registry_sha256": sha_text(fields[5], "journal registry digest"),
                "runs_sha256": sha_text(fields[6], "journal run digest"),
                "observed_at_utc": fields[7],
                "first_seven": "\t".join(fields[:7]),
            }
        )
    check(bool(result), "empty journal")
    return result


def inspect_selection(
    selection_root: Path,
    protocol_path: Path,
    monitor_source: Path,
    protocol: dict[str, Any],
    protocol_sha: str,
) -> dict[str, Any]:
    root = selection_root.resolve()
    check(selection_root.is_dir() and not selection_root.is_symlink(), "unsafe selection root")
    members = list(root.iterdir())
    check(all(member.is_file() and not member.is_symlink() for member in members), "unsafe selection member")
    allowed = set(protocol["security"]["selection_support_input_basenames"])
    check({member.name for member in members} == allowed, "selection basename contract")
    check((root / "COMPLETE").stat().st_size == 0, "bad COMPLETE")
    hashes = selection_manifest(root)
    check((root / "protocol.json").read_bytes() == protocol_path.read_bytes(), "protocol byte binding")
    check(file_digest(root / "protocol.json") == protocol_sha, "protocol hash binding")
    check((root / "source_script.sh").read_bytes() == monitor_source.read_bytes(), "monitor byte binding")
    check((root / "monitor.lock").stat().st_size == 0, "monitor lock bytes")
    check((root / "monitor.pid").read_text(encoding="utf-8").strip().isdigit(), "monitor PID")
    check(
        (root / "security_scan_receipt.txt").read_text(encoding="utf-8").splitlines()
        == ["boundary_aware_credential_file_hits=0", "credential_filename_hits=0"],
        "selection security receipt",
    )
    preflight = (root / "preflight_13.txt").read_text(encoding="utf-8").splitlines()
    check(len(preflight) == 13 and all(row.endswith("PASS") for row in preflight), "preflight receipt")

    ready = key_values(root / "READY")
    expected_keys = {
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
    check(set(ready) == expected_keys, "READY fields")
    check(ready["status"] == "TARGET522_FIRST_OBSERVED_CROSSING_READY", "READY status")
    check(COMMIT_PATTERN.fullmatch(ready["source_commit"]) is not None, "selection source commit")
    check(ready["protocol_sha256"] == protocol_sha, "READY protocol")
    baseline = protocol["freeze_state"]["baseline_snapshot_sha256"]
    baseline_count = protocol["freeze_state"]["baseline_counts"]["provisional_first960_runs"]
    target = protocol["activation_rule"]["target_total_physical_runs"]
    minimum = protocol["activation_rule"]["minimum_disjoint_increment_physical_runs"]
    check(ready["baseline_snapshot_sha256"] == baseline, "READY baseline")
    check(ready["baseline_runs"] == str(baseline_count), "READY baseline count")
    candidate = sha_text(ready["candidate_snapshot_sha256"], "candidate digest")
    for key in ("candidate_runs", "candidate_endpoints", "candidate_tasks", "disjoint_increment_runs"):
        check(ready[key].isdigit() and int(ready[key]) > 0, f"READY count {key}")
    check(int(ready["candidate_runs"]) >= target, "target not reached")
    check(int(ready["disjoint_increment_runs"]) >= minimum, "increment target not reached")
    check(
        int(ready["disjoint_increment_runs"]) == int(ready["candidate_runs"]) - baseline_count,
        "READY increment arithmetic",
    )
    for key in ("candidate_summary_sha256", "candidate_registry_sha256", "candidate_runs_sha256"):
        sha_text(ready[key], key)
    check(ready["manual_snapshot_choice"] == "false", "manual candidate")
    check(ready["earlier_observed_target_crossing_skipped"] == "false", "skipped candidate")
    check(ready["profile_values_read_for_selection"] == "false", "profile-informed selection")
    check(ready["prospective_outcomes_or_prediction_values_read"] == "false", "value-informed selection")
    check(ready["raw_senior_archives_opened"] == "false", "raw archive opened")
    check(ready["gpu_api_model_fit_base_update"] == "0/0/0/0", "selection resources")

    journal = observed_rows(root / "observed.tsv")
    check(journal[0]["snapshot_sha256"] == baseline and journal[0]["runs"] == baseline_count, "journal baseline")
    crossing = next((row for row in journal if row["runs"] >= target), None)
    check(crossing is not None and crossing["snapshot_sha256"] == candidate, "first crossing")
    check(sum(row["snapshot_sha256"] == candidate for row in journal) == 1, "candidate multiplicity")
    check((root / "candidate.tsv").read_text(encoding="utf-8").rstrip("\n") == crossing["first_seven"], "candidate row")
    check(crossing["runs"] == int(ready["candidate_runs"]), "candidate runs")
    check(crossing["endpoints"] == int(ready["candidate_endpoints"]), "candidate endpoints")
    check(crossing["tasks"] == int(ready["candidate_tasks"]), "candidate tasks")
    check(crossing["summary_sha256"] == ready["candidate_summary_sha256"], "candidate summary")
    check(crossing["registry_sha256"] == ready["candidate_registry_sha256"], "candidate registry")
    check(crossing["runs_sha256"] == ready["candidate_runs_sha256"], "candidate runs hash")

    logs = (root / "monitor.log").read_text(encoding="utf-8").splitlines()
    latches = [index for index, row in enumerate(logs) if " candidate_latched " in row]
    check(len(latches) == 1 and f"snapshot={candidate}" in logs[latches[0]], "latch log")
    stable = []
    for row in logs[latches[0] + 1 :]:
        matched = re.search(rf" candidate={re.escape(candidate)} stable=([0-9]+)$", row)
        if matched:
            stable.append(int(matched.group(1)))
    stability = protocol["activation_rule"]["candidate_must_be_hash_stable_for_consecutive_polls"]
    check(stable[-(stability - 1) :] == list(range(1, stability)), "stability sequence")
    return {
        "baseline": baseline,
        "candidate": candidate,
        "selection_source_commit": ready["source_commit"],
        "candidate_counts": {
            "runs": crossing["runs"],
            "endpoints": crossing["endpoints"],
            "tasks": crossing["tasks"],
        },
        "baseline_journal": journal[0],
        "candidate_journal": crossing,
        "manifest_sha256": file_digest(root / "SHA256SUMS"),
        "monitor_source_sha256": hashes["source_script.sh"],
        "member_hashes": hashes,
        "checks": {
            "complete_hash_bound_selection_package": True,
            "monitor_source_and_protocol_bytes_exact": True,
            "candidate_is_first_observed_target_crossing": True,
            "candidate_hash_stability_log_and_completion_exact": True,
            "selection_used_no_profile_or_prospective_values": True,
        },
    }


def incremental_population(
    baseline: SnapshotView,
    candidate: SnapshotView,
    protocol: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    old_runs, all_runs = set(baseline.run_objects), set(candidate.run_objects)
    old_cards, all_cards = set(baseline.graph_cards), set(candidate.graph_cards)
    check(old_runs <= all_runs, "run subset")
    check(old_cards <= all_cards, "card subset")
    check(
        candidate.registry_lines[: len(baseline.registry_lines)] == baseline.registry_lines,
        "registry append-only",
    )
    check(
        tuple(candidate.run_objects)[: len(baseline.run_objects)] == tuple(baseline.run_objects),
        "run ordering append-only",
    )
    for run_id in old_runs:
        check(candidate.run_objects[run_id] == baseline.run_objects[run_id], "old run object")
        check(candidate.run_lines[run_id] == baseline.run_lines[run_id], "old run bytes")
    for card_id in old_cards:
        check(candidate.card_objects[card_id] == baseline.card_objects[card_id], "old card object")
        check(candidate.card_lines[card_id] == baseline.card_lines[card_id], "old card bytes")
    added_runs = all_runs - old_runs
    added_cards = all_cards - old_cards
    check(
        len(added_runs) >= protocol["activation_rule"]["minimum_disjoint_increment_physical_runs"],
        "small run increment",
    )
    check(all(candidate.graph_cards[key]["run"] in added_runs for key in added_cards), "new card in old run")
    check(all(candidate.graph_cards[key]["run"] not in added_runs for key in old_cards), "old card in new run")
    cards = {key: candidate.graph_cards[key] for key in added_cards}
    runs = {key: candidate.run_objects[key] for key in added_runs}
    run_counts = collections.Counter(card["run"] for card in cards.values())
    check(set(run_counts) == added_runs, "increment run/card set")
    for run_id, run in runs.items():
        check(run_counts[run_id] == run["endpoints"], "partial increment run")
    return cards, runs, {
        "baseline_runs_exact_subset": True,
        "baseline_endpoints_exact_subset": True,
        "registry_exact_append_only_prefix": True,
        "run_ledger_exact_append_only_order": True,
        "old_run_payloads_and_bytes_unchanged": True,
        "old_endpoint_payloads_and_bytes_unchanged": True,
        "increment_contains_only_complete_new_physical_runs": True,
        "baseline_runs": len(baseline.run_objects),
        "candidate_runs": len(candidate.run_objects),
        "increment_runs": len(runs),
        "baseline_endpoints": len(baseline.graph_cards),
        "candidate_endpoints": len(candidate.graph_cards),
        "increment_endpoints": len(cards),
    }


def adapted_math_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(protocol)
    gates = result["strong_positive_gates"]
    gates["minimum_task_canonical_standardized_within_tv_integrity_floor"] = gates[
        "minimum_task_canonical_standardized_within_tv"
    ]
    gates["minimum_physical_run_canonical_standardized_within_tv_integrity_floor"] = gates[
        "minimum_physical_run_canonical_standardized_within_tv"
    ]
    support = result["hard_integrity_and_support_gates"]
    support["minimum_conditionable_tasks"] = support["minimum_conditionable_tasks_in_increment"]
    support["minimum_conditionable_physical_runs"] = support[
        "minimum_conditionable_physical_runs_in_increment"
    ]
    return result


def independent_classification(
    summary: dict[str, Any], protocol: dict[str, Any], hard: dict[str, bool]
) -> str:
    if not all(hard.values()):
        result = "FORWARD_INCREMENT_WITHIN_STRATUM_GATE_FAIL"
    else:
        task_strong = summary["axis_strength"]["task"]
        run_strong = summary["axis_strength"]["physical_run"]
        task_tv = independent_math.decoded(
            summary["partitions"]["task"]["canonical_marginal_standardized_within_total_variation"],
            "task TV",
        )
        run_tv = independent_math.decoded(
            summary["partitions"]["physical_run"]["canonical_marginal_standardized_within_total_variation"],
            "run TV",
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
    check(result in protocol["ordered_classification"], "classification outside protocol")
    return result


def deep_equal(expected: Any, actual: Any, label: str) -> None:
    if isinstance(expected, dict):
        check(isinstance(actual, dict) and set(actual) == set(expected), f"mapping mismatch: {label}")
        for key, value in expected.items():
            deep_equal(value, actual[key], f"{label}.{key}")
    elif isinstance(expected, list):
        check(isinstance(actual, list) and len(actual) == len(expected), f"list mismatch: {label}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            deep_equal(left, right, f"{label}[{index}]")
    else:
        check(expected == actual, f"value mismatch: {label}")


def verify(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha256: str,
    receipt_path: Path,
    receipt_sha256: str,
    producer_source: Path,
    producer_source_sha256: str,
    source_commit: str,
) -> dict[str, Any]:
    check(COMMIT_PATTERN.fullmatch(source_commit) is not None, "analysis source commit")
    protocol, actual_protocol_sha = protocol_file(protocol_path, protocol_sha256)
    check(file_digest(receipt_path) == receipt_sha256, "receipt digest")
    receipt = object_file(receipt_path)
    check(receipt.get("protocol") == RECEIPT_PROTOCOL, "receipt protocol")
    check(receipt.get("status") == "OUTCOME_BLIND_FORWARD_INCREMENT_AUDIT_COMPLETE", "receipt status")
    check(file_digest(producer_source) == producer_source_sha256, "producer source digest")
    monitor_source = repo_root.resolve() / "phase1" / "scripts" / "latch_tree_within_stratum_forward_target522_20260828.sh"
    selection = inspect_selection(
        selection_root,
        protocol_path,
        monitor_source,
        protocol,
        actual_protocol_sha,
    )
    baseline = collect_snapshot(state_root, selection["baseline"])
    candidate = collect_snapshot(state_root, selection["candidate"])
    baseline_journal = selection["baseline_journal"]
    candidate_journal = selection["candidate_journal"]
    check(
        baseline.bindings["accumulator_summary_sha256"] == baseline_journal["summary_sha256"]
        and baseline.bindings["registry_sha256"] == baseline_journal["registry_sha256"]
        and baseline.bindings["provisional_runs_sha256"] == baseline_journal["runs_sha256"],
        "baseline journal bindings",
    )
    check(
        candidate.bindings["accumulator_summary_sha256"] == candidate_journal["summary_sha256"]
        and candidate.bindings["registry_sha256"] == candidate_journal["registry_sha256"]
        and candidate.bindings["provisional_runs_sha256"] == candidate_journal["runs_sha256"],
        "candidate journal bindings",
    )
    baseline_counts = protocol["freeze_state"]["baseline_counts"]
    check(
        baseline.bindings["runs"] == baseline_counts["provisional_first960_runs"]
        and baseline.bindings["endpoints"] == baseline_counts["eligible_endpoints"]
        and baseline.bindings["tasks"] == baseline_counts["tasks"],
        "baseline counts",
    )
    check(candidate.bindings["runs"] == selection["candidate_counts"]["runs"], "candidate run count")
    check(candidate.bindings["endpoints"] == selection["candidate_counts"]["endpoints"], "candidate endpoint count")
    check(candidate.bindings["tasks"] == selection["candidate_counts"]["tasks"], "candidate task count")

    cards, runs, append_only = incremental_population(baseline, candidate, protocol)
    try:
        edges, graph_inventory = independent_math.reconstruct_edges(cards)
        summary = independent_math.independently_summarize(edges, adapted_math_protocol(protocol))
    except independent_math.VerificationError as error:
        raise ForwardVerificationError(f"independent tree reconstruction: {error}") from error
    parent_present = Fraction(len(edges), len(cards))
    support = protocol["hard_integrity_and_support_gates"]
    hard = {
        **selection["checks"],
        "baseline_runs_and_endpoints_are_exact_subsets_of_candidate": True,
        "old_run_and_endpoint_rows_are_unchanged": True,
        "candidate_total_runs_at_least_target": len(candidate.run_objects)
        >= support["candidate_total_runs_at_least"],
        "disjoint_increment_runs_at_least_minimum": len(runs)
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
    classification = independent_classification(summary, protocol, hard)
    producer_math = repo_root.resolve() / "phase1" / "decompose_tree_linearization_within_strata.py"
    expected_receipt = {
        "protocol": RECEIPT_PROTOCOL,
        "status": "OUTCOME_BLIND_FORWARD_INCREMENT_AUDIT_COMPLETE",
        "classification": classification,
        "protocol_sha256": actual_protocol_sha,
        "analysis_source_commit": source_commit,
        "selection_source_commit": selection["selection_source_commit"],
        "producer_source_sha256": producer_source_sha256,
        "math_source_sha256": file_digest(producer_math),
        "snapshot_bindings": {
            "baseline": baseline.bindings,
            "candidate": candidate.bindings,
            "selection_support": {
                "sha256sums_sha256": selection["manifest_sha256"],
                "monitor_source_sha256": selection["monitor_source_sha256"],
                "protocol_sha256": actual_protocol_sha,
            },
        },
        "append_only_and_increment": append_only,
        "inventory": {
            **summary["inventory"],
            **graph_inventory,
            "increment_endpoints": len(cards),
            "increment_physical_runs": len(runs),
            "increment_tasks": len({card["task"] for card in cards.values()}),
            "parent_present_endpoints": len(edges),
            "parent_present_endpoint_fraction": independent_math.encoded(parent_present),
        },
        "overall_edge_total_variation": summary["overall_edge_total_variation"],
        "partitions": summary["partitions"],
        "pre_registered_gate": {
            "hard_integrity_and_support": hard,
            "all_hard_gates_passed": all(hard.values()),
            "axis_strength": summary["axis_strength"],
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
    deep_equal(expected_receipt, receipt, "receipt")
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": "INDEPENDENT_FORWARD_INCREMENT_AUDIT_PASS",
        "classification": classification,
        "baseline_snapshot_sha256": selection["baseline"],
        "candidate_snapshot_sha256": selection["candidate"],
        "receipt_sha256": receipt_sha256,
        "producer_source_sha256": producer_source_sha256,
        "independent_math_source_sha256": file_digest(Path(independent_math.__file__)),
        "all_hard_gates_passed": all(hard.values()),
        "checks": {
            "selection_package_independently_reconstructed": True,
            "baseline_and_candidate_populations_independently_reconstructed": True,
            "append_only_and_disjoint_increment_independently_rechecked": True,
            "graph_multiplicities_and_exact_metrics_independently_recomputed": True,
            "classification_and_identity_free_receipt_independently_recomputed": True,
            "imports_new_producer": False,
        },
        "security": {
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def write_once(path: Path, value: dict[str, Any]) -> None:
    check(not path.exists(), "refusing to overwrite verifier output")
    check(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe output parent")
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
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--expect-receipt-sha256", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--expect-producer-source-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            args.state_root,
            args.selection_root,
            args.repo_root,
            args.protocol,
            args.expect_protocol_sha256,
            args.receipt,
            args.expect_receipt_sha256,
            args.producer_source,
            args.expect_producer_source_sha256,
            args.source_commit,
        )
        write_once(args.out.resolve(), result)
    except (ForwardVerificationError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 2
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
