"""Independent reconstruction of the transition future-escrow support audit.

This verifier deliberately does not import audit_transition_future_escrow_support.
It reuses only the previously audited blind-snapshot loader, then independently
reconstructs the training closure, overlap counts, and every producer field.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from phase1.prospective_wl_graph_escrow import EscrowError, load_snapshot


PROTOCOL = "transition-future-escrow-support-audit-v1"
VERIFY_PROTOCOL = "transition-future-escrow-support-independent-verifier-v1"
STATUS_OVERLAP = "CURRENT_SUPPORT_NOT_SOURCE_INDEPENDENT"
STATUS_NOVEL = "CURRENT_SUPPORT_SOURCE_NOVEL"


class VerificationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"JSON root is not an object: {path.name}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            check(bool(line.strip()), f"blank JSONL line: {path.name}:{line_number}")
            value = json.loads(line)
            check(isinstance(value, dict), f"non-object JSONL row: {path.name}:{line_number}")
            rows.append(value)
    return rows


def load_training_closure(cards_path: Path, train_path: Path, dev_path: Path):
    pair_rows = read_jsonl(train_path) + read_jsonl(dev_path)
    needed: set[str] = set()
    for row in pair_rows:
        for key in ("better", "worse", "parent"):
            value = row.get(key)
            check(isinstance(value, str) and bool(value), "training pair identity missing")
            needed.add(value)
    grouped = json.loads(cards_path.read_text(encoding="utf-8"))
    check(isinstance(grouped, dict), "training Cards root is not grouped")
    identifiers: set[str] = set()
    runs: set[str] = set()
    code_sha: set[str] = set()
    for run_id, rows in grouped.items():
        check(isinstance(run_id, str) and isinstance(rows, list), "invalid training Cards group")
        for row in rows:
            identifier = row.get("id") if isinstance(row, dict) else None
            if identifier not in needed:
                continue
            check(identifier not in identifiers, "duplicate needed training card")
            code = row.get("code")
            check(isinstance(code, str), "needed training code missing")
            identifiers.add(identifier)
            runs.add(run_id)
            code_sha.add(hashlib.sha256(code.encode()).hexdigest())
    check(identifiers == needed, "needed training card missing")
    return identifiers, runs, code_sha, len(pair_rows)


def reconstruct(
    state_root: Path,
    snapshot_sha: str,
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    expected_hashes: dict[str, str],
) -> dict[str, Any]:
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        check(sha256_file(path) == expected_hashes[role], f"{role} input SHA mismatch")
    state_root = state_root.resolve()
    check((state_root / "LATEST").read_text().strip() == snapshot_sha, "LATEST mismatch")
    snapshot_root = state_root / "snapshots" / snapshot_sha
    try:
        cards, raw_pairs, metadata = load_snapshot(
            state_root,
            snapshot_root,
            snapshot_sha,
            dt.datetime.max.replace(tzinfo=dt.timezone.utc),
        )
    except EscrowError as error:
        raise VerificationError(str(error)) from error
    selected_runs = {card["run"] for card in cards.values()}
    pairs = [((cards[left]["task"], cards[left]["run"], cards[left]["parent"]), left, right)
             for left, right in raw_pairs]
    check(
        all(
            cards[right]["task"] == group[0]
            and cards[right]["run"] == group[1]
            and cards[right]["parent"] == group[2]
            for group, _left, right in pairs
        ),
        "pair group reconstruction mismatch",
    )
    train_ids, train_runs, train_code, train_rows = load_training_closure(
        cards_path, train_path, dev_path
    )
    parent_groups = {group for group, _left, _right in pairs}
    present_parent_groups = {group for group in parent_groups if group[2] in cards}
    check(
        all(cards[parent]["task"] == task and cards[parent]["run"] == run
            for task, run, parent in present_parent_groups),
        "present parent task/run mismatch",
    )
    covered_pairs = [item for item in pairs if item[0][2] in cards]
    source_novel_pairs = []
    for group, left, right in covered_pairs:
        parent = group[2]
        if (
            not ({left, right, parent} & train_ids)
            and cards[left]["code_sha256"] not in train_code
            and cards[right]["code_sha256"] not in train_code
            and cards[parent]["code_sha256"] not in train_code
            and group[1] not in train_runs
        ):
            source_novel_pairs.append((group, left, right))
    card_overlap = set(cards) & train_ids
    run_overlap = selected_runs & train_runs
    code_overlap = {card["code_sha256"] for card in cards.values()} & train_code
    pair_tasks = collections.Counter(group[0] for group, _left, _right in pairs)
    covered_tasks = collections.Counter(group[0] for group, _left, _right in covered_pairs)
    cross_checks = metadata["cross_checks_against_accumulator"]
    manifest_hashes = metadata["blind_manifest_sha256"]
    summary_hashes = metadata["intake_summary_sha256"]
    return {
        "blindness": {
            "effect_metrics_computed": [],
            "label_vault_opened": False,
            "outcome_paths_accepted_by_cli": False,
            "score_registry_opened": False,
        },
        "inputs": {
            "cards_sha256": expected_hashes["cards"],
            "dev_sha256": expected_hashes["dev"],
            "snapshot_sha256": snapshot_sha,
            "train_sha256": expected_hashes["train"],
            "accumulator_summary_sha256": metadata["accumulator_summary_sha256"],
            "blind_manifest_hash_registry_sha256": hashlib.sha256(
                json.dumps(manifest_hashes, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "intake_registry_sha256": metadata["intake_registry_sha256"],
            "intake_summary_hash_registry_sha256": hashlib.sha256(
                json.dumps(summary_hashes, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "provisional_runs_sha256": metadata["provisional_runs_sha256"],
            "snapshot_cross_checks": {
                "drops": cross_checks["transactions"],
                "runs": cross_checks["all_eligible_runs"],
                "endpoints": cross_checks["all_eligible_endpoints"],
                "first960_runs": cross_checks["provisional_first960_runs"],
                "first960_endpoints": cross_checks["provisional_first960_endpoints"],
                "first960_pairs": cross_checks["provisional_first960_pairs"],
            },
        },
        "inventory": {
            "blind_cards": len(cards),
            "blind_runs": len(selected_runs),
            "blind_tasks": len({card["task"] for card in cards.values()}),
            "covered_pair_tasks": len(covered_tasks),
            "dominant_covered_pair_task_share": (
                max(covered_tasks.values()) / len(covered_pairs) if covered_pairs else 0.0
            ),
            "dominant_pair_task_share": max(pair_tasks.values()) / len(pairs),
            "pair_parent_source_coverage": len(covered_pairs) / len(pairs),
            "pairs": len(pairs),
            "pairs_with_parent_source": len(covered_pairs),
            "parent_groups": len(parent_groups),
            "parent_groups_with_source": len(present_parent_groups),
            "source_novel_parent_covered_pairs": len(source_novel_pairs),
            "training_needed_cards": len(train_ids),
            "training_pair_rows": train_rows,
        },
        "overlap": {
            "blind_card_ids_in_training_support": len(card_overlap),
            "blind_code_sha_in_training_support": len(code_overlap),
            "blind_run_ids_in_training_support": len(run_overlap),
            "zero_run_overlap": not run_overlap,
        },
        "protocol": PROTOCOL,
        "status": STATUS_OVERLAP if card_overlap or code_overlap or run_overlap else STATUS_NOVEL,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    expected = reconstruct(
        args.state_root,
        args.expect_snapshot_sha,
        args.training_cards,
        args.train_pairs,
        args.dev_pairs,
        {
            "cards": args.expect_training_cards_sha,
            "train": args.expect_train_pairs_sha,
            "dev": args.expect_dev_pairs_sha,
        },
    )
    producer = read_json(args.producer)
    check(producer == expected, "producer artifact differs from independent reconstruction")
    payload = json.dumps(expected, indent=2, sort_keys=True, allow_nan=False) + "\n"
    return {
        "all_fields_exact": True,
        "blindness": expected["blindness"],
        "independent_summary_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "producer_imported": False,
        "producer_sha256": sha256_file(args.producer),
        "protocol": VERIFY_PROTOCOL,
        "raw_snapshot_and_training_closure_recomputed": True,
        "status": "INDEPENDENT_TRANSITION_FUTURE_ESCROW_SUPPORT_VERIFIED",
        "support_status": expected["status"],
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("xb") as handle:
        handle.write(payload.encode())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--expect-snapshot-sha", required=True)
    parser.add_argument("--training-cards", required=True, type=Path)
    parser.add_argument("--expect-training-cards-sha", required=True)
    parser.add_argument("--train-pairs", required=True, type=Path)
    parser.add_argument("--expect-train-pairs-sha", required=True)
    parser.add_argument("--dev-pairs", required=True, type=Path)
    parser.add_argument("--expect-dev-pairs-sha", required=True)
    parser.add_argument("--producer", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    check(not args.output.exists(), "refusing to overwrite output")
    receipt = verify(args)
    write_json(args.output, receipt)
    print(json.dumps({"status": receipt["status"], "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
