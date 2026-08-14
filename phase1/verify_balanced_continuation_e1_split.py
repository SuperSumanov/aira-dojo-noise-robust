"""Independent reconstruction verifier for the E1 80/10/10 data boundary."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import stat
import tempfile
from collections import defaultdict
from typing import Any, Iterator


SCHEMA = "balanced-continuation-e1-split-v1"
SEED = 20260814
TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")
SPECS: dict[str, dict[str, Any]] = {
    "spaceship-titanic": {
        "id": "PassengerId", "target": "Transported", "metric": "accuracy",
        "orientation": 1, "default": "False", "labels": {"True", "False"},
        "rows": 7823,
        "train_sha": "d852203bbc5e603b92a7cfc0b46e23277c43d7a910b1db8b0ad58b7c6e3f2baa",
        "description_sha": "ee35380587404b263ef8b38d9a2fff4196563abb2e12bc086b02c9808b7f37cb",
    },
    "tabular-playground-series-may-2022": {
        "id": "id", "target": "target", "metric": "roc_auc", "orientation": 1,
        "default": "0.5", "labels": {"0", "1"}, "rows": 800000,
        "train_sha": "f0940d6a4c3536752bdc3ba99251fc3020662ea43b28dfad520d810b3cde5514",
        "description_sha": "a64340a1c829f6e2c3ee8411cfa3089a4418571fee7186c91b5be2ef241bfcff",
    },
}


class VerifySplitError(RuntimeError):
    pass


def canon(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def key(task: str, row_id: str, index: int) -> bytes:
    return hashlib.sha256(f"{SCHEMA}|{SEED}|{task}|{row_id}|{index}".encode()).digest()


def source_files(root: pathlib.Path, task: str) -> tuple[pathlib.Path, pathlib.Path]:
    authorized = root / task / "prepared" / "public"
    return authorized / "train.csv", authorized / "description.md"


def allocate(path: pathlib.Path, task: str) -> tuple[bytearray, dict[str, Any], list[str]]:
    spec = SPECS[task]
    strata: dict[str, list[tuple[bytes, int]]] = defaultdict(list)
    ids: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        if len(header) != len(set(header)) or spec["id"] not in header or spec["target"] not in header:
            raise VerifySplitError(f"source header differs: {task}")
        count = 0
        for index, row in enumerate(reader):
            row_id, label = row[spec["id"]], row[spec["target"]]
            if not row_id or row_id in ids or label not in spec["labels"]:
                raise VerifySplitError(f"source identity/label differs: {task}:{index}")
            ids.add(row_id)
            strata[label].append((key(task, row_id, index), index))
            count += 1
    if count != spec["rows"] or set(strata) != set(spec["labels"]):
        raise VerifySplitError(f"source rows/strata differ: {task}")
    roles = bytearray(count)
    classes: dict[str, dict[str, int]] = {}
    for label in sorted(strata):
        ranked = sorted(strata[label])
        n_search = len(ranked) // 10
        n_val = len(ranked) // 10
        for _, index in ranked[:n_search]:
            roles[index] = 1
        for _, index in ranked[n_search : n_search + n_val]:
            roles[index] = 2
        classes[label] = {
            "source": len(ranked),
            "train": len(ranked) - n_search - n_val,
            "dsearch": n_search,
            "dval": n_val,
        }
    counts = {
        "source": count,
        "train": roles.count(0),
        "dsearch": roles.count(1),
        "dval": roles.count(2),
        "classes": classes,
    }
    return roles, counts, header


def next_or_fail(reader: Iterator[dict[str, str]], label: str) -> dict[str, str]:
    try:
        return next(reader)
    except StopIteration as exc:
        raise VerifySplitError(f"generated {label} ended early") from exc


def verify_task(root: pathlib.Path, source_root: pathlib.Path, task: str) -> dict[str, Any]:
    spec = SPECS[task]
    source_train, source_description = source_files(source_root, task)
    if sha_file(source_train) != spec["train_sha"] or sha_file(source_description) != spec["description_sha"]:
        raise VerifySplitError(f"source hash differs: {task}")
    roles, counts, header = allocate(source_train, task)
    feature_header = [name for name in header if name != spec["target"]]
    public = root / "public" / task
    paths = {
        "train": public / "train.csv",
        "test": public / "test.csv",
        "sample": public / "sample_submission.csv",
        "description": public / "description.md",
        "dsearch": root / "private" / "dsearch" / f"{task}.csv",
        "dval": root / "private" / "dval" / f"{task}.csv",
    }
    if any(not path.is_file() for path in paths.values()):
        raise VerifySplitError(f"generated task file missing: {task}")
    if paths["description"].read_bytes() != source_description.read_bytes():
        raise VerifySplitError(f"description bytes differ: {task}")
    if os.name == "posix":
        for role in ("train", "test", "sample", "description"):
            if stat.S_IMODE(paths[role].stat().st_mode) != 0o444:
                raise VerifySplitError(f"public file mode differs: {task}/{role}")
        for role in ("dsearch", "dval"):
            if stat.S_IMODE(paths[role].stat().st_mode) != 0o600:
                raise VerifySplitError(f"private file mode differs: {task}/{role}")

    membership = hashlib.sha256()
    with (
        source_train.open("r", encoding="utf-8-sig", newline="") as source_handle,
        paths["train"].open("r", encoding="utf-8", newline="") as train_handle,
        paths["test"].open("r", encoding="utf-8", newline="") as test_handle,
        paths["sample"].open("r", encoding="utf-8", newline="") as sample_handle,
        paths["dsearch"].open("r", encoding="utf-8", newline="") as dsearch_handle,
        paths["dval"].open("r", encoding="utf-8", newline="") as dval_handle,
    ):
        source_reader = csv.DictReader(source_handle)
        generated = {
            "train": iter(csv.DictReader(train_handle)),
            "test": iter(csv.DictReader(test_handle)),
            "sample": iter(csv.DictReader(sample_handle)),
            "dsearch": iter(csv.DictReader(dsearch_handle)),
            "dval": iter(csv.DictReader(dval_handle)),
        }
        if list(source_reader.fieldnames or []) != header:
            raise VerifySplitError("source header changed between passes")
        # Re-opened reader objects expose their headers through the iterator's instance.
        train_reader = generated["train"]
        test_reader = generated["test"]
        sample_reader = generated["sample"]
        dsearch_reader = generated["dsearch"]
        dval_reader = generated["dval"]
        # DictReader iterators are the DictReader objects themselves.
        if list(train_reader.fieldnames or []) != header:
            raise VerifySplitError(f"generated train header differs: {task}")
        if list(test_reader.fieldnames or []) != feature_header:
            raise VerifySplitError(f"generated test header differs: {task}")
        expected_label_header = [spec["id"], spec["target"]]
        if list(sample_reader.fieldnames or []) != expected_label_header:
            raise VerifySplitError(f"generated sample header differs: {task}")
        if list(dsearch_reader.fieldnames or []) != expected_label_header or list(dval_reader.fieldnames or []) != expected_label_header:
            raise VerifySplitError(f"generated private header differs: {task}")

        for index, source_row in enumerate(source_reader):
            role = int(roles[index])
            role_name = ("train", "dsearch", "dval")[role]
            membership.update(canon({
                "id": source_row[spec["id"]], "role": role_name, "source_index": index
            }) + b"\n")
            if role == 0:
                if next_or_fail(train_reader, f"{task}/train") != source_row:
                    raise VerifySplitError(f"generated train row differs: {task}:{index}")
                continue
            expected_test = {name: source_row[name] for name in feature_header}
            expected_sample = {
                spec["id"]: source_row[spec["id"]], spec["target"]: spec["default"]
            }
            expected_label = {
                spec["id"]: source_row[spec["id"]], spec["target"]: source_row[spec["target"]]
            }
            if next_or_fail(test_reader, f"{task}/test") != expected_test:
                raise VerifySplitError(f"generated test row differs: {task}:{index}")
            if next_or_fail(sample_reader, f"{task}/sample") != expected_sample:
                raise VerifySplitError(f"generated sample row differs: {task}:{index}")
            if next_or_fail(generated[role_name], f"{task}/{role_name}") != expected_label:
                raise VerifySplitError(f"generated private row differs: {task}:{index}")
        for label, reader in generated.items():
            try:
                next(reader)
            except StopIteration:
                continue
            raise VerifySplitError(f"generated {task}/{label} has extra rows")

    return {
        "task": task,
        "id_column": spec["id"],
        "target_column": spec["target"],
        "metric": spec["metric"],
        "orientation": spec["orientation"],
        "sample_default": spec["default"],
        "split_seed": SEED,
        "source_train_sha256": spec["train_sha"],
        "source_description_sha256": spec["description_sha"],
        "source_inputs_opened": ["train.csv", "description.md"],
        "official_test_opened": False,
        "private_answers_opened": False,
        "counts": counts,
        "membership_sha256": membership.hexdigest(),
        "public_file_sha256": {
            "train.csv": sha_file(paths["train"]),
            "test.csv": sha_file(paths["test"]),
            "sample_submission.csv": sha_file(paths["sample"]),
            "description.md": sha_file(paths["description"]),
        },
        "private_label_sha256": {
            "dsearch": sha_file(paths["dsearch"]), "dval": sha_file(paths["dval"])
        },
    }


def manifest(root: pathlib.Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "sha256_manifest.json":
            output[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size,
                "mode": stat.S_IMODE(path.stat().st_mode),
                "sha256": sha_file(path),
            }
    return output


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
    root = pathlib.Path(args.result).resolve()
    source_root = pathlib.Path(args.source_root).resolve()
    if not root.is_dir() or not source_root.is_dir():
        raise VerifySplitError("result/source root is missing")
    contracts = [verify_task(root, source_root, task) for task in TASKS]
    expected_public = {
        "schema_version": "balanced-continuation-public-dataset-contract-v1",
        "split_schema_version": SCHEMA,
        "split_seed": SEED,
        "tasks": [
            {key: contract[key] for key in (
                "task", "id_column", "target_column", "metric", "orientation", "counts",
                "membership_sha256", "public_file_sha256", "source_train_sha256",
                "source_description_sha256",
            )}
            for contract in contracts
        ],
        "candidate_visible_roles": ["D_train", "unlabeled_D_search_plus_D_val"],
        "official_test_materialized": False,
        "private_labels_under_public_root": False,
    }
    public_path = root / "public_dataset_contract.json"
    if json.loads(public_path.read_bytes()) != expected_public:
        raise VerifySplitError("public dataset contract differs")
    public_sha = sha_file(public_path)
    expected_split = {
        "schema_version": SCHEMA,
        "split_seed": SEED,
        "policy": "80/10/10_stratified_floor_per_class",
        "tasks": contracts,
        "public_dataset_contract_sha256": public_sha,
        "dtest_rows_read": 0,
        "official_test_materialized": False,
        "private_answers_read": False,
    }
    split_path = root / "split_manifest_opaque.json"
    if json.loads(split_path.read_bytes()) != expected_split:
        raise VerifySplitError("opaque split manifest differs")
    if os.name == "posix" and stat.S_IMODE(split_path.stat().st_mode) != 0o600:
        raise VerifySplitError("opaque split manifest is not mode 0600")
    split_sha = sha_file(split_path)
    summary = json.loads((root / "summary.json").read_bytes())
    expected_summary = {
        "schema_version": SCHEMA,
        "status": "VERIFIED_E1_80_10_10_SPLIT_BUILT",
        "split_seed": SEED,
        "task_count": 2,
        "tasks": list(TASKS),
        "public_dataset_contract_sha256": public_sha,
        "split_manifest_sha256_opaque": split_sha,
        "dtest_rows_read": 0,
        "private_answers_read": False,
        "source_inputs_per_task": ["train.csv", "description.md"],
        "counts": {contract["task"]: contract["counts"] for contract in contracts},
    }
    if summary != expected_summary:
        raise VerifySplitError("split summary differs")
    stored_manifest = json.loads((root / "sha256_manifest.json").read_bytes())
    if stored_manifest != manifest(root):
        raise VerifySplitError("recursive split artifact manifest differs")
    receipt = {
        "schema_version": "balanced-continuation-e1-split-verification-v1",
        "status": "VERIFIED_E1_SPLIT_RECONSTRUCTION_NO_DTEST_READ",
        "producer_imported": False,
        "tasks": list(TASKS),
        "counts": expected_summary["counts"],
        "public_dataset_contract_sha256": public_sha,
        "split_manifest_sha256_opaque": split_sha,
        "dtest_rows_read": 0,
        "private_answers_read": False,
        "result_manifest_sha256": sha_file(root / "sha256_manifest.json"),
    }
    receipt_path = pathlib.Path(args.receipt).resolve()
    if receipt_path.exists() or receipt_path.is_symlink():
        raise VerifySplitError("verification receipt must not pre-exist")
    atomic_json(receipt_path, receipt)
    print(canon(receipt).decode())
    return receipt


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--receipt", required=True)
    return ap


def main() -> int:
    try:
        verify(parser().parse_args())
    except (VerifySplitError, OSError, UnicodeError, csv.Error, json.JSONDecodeError) as exc:
        print(f"E1_SPLIT_VERIFY_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
