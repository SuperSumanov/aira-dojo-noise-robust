#!/usr/bin/env python3
"""Independent verifier for the Target-522 rank Stage-A compatibility projection."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping


SHA_RE = re.compile(r"[0-9a-f]{64}")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"{path} must contain an object")
    return value


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def verify(
    compatibility: Mapping[str, Any],
    compatibility_sha: str,
    rank_protocol: Mapping[str, Any],
    rank_protocol_sha: str,
    actual: Mapping[str, Any],
    actual_sha: str,
    projected: Mapping[str, Any],
    projected_sha: str,
    claimed_receipt: Mapping[str, Any],
    claimed_receipt_sha: str,
) -> dict[str, Any]:
    for value, label in (
        (compatibility_sha, "compatibility SHA"),
        (rank_protocol_sha, "rank SHA"),
        (actual_sha, "actual SHA"),
        (projected_sha, "projected SHA"),
        (claimed_receipt_sha, "receipt SHA"),
    ):
        check(SHA_RE.fullmatch(value) is not None, label)
    check(
        compatibility.get("protocol") == "target522-linear-contrast-rank-stage-a-compatibility-v1",
        "compatibility protocol",
    )
    check(rank_protocol.get("protocol") == "target522-linear-contrast-rank-audit-v1", "rank protocol")
    bridge = compatibility["stage_a_execution_bridge"]
    check(
        rank_protocol["frozen_stage_a"]["source_commit"]
        == bridge["frozen_scientific_source_commit"],
        "frozen commit",
    )
    check(
        rank_protocol["frozen_stage_a"]["scientific_protocol_sha256"]
        == bridge["scientific_protocol_sha256"],
        "frozen protocol",
    )
    check(actual.get("protocol") == bridge["public_protocol"], "actual protocol")
    check(actual.get("status") == "COMPLETE", "actual incomplete")
    check(actual.get("analysis_source_commit") == bridge["compatible_execution_source_commit"], "actual commit")
    check(actual.get("protocol_sha256") == bridge["scientific_protocol_sha256"], "actual science")
    check(
        actual.get("selection_container_compatibility_sha256")
        == bridge["selection_container_compatibility_sha256"],
        "actual compatibility",
    )
    check(
        actual["selection_container"].get("outer_sha256sums_sha256")
        == bridge["outer_selection_sha256sums_sha256"],
        "actual outer manifest",
    )

    reconstructed = copy.deepcopy(dict(actual))
    removed = compatibility["projection"]["remove_exact_top_level_keys"]
    check(removed == ["selection_container", "selection_container_compatibility_sha256"], "removals")
    for key in removed:
        check(key in reconstructed, f"missing {key}")
        del reconstructed[key]
    replace_key = compatibility["projection"]["replace_exact_top_level_key"]
    replacement = compatibility["projection"]["replacement_value"]
    check(replace_key == "analysis_source_commit", "replacement key")
    check(replacement == bridge["frozen_scientific_source_commit"], "replacement value")
    reconstructed[replace_key] = replacement
    check(reconstructed == projected, "projection reconstruction mismatch")
    check(hashlib.sha256(canonical_bytes(projected)).hexdigest() == projected_sha, "projected canonical SHA")

    expected_receipt = {
        "protocol": "target522-linear-contrast-rank-stage-a-projection-receipt-v1",
        "status": "EXACT_EXECUTION_COMPATIBILITY_PROJECTION",
        "compatibility_sha256": compatibility_sha,
        "rank_scientific_protocol_sha256": rank_protocol_sha,
        "actual_stage_a_public_sha256": actual_sha,
        "projected_stage_a_public_sha256": projected_sha,
        "actual_execution_source_commit": bridge["compatible_execution_source_commit"],
        "frozen_scientific_source_commit": bridge["frozen_scientific_source_commit"],
        "removed_top_level_keys": sorted(removed),
        "changed_top_level_keys": ["analysis_source_commit"],
        "other_top_level_changes": 0,
        "private_selection_opened": False,
        "candidate_identity_opened": False,
        "prospective_values_read": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }
    check(claimed_receipt == expected_receipt, "projection receipt mismatch")
    return {
        "protocol": "target522-linear-contrast-rank-stage-a-projection-verification-v1",
        "status": "INDEPENDENT_PROJECTION_RECONSTRUCTION_EXACT",
        "compatibility_sha256": compatibility_sha,
        "actual_stage_a_public_sha256": actual_sha,
        "projected_stage_a_public_sha256": projected_sha,
        "claimed_projection_receipt_sha256": claimed_receipt_sha,
        "private_selection_opened": False,
        "candidate_identity_opened": False,
        "prospective_values_read": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compatibility", type=Path, required=True)
    parser.add_argument("--compatibility-sha256", required=True)
    parser.add_argument("--rank-protocol", type=Path, required=True)
    parser.add_argument("--rank-protocol-sha256", required=True)
    parser.add_argument("--actual-stage-a-public", type=Path, required=True)
    parser.add_argument("--actual-stage-a-public-sha256", required=True)
    parser.add_argument("--projected-stage-a-public", type=Path, required=True)
    parser.add_argument("--projected-stage-a-public-sha256", required=True)
    parser.add_argument("--claimed-projection-receipt", type=Path, required=True)
    parser.add_argument("--claimed-projection-receipt-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bindings = (
        (args.compatibility.resolve(), args.compatibility_sha256, "compatibility"),
        (args.rank_protocol.resolve(), args.rank_protocol_sha256, "rank protocol"),
        (args.actual_stage_a_public.resolve(), args.actual_stage_a_public_sha256, "actual Stage-A"),
        (args.projected_stage_a_public.resolve(), args.projected_stage_a_public_sha256, "projected Stage-A"),
        (
            args.claimed_projection_receipt.resolve(),
            args.claimed_projection_receipt_sha256,
            "projection receipt",
        ),
    )
    for path, expected, label in bindings:
        check(SHA_RE.fullmatch(expected) is not None and sha256(path) == expected, f"{label} file SHA")
    result = verify(
        read(args.compatibility.resolve()),
        args.compatibility_sha256,
        read(args.rank_protocol.resolve()),
        args.rank_protocol_sha256,
        read(args.actual_stage_a_public.resolve()),
        args.actual_stage_a_public_sha256,
        read(args.projected_stage_a_public.resolve()),
        args.projected_stage_a_public_sha256,
        read(args.claimed_projection_receipt.resolve()),
        args.claimed_projection_receipt_sha256,
    )
    write_exclusive(args.output.resolve(), result)
    print(
        canonical_bytes(
            {
                "status": result["status"],
                "projected_stage_a_public_sha256": result["projected_stage_a_public_sha256"],
                "prospective_values_read": False,
            }
        ).decode(),
        end="",
    )


if __name__ == "__main__":
    main()
