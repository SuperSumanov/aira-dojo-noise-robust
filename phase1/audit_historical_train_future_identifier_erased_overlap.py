"""Outcome-blind identifier-erased overlap audit from v11 train to first-960."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import keyword
import os
import platform
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Any

from phase1 import audit_historical_train_future_fuzzy_overlap as lexical_core
from phase1 import audit_prospective_fuzzy_code_clones as cohort
from phase1 import historical_train_future_identifier_erased_schema as schema
from phase1 import historical_train_future_overlap_schema as lexical_schema


class IdentifierErasedAuditError(RuntimeError):
    """Raised when a frozen input, representation, or blindness gate fails."""


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
    if observed != expected:
        raise IdentifierErasedAuditError("lexical-core dependency contract drift")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def identifier_erased_tokens(code: str) -> tuple[str, ...] | None:
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
        stream = tokenize.generate_tokens(io.StringIO(code).readline)
        for token in stream:
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


def shingles_from_tokens(tokens: tuple[str, ...]) -> frozenset[int] | None:
    if len(tokens) < schema.SHINGLE_SIZE:
        return None
    values = frozenset(
        int.from_bytes(
            hashlib.blake2b(
                "\0".join(tokens[index : index + schema.SHINGLE_SIZE]).encode("utf-8"),
                digest_size=schema.SHINGLE_HASH_BITS // 8,
            ).digest(),
            "big",
        )
        for index in range(len(tokens) - schema.SHINGLE_SIZE + 1)
    )
    return values if len(values) >= schema.MIN_DISTINCT_SHINGLES else None


def fingerprint(
    records: list[cohort.CodeRecord],
) -> tuple[list[lexical_core.Record], dict[str, Any]]:
    values: list[lexical_core.Record] = []
    token_failures = 0
    too_short = 0
    for record in records:
        tokens = identifier_erased_tokens(record.code)
        if tokens is None:
            token_failures += 1
            continue
        shingles = shingles_from_tokens(tokens)
        if shingles is None:
            too_short += 1
            continue
        values.append(
            lexical_core.Record(record.card_id, record.run_id, record.task, shingles)
        )
    return values, {
        "input_endpoints": len(records),
        "fingerprinted_endpoints": len(values),
        "tokenization_failures": token_failures,
        "too_short_or_low_distinct_shingles": too_short,
        "coverage": len(values) / len(records) if records else None,
    }


def audit(
    repo_root: Path,
    state_root: Path,
    snapshot_root: Path,
    source_commit: str,
) -> dict[str, Any]:
    require_dependency_contract()
    historical_code, historical_inputs = lexical_core.load_historical_train(repo_root)
    future_code, future_inputs = cohort.load_cohort(
        state_root, snapshot_root, schema.FROZEN_COHORT_RUN_TARGET
    )
    historical, historical_fingerprint = fingerprint(historical_code)
    prospective, prospective_fingerprint = fingerprint(future_code)
    if not historical or not prospective:
        raise IdentifierErasedAuditError("empty fingerprinted side")
    historical_runs = {record.run_id for record in historical_code}
    prospective_runs = {record.run_id for record in future_code}
    if historical_runs.intersection(prospective_runs):
        raise IdentifierErasedAuditError("historical and prospective runs overlap")

    primary_edges, candidates = lexical_core.bipartite_join(historical, prospective)
    strict_edges = [
        edge
        for edge in primary_edges
        if schema.STRICT_DENOMINATOR * edge.intersection
        >= schema.STRICT_NUMERATOR * edge.union
    ]
    primary = lexical_core.aggregate(historical, prospective, primary_edges)
    strict = lexical_core.aggregate(historical, prospective, strict_edges)
    historical_subset = sorted(
        historical, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    prospective_subset = sorted(
        prospective, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_PER_SIDE]
    subset_join, _ = lexical_core.bipartite_join(
        historical_subset, prospective_subset
    )
    subset_brute = lexical_core.brute_force(historical_subset, prospective_subset)
    join_digest = lexical_core.edge_signature(subset_join)
    brute_digest = lexical_core.edge_signature(subset_brute)
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
    return {
        "protocol": schema.PROTOCOL,
        "status": "PROVISIONAL_IDENTIFIER_ERASED_TRAIN_FUTURE_OVERLAP_AUDIT_COMPLETE",
        "source_commit": source_commit,
        "source_sha256": sha256_file(Path(__file__)),
        "schema_sha256": sha256_file(Path(schema.__file__).resolve()),
        "lexical_core_sha256": sha256_file(Path(lexical_core.__file__).resolve()),
        "cohort_loader_sha256": sha256_file(Path(cohort.__file__).resolve()),
        "lexical_schema_sha256": sha256_file(Path(lexical_schema.__file__).resolve()),
        "representation_contract": {
            "name": schema.REPRESENTATION,
            "python_hard_keywords_preserved": True,
            "non_keyword_names_replaced": schema.IDENTIFIER_TOKEN,
            "numbers_replaced": schema.NUMBER_TOKEN,
            "strings_replaced": schema.STRING_TOKEN,
            "operators_preserved": True,
            "comments_and_layout_dropped": True,
            "shingle_size": schema.SHINGLE_SIZE,
            "shingle_hash_bits": schema.SHINGLE_HASH_BITS,
            "minimum_distinct_shingles": schema.MIN_DISTINCT_SHINGLES,
            "primary_jaccard": [schema.PRIMARY_NUMERATOR, schema.PRIMARY_DENOMINATOR],
            "strict_jaccard": [schema.STRICT_NUMERATOR, schema.STRICT_DENOMINATOR],
        },
        "snapshot_sha256": snapshot_root.resolve().name,
        "historical_scope": historical_inputs,
        "prospective_scope": {
            "target_runs": schema.FROZEN_COHORT_RUN_TARGET,
            "observed_runs": len(prospective_runs),
            "observed_endpoints": len(future_code),
            "closure_provided": False,
            "inputs": future_inputs,
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
            "strong_low_identifier_erased_overlap_support": all(gates.values()),
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
        "interpretation_contract": {
            "identifier_erased_syntactic_overlap_only": True,
            "type_2_and_partial_type_3_clone_sensitivity": True,
            "semantic_equivalence_proven": False,
            "pretraining_contamination_absence_proven": False,
            "aggressive_abstraction_false_positive_risk": True,
            "historical_label_or_observation_fields_used": False,
            "prospective_outcomes_read": False,
            "predictor_effect_computed": False,
            "closure_rerun_required": True,
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "python_executable": str(Path(sys.executable).resolve()),
            "randomness_used": False,
        },
        "security": {
            "prospective_label_vault_opened": False,
            "prospective_outcome_files_opened": [],
            "prediction_values_read": False,
            "code_or_identity_values_emitted": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise IdentifierErasedAuditError(f"output exists: {path}")
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    head = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != args.source_commit:
        raise IdentifierErasedAuditError("source commit binding failed")
    for path in (
        Path(__file__).resolve(),
        Path(schema.__file__).resolve(),
        Path(lexical_core.__file__).resolve(),
        Path(cohort.__file__).resolve(),
        Path(lexical_schema.__file__).resolve(),
    ):
        committed = committed_blob(repo_root, head, path)
        worktree = subprocess.check_output(
            ["git", "-C", str(repo_root), "hash-object", str(path)], text=True
        ).strip()
        if committed != worktree:
            raise IdentifierErasedAuditError(f"source blob binding failed: {path.name}")
    result = audit(repo_root, args.state_root, args.snapshot_root, args.source_commit)
    atomic_json(args.output, result)
    print(
        result["status"],
        f"historical={result['historical_scope']['union_endpoints']}",
        f"prospective={result['prospective_scope']['observed_endpoints']}",
        "prospective_outcomes_read=false",
    )


if __name__ == "__main__":
    main()
