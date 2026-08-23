"""Independent source-binding verifier for clean scaling materialization.

This module intentionally does not import the materializer.  It reconstructs
truth/component identities and one-shot prediction normalization from immutable
source artifacts using a second implementation.  It never trains or scores a
model.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


TRUTH_PROTOCOL = "critic-scaling-truth-materialization-v1"
VERIFY_PROTOCOL = "critic-scaling-materialization-independent-verification-v1"
LOCK_PROTOCOL = "critic-scaling-confirmation-lock-v1"
ONE_SHOT_PROTOCOL = "rm-one-shot-test-v1"
MODEL_LEDGER_PROTOCOL = "critic-scaling-derived-one-shot-ledger-v1"
CHECKPOINT_PROTOCOL = "critic-scaling-checkpoint-manifest-v1"
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40_OR_64 = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{20,}|"
    rb"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerificationError(RuntimeError):
    pass


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    truth = commands.add_parser("truth")
    for name in ("pairs", "cards", "truth", "receipt", "output"):
        truth.add_argument(f"--{name}", type=Path, required=True)
    truth.add_argument("--expected-pairs-sha256", required=True)
    truth.add_argument("--expected-cards-sha256", required=True)
    truth.add_argument("--expected-truth-sha256", required=True)
    truth.add_argument("--expected-receipt-sha256", required=True)

    model = commands.add_parser("model")
    for name in (
        "truth", "lock", "checkpoint-manifest", "one-shot-output",
        "one-shot-ledger", "predictions", "derived-ledger", "output",
    ):
        model.add_argument(f"--{name}", type=Path, required=True)
    for name in (
        "truth", "lock", "checkpoint-manifest", "one-shot-output",
        "one-shot-ledger", "predictions", "derived-ledger",
    ):
        model.add_argument(f"--expected-{name}-sha256", required=True)
    return parser.parse_args()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def compact(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest_file(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            state.update(block)
    return state.hexdigest()


def digest_path(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()


def expect_digest(value: Any, label: str, *, git: bool = False) -> str:
    pattern = HEX40_OR_64 if git else HEX64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise VerificationError(f"invalid digest for {label}")
    return value


def bind(path: Path, expected: Any, label: str) -> str:
    expected = expect_digest(expected, f"expected {label}")
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is not a regular file")
    actual = digest_file(path)
    if actual != expected:
        raise VerificationError(f"{label} digest mismatch")
    return actual


def scan(path: Path, label: str) -> None:
    carry = b""
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            payload = carry + block
            if CREDENTIAL.search(payload):
                raise VerificationError(f"credential-shaped bytes in {label}")
            carry = payload[-256:]


def object_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot parse {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    raise VerificationError(f"blank line in {label}:{number}")
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise VerificationError(f"non-object in {label}:{number}")
                result.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        if isinstance(error, VerificationError):
            raise
        raise VerificationError(f"cannot parse {label}") from error
    if not result:
        raise VerificationError(f"empty {label}")
    return result


def text(row: Mapping[str, Any], key: str, where: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise VerificationError(f"invalid {key} in {where}")
    return value


def number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VerificationError(f"non-numeric {label}")
    result = float(value)
    if not math.isfinite(result):
        raise VerificationError(f"non-finite {label}")
    return result


def flatten_cards(path: Path) -> dict[str, dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    try:
        root = json.loads(raw)
    except json.JSONDecodeError:
        root = None
    entries: list[tuple[str | None, dict[str, Any]]] = []
    if isinstance(root, dict) and all(isinstance(value, list) for value in root.values()):
        for run in sorted(root):
            if not isinstance(run, str) or not run:
                raise VerificationError("invalid grouped run")
            for card in root[run]:
                if not isinstance(card, dict):
                    raise VerificationError("non-object grouped Card")
                entries.append((run, card))
    elif isinstance(root, list):
        for card in root:
            if not isinstance(card, dict):
                raise VerificationError("non-object Card array row")
            entries.append((None, card))
    else:
        for line_no, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                raise VerificationError(f"blank Cards line {line_no}")
            try:
                card = json.loads(line)
            except json.JSONDecodeError as error:
                raise VerificationError(f"bad Cards line {line_no}") from error
            if not isinstance(card, dict):
                raise VerificationError(f"non-object Cards line {line_no}")
            entries.append((None, card))
    output: dict[str, dict[str, Any]] = {}
    for index, (group_run, card) in enumerate(entries, 1):
        where = f"Card {index}"
        identifier = text(card, "id", where)
        if identifier in output:
            raise VerificationError("duplicate Card ID")
        declared_run = card.get("run_id")
        if declared_run is not None and (not isinstance(declared_run, str) or not declared_run):
            raise VerificationError(f"invalid run in {where}")
        if group_run and declared_run and group_run != declared_run:
            raise VerificationError(f"run mismatch in {where}")
        run = group_run or declared_run
        if not isinstance(run, str) or not run:
            raise VerificationError(f"missing run in {where}")
        task_value = card.get("task")
        if isinstance(task_value, dict):
            task = text(task_value, "name", where)
        elif isinstance(task_value, str) and task_value:
            task = task_value
        else:
            raise VerificationError(f"invalid task in {where}")
        lineage = card.get("lineage")
        if not isinstance(lineage, dict):
            raise VerificationError(f"invalid lineage in {where}")
        parent = lineage.get("parent_id")
        if parent is not None and (not isinstance(parent, str) or not parent):
            raise VerificationError(f"invalid parent in {where}")
        label = card.get("label")
        grade = None
        if isinstance(label, dict) and label.get("graded") is not None:
            grade = number(label["graded"], f"grade in {where}")
        output[identifier] = {"run": run, "task": task, "parent": parent, "grade": grade}
    if not output:
        raise VerificationError("empty Cards")
    return output


def graph_parts(edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    neighbours: dict[str, set[str]] = collections.defaultdict(set)
    for left, right in edges:
        neighbours[left].add(right)
        neighbours[right].add(left)
    unseen = set(neighbours)
    parts: list[list[str]] = []
    while unseen:
        seed = min(unseen)
        found = {seed}
        queue = [seed]
        while queue:
            current = queue.pop(0)
            for adjacent in sorted(neighbours[current]):
                if adjacent not in found:
                    found.add(adjacent)
                    queue.append(adjacent)
        parts.append(sorted(found))
        unseen.difference_update(found)
    return sorted(parts)


def component_id(group: tuple[str, str, str, str], endpoints: Sequence[str]) -> str:
    payload = ["critic-scaling-component-v1", *group, sorted(endpoints)]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def pair_id(row: Mapping[str, Any]) -> str:
    payload = [
        row["task"], row["pair_semantics"], row["parent_id"],
        row["comparison_component_id"], row["better_id"], row["worse_id"],
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def reconstruct_truth(
    source_pairs: Sequence[dict[str, Any]], cards: Mapping[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    working: list[dict[str, Any]] = []
    signs: dict[str, int] = {}
    edges_seen: set[tuple[str, str, str, frozenset[str]]] = set()
    budgets: set[str] = set()
    grouped: dict[tuple[str, str, str, str], list[tuple[str, str]]] = collections.defaultdict(list)
    for index, source in enumerate(source_pairs, 1):
        where = f"pair {index}"
        if source.get("intask_split") != "test":
            raise VerificationError(f"non-test {where}")
        task = text(source, "task", where)
        semantics = text(source, "pair_semantics", where)
        if semantics != "canonical_raw_sibling":
            raise VerificationError(f"non-canonical {where}")
        parent = source.get("parent", source.get("parent_id"))
        if source.get("parent") is not None and source.get("parent_id") not in (None, parent):
            raise VerificationError(f"conflicting parent in {where}")
        if not isinstance(parent, str) or not parent:
            raise VerificationError(f"missing parent in {where}")
        better, worse = text(source, "better", where), text(source, "worse", where)
        if better == worse or better not in cards or worse not in cards:
            raise VerificationError(f"bad endpoints in {where}")
        bcard, wcard = cards[better], cards[worse]
        if bcard["task"] != task or wcard["task"] != task:
            raise VerificationError(f"task mismatch in {where}")
        if bcard["parent"] != parent or wcard["parent"] != parent:
            raise VerificationError(f"lineage mismatch in {where}")
        runs = [bcard["run"], wcard["run"]]
        if source.get("endpoint_run_ids") != runs:
            raise VerificationError(f"endpoint run mismatch in {where}")
        parent_run = text(source, "parent_run_id", where)
        if parent_run != runs[0] or parent_run != runs[1]:
            raise VerificationError(f"cross-run {where}")
        if parent in cards and (
            cards[parent]["run"] != parent_run or cards[parent]["task"] != task
        ):
            raise VerificationError(f"parent metadata mismatch in {where}")
        bgrade, wgrade = bcard["grade"], wcard["grade"]
        if bgrade is None or wgrade is None or bgrade == wgrade:
            raise VerificationError(f"invalid utility in {where}")
        edge_key = (task, semantics, parent, frozenset((better, worse)))
        if edge_key in edges_seen:
            raise VerificationError(f"duplicate edge in {where}")
        edges_seen.add(edge_key)
        sign = 1 if bgrade > wgrade else -1
        if task in signs and signs[task] != sign:
            raise VerificationError(f"direction mismatch for {task}")
        signs[task] = sign
        budgets.add(compact(source.get("budget")))
        group = (task, semantics, parent, parent_run)
        grouped[group].append((better, worse))
        working.append(
            {
                "split": "test",
                "task": task,
                "pair_semantics": semantics,
                "parent_id": parent,
                "parent_run_id": parent_run,
                "better_id": better,
                "worse_id": worse,
                "better_run_id": runs[0],
                "worse_run_id": runs[1],
                "better_utility": sign * bgrade,
                "worse_utility": sign * wgrade,
                "_group": group,
            }
        )
    if len(budgets) != 1:
        raise VerificationError("multiple budgets")
    membership: dict[tuple[tuple[str, str, str, str], str], str] = {}
    for group in sorted(grouped):
        for endpoints in graph_parts(grouped[group]):
            identity = component_id(group, endpoints)
            for endpoint in endpoints:
                membership[(group, endpoint)] = identity
    rows: list[dict[str, Any]] = []
    for source in working:
        group = source.pop("_group")
        component = membership[(group, source["better_id"])]
        if component != membership[(group, source["worse_id"])]:
            raise VerificationError("component split")
        row = {"comparison_component_id": component, **source}
        row["pair_id"] = pair_id(row)
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row["task"], row["parent_id"], row["comparison_component_id"],
            row["better_id"], row["worse_id"],
        )
    )
    counts = collections.Counter(row["task"] for row in rows)
    support = {
        "pairs": len(rows),
        "tasks": len(counts),
        "components": len({row["comparison_component_id"] for row in rows}),
        "dominant_task_pair_share": max(counts.values()) / len(rows),
        "budget_canonical_json": next(iter(budgets)),
        "task_grade_direction": {
            task: "higher_raw_grade_is_better" if sign == 1 else "lower_raw_grade_is_better"
            for task, sign in sorted(signs.items())
        },
    }
    return rows, support


def write_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise VerificationError("verification output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(canonical(dict(payload)))
    except FileExistsError as error:
        raise VerificationError("verification output already exists") from error


def verify_truth(args: argparse.Namespace) -> int:
    pairs_sha = bind(args.pairs, args.expected_pairs_sha256, "pairs")
    cards_sha = bind(args.cards, args.expected_cards_sha256, "Cards")
    truth_sha = bind(args.truth, args.expected_truth_sha256, "truth")
    receipt_sha = bind(args.receipt, args.expected_receipt_sha256, "truth receipt")
    for path, label in (
        (args.pairs, "pairs"), (args.cards, "Cards"),
        (args.truth, "truth"), (args.receipt, "truth receipt"),
    ):
        scan(path, label)
    expected_rows, support = reconstruct_truth(jsonl(args.pairs, "pairs"), flatten_cards(args.cards))
    observed_rows = jsonl(args.truth, "truth")
    if observed_rows != expected_rows:
        raise VerificationError("truth rows differ from independent reconstruction")
    receipt = object_file(args.receipt, "truth receipt")
    if receipt.get("protocol") != TRUTH_PROTOCOL or receipt.get("status") != "COMPLETE":
        raise VerificationError("invalid truth receipt protocol")
    if receipt.get("inputs") != {"pairs_sha256": pairs_sha, "cards_sha256": cards_sha}:
        raise VerificationError("truth receipt input binding differs")
    if receipt.get("truth") != {"sha256": truth_sha, "rows": len(expected_rows)}:
        raise VerificationError("truth receipt output binding differs")
    if receipt.get("support") != support:
        raise VerificationError("truth receipt support differs")
    source_commit = receipt.get("source_commit")
    expect_digest(source_commit, "truth source commit", git=True)
    write_receipt(
        args.output,
        {
            "protocol": VERIFY_PROTOCOL,
            "status": "VERIFIED_TRUTH_SOURCE_BINDING",
            "imports_producer": False,
            "pairs_sha256": pairs_sha,
            "cards_sha256": cards_sha,
            "truth_sha256": truth_sha,
            "truth_receipt_sha256": receipt_sha,
            "rows": len(expected_rows),
            "support": support,
        },
    )
    return 0


def truth_index(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    output: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, 1):
        where = f"truth row {index}"
        for field in (
            "pair_id", "task", "pair_semantics", "parent_id", "parent_run_id",
            "comparison_component_id", "better_id", "worse_id", "better_run_id",
            "worse_run_id",
        ):
            text(row, field, where)
        if row.get("split") != "test" or row["pair_id"] != pair_id(row):
            raise VerificationError(f"invalid identity in {where}")
        if row["pair_id"] in seen_ids:
            raise VerificationError("duplicate pair ID")
        seen_ids.add(row["pair_id"])
        key = (
            row["task"], row["pair_semantics"], row["parent_id"],
            row["better_id"], row["worse_id"],
        )
        if key in output:
            raise VerificationError("duplicate truth identity")
        output[key] = row
    return output


def verify_model(args: argparse.Namespace) -> int:
    paths = {
        "truth": (args.truth, args.expected_truth_sha256),
        "lock": (args.lock, args.expected_lock_sha256),
        "checkpoint_manifest": (
            args.checkpoint_manifest, args.expected_checkpoint_manifest_sha256
        ),
        "one_shot_output": (args.one_shot_output, args.expected_one_shot_output_sha256),
        "one_shot_ledger": (args.one_shot_ledger, args.expected_one_shot_ledger_sha256),
        "predictions": (args.predictions, args.expected_predictions_sha256),
        "derived_ledger": (args.derived_ledger, args.expected_derived_ledger_sha256),
    }
    hashes: dict[str, str] = {}
    for label, (path, expected) in paths.items():
        hashes[label] = bind(path, expected, label)
        scan(path, label)
    lock = object_file(args.lock, "lock")
    if lock.get("protocol") != LOCK_PROTOCOL or lock.get("status") != "LOCKED_BEFORE_TEST_ACCESS":
        raise VerificationError("invalid lock")
    dataset = lock.get("dataset")
    if not isinstance(dataset, dict) or dataset.get("truth_sha256") != hashes["truth"]:
        raise VerificationError("lock/truth mismatch")
    manifest = object_file(args.checkpoint_manifest, "checkpoint manifest")
    if manifest.get("protocol") != CHECKPOINT_PROTOCOL or manifest.get("status") != "LOCKED_BEFORE_TEST_ACCESS":
        raise VerificationError("invalid checkpoint manifest")
    runs = lock.get("runs")
    if not isinstance(runs, list):
        raise VerificationError("lock runs absent")
    matching = [
        run for run in runs
        if isinstance(run, dict)
        and run.get("checkpoint_manifest_sha256") == hashes["checkpoint_manifest"]
    ]
    if len(matching) != 1:
        raise VerificationError("manifest does not select one locked run")
    run = matching[0]
    if run.get("one_shot_output_path_sha256") != digest_path(args.one_shot_output):
        raise VerificationError("output path was not locked")
    if run.get("one_shot_ledger_path_sha256") != digest_path(args.one_shot_ledger):
        raise VerificationError("ledger path was not locked")
    if number(run.get("model_size_b"), "run size") != number(manifest.get("model_size_b"), "manifest size"):
        raise VerificationError("manifest size mismatch")
    if run.get("seed") != manifest.get("seed"):
        raise VerificationError("manifest seed mismatch")
    manifest_artifacts = manifest.get("artifacts")
    if not isinstance(manifest_artifacts, dict):
        raise VerificationError("manifest artifacts absent")

    upstream_ledger = object_file(args.one_shot_ledger, "one-shot ledger")
    if upstream_ledger.get("protocol") != ONE_SHOT_PROTOCOL or upstream_ledger.get("status") != "COMPLETE":
        raise VerificationError("upstream ledger incomplete")
    expected_artifacts = upstream_ledger.get("expected_artifacts")
    observed_artifacts = upstream_ledger.get("observed_artifacts")
    if not isinstance(expected_artifacts, dict) or observed_artifacts != expected_artifacts:
        raise VerificationError("upstream artifact receipts differ")
    if expected_artifacts.get("pairs") != dataset.get("pairs_sha256"):
        raise VerificationError("upstream pairs differ")
    if expected_artifacts.get("cards") != dataset.get("cards_sha256"):
        raise VerificationError("upstream Cards differ")
    if "model.safetensors" not in expected_artifacts:
        raise VerificationError("upstream model receipt absent")
    for name, digest in expected_artifacts.items():
        expect_digest(digest, f"upstream {name}")
        if name not in {"pairs", "cards"} and manifest_artifacts.get(name) != digest:
            raise VerificationError(f"manifest artifact mismatch for {name}")
    if upstream_ledger.get("output") != str(args.one_shot_output.resolve()):
        raise VerificationError("upstream output path differs")
    result = upstream_ledger.get("result")
    if not isinstance(result, dict) or result.get("output_sha256") != hashes["one_shot_output"]:
        raise VerificationError("upstream output hash differs")

    upstream_output = object_file(args.one_shot_output, "one-shot output")
    if upstream_output.get("protocol") != ONE_SHOT_PROTOCOL or upstream_output.get("split") != "test":
        raise VerificationError("invalid upstream output")
    if upstream_output.get("artifacts") != expected_artifacts:
        raise VerificationError("upstream output artifacts differ")
    source_predictions = upstream_output.get("pair_predictions")
    truth_rows = jsonl(args.truth, "truth")
    index = truth_index(truth_rows)
    if not isinstance(source_predictions, list) or len(source_predictions) != len(truth_rows):
        raise VerificationError("upstream prediction count differs")
    if upstream_output.get("n_pairs") != len(source_predictions) or result.get("n_pairs") != len(source_predictions):
        raise VerificationError("upstream count receipts differ")

    expected_normalized: list[dict[str, Any]] = []
    indices: set[int] = set()
    identities: set[str] = set()
    scores: dict[str, float] = {}
    for position, source in enumerate(source_predictions, 1):
        if not isinstance(source, dict):
            raise VerificationError(f"non-object source prediction {position}")
        pair_index_value = source.get("pair_index")
        if (
            isinstance(pair_index_value, bool)
            or not isinstance(pair_index_value, int)
            or pair_index_value < 0
            or pair_index_value in indices
        ):
            raise VerificationError("invalid source pair_index")
        indices.add(pair_index_value)
        key = (
            text(source, "task", "source prediction"),
            text(source, "pair_semantics", "source prediction"),
            text(source, "parent", "source prediction"),
            text(source, "better", "source prediction"),
            text(source, "worse", "source prediction"),
        )
        truth = index.get(key)
        if truth is None:
            raise VerificationError("source pair absent or reversed")
        if source.get("parent_run_id") != truth["parent_run_id"]:
            raise VerificationError("source parent run differs")
        if source.get("endpoint_run_ids") != [truth["better_run_id"], truth["worse_run_id"]]:
            raise VerificationError("source endpoint runs differ")
        better_score = number(source.get("better_score"), "better score")
        worse_score = number(source.get("worse_score"), "worse score")
        margin = number(source.get("margin"), "margin")
        if not math.isclose(margin, better_score - worse_score, rel_tol=0.0, abs_tol=1e-9):
            raise VerificationError("source margin differs")
        for endpoint, score in (
            (truth["better_id"], better_score), (truth["worse_id"], worse_score)
        ):
            if endpoint in scores and not math.isclose(
                scores[endpoint], score, rel_tol=0.0, abs_tol=1e-9
            ):
                raise VerificationError("source endpoint score differs")
            scores[endpoint] = score
        identity = truth["pair_id"]
        if identity in identities:
            raise VerificationError("duplicate source pair")
        identities.add(identity)
        expected_normalized.append(
            {
                "pair_id": identity,
                "better_score": better_score,
                "worse_score": worse_score,
                "margin": margin,
            }
        )
    if indices != set(range(len(source_predictions))):
        raise VerificationError("source pair_index coverage differs")
    expected_normalized.sort(key=lambda row: row["pair_id"])
    if jsonl(args.predictions, "normalized predictions") != expected_normalized:
        raise VerificationError("normalized predictions differ from independent reconstruction")

    derived = object_file(args.derived_ledger, "derived ledger")
    required = {
        "protocol": MODEL_LEDGER_PROTOCOL,
        "status": "COMPLETE",
        "test_attempts": 1,
        "lock_sha256": hashes["lock"],
        "truth_sha256": hashes["truth"],
        "prediction_sha256": hashes["predictions"],
        "checkpoint_manifest_sha256": hashes["checkpoint_manifest"],
    }
    if any(derived.get(key) != value for key, value in required.items()):
        raise VerificationError("derived ledger core fields differ")
    source_binding = derived.get("source_one_shot")
    expected_binding = {
        "ledger_sha256": hashes["one_shot_ledger"],
        "output_sha256": hashes["one_shot_output"],
        "ledger_path_sha256": digest_path(args.one_shot_ledger),
        "output_path_sha256": digest_path(args.one_shot_output),
        "expected_artifacts": expected_artifacts,
    }
    if source_binding != expected_binding:
        raise VerificationError("derived source binding differs")
    write_receipt(
        args.output,
        {
            "protocol": VERIFY_PROTOCOL,
            "status": "VERIFIED_MODEL_SOURCE_BINDING",
            "imports_producer": False,
            "hashes": hashes,
            "rows": len(expected_normalized),
            "model_size_b": run.get("model_size_b"),
            "seed": run.get("seed"),
        },
    )
    return 0


def main() -> int:
    args = arguments()
    if args.command == "truth":
        return verify_truth(args)
    if args.command == "model":
        return verify_model(args)
    raise VerificationError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
