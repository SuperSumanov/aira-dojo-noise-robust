"""Outcome-blind full-v11-release to prospective identifier-erased audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from phase1 import audit_historical_train_future_fuzzy_overlap as join_core
from phase1 import audit_historical_train_future_identifier_erased_overlap as id_core
from phase1 import audit_prospective_fuzzy_code_clones as cohort
from phase1 import historical_release_future_identifier_erased_schema as schema
from phase1 import historical_train_future_identifier_erased_schema as train_schema


class ReleaseOverlapAuditError(RuntimeError):
    """Raised when a frozen input, blindness gate, or result binding fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseOverlapAuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected object: {path.name}")
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ReleaseOverlapAuditError(
                    f"invalid JSONL: {path.name}:{line_number}"
                ) from error
            require(isinstance(value, dict), f"non-object: {path.name}:{line_number}")
            yield value


def require_dependency_contract() -> None:
    observed = (
        train_schema.FROZEN_COHORT_RUN_TARGET,
        train_schema.SHINGLE_SIZE,
        train_schema.SHINGLE_HASH_BITS,
        train_schema.MIN_DISTINCT_SHINGLES,
        train_schema.PRIMARY_NUMERATOR,
        train_schema.PRIMARY_DENOMINATOR,
        train_schema.STRICT_NUMERATOR,
        train_schema.STRICT_DENOMINATOR,
        train_schema.SELF_CHECK_PER_SIDE,
        train_schema.MIN_HISTORICAL_COVERAGE,
        train_schema.MIN_PROSPECTIVE_COVERAGE,
        train_schema.MAX_PROSPECTIVE_AFFECTED_FRACTION,
        train_schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION,
        train_schema.MAX_LARGE_MULTITASK_COMPONENTS,
        train_schema.LARGE_COMPONENT_MIN_ENDPOINTS,
        train_schema.LARGE_COMPONENT_MIN_TASKS,
        train_schema.IDENTIFIER_TOKEN,
        train_schema.NUMBER_TOKEN,
        train_schema.STRING_TOKEN,
    )
    expected = (
        schema.FROZEN_COHORT_RUN_TARGET,
        schema.SHINGLE_SIZE,
        schema.SHINGLE_HASH_BITS,
        schema.MIN_DISTINCT_SHINGLES,
        schema.PRIMARY_NUMERATOR,
        schema.PRIMARY_DENOMINATOR,
        schema.STRICT_NUMERATOR,
        schema.STRICT_DENOMINATOR,
        schema.SELF_CHECK_PER_SIDE,
        schema.MIN_HISTORICAL_COVERAGE,
        schema.MIN_PROSPECTIVE_COVERAGE,
        schema.MAX_PROSPECTIVE_AFFECTED_FRACTION,
        schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION,
        schema.MAX_LARGE_MULTITASK_COMPONENTS,
        schema.LARGE_COMPONENT_MIN_ENDPOINTS,
        schema.LARGE_COMPONENT_MIN_TASKS,
        schema.IDENTIFIER_TOKEN,
        schema.NUMBER_TOKEN,
        schema.STRING_TOKEN,
    )
    require(observed == expected, "identifier-erased dependency contract drift")


def validate_protocol(protocol: dict[str, Any]) -> None:
    historical = protocol.get("fixed_historical_population", {})
    future = protocol.get("fixed_future_population", {})
    representation = protocol.get("representation", {})
    thresholds = protocol.get("thresholds", {})
    require(protocol.get("status") == "RESULT_BLIND_PROTOCOL_FROZEN", "protocol status")
    require(historical.get("cards_sha256") == schema.HISTORICAL_CARDS_SHA256, "protocol cards SHA")
    require(historical.get("endpoints") == schema.HISTORICAL_ENDPOINTS, "protocol historical endpoints")
    require(historical.get("physical_runs") == schema.HISTORICAL_RUNS, "protocol historical runs")
    require(historical.get("tasks") == schema.HISTORICAL_TASKS, "protocol historical tasks")
    require(future.get("snapshot_sha256") == schema.FIXED_SNAPSHOT_SHA256, "protocol snapshot")
    require(future.get("runs") == schema.OBSERVED_FUTURE_RUNS, "protocol future runs")
    require(future.get("endpoints") == schema.OBSERVED_FUTURE_ENDPOINTS, "protocol future endpoints")
    require(representation.get("name") == schema.REPRESENTATION, "protocol representation")
    require(thresholds.get("primary_jaccard") == "17/20", "protocol primary threshold")
    require(thresholds.get("strict_sensitivity_jaccard") == "19/20", "protocol strict threshold")


