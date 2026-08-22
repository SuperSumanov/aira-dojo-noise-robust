#!/usr/bin/env python3
"""Build a grade-independent endpoint-hash orientation overlay for global pairs."""

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


PROTOCOL = "global-local-calibration-candidate-v2"
OUTPUT_PROTOCOL = "global-pair-hash-orientation-control-v2"
ROW_SCHEMA = "global-pair-hash-orientation-row-v2"
FROZEN_PROTOCOL_SHA256 = "3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9"
SHA_RX = re.compile(r"[0-9a-f]{64}")
OUTPUT_KEYS = {
    "schema_version",
    "source_row_number",
    "task",
    "source_identity_sha256",
    "unordered_pair_sha256",
    "hash_better",
    "hash_worse",
}


class HashControlError(RuntimeError):
    """Raised when the frozen negative-control contract cannot be honored."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value.lower()) is None:
        raise HashControlError(f"invalid {label}")
    return value.lower()


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    expected = require_sha(expected_sha, "protocol SHA")
    if expected != FROZEN_PROTOCOL_SHA256 or digest(path) != expected:
        raise HashControlError("candidate protocol SHA mismatch")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HashControlError("cannot read candidate protocol") from error
    control = value.get("hash_control") or {}
    scope = value.get("scope") or {}
    arms = {row.get("id"): row for row in value.get("arms") or [] if isinstance(row, dict)}
    if (
        value.get("protocol") != PROTOCOL
        or value.get("status") != "ARMS_FROZEN_IDENTITY_G0_BUDGET_EFFECT_BLOCKED"
        or set(arms) != {"L1", "Lbudget", "Gbudget", "G_to_L", "Ghash_to_L"}
        or control.get("seed") != 20260823
        or control.get("pair_level_independent_flips") is not False
        or control.get("shared_endpoint_order_is_transitive") is not True
        or control.get("true_grade_may_affect_hash_orientation") is not False
        or control.get("sha_collision_action") != "fail closed"
        or scope.get("gpu_jobs_authorized") != 0
        or scope.get("model_fits_authorized") != 0
        or scope.get("replay_or_effect_submission_authorized") is not False
    ):
        raise HashControlError("candidate protocol hash-control contract mismatch")
    return value


def load_train_rows(path: Path, expected_sha: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file() or digest(path) != require_sha(expected_sha, "global-train SHA"):
        raise HashControlError("global-train input SHA mismatch")
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    raise HashControlError("blank global-train row")
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise HashControlError("global-train row is not an object")
                missing = {"better", "worse", "task", "intask_split"} - set(row)
                if missing:
                    raise HashControlError(f"global-train schema missing {sorted(missing)}")
                better, worse, task = row["better"], row["worse"], row["task"]
                if (
                    row["intask_split"] != "train"
                    or not isinstance(better, str)
                    or not better
                    or not isinstance(worse, str)
                    or not worse
                    or better == worse
                    or not isinstance(task, str)
                    or not task
                ):
                    raise HashControlError(f"invalid train-only pair at row {number}")
                rows.append(row)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HashControlError("cannot read global-train input") from error
    if not rows:
        raise HashControlError("global-train input is empty")
    return rows


def build_overlay(rows: list[dict[str, Any]], seed: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    result: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    endpoint_tasks: dict[str, str] = {}
    per_task: Counter[str] = Counter()
    for number, row in enumerate(rows, 1):
        endpoints = sorted((row["better"], row["worse"]))
        task = row["task"]
        for endpoint in endpoints:
            previous_task = endpoint_tasks.setdefault(endpoint, task)
            if previous_task != task:
                raise HashControlError("endpoint reused across tasks")
        pair = (task, endpoints[0], endpoints[1])
        if pair in seen_pairs:
            raise HashControlError("duplicate unordered global-train pair")
        seen_pairs.add(pair)
        utilities = {card: text_digest(f"{seed}|{card}") for card in endpoints}
        if utilities[endpoints[0]] == utilities[endpoints[1]]:
            raise HashControlError("endpoint hash collision")
        hash_better = max(endpoints, key=lambda card: utilities[card])
        hash_worse = endpoints[0] if hash_better == endpoints[1] else endpoints[1]
        per_task[task] += 1
        safe_identity = {
            "intask_split": "train",
            "source_row_number": number,
            "task": task,
            "unordered_endpoints": endpoints,
        }
        result.append(
            {
                "schema_version": ROW_SCHEMA,
                "source_row_number": number,
                "task": task,
                "source_identity_sha256": text_digest(canonical(safe_identity)),
                "unordered_pair_sha256": text_digest(canonical({"task": task, "endpoints": endpoints})),
                "hash_better": hash_better,
                "hash_worse": hash_worse,
            }
        )
    return result, dict(sorted(per_task.items()))


def write_rows(path: Path, rows: list[dict[str, Any]]) -> str:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            if set(row) != OUTPUT_KEYS:
                raise HashControlError("internal overlay schema mismatch")
            handle.write(canonical(row) + "\n")
    return digest(path)


def produce(
    protocol_path: Path,
    expected_protocol_sha: str,
    global_train_path: Path,
    expected_global_train_sha: str,
    out_dir: Path,
) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite hash-control output: {out_dir}")
    protocol = load_protocol(protocol_path, expected_protocol_sha)
    rows = load_train_rows(global_train_path, expected_global_train_sha)
    seed = protocol["hash_control"]["seed"]
    overlay, per_task = build_overlay(rows, seed)

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp.", dir=out_dir.parent))
    try:
        overlay_sha = write_rows(temporary / "orientation_overlay.jsonl", overlay)
        summary = {
            "protocol": OUTPUT_PROTOCOL,
            "status": "HASH_ORIENTATION_OVERLAY_READY_EFFECT_BLOCKED",
            "inputs": {
                "candidate_protocol_sha256": require_sha(expected_protocol_sha, "protocol SHA"),
                "global_train_sha256": require_sha(expected_global_train_sha, "global-train SHA"),
            },
            "orientation": {
                "seed": seed,
                "endpoint_utility": protocol["hash_control"]["endpoint_utility"],
                "larger_hash_is_better": True,
                "pair_level_independent_flips": False,
                "shared_endpoint_order_is_transitive": True,
                "true_grade_used": False,
            },
            "counts": {
                "rows": len(overlay),
                "unique_unordered_pairs": len(overlay),
                "tasks": len(per_task),
                "per_task": per_task,
            },
            "privacy": {
                "source_outcome_fields_written": [],
                "gap_raw_written": False,
                "original_better_worse_relation_written": False,
                "source_row_commitment_written": False,
                "safe_identity_commitment_written": True,
                "grade_derived_commitment_written": False,
                "code_opened": False,
            },
            "gates": {
                "train_only_input": True,
                "row_order_preserved": True,
                "effect_submission_authorized": False,
                "gpu_jobs_authorized": 0,
                "model_fits_authorized": 0,
            },
            "outputs": {"orientation_overlay_sha256": overlay_sha},
            "implementation": {"script_sha256": digest(Path(__file__))},
        }
        (temporary / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, out_dir)
    except Exception:
        for child in temporary.iterdir():
            child.unlink()
        temporary.rmdir()
        raise
    return summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", default=FROZEN_PROTOCOL_SHA256)
    parser.add_argument("--global-train", required=True, type=Path)
    parser.add_argument("--expect-global-train-sha256", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    summary = produce(
        args.protocol,
        args.expect_protocol_sha256,
        args.global_train,
        args.expect_global_train_sha256,
        args.out_dir,
    )
    print(canonical({
        "status": summary["status"],
        "rows": summary["counts"]["rows"],
        "effect_submission_authorized": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
