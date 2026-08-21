#!/usr/bin/env python3
"""Build the source-aware Decision-Corpus evidence index v2.

The builder upgrades the independently verified v1 stack without changing its
five estimands, then adds the separately verified source-opportunity boundary.
Only already-published JSON receipts are read; no pair labels, predictor
outputs, prospective outcomes, or model checkpoints are opened.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any


PROTOCOL = "decision_corpus_evidence_index_v2"
STATUS = "PROVISIONAL_SOURCE_AWARE_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_PROTOCOL = "decision_corpus_evidence_index_v1"
SOURCE_STATUS = "PROVISIONAL_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_INDEX_RELATIVE = (
    "phase1/results/decision_corpus_evidence_index_v1_20260820/index.json"
)
SOURCE_INDEX_SHA256_NORMALIZED_LF = (
    "cfbe749f84114a633d902a358f8ef8243c4c4fe71433961c94e18494ca93769d"
)

SCOPE = {
    "estimands_merged": False,
    "source_choice_set_complete": False,
    "missing_at_random_assumed": False,
    "prospective_outcomes_read": False,
    "prospective_vault_open_allowed": False,
    "frozen_accuracy_computed_by_deployment_cost": False,
    "release_complete": False,
}

REPORTING_CONTRACT = {
    "first_or_only_claim_allowed": False,
    "complete_choice_set_language_allowed": False,
    "missing_at_random_language_allowed": False,
    "self_report_classification": "post_execution_signal",
    "prospective_effect_claim_allowed": False,
}

SUPPORTED_CLAIMS = {
    "decision_corpus": (
        "Published pairs are context-consistent physical-run siblings with "
        "same-budget train/frozen isolation inside the audited release."
    ),
    "source_opportunity": (
        "The release is a labeled sibling fragment with a high-coverage, "
        "parent-linked registry of missing generated identities and statuses."
    ),
    "label_repeatability": (
        "Pair ordering is highly repeatable on the independently regraded "
        "ten-task subset under the recorded regrade protocol."
    ),
    "normalized_clone": (
        "No cross-run or cross-task duplicates were observed among endpoints "
        "covered by the preregistered token and AST normalizations."
    ),
    "deployment_cost": (
        "The audited lightweight predictors have online query latency far below "
        "recorded candidate execution time under the pinned CPU protocol."
    ),
    "prospective_gate": (
        "The preregistered confirmatory cohort is accruing outcome-blind and "
        "remains sealed until its run target and independent closure are met."
    ),
}

SOURCE_ENTRY = {
    "name": "source_opportunity",
    "estimand": (
        "retention boundary plus parent-linked identity and journal-status "
        "coverage for generated siblings absent from the labeled release"
    ),
    "supported_claim": SUPPORTED_CLAIMS["source_opportunity"],
    "does_not_prove": (
        "The registry does not recover missing numeric outcomes, establish "
        "missing-at-random, make the labeled fragment a complete choice set, "
        "or demonstrate a censor-aware selector's utility."
    ),
    "artifacts": [
        {
            "path": (
                "phase1/results/raw_choice_set_completeness_v11_20260815_6610618/"
                "verification_summary.json"
            ),
            "json_assertions": {
                "status": "VERIFIED_RAW_CHOICE_SET_COMPLETENESS_AUDIT",
                "labeled_sibling_fragment_claim_allowed": True,
                "choice_set_faithful_claim_allowed": False,
                "parents": 3252,
                "reads_first960": False,
                "reads_pair_orientation": False,
                "uses_numeric_outcome_magnitude": False,
            },
        },
        {
            "path": (
                "phase1/results/"
                "source_opportunity_identity_recovery_v11_20260815_3faf001/"
                "verification_summary.json"
            ),
            "json_assertions": {
                "status": "VERIFIED_SOURCE_OPPORTUNITY_IDENTITY_RECOVERY",
                "opportunity_identity_registry_claim_allowed": True,
                "complete_labeled_choice_set_claim_allowed": False,
                "source_incomplete_parents": 870,
                "exact_identity_recoverable_parents": 721,
                "exact_identity_recovery_rate": 0.828735632183908,
                "recovered_missing_identities": 996,
                "nonorphan_unrecoverable_incomplete_parents": 0,
                "reads_first960": False,
                "reads_numeric_outcomes": False,
            },
        },
        {
            "path": (
                "phase1/results/"
                "source_opportunity_journal_status_v11_20260815_42cb6b1/"
                "verification_summary.json"
            ),
            "json_assertions": {
                "status": "VERIFIED_SOURCE_OPPORTUNITY_JOURNAL_STATUS",
                "missing_status_registry_claim_allowed": True,
                "complete_labeled_choice_set_claim_allowed": False,
                "missing_at_random_claim_allowed": False,
                "target_missing_identities": 996,
                "unique_nodes_recovered": 902,
                "node_recovery_rate": 0.9056224899598394,
                "categories.EXECUTION_ERROR": 893,
                "categories.OFFICIAL_GRADE_ABSENT": 9,
                "source_journal_collisions": 0,
                "journal_parent_mismatches": 0,
                "reads_first960": False,
                "reads_numeric_grade": False,
            },
        },
    ],
}


class BuildError(RuntimeError):
    pass


def normalized_utf8_lf(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise BuildError(f"artifact is not UTF-8 JSON: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_utf8_lf(path)).hexdigest()


def resolve_artifact(repo_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise BuildError(f"absolute artifact path is forbidden: {relative}")
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise BuildError(f"artifact escapes repository root: {relative}") from error
    if not resolved.is_file():
        raise BuildError(f"artifact is missing: {relative}")
    return resolved


def build_index(repo_root: Path, source_index_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_index_path = source_index_path.resolve()
    expected_source = (repo_root / SOURCE_INDEX_RELATIVE).resolve()
    if source_index_path != expected_source:
        raise BuildError("source index path is not the frozen v1 index")
    if normalized_sha256(source_index_path) != SOURCE_INDEX_SHA256_NORMALIZED_LF:
        raise BuildError("source v1 index normalized SHA-256 mismatch")

    source = json.loads(normalized_utf8_lf(source_index_path).decode("utf-8"))
    if source.get("protocol") != SOURCE_PROTOCOL or source.get("status") != SOURCE_STATUS:
        raise BuildError("source v1 protocol/status mismatch")
    source_names = [entry.get("name") for entry in source.get("entries", [])]
    expected_names = [
        "decision_corpus",
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "prospective_gate",
    ]
    if source_names != expected_names:
        raise BuildError("source v1 entry order or membership changed")

    inherited: dict[str, dict[str, Any]] = {}
    for original in source["entries"]:
        entry = copy.deepcopy(original)
        name = entry["name"]
        entry["supported_claim"] = SUPPORTED_CLAIMS[name]
        for artifact in entry["artifacts"]:
            resolved = resolve_artifact(repo_root, artifact["path"])
            artifact.pop("sha256", None)
            artifact["sha256_normalized_lf"] = normalized_sha256(resolved)
        inherited[name] = entry

    source_entry = copy.deepcopy(SOURCE_ENTRY)
    for artifact in source_entry["artifacts"]:
        resolved = resolve_artifact(repo_root, artifact["path"])
        artifact["sha256_normalized_lf"] = normalized_sha256(resolved)

    order = [
        "decision_corpus",
        "source_opportunity",
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "prospective_gate",
    ]
    inherited["source_opportunity"] = source_entry
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "source_v1_index": {
            "path": SOURCE_INDEX_RELATIVE,
            "sha256_normalized_lf": SOURCE_INDEX_SHA256_NORMALIZED_LF,
        },
        "scope": SCOPE,
        "reporting_contract": REPORTING_CONTRACT,
        "entries": [inherited[name] for name in order],
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise BuildError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--source-index", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    payload = build_index(Path(arguments.repo_root), Path(arguments.source_index))
    atomic_json(Path(arguments.out).resolve(), payload)
    print(STATUS)


if __name__ == "__main__":
    main()
