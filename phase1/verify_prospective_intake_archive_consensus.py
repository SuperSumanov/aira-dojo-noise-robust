#!/usr/bin/env python3
"""Independently verify one archive-consensus intake without emitting task identities."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any


PROTOCOL = "prospective-intake-archive-consensus-verification-v1"
FALLBACK_PROTOCOL = "prospective-intake-archive-consensus-fallback-v1"
FALLBACK_PROTOCOL_SHA256 = (
    "3110da4403fa0477454d8e1415fd23e9a7a7482694b778784c9d5270b8e4993e"
)
SHA_RX = re.compile(r"[0-9a-f]{64}")
SEED_SUFFIX = re.compile(r"^(?P<stem>.+)-[0-9]+seeds\.tar\.gz$")
NON_ASCII_ALNUM = re.compile(r"[^a-z0-9]+")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)


class ConsensusVerificationError(RuntimeError):
    pass


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path, *, object_only: bool = False) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConsensusVerificationError(f"cannot parse JSON artifact: {path.name}") from error
    if object_only and not isinstance(value, dict):
        raise ConsensusVerificationError(f"JSON artifact is not an object: {path.name}")
    return value


def normalize(value: str) -> str:
    return NON_ASCII_ALNUM.sub("-", value.casefold()).strip("-")


def safe_member(member: tarfile.TarInfo) -> PurePosixPath:
    if "\\" in member.name or "\x00" in member.name:
        raise ConsensusVerificationError("unsafe tar member spelling")
    pure = PurePosixPath(member.name)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise ConsensusVerificationError("unsafe tar member path")
    if member.issym() or member.islnk() or member.isdev() or member.isfifo():
        raise ConsensusVerificationError("unsafe tar member type")
    return pure


def checkpoint_identity(blob: bytes) -> set[str]:
    if CREDENTIAL.search(blob):
        raise ConsensusVerificationError("credential-shaped checkpoint journal")
    try:
        lines = blob.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ConsensusVerificationError("checkpoint journal is not UTF-8") from error
    identifiers: set[str] = set()
    rows = 0
    for line_number, line in enumerate(lines, 1):
        if not line:
            continue
        rows += 1
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ConsensusVerificationError(
                f"invalid checkpoint journal JSON at line {line_number}"
            ) from error
        if not isinstance(value, dict):
            raise ConsensusVerificationError("checkpoint journal row is not an object")
        metric_info = value.get("metric_info") or {}
        if not isinstance(metric_info, dict):
            raise ConsensusVerificationError("checkpoint metric_info is not an object")
        competition = metric_info.get("competition_id")
        if competition:
            identifiers.add(str(competition))
    if rows == 0:
        raise ConsensusVerificationError("empty checkpoint journal")
    if len(identifiers) > 1:
        raise ConsensusVerificationError("checkpoint journal has multiple competitions")
    return identifiers


def inspect_archive(archive: Path, max_member_bytes: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_roots: set[str] = set()
    with tarfile.open(archive, "r|gz") as handle:
        for member in handle:
            pure = safe_member(member)
            if not (
                member.isfile()
                and len(pure.parts) >= 3
                and pure.parts[-2:] == ("checkpoint", "journal.jsonl")
            ):
                continue
            root = "/".join(pure.parts[:-2])
            if root in seen_roots:
                raise ConsensusVerificationError("duplicate checkpoint journal for run")
            seen_roots.add(root)
            if member.size < 0 or member.size > max_member_bytes:
                raise ConsensusVerificationError("checkpoint journal exceeds byte cap")
            source = handle.extractfile(member)
            if source is None:
                raise ConsensusVerificationError("checkpoint journal is unreadable")
            blob = source.read(max_member_bytes + 1)
            if len(blob) != member.size or len(blob) > max_member_bytes:
                raise ConsensusVerificationError("checkpoint journal read-size mismatch")
            records.append(
                {
                    "journal_member": member.name,
                    "journal_sha256": sha256_bytes(blob),
                    "identifiers": checkpoint_identity(blob),
                }
            )
    if not records:
        raise ConsensusVerificationError("archive has no checkpoint journals")
    records.sort(key=lambda row: row["journal_member"])
    return records


def verify(
    archive: Path,
    expected_archive_sha256: str,
    intake_dir: Path,
    expected_intake_summary_sha256: str,
    max_member_bytes: int = 2 * 1024 * 1024 * 1024,
) -> dict[str, Any]:
    archive = archive.resolve()
    intake_dir = intake_dir.resolve()
    if (
        not archive.is_file()
        or archive.is_symlink()
        or not SHA_RX.fullmatch(expected_archive_sha256)
        or sha256(archive) != expected_archive_sha256
    ):
        raise ConsensusVerificationError("archive identity mismatch")
    if max_member_bytes <= 0:
        raise ConsensusVerificationError("member byte cap must be positive")

    summary_path = intake_dir / "summary.json"
    if (
        not SHA_RX.fullmatch(expected_intake_summary_sha256)
        or sha256(summary_path) != expected_intake_summary_sha256
    ):
        raise ConsensusVerificationError("intake summary identity mismatch")
    records = inspect_archive(archive, max_member_bytes)
    explicit = sum(bool(row["identifiers"]) for row in records)
    fallback = len(records) - explicit
    exact_union = set().union(*(row["identifiers"] for row in records))
    normalized_union = {normalize(value) for value in exact_union}
    suffix = SEED_SUFFIX.fullmatch(archive.name)
    if (
        fallback <= 0
        or explicit <= 0
        or len(exact_union) != 1
        or "" in normalized_union
        or len(normalized_union) != 1
        or suffix is None
        or normalize(suffix.group("stem")) != next(iter(normalized_union))
    ):
        raise ConsensusVerificationError("frozen archive-consensus rule is not satisfied")
    consensus = next(iter(exact_union))

    summary = read_json(summary_path, object_only=True)
    configuration = summary.get("configuration")
    inventory = summary.get("inventory")
    outputs = summary.get("outputs")
    if (
        not isinstance(configuration, dict)
        or not isinstance(inventory, dict)
        or not isinstance(outputs, dict)
        or configuration.get("archive_selection") != "explicit_names"
        or configuration.get("selected_archive_names") != [archive.name]
        or configuration.get("archive_consensus_fallback_protocol") != FALLBACK_PROTOCOL
        or configuration.get("archive_consensus_fallback_protocol_sha256")
        != FALLBACK_PROTOCOL_SHA256
        or inventory.get("runs") != len(records)
        or inventory.get("archive_consensus_fallback_runs") != fallback
    ):
        raise ConsensusVerificationError("intake summary consensus binding mismatch")

    with (intake_dir / "archive_manifest.tsv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        manifest = list(csv.DictReader(handle, delimiter="\t"))
    if (
        len(manifest) != 1
        or manifest[0].get("name") != archive.name
        or manifest[0].get("sha256") != expected_archive_sha256
    ):
        raise ConsensusVerificationError("intake archive manifest binding mismatch")

    provenance = read_json(intake_dir / "source_provenance.json")
    if outputs.get("source_provenance_sha256") != sha256(
        intake_dir / "source_provenance.json"
    ):
        raise ConsensusVerificationError("source provenance summary hash mismatch")
    if not isinstance(provenance, list) or len(provenance) != len(records):
        raise ConsensusVerificationError("source provenance cardinality mismatch")
    by_sha: dict[str, dict[str, Any]] = {}
    for row in provenance:
        if not isinstance(row, dict) or row.get("journal_sha256") in by_sha:
            raise ConsensusVerificationError("source provenance journal identity mismatch")
        by_sha[str(row.get("journal_sha256"))] = row
    for record in records:
        row = by_sha.get(record["journal_sha256"])
        expected_source = (
            "explicit_journal" if record["identifiers"] else "archive_consensus_fallback"
        )
        if (
            row is None
            or row.get("journal_member") != record["journal_member"]
            or row.get("competition_id_source") != expected_source
            or row.get("task") != consensus
            or row.get("run_id") != f"journal:{record['journal_sha256']}"
        ):
            raise ConsensusVerificationError("source provenance consensus mapping mismatch")

    audits = read_json(intake_dir / "archive_audits.json")
    if outputs.get("archive_audits_sha256") != sha256(intake_dir / "archive_audits.json"):
        raise ConsensusVerificationError("archive audit summary hash mismatch")
    if (
        not isinstance(audits, list)
        or len(audits) != 1
        or audits[0].get("archive_name") != archive.name
        or audits[0].get("checkpoint_runs") != len(records)
        or audits[0].get("competition_id_explicit_journals") != explicit
        or audits[0].get("competition_id_archive_consensus_fallback_journals") != fallback
        or audits[0].get("archive_consensus_fallback_used") is not True
    ):
        raise ConsensusVerificationError("archive audit consensus binding mismatch")
    if sha256(archive) != expected_archive_sha256:
        raise ConsensusVerificationError("archive changed during independent verification")

    return {
        "protocol": PROTOCOL,
        "status": "ARCHIVE_CONSENSUS_INDEPENDENT_VERIFICATION_PASS",
        "archive_sha256": expected_archive_sha256,
        "intake_summary_sha256": expected_intake_summary_sha256,
        "checkpoint_journals": len(records),
        "explicit_competition_journals": explicit,
        "archive_consensus_fallback_journals": fallback,
        "global_exact_distinct_competitions": len(exact_union),
        "global_normalized_distinct_competitions": len(normalized_union),
        "archive_stem_match": True,
        "provenance_mapping_verified": True,
        "security": {
            "credential_scan_before_json": True,
            "env_or_key_members_opened": False,
            "live_event_journals_opened": False,
            "label_vault_opened": False,
            "outcomes_predictions_accuracy_utility_read": False,
            "competition_identities_emitted": False,
        },
    }


def atomic_json(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite verifier output: {path}")
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--expect-archive-sha256", required=True)
    parser.add_argument("--intake-dir", required=True, type=Path)
    parser.add_argument("--expect-intake-summary-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-member-bytes", type=int, default=2 * 1024 * 1024 * 1024)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.archive,
            args.expect_archive_sha256,
            args.intake_dir,
            args.expect_intake_summary_sha256,
            args.max_member_bytes,
        )
        atomic_json(args.out, receipt)
        print(
            receipt["status"],
            f"checkpoint_journals={receipt['checkpoint_journals']}",
            f"fallback_journals={receipt['archive_consensus_fallback_journals']}",
            "identities_emitted=false",
            "outcomes_read=false",
            flush=True,
        )
        return 0
    except (OSError, tarfile.TarError, ConsensusVerificationError) as error:
        print(f"ARCHIVE_CONSENSUS_VERIFICATION_ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
