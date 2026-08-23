#!/usr/bin/env python3
"""Publish the first independently verified closed future-cohort receipt once.

The fixed anchor removes caller choice from later prediction/truth runners.  It
reads identity-only formal artifacts and never opens blind code, labels, scores,
or replay outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-future-closure-anchor-v1"
STATUS = "FUTURE_COHORT_FIRST_CLOSURE_ANCHORED_TRUTH_UNREAD"
COHORT_PROTOCOL = "score-channel-future-identity-cohort-v1"
VERIFICATION_PROTOCOL = "score-channel-future-identity-cohort-independent-verifier-v1"
SHA = re.compile(r"[0-9a-f]{64}")


class AnchorError(RuntimeError):
    """Identity-only closure receipt could not be anchored safely."""


def stable_file_bytes(path: Path, label: str) -> bytes:
    if path.is_symlink():
        raise AnchorError(f"symlinked {label}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise AnchorError(f"cannot open stable {label}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AnchorError(f"non-regular {label}")
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(payload) != before.st_size
    ):
        raise AnchorError(f"{label} changed while being read")
    return payload


def digest(path: Path) -> str:
    return hashlib.sha256(stable_file_bytes(path, str(path))).hexdigest()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def obj(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(stable_file_bytes(path, label).decode("utf-8"))
    if not isinstance(value, dict):
        raise AnchorError(f"{label} is not an object")
    return value


def sha(value: Any, label: str, *, length: int = 64) -> str:
    if not isinstance(value, str):
        raise AnchorError(f"invalid {label}")
    lowered = value.lower()
    if len(lowered) != length or any(character not in "0123456789abcdef" for character in lowered):
        raise AnchorError(f"invalid {label}")
    return lowered


def verify_sha_manifest(formal: Path) -> str:
    manifest = formal / "SHA256SUMS"
    if manifest.is_symlink() or not manifest.is_file():
        raise AnchorError("formal SHA256SUMS is missing or unsafe")
    manifest_payload = stable_file_bytes(manifest, "formal SHA256SUMS")
    seen: set[str] = set()
    for number, line in enumerate(manifest_payload.decode("utf-8").splitlines(), 1):
        if len(line) < 67 or line[64:66] not in {"  ", " *"}:
            raise AnchorError(f"invalid SHA256SUMS row {number}")
        expected, relative = line[:64], line[66:]
        if not SHA.fullmatch(expected) or not relative or relative in seen:
            raise AnchorError(f"invalid SHA256SUMS identity {number}")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.name == "SHA256SUMS":
            raise AnchorError(f"unsafe SHA256SUMS path {number}")
        target = formal / path
        if target.is_symlink() or not target.is_file() or digest(target) != expected:
            raise AnchorError(f"formal artifact hash mismatch: {relative}")
        seen.add(relative)
    required = {
        "COMPLETE",
        "control_commit.txt",
        "latest_before.txt",
        "observations_before_sha256.txt",
        "producer_a/summary.json",
        "producer_a/cohort_runs.jsonl",
        "producer_a/cohort_archives.jsonl",
        "producer_b/summary.json",
        "verification_a.json",
        "verification_b.json",
        "producer_reproducibility.diff",
        "verifier_reproducibility.diff",
    }
    if not required.issubset(seen):
        raise AnchorError("formal SHA256SUMS lacks closure evidence")
    return hashlib.sha256(manifest_payload).hexdigest()


def repository_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AnchorError("cannot resolve anchor source commit")
    return sha(result.stdout.strip(), "anchor source commit", length=40)


def build_anchor(formal: Path, result_root: Path, repo: Path) -> dict[str, Any]:
    if (
        formal.is_symlink()
        or result_root.is_symlink()
        or not formal.is_dir()
        or not result_root.is_dir()
        or formal.resolve().parent != result_root.resolve()
    ):
        raise AnchorError("formal result is not a direct safe child of result root")
    if (formal / "COMPLETE").read_text(encoding="utf-8") != "SCORE_CHANNEL_FUTURE_IDENTITY_COHORT_FORMAL_COMPLETE\n":
        raise AnchorError("formal completion marker mismatch")
    if (formal / "producer_reproducibility.diff").stat().st_size != 0:
        raise AnchorError("cohort producer replicas differ")
    if (formal / "verifier_reproducibility.diff").stat().st_size != 0:
        raise AnchorError("cohort verifier replicas differ")
    manifest_sha = verify_sha_manifest(formal)
    cohort = formal / "producer_a"
    summary_path = cohort / "summary.json"
    runs_path = cohort / "cohort_runs.jsonl"
    archives_path = cohort / "cohort_archives.jsonl"
    verification_path = formal / "verification_a.json"
    summary = obj(summary_path, "closed cohort summary")
    verification = obj(verification_path, "closed cohort verification")
    closure, inventory = summary.get("closure") or {}, summary.get("inventory") or {}
    blindness = summary.get("blindness") or {}
    outputs = summary.get("outputs") or {}
    if (
        summary.get("protocol") != COHORT_PROTOCOL
        or summary.get("status") != "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        or closure.get("accepted_unique_physical_run_target") != 300
        or closure.get("complete_boundary_archive_included") is not True
        or closure.get("remaining_runs_to_target") != 0
        or not isinstance(inventory.get("selected_physical_runs"), int)
        or inventory["selected_physical_runs"] < 300
        or blindness.get("label_vault_opened") is not False
        or blindness.get("score_or_outcome_opened") is not False
        or blindness.get("truth_support_computed") is not False
        or blindness.get("replay_submission_authorized") is not False
        or digest(runs_path) != outputs.get("cohort_runs_sha256")
        or digest(archives_path) != outputs.get("cohort_archives_sha256")
    ):
        raise AnchorError("closed cohort summary contract mismatch")
    summary_sha = digest(summary_path)
    if (
        verification.get("protocol") != VERIFICATION_PROTOCOL
        or verification.get("status") != "PASS_IDENTITY_CLOSED_TRUTH_UNREAD"
        or verification.get("cohort_summary_sha256") != summary_sha
        or verification.get("cohort_runs_sha256") != outputs["cohort_runs_sha256"]
        or verification.get("cohort_archives_sha256") != outputs["cohort_archives_sha256"]
        or verification.get("label_vault_opened") is not False
        or verification.get("score_or_outcome_opened") is not False
        or verification.get("raw_archive_payload_opened") is not False
        or verification.get("replay_submission_authorized") is not False
    ):
        raise AnchorError("independent closed-cohort verification mismatch")
    commit = sha(
        (formal / "control_commit.txt").read_text(encoding="utf-8").strip(),
        "cohort control commit",
        length=40,
    )
    latest = sha(
        (formal / "latest_before.txt").read_text(encoding="utf-8").strip(),
        "prospective LATEST transaction SHA",
    )
    observations = sha(
        (formal / "observations_before_sha256.txt").read_text(encoding="utf-8").strip(),
        "observations SHA",
    )
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "cohort_dir": str(cohort.resolve()),
        "cohort_summary_sha256": summary_sha,
        "cohort_runs_sha256": outputs["cohort_runs_sha256"],
        "cohort_archives_sha256": outputs["cohort_archives_sha256"],
        "selected_physical_runs": inventory["selected_physical_runs"],
        "selected_tasks": inventory["selected_tasks"],
        "complete_boundary_archive": closure["boundary_archive"],
        "formal_result_dir": str(formal.resolve()),
        "formal_sha256s_sha256": manifest_sha,
        "independent_verification_sha256": digest(verification_path),
        "cohort_control_commit": commit,
        "prospective_latest_sha256": latest,
        "observations_sha256": observations,
        "identity_selected_before_truth": True,
        "label_vault_opened": False,
        "score_or_outcome_opened": False,
        "replay_submission_authorized": False,
        "publisher_commit": repository_head(repo),
        "publisher_source_sha256": digest(Path(__file__)),
    }


def publish(anchor: Path, document: dict[str, Any]) -> dict[str, Any]:
    payload = canonical(document)
    if anchor.is_symlink():
        raise AnchorError("closure anchor path is a symlink")
    if anchor.exists():
        existing = obj(anchor, "existing closure anchor")
        immutable_keys = set(document) - {"publisher_commit", "publisher_source_sha256"}
        if (
            set(existing) != set(document)
            or any(existing.get(key) != document.get(key) for key in immutable_keys)
            or stat.S_IMODE(anchor.stat().st_mode) & 0o222
            or sha(existing.get("publisher_commit"), "existing publisher commit", length=40)
            != existing.get("publisher_commit")
            or sha(existing.get("publisher_source_sha256"), "existing publisher source SHA")
            != existing.get("publisher_source_sha256")
        ):
            raise AnchorError("first closure anchor already binds a different receipt")
        return existing
    anchor.parent.mkdir(parents=True, exist_ok=True)
    temporary = anchor.with_name(f".{anchor.name}.tmp.{os.getpid()}")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o400,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.link(temporary, anchor)
    except Exception:
        os.chmod(temporary, 0o600)
        temporary.unlink(missing_ok=True)
        raise
    os.chmod(temporary, 0o600)
    temporary.unlink()
    os.chmod(anchor, 0o444)
    return document


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-result-dir", required=True, type=Path)
    parser.add_argument("--result-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--anchor", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        document = build_anchor(args.formal_result_dir, args.result_root, args.repo_root)
        published = publish(args.anchor, document)
    except (AnchorError, OSError, UnicodeError, json.JSONDecodeError, KeyError, ValueError) as error:
        print(f"FUTURE_COHORT_CLOSURE_ANCHOR_ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(published, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
