#!/usr/bin/env python3
"""Atomically bind prospective intakes to the frozen scorer and audit registries.

This module never accepts a label-vault path and never reads outcomes.  ``score-drop``
turns one hash-locked intake into one atomic score transaction.  ``validate-registry``
then replays all label-free bindings across drops and rejects duplicate provenance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import fixed_decision_scorer as frozen_scorer


PROTOCOL = "prospective_drop_scoring_v1"
INTAKE_PROTOCOL = "prospective_drop_intake_v1"
SCORER_PROTOCOL = "prospective_decision_v1"
LEGACY_INTAKE_GIT_COMMIT = "90842c49dbd73d41d405a5ecdad2224ee447b375"
LEGACY_INTAKE_SOURCE_SHA256 = (
    "ef02ad7905c4fa3a17e4e91af373a735fd6a981590cd637a4af533eb067b9af2"
)
ARCHIVE_CONSENSUS_PROTOCOL = "prospective-intake-archive-consensus-fallback-v1"
ARCHIVE_CONSENSUS_PROTOCOL_SHA256 = (
    "3110da4403fa0477454d8e1415fd23e9a7a7482694b778784c9d5270b8e4993e"
)
ACTIVE_RECEIPT_SHA256 = (
    "cfab01a80536a50ef21c47ac269c7ce54a11a3b1f0b6daa5700873cbb02ce178"
)
FIXED_SCORER_SHA256 = (
    "c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23"
)
PRECUTOFF_RUNS_SHA256 = (
    "94c39feda828ed19e4a543b2abd7ad07bfb1e7266883bf49d0193cf48cbf012a"
)
PRECUTOFF_ENDPOINT_DENYLIST_SHA256 = (
    "2f0cc4f3dc203801c569237716ba82cbc2bde2f854b67eee6efa9452e92447e6"
)
DROP_ID_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
SHA_RX = re.compile(r"[0-9a-f]{64}")
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
SCORE_FIELDS = (
    "card_id",
    "task",
    "run_id",
    "parent",
    "generation_started_at_utc",
    "source_sha256",
    "static_lr",
    "char_tfidf_lr",
)
REGISTRY_KEYS = {
    "drop_id",
    "intake_dir",
    "intake_summary_sha256",
    "score_dir",
    "score_summary_sha256",
}
INTAKE_TOP_KEYS = {
    "activated_at_utc",
    "blindness",
    "configuration",
    "git_commit",
    "inputs",
    "inventory",
    "outputs",
    "protocol",
    "security",
    "selection_rule",
    "software",
    "source_sha256",
    "status",
}
INTAKE_INPUT_KEYS = {
    "archive_manifest_sha256",
    "drop_dir",
    "freeze_receipt_sha256",
    "precutoff_endpoint_denylist_sha256",
}
INTAKE_OUTPUT_KEYS = {
    "all_blind_views_sha256",
    "archive_audits_sha256",
    "eligible_blind_manifest_sha256",
    "eligible_structural_pairs_sha256",
    "label_vault_sha256",
    "source_provenance_sha256",
    "structural_pairs_sha256",
}
LEGACY_INTAKE_INVENTORY_KEYS = {
    "archives",
    "discovered_run_roots",
    "eligible_endpoints",
    "eligible_runs",
    "eligible_structural_pairs",
    "eligible_tasks",
    "empty_code_nodes_excluded",
    "endpoints",
    "live_only_runs_excluded",
    "no_scoreable_code_runs",
    "runs",
    "structural_pairs",
    "tasks",
}
INTAKE_INVENTORY_KEYS = LEGACY_INTAKE_INVENTORY_KEYS | {
    "archive_consensus_fallback_runs"
}
LEGACY_PROVENANCE_KEYS = {
    "archive_name",
    "archive_sha256",
    "eligible",
    "empty_code_nodes_excluded",
    "endpoints",
    "flow_status",
    "generation_started_at_utc",
    "journal_member",
    "journal_mtime",
    "journal_sha256",
    "run_id",
    "task",
}
PROVENANCE_KEYS = LEGACY_PROVENANCE_KEYS | {"competition_id_source"}
TRANSACTION_TOP_KEYS = {
    "status",
    "protocol",
    "drop_id",
    "git_commit",
    "source_sha256",
    "inputs",
    "inventory",
    "outputs",
    "security",
    "software",
}
NESTED_SCORE_TOP_KEYS = {
    "status",
    "protocol",
    "git_commit",
    "source_sha256",
    "labels_read",
    "post_execution_fields_read",
    "inputs",
    "audit",
    "outputs",
    "software",
}


class PipelineError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def require_sha(value: Any, label: str) -> str:
    normalized = str(value).lower()
    if not SHA_RX.fullmatch(normalized):
        raise PipelineError(f"invalid {label} SHA-256")
    return normalized


def require_drop_id(value: Any) -> str:
    drop_id = str(value)
    if not DROP_ID_RX.fullmatch(drop_id):
        raise PipelineError("invalid drop_id")
    return drop_id


def require_exact_keys(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise PipelineError(f"{label} schema mismatch")
    return value


def strict_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PipelineError(f"invalid {label}")
    return value


def ensure_output_separate(output: Path, protected: list[Path], label: str) -> None:
    resolved = output.resolve()
    for item in protected:
        base = item.resolve()
        if resolved == base or base in resolved.parents:
            raise PipelineError(f"{label} must be outside protected input directories")


def load_json(path: Path, expected_sha: str, label: str) -> dict[str, Any]:
    expected = require_sha(expected_sha, label)
    if sha256(path) != expected:
        raise PipelineError(f"{label} SHA mismatch")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PipelineError(f"cannot parse {label}") from error
    if not isinstance(value, dict):
        raise PipelineError(f"{label} must be a JSON object")
    return value


def load_active_scorer(scorer_dir: Path) -> dict[str, Any]:
    receipt_path = scorer_dir / "freeze_receipt.json"
    summary_path = scorer_dir / "summary.json"
    bundle_path = scorer_dir / "fixed_scorer.npz"
    runs_path = scorer_dir / "precutoff_runs.txt"
    if sha256(receipt_path) != ACTIVE_RECEIPT_SHA256:
        raise PipelineError("active scorer receipt SHA mismatch")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "PROSPECTIVE_SCORER_ACTIVE" or receipt.get(
        "protocol"
    ) != SCORER_PROTOCOL:
        raise PipelineError("scorer receipt is not active")
    if require_sha(receipt.get("fixed_scorer_sha256"), "fixed scorer") != FIXED_SCORER_SHA256:
        raise PipelineError("receipt fixed scorer mismatch")
    if require_sha(receipt.get("precutoff_runs_sha256"), "pre-cutoff runs") != PRECUTOFF_RUNS_SHA256:
        raise PipelineError("receipt pre-cutoff run mismatch")
    if sha256(bundle_path) != FIXED_SCORER_SHA256 or sha256(runs_path) != PRECUTOFF_RUNS_SHA256:
        raise PipelineError("active scorer artifact mismatch")
    if sha256(summary_path) != require_sha(
        receipt.get("producer_summary_sha256"), "producer summary"
    ):
        raise PipelineError("active scorer producer summary mismatch")
    return receipt


def load_blind_identities(
    path: Path,
    expected_sha: str,
    max_endpoints: int,
) -> dict[str, dict[str, str]]:
    if sha256(path) != require_sha(expected_sha, "eligible manifest"):
        raise PipelineError("eligible manifest SHA mismatch")
    identities: dict[str, dict[str, str]] = {}
    previous: str | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise PipelineError("cannot read eligible manifest") from error
    for line_number, line in enumerate(lines, 1):
        if not line:
            raise PipelineError(f"blank eligible manifest line {line_number}")
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as error:
            raise PipelineError(f"invalid eligible JSON at line {line_number}") from error
        require_exact_keys(raw, BLIND_KEYS, f"eligible line {line_number}")
        lineage = require_exact_keys(
            raw["lineage"], LINEAGE_KEYS, f"eligible lineage line {line_number}"
        )
        for key in ("card_id", "task", "run_id", "code", "code_sha256", "generation_started_at_utc", "source_sha256"):
            if not isinstance(raw[key], str):
                raise PipelineError(f"invalid eligible {key} type at line {line_number}")
        card_id = raw["card_id"]
        if not card_id or (previous is not None and card_id <= previous):
            raise PipelineError("eligible endpoint IDs must be strictly sorted and unique")
        previous = card_id
        if any(character in raw[key] for key in ("card_id", "task", "run_id") for character in "\r\n\t"):
            raise PipelineError(f"control whitespace in eligible identity at line {line_number}")
        code_sha = hashlib.sha256(raw["code"].encode("utf-8")).hexdigest()
        if not raw["code"] or code_sha != require_sha(raw["code_sha256"], "endpoint code"):
            raise PipelineError(f"eligible code SHA mismatch at line {line_number}")
        source_sha = require_sha(raw["source_sha256"], "journal source")
        if raw["run_id"] != f"journal:{source_sha}":
            raise PipelineError(f"eligible run/source mismatch at line {line_number}")
        frozen_scorer.parse_utc(raw["generation_started_at_utc"])
        for key in ("depth", "step", "n_siblings"):
            strict_nonnegative_int(lineage[key], f"lineage {key}")
        if lineage["depth"] < 1 or lineage["step"] < 1:
            raise PipelineError(f"eligible endpoint is not a non-root at line {line_number}")
        if not isinstance(lineage["parent"], str) or not lineage["parent"]:
            raise PipelineError(f"invalid parent at line {line_number}")
        if not isinstance(lineage["op"], str):
            raise PipelineError(f"invalid op at line {line_number}")
        identities[card_id] = {
            "card_id": card_id,
            "task": raw["task"],
            "run_id": raw["run_id"],
            "parent": lineage["parent"],
            "generation_started_at_utc": raw["generation_started_at_utc"],
            "source_sha256": source_sha,
            "code_sha256": code_sha,
        }
        if len(identities) > max_endpoints:
            raise PipelineError("eligible manifest exceeds endpoint cap")
    return identities


def load_archive_shas(path: Path, expected_sha: str) -> set[str]:
    if sha256(path) != require_sha(expected_sha, "archive manifest"):
        raise PipelineError("archive manifest SHA mismatch")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["name", "size", "sha256"]:
            raise PipelineError("archive manifest header mismatch")
        rows = list(reader)
    shas: set[str] = set()
    for line_number, row in enumerate(rows, 2):
        if set(row) != {"name", "size", "sha256"} or not row["name"]:
            raise PipelineError(f"archive manifest row mismatch at line {line_number}")
        if any(character in row["name"] for character in "\r\n\t"):
            raise PipelineError(f"archive name contains control whitespace at line {line_number}")
        try:
            size = int(row["size"])
        except ValueError as error:
            raise PipelineError(f"invalid archive size at line {line_number}") from error
        strict_nonnegative_int(size, "archive size")
        archive_sha = require_sha(row["sha256"], "archive")
        if archive_sha in shas:
            raise PipelineError("duplicate archive SHA within intake")
        shas.add(archive_sha)
    if not shas:
        raise PipelineError("empty archive manifest")
    return shas


def load_json_array(path: Path, expected_sha: str, label: str) -> list[Any]:
    if sha256(path) != require_sha(expected_sha, label):
        raise PipelineError(f"{label} SHA mismatch")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PipelineError(f"cannot parse {label}") from error
    if not isinstance(value, list):
        raise PipelineError(f"{label} must be a JSON array")
    return value


def load_provenance(
    path: Path,
    expected_sha: str,
    archive_shas: set[str],
    activated_at: Any,
    consensus_schema: bool,
) -> dict[str, dict[str, Any]]:
    value = load_json_array(path, expected_sha, "source provenance")
    runs: dict[str, dict[str, Any]] = {}
    activation = frozen_scorer.parse_utc(str(activated_at))
    expected_keys = PROVENANCE_KEYS if consensus_schema else LEGACY_PROVENANCE_KEYS
    for index, raw in enumerate(value, 1):
        require_exact_keys(raw, expected_keys, f"source provenance row {index}")
        for key in (
            "archive_name",
            "archive_sha256",
            "flow_status",
            "generation_started_at_utc",
            "journal_member",
            "journal_sha256",
            "run_id",
            "task",
        ):
            if not isinstance(raw[key], str) or not raw[key]:
                raise PipelineError(f"invalid provenance {key} at row {index}")
        for key in ("endpoints", "empty_code_nodes_excluded", "journal_mtime"):
            strict_nonnegative_int(raw[key], f"provenance {key}")
        if not isinstance(raw["eligible"], bool):
            raise PipelineError(f"invalid provenance eligibility at row {index}")
        archive_sha = require_sha(raw["archive_sha256"], "provenance archive")
        journal_sha = require_sha(raw["journal_sha256"], "provenance journal")
        run_id = raw["run_id"]
        if archive_sha not in archive_shas or run_id != f"journal:{journal_sha}":
            raise PipelineError(f"provenance identity mismatch at row {index}")
        generation = frozen_scorer.parse_utc(raw["generation_started_at_utc"])
        if raw["eligible"] is not (generation > activation):
            raise PipelineError(f"provenance eligibility mismatch at row {index}")
        expected_flow = "scoreable" if raw["endpoints"] else "no_scoreable_code"
        if raw["flow_status"] != expected_flow:
            raise PipelineError(f"provenance flow status mismatch at row {index}")
        if consensus_schema and raw["competition_id_source"] not in {
            "explicit_journal",
            "archive_consensus_fallback",
        }:
            raise PipelineError(f"invalid provenance competition source at row {index}")
        if run_id in runs:
            raise PipelineError("duplicate physical run in source provenance")
        runs[run_id] = raw
    return runs


def validate_prospective_identities(
    identities: dict[str, dict[str, str]],
    receipt: dict[str, Any],
    scorer_dir: Path,
    endpoint_denylist: Path,
) -> None:
    activated_at = frozen_scorer.parse_utc(str(receipt["activated_at_utc"]))
    run_lines = (scorer_dir / "precutoff_runs.txt").read_text(encoding="utf-8").splitlines()
    if len(run_lines) != frozen_scorer.EXPECTED["precutoff_runs"] or len(set(run_lines)) != len(
        run_lines
    ):
        raise PipelineError("pre-cutoff run inventory mismatch")
    endpoint_ids, code_shas, audit = frozen_scorer.load_endpoint_denylist(
        endpoint_denylist,
        PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
        frozen_scorer.PRECUTOFF_ENDPOINTS,
    )
    if audit["endpoint_ids"] != frozen_scorer.PRECUTOFF_ENDPOINTS:
        raise PipelineError("pre-cutoff endpoint inventory mismatch")
    run_set = set(run_lines)
    for card_id, identity in identities.items():
        if (
            identity["run_id"] in run_set
            or card_id in endpoint_ids
            or identity["code_sha256"] in code_shas
        ):
            raise PipelineError("pre-cutoff identity appears in eligible manifest")
        if frozen_scorer.parse_utc(identity["generation_started_at_utc"]) <= activated_at:
            raise PipelineError("non-prospective generation time in eligible manifest")


def validate_intake(
    intake_dir: Path,
    expected_summary_sha: str,
    repo_root: Path,
    receipt: dict[str, Any],
    max_endpoints: int,
) -> dict[str, Any]:
    summary_path = intake_dir / "summary.json"
    summary = load_json(summary_path, expected_summary_sha, "intake summary")
    require_exact_keys(summary, INTAKE_TOP_KEYS, "intake summary")
    if summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE" or summary.get(
        "protocol"
    ) != INTAKE_PROTOCOL:
        raise PipelineError("intake is not complete")
    if not isinstance(summary.get("configuration"), dict):
        raise PipelineError("intake configuration must be an object")
    current_commit = git_commit(repo_root)
    intake_source = sha256(Path(__file__).with_name("prospective_drop_intake.py"))
    intake_identity = (summary.get("git_commit"), summary.get("source_sha256"))
    if not all(isinstance(value, str) for value in intake_identity) or intake_identity not in {
        (current_commit, intake_source),
        (LEGACY_INTAKE_GIT_COMMIT, LEGACY_INTAKE_SOURCE_SHA256),
    }:
        raise PipelineError("intake code identity mismatch")
    consensus_schema = intake_identity == (current_commit, intake_source)
    if summary.get("activated_at_utc") != receipt.get("activated_at_utc"):
        raise PipelineError("intake activation timestamp mismatch")
    inputs = summary.get("inputs")
    outputs = summary.get("outputs")
    inventory = summary.get("inventory")
    blindness = summary.get("blindness")
    security = summary.get("security")
    if not all(isinstance(item, dict) for item in (inputs, outputs, inventory, blindness, security)):
        raise PipelineError("intake summary sections must be objects")
    require_exact_keys(inputs, INTAKE_INPUT_KEYS, "intake inputs")
    require_exact_keys(outputs, INTAKE_OUTPUT_KEYS, "intake outputs")
    expected_inventory_keys = (
        INTAKE_INVENTORY_KEYS if consensus_schema else LEGACY_INTAKE_INVENTORY_KEYS
    )
    require_exact_keys(inventory, expected_inventory_keys, "intake inventory")
    for key in expected_inventory_keys:
        strict_nonnegative_int(inventory[key], f"intake inventory {key}")
    configuration = summary["configuration"]
    consensus_configuration = (
        configuration.get("archive_consensus_fallback_protocol"),
        configuration.get("archive_consensus_fallback_protocol_sha256"),
    )
    configuration_mismatch = (
        consensus_configuration
        != (ARCHIVE_CONSENSUS_PROTOCOL, ARCHIVE_CONSENSUS_PROTOCOL_SHA256)
        if consensus_schema
        else consensus_configuration != (None, None)
    )
    if configuration_mismatch:
        raise PipelineError("intake archive-consensus protocol mismatch")
    if require_sha(inputs.get("freeze_receipt_sha256"), "intake receipt") != ACTIVE_RECEIPT_SHA256:
        raise PipelineError("intake scorer receipt mismatch")
    if require_sha(
        inputs.get("precutoff_endpoint_denylist_sha256"), "intake endpoint denylist"
    ) != PRECUTOFF_ENDPOINT_DENYLIST_SHA256:
        raise PipelineError("intake endpoint denylist mismatch")
    if blindness != {
        "label_values_printed": False,
        "labels_used_for_endpoint_selection": False,
        "labels_used_for_run_selection": False,
        "metrics_computed": [],
    }:
        raise PipelineError("intake blindness contract mismatch")
    if security.get("env_members_read") is not False or security.get(
        "live_event_journal_members_read"
    ) is not False:
        raise PipelineError("intake unsafe-member audit mismatch")
    if security.get("precutoff_endpoint_id_overlap") != 0 or security.get(
        "precutoff_code_sha256_overlap"
    ) != 0:
        raise PipelineError("intake pre-cutoff overlap is nonzero")
    eligible_count = strict_nonnegative_int(
        inventory.get("eligible_endpoints"), "eligible endpoint count"
    )
    blind_path = intake_dir / "eligible_blind_manifest.jsonl"
    expected_blind_sha = require_sha(
        outputs.get("eligible_blind_manifest_sha256"), "eligible manifest"
    )
    identities = load_blind_identities(blind_path, expected_blind_sha, max_endpoints)
    if len(identities) != eligible_count:
        raise PipelineError("intake eligible endpoint inventory mismatch")
    archive_path = intake_dir / "archive_manifest.tsv"
    archive_shas = load_archive_shas(
        archive_path,
        require_sha(inputs.get("archive_manifest_sha256"), "archive manifest"),
    )
    if len(archive_shas) != inventory["archives"]:
        raise PipelineError("intake archive inventory mismatch")
    provenance = load_provenance(
        intake_dir / "source_provenance.json",
        require_sha(outputs.get("source_provenance_sha256"), "source provenance"),
        archive_shas,
        receipt["activated_at_utc"],
        consensus_schema,
    )
    if len(provenance) != inventory["runs"]:
        raise PipelineError("intake run inventory mismatch")
    eligible_provenance = {run for run, row in provenance.items() if row["eligible"]}
    manifest_runs = {row["run_id"] for row in identities.values()}
    if not manifest_runs <= eligible_provenance:
        raise PipelineError("eligible manifest contains a non-eligible provenance run")
    if len(eligible_provenance) != inventory["eligible_runs"]:
        raise PipelineError("intake eligible run inventory mismatch")
    if consensus_schema and inventory["archive_consensus_fallback_runs"] != sum(
        row["competition_id_source"] == "archive_consensus_fallback"
        for row in provenance.values()
    ):
        raise PipelineError("intake archive-consensus fallback inventory mismatch")
    return {
        "summary": summary,
        "summary_sha256": sha256(summary_path),
        "blind_path": blind_path,
        "blind_sha256": expected_blind_sha,
        "identities": identities,
        "archive_shas": archive_shas,
        "provenance": provenance,
        "label_vault_sha256": require_sha(outputs.get("label_vault_sha256"), "label vault"),
    }


def load_score_rows(
    path: Path,
    expected_sha: str,
    identities: dict[str, dict[str, str]],
) -> dict[str, dict[str, float]]:
    if sha256(path) != require_sha(expected_sha, "blind scores"):
        raise PipelineError("blind score CSV SHA mismatch")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SCORE_FIELDS:
            raise PipelineError("blind score CSV header mismatch")
        rows = list(reader)
    if len(rows) != len(identities):
        raise PipelineError("blind score row count mismatch")
    scores: dict[str, dict[str, float]] = {}
    previous: str | None = None
    for line_number, row in enumerate(rows, 2):
        if set(row) != set(SCORE_FIELDS):
            raise PipelineError(f"blind score schema mismatch at line {line_number}")
        card_id = row["card_id"]
        if previous is not None and card_id <= previous:
            raise PipelineError("blind score IDs must be strictly sorted and unique")
        previous = card_id
        identity = identities.get(card_id)
        if identity is None:
            raise PipelineError(f"unknown scored endpoint at line {line_number}")
        for key in (
            "card_id",
            "task",
            "run_id",
            "parent",
            "generation_started_at_utc",
            "source_sha256",
        ):
            if row[key] != identity[key]:
                raise PipelineError(f"blind score identity mismatch for {card_id}: {key}")
        parsed: dict[str, float] = {}
        for model in ("static_lr", "char_tfidf_lr"):
            try:
                value = float(row[model])
            except ValueError as error:
                raise PipelineError(f"invalid {model} score for {card_id}") from error
            if not math.isfinite(value):
                raise PipelineError(f"non-finite {model} score for {card_id}")
            parsed[model] = value
        scores[card_id] = parsed
    if set(scores) != set(identities):
        raise PipelineError("blind score endpoint set mismatch")
    return scores


def validate_nested_score(
    score_dir: Path,
    identities: dict[str, dict[str, str]],
    intake: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    summary_path = score_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    require_exact_keys(summary, NESTED_SCORE_TOP_KEYS, "nested scorer summary")
    if summary.get("status") != "BLIND_SCORING_COMPLETE" or summary.get(
        "protocol"
    ) != SCORER_PROTOCOL:
        raise PipelineError("nested scorer is not complete")
    if summary.get("git_commit") != git_commit(repo_root) or summary.get(
        "source_sha256"
    ) != sha256(Path(frozen_scorer.__file__)):
        raise PipelineError("nested scorer code identity mismatch")
    if summary.get("labels_read") is not False or summary.get(
        "post_execution_fields_read"
    ) is not False:
        raise PipelineError("nested scorer blindness mismatch")
    inputs = summary.get("inputs", {})
    expected_inputs = {
        "blind_manifest_sha256": intake["blind_sha256"],
        "freeze_receipt_sha256": ACTIVE_RECEIPT_SHA256,
        "fixed_scorer_sha256": FIXED_SCORER_SHA256,
        "precutoff_runs_sha256": PRECUTOFF_RUNS_SHA256,
        "precutoff_endpoint_denylist_sha256": PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
    }
    if inputs != expected_inputs:
        raise PipelineError("nested scorer input binding mismatch")
    audit = summary.get("audit", {})
    expected_runs = len({row["run_id"] for row in identities.values()})
    expected_tasks = len({row["task"] for row in identities.values()})
    if audit.get("endpoints") != len(identities) or audit.get("runs") != expected_runs or audit.get(
        "tasks"
    ) != expected_tasks:
        raise PipelineError("nested scorer inventory mismatch")
    if audit.get("labels_read") is not False or audit.get("post_execution_fields_read") is not False:
        raise PipelineError("nested scorer audit blindness mismatch")
    if audit.get("precutoff_endpoint_id_overlap") != 0 or audit.get(
        "precutoff_code_sha256_overlap"
    ) != 0:
        raise PipelineError("nested scorer pre-cutoff overlap is nonzero")
    if audit.get("precutoff_endpoint_ids_checked") != frozen_scorer.PRECUTOFF_ENDPOINTS:
        raise PipelineError("nested scorer endpoint denylist inventory mismatch")
    outputs = summary.get("outputs", {})
    if outputs.get("blind_scores") != "blind_scores.csv":
        raise PipelineError("nested scorer output path must be relative and fixed")
    score_sha = require_sha(outputs.get("blind_scores_sha256"), "blind scores")
    scores = load_score_rows(score_dir / "blind_scores.csv", score_sha, identities)
    return {
        "summary": summary,
        "summary_sha256": sha256(summary_path),
        "blind_scores_sha256": score_sha,
        "scores": scores,
    }


def score_drop(args: argparse.Namespace) -> int:
    out_dir = args.out_dir.resolve()
    intake_dir = args.intake_dir.resolve()
    scorer_dir = args.scorer_dir.resolve()
    endpoint_denylist = args.precutoff_endpoint_denylist.resolve()
    repo_root = args.repo_root.resolve()
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite score transaction: {out_dir}")
    ensure_output_separate(out_dir, [intake_dir, scorer_dir], "score output")
    drop_id = require_drop_id(args.drop_id)
    receipt = load_active_scorer(scorer_dir)
    if sha256(endpoint_denylist) != PRECUTOFF_ENDPOINT_DENYLIST_SHA256:
        raise PipelineError("pre-cutoff endpoint denylist SHA mismatch")
    intake = validate_intake(
        intake_dir,
        args.expect_intake_summary_sha256,
        repo_root,
        receipt,
        args.max_endpoints,
    )
    validate_prospective_identities(
        intake["identities"], receipt, scorer_dir, endpoint_denylist
    )
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp.", dir=str(out_dir.parent))
    )
    identities = intake["identities"]
    nested: dict[str, Any] | None = None
    if identities:
        nested_dir = temporary / "scores"
        frozen_scorer.score(
            argparse.Namespace(
                scorer_dir=scorer_dir,
                blind_manifest=intake["blind_path"],
                precutoff_endpoint_denylist=endpoint_denylist,
                out_dir=nested_dir,
                repo_root=repo_root,
                expect_receipt_sha256=ACTIVE_RECEIPT_SHA256,
                expect_blind_manifest_sha256=intake["blind_sha256"],
            )
        )
        nested = validate_nested_score(nested_dir, identities, intake, repo_root)
        status = "BLIND_DROP_SCORING_COMPLETE"
    else:
        status = "NO_ELIGIBLE_ENDPOINTS"
    summary = {
        "status": status,
        "protocol": PROTOCOL,
        "drop_id": drop_id,
        "git_commit": git_commit(repo_root),
        "source_sha256": sha256(Path(__file__)),
        "inputs": {
            "intake_summary_sha256": intake["summary_sha256"],
            "intake_source_sha256": intake["summary"]["source_sha256"],
            "archive_manifest_sha256": intake["summary"]["inputs"]["archive_manifest_sha256"],
            "eligible_blind_manifest_sha256": intake["blind_sha256"],
            "label_vault_sha256_opaque": intake["label_vault_sha256"],
            "freeze_receipt_sha256": ACTIVE_RECEIPT_SHA256,
            "fixed_scorer_sha256": FIXED_SCORER_SHA256,
            "precutoff_runs_sha256": PRECUTOFF_RUNS_SHA256,
            "precutoff_endpoint_denylist_sha256": PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
        },
        "inventory": {
            "eligible_endpoints": len(identities),
            "scoreable_runs": len({row["run_id"] for row in identities.values()}),
            "scoreable_tasks": len({row["task"] for row in identities.values()}),
        },
        "outputs": {
            "nested_scorer_summary": None if nested is None else "scores/summary.json",
            "nested_scorer_summary_sha256": None if nested is None else nested["summary_sha256"],
            "blind_scores": None if nested is None else "scores/blind_scores.csv",
            "blind_scores_sha256": None if nested is None else nested["blind_scores_sha256"],
        },
        "security": {
            "labels_read": False,
            "label_vault_opened": False,
            "post_execution_fields_read": False,
            "outcome_files_opened": [],
        },
        "software": {
            "python": sys.version,
            "platform": platform.platform(),
        },
    }
    atomic_json(temporary / "summary.json", summary)
    temporary.rename(out_dir)
    print(
        status,
        f"drop_id={drop_id}",
        f"endpoints={len(identities)}",
        "label_vault_opened=false",
        flush=True,
    )
    return 0


def validate_transaction(
    entry: dict[str, Any],
    repo_root: Path,
    max_endpoints: int,
) -> dict[str, Any]:
    drop_id = require_drop_id(entry["drop_id"])
    intake_dir = Path(entry["intake_dir"]).resolve()
    score_dir = Path(entry["score_dir"]).resolve()
    fixed_dir = repo_root / "phase1" / "results" / "fixed_decision_scorer_v11_20260814"
    receipt = load_active_scorer(fixed_dir)
    intake = validate_intake(
        intake_dir,
        entry["intake_summary_sha256"],
        repo_root,
        receipt,
        max_endpoints,
    )
    validate_prospective_identities(
        intake["identities"],
        receipt,
        fixed_dir,
        fixed_dir / "precutoff_endpoint_denylist.csv",
    )
    ensure_output_separate(score_dir, [intake_dir, fixed_dir], "score transaction")
    summary = load_json(
        score_dir / "summary.json", entry["score_summary_sha256"], "score transaction summary"
    )
    require_exact_keys(summary, TRANSACTION_TOP_KEYS, "score transaction summary")
    if summary.get("protocol") != PROTOCOL or summary.get("drop_id") != drop_id:
        raise PipelineError("score transaction identity mismatch")
    if summary.get("git_commit") != git_commit(repo_root) or summary.get(
        "source_sha256"
    ) != sha256(Path(__file__)):
        raise PipelineError("score transaction code identity mismatch")
    expected_status = "BLIND_DROP_SCORING_COMPLETE" if intake["identities"] else "NO_ELIGIBLE_ENDPOINTS"
    if summary.get("status") != expected_status:
        raise PipelineError("score transaction status mismatch")
    inputs = summary.get("inputs", {})
    expected_bindings = {
        "intake_summary_sha256": intake["summary_sha256"],
        "intake_source_sha256": intake["summary"]["source_sha256"],
        "archive_manifest_sha256": intake["summary"]["inputs"]["archive_manifest_sha256"],
        "eligible_blind_manifest_sha256": intake["blind_sha256"],
        "label_vault_sha256_opaque": intake["label_vault_sha256"],
        "freeze_receipt_sha256": ACTIVE_RECEIPT_SHA256,
        "fixed_scorer_sha256": FIXED_SCORER_SHA256,
        "precutoff_runs_sha256": PRECUTOFF_RUNS_SHA256,
        "precutoff_endpoint_denylist_sha256": PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
    }
    if inputs != expected_bindings:
        raise PipelineError("score transaction input binding mismatch")
    inventory = summary.get("inventory", {})
    identities = intake["identities"]
    if inventory != {
        "eligible_endpoints": len(identities),
        "scoreable_runs": len({row["run_id"] for row in identities.values()}),
        "scoreable_tasks": len({row["task"] for row in identities.values()}),
    }:
        raise PipelineError("score transaction inventory mismatch")
    if summary.get("security") != {
        "labels_read": False,
        "label_vault_opened": False,
        "post_execution_fields_read": False,
        "outcome_files_opened": [],
    }:
        raise PipelineError("score transaction blindness mismatch")
    outputs = summary.get("outputs", {})
    nested = None
    if identities:
        if outputs.get("nested_scorer_summary") != "scores/summary.json" or outputs.get(
            "blind_scores"
        ) != "scores/blind_scores.csv":
            raise PipelineError("score transaction relative output mismatch")
        nested = validate_nested_score(score_dir / "scores", identities, intake, repo_root)
        if outputs.get("nested_scorer_summary_sha256") != nested["summary_sha256"] or outputs.get(
            "blind_scores_sha256"
        ) != nested["blind_scores_sha256"]:
            raise PipelineError("score transaction output SHA mismatch")
    elif outputs != {
        "nested_scorer_summary": None,
        "nested_scorer_summary_sha256": None,
        "blind_scores": None,
        "blind_scores_sha256": None,
    }:
        raise PipelineError("empty score transaction output mismatch")
    return {
        "drop_id": drop_id,
        "intake": intake,
        "score_summary_sha256": sha256(score_dir / "summary.json"),
        "blind_scores_sha256": None if nested is None else nested["blind_scores_sha256"],
        "score_dir": str(score_dir),
    }


def load_registry(path: Path, max_drops: int) -> tuple[list[dict[str, Any]], str]:
    blob = path.read_bytes()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        lines = blob.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise PipelineError("score registry is not UTF-8") from error
    for line_number, line in enumerate(lines, 1):
        if not line:
            raise PipelineError(f"blank score registry line {line_number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise PipelineError(f"invalid score registry JSON at line {line_number}") from error
        require_exact_keys(row, REGISTRY_KEYS, f"score registry line {line_number}")
        drop_id = require_drop_id(row["drop_id"])
        if drop_id in seen:
            raise PipelineError("duplicate score registry drop_id")
        seen.add(drop_id)
        require_sha(row["intake_summary_sha256"], "registry intake summary")
        require_sha(row["score_summary_sha256"], "registry score summary")
        if not isinstance(row["intake_dir"], str) or not isinstance(row["score_dir"], str):
            raise PipelineError("score registry paths must be strings")
        rows.append(row)
        if len(rows) > max_drops:
            raise PipelineError("score registry exceeds drop cap")
    if not rows:
        raise PipelineError("empty score registry")
    return rows, sha256_bytes(blob)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return sha256(path)


def validate_registry(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite score registry output: {out_dir}")
    registry, registry_sha = load_registry(args.registry.resolve(), args.max_drops)
    protected = [Path(row["intake_dir"]) for row in registry] + [
        Path(row["score_dir"]) for row in registry
    ]
    ensure_output_separate(out_dir, protected, "score registry output")
    transactions = [
        validate_transaction(row, repo_root, args.max_endpoints) for row in registry
    ]
    archive_owner: dict[str, str] = {}
    run_owner: dict[str, str] = {}
    endpoint_owner: dict[str, str] = {}
    code_owner: dict[str, str] = {}
    duplicate_code_endpoints = 0
    index: list[dict[str, Any]] = []
    for transaction in transactions:
        drop_id = transaction["drop_id"]
        intake = transaction["intake"]
        for archive_sha in intake["archive_shas"]:
            previous = archive_owner.setdefault(archive_sha, drop_id)
            if previous != drop_id:
                raise PipelineError("source archive appears in multiple score drops")
        for run_id in intake["provenance"]:
            previous_run = run_owner.setdefault(run_id, drop_id)
            if previous_run != drop_id:
                raise PipelineError("physical run appears in multiple score drops")
        for card_id, identity in intake["identities"].items():
            previous_card = endpoint_owner.setdefault(card_id, drop_id)
            if previous_card != drop_id:
                raise PipelineError("endpoint appears in multiple score drops")
            previous_code = code_owner.setdefault(identity["code_sha256"], card_id)
            if previous_code != card_id:
                duplicate_code_endpoints += 1
        index.append(
            {
                "drop_id": drop_id,
                "intake_summary_sha256": intake["summary_sha256"],
                "score_summary_sha256": transaction["score_summary_sha256"],
                "blind_scores_sha256": transaction["blind_scores_sha256"],
                "eligible_endpoints": len(intake["identities"]),
                "scoreable_runs": len(
                    {row["run_id"] for row in intake["identities"].values()}
                ),
                "scoreable_tasks": len(
                    {row["task"] for row in intake["identities"].values()}
                ),
            }
        )
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp.", dir=str(out_dir.parent))
    )
    index_sha = write_jsonl(temporary / "score_index.jsonl", index)
    summary = {
        "status": "PROSPECTIVE_SCORE_REGISTRY_VERIFIED",
        "protocol": PROTOCOL,
        "git_commit": git_commit(repo_root),
        "source_sha256": sha256(Path(__file__)),
        "inputs": {
            "registry_sha256": registry_sha,
            "freeze_receipt_sha256": ACTIVE_RECEIPT_SHA256,
            "fixed_scorer_sha256": FIXED_SCORER_SHA256,
            "precutoff_runs_sha256": PRECUTOFF_RUNS_SHA256,
            "precutoff_endpoint_denylist_sha256": PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
        },
        "inventory": {
            "drops": len(transactions),
            "eligible_endpoints": len(endpoint_owner),
            "physical_runs": len(run_owner),
            "scoreable_runs": len(
                {
                    row["run_id"]
                    for transaction in transactions
                    for row in transaction["intake"]["identities"].values()
                }
            ),
            "tasks": len(
                {
                    row["task"]
                    for transaction in transactions
                    for row in transaction["intake"]["identities"].values()
                }
            ),
            "source_archives": len(archive_owner),
            "unique_exact_code_sha256": len(code_owner),
            "exact_code_duplicate_endpoints": duplicate_code_endpoints,
        },
        "outputs": {"score_index_sha256": index_sha},
        "security": {
            "labels_read": False,
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "opened_basenames": sorted(
                {
                    "archive_manifest.tsv",
                    "blind_scores.csv",
                    "eligible_blind_manifest.jsonl",
                    "freeze_receipt.json",
                    "fixed_scorer.npz",
                    "precutoff_endpoint_denylist.csv",
                    "precutoff_runs.txt",
                    "score_index.jsonl",
                    "source_provenance.json",
                    "summary.json",
                    args.registry.name,
                }
            ),
        },
        "software": {"python": sys.version, "platform": platform.platform()},
    }
    atomic_json(temporary / "summary.json", summary)
    temporary.rename(out_dir)
    print(
        "PROSPECTIVE_SCORE_REGISTRY_VERIFIED",
        f"drops={len(transactions)}",
        f"endpoints={len(endpoint_owner)}",
        "label_vault_opened=false",
        flush=True,
    )
    return 0


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    score_parser = subparsers.add_parser("score-drop")
    score_parser.add_argument("--drop-id", required=True)
    score_parser.add_argument("--repo-root", required=True, type=Path)
    score_parser.add_argument("--intake-dir", required=True, type=Path)
    score_parser.add_argument("--expect-intake-summary-sha256", required=True)
    score_parser.add_argument("--scorer-dir", required=True, type=Path)
    score_parser.add_argument("--precutoff-endpoint-denylist", required=True, type=Path)
    score_parser.add_argument("--out-dir", required=True, type=Path)
    score_parser.add_argument("--max-endpoints", type=int, default=1_000_000)
    score_parser.set_defaults(function=score_drop)

    registry_parser = subparsers.add_parser("validate-registry")
    registry_parser.add_argument("--repo-root", required=True, type=Path)
    registry_parser.add_argument("--registry", required=True, type=Path)
    registry_parser.add_argument("--out-dir", required=True, type=Path)
    registry_parser.add_argument("--max-drops", type=int, default=512)
    registry_parser.add_argument("--max-endpoints", type=int, default=10_000_000)
    registry_parser.set_defaults(function=validate_registry)
    args = parser.parse_args()
    if getattr(args, "max_endpoints", 1) <= 0 or getattr(args, "max_drops", 1) <= 0:
        parser.error("resource caps must be positive")
    return args


def main() -> int:
    args = arguments()
    return int(args.function(args))


if __name__ == "__main__":
    raise SystemExit(main())
