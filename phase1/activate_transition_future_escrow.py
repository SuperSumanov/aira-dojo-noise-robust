"""Create the one-time UTC activation receipt for transition future escrow."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROTOCOL = "transition-future-escrow-v1"
FULLFIT_STATUS = "TRANSITION_FUTURE_FULLFIT_COMPLETE_PENDING_INDEPENDENT_VERIFICATION"
VERIFY_STATUS = "INDEPENDENT_TRANSITION_FUTURE_FULLFIT_VERIFIED"
STATUS = "TRANSITION_FUTURE_ESCROW_ACTIVE"
SHA = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


class ActivationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ActivationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"expected object: {path.name}")
    return value


def locked(path: Path, expected: str) -> Path:
    resolved = path.resolve()
    check(
        SHA.fullmatch(expected) is not None
        and resolved.is_file()
        and sha256_file(resolved) == expected,
        f"locked input differs: {path.name}",
    )
    return resolved


def parse_utc(value: str) -> dt.datetime:
    check(isinstance(value, str) and value.endswith("Z"), "UTC timestamp must end in Z")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ActivationError("invalid UTC timestamp") from error
    check(parsed.tzinfo is not None, "naive UTC timestamp")
    return parsed.astimezone(dt.timezone.utc)


def utc_now() -> tuple[str, int]:
    wall_ns = time.time_ns()
    value = dt.datetime.fromtimestamp(wall_ns / 1_000_000_000, tz=dt.timezone.utc)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z"), wall_ns


def bind_source(repo: Path, commit: str, source_paths: list[Any]) -> dict[str, str]:
    check(COMMIT.fullmatch(commit) is not None, "source commit is not full lowercase SHA")
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    check(head == commit, "source commit mismatch")
    hashes = {}
    for relative in source_paths:
        check(isinstance(relative, str), "non-string source path")
        path = repo / relative
        check(path.is_file(), f"bound source missing: {relative}")
        current_blob = subprocess.check_output(
            ["git", "-C", str(repo), "hash-object", str(path)], text=True
        ).strip()
        committed_blob = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", f"{commit}:{relative}"], text=True
        ).strip()
        check(current_blob == committed_blob, f"bound source differs: {relative}")
        hashes[relative] = sha256_file(path)
    return dict(sorted(hashes.items()))


def current_snapshot_receipt(state_root: Path, expected_snapshot: str) -> dict[str, Any]:
    check(SHA.fullmatch(expected_snapshot) is not None, "snapshot SHA invalid")
    state_root = state_root.resolve()
    check((state_root / "LATEST").read_text().strip() == expected_snapshot, "LATEST differs")
    snapshot = (state_root / "snapshots" / expected_snapshot).resolve()
    check(snapshot.parent == state_root / "snapshots" and snapshot.is_dir(), "snapshot path differs")
    runs_path = snapshot / "accumulator" / "provisional_runs.jsonl"
    rows = []
    with runs_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            check(bool(line.strip()), f"blank run row: {line_number}")
            row = json.loads(line)
            check(isinstance(row, dict), f"non-object run row: {line_number}")
            check(row.get("flow_status") == "scoreable", "non-scoreable run in accumulator")
            parse_utc(row.get("generation_started_at_utc"))
            rows.append(row)
    check(bool(rows) and len({row.get("run_id") for row in rows}) == len(rows), "run inventory invalid")
    maximum = max(rows, key=lambda row: parse_utc(row["generation_started_at_utc"]))[
        "generation_started_at_utc"
    ]
    return {
        "maximum_generation_started_at_utc": maximum,
        "provisional_runs": len(rows),
        "provisional_runs_sha256": sha256_file(runs_path),
        "snapshot_sha256": expected_snapshot,
    }


def activate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = locked(args.protocol, args.expect_protocol_sha256)
    summary_path = locked(args.model_summary, args.expect_model_summary_sha256)
    spec_path = locked(args.model_spec, args.expect_model_spec_sha256)
    reference_path = locked(args.train_reference, args.expect_train_reference_sha256)
    verification_path = locked(args.model_verification, args.expect_model_verification_sha256)
    protocol = read_object(protocol_path)
    summary = read_object(summary_path)
    verification = read_object(verification_path)
    check(protocol.get("protocol") == PROTOCOL, "protocol identity differs")
    source_paths = protocol.get("source_paths")
    check(isinstance(source_paths, list) and source_paths, "protocol source paths missing")
    source_hashes = bind_source(args.repo_root.resolve(), args.source_commit, source_paths)
    check(
        summary.get("status") == FULLFIT_STATUS
        and summary.get("source_commit") == args.source_commit
        and summary.get("inputs", {}).get("protocol_sha256") == args.expect_protocol_sha256
        and summary.get("outputs", {}).get("model_spec_sha256") == args.expect_model_spec_sha256
        and summary.get("outputs", {}).get("train_reference_sha256")
        == args.expect_train_reference_sha256,
        "model summary contract differs",
    )
    check(
        verification.get("status") == VERIFY_STATUS
        and verification.get("source_commit") == args.source_commit
        and verification.get("model_spec_sha256") == args.expect_model_spec_sha256
        and verification.get("train_reference_sha256") == args.expect_train_reference_sha256
        and verification.get("producer_summary_sha256") == args.expect_model_summary_sha256
        and verification.get("producer_imported") is False
        and verification.get("all_model_spec_fields_exact") is True
        and verification.get("maximum_reference_margin_difference") <= 1e-12,
        "independent model verification contract differs",
    )
    check(
        sha256_file(spec_path) == args.expect_model_spec_sha256
        and sha256_file(reference_path) == args.expect_train_reference_sha256,
        "model artifacts changed after lock",
    )
    for scope in (summary.get("scope", {}), verification.get("scope", {})):
        check(
            scope.get("prospective_outcomes_read") is False
            and scope.get("effect_metrics_computed") == []
            and scope.get("test_split_read") is False,
            "model receipt scope differs",
        )
    snapshot = current_snapshot_receipt(args.state_root, args.expect_snapshot_sha256)
    activated_at, wall_ns = utc_now()
    check(
        parse_utc(activated_at) > parse_utc(snapshot["maximum_generation_started_at_utc"]),
        "activation is not after existing support",
    )
    return {
        "activated_at_utc": activated_at,
        "activation_wall_clock_unix_ns": wall_ns,
        "current_support_at_activation": {
            **snapshot,
            "strict_post_activation_runs": 0,
        },
        "host": socket.gethostname(),
        "inputs": {
            "model_spec_sha256": args.expect_model_spec_sha256,
            "model_summary_sha256": args.expect_model_summary_sha256,
            "model_verification_sha256": args.expect_model_verification_sha256,
            "protocol_sha256": args.expect_protocol_sha256,
            "train_reference_sha256": args.expect_train_reference_sha256,
        },
        "protocol": PROTOCOL,
        "scope": {
            "api_calls": 0,
            "base_llm_updates": 0,
            "effect_metrics_computed": [],
            "gpu": 0,
            "hand_entered_activation_timestamp_used": False,
            "prospective_outcomes_read": False,
        },
        "source_commit": args.source_commit,
        "source_file_sha256": source_hashes,
        "status": STATUS,
        "temporal_contract": {
            "generation_start_at_or_before_activation": "support_only",
            "generation_start_strictly_after_activation": "strict_future",
        },
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--protocol", required=True, type=Path)
    value.add_argument("--expect-protocol-sha256", required=True)
    value.add_argument("--model-summary", required=True, type=Path)
    value.add_argument("--expect-model-summary-sha256", required=True)
    value.add_argument("--model-spec", required=True, type=Path)
    value.add_argument("--expect-model-spec-sha256", required=True)
    value.add_argument("--train-reference", required=True, type=Path)
    value.add_argument("--expect-train-reference-sha256", required=True)
    value.add_argument("--model-verification", required=True, type=Path)
    value.add_argument("--expect-model-verification-sha256", required=True)
    value.add_argument("--state-root", required=True, type=Path)
    value.add_argument("--expect-snapshot-sha256", required=True)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.output.exists():
        print("TRANSITION_FUTURE_ACTIVATION_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = activate(args)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n")
    except (
        ActivationError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"TRANSITION_FUTURE_ACTIVATION_ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": STATUS, "activated_at_utc": receipt["activated_at_utc"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
