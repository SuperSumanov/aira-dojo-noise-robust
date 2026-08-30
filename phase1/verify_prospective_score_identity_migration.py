#!/usr/bin/env python3
"""Independently verify exact score-code epochs without opening score values."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


LEGACY_GIT_COMMIT = "90842c49dbd73d41d405a5ecdad2224ee447b375"
LEGACY_TOP_SOURCE_SHA256 = (
    "f7fc2aa8f03ed52e5b9431b925581741ce3a17867fb0a25577deae805bd0ba01"
)
LEGACY_NESTED_SOURCE_SHA256 = (
    "678ecb2a0651135a679d00a06005c0fbfc83673ad7ba833f86a17c63f4e47ccf"
)
REGISTRY_KEYS = {
    "drop_id",
    "intake_dir",
    "intake_summary_sha256",
    "score_dir",
    "score_summary_sha256",
}
SHA256_RX = re.compile(r"[0-9a-f]{64}")
COMMIT_RX = re.compile(r"[0-9a-f]{40}")


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RX.fullmatch(value) is None:
        raise VerificationError(f"invalid {label} SHA-256")
    return value


def load_json(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise VerificationError(f"unsafe or missing {label}")
    if sha256(path) != expected_sha256:
        raise VerificationError(f"{label} SHA-256 mismatch")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot parse {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label} must be an object")
    return value


def classify(
    actual: tuple[Any, Any],
    current: tuple[str, str],
    legacy_source: str,
    label: str,
) -> str:
    if actual == current:
        return "current"
    if actual == (LEGACY_GIT_COMMIT, legacy_source):
        return "legacy"
    raise VerificationError(f"unknown {label} code identity")


def verify(args: argparse.Namespace) -> dict[str, Any]:
    registry = args.registry.resolve()
    expected_registry_sha = require_hash(args.expect_registry_sha256, "registry")
    if not registry.is_file() or registry.is_symlink() or sha256(registry) != expected_registry_sha:
        raise VerificationError("score registry SHA-256 mismatch")
    if COMMIT_RX.fullmatch(args.current_git_commit) is None:
        raise VerificationError("invalid current git commit")
    current_top = (
        args.current_git_commit,
        require_hash(args.current_top_source_sha256, "current top source"),
    )
    current_nested = (
        args.current_git_commit,
        require_hash(args.current_nested_source_sha256, "current nested source"),
    )

    epoch_counts = {"legacy": 0, "current": 0}
    nested_epoch_counts = {"legacy": 0, "current": 0}
    without_nested = 0
    seen_drop_ids: set[str] = set()
    lines = registry.read_text(encoding="utf-8").splitlines()
    if not lines or len(lines) > args.max_transactions:
        raise VerificationError("score registry size outside verifier cap")
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise VerificationError(f"invalid registry JSON at line {line_number}") from error
        if not isinstance(row, dict) or set(row) != REGISTRY_KEYS:
            raise VerificationError(f"registry schema mismatch at line {line_number}")
        drop_id = row.get("drop_id")
        if not isinstance(drop_id, str) or not drop_id or drop_id in seen_drop_ids:
            raise VerificationError("invalid or duplicate registry drop ID")
        seen_drop_ids.add(drop_id)
        score_dir = Path(str(row.get("score_dir"))).resolve()
        top = load_json(
            score_dir / "summary.json",
            require_hash(row.get("score_summary_sha256"), "score summary"),
            "score summary",
        )
        top_epoch = classify(
            (top.get("git_commit"), top.get("source_sha256")),
            current_top,
            LEGACY_TOP_SOURCE_SHA256,
            "top-level score",
        )
        epoch_counts[top_epoch] += 1
        outputs = top.get("outputs")
        if not isinstance(outputs, dict):
            raise VerificationError("score outputs must be an object")
        nested_relative = outputs.get("nested_scorer_summary")
        if nested_relative is None:
            if outputs.get("nested_scorer_summary_sha256") is not None:
                raise VerificationError("empty nested score carries a summary SHA")
            without_nested += 1
            continue
        if nested_relative != "scores/summary.json":
            raise VerificationError("nested score path is not fixed and relative")
        nested = load_json(
            score_dir / nested_relative,
            require_hash(
                outputs.get("nested_scorer_summary_sha256"),
                "nested score summary",
            ),
            "nested score summary",
        )
        nested_epoch = classify(
            (nested.get("git_commit"), nested.get("source_sha256")),
            current_nested,
            LEGACY_NESTED_SOURCE_SHA256,
            "nested score",
        )
        if nested_epoch != top_epoch:
            raise VerificationError("mixed top-level and nested score code epochs")
        nested_epoch_counts[nested_epoch] += 1

    expected_counts = {
        "legacy": args.expect_legacy_transactions,
        "current": args.expect_current_transactions,
    }
    if epoch_counts != expected_counts:
        raise VerificationError("score epoch transaction count mismatch")
    if without_nested != args.expect_without_nested:
        raise VerificationError("transactions-without-nested count mismatch")
    if sum(nested_epoch_counts.values()) + without_nested != len(lines):
        raise VerificationError("nested score coverage accounting mismatch")
    return {
        "status": "PROSPECTIVE_SCORE_IDENTITY_MIGRATION_INDEPENDENT_VERIFICATION_PASS",
        "protocol": "prospective-score-identity-migration-verifier-v1",
        "registry_sha256": expected_registry_sha,
        "transactions": len(lines),
        "top_level_epoch_counts": epoch_counts,
        "nested_epoch_counts": nested_epoch_counts,
        "transactions_without_nested": without_nested,
        "security": {
            "summary_json_only": True,
            "blind_score_csv_opened": False,
            "intake_manifest_opened": False,
            "label_vault_opened": False,
            "outcomes_predictions_accuracy_utility_read": False,
            "candidate_identities_emitted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--expect-registry-sha256", required=True)
    parser.add_argument("--current-git-commit", required=True)
    parser.add_argument("--current-top-source-sha256", required=True)
    parser.add_argument("--current-nested-source-sha256", required=True)
    parser.add_argument("--expect-legacy-transactions", required=True, type=int)
    parser.add_argument("--expect-current-transactions", required=True, type=int)
    parser.add_argument("--expect-without-nested", required=True, type=int)
    parser.add_argument("--max-transactions", type=int, default=512)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if min(
        args.expect_legacy_transactions,
        args.expect_current_transactions,
        args.expect_without_nested,
    ) < 0 or args.max_transactions <= 0:
        raise VerificationError("invalid expected count or verifier cap")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError(f"refusing to overwrite verifier output: {out}")
    receipt = verify(args)
    blob = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, "wb") as handle:
        handle.write(blob)
    print(
        receipt["status"],
        f"transactions={receipt['transactions']}",
        "values_read=false",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
