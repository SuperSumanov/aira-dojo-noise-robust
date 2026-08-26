"""Join promoted independent receipts without opening prediction pair files."""

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
STATUS = "RECEIPT_CERTIFIED_EXACT_CANONICAL_COMMON_SUPPORT"
SHA_RE = re.compile(r"[0-9a-f]{64}")


class ReceiptSupportError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReceiptSupportError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected object: {path.name}")
    return value


def read_state(path: Path, fields: int) -> tuple[str, Path, str]:
    rows = path.read_text(encoding="utf-8").strip().split("\t")
    require(len(rows) == fields, f"state field count mismatch: {path.name}")
    snapshot, artifact, summary_sha = rows[:3]
    require(SHA_RE.fullmatch(snapshot) is not None, "invalid state snapshot")
    require(SHA_RE.fullmatch(summary_sha) is not None, "invalid state summary hash")
    artifact_path = Path(artifact).resolve()
    require(artifact_path.is_dir(), "state artifact missing")
    require(sha256_file(artifact_path / "summary.json") == summary_sha, "state summary hash mismatch")
    if fields == 4:
        require(rows[3].isdigit() and int(rows[3]) > 0, "invalid WL all-run count")
    return snapshot, artifact_path, summary_sha


def command_option(tokens: list[str], option: str) -> str:
    locations = [index for index, token in enumerate(tokens) if token == option]
    require(len(locations) == 1, f"command option count mismatch: {option}")
    index = locations[0]
    require(index + 1 < len(tokens), f"command option missing value: {option}")
    return tokens[index + 1]


def validate_command(
    path: Path,
    *,
    family: str,
    snapshot: str,
    artifact: Path,
    receipt: Path,
) -> str:
    require(path.parent.resolve() == artifact.parent.resolve(), f"{family} command is outside artifact receipt root")
    require(receipt.parent.resolve() == artifact.parent.resolve(), f"{family} receipt is outside artifact receipt root")
    tokens = shlex.split(path.read_text(encoding="utf-8"), posix=True)
    module = command_option(tokens, "-m")
    expected_module = {
        "wl": "phase1.verify_prospective_wl_graph_escrow",
        "transition": "phase1.verify_prospective_transition_future_escrow",
    }[family]
    require(module == expected_module, f"{family} verifier module mismatch")
    require(command_option(tokens, "--expect-snapshot-sha256") == snapshot, f"{family} command snapshot mismatch")
    require(Path(command_option(tokens, "--artifact")).resolve() == artifact.resolve(), f"{family} command artifact mismatch")
    require(Path(command_option(tokens, "--output")).resolve() == receipt.resolve(), f"{family} command output mismatch")
    return sha256_file(path)


