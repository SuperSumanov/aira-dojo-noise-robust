"""Outcome-blind exact-parent support audit for Meta Kaggle human forks.

This stage reads only kernel, version, competition-link, and competition
identity metadata.  It intentionally has no input for submission records or
notebook content.  A passing result is only permission to pre-register a later
stage; it is not a predictor result.
"""

from __future__ import annotations

import argparse
import array
import csv
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


csv.field_size_limit(min(sys.maxsize, 1 << 30))


PROTOCOL = "meta-kaggle-exact-parent-human-fork-s0b-v1"
SNAPSHOT_CUTOFF = datetime(2026, 8, 21, 9, 13, 44, tzinfo=timezone.utc)
MIN_DIRECT_PARENT_AGREEMENT = 0.95
MIN_PAIRS = 500
MIN_PARENTS = 100
MIN_COMPETITIONS = 20
MAX_DOMINANT_COMPETITION_SHARE = 0.20
CHILD_RANK_DOMAIN = "meta-kaggle-exact-parent-child-rank-v1"
ORIENTATION_DOMAIN = "meta-kaggle-exact-parent-orientation-v1"
REGISTERED_SOURCES = (
    "phase1/meta_kaggle_exact_parent_s0_protocol_v1.json",
    "phase1/meta_kaggle_exact_parent_s0a_input_manifest.json",
    "phase1/meta_kaggle_exact_parent_s0b.py",
    "phase1/verify_meta_kaggle_exact_parent_s0b.py",
    "phase1/scripts/run_meta_kaggle_exact_parent_s0b_20260821.sh",
    "phase1/tests/test_meta_kaggle_exact_parent_s0b.py",
)

KERNEL_COLUMNS = (
    "Id",
    "ForkParentKernelVersionId",
    "FirstKernelVersionId",
)
VERSION_COLUMNS = (
    "Id",
    "ScriptId",
    "ParentScriptVersionId",
    "CreationDate",
    "VersionNumber",
)
LINK_COLUMNS = ("KernelVersionId", "SourceCompetitionId")
COMPETITION_COLUMNS = (
    "Id",
    "DeadlineDate",
    "FinalLeaderboardHasBeenVerified",
    "HasLeaderboard",
)


class AuditError(RuntimeError):
    """Raised for a malformed or unbound fixed input."""


@dataclass(frozen=True)
class Thresholds:
    direct_parent_agreement: float = MIN_DIRECT_PARENT_AGREEMENT
    pairs: int = MIN_PAIRS
    parents: int = MIN_PARENTS
    competitions: int = MIN_COMPETITIONS
    dominant_share: float = MAX_DOMINANT_COMPETITION_SHARE


@dataclass(frozen=True)
class ForkEdge:
    child_kernel_id: int
    child_first_version_id: int
    parent_version_id: int


