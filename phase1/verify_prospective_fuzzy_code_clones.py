"""Independent non-importing verifier for the prospective fuzzy-clone audit."""

from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import keyword
import math
import os
import subprocess
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from phase1 import prospective_fuzzy_clone_schema as schema


class VerificationError(RuntimeError):
    """Raised when independent reproduction differs from the producer receipt."""


@dataclass(frozen=True)
class Record:
    card_id: str
    run_id: str
    task: str
    parent: str
    shingles: frozenset[int]


@dataclass(frozen=True)
class Edge:
    left: int
    right: int
    intersection: int
    union: int


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


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
                raise VerificationError(
                    f"invalid JSONL: {path.name}:{line_number}"
                ) from error
            require(isinstance(value, dict), f"non-object: {path.name}:{line_number}")
            yield value


def shingles(code: str) -> frozenset[int] | None:
    ignored = {
        tokenize.ENCODING,
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
    }
    tokens: list[str] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type in ignored:
                continue
            value = token.string
            if token.type == tokenize.NUMBER:
                value = "<NUMBER>"
            elif token.type == tokenize.STRING:
                value = "<STRING>"
            tokens.append(f"{token.type}:{value}")
    except (IndentationError, SyntaxError, tokenize.TokenError):
        return None
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


def identifier_erased_shingles(code: str) -> frozenset[int] | None:
    ignored = {
        tokenize.ENCODING,
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
    }
    tokens: list[str] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type in ignored:
                continue
            if token.type == tokenize.NAME:
                tokens.append(
                    token.string
                    if keyword.iskeyword(token.string)
                    else schema.IDENTIFIER_TOKEN
                )
            elif token.type == tokenize.NUMBER:
                tokens.append(schema.NUMBER_TOKEN)
            elif token.type == tokenize.STRING:
                tokens.append(schema.STRING_TOKEN)
            elif token.type == tokenize.OP:
                tokens.append(token.string)
            elif token.type == tokenize.ERRORTOKEN and token.string.isspace():
                continue
            else:
                tokens.append(f"{tokenize.tok_name[token.type]}:{token.string}")
    except (IndentationError, SyntaxError, tokenize.TokenError):
        return None
    if len(tokens) < schema.SHINGLE_SIZE:
        return None
    values: set[int] = set()
    for offset in range(len(tokens) - schema.SHINGLE_SIZE + 1):
        payload = "\0".join(tokens[offset : offset + schema.SHINGLE_SIZE]).encode(
            "utf-8"
        )
        digest = hashlib.blake2b(
            payload, digest_size=schema.SHINGLE_HASH_BITS // 8
        )
        values.add(int.from_bytes(digest.digest(), "big"))
    if len(values) < schema.MIN_DISTINCT_SHINGLES:
        return None
    return frozenset(values)


def passes(intersection: int, union: int, numerator: int, denominator: int) -> bool:
    return denominator * intersection >= numerator * union


def independent_join(records: list[Record]) -> tuple[list[Edge], int]:
    frequencies: collections.Counter[int] = collections.Counter()
    for row in records:
        frequencies.update(row.shingles)
    prefixes: list[list[int]] = []
    for row in records:
        ordered = sorted(row.shingles, key=lambda value: (frequencies[value], value))
        required = math.ceil(
            schema.PRIMARY_JACCARD_NUMERATOR
            * len(ordered)
            / schema.PRIMARY_JACCARD_DENOMINATOR
        )
        prefixes.append(ordered[: len(ordered) - required + 1])

    postings: dict[int, list[int]] = collections.defaultdict(list)
    for index, values in enumerate(prefixes):
        for value in values:
            postings[value].append(index)
    candidate_pairs: set[tuple[int, int]] = set()
    for posting in postings.values():
        for right_offset in range(1, len(posting)):
            right = posting[right_offset]
            for left in posting[:right_offset]:
                shorter = min(len(records[left].shingles), len(records[right].shingles))
                longer = max(len(records[left].shingles), len(records[right].shingles))
                if (
                    schema.PRIMARY_JACCARD_DENOMINATOR * shorter
                    >= schema.PRIMARY_JACCARD_NUMERATOR * longer
                ):
                    candidate_pairs.add((left, right))

    edges = []
    for left, right in sorted(candidate_pairs):
        intersection = len(records[left].shingles & records[right].shingles)
        union = len(records[left].shingles) + len(records[right].shingles) - intersection
        if passes(
            intersection,
            union,
            schema.PRIMARY_JACCARD_NUMERATOR,
            schema.PRIMARY_JACCARD_DENOMINATOR,
        ):
            edges.append(Edge(left, right, intersection, union))
    return edges, len(candidate_pairs)