def receipt_scope(receipt: dict[str, Any], family: str) -> None:
    if family == "wl":
        require(receipt.get("prospective_outcomes_read") is False, "WL outcome scope mismatch")
        require(receipt.get("effect_metrics_computed") == [], "WL effect scope mismatch")
    else:
        scope = receipt.get("scope", {})
        require(scope.get("prospective_outcomes_read") is False, "transition outcome scope mismatch")
        require(scope.get("effect_metrics_computed") == [], "transition effect scope mismatch")


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol = read_object(args.protocol)
    require(sha256_file(args.protocol) == args.expect_protocol_sha256, "protocol hash mismatch")
    require(protocol.get("protocol") == PROTOCOL, "protocol identity mismatch")
    require(protocol.get("claim", {}).get("status") == STATUS, "claim status mismatch")

    contracts = protocol.get("verifier_contracts", {})
    require(set(contracts) == {"wl", "transition"}, "verifier contract set mismatch")
    source_paths = {"wl": args.wl_verifier_source, "transition": args.transition_verifier_source}
    for family, path in source_paths.items():
        require(
            sha256_file(path) == contracts[family]["source_sha256"],
            f"{family} verifier source hash mismatch",
        )

    wl_snapshot, wl_artifact, wl_summary_sha = read_state(args.wl_state, 4)
    transition_snapshot, transition_artifact, transition_summary_sha = read_state(args.transition_state, 3)
    require(wl_snapshot == transition_snapshot == args.expect_snapshot_sha256, "state snapshot mismatch")

    receipts = {
        "wl": read_object(args.wl_independent_receipt),
        "transition": read_object(args.transition_independent_receipt),
    }
    summary_hashes = {"wl": wl_summary_sha, "transition": transition_summary_sha}
    receipt_paths = {
        "wl": args.wl_independent_receipt,
        "transition": args.transition_independent_receipt,
    }
    command_paths = {
        "wl": args.wl_verifier_command,
        "transition": args.transition_verifier_command,
    }
    artifacts = {"wl": wl_artifact, "transition": transition_artifact}
    command_hashes = {
        family: validate_command(
            command_paths[family],
            family=family,
            snapshot=wl_snapshot,
            artifact=artifacts[family],
            receipt=receipt_paths[family],
        )
        for family in ("wl", "transition")
    }
    pair_counts: dict[str, int] = {}
    for family, receipt in receipts.items():
        require(receipt.get("status") == contracts[family]["independent_status"], f"{family} status mismatch")
        require(
            receipt.get("artifact_summary_sha256") == summary_hashes[family],
            f"{family} receipt summary binding mismatch",
        )
        pairs = receipt.get("pairs")
        require(isinstance(pairs, int) and pairs > 0, f"{family} pair count invalid")
        pair_counts[family] = pairs
        receipt_scope(receipt, family)
    require(pair_counts["wl"] == pair_counts["transition"], "receipt-certified pair counts differ")
    require(receipts["wl"].get("snapshot_sha256") == wl_snapshot, "WL receipt snapshot mismatch")
    transition_receipt_snapshot = receipts["transition"].get("snapshot_sha256")
    require(
        transition_receipt_snapshot in (None, transition_snapshot),
        "transition receipt snapshot mismatch",
    )

    source_contracts = {
        family: {
            "commit": contracts[family]["commit"],
            "independent_status": contracts[family]["independent_status"],
            "source_sha256": contracts[family]["source_sha256"],
        }
        for family in ("wl", "transition")
    }
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
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
                "artifact_summary_sha256": summary_hashes[family],
                "independent_receipt_sha256": sha256_file(receipt_paths[family]),
                "independent_verifier_command_sha256": command_hashes[family],
                "independent_status": receipts[family]["status"],
                "pairs": pair_counts[family],
                "state_sha256": sha256_file(args.wl_state if family == "wl" else args.transition_state),
            }
            for family in ("wl", "transition")
        },
        "source_contracts": source_contracts,
        "scope": protocol["scope"],
        "input_policy": protocol["inputs"],
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--protocol", required=True, type=Path)
    value.add_argument("--expect-protocol-sha256", required=True)
    value.add_argument("--expect-snapshot-sha256", required=True)
    value.add_argument("--wl-state", required=True, type=Path)
    value.add_argument("--transition-state", required=True, type=Path)
    value.add_argument("--wl-independent-receipt", required=True, type=Path)
    value.add_argument("--transition-independent-receipt", required=True, type=Path)
    value.add_argument("--wl-verifier-command", required=True, type=Path)
    value.add_argument("--transition-verifier-command", required=True, type=Path)
    value.add_argument("--wl-verifier-source", required=True, type=Path)
    value.add_argument("--transition-verifier-source", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.output.exists():
        print("RECEIPT_SUPPORT_ERROR: output exists", file=sys.stderr)
        return 2
    temporary = args.output.with_name(f"{args.output.name}.tmp.{os.getpid()}")
    try:
        receipt = build(args)
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, args.output)
    except (ReceiptSupportError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        if temporary.exists():
            temporary.unlink()
        print(f"RECEIPT_SUPPORT_ERROR: {error}", file=sys.stderr)
        return 2
    print(STATUS, f"pairs={receipt['receipt_certified_common_support']['pairs']}", "outcomes_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
