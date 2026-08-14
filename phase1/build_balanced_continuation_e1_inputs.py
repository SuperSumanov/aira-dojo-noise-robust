"""Freeze outcome-blind real inputs for balanced-continuation E1.

The selector uses the v11 corpus only for structural identity/code and the b0 training
decision file only as a parent/run eligibility whitelist.  It never reads grade, gap,
winner orientation, or first-960/prospective outcomes.  The two task names and all input
hashes are source constants so that a later result cannot change the E1 sample.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import tempfile
from collections import defaultdict
from typing import Any


SCHEMA = "balanced-continuation-e1-inputs-v1"
SELECTION_RULE = "v11-b0-train-exact-two-sort-run-parent-first-v1"
TARGET_TASKS = (
    "spaceship-titanic",
    "tabular-playground-series-may-2022",
)
EXPECTED_CARD_ROWS = 16012
EXPECTED_SHA256 = {
    "cards": "6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75",
    # These are the LF bytes in the exact Git worktree used on Linux.  Hashing a
    # Windows checkout would instead bind CRLF materialization, not the experiment.
    "hold": "b31bd70a4483ac1ca207eae47ae39d7b00ced1b02c81583d0b0447fdd3d8489b",
    "decision_train_b0": "bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca",
    "frozen_b0": "2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8",
    "frozen_b1": "a56f6c7bd6aad141fdaa45f3f30f944062e8dea922eefc03e75bc8b415e7bc90",
    "frozen_b2": "79d4694d4cea5a81a04c9d463b5c6599a559bbf867f34205fa5715b054f10bc7",
}
LFS_POINTER = b"version https://git-lfs.github.com/spec/v1\n"
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class E1InputError(RuntimeError):
    """The frozen E1 input contract failed closed."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: pathlib.Path, role: str) -> str:
    if not path.is_file():
        raise E1InputError(f"missing {role}: {path}")
    with path.open("rb") as handle:
        if handle.readline() == LFS_POINTER:
            raise E1InputError(f"{role} is an unsmudged Git LFS pointer")
    actual = file_sha256(path)
    if actual != EXPECTED_SHA256[role]:
        raise E1InputError(
            f"{role} SHA differs: expected={EXPECTED_SHA256[role]} actual={actual}"
        )
    return actual


def atomic_bytes(path: pathlib.Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_json(path: pathlib.Path, value: Any) -> None:
    atomic_bytes(path, canonical_json(value) + b"\n")


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    atomic_bytes(path, b"".join(canonical_json(row) + b"\n" for row in rows))


def load_hold_runs(path: pathlib.Path) -> set[str]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict) or set(value) != {
        "all", "hold", "new_hold", "prior_all", "prior_hold", "seed"
    }:
        raise E1InputError("v11 hold manifest schema differs")
    hold = value["hold"]
    universe = value["all"]
    if not isinstance(hold, list) or not isinstance(universe, list):
        raise E1InputError("v11 hold/all must be lists")
    if len(hold) != len(set(hold)) or not set(hold) <= set(universe):
        raise E1InputError("v11 held runs are duplicated or outside the universe")
    return set(hold)


def load_training_parent_whitelist(path: pathlib.Path) -> dict[str, set[tuple[str, str]]]:
    by_task: dict[str, set[tuple[str, str]]] = {task: set() for task in TARGET_TASKS}
    allowed_keys = {
        "better", "budget", "clears_tau", "gap_raw", "intask_split", "loto_fold",
        "parent", "run_id", "set_size", "src", "task", "worse",
    }
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != allowed_keys:
                raise E1InputError(f"decision train schema differs at line {line_number}")
            task = row["task"]
            if task not in by_task:
                continue
            # These are the only fields used.  Winner IDs and gap are deliberately ignored.
            if row["budget"] != 0 or row["intask_split"] != "train" or row["set_size"] != 2:
                continue
            run_id, parent = row["run_id"], row["parent"]
            if not isinstance(run_id, str) or not isinstance(parent, str):
                raise E1InputError("decision train parent/run identity is invalid")
            by_task[task].add((run_id, parent))
    if any(not by_task[task] for task in TARGET_TASKS):
        raise E1InputError("a frozen E1 task has no exact-two b0 training parent")
    return by_task


def load_frozen_identity(path: pathlib.Path) -> tuple[set[str], set[str]]:
    endpoints: set[str] = set()
    runs: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            if not isinstance(row, dict):
                raise E1InputError(f"frozen identity row is not an object: {line_number}")
            # Identity-only leakage audit.  No gap, score, or orientation is retained.
            for key in ("better", "worse", "run_id"):
                if not isinstance(row.get(key), str) or not row[key]:
                    raise E1InputError(f"invalid frozen {key} at line {line_number}")
            endpoints.update((row["better"], row["worse"]))
            runs.add(row["run_id"])
    return endpoints, runs


