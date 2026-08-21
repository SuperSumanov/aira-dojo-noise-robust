"""Build a leakage-free train/dev split over pair-graph connected components."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROTOCOL = "pair-graph-component-train-dev-split-v1"
SEED = 20260821
TARGET_NUMERATOR = 1
TARGET_DENOMINATOR = 10
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "pairs": ("bd6551dfce85d83f9f59716a31a9d7ab88605d6a21f51b41eb28177a952f47d0", 2552829),
}


class SplitError(RuntimeError):
    """Raised when a component split invariant is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_lines(rows: list[dict[str, Any]]) -> bytes:
    return "".join(canonical_json(row) + "\n" for row in rows).encode()


def write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def verify_fixed(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    if path.stat().st_size != expected_bytes or sha256_file(path) != expected_hash:
        raise SplitError(f"{role} identity mismatch")


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise SplitError(f"blank pair row at {line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise SplitError(f"non-object pair row at {line_number}")
            rows.append(row)
    return rows


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        task, parent = row["task"], row["parent"]
        left, right = sorted((row["better"], row["worse"]))
    except (KeyError, TypeError, ValueError) as error:
        raise SplitError("invalid pair identity") from error
    if not all(isinstance(value, str) and value for value in (task, parent, left, right)):
        raise SplitError("empty pair identity")
    if left == right:
        raise SplitError("self pair")
    return task, parent, left, right


def load_card_maps(path: Path, needed: set[str]) -> tuple[dict[str, str], dict[str, str], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise SplitError("cards root is not grouped")
    run_of: dict[str, str] = {}
    task_of: dict[str, str] = {}
    task_by_run: dict[str, str] = {}
    seen: set[str] = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not isinstance(cards, list):
            raise SplitError("invalid grouped-card entry")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str):
                raise SplitError("invalid card")
            card_id = card["id"]
            if card_id in seen:
                raise SplitError("duplicate card id")
            seen.add(card_id)
            if card_id not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            if not isinstance(task, str) or not task:
                raise SplitError("needed card lacks task")
            previous_task = task_by_run.setdefault(run_id, task)
            if previous_task != task:
                raise SplitError("physical run contains needed endpoints from multiple tasks")
            run_of[card_id] = run_id
            task_of[card_id] = task
    if set(run_of) != needed:
        raise SplitError("pair endpoint missing from cards")
    return run_of, task_of, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


class DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, value: str) -> None:
        self.parent.setdefault(value, value)

    def find(self, value: str) -> str:
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            next_value = self.parent[value]
            self.parent[value] = root
            value = next_value
        return root

    def union(self, left: str, right: str) -> None:
        self.add(left)
        self.add(right)
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        smaller, larger = sorted((left_root, right_root))
        self.parent[larger] = smaller


def component_digest(task: str, runs: tuple[str, ...]) -> str:
    payload = canonical_json([SEED, task, list(runs)]).encode()
    return hashlib.sha256(payload).hexdigest()


def choose_dev_indices(weights: list[int], digests: list[str]) -> tuple[int, ...]:
    if len(weights) < 2:
        return ()
    states: dict[int, tuple[int, ...]] = {0: ()}
    for index, weight in enumerate(weights):
        updated = dict(states)
        for total, selected in states.items():
            candidate_total = total + weight
            candidate = selected + (index,)
            if candidate_total not in updated or tuple(digests[i] for i in candidate) < tuple(
                digests[i] for i in updated[candidate_total]
            ):
                updated[candidate_total] = candidate
        states = updated
    all_indices = tuple(range(len(weights)))
    candidates = [
        (total, selected) for total, selected in states.items()
        if selected and selected != all_indices
    ]
    if not candidates:
        raise SplitError("task with multiple components has no proper dev subset")
    task_pairs = sum(weights)
    _, selected = min(
        candidates,
        key=lambda item: (
            abs(TARGET_DENOMINATOR * item[0] - TARGET_NUMERATOR * task_pairs),
            item[0],
            tuple(digests[i] for i in item[1]),
        ),
    )
    return selected


def build_components(
    train_rows: list[dict[str, Any]],
    run_of: dict[str, str],
    task_of: dict[str, str],
) -> tuple[dict[tuple[str, str, str, str], str], dict[str, Any]]:
    dsu_by_task: dict[str, DisjointSet] = defaultdict(DisjointSet)
    keys: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in train_rows:
        key = pair_key(row)
        if key in seen:
            raise SplitError("duplicate outer-train pair")
        seen.add(key)
        task, _, left, right = key
        if task_of[left] != task or task_of[right] != task:
            raise SplitError("pair/card task mismatch")
        left_run, right_run = run_of[left], run_of[right]
        dsu_by_task[task].union(left_run, right_run)
        keys.append(key)

    runs_by_root: dict[tuple[str, str], set[str]] = defaultdict(set)
    for task, dsu in dsu_by_task.items():
        for run_id in dsu.parent:
            runs_by_root[(task, dsu.find(run_id))].add(run_id)

    key_root: dict[tuple[str, str, str, str], tuple[str, str]] = {}
    pair_count_by_root: Counter[tuple[str, str]] = Counter()
    for key in keys:
        task, _, left, right = key
        root = dsu_by_task[task].find(run_of[left])
        if root != dsu_by_task[task].find(run_of[right]):
            raise SplitError("pair endpoints cross components")
        key_root[key] = (task, root)
        pair_count_by_root[(task, root)] += 1

    dev_roots: set[tuple[str, str]] = set()
    task_receipts: dict[str, Any] = {}
    roots_by_task: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for task_root in runs_by_root:
        roots_by_task[task_root[0]].append(task_root)
    component_id: dict[tuple[str, str], str] = {}
    for task in sorted(roots_by_task):
        components = []
        for task_root in roots_by_task[task]:
            runs = tuple(sorted(runs_by_root[task_root]))
            digest = component_digest(task, runs)
            component_id[task_root] = digest
            components.append((digest, task_root, pair_count_by_root[task_root], len(runs)))
        components.sort(key=lambda item: item[0])
        weights = [item[2] for item in components]
        digests = [item[0] for item in components]
        selected_indices = choose_dev_indices(weights, digests)
        selected = {components[index][1] for index in selected_indices}
        dev_roots.update(selected)
        task_receipts[task] = {
            "components": len(components),
            "pairs": sum(weights),
            "dev_components": len(selected),
            "dev_pairs": sum(pair_count_by_root[root] for root in selected),
            "train_components": len(components) - len(selected),
            "component_pair_weights": [item[2] for item in components],
            "component_run_counts": [item[3] for item in components],
            "component_ids_sha256": hashlib.sha256(canonical_json(digests).encode()).hexdigest(),
            "dev_component_ids_sha256": hashlib.sha256(
                canonical_json(sorted(component_id[root] for root in selected)).encode()
            ).hexdigest(),
        }

    split_by_key = {
        key: "dev" if key_root[key] in dev_roots else "train"
        for key in keys
    }
    component_by_key = {key: component_id[key_root[key]] for key in keys}
    return component_by_key, {
        "split_by_key": split_by_key,
        "task_receipts": task_receipts,
        "components": len(runs_by_root),
        "dev_components": len(dev_roots),
    }


def build_split(
    cards_path: Path,
    pairs_path: Path,
    train_output: Path,
    dev_output: Path,
    test_output: Path,
    manifest_output: Path,
    *,
    enforce_fixed_identity: bool = True,
) -> dict[str, Any]:
    outputs = (train_output, dev_output, test_output, manifest_output)
    if len({path.resolve() for path in outputs}) != len(outputs) or any(path.exists() for path in outputs):
        raise SplitError("outputs must be distinct and absent")
    if enforce_fixed_identity:
        verify_fixed(cards_path, "cards")
        verify_fixed(pairs_path, "pairs")
    rows = read_rows(pairs_path)
    keys = [pair_key(row) for row in rows]
    if len(keys) != len(set(keys)):
        raise SplitError("duplicate unordered pair")
    train_rows = [row for row in rows if row.get("intask_split") == "train"]
    test_rows = [row for row in rows if row.get("intask_split") == "test"]
    if len(train_rows) + len(test_rows) != len(rows):
        raise SplitError("unsupported outer split")
    needed = {endpoint for key in keys for endpoint in key[2:]}
    run_of, task_of, card_inventory = load_card_maps(cards_path, needed)
    component_by_key, component_receipt = build_components(train_rows, run_of, task_of)
    split_by_key = component_receipt.pop("split_by_key")

    derived: dict[str, list[dict[str, Any]]] = {"train": [], "dev": []}
    for row in train_rows:
        key = pair_key(row)
        split = split_by_key[key]
        output_row = dict(row)
        output_row["outer_intask_split"] = "train"
        output_row["intask_split"] = split
        output_row["train_dev_protocol"] = PROTOCOL
        output_row["train_dev_seed"] = SEED
        output_row["train_dev_target_numerator"] = TARGET_NUMERATOR
        output_row["train_dev_target_denominator"] = TARGET_DENOMINATOR
        output_row["pair_component_id"] = component_by_key[key]
        derived[split].append(output_row)
    if not derived["train"] or not derived["dev"] or not test_rows:
        raise SplitError("component split produced an empty pool")

    train_bytes = canonical_lines(derived["train"])
    dev_bytes = canonical_lines(derived["dev"])
    test_bytes = canonical_lines(test_rows)
    train_endpoints = {endpoint for row in derived["train"] for endpoint in pair_key(row)[2:]}
    dev_endpoints = {endpoint for row in derived["dev"] for endpoint in pair_key(row)[2:]}
    test_endpoints = {endpoint for row in test_rows for endpoint in pair_key(row)[2:]}
    train_runs = {run_of[endpoint] for endpoint in train_endpoints}
    dev_runs = {run_of[endpoint] for endpoint in dev_endpoints}
    test_runs = {run_of[endpoint] for endpoint in test_endpoints}
    if train_endpoints & dev_endpoints or train_runs & dev_runs:
        raise SplitError("train/dev leakage")
    if (train_endpoints | dev_endpoints) & test_endpoints or (train_runs | dev_runs) & test_runs:
        raise SplitError("outer-test leakage")

    manifest = {
        "protocol": PROTOCOL,
        "status": "PAIR_COMPONENT_SPLIT_VERIFIED_BY_PRODUCER",
        "seed": SEED,
        "target_numerator": TARGET_NUMERATOR,
        "target_denominator": TARGET_DENOMINATOR,
        "cards_sha256": sha256_file(cards_path),
        "source_pairs_sha256": sha256_file(pairs_path),
        "train_pairs_sha256": hashlib.sha256(train_bytes).hexdigest(),
        "dev_pairs_sha256": hashlib.sha256(dev_bytes).hexdigest(),
        "heldout_test_pairs_sha256": hashlib.sha256(test_bytes).hexdigest(),
        "source_train_pairs": len(train_rows),
        "source_test_pairs": len(test_rows),
        "train_pairs": len(derived["train"]),
        "dev_pairs": len(derived["dev"]),
        "heldout_test_pairs": len(test_rows),
        "dropped_source_train_pairs": 0,
        "train_runs": len(train_runs),
        "dev_runs": len(dev_runs),
        "heldout_test_runs": len(test_runs),
        "train_dev_card_overlap": 0,
        "train_dev_run_overlap": 0,
        "outer_test_card_overlap": 0,
        "outer_test_run_overlap": 0,
        "card_inventory": card_inventory,
        **component_receipt,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    write_exclusive(train_output, train_bytes)
    write_exclusive(dev_output, dev_bytes)
    write_exclusive(test_output, test_bytes)
    write_exclusive(manifest_output, manifest_bytes)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("train_output", type=Path)
    parser.add_argument("dev_output", type=Path)
    parser.add_argument("test_output", type=Path)
    parser.add_argument("manifest_output", type=Path)
    arguments = parser.parse_args()
    manifest = build_split(
        arguments.cards, arguments.pairs, arguments.train_output, arguments.dev_output,
        arguments.test_output, arguments.manifest_output,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
