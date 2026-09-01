#!/usr/bin/env python3
"""Independent verifier for conservative Decision Corpus release-content tiers."""

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


SHA_RE = re.compile(r"[0-9a-f]{64}")
FIELDS = {"stdout_tail", "code_literal_or_comment"}
WITHHELD = ["code", "obs.stdout_tail"]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"{path} object")
    return value


def fraction_payload(numerator: int, denominator: int) -> dict[str, Any]:
    value = Fraction(numerator, denominator)
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def verify(
    protocol: Mapping[str, Any],
    protocol_sha: str,
    summary: Mapping[str, Any],
    summary_sha: str,
    scan_private: Mapping[str, Any],
    scan_private_sha: str,
    cards_path: Path,
    cards_sha: str,
    claimed_public: Mapping[str, Any],
    claimed_public_sha: str,
    claimed_private: Mapping[str, Any],
    claimed_private_sha: str,
) -> dict[str, Any]:
    for value in (
        protocol_sha, summary_sha, scan_private_sha, cards_sha,
        claimed_public_sha, claimed_private_sha,
    ):
        check(SHA_RE.fullmatch(value) is not None, "SHA syntax")
    check(protocol.get("protocol") == "decision-corpus-release-content-tier-v1", "protocol")
    check(protocol.get("version") == 1, "protocol version")
    check(
        protocol.get("status")
        == "FROZEN_AFTER_GLOBAL_SCAN_COUNTS_BEFORE_TASK_OR_CARD_DISPOSITION_READ",
        "protocol status",
    )
    freeze = protocol.get("freeze_observation")
    check(isinstance(freeze, Mapping), "freeze observation")
    for key in (
        "task_level_scan_summary_opened",
        "private_card_hash_hit_manifest_opened",
        "raw_matched_span_opened",
        "card_code_or_stdout_value_opened_for_tiering",
    ):
        check(freeze.get(key) is False, f"post-result freeze {key}")
    rule = protocol.get("decision_rule")
    check(isinstance(rule, Mapping), "decision rule")
    check(rule.get("post_result_rule_change_allowed") is False, "post-result rule change")
    security = protocol.get("security")
    check(isinstance(security, Mapping), "protocol security")
    check(security.get("prospective_resources_read") is False, "prospective scope")
    check(security.get("raw_matched_span_emitted") is False, "raw span scope")
    check(security.get("gpu_paid_api_model_fit_base_update") == "0/0/0/0", "resource scope")
    check(summary.get("protocol") == "release-content-scan-v1", "summary protocol")
    check(summary.get("status") in {
        "PARTIAL_COVERAGE",
        "PARTIAL_COVERAGE_MATCHES_REQUIRE_REVIEW",
        "FULL_COVERAGE_MATCHES_REQUIRE_REVIEW",
        "FULL_COVERAGE_NO_MATCHES",
    }, "summary status")
    check(scan_private.get("protocol") == "release-content-scan-private-manifest-v1", "private protocol")
    check(summary["input"].get("cards_sha256") == cards_sha, "summary cards")
    check(scan_private.get("cards_sha256") == cards_sha, "private cards")
    coverage = summary.get("coverage")
    totals = summary.get("totals")
    check(isinstance(coverage, Mapping) and isinstance(totals, Mapping), "scan aggregates")
    check(coverage.get("tasks_scanned") == freeze.get("global_tasks_scanned"), "frozen tasks scanned")
    check(coverage.get("tasks_total") == freeze.get("global_tasks_total"), "frozen tasks total")
    check(totals.get("matched_patterns") == freeze.get("global_matched_patterns"), "frozen matches")
    check(
        totals.get("affected_card_sum_across_tasks")
        == freeze.get("global_affected_card_sum_across_tasks"),
        "frozen affected-card sum",
    )

    by_hash: dict[str, str] = {}
    task_counts: Counter[str] = Counter()
    with cards_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            task = str(row["task"]["name"])
            card_hash = hashlib.sha256(str(row["id"]).encode("utf-8")).hexdigest()
            check(card_hash not in by_hash, "duplicate card hash")
            by_hash[card_hash] = task
            task_counts[task] += 1
    check(len(by_hash) == summary["input"]["cards_rows"], "cards rows")
    check(set(task_counts) == set(summary["tasks"]), "task set")
    for task, count in task_counts.items():
        check(summary["tasks"][task].get("cards") == count, f"task card count {task}")

    trigger_fields: dict[str, set[str]] = defaultdict(set)
    seen: set[tuple[str, str, str]] = set()
    for hit in scan_private.get("hits", []):
        check(set(hit) == {"task", "card_id_sha256", "field", "matched_span_sha256"}, "hit schema")
        task, card_hash, field = str(hit["task"]), str(hit["card_id_sha256"]), str(hit["field"])
        check(by_hash.get(card_hash) == task and field in FIELDS, "hit binding")
        key = (task, card_hash, field)
        check(key not in seen, "duplicate hit")
        seen.add(key)
        spans = hit["matched_span_sha256"]
        check(
            isinstance(spans, list) and bool(spans) and spans == sorted(set(spans))
            and all(SHA_RE.fullmatch(str(value)) is not None for value in spans),
            "span hashes",
        )
        trigger_fields[card_hash].add(field)

    matched_by_task_field: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {field: set() for field in FIELDS}
    )
    for card_hash, fields in trigger_fields.items():
        task = by_hash[card_hash]
        for field in fields:
            matched_by_task_field[task][field].add(card_hash)
    for task, summary_row in summary["tasks"].items():
        prepared = summary_row.get("prepared_text_available")
        check(isinstance(prepared, bool), f"prepared flag {task}")
        fields = matched_by_task_field[task]
        matched_cards = set().union(*fields.values())
        if prepared:
            check(summary_row.get("affected_cards") == len(matched_cards), f"affected cards {task}")
            check(
                summary_row.get("affected_card_fields")
                == {field: len(fields[field]) for field in sorted(FIELDS)},
                f"affected fields {task}",
            )
        else:
            check(not matched_cards, f"unscanned task has hits {task}")

    expected_private_rows: list[dict[str, Any]] = []
    expected_tasks: dict[str, Any] = {}
    eligible_total = matched_total = unscanned_total = 0
    for task in sorted(task_counts):
        hashes = sorted(card_hash for card_hash, name in by_hash.items() if name == task)
        prepared = bool(summary["tasks"][task]["prepared_text_available"])
        matched = {card_hash for card_hash in hashes if card_hash in trigger_fields}
        unscanned = set(hashes) if not prepared else set()
        withheld = matched | unscanned
        eligible = len(hashes) - len(withheld)
        eligible_total += eligible
        matched_total += len(matched)
        unscanned_total += len(unscanned)
        expected_tasks[task] = {
            "cards": len(hashes),
            "prepared_text_available": prepared,
            "content_review_eligible_cards": eligible,
            "structure_only_due_matched_pattern": len(matched),
            "structure_only_due_unscanned_task": len(unscanned),
            "structure_only_cards": len(withheld),
        }
        for card_hash in hashes:
            reasons = []
            if card_hash in unscanned:
                reasons.append("UNSCANNED_TASK_NO_PREPARED_TEXT")
            if card_hash in matched:
                reasons.append("MATCHED_COMPETITION_DATA_PATTERN")
            is_withheld = card_hash in withheld
            expected_private_rows.append({
                "card_id_sha256": card_hash,
                "task": task,
                "release_tier": "STRUCTURE_ONLY" if is_withheld else "CONTENT_REVIEW_ELIGIBLE",
                "reason_codes": reasons,
                "triggering_scan_fields": sorted(trigger_fields.get(card_hash, set())),
                "withheld_fields": WITHHELD if is_withheld else [],
            })
    total = len(by_hash)
    withheld_total = total - eligible_total
    check(len(expected_private_rows) == total, "private tier map completeness")
    check(matched_total == totals.get("affected_card_sum_across_tasks"), "matched-card aggregate")
    expected_totals = {
        "cards": total,
        "content_review_eligible_cards": eligible_total,
        "structure_only_cards": withheld_total,
        "structure_only_due_matched_pattern": matched_total,
        "structure_only_due_unscanned_task": unscanned_total,
        "content_review_eligible_fraction": fraction_payload(eligible_total, total),
    }
    check(claimed_public.get("protocol") == "decision-corpus-release-content-tier-summary-v1", "public protocol")
    check(claimed_public.get("status") == "COMPLETE_PENDING_EXTERNAL_RELEASE_GATES", "public status")
    check(claimed_public.get("protocol_sha256") == protocol_sha, "public protocol SHA")
    check(claimed_public.get("scan_summary_sha256") == summary_sha, "public summary SHA")
    check(claimed_public.get("scan_private_manifest_sha256") == scan_private_sha, "public private SHA")
    check(claimed_public.get("cards_sha256") == cards_sha, "public cards SHA")
    check(claimed_public.get("totals") == expected_totals, "public totals")
    check(claimed_public.get("tasks") == expected_tasks, "public task reconstruction")
    boundary = claimed_public.get("release_boundary")
    check(isinstance(boundary, Mapping), "release boundary")
    check(boundary.get("content_review_eligible_is_release_clearance") is False, "clearance claim")
    check(boundary.get("zero_scan_match_is_proof_of_no_leakage") is False, "no-leak claim")
    public_scope = claimed_public.get("scope")
    check(isinstance(public_scope, Mapping), "public scope")
    check(public_scope.get("raw_card_ids_emitted") is False, "raw IDs")
    check(public_scope.get("card_id_hashes_emitted_publicly") is False, "public hashes")
    check(public_scope.get("raw_card_values_emitted") is False, "raw values")
    check(public_scope.get("raw_matched_spans_emitted") is False, "raw spans")
    check(public_scope.get("prospective_resources_read") is False, "prospective")

    check(claimed_private.get("protocol") == "decision-corpus-release-content-tier-private-manifest-v1", "private output protocol")
    check(claimed_private.get("protocol_sha256") == protocol_sha, "private protocol SHA")
    check(claimed_private.get("scan_summary_sha256") == summary_sha, "private summary SHA")
    check(claimed_private.get("scan_private_manifest_sha256") == scan_private_sha, "private input SHA")
    check(claimed_private.get("cards_sha256") == cards_sha, "private cards SHA")
    check(claimed_private.get("rows") == expected_private_rows, "private row reconstruction")
    private_scope = claimed_private.get("scope")
    check(isinstance(private_scope, Mapping), "private scope")
    check(all(private_scope.get(key) is False for key in (
        "raw_card_ids_emitted", "raw_card_values_emitted", "raw_matched_spans_emitted", "prospective_resources_read"
    )), "private scope flags")
    return {
        "protocol": "decision-corpus-release-content-tier-independent-verification-v1",
        "status": "INDEPENDENT_RECONSTRUCTION_EXACT",
        "protocol_sha256": protocol_sha,
        "scan_summary_sha256": summary_sha,
        "scan_private_manifest_sha256": scan_private_sha,
        "cards_sha256": cards_sha,
        "claimed_public_sha256": claimed_public_sha,
        "claimed_private_sha256": claimed_private_sha,
        "cards_reconstructed": total,
        "private_tier_rows_reconstructed": total,
        "structure_only_rows_reconstructed": withheld_total,
        "raw_card_ids_or_values_emitted": False,
        "prospective_resources_read": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }


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
    parser.add_argument("--claimed-public", type=Path, required=True)
    parser.add_argument("--claimed-public-sha256", required=True)
    parser.add_argument("--claimed-private", type=Path, required=True)
    parser.add_argument("--claimed-private-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = (
        (args.protocol.resolve(), args.protocol_sha256),
        (args.scan_summary.resolve(), args.scan_summary_sha256),
        (args.scan_private_manifest.resolve(), args.scan_private_manifest_sha256),
        (args.cards.resolve(), args.cards_sha256),
        (args.claimed_public.resolve(), args.claimed_public_sha256),
        (args.claimed_private.resolve(), args.claimed_private_sha256),
    )
    for path, expected in paths:
        check(SHA_RE.fullmatch(expected) is not None and file_hash(path) == expected, "file SHA")
    result = verify(
        read(args.protocol.resolve()), args.protocol_sha256,
        read(args.scan_summary.resolve()), args.scan_summary_sha256,
        read(args.scan_private_manifest.resolve()), args.scan_private_manifest_sha256,
        args.cards.resolve(), args.cards_sha256,
        read(args.claimed_public.resolve()), args.claimed_public_sha256,
        read(args.claimed_private.resolve()), args.claimed_private_sha256,
    )
    write_exclusive(args.output.resolve(), result)
    print(canonical_bytes({
        "status": result["status"],
        "output_sha256": file_hash(args.output.resolve()),
        "raw_values_emitted": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