def scan_cards(
    path: pathlib.Path,
    held_runs: set[str],
    whitelist: dict[str, set[tuple[str, str]]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, int]]:
    cards: dict[str, dict[str, Any]] = {}
    children: dict[str, list[str]] = defaultdict(list)
    counts = {"rows": 0, "target_rows": 0, "credential_rows": 0}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            counts["rows"] += 1
            row = json.loads(line)
            if not isinstance(row, dict):
                raise E1InputError(f"card row is not an object: {line_number}")
            card_id = row.get("id")
            task_obj = row.get("task")
            lineage = row.get("lineage") or {}
            if not isinstance(card_id, str) or not card_id or card_id in cards:
                raise E1InputError(f"invalid or duplicate card id at line {line_number}")
            if not isinstance(task_obj, dict) or not isinstance(task_obj.get("name"), str):
                raise E1InputError(f"invalid card task at line {line_number}")
            task = task_obj["name"]
            if task not in TARGET_TASKS:
                cards[card_id] = {"task": task, "run_id": row.get("run_id"), "parent": None}
                continue
            counts["target_rows"] += 1
            run_id = row.get("run_id")
            parent = lineage.get("parent_id") if isinstance(lineage, dict) else None
            code = row.get("code")
            if not isinstance(run_id, str) or not run_id:
                raise E1InputError(f"target card lacks run_id at line {line_number}")
            if not isinstance(code, str):
                raise E1InputError(f"target card lacks code at line {line_number}")
            raw_code = code.encode("utf-8")
            if CREDENTIAL.search(raw_code):
                counts["credential_rows"] += 1
            cards[card_id] = {
                "task": task,
                "run_id": run_id,
                "parent": parent,
                "code": code,
                "code_sha256": sha256_bytes(raw_code),
                "held": run_id in held_runs,
            }
            if isinstance(parent, str) and parent:
                children[parent].append(card_id)
    if counts["credential_rows"]:
        raise E1InputError("credential-shaped bytes found in target-task code")
    if counts["rows"] != EXPECTED_CARD_ROWS:
        raise E1InputError(f"v11 card row count differs: {counts['rows']}")

    # Restrict to structurally exact-two children in one task/run, on non-held runs,
    # and to parents independently present in the b0 training-decision whitelist.
    eligible: dict[str, list[str]] = {}
    for parent, child_ids in children.items():
        if len(child_ids) != 2:
            continue
        child_rows = [cards[card_id] for card_id in child_ids]
        tasks = {row["task"] for row in child_rows}
        runs = {row["run_id"] for row in child_rows}
        if len(tasks) != 1 or len(runs) != 1:
            continue
        task = next(iter(tasks))
        run_id = next(iter(runs))
        if task not in TARGET_TASKS or run_id in held_runs:
            continue
        if (run_id, parent) not in whitelist[task]:
            continue
        if any(not row["code"] for row in child_rows):
            continue
        hashes = {row["code_sha256"] for row in child_rows}
        if len(hashes) != 2:
            continue
        eligible[parent] = sorted(child_ids)
    return cards, eligible, counts


