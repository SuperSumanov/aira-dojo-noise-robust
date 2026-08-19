#!/usr/bin/env python3
"""Outcome-blind support audit for leave-one-generator/client-out transfer."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


PROTOCOL = "cross-client-transfer-support-v1"
MIN_OTHER_PAIRS_PER_STRATUM = 50
MIN_OTHER_CLIENTS_PER_STRATUM = 2
MIN_TEST_PAIRS = 200
MIN_TEST_TASKS = 4
MIN_TEST_RUNS = 15
MIN_TRAIN_PAIRS = 1_000
MIN_TRAIN_CLIENTS = 3
MAX_DOMINANT_TASK_SHARE = 0.50
MIN_ELIGIBLE_CLIENTS = 6
MIN_TOTAL_ELIGIBLE_TEST_PAIRS = 3_000
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


def locked(value: str, expected: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file() or sha256_file(path) != expected.lower():
        raise AuditError(f"locked input mismatch: {path.name}")
    if not credential_free(path):
        raise AuditError(f"credential-shaped bytes refused: {path.name}")
    return path


def environment(card: dict[str, Any]) -> tuple[Any, Any, Any]:
    return card.get("hardware"), card.get("time_limit"), card.get("execution_timeout")


def environment_sha(value: tuple[Any, Any, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def load_cards(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        grouped = json.load(handle)
    if not isinstance(grouped, dict) or not grouped:
        raise AuditError("cards payload must be a nonempty run mapping")
    cards: dict[str, dict[str, Any]] = {}
    runs: dict[str, dict[str, Any]] = {}
    for run_id, rows in grouped.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(rows, list) or not rows:
            raise AuditError("invalid grouped run")
        first = rows[0]
        task_obj = first.get("task") if isinstance(first, dict) else None
        task = task_obj.get("name") if isinstance(task_obj, dict) else None
        client = first.get("client") if isinstance(first, dict) else None
        env = environment(first) if isinstance(first, dict) else None
        if not isinstance(task, str) or not task or not isinstance(client, str) or not client.strip():
            raise AuditError("run task/client missing")
        for card in rows:
            card_task = card.get("task") if isinstance(card, dict) else None
            card_id = card.get("id") if isinstance(card, dict) else None
            code = card.get("code") if isinstance(card, dict) else None
            if (
                not isinstance(card_id, str)
                or not card_id
                or card_id in cards
                or not isinstance(card_task, dict)
                or card_task.get("name") != task
                or card.get("client") != client
                or environment(card) != env
                or not isinstance(code, str)
            ):
                raise AuditError("card/run contract violation")
            cards[card_id] = {
                "run": run_id,
                "task": task,
                "client": client,
                "environment": env,
                "environment_sha256": environment_sha(env),
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
            }
        runs[run_id] = {
            "task": task,
            "client": client,
            "environment": env,
            "environment_sha256": environment_sha(env),
            "cards": len(rows),
        }
    return cards, runs


def load_pairs(path: Path, cards: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AuditError(f"blank pair line {line_number}")
            row = json.loads(line)
            split = row.get("intask_split")
            if split not in {"train", "test"}:
                raise AuditError("invalid original split")
            if split != "train":
                continue
            endpoints = sorted([row.get("better"), row.get("worse")])
            if not all(isinstance(item, str) and item in cards for item in endpoints):
                raise AuditError("pair endpoint missing")
            if endpoints[0] == endpoints[1]:
                raise AuditError("self pair")
            pair_key = hashlib.sha256("\0".join(endpoints).encode()).hexdigest()
            if pair_key in seen:
                raise AuditError("duplicate unordered train pair")
            seen.add(pair_key)
            left, right = (cards[item] for item in endpoints)
            if left["task"] != right["task"]:
                raise AuditError("pair spans tasks")
            same_client = left["client"] == right["client"]
            same_environment = left["environment"] == right["environment"]
            pairs.append(
                {
                    "pair_key_sha256": pair_key,
                    "endpoint_a": endpoints[0],
                    "endpoint_b": endpoints[1],
                    "run_ids": sorted({left["run"], right["run"]}),
                    "task": left["task"],
                    "client": left["client"] if same_client else None,
                    "same_client": same_client,
                    "same_environment": same_environment,
                    "environment_sha256": left["environment_sha256"] if same_environment else None,
                    "code_sha256s": [left["code_sha256"], right["code_sha256"]],
                }
            )
    return pairs


def derive(cards: dict[str, dict[str, Any]], runs: dict[str, dict[str, Any]], pairs: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    exact = [row for row in pairs if row["same_client"] and row["same_environment"]]
    clients = sorted({row["client"] for row in exact})
    code_by_client: dict[str, set[str]] = collections.defaultdict(set)
    for card in cards.values():
        code_by_client[card["client"]].add(card["code_sha256"])
    stratum_rows: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in exact:
        stratum_rows[(row["task"], row["environment_sha256"])].append(row)

    per_client: dict[str, Any] = {}
    pool: list[dict[str, Any]] = []
    for client in clients:
        other_codes = set().union(*(code_by_client[item] for item in clients if item != client))
        eligible_rows: list[dict[str, Any]] = []
        prefilter_rows = [row for row in exact if row["client"] == client]
        code_overlap_pairs = 0
        for row in prefilter_rows:
            if any(value in other_codes for value in row["code_sha256s"]):
                code_overlap_pairs += 1
                continue
            candidates = [
                item
                for item in stratum_rows[(row["task"], row["environment_sha256"])]
                if item["client"] != client
            ]
            other_clients = {item["client"] for item in candidates}
            if len(candidates) < MIN_OTHER_PAIRS_PER_STRATUM or len(other_clients) < MIN_OTHER_CLIENTS_PER_STRATUM:
                continue
            eligible_rows.append(row)

        eligible_strata = {(row["task"], row["environment_sha256"]) for row in eligible_rows}
        train_rows = [
            row
            for row in exact
            if row["client"] != client and (row["task"], row["environment_sha256"]) in eligible_strata
        ]
        tasks = collections.Counter(row["task"] for row in eligible_rows)
        test_runs = {run_id for row in eligible_rows for run_id in row["run_ids"]}
        train_runs = {run_id for row in train_rows for run_id in row["run_ids"]}
        train_clients = {row["client"] for row in train_rows}
        dominant = max(tasks.values(), default=0) / len(eligible_rows) if eligible_rows else None
        criteria = {
            "test_pairs_ge_200": len(eligible_rows) >= MIN_TEST_PAIRS,
            "test_tasks_ge_4": len(tasks) >= MIN_TEST_TASKS,
            "test_runs_ge_15": len(test_runs) >= MIN_TEST_RUNS,
            "train_pairs_ge_1000": len(train_rows) >= MIN_TRAIN_PAIRS,
            "train_clients_ge_3": len(train_clients) >= MIN_TRAIN_CLIENTS,
            "dominant_task_share_le_0_50": dominant is not None and dominant <= MAX_DOMINANT_TASK_SHARE,
        }
        eligible = all(criteria.values())
        per_client[client] = {
            "prefilter_exact_pairs": len(prefilter_rows),
            "cross_client_exact_code_overlap_pairs_excluded": code_overlap_pairs,
            "supported_test_pairs": len(eligible_rows),
            "supported_test_tasks": len(tasks),
            "supported_test_runs": len(test_runs),
            "supported_train_pairs": len(train_rows),
            "supported_train_runs": len(train_runs),
            "supported_train_clients": len(train_clients),
            "dominant_test_task_share": dominant,
            "test_pairs_per_task": dict(sorted(tasks.items())),
            "criteria": criteria,
            "eligible": eligible,
        }
        if eligible:
            for row in eligible_rows:
                pool.append(
                    {
                        "client": client,
                        "endpoint_a": row["endpoint_a"],
                        "endpoint_b": row["endpoint_b"],
                        "environment_sha256": row["environment_sha256"],
                        "pair_key_sha256": row["pair_key_sha256"],
                        "run_ids": row["run_ids"],
                        "task": row["task"],
                    }
                )

    pool.sort(key=lambda row: (row["client"], row["task"], row["pair_key_sha256"]))
    eligible_clients = sorted(client for client, row in per_client.items() if row["eligible"])
    summary = {
        "protocol": PROTOCOL,
        "configuration": {
            "min_other_pairs_per_stratum": MIN_OTHER_PAIRS_PER_STRATUM,
            "min_other_clients_per_stratum": MIN_OTHER_CLIENTS_PER_STRATUM,
            "exact_stratum_fields": ["task", "hardware", "time_limit", "execution_timeout"],
        },
        "inventory": {
            "cards": len(cards),
            "runs": len(runs),
            "clients": len({row["client"] for row in runs.values()}),
            "tasks": len({row["task"] for row in runs.values()}),
            "train_pairs": len(pairs),
            "same_client_same_environment_pairs": len(exact),
            "eligible_clients": len(eligible_clients),
            "eligible_client_names": eligible_clients,
            "total_eligible_test_pairs": len(pool),
            "eligible_client_task_cells": sum(per_client[item]["supported_test_tasks"] for item in eligible_clients),
        },
        "per_client": per_client,
        "criteria": {
            "eligible_clients_ge_6": len(eligible_clients) >= MIN_ELIGIBLE_CLIENTS,
            "total_eligible_test_pairs_ge_3000": len(pool) >= MIN_TOTAL_ELIGIBLE_TEST_PAIRS,
        },
        "scope": {
            "gpu": 0,
            "api_calls": 0,
            "model_trained": False,
            "pair_orientation_used_for_effect": False,
            "numeric_grade_used": False,
            "frozen_test_used": False,
            "raw_code_emitted": False,
        },
    }
    summary["status"] = (
        "CROSS_CLIENT_TRANSFER_SUPPORT_PASS"
        if all(summary["criteria"].values())
        else "INSUFFICIENT_CROSS_CLIENT_TRANSFER_SUPPORT"
    )
    return summary, pool


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--senior-source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit) or not re.fullmatch(r"[0-9a-f]{40}", args.senior_source_commit):
        raise AuditError("source commits must be full SHA1 values")
    cards_path = locked(args.cards, args.expect_cards_sha256)
    pairs_path = locked(args.pairs, args.expect_pairs_sha256)
    output = Path(args.output).resolve()
    if output.exists():
        raise AuditError("output already exists")
    output.mkdir(parents=True)
    cards, runs = load_cards(cards_path)
    pairs = load_pairs(pairs_path, cards)
    summary, pool = derive(cards, runs, pairs)
    summary["inputs"] = {
        "cards_sha256": args.expect_cards_sha256.lower(),
        "pairs_sha256": args.expect_pairs_sha256.lower(),
    }
    summary["source_commit"] = args.source_commit
    summary["senior_source_commit"] = args.senior_source_commit
    write_json(output / "summary.json", summary)
    with (output / "eligible_pool.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in pool:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    manifest = {
        name: sha256_file(output / name)
        for name in ("eligible_pool.jsonl", "summary.json")
    }
    write_json(output / "sha256_manifest.json", manifest)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
