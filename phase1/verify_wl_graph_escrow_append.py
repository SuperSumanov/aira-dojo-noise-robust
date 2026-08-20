#!/usr/bin/env python3
"""Verify that a later WL prediction escrow is a blind, deterministic append.

This verifier deliberately has no label or effect-metric input.  It binds the
new artifact to the already frozen scorer/activation chain, checks the
independent numerical receipt, and proves that every row from the prior
snapshot is byte-semantically unchanged in the later snapshot.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ARMS = (
    "step_only_lr",
    "wl_graph_lr",
    "wl_graph_static_lr",
    "wl_graph_static_tfidf_lr",
)
ENDPOINT_FIELDS = (
    "card_id",
    "task",
    "run_id",
    "parent",
    "code_sha256",
    "generation_started_at_utc",
    "temporal_stratum",
    *ARMS,
)
PAIR_BASE_FIELDS = {
    "task",
    "run_id",
    "parent",
    "left",
    "right",
    "temporal_stratum",
    "pair_key_sha256",
}
PAIR_FIELDS = PAIR_BASE_FIELDS | {
    field
    for arm in ARMS
    for field in (f"{arm}_margin_left_minus_right", f"{arm}_selected")
}
STRATA = {"outcome_unread_support_only", "strict_post_activation_primary"}
FIXED_INPUT_KEYS = (
    "protocol_sha256",
    "bundle_sha256",
    "bundle_summary_sha256",
    "bundle_verification_sha256",
)
FORBIDDEN_TRACE_FRAGMENTS = (
    "/prospective_decision_v1/label",
    "/prospective_decision_v1/outcome",
    "/prospective_decision_v1/scorer",
    "/prospective_decision_v1/score_index",
    "decision_frozen_v11",
    "decision_extension_v11",
    "temporal_blind_0812_v1",
    "label_vault",
    "outcome_vault",
)
CREDENTIAL_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9._-]{16,}"),
    re.compile(rb"hf_[A-Za-z0-9]{16,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"xox[baprs]-[A-Za-z0-9-]{16,}"),
)
STATUS = "WL_GRAPH_ESCROW_APPEND_INDEPENDENTLY_VERIFIED"


class AppendVerificationError(RuntimeError):
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
        raise AppendVerificationError(f"expected JSON object: {path.name}")
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AppendVerificationError(f"blank JSONL row: {path.name}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AppendVerificationError(f"non-object JSONL row: {path.name}:{line_number}")
            yield value


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AppendVerificationError(f"invalid SHA256: {label}")
    return value


def _load_endpoint_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ENDPOINT_FIELDS:
            raise AppendVerificationError("endpoint CSV schema mismatch")
        for line_number, row in enumerate(reader, 2):
            identifier = row.get("card_id", "")
            if not identifier or identifier in rows:
                raise AppendVerificationError(f"duplicate/empty endpoint key at line {line_number}")
            if row.get("temporal_stratum") not in STRATA:
                raise AppendVerificationError("endpoint stratum mismatch")
            _require_sha256(row.get("code_sha256"), "endpoint code")
            for arm in ARMS:
                try:
                    value = float(row[arm])
                except (KeyError, ValueError) as error:
                    raise AppendVerificationError("invalid endpoint score") from error
                if not math.isfinite(value):
                    raise AppendVerificationError("non-finite endpoint score")
            rows[identifier] = dict(row)
    if not rows:
        raise AppendVerificationError("empty endpoint artifact")
    return rows


def _load_pair_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        if set(row) != PAIR_FIELDS:
            raise AppendVerificationError("pair JSONL schema mismatch")
        key = _require_sha256(row.get("pair_key_sha256"), "pair key")
        left, right = row.get("left"), row.get("right")
        if (
            not isinstance(left, str)
            or not isinstance(right, str)
            or not left
            or left >= right
            or key in rows
            or hashlib.sha256("\0".join((left, right)).encode()).hexdigest() != key
        ):
            raise AppendVerificationError("duplicate or invalid pair identity")
        if row.get("temporal_stratum") not in STRATA:
            raise AppendVerificationError("pair stratum mismatch")
        for arm in ARMS:
            margin = row[f"{arm}_margin_left_minus_right"]
            selected = row[f"{arm}_selected"]
            if not isinstance(margin, (int, float)) or not math.isfinite(float(margin)):
                raise AppendVerificationError("non-finite pair margin")
            expected = left if margin > 0 else right if margin < 0 else "tie"
            if selected != expected:
                raise AppendVerificationError("pair selection/margin mismatch")
        rows[key] = row
    return rows


def _counter_dict(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(collections.Counter(values).items()))


def _load_artifact(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    root = root.resolve()
    paths = {
        name: root / name
        for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")
    }
    manifest = read_object(root / "sha256_manifest.json")
    actual_manifest = {name: sha256_file(path) for name, path in paths.items()}
    if manifest != actual_manifest:
        raise AppendVerificationError("artifact SHA manifest mismatch")
    summary = read_object(paths["summary.json"])
    endpoints = _load_endpoint_rows(paths["endpoint_scores.csv"])
    pairs = _load_pair_rows(paths["pair_predictions.jsonl"])
    for pair in pairs.values():
        left, right = pair["left"], pair["right"]
        if left not in endpoints or right not in endpoints:
            raise AppendVerificationError("pair endpoint missing")
        endpoint = endpoints[left]
        if any(
            pair[field] != endpoint[endpoint_field]
            for field, endpoint_field in (
                ("task", "task"),
                ("run_id", "run_id"),
                ("parent", "parent"),
                ("temporal_stratum", "temporal_stratum"),
            )
        ) or any(
            endpoints[right][field] != endpoint[field]
            for field in ("task", "run_id", "parent", "temporal_stratum")
        ):
            raise AppendVerificationError("pair/endpoint metadata mismatch")

    run_stratum: dict[str, str] = {}
    for row in endpoints.values():
        prior = run_stratum.setdefault(row["run_id"], row["temporal_stratum"])
        if prior != row["temporal_stratum"]:
            raise AppendVerificationError("run spans temporal strata")
    inventory = summary.get("inventory", {})
    expected_inventory = {
        "endpoints": len(endpoints),
        "runs": len(run_stratum),
        "tasks": len({row["task"] for row in endpoints.values()}),
        "pairs": len(pairs),
        "run_strata": _counter_dict(run_stratum.values()),
        "pair_strata": _counter_dict(row["temporal_stratum"] for row in pairs.values()),
        "ties": {
            arm: sum(row[f"{arm}_selected"] == "tie" for row in pairs.values())
            for arm in ARMS
        },
    }
    if inventory != expected_inventory:
        raise AppendVerificationError("artifact inventory mismatch")
    if summary.get("outputs") != {
        "endpoint_scores_sha256": actual_manifest["endpoint_scores.csv"],
        "pair_predictions_sha256": actual_manifest["pair_predictions.jsonl"],
    }:
        raise AppendVerificationError("summary output hash mismatch")
    scope = summary.get("scope", {})
    if (
        summary.get("status") != "PROSPECTIVE_WL_GRAPH_PREDICTION_ESCROW_COMPLETE"
        or summary.get("protocol") != "prospective-wl-graph-escrow-v1"
        or scope.get("prospective_outcomes_read") is not False
        or scope.get("temporal_label_vault_read") is not False
        or scope.get("v11_frozen_or_extension_read") is not False
        or scope.get("effect_metrics_computed") != []
        or scope.get("gpu") != 0
        or scope.get("api_calls") != 0
        or scope.get("base_llm_updates") != 0
    ):
        raise AppendVerificationError("artifact blindness/resource scope mismatch")
    return summary, endpoints, pairs


def _scan_traces(paths: list[Path]) -> dict[str, Any]:
    receipts: dict[str, Any] = {}
    total_lines = 0
    for path in paths:
        digest = sha256_file(path)
        hits = collections.Counter()
        line_count = 0
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line_count += 1
                lowered = line.lower()
                for fragment in FORBIDDEN_TRACE_FRAGMENTS:
                    if fragment.lower() in lowered:
                        hits[fragment] += 1
        if hits:
            raise AppendVerificationError(f"forbidden path observed in trace: {path.name}")
        receipts[path.name] = {"sha256": digest, "lines": line_count, "forbidden_path_hits": 0}
        total_lines += line_count
    return {
        "method": "strict-any-syscall-path-fragment-v1",
        "forbidden_fragments": list(FORBIDDEN_TRACE_FRAGMENTS),
        "total_lines": total_lines,
        "total_forbidden_path_hits": 0,
        "traces": dict(sorted(receipts.items())),
    }


def _iter_scan_files(roots: list[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        candidates = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
        for path in candidates:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved


def _scan_credentials(roots: list[Path]) -> dict[str, Any]:
    files = 0
    bytes_scanned = 0
    for path in _iter_scan_files(roots):
        size = path.stat().st_size
        if size > 512 * 1024 * 1024:
            raise AppendVerificationError(f"credential scan refuses oversized file: {path.name}")
        blob = path.read_bytes()
        files += 1
        bytes_scanned += len(blob)
        if any(pattern.search(blob) for pattern in CREDENTIAL_PATTERNS):
            raise AppendVerificationError(f"credential-shaped content detected: {path.name}")
    return {
        "method": "high-confidence-credential-shapes-v1",
        "files_scanned": files,
        "bytes_scanned": bytes_scanned,
        "matches": 0,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    prior_summary, prior_endpoints, prior_pairs = _load_artifact(args.prior_artifact)
    current_summary, current_endpoints, current_pairs = _load_artifact(args.current_artifact)
    if sha256_file(args.prior_artifact / "summary.json") != args.expect_prior_summary_sha256:
        raise AppendVerificationError("prior summary hash mismatch")
    if prior_summary.get("inputs", {}).get("snapshot_sha256") != args.expect_prior_snapshot_sha256:
        raise AppendVerificationError("prior snapshot binding mismatch")
    if current_summary.get("inputs", {}).get("snapshot_sha256") != args.expect_current_snapshot_sha256:
        raise AppendVerificationError("current snapshot binding mismatch")
    if args.expect_prior_snapshot_sha256 == args.expect_current_snapshot_sha256:
        raise AppendVerificationError("current snapshot did not advance")

    if prior_summary.get("source_commit") != args.expect_scorer_commit or current_summary.get("source_commit") != args.expect_scorer_commit:
        raise AppendVerificationError("scorer commit changed across escrows")
    if prior_summary.get("source_file_sha256") != current_summary.get("source_file_sha256"):
        raise AppendVerificationError("scorer source identity changed")
    if prior_summary.get("activation") != current_summary.get("activation"):
        raise AppendVerificationError("activation boundary changed")
    for key in FIXED_INPUT_KEYS:
        if prior_summary.get("inputs", {}).get(key) != current_summary.get("inputs", {}).get(key):
            raise AppendVerificationError(f"frozen input changed: {key}")

    if not set(prior_endpoints).issubset(current_endpoints):
        raise AppendVerificationError("prior endpoint support is not a subset")
    if not set(prior_pairs).issubset(current_pairs):
        raise AppendVerificationError("prior pair support is not a subset")
    for key, row in prior_endpoints.items():
        if current_endpoints[key] != row:
            raise AppendVerificationError(f"prior endpoint row changed: {key}")
    for key, row in prior_pairs.items():
        if current_pairs[key] != row:
            raise AppendVerificationError(f"prior pair row changed: {key}")
    prior_runs = {row["run_id"] for row in prior_endpoints.values()}
    current_runs = {row["run_id"] for row in current_endpoints.values()}
    if len(current_endpoints) <= len(prior_endpoints) or len(current_runs) <= len(prior_runs) or len(current_pairs) < len(prior_pairs):
        raise AppendVerificationError("later escrow is not a growing append")

    independent = read_object(args.current_independent_verification)
    differences = independent.get("maximum_absolute_score_difference", {})
    if (
        independent.get("status") != "INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED"
        or independent.get("artifact_summary_sha256") != sha256_file(args.current_artifact / "summary.json")
        or independent.get("snapshot_sha256") != args.expect_current_snapshot_sha256
        or independent.get("endpoints") != len(current_endpoints)
        or independent.get("pairs") != len(current_pairs)
        or independent.get("prospective_outcomes_read") is not False
        or independent.get("effect_metrics_computed") != []
        or set(differences) != set(ARMS)
        or any(not isinstance(value, (int, float)) or value > 1e-12 for value in differences.values())
    ):
        raise AppendVerificationError("independent numerical receipt mismatch")

    strict_endpoints = {
        key: row for key, row in current_endpoints.items()
        if row["temporal_stratum"] == "strict_post_activation_primary"
    }
    strict_pairs = [
        row for row in current_pairs.values()
        if row["temporal_stratum"] == "strict_post_activation_primary"
    ]
    strict_task_pairs = collections.Counter(row["task"] for row in strict_pairs)
    dominant_share = max(strict_task_pairs.values(), default=0) / max(len(strict_pairs), 1)
    strict_inventory = {
        "endpoints": len(strict_endpoints),
        "runs": len({row["run_id"] for row in strict_endpoints.values()}),
        "tasks": len({row["task"] for row in strict_endpoints.values()}),
        "pairs": len(strict_pairs),
        "dominant_pair_task_share": dominant_share if strict_pairs else None,
        "pair_task_counts": dict(sorted(strict_task_pairs.items())),
    }
    fixed_gate = {
        "minimum_pairs": 1500,
        "minimum_runs": 150,
        "minimum_tasks": 15,
        "maximum_dominant_pair_task_share": 0.25,
    }
    gate_pass = (
        strict_inventory["pairs"] >= fixed_gate["minimum_pairs"]
        and strict_inventory["runs"] >= fixed_gate["minimum_runs"]
        and strict_inventory["tasks"] >= fixed_gate["minimum_tasks"]
        and dominant_share <= fixed_gate["maximum_dominant_pair_task_share"]
    )
    trace_audit = _scan_traces(args.trace)
    credential_audit = _scan_credentials(args.scan_root)
    return {
        "status": STATUS,
        "scorer_commit": args.expect_scorer_commit,
        "frozen_identity": {
            "activation": current_summary["activation"],
            **{key: current_summary["inputs"][key] for key in FIXED_INPUT_KEYS},
        },
        "prior": {
            "snapshot_sha256": args.expect_prior_snapshot_sha256,
            "summary_sha256": args.expect_prior_summary_sha256,
            "endpoints": len(prior_endpoints),
            "runs": len(prior_runs),
            "pairs": len(prior_pairs),
        },
        "current": {
            "snapshot_sha256": args.expect_current_snapshot_sha256,
            "summary_sha256": sha256_file(args.current_artifact / "summary.json"),
            "endpoints": len(current_endpoints),
            "runs": len(current_runs),
            "pairs": len(current_pairs),
        },
        "added": {
            "endpoints": len(current_endpoints) - len(prior_endpoints),
            "runs": len(current_runs) - len(prior_runs),
            "pairs": len(current_pairs) - len(prior_pairs),
        },
        "append_invariants": {
            "prior_endpoint_rows_exactly_unchanged": True,
            "prior_pair_rows_exactly_unchanged": True,
            "prior_endpoint_keys_subset": True,
            "prior_pair_keys_subset": True,
        },
        "strict_post_activation_inventory": strict_inventory,
        "fixed_effect_eligibility_gate": {**fixed_gate, "passed": gate_pass},
        "independent_maximum_absolute_score_difference": differences,
        "trace_audit": trace_audit,
        "credential_audit": credential_audit,
        "prospective_outcomes_read": False,
        "effect_metrics_computed": [],
        "gpu": 0,
        "api_calls": 0,
        "base_llm_updates": 0,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--prior-artifact", required=True, type=Path)
    value.add_argument("--current-artifact", required=True, type=Path)
    value.add_argument("--current-independent-verification", required=True, type=Path)
    value.add_argument("--expect-scorer-commit", required=True)
    value.add_argument("--expect-prior-summary-sha256", required=True)
    value.add_argument("--expect-prior-snapshot-sha256", required=True)
    value.add_argument("--expect-current-snapshot-sha256", required=True)
    value.add_argument("--trace", required=True, action="append", type=Path)
    value.add_argument("--scan-root", required=True, action="append", type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.output.exists():
        print("WL_GRAPH_APPEND_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(args)
        args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    except (AppendVerificationError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"WL_GRAPH_APPEND_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    current = receipt["current"]
    strict = receipt["strict_post_activation_inventory"]
    print(
        STATUS,
        f"endpoints={current['endpoints']}",
        f"pairs={current['pairs']}",
        f"strict_runs={strict['runs']}",
        f"strict_pairs={strict['pairs']}",
        f"effect_gate={receipt['fixed_effect_eligibility_gate']['passed']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
