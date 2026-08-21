#!/usr/bin/env python3
"""Build the observability-aware Decision-Corpus evidence index v3."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any


PROTOCOL = "decision_corpus_evidence_index_v3"
STATUS = "PROVISIONAL_OBSERVABILITY_AWARE_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_PROTOCOL = "decision_corpus_evidence_index_v2"
SOURCE_STATUS = "PROVISIONAL_SOURCE_AWARE_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_INDEX_RELATIVE = (
    "phase1/results/decision_corpus_evidence_index_v2_20260821/index.json"
)
SOURCE_INDEX_SHA256_NORMALIZED_LF = (
    "fdb77b4458c4342a0fa62c860ed7141478e38a1dc5c26ac369e70ba961ff5c02"
)
SOURCE_ENTRY_NAMES = [
    "decision_corpus",
    "source_opportunity",
    "label_repeatability",
    "normalized_clone",
    "deployment_cost",
    "prospective_gate",
]

SCOPE = {
    "estimands_merged": False,
    "source_choice_set_complete": False,
    "missing_at_random_assumed": False,
    "prospective_outcomes_read": False,
    "prospective_vault_open_allowed": False,
    "frozen_accuracy_computed_by_deployment_cost": False,
    "release_complete": False,
    "observability_is_actual_agent_comparison_log": False,
    "observability_establishes_predictor_or_search_utility": False,
}

REPORTING_CONTRACT = {
    "first_or_only_claim_allowed": False,
    "complete_choice_set_language_allowed": False,
    "missing_at_random_language_allowed": False,
    "self_report_classification": "post_execution_signal",
    "prospective_effect_claim_allowed": False,
    "decision_point_disappearance_language_allowed": False,
    "actual_agent_comparison_count_language_allowed": False,
}

OBSERVABILITY_ENTRY = {
    "name": "decision_observability",
    "estimand": (
        "finite-population child-slot and declared undirected sibling-pair "
        "capacity through source, raw, finite, and published release stages"
    ),
    "supported_claim": (
        "In the audited 3,252-parent release, 14.61 percent source child-slot "
        "loss corresponds to 38.51 percent declared pair-capacity loss; the "
        "comparison-resolution loss is material in both train and frozen roles."
    ),
    "does_not_prove": (
        "Declared C(n,2) capacity is not a log of comparisons made by the "
        "agent, all audited parents retain a finite published decision, and "
        "the census does not recover a complete labeled choice set or establish "
        "predictor accuracy, search utility, missing-at-random, or causality."
    ),
    "artifacts": [
        {
            "path": (
                "phase1/results/"
                "decision_observability_funnel_v1_20260821_1b8a7b9/"
                "formal_summary.json"
            ),
            "sha256_normalized_lf": (
                "e2bf11bc557ff147a11040821a6d3aa5a0650023ba585bbbf7f5e730fcf07ceb"
            ),
            "json_assertions": {
                "protocol": "decision-observability-funnel-v1",
                "status": "VERIFIED_MATERIAL_COMBINATORIAL_DECISION_ATTRITION",
                "claim_allowed": True,
                "inputs.parent_rows": 3252,
                "overall.source_children": 9088,
                "overall.finite_children": 7760,
                "overall.source_pair_capacity": 9755,
                "overall.finite_pair_capacity": 5998,
                "overall.published_unique_edges": 5897,
                "overall.source_to_finite_child_loss_share": 0.14612676056338025,
                "overall.source_to_finite_pair_loss_share": 0.3851358277806253,
                "overall.pair_minus_child_loss_share": 0.23900906721724502,
                "overall.pair_attrition_amplification": 2.6356283154144,
                "overall.source_to_raw_pair_loss": 3757,
                "overall.raw_to_finite_pair_loss": 0,
                "overall.finite_to_published_pair_loss": 101,
                "overall.decision_parent_survival": 1.0,
                "roles.train.source_to_finite_pair_loss_share": 0.4112200435729847,
                "roles.frozen.source_to_finite_pair_loss_share": 0.3173546382600977,
                "support.supported_tasks": 14,
                "support.tasks_with_pair_loss_gt_child_loss": 12,
                "criteria.finite_pair_loss_share_ge_material_minimum": True,
                "criteria.loss_stages_add_exactly": True,
                "criteria.pair_minus_child_loss_share_ge_material_minimum": True,
                "criteria.supported_tasks_ge_minimum": True,
                "criteria.tasks_with_pair_loss_gt_child_loss_ge_minimum": True,
                "criteria.train_and_frozen_pair_loss_gt_child_loss": True,
                "scope.complete_choice_set_claim": False,
                "scope.missing_at_random_claim": False,
                "scope.numeric_outcome_read": False,
                "scope.pair_orientation_read": False,
                "scope.prospective_outcome_read": False,
                "scope.gpu_hours": 0,
                "scope.api_calls": 0,
                "scope.base_llm_updates": 0,
            },
        },
        {
            "path": (
                "phase1/results/"
                "decision_observability_funnel_v1_20260821_1b8a7b9/"
                "verification_a.json"
            ),
            "sha256_normalized_lf": (
                "d83f2128ccc1d0309a31b3aa5f518b453514181dc1d858445b23facbcbe4feb1"
            ),
            "json_assertions": {
                "status": "INDEPENDENT_DECISION_OBSERVABILITY_FUNNEL_VERIFIED",
                "producer_status": "VERIFIED_MATERIAL_COMBINATORIAL_DECISION_ATTRITION",
                "imports_producer": False,
                "claim_allowed": True,
                "maximum_reconstruction_difference": 0.0,
                "parent_rows": 3252,
                "source_pair_capacity": 9755,
                "finite_pair_capacity": 5998,
                "artifact_summary_sha256": (
                    "e2bf11bc557ff147a11040821a6d3aa5a0650023ba585bbbf7f5e730fcf07ceb"
                ),
                "prospective_outcome_read": False,
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
    if not resolved.is_file() or resolved.suffix != ".json":
        raise BuildError(f"JSON artifact is missing: {relative}")
    return resolved


def build_index(repo_root: Path, source_index_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_index_path = source_index_path.resolve()
    expected_source = (repo_root / SOURCE_INDEX_RELATIVE).resolve()
    if source_index_path != expected_source:
        raise BuildError("source index path is not the frozen v2 index")
    if normalized_sha256(source_index_path) != SOURCE_INDEX_SHA256_NORMALIZED_LF:
        raise BuildError("source v2 index normalized SHA-256 mismatch")

    source = json.loads(normalized_utf8_lf(source_index_path).decode("utf-8"))
    if source.get("protocol") != SOURCE_PROTOCOL or source.get("status") != SOURCE_STATUS:
        raise BuildError("source v2 protocol/status mismatch")
    if [entry.get("name") for entry in source.get("entries", [])] != SOURCE_ENTRY_NAMES:
        raise BuildError("source v2 entry order or membership changed")

    entry = copy.deepcopy(OBSERVABILITY_ENTRY)
    for artifact in entry["artifacts"]:
        resolved = resolve_artifact(repo_root, artifact["path"])
        if normalized_sha256(resolved) != artifact["sha256_normalized_lf"]:
            raise BuildError(f"pinned artifact SHA mismatch: {artifact['path']}")

    entries = copy.deepcopy(source["entries"])
    entries.insert(2, entry)
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "source_v2_index": {
            "path": SOURCE_INDEX_RELATIVE,
            "sha256_normalized_lf": SOURCE_INDEX_SHA256_NORMALIZED_LF,
        },
        "scope": SCOPE,
        "reporting_contract": REPORTING_CONTRACT,
        "entries": entries,
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

