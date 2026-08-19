"""Materialize the frozen 24-parent E2-A input/code vault from the support receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import tempfile
from collections import Counter
from typing import Any


SCHEMA = "balanced-continuation-e2a-inputs-v1"
SUPPORT_SCHEMA = "balanced-continuation-e2a-support-audit-v1"
EXPECTED_SUPPORT_SHA256 = "7ffb23a7577640ef61730d214f7cccd6b3c202b07356a864885b41b46ec98ac0"
EXPECTED_CARDS_SHA256 = "6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75"
EXPECTED_CARD_ROWS = 16012
TASKS = (
    "spaceship-titanic", "tabular-playground-series-may-2022",
    "spooky-author-identification", "us-patent-phrase-to-phrase-matching",
    "nomad2018-predict-transparent-conductors",
    "learning-agency-lab-automated-essay-scoring-2",
)
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class InputError(RuntimeError):
    pass


def canon(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_json(path: pathlib.Path, expected_sha: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise InputError(f"missing or symlinked input: {path}")
    raw = path.read_bytes()
    if sha_bytes(raw) != expected_sha:
        raise InputError(f"input SHA differs: {path.name}")
    if CREDENTIAL.search(raw):
        raise InputError(f"credential-shaped bytes in {path.name}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise InputError(f"input is not an object: {path.name}")
    return value


def atomic_bytes(path: pathlib.Path, raw: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        if mode is not None: os.chmod(temporary, mode)
        os.replace(temporary, path)
        if mode is not None: os.chmod(path, mode)
    finally:
        if temporary.exists(): temporary.unlink()


def atomic_json(path: pathlib.Path, value: Any, mode: int | None = None) -> None:
    atomic_bytes(path, canon(value) + b"\n", mode=mode)


def atomic_jsonl(path: pathlib.Path, rows: list[dict[str, Any]], mode: int | None = None) -> None:
    atomic_bytes(path, b"".join(canon(row) + b"\n" for row in rows), mode=mode)


def validate_support(value: dict[str, Any]) -> list[dict[str, Any]]:
    if (
        value.get("schema_version") != SUPPORT_SCHEMA
        or value.get("status") != "E2A_SIX_TASK_STRUCTURAL_AND_PUBLIC_TRAIN_SUPPORT_PASS"
        or value.get("tasks") != list(TASKS)
        or value.get("selected_anchor_count") != 24
        or value.get("selected_sibling_count") != 48
        or value.get("selected_physical_run_count") != 24
        or value.get("scientific_outcomes_read") is not False
        or value.get("official_test_opened") is not False
        or value.get("private_answers_opened") is not False
    ):
        raise InputError("support receipt top-level contract differs")
    rows = value.get("selected_anchors")
    if not isinstance(rows, list) or len(rows) != 24:
        raise InputError("support selected-anchor rows differ")
    counts = Counter(row.get("task") for row in rows if isinstance(row, dict))
    if counts != Counter({task: 4 for task in TASKS}):
        raise InputError("support task balance differs")
    return rows


def load_selected_cards(path: pathlib.Path, selected_ids: set[str]) -> dict[str, dict[str, str]]:
    if not path.is_file() or path.is_symlink() or sha(path) != EXPECTED_CARDS_SHA256:
        raise InputError("v11 cards path/hash differs")
    result: dict[str, dict[str, str]] = {}
    row_count = 0
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, 1):
            row_count += 1
            row = json.loads(line)
            card_id = row.get("id") if isinstance(row, dict) else None
            if card_id not in selected_ids:
                continue
            task_obj = row.get("task")
            lineage = row.get("lineage") or {}
            run = row.get("run_id")
            code = row.get("code")
            if (
                not isinstance(task_obj, dict) or not isinstance(task_obj.get("name"), str)
                or not isinstance(lineage, dict) or not isinstance(lineage.get("parent_id"), str)
                or not isinstance(run, str) or not run or not isinstance(code, str) or not code
            ):
                raise InputError(f"selected card schema differs at line {index}")
            raw_code = code.encode("utf-8")
            if CREDENTIAL.search(raw_code):
                raise InputError("credential-shaped bytes in selected code")
            result[card_id] = {
                "task": task_obj["name"], "run": run, "parent": lineage["parent_id"],
                "code": code, "code_sha256": sha_bytes(raw_code),
            }
    if row_count != EXPECTED_CARD_ROWS or set(result) != selected_ids:
        raise InputError("card count or selected-card coverage differs")
    return result


def recursive_manifest(root: pathlib.Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "sha256_manifest.json":
            result[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size, "mode": stat.S_IMODE(path.stat().st_mode),
                "sha256": sha(path),
            }
    return result


def build(args: argparse.Namespace) -> dict[str, Any]:
    support_path = pathlib.Path(args.support).resolve()
    support = checked_json(support_path, EXPECTED_SUPPORT_SHA256)
    selected = validate_support(support)
    sibling_ids = {
        sibling for row in selected for sibling in row.get("sibling_ids", [])
        if isinstance(sibling, str)
    }
    if len(sibling_ids) != 48:
        raise InputError("support sibling identities differ")
    cards = load_selected_cards(pathlib.Path(args.cards).resolve(), sibling_ids)
    by_task = {task: sorted(
        [row for row in selected if row["task"] == task], key=lambda row: row["selection_key"]
    ) for task in TASKS}
    calibration_parent = {task: by_task[task][0]["parent_id"] for task in TASKS}
    anchors: list[dict[str, str]] = []
    vault: list[dict[str, str]] = []
    public_rows: list[dict[str, Any]] = []
    code_hashes: set[str] = set()
    run_ids: set[str] = set()
    for task in TASKS:
        if len(by_task[task]) != 4:
            raise InputError(f"task anchor count differs: {task}")
        for source in by_task[task]:
            run, parent = source["physical_run_id"], source["parent_id"]
            child_ids = source["sibling_ids"]
            expected_hashes = source["sibling_code_sha256"]
            if len(child_ids) != 2 or len(set(child_ids)) != 2 or len(expected_hashes) != 2:
                raise InputError("support exact-two sibling contract differs")
            rows = [cards[card_id] for card_id in child_ids]
            actual_hashes = [row["code_sha256"] for row in rows]
            if (
                any(row["task"] != task or row["run"] != run or row["parent"] != parent for row in rows)
                or actual_hashes != expected_hashes
            ):
                raise InputError("selected card identity/hash differs from support receipt")
            calibration = parent == calibration_parent[task]
            context = {
                "schema_version": SCHEMA, "support_sha256": EXPECTED_SUPPORT_SHA256,
                "cards_sha256": EXPECTED_CARDS_SHA256, "task": task,
                "source_run_id": run, "parent_id": parent, "sibling_ids": child_ids,
                "sibling_code_sha256": actual_hashes, "selection_key": source["selection_key"],
                "calibration_parent": calibration,
            }
            contract_sha = sha_bytes(canon(context))
            anchor_id = sha_bytes(canon({
                "schema_version": SCHEMA, "domain": "anchor-id",
                "task": task, "source_run_id": run, "parent_id": parent,
            }))
            if anchor_id == contract_sha:
                raise InputError("anchor identity and contract hash unexpectedly collide")
            public_rows.append({
                **context, "anchor_id": anchor_id, "anchor_contract_sha256": contract_sha,
            })
            run_ids.add(run)
            for card_id, row in zip(child_ids, rows):
                anchors.append({
                    "anchor_id": anchor_id, "task": task, "source_run_id": run,
                    "parent_id": parent, "sibling_id": card_id,
                    "code_sha256": row["code_sha256"],
                    "anchor_contract_sha256": contract_sha,
                })
                vault.append({
                    "sibling_id": card_id, "code": row["code"], "code_sha256": row["code_sha256"],
                })
                code_hashes.add(row["code_sha256"])
    if len(anchors) != 48 or len(vault) != 48 or len(code_hashes) != 48 or len(run_ids) != 24:
        raise InputError("materialized anchor/vault/run uniqueness differs")
    calibration_ids = [row["anchor_id"] for row in public_rows if row["calibration_parent"]]
    if len(calibration_ids) != 6:
        raise InputError("calibration anchor count differs")
    output = pathlib.Path(args.output)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise InputError("output must be a new absolute path")
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if staging.exists() or staging.is_symlink():
        raise InputError("staging path exists")
    staging.mkdir(parents=True)
    try:
        atomic_jsonl(staging / "anchors.jsonl", anchors)
        atomic_jsonl(staging / "code_vault.jsonl", vault, mode=0o600)
        atomic_json(staging / "selected_public.json", public_rows)
        atomic_json(staging / "calibration_anchor_ids.json", calibration_ids)
        summary = {
            "schema_version": SCHEMA, "status": "E2A_INPUTS_FROZEN_OUTCOME_BLIND",
            "support_sha256": EXPECTED_SUPPORT_SHA256, "cards_sha256": EXPECTED_CARDS_SHA256,
            "tasks": list(TASKS), "task_count": 6, "parents_per_task": 4,
            "anchor_count": 24, "physical_run_count": 24, "sibling_count": 48,
            "calibration_anchor_count": 6, "broad_replicates": 1,
            "calibration_replicates": 2, "contains_outcomes": False,
            "scientific_outcomes_read": False, "official_test_read": False,
            "first960_or_prospective_read": False,
            "anchors_sha256": sha(staging / "anchors.jsonl"),
            "code_vault_sha256": sha(staging / "code_vault.jsonl"),
            "selected_public_sha256": sha(staging / "selected_public.json"),
            "calibration_anchor_ids_sha256": sha(staging / "calibration_anchor_ids.json"),
        }
        atomic_json(staging / "summary.json", summary)
        atomic_json(staging / "sha256_manifest.json", recursive_manifest(staging))
        os.replace(staging, output)
    except BaseException:
        if staging.exists(): shutil.rmtree(staging)
        raise
    print(canon(summary).decode("utf-8"))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--support", required=True); ap.add_argument("--cards", required=True)
    ap.add_argument("--output", required=True)
    return ap


def main() -> int:
    try:
        build(parser().parse_args())
    except (InputError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"E2A_INPUT_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