def brute_force(records: list[Record]) -> list[Edge]:
    edges = []
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            intersection = len(records[left].shingles & records[right].shingles)
            union = len(records[left].shingles) + len(records[right].shingles) - intersection
            if passes(
                intersection,
                union,
                schema.PRIMARY_JACCARD_NUMERATOR,
                schema.PRIMARY_JACCARD_DENOMINATOR,
            ):
                edges.append(Edge(left, right, intersection, union))
    return edges


def edge_signature(edges: list[Edge]) -> str:
    rows = sorted(
        f"{edge.left}:{edge.right}:{edge.intersection}:{edge.union}"
        for edge in edges
    )
    return sha256_text("\n".join(rows))


def category(left: Record, right: Record) -> str:
    if left.run_id != right.run_id:
        return "cross_run_same_task" if left.task == right.task else "cross_run_cross_task"
    if left.parent and left.parent == right.parent:
        return "same_parent_siblings"
    if left.parent == right.card_id or right.parent == left.card_id:
        return "parent_child"
    return "same_run_other"


def private_edge_digest(left: Record, right: Record, edge: Edge) -> str:
    first, second = sorted((left.card_id, right.card_id))
    return sha256_text(
        f"{first}\x00{second}\x00{edge.intersection}\x00{edge.union}"
    )


def aggregate(records: list[Record], edges: list[Edge]) -> dict[str, Any]:
    counts = {name: 0 for name in schema.RELATIONS}
    affected = {name: set() for name in schema.RELATIONS}
    parents = list(range(len(records)))
    sizes = [1] * len(records)

    def find(value: int) -> int:
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left == right:
            return
        if sizes[left] < sizes[right]:
            left, right = right, left
        parents[right] = left
        sizes[left] += sizes[right]

    cross_run_members: set[int] = set()
    cross_task_members: set[int] = set()
    digest_rows = []
    cross_run_pairs = 0
    for edge in edges:
        left, right = records[edge.left], records[edge.right]
        relation = category(left, right)
        counts[relation] += 1
        affected[relation].update((edge.left, edge.right))
        digest_rows.append(private_edge_digest(left, right, edge))
        if relation.startswith("cross_run_"):
            cross_run_pairs += 1
            cross_run_members.update((edge.left, edge.right))
            union(edge.left, edge.right)
            if left.task != right.task:
                cross_task_members.update((edge.left, edge.right))

    components: dict[int, set[int]] = collections.defaultdict(set)
    for member in cross_run_members:
        components[find(member)].add(member)
    component_rows = [
        (len(members), len({records[index].task for index in members}))
        for members in components.values()
    ]
    large = sum(
        endpoints >= schema.LARGE_COMPONENT_MIN_ENDPOINTS
        and tasks >= schema.LARGE_COMPONENT_MIN_TASKS
        for endpoints, tasks in component_rows
    )
    payload = "\n".join(sorted(digest_rows))
    if payload:
        payload += "\n"
    return {
        "near_duplicate_pairs": len(edges),
        "relation_pair_counts": counts,
        "relation_affected_endpoint_counts": {
            name: len(affected[name]) for name in schema.RELATIONS
        },
        "cross_run_pairs": cross_run_pairs,
        "cross_run_affected_endpoints": len(cross_run_members),
        "cross_run_affected_endpoint_fraction": len(cross_run_members) / len(records),
        "cross_task_affected_endpoints": len(cross_task_members),
        "cross_task_affected_endpoint_fraction": len(cross_task_members) / len(records),
        "cross_run_components": len(component_rows),
        "largest_cross_run_component_endpoints": max(
            (row[0] for row in component_rows), default=0
        ),
        "largest_cross_run_component_tasks": max(
            (row[1] for row in component_rows), default=0
        ),
        "large_multitask_components": large,
        "edge_digest_sha256": sha256_text(payload),
        "edge_identities_emitted": False,
    }


