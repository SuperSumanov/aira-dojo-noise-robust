#!/usr/bin/env python3
"""Append-safe task-balance forward accounting for future snapshots.

V3 keeps every V2 invariant while admitting a monotone expansion of the task
universe.  It must not be used to rescue the already observed 887 snapshot.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from phase1.build_task_balance_accrual_guard_v2 import BalanceGuardV2Error
from phase1.task_balance_guard_forward_validation_v2 import (
    ForwardV2Error,
    build_forward as build_forward_v2,
    write_new,
)


class ForwardV3Error(ForwardV2Error):
    """Raised when the monotone task-expansion contract fails."""


def build_forward(
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
    current_common_support_path: Path,
    current_common_support_sha: str,
) -> dict[str, Any]:
    try:
        return build_forward_v2(
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
            current_common_support_path,
            current_common_support_sha,
            allow_task_expansion=True,
        )
    except ForwardV2Error as exc:
        raise ForwardV3Error(str(exc)) from exc


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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = build_forward(
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
        )
        write_new(args.output.resolve(), value)
        print(
            json.dumps(
                value["frozen_guard_forward_result"],
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (
        OSError,
        BalanceGuardV2Error,
        ForwardV3Error,
        ValueError,
        TypeError,
        ZeroDivisionError,
    ) as exc:
        print(f"TASK_BALANCE_FORWARD_V3_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
