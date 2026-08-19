#!/usr/bin/env python3
"""Structure-only audit for a train-derived dev split on senior augmented pairs."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "senior-augmented-train-dev-support-v1"
DEV_DOMAIN = "augmented-dev-v1|20260819"
CURVE_DOMAIN = "augmented-curve-v1|20260819"
FRACTIONS = (0.25, 0.50, 0.75, 1.00)
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class AuditError(RuntimeError):
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


def locked(path_value: str, digest: str) -> Path:
    path = Path(path_value).resolve()
    if not path.is_file() or sha256_file(path) != digest:
        raise AuditError(f"locked input mismatch: {path.name}")
    if not credential_free(path):
        raise AuditError(f"credential-shaped bytes refused: {path.name}")
    return path


def stable_hash(domain: str, task: str, run_id: str) -> str:
    return hashlib.sha256(f"{domain}|{task}|{run_id}".encode()).hexdigest()


def config_value(card: dict[str, Any]) -> tuple[Any, ...]:
    return (
        card.get("client"),
        card.get("hardware"),
        card.get("time_limit"),
        card.get("execution_timeout"),
    )


def load_cards(path: Path) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not payload:
        raise AuditError("grouped cards must be a nonempty object")
    card_runs: dict[str, str] = {}
    runs: dict[str, dict[str, Any]] = {}
    for run_id, cards in payload.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(cards, list) or not cards:
            raise AuditError("invalid grouped run")
        first = cards[0]
        if not isinstance(first, dict) or not isinstance(first.get("task"), dict):
            raise AuditError("invalid first card")
        task = first["task"].get("name")
        if not isinstance(task, str) or not task:
            raise AuditError("run task missing")
        config = config_value(first)
        config_sha = hashlib.sha256(json.dumps(config, separators=(",", ":")).encode()).hexdigest()
        for card in cards:
            if not isinstance(card, dict) or not isinstance(card.get("task"), dict):
                raise AuditError("invalid card")
            card_id = card.get("id")
            if not isinstance(card_id, str) or not card_id or card_id in card_runs:
                raise AuditError("card identity missing or duplicated")
            if card["task"].get("name") != task or config_value(card) != config:
                raise AuditError("run metadata is not constant")
            card_runs[card_id] = run_id
        runs[run_id] = {"task": task, "config_sha256": config_sha, "cards": len(cards)}
    return card_runs, runs


def load_split(path: Path, current_runs: set[str]) -> tuple[set[str], set[str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"all", "hold"}:
        raise AuditError("runsplit schema mismatch")
    assigned = set(value["all"])
    hold = set(value["hold"])
    if not all(isinstance(run_id, str) and run_id for run_id in assigned | hold):
        raise AuditError("runsplit identity invalid")
    if not hold <= assigned or not current_runs <= assigned:
        raise AuditError("runsplit coverage mismatch")
    return assigned, hold


def assign_roles(runs: dict[str, dict[str, Any]], hold: set[str]) -> list[dict[str, Any]]:
    train_by_task: dict[str, list[str]] = collections.defaultdict(list)
    for run_id, row in runs.items():
        if run_id not in hold:
            train_by_task[row["task"]].append(run_id)
    roles: dict[str, str] = {}
    for task, run_ids in train_by_task.items():
        if len(run_ids) < 5:
            roles.update({run_id: "excluded_low_support" for run_id in run_ids})
            continue
        ordered = sorted(run_ids, key=lambda run_id: stable_hash(DEV_DOMAIN, task, run_id))
        dev_count = max(1, math.floor(0.2 * len(ordered)))
        roles.update({run_id: "dev" if index < dev_count else "train" for index, run_id in enumerate(ordered)})
    rows_out = []
    for run_id in sorted(runs):
        task = runs[run_id]["task"]
        role = "test_hold" if run_id in hold else roles[run_id]
        rows_out.append(
            {
                "run_id": run_id,
                "task": task,
                "role": role,
                "original_hold": run_id in hold,
                "cards": runs[run_id]["cards"],
                "config_sha256": runs[run_id]["config_sha256"],
                "dev_order_sha256": stable_hash(DEV_DOMAIN, task, run_id),
                "curve_order_sha256": stable_hash(CURVE_DOMAIN, task, run_id),
            }
        )
    return rows_out


def pair_rows(path: Path, card_runs: dict[str, str], runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    identities: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AuditError(f"blank pair line {line_number}")
            pair = json.loads(line)
            split = pair.get("intask_split")
            endpoints = (pair.get("better"), pair.get("worse"))
            if split not in {"train", "test"} or not all(isinstance(value, str) and value for value in endpoints):
                raise AuditError("pair split or endpoint invalid")
            if endpoints[0] == endpoints[1] or any(value not in card_runs for value in endpoints):
                raise AuditError("pair endpoint identity invalid")
            pair_key = hashlib.sha256("\0".join(sorted(endpoints)).encode()).hexdigest()
            if pair_key in identities:
                raise AuditError("duplicate unordered pair")
            identities.add(pair_key)
            endpoint_runs = sorted({card_runs[endpoints[0]], card_runs[endpoints[1]]})
            tasks = {runs[run_id]["task"] for run_id in endpoint_runs}
            if len(tasks) != 1:
                raise AuditError("pair spans tasks")
            configs = {runs[run_id]["config_sha256"] for run_id in endpoint_runs}
            output.append(
                {
                    "pair_key_sha256": pair_key,
                    "original_split": split,
                    "task": next(iter(tasks)),
                    "run_ids": endpoint_runs,
                    "same_experiment_contract": len(configs) == 1,
                }
            )
    return output


def derive(run_rows: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    run_map = {row["run_id"]: row for row in run_rows}
    split_inconsistency = 0
    train_pairs: list[dict[str, Any]] = []
    test_pairs = 0
    for pair in pairs:
        roles = {run_map[run_id]["role"] for run_id in pair["run_ids"]}
        if pair["original_split"] == "test":
            test_pairs += 1
            if roles != {"test_hold"}:
                split_inconsistency += 1
        else:
            train_pairs.append(pair)
            if "test_hold" in roles:
                split_inconsistency += 1

    dev = []
    full = []
    cross = 0
    for pair in train_pairs:
        roles = {run_map[run_id]["role"] for run_id in pair["run_ids"]}
        if roles == {"dev"}:
            dev.append(pair)
        elif roles == {"train"}:
            full.append(pair)
        else:
            cross += 1
    dev_tasks = collections.Counter(row["task"] for row in dev)
    full_tasks = collections.Counter(row["task"] for row in full)
    large_dev_tasks = sum(value >= 20 for value in dev_tasks.values())

    train_runs_by_task: dict[str, list[str]] = collections.defaultdict(list)
    for row in run_rows:
        if row["role"] == "train":
            train_runs_by_task[row["task"]].append(row["run_id"])
    fraction_counts: dict[str, int] = {}
    for fraction in FRACTIONS:
        selected: set[str] = set()
        for task, run_ids in train_runs_by_task.items():
            ordered = sorted(run_ids, key=lambda run_id: run_map[run_id]["curve_order_sha256"])
            count = max(1, math.ceil(fraction * len(ordered)))
            selected.update(ordered[:count])
        fraction_counts[f"{fraction:.2f}"] = sum(all(run_id in selected for run_id in pair["run_ids"]) for pair in full)
    values = list(fraction_counts.values())
    dev_contract_share = sum(row["same_experiment_contract"] for row in dev) / len(dev) if dev else None
    full_contract_share = sum(row["same_experiment_contract"] for row in full) / len(full) if full else None
    criteria = {
        "original_train_pairs_ge_2500": len(train_pairs) >= 2500,
        "original_split_inconsistency_eq_0": split_inconsistency == 0,
        "train_dev_hold_overlap_eq_0": all(not row["original_hold"] for row in run_rows if row["role"] in {"train", "dev"}),
        "dev_pairs_ge_400": len(dev) >= 400,
        "dev_tasks_ge_8": len(dev_tasks) >= 8,
        "dominant_dev_task_share_le_0_35": bool(dev) and max(dev_tasks.values()) / len(dev) <= 0.35,
        "full_train_pairs_ge_2000": len(full) >= 2000,
        "quarter_train_pairs_ge_300": values[0] >= 300,
        "fraction_pair_counts_strictly_increasing": all(left < right for left, right in zip(values, values[1:])),
        "full_and_dev_same_experiment_share_ge_0_95": dev_contract_share is not None
        and full_contract_share is not None
        and dev_contract_share >= 0.95
        and full_contract_share >= 0.95,
        "dev_tasks_with_ge_20_pairs_ge_6": large_dev_tasks >= 6,
    }
    return {
        "status": "TRAIN_ONLY_DEV_LEARNING_CURVE_SUPPORT_FEASIBLE" if all(criteria.values()) else "INSUFFICIENT_TRAIN_ONLY_DEV_SUPPORT",
        "inventory": {
            "current_runs": len(run_rows),
            "current_tasks": len({row["task"] for row in run_rows}),
            "original_train_pairs": len(train_pairs),
            "original_test_pairs_structure_only": test_pairs,
            "split_inconsistency": split_inconsistency,
            "dev_runs": sum(row["role"] == "dev" for row in run_rows),
            "train_runs": sum(row["role"] == "train" for row in run_rows),
            "test_hold_runs": sum(row["role"] == "test_hold" for row in run_rows),
            "excluded_low_support_runs": sum(row["role"] == "excluded_low_support" for row in run_rows),
            "dev_pairs": len(dev),
            "full_train_pairs": len(full),
            "cross_train_dev_or_excluded_pairs": cross,
            "dev_tasks": len(dev_tasks),
            "full_train_tasks": len(full_tasks),
            "dominant_dev_task_share": max(dev_tasks.values()) / len(dev) if dev else None,
            "dev_tasks_with_ge_20_pairs": large_dev_tasks,
            "dev_same_experiment_contract_share": dev_contract_share,
            "full_train_same_experiment_contract_share": full_contract_share,
        },
        "fraction_train_pair_counts": fraction_counts,
        "dev_pairs_per_task": dict(sorted(dev_tasks.items())),
        "full_train_pairs_per_task": dict(sorted(full_tasks.items())),
        "criteria": criteria,
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(args: argparse.Namespace) -> int:
    cards_path = locked(args.cards, args.expect_cards_sha256)
    pairs_path = locked(args.pairs, args.expect_pairs_sha256)
    split_path = locked(args.runsplit, args.expect_runsplit_sha256)
    card_runs, runs = load_cards(cards_path)
    _, hold = load_split(split_path, set(runs))
    run_rows = assign_roles(runs, hold)
    pairs = pair_rows(pairs_path, card_runs, runs)
    derived = derive(run_rows, pairs)
    summary = {
        "protocol": PROTOCOL,
        **derived,
        "source_commit": args.source_commit,
        "senior_source_commit": args.senior_source_commit,
        "scope": {
            "model_trained": False,
            "pair_orientation_used_for_effect": False,
            "numeric_grade_used": False,
            "numeric_grade_emitted": False,
            "raw_code_emitted": False,
            "frozen_test_used_for_validation": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "inputs": {
            "cards_sha256": args.expect_cards_sha256,
            "pairs_sha256": args.expect_pairs_sha256,
            "runsplit_sha256": args.expect_runsplit_sha256,
        },
        "configuration": {"dev_domain": DEV_DOMAIN, "curve_domain": CURVE_DOMAIN, "fractions": list(FRACTIONS)},
    }
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise AuditError("output path exists")
    staging.mkdir(parents=True)
    write_json(staging / "summary.json", summary)
    with (staging / "run_manifest.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in run_rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    with (staging / "pair_structure.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in pairs:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    write_json(
        staging / "sha256_manifest.json",
        {name: sha256_file(staging / name) for name in ("summary.json", "run_manifest.jsonl", "pair_structure.jsonl")},
    )
    staging.replace(output)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--cards", required=True)
    value.add_argument("--expect-cards-sha256", required=True)
    value.add_argument("--pairs", required=True)
    value.add_argument("--expect-pairs-sha256", required=True)
    value.add_argument("--runsplit", required=True)
    value.add_argument("--expect-runsplit-sha256", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--senior-source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except (AuditError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"SENIOR_AUGMENTED_TRAIN_DEV_SUPPORT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
