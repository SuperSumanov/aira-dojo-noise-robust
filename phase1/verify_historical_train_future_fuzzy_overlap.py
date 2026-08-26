"""Independent verifier for historical-train to prospective lexical overlap."""

from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import math
import os
import subprocess
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from phase1 import historical_train_future_overlap_schema as schema
from phase1 import prospective_fuzzy_clone_schema as prospective_schema
from phase1 import verify_prospective_fuzzy_code_clones as token_impl


class VerificationError(RuntimeError):
    """Raised when an input or independently recomputed value differs."""


@dataclass(frozen=True)
class CodeRecord:
    card_id: str
    run_id: str
    task: str
    code: str


@dataclass(frozen=True)
class Record:
    card_id: str
    run_id: str
    task: str
    shingles: frozenset[int]


@dataclass(frozen=True)
class Edge:
    historical: int
    prospective: int
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


def normalized_lf_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


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


def require_dependency_contract() -> None:
    observed = (
        prospective_schema.SHINGLE_SIZE,
        prospective_schema.SHINGLE_HASH_BITS,
        prospective_schema.MIN_DISTINCT_SHINGLES,
        prospective_schema.PRIMARY_JACCARD_NUMERATOR,
        prospective_schema.PRIMARY_JACCARD_DENOMINATOR,
        prospective_schema.STRICT_JACCARD_NUMERATOR,
        prospective_schema.STRICT_JACCARD_DENOMINATOR,
    )
    expected = (
        schema.SHINGLE_SIZE,
        schema.SHINGLE_HASH_BITS,
        schema.MIN_DISTINCT_SHINGLES,
        schema.PRIMARY_NUMERATOR,
        schema.PRIMARY_DENOMINATOR,
        schema.STRICT_NUMERATOR,
        schema.STRICT_DENOMINATOR,
    )
    require(observed == expected, "token implementation contract drift")


def load_historical(repo_root: Path) -> tuple[list[CodeRecord], dict[str, Any]]:
    identities: dict[str, tuple[str, str]] = {}
    runs: set[str] = set()
    tasks: set[str] = set()
    parents: set[str] = set()
    pair_hashes: dict[str, str] = {}
    pair_rows: dict[str, int] = {}
    total_rows = 0
    for relative, expected_sha, expected_rows in schema.HISTORICAL_PAIR_FILES:
        path = repo_root / relative
        actual_sha = normalized_lf_sha256(path)
        require(actual_sha == expected_sha, f"pair SHA: {relative}")
        rows = 0
        for row in read_jsonl(path):
            require(
                {"better", "worse", "run_id", "task", "parent"}.issubset(row),
                f"pair schema: {relative}",
            )
            run_id, task, parent = row["run_id"], row["task"], row["parent"]
            require(
                all(isinstance(value, str) for value in (run_id, task, parent)),
                "pair identity type",
            )
            for key in ("better", "worse"):
                card_id = row[key]
                require(isinstance(card_id, str), "endpoint type")
                previous = identities.setdefault(card_id, (run_id, task))
                require(previous == (run_id, task), "endpoint identity conflict")
            runs.add(run_id)
            tasks.add(task)
            parents.add(parent)
            rows += 1
            total_rows += 1
        require(rows == expected_rows, f"pair rows: {relative}")
        pair_hashes[relative] = actual_sha
        pair_rows[relative] = rows

    require(
        (
            total_rows,
            len(identities),
            len(runs),
            len(tasks),
            len(parents),
        )
        == (
            schema.HISTORICAL_UNION_ROWS,
            schema.HISTORICAL_UNION_ENDPOINTS,
            schema.HISTORICAL_UNION_RUNS,
            schema.HISTORICAL_UNION_TASKS,
            schema.HISTORICAL_UNION_PARENTS,
        ),
        "historical union counts",
    )
    cards_path = repo_root / schema.HISTORICAL_CARDS_PATH
    require(sha256_file(cards_path) == schema.HISTORICAL_CARDS_SHA256, "cards SHA")
    selected: dict[str, CodeRecord] = {}
    seen: set[str] = set()
    for row in read_jsonl(cards_path):
        card_id = row.get("id")
        require(isinstance(card_id, str) and card_id not in seen, "cards ID")
        seen.add(card_id)
        if card_id not in identities:
            continue
        task = row.get("task")
        require(
            isinstance(task, dict) and isinstance(task.get("name"), str),
            "cards task schema",
        )
        run_id, code = row.get("run_id"), row.get("code")
        require(isinstance(run_id, str) and isinstance(code, str), "cards code/run")
        require(identities[card_id] == (run_id, task["name"]), "pair/card identity")
        selected[card_id] = CodeRecord(card_id, run_id, task["name"], code)
    require(set(selected) == set(identities), "historical endpoints missing")
    return [selected[key] for key in sorted(selected)], {
        "cards_path": schema.HISTORICAL_CARDS_PATH,
        "cards_sha256": schema.HISTORICAL_CARDS_SHA256,
        "pair_normalized_lf_sha256": pair_hashes,
        "pair_rows": pair_rows,
        "union_rows": total_rows,
        "union_endpoints": len(identities),
        "union_runs": len(runs),
        "union_tasks": len(tasks),
        "union_parents": len(parents),
        "historical_label_or_observation_fields_used": False,
    }


