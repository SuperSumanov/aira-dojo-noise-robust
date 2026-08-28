"""Independent verifier for full-v11-release identifier-erased overlap."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

from phase1 import historical_release_future_identifier_erased_schema as schema
from phase1 import historical_train_future_identifier_erased_schema as train_schema
from phase1 import verify_historical_train_future_fuzzy_overlap as independent_core
from phase1 import verify_historical_train_future_identifier_erased_overlap as token_core


class ReleaseOverlapVerificationError(RuntimeError):
    """Raised when an independently recomputed value differs."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseOverlapVerificationError(message)


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
                raise ReleaseOverlapVerificationError(
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
    require(observed == expected, "independent dependency contract drift")


def validate_protocol(protocol: dict[str, Any]) -> None:
    historical = protocol.get("fixed_historical_population", {})
    future = protocol.get("fixed_future_population", {})
    require(protocol.get("status") == "RESULT_BLIND_PROTOCOL_FROZEN", "protocol status")
    require(historical.get("cards_sha256") == schema.HISTORICAL_CARDS_SHA256, "protocol cards SHA")
    require(historical.get("endpoints") == schema.HISTORICAL_ENDPOINTS, "protocol endpoints")
    require(historical.get("physical_runs") == schema.HISTORICAL_RUNS, "protocol runs")
    require(historical.get("tasks") == schema.HISTORICAL_TASKS, "protocol tasks")
    require(future.get("snapshot_sha256") == schema.FIXED_SNAPSHOT_SHA256, "protocol snapshot")
    require(future.get("runs") == schema.OBSERVED_FUTURE_RUNS, "protocol future runs")
    require(future.get("endpoints") == schema.OBSERVED_FUTURE_ENDPOINTS, "protocol future endpoints")
    require(protocol.get("representation", {}).get("name") == schema.REPRESENTATION, "protocol representation")
    require(protocol.get("thresholds", {}).get("primary_jaccard") == "17/20", "protocol primary")
    require(protocol.get("thresholds", {}).get("strict_sensitivity_jaccard") == "19/20", "protocol strict")


def load_historical_release(
    repo_root: Path,
) -> tuple[list[independent_core.CodeRecord], dict[str, Any]]:
    cards_path = repo_root / schema.HISTORICAL_CARDS_PATH
    receipt_path = repo_root / schema.HISTORICAL_RELEASE_RECEIPT_PATH
    require(cards_path.stat().st_size == schema.HISTORICAL_CARDS_BYTES, "cards bytes")
    require(sha256_file(cards_path) == schema.HISTORICAL_CARDS_SHA256, "cards SHA")
    require(sha256_file(receipt_path) == schema.HISTORICAL_RELEASE_RECEIPT_SHA256, "receipt SHA")
    receipt = read_json(receipt_path)
    output = receipt.get("output", {})
    segmentation = receipt.get("segmentation", {})
    require(receipt.get("status") == "VERIFIED_BYTE_EXACT_CORPUS_REBUILD", "receipt status")
    require(
        (output.get("rows"), output.get("bytes"), output.get("sha256"))
        == (
            schema.HISTORICAL_ENDPOINTS,
            schema.HISTORICAL_CARDS_BYTES,
            schema.HISTORICAL_CARDS_SHA256,
        ),
        "receipt output",
    )
    require(
        (
            segmentation.get("runs"),
            segmentation.get("cross_segment_parents"),
            segmentation.get("mixed_task_segments"),
        )
        == (schema.HISTORICAL_RUNS, 0, 0),
        "receipt segmentation",
    )
    records: list[independent_core.CodeRecord] = []
    seen: set[str] = set()
    runs: set[str] = set()
    tasks: set[str] = set()
    for row in read_jsonl(cards_path):
        card_id, run_id, code, task = (
            row.get("id"),
            row.get("run_id"),
            row.get("code"),
            row.get("task"),
        )
        require(isinstance(card_id, str) and card_id not in seen, "card ID")
        require(isinstance(run_id, str) and run_id, "run ID")
        require(isinstance(code, str), "code")
        require(isinstance(task, dict) and isinstance(task.get("name"), str), "task")
        seen.add(card_id)
        runs.add(run_id)
        tasks.add(task["name"])
        records.append(independent_core.CodeRecord(card_id, run_id, task["name"], code))
    require(
        (len(records), len(runs), len(tasks))
        == (schema.HISTORICAL_ENDPOINTS, schema.HISTORICAL_RUNS, schema.HISTORICAL_TASKS),
        "historical population counts",
    )
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
    return (
        "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS"
        if primary_links == 0
        else "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS"
    )


def reproduce(
    repo_root: Path,
    state_root: Path,
    snapshot_root: Path,
    producer: dict[str, Any],
    protocol: dict[str, Any],
    receipt_path: Path,
) -> dict[str, Any]:
    require_dependency_contract()
    validate_protocol(protocol)
    require(producer.get("protocol") == schema.PROTOCOL, "producer protocol")
    require(producer.get("snapshot_sha256") == schema.FIXED_SNAPSHOT_SHA256, "producer snapshot")
    historical_code, historical_scope = load_historical_release(repo_root)
    prospective_code, prospective_inputs = independent_core.load_prospective(
        state_root, snapshot_root, producer
    )
    require(historical_scope == producer["historical_scope"], "historical scope")
    require(prospective_inputs == producer["prospective_scope"]["inputs"], "prospective inputs")
    historical, historical_fingerprint = token_core.fingerprint(historical_code)
    prospective, prospective_fingerprint = token_core.fingerprint(prospective_code)
    require(historical and prospective, "empty fingerprinted side")
    require(historical_fingerprint == producer["historical_fingerprinting"], "historical fingerprint")
    require(prospective_fingerprint == producer["prospective_fingerprinting"], "future fingerprint")
    historical_runs = {record.run_id for record in historical_code}
    prospective_runs = {record.run_id for record in prospective_code}
    require(not historical_runs.intersection(prospective_runs), "historical/future run overlap")
    require(len(prospective_runs) == schema.OBSERVED_FUTURE_RUNS, "future runs")
    require(len(prospective_code) == schema.OBSERVED_FUTURE_ENDPOINTS, "future endpoints")
    require(len({record.task for record in prospective_code}) == schema.OBSERVED_FUTURE_TASKS, "future tasks")

    edges, candidates = independent_core.independent_join(historical, prospective)
    strict_edges = [
        edge
        for edge in edges
        if schema.STRICT_DENOMINATOR * edge.intersection
        >= schema.STRICT_NUMERATOR * edge.union
    ]
    primary = independent_core.aggregate(historical, prospective, edges)
    strict = independent_core.aggregate(historical, prospective, strict_edges)
    require(
        candidates == producer["primary_jaccard_0_85"]["candidate_pairs_exactly_checked"],
        "candidate count",
    )
    for key, value in primary.items():
        require(value == producer["primary_jaccard_0_85"][key], f"primary {key}")
    for key, value in strict.items():
        require(value == producer["strict_jaccard_0_95"][key], f"strict {key}")

    historical_subset = sorted(
        historical, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    prospective_subset = sorted(
        prospective, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    subset_join, _ = independent_core.independent_join(historical_subset, prospective_subset)
    subset_brute = independent_core.brute_force(historical_subset, prospective_subset)
    join_digest = independent_core.edge_signature(subset_join)
    brute_digest = independent_core.edge_signature(subset_brute)
    require(join_digest == brute_digest, "independent subset brute force")
    require(join_digest == producer["bipartite_join_self_check"]["join_edge_digest"], "producer join digest")
    require(brute_digest == producer["bipartite_join_self_check"]["brute_force_edge_digest"], "producer brute digest")
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
        "bipartite_join_self_check": True,
    }
    require(gates == producer["pre_registered_gate"]["checks"], "gate values")
    classification = classify(gates, len(edges))
    require(classification == producer["classification"], "classification")
    require(producer["claim_boundary"] == protocol["claim_boundary"], "claim boundary")
    return {
        "protocol": schema.INDEPENDENT_PROTOCOL,
        "status": "INDEPENDENTLY_VERIFIED_HISTORICAL_RELEASE_FUTURE_OVERLAP",
        "classification": classification,
        "producer_receipt_sha256": sha256_file(receipt_path),
        "snapshot_sha256": producer["snapshot_sha256"],
        "historical_endpoints": len(historical_code),
        "historical_runs": len(historical_runs),
        "prospective_endpoints": len(prospective_code),
        "prospective_runs": len(prospective_runs),
        "primary_candidate_pairs": candidates,
        "primary_near_duplicate_pairs": len(edges),
        "primary_edge_digest_sha256": primary["edge_digest_sha256"],
        "strict_near_duplicate_pairs": len(strict_edges),
        "strict_edge_digest_sha256": strict["edge_digest_sha256"],
        "producer_aggregate_matches": True,
        "subset_bruteforce_matches": True,
        "imports_new_producer_code": False,
        "raw_senior_archives_opened": False,
        "historical_label_or_observation_fields_used": False,
        "prospective_outcomes_read": False,
        "prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
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
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    producer = read_json(args.receipt)
    protocol = read_json(args.protocol)
    require(sha256_file(args.protocol) == args.expect_protocol_sha256, "protocol SHA")
    validate_protocol(protocol)
    head = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    require(head == producer["source_commit"], "HEAD/source commit")
    producer_path = repo_root / "phase1/audit_historical_release_future_identifier_erased_overlap.py"
    require(sha256_file(producer_path) == producer["source_sha256"], "producer SHA")
    require(sha256_file(Path(schema.__file__).resolve()) == producer["schema_sha256"], "schema SHA")
    require(
        sha256_file(Path(independent_core.__file__).resolve()) != producer["join_core_sha256"],
        "producer and verifier join cores unexpectedly identical",
    )
    dependencies = (
        Path(__file__).resolve(),
        Path(schema.__file__).resolve(),
        Path(independent_core.__file__).resolve(),
        Path(token_core.__file__).resolve(),
        args.protocol.resolve(),
    )
    for path in dependencies:
        require(
            committed_blob(repo_root, head, path)
            == subprocess.check_output(
                ["git", "-C", str(repo_root), "hash-object", str(path)], text=True
            ).strip(),
            f"verifier blob binding: {path.name}",
        )
    result = reproduce(
        repo_root,
        args.state_root,
        args.snapshot_root,
        producer,
        protocol,
        args.receipt.resolve(),
    )
    result["verifier_source_sha256"] = sha256_file(Path(__file__).resolve())
    result["independent_join_core_sha256"] = sha256_file(
        Path(independent_core.__file__).resolve()
    )
    result["independent_token_core_sha256"] = sha256_file(
        Path(token_core.__file__).resolve()
    )
    atomic_json(args.output, result)
    print(result["status"])


if __name__ == "__main__":
    main()