@dataclass(frozen=True)
class VersionRecord:
    version_id: int
    script_id: int | None
    parent_version_id: int | None
    creation_time: datetime | None
    version_number: int | None


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def exact_uint(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        if any(character in text for character in ".eE"):
            number = float(text)
            if not number.is_integer():
                return None
            result = int(number)
        else:
            result = int(text)
    except (ValueError, OverflowError):
        return None
    return result if 0 <= result < (1 << 64) else None


def exact_positive(value: str) -> int | None:
    result = exact_uint(value)
    return result if result is not None and result > 0 else None


def exact_bool(value: str) -> bool | None:
    text = value.strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    return None


DATE_FORMATS = (
    "%m/%d/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
)


def exact_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    for date_format in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, date_format)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def projected_csv(path: Path, required: Sequence[str]) -> Iterator[tuple[str, ...]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        try:
            header = next(reader)
        except StopIteration as error:
            raise AuditError(f"empty CSV: {path.name}") from error
        require(len(header) == len(set(header)), f"duplicate CSV header: {path.name}")
        missing = sorted(set(required) - set(header))
        require(not missing, f"missing columns in {path.name}: {missing}")
        indexes = tuple(header.index(name) for name in required)
        for row_number, row in enumerate(reader, 2):
            require(len(row) == len(header), f"CSV width mismatch: {path.name}:{row_number}")
            yield tuple(row[index] for index in indexes)


class PartitionedUInt64Uniqueness:
    """Bounded-memory exact duplicate counter for a large integer column."""

    def __init__(self, scratch: Path, prefix: str, partitions: int = 64) -> None:
        require(partitions > 1, "partitions must exceed one")
        self.paths = tuple(scratch / f"{prefix}-{index:03d}.u64" for index in range(partitions))
        self.handles = tuple(path.open("wb") for path in self.paths)
        self.buffers = [bytearray() for _ in self.paths]
        self.partitions = partitions
        self.count = 0

    def add(self, value: int) -> None:
        index = value % self.partitions
        self.buffers[index].extend(struct.pack("<Q", value))
        self.count += 1
        if len(self.buffers[index]) >= (1 << 20):
            self.handles[index].write(self.buffers[index])
            self.buffers[index].clear()

    def finish(self) -> int:
        for handle, buffer in zip(self.handles, self.buffers):
            if buffer:
                handle.write(buffer)
            handle.close()
        duplicates = 0
        for path in self.paths:
            values = array.array("Q")
            with path.open("rb") as handle:
                values.fromfile(handle, os.path.getsize(path) // values.itemsize)
            if struct.pack("=Q", 1) != struct.pack("<Q", 1):
                values.byteswap()
            values = array.array("Q", sorted(values))
            duplicates += sum(left == right for left, right in zip(values, values[1:]))
        return duplicates

    def abort(self) -> None:
        for handle in self.handles:
            if not handle.closed:
                handle.close()


def scan_kernels(path: Path, scratch: Path) -> tuple[dict[str, int], dict[int, ForkEdge], set[int]]:
    counts: Counter[str] = Counter()
    edges: dict[int, ForkEdge] = {}
    tracker = PartitionedUInt64Uniqueness(scratch, "kernel-id")
    try:
        for kernel_id_raw, parent_raw, first_raw in projected_csv(path, KERNEL_COLUMNS):
            counts["rows"] += 1
            kernel_id = exact_positive(kernel_id_raw)
            if kernel_id is None:
                counts["malformed_id"] += 1
                continue
            tracker.add(kernel_id)
            if not parent_raw.strip():
                continue
            counts["explicit_fork_rows"] += 1
            parent_id = exact_positive(parent_raw)
            first_id = exact_positive(first_raw)
            if parent_id is None or first_id is None:
                counts["malformed_explicit_fork"] += 1
                continue
            if kernel_id in edges:
                counts["duplicate_explicit_child_kernel"] += 1
                continue
            edges[kernel_id] = ForkEdge(kernel_id, first_id, parent_id)
    except BaseException:
        tracker.abort()
        raise
    counts["duplicate_id"] = tracker.finish()
    needed = {identifier for edge in edges.values() for identifier in (edge.child_first_version_id, edge.parent_version_id)}
    return dict(sorted(counts.items())), edges, needed


def scan_versions(
    path: Path,
    needed: set[int],
    scratch: Path,
) -> tuple[dict[str, int], dict[int, VersionRecord]]:
    counts: Counter[str] = Counter()
    records: dict[int, VersionRecord] = {}
    tracker = PartitionedUInt64Uniqueness(scratch, "version-id")
    try:
        for version_raw, script_raw, parent_raw, created_raw, number_raw in projected_csv(path, VERSION_COLUMNS):
            counts["rows"] += 1
            version_id = exact_positive(version_raw)
            if version_id is None:
                counts["malformed_id"] += 1
                continue
            tracker.add(version_id)
            if version_id not in needed:
                continue
            if version_id in records:
                counts["duplicate_relevant_id"] += 1
                continue
            records[version_id] = VersionRecord(
                version_id=version_id,
                script_id=exact_positive(script_raw),
                parent_version_id=exact_positive(parent_raw),
                creation_time=exact_datetime(created_raw),
                version_number=exact_positive(number_raw),
            )
    except BaseException:
        tracker.abort()
        raise
    counts["duplicate_id"] = tracker.finish()
    counts["required_ids"] = len(needed)
    counts["required_ids_found"] = len(records)
    counts["required_ids_missing"] = len(needed - set(records))
    return dict(sorted(counts.items())), records


def scan_competition_links(
    path: Path,
    needed_versions: set[int],
) -> tuple[dict[str, int], dict[int, set[int]]]:
    counts: Counter[str] = Counter()
    links: dict[int, set[int]] = defaultdict(set)
    seen_relevant: set[tuple[int, int]] = set()
    for version_raw, competition_raw in projected_csv(path, LINK_COLUMNS):
        counts["rows"] += 1
        version_id = exact_positive(version_raw)
        competition_id = exact_positive(competition_raw)
        if version_id is None or competition_id is None:
            counts["malformed_row"] += 1
            continue
        if version_id not in needed_versions:
            continue
        key = (version_id, competition_id)
        if key in seen_relevant:
            counts["duplicate_relevant_link"] += 1
        seen_relevant.add(key)
        links[version_id].add(competition_id)
    counts["relevant_versions_with_links"] = len(links)
    return dict(sorted(counts.items())), dict(links)


def scan_competitions(
    path: Path,
    needed_competitions: set[int],
) -> tuple[dict[str, int], dict[int, dict[str, Any]]]:
    counts: Counter[str] = Counter()
    competitions: dict[int, dict[str, Any]] = {}
    for competition_raw, deadline_raw, verified_raw, leaderboard_raw in projected_csv(path, COMPETITION_COLUMNS):
        counts["rows"] += 1
        competition_id = exact_positive(competition_raw)
        if competition_id is None:
            counts["malformed_id"] += 1
            continue
        if competition_id not in needed_competitions:
            continue
        if competition_id in competitions:
            counts["duplicate_relevant_id"] += 1
            continue
        deadline = exact_datetime(deadline_raw)
        verified = exact_bool(verified_raw)
        has_leaderboard = exact_bool(leaderboard_raw)
        competitions[competition_id] = {
            "deadline": deadline,
            "verified": verified,
            "has_leaderboard": has_leaderboard,
            "eligible_closed": bool(
                deadline is not None
                and deadline < SNAPSHOT_CUTOFF
                and verified is True
                and has_leaderboard is True
            ),
        }
    counts["required_ids"] = len(needed_competitions)
    counts["required_ids_found"] = len(competitions)
    counts["required_ids_missing"] = len(needed_competitions - set(competitions))
    return dict(sorted(counts.items())), competitions


def cycle_node_count(edges: Iterable[tuple[int, int]]) -> int:
    adjacency: dict[int, set[int]] = defaultdict(set)
    indegree: Counter[int] = Counter()
    nodes: set[int] = set()
    for parent, child in edges:
        nodes.update((parent, child))
        if child not in adjacency[parent]:
            adjacency[parent].add(child)
            indegree[child] += 1
            indegree.setdefault(parent, 0)
    queue = deque(sorted(node for node in nodes if indegree[node] == 0))
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for child in sorted(adjacency.get(node, ())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return len(nodes) - visited


def deterministic_pair(parent_id: int, children: Sequence[dict[str, int]]) -> dict[str, int]:
    ranked = sorted(
        children,
        key=lambda child: (
            hashlib.sha256(
                f"{CHILD_RANK_DOMAIN}|{parent_id}|{child['child_kernel_id']}".encode("ascii")
            ).hexdigest(),
            child["child_kernel_id"],
        ),
    )
    first, second = ranked[:2]
    orientation = hashlib.sha256(
        f"{ORIENTATION_DOMAIN}|{parent_id}|{first['child_kernel_id']}|{second['child_kernel_id']}".encode("ascii")
    ).digest()[0] & 1
    left, right = (second, first) if orientation else (first, second)
    return {
        "parent_version_id": parent_id,
        "competition_id": left["competition_id"],
        "child_a_kernel_id": left["child_kernel_id"],
        "child_a_first_version_id": left["child_first_version_id"],
        "child_b_kernel_id": right["child_kernel_id"],
        "child_b_first_version_id": right["child_first_version_id"],
    }


def reconstruct(
    kernels_path: Path,
    versions_path: Path,
    links_path: Path,
    competitions_path: Path,
    scratch_root: Path,
    thresholds: Thresholds = Thresholds(),
) -> tuple[dict[str, Any], list[dict[str, int]]]:
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="meta-kaggle-s0b-", dir=scratch_root) as temporary:
        scratch = Path(temporary)
        kernel_counts, fork_edges, needed_versions = scan_kernels(kernels_path, scratch)
        version_counts, versions = scan_versions(versions_path, needed_versions, scratch)

    link_counts, competition_links = scan_competition_links(links_path, needed_versions)
    needed_competitions = {competition for values in competition_links.values() for competition in values}
    competition_counts, competitions = scan_competitions(competitions_path, needed_competitions)

    edge_counts: Counter[str] = Counter()
    base_valid: list[dict[str, int]] = []
    graph_edges: list[tuple[int, int]] = []
    direct_matches = 0
    for edge in fork_edges.values():
        child = versions.get(edge.child_first_version_id)
        parent = versions.get(edge.parent_version_id)
        if child is None:
            edge_counts["child_first_version_missing"] += 1
        if parent is None:
            edge_counts["parent_version_missing"] += 1
        if child is not None and child.parent_version_id == edge.parent_version_id:
            direct_matches += 1
        else:
            edge_counts["direct_parent_field_mismatch"] += 1
        valid = child is not None and parent is not None
        if child is not None:
            if child.script_id != edge.child_kernel_id:
                edge_counts["child_first_script_mismatch"] += 1
                valid = False
            if child.version_number != 1:
                edge_counts["child_not_version_one"] += 1
                valid = False
            if child.parent_version_id != edge.parent_version_id:
                valid = False
        if parent is not None:
            if parent.script_id is None:
                edge_counts["parent_script_missing"] += 1
                valid = False
            elif parent.script_id == edge.child_kernel_id:
                edge_counts["parent_child_same_script"] += 1
                valid = False
        if child is None or parent is None or child.creation_time is None or parent.creation_time is None:
            edge_counts["creation_time_missing"] += 1
            valid = False
        elif child.creation_time <= parent.creation_time:
            edge_counts["parent_child_time_order_invalid"] += 1
            valid = False
        if valid:
            graph_edges.append((edge.parent_version_id, edge.child_first_version_id))
            base_valid.append(
                {
                    "parent_version_id": edge.parent_version_id,
                    "child_kernel_id": edge.child_kernel_id,
                    "child_first_version_id": edge.child_first_version_id,
                }
            )

    cycle_nodes = cycle_node_count(graph_edges)
    edge_counts["cycle_nodes"] = cycle_nodes
    eligible_children: dict[int, list[dict[str, int]]] = defaultdict(list)
    for child in base_valid:
        parent_id = child["parent_version_id"]
        child_id = child["child_first_version_id"]
        parent_competitions = competition_links.get(parent_id, set())
        child_competitions = competition_links.get(child_id, set())
        if len(parent_competitions) != 1:
            edge_counts["parent_competition_not_singleton"] += 1
            continue
        if len(child_competitions) != 1:
            edge_counts["child_competition_not_singleton"] += 1
            continue
        if parent_competitions != child_competitions:
            edge_counts["parent_child_competition_mismatch"] += 1
            continue
        competition_id = next(iter(parent_competitions))
        competition = competitions.get(competition_id)
        if competition is None:
            edge_counts["competition_record_missing"] += 1
            continue
        if not competition["eligible_closed"]:
            edge_counts["competition_not_closed_verified"] += 1
            continue
        eligible_children[parent_id].append({**child, "competition_id": competition_id})

    pairs: list[dict[str, int]] = []
    for parent_id in sorted(eligible_children):
        children = eligible_children[parent_id]
        distinct_child_ids = {child["child_kernel_id"] for child in children}
        if len(distinct_child_ids) < 2:
            continue
        require(len(distinct_child_ids) == len(children), "duplicate eligible child kernel within parent")
        pairs.append(deterministic_pair(parent_id, children))

    competition_pair_counts = Counter(pair["competition_id"] for pair in pairs)
    dominant_share = max(competition_pair_counts.values(), default=0) / len(pairs) if pairs else None
    explicit_count = kernel_counts.get("explicit_fork_rows", 0)
    agreement_rate = direct_matches / explicit_count if explicit_count else None

    identity_criteria = {
        "kernel_ids_globally_unique": kernel_counts.get("duplicate_id", 0) == 0,
        "kernel_ids_well_formed": kernel_counts.get("malformed_id", 0) == 0,
        "kernel_version_ids_globally_unique": version_counts.get("duplicate_id", 0) == 0,
        "kernel_version_ids_well_formed": version_counts.get("malformed_id", 0) == 0,
        "relevant_competition_ids_unique": competition_counts.get("duplicate_relevant_id", 0) == 0,
        "selected_graph_acyclic": cycle_nodes == 0,
        "direct_parent_field_agreement_rate_ge_0_95": bool(
            agreement_rate is not None and agreement_rate >= thresholds.direct_parent_agreement
        ),
        "selected_pair_identity_complete": all(
            pair["child_a_kernel_id"] != pair["child_b_kernel_id"]
            and pair["parent_version_id"] > 0
            and pair["competition_id"] > 0
            for pair in pairs
        ),
    }
    support_criteria = {
        "canonical_pairs_ge_500": len(pairs) >= thresholds.pairs,
        "distinct_parents_ge_100": len({pair["parent_version_id"] for pair in pairs}) >= thresholds.parents,
        "completed_competitions_ge_20": len(competition_pair_counts) >= thresholds.competitions,
        "dominant_competition_share_le_0_20": bool(
            dominant_share is not None and dominant_share <= thresholds.dominant_share
        ),
    }
    if not all(identity_criteria.values()):
        status = "IDENTITY_UNAVAILABLE"
    elif not all(support_criteria.values()):
        status = "INSUFFICIENT_EXACT_PARENT_SUPPORT"
    else:
        status = "EXACT_PARENT_STRUCTURE_SUPPORT_FEASIBLE"

    summary = {
        "protocol": PROTOCOL,
        "status": status,
        "snapshot_cutoff_utc": SNAPSHOT_CUTOFF.isoformat().replace("+00:00", "Z"),
        "thresholds": {
            "direct_parent_agreement_rate_ge": thresholds.direct_parent_agreement,
            "canonical_pairs_ge": thresholds.pairs,
            "distinct_parents_ge": thresholds.parents,
            "completed_competitions_ge": thresholds.competitions,
            "dominant_competition_share_le": thresholds.dominant_share,
        },
        "inventory": {
            "kernels": kernel_counts,
            "kernel_versions": version_counts,
            "competition_links": link_counts,
            "competitions": competition_counts,
            "parsed_explicit_fork_edges": len(fork_edges),
            "base_valid_fork_edges": len(base_valid),
            "eligible_closed_competition_children": sum(map(len, eligible_children.values())),
            "eligible_parent_groups": len(eligible_children),
            "canonical_pairs": len(pairs),
            "completed_competitions_in_pairs": len(competition_pair_counts),
            "dominant_competition_share": dominant_share,
            "direct_parent_field_matches": direct_matches,
            "direct_parent_field_agreement_rate": agreement_rate,
            "edge_failures": dict(sorted(edge_counts.items())),
            "pairs_per_competition": {str(key): value for key, value in sorted(competition_pair_counts.items())},
        },
        "identity_criteria": identity_criteria,
        "support_criteria": support_criteria,
        "scope": {
            "gpu": 0,
            "api_calls": 0,
            "model_trained": False,
            "notebook_content_used": False,
            "predictor_effect_computed": False,
            "outcome_table_rows_used": 0,
        },
    }
    return summary, pairs


def git_output(repo_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def bind_source(repo_root: Path, source_commit: str) -> dict[str, str]:
    require(git_output(repo_root, "rev-parse", "HEAD") == source_commit, "HEAD/source commit mismatch")
    hashes: dict[str, str] = {}
    for relative in REGISTERED_SOURCES:
        path = repo_root / relative
        require(path.is_file(), f"registered source missing: {relative}")
        require(
            git_output(repo_root, "hash-object", relative)
            == git_output(repo_root, "rev-parse", f"{source_commit}:{relative}"),
            f"registered source differs from commit: {relative}",
        )
        hashes[relative] = sha256_file(path)
    return hashes


def require_hash(path: Path, expected: str) -> str:
    observed = sha256_file(path)
    require(observed == expected, f"SHA256 mismatch: {path.name}")
    return observed


def write_result(output: Path, summary: dict[str, Any], pairs: list[dict[str, int]]) -> None:
    require(not output.exists(), f"output already exists: {output}")
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(canonical_json(summary))
    with (output / "canonical_pairs.jsonl").open("wb") as handle:
        for pair in pairs:
            handle.write(json.dumps(pair, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n")
    manifest = {
        name: sha256_file(output / name)
        for name in ("canonical_pairs.jsonl", "summary.json")
    }
    (output / "sha256_manifest.json").write_bytes(canonical_json(manifest))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--kernels", type=Path, required=True)
    parser.add_argument("--expect-kernels-sha256", required=True)
    parser.add_argument("--kernel-versions", type=Path, required=True)
    parser.add_argument("--expect-kernel-versions-sha256", required=True)
    parser.add_argument("--competition-links", type=Path, required=True)
    parser.add_argument("--expect-competition-links-sha256", required=True)
    parser.add_argument("--competitions", type=Path, required=True)
    parser.add_argument("--expect-competitions-sha256", required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_hashes = bind_source(args.repo_root.resolve(), args.source_commit)
    input_hashes = {
        "protocol": require_hash(args.protocol.resolve(), args.expect_protocol_sha256),
        "kernels": require_hash(args.kernels.resolve(), args.expect_kernels_sha256),
        "kernel_versions": require_hash(args.kernel_versions.resolve(), args.expect_kernel_versions_sha256),
        "competition_links": require_hash(args.competition_links.resolve(), args.expect_competition_links_sha256),
        "competitions": require_hash(args.competitions.resolve(), args.expect_competitions_sha256),
    }
    summary, pairs = reconstruct(
        args.kernels.resolve(),
        args.kernel_versions.resolve(),
        args.competition_links.resolve(),
        args.competitions.resolve(),
        args.scratch_root.resolve(),
    )
    summary["source_commit"] = args.source_commit
    summary["source_sha256"] = source_hashes
    summary["input_sha256"] = input_hashes
    write_result(args.output.resolve(), summary, pairs)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