def load_prospective(
    state_root: Path, snapshot_root: Path, producer: dict[str, Any]
) -> tuple[list[CodeRecord], dict[str, Any]]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    require(snapshot_root.parent == state_root / "snapshots", "snapshot path")
    require(snapshot_root.name == producer["snapshot_sha256"], "snapshot SHA name")
    inputs = producer["prospective_scope"]["inputs"]
    registry_path = snapshot_root / "intake_registry.jsonl"
    runs_path = snapshot_root / "accumulator" / "provisional_runs.jsonl"
    summary_path = snapshot_root / "accumulator" / "summary.json"
    require(sha256_file(registry_path) == inputs["intake_registry_sha256"], "registry SHA")
    require(sha256_file(runs_path) == inputs["provisional_runs_sha256"], "runs SHA")
    require(sha256_file(summary_path) == inputs["accumulator_summary_sha256"], "summary SHA")

    runs = list(read_jsonl(runs_path))
    require(all(set(row) == prospective_schema.RUN_KEYS for row in runs), "run schema")
    run_rows: dict[str, dict[str, Any]] = {}
    for row in runs:
        run_id = row["run_id"]
        require(isinstance(run_id, str) and run_id not in run_rows, "duplicate run")
        require(row["flow_status"] == "scoreable", "run flow")
        run_rows[run_id] = row
    ordered = sorted(
        runs,
        key=lambda row: (
            str(row["generation_started_at_utc"]),
            str(row["source_sha256"]),
            str(row["run_id"]),
        ),
    )
    target = producer["prospective_scope"]["target_runs"]
    require(target == schema.FROZEN_COHORT_RUN_TARGET, "target runs")
    cohort_ids = {str(row["run_id"]) for row in ordered[:target]}

    records: list[CodeRecord] = []
    seen_cards: set[str] = set()
    endpoint_counts: collections.Counter[str] = collections.Counter()
    drop_for_run: dict[str, str] = {}
    intake_summary_shas: dict[str, str] = {}
    registry = list(read_jsonl(registry_path))
    for entry in registry:
        require(set(entry) == {"drop_id", "intake_dir", "summary_sha256"}, "registry schema")
        drop_id = entry["drop_id"]
        intake = Path(entry["intake_dir"]).resolve()
        require(isinstance(drop_id, str) and intake.parent == state_root / "intakes", "intake path")
        require(intake.name == drop_id, "intake name")
        intake_summary = intake / "summary.json"
        require(sha256_file(intake_summary) == entry["summary_sha256"], "intake summary SHA")
        require(inputs["intake_summary_sha256"][drop_id] == entry["summary_sha256"], "bound intake SHA")
        intake_summary_shas[drop_id] = entry["summary_sha256"]
        intake_payload = read_json(intake_summary)
        security = intake_payload["security"]
        blindness = intake_payload["blindness"]
        require(security["env_members_read"] is False, "env member read")
        require(security["live_event_journal_members_read"] is False, "journal member read")
        require(security["journal_scanned_before_json"] is True, "journal order")
        require(blindness["labels_used_for_run_selection"] is False, "label run selection")
        require(blindness["labels_used_for_endpoint_selection"] is False, "label endpoint selection")
        manifest = intake / "eligible_blind_manifest.jsonl"
        require(
            sha256_file(manifest)
            == intake_payload["outputs"]["eligible_blind_manifest_sha256"],
            "blind manifest SHA",
        )
        for row in read_jsonl(manifest):
            require(set(row) == prospective_schema.BLIND_KEYS, "blind schema")
            require(set(row["lineage"]) == prospective_schema.LINEAGE_KEYS, "lineage schema")
            require(sha256_text(row["code"]) == row["code_sha256"], "code SHA")
            require(row["card_id"] not in seen_cards, "duplicate prospective card")
            seen_cards.add(row["card_id"])
            run_id = row["run_id"]
            require(run_id in run_rows, "unknown prospective run")
            run_row = run_rows[run_id]
            require(run_row["drop_id"] == drop_id, "run/drop binding")
            require(run_row["task"] == row["task"], "run/task binding")
            require(
                run_row["generation_started_at_utc"] == row["generation_started_at_utc"]
                and run_row["source_sha256"] == row["source_sha256"],
                "run ordering identity",
            )
            previous_drop = drop_for_run.setdefault(run_id, drop_id)
            require(previous_drop == drop_id, "run crosses drops")
            endpoint_counts[run_id] += 1
            if run_id in cohort_ids:
                records.append(CodeRecord(row["card_id"], run_id, row["task"], row["code"]))

    accumulator = read_json(summary_path)
    require(accumulator["security"]["label_vault_opened"] is False, "label vault")
    require(accumulator["security"]["outcome_files_opened"] == [], "outcome files")
    require(accumulator["security"]["scorer_prediction_files_opened"] == [], "prediction files")
    require(accumulator["closure"]["provided"] is False, "unexpected closure")
    require(set(endpoint_counts) == set(run_rows), "prospective run support")
    require(
        all(endpoint_counts[run_id] == row["endpoints"] for run_id, row in run_rows.items()),
        "prospective endpoint accounting",
    )
    require(accumulator["inventory"]["drops"] == len(registry), "drop count")
    require(accumulator["inventory"]["eligible_runs"] == len(runs), "eligible runs")
    require(accumulator["inventory"]["eligible_endpoints"] == len(seen_cards), "eligible endpoints")
    require(accumulator["inventory"]["provisional_first960_runs"] == len(cohort_ids), "cohort runs")
    require(accumulator["inventory"]["provisional_first960_endpoints"] == len(records), "cohort endpoints")
    require(dict(sorted(intake_summary_shas.items())) == inputs["intake_summary_sha256"], "intake set")
    return records, inputs


