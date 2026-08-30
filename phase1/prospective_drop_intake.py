"""Create a label-separated prospective scorer manifest directly from senior tar drops.

The intake never extracts or reads ``env_variables.json``.  It streams only completed
AIRA-Dojo journal members, scans their raw bytes for credential shapes before JSON parsing,
derives physical-run start time from the root node's ``creation_time``, and writes separate
blind and label-vault artifacts.  No metric is computed here.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import itertools
import json
import math
import os
import platform
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .build_cards import TASK_TYPE
from .cards import TaskInfo, parse_journal_nodes
from .endpoint_denylist import (
    PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
    PRECUTOFF_ENDPOINTS,
    load_endpoint_denylist,
)


PROTOCOL = "prospective_drop_intake_v1"
ARCHIVE_CONSENSUS_PROTOCOL = "prospective-intake-archive-consensus-fallback-v1"
ARCHIVE_CONSENSUS_PROTOCOL_SHA256 = (
    "3110da4403fa0477454d8e1415fd23e9a7a7482694b778784c9d5270b8e4993e"
)
ARCHIVE_CONSENSUS_PROTOCOL_PATH = Path(
    "phase1/prospective_intake_archive_consensus_fallback_v1.json"
)
ARCHIVE_SEED_SUFFIX = re.compile(r"^(?P<stem>.+)-[0-9]+seeds\.tar\.gz$")
NON_ASCII_ALNUM = re.compile(r"[^a-z0-9]+")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)
BLIND_KEYS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "generation_started_at_utc",
    "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}


class IntakeError(RuntimeError):
    pass


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def parse_utc(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise IntakeError(f"invalid timestamp: {value!r}") from error
    if parsed.tzinfo is None:
        raise IntakeError("timestamp must include timezone")
    return parsed.astimezone(dt.timezone.utc)


def utc_from_epoch(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IntakeError("root creation_time must be numeric")
    timestamp = float(value)
    if not math.isfinite(timestamp):
        raise IntakeError("root creation_time must be finite")
    try:
        parsed = dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise IntakeError("root creation_time is outside datetime range") from error
    return parsed.isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> str:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    os.replace(temporary, path)
    return sha256(path)


def safe_member_path(member: tarfile.TarInfo) -> PurePosixPath:
    if "\\" in member.name or "\x00" in member.name:
        raise IntakeError("unsafe tar member spelling")
    pure = PurePosixPath(member.name)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise IntakeError("unsafe tar member path")
    if member.issym() or member.islnk() or member.isdev() or member.isfifo():
        raise IntakeError("unsafe tar member type")
    return pure


def journal_role(pure: PurePosixPath) -> tuple[str, str] | None:
    if len(pure.parts) >= 3 and pure.parts[-2:] == ("checkpoint", "journal.jsonl"):
        return "/".join(pure.parts[:-2]), "checkpoint"
    if len(pure.parts) >= 3 and pure.parts[-2:] == ("json", "JOURNAL.jsonl"):
        return "/".join(pure.parts[:-2]), "live"
    return None


def read_member(
    handle: tarfile.TarFile,
    member: tarfile.TarInfo,
    max_member_bytes: int,
) -> bytes:
    if member.size < 0 or member.size > max_member_bytes:
        raise IntakeError(f"journal size outside cap: {member.name}")
    source = handle.extractfile(member)
    if source is None:
        raise IntakeError(f"journal member unreadable: {member.name}")
    blob = source.read(max_member_bytes + 1)
    if len(blob) != member.size or len(blob) > max_member_bytes:
        raise IntakeError(f"journal size/read mismatch: {member.name}")
    if CREDENTIAL.search(blob):
        raise IntakeError(f"credential-shaped journal refused before JSON parse: {member.name}")
    return blob


def journals_from_archive(
    archive: Path,
    max_member_bytes: int,
    max_members: int,
    max_total_member_bytes: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    selected: list[dict[str, Any]] = []
    with tarfile.open(archive, "r|gz") as handle:
        grouped: dict[str, set[str]] = collections.defaultdict(set)
        member_count = 0
        total_member_bytes = 0
        for member in handle:
            member_count += 1
            total_member_bytes += max(0, member.size)
            if member_count > max_members:
                raise IntakeError(f"archive exceeds member-count cap: {archive.name}")
            if total_member_bytes > max_total_member_bytes:
                raise IntakeError(f"archive exceeds declared-byte cap: {archive.name}")
            pure = safe_member_path(member)
            role = journal_role(pure)
            if role is not None and member.isfile():
                root, kind = role
                if kind in grouped[root]:
                    raise IntakeError(f"duplicate {kind} journal member for run {root}")
                grouped[root].add(kind)
                if kind == "checkpoint":
                    selected.append(
                        {
                            "run_source_path": root,
                            "journal_member": member.name,
                            "journal_mtime": int(member.mtime),
                            "blob": read_member(handle, member, max_member_bytes),
                        }
                    )
        if not grouped:
            raise IntakeError(f"archive has no supported journal members: {archive.name}")
        audit = {
            "discovered_run_roots": len(grouped),
            "checkpoint_runs": sum("checkpoint" in candidates for candidates in grouped.values()),
            "checkpoint_with_live_event_log": sum(
                set(candidates) == {"checkpoint", "live"} for candidates in grouped.values()
            ),
            "checkpoint_without_live_event_log": sum(
                set(candidates) == {"checkpoint"} for candidates in grouped.values()
            ),
            "live_only_runs_excluded": sum(
                set(candidates) == {"live"} for candidates in grouped.values()
            ),
            "members": member_count,
            "declared_member_bytes": total_member_bytes,
        }
    selected.sort(key=lambda item: (item["run_source_path"], item["journal_member"]))
    return selected, audit


def parse_journal_rows(blob: bytes) -> list[dict[str, Any]]:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as error:
        raise IntakeError("journal is not UTF-8") from error
    nodes: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise IntakeError(f"invalid journal JSON at line {line_number}") from error
        if not isinstance(value, dict):
            raise IntakeError(f"journal row is not an object at line {line_number}")
        nodes.append(value)
    if not nodes:
        raise IntakeError("empty journal")
    return nodes


def competition_ids(nodes: list[dict[str, Any]]) -> set[str]:
    competitions: set[str] = set()
    for node in nodes:
        metric_info = node.get("metric_info") or {}
        if not isinstance(metric_info, dict):
            raise IntakeError("journal metric_info must be an object")
        competition = metric_info.get("competition_id")
        if competition:
            competitions.add(str(competition))
    return competitions


def normalize_competition(value: str) -> str:
    return NON_ASCII_ALNUM.sub("-", value.casefold()).strip("-")


def resolve_archive_consensus(
    sources: list[dict[str, Any]],
    archive_name: str,
    *,
    explicitly_selected_single_archive: bool,
    repo_root: Path,
) -> tuple[str | None, dict[str, Any]]:
    """Resolve a missing journal task only under the frozen one-archive consensus rule."""
    per_journal: list[set[str]] = []
    for source in sources:
        identifiers = competition_ids(parse_journal_rows(source["blob"]))
        if len(identifiers) > 1:
            raise IntakeError("journal identifies more than one competition")
        per_journal.append(identifiers)

    explicit_journals = sum(bool(identifiers) for identifiers in per_journal)
    missing_journals = len(per_journal) - explicit_journals
    audit: dict[str, Any] = {
        "competition_id_explicit_journals": explicit_journals,
        "competition_id_archive_consensus_fallback_journals": 0,
        "archive_consensus_fallback_used": False,
    }
    if missing_journals == 0:
        return None, audit
    if not explicitly_selected_single_archive:
        raise IntakeError(
            "missing competition requires one explicitly selected immutable archive"
        )
    if explicit_journals == 0:
        raise IntakeError("archive consensus requires at least one explicit competition")

    exact_union = set().union(*per_journal)
    if len(exact_union) != 1:
        raise IntakeError("archive consensus requires exactly one explicit competition")
    normalized_union = {normalize_competition(value) for value in exact_union}
    if "" in normalized_union or len(normalized_union) != 1:
        raise IntakeError("archive consensus normalized competition is not unique")

    suffix_match = ARCHIVE_SEED_SUFFIX.fullmatch(archive_name)
    if suffix_match is None:
        raise IntakeError("archive consensus requires a -Nseeds.tar.gz filename")
    archive_stem = normalize_competition(suffix_match.group("stem"))
    if archive_stem != next(iter(normalized_union)):
        raise IntakeError("archive consensus competition does not match archive stem")

    protocol_path = repo_root / ARCHIVE_CONSENSUS_PROTOCOL_PATH
    if not protocol_path.is_file() or sha256(protocol_path) != ARCHIVE_CONSENSUS_PROTOCOL_SHA256:
        raise IntakeError("archive consensus frozen protocol SHA mismatch")

    audit["competition_id_archive_consensus_fallback_journals"] = missing_journals
    audit["archive_consensus_fallback_used"] = True
    return next(iter(exact_union)), audit


def decode_journal(
    blob: bytes,
    archive_consensus: str | None = None,
) -> tuple[list[dict[str, Any]], str, str, str]:
    nodes = parse_journal_rows(blob)

    steps = [node.get("step") for node in nodes]
    if any(isinstance(step, bool) or not isinstance(step, int) for step in steps):
        raise IntakeError("journal steps must be integers")
    if len(set(steps)) != len(steps):
        raise IntakeError("duplicate journal step")
    step_set = set(steps)
    for node in nodes:
        parents = node.get("parents") or []
        if not isinstance(parents, list) or any(
            isinstance(parent, bool) or not isinstance(parent, int) for parent in parents
        ):
            raise IntakeError("journal parents must be integer step lists")
        if any(parent not in step_set or parent == node["step"] for parent in parents):
            raise IntakeError("journal contains missing or self parent")
        if node["step"] == 0 and parents:
            raise IntakeError("step-0 root must not have parents")
        if node["step"] != 0 and len(parents) != 1:
            raise IntakeError("every non-root node must have exactly one parent")
        if any(parent >= node["step"] for parent in parents):
            raise IntakeError("journal parent step must precede child step")
    roots = [node for node in nodes if node.get("step") == 0 and not (node.get("parents") or [])]
    if len(roots) != 1:
        raise IntakeError("journal must have exactly one step-0 root")
    started = utc_from_epoch(roots[0].get("creation_time"))
    started_epoch = parse_utc(started).timestamp()
    now_epoch = dt.datetime.now(dt.timezone.utc).timestamp()
    for node in nodes:
        creation = node.get("creation_time")
        if isinstance(creation, bool) or not isinstance(creation, (int, float)):
            raise IntakeError("every journal node must have numeric creation_time")
        if not math.isfinite(float(creation)) or float(creation) + 1e-6 < started_epoch:
            raise IntakeError("journal creation_time precedes run root")
        if float(creation) > now_epoch + 300:
            raise IntakeError("journal creation_time is implausibly in the future")

    competitions = competition_ids(nodes)
    if len(competitions) > 1:
        raise IntakeError("journal identifies more than one competition")
    if competitions:
        return nodes, next(iter(competitions)), started, "explicit_journal"
    if archive_consensus is None:
        raise IntakeError("journal must identify exactly one competition")
    return nodes, archive_consensus, started, "archive_consensus_fallback"


def finite_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def run_payload(
    source: dict[str, Any],
    archive_name: str,
    archive_sha: str,
    activated_at: dt.datetime,
    archive_consensus: str | None = None,
) -> dict[str, Any]:
    blob = source["blob"]
    journal_sha = sha256_bytes(blob)
    nodes, competition, started, competition_id_source = decode_journal(
        blob, archive_consensus
    )
    if source["journal_mtime"] + 300 < parse_utc(started).timestamp():
        raise IntakeError("journal member mtime predates root creation_time")
    task = TaskInfo(
        name=competition,
        type=TASK_TYPE.get(competition, "tabular"),
        metric="",
        desc=competition,
    )
    parsed_cards = parse_journal_nodes(nodes, task)
    cards = [card for card in parsed_cards if str(card.code or "")]
    run_id = f"journal:{journal_sha}"
    eligible = parse_utc(started) > activated_at
    blind_rows: list[dict[str, Any]] = []
    vault_rows: list[dict[str, Any]] = []
    for card in cards:
        code = str(card.code or "")
        lineage = card.lineage
        view = {
            "card_id": str(card.id),
            "task": competition,
            "run_id": run_id,
            "code": code,
            "code_sha256": sha256_bytes(code.encode("utf-8")),
            "lineage": {
                "parent": "" if lineage.parent_id is None else str(lineage.parent_id),
                "depth": lineage.tree_depth,
                "step": lineage.step,
                "n_siblings": lineage.n_siblings,
                "op": lineage.op,
            },
            "generation_started_at_utc": started,
            "source_sha256": journal_sha,
        }
        if set(view) != BLIND_KEYS or set(view["lineage"]) != LINEAGE_KEYS:
            raise IntakeError("internal blind schema mismatch")
        label = card.label
        vault_rows.append(
            {
                "card_id": str(card.id),
                "task": competition,
                "run_id": run_id,
                "graded": finite_or_none(label.graded if label else None),
                "y_norm": finite_or_none(label.y_norm if label else None),
                "eligible_by_start_time": eligible,
            }
        )
        blind_rows.append(view)
    return {
        "run_id": run_id,
        "task": competition,
        "generation_started_at_utc": started,
        "eligible": eligible,
        "archive_name": archive_name,
        "archive_sha256": archive_sha,
        "journal_member": source["journal_member"],
        "journal_mtime": source["journal_mtime"],
        "journal_sha256": journal_sha,
        "competition_id_source": competition_id_source,
        "flow_status": "scoreable" if cards else "no_scoreable_code",
        "endpoints": len(cards),
        "empty_code_nodes_excluded": len(parsed_cards) - len(cards),
        "blind_rows": blind_rows,
        "vault_rows": vault_rows,
    }


def structural_pairs(blind_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    for row in blind_rows:
        parent = str(row["lineage"]["parent"])
        if parent:
            grouped[(str(row["task"]), str(row["run_id"]), parent)].append(str(row["card_id"]))
    output = []
    for (task, run_id, parent), card_ids in sorted(grouped.items()):
        for left, right in itertools.combinations(sorted(set(card_ids)), 2):
            output.append(
                {"task": task, "run_id": run_id, "parent": parent, "left": left, "right": right}
            )
    return output


def select_archives(drop_dir: Path, requested_names: list[str] | None) -> list[Path]:
    """Resolve either the whole flat drop or an explicit immutable archive subset."""
    if requested_names is None:
        return sorted(drop_dir.glob("*.tar.gz"), key=lambda path: path.name)
    if not requested_names:
        raise IntakeError("explicit archive selection must be non-empty")
    if len(set(requested_names)) != len(requested_names):
        raise IntakeError("explicit archive names must be unique")
    archives: list[Path] = []
    for name in sorted(requested_names):
        if (
            not isinstance(name, str)
            or not name.endswith(".tar.gz")
            or name in {".tar.gz", "..tar.gz"}
            or "/" in name
            or "\\" in name
            or "\x00" in name
            or any(character in name for character in "\t\r\n")
        ):
            raise IntakeError("explicit archive name must be a safe tar.gz basename")
        path = drop_dir / name
        if not path.exists():
            raise IntakeError(f"explicit archive is missing: {name}")
        archives.append(path)
    return archives


def build(args: argparse.Namespace) -> int:
    drop_dir = args.drop_dir.resolve()
    out_dir = args.out_dir.resolve()
    if not drop_dir.is_dir():
        raise IntakeError("drop directory does not exist")
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite intake output: {out_dir}")
    if out_dir == drop_dir or drop_dir in out_dir.parents:
        raise IntakeError("output directory must be outside the immutable source drop")
    caps = (
        args.max_archive_bytes,
        args.max_total_archive_bytes,
        args.max_member_bytes,
        args.max_members_per_archive,
        args.max_total_member_bytes_per_archive,
        args.max_total_journal_bytes,
        args.max_archives,
        getattr(args, "_expect_precutoff_endpoints", PRECUTOFF_ENDPOINTS),
    )
    if any(value <= 0 for value in caps):
        raise IntakeError("resource caps must be positive")
    receipt_sha = sha256(args.freeze_receipt)
    if receipt_sha != args.expect_freeze_receipt_sha256.lower():
        raise IntakeError("freeze receipt SHA mismatch")
    receipt = json.loads(args.freeze_receipt.read_text(encoding="utf-8"))
    if (
        receipt.get("status") != "PROSPECTIVE_SCORER_ACTIVE"
        or receipt.get("protocol") != "prospective_decision_v1"
    ):
        raise IntakeError("prospective scorer is not active")
    activated_at = parse_utc(str(receipt["activated_at_utc"]))
    precutoff_ids, precutoff_code_shas, precutoff_audit = load_endpoint_denylist(
        args.precutoff_endpoint_denylist,
        getattr(
            args,
            "_expect_precutoff_endpoint_denylist_sha256",
            PRECUTOFF_ENDPOINT_DENYLIST_SHA256,
        ),
        getattr(args, "_expect_precutoff_endpoints", PRECUTOFF_ENDPOINTS),
    )

    requested_names = getattr(args, "archive_name", None)
    archives = select_archives(drop_dir, requested_names)
    if not archives:
        raise IntakeError("drop has no tar.gz archives")
    if len(archives) > args.max_archives:
        raise IntakeError("drop exceeds archive-count cap")
    if any("\t" in path.name or "\n" in path.name or "\r" in path.name for path in archives):
        raise IntakeError("archive filename contains control whitespace")
    if any(
        path.parent != drop_dir
        or path.is_symlink()
        or not path.is_file()
        or path.resolve().parent != drop_dir
        for path in archives
    ):
        raise IntakeError("archive inventory is not flat")
    archive_sizes = [path.stat().st_size for path in archives]
    if any(size > args.max_archive_bytes for size in archive_sizes):
        raise IntakeError("drop contains archive above byte cap")
    if sum(archive_sizes) > args.max_total_archive_bytes:
        raise IntakeError("drop exceeds total archive-byte cap")
    archive_records = [
        {"name": path.name, "size": path.stat().st_size, "sha256": sha256(path), "path": path}
        for path in archives
    ]
    archive_hashes = [record["sha256"] for record in archive_records]
    if len(set(archive_hashes)) != len(archive_hashes):
        raise IntakeError("duplicate archive bytes require explicit curation")

    runs: list[dict[str, Any]] = []
    journal_hashes: set[str] = set()
    total_journal_bytes = 0
    archive_audits: list[dict[str, Any]] = []
    explicitly_selected_single_archive = requested_names is not None and len(archives) == 1
    for record in archive_records:
        if sha256(record["path"]) != record["sha256"]:
            raise IntakeError("archive changed after inventory freeze")
        sources, archive_audit = journals_from_archive(
            record["path"],
            args.max_member_bytes,
            args.max_members_per_archive,
            args.max_total_member_bytes_per_archive,
        )
        archive_consensus, consensus_audit = resolve_archive_consensus(
            sources,
            record["name"],
            explicitly_selected_single_archive=explicitly_selected_single_archive,
            repo_root=args.repo_root,
        )
        archive_audits.append(
            {"archive_name": record["name"], **archive_audit, **consensus_audit}
        )
        for source in sources:
            total_journal_bytes += len(source["blob"])
            if total_journal_bytes > args.max_total_journal_bytes:
                raise IntakeError("drop exceeds total-journal-byte cap")
            run = run_payload(
                source,
                record["name"],
                record["sha256"],
                activated_at,
                archive_consensus,
            )
            if run["journal_sha256"] in journal_hashes:
                raise IntakeError("duplicate source journal across archives")
            journal_hashes.add(run["journal_sha256"])
            runs.append(run)
        if sha256(record["path"]) != record["sha256"]:
            raise IntakeError("archive changed during intake")
    if not runs:
        raise IntakeError("drop produced no physical runs")

    all_blind = [row for run in runs for row in run["blind_rows"]]
    all_vault = [row for run in runs for row in run["vault_rows"]]
    eligible_runs = {run["run_id"] for run in runs if run["eligible"]}
    eligible_blind = [row for row in all_blind if row["run_id"] in eligible_runs]
    card_ids = [row["card_id"] for row in all_blind]
    if len(set(card_ids)) != len(card_ids):
        raise IntakeError("card ID collision across physical runs")
    if {row["card_id"] for row in all_vault} != set(card_ids):
        raise IntakeError("blind/vault card support mismatch")
    id_overlap = sorted(set(card_ids) & precutoff_ids)
    code_overlap = sorted({row["code_sha256"] for row in all_blind} & precutoff_code_shas)
    if id_overlap or code_overlap:
        raise IntakeError(
            f"pre-cutoff endpoint/code overlap: ids={len(id_overlap)} code_sha256={len(code_overlap)}"
        )
    all_blind.sort(key=lambda row: row["card_id"])
    eligible_blind.sort(key=lambda row: row["card_id"])
    all_vault.sort(key=lambda row: row["card_id"])
    all_pairs = structural_pairs(all_blind)
    eligible_pairs = [row for row in all_pairs if row["run_id"] in eligible_runs]

    temporary = out_dir.with_name(f"{out_dir.name}.tmp.{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"temporary output already exists: {temporary}")
    temporary.mkdir(parents=True)
    archive_manifest = temporary / "archive_manifest.tsv"
    with archive_manifest.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("name", "size", "sha256"), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for record in archive_records:
            writer.writerow({key: record[key] for key in ("name", "size", "sha256")})
    provenance = [
        {key: run[key] for key in (
            "run_id",
            "task",
            "generation_started_at_utc",
            "eligible",
            "archive_name",
            "archive_sha256",
            "journal_member",
            "journal_mtime",
            "journal_sha256",
            "competition_id_source",
            "flow_status",
            "endpoints",
            "empty_code_nodes_excluded",
        )}
        for run in sorted(runs, key=lambda item: (
            item["generation_started_at_utc"], item["journal_sha256"], item["run_id"]
        ))
    ]
    atomic_json(temporary / "source_provenance.json", provenance)
    atomic_json(temporary / "archive_audits.json", archive_audits)
    all_blind_sha = write_jsonl(temporary / "all_blind_views.jsonl", all_blind)
    eligible_sha = write_jsonl(temporary / "eligible_blind_manifest.jsonl", eligible_blind)
    vault_sha = write_jsonl(temporary / "label_vault.jsonl", all_vault)
    os.chmod(temporary / "label_vault.jsonl", 0o600)
    pair_sha = write_jsonl(temporary / "structural_pairs.jsonl", all_pairs)
    eligible_pair_sha = write_jsonl(temporary / "eligible_structural_pairs.jsonl", eligible_pairs)
    summary = {
        "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
        "protocol": PROTOCOL,
        "git_commit": git_commit(args.repo_root),
        "source_sha256": sha256(Path(__file__)),
        "activated_at_utc": receipt["activated_at_utc"],
        "selection_rule": "physical run root creation_time strictly after scorer activation",
        "inputs": {
            "drop_dir": str(drop_dir),
            "freeze_receipt_sha256": receipt_sha,
            "precutoff_endpoint_denylist_sha256": sha256(args.precutoff_endpoint_denylist),
            "archive_manifest_sha256": sha256(archive_manifest),
        },
        "inventory": {
            "archives": len(archives),
            "discovered_run_roots": sum(item["discovered_run_roots"] for item in archive_audits),
            "runs": len(runs),
            "live_only_runs_excluded": sum(item["live_only_runs_excluded"] for item in archive_audits),
            "tasks": len({run["task"] for run in runs}),
            "endpoints": len(all_blind),
            "structural_pairs": len(all_pairs),
            "eligible_runs": len(eligible_runs),
            "eligible_tasks": len({run["task"] for run in runs if run["eligible"]}),
            "eligible_endpoints": len(eligible_blind),
            "eligible_structural_pairs": len(eligible_pairs),
            "no_scoreable_code_runs": sum(
                run["flow_status"] == "no_scoreable_code" for run in runs
            ),
            "empty_code_nodes_excluded": sum(run["empty_code_nodes_excluded"] for run in runs),
            "archive_consensus_fallback_runs": sum(
                run["competition_id_source"] == "archive_consensus_fallback" for run in runs
            ),
        },
        "outputs": {
            "all_blind_views_sha256": all_blind_sha,
            "eligible_blind_manifest_sha256": eligible_sha,
            "label_vault_sha256": vault_sha,
            "structural_pairs_sha256": pair_sha,
            "eligible_structural_pairs_sha256": eligible_pair_sha,
            "source_provenance_sha256": sha256(temporary / "source_provenance.json"),
            "archive_audits_sha256": sha256(temporary / "archive_audits.json"),
        },
        "security": {
            "env_members_read": False,
            "env_members_extracted": False,
            "live_event_journal_members_read": False,
            "journal_scanned_before_json": True,
            "credential_shaped_journals": 0,
            "raw_journals_written": False,
            "precutoff_endpoint_ids_checked": precutoff_audit["endpoint_ids"],
            "precutoff_code_sha256_checked": precutoff_audit["unique_code_sha256"],
            "precutoff_endpoint_id_overlap": 0,
            "precutoff_code_sha256_overlap": 0,
        },
        "blindness": {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
            "label_values_printed": False,
            "metrics_computed": [],
        },
        "configuration": {
            "archive_selection": "all_in_drop_dir" if requested_names is None else "explicit_names",
            "selected_archive_names": [path.name for path in archives],
            "archive_consensus_fallback_protocol": ARCHIVE_CONSENSUS_PROTOCOL,
            "archive_consensus_fallback_protocol_sha256": (
                ARCHIVE_CONSENSUS_PROTOCOL_SHA256
            ),
            "max_archives": args.max_archives,
            "max_archive_bytes": args.max_archive_bytes,
            "max_total_archive_bytes": args.max_total_archive_bytes,
            "max_member_bytes": args.max_member_bytes,
            "max_members_per_archive": args.max_members_per_archive,
            "max_total_member_bytes_per_archive": args.max_total_member_bytes_per_archive,
            "max_total_journal_bytes": args.max_total_journal_bytes,
        },
        "software": {"python": platform.python_version(), "platform": platform.platform()},
    }
    atomic_json(temporary / "summary.json", summary)
    os.replace(temporary, out_dir)
    print(
        summary["status"],
        f"runs={len(runs)}",
        f"eligible_runs={len(eligible_runs)}",
        f"eligible_endpoints={len(eligible_blind)}",
        "env_members_read=false",
        "label_values_printed=false",
        flush=True,
    )
    return 0


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop-dir", required=True, type=Path)
    parser.add_argument(
        "--archive-name",
        action="append",
        help="safe tar.gz basename to ingest; repeat for an explicit immutable subset",
    )
    parser.add_argument("--freeze-receipt", required=True, type=Path)
    parser.add_argument("--precutoff-endpoint-denylist", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--expect-freeze-receipt-sha256", required=True)
    parser.add_argument("--max-archive-bytes", type=int, default=64 * 1024 * 1024 * 1024)
    parser.add_argument("--max-total-archive-bytes", type=int, default=512 * 1024 * 1024 * 1024)
    parser.add_argument("--max-member-bytes", type=int, default=512 * 1024 * 1024)
    parser.add_argument("--max-members-per-archive", type=int, default=1_000_000)
    parser.add_argument(
        "--max-total-member-bytes-per-archive", type=int, default=256 * 1024 * 1024 * 1024
    )
    parser.add_argument("--max-total-journal-bytes", type=int, default=4 * 1024 * 1024 * 1024)
    parser.add_argument("--max-archives", type=int, default=512)
    return parser.parse_args()


def main() -> int:
    return build(arguments())


if __name__ == "__main__":
    raise SystemExit(main())
