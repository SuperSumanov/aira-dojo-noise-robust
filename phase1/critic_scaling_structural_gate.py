"""Outcome-free structural gate for clean direct-decision critic scaling."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "critic-scaling-structural-gate-v1"
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "merged": ("bd6551dfce85d83f9f59716a31a9d7ab88605d6a21f51b41eb28177a952f47d0", 2552829),
    "draft": ("3ca77a18e224cacbb7f52121d6e8c2b66f17298c68dd06fbc42a14a238ad05b9", 1465008),
    "improve": ("7aca481afda5317fe78a0ad52fc7488fceff7fde6531c74ebb718df9e3b6926e", 1087821),
}


class GateError(RuntimeError):
    """Raised when an identity or split invariant fails closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def verify_identity(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    if path.stat().st_size != expected_bytes or sha256_file(path) != expected_hash:
        raise GateError(f"{role} identity mismatch")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise GateError(f"blank row at {path.name}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise GateError(f"non-object row at {path.name}:{line_number}")
            rows.append(row)
    return rows


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        task, parent = row["task"], row["parent"]
        left, right = sorted((row["better"], row["worse"]))
    except (KeyError, TypeError, ValueError) as error:
        raise GateError("invalid pair identity") from error
    if not all(isinstance(value, str) and value for value in (task, parent, left, right)):
        raise GateError("empty pair identity")
    if left == right:
        raise GateError("self pair")
    return task, parent, left, right


def keyed(rows: list[dict[str, Any]], role: str) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    output: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = pair_key(row)
        if key in output:
            raise GateError(f"duplicate unordered pair in {role}")
        output[key] = row
    return output


def source_form(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if normalized.pop("outer_intask_split", None) != "train":
        raise GateError("derived train/dev row lacks outer-train receipt")
    normalized.pop("train_dev_protocol", None)
    normalized.pop("train_dev_seed", None)
    normalized["intask_split"] = "train"
    return normalized


def load_card_maps(path: Path, needed: set[str]) -> tuple[dict[str, str], dict[str, str], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise GateError("cards root is not grouped")
    run_of: dict[str, str] = {}
    task_of: dict[str, str] = {}
    seen: set[str] = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not isinstance(cards, list):
            raise GateError("invalid grouped-card entry")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str):
                raise GateError("invalid card")
            card_id = card["id"]
            if card_id in seen:
                raise GateError("duplicate card id")
            seen.add(card_id)
            if card_id not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            if not isinstance(task, str) or not task:
                raise GateError("needed card lacks task")
            run_of[card_id] = run_id
            task_of[card_id] = task
    if set(run_of) != needed:
        raise GateError("pair endpoint missing from cards")
    return run_of, task_of, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


def inventory(
    rows: dict[tuple[str, str, str, str], dict[str, Any]],
    run_of: dict[str, str],
    semantics: dict[tuple[str, str, str, str], str],
) -> dict[str, Any]:
    endpoints = {endpoint for key in rows for endpoint in key[2:]}
    runs = {run_of[endpoint] for endpoint in endpoints}
    task_counts = Counter(key[0] for key in rows)
    semantic_counts = Counter(semantics[key] for key in rows)
    parents = {(key[0], key[1]) for key in rows}
    return {
        "pairs": len(rows),
        "endpoints": len(endpoints),
        "runs": len(runs),
        "tasks": len(task_counts),
        "parents": len(parents),
        "task_counts": dict(sorted(task_counts.items())),
        "semantics": dict(sorted(semantic_counts.items())),
        "dominant_task_pairs": max(task_counts.values(), default=0),
        "dominant_task_share": max(task_counts.values(), default=0) / len(rows) if rows else None,
    }


def evaluate(
    cards_path: Path,
    merged_path: Path,
    draft_path: Path,
    improve_path: Path,
    train_path: Path,
    dev_path: Path,
    test_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    for role, path in (("cards", cards_path), ("merged", merged_path), ("draft", draft_path), ("improve", improve_path)):
        verify_identity(path, role)

    merged = keyed(read_jsonl(merged_path), "merged")
    draft = keyed(read_jsonl(draft_path), "draft")
    improve = keyed(read_jsonl(improve_path), "improve")
    if set(draft) & set(improve) or set(merged) != set(draft) | set(improve):
        raise GateError("Draft/Improve are not an exact disjoint union of merged")
    semantics = {key: "Draft" for key in draft} | {key: "Improve" for key in improve}

    source_train = {key: row for key, row in merged.items() if row.get("intask_split") == "train"}
    source_test = {key: row for key, row in merged.items() if row.get("intask_split") == "test"}
    if len(source_train) != 5240 or len(source_test) != 931:
        raise GateError("outer split cardinality mismatch")

    train = keyed(read_jsonl(train_path), "train")
    dev = keyed(read_jsonl(dev_path), "dev")
    test = keyed(read_jsonl(test_path), "test")
    if any(row.get("intask_split") != "train" for row in train.values()):
        raise GateError("train output contains non-train rows")
    if any(row.get("intask_split") != "dev" for row in dev.values()):
        raise GateError("dev output contains non-dev rows")
    if any(row.get("intask_split") != "test" for row in test.values()):
        raise GateError("test output contains non-test rows")
    if test != source_test:
        raise GateError("dedicated test differs from source outer test")
    for derived in (train, dev):
        for key, row in derived.items():
            if key not in source_train or source_form(row) != source_train[key]:
                raise GateError("derived train/dev content differs from outer train")
    if set(train) & set(dev) or (set(train) | set(dev)) - set(source_train):
        raise GateError("invalid train/dev pair partition")

    all_keys = set(train) | set(dev) | set(test)
    endpoints = {endpoint for key in all_keys for endpoint in key[2:]}
    run_of, task_of, card_inventory = load_card_maps(cards_path, endpoints)
    for key in all_keys:
        if task_of[key[2]] != key[0] or task_of[key[3]] != key[0]:
            raise GateError("pair/card task mismatch")

    split_endpoints = {
        name: {endpoint for key in rows for endpoint in key[2:]}
        for name, rows in (("train", train), ("dev", dev), ("test", test))
    }
    split_runs = {name: {run_of[endpoint] for endpoint in values} for name, values in split_endpoints.items()}
    overlap = {
        f"{left}_{right}_pairs": len(set(rows_left) & set(rows_right))
        for left, rows_left, right, rows_right in (
            ("train", train, "dev", dev), ("train", train, "test", test), ("dev", dev, "test", test)
        )
    }
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        overlap[f"{left}_{right}_endpoints"] = len(split_endpoints[left] & split_endpoints[right])
        overlap[f"{left}_{right}_runs"] = len(split_runs[left] & split_runs[right])
    if any(overlap.values()):
        raise GateError("split overlap is nonzero")

    dropped = set(source_train) - set(train) - set(dev)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest = {
        "train_pairs": len(train),
        "dev_pairs": len(dev),
        "frozen_test_pairs": len(test),
        "dropped_cross_split_pairs": len(dropped),
        "train_pairs_sha256": sha256_file(train_path),
        "dev_pairs_sha256": sha256_file(dev_path),
        "frozen_test_pairs_sha256": sha256_file(test_path),
        "seed": 20260821,
        "dev_fraction": 0.1,
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        raise GateError("split manifest mismatch")

    inventories = {
        name: inventory(rows, run_of, semantics)
        for name, rows in (("train", train), ("dev", dev), ("test", test))
    }
    dropped_semantics = Counter(semantics[key] for key in dropped)
    gates = {
        "zero_pair_endpoint_run_overlap": not any(overlap.values()),
        "test_exact_931": len(test) == 931,
        "train_at_least_3800": len(train) >= 3800,
        "dev_at_least_300": len(dev) >= 300,
        "cross_split_drop_at_most_25pct": len(dropped) / len(source_train) <= 0.25,
        "dev_at_least_20_tasks": inventories["dev"]["tasks"] >= 20,
        "dev_dominant_at_most_20pct": inventories["dev"]["dominant_task_share"] <= 0.20,
        "dev_draft_at_least_100": inventories["dev"]["semantics"].get("Draft", 0) >= 100,
        "dev_improve_at_least_100": inventories["dev"]["semantics"].get("Improve", 0) >= 100,
    }
    return {
        "protocol": PROTOCOL,
        "status": "STRUCTURAL_PREP_ELIGIBLE" if all(gates.values()) else "STRUCTURAL_PREP_INELIGIBLE",
        "input_identity": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in ("cards", "merged", "draft", "improve")
        },
        "split_parameters": {"seed": 20260821, "dev_fraction": 0.1},
        "card_inventory": card_inventory,
        "inventory": inventories,
        "dropped_cross_split_pairs": len(dropped),
        "dropped_cross_split_fraction": len(dropped) / len(source_train),
        "dropped_semantics": dict(sorted(dropped_semantics.items())),
        "overlap": overlap,
        "manifest_checks": expected_manifest,
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("merged", type=Path)
    parser.add_argument("draft", type=Path)
    parser.add_argument("improve", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("test", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    result = evaluate(
        arguments.cards, arguments.merged, arguments.draft, arguments.improve,
        arguments.train, arguments.dev, arguments.test, arguments.manifest,
    )
    with arguments.output.open("xb") as handle:
        handle.write(canonical(result))
    print(canonical(result).decode(), end="")


if __name__ == "__main__":
    main()
