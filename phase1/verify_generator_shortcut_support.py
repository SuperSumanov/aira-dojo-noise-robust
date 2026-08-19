#!/usr/bin/env python3
"""Independent verifier for generator-shortcut structural support artifacts."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


FOLDS = 5
FOLD_DOMAIN = "generator-shortcut-run-oof-v1|20260819"


class VerifyError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_fold(run_id: str) -> int:
    digest = hashlib.sha256(f"{FOLD_DOMAIN}|{run_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % FOLDS


def pool(rows: list[dict[str, Any]], predicate: Any) -> dict[str, Any]:
    selected = [row for row in rows if predicate(row)]
    tasks = collections.Counter(row["task"] for row in selected)
    return {
        "pairs": len(selected),
        "tasks": len(tasks),
        "dominant_task_share": max(tasks.values(), default=0) / len(selected) if selected else None,
        "pairs_per_task": dict(sorted(tasks.items())),
    }


def verify(args: argparse.Namespace) -> int:
    cards_path = Path(args.cards).resolve()
    pairs_path = Path(args.pairs).resolve()
    artifact_path = Path(args.artifact).resolve()
    if sha256_file(cards_path) != args.expect_cards_sha256 or sha256_file(pairs_path) != args.expect_pairs_sha256:
        raise VerifyError("input hash mismatch")
    summary = json.loads((artifact_path / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((artifact_path / "sha256_manifest.json").read_text(encoding="utf-8"))
    if manifest != {"summary.json": sha256_file(artifact_path / "summary.json")}:
        raise VerifyError("artifact manifest mismatch")

    grouped = json.loads(cards_path.read_text(encoding="utf-8"))
    card_run: dict[str, str] = {}
    runs: dict[str, dict[str, Any]] = {}
    for run_id, cards in grouped.items():
        first = cards[0]
        task = first["task"]["name"]
        client_value = first.get("client")
        client = client_value if isinstance(client_value, str) and client_value.strip() else None
        env = (first.get("hardware"), first.get("time_limit"), first.get("execution_timeout"))
        for card in cards:
            if card["task"]["name"] != task:
                raise VerifyError("run task mismatch")
            if (card.get("client"), card.get("hardware"), card.get("time_limit"), card.get("execution_timeout")) != (
                first.get("client"), first.get("hardware"), first.get("time_limit"), first.get("execution_timeout")
            ):
                raise VerifyError("run config mismatch")
            card_id = card["id"]
            if card_id in card_run:
                raise VerifyError("duplicate card")
            card_run[card_id] = run_id
        runs[run_id] = {"task": task, "client": client, "env": env, "fold": run_fold(run_id)}

    rows: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    with pairs_path.open(encoding="utf-8") as handle:
        for line in handle:
            pair = json.loads(line)
            if pair["intask_split"] != "train":
                continue
            endpoints = (pair["better"], pair["worse"])
            key = tuple(sorted(endpoints))
            if key in identities:
                raise VerifyError("duplicate pair")
            identities.add(key)
            endpoint_runs = sorted({card_run[value] for value in endpoints})
            endpoint_rows = [runs[card_run[value]] for value in endpoints]
            if len({row["task"] for row in endpoint_rows}) != 1:
                raise VerifyError("cross-task pair")
            clients = [row["client"] for row in endpoint_rows]
            folds = {runs[run_id]["fold"] for run_id in endpoint_runs}
            rows.append(
                {
                    "task": endpoint_rows[0]["task"],
                    "clients": clients,
                    "known": all(value is not None for value in clients),
                    "same_client": clients[0] == clients[1] if all(value is not None for value in clients) else None,
                    "same_environment": endpoint_rows[0]["env"] == endpoint_rows[1]["env"],
                    "oof": len(folds) == 1,
                }
            )

    expected_pools = {
        "all_train": pool(rows, lambda row: True),
        "known_client": pool(rows, lambda row: row["known"]),
        "same_client": pool(rows, lambda row: row["known"] and row["same_client"]),
        "cross_client": pool(rows, lambda row: row["known"] and not row["same_client"]),
        "cross_client_same_environment": pool(
            rows, lambda row: row["known"] and not row["same_client"] and row["same_environment"]
        ),
        "oof_all": pool(rows, lambda row: row["oof"]),
        "oof_same_client": pool(rows, lambda row: row["oof"] and row["known"] and row["same_client"]),
        "oof_cross_client_same_environment": pool(
            rows, lambda row: row["oof"] and row["known"] and not row["same_client"] and row["same_environment"]
        ),
    }
    if summary.get("pools") != expected_pools:
        raise VerifyError("pool counts do not reproduce")
    if summary.get("inventory", {}).get("cards") != len(card_run) or summary["inventory"].get("runs") != len(runs):
        raise VerifyError("inventory does not reproduce")
    result = {
        "status": "VERIFIED_GENERATOR_SHORTCUT_SUPPORT",
        "artifact_summary_sha256": sha256_file(artifact_path / "summary.json"),
        "cards": len(card_run),
        "runs": len(runs),
        "train_pairs": len(rows),
        "pools_reproduced": True,
    }
    output = Path(args.output).resolve()
    if output.exists():
        raise VerifyError("output exists")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", required=True)
    try:
        return verify(parser.parse_args())
    except (VerifyError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"GENERATOR_SHORTCUT_SUPPORT_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