def reproduce(
    state_root: Path, snapshot_root: Path, producer: dict[str, Any]
) -> dict[str, Any]:
    protocol = producer.get("protocol")
    require(
        protocol in {schema.PROTOCOL, schema.IDENTIFIER_ERASED_PROTOCOL},
        "protocol mismatch",
    )
    identifier_erased = protocol == schema.IDENTIFIER_ERASED_PROTOCOL
    expected_representation = (
        schema.IDENTIFIER_ERASED_REPRESENTATION
        if identifier_erased
        else schema.LEXICAL_REPRESENTATION
    )
    require(
        producer.get("fingerprinting", {}).get("representation")
        == expected_representation,
        "representation mismatch",
    )
    fingerprint_function = identifier_erased_shingles if identifier_erased else shingles
    require(snapshot_root.resolve().name == producer.get("snapshot_sha256"), "snapshot mismatch")
    require(snapshot_root.resolve().parent == state_root.resolve() / "snapshots", "path mismatch")
    inputs = producer["inputs"]
    registry_path = snapshot_root / "intake_registry.jsonl"
    runs_path = snapshot_root / "accumulator" / "provisional_runs.jsonl"
    summary_path = snapshot_root / "accumulator" / "summary.json"
    require(sha256_file(registry_path) == inputs["intake_registry_sha256"], "registry SHA")
    require(sha256_file(runs_path) == inputs["provisional_runs_sha256"], "runs SHA")
    require(sha256_file(summary_path) == inputs["accumulator_summary_sha256"], "summary SHA")

    runs = list(read_jsonl(runs_path))
    require(all(set(row) == schema.RUN_KEYS for row in runs), "run schema")
    run_rows: dict[str, dict[str, Any]] = {}
    for row in runs:
        require(row["run_id"] not in run_rows, "duplicate run")
        require(row["flow_status"] == "scoreable", "run flow status")
        run_rows[row["run_id"]] = row
    ordered = sorted(
        runs,
        key=lambda row: (
            str(row["generation_started_at_utc"]),
            str(row["source_sha256"]),
            str(row["run_id"]),
        ),
    )
    target = producer["scope"]["target_runs"]
    require(target == schema.FROZEN_COHORT_RUN_TARGET, "target mismatch")
    cohort_ids = {str(row["run_id"]) for row in ordered[:target]}

    registry = list(read_jsonl(registry_path))
    records = []
    token_failures = 0
    low_shingle = 0
    all_endpoints = 0
    seen_cards: set[str] = set()
    endpoint_counts: collections.Counter[str] = collections.Counter()
    drop_for_run: dict[str, str] = {}
    for entry in registry:
        require(set(entry) == {"drop_id", "intake_dir", "summary_sha256"}, "registry schema")
        intake = Path(entry["intake_dir"]).resolve()
        require(intake.parent == state_root.resolve() / "intakes", "intake path")
        summary = intake / "summary.json"
        require(sha256_file(summary) == entry["summary_sha256"], "intake summary SHA")
        require(
            inputs["intake_summary_sha256"][entry["drop_id"]]
            == entry["summary_sha256"],
            "bound intake summary SHA",
        )
        intake_payload = read_json(summary)
        outputs = intake_payload["outputs"]
        security = intake_payload["security"]
        blindness = intake_payload["blindness"]
        require(security["env_members_read"] is False, "env members read")
        require(security["live_event_journal_members_read"] is False, "journal read")
        require(security["journal_scanned_before_json"] is True, "journal not scanned")
        require(blindness["labels_used_for_run_selection"] is False, "label run selection")
        require(blindness["labels_used_for_endpoint_selection"] is False, "label endpoint selection")
        manifest = intake / "eligible_blind_manifest.jsonl"
        require(sha256_file(manifest) == outputs["eligible_blind_manifest_sha256"], "manifest SHA")
        for row in read_jsonl(manifest):
            all_endpoints += 1
            require(set(row) == schema.BLIND_KEYS, "blind schema")
            require(set(row["lineage"]) == schema.LINEAGE_KEYS, "lineage schema")
            require(sha256_text(row["code"]) == row["code_sha256"], "code SHA")
            require(row["card_id"] not in seen_cards, "duplicate card")
            seen_cards.add(row["card_id"])
            require(row["run_id"] in run_rows, "unknown run")
            run_row = run_rows[row["run_id"]]
            require(run_row["drop_id"] == entry["drop_id"], "run drop binding")
            require(run_row["task"] == row["task"], "run task binding")
            require(
                run_row["generation_started_at_utc"]
                == row["generation_started_at_utc"],
                "run timestamp binding",
            )
            require(run_row["source_sha256"] == row["source_sha256"], "run source binding")
            previous_drop = drop_for_run.setdefault(row["run_id"], entry["drop_id"])
            require(previous_drop == entry["drop_id"], "run crosses drops")
            endpoint_counts[row["run_id"]] += 1
            if row["run_id"] not in cohort_ids:
                continue
            values = fingerprint_function(row["code"])
            if values is None:
                # Distinguish lexical failures from short/low-diversity cases without
                # importing or calling the producer implementation.
                try:
                    list(tokenize.generate_tokens(io.StringIO(row["code"]).readline))
                except (IndentationError, SyntaxError, tokenize.TokenError):
                    token_failures += 1
                else:
                    low_shingle += 1
                continue
            records.append(
                Record(
                    row["card_id"],
                    row["run_id"],
                    row["task"],
                    row["lineage"]["parent"],
                    values,
                )
            )

    accumulator = read_json(summary_path)
    require(accumulator["security"]["label_vault_opened"] is False, "label vault")
    require(accumulator["security"]["outcome_files_opened"] == [], "outcomes")
    require(accumulator["security"]["scorer_prediction_files_opened"] == [], "predictions")
    require(accumulator["closure"]["provided"] is False, "unexpected closure")
    require(all_endpoints == accumulator["inventory"]["eligible_endpoints"], "endpoint count")
    require(set(endpoint_counts) == set(run_rows), "run support")
    require(
        all(endpoint_counts[run_id] == row["endpoints"] for run_id, row in run_rows.items()),
        "run endpoint accounting",
    )

    edges, candidates = independent_join(records)
    strict = [
        edge
        for edge in edges
        if passes(
            edge.intersection,
            edge.union,
            schema.STRICT_JACCARD_NUMERATOR,
            schema.STRICT_JACCARD_DENOMINATOR,
        )
    ]
    primary = aggregate(records, edges)
    strict_summary = aggregate(records, strict)
    expected_fingerprint = producer["fingerprinting"]
    require(len(records) == expected_fingerprint["fingerprinted_endpoints"], "fingerprinted count")
    require(token_failures == expected_fingerprint["tokenization_failures"], "token failures")
    require(low_shingle == expected_fingerprint["too_short_or_low_distinct_shingles"], "low shingles")
    require(candidates == producer["primary_jaccard_0_85"]["candidate_pairs_exactly_checked"], "candidate count")
    for key, value in primary.items():
        require(value == producer["primary_jaccard_0_85"][key], f"primary mismatch: {key}")
    for key, value in strict_summary.items():
        require(value == producer["strict_jaccard_0_95"][key], f"strict mismatch: {key}")

    subset = sorted(records, key=lambda row: sha256_text(row.card_id))[
        : schema.SELF_CHECK_DOCUMENTS
    ]
    subset_join, _ = independent_join(subset)
    subset_brute = brute_force(subset)
    require(edge_signature(subset_join) == edge_signature(subset_brute), "subset brute-force mismatch")
    coverage = len(records) / producer["scope"]["observed_endpoints"]
    gates = {
        "fingerprint_coverage": coverage >= schema.MIN_FINGERPRINT_COVERAGE,
        "cross_run_affected_endpoint_fraction": primary[
            "cross_run_affected_endpoint_fraction"
        ]
        <= schema.MAX_CROSS_RUN_AFFECTED_ENDPOINT_FRACTION,
        "cross_task_affected_endpoint_fraction": primary[
            "cross_task_affected_endpoint_fraction"
        ]
        <= schema.MAX_CROSS_TASK_AFFECTED_ENDPOINT_FRACTION,
        "large_multitask_components": primary["large_multitask_components"]
        <= schema.MAX_LARGE_MULTITASK_COMPONENTS,
        "exact_join_self_check": True,
    }
    gate_payload = producer["pre_registered_gate"]
    require(gate_payload["checks"] == gates, "gate mismatch")
    require(
        gate_payload["strong_low_fuzzy_clone_support"] is all(gates.values()),
        "low-overlap gate mismatch",
    )
    require(
        gate_payload["strict_lineage_local_support"]
        is (all(gates.values()) and primary["cross_run_pairs"] == 0),
        "strict lineage-local gate mismatch",
    )
    independent_protocol = (
        schema.IDENTIFIER_ERASED_INDEPENDENT_PROTOCOL
        if identifier_erased
        else schema.INDEPENDENT_PROTOCOL
    )
    status = (
        "INDEPENDENTLY_VERIFIED_PROVISIONAL_IDENTIFIER_ERASED_FUZZY_CODE_CLONE_AUDIT"
        if identifier_erased
        else "INDEPENDENTLY_VERIFIED_PROVISIONAL_FUZZY_CODE_CLONE_AUDIT"
    )
    return {
        "protocol": independent_protocol,
        "status": status,
        "representation": expected_representation,
        "producer_receipt_sha256": sha256_file(Path(producer["_receipt_path"])),
        "snapshot_sha256": producer["snapshot_sha256"],
        "observed_runs": producer["scope"]["observed_runs"],
        "observed_endpoints": producer["scope"]["observed_endpoints"],
        "fingerprinted_endpoints": len(records),
        "primary_candidate_pairs": candidates,
        "primary_near_duplicate_pairs": len(edges),
        "primary_edge_digest_sha256": primary["edge_digest_sha256"],
        "strict_near_duplicate_pairs": len(strict),
        "strict_edge_digest_sha256": strict_summary["edge_digest_sha256"],
        "subset_bruteforce_matches": True,
        "producer_aggregate_matches": True,
        "imports_producer_code": False,
        "semantic_equivalence_certified": False,
        "prospective_outcomes_read": False,
        "prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise VerificationError(f"output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    producer = read_json(args.receipt)
    producer["_receipt_path"] = str(args.receipt.resolve())
    repo_root = Path(__file__).resolve().parent.parent
    head = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    require(head == producer["source_commit"], "verifier HEAD differs from source commit")
    producer_path = repo_root / "phase1" / "audit_prospective_fuzzy_code_clones.py"
    require(sha256_file(producer_path) == producer["source_sha256"], "producer source SHA")
    require(
        sha256_file(Path(schema.__file__).resolve()) == producer["schema_sha256"],
        "schema source SHA",
    )
    result = reproduce(args.state_root, args.snapshot_root, producer)
    atomic_json(args.output, result)
    print(result["status"])


if __name__ == "__main__":
    main()