def load_historical_release(
    repo_root: Path,
) -> tuple[list[cohort.CodeRecord], dict[str, Any]]:
    cards_path = repo_root / schema.HISTORICAL_CARDS_PATH
    receipt_path = repo_root / schema.HISTORICAL_RELEASE_RECEIPT_PATH
    require(cards_path.stat().st_size == schema.HISTORICAL_CARDS_BYTES, "historical cards bytes")
    require(sha256_file(cards_path) == schema.HISTORICAL_CARDS_SHA256, "historical cards SHA")
    require(
        sha256_file(receipt_path) == schema.HISTORICAL_RELEASE_RECEIPT_SHA256,
        "historical release receipt SHA",
    )
    receipt = read_json(receipt_path)
    release_output = receipt.get("output", {})
    segmentation = receipt.get("segmentation", {})
    require(receipt.get("status") == "VERIFIED_BYTE_EXACT_CORPUS_REBUILD", "release receipt status")
    require(release_output.get("rows") == schema.HISTORICAL_ENDPOINTS, "release receipt rows")
    require(release_output.get("bytes") == schema.HISTORICAL_CARDS_BYTES, "release receipt bytes")
    require(release_output.get("sha256") == schema.HISTORICAL_CARDS_SHA256, "release receipt cards SHA")
    require(segmentation.get("runs") == schema.HISTORICAL_RUNS, "release receipt runs")
    require(segmentation.get("cross_segment_parents") == 0, "release cross-segment parents")
    require(segmentation.get("mixed_task_segments") == 0, "release mixed-task segments")

    records: list[cohort.CodeRecord] = []
    seen: set[str] = set()
    runs: set[str] = set()
    tasks: set[str] = set()
    for row in read_jsonl(cards_path):
        card_id = row.get("id")
        run_id = row.get("run_id")
        code = row.get("code")
        task = row.get("task")
        require(isinstance(card_id, str) and card_id not in seen, "historical card ID")
        require(isinstance(run_id, str) and run_id, "historical run ID")
        require(isinstance(code, str), "historical code")
        require(isinstance(task, dict) and isinstance(task.get("name"), str), "historical task")
        seen.add(card_id)
        runs.add(run_id)
        tasks.add(task["name"])
        records.append(cohort.CodeRecord(card_id, run_id, task["name"], "", code))
    require(len(records) == schema.HISTORICAL_ENDPOINTS, "historical endpoint count")
    require(len(runs) == schema.HISTORICAL_RUNS, "historical run count")
    require(len(tasks) == schema.HISTORICAL_TASKS, "historical task count")
    records.sort(key=lambda record: record.card_id)
    return records, {
        "population": "complete_byte_reproducible_v11_release",
        "cards_path": schema.HISTORICAL_CARDS_PATH,
        "cards_sha256": schema.HISTORICAL_CARDS_SHA256,
        "cards_bytes": schema.HISTORICAL_CARDS_BYTES,
        "release_receipt_path": schema.HISTORICAL_RELEASE_RECEIPT_PATH,
        "release_receipt_sha256": schema.HISTORICAL_RELEASE_RECEIPT_SHA256,
        "endpoints": len(records),
        "runs": len(runs),
        "tasks": len(tasks),
        "historical_label_or_observation_fields_used": False,
    }


def classify(gates: dict[str, bool], primary_links: int) -> str:
    if not all(gates.values()):
        return "RELEASE_SPLIT_INTEGRITY_GATE_FAIL"
    if primary_links == 0:
        return "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS"
    return "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS"


