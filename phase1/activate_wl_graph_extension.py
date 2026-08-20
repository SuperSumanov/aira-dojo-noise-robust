#!/usr/bin/env python3
"""Create the one-time UTC activation receipt for the WL graph extension."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "prospective-wl-graph-escrow-v1"
STATUS = "PROSPECTIVE_WL_GRAPH_EXTENSION_ACTIVE"
FULL_SHA = re.compile(r"[0-9a-f]{64}")
FULL_COMMIT = re.compile(r"[0-9a-f]{40}")


class ActivationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ActivationError(f"expected JSON object: {path.name}")
    return value


def locked(path: Path, expected: str) -> Path:
    path = path.resolve()
    if not FULL_SHA.fullmatch(expected) or not path.is_file() or sha256_file(path) != expected:
        raise ActivationError(f"locked input mismatch: {path.name}")
    return path


def bind_source(repo: Path, source_commit: str, relative_paths: list[str]) -> dict[str, str]:
    if not FULL_COMMIT.fullmatch(source_commit):
        raise ActivationError("source commit is not a full lowercase SHA")
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if head != source_commit:
        raise ActivationError("source HEAD mismatch")
    bound: dict[str, str] = {}
    for relative in relative_paths:
        path = repo / relative
        if not path.is_file():
            raise ActivationError(f"bound source missing: {relative}")
        actual_blob = subprocess.check_output(["git", "-C", str(repo), "hash-object", str(path)], text=True).strip()
        expected_blob = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", f"{source_commit}:{relative}"], text=True
        ).strip()
        if actual_blob != expected_blob:
            raise ActivationError(f"bound source differs from commit: {relative}")
        bound[relative] = sha256_file(path)
    return dict(sorted(bound.items()))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def activate(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.repo_root.resolve()
    protocol_path = locked(args.protocol, args.expect_protocol_sha256)
    bundle_path = locked(args.bundle, args.expect_bundle_sha256)
    summary_path = locked(args.bundle_summary, args.expect_bundle_summary_sha256)
    verification_path = locked(args.bundle_verification, args.expect_bundle_verification_sha256)
    erratum_path = locked(args.time_erratum, args.expect_time_erratum_sha256)

    protocol = read_object(protocol_path)
    summary = read_object(summary_path)
    verification = read_object(verification_path)
    erratum = read_object(erratum_path)
    source_paths = protocol.get("source_paths")
    if protocol.get("protocol") != PROTOCOL or not isinstance(source_paths, list) or not source_paths:
        raise ActivationError("prediction protocol mismatch")
    source_hashes = bind_source(repo, args.source_commit, [str(value) for value in source_paths])

    bundle_contract = protocol.get("bundle")
    if not isinstance(bundle_contract, dict) or bundle_contract != {
        "bundle_sha256": args.expect_bundle_sha256,
        "build_source_commit": summary.get("source_commit"),
        "build_summary_sha256": args.expect_bundle_summary_sha256,
        "independent_verification_sha256": args.expect_bundle_verification_sha256,
    }:
        raise ActivationError("protocol bundle contract mismatch")
    if (
        summary.get("status") != "WL_GRAPH_MULTIVIEW_BUILD_COMPLETE_NOT_YET_INDEPENDENTLY_VERIFIED"
        or summary.get("outputs", {}).get("bundle_sha256") != args.expect_bundle_sha256
        or summary.get("scope", {}).get("v11_frozen_or_extension_read") is not False
        or summary.get("scope", {}).get("outcome_metrics_computed") != []
        or verification.get("status") != "INDEPENDENT_WL_GRAPH_MULTIVIEW_REFIT_VERIFIED"
        or verification.get("bundle_sha256") != args.expect_bundle_sha256
        or verification.get("source_commit") != summary.get("source_commit")
        or verification.get("maximum_numeric_array_difference", 1.0) > 1e-12
        or verification.get("maximum_reference_score_difference", 1.0) > 1e-12
        or verification.get("scope", {}).get("prospective_outcomes_read") is not False
        or erratum.get("protocol") != "wl-graph-multiview-extension-v1"
        or erratum.get("status") != "DECLARED_FREEZE_TIMESTAMP_INVALIDATED"
        or erratum.get("consequences", {}).get(
            "declared_frozen_at_utc_may_be_used_as_temporal_boundary"
        )
        is not False
    ):
        raise ActivationError("bundle verification, scope, or time erratum mismatch")

    return {
        "status": STATUS,
        "protocol": PROTOCOL,
        "activated_at_utc": utc_now(),
        "source_commit": args.source_commit,
        "source_file_sha256": source_hashes,
        "inputs": {
            "protocol_sha256": args.expect_protocol_sha256,
            "bundle_sha256": args.expect_bundle_sha256,
            "bundle_summary_sha256": args.expect_bundle_summary_sha256,
            "bundle_verification_sha256": args.expect_bundle_verification_sha256,
            "time_erratum_sha256": args.expect_time_erratum_sha256,
        },
        "temporal_contract": {
            "generated_strictly_after_activation": "strict_post_activation_primary",
            "generated_at_or_before_activation": "outcome_unread_support_only",
            "hand_entered_protocol_timestamp_used": False,
        },
        "scope": {
            "v11_frozen_or_extension_read": False,
            "prospective_outcomes_read": False,
            "temporal_label_vault_read": False,
            "effect_metrics_computed": [],
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--protocol", required=True, type=Path)
    value.add_argument("--expect-protocol-sha256", required=True)
    value.add_argument("--bundle", required=True, type=Path)
    value.add_argument("--expect-bundle-sha256", required=True)
    value.add_argument("--bundle-summary", required=True, type=Path)
    value.add_argument("--expect-bundle-summary-sha256", required=True)
    value.add_argument("--bundle-verification", required=True, type=Path)
    value.add_argument("--expect-bundle-verification-sha256", required=True)
    value.add_argument("--time-erratum", required=True, type=Path)
    value.add_argument("--expect-time-erratum-sha256", required=True)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.output.exists():
        print("WL_GRAPH_ACTIVATION_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = activate(args)
        args.output.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (ActivationError, OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"WL_GRAPH_ACTIVATION_ERROR: {error}", file=sys.stderr)
        return 2
    print(STATUS, f"activated_at_utc={receipt['activated_at_utc']}", "effect_metrics=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
