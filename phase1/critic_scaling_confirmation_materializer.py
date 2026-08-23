"""Fail-closed adapters for the clean critic-scaling confirmation contract.

This module has three deliberately separate operations:

* ``truth`` converts an already frozen, dedicated test-pair file plus immutable
  Cards into the canonical truth JSONL that is hashed into the pre-test lock;
* ``model-prediction`` converts one completed upstream one-shot evaluator
  receipt into canonical pair predictions and a derived confirmation ledger;
* ``bundle`` assembles already materialized artifacts without copying or
  changing any result-bearing row.

Nothing here trains or scores a model.  Running ``truth`` does open labels, so
the implementation is tested only on synthetic data until truth access is
separately authorized.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


TRUTH_RECEIPT_PROTOCOL = "critic-scaling-truth-materialization-v1"
MODEL_LEDGER_PROTOCOL = "critic-scaling-derived-one-shot-ledger-v1"
CHECKPOINT_MANIFEST_PROTOCOL = "critic-scaling-checkpoint-manifest-v1"
BUNDLE_INPUTS_PROTOCOL = "critic-scaling-confirmation-bundle-inputs-v1"
BUNDLE_PROTOCOL = "critic-scaling-confirmation-bundle-v1"
LOCK_PROTOCOL = "critic-scaling-confirmation-lock-v1"
ONE_SHOT_PROTOCOL = "rm-one-shot-test-v1"
HEX40_OR_64 = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
HEX64 = re.compile(r"[0-9a-f]{64}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{20,}|"
    rb"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class MaterializationError(RuntimeError):
    """Raised when an immutable identity or receipt invariant fails."""


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    truth = subparsers.add_parser("truth")
    truth.add_argument("--pairs", type=Path, required=True)
    truth.add_argument("--cards", type=Path, required=True)
    truth.add_argument("--expected-pairs-sha256", required=True)
    truth.add_argument("--expected-cards-sha256", required=True)
    truth.add_argument("--source-commit", required=True)
    truth.add_argument("--output", type=Path, required=True)
    truth.add_argument("--receipt", type=Path, required=True)

    model = subparsers.add_parser("model-prediction")
    model.add_argument("--truth", type=Path, required=True)
    model.add_argument("--expected-truth-sha256", required=True)
    model.add_argument("--lock", type=Path, required=True)
    model.add_argument("--expected-lock-sha256", required=True)
    model.add_argument("--one-shot-output", type=Path, required=True)
    model.add_argument("--expected-one-shot-output-sha256", required=True)
    model.add_argument("--one-shot-ledger", type=Path, required=True)
    model.add_argument("--expected-one-shot-ledger-sha256", required=True)
    model.add_argument("--checkpoint-manifest", type=Path, required=True)
    model.add_argument("--checkpoint-manifest-sha256", required=True)
    model.add_argument("--output", type=Path, required=True)
    model.add_argument("--ledger", type=Path, required=True)

    bundle = subparsers.add_parser("bundle")
    bundle.add_argument("--contract", type=Path, required=True)
    bundle.add_argument("--expected-contract-sha256", required=True)
    bundle.add_argument("--lock", type=Path, required=True)
    bundle.add_argument("--expected-lock-sha256", required=True)
    bundle.add_argument("--root", type=Path, required=True)
    bundle.add_argument("--inputs", type=Path, required=True)
    bundle.add_argument("--expected-inputs-sha256", required=True)
    bundle.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def compact_line(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_identity(path: Path) -> str:
    """Hash a precommittable absolute path without exposing it in the lock."""
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()


def require_digest(value: Any, label: str, *, git_ok: bool = False) -> str:
    pattern = HEX40_OR_64 if git_ok else HEX64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise MaterializationError(f"{label} is not a lowercase digest")
    return value


def locked_file(path: Path, expected: Any, label: str) -> str:
    digest = require_digest(expected, f"{label} expected SHA256")
    if path.is_symlink() or not path.is_file():
        raise MaterializationError(f"{label} must be a regular non-symlink file")
    observed = sha256_file(path)
    if observed != digest:
        raise MaterializationError(f"{label} SHA256 mismatch")
    return observed


def credential_scan(path: Path, label: str) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise MaterializationError(f"credential-shaped bytes refused in {label}")
            overlap = payload[-256:]


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MaterializationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise MaterializationError(f"{label} root is not an object")
    return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    raise MaterializationError(f"blank row in {label}:{line_number}")
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise MaterializationError(f"non-object row in {label}:{line_number}")
                rows.append(row)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        if isinstance(error, MaterializationError):
            raise
        raise MaterializationError(f"cannot read {label}") from error
    if not rows:
        raise MaterializationError(f"{label} is empty")
    return rows


def write_exclusive(path: Path, payload: bytes, label: str) -> None:
    if path.exists() or path.is_symlink():
        raise MaterializationError(f"refusing to overwrite {label}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as error:
        raise MaterializationError(f"refusing to overwrite {label}") from error


def write_jsonl_exclusive(path: Path, rows: Iterable[Mapping[str, Any]], label: str) -> None:
    payload = "".join(compact_line(dict(row)) for row in rows).encode("utf-8")
    write_exclusive(path, payload, label)


def required_text(row: Mapping[str, Any], field: str, where: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise MaterializationError(f"invalid {field} in {where}")
    return value


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MaterializationError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise MaterializationError(f"{label} is non-finite")
    return result


def task_name(card: Mapping[str, Any], where: str) -> str:
    task = card.get("task")
    if isinstance(task, dict):
        return required_text(task, "name", where)
    if isinstance(task, str) and task:
        return task
    raise MaterializationError(f"invalid task in {where}")


def card_grade(card: Mapping[str, Any], where: str) -> float | None:
    label = card.get("label")
    if not isinstance(label, dict) or label.get("graded") is None:
        return None
    return finite_number(label.get("graded"), f"grade in {where}")


def parse_cards_payload(path: Path) -> list[tuple[str | None, dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    records: list[tuple[str | None, dict[str, Any]]] = []
    if isinstance(value, dict) and all(isinstance(cards, list) for cards in value.values()):
        for run_id in sorted(value):
            if not isinstance(run_id, str) or not run_id:
                raise MaterializationError("invalid grouped Cards run ID")
            for card in value[run_id]:
                if not isinstance(card, dict):
                    raise MaterializationError("grouped Cards contains a non-object")
                records.append((run_id, card))
        return records
    if isinstance(value, list):
        for card in value:
            if not isinstance(card, dict):
                raise MaterializationError("Cards array contains a non-object")
            records.append((None, card))
        return records
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            raise MaterializationError(f"blank row in Cards:{line_number}")
        try:
            card = json.loads(line)
        except json.JSONDecodeError as error:
            raise MaterializationError(f"invalid Cards JSON at line {line_number}") from error
        if not isinstance(card, dict):
            raise MaterializationError(f"non-object Cards row at line {line_number}")
        records.append((None, card))
    return records


def load_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for index, (group_run, source) in enumerate(parse_cards_payload(path), 1):
        where = f"Card {index}"
        card_id = required_text(source, "id", where)
        if card_id in cards:
            raise MaterializationError(f"duplicate Card ID {card_id!r}")
        declared_run = source.get("run_id")
        if declared_run is not None and (not isinstance(declared_run, str) or not declared_run):
            raise MaterializationError(f"invalid run_id in {where}")
        if group_run is not None and declared_run is not None and group_run != declared_run:
            raise MaterializationError(f"group/run mismatch in {where}")
        run_id = group_run or declared_run
        if not isinstance(run_id, str) or not run_id:
            raise MaterializationError(f"missing physical run in {where}")
        lineage = source.get("lineage")
        if not isinstance(lineage, dict):
            raise MaterializationError(f"invalid lineage in {where}")
        parent = lineage.get("parent_id")
        if parent is not None and (not isinstance(parent, str) or not parent):
            raise MaterializationError(f"invalid parent_id in {where}")
        cards[card_id] = {
            "task": task_name(source, where),
            "run_id": run_id,
            "parent_id": parent,
            "grade": card_grade(source, where),
        }
    if not cards:
        raise MaterializationError("Cards input is empty")
    return cards


def component_digest(
    task: str, semantics: str, parent: str, parent_run: str, endpoints: Sequence[str]
) -> str:
    payload = [
        "critic-scaling-component-v1",
        task,
        semantics,
        parent,
        parent_run,
        sorted(endpoints),
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def truth_pair_id(row: Mapping[str, Any]) -> str:
    payload = [
        row["task"],
        row["pair_semantics"],
        row["parent_id"],
        row["comparison_component_id"],
        row["better_id"],
        row["worse_id"],
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def connected_components(edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = collections.defaultdict(set)
    for left, right in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    remaining = set(adjacency)
    components: list[list[str]] = []
    while remaining:
        start = min(remaining)
        reached = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbour in sorted(adjacency[node]):
                if neighbour not in reached:
                    reached.add(neighbour)
                    stack.append(neighbour)
        components.append(sorted(reached))
        remaining -= reached
    return sorted(components)


def build_truth_rows(
    pair_rows: Sequence[dict[str, Any]], cards: Mapping[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    task_signs: dict[str, int] = {}
    unordered: set[tuple[str, str, str, frozenset[str]]] = set()
    budget_values: set[str] = set()
    groups: dict[tuple[str, str, str, str], list[tuple[str, str]]] = collections.defaultdict(list)

    for index, source in enumerate(pair_rows, 1):
        where = f"pair row {index}"
        if source.get("intask_split") != "test":
            raise MaterializationError(f"{where} is not dedicated test")
        task = required_text(source, "task", where)
        semantics = required_text(source, "pair_semantics", where)
        if semantics != "canonical_raw_sibling":
            raise MaterializationError(f"{where} is not canonical_raw_sibling")
        parent = source.get("parent")
        parent_alias = source.get("parent_id")
        if parent is None:
            parent = parent_alias
        elif parent_alias is not None and parent_alias != parent:
            raise MaterializationError(f"{where} has conflicting parent identities")
        if not isinstance(parent, str) or not parent:
            raise MaterializationError(f"{where} lacks a parent")
        better = required_text(source, "better", where)
        worse = required_text(source, "worse", where)
        if better == worse or better not in cards or worse not in cards:
            raise MaterializationError(f"{where} has invalid endpoints")
        better_card, worse_card = cards[better], cards[worse]
        if better_card["task"] != task or worse_card["task"] != task:
            raise MaterializationError(f"{where} task disagrees with Cards")
        if better_card["parent_id"] != parent or worse_card["parent_id"] != parent:
            raise MaterializationError(f"{where} is not a raw sibling edge")
        endpoint_runs = source.get("endpoint_run_ids")
        expected_runs = [better_card["run_id"], worse_card["run_id"]]
        if endpoint_runs != expected_runs:
            raise MaterializationError(f"{where} endpoint run receipt mismatch")
        parent_run = required_text(source, "parent_run_id", where)
        if not (parent_run == expected_runs[0] == expected_runs[1]):
            raise MaterializationError(f"{where} crosses physical runs")
        if parent in cards:
            parent_card = cards[parent]
            if parent_card["run_id"] != parent_run or parent_card["task"] != task:
                raise MaterializationError(f"{where} parent metadata mismatch")
        better_grade = better_card["grade"]
        worse_grade = worse_card["grade"]
        if better_grade is None or worse_grade is None or better_grade == worse_grade:
            raise MaterializationError(f"{where} lacks a strict finite utility gap")
        identity = (task, semantics, parent, frozenset((better, worse)))
        if identity in unordered:
            raise MaterializationError(f"duplicate or reversed edge in {where}")
        unordered.add(identity)
        sign = 1 if better_grade > worse_grade else -1
        previous_sign = task_signs.setdefault(task, sign)
        if previous_sign != sign:
            raise MaterializationError(f"task {task!r} has inconsistent grade direction")
        budget_values.add(compact_line(source.get("budget")).strip())
        group = (task, semantics, parent, parent_run)
        groups[group].append((better, worse))
        parsed.append(
            {
                "task": task,
                "pair_semantics": semantics,
                "parent_id": parent,
                "parent_run_id": parent_run,
                "better_id": better,
                "worse_id": worse,
                "better_run_id": expected_runs[0],
                "worse_run_id": expected_runs[1],
                "better_utility": sign * better_grade,
                "worse_utility": sign * worse_grade,
                "_group": group,
            }
        )
    if len(budget_values) != 1:
        raise MaterializationError("pair identity omits budget, so exactly one budget is required")

    endpoint_components: dict[tuple[tuple[str, str, str, str], str], str] = {}
    for group in sorted(groups):
        for endpoints in connected_components(groups[group]):
            component_id = component_digest(*group, endpoints)
            for endpoint in endpoints:
                endpoint_components[(group, endpoint)] = component_id

    output: list[dict[str, Any]] = []
    for source in parsed:
        group = source.pop("_group")
        better_component = endpoint_components[(group, source["better_id"])]
        worse_component = endpoint_components[(group, source["worse_id"])]
        if better_component != worse_component:
            raise MaterializationError("edge endpoints were split across components")
        row = {"split": "test", "comparison_component_id": better_component, **source}
        if not row["better_utility"] > row["worse_utility"]:
            raise MaterializationError("oriented utility is not strictly positive")
        row["pair_id"] = truth_pair_id(row)
        output.append(row)
    output.sort(
        key=lambda row: (
            row["task"], row["parent_id"], row["comparison_component_id"],
            row["better_id"], row["worse_id"],
        )
    )
    task_counts = collections.Counter(row["task"] for row in output)
    components = {row["comparison_component_id"] for row in output}
    metadata = {
        "pairs": len(output),
        "tasks": len(task_counts),
        "components": len(components),
        "dominant_task_pair_share": max(task_counts.values()) / len(output),
        "budget_canonical_json": next(iter(budget_values)),
        "task_grade_direction": {
            task: "higher_raw_grade_is_better" if sign == 1 else "lower_raw_grade_is_better"
            for task, sign in sorted(task_signs.items())
        },
    }
    return output, metadata


def materialize_truth(args: argparse.Namespace) -> int:
    pairs_sha = locked_file(args.pairs, args.expected_pairs_sha256, "frozen pairs")
    cards_sha = locked_file(args.cards, args.expected_cards_sha256, "frozen Cards")
    require_digest(args.source_commit, "source commit", git_ok=True)
    credential_scan(args.pairs, "frozen pairs")
    credential_scan(args.cards, "frozen Cards")
    if args.output.resolve() == args.receipt.resolve():
        raise MaterializationError("truth output and receipt must differ")
    if args.output.exists() or args.receipt.exists():
        raise MaterializationError("truth output or receipt already exists")
    rows, support = build_truth_rows(read_jsonl(args.pairs, "frozen pairs"), load_cards(args.cards))
    write_jsonl_exclusive(args.output, rows, "truth output")
    receipt = {
        "protocol": TRUTH_RECEIPT_PROTOCOL,
        "status": "COMPLETE",
        "source_commit": args.source_commit,
        "inputs": {"pairs_sha256": pairs_sha, "cards_sha256": cards_sha},
        "truth": {"sha256": sha256_file(args.output), "rows": len(rows)},
        "support": support,
        "access_attestation": {
            "truth_labels_opened": True,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
        },
    }
    write_exclusive(args.receipt, canonical_bytes(receipt), "truth receipt")
    return 0


def load_truth(path: Path) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str, str, str], dict[str, Any]]]:
    rows = read_jsonl(path, "truth")
    index: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    pair_ids: set[str] = set()
    for number, row in enumerate(rows, 1):
        where = f"truth row {number}"
        for field in (
            "pair_id", "task", "pair_semantics", "parent_id", "parent_run_id",
            "comparison_component_id", "better_id", "worse_id", "better_run_id",
            "worse_run_id",
        ):
            required_text(row, field, where)
        if row.get("split") != "test" or row["pair_id"] != truth_pair_id(row):
            raise MaterializationError(f"{where} has invalid canonical identity")
        if row["pair_id"] in pair_ids:
            raise MaterializationError("duplicate pair_id in truth")
        pair_ids.add(row["pair_id"])
        key = (
            row["task"], row["pair_semantics"], row["parent_id"],
            row["better_id"], row["worse_id"],
        )
        if key in index:
            raise MaterializationError("duplicate oriented identity in truth")
        index[key] = row
    return rows, index


def validate_lock(lock: Mapping[str, Any], lock_sha: str, truth_sha: str) -> dict[str, Any]:
    if lock.get("protocol") != LOCK_PROTOCOL or lock.get("status") != "LOCKED_BEFORE_TEST_ACCESS":
        raise MaterializationError("invalid pre-test lock")
    dataset = lock.get("dataset")
    if not isinstance(dataset, dict) or dataset.get("truth_sha256") != truth_sha:
        raise MaterializationError("lock does not bind this truth")
    require_digest(lock_sha, "lock SHA256")
    return dict(lock)


def normalize_model_prediction(args: argparse.Namespace) -> int:
    truth_sha = locked_file(args.truth, args.expected_truth_sha256, "truth")
    lock_sha = locked_file(args.lock, args.expected_lock_sha256, "pre-test lock")
    source_output_sha = locked_file(
        args.one_shot_output, args.expected_one_shot_output_sha256, "one-shot output"
    )
    source_ledger_sha = locked_file(
        args.one_shot_ledger, args.expected_one_shot_ledger_sha256, "one-shot ledger"
    )
    checkpoint_sha = require_digest(
        args.checkpoint_manifest_sha256, "checkpoint manifest SHA256"
    )
    locked_file(args.checkpoint_manifest, checkpoint_sha, "checkpoint manifest")
    for path, label in (
        (args.truth, "truth"),
        (args.lock, "pre-test lock"),
        (args.one_shot_output, "one-shot output"),
        (args.one_shot_ledger, "one-shot ledger"),
        (args.checkpoint_manifest, "checkpoint manifest"),
    ):
        credential_scan(path, label)
    if args.output.resolve() == args.ledger.resolve():
        raise MaterializationError("prediction output and derived ledger must differ")
    if args.output.exists() or args.ledger.exists():
        raise MaterializationError("prediction output or derived ledger already exists")

    lock = validate_lock(read_object(args.lock, "pre-test lock"), lock_sha, truth_sha)
    locked_runs = lock.get("runs")
    if not isinstance(locked_runs, list):
        raise MaterializationError("lock runs are absent")
    matching_runs = [
        row for row in locked_runs
        if isinstance(row, dict) and row.get("checkpoint_manifest_sha256") == checkpoint_sha
    ]
    if len(matching_runs) != 1:
        raise MaterializationError("checkpoint manifest does not identify exactly one locked run")
    locked_run = matching_runs[0]
    if locked_run.get("one_shot_output_path_sha256") != path_identity(args.one_shot_output):
        raise MaterializationError("one-shot output path was not pre-locked")
    if locked_run.get("one_shot_ledger_path_sha256") != path_identity(args.one_shot_ledger):
        raise MaterializationError("one-shot ledger path was not pre-locked")

    checkpoint_manifest = read_object(args.checkpoint_manifest, "checkpoint manifest")
    if (
        checkpoint_manifest.get("protocol") != CHECKPOINT_MANIFEST_PROTOCOL
        or checkpoint_manifest.get("status") != "LOCKED_BEFORE_TEST_ACCESS"
    ):
        raise MaterializationError("invalid checkpoint manifest")
    if (
        finite_number(checkpoint_manifest.get("model_size_b"), "manifest model size")
        != finite_number(locked_run.get("model_size_b"), "locked model size")
        or checkpoint_manifest.get("seed") != locked_run.get("seed")
    ):
        raise MaterializationError("checkpoint manifest run identity differs from lock")
    checkpoint_artifacts = checkpoint_manifest.get("artifacts")
    if not isinstance(checkpoint_artifacts, dict):
        raise MaterializationError("checkpoint manifest lacks artifacts")

    source_ledger = read_object(args.one_shot_ledger, "one-shot ledger")
    if source_ledger.get("protocol") != ONE_SHOT_PROTOCOL or source_ledger.get("status") != "COMPLETE":
        raise MaterializationError("one-shot ledger is not complete")
    expected_artifacts = source_ledger.get("expected_artifacts")
    observed_artifacts = source_ledger.get("observed_artifacts")
    if not isinstance(expected_artifacts, dict) or not isinstance(observed_artifacts, dict):
        raise MaterializationError("one-shot ledger lacks artifact receipts")
    for name in ("pairs", "cards", "model.safetensors"):
        digest = expected_artifacts.get(name)
        require_digest(digest, f"one-shot expected {name}")
        if observed_artifacts.get(name) != digest:
            raise MaterializationError(f"one-shot observed {name} differs")
    dataset = lock["dataset"]
    if expected_artifacts["pairs"] != dataset.get("pairs_sha256"):
        raise MaterializationError("one-shot pairs differ from truth source")
    if expected_artifacts["cards"] != dataset.get("cards_sha256"):
        raise MaterializationError("one-shot Cards differ from truth source")
    for name, digest in expected_artifacts.items():
        if name in {"pairs", "cards"}:
            continue
        require_digest(digest, f"one-shot expected {name}")
        if checkpoint_artifacts.get(name) != digest:
            raise MaterializationError(f"one-shot {name} differs from checkpoint manifest")
    result_receipt = source_ledger.get("result")
    if not isinstance(result_receipt, dict) or result_receipt.get("output_sha256") != source_output_sha:
        raise MaterializationError("one-shot ledger does not bind its output")
    if source_ledger.get("output") != str(args.one_shot_output.resolve()):
        raise MaterializationError("one-shot ledger output path differs")

    source_output = read_object(args.one_shot_output, "one-shot output")
    if source_output.get("protocol") != ONE_SHOT_PROTOCOL or source_output.get("split") != "test":
        raise MaterializationError("one-shot output protocol or split is invalid")
    if source_output.get("artifacts") != observed_artifacts:
        raise MaterializationError("one-shot output artifacts differ from ledger")
    predictions = source_output.get("pair_predictions")
    if not isinstance(predictions, list) or not predictions:
        raise MaterializationError("one-shot output lacks pair predictions")
    truth_rows, truth_index = load_truth(args.truth)
    if source_output.get("n_pairs") != len(predictions) or len(predictions) != len(truth_rows):
        raise MaterializationError("one-shot pair count differs from truth")
    if result_receipt.get("n_pairs") != len(predictions):
        raise MaterializationError("one-shot ledger pair count differs")

    normalized: list[dict[str, Any]] = []
    seen_indices: set[int] = set()
    seen_pairs: set[str] = set()
    endpoint_scores: dict[str, float] = {}
    for number, source in enumerate(predictions, 1):
        where = f"one-shot prediction {number}"
        if not isinstance(source, dict):
            raise MaterializationError(f"{where} is not an object")
        pair_index = source.get("pair_index")
        if isinstance(pair_index, bool) or not isinstance(pair_index, int) or pair_index < 0:
            raise MaterializationError(f"{where} has invalid pair_index")
        if pair_index in seen_indices:
            raise MaterializationError("duplicate one-shot pair_index")
        seen_indices.add(pair_index)
        key = (
            required_text(source, "task", where),
            required_text(source, "pair_semantics", where),
            required_text(source, "parent", where),
            required_text(source, "better", where),
            required_text(source, "worse", where),
        )
        truth_row = truth_index.get(key)
        if truth_row is None:
            raise MaterializationError(f"{where} is absent or reversed relative to truth")
        if source.get("parent_run_id") != truth_row["parent_run_id"]:
            raise MaterializationError(f"{where} parent run mismatch")
        if source.get("endpoint_run_ids") != [
            truth_row["better_run_id"], truth_row["worse_run_id"]
        ]:
            raise MaterializationError(f"{where} endpoint run mismatch")
        better_score = finite_number(source.get("better_score"), f"{where} better_score")
        worse_score = finite_number(source.get("worse_score"), f"{where} worse_score")
        margin = finite_number(source.get("margin"), f"{where} margin")
        if not math.isclose(margin, better_score - worse_score, rel_tol=0.0, abs_tol=1e-9):
            raise MaterializationError(f"{where} margin mismatch")
        for endpoint, score in (
            (truth_row["better_id"], better_score),
            (truth_row["worse_id"], worse_score),
        ):
            previous = endpoint_scores.setdefault(endpoint, score)
            if not math.isclose(previous, score, rel_tol=0.0, abs_tol=1e-9):
                raise MaterializationError(f"{where} endpoint score is inconsistent")
        pair_id = truth_row["pair_id"]
        if pair_id in seen_pairs:
            raise MaterializationError("duplicate one-shot pair identity")
        seen_pairs.add(pair_id)
        normalized.append(
            {
                "pair_id": pair_id,
                "better_score": better_score,
                "worse_score": worse_score,
                "margin": margin,
            }
        )
    if seen_indices != set(range(len(predictions))) or seen_pairs != {row["pair_id"] for row in truth_rows}:
        raise MaterializationError("one-shot prediction coverage is not exact")
    normalized.sort(key=lambda row: row["pair_id"])
    write_jsonl_exclusive(args.output, normalized, "normalized predictions")
    prediction_sha = sha256_file(args.output)
    derived_ledger = {
        "protocol": MODEL_LEDGER_PROTOCOL,
        "status": "COMPLETE",
        "test_attempts": 1,
        "lock_sha256": lock_sha,
        "truth_sha256": truth_sha,
        "prediction_sha256": prediction_sha,
        "checkpoint_manifest_sha256": checkpoint_sha,
        "locked_run": {
            "model_size_b": locked_run.get("model_size_b"),
            "seed": locked_run.get("seed"),
        },
        "source_one_shot": {
            "ledger_sha256": source_ledger_sha,
            "output_sha256": source_output_sha,
            "ledger_path_sha256": path_identity(args.one_shot_ledger),
            "output_path_sha256": path_identity(args.one_shot_output),
            "expected_artifacts": expected_artifacts,
        },
    }
    write_exclusive(args.ledger, canonical_bytes(derived_ledger), "derived ledger")
    return 0


def safe_member(root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise MaterializationError(f"{label} path must be relative")
    root_resolved = root.resolve()
    cursor = root
    for part in Path(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise MaterializationError(f"{label} path contains a symlink")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as error:
        raise MaterializationError(f"{label} escapes bundle root") from error
    if not candidate.is_file():
        raise MaterializationError(f"{label} is absent")
    return candidate


def artifact_spec(root: Path, relative: Any, label: str) -> dict[str, Any]:
    path = safe_member(root, relative, label)
    rows = len(read_jsonl(path, label))
    return {"path": str(Path(relative).as_posix()), "sha256": sha256_file(path), "rows": rows}


def ledger_spec(
    root: Path,
    relative: Any,
    label: str,
    *,
    lock_sha: str,
    truth_sha: str,
    prediction_sha: str,
    checkpoint_sha: str | None,
) -> dict[str, str]:
    path = safe_member(root, relative, label)
    ledger = read_object(path, label)
    expected = {
        "status": "COMPLETE",
        "test_attempts": 1,
        "lock_sha256": lock_sha,
        "truth_sha256": truth_sha,
        "prediction_sha256": prediction_sha,
    }
    if any(ledger.get(key) != value for key, value in expected.items()):
        raise MaterializationError(f"{label} disagrees with artifacts")
    if checkpoint_sha is not None and ledger.get("checkpoint_manifest_sha256") != checkpoint_sha:
        raise MaterializationError(f"{label} checkpoint mismatch")
    return {"path": str(Path(relative).as_posix()), "sha256": sha256_file(path)}


def assemble_bundle(args: argparse.Namespace) -> int:
    contract_sha = locked_file(args.contract, args.expected_contract_sha256, "contract")
    lock_sha = locked_file(args.lock, args.expected_lock_sha256, "pre-test lock")
    inputs_sha = locked_file(args.inputs, args.expected_inputs_sha256, "bundle inputs")
    del inputs_sha
    for path, label in (
        (args.contract, "contract"), (args.lock, "pre-test lock"), (args.inputs, "bundle inputs")
    ):
        credential_scan(path, label)
    root = args.root.resolve()
    if not root.is_dir() or args.root.is_symlink():
        raise MaterializationError("bundle root must be a non-symlink directory")
    try:
        args.output.resolve().relative_to(root)
    except ValueError as error:
        raise MaterializationError("bundle output escapes bundle root") from error
    if args.output.exists() or args.output.is_symlink():
        raise MaterializationError("bundle output already exists")
    contract = read_object(args.contract, "contract")
    lock = read_object(args.lock, "pre-test lock")
    if lock.get("contract_sha256") != contract_sha:
        raise MaterializationError("lock references a different contract")
    dataset = lock.get("dataset")
    if not isinstance(dataset, dict):
        raise MaterializationError("lock dataset is absent")
    truth_sha = require_digest(dataset.get("truth_sha256"), "locked truth SHA256")
    inputs = read_object(args.inputs, "bundle inputs")
    if inputs.get("protocol") != BUNDLE_INPUTS_PROTOCOL:
        raise MaterializationError("invalid bundle-input protocol")
    truth = artifact_spec(root, inputs.get("truth"), "truth")
    if truth["sha256"] != truth_sha or truth["rows"] != dataset.get("truth_rows"):
        raise MaterializationError("bundle truth differs from lock")
    baseline_lock = lock.get("baseline")
    baseline_input = inputs.get("baseline")
    if not isinstance(baseline_lock, dict) or not isinstance(baseline_input, dict):
        raise MaterializationError("baseline input is absent")
    baseline_predictions = artifact_spec(
        root, baseline_input.get("predictions"), "baseline predictions"
    )
    if baseline_predictions["rows"] != truth["rows"]:
        raise MaterializationError("baseline prediction row count differs")
    baseline_ledger = ledger_spec(
        root,
        baseline_input.get("ledger"),
        "baseline ledger",
        lock_sha=lock_sha,
        truth_sha=truth_sha,
        prediction_sha=baseline_predictions["sha256"],
        checkpoint_sha=None,
    )
    locked_runs = lock.get("runs")
    supplied_runs = inputs.get("runs")
    if not isinstance(locked_runs, list) or not isinstance(supplied_runs, list):
        raise MaterializationError("model run matrix is absent")
    lock_by_key: dict[tuple[float, int], dict[str, Any]] = {}
    for row in locked_runs:
        if not isinstance(row, dict):
            raise MaterializationError("invalid locked run")
        key = (finite_number(row.get("model_size_b"), "locked model size"), row.get("seed"))
        if isinstance(key[1], bool) or not isinstance(key[1], int) or key in lock_by_key:
            raise MaterializationError("invalid or duplicate locked run")
        lock_by_key[key] = row
    bundle_runs: list[dict[str, Any]] = []
    seen: set[tuple[float, int]] = set()
    for row in supplied_runs:
        if not isinstance(row, dict):
            raise MaterializationError("invalid supplied run")
        size = finite_number(row.get("model_size_b"), "supplied model size")
        seed = row.get("seed")
        key = (size, seed)
        if isinstance(seed, bool) or not isinstance(seed, int) or key in seen or key not in lock_by_key:
            raise MaterializationError("unknown or duplicate supplied run")
        seen.add(key)
        checkpoint_sha = require_digest(
            lock_by_key[key].get("checkpoint_manifest_sha256"), "locked checkpoint manifest"
        )
        if row.get("checkpoint_manifest_sha256") != checkpoint_sha:
            raise MaterializationError("supplied checkpoint differs from lock")
        predictions = artifact_spec(root, row.get("predictions"), f"model {size:g}/{seed} predictions")
        if predictions["rows"] != truth["rows"]:
            raise MaterializationError("model prediction row count differs")
        ledger = ledger_spec(
            root,
            row.get("ledger"),
            f"model {size:g}/{seed} ledger",
            lock_sha=lock_sha,
            truth_sha=truth_sha,
            prediction_sha=predictions["sha256"],
            checkpoint_sha=checkpoint_sha,
        )
        bundle_runs.append(
            {
                "model_size_b": size,
                "seed": seed,
                "checkpoint_manifest_sha256": checkpoint_sha,
                "predictions": predictions,
                "ledger": ledger,
            }
        )
    if seen != set(lock_by_key):
        raise MaterializationError("supplied model matrix is incomplete")
    bundle = {
        "protocol": BUNDLE_PROTOCOL,
        "status": "COMPLETE",
        "lock_sha256": lock_sha,
        "truth": truth,
        "baseline": {
            "id": baseline_lock.get("id"),
            "receipt_sha256": baseline_lock.get("receipt_sha256"),
            "predictions": baseline_predictions,
            "ledger": baseline_ledger,
        },
        "runs": sorted(bundle_runs, key=lambda row: (row["model_size_b"], row["seed"])),
    }
    write_exclusive(args.output, canonical_bytes(bundle), "confirmation bundle")
    return 0


def main() -> int:
    args = arguments()
    if args.command == "truth":
        return materialize_truth(args)
    if args.command == "model-prediction":
        return normalize_model_prediction(args)
    if args.command == "bundle":
        return assemble_bundle(args)
    raise MaterializationError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