def fingerprint(records: list[CodeRecord]) -> tuple[list[Record], dict[str, Any]]:
    values: list[Record] = []
    token_failures = 0
    low_shingle = 0
    for record in records:
        shingle_values = token_impl.shingles(record.code)
        if shingle_values is None:
            try:
                list(tokenize.generate_tokens(io.StringIO(record.code).readline))
            except (IndentationError, SyntaxError, tokenize.TokenError):
                token_failures += 1
            else:
                low_shingle += 1
            continue
        values.append(Record(record.card_id, record.run_id, record.task, shingle_values))
    return values, {
        "input_endpoints": len(records),
        "fingerprinted_endpoints": len(values),
        "tokenization_failures": token_failures,
        "too_short_or_low_distinct_shingles": low_shingle,
        "coverage": len(values) / len(records) if records else None,
    }


def prefix(values: frozenset[int], frequency: collections.Counter[int]) -> list[int]:
    ordered = sorted(values, key=lambda value: (frequency[value], value))
    required = math.ceil(schema.PRIMARY_NUMERATOR * len(ordered) / schema.PRIMARY_DENOMINATOR)
    return ordered[: len(ordered) - required + 1]


def independent_join(
    historical: list[Record], prospective: list[Record]
) -> tuple[list[Edge], int]:
    frequency: collections.Counter[int] = collections.Counter()
    for row in historical + prospective:
        frequency.update(row.shingles)
    postings: dict[int, list[int]] = collections.defaultdict(list)
    for index, row in enumerate(historical):
        for value in prefix(row.shingles, frequency):
            postings[value].append(index)
    candidates: set[tuple[int, int]] = set()
    for prospective_index, row in enumerate(prospective):
        for value in prefix(row.shingles, frequency):
            for historical_index in postings[value]:
                shorter = min(len(historical[historical_index].shingles), len(row.shingles))
                longer = max(len(historical[historical_index].shingles), len(row.shingles))
                if schema.PRIMARY_DENOMINATOR * shorter >= schema.PRIMARY_NUMERATOR * longer:
                    candidates.add((historical_index, prospective_index))
    edges = []
    for historical_index, prospective_index in sorted(candidates):
        left = historical[historical_index].shingles
        right = prospective[prospective_index].shingles
        intersection = len(left & right)
        union = len(left) + len(right) - intersection
        if schema.PRIMARY_DENOMINATOR * intersection >= schema.PRIMARY_NUMERATOR * union:
            edges.append(Edge(historical_index, prospective_index, intersection, union))
    return edges, len(candidates)


