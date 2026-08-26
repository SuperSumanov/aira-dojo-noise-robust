"""Independent verifier for identifier-erased historical-to-future overlap."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import keyword
import os
import subprocess
import tokenize
from pathlib import Path
from typing import Any

from phase1 import historical_train_future_identifier_erased_schema as schema
from phase1 import historical_train_future_overlap_schema as lexical_schema
from phase1 import verify_historical_train_future_fuzzy_overlap as independent_core


class IdentifierErasedVerificationError(RuntimeError):
    """Raised when an independently recomputed value differs."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IdentifierErasedVerificationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_dependency_contract() -> None:
    observed = (
        lexical_schema.FROZEN_COHORT_RUN_TARGET,
        lexical_schema.SHINGLE_SIZE,
        lexical_schema.SHINGLE_HASH_BITS,
        lexical_schema.MIN_DISTINCT_SHINGLES,
        lexical_schema.PRIMARY_NUMERATOR,
        lexical_schema.PRIMARY_DENOMINATOR,
        lexical_schema.STRICT_NUMERATOR,
        lexical_schema.STRICT_DENOMINATOR,
        lexical_schema.SELF_CHECK_PER_SIDE,
        lexical_schema.MIN_HISTORICAL_COVERAGE,
        lexical_schema.MIN_PROSPECTIVE_COVERAGE,
        lexical_schema.MAX_PROSPECTIVE_AFFECTED_FRACTION,
        lexical_schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION,
        lexical_schema.MAX_LARGE_MULTITASK_COMPONENTS,
        lexical_schema.LARGE_COMPONENT_MIN_ENDPOINTS,
        lexical_schema.LARGE_COMPONENT_MIN_TASKS,
        lexical_schema.HISTORICAL_CARDS_SHA256,
        lexical_schema.HISTORICAL_PAIR_FILES,
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
        schema.HISTORICAL_CARDS_SHA256,
        schema.HISTORICAL_PAIR_FILES,
    )
    require(observed == expected, "independent-core dependency contract drift")


def independent_identifier_erased_tokens(code: str) -> tuple[str, ...] | None:
    ignored = {
        tokenize.ENCODING,
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
    }
    values: list[str] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type in ignored:
                continue
            if token.type == tokenize.NAME:
                values.append(
                    token.string if keyword.iskeyword(token.string) else schema.IDENTIFIER_TOKEN
                )
            elif token.type == tokenize.NUMBER:
                values.append(schema.NUMBER_TOKEN)
            elif token.type == tokenize.STRING:
                values.append(schema.STRING_TOKEN)
            elif token.type == tokenize.OP:
                values.append(token.string)
            elif token.type == tokenize.ERRORTOKEN and token.string.isspace():
                continue
            else:
                values.append(f"{tokenize.tok_name[token.type]}:{token.string}")
    except (IndentationError, SyntaxError, tokenize.TokenError):
        return None
    return tuple(values)


def independent_shingles(tokens: tuple[str, ...]) -> frozenset[int] | None:
    if len(tokens) < schema.SHINGLE_SIZE:
        return None
    hashes: set[int] = set()
    for start in range(0, len(tokens) - schema.SHINGLE_SIZE + 1):
        payload = "\0".join(tokens[start : start + schema.SHINGLE_SIZE]).encode(
            "utf-8"
        )
        digest = hashlib.blake2b(
            payload, digest_size=schema.SHINGLE_HASH_BITS // 8
        ).digest()
        hashes.add(int.from_bytes(digest, byteorder="big", signed=False))
    return frozenset(hashes) if len(hashes) >= schema.MIN_DISTINCT_SHINGLES else None


def fingerprint(
    records: list[independent_core.CodeRecord],
) -> tuple[list[independent_core.Record], dict[str, Any]]:
    values: list[independent_core.Record] = []
    token_failures = 0
    too_short = 0
    for record in records:
        tokens = independent_identifier_erased_tokens(record.code)
        if tokens is None:
            token_failures += 1
            continue
        shingles = independent_shingles(tokens)
        if shingles is None:
            too_short += 1
            continue
        values.append(
            independent_core.Record(
                record.card_id, record.run_id, record.task, shingles
            )
        )
    return values, {
        "input_endpoints": len(records),
        "fingerprinted_endpoints": len(values),
        "tokenization_failures": token_failures,
        "too_short_or_low_distinct_shingles": too_short,
        "coverage": len(values) / len(records) if records else None,
    }


