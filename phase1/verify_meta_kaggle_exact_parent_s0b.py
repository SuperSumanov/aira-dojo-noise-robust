"""Independent verifier for the Meta Kaggle exact-parent S0b audit.

The verifier does not import the producer.  It independently scans the four
allowed metadata tables, reconstructs every aggregate and canonical pair, and
requires exact equality with the sealed producer directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


csv.field_size_limit(min(sys.maxsize, 1 << 30))


PRODUCER_PROTOCOL = "meta-kaggle-exact-parent-human-fork-s0b-v1"
VERIFIER_PROTOCOL = "independent-meta-kaggle-exact-parent-human-fork-s0b-v1"
CUTOFF = datetime(2026, 8, 21, 9, 13, 44, tzinfo=timezone.utc)
REGISTERED = (
    "phase1/meta_kaggle_exact_parent_s0_protocol_v1.json",
    "phase1/meta_kaggle_exact_parent_s0a_input_manifest.json",
    "phase1/meta_kaggle_exact_parent_s0b.py",
    "phase1/verify_meta_kaggle_exact_parent_s0b.py",
    "phase1/scripts/run_meta_kaggle_exact_parent_s0b_20260821.sh",
    "phase1/tests/test_meta_kaggle_exact_parent_s0b.py",
)
RANK_DOMAIN = "meta-kaggle-exact-parent-child-rank-v1"
ORDER_DOMAIN = "meta-kaggle-exact-parent-orientation-v1"


class VerificationError(RuntimeError):
    pass


def demand(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            state.update(chunk)
    return state.hexdigest()


def stable_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def positive_integer(value: str) -> int | None:
    token = value.strip()
    if not token:
        return None
    try:
        number = float(token) if any(character in token for character in ".eE") else int(token)
    except (ValueError, OverflowError):
        return None
    if isinstance(number, float) and (not math.isfinite(number) or not number.is_integer()):
        return None
    result = int(number)
    return result if 0 < result < 2**64 else None


def boolean(value: str) -> bool | None:
    normalized = value.strip().casefold()
    if normalized in ("true", "1"):
        return True
    if normalized in ("false", "0"):
        return False
    return None


def timestamp(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    formats = (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    )
    for candidate in formats:
        try:
            parsed = datetime.strptime(normalized, candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def dictionaries(path: Path, required: tuple[str, ...]) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream, strict=True)
        demand(rows.fieldnames is not None, f"header absent: {path.name}")
        demand(len(rows.fieldnames) == len(set(rows.fieldnames)), f"duplicate header: {path.name}")
        demand(set(required).issubset(rows.fieldnames), f"required columns absent: {path.name}")
        for line_number, row in enumerate(rows, 2):
            demand(None not in row, f"wide row: {path.name}:{line_number}")
            demand(all(value is not None for value in row.values()), f"narrow row: {path.name}:{line_number}")
            yield {name: row[name] for name in required}


class TextPartitionDuplicateCounter:
    """Independent bounded-memory integer duplicate audit."""

    def __init__(self, directory: Path, label: str, partitions: int = 97) -> None:
        self.partitions = partitions
        self.paths = [directory / f"{label}-{index:03d}.txt" for index in range(partitions)]
        self.streams = [path.open("w", encoding="ascii", newline="\n") for path in self.paths]

    def append(self, identifier: int) -> None:
        self.streams[identifier % self.partitions].write(f"{identifier}\n")

    def close_and_count(self) -> int:
        for stream in self.streams:
            stream.close()
        duplicates = 0
        for path in self.paths:
            observed: set[int] = set()
            with path.open(encoding="ascii") as lines:
                for line in lines:
                    identifier = int(line)
                    if identifier in observed:
                        duplicates += 1
                    else:
                        observed.add(identifier)
        return duplicates

    def abort(self) -> None:
        for stream in self.streams:
            if not stream.closed:
                stream.close()


def read_kernels(path: Path, temporary: Path) -> tuple[dict[str, int], dict[int, tuple[int, int]], set[int]]:
    statistics: Counter[str] = Counter()
    forks: dict[int, tuple[int, int]] = {}
    uniqueness = TextPartitionDuplicateCounter(temporary, "kernels")
    try:
        for row in dictionaries(path, ("Id", "ForkParentKernelVersionId", "FirstKernelVersionId")):
            statistics["rows"] += 1
            kernel = positive_integer(row["Id"])
            if kernel is None:
                statistics["malformed_id"] += 1
                continue
            uniqueness.append(kernel)
            if not row["ForkParentKernelVersionId"].strip():
                continue
            statistics["explicit_fork_rows"] += 1
            parent = positive_integer(row["ForkParentKernelVersionId"])
            first = positive_integer(row["FirstKernelVersionId"])
            if parent is None or first is None:
                statistics["malformed_explicit_fork"] += 1
                continue
            if kernel in forks:
                statistics["duplicate_explicit_child_kernel"] += 1
                continue
            forks[kernel] = (first, parent)
    except BaseException:
        uniqueness.abort()
        raise
    statistics["duplicate_id"] = uniqueness.close_and_count()
    required = {value for first_parent in forks.values() for value in first_parent}
    return dict(sorted(statistics.items())), forks, required


def read_versions(
    path: Path,
    required: set[int],
    temporary: Path,
) -> tuple[dict[str, int], dict[int, tuple[int | None, int | None, datetime | None, int | None]]]:
    statistics: Counter[str] = Counter()
    versions: dict[int, tuple[int | None, int | None, datetime | None, int | None]] = {}
    uniqueness = TextPartitionDuplicateCounter(temporary, "versions")
    names = ("Id", "ScriptId", "ParentScriptVersionId", "CreationDate", "VersionNumber")
    try:
        for row in dictionaries(path, names):
            statistics["rows"] += 1
            version = positive_integer(row["Id"])
            if version is None:
                statistics["malformed_id"] += 1
                continue
            uniqueness.append(version)
            if version not in required:
                continue
            if version in versions:
                statistics["duplicate_relevant_id"] += 1
                continue
            versions[version] = (
                positive_integer(row["ScriptId"]),
                positive_integer(row["ParentScriptVersionId"]),
                timestamp(row["CreationDate"]),
                positive_integer(row["VersionNumber"]),
            )
    except BaseException:
        uniqueness.abort()
        raise
    statistics["duplicate_id"] = uniqueness.close_and_count()
    statistics["required_ids"] = len(required)
    statistics["required_ids_found"] = len(versions)
    statistics["required_ids_missing"] = len(required - set(versions))
    return dict(sorted(statistics.items())), versions


def read_links(path: Path, required: set[int]) -> tuple[dict[str, int], dict[int, set[int]]]:
    statistics: Counter[str] = Counter()
    result: dict[int, set[int]] = defaultdict(set)
    observed: set[tuple[int, int]] = set()
    for row in dictionaries(path, ("KernelVersionId", "SourceCompetitionId")):
        statistics["rows"] += 1
        version = positive_integer(row["KernelVersionId"])
        competition = positive_integer(row["SourceCompetitionId"])
        if version is None or competition is None:
            statistics["malformed_row"] += 1
            continue
        if version not in required:
            continue
        key = (version, competition)
        if key in observed:
            statistics["duplicate_relevant_link"] += 1
        observed.add(key)
        result[version].add(competition)
    statistics["relevant_versions_with_links"] = len(result)
    return dict(sorted(statistics.items())), dict(result)


def read_competitions(path: Path, required: set[int]) -> tuple[dict[str, int], dict[int, bool]]:
    statistics: Counter[str] = Counter()
    result: dict[int, bool] = {}
    names = ("Id", "DeadlineDate", "FinalLeaderboardHasBeenVerified", "HasLeaderboard")
    for row in dictionaries(path, names):
        statistics["rows"] += 1
        competition = positive_integer(row["Id"])
        if competition is None:
            statistics["malformed_id"] += 1
            continue
        if competition not in required:
            continue
        if competition in result:
            statistics["duplicate_relevant_id"] += 1
            continue
        deadline = timestamp(row["DeadlineDate"])
        result[competition] = bool(
            deadline is not None
            and deadline < CUTOFF
            and boolean(row["FinalLeaderboardHasBeenVerified"]) is True
            and boolean(row["HasLeaderboard"]) is True
        )
    statistics["required_ids"] = len(required)
    statistics["required_ids_found"] = len(result)
    statistics["required_ids_missing"] = len(required - set(result))
    return dict(sorted(statistics.items())), result


def cyclic_nodes(edges: list[tuple[int, int]]) -> int:
    children: dict[int, set[int]] = defaultdict(set)
    incoming: Counter[int] = Counter()
    vertices: set[int] = set()
    for parent, child in edges:
        vertices.update((parent, child))
        if child not in children[parent]:
            children[parent].add(child)
            incoming[child] += 1
            incoming.setdefault(parent, 0)
    ready = deque(sorted(vertex for vertex in vertices if incoming[vertex] == 0))
    removed = 0
    while ready:
        vertex = ready.popleft()
        removed += 1
        for child in sorted(children.get(vertex, ())):
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    return len(vertices) - removed


def choose_pair(parent: int, children: list[dict[str, int]]) -> dict[str, int]:
    ranked = sorted(
        children,
        key=lambda item: (
            hashlib.sha256(f"{RANK_DOMAIN}|{parent}|{item['child_kernel_id']}".encode()).hexdigest(),
            item["child_kernel_id"],
        ),
    )
    left, right = ranked[:2]
    flip = hashlib.sha256(
        f"{ORDER_DOMAIN}|{parent}|{left['child_kernel_id']}|{right['child_kernel_id']}".encode()
    ).digest()[0] % 2
    if flip:
        left, right = right, left
    return {
        "parent_version_id": parent,
        "competition_id": left["competition_id"],
        "child_a_kernel_id": left["child_kernel_id"],
        "child_a_first_version_id": left["child_first_version_id"],
        "child_b_kernel_id": right["child_kernel_id"],
        "child_b_first_version_id": right["child_first_version_id"],
    }


def rebuild(
    kernels_path: Path,
    versions_path: Path,
    links_path: Path,
    competitions_path: Path,
    scratch_root: Path,
) -> tuple[dict[str, Any], list[dict[str, int]]]:
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="meta-kaggle-s0b-verifier-", dir=scratch_root) as name:
        temporary = Path(name)
        kernel_counts, fork_rows, required_versions = read_kernels(kernels_path, temporary)
        version_counts, versions = read_versions(versions_path, required_versions, temporary)
    link_counts, links = read_links(links_path, required_versions)
    required_competitions = {identifier for values in links.values() for identifier in values}
    competition_counts, competitions = read_competitions(competitions_path, required_competitions)

    failures: Counter[str] = Counter()
    valid_edges: list[dict[str, int]] = []
    directed: list[tuple[int, int]] = []
    parent_matches = 0
    for child_kernel, (first_id, parent_id) in fork_rows.items():
        child = versions.get(first_id)
        parent = versions.get(parent_id)
        if child is None:
            failures["child_first_version_missing"] += 1
        if parent is None:
            failures["parent_version_missing"] += 1
        if child is not None and child[1] == parent_id:
            parent_matches += 1
        else:
            failures["direct_parent_field_mismatch"] += 1
        valid = child is not None and parent is not None
        if child is not None:
            if child[0] != child_kernel:
                failures["child_first_script_mismatch"] += 1
                valid = False
            if child[3] != 1:
                failures["child_not_version_one"] += 1
                valid = False
            if child[1] != parent_id:
                valid = False
        if parent is not None:
            if parent[0] is None:
                failures["parent_script_missing"] += 1
                valid = False
            elif parent[0] == child_kernel:
                failures["parent_child_same_script"] += 1
                valid = False
        if child is None or parent is None or child[2] is None or parent[2] is None:
            failures["creation_time_missing"] += 1
            valid = False
        elif child[2] <= parent[2]:
            failures["parent_child_time_order_invalid"] += 1
            valid = False
        if valid:
            directed.append((parent_id, first_id))
            valid_edges.append(
                {
                    "parent_version_id": parent_id,
                    "child_kernel_id": child_kernel,
                    "child_first_version_id": first_id,
                }
            )

    cycle_count = cyclic_nodes(directed)
    failures["cycle_nodes"] = cycle_count
    children_by_parent: dict[int, list[dict[str, int]]] = defaultdict(list)
    for edge in valid_edges:
        parent_sources = links.get(edge["parent_version_id"], set())
        child_sources = links.get(edge["child_first_version_id"], set())
        if len(parent_sources) != 1:
            failures["parent_competition_not_singleton"] += 1
            continue
        if len(child_sources) != 1:
            failures["child_competition_not_singleton"] += 1
            continue
        if parent_sources != child_sources:
            failures["parent_child_competition_mismatch"] += 1
            continue
        competition = next(iter(parent_sources))
        if competition not in competitions:
            failures["competition_record_missing"] += 1
            continue
        if not competitions[competition]:
            failures["competition_not_closed_verified"] += 1
            continue
        children_by_parent[edge["parent_version_id"]].append({**edge, "competition_id": competition})

    pairs: list[dict[str, int]] = []
    for parent in sorted(children_by_parent):
        children = children_by_parent[parent]
        identities = {child["child_kernel_id"] for child in children}
        if len(identities) < 2:
            continue
        demand(len(identities) == len(children), "duplicate child in selected parent")
        pairs.append(choose_pair(parent, children))

    by_competition = Counter(pair["competition_id"] for pair in pairs)
    dominant = max(by_competition.values(), default=0) / len(pairs) if pairs else None
    explicit = kernel_counts.get("explicit_fork_rows", 0)
    agreement = parent_matches / explicit if explicit else None
    identity = {
        "kernel_ids_globally_unique": kernel_counts.get("duplicate_id", 0) == 0,
        "kernel_ids_well_formed": kernel_counts.get("malformed_id", 0) == 0,
        "kernel_version_ids_globally_unique": version_counts.get("duplicate_id", 0) == 0,
        "kernel_version_ids_well_formed": version_counts.get("malformed_id", 0) == 0,
        "relevant_competition_ids_unique": competition_counts.get("duplicate_relevant_id", 0) == 0,
        "selected_graph_acyclic": cycle_count == 0,
        "direct_parent_field_agreement_rate_ge_0_95": bool(agreement is not None and agreement >= 0.95),
        "selected_pair_identity_complete": all(
            pair["child_a_kernel_id"] != pair["child_b_kernel_id"]
            and pair["parent_version_id"] > 0
            and pair["competition_id"] > 0
            for pair in pairs
        ),
    }
    support = {
        "canonical_pairs_ge_500": len(pairs) >= 500,
        "distinct_parents_ge_100": len({pair["parent_version_id"] for pair in pairs}) >= 100,
        "completed_competitions_ge_20": len(by_competition) >= 20,
        "dominant_competition_share_le_0_20": bool(dominant is not None and dominant <= 0.20),
    }
    state = (
        "IDENTITY_UNAVAILABLE"
        if not all(identity.values())
        else "INSUFFICIENT_EXACT_PARENT_SUPPORT"
        if not all(support.values())
        else "EXACT_PARENT_STRUCTURE_SUPPORT_FEASIBLE"
    )
    summary = {
        "protocol": PRODUCER_PROTOCOL,
        "status": state,
        "snapshot_cutoff_utc": CUTOFF.isoformat().replace("+00:00", "Z"),
        "thresholds": {
            "direct_parent_agreement_rate_ge": 0.95,
            "canonical_pairs_ge": 500,
            "distinct_parents_ge": 100,
            "completed_competitions_ge": 20,
            "dominant_competition_share_le": 0.20,
        },
        "inventory": {
            "kernels": kernel_counts,
            "kernel_versions": version_counts,
            "competition_links": link_counts,
            "competitions": competition_counts,
            "parsed_explicit_fork_edges": len(fork_rows),
            "base_valid_fork_edges": len(valid_edges),
            "eligible_closed_competition_children": sum(map(len, children_by_parent.values())),
            "eligible_parent_groups": len(children_by_parent),
            "canonical_pairs": len(pairs),
            "completed_competitions_in_pairs": len(by_competition),
            "dominant_competition_share": dominant,
            "direct_parent_field_matches": parent_matches,
            "direct_parent_field_agreement_rate": agreement,
            "edge_failures": dict(sorted(failures.items())),
            "pairs_per_competition": {str(key): value for key, value in sorted(by_competition.items())},
        },
        "identity_criteria": identity,
        "support_criteria": support,
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


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def verify_sources(repo: Path, commit: str) -> dict[str, str]:
    demand(git(repo, "rev-parse", "HEAD") == commit, "checked-out commit mismatch")
    result: dict[str, str] = {}
    for relative in REGISTERED:
        demand(
            git(repo, "hash-object", relative) == git(repo, "rev-parse", f"{commit}:{relative}"),
            f"registered source differs from commit: {relative}",
        )
        result[relative] = digest(repo / relative)
    return result


def load_json(path: Path) -> Any:
    def unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            demand(key not in result, f"duplicate JSON key: {path.name}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def arguments() -> argparse.Namespace:
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
    parser.add_argument("--producer-dir", type=Path, required=True)
    parser.add_argument("--expect-producer-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    repo = args.repo_root.resolve()
    source_hashes = verify_sources(repo, args.source_commit)
    inputs = {
        "protocol": digest(args.protocol.resolve()),
        "kernels": digest(args.kernels.resolve()),
        "kernel_versions": digest(args.kernel_versions.resolve()),
        "competition_links": digest(args.competition_links.resolve()),
        "competitions": digest(args.competitions.resolve()),
    }
    expected_inputs = {
        "protocol": args.expect_protocol_sha256,
        "kernels": args.expect_kernels_sha256,
        "kernel_versions": args.expect_kernel_versions_sha256,
        "competition_links": args.expect_competition_links_sha256,
        "competitions": args.expect_competitions_sha256,
    }
    demand(inputs == expected_inputs, "input hash mismatch")

    producer_dir = args.producer_dir.resolve()
    manifest_path = producer_dir / "sha256_manifest.json"
    demand(digest(manifest_path) == args.expect_producer_manifest_sha256, "producer manifest hash mismatch")
    manifest = load_json(manifest_path)
    demand(isinstance(manifest, dict), "producer manifest root malformed")
    demand(set(manifest) == {"canonical_pairs.jsonl", "summary.json"}, "producer manifest files differ")
    for name, expected in manifest.items():
        demand(digest(producer_dir / name) == expected, f"producer artifact hash mismatch: {name}")

    summary, pairs = rebuild(
        args.kernels.resolve(),
        args.kernel_versions.resolve(),
        args.competition_links.resolve(),
        args.competitions.resolve(),
        args.scratch_root.resolve(),
    )
    summary["source_commit"] = args.source_commit
    summary["source_sha256"] = source_hashes
    summary["input_sha256"] = inputs
    demand(load_json(producer_dir / "summary.json") == summary, "producer summary differs from reconstruction")
    pair_bytes = b"".join(
        json.dumps(pair, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
        for pair in pairs
    )
    demand((producer_dir / "canonical_pairs.jsonl").read_bytes() == pair_bytes, "canonical pairs differ")

    verification = {
        "protocol": VERIFIER_PROTOCOL,
        "verified": True,
        "verified_status": summary["status"],
        "kernels_rescanned": summary["inventory"]["kernels"]["rows"],
        "kernel_versions_rescanned": summary["inventory"]["kernel_versions"]["rows"],
        "competition_links_rescanned": summary["inventory"]["competition_links"]["rows"],
        "competitions_rescanned": summary["inventory"]["competitions"]["rows"],
        "canonical_pairs_rebuilt": len(pairs),
        "producer_manifest_sha256": digest(manifest_path),
    }
    args.output.resolve().write_bytes(stable_json(verification))
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
