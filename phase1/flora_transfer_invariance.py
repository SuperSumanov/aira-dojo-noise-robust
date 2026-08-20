#!/usr/bin/env python3
"""Outcome-blind compatibility audit for FLORA-style workflow graph baselines."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_NAME = "flora-transfer-invariance-v1"
LITERAL_FIELDS = {
    "workflow_internal_nodes_with_prompts": "nodes",
    "workflow_internal_edges": "edge_index",
    "per_node_operator_implementation": "operator_nodes",
    "per_node_implementation_code": "code_nodes",
    "global_workflow_prompt": "full_prompts",
    "global_workflow_code": "workflow_code",
    "natural_language_task_description": "task_description",
}
LINEAGE_VARIABLE_FIELDS = ("op", "depth", "step", "n_siblings")
PROSPECTIVE_BLIND_KEYS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "generation_started_at_utc",
    "source_sha256",
}
PROSPECTIVE_LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
PROSPECTIVE_RUN_KEYS = {
    "run_id",
    "task",
    "drop_id",
    "flow_status",
    "endpoints",
    "generation_started_at_utc",
    "source_sha256",
}


class AuditError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AuditError(f"expected object: {path.name}")
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AuditError(f"blank line: {path.name}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AuditError(f"non-object: {path.name}:{line_number}")
            yield value


def require_sha(path: Path, expected: Any) -> None:
    if not isinstance(expected, str) or sha256_file(path) != expected:
        raise AuditError(f"SHA mismatch: {path.name}")


def literal_support(row: dict[str, Any]) -> dict[str, bool]:
    task = row.get("task")
    nested_task_description = task.get("desc") if isinstance(task, dict) else None
    checks = {
        "workflow_internal_nodes_with_prompts": isinstance(row.get("nodes"), dict)
        and bool(row["nodes"]),
        "workflow_internal_edges": isinstance(row.get("edge_index"), list),
        "per_node_operator_implementation": isinstance(row.get("operator_nodes"), dict)
        and bool(row["operator_nodes"]),
        "per_node_implementation_code": isinstance(row.get("code_nodes"), dict)
        and bool(row["code_nodes"]),
        "global_workflow_prompt": isinstance(row.get("full_prompts"), str)
        and bool(row["full_prompts"].strip()),
        "global_workflow_code": isinstance(row.get("workflow_code"), str)
        and bool(row["workflow_code"].strip()),
        "natural_language_task_description": (
            isinstance(row.get("task_description"), str)
            and bool(row["task_description"].strip())
        )
        or (
            isinstance(nested_task_description, str)
            and bool(nested_task_description.strip())
        ),
    }
    if set(checks) != set(LITERAL_FIELDS):
        raise AssertionError("literal support implementation drift")
    return checks


def endpoint_from_row(row: dict[str, Any], prospective: bool) -> dict[str, Any]:
    lineage = row.get("lineage")
    if not isinstance(lineage, dict):
        raise AuditError("lineage missing")
    identifier = row.get("card_id" if prospective else "id")
    parent = lineage.get("parent" if prospective else "parent_id")
    code = row.get("code")
    task_value = row.get("task")
    task_identifier = (
        task_value
        if isinstance(task_value, str)
        else task_value.get("name") if isinstance(task_value, dict) else None
    )
    values = (identifier, task_identifier, row.get("run_id"), code, lineage.get("op"))
    if not all(isinstance(value, str) and value for value in values):
        raise AuditError("endpoint identity/code/lineage missing")
    if prospective and (not isinstance(parent, str) or not parent):
        raise AuditError("prospective endpoint parent missing")
    if parent is not None and not isinstance(parent, str):
        raise AuditError("invalid endpoint parent")
    if prospective and sha256_text(code) != row.get("code_sha256"):
        raise AuditError("prospective code SHA mismatch")
    return {
        "id": identifier,
        "task": task_identifier,
        "run_id": row["run_id"],
        "parent": parent,
        "op": lineage["op"],
        "depth": lineage.get("depth"),
        "step": lineage.get("step"),
        "n_siblings": lineage.get("n_siblings"),
        "code_sha256": sha256_text(code),
        "literal": literal_support(row),
        "candidate_code_available": True,
        "task_identifier_available": True,
    }


def load_v11(cards_path: Path, decision_paths: list[Path]) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str]], dict[str, Any]]:
    raw_cards: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(cards_path):
        identifier = row.get("id")
        if not isinstance(identifier, str) or identifier in raw_cards:
            raise AuditError("invalid or duplicate v11 card")
        raw_cards[identifier] = row
    scoped: set[str] = set()
    pairs: list[tuple[str, str]] = []
    contexts: list[tuple[str, str, Any, Any, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    roles = collections.Counter()
    declared_run_rows = 0
    for path in decision_paths:
        role = path.stem.split("_v11_")[0].replace("decision_", "")
        for row in read_jsonl(path):
            left, right = row.get("better"), row.get("worse")
            if not isinstance(left, str) or not isinstance(right, str) or left == right:
                raise AuditError("invalid v11 decision pair")
            if left not in raw_cards or right not in raw_cards:
                raise AuditError("v11 pair endpoint absent")
            key = tuple(sorted((left, right)))
            if key in seen_pairs:
                raise AuditError("duplicate v11 unordered pair")
            seen_pairs.add(key)
            pairs.append((left, right))
            contexts.append((left, right, row.get("task"), row.get("run_id"), row.get("parent")))
            declared_run_rows += isinstance(row.get("run_id"), str) and bool(row["run_id"])
            scoped.update((left, right))
            roles[role] += 1
    scoped_cards = {
        identifier: endpoint_from_row(raw_cards[identifier], prospective=False)
        for identifier in sorted(scoped)
    }
    for left, right, task, run_id, parent in contexts:
        left_endpoint, right_endpoint = scoped_cards[left], scoped_cards[right]
        if left_endpoint["run_id"] != right_endpoint["run_id"]:
            raise AuditError("v11 pair endpoints span runs")
        for endpoint in (left_endpoint, right_endpoint):
            if endpoint["task"] != task or endpoint["parent"] != parent:
                raise AuditError("v11 pair context mismatch")
            if run_id is not None and endpoint["run_id"] != run_id:
                raise AuditError("v11 declared run mismatch")
    return scoped_cards, pairs, {
        "cards_sha256": sha256_file(cards_path),
        "decision_sha256": {path.name: sha256_file(path) for path in decision_paths},
        "decision_rows_by_role": dict(sorted(roles.items())),
        "decision_rows_with_declared_run_id": declared_run_rows,
        "decision_rows_with_endpoint_derived_run_id": len(pairs) - declared_run_rows,
    }


def load_prospective(
    state_root: Path, snapshot_root: Path, cohort_run_target: int
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str]], dict[str, Any]]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    if snapshot_root.parent != state_root / "snapshots":
        raise AuditError("snapshot outside state root")
    if len(snapshot_root.name) != 64 or any(c not in "0123456789abcdef" for c in snapshot_root.name):
        raise AuditError("invalid snapshot identity")
    registry_path = snapshot_root / "intake_registry.jsonl"
    runs_path = snapshot_root / "accumulator" / "provisional_runs.jsonl"
    registry = list(read_jsonl(registry_path))
    all_cards: dict[str, dict[str, Any]] = {}
    intake_shas: dict[str, str] = {}
    run_drop: dict[str, str] = {}
    for entry in registry:
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise AuditError("prospective registry schema mismatch")
        drop_id = entry["drop_id"]
        intake = Path(entry["intake_dir"]).resolve()
        if not isinstance(drop_id, str) or intake.parent != state_root / "intakes" or intake.name != drop_id:
            raise AuditError("prospective intake binding mismatch")
        if drop_id in intake_shas:
            raise AuditError("duplicate prospective drop")
        summary_path = intake / "summary.json"
        require_sha(summary_path, entry["summary_sha256"])
        summary = read_json(summary_path)
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if not all(isinstance(value, dict) for value in (outputs, security, blindness)):
            raise AuditError("prospective intake contract missing")
        if (
            security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
            or blindness.get("metrics_computed") != []
        ):
            raise AuditError("prospective blindness/security mismatch")
        manifest = intake / "eligible_blind_manifest.jsonl"
        require_sha(manifest, outputs.get("eligible_blind_manifest_sha256"))
        intake_shas[drop_id] = entry["summary_sha256"]
        for row in read_jsonl(manifest):
            if set(row) != PROSPECTIVE_BLIND_KEYS or not isinstance(row.get("lineage"), dict):
                raise AuditError("prospective manifest schema mismatch")
            if set(row["lineage"]) != PROSPECTIVE_LINEAGE_KEYS:
                raise AuditError("prospective lineage schema mismatch")
            endpoint = endpoint_from_row(row, prospective=True)
            identifier = endpoint["id"]
            if identifier in all_cards:
                raise AuditError("duplicate prospective card")
            owner = run_drop.setdefault(endpoint["run_id"], drop_id)
            if owner != drop_id:
                raise AuditError("prospective run spans drops")
            all_cards[identifier] = endpoint
    runs = list(read_jsonl(runs_path))
    seen_runs: set[str] = set()
    for row in runs:
        if set(row) != PROSPECTIVE_RUN_KEYS or row.get("flow_status") != "scoreable":
            raise AuditError("prospective run schema/status mismatch")
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or run_id in seen_runs or row.get("drop_id") != run_drop.get(run_id):
            raise AuditError("prospective run identity/drop mismatch")
        seen_runs.add(run_id)
    ordered = sorted(
        runs,
        key=lambda row: (
            str(row["generation_started_at_utc"]),
            str(row["source_sha256"]),
            str(row["run_id"]),
        ),
    )
    cohort_runs = {str(row["run_id"]) for row in ordered[:cohort_run_target]}
    cards = {
        identifier: endpoint
        for identifier, endpoint in sorted(all_cards.items())
        if endpoint["run_id"] in cohort_runs
    }
    groups: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    for identifier, endpoint in cards.items():
        groups[(endpoint["task"], endpoint["run_id"], endpoint["parent"])].append(identifier)
    pairs = [
        pair
        for key in sorted(groups)
        for pair in itertools.combinations(sorted(groups[key]), 2)
    ]
    return cards, pairs, {
        "snapshot_sha256": snapshot_root.name,
        "registry_sha256": sha256_file(registry_path),
        "runs_sha256": sha256_file(runs_path),
        "intake_summary_sha256": dict(sorted(intake_shas.items())),
        "observed_runs": len(cohort_runs),
        "target_runs": cohort_run_target,
    }


def summarize_cohort(cards: dict[str, dict[str, Any]], pairs: list[tuple[str, str]]) -> dict[str, Any]:
    if not cards or not pairs:
        raise AuditError("empty audit cohort")
    literal_counts = {
        field: sum(bool(card["literal"][field]) for card in cards.values())
        for field in LITERAL_FIELDS
    }
    complete = sum(all(card["literal"].values()) for card in cards.values())
    differences = collections.Counter()
    invariant = 0
    code_distinct = 0
    choice_sets: set[tuple[str, str, str]] = set()
    runs: set[str] = set()
    tasks: set[str] = set()
    for left_id, right_id in pairs:
        left, right = cards[left_id], cards[right_id]
        if any(left[field] != right[field] for field in ("task", "run_id", "parent")):
            raise AuditError("pair is not a sibling comparison")
        choice_sets.add((left["task"], left["run_id"], left["parent"]))
        runs.add(left["run_id"])
        tasks.add(left["task"])
        changed = False
        for field in LINEAGE_VARIABLE_FIELDS:
            if left[field] != right[field]:
                differences[field] += 1
                changed = True
        if not changed:
            invariant += 1
        if left["code_sha256"] != right["code_sha256"]:
            code_distinct += 1
    denominator = len(pairs)
    return {
        "inventory": {
            "scoped_endpoints": len(cards),
            "sibling_pairs": denominator,
            "choice_sets": len(choice_sets),
            "physical_runs_with_pairs": len(runs),
            "tasks_with_pairs": len(tasks),
        },
        "literal_semantic_support": {
            "field_supported_endpoints": dict(sorted(literal_counts.items())),
            "field_supported_fractions": {
                field: literal_counts[field] / len(cards) for field in sorted(literal_counts)
            },
            "literal_equivalent_endpoints": complete,
            "literal_equivalent_fraction": complete / len(cards),
            "candidate_code_available_fraction": sum(
                card["candidate_code_available"] for card in cards.values()
            )
            / len(cards),
            "task_identifier_available_fraction": sum(
                card["task_identifier_available"] for card in cards.values()
            )
            / len(cards),
        },
        "pair_invariance": {
            "noncode_pair_invariant_pairs": invariant,
            "noncode_pair_invariant_fraction": invariant / denominator,
            "noncode_discriminative_pairs": denominator - invariant,
            "differences_by_lineage_field": {
                field: differences[field] for field in LINEAGE_VARIABLE_FIELDS
            },
            "exact_code_distinct_pairs": code_distinct,
            "exact_code_distinct_fraction": code_distinct / denominator,
        },
    }


def bind_source(repo_root: Path, source_commit: str, protocol_path: Path) -> None:
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise AuditError("invalid source commit")
    actual = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()
    if actual != source_commit:
        raise AuditError("source commit mismatch")
    if subprocess.check_output(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip():
        raise AuditError("worktree is not clean")
    protocol = read_json(protocol_path)
    if protocol.get("protocol") != PROTOCOL_NAME or protocol.get("literal_required_semantics") != list(LITERAL_FIELDS):
        raise AuditError("protocol content mismatch")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parent.parent
    protocol_path = Path(args.protocol).resolve()
    bind_source(repo_root, args.source_commit, protocol_path)
    v11_cards, v11_pairs, v11_inputs = load_v11(
        Path(args.v11_cards).resolve(), [Path(path).resolve() for path in args.v11_decision]
    )
    prospective_cards, prospective_pairs, prospective_inputs = load_prospective(
        Path(args.state_root), Path(args.snapshot_root), args.cohort_run_target
    )
    cohorts = {
        "prospective_first960_prefix": summarize_cohort(prospective_cards, prospective_pairs),
        "v11_published_b0": summarize_cohort(v11_cards, v11_pairs),
    }
    prospective = cohorts["prospective_first960_prefix"]
    literal_supported = all(
        cohort["literal_semantic_support"]["literal_equivalent_fraction"] == 1.0
        for cohort in cohorts.values()
    )
    prospective_lineage_nondegenerate = (
        prospective["pair_invariance"]["noncode_discriminative_pairs"] > 0
    )
    omission_supported = not literal_supported and not prospective_lineage_nondegenerate
    status = (
        "FLORA_LITERAL_UNSUPPORTED_AND_PROSPECTIVE_LINEAGE_ONLY_PAIR_INVARIANT"
        if omission_supported
        else "FLORA_TRANSFER_REQUIRES_FURTHER_ADJUDICATION"
    )
    summary = {
        "protocol": PROTOCOL_NAME,
        "status": status,
        "source_commit": args.source_commit,
        "protocol_sha256": sha256_file(protocol_path),
        "cohorts": cohorts,
        "inputs": {"v11": v11_inputs, "prospective": prospective_inputs},
        "decision": {
            "literal_transfer_supported": literal_supported,
            "prospective_lineage_only_nondegenerate": prospective_lineage_nondegenerate,
            "baseline_omission_rationale_supported": omission_supported,
            "adapted_code_graph_is_new_representation": True,
            "future_outcome_unread_extension_required_for_effect_test": True,
            "performance_claim_allowed": False,
        },
        "security": {
            "prospective_outcomes_opened": False,
            "prospective_label_vault_opened": False,
            "scorer_predictions_opened": False,
            "raw_code_task_run_or_card_values_emitted": False,
            "v11_outcome_metrics_computed": False,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise AuditError("refusing to overwrite output")
    staging.mkdir(parents=True)
    write_json(staging / "summary.json", summary)
    with (staging / "cohort_stats.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "cohort",
                "scoped_endpoints",
                "sibling_pairs",
                "choice_sets",
                "literal_equivalent_fraction",
                "noncode_pair_invariant_fraction",
                "noncode_discriminative_pairs",
                "exact_code_distinct_fraction",
            ),
        )
        writer.writeheader()
        for name, cohort in sorted(cohorts.items()):
            writer.writerow(
                {
                    "cohort": name,
                    **{key: cohort["inventory"][key] for key in ("scoped_endpoints", "sibling_pairs", "choice_sets")},
                    "literal_equivalent_fraction": cohort["literal_semantic_support"]["literal_equivalent_fraction"],
                    "noncode_pair_invariant_fraction": cohort["pair_invariance"]["noncode_pair_invariant_fraction"],
                    "noncode_discriminative_pairs": cohort["pair_invariance"]["noncode_discriminative_pairs"],
                    "exact_code_distinct_fraction": cohort["pair_invariance"]["exact_code_distinct_fraction"],
                }
            )
    manifest = {
        name: sha256_file(staging / name) for name in ("summary.json", "cohort_stats.csv")
    }
    write_json(staging / "artifact_manifest.json", manifest)
    staging.replace(output)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--v11-cards", required=True)
    parser.add_argument("--v11-decision", action="append", required=True)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--cohort-run-target", type=int, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    try:
        summary = run(parse_args())
    except (AuditError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"FLORA_TRANSFER_AUDIT_ERROR: {error}", file=sys.stderr)
        return 2
    print(
        summary["status"],
        f"v11_pairs={summary['cohorts']['v11_published_b0']['inventory']['sibling_pairs']}",
        f"prospective_pairs={summary['cohorts']['prospective_first960_prefix']['inventory']['sibling_pairs']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
