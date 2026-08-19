#!/usr/bin/env python3
"""Freeze label-blind predictions for the sealed 0812 temporal holdout."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import fixed_decision_scorer as scorer


PROTOCOL = "temporal-prediction-escrow-v1"
VIEW_KEYS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "source_archive_sha256",
    "source_journal_sha256",
    "prospective_status",
}
LINEAGE_KEYS = {"parent", "depth", "step", "n_siblings", "op"}
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class EscrowError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def credential_free(path: Path) -> bool:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            window = overlap + chunk
            if CREDENTIAL.search(window):
                return False
            overlap = window[-512:]
    return True


def locked(path: Path, expected: str, scan: bool = False) -> Path:
    path = path.resolve()
    if not path.is_file() or sha256_file(path) != expected.lower():
        raise EscrowError(f"locked input mismatch: {path.name}")
    if scan and not credential_free(path):
        raise EscrowError(f"credential-shaped bytes refused: {path.name}")
    return path


def load_denylist(path: Path) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    codes: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["card_id", "code_sha256"]:
            raise EscrowError("denylist schema mismatch")
        for row in reader:
            if row["card_id"] in ids:
                raise EscrowError("duplicate denylist card")
            ids.add(row["card_id"])
            codes.add(row["code_sha256"])
    if not ids or not codes:
        raise EscrowError("empty denylist")
    return ids, codes


def load_views(path: Path, deny_ids: set[str], deny_codes: set[str]) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise EscrowError(f"blank blind-view line {line_number}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != VIEW_KEYS:
                raise EscrowError(f"blind-view schema mismatch at line {line_number}")
            lineage = row["lineage"]
            if not isinstance(lineage, dict) or set(lineage) != LINEAGE_KEYS:
                raise EscrowError(f"lineage schema mismatch at line {line_number}")
            card_id = row["card_id"]
            code = row["code"]
            task = row["task"]
            run_id = row["run_id"]
            if not all(isinstance(value, str) and value for value in (card_id, code, task, run_id)):
                raise EscrowError(f"blind-view identity/code invalid at line {line_number}")
            code_sha = hashlib.sha256(code.encode()).hexdigest()
            if code_sha != row["code_sha256"]:
                raise EscrowError(f"code SHA mismatch at line {line_number}")
            if card_id in cards or card_id in deny_ids or code_sha in deny_codes:
                raise EscrowError(f"duplicate or pre-cutoff overlap at line {line_number}")
            for key in ("depth", "step", "n_siblings"):
                if isinstance(lineage[key], bool) or not isinstance(lineage[key], int) or lineage[key] < 0:
                    raise EscrowError(f"lineage integer invalid at line {line_number}")
            cards[card_id] = {
                "id": card_id,
                "task": task,
                "run": run_id,
                "code": code,
                "lineage": {key: lineage[key] for key in ("depth", "step", "n_siblings", "op")},
                "parent": lineage["parent"],
                "code_sha256": code_sha,
            }
    if not cards:
        raise EscrowError("empty blind views")
    return cards


def load_pairs(path: Path, cards: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise EscrowError(f"blank structure line {line_number}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != PAIR_KEYS:
                raise EscrowError(f"structure schema mismatch at line {line_number}")
            left, right = row["left"], row["right"]
            if left == right or left not in cards or right not in cards:
                raise EscrowError(f"structure endpoint invalid at line {line_number}")
            key = tuple(sorted((left, right)))
            if key in seen:
                raise EscrowError(f"duplicate unordered structure pair at line {line_number}")
            seen.add(key)
            if any(cards[value]["task"] != row["task"] for value in (left, right)):
                raise EscrowError(f"structure task mismatch at line {line_number}")
            if any(cards[value]["run"] != row["run_id"] for value in (left, right)):
                raise EscrowError(f"structure run mismatch at line {line_number}")
            if any(cards[value]["parent"] != row["parent"] for value in (left, right)):
                raise EscrowError(f"structure parent mismatch at line {line_number}")
            rows.append(row)
    if not rows:
        raise EscrowError("empty sibling structure")
    return rows


def git_commit(repo_root: Path) -> str:
    value = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise EscrowError("git commit unavailable")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(args: argparse.Namespace) -> int:
    views_path = locked(args.blind_views, args.expect_blind_views_sha256, scan=True)
    structure_path = locked(args.structure, args.expect_structure_sha256)
    bundle_path = locked(args.bundle, args.expect_bundle_sha256)
    receipt_path = locked(args.freeze_receipt, args.expect_receipt_sha256)
    denylist_path = locked(args.denylist, args.expect_denylist_sha256)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "PROSPECTIVE_SCORER_ACTIVE" or receipt.get("fixed_scorer_sha256") != args.expect_bundle_sha256:
        raise EscrowError("frozen scorer receipt mismatch")
    deny_ids, deny_codes = load_denylist(denylist_path)
    cards = load_views(views_path, deny_ids, deny_codes)
    pairs = load_pairs(structure_path, cards)
    arrays = scorer.load_bundle(bundle_path)
    scores = scorer.score_cards(cards, arrays)
    if set(scores) != set(cards):
        raise EscrowError("score coverage mismatch")

    output = args.output.resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise EscrowError("output path exists")
    staging.mkdir(parents=True)
    endpoint_path = staging / "endpoint_scores.csv"
    with endpoint_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("card_id", "task", "run_id", "parent", "code_sha256", "static_lr", "char_tfidf_lr"),
            lineterminator="\n",
        )
        writer.writeheader()
        for card_id in sorted(cards):
            row = cards[card_id]
            writer.writerow(
                {
                    "card_id": card_id,
                    "task": row["task"],
                    "run_id": row["run"],
                    "parent": row["parent"],
                    "code_sha256": row["code_sha256"],
                    "static_lr": format(scores[card_id]["static_lr"], ".17g"),
                    "char_tfidf_lr": format(scores[card_id]["char_tfidf_lr"], ".17g"),
                }
            )
    pair_path = staging / "pair_predictions.jsonl"
    ties = {"static_lr": 0, "char_tfidf_lr": 0}
    with pair_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in sorted(pairs, key=lambda item: (item["task"], item["run_id"], item["parent"], item["left"], item["right"])):
            output_row: dict[str, Any] = {key: row[key] for key in ("task", "run_id", "parent", "left", "right")}
            output_row["pair_key_sha256"] = hashlib.sha256("\0".join(sorted((row["left"], row["right"]))).encode()).hexdigest()
            for arm in ("static_lr", "char_tfidf_lr"):
                margin = scores[row["left"]][arm] - scores[row["right"]][arm]
                selected = row["left"] if margin > 0 else row["right"] if margin < 0 else "tie"
                ties[arm] += margin == 0
                output_row[f"{arm}_margin_left_minus_right"] = float(format(margin, ".17g"))
                output_row[f"{arm}_selected"] = selected
            handle.write(json.dumps(output_row, sort_keys=True, separators=(",", ":")) + "\n")
    summary = {
        "protocol": PROTOCOL,
        "status": "TEMPORAL_PREDICTION_ESCROW_COMPLETE",
        "source_commit": git_commit(args.repo_root),
        "inputs": {
            "blind_views_sha256": args.expect_blind_views_sha256,
            "structure_sha256": args.expect_structure_sha256,
            "bundle_sha256": args.expect_bundle_sha256,
            "freeze_receipt_sha256": args.expect_receipt_sha256,
            "denylist_sha256": args.expect_denylist_sha256,
        },
        "inventory": {
            "endpoints": len(cards),
            "pairs": len(pairs),
            "runs": len({row["run"] for row in cards.values()}),
            "tasks": len({row["task"] for row in cards.values()}),
            "precutoff_endpoint_id_overlap": 0,
            "precutoff_code_sha256_overlap": 0,
            "ties": ties,
        },
        "outputs": {
            "endpoint_scores_sha256": sha256_file(endpoint_path),
            "pair_predictions_sha256": sha256_file(pair_path),
        },
        "scope": {
            "label_vault_path_accepted": False,
            "label_vault_read": False,
            "accuracy_computed": False,
            "numeric_grade_used": False,
            "gpu": 0,
            "api_calls": 0,
        },
    }
    write_json(staging / "summary.json", summary)
    write_json(
        staging / "sha256_manifest.json",
        {name: sha256_file(staging / name) for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")},
    )
    staging.replace(output)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--blind-views", required=True, type=Path)
    value.add_argument("--expect-blind-views-sha256", required=True)
    value.add_argument("--structure", required=True, type=Path)
    value.add_argument("--expect-structure-sha256", required=True)
    value.add_argument("--bundle", required=True, type=Path)
    value.add_argument("--expect-bundle-sha256", required=True)
    value.add_argument("--freeze-receipt", required=True, type=Path)
    value.add_argument("--expect-receipt-sha256", required=True)
    value.add_argument("--denylist", required=True, type=Path)
    value.add_argument("--expect-denylist-sha256", required=True)
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except (EscrowError, scorer.IntegrityError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"TEMPORAL_PREDICTION_ESCROW_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