def brute_force(historical: list[Record], prospective: list[Record]) -> list[Edge]:
    edges = []
    for historical_index, left in enumerate(historical):
        for prospective_index, right in enumerate(prospective):
            intersection = len(left.shingles & right.shingles)
            union = len(left.shingles) + len(right.shingles) - intersection
            if schema.PRIMARY_DENOMINATOR * intersection >= schema.PRIMARY_NUMERATOR * union:
                edges.append(Edge(historical_index, prospective_index, intersection, union))
    return edges


def edge_signature(edges: list[Edge]) -> str:
    return sha256_text(
        "\n".join(
            sorted(
                f"{edge.historical}:{edge.prospective}:{edge.intersection}:{edge.union}"
                for edge in edges
            )
        )
    )


def aggregate(
    historical: list[Record], prospective: list[Record], edges: list[Edge]
) -> dict[str, Any]:
    historical_members: set[int] = set()
    prospective_members: set[int] = set()
    cross_task_historical: set[int] = set()
    cross_task_prospective: set[int] = set()
    same_task_pairs = 0
    cross_task_pairs = 0
    node_count = len(historical) + len(prospective)
    parents = list(range(node_count))
    sizes = [1] * node_count

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

    digest_rows = []
    for edge in edges:
        left, right = historical[edge.historical], prospective[edge.prospective]
        historical_members.add(edge.historical)
        prospective_members.add(edge.prospective)
        if left.task == right.task:
            same_task_pairs += 1
        else:
            cross_task_pairs += 1
            cross_task_historical.add(edge.historical)
            cross_task_prospective.add(edge.prospective)
        union(edge.historical, len(historical) + edge.prospective)
        first, second = sorted((left.card_id, right.card_id))
        digest_rows.append(
            sha256_text(f"{first}\x00{second}\x00{edge.intersection}\x00{edge.union}")
        )

    component_members: dict[int, set[int]] = collections.defaultdict(set)
    for index in historical_members:
        component_members[find(index)].add(index)
    for index in prospective_members:
        node = len(historical) + index
        component_members[find(node)].add(node)
    component_rows = []
    for members in component_members.values():
        tasks = {
            historical[node].task
            if node < len(historical)
            else prospective[node - len(historical)].task
            for node in members
        }
        component_rows.append((len(members), len(tasks)))
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
        "same_task_pairs": same_task_pairs,
        "cross_task_pairs": cross_task_pairs,
        "historical_affected_endpoints": len(historical_members),
        "historical_affected_fraction": len(historical_members) / len(historical),
        "prospective_affected_endpoints": len(prospective_members),
        "prospective_affected_fraction": len(prospective_members) / len(prospective),
        "cross_task_historical_affected_endpoints": len(cross_task_historical),
        "cross_task_historical_affected_fraction": len(cross_task_historical)
        / len(historical),
        "cross_task_prospective_affected_endpoints": len(cross_task_prospective),
        "cross_task_prospective_affected_fraction": len(cross_task_prospective) / len(prospective),
        "components": len(component_rows),
        "largest_component_endpoints": max((row[0] for row in component_rows), default=0),
        "largest_component_tasks": max((row[1] for row in component_rows), default=0),
        "large_multitask_components": large,
        "edge_digest_sha256": sha256_text(payload),
        "edge_identities_emitted": False,
    }


