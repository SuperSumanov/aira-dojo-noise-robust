#!/usr/bin/env python3
"""Build conservative release tiers from the value-free v11 content scan."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping


PROTOCOL_NAME = "decision-corpus-release-content-tier-v1"
SCAN_PROTOCOL = "release-content-scan-v1"
PRIVATE_SCAN_PROTOCOL = "release-content-scan-private-manifest-v1"
SHA_RE = re.compile(r"[0-9a-f]{64}")
ALLOWED_SCAN_FIELDS = {"stdout_tail", "code_literal_or_comment"}
WITHHELD_FIELDS = ["code", "obs.stdout_tail"]


class TierError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TierError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must contain an object")
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


def exact_fraction(numerator: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0 and 0 <= numerator <= denominator, "invalid fraction")
    value = Fraction(numerator, denominator)
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def read_card_index(cards_path: Path) -> tuple[dict[str, str], Counter[str], int]:
    by_hash: dict[str, str] = {}
    counts: Counter[str] = Counter()
    rows = 0
    with cards_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            require(isinstance(row, dict), f"cards row {line_number}")
            task = str((row.get("task") or {}).get("name") or "")
            card_id = str(row.get("id") or "")
            require(task != "" and card_id != "", f"cards identity row {line_number}")
            card_hash = sha256_text(card_id)
            require(card_hash not in by_hash, "duplicate card-id hash")
            by_hash[card_hash] = task
            counts[task] += 1
            rows += 1
    require(rows > 0, "empty cards")
    return by_hash, counts, rows


def validate_protocol(protocol: Mapping[str, Any]) -> None:
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol")
    require(protocol.get("version") == 1, "protocol version")
    require(
        protocol.get("status")
        == "FROZEN_AFTER_GLOBAL_SCAN_COUNTS_BEFORE_TASK_OR_CARD_DISPOSITION_READ",
        "protocol status",
    )
    freeze = protocol.get("freeze_observation")
    require(isinstance(freeze, Mapping), "freeze observation")
    for key in (
        "task_level_scan_summary_opened",
        "private_card_hash_hit_manifest_opened",
        "raw_matched_span_opened",
        "card_code_or_stdout_value_opened_for_tiering",
    ):
        require(freeze.get(key) is False, f"post-result tier freeze: {key}")
    rule = protocol.get("decision_rule")
    require(isinstance(rule, Mapping), "decision rule")
    require(rule.get("post_result_rule_change_allowed") is False, "post-result rule change")
    require(rule.get("whole_card_conservatism") is not None, "whole-card rule")
    security = protocol.get("security")
    require(isinstance(security, Mapping), "security")
    require(security.get("prospective_resources_read") is False, "prospective scope")
    require(security.get("raw_matched_span_emitted") is False, "raw span scope")
    require(security.get("gpu_paid_api_model_fit_base_update") == "0/0/0/0", "resource scope")


def build(
    protocol: Mapping[str, Any],
    protocol_sha: str,
    scan_summary: Mapping[str, Any],
    scan_summary_sha: str,
    scan_private: Mapping[str, Any],
    scan_private_sha: str,
    cards_path: Path,
    cards_sha: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_protocol(protocol)
    freeze = protocol["freeze_observation"]
    for value, label in (
        (protocol_sha, "protocol SHA"),
        (scan_summary_sha, "scan summary SHA"),
        (scan_private_sha, "scan private SHA"),
        (cards_sha, "cards SHA"),
    ):
        require(SHA_RE.fullmatch(value) is not None, label)
    require(scan_summary.get("protocol") == SCAN_PROTOCOL, "scan protocol")
    require(scan_summary.get("status") in {
        "PARTIAL_COVERAGE",
        "PARTIAL_COVERAGE_MATCHES_REQUIRE_REVIEW",
        "FULL_COVERAGE_MATCHES_REQUIRE_REVIEW",
        "FULL_COVERAGE_NO_MATCHES",
    }, "scan status")
    require(scan_private.get("protocol") == PRIVATE_SCAN_PROTOCOL, "private scan protocol")
    require(scan_summary["input"].get("cards_sha256") == cards_sha, "summary cards SHA")
    require(scan_private.get("cards_sha256") == cards_sha, "private cards SHA")
    coverage = scan_summary.get("coverage")
    totals = scan_summary.get("totals")
    require(isinstance(coverage, Mapping) and isinstance(totals, Mapping), "scan aggregates")
    require(coverage.get("tasks_scanned") == freeze.get("global_tasks_scanned"), "frozen tasks scanned")
    require(coverage.get("tasks_total") == freeze.get("global_tasks_total"), "frozen tasks total")
    require(totals.get("matched_patterns") == freeze.get("global_matched_patterns"), "frozen matches")
    require(
        totals.get("affected_card_sum_across_tasks")
        == freeze.get("global_affected_card_sum_across_tasks"),
        "frozen affected-card sum",
    )
    by_hash, cards_by_task, rows = read_card_index(cards_path)
    require(scan_summary["input"].get("cards_rows") == rows, "summary cards rows")
    task_summary = scan_summary.get("tasks")
    require(isinstance(task_summary, Mapping), "scan task summary")
    require(set(task_summary) == set(cards_by_task), "scan task set")
    for task, count in cards_by_task.items():
        require(task_summary[task].get("cards") == count, f"card count {task}")

    hit_fields: dict[str, set[str]] = defaultdict(set)
    seen_hit_keys: set[tuple[str, str, str]] = set()
    hits = scan_private.get("hits")
    require(isinstance(hits, list), "private hit list")
    for hit in hits:
        require(isinstance(hit, Mapping), "private hit row")
        require(set(hit) == {"task", "card_id_sha256", "field", "matched_span_sha256"}, "hit schema")
        task = str(hit["task"])
        card_hash = str(hit["card_id_sha256"])
        field = str(hit["field"])
        spans = hit["matched_span_sha256"]
        require(task in cards_by_task, "hit task")
        require(SHA_RE.fullmatch(card_hash) is not None and by_hash.get(card_hash) == task, "hit card hash")
        require(field in ALLOWED_SCAN_FIELDS, "hit field")
        require(
            isinstance(spans, list)
            and bool(spans)
            and spans == sorted(set(spans))
            and all(SHA_RE.fullmatch(str(value)) is not None for value in spans),
            "matched-span hash schema",
        )
        key = (task, card_hash, field)
        require(key not in seen_hit_keys, "duplicate hit key")
        seen_hit_keys.add(key)
        hit_fields[card_hash].add(field)

    matched_by_task_field: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {field: set() for field in ALLOWED_SCAN_FIELDS}
    )
    for card_hash, fields in hit_fields.items():
        task = by_hash[card_hash]
        for field in fields:
            matched_by_task_field[task][field].add(card_hash)
    for task, summary_row in task_summary.items():
        prepared = summary_row.get("prepared_text_available")
        require(isinstance(prepared, bool), f"prepared flag {task}")
        fields = matched_by_task_field[task]
        matched_cards = set().union(*fields.values())
        if prepared:
            require(summary_row.get("affected_cards") == len(matched_cards), f"affected cards {task}")
            require(
                summary_row.get("affected_card_fields")
                == {field: len(fields[field]) for field in sorted(ALLOWED_SCAN_FIELDS)},
                f"affected fields {task}",
            )
        else:
            require(not matched_cards, f"unscanned task has private hits {task}")

    private_rows: list[dict[str, Any]] = []
    public_tasks: dict[str, Any] = {}
    eligible_total = matched_total = unscanned_total = 0
    for task in sorted(cards_by_task):
        hashes = sorted(card_hash for card_hash, value in by_hash.items() if value == task)
        prepared = bool(task_summary[task]["prepared_text_available"])
        matched_hashes = {card_hash for card_hash in hashes if card_hash in hit_fields}
        unscanned_hashes = set(hashes) if not prepared else set()
        withheld_hashes = matched_hashes | unscanned_hashes
        eligible = len(hashes) - len(withheld_hashes)
        eligible_total += eligible
        matched_total += len(matched_hashes)
        unscanned_total += len(unscanned_hashes)
        public_tasks[task] = {
            "cards": len(hashes),
            "prepared_text_available": prepared,
            "content_review_eligible_cards": eligible,
            "structure_only_due_matched_pattern": len(matched_hashes),
            "structure_only_due_unscanned_task": len(unscanned_hashes),
            "structure_only_cards": len(withheld_hashes),
        }
        for card_hash in hashes:
            reasons: list[str] = []
            if card_hash in unscanned_hashes:
                reasons.append("UNSCANNED_TASK_NO_PREPARED_TEXT")
            if card_hash in matched_hashes:
                reasons.append("MATCHED_COMPETITION_DATA_PATTERN")
            withheld = card_hash in withheld_hashes
            private_rows.append({
                "card_id_sha256": card_hash,
                "task": task,
                "release_tier": "STRUCTURE_ONLY" if withheld else "CONTENT_REVIEW_ELIGIBLE",
                "reason_codes": reasons,
                "triggering_scan_fields": sorted(hit_fields.get(card_hash, set())),
                "withheld_fields": WITHHELD_FIELDS if withheld else [],
            })
    withheld_total = rows - eligible_total
    require(len(private_rows) == rows, "private tier map completeness")
    require(eligible_total + withheld_total == rows, "tier total")
    require(matched_total == len(hit_fields), "matched-card total")
    require(matched_total == totals.get("affected_card_sum_across_tasks"), "matched-card aggregate")
    public = {
        "protocol": "decision-corpus-release-content-tier-summary-v1",
        "status": "COMPLETE_PENDING_EXTERNAL_RELEASE_GATES",
        "protocol_sha256": protocol_sha,
        "scan_summary_sha256": scan_summary_sha,
        "scan_private_manifest_sha256": scan_private_sha,
        "cards_sha256": cards_sha,
        "totals": {
            "cards": rows,
            "content_review_eligible_cards": eligible_total,
            "structure_only_cards": withheld_total,
            "structure_only_due_matched_pattern": matched_total,
            "structure_only_due_unscanned_task": unscanned_total,
            "content_review_eligible_fraction": exact_fraction(eligible_total, rows),
        },
        "tasks": public_tasks,
        "release_boundary": {
            "content_review_eligible_is_release_clearance": False,
            "zero_scan_match_is_proof_of_no_leakage": False,
            "structure_metadata_still_requires_license_and_privacy_review": True,
            "raw_or_redacted_cards_materialized": False,
        },
        "scope": {
            "raw_card_ids_emitted": False,
            "card_id_hashes_emitted_publicly": False,
            "raw_card_values_emitted": False,
            "raw_matched_spans_emitted": False,
            "absolute_source_paths_emitted": False,
            "prospective_resources_read": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }
    private = {
        "protocol": "decision-corpus-release-content-tier-private-manifest-v1",
        "protocol_sha256": protocol_sha,
        "scan_summary_sha256": scan_summary_sha,
        "scan_private_manifest_sha256": scan_private_sha,
        "cards_sha256": cards_sha,
        "rows": private_rows,
        "scope": {
            "raw_card_ids_emitted": False,
            "raw_card_values_emitted": False,
            "raw_matched_spans_emitted": False,
            "prospective_resources_read": False,
        },
    }
    return public, private


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--scan-summary", type=Path, required=True)
    parser.add_argument("--scan-summary-sha256", required=True)
    parser.add_argument("--scan-private-manifest", type=Path, required=True)
    parser.add_argument("--scan-private-manifest-sha256", required=True)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--cards-sha256", required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bindings = (
        (args.protocol.resolve(), args.protocol_sha256, "protocol"),
        (args.scan_summary.resolve(), args.scan_summary_sha256, "scan summary"),
        (args.scan_private_manifest.resolve(), args.scan_private_manifest_sha256, "scan private manifest"),
        (args.cards.resolve(), args.cards_sha256, "cards"),
    )
    for path, expected, label in bindings:
        require(SHA_RE.fullmatch(expected) is not None and sha256_file(path) == expected, f"{label} file SHA")
    public, private = build(
        read_object(args.protocol.resolve()),
        args.protocol_sha256,
        read_object(args.scan_summary.resolve()),
        args.scan_summary_sha256,
        read_object(args.scan_private_manifest.resolve()),
        args.scan_private_manifest_sha256,
        args.cards.resolve(),
        args.cards_sha256,
    )
    write_exclusive(args.public_output.resolve(), public)
    write_exclusive(args.private_output.resolve(), private)
    print(canonical_bytes({
        "status": public["status"],
        "public_output_sha256": sha256_file(args.public_output.resolve()),
        "private_output_sha256": sha256_file(args.private_output.resolve()),
        "raw_values_emitted": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
