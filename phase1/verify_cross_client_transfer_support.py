#!/usr/bin/env python3
"""Independent verifier for cross-client transfer structural support."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_credential_free(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            window = overlap + chunk
            if CREDENTIAL.search(window):
                raise RuntimeError(f"credential-shaped bytes refused: {path.name}")
            overlap = window[-512:]


def env(card: dict[str, Any]) -> tuple[Any, Any, Any]:
    return card.get("hardware"), card.get("time_limit"), card.get("execution_timeout")


def env_sha(value: tuple[Any, Any, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def recompute(cards_path: Path, pairs_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with cards_path.open(encoding="utf-8") as handle:
        grouped = json.load(handle)
    cards: dict[str, dict[str, Any]] = {}
    run_meta: dict[str, dict[str, Any]] = {}
    for run_id, rows in grouped.items():
        first = rows[0]
        task = first["task"]["name"]
        client = first["client"]
        environment = env(first)
        run_meta[run_id] = {"task": task, "client": client, "environment": environment}
        for card in rows:
            if card["task"]["name"] != task or card["client"] != client or env(card) != environment:
                raise RuntimeError("independent run contract failure")
            cards[card["id"]] = {
                "run": run_id,
                "task": task,
                "client": client,
                "environment": environment,
                "environment_sha256": env_sha(environment),
                "code_sha256": hashlib.sha256(card.get("code", "").encode()).hexdigest(),
            }
    exact: list[dict[str, Any]] = []
    all_train = 0
    seen: set[str] = set()
    for line in pairs_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["intask_split"] != "train":
            continue
        all_train += 1
        endpoints = sorted((row["better"], row["worse"]))
        pair_key = hashlib.sha256("\0".join(endpoints).encode()).hexdigest()
        if pair_key in seen:
            raise RuntimeError("independent duplicate pair")
        seen.add(pair_key)
        left, right = cards[endpoints[0]], cards[endpoints[1]]
        if left["task"] != right["task"]:
            raise RuntimeError("independent cross-task pair")
        if left["client"] == right["client"] and left["environment"] == right["environment"]:
            exact.append(
                {
                    "pair_key_sha256": pair_key,
                    "endpoint_a": endpoints[0],
                    "endpoint_b": endpoints[1],
                    "run_ids": sorted({left["run"], right["run"]}),
                    "task": left["task"],
                    "client": left["client"],
                    "environment_sha256": left["environment_sha256"],
                    "code_sha256s": [left["code_sha256"], right["code_sha256"]],
                }
            )
    clients = sorted({row["client"] for row in exact})
    code_by_client: dict[str, set[str]] = collections.defaultdict(set)
    for card in cards.values():
        code_by_client[card["client"]].add(card["code_sha256"])
    strata: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in exact:
        strata[(row["task"], row["environment_sha256"])].append(row)
    per_client: dict[str, Any] = {}
    pool: list[dict[str, Any]] = []
    for client in clients:
        other_codes = set().union(*(code_by_client[item] for item in clients if item != client))
        pre = [row for row in exact if row["client"] == client]
        selected = []
        overlap = 0
        for row in pre:
            if any(value in other_codes for value in row["code_sha256s"]):
                overlap += 1
                continue
            other = [item for item in strata[(row["task"], row["environment_sha256"])] if item["client"] != client]
            if len(other) >= 50 and len({item["client"] for item in other}) >= 2:
                selected.append(row)
        selected_strata = {(row["task"], row["environment_sha256"]) for row in selected}
        train = [row for row in exact if row["client"] != client and (row["task"], row["environment_sha256"]) in selected_strata]
        tasks = collections.Counter(row["task"] for row in selected)
        test_runs = {value for row in selected for value in row["run_ids"]}
        train_runs = {value for row in train for value in row["run_ids"]}
        train_clients = {row["client"] for row in train}
        dominant = max(tasks.values(), default=0) / len(selected) if selected else None
        criteria = {
            "test_pairs_ge_200": len(selected) >= 200,
            "test_tasks_ge_4": len(tasks) >= 4,
            "test_runs_ge_15": len(test_runs) >= 15,
            "train_pairs_ge_1000": len(train) >= 1000,
            "train_clients_ge_3": len(train_clients) >= 3,
            "dominant_task_share_le_0_50": dominant is not None and dominant <= 0.50,
        }
        eligible = all(criteria.values())
        per_client[client] = {
            "prefilter_exact_pairs": len(pre),
            "cross_client_exact_code_overlap_pairs_excluded": overlap,
            "supported_test_pairs": len(selected),
            "supported_test_tasks": len(tasks),
            "supported_test_runs": len(test_runs),
            "supported_train_pairs": len(train),
            "supported_train_runs": len(train_runs),
            "supported_train_clients": len(train_clients),
            "dominant_test_task_share": dominant,
            "test_pairs_per_task": dict(sorted(tasks.items())),
            "criteria": criteria,
            "eligible": eligible,
        }
        if eligible:
            for row in selected:
                pool.append({key: row[key] for key in ("client", "endpoint_a", "endpoint_b", "environment_sha256", "pair_key_sha256", "run_ids", "task")})
    pool.sort(key=lambda row: (row["client"], row["task"], row["pair_key_sha256"]))
    eligible_clients = sorted(client for client, value in per_client.items() if value["eligible"])
    inventory = {
        "cards": len(cards),
        "runs": len(run_meta),
        "clients": len({value["client"] for value in run_meta.values()}),
        "tasks": len({value["task"] for value in run_meta.values()}),
        "train_pairs": all_train,
        "same_client_same_environment_pairs": len(exact),
        "eligible_clients": len(eligible_clients),
        "eligible_client_names": eligible_clients,
        "total_eligible_test_pairs": len(pool),
        "eligible_client_task_cells": sum(per_client[item]["supported_test_tasks"] for item in eligible_clients),
    }
    return {"inventory": inventory, "per_client": per_client}, pool


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cards, pairs = Path(args.cards), Path(args.pairs)
    if sha(cards) != args.expect_cards_sha256 or sha(pairs) != args.expect_pairs_sha256:
        raise RuntimeError("independent input hash mismatch")
    assert_credential_free(cards)
    assert_credential_free(pairs)
    artifact = Path(args.artifact)
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    observed_pool = [json.loads(line) for line in (artifact / "eligible_pool.jsonl").read_text(encoding="utf-8").splitlines()]
    rebuilt, pool = recompute(cards, pairs)
    if rebuilt["inventory"] != summary["inventory"] or rebuilt["per_client"] != summary["per_client"]:
        raise RuntimeError("independent summary mismatch")
    if pool != observed_pool:
        raise RuntimeError("independent pool mismatch")
    output = {
        "status": "VERIFIED_CROSS_CLIENT_TRANSFER_SUPPORT",
        "summary_sha256": sha(artifact / "summary.json"),
        "eligible_pool_sha256": sha(artifact / "eligible_pool.jsonl"),
        "eligible_clients": rebuilt["inventory"]["eligible_clients"],
        "eligible_test_pairs": rebuilt["inventory"]["total_eligible_test_pairs"],
    }
    path = Path(args.output)
    if path.exists():
        raise RuntimeError("verification output exists")
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