def audit(
    repo_root: Path,
    state_root: Path,
    snapshot_root: Path,
    source_commit: str,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    require_dependency_contract()
    validate_protocol(protocol)
    require(snapshot_root.resolve().name == schema.FIXED_SNAPSHOT_SHA256, "snapshot root")
    historical_code, historical_scope = load_historical_release(repo_root)
    future_code, future_inputs = cohort.load_cohort(
        state_root, snapshot_root, schema.FROZEN_COHORT_RUN_TARGET
    )
    historical, historical_fingerprint = id_core.fingerprint(historical_code)
    prospective, prospective_fingerprint = id_core.fingerprint(future_code)
    require(historical and prospective, "empty fingerprinted side")
    historical_runs = {record.run_id for record in historical_code}
    prospective_runs = {record.run_id for record in future_code}
    require(not historical_runs.intersection(prospective_runs), "historical/future run overlap")
    require(len(prospective_runs) == schema.OBSERVED_FUTURE_RUNS, "future run count")
    require(len(future_code) == schema.OBSERVED_FUTURE_ENDPOINTS, "future endpoint count")
    require(len({record.task for record in future_code}) == schema.OBSERVED_FUTURE_TASKS, "future task count")

    primary_edges, candidates = join_core.bipartite_join(historical, prospective)
    strict_edges = [
        edge
        for edge in primary_edges
        if schema.STRICT_DENOMINATOR * edge.intersection
        >= schema.STRICT_NUMERATOR * edge.union
    ]
    primary = join_core.aggregate(historical, prospective, primary_edges)
    strict = join_core.aggregate(historical, prospective, strict_edges)
    historical_subset = sorted(
        historical, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    prospective_subset = sorted(
        prospective, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    subset_join, _ = join_core.bipartite_join(historical_subset, prospective_subset)
    subset_brute = join_core.brute_force(historical_subset, prospective_subset)
    join_digest = join_core.edge_signature(subset_join)
    brute_digest = join_core.edge_signature(subset_brute)
    self_check = join_digest == brute_digest
    gates = {
        "historical_fingerprint_coverage": historical_fingerprint["coverage"]
        >= schema.MIN_HISTORICAL_COVERAGE,
        "prospective_fingerprint_coverage": prospective_fingerprint["coverage"]
        >= schema.MIN_PROSPECTIVE_COVERAGE,
        "prospective_affected_fraction": primary["prospective_affected_fraction"]
        <= schema.MAX_PROSPECTIVE_AFFECTED_FRACTION,
        "cross_task_prospective_affected_fraction": primary[
            "cross_task_prospective_affected_fraction"
        ]
        <= schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION,
        "large_multitask_components": primary["large_multitask_components"]
        <= schema.MAX_LARGE_MULTITASK_COMPONENTS,
        "bipartite_join_self_check": self_check,
    }
    classification = classify(gates, len(primary_edges))
    return {
        "protocol": schema.PROTOCOL,
        "status": "PROVISIONAL_HISTORICAL_RELEASE_FUTURE_OVERLAP_AUDIT_COMPLETE",
        "classification": classification,
        "source_commit": source_commit,
        "source_sha256": sha256_file(Path(__file__)),
        "schema_sha256": sha256_file(Path(schema.__file__).resolve()),
        "identifier_core_sha256": sha256_file(Path(id_core.__file__).resolve()),
        "join_core_sha256": sha256_file(Path(join_core.__file__).resolve()),
        "cohort_loader_sha256": sha256_file(Path(cohort.__file__).resolve()),
        "snapshot_sha256": snapshot_root.resolve().name,
        "historical_scope": historical_scope,
        "prospective_scope": {
            "target_runs": schema.FROZEN_COHORT_RUN_TARGET,
            "observed_runs": len(prospective_runs),
            "observed_endpoints": len(future_code),
            "observed_tasks": len({record.task for record in future_code}),
            "closure_provided": False,
            "inputs": future_inputs,
        },
        "representation_contract": {
            "name": schema.REPRESENTATION,
            "shingle_size": schema.SHINGLE_SIZE,
            "shingle_hash_bits": schema.SHINGLE_HASH_BITS,
            "minimum_distinct_shingles": schema.MIN_DISTINCT_SHINGLES,
            "primary_jaccard": [schema.PRIMARY_NUMERATOR, schema.PRIMARY_DENOMINATOR],
            "strict_jaccard": [schema.STRICT_NUMERATOR, schema.STRICT_DENOMINATOR],
        },
        "historical_fingerprinting": historical_fingerprint,
        "prospective_fingerprinting": prospective_fingerprint,
        "physical_run_sets_disjoint": True,
        "primary_jaccard_0_85": {
            "threshold_numerator": schema.PRIMARY_NUMERATOR,
            "threshold_denominator": schema.PRIMARY_DENOMINATOR,
            "candidate_pairs_exactly_checked": candidates,
            **primary,
        },
        "strict_jaccard_0_95": {
            "threshold_numerator": schema.STRICT_NUMERATOR,
            "threshold_denominator": schema.STRICT_DENOMINATOR,
            **strict,
        },
        "bipartite_join_self_check": {
            "historical_documents": len(historical_subset),
            "prospective_documents": len(prospective_subset),
            "brute_force_pairs": len(historical_subset) * len(prospective_subset),
            "join_edge_digest": join_digest,
            "brute_force_edge_digest": brute_digest,
            "passed": self_check,
        },
        "pre_registered_gate": {
            "checks": gates,
            "all_passed": all(gates.values()),
            "thresholds": {
                "minimum_historical_coverage": schema.MIN_HISTORICAL_COVERAGE,
                "minimum_prospective_coverage": schema.MIN_PROSPECTIVE_COVERAGE,
                "maximum_prospective_affected_fraction": schema.MAX_PROSPECTIVE_AFFECTED_FRACTION,
                "maximum_cross_task_prospective_affected_fraction": (
                    schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION
                ),
                "maximum_large_multitask_components": schema.MAX_LARGE_MULTITASK_COMPONENTS,
            },
        },
        "prior_result_disclosure": protocol["prior_result_disclosure"],
        "claim_boundary": protocol["claim_boundary"],
        "reproducibility": {
            "python_version": platform.python_version(),
            "python_executable": str(Path(sys.executable).resolve()),
            "randomness_used": False,
        },
        "security": {
            "historical_label_or_observation_fields_used": False,
            "prospective_label_vault_opened": False,
            "prospective_outcome_files_opened": [],
            "prediction_values_read": False,
            "code_or_identity_values_emitted": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def atomic_json(path: Path, payload: Any) -> None:
    require(not path.exists(), f"output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def committed_blob(repo_root: Path, head: str, path: Path) -> str:
    relative = path.resolve().relative_to(repo_root).as_posix()
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", f"{head}:{relative}"], text=True
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    head = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    require(head == args.source_commit, "source commit binding")
    require(sha256_file(args.protocol) == args.expect_protocol_sha256, "protocol SHA")
    protocol = read_json(args.protocol)
    validate_protocol(protocol)
    dependencies = (
        Path(__file__).resolve(),
        Path(schema.__file__).resolve(),
        Path(id_core.__file__).resolve(),
        Path(join_core.__file__).resolve(),
        Path(cohort.__file__).resolve(),
        args.protocol.resolve(),
    )
    for path in dependencies:
        require(
            committed_blob(repo_root, head, path)
            == subprocess.check_output(
                ["git", "-C", str(repo_root), "hash-object", str(path)], text=True
            ).strip(),
            f"source blob binding: {path.name}",
        )
    result = audit(repo_root, args.state_root, args.snapshot_root, args.source_commit, protocol)
    atomic_json(args.output, result)
    print(
        result["status"],
        f"historical={result['historical_scope']['endpoints']}",
        f"prospective={result['prospective_scope']['observed_endpoints']}",
        "prospective_outcomes_read=false",
    )


if __name__ == "__main__":
    main()
