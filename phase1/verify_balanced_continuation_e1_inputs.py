"""Independent verifier for the frozen balanced-continuation E1 inputs.

This module deliberately does not import the producer.  It reconstructs the selected
parents and all output rows from the hash-locked source files, then checks the producer's
artifacts byte-for-byte at the semantic level.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import tempfile
from collections import defaultdict
from typing import Any


SCHEMA = "balanced-continuation-e1-inputs-v1"
RULE = "v11-b0-train-exact-two-sort-run-parent-first-v1"
TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")
EXPECTED_CARD_ROWS = 16012
HASHES = {
    "cards": "6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75",
    "hold": "b31bd70a4483ac1ca207eae47ae39d7b00ced1b02c81583d0b0447fdd3d8489b",
    "decision_train_b0": "bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca",
    "frozen_b0": "2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8",
    "frozen_b1": "a56f6c7bd6aad141fdaa45f3f30f944062e8dea922eefc03e75bc8b415e7bc90",
    "frozen_b2": "79d4694d4cea5a81a04c9d463b5c6599a559bbf867f34205fa5715b054f10bc7",
}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerifyError(RuntimeError):
    pass


def canon(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_digest(path: pathlib.Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path: pathlib.Path) -> Any:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    return json.loads(raw)


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise VerifyError(f"non-object JSONL row in {path.name}")
    return rows


def atomic_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canon(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify(args: argparse.Namespace) -> dict[str, Any]:
    sources = {
        "cards": pathlib.Path(args.cards).resolve(),
        "hold": pathlib.Path(args.hold).resolve(),
        "decision_train_b0": pathlib.Path(args.decision_train_b0).resolve(),
        "frozen_b0": pathlib.Path(args.frozen_b0).resolve(),
        "frozen_b1": pathlib.Path(args.frozen_b1).resolve(),
        "frozen_b2": pathlib.Path(args.frozen_b2).resolve(),
    }
    for role, path in sources.items():
        if not path.is_file() or file_digest(path) != HASHES[role]:
            raise VerifyError(f"source hash mismatch: {role}")

    result = pathlib.Path(args.result).resolve()
    expected_files = {
        "anchors.jsonl", "code_vault.jsonl", "selected_public.json", "summary.json",
        "sha256_manifest.json",
    }
    if not result.is_dir() or {p.name for p in result.iterdir()} != expected_files:
        raise VerifyError("E1 result file set differs")

    hold_obj = json.loads(sources["hold"].read_bytes())
    held = set(hold_obj["hold"])
    allowed: dict[str, set[tuple[str, str]]] = {task: set() for task in TASKS}
    for row in read_jsonl(sources["decision_train_b0"]):
        task = row.get("task")
        if (
            task in allowed
            and row.get("budget") == 0
            and row.get("intask_split") == "train"
            and row.get("set_size") == 2
        ):
            allowed[task].add((row["run_id"], row["parent"]))

    cards: dict[str, dict[str, Any]] = {}
    children: dict[str, list[str]] = defaultdict(list)
    rows_seen = 0
    target_seen = 0
    with sources["cards"].open("r", encoding="utf-8") as handle:
        for line in handle:
            rows_seen += 1
            row = json.loads(line)
            card_id = row["id"]
            if card_id in cards:
                raise VerifyError("duplicate card id")
            task = row["task"]["name"]
            if task not in TASKS:
                cards[card_id] = {"task": task, "run_id": row.get("run_id")}
                continue
            target_seen += 1
            run_id = row["run_id"]
            parent = (row.get("lineage") or {}).get("parent_id")
            code = row["code"]
            if not all(isinstance(value, str) for value in (card_id, run_id, code)):
                raise VerifyError("target card structural field differs")
            if CREDENTIAL.search(code.encode("utf-8")):
                raise VerifyError("credential-shaped bytes in selected task universe")
            cards[card_id] = {
                "task": task,
                "run_id": run_id,
                "parent": parent,
                "code": code,
                "code_sha256": digest(code.encode("utf-8")),
            }
            if isinstance(parent, str) and parent:
                children[parent].append(card_id)
    if rows_seen != EXPECTED_CARD_ROWS:
        raise VerifyError("card count differs")

    eligible_by_task: dict[str, list[tuple[str, str, list[str]]]] = {
        task: [] for task in TASKS
    }
    for parent, raw_ids in children.items():
        if len(raw_ids) != 2:
            continue
        ids = sorted(raw_ids)
        values = [cards[item] for item in ids]
        tasks = {value["task"] for value in values}
        runs = {value["run_id"] for value in values}
        if len(tasks) != 1 or len(runs) != 1:
            continue
        task, run_id = next(iter(tasks)), next(iter(runs))
        if task not in TASKS or run_id in held or (run_id, parent) not in allowed[task]:
            continue
        if not all(value["code"] for value in values):
            continue
        if len({value["code_sha256"] for value in values}) != 2:
            continue
        eligible_by_task[task].append((run_id, parent, ids))
    for task in TASKS:
        eligible_by_task[task].sort(key=lambda item: (item[0], item[1]))
        if not eligible_by_task[task]:
            raise VerifyError(f"no independently reconstructed anchor: {task}")

    expected_anchors: list[dict[str, Any]] = []
    expected_vault: list[dict[str, Any]] = []
    expected_public: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    selected_runs: set[str] = set()
    for task in TASKS:
        run_id, parent, sibling_ids = eligible_by_task[task][0]
        anchor_id = digest(f"{SCHEMA}|{RULE}|{task}|{run_id}|{parent}".encode("utf-8"))
        context = {
            "schema_version": SCHEMA,
            "selection_rule": RULE,
            "cards_sha256": HASHES["cards"],
            "hold_sha256": HASHES["hold"],
            "decision_train_b0_sha256": HASHES["decision_train_b0"],
            "task": task,
            "source_run_id": run_id,
            "parent_id": parent,
            "sibling_ids": sibling_ids,
        }
        anchor_hash = digest(canon(context))
        expected_public.append(context | {
            "anchor_id": anchor_id,
            "anchor_contract_sha256": anchor_hash,
        })
        for sibling_id in sibling_ids:
            card = cards[sibling_id]
            expected_anchors.append({
                "anchor_id": anchor_id,
                "task": task,
                "source_run_id": run_id,
                "parent_id": parent,
                "sibling_id": sibling_id,
                "code_sha256": card["code_sha256"],
                "anchor_contract_sha256": anchor_hash,
            })
            expected_vault.append({
                "sibling_id": sibling_id,
                "code": card["code"],
                "code_sha256": card["code_sha256"],
            })
            selected_ids.add(sibling_id)
        selected_runs.add(run_id)

    if read_jsonl(result / "anchors.jsonl") != expected_anchors:
        raise VerifyError("anchors do not match independent reconstruction")
    if read_jsonl(result / "code_vault.jsonl") != expected_vault:
        raise VerifyError("code vault does not match independent reconstruction")
    if read_json(result / "selected_public.json") != expected_public:
        raise VerifyError("public selection receipt differs")

    frozen_ids: set[str] = set()
    for role in ("frozen_b0", "frozen_b1", "frozen_b2"):
        for row in read_jsonl(sources[role]):
            if not isinstance(row, dict):
                raise VerifyError("frozen identity row is not an object")
            endpoints = (row.get("better"), row.get("worse"))
            if not all(isinstance(item, str) and item for item in endpoints):
                raise VerifyError("frozen endpoint identity differs")
            frozen_ids.update(endpoints)
    if frozen_ids - cards.keys():
        raise VerifyError("frozen endpoint is absent from v11 cards")
    frozen_runs = {cards[item].get("run_id") for item in frozen_ids}
    if any(not isinstance(item, str) or not item for item in frozen_runs):
        raise VerifyError("frozen endpoint run cannot be reconstructed")
    if selected_ids & frozen_ids or selected_runs & frozen_runs:
        raise VerifyError("selected input overlaps frozen evaluation identity")

    summary = read_json(result / "summary.json")
    required_summary = {
        "schema_version": SCHEMA,
        "status": "E1_INPUTS_FROZEN_OUTCOME_BLIND",
        "selection_rule": RULE,
        "contains_outcomes": False,
        "winner_orientation_read": False,
        "gap_read": False,
        "first960_or_prospective_read": False,
        "frozen_run_id_source": "v11-card-endpoint-lookup",
        "frozen_rows_run_id_required": False,
        "tasks": list(TASKS),
        "task_count": 2,
        "anchor_count": 2,
        "siblings_per_anchor": 2,
        "selected_sibling_count": 4,
        "selected_exact_code_count": 4,
        "selected_frozen_endpoint_overlap": 0,
        "selected_frozen_run_overlap": 0,
        "input_sha256": HASHES,
    }
    if not isinstance(summary, dict) or any(summary.get(k) != v for k, v in required_summary.items()):
        raise VerifyError("summary frozen fields differ")
    if set(summary.get("support", {})) != set(TASKS):
        raise VerifyError("summary task support differs")
    if summary.get("card_counts", {}).get("rows") != rows_seen:
        raise VerifyError("summary card count differs")
    if summary.get("card_counts", {}).get("target_rows") != target_seen:
        raise VerifyError("summary target-card count differs")
    for task in TASKS:
        expected_support = {
            "eligible_exact_two_parents": len(eligible_by_task[task]),
            "eligible_physical_runs": len({item[0] for item in eligible_by_task[task]}),
            "selection_rank": 0,
        }
        if summary["support"][task] != expected_support:
            raise VerifyError(f"support summary differs for {task}")

    manifest = read_json(result / "sha256_manifest.json")
    expected_manifest_keys = expected_files - {"sha256_manifest.json"}
    if set(manifest) != expected_manifest_keys:
        raise VerifyError("producer hash manifest key set differs")
    for name, expected_hash in manifest.items():
        if file_digest(result / name) != expected_hash:
            raise VerifyError(f"producer hash manifest mismatch: {name}")

    receipt = {
        "schema_version": "balanced-continuation-e1-input-verification-v1",
        "status": "VERIFIED_E1_INPUTS_OUTCOME_BLIND_ZERO_FROZEN_OVERLAP",
        "producer_imported": False,
        "tasks": list(TASKS),
        "anchors": 2,
        "siblings": 4,
        "exact_code_hashes": 4,
        "selected_frozen_endpoint_overlap": 0,
        "selected_frozen_run_overlap": 0,
        "source_sha256": HASHES,
        "result_file_sha256": {
            name: file_digest(result / name) for name in sorted(expected_files)
        },
    }
    receipt_path = pathlib.Path(args.receipt).resolve()
    if receipt_path.exists() or receipt_path.is_symlink():
        raise VerifyError("verification receipt must not pre-exist")
    atomic_json(receipt_path, receipt)
    print(canon(receipt).decode("utf-8"))
    return receipt


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--hold", required=True)
    ap.add_argument("--decision-train-b0", required=True)
    ap.add_argument("--frozen-b0", required=True)
    ap.add_argument("--frozen-b1", required=True)
    ap.add_argument("--frozen-b2", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--receipt", required=True)
    return ap


def main() -> int:
    try:
        verify(parser().parse_args())
    except (VerifyError, OSError, UnicodeError, json.JSONDecodeError, KeyError) as exc:
        print(f"E1_INPUT_VERIFY_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