def reproduce(
    repo_root: Path,
    state_root: Path,
    snapshot_root: Path,
    producer: dict[str, Any],
) -> dict[str, Any]:
    require_dependency_contract()
    require(producer.get("protocol") == schema.PROTOCOL, "protocol")
    require(
        producer["representation_contract"]["name"] == schema.REPRESENTATION,
        "representation",
    )
    historical_code, historical_scope = independent_core.load_historical(repo_root)
    prospective_code, prospective_inputs = independent_core.load_prospective(
        state_root, snapshot_root, producer
    )
    require(historical_scope == producer["historical_scope"], "historical scope")
    require(
        prospective_inputs == producer["prospective_scope"]["inputs"],
        "prospective inputs",
    )
    historical, historical_fingerprint = fingerprint(historical_code)
    prospective, prospective_fingerprint = fingerprint(prospective_code)
    require(historical and prospective, "empty fingerprinted side")
    require(
        historical_fingerprint == producer["historical_fingerprinting"],
        "historical fingerprint",
    )
    require(
        prospective_fingerprint == producer["prospective_fingerprinting"],
        "prospective fingerprint",
    )
    historical_runs = {record.run_id for record in historical_code}
    prospective_runs = {record.run_id for record in prospective_code}
    require(not historical_runs.intersection(prospective_runs), "physical run overlap")
    require(
        len(prospective_runs) == producer["prospective_scope"]["observed_runs"],
        "run count",
    )
    require(
        len(prospective_code) == producer["prospective_scope"]["observed_endpoints"],
        "endpoint count",
    )

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
        candidates
        == producer["primary_jaccard_0_85"]["candidate_pairs_exactly_checked"],
        "candidate count",
    )
    for key, value in primary.items():
        require(value == producer["primary_jaccard_0_85"][key], f"primary: {key}")
    for key, value in strict.items():
        require(value == producer["strict_jaccard_0_95"][key], f"strict: {key}")

    historical_subset = sorted(
        historical, key=lambda record: independent_core.sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    prospective_subset = sorted(
        prospective, key=lambda record: independent_core.sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    subset_join, _ = independent_core.independent_join(
        historical_subset, prospective_subset
    )
    subset_brute = independent_core.brute_force(
        historical_subset, prospective_subset
    )
    join_digest = independent_core.edge_signature(subset_join)
    brute_digest = independent_core.edge_signature(subset_brute)
    require(join_digest == brute_digest, "subset brute force")
    producer_check = producer["bipartite_join_self_check"]
    require(join_digest == producer_check["join_edge_digest"], "producer subset join")
    require(
        brute_digest == producer_check["brute_force_edge_digest"],
        "producer subset brute",
    )

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
    return {
        "protocol": schema.INDEPENDENT_PROTOCOL,
        "status": "INDEPENDENTLY_VERIFIED_PROVISIONAL_IDENTIFIER_ERASED_OVERLAP",
        "producer_receipt_sha256": sha256_file(Path(producer["_receipt_path"])),
        "snapshot_sha256": producer["snapshot_sha256"],
        "historical_endpoints": len(historical_code),
        "prospective_runs": len(prospective_runs),
        "prospective_endpoints": len(prospective_code),
        "primary_candidate_pairs": candidates,
        "primary_near_duplicate_pairs": len(edges),
        "primary_edge_digest_sha256": primary["edge_digest_sha256"],
        "strict_near_duplicate_pairs": len(strict_edges),
        "strict_edge_digest_sha256": strict["edge_digest_sha256"],
        "producer_aggregate_matches": True,
        "subset_bruteforce_matches": True,
        "imports_new_producer_code": False,
        "historical_label_or_observation_fields_used": False,
        "prospective_outcomes_read": False,
        "prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "receipt object")
    return value


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise IdentifierErasedVerificationError(f"output exists: {path}")
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    producer = read_json(args.receipt)
    producer["_receipt_path"] = str(args.receipt.resolve())
    head = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    require(head == producer["source_commit"], "HEAD/source commit")
    producer_path = (
        repo_root / "phase1/audit_historical_train_future_identifier_erased_overlap.py"
    )
    require(sha256_file(producer_path) == producer["source_sha256"], "producer SHA")
    require(
        sha256_file(Path(schema.__file__).resolve()) == producer["schema_sha256"],
        "schema SHA",
    )
    require(
        sha256_file(Path(independent_core.__file__).resolve())
        != producer["lexical_core_sha256"],
        "producer and verifier core unexpectedly identical",
    )
    for path in (
        Path(__file__).resolve(),
        Path(schema.__file__).resolve(),
        Path(lexical_schema.__file__).resolve(),
        Path(independent_core.__file__).resolve(),
    ):
        worktree_blob = subprocess.check_output(
            ["git", "-C", str(repo_root), "hash-object", str(path)], text=True
        ).strip()
        require(
            committed_blob(repo_root, head, path) == worktree_blob,
            f"verifier blob binding: {path.name}",
        )
    result = reproduce(repo_root, args.state_root, args.snapshot_root, producer)
    result["verifier_source_sha256"] = sha256_file(Path(__file__).resolve())
    result["independent_core_sha256"] = sha256_file(
        Path(independent_core.__file__).resolve()
    )
    atomic_json(args.output, result)
    print(result["status"])


if __name__ == "__main__":
    main()
