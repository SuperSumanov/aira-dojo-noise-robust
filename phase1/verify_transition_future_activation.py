"""Independent structural verifier for a transition future activation receipt."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "transition-future-escrow-v1"
ACTIVATION_STATUS = "TRANSITION_FUTURE_ESCROW_ACTIVE"
STATUS = "INDEPENDENT_TRANSITION_FUTURE_ACTIVATION_VERIFIED"
SHA = re.compile(r"[0-9a-f]{64}")


class VerifyError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def locked(path: Path, expected: str) -> Path:
    resolved = path.resolve()
    check(
        SHA.fullmatch(expected) is not None
        and resolved.is_file()
        and sha256_file(resolved) == expected,
        f"locked input differs: {path.name}",
    )
    return resolved


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"expected object: {path.name}")
    return value


def parse_utc(value: Any) -> dt.datetime:
    check(isinstance(value, str) and value.endswith("Z"), "UTC timestamp format differs")
    try:
        result = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise VerifyError("UTC timestamp invalid") from error
    check(result.tzinfo is not None, "UTC timestamp is naive")
    return result.astimezone(dt.timezone.utc)


def source_hashes(repo: Path, commit: str, paths: list[Any]) -> dict[str, str]:
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    check(head == commit, "source commit differs")
    result = {}
    for relative in paths:
        check(isinstance(relative, str), "non-string source path")
        path = repo / relative
        committed = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", f"{commit}:{relative}"], text=True
        ).strip()
        current = subprocess.check_output(
            ["git", "-C", str(repo), "hash-object", str(path)], text=True
        ).strip()
        check(current == committed, f"source path differs: {relative}")
        result[relative] = sha256_file(path)
    return dict(sorted(result.items()))


def snapshot_receipt(state_root: Path, expected_snapshot: str) -> dict[str, Any]:
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
            check(
                isinstance(row, dict) and row.get("flow_status") == "scoreable",
                "run row contract differs",
            )
            parse_utc(row.get("generation_started_at_utc"))
            rows.append(row)
    check(bool(rows) and len({row.get("run_id") for row in rows}) == len(rows), "run inventory differs")
    return {
        "maximum_generation_started_at_utc": max(
            rows, key=lambda row: parse_utc(row["generation_started_at_utc"])
        )["generation_started_at_utc"],
        "provisional_runs": len(rows),
        "provisional_runs_sha256": sha256_file(runs_path),
        "snapshot_sha256": expected_snapshot,
        "strict_post_activation_runs": 0,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    activation_path = locked(args.activation, args.expect_activation_sha256)
    protocol_path = locked(args.protocol, args.expect_protocol_sha256)
    summary_path = locked(args.model_summary, args.expect_model_summary_sha256)
    spec_path = locked(args.model_spec, args.expect_model_spec_sha256)
    reference_path = locked(args.train_reference, args.expect_train_reference_sha256)
    model_verification_path = locked(
        args.model_verification, args.expect_model_verification_sha256
    )
    activation = read_object(activation_path)
    protocol = read_object(protocol_path)
    summary = read_object(summary_path)
    model_verification = read_object(model_verification_path)
    check(protocol.get("protocol") == PROTOCOL, "protocol identity differs")
    paths = protocol.get("source_paths")
    check(isinstance(paths, list) and paths, "protocol source paths missing")
    bound = source_hashes(args.repo_root.resolve(), args.source_commit, paths)
    expected_inputs = {
        "model_spec_sha256": args.expect_model_spec_sha256,
        "model_summary_sha256": args.expect_model_summary_sha256,
        "model_verification_sha256": args.expect_model_verification_sha256,
        "protocol_sha256": args.expect_protocol_sha256,
        "train_reference_sha256": args.expect_train_reference_sha256,
    }
    check(
        activation.get("status") == ACTIVATION_STATUS
        and activation.get("protocol") == PROTOCOL
        and activation.get("source_commit") == args.source_commit
        and activation.get("source_file_sha256") == bound
        and activation.get("inputs") == expected_inputs,
        "activation source/input contract differs",
    )
    check(
        summary.get("outputs", {}).get("model_spec_sha256") == sha256_file(spec_path)
        and summary.get("outputs", {}).get("train_reference_sha256")
        == sha256_file(reference_path)
        and model_verification.get("producer_summary_sha256") == sha256_file(summary_path)
        and model_verification.get("status")
        == "INDEPENDENT_TRANSITION_FUTURE_FULLFIT_VERIFIED"
        and model_verification.get("producer_imported") is False,
        "model verification chain differs",
    )
    expected_snapshot = snapshot_receipt(args.state_root, args.expect_snapshot_sha256)
    check(
        activation.get("current_support_at_activation") == expected_snapshot,
        "activation support snapshot differs",
    )
    activated = parse_utc(activation.get("activated_at_utc"))
    wall_ns = activation.get("activation_wall_clock_unix_ns")
    check(isinstance(wall_ns, int) and not isinstance(wall_ns, bool), "activation wall ns differs")
    wall_time = dt.datetime.fromtimestamp(wall_ns / 1_000_000_000, tz=dt.timezone.utc)
    check(abs((activated - wall_time).total_seconds()) <= 1e-6, "activation clock fields differ")
    check(
        activated > parse_utc(expected_snapshot["maximum_generation_started_at_utc"]),
        "activation does not follow existing support",
    )
    check(
        activation.get("host") == socket.gethostname()
        and activation.get("temporal_contract")
        == {
            "generation_start_at_or_before_activation": "support_only",
            "generation_start_strictly_after_activation": "strict_future",
        },
        "activation host/temporal contract differs",
    )
    scope = activation.get("scope", {})
    check(
        scope.get("prospective_outcomes_read") is False
        and scope.get("effect_metrics_computed") == []
        and scope.get("hand_entered_activation_timestamp_used") is False,
        "activation scope differs",
    )
    return {
        "activated_at_utc": activation["activated_at_utc"],
        "activation_sha256": args.expect_activation_sha256,
        "all_fields_verified": True,
        "current_support_strict_runs": 0,
        "producer_imported": False,
        "protocol": "transition-future-activation-independent-verifier-v1",
        "source_commit": args.source_commit,
        "status": STATUS,
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
    value.add_argument("--activation", required=True, type=Path)
    value.add_argument("--expect-activation-sha256", required=True)
    value.add_argument("--state-root", required=True, type=Path)
    value.add_argument("--expect-snapshot-sha256", required=True)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.output.exists():
        print("TRANSITION_FUTURE_ACTIVATION_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(args)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    except (
        VerifyError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"TRANSITION_FUTURE_ACTIVATION_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": STATUS, "activation": receipt["activation_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
