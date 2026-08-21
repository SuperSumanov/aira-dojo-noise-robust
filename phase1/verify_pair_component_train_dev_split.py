"""Independent verifier for pair-graph component train/dev splits."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROTOCOL = "pair-graph-component-train-dev-split-v1"
SEED = 20260821
NUMERATOR = 1
DENOMINATOR = 10
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "pairs": ("bd6551dfce85d83f9f59716a31a9d7ab88605d6a21f51b41eb28177a952f47d0", 2552829),
}


class VerificationError(RuntimeError):
    """Raised when the independently reconstructed split differs."""


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def rows_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(compact(row) + "\n" for row in rows).encode()


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise VerificationError(f"blank row {line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise VerificationError(f"non-object row {line_number}")
            rows.append(row)
    return rows


def key_of(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        endpoints = sorted((row["better"], row["worse"]))
        values = (row["task"], row["parent"], endpoints[0], endpoints[1])
    except (KeyError, TypeError, ValueError) as error:
        raise VerificationError("invalid pair identity") from error
    if not all(isinstance(value, str) and value for value in values) or values[2] == values[3]:
        raise VerificationError("invalid pair identity")
    return values


def fixed_identity(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    if path.stat().st_size != expected_bytes or digest_file(path) != expected_hash:
        raise VerificationError(f"{role} identity mismatch")


def card_lookup(path: Path, needed: set[str]) -> tuple[dict[str, str], dict[str, str], dict[str, int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise VerificationError("cards root invalid")
    run_map: dict[str, str] = {}
    task_map: dict[str, str] = {}
    task_by_run: dict[str, str] = {}
    all_ids: set[str] = set()
    total = 0
    for run_id, cards in payload.items():
        if not isinstance(run_id, str) or not isinstance(cards, list):
            raise VerificationError("grouped cards invalid")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str):
                raise VerificationError("card invalid")
            card_id = card["id"]
            if card_id in all_ids:
                raise VerificationError("card id duplicated")
            all_ids.add(card_id)
            if card_id in needed:
                task_object = card.get("task")
                task_name = task_object.get("name") if isinstance(task_object, dict) else None
                if not isinstance(task_name, str) or not task_name:
                    raise VerificationError("needed card task missing")
                previous_task = task_by_run.setdefault(run_id, task_name)
                if previous_task != task_name:
                    raise VerificationError("physical run mixes needed endpoint tasks")
                run_map[card_id] = run_id
                task_map[card_id] = task_name
    if set(run_map) != needed:
        raise VerificationError("needed endpoint absent")
    return run_map, task_map, {"cards": total, "run_groups": len(payload), "needed_cards": len(needed)}


def component_hash(task: str, run_ids: tuple[str, ...]) -> str:
    return hashlib.sha256(compact([SEED, task, list(run_ids)]).encode()).hexdigest()


def select_component_positions(weights: list[int], ids: list[str]) -> tuple[int, ...]:
    if len(weights) == 1:
        return ()
    possibilities: dict[int, tuple[int, ...]] = {0: ()}
    for position in range(len(weights)):
        additions = []
        for weight_sum, positions in possibilities.items():
            additions.append((weight_sum + weights[position], positions + (position,)))
        for weight_sum, positions in additions:
            incumbent = possibilities.get(weight_sum)
            if incumbent is None or tuple(ids[index] for index in positions) < tuple(
                ids[index] for index in incumbent
            ):
                possibilities[weight_sum] = positions
    full = tuple(range(len(weights)))
    proper = [(weight_sum, positions) for weight_sum, positions in possibilities.items() if positions and positions != full]
    if not proper:
        raise VerificationError("no proper component subset")
    total_pairs = sum(weights)
    return min(
        proper,
        key=lambda item: (
            abs(DENOMINATOR * item[0] - NUMERATOR * total_pairs),
            item[0],
            tuple(ids[index] for index in item[1]),
        ),
    )[1]


def reconstruct(
    cards_path: Path,
    pairs_path: Path,
    *,
    enforce_fixed_identity: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if enforce_fixed_identity:
        fixed_identity(cards_path, "cards")
        fixed_identity(pairs_path, "pairs")
    source_rows = read_rows(pairs_path)
    source_keys = [key_of(row) for row in source_rows]
    if len(source_keys) != len(set(source_keys)):
        raise VerificationError("source duplicate pair")
    outer_train = [row for row in source_rows if row.get("intask_split") == "train"]
    outer_test = [row for row in source_rows if row.get("intask_split") == "test"]
    if len(outer_train) + len(outer_test) != len(source_rows):
        raise VerificationError("source split invalid")
    needed = {endpoint for key in source_keys for endpoint in key[2:]}
    run_map, task_map, card_inventory = card_lookup(cards_path, needed)

    parent_by_task: dict[str, dict[str, str]] = defaultdict(dict)

    def root(task: str, run_id: str) -> str:
        parents = parent_by_task[task]
        current = run_id
        while parents[current] != current:
            current = parents[current]
        return current

    def ensure(task: str, run_id: str) -> None:
        parent_by_task[task].setdefault(run_id, run_id)

    for row in outer_train:
        task, _, left, right = key_of(row)
        if task_map[left] != task or task_map[right] != task:
            raise VerificationError("pair/card task differs")
        left_run, right_run = run_map[left], run_map[right]
        ensure(task, left_run)
        ensure(task, right_run)
        left_root, right_root = root(task, left_run), root(task, right_run)
        if left_root != right_root:
            low, high = sorted((left_root, right_root))
            parent_by_task[task][high] = low

    members: dict[tuple[str, str], set[str]] = defaultdict(set)
    for task, parents in parent_by_task.items():
        for run_id in parents:
            members[(task, root(task, run_id))].add(run_id)

    pair_roots: dict[tuple[str, str, str, str], tuple[str, str]] = {}
    weights: Counter[tuple[str, str]] = Counter()
    for row in outer_train:
        pair_key = key_of(row)
        task, _, left, right = pair_key
        pair_root = (task, root(task, run_map[left]))
        if pair_root[1] != root(task, run_map[right]):
            raise VerificationError("pair crosses reconstructed component")
        pair_roots[pair_key] = pair_root
        weights[pair_root] += 1

    roots_per_task: dict[str, list[tuple[str, str]]] = defaultdict(list)
    ids: dict[tuple[str, str], str] = {}
    for task_root, run_ids in members.items():
        task = task_root[0]
        ids[task_root] = component_hash(task, tuple(sorted(run_ids)))
        roots_per_task[task].append(task_root)

    dev_roots: set[tuple[str, str]] = set()
    task_receipts: dict[str, Any] = {}
    for task in sorted(roots_per_task):
        ordered = sorted(roots_per_task[task], key=lambda item: ids[item])
        ordered_weights = [weights[item] for item in ordered]
        ordered_ids = [ids[item] for item in ordered]
        selected_positions = select_component_positions(ordered_weights, ordered_ids)
        selected = {ordered[position] for position in selected_positions}
        dev_roots.update(selected)
        task_receipts[task] = {
            "components": len(ordered),
            "pairs": sum(ordered_weights),
            "dev_components": len(selected),
            "dev_pairs": sum(weights[item] for item in selected),
            "train_components": len(ordered) - len(selected),
            "component_pair_weights": ordered_weights,
            "component_run_counts": [len(members[item]) for item in ordered],
            "component_ids_sha256": hashlib.sha256(compact(ordered_ids).encode()).hexdigest(),
            "dev_component_ids_sha256": hashlib.sha256(
                compact(sorted(ids[item] for item in selected)).encode()
            ).hexdigest(),
        }

    expected: dict[str, list[dict[str, Any]]] = {"train": [], "dev": []}
    for row in outer_train:
        pair_key = key_of(row)
        split = "dev" if pair_roots[pair_key] in dev_roots else "train"
        derived = dict(row)
        derived["outer_intask_split"] = "train"
        derived["intask_split"] = split
        derived["train_dev_protocol"] = PROTOCOL
        derived["train_dev_seed"] = SEED
        derived["train_dev_target_numerator"] = NUMERATOR
        derived["train_dev_target_denominator"] = DENOMINATOR
        derived["pair_component_id"] = ids[pair_roots[pair_key]]
        expected[split].append(derived)

    train_endpoints = {endpoint for row in expected["train"] for endpoint in key_of(row)[2:]}
    dev_endpoints = {endpoint for row in expected["dev"] for endpoint in key_of(row)[2:]}
    test_endpoints = {endpoint for row in outer_test for endpoint in key_of(row)[2:]}
    train_runs = {run_map[endpoint] for endpoint in train_endpoints}
    dev_runs = {run_map[endpoint] for endpoint in dev_endpoints}
    test_runs = {run_map[endpoint] for endpoint in test_endpoints}
    if train_endpoints & dev_endpoints or train_runs & dev_runs:
        raise VerificationError("reconstruction has train/dev leakage")
    if (train_endpoints | dev_endpoints) & test_endpoints or (train_runs | dev_runs) & test_runs:
        raise VerificationError("reconstruction has outer-test leakage")

    train_bytes = rows_bytes(expected["train"])
    dev_bytes = rows_bytes(expected["dev"])
    test_bytes = rows_bytes(outer_test)
    manifest = {
        "protocol": PROTOCOL,
        "status": "PAIR_COMPONENT_SPLIT_VERIFIED_BY_PRODUCER",
        "seed": SEED,
        "target_numerator": NUMERATOR,
        "target_denominator": DENOMINATOR,
        "cards_sha256": digest_file(cards_path),
        "source_pairs_sha256": digest_file(pairs_path),
        "train_pairs_sha256": hashlib.sha256(train_bytes).hexdigest(),
        "dev_pairs_sha256": hashlib.sha256(dev_bytes).hexdigest(),
        "heldout_test_pairs_sha256": hashlib.sha256(test_bytes).hexdigest(),
        "source_train_pairs": len(outer_train),
        "source_test_pairs": len(outer_test),
        "train_pairs": len(expected["train"]),
        "dev_pairs": len(expected["dev"]),
        "heldout_test_pairs": len(outer_test),
        "dropped_source_train_pairs": 0,
        "train_runs": len(train_runs),
        "dev_runs": len(dev_runs),
        "heldout_test_runs": len(test_runs),
        "train_dev_card_overlap": 0,
        "train_dev_run_overlap": 0,
        "outer_test_card_overlap": 0,
        "outer_test_run_overlap": 0,
        "card_inventory": card_inventory,
        "task_receipts": task_receipts,
        "components": len(members),
        "dev_components": len(dev_roots),
    }
    return expected["train"], expected["dev"], outer_test, manifest


def verify(
    cards_path: Path,
    pairs_path: Path,
    train_path: Path,
    dev_path: Path,
    test_path: Path,
    manifest_path: Path,
    *,
    enforce_fixed_identity: bool = True,
) -> dict[str, Any]:
    train, dev, test, expected_manifest = reconstruct(
        cards_path, pairs_path, enforce_fixed_identity=enforce_fixed_identity,
    )
    expected_files = {
        train_path: rows_bytes(train),
        dev_path: rows_bytes(dev),
        test_path: rows_bytes(test),
        manifest_path: (json.dumps(expected_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(),
    }
    for path, expected_bytes in expected_files.items():
        if path.read_bytes() != expected_bytes:
            raise VerificationError(f"output differs from independent reconstruction: {path.name}")
    return {
        "protocol": "independent-pair-graph-component-split-verifier-v1",
        "status": "PAIR_COMPONENT_SPLIT_INDEPENDENTLY_VERIFIED",
        "producer_protocol": expected_manifest["protocol"],
        "source_pairs": expected_manifest["source_train_pairs"] + expected_manifest["source_test_pairs"],
        "train_pairs": len(train),
        "dev_pairs": len(dev),
        "heldout_test_pairs": len(test),
        "components": expected_manifest["components"],
        "dev_components": expected_manifest["dev_components"],
        "train_sha256": digest_file(train_path),
        "dev_sha256": digest_file(dev_path),
        "heldout_test_sha256": digest_file(test_path),
        "manifest_sha256": digest_file(manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("test", type=Path)
    parser.add_argument("manifest", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(verify(
        arguments.cards, arguments.pairs, arguments.train, arguments.dev,
        arguments.test, arguments.manifest,
    ), indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
