"""Independent verifier for the frozen E2-A 24-parent input/code vault."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import stat
import tempfile
from collections import Counter
from typing import Any


SCHEMA = "balanced-continuation-e2a-inputs-v1"
SUPPORT_SHA = "7ffb23a7577640ef61730d214f7cccd6b3c202b07356a864885b41b46ec98ac0"
CARDS_SHA = "6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75"
CARD_ROWS = 16012
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


class VerifyError(RuntimeError):
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


def read_json(path: pathlib.Path) -> Any:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    return json.loads(raw)


def read_jsonl(path: pathlib.Path, permit_code: bool = False) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    rows = []
    for index, line in enumerate(raw.splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise VerifyError(f"non-object row in {path.name}:{index}")
        if not permit_code and "code" in value:
            raise VerifyError(f"unexpected code bytes in public artifact: {path.name}")
        rows.append(value)
    return rows


def load_cards(path: pathlib.Path, selected: set[str]) -> dict[str, dict[str, str]]:
    if not path.is_file() or path.is_symlink() or sha(path) != CARDS_SHA:
        raise VerifyError("cards source path/hash differs")
    result = {}
    row_count = 0
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, 1):
            row_count += 1
            row = json.loads(line)
            card_id = row.get("id") if isinstance(row, dict) else None
            if card_id not in selected:
                continue
            task_obj = row.get("task"); lineage = row.get("lineage") or {}
            run = row.get("run_id"); code = row.get("code")
            if (
                not isinstance(task_obj, dict) or not isinstance(task_obj.get("name"), str)
                or not isinstance(lineage, dict) or not isinstance(lineage.get("parent_id"), str)
                or not isinstance(run, str) or not run or not isinstance(code, str) or not code
            ):
                raise VerifyError(f"selected card schema differs: {index}")
            if CREDENTIAL.search(code.encode("utf-8")):
                raise VerifyError("credential-shaped bytes in selected card")
            result[card_id] = {
                "task": task_obj["name"], "run": run, "parent": lineage["parent_id"],
                "code": code, "code_sha256": sha_bytes(code.encode("utf-8")),
            }
    if row_count != CARD_ROWS or set(result) != selected:
        raise VerifyError("card count or selected coverage differs")
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


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise VerifyError("verification receipt must not pre-exist")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canon(value) + b"\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()


def verify(args: argparse.Namespace) -> dict[str, Any]:
    support_path = pathlib.Path(args.support).resolve()
    if not support_path.is_file() or support_path.is_symlink() or sha(support_path) != SUPPORT_SHA:
        raise VerifyError("support receipt path/hash differs")
    support = read_json(support_path)
    source_rows = support.get("selected_anchors") if isinstance(support, dict) else None
    if not isinstance(source_rows, list) or len(source_rows) != 24:
        raise VerifyError("support selected-anchor rows differ")
    result = pathlib.Path(args.result).resolve()
    if not result.is_dir() or result.is_symlink():
        raise VerifyError("input result root differs")
    expected_names = {
        "anchors.jsonl", "code_vault.jsonl", "selected_public.json",
        "calibration_anchor_ids.json", "summary.json", "sha256_manifest.json",
    }
    if {path.name for path in result.iterdir()} != expected_names:
        raise VerifyError("input result membership differs")
    anchors = read_jsonl(result / "anchors.jsonl")
    vault = read_jsonl(result / "code_vault.jsonl", permit_code=True)
    public = read_json(result / "selected_public.json")
    calibration_ids = read_json(result / "calibration_anchor_ids.json")
    if (
        not isinstance(public, list) or len(public) != 24
        or not isinstance(calibration_ids, list) or len(calibration_ids) != 6
        or len(anchors) != 48 or len(vault) != 48
    ):
        raise VerifyError("input artifact row counts differ")
    if os.name == "posix" and stat.S_IMODE((result / "code_vault.jsonl").stat().st_mode) != 0o600:
        raise VerifyError("code vault mode differs")
    support_by_identity = {
        (row["task"], row["physical_run_id"], row["parent_id"]): row for row in source_rows
    }
    if len(support_by_identity) != 24:
        raise VerifyError("support identities are duplicated")
    selected_ids = {item for row in source_rows for item in row["sibling_ids"]}
    cards = load_cards(pathlib.Path(args.cards).resolve(), selected_ids)
    anchor_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in anchors:
        if set(row) != {
            "anchor_id", "task", "source_run_id", "parent_id", "sibling_id",
            "code_sha256", "anchor_contract_sha256",
        }:
            raise VerifyError("anchor row schema differs")
        anchor_by_id.setdefault(row["anchor_id"], []).append(row)
    vault_by_id = {}
    for row in vault:
        if set(row) != {"sibling_id", "code", "code_sha256"} or row["sibling_id"] in vault_by_id:
            raise VerifyError("code-vault schema/identity differs")
        if sha_bytes(row["code"].encode("utf-8")) != row["code_sha256"]:
            raise VerifyError("code-vault row hash differs")
        vault_by_id[row["sibling_id"]] = row
    if set(vault_by_id) != selected_ids or len(anchor_by_id) != 24:
        raise VerifyError("vault/anchor coverage differs")
    expected_calibration = []
    seen_runs: set[str] = set()
    expected_public = []
    for task in TASKS:
        task_sources = sorted(
            [row for row in source_rows if row["task"] == task], key=lambda row: row["selection_key"]
        )
        if len(task_sources) != 4:
            raise VerifyError(f"support task balance differs: {task}")
        calibration_parent = task_sources[0]["parent_id"]
        for source in task_sources:
            run, parent = source["physical_run_id"], source["parent_id"]
            sibling_ids = source["sibling_ids"]
            hashes = source["sibling_code_sha256"]
            calibration = parent == calibration_parent
            context = {
                "schema_version": SCHEMA, "support_sha256": SUPPORT_SHA,
                "cards_sha256": CARDS_SHA, "task": task, "source_run_id": run,
                "parent_id": parent, "sibling_ids": sibling_ids,
                "sibling_code_sha256": hashes, "selection_key": source["selection_key"],
                "calibration_parent": calibration,
            }
            contract_sha = sha_bytes(canon(context))
            anchor_id = sha_bytes(canon({
                "schema_version": SCHEMA, "domain": "anchor-id", "task": task,
                "source_run_id": run, "parent_id": parent,
            }))
            expected_public.append({
                **context, "anchor_id": anchor_id, "anchor_contract_sha256": contract_sha,
            })
            if calibration: expected_calibration.append(anchor_id)
            sibling_rows = anchor_by_id.get(anchor_id, [])
            if len(sibling_rows) != 2 or {row["sibling_id"] for row in sibling_rows} != set(sibling_ids):
                raise VerifyError("anchor exact-two coverage differs")
            for sibling_id, expected_hash in zip(sibling_ids, hashes):
                card = cards[sibling_id]; vault_row = vault_by_id[sibling_id]
                if (
                    card["task"] != task or card["run"] != run or card["parent"] != parent
                    or card["code_sha256"] != expected_hash or vault_row["code_sha256"] != expected_hash
                    or vault_row["code"] != card["code"]
                ):
                    raise VerifyError("card/support/vault binding differs")
                anchor_row = next(row for row in sibling_rows if row["sibling_id"] == sibling_id)
                if anchor_row != {
                    "anchor_id": anchor_id, "task": task, "source_run_id": run,
                    "parent_id": parent, "sibling_id": sibling_id,
                    "code_sha256": expected_hash, "anchor_contract_sha256": contract_sha,
                }:
                    raise VerifyError("anchor row binding differs")
            if run in seen_runs:
                raise VerifyError("physical run reused across E2-A anchors")
            seen_runs.add(run)
    if public != expected_public or calibration_ids != expected_calibration:
        raise VerifyError("public selection/calibration identities differ")
    if len(seen_runs) != 24 or Counter(row["task"] for row in public) != Counter({task: 4 for task in TASKS}):
        raise VerifyError("run/task balance differs")
    summary = read_json(result / "summary.json")
    expected_summary = {
        "schema_version": SCHEMA, "status": "E2A_INPUTS_FROZEN_OUTCOME_BLIND",
        "support_sha256": SUPPORT_SHA, "cards_sha256": CARDS_SHA, "tasks": list(TASKS),
        "task_count": 6, "parents_per_task": 4, "anchor_count": 24,
        "physical_run_count": 24, "sibling_count": 48, "calibration_anchor_count": 6,
        "broad_replicates": 1, "calibration_replicates": 2,
        "contains_outcomes": False, "scientific_outcomes_read": False,
        "official_test_read": False, "first960_or_prospective_read": False,
        "anchors_sha256": sha(result / "anchors.jsonl"),
        "code_vault_sha256": sha(result / "code_vault.jsonl"),
        "selected_public_sha256": sha(result / "selected_public.json"),
        "calibration_anchor_ids_sha256": sha(result / "calibration_anchor_ids.json"),
    }
    if summary != expected_summary:
        raise VerifyError("input summary differs")
    if read_json(result / "sha256_manifest.json") != recursive_manifest(result):
        raise VerifyError("input recursive manifest differs")
    receipt = {
        "schema_version": "balanced-continuation-e2a-input-verification-v1",
        "status": "VERIFIED_E2A_INPUTS_OUTCOME_BLIND_DISTINCT_RUNS",
        "producer_imported": False, "support_sha256": SUPPORT_SHA,
        "cards_sha256": CARDS_SHA, "tasks": list(TASKS), "anchors": 24,
        "physical_runs": 24, "siblings": 48, "calibration_anchors": 6,
        "scientific_outcomes_read": False, "official_test_read": False,
        "first960_or_prospective_read": False,
        "result_manifest_sha256": sha(result / "sha256_manifest.json"),
    }
    atomic_json(pathlib.Path(args.receipt).resolve(), receipt)
    print(canon(receipt).decode("utf-8"))
    return receipt


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--support", required=True); ap.add_argument("--cards", required=True)
    ap.add_argument("--result", required=True); ap.add_argument("--receipt", required=True)
    return ap


def main() -> int:
    try:
        verify(parser().parse_args())
    except (VerifyError, OSError, UnicodeError, json.JSONDecodeError, KeyError, StopIteration) as exc:
        print(f"E2A_INPUT_VERIFY_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
