#!/usr/bin/env python3
"""Outcome-blind support audit for a generator/client shortcut experiment."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "generator-shortcut-support-v1"
FOLDS = 5
FOLD_DOMAIN = "generator-shortcut-run-oof-v1|20260819"
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


def locked(path_value: str, expected: str) -> Path:
    path = Path(path_value).resolve()
    if not path.is_file() or sha256_file(path) != expected:
        raise AuditError(f"locked input mismatch: {path.name}")
    if not credential_free(path):
        raise AuditError(f"credential-shaped bytes refused: {path.name}")
    return path


def config(card: dict[str, Any]) -> tuple[Any, ...]:
    return (
        card.get("client"),
        card.get("hardware"),
        card.get("time_limit"),
        card.get("execution_timeout"),
    )


def environment(card: dict[str, Any]) -> tuple[Any, ...]:
    return (card.get("hardware"), card.get("time_limit"), card.get("execution_timeout"))


def fold(run_id: str) -> int:
    digest = hashlib.sha256(f"{FOLD_DOMAIN}|{run_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % FOLDS


def load_cards(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not payload:
        raise AuditError("grouped cards must be a nonempty object")
    cards_out: dict[str, dict[str, Any]] = {}
    runs_out: dict[str, dict[str, Any]] = {}
    for run_id, cards in payload.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(cards, list) or not cards:
            raise AuditError("invalid grouped run")
        first = cards[0]
        if not isinstance(first, dict) or not isinstance(first.get("task"), dict):
            raise AuditError("invalid first card")
        task = first["task"].get("name")
        if not isinstance(task, str) or not task:
            raise AuditError("run task missing")
        run_config = config(first)
        run_environment = environment(first)
        client = first.get("client")
        client = client if isinstance(client, str) and client.strip() else None
        for card in cards:
            if not isinstance(card, dict) or not isinstance(card.get("task"), dict):
                raise AuditError("invalid card")
            card_id = card.get("id")
            if not isinstance(card_id, str) or not card_id or card_id in cards_out:
                raise AuditError("card identity missing or duplicated")
            if card["task"].get("name") != task or config(card) != run_config:
                raise AuditError("run task/config is not constant")
            cards_out[card_id] = {"run_id": run_id, "task": task}
        runs_out[run_id] = {
            "task": task,
            "client": client,
            "environment": run_environment,
            "fold": fold(run_id),
            "cards": len(cards),
        }
    return cards_out, runs_out


def load_train_pairs(path: Path, cards: dict[str, dict[str, Any]], runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AuditError(f"blank pair line {line_number}")
            row = json.loads(line)
            if row.get("intask_split") not in {"train", "test"}:
                raise AuditError("pair split invalid")
            if row["intask_split"] != "train":
                continue
            endpoints = (row.get("better"), row.get("worse"))
            if not all(isinstance(value, str) and value in cards for value in endpoints):
                raise AuditError("pair endpoint invalid")
            if endpoints[0] == endpoints[1]:
                raise AuditError("self pair")
            key = hashlib.sha256("\0".join(sorted(endpoints)).encode()).hexdigest()
            if key in seen:
                raise AuditError("duplicate unordered train pair")
            seen.add(key)
            endpoint_runs = sorted({cards[value]["run_id"] for value in endpoints})
            task_values = {cards[value]["task"] for value in endpoints}
            if len(task_values) != 1:
                raise AuditError("pair spans tasks")
            clients = [runs[cards[value]["run_id"]]["client"] for value in endpoints]
            environments = [runs[cards[value]["run_id"]]["environment"] for value in endpoints]
            endpoint_folds = {runs[run_id]["fold"] for run_id in endpoint_runs}
            output.append(
                {
                    "task": next(iter(task_values)),
                    "run_ids": endpoint_runs,
                    "clients": clients,
                    "clients_known": all(value is not None for value in clients),
                    "same_client": clients[0] == clients[1] if all(value is not None for value in clients) else None,
                    "same_environment": environments[0] == environments[1],
                    "oof_eligible": len(endpoint_folds) == 1,
                    "fold": next(iter(endpoint_folds)) if len(endpoint_folds) == 1 else None,
                }
            )
    return output


def counter(rows: list[dict[str, Any]], predicate: Any) -> dict[str, Any]:
    selected = [row for row in rows if predicate(row)]
    per_task = collections.Counter(row["task"] for row in selected)
    return {
        "pairs": len(selected),
        "tasks": len(per_task),
        "dominant_task_share": max(per_task.values(), default=0) / len(selected) if selected else None,
        "pairs_per_task": dict(sorted(per_task.items())),
    }


def derive(cards: dict[str, dict[str, Any]], runs: dict[str, dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    run_clients = collections.Counter(row["client"] or "<missing>" for row in runs.values())
    same_client_pairs = [row for row in pairs if row["clients_known"] and row["same_client"]]
    same_by_client: dict[str, dict[str, Any]] = {}
    for client in sorted(value for value in run_clients if value != "<missing>"):
        selected = [row for row in same_client_pairs if row["clients"][0] == client and row["oof_eligible"]]
        tasks = collections.Counter(row["task"] for row in selected)
        same_by_client[client] = {"oof_pairs": len(selected), "tasks": len(tasks), "pairs_per_task": dict(sorted(tasks.items()))}

    pools = {
        "all_train": counter(pairs, lambda row: True),
        "known_client": counter(pairs, lambda row: row["clients_known"]),
        "same_client": counter(pairs, lambda row: row["clients_known"] and row["same_client"]),
        "cross_client": counter(pairs, lambda row: row["clients_known"] and not row["same_client"]),
        "cross_client_same_environment": counter(
            pairs, lambda row: row["clients_known"] and not row["same_client"] and row["same_environment"]
        ),
        "oof_all": counter(pairs, lambda row: row["oof_eligible"]),
        "oof_same_client": counter(
            pairs, lambda row: row["oof_eligible"] and row["clients_known"] and row["same_client"]
        ),
        "oof_cross_client_same_environment": counter(
            pairs,
            lambda row: row["oof_eligible"]
            and row["clients_known"]
            and not row["same_client"]
            and row["same_environment"],
        ),
    }
    eligible_loso_clients = sorted(
        client for client, row in same_by_client.items() if row["oof_pairs"] >= 80 and row["tasks"] >= 2
    )
    criteria = {
        "known_client_train_pairs_ge_4000": pools["known_client"]["pairs"] >= 4000,
        "oof_same_client_pairs_ge_400": pools["oof_same_client"]["pairs"] >= 400,
        "oof_same_client_tasks_ge_6": pools["oof_same_client"]["tasks"] >= 6,
        "oof_cross_client_same_environment_pairs_ge_400": pools["oof_cross_client_same_environment"]["pairs"] >= 400,
        "oof_cross_client_same_environment_tasks_ge_6": pools["oof_cross_client_same_environment"]["tasks"] >= 6,
        "eligible_loso_clients_ge_2": len(eligible_loso_clients) >= 2,
    }
    return {
        "status": "GENERATOR_SHORTCUT_EFFECT_AUDIT_FEASIBLE" if all(criteria.values()) else "INSUFFICIENT_GENERATOR_SHORTCUT_SUPPORT",
        "inventory": {
            "cards": len(cards),
            "runs": len(runs),
            "tasks": len({row["task"] for row in runs.values()}),
            "train_pairs": len(pairs),
            "clients": len(run_clients) - ("<missing>" in run_clients),
            "missing_client_runs": run_clients.get("<missing>", 0),
        },
        "runs_per_client": dict(sorted(run_clients.items())),
        "pools": pools,
        "same_client_oof_support_by_client": same_by_client,
        "eligible_loso_clients": eligible_loso_clients,
        "criteria": criteria,
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(args: argparse.Namespace) -> int:
    cards_path = locked(args.cards, args.expect_cards_sha256)
    pairs_path = locked(args.pairs, args.expect_pairs_sha256)
    cards, runs = load_cards(cards_path)
    pairs = load_train_pairs(pairs_path, cards, runs)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise AuditError("output path exists")
    staging.mkdir(parents=True)
    summary = {
        "protocol": PROTOCOL,
        "source_commit": args.source_commit,
        "senior_source_commit": args.senior_source_commit,
        **derive(cards, runs, pairs),
        "configuration": {"folds": FOLDS, "fold_domain": FOLD_DOMAIN},
        "inputs": {"cards_sha256": args.expect_cards_sha256, "pairs_sha256": args.expect_pairs_sha256},
        "scope": {
            "numeric_grade_used": False,
            "pair_orientation_used_for_effect": False,
            "raw_code_used": False,
            "frozen_test_used": False,
            "model_trained": False,
            "gpu": 0,
            "api_calls": 0,
        },
    }
    write_json(staging / "summary.json", summary)
    write_json(staging / "sha256_manifest.json", {"summary.json": sha256_file(staging / "summary.json")})
    staging.replace(output)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--cards", required=True)
    value.add_argument("--expect-cards-sha256", required=True)
    value.add_argument("--pairs", required=True)
    value.add_argument("--expect-pairs-sha256", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--senior-source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except (AuditError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"GENERATOR_SHORTCUT_SUPPORT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
