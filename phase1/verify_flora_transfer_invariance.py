#!/usr/bin/env python3
"""Independent verifier for the FLORA transfer invariance audit.

This module intentionally does not import the producer.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "flora-transfer-invariance-v1"
LITERAL = (
    ("workflow_internal_nodes_with_prompts", "nodes", dict),
    ("workflow_internal_edges", "edge_index", list),
    ("per_node_operator_implementation", "operator_nodes", dict),
    ("per_node_implementation_code", "code_nodes", dict),
    ("global_workflow_prompt", "full_prompts", str),
    ("global_workflow_code", "workflow_code", str),
    ("natural_language_task_description", "task_description", str),
)
VARYING = ("op", "depth", "step", "n_siblings")
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
    "run_id", "task", "drop_id", "flow_status", "endpoints",
    "generation_started_at_utc", "source_sha256",
}


class VerifyError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            value.update(block)
    return value.hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def objects(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise VerifyError(f"blank JSONL row {path.name}:{number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise VerifyError("JSONL row is not an object")
            yield value


def object_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerifyError("JSON file is not an object")
    return value


def endpoint(row: dict[str, Any], prospective: bool) -> dict[str, Any]:
    lineage = row.get("lineage")
    if not isinstance(lineage, dict):
        raise VerifyError("missing lineage")
    identifier = row.get("card_id" if prospective else "id")
    parent = lineage.get("parent" if prospective else "parent_id")
    code = row.get("code")
    task_value = row.get("task")
    task_identifier = task_value if isinstance(task_value, str) else task_value.get("name") if isinstance(task_value, dict) else None
    required = (identifier, task_identifier, row.get("run_id"), code, lineage.get("op"))
    if not all(isinstance(value, str) and value for value in required):
        raise VerifyError("invalid endpoint")
    if prospective and (not isinstance(parent, str) or not parent):
        raise VerifyError("prospective parent missing")
    if parent is not None and not isinstance(parent, str):
        raise VerifyError("invalid parent")
    if prospective and text_digest(code) != row.get("code_sha256"):
        raise VerifyError("code digest mismatch")
    support: dict[str, bool] = {}
    for semantic, key, expected_type in LITERAL:
        value = row.get(key)
        support[semantic] = isinstance(value, expected_type) and (
            bool(value.strip()) if isinstance(value, str) else (bool(value) if expected_type is dict else True)
        )
    nested_description = task_value.get("desc") if isinstance(task_value, dict) else None
    support["natural_language_task_description"] = support["natural_language_task_description"] or (
        isinstance(nested_description, str) and bool(nested_description.strip())
    )
    return {
        "id": identifier,
        "task": task_identifier,
        "run_id": row["run_id"],
        "parent": parent,
        "op": lineage["op"],
        "depth": lineage.get("depth"),
        "step": lineage.get("step"),
        "n_siblings": lineage.get("n_siblings"),
        "code": text_digest(code),
        "literal": support,
    }


def v11_inputs(cards_path: Path, decision_paths: list[Path]) -> tuple[dict[str, Any], list[tuple[str, str]], dict[str, Any]]:
    raw_cards: dict[str, dict[str, Any]] = {}
    for row in objects(cards_path):
        identifier = row.get("id")
        if not isinstance(identifier, str) or identifier in raw_cards:
            raise VerifyError("duplicate v11 card")
        raw_cards[identifier] = row
    scoped: set[str] = set()
    pairs: list[tuple[str, str]] = []
    contexts: list[tuple[str, str, Any, Any, Any]] = []
    seen: set[tuple[str, str]] = set()
    roles: collections.Counter[str] = collections.Counter()
    declared_run_rows = 0
    for path in decision_paths:
        role = path.stem.split("_v11_")[0].replace("decision_", "")
        for row in objects(path):
            left, right = row.get("better"), row.get("worse")
            if not isinstance(left, str) or not isinstance(right, str) or left == right:
                raise VerifyError("invalid v11 pair")
            key = tuple(sorted((left, right)))
            if key in seen or left not in raw_cards or right not in raw_cards:
                raise VerifyError("duplicate or unknown v11 pair")
            seen.add(key)
            scoped.update((left, right))
            pairs.append((left, right))
            contexts.append((left, right, row.get("task"), row.get("run_id"), row.get("parent")))
            declared_run_rows += isinstance(row.get("run_id"), str) and bool(row["run_id"])
            roles[role] += 1
    cards = {key: endpoint(raw_cards[key], False) for key in sorted(scoped)}
    for left, right, task, run_id, parent in contexts:
        left_card, right_card = cards[left], cards[right]
        if left_card["run_id"] != right_card["run_id"]:
            raise VerifyError("v11 pair spans runs")
        for card in (left_card, right_card):
            if card["task"] != task or card["parent"] != parent:
                raise VerifyError("v11 context mismatch")
            if run_id is not None and card["run_id"] != run_id:
                raise VerifyError("v11 declared run mismatch")
    return cards, pairs, {
        "cards_sha256": digest(cards_path),
        "decision_sha256": {path.name: digest(path) for path in decision_paths},
        "decision_rows_by_role": dict(sorted(roles.items())),
        "decision_rows_with_declared_run_id": declared_run_rows,
        "decision_rows_with_endpoint_derived_run_id": len(pairs) - declared_run_rows,
    }


def prospective_inputs(state: Path, snapshot: Path, target: int) -> tuple[dict[str, Any], list[tuple[str, str]], dict[str, Any]]:
    state, snapshot = state.resolve(), snapshot.resolve()
    if snapshot.parent != state / "snapshots" or len(snapshot.name) != 64:
        raise VerifyError("snapshot binding mismatch")
    registry_path = snapshot / "intake_registry.jsonl"
    runs_path = snapshot / "accumulator" / "provisional_runs.jsonl"
    all_cards: dict[str, dict[str, Any]] = {}
    run_drop: dict[str, str] = {}
    summary_shas: dict[str, str] = {}
    for entry in objects(registry_path):
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise VerifyError("registry schema mismatch")
        drop = entry["drop_id"]
        intake = Path(entry["intake_dir"]).resolve()
        if not isinstance(drop, str) or intake.parent != state / "intakes" or intake.name != drop:
            raise VerifyError("intake binding mismatch")
        summary_path = intake / "summary.json"
        if digest(summary_path) != entry["summary_sha256"]:
            raise VerifyError("intake summary digest mismatch")
        summary = object_file(summary_path)
        outputs, security, blindness = summary.get("outputs"), summary.get("security"), summary.get("blindness")
        if not all(isinstance(value, dict) for value in (outputs, security, blindness)):
            raise VerifyError("intake contract absent")
        if (
            security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
            or blindness.get("metrics_computed") != []
        ):
            raise VerifyError("intake blindness mismatch")
        manifest = intake / "eligible_blind_manifest.jsonl"
        if digest(manifest) != outputs.get("eligible_blind_manifest_sha256"):
            raise VerifyError("manifest digest mismatch")
        summary_shas[drop] = entry["summary_sha256"]
        for row in objects(manifest):
            if set(row) != BLIND_KEYS or set(row.get("lineage", {})) != LINEAGE_KEYS:
                raise VerifyError("blind manifest schema mismatch")
            card = endpoint(row, True)
            if card["id"] in all_cards:
                raise VerifyError("duplicate prospective card")
            if run_drop.setdefault(card["run_id"], drop) != drop:
                raise VerifyError("run spans drops")
            all_cards[card["id"]] = card
    runs = list(objects(runs_path))
    seen_runs: set[str] = set()
    for row in runs:
        run = row.get("run_id")
        if set(row) != RUN_KEYS or row.get("flow_status") != "scoreable":
            raise VerifyError("run schema mismatch")
        if not isinstance(run, str) or run in seen_runs or run_drop.get(run) != row.get("drop_id"):
            raise VerifyError("run identity mismatch")
        seen_runs.add(run)
    ordered = sorted(runs, key=lambda row: (str(row["generation_started_at_utc"]), str(row["source_sha256"]), str(row["run_id"])))
    cohort_runs = {str(row["run_id"]) for row in ordered[:target]}
    cards = {key: value for key, value in sorted(all_cards.items()) if value["run_id"] in cohort_runs}
    groups: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    for key, card in cards.items():
        groups[(card["task"], card["run_id"], card["parent"])].append(key)
    pairs = [pair for group in sorted(groups) for pair in itertools.combinations(sorted(groups[group]), 2)]
    return cards, pairs, {
        "snapshot_sha256": snapshot.name,
        "registry_sha256": digest(registry_path),
        "runs_sha256": digest(runs_path),
        "intake_summary_sha256": dict(sorted(summary_shas.items())),
        "observed_runs": len(cohort_runs),
        "target_runs": target,
    }


def aggregate(cards: dict[str, dict[str, Any]], pairs: list[tuple[str, str]]) -> dict[str, Any]:
    if not cards or not pairs:
        raise VerifyError("empty cohort")
    field_counts = {semantic: sum(card["literal"][semantic] for card in cards.values()) for semantic, _key, _type in LITERAL}
    complete = sum(all(card["literal"].values()) for card in cards.values())
    differences = collections.Counter()
    invariant = 0
    distinct = 0
    sets, runs, tasks = set(), set(), set()
    for left_key, right_key in pairs:
        left, right = cards[left_key], cards[right_key]
        if (left["task"], left["run_id"], left["parent"]) != (right["task"], right["run_id"], right["parent"]):
            raise VerifyError("non-sibling pair")
        sets.add((left["task"], left["run_id"], left["parent"]))
        runs.add(left["run_id"])
        tasks.add(left["task"])
        changed = [field for field in VARYING if left[field] != right[field]]
        if not changed:
            invariant += 1
        differences.update(changed)
        distinct += left["code"] != right["code"]
    count = len(pairs)
    return {
        "inventory": {
            "scoped_endpoints": len(cards), "sibling_pairs": count, "choice_sets": len(sets),
            "physical_runs_with_pairs": len(runs), "tasks_with_pairs": len(tasks),
        },
        "literal_semantic_support": {
            "field_supported_endpoints": dict(sorted(field_counts.items())),
            "field_supported_fractions": {key: field_counts[key] / len(cards) for key in sorted(field_counts)},
            "literal_equivalent_endpoints": complete,
            "literal_equivalent_fraction": complete / len(cards),
            "candidate_code_available_fraction": 1.0,
            "task_identifier_available_fraction": 1.0,
        },
        "pair_invariance": {
            "noncode_pair_invariant_pairs": invariant,
            "noncode_pair_invariant_fraction": invariant / count,
            "noncode_discriminative_pairs": count - invariant,
            "differences_by_lineage_field": {field: differences[field] for field in VARYING},
            "exact_code_distinct_pairs": distinct,
            "exact_code_distinct_fraction": distinct / count,
        },
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(__file__).resolve().parent.parent
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if actual != args.source_commit:
        raise VerifyError("source commit mismatch")
    if subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True).strip():
        raise VerifyError("dirty verifier worktree")
    protocol_path = Path(args.protocol).resolve()
    protocol = object_file(protocol_path)
    if protocol.get("protocol") != PROTOCOL:
        raise VerifyError("protocol identity mismatch")
    artifact = Path(args.artifact).resolve()
    manifest = object_file(artifact / "artifact_manifest.json")
    if manifest != {name: digest(artifact / name) for name in ("summary.json", "cohort_stats.csv")}:
        raise VerifyError("artifact manifest mismatch")
    summary = object_file(artifact / "summary.json")
    v11_cards, v11_pairs, v11_meta = v11_inputs(Path(args.v11_cards), [Path(path) for path in args.v11_decision])
    pro_cards, pro_pairs, pro_meta = prospective_inputs(Path(args.state_root), Path(args.snapshot_root), args.cohort_run_target)
    expected_cohorts = {
        "prospective_first960_prefix": aggregate(pro_cards, pro_pairs),
        "v11_published_b0": aggregate(v11_cards, v11_pairs),
    }
    assertions = {
        "protocol": summary.get("protocol") == PROTOCOL,
        "source_commit": summary.get("source_commit") == args.source_commit,
        "protocol_sha256": summary.get("protocol_sha256") == digest(protocol_path),
        "cohorts": summary.get("cohorts") == expected_cohorts,
        "v11_inputs": summary.get("inputs", {}).get("v11") == v11_meta,
        "prospective_inputs": summary.get("inputs", {}).get("prospective") == pro_meta,
        "literal_decision": summary.get("decision", {}).get("literal_transfer_supported")
        == all(c["literal_semantic_support"]["literal_equivalent_fraction"] == 1.0 for c in expected_cohorts.values()),
        "prospective_lineage_decision": summary.get("decision", {}).get("prospective_lineage_only_nondegenerate")
        == (expected_cohorts["prospective_first960_prefix"]["pair_invariance"]["noncode_discriminative_pairs"] > 0),
        "no_performance_claim": summary.get("decision", {}).get("performance_claim_allowed") is False,
        "security_contract": summary.get("security") == {
            "prospective_outcomes_opened": False, "prospective_label_vault_opened": False,
            "scorer_predictions_opened": False, "raw_code_task_run_or_card_values_emitted": False,
            "v11_outcome_metrics_computed": False, "gpu": 0, "api_calls": 0, "base_llm_updates": 0,
        },
    }
    if not all(assertions.values()):
        failed = [name for name, passed in assertions.items() if not passed]
        raise VerifyError("failed assertions: " + ",".join(failed))
    expected_omission = (
        not summary["decision"]["literal_transfer_supported"]
        and not summary["decision"]["prospective_lineage_only_nondegenerate"]
    )
    if summary["decision"].get("baseline_omission_rationale_supported") != expected_omission:
        raise VerifyError("omission decision mismatch")
    return {
        "status": "INDEPENDENT_FLORA_TRANSFER_AUDIT_VERIFIED",
        "protocol": PROTOCOL,
        "source_commit": args.source_commit,
        "artifact_summary_sha256": digest(artifact / "summary.json"),
        "assertions": assertions,
        "all_pass": True,
        "producer_imported": False,
        "prospective_outcomes_opened": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--v11-cards", required=True)
    parser.add_argument("--v11-decision", action="append", required=True)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--cohort-run-target", type=int, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = verify(args)
        output = Path(args.output)
        if output.exists():
            raise VerifyError("refusing to overwrite verifier output")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    except (VerifyError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"FLORA_TRANSFER_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    print(receipt["status"], "outcomes_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
