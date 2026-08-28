"""Outcome-blind near-duplicate audit for the prospective first-960 prefix.

The primary relation is exact Jaccard >= 0.85 over sets of normalized
five-token shingles.  "Exact" refers to the threshold join over deterministic
128-bit shingle hashes; it is not a semantic-equivalence claim.  The audit
never emits code, card IDs, run IDs, task names, labels, outcomes, predictions,
or per-edge identities.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import keyword
import math
import os
import platform
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from phase1 import prospective_fuzzy_clone_schema as schema


class FuzzyCloneAuditError(RuntimeError):
    """Raised when an input, blindness, or reproducibility gate fails."""


@dataclass(frozen=True)
class CodeRecord:
    card_id: str
    run_id: str
    task: str
    parent: str
    code: str


@dataclass(frozen=True)
class FingerprintedRecord:
    card_id: str
    run_id: str
    task: str
    parent: str
    shingles: frozenset[int]


@dataclass(frozen=True)
class NearEdge:
    left: int
    right: int
    intersection: int
    union: int


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
    if not isinstance(value, dict):
        raise FuzzyCloneAuditError(f"expected JSON object: {path.name}")
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise FuzzyCloneAuditError(
                    f"invalid JSONL in {path.name} at line {line_number}"
                ) from error
            if not isinstance(value, dict):
                raise FuzzyCloneAuditError(
                    f"non-object JSONL in {path.name} at line {line_number}"
                )
            yield value


def require_sha(path: Path, expected: Any) -> None:
    if not isinstance(expected, str) or sha256_file(path) != expected:
        raise FuzzyCloneAuditError(f"SHA mismatch: {path.name}")


def normalized_tokens(code: str) -> list[str] | None:
    """Return formatting/comment-insensitive tokens with literals normalized."""

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
            value = token.string
            if token.type == tokenize.NUMBER:
                value = "<NUMBER>"
            elif token.type == tokenize.STRING:
                value = "<STRING>"
            values.append(f"{token.type}:{value}")
    except (IndentationError, SyntaxError, tokenize.TokenError):
        return None
    return values


def identifier_erased_tokens(code: str) -> list[str] | None:
    """Return Python tokens after erasing non-keyword names and literals."""

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
                    token.string
                    if keyword.iskeyword(token.string)
                    else schema.IDENTIFIER_TOKEN
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
    return values


def shingles_from_tokens(tokens: list[str]) -> frozenset[int] | None:
    if len(tokens) < schema.SHINGLE_SIZE:
        return None
    values: set[int] = set()
    for offset in range(len(tokens) - schema.SHINGLE_SIZE + 1):
        payload = "\x1f".join(tokens[offset : offset + schema.SHINGLE_SIZE]).encode(
            "utf-8"
        )
        digest = hashlib.blake2b(payload, digest_size=schema.SHINGLE_HASH_BITS // 8)
        values.add(int.from_bytes(digest.digest(), "big"))
    if len(values) < schema.MIN_DISTINCT_SHINGLES:
        return None
    return frozenset(values)


def identifier_erased_shingles_from_tokens(
    tokens: list[str],
) -> frozenset[int] | None:
    if len(tokens) < schema.SHINGLE_SIZE:
        return None
    values = {
        int.from_bytes(
            hashlib.blake2b(
                "\0".join(tokens[offset : offset + schema.SHINGLE_SIZE]).encode(
                    "utf-8"
                ),
                digest_size=schema.SHINGLE_HASH_BITS // 8,
            ).digest(),
            "big",
        )
        for offset in range(len(tokens) - schema.SHINGLE_SIZE + 1)
    }
    if len(values) < schema.MIN_DISTINCT_SHINGLES:
        return None
    return frozenset(values)


def token_shingles(code: str) -> frozenset[int] | None:
    tokens = normalized_tokens(code)
    if tokens is None:
        return None
    return shingles_from_tokens(tokens)


def identifier_erased_token_shingles(code: str) -> frozenset[int] | None:
    tokens = identifier_erased_tokens(code)
    if tokens is None:
        return None
    return identifier_erased_shingles_from_tokens(tokens)


def threshold_passes(
    intersection: int, union: int, numerator: int, denominator: int
) -> bool:
    return denominator * intersection >= numerator * union


def prefix_length(size: int, numerator: int, denominator: int) -> int:
    required_overlap = math.ceil(numerator * size / denominator)
    return size - required_overlap + 1


def exact_threshold_join(
    records: list[FingerprintedRecord],
    numerator: int = schema.PRIMARY_JACCARD_NUMERATOR,
    denominator: int = schema.PRIMARY_JACCARD_DENOMINATOR,
) -> tuple[list[NearEdge], int]:
    """Exact set-Jaccard threshold join via globally ordered prefix filtering."""

    document_frequency: collections.Counter[int] = collections.Counter()
    for record in records:
        document_frequency.update(record.shingles)
    ordered = [
        sorted(record.shingles, key=lambda value: (document_frequency[value], value))
        for record in records
    ]
    inverted: dict[int, list[int]] = collections.defaultdict(list)
    candidates: set[int] = set()
    for index, values in enumerate(ordered):
        length = prefix_length(len(values), numerator, denominator)
        for value in values[:length]:
            for previous in inverted[value]:
                left, right = previous, index
                if len(records[left].shingles) > len(records[right].shingles):
                    shorter, longer = right, left
                else:
                    shorter, longer = left, right
                if denominator * len(records[shorter].shingles) < numerator * len(
                    records[longer].shingles
                ):
                    continue
                candidates.add((left << 32) | right)
            inverted[value].append(index)

    edges: list[NearEdge] = []
    for packed in sorted(candidates):
        left = packed >> 32
        right = packed & 0xFFFFFFFF
        left_values = records[left].shingles
        right_values = records[right].shingles
        intersection = len(left_values.intersection(right_values))
        union = len(left_values) + len(right_values) - intersection
        if threshold_passes(intersection, union, numerator, denominator):
            edges.append(NearEdge(left, right, intersection, union))
    return edges, len(candidates)


def brute_force_edges(
    records: list[FingerprintedRecord],
    numerator: int = schema.PRIMARY_JACCARD_NUMERATOR,
    denominator: int = schema.PRIMARY_JACCARD_DENOMINATOR,
) -> list[NearEdge]:
    edges: list[NearEdge] = []
    for right in range(len(records)):
        for left in range(right):
            left_values = records[left].shingles
            right_values = records[right].shingles
            intersection = len(left_values.intersection(right_values))
            union = len(left_values) + len(right_values) - intersection
            if threshold_passes(intersection, union, numerator, denominator):
                edges.append(NearEdge(left, right, intersection, union))
    return edges


def relation(
    left: FingerprintedRecord, right: FingerprintedRecord
) -> str:
    if left.run_id != right.run_id:
        if left.task == right.task:
            return "cross_run_same_task"
        return "cross_run_cross_task"
    if left.parent and left.parent == right.parent:
        return "same_parent_siblings"
    if left.parent == right.card_id or right.parent == left.card_id:
        return "parent_child"
    return "same_run_other"


def edge_digest(
    left: FingerprintedRecord, right: FingerprintedRecord, edge: NearEdge
) -> str:
    first, second = sorted((left.card_id, right.card_id))
    return sha256_text(
        f"{first}\x00{second}\x00{edge.intersection}\x00{edge.union}"
    )


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.component_size = [1] * size

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        if self.component_size[left_root] < self.component_size[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        self.component_size[left_root] += self.component_size[right_root]


def summarize_edges(
    records: list[FingerprintedRecord], edges: list[NearEdge]
) -> dict[str, Any]:
    relation_counts = {name: 0 for name in schema.RELATIONS}
    affected_by_relation = {name: set() for name in schema.RELATIONS}
    cross_run_edges: list[NearEdge] = []
    digests: list[str] = []
    union_find = UnionFind(len(records))

    for edge in edges:
        left, right = records[edge.left], records[edge.right]
        category = relation(left, right)
        relation_counts[category] += 1
        affected_by_relation[category].update((edge.left, edge.right))
        digests.append(edge_digest(left, right, edge))
        if category.startswith("cross_run_"):
            cross_run_edges.append(edge)
            union_find.union(edge.left, edge.right)

    cross_run_members = set()
    cross_task_members = set()
    component_members: dict[int, set[int]] = collections.defaultdict(set)
    for edge in cross_run_edges:
        cross_run_members.update((edge.left, edge.right))
        if records[edge.left].task != records[edge.right].task:
            cross_task_members.update((edge.left, edge.right))
    for member in cross_run_members:
        component_members[union_find.find(member)].add(member)
    component_rows = []
    for members in component_members.values():
        component_rows.append(
            (len(members), len({records[index].task for index in members}))
        )
    large_multitask = sum(
        endpoints >= schema.LARGE_COMPONENT_MIN_ENDPOINTS
        and tasks >= schema.LARGE_COMPONENT_MIN_TASKS
        for endpoints, tasks in component_rows
    )
    digest_payload = "\n".join(sorted(digests))
    if digest_payload:
        digest_payload += "\n"
    return {
        "near_duplicate_pairs": len(edges),
        "relation_pair_counts": relation_counts,
        "relation_affected_endpoint_counts": {
            name: len(affected_by_relation[name]) for name in schema.RELATIONS
        },
        "cross_run_pairs": len(cross_run_edges),
        "cross_run_affected_endpoints": len(cross_run_members),
        "cross_run_affected_endpoint_fraction": len(cross_run_members) / len(records)
        if records
        else None,
        "cross_task_affected_endpoints": len(cross_task_members),
        "cross_task_affected_endpoint_fraction": len(cross_task_members) / len(records)
        if records
        else None,
        "cross_run_components": len(component_rows),
        "largest_cross_run_component_endpoints": max(
            (row[0] for row in component_rows), default=0
        ),
        "largest_cross_run_component_tasks": max(
            (row[1] for row in component_rows), default=0
        ),
        "large_multitask_components": large_multitask,
        "edge_digest_sha256": sha256_text(digest_payload),
        "edge_identities_emitted": False,
    }


def load_cohort(
    state_root: Path, snapshot_root: Path, cohort_run_target: int
) -> tuple[list[CodeRecord], dict[str, Any]]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    if snapshot_root.parent != state_root / "snapshots":
        raise FuzzyCloneAuditError("snapshot is outside state root")
    if len(snapshot_root.name) != 64 or any(
        character not in "0123456789abcdef" for character in snapshot_root.name
    ):
        raise FuzzyCloneAuditError("snapshot basename is not a lowercase SHA-256")

    registry_path = snapshot_root / "intake_registry.jsonl"
    accumulator_dir = snapshot_root / "accumulator"
    runs_path = accumulator_dir / "provisional_runs.jsonl"
    summary_path = accumulator_dir / "summary.json"
    registry = list(read_jsonl(registry_path))
    cards: dict[str, CodeRecord] = {}
    card_order_identity: dict[str, tuple[str, str]] = {}
    drop_for_run: dict[str, str] = {}
    intake_summary_shas: dict[str, str] = {}
    seen_drops: set[str] = set()

    for entry in registry:
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise FuzzyCloneAuditError("registry schema mismatch")
        drop_id = entry["drop_id"]
        if not isinstance(drop_id, str) or drop_id in seen_drops:
            raise FuzzyCloneAuditError("duplicate or invalid drop ID")
        seen_drops.add(drop_id)
        intake_dir = Path(entry["intake_dir"]).resolve()
        if intake_dir.parent != state_root / "intakes" or intake_dir.name != drop_id:
            raise FuzzyCloneAuditError("intake path binding mismatch")
        intake_summary = intake_dir / "summary.json"
        require_sha(intake_summary, entry["summary_sha256"])
        summary = read_json(intake_summary)
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if not all(isinstance(value, dict) for value in (outputs, security, blindness)):
            raise FuzzyCloneAuditError("intake metadata missing")
        assert isinstance(outputs, dict)
        assert isinstance(security, dict)
        assert isinstance(blindness, dict)
        if (
            security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or security.get("journal_scanned_before_json") is not True
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
        ):
            raise FuzzyCloneAuditError("intake blindness gate mismatch")
        intake_summary_shas[drop_id] = entry["summary_sha256"]
        manifest = intake_dir / "eligible_blind_manifest.jsonl"
        require_sha(manifest, outputs.get("eligible_blind_manifest_sha256"))
        for row in read_jsonl(manifest):
            if set(row) != schema.BLIND_KEYS or not isinstance(row.get("lineage"), dict):
                raise FuzzyCloneAuditError("blind manifest schema mismatch")
            if set(row["lineage"]) != schema.LINEAGE_KEYS:
                raise FuzzyCloneAuditError("blind lineage schema mismatch")
            values = (
                row["card_id"],
                row["run_id"],
                row["task"],
                row["code"],
                row["lineage"]["parent"],
                row["generation_started_at_utc"],
                row["source_sha256"],
            )
            if not all(isinstance(value, str) for value in values):
                raise FuzzyCloneAuditError("blind manifest identity type mismatch")
            card_id, run_id, task, code, parent, generation_started, source_sha = values
            if len(source_sha) != 64 or any(
                character not in "0123456789abcdef" for character in source_sha
            ):
                raise FuzzyCloneAuditError("blind manifest source SHA mismatch")
            if card_id in cards or sha256_text(code) != row["code_sha256"]:
                raise FuzzyCloneAuditError("duplicate card or code SHA mismatch")
            owner = drop_for_run.setdefault(run_id, drop_id)
            if owner != drop_id:
                raise FuzzyCloneAuditError("run appears in multiple drops")
            cards[card_id] = CodeRecord(card_id, run_id, task, parent, code)
            card_order_identity[card_id] = (generation_started, source_sha)

    runs = list(read_jsonl(runs_path))
    run_rows: dict[str, dict[str, Any]] = {}
    for row in runs:
        if set(row) != schema.RUN_KEYS:
            raise FuzzyCloneAuditError("provisional run schema mismatch")
        run_id = row["run_id"]
        if not isinstance(run_id, str) or run_id in run_rows:
            raise FuzzyCloneAuditError("duplicate or invalid run ID")
        if (
            not isinstance(row["task"], str)
            or not isinstance(row["generation_started_at_utc"], str)
            or not isinstance(row["source_sha256"], str)
            or not isinstance(row["endpoints"], int)
            or row["flow_status"] != "scoreable"
            or row["drop_id"] != drop_for_run.get(run_id)
        ):
            raise FuzzyCloneAuditError("run flow or drop binding mismatch")
        run_rows[run_id] = row
    if {record.run_id for record in cards.values()} != set(run_rows):
        raise FuzzyCloneAuditError("card and run support differ")
    endpoint_counts = collections.Counter(record.run_id for record in cards.values())
    if any(row["endpoints"] != endpoint_counts[run_id] for run_id, row in run_rows.items()):
        raise FuzzyCloneAuditError("run endpoint accounting mismatch")
    for card_id, record in cards.items():
        run_row = run_rows[record.run_id]
        if (
            record.task != run_row["task"]
            or card_order_identity[card_id]
            != (run_row["generation_started_at_utc"], run_row["source_sha256"])
        ):
            raise FuzzyCloneAuditError("card and run ordering identity differ")

    ordered_runs = sorted(
        runs,
        key=lambda row: (
            str(row["generation_started_at_utc"]),
            str(row["source_sha256"]),
            str(row["run_id"]),
        ),
    )
    cohort_rows = ordered_runs[:cohort_run_target]
    cohort_ids = {str(row["run_id"]) for row in cohort_rows}
    cohort = [
        record
        for _, record in sorted(cards.items())
        if record.run_id in cohort_ids
    ]

    accumulator = read_json(summary_path)
    inventory = accumulator.get("inventory")
    security = accumulator.get("security")
    closure = accumulator.get("closure")
    if not all(isinstance(value, dict) for value in (inventory, security, closure)):
        raise FuzzyCloneAuditError("accumulator metadata missing")
    assert isinstance(inventory, dict)
    assert isinstance(security, dict)
    assert isinstance(closure, dict)
    if (
        security.get("label_vault_opened") is not False
        or security.get("outcome_files_opened") != []
        or security.get("scorer_prediction_files_opened") != []
        or closure.get("provided") is not False
    ):
        raise FuzzyCloneAuditError("accumulator blindness gate mismatch")
    cross_checks = {
        "transactions": inventory.get("drops") == len(registry),
        "all_eligible_runs": inventory.get("eligible_runs") == len(runs),
        "all_eligible_endpoints": inventory.get("eligible_endpoints") == len(cards),
        "provisional_first960_runs": inventory.get("provisional_first960_runs")
        == len(cohort_rows),
        "provisional_first960_endpoints": inventory.get("provisional_first960_endpoints")
        == len(cohort),
    }
    if not all(cross_checks.values()):
        raise FuzzyCloneAuditError("audit differs from accumulator inventory")
    inputs = {
        "intake_registry_sha256": sha256_file(registry_path),
        "provisional_runs_sha256": sha256_file(runs_path),
        "accumulator_summary_sha256": sha256_file(summary_path),
        "intake_summary_sha256": dict(sorted(intake_summary_shas.items())),
        "cross_checks_against_accumulator": cross_checks,
    }
    return cohort, inputs


def audit(
    state_root: Path,
    snapshot_root: Path,
    cohort_run_target: int,
    source_commit: str,
    representation: str = schema.LEXICAL_REPRESENTATION,
) -> dict[str, Any]:
    if representation not in {
        schema.LEXICAL_REPRESENTATION,
        schema.IDENTIFIER_ERASED_REPRESENTATION,
    }:
        raise FuzzyCloneAuditError("unsupported fingerprint representation")
    identifier_erased = representation == schema.IDENTIFIER_ERASED_REPRESENTATION
    token_function = identifier_erased_tokens if identifier_erased else normalized_tokens
    shingle_function = (
        identifier_erased_shingles_from_tokens
        if identifier_erased
        else shingles_from_tokens
    )
    cohort, inputs = load_cohort(state_root, snapshot_root, cohort_run_target)
    fingerprinted: list[FingerprintedRecord] = []
    failed_tokenization = 0
    too_short = 0
    for record in cohort:
        tokens = token_function(record.code)
        if tokens is None:
            failed_tokenization += 1
            continue
        if len(tokens) < schema.SHINGLE_SIZE:
            too_short += 1
            continue
        shingles = shingle_function(tokens)
        if shingles is None:
            too_short += 1
            continue
        fingerprinted.append(
            FingerprintedRecord(
                record.card_id,
                record.run_id,
                record.task,
                record.parent,
                shingles,
            )
        )

    primary_edges, candidates = exact_threshold_join(fingerprinted)
    strict_edges = [
        edge
        for edge in primary_edges
        if threshold_passes(
            edge.intersection,
            edge.union,
            schema.STRICT_JACCARD_NUMERATOR,
            schema.STRICT_JACCARD_DENOMINATOR,
        )
    ]
    primary_summary = summarize_edges(fingerprinted, primary_edges)
    strict_summary = summarize_edges(fingerprinted, strict_edges)

    subset = sorted(
        fingerprinted, key=lambda record: sha256_text(record.card_id)
    )[: schema.SELF_CHECK_DOCUMENTS]
    subset_join, _ = exact_threshold_join(subset)
    subset_brute = brute_force_edges(subset)
    subset_join_digest = sha256_text(
        "\n".join(sorted(
            f"{edge.left}:{edge.right}:{edge.intersection}:{edge.union}"
            for edge in subset_join
        ))
    )
    subset_brute_digest = sha256_text(
        "\n".join(sorted(
            f"{edge.left}:{edge.right}:{edge.intersection}:{edge.union}"
            for edge in subset_brute
        ))
    )
    self_check_passed = subset_join_digest == subset_brute_digest
    coverage = len(fingerprinted) / len(cohort) if cohort else None
    gates = {
        "fingerprint_coverage": coverage is not None
        and coverage >= schema.MIN_FINGERPRINT_COVERAGE,
        "cross_run_affected_endpoint_fraction": primary_summary[
            "cross_run_affected_endpoint_fraction"
        ]
        is not None
        and primary_summary["cross_run_affected_endpoint_fraction"]
        <= schema.MAX_CROSS_RUN_AFFECTED_ENDPOINT_FRACTION,
        "cross_task_affected_endpoint_fraction": primary_summary[
            "cross_task_affected_endpoint_fraction"
        ]
        is not None
        and primary_summary["cross_task_affected_endpoint_fraction"]
        <= schema.MAX_CROSS_TASK_AFFECTED_ENDPOINT_FRACTION,
        "large_multitask_components": primary_summary["large_multitask_components"]
        <= schema.MAX_LARGE_MULTITASK_COMPONENTS,
        "exact_join_self_check": self_check_passed,
    }
    strict_lineage_local = all(gates.values()) and primary_summary["cross_run_pairs"] == 0
    protocol = (
        schema.IDENTIFIER_ERASED_PROTOCOL if identifier_erased else schema.PROTOCOL
    )
    status = (
        "PROVISIONAL_IDENTIFIER_ERASED_FUZZY_CODE_CLONE_AUDIT_COMPLETE"
        if identifier_erased
        else "PROVISIONAL_FUZZY_CODE_CLONE_AUDIT_COMPLETE"
    )
    fingerprint_method = (
        "python_identifier_erased_token_5gram_set_blake2b128"
        if identifier_erased
        else "normalized_token_5gram_set_blake2b128"
    )

    return {
        "status": status,
        "protocol": protocol,
        "source_commit": source_commit,
        "source_sha256": sha256_file(Path(__file__)),
        "schema_sha256": sha256_file(Path(schema.__file__).resolve()),
        "snapshot_sha256": snapshot_root.resolve().name,
        "scope": {
            "name": "provisional_first960_prefix",
            "target_runs": cohort_run_target,
            "observed_runs": len({record.run_id for record in cohort}),
            "observed_endpoints": len(cohort),
            "confirmatory_outcomes_opened": False,
            "closure_provided": False,
        },
        "inputs": inputs,
        "fingerprinting": {
            "representation": representation,
            "method": fingerprint_method,
            "non_keyword_names_replaced": (
                schema.IDENTIFIER_TOKEN if identifier_erased else None
            ),
            "shingle_size": schema.SHINGLE_SIZE,
            "shingle_hash_bits": schema.SHINGLE_HASH_BITS,
            "minimum_distinct_shingles": schema.MIN_DISTINCT_SHINGLES,
            "input_endpoints": len(cohort),
            "fingerprinted_endpoints": len(fingerprinted),
            "tokenization_failures": failed_tokenization,
            "too_short_or_low_distinct_shingles": too_short,
            "coverage": coverage,
        },
        "primary_jaccard_0_85": {
            "threshold_numerator": schema.PRIMARY_JACCARD_NUMERATOR,
            "threshold_denominator": schema.PRIMARY_JACCARD_DENOMINATOR,
            "candidate_pairs_exactly_checked": candidates,
            **primary_summary,
        },
        "strict_jaccard_0_95": {
            "threshold_numerator": schema.STRICT_JACCARD_NUMERATOR,
            "threshold_denominator": schema.STRICT_JACCARD_DENOMINATOR,
            **strict_summary,
        },
        "exact_join_self_check": {
            "selection": "lowest_sha256_card_identity",
            "documents": len(subset),
            "brute_force_pairs": len(subset) * (len(subset) - 1) // 2,
            "join_edge_digest": subset_join_digest,
            "brute_force_edge_digest": subset_brute_digest,
            "passed": self_check_passed,
        },
        "pre_registered_gate": {
            "thresholds": {
                "minimum_fingerprint_coverage": schema.MIN_FINGERPRINT_COVERAGE,
                "maximum_cross_run_affected_endpoint_fraction": schema.MAX_CROSS_RUN_AFFECTED_ENDPOINT_FRACTION,
                "maximum_cross_task_affected_endpoint_fraction": schema.MAX_CROSS_TASK_AFFECTED_ENDPOINT_FRACTION,
                "maximum_large_multitask_components": schema.MAX_LARGE_MULTITASK_COMPONENTS,
                "large_component_minimum_endpoints": schema.LARGE_COMPONENT_MIN_ENDPOINTS,
                "large_component_minimum_tasks": schema.LARGE_COMPONENT_MIN_TASKS,
            },
            "checks": gates,
            "strong_low_fuzzy_clone_support": all(gates.values()),
            "strict_lineage_local_support": strict_lineage_local,
            "strict_lineage_local_requires_zero_cross_run_pairs": True,
            "semantic_equivalence_absence_proven": False,
            "training_data_contamination_absence_proven": False,
        },
        "interpretation_contract": {
            "near_duplicate_algorithm_novelty_claimed": False,
            "exact_means_threshold_join_over_hashed_token_shingle_sets": True,
            "identifier_and_literal_erasure_used": identifier_erased,
            "aggressive_abstraction_false_positive_risk": identifier_erased,
            "semantic_clone_absence_claimed": False,
            "provisional_prefix_requires_closure_rerun": True,
            "predictor_accuracy_or_effect_computed": False,
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "python_executable": str(Path(sys.executable).resolve()),
            "randomness_used": False,
        },
        "security": {
            "allowed_basenames_read": [
                "eligible_blind_manifest.jsonl",
                "intake_registry.jsonl",
                "provisional_runs.jsonl",
                "summary.json",
            ],
            "code_values_emitted": False,
            "task_card_or_run_values_emitted": False,
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
            "gpu_calls": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
        },
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--cohort-run-target", required=True, type=int)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--representation",
        choices=(
            schema.LEXICAL_REPRESENTATION,
            schema.IDENTIFIER_ERASED_REPRESENTATION,
        ),
        default=schema.LEXICAL_REPRESENTATION,
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.cohort_run_target != schema.FROZEN_COHORT_RUN_TARGET:
        raise FuzzyCloneAuditError("cohort target differs from frozen protocol")
    if len(args.source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in args.source_commit
    ):
        raise FuzzyCloneAuditError("source commit is not a lowercase full Git SHA")
    repo_root = Path(__file__).resolve().parent.parent
    actual_commit = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    source_relative = Path(__file__).resolve().relative_to(repo_root).as_posix()
    committed_blob = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", f"{actual_commit}:{source_relative}"],
        text=True,
    ).strip()
    worktree_blob = subprocess.check_output(
        ["git", "-C", str(repo_root), "hash-object", str(Path(__file__).resolve())],
        text=True,
    ).strip()
    if actual_commit != args.source_commit or committed_blob != worktree_blob:
        raise FuzzyCloneAuditError("source commit or Git blob binding failed")
    receipt = audit(
        args.state_root,
        args.snapshot_root,
        args.cohort_run_target,
        args.source_commit,
        args.representation,
    )
    atomic_json(args.output, receipt)
    print(
        receipt["status"],
        f"runs={receipt['scope']['observed_runs']}",
        f"endpoints={receipt['scope']['observed_endpoints']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