def reproduce(
    repo_root: Path,
    state_root: Path,
    snapshot_root: Path,
    producer: dict[str, Any],
) -> dict[str, Any]:
    require_dependency_contract()
    require(producer.get("protocol") == schema.PROTOCOL, "protocol")
    historical_code, historical_scope = load_historical(repo_root)
    prospective_code, prospective_inputs = load_prospective(
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
    historical_runs = {row.run_id for row in historical_code}
    prospective_runs = {row.run_id for row in prospective_code}
    require(not historical_runs.intersection(prospective_runs), "physical run overlap")
    require(len(prospective_runs) == producer["prospective_scope"]["observed_runs"], "run count")
    require(len(prospective_code) == producer["prospective_scope"]["observed_endpoints"], "endpoint count")

    edges, candidates = independent_join(historical, prospective)
    strict = [
        edge
        for edge in edges
        if schema.STRICT_DENOMINATOR * edge.intersection
        >= schema.STRICT_NUMERATOR * edge.union
    ]
    primary_summary = aggregate(historical, prospective, edges)
    strict_summary = aggregate(historical, prospective, strict)
    require(
        candidates
        == producer["primary_jaccard_0_85"]["candidate_pairs_exactly_checked"],
        "candidate count",
    )
    for key, value in primary_summary.items():
        require(value == producer["primary_jaccard_0_85"][key], f"primary: {key}")
    for key, value in strict_summary.items():
        require(value == producer["strict_jaccard_0_95"][key], f"strict: {key}")

    historical_subset = sorted(historical, key=lambda row: sha256_text(row.card_id))[
        : schema.SELF_CHECK_PER_SIDE
    ]
    prospective_subset = sorted(prospective, key=lambda row: sha256_text(row.card_id))[
        : schema.SELF_CHECK_PER_SIDE
    ]
    subset_join, _ = independent_join(historical_subset, prospective_subset)
    subset_brute = brute_force(historical_subset, prospective_subset)
    join_digest = edge_signature(subset_join)
    brute_digest = edge_signature(subset_brute)
    require(join_digest == brute_digest, "subset brute-force")
    producer_check = producer["bipartite_join_self_check"]
    require(join_digest == producer_check["join_edge_digest"], "producer subset join")
    require(brute_digest == producer_check["brute_force_edge_digest"], "producer subset brute")

    gates = {
        "historical_fingerprint_coverage": historical_fingerprint["coverage"]
        >= schema.MIN_HISTORICAL_COVERAGE,
        "prospective_fingerprint_coverage": prospective_fingerprint["coverage"]
        >= schema.MIN_PROSPECTIVE_COVERAGE,
        "prospective_affected_fraction": primary_summary["prospective_affected_fraction"]
        <= schema.MAX_PROSPECTIVE_AFFECTED_FRACTION,
        "cross_task_prospective_affected_fraction": primary_summary[
            "cross_task_prospective_affected_fraction"
        ]
        <= schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION,
        "large_multitask_components": primary_summary["large_multitask_components"]
        <= schema.MAX_LARGE_MULTITASK_COMPONENTS,
        "bipartite_join_self_check": True,
    }
    require(gates == producer["pre_registered_gate"]["checks"], "gate values")
    return {
        "protocol": schema.INDEPENDENT_PROTOCOL,
        "status": "INDEPENDENTLY_VERIFIED_PROVISIONAL_HISTORICAL_TRAIN_FUTURE_OVERLAP",
        "producer_receipt_sha256": sha256_file(Path(producer["_receipt_path"])),
        "snapshot_sha256": producer["snapshot_sha256"],
        "historical_endpoints": len(historical_code),
        "prospective_runs": len(prospective_runs),
        "prospective_endpoints": len(prospective_code),
        "primary_candidate_pairs": candidates,
        "primary_near_duplicate_pairs": len(edges),
        "primary_edge_digest_sha256": primary_summary["edge_digest_sha256"],
        "strict_near_duplicate_pairs": len(strict),
        "strict_edge_digest_sha256": strict_summary["edge_digest_sha256"],
        "producer_aggregate_matches": True,
        "subset_bruteforce_matches": True,
        "imports_new_producer_code": False,
        "historical_label_or_observation_fields_used": False,
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
    producer_path = repo_root / "phase1/audit_historical_train_future_fuzzy_overlap.py"
    require(sha256_file(producer_path) == producer["source_sha256"], "producer source SHA")
    require(
        sha256_file(Path(schema.__file__).resolve()) == producer["schema_sha256"],
        "schema source SHA",
    )
    fuzzy_path = repo_root / "phase1/audit_prospective_fuzzy_code_clones.py"
    require(sha256_file(fuzzy_path) == producer["fuzzy_dependency_sha256"], "fuzzy source SHA")
    require(
        sha256_file(Path(prospective_schema.__file__).resolve())
        == producer["fuzzy_schema_dependency_sha256"],
        "fuzzy schema SHA",
    )
    for path in (
        Path(__file__).resolve(),
        Path(schema.__file__).resolve(),
        Path(prospective_schema.__file__).resolve(),
        Path(token_impl.__file__).resolve(),
    ):
        require(
            committed_blob(repo_root, head, path)
            == subprocess.check_output(
                ["git", "-C", str(repo_root), "hash-object", str(path)], text=True
            ).strip(),
            f"verifier blob binding: {path.name}",
        )
    result = reproduce(repo_root, args.state_root, args.snapshot_root, producer)
    result["verifier_source_sha256"] = sha256_file(Path(__file__).resolve())
    result["token_implementation_sha256"] = sha256_file(Path(token_impl.__file__).resolve())
    atomic_json(args.output, result)
    print(result["status"])


if __name__ == "__main__":
    main()