def build(args: argparse.Namespace) -> dict[str, Any]:
    inputs = {
        "cards": pathlib.Path(args.cards).resolve(),
        "hold": pathlib.Path(args.hold).resolve(),
        "decision_train_b0": pathlib.Path(args.decision_train_b0).resolve(),
        "frozen_b0": pathlib.Path(args.frozen_b0).resolve(),
        "frozen_b1": pathlib.Path(args.frozen_b1).resolve(),
        "frozen_b2": pathlib.Path(args.frozen_b2).resolve(),
    }
    hashes = {role: require_hash(path, role) for role, path in inputs.items()}
    held_runs = load_hold_runs(inputs["hold"])
    whitelist = load_training_parent_whitelist(inputs["decision_train_b0"])
    cards, eligible, card_counts = scan_cards(inputs["cards"], held_runs, whitelist)

    selected: list[tuple[str, str, list[str]]] = []
    support: dict[str, Any] = {}
    for task in TARGET_TASKS:
        candidates = []
        for parent, child_ids in eligible.items():
            first = cards[child_ids[0]]
            if first["task"] == task:
                candidates.append((first["run_id"], parent, child_ids))
        candidates.sort(key=lambda item: (item[0], item[1]))
        if not candidates:
            raise E1InputError(f"no eligible anchor for {task}")
        selected.append((task, candidates[0][1], candidates[0][2]))
        support[task] = {
            "eligible_exact_two_parents": len(candidates),
            "eligible_physical_runs": len({item[0] for item in candidates}),
            "selection_rank": 0,
        }

    frozen_endpoints: set[str] = set()
    frozen_runs: set[str] = set()
    for role in ("frozen_b0", "frozen_b1", "frozen_b2"):
        endpoints, runs = load_frozen_identity(inputs[role])
        frozen_endpoints.update(endpoints)
        frozen_runs.update(runs)

    anchors: list[dict[str, str]] = []
    vault: list[dict[str, str]] = []
    selected_public: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    selected_runs: set[str] = set()
    selected_hashes: set[str] = set()
    for task, parent, child_ids in selected:
        run_id = cards[child_ids[0]]["run_id"]
        anchor_id = sha256_bytes(
            f"{SCHEMA}|{SELECTION_RULE}|{task}|{run_id}|{parent}".encode("utf-8")
        )
        anchor_context = {
            "schema_version": SCHEMA,
            "selection_rule": SELECTION_RULE,
            "cards_sha256": hashes["cards"],
            "hold_sha256": hashes["hold"],
            "decision_train_b0_sha256": hashes["decision_train_b0"],
            "task": task,
            "source_run_id": run_id,
            "parent_id": parent,
            "sibling_ids": child_ids,
        }
        anchor_contract_sha = sha256_bytes(canonical_json(anchor_context))
        for child_id in child_ids:
            card = cards[child_id]
            anchors.append(
                {
                    "anchor_id": anchor_id,
                    "task": task,
                    "source_run_id": run_id,
                    "parent_id": parent,
                    "sibling_id": child_id,
                    "code_sha256": card["code_sha256"],
                    "anchor_contract_sha256": anchor_contract_sha,
                }
            )
            vault.append(
                {
                    "sibling_id": child_id,
                    "code": card["code"],
                    "code_sha256": card["code_sha256"],
                }
            )
            selected_ids.add(child_id)
            selected_hashes.add(card["code_sha256"])
        selected_runs.add(run_id)
        selected_public.append(anchor_context | {
            "anchor_id": anchor_id,
            "anchor_contract_sha256": anchor_contract_sha,
        })

    if len(anchors) != 4 or len(vault) != 4 or len(selected_hashes) != 4:
        raise E1InputError("E1 must freeze exactly four unique sibling programs")
    endpoint_overlap = selected_ids & frozen_endpoints
    run_overlap = selected_runs & frozen_runs
    if endpoint_overlap or run_overlap:
        raise E1InputError(
            f"selected E1 input overlaps frozen evaluation: endpoints={len(endpoint_overlap)} "
            f"runs={len(run_overlap)}"
        )

    output = pathlib.Path(args.output)
    if not output.is_absolute():
        raise E1InputError("output must be an absolute path")
    if output.exists() or output.is_symlink():
        raise E1InputError("output must not pre-exist")
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if staging.exists() or staging.is_symlink():
        raise E1InputError("staging path already exists")
    staging.mkdir(parents=True)
    try:
        write_jsonl(staging / "anchors.jsonl", anchors)
        write_jsonl(staging / "code_vault.jsonl", vault)
        write_json(staging / "selected_public.json", selected_public)
        summary = {
            "schema_version": SCHEMA,
            "status": "E1_INPUTS_FROZEN_OUTCOME_BLIND",
            "selection_rule": SELECTION_RULE,
            "contains_outcomes": False,
            "winner_orientation_read": False,
            "gap_read": False,
            "first960_or_prospective_read": False,
            "tasks": list(TARGET_TASKS),
            "task_count": 2,
            "anchor_count": 2,
            "siblings_per_anchor": 2,
            "selected_sibling_count": 4,
            "selected_exact_code_count": len(selected_hashes),
            "selected_frozen_endpoint_overlap": 0,
            "selected_frozen_run_overlap": 0,
            "input_sha256": hashes,
            "card_counts": card_counts,
            "support": support,
        }
        write_json(staging / "summary.json", summary)
        manifest = {
            path.name: file_sha256(path)
            for path in sorted(staging.iterdir())
            if path.is_file()
        }
        write_json(staging / "sha256_manifest.json", manifest)
        os.replace(staging, output)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(canonical_json(summary).decode("utf-8"))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--hold", required=True)
    ap.add_argument("--decision-train-b0", required=True)
    ap.add_argument("--frozen-b0", required=True)
    ap.add_argument("--frozen-b1", required=True)
    ap.add_argument("--frozen-b2", required=True)
    ap.add_argument("--output", required=True)
    return ap


def main() -> int:
    try:
        build(parser().parse_args())
    except (E1InputError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"E1_INPUT_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
