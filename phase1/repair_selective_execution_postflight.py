#!/usr/bin/env python3
"""Repair only the self-referential manifest of a completed selective audit.

The producer and verifier are never imported or rerun.  This command accepts
only a staging directory whose independent verifier already passed, preserves
the failed manifest, creates an append-only repair receipt, hashes the now
stable payload, and atomically promotes the directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


PROTOCOL = "selective_execution_v11_retrospective_discovery_v1"
VERIFICATION = "INDEPENDENT_SELECTIVE_EXECUTION_VERIFY_PASS"
SCIENTIFIC_COMMIT = "7a1562a4506f17d713467956c797fb0d3226a8c5"


class RepairError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_targets(staging: Path, final: Path) -> tuple[Path, Path]:
    staging = staging.resolve()
    final = final.resolve()
    if not staging.is_dir() or final.exists():
        raise RepairError("staging must exist and final must not exist")
    if staging.parent != final.parent or staging.name != final.name + ".staging":
        raise RepairError("final must be the staging path without .staging")
    if not staging.name.startswith("selective_execution_v11_20260814_"):
        raise RepairError("unexpected result-root basename")
    return staging, final


def create_manifest(root: Path) -> Path:
    manifest = root / "SHA256SUMS"
    if manifest.exists():
        raise RepairError("new manifest already exists")
    lines = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        lines.append(f"{sha256(path)}  {relative}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for line in lines:
        expected, relative = line.split("  ", 1)
        if sha256(root / relative) != expected:
            raise RepairError(f"manifest verification failed: {relative}")
    return manifest


def repair(staging: Path, final: Path, repair_commit: str) -> dict[str, Any]:
    staging, final = validate_targets(staging, final)
    summary_path = staging / "result" / "summary.json"
    verify_path = staging / "result" / "independent_verify.json"
    failed_manifest = staging / "SHA256SUMS"
    if not summary_path.is_file() or not verify_path.is_file() or not failed_manifest.is_file():
        raise RepairError("required completed-chain artifact is missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    verification = json.loads(verify_path.read_text(encoding="utf-8"))
    if summary.get("protocol") != PROTOCOL or verification.get("protocol") != PROTOCOL:
        raise RepairError("protocol mismatch")
    if verification.get("verification") != VERIFICATION:
        raise RepairError("independent verifier did not pass")
    if verification.get("producer_verdict") != summary.get("verdict"):
        raise RepairError("producer/verifier verdict mismatch")
    if summary.get("frozen_or_first960_read") is not False or verification.get("frozen_or_first960_read") is not False:
        raise RepairError("forbidden-read receipt mismatch")
    if verification.get("summary_sha256") != sha256(summary_path):
        raise RepairError("summary hash no longer matches verifier receipt")

    preserved = staging / "SHA256SUMS.failed_self_reference"
    if preserved.exists():
        raise RepairError("failed manifest was already preserved")
    failed_sha = sha256(failed_manifest)
    failed_manifest.replace(preserved)
    receipt = {
        "protocol": PROTOCOL,
        "operation": "postflight_manifest_repair_only_no_scientific_recompute",
        "reason": "run.log was still open while the original manifest was verified",
        "scientific_commit": SCIENTIFIC_COMMIT,
        "repair_commit": repair_commit,
        "producer_verdict": summary["verdict"],
        "independent_verification": verification["verification"],
        "summary_sha256": sha256(summary_path),
        "independent_verify_sha256": sha256(verify_path),
        "failed_manifest_sha256": failed_sha,
        "frozen_or_first960_read": False,
        "producer_rerun": False,
        "verifier_rerun": False,
    }
    write_json(staging / "postflight_repair_receipt.json", receipt)
    manifest = create_manifest(staging)
    receipt["repaired_manifest_sha256"] = sha256(manifest)
    # The receipt cannot include the manifest hash without invalidating the
    # manifest.  Report it to stdout after promotion instead.
    os.replace(staging, final)
    primary = summary["policies"]["tri_unanimous_q20"]
    print(
        "POSTFLIGHT_REPAIR_PASS "
        f"verdict={summary['verdict']} selected={primary['selected']} "
        f"task_macro={primary['task_macro_accuracy']:.12f} "
        f"manifest_sha256={receipt['repaired_manifest_sha256']} final={final}",
        flush=True,
    )
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--final", required=True, type=Path)
    parser.add_argument("--repair-commit", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repair(args.staging, args.final, args.repair_commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
