"""Independently verify receipt-certified common support without prediction files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "prediction-receipt-common-support-v1"
CANDIDATE_STATUS = "RECEIPT_CERTIFIED_EXACT_CANONICAL_COMMON_SUPPORT"
STATUS = "INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(ValueError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            value.update(chunk)
    return value.hexdigest()


def object_from(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(type(value) is dict, f"not a JSON object: {path.name}")
    return value


def state_from(path: Path, count: int) -> tuple[str, Path, str]:
    values = path.read_text(encoding="utf-8").strip().split("\t")
    check(len(values) == count, f"state arity mismatch: {path.name}")
    snapshot, artifact_text, summary_hash = values[:3]
    check(SHA_RE.fullmatch(snapshot) is not None, "invalid state snapshot")
    check(SHA_RE.fullmatch(summary_hash) is not None, "invalid state summary digest")
    artifact = Path(artifact_text).resolve()
    check(artifact.is_dir(), "state artifact directory absent")
    check(digest(artifact / "summary.json") == summary_hash, "state-to-summary binding failed")
    if count == 4:
        check(values[3].isdecimal() and int(values[3]) >= 1, "invalid WL registry count")
    return snapshot, artifact, summary_hash


def one_option(tokens: list[str], name: str) -> str:
    indices = [position for position, token in enumerate(tokens) if token == name]
    check(len(indices) == 1, f"unexpected option multiplicity: {name}")
    position = indices[0]
    check(position + 1 < len(tokens), f"option lacks argument: {name}")
    return tokens[position + 1]


def command_binding(
    path: Path,
    family: str,
    snapshot: str,
    artifact: Path,
    receipt: Path,
) -> str:
    check(path.parent.resolve() == artifact.parent.resolve(), f"{family} command root mismatch")
    check(receipt.parent.resolve() == artifact.parent.resolve(), f"{family} receipt root mismatch")
    words = shlex.split(path.read_text(encoding="utf-8"), posix=True)
    expected_module = (
        "phase1.verify_prospective_wl_graph_escrow"
        if family == "wl"
        else "phase1.verify_prospective_transition_future_escrow"
    )
    check(one_option(words, "-m") == expected_module, f"{family} verifier identity mismatch")
    check(one_option(words, "--expect-snapshot-sha256") == snapshot, f"{family} command snapshot mismatch")
    check(Path(one_option(words, "--artifact")).resolve() == artifact.resolve(), f"{family} command artifact mismatch")
    check(Path(one_option(words, "--output")).resolve() == receipt.resolve(), f"{family} command receipt mismatch")
    return digest(path)


def scope_is_blind(receipt: dict[str, Any], family: str) -> None:
    if family == "wl":
        check(receipt.get("prospective_outcomes_read") is False, "WL outcome attestation failed")
        check(receipt.get("effect_metrics_computed") == [], "WL effect attestation failed")
    else:
        scope = receipt.get("scope")
        check(type(scope) is dict, "transition scope absent")
        check(scope.get("prospective_outcomes_read") is False, "transition outcome attestation failed")
        check(scope.get("effect_metrics_computed") == [], "transition effect attestation failed")


def verify(args: argparse.Namespace) -> dict[str, Any]:
    protocol = object_from(args.protocol)
    check(digest(args.protocol) == args.expect_protocol_sha256, "protocol digest mismatch")
    check(protocol.get("protocol") == PROTOCOL, "protocol name mismatch")
    check(protocol.get("claim", {}).get("status") == CANDIDATE_STATUS, "protocol claim mismatch")
    contracts = protocol.get("verifier_contracts")
    check(type(contracts) is dict and set(contracts) == {"wl", "transition"}, "contract family mismatch")

    sources = {
        "wl": args.wl_verifier_source,
        "transition": args.transition_verifier_source,
    }
    for family in ("wl", "transition"):
        check(digest(sources[family]) == contracts[family]["source_sha256"], f"{family} source digest mismatch")

    wl_snapshot, wl_artifact, wl_summary = state_from(args.wl_state, 4)
    tr_snapshot, tr_artifact, tr_summary = state_from(args.transition_state, 3)
    check(wl_snapshot == tr_snapshot == args.expect_snapshot_sha256, "promoted snapshots differ")

    paths = {
        "wl": {
            "receipt": args.wl_independent_receipt,
            "command": args.wl_verifier_command,
            "state": args.wl_state,
            "artifact": wl_artifact,
            "summary": wl_summary,
        },
        "transition": {
            "receipt": args.transition_independent_receipt,
            "command": args.transition_verifier_command,
            "state": args.transition_state,
            "artifact": tr_artifact,
            "summary": tr_summary,
        },
    }
    receipts: dict[str, dict[str, Any]] = {}
    command_hashes: dict[str, str] = {}
    pair_counts: dict[str, int] = {}
    for family in ("wl", "transition"):
        item = paths[family]
        receipt = object_from(item["receipt"])
        receipts[family] = receipt
        check(receipt.get("status") == contracts[family]["independent_status"], f"{family} receipt status mismatch")
        check(receipt.get("artifact_summary_sha256") == item["summary"], f"{family} summary receipt mismatch")
        count = receipt.get("pairs")
        check(type(count) is int and count > 0, f"{family} pair count invalid")
        pair_counts[family] = count
        scope_is_blind(receipt, family)
        command_hashes[family] = command_binding(
            item["command"], family, wl_snapshot, item["artifact"], item["receipt"]
        )
    check(pair_counts["wl"] == pair_counts["transition"], "canonical pair counts differ")
    check(receipts["wl"].get("snapshot_sha256") == wl_snapshot, "WL receipt snapshot mismatch")
    check(receipts["transition"].get("snapshot_sha256") in (None, tr_snapshot), "transition receipt snapshot mismatch")

    expected = {
        "protocol": PROTOCOL,
        "status": CANDIDATE_STATUS,
        "snapshot_sha256": wl_snapshot,
        "receipt_certified_common_support": {
            "pairs": pair_counts["wl"],
            "same_immutable_snapshot": True,
            "same_canonical_pair_population_certified": True,
            "basis": protocol["claim"]["basis"],
            "pair_identity_or_orientation_reopened": False,
        },
        "families": {
            family: {
                "artifact_summary_sha256": paths[family]["summary"],
                "independent_receipt_sha256": digest(paths[family]["receipt"]),
                "independent_verifier_command_sha256": command_hashes[family],
                "independent_status": receipts[family]["status"],
                "pairs": pair_counts[family],
                "state_sha256": digest(paths[family]["state"]),
            }
            for family in ("wl", "transition")
        },
        "source_contracts": {
            family: {
                "commit": contracts[family]["commit"],
                "independent_status": contracts[family]["independent_status"],
                "source_sha256": contracts[family]["source_sha256"],
            }
            for family in ("wl", "transition")
        },
        "scope": protocol["scope"],
        "input_policy": protocol["inputs"],
    }
    candidate = object_from(args.candidate)
    check(candidate == expected, "candidate differs from independent reconstruction")
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "snapshot_sha256": wl_snapshot,
        "pairs": pair_counts["wl"],
        "candidate_sha256": digest(args.candidate),
        "candidate_exact": True,
        "same_canonical_pair_population_certified": True,
        "prediction_pair_files_opened": False,
        "prediction_values_accessed": False,
        "prospective_outcomes_read": False,
        "effect_metrics_computed": [],
        "producer_imported": False,
    }


def arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--expect-snapshot-sha256", required=True)
    parser.add_argument("--wl-state", required=True, type=Path)
    parser.add_argument("--transition-state", required=True, type=Path)
    parser.add_argument("--wl-independent-receipt", required=True, type=Path)
    parser.add_argument("--transition-independent-receipt", required=True, type=Path)
    parser.add_argument("--wl-verifier-command", required=True, type=Path)
    parser.add_argument("--transition-verifier-command", required=True, type=Path)
    parser.add_argument("--wl-verifier-source", required=True, type=Path)
    parser.add_argument("--transition-verifier-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = arguments().parse_args()
    if args.output.exists():
        print("RECEIPT_SUPPORT_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    temporary = args.output.with_name(f"{args.output.name}.tmp.{os.getpid()}")
    try:
        result = verify(args)
        temporary.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, args.output)
    except (VerificationError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        if temporary.exists():
            temporary.unlink()
        print(f"RECEIPT_SUPPORT_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    print(STATUS, f"pairs={result['pairs']}", "outcomes_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
