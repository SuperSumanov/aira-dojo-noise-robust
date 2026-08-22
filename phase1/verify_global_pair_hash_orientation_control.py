#!/usr/bin/env python3
"""Independent reconstruction of the global endpoint-hash orientation overlay."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


FROZEN_PROTOCOL_SHA256 = "3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9"
OUTPUT_KEYS = {
    "schema_version", "source_row_number", "task", "source_identity_sha256",
    "unordered_pair_sha256", "hash_better", "hash_worse",
}
SHA_RX = re.compile(r"[0-9a-f]{64}")


class VerificationError(RuntimeError):
    """Raised when the overlay is not the frozen grade-independent transform."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def file_hash(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def string_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value.lower()) is None:
        raise VerificationError(f"invalid {label}")
    return value.lower()


def object_file(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def source_rows(path: Path, expected_hash: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file() or file_hash(path) != sha(expected_hash, "source SHA"):
        raise VerificationError("source hash mismatch")
    result: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                raise VerificationError("blank source row")
            row = json.loads(line)
            if not isinstance(row, dict) or not {"better", "worse", "task", "intask_split"} <= set(row):
                raise VerificationError("source schema mismatch")
            values = (row["better"], row["worse"], row["task"])
            if (
                row["intask_split"] != "train"
                or any(not isinstance(value, str) or not value for value in values)
                or row["better"] == row["worse"]
            ):
                raise VerificationError(f"invalid source row {number}")
            result.append(row)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError("cannot read source rows") from error
    if not result:
        raise VerificationError("empty source")
    return result


def expected_overlay(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    endpoint_tasks: dict[str, str] = {}
    task_counts: Counter[str] = Counter()
    for number, row in enumerate(rows, 1):
        endpoints = tuple(sorted((row["better"], row["worse"])))
        task = row["task"]
        for endpoint in endpoints:
            previous_task = endpoint_tasks.setdefault(endpoint, task)
            if previous_task != task:
                raise VerificationError("endpoint reused across tasks")
        pair = (task, endpoints[0], endpoints[1])
        if pair in seen:
            raise VerificationError("duplicate source pair")
        seen.add(pair)
        utility_left = string_hash("20260823|" + endpoints[0])
        utility_right = string_hash("20260823|" + endpoints[1])
        if utility_left == utility_right:
            raise VerificationError("endpoint hash collision")
        if utility_left > utility_right:
            better, worse = endpoints[0], endpoints[1]
        else:
            better, worse = endpoints[1], endpoints[0]
        task_counts[task] += 1
        safe_identity = {
            "intask_split": "train",
            "source_row_number": number,
            "task": task,
            "unordered_endpoints": list(endpoints),
        }
        result.append({
            "schema_version": "global-pair-hash-orientation-row-v2",
            "source_row_number": number,
            "task": task,
            "source_identity_sha256": string_hash(canonical(safe_identity)),
            "unordered_pair_sha256": string_hash(canonical({"task": task, "endpoints": list(endpoints)})),
            "hash_better": better,
            "hash_worse": worse,
        })
    return result, dict(sorted(task_counts.items()))


def overlay_rows(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError("overlay is not a regular file")
    result: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                raise VerificationError("blank overlay row")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != OUTPUT_KEYS:
                raise VerificationError(f"overlay schema mismatch at row {number}")
            result.append(row)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError("cannot read overlay") from error
    return result


def verify(
    protocol_path: Path,
    expected_protocol_sha: str,
    global_train_path: Path,
    expected_global_train_sha: str,
    output_dir: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    protocol_sha = sha(expected_protocol_sha, "protocol SHA")
    source_sha = sha(expected_global_train_sha, "source SHA")
    if protocol_sha != FROZEN_PROTOCOL_SHA256 or file_hash(protocol_path) != FROZEN_PROTOCOL_SHA256:
        raise VerificationError("protocol SHA mismatch")
    protocol = object_file(protocol_path, "candidate protocol")
    control = protocol.get("hash_control") or {}
    if (
        protocol.get("protocol") != "global-local-calibration-candidate-v2"
        or protocol.get("status") != "ARMS_FROZEN_IDENTITY_G0_BUDGET_EFFECT_BLOCKED"
        or control.get("seed") != 20260823
        or control.get("shared_endpoint_order_is_transitive") is not True
        or control.get("true_grade_may_affect_hash_orientation") is not False
    ):
        raise VerificationError("protocol hash-control mismatch")

    source = source_rows(global_train_path, source_sha)
    reconstructed, per_task = expected_overlay(source)
    overlay_path = output_dir / "orientation_overlay.jsonl"
    observed = overlay_rows(overlay_path)
    expected_bytes = "".join(canonical(row) + "\n" for row in reconstructed).encode("utf-8")
    if observed != reconstructed or overlay_path.read_bytes() != expected_bytes:
        raise VerificationError("orientation overlay reconstruction mismatch")

    summary_path = output_dir / "summary.json"
    summary = object_file(summary_path, "hash-control summary")
    inputs = summary.get("inputs") or {}
    orientation = summary.get("orientation") or {}
    counts = summary.get("counts") or {}
    privacy = summary.get("privacy") or {}
    gates = summary.get("gates") or {}
    if (
        summary.get("protocol") != "global-pair-hash-orientation-control-v2"
        or summary.get("status") != "HASH_ORIENTATION_OVERLAY_READY_EFFECT_BLOCKED"
        or inputs.get("candidate_protocol_sha256") != protocol_sha
        or inputs.get("global_train_sha256") != source_sha
        or orientation.get("seed") != 20260823
        or orientation.get("endpoint_utility") != control.get("endpoint_utility")
        or orientation.get("larger_hash_is_better") is not True
        or orientation.get("pair_level_independent_flips") is not False
        or orientation.get("shared_endpoint_order_is_transitive") is not True
        or orientation.get("true_grade_used") is not False
        or counts.get("rows") != len(source)
        or counts.get("unique_unordered_pairs") != len(source)
        or counts.get("tasks") != len(per_task)
        or counts.get("per_task") != per_task
        or privacy.get("source_outcome_fields_written") != []
        or privacy.get("gap_raw_written") is not False
        or privacy.get("original_better_worse_relation_written") is not False
        or privacy.get("source_row_commitment_written") is not False
        or privacy.get("safe_identity_commitment_written") is not True
        or privacy.get("grade_derived_commitment_written") is not False
        or privacy.get("code_opened") is not False
        or gates.get("train_only_input") is not True
        or gates.get("row_order_preserved") is not True
        or gates.get("effect_submission_authorized") is not False
        or gates.get("gpu_jobs_authorized") != 0
        or gates.get("model_fits_authorized") != 0
        or set(summary.get("outputs") or {}) != {"orientation_overlay_sha256"}
        or (summary.get("outputs") or {}).get("orientation_overlay_sha256") != file_hash(overlay_path)
    ):
        raise VerificationError("hash-control summary reconstruction mismatch")

    receipt = {
        "protocol": "global-pair-hash-orientation-independent-verification-v1",
        "status": "PASS_HASH_ORIENTATION_OVERLAY_EFFECT_BLOCKED",
        "producer_module_imported": False,
        "candidate_protocol_sha256": protocol_sha,
        "global_train_sha256": source_sha,
        "orientation_overlay_sha256": file_hash(overlay_path),
        "summary_sha256": file_hash(summary_path),
        "rows": len(source),
        "true_grade_used": False,
        "effect_submission_authorized": False,
    }
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite receipt: {receipt_path}")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{receipt_path.name}.", dir=receipt_path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, receipt_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return receipt


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", default=FROZEN_PROTOCOL_SHA256)
    parser.add_argument("--global-train", required=True, type=Path)
    parser.add_argument("--expect-global-train-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    receipt = verify(
        args.protocol,
        args.expect_protocol_sha256,
        args.global_train,
        args.expect_global_train_sha256,
        args.output_dir,
        args.receipt,
    )
    print(canonical(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
