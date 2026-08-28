#!/usr/bin/env python3
"""Independent V3 verifier for monotone task-universe expansion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from phase1.verify_task_balance_guard_forward_validation_v2 import (
    ForwardV2VerificationError,
    verify as verify_v2,
    write_new,
)


class ForwardV3VerificationError(ForwardV2VerificationError):
    """Raised when an independently reconstructed V3 field differs."""


def verify(
    guard_path: Path,
    guard_sha: str,
    guard_verification_path: Path,
    guard_verification_sha: str,
    baseline_summary_path: Path,
    baseline_summary_sha: str,
    baseline_ledger_path: Path,
    baseline_ledger_sha: str,
    baseline_snapshot: str,
    current_summary_path: Path,
    current_summary_sha: str,
    current_ledger_path: Path,
    current_ledger_sha: str,
    current_snapshot: str,
    common_support_path: Path,
    common_support_sha: str,
    result_path: Path,
    result_sha: str,
) -> dict[str, Any]:
    try:
        return verify_v2(
            guard_path,
            guard_sha,
            guard_verification_path,
            guard_verification_sha,
            baseline_summary_path,
            baseline_summary_sha,
            baseline_ledger_path,
            baseline_ledger_sha,
            baseline_snapshot,
            current_summary_path,
            current_summary_sha,
            current_ledger_path,
            current_ledger_sha,
            current_snapshot,
            common_support_path,
            common_support_sha,
            result_path,
            result_sha,
            allow_task_expansion=True,
        )
    except ForwardV2VerificationError as exc:
        raise ForwardV3VerificationError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guard", required=True, type=Path)
    parser.add_argument("--expect-guard-sha256", required=True)
    parser.add_argument("--guard-verification", required=True, type=Path)
    parser.add_argument("--expect-guard-verification-sha256", required=True)
    parser.add_argument("--baseline-summary", required=True, type=Path)
    parser.add_argument("--expect-baseline-summary-sha256", required=True)
    parser.add_argument("--baseline-ledger", required=True, type=Path)
    parser.add_argument("--expect-baseline-ledger-sha256", required=True)
    parser.add_argument("--baseline-snapshot-sha256", required=True)
    parser.add_argument("--current-summary", required=True, type=Path)
    parser.add_argument("--expect-current-summary-sha256", required=True)
    parser.add_argument("--current-ledger", required=True, type=Path)
    parser.add_argument("--expect-current-ledger-sha256", required=True)
    parser.add_argument("--current-snapshot-sha256", required=True)
    parser.add_argument("--current-common-support-verification", required=True, type=Path)
    parser.add_argument("--expect-current-common-support-verification-sha256", required=True)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--expect-result-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.guard,
            args.expect_guard_sha256,
            args.guard_verification,
            args.expect_guard_verification_sha256,
            args.baseline_summary,
            args.expect_baseline_summary_sha256,
            args.baseline_ledger,
            args.expect_baseline_ledger_sha256,
            args.baseline_snapshot_sha256,
            args.current_summary,
            args.expect_current_summary_sha256,
            args.current_ledger,
            args.expect_current_ledger_sha256,
            args.current_snapshot_sha256,
            args.current_common_support_verification,
            args.expect_current_common_support_verification_sha256,
            args.result,
            args.expect_result_sha256,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt["recomputed"], sort_keys=True, separators=(",", ":")))
        return 0
    except (
        OSError,
        ForwardV3VerificationError,
        ValueError,
        TypeError,
        ZeroDivisionError,
    ) as exc:
        print(f"TASK_BALANCE_FORWARD_V3_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
