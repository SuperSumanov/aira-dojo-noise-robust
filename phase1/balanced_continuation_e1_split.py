"""Build the label-isolated 80/10/10 datasets for balanced-continuation E1.

Only each task's public ``train.csv`` and ``description.md`` are opened.  The original
competition test file and private answers are neither accepted as arguments nor named in
the implementation.  Held-out rows become a generated unlabeled test table; D_search and
D_val labels live outside the candidate-visible root.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import shutil
import stat
import tempfile
from collections import defaultdict
from typing import Any


SCHEMA = "balanced-continuation-e1-split-v1"
SPLIT_SEED = 20260814
TASK_ORDER = ("spaceship-titanic", "tabular-playground-series-may-2022")
TASK_SPECS: dict[str, dict[str, Any]] = {
    "spaceship-titanic": {
        "id_column": "PassengerId",
        "target_column": "Transported",
        "metric": "accuracy",
        "orientation": 1,
        "sample_default": "False",
        "allowed_labels": {"True", "False"},
        "source_rows": 7823,
        "train_sha256": "d852203bbc5e603b92a7cfc0b46e23277c43d7a910b1db8b0ad58b7c6e3f2baa",
        "description_sha256": "ee35380587404b263ef8b38d9a2fff4196563abb2e12bc086b02c9808b7f37cb",
    },
    "tabular-playground-series-may-2022": {
        "id_column": "id",
        "target_column": "target",
        "metric": "roc_auc",
        "orientation": 1,
        "sample_default": "0.5",
        "allowed_labels": {"0", "1"},
        "source_rows": 800000,
        "train_sha256": "f0940d6a4c3536752bdc3ba99251fc3020662ea43b28dfad520d810b3cde5514",
        "description_sha256": "a64340a1c829f6e2c3ee8411cfa3089a4418571fee7186c91b5be2ef241bfcff",
    },
}


class SplitError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: pathlib.Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_bytes(path: pathlib.Path, raw: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        if mode is not None:
            os.chmod(path, mode)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_json(path: pathlib.Path, value: Any, mode: int | None = None) -> None:
    atomic_bytes(path, canonical_json(value) + b"\n", mode=mode)


def deterministic_key(task: str, row_id: str, source_index: int) -> bytes:
    return hashlib.sha256(
        f"{SCHEMA}|{SPLIT_SEED}|{task}|{row_id}|{source_index}".encode("utf-8")
    ).digest()


def source_paths(source_root: pathlib.Path, task: str) -> tuple[pathlib.Path, pathlib.Path]:
    # Deliberately return only the two authorized inputs.
    public = source_root / task / "prepared" / "public"
    return public / "train.csv", public / "description.md"


def validate_source(source_root: pathlib.Path, task: str) -> tuple[pathlib.Path, pathlib.Path]:
    train_path, description_path = source_paths(source_root, task)
    spec = TASK_SPECS[task]
    for path, key in ((train_path, "train_sha256"), (description_path, "description_sha256")):
        if not path.is_file():
            raise SplitError(f"authorized source is missing: {path}")
        actual = file_sha256(path)
        if actual != spec[key]:
            raise SplitError(f"{task} {path.name} SHA differs: {actual}")
    return train_path, description_path


def allocate_roles(train_path: pathlib.Path, task: str) -> tuple[bytearray, dict[str, Any], list[str]]:
    spec = TASK_SPECS[task]
    id_column = spec["id_column"]
    target_column = spec["target_column"]
    strata: dict[str, list[tuple[bytes, int]]] = defaultdict(list)
    seen_ids: set[str] = set()
    row_count = 0
    with train_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise SplitError(f"{task} has invalid CSV header")
        header = list(reader.fieldnames)
        if id_column not in header or target_column not in header:
            raise SplitError(f"{task} id/target column is missing")
        for source_index, row in enumerate(reader):
            if None in row or set(row) != set(header):
                raise SplitError(f"{task} malformed source row {source_index}")
            row_id = row[id_column]
            label = row[target_column]
            if not row_id or row_id in seen_ids:
                raise SplitError(f"{task} empty or duplicate id at row {source_index}")
            if label not in spec["allowed_labels"]:
                raise SplitError(f"{task} unexpected target value at row {source_index}")
            seen_ids.add(row_id)
            strata[label].append((deterministic_key(task, row_id, source_index), source_index))
            row_count += 1
    if row_count != spec["source_rows"]:
        raise SplitError(f"{task} source row count differs: {row_count}")
    if set(strata) != set(spec["allowed_labels"]):
        raise SplitError(f"{task} target strata differ")

    roles = bytearray(row_count)  # 0=train, 1=D_search, 2=D_val
    class_counts: dict[str, dict[str, int]] = {}
    for label in sorted(strata):
        ranked = sorted(strata[label])
        count = len(ranked)
        if count < 20:
            raise SplitError(f"{task} stratum {label} is too small for 80/10/10")
        n_search = count // 10
        n_val = count // 10
        for _, source_index in ranked[:n_search]:
            roles[source_index] = 1
        for _, source_index in ranked[n_search : n_search + n_val]:
            roles[source_index] = 2
        class_counts[label] = {
            "source": count,
            "train": count - n_search - n_val,
            "dsearch": n_search,
            "dval": n_val,
        }
    counts = {
        "source": row_count,
        "train": roles.count(0),
        "dsearch": roles.count(1),
        "dval": roles.count(2),
        "classes": class_counts,
    }
    if counts["train"] + counts["dsearch"] + counts["dval"] != row_count:
        raise SplitError("split role counts do not cover the source")
    return roles, counts, header


def write_task(
    staging: pathlib.Path,
    source_root: pathlib.Path,
    task: str,
) -> dict[str, Any]:
    train_source, description_source = validate_source(source_root, task)
    roles, counts, header = allocate_roles(train_source, task)
    spec = TASK_SPECS[task]
    id_column = spec["id_column"]
    target_column = spec["target_column"]
    feature_header = [name for name in header if name != target_column]
    public = staging / "public" / task
    private_search = staging / "private" / "dsearch"
    private_val = staging / "private" / "dval"
    public.mkdir(parents=True)
    private_search.mkdir(parents=True, exist_ok=True)
    private_val.mkdir(parents=True, exist_ok=True)
    output_paths = {
        "train": public / "train.csv",
        "test": public / "test.csv",
        "sample": public / "sample_submission.csv",
        "dsearch": private_search / f"{task}.csv",
        "dval": private_val / f"{task}.csv",
    }
    membership = hashlib.sha256()
    role_counts = {0: 0, 1: 0, 2: 0}
    with (
        train_source.open("r", encoding="utf-8-sig", newline="") as source_handle,
        output_paths["train"].open("x", encoding="utf-8", newline="") as train_handle,
        output_paths["test"].open("x", encoding="utf-8", newline="") as test_handle,
        output_paths["sample"].open("x", encoding="utf-8", newline="") as sample_handle,
        output_paths["dsearch"].open("x", encoding="utf-8", newline="") as dsearch_handle,
        output_paths["dval"].open("x", encoding="utf-8", newline="") as dval_handle,
    ):
        reader = csv.DictReader(source_handle)
        writers = {
            "train": csv.DictWriter(train_handle, fieldnames=header, lineterminator="\n"),
            "test": csv.DictWriter(test_handle, fieldnames=feature_header, lineterminator="\n"),
            "sample": csv.DictWriter(
                sample_handle, fieldnames=[id_column, target_column], lineterminator="\n"
            ),
            "dsearch": csv.DictWriter(
                dsearch_handle, fieldnames=[id_column, target_column], lineterminator="\n"
            ),
            "dval": csv.DictWriter(
                dval_handle, fieldnames=[id_column, target_column], lineterminator="\n"
            ),
        }
        for writer in writers.values():
            writer.writeheader()
        for source_index, row in enumerate(reader):
            role = int(roles[source_index])
            role_counts[role] += 1
            role_name = ("train", "dsearch", "dval")[role]
            membership.update(
                canonical_json({"id": row[id_column], "role": role_name, "source_index": source_index})
                + b"\n"
            )
            if role == 0:
                writers["train"].writerow(row)
                continue
            writers["test"].writerow({name: row[name] for name in feature_header})
            writers["sample"].writerow(
                {id_column: row[id_column], target_column: spec["sample_default"]}
            )
            writers[role_name].writerow(
                {id_column: row[id_column], target_column: row[target_column]}
            )
        for handle in (train_handle, test_handle, sample_handle, dsearch_handle, dval_handle):
            handle.flush()
            os.fsync(handle.fileno())
    if [role_counts[index] for index in range(3)] != [
        counts["train"], counts["dsearch"], counts["dval"]
    ]:
        raise SplitError(f"{task} write counts differ from allocation")

    description = public / "description.md"
    shutil.copyfile(description_source, description)
    for path in (output_paths["train"], output_paths["test"], output_paths["sample"], description):
        os.chmod(path, 0o444)
    for path in (output_paths["dsearch"], output_paths["dval"]):
        os.chmod(path, 0o600)
    os.chmod(public, 0o555)

    public_hashes = {
        "train.csv": file_sha256(output_paths["train"]),
        "test.csv": file_sha256(output_paths["test"]),
        "sample_submission.csv": file_sha256(output_paths["sample"]),
        "description.md": file_sha256(description),
    }
    private_hashes = {
        "dsearch": file_sha256(output_paths["dsearch"]),
        "dval": file_sha256(output_paths["dval"]),
    }
    return {
        "task": task,
        "id_column": id_column,
        "target_column": target_column,
        "metric": spec["metric"],
        "orientation": spec["orientation"],
        "sample_default": spec["sample_default"],
        "split_seed": SPLIT_SEED,
        "source_train_sha256": spec["train_sha256"],
        "source_description_sha256": spec["description_sha256"],
        "source_inputs_opened": ["train.csv", "description.md"],
        "official_test_opened": False,
        "private_answers_opened": False,
        "counts": counts,
        "membership_sha256": membership.hexdigest(),
        "public_file_sha256": public_hashes,
        "private_label_sha256": private_hashes,
    }


def recursive_manifest(root: pathlib.Path) -> dict[str, dict[str, Any]]:
    value: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "sha256_manifest.json":
            value[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size,
                "mode": stat.S_IMODE(path.stat().st_mode),
                "sha256": file_sha256(path),
            }
    return value


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_root = pathlib.Path(args.source_root).resolve()
    output = pathlib.Path(args.output)
    if not source_root.is_dir():
        raise SplitError("source root is missing")
    if not output.is_absolute():
        raise SplitError("output must be absolute")
    if output.exists() or output.is_symlink():
        raise SplitError("output must not pre-exist")
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if staging.exists() or staging.is_symlink():
        raise SplitError("staging path already exists")
    staging.mkdir(parents=True)
    try:
        (staging / "private").mkdir()
        os.chmod(staging / "private", 0o700)
        task_contracts = [write_task(staging, source_root, task) for task in TASK_ORDER]
        public_contract = {
            "schema_version": "balanced-continuation-public-dataset-contract-v1",
            "split_schema_version": SCHEMA,
            "split_seed": SPLIT_SEED,
            "tasks": [
                {
                    key: contract[key]
                    for key in (
                        "task", "id_column", "target_column", "metric", "orientation",
                        "counts", "membership_sha256", "public_file_sha256",
                        "source_train_sha256", "source_description_sha256",
                    )
                }
                for contract in task_contracts
            ],
            "candidate_visible_roles": ["D_train", "unlabeled_D_search_plus_D_val"],
            "official_test_materialized": False,
            "private_labels_under_public_root": False,
        }
        atomic_json(staging / "public_dataset_contract.json", public_contract)
        public_contract_sha = file_sha256(staging / "public_dataset_contract.json")
        split_manifest = {
            "schema_version": SCHEMA,
            "split_seed": SPLIT_SEED,
            "policy": "80/10/10_stratified_floor_per_class",
            "tasks": task_contracts,
            "public_dataset_contract_sha256": public_contract_sha,
            "dtest_rows_read": 0,
            "official_test_materialized": False,
            "private_answers_read": False,
        }
        atomic_json(staging / "split_manifest_opaque.json", split_manifest, mode=0o600)
        split_sha = file_sha256(staging / "split_manifest_opaque.json")
        summary = {
            "schema_version": SCHEMA,
            "status": "VERIFIED_E1_80_10_10_SPLIT_BUILT",
            "split_seed": SPLIT_SEED,
            "task_count": len(TASK_ORDER),
            "tasks": list(TASK_ORDER),
            "public_dataset_contract_sha256": public_contract_sha,
            "split_manifest_sha256_opaque": split_sha,
            "dtest_rows_read": 0,
            "private_answers_read": False,
            "source_inputs_per_task": ["train.csv", "description.md"],
            "counts": {contract["task"]: contract["counts"] for contract in task_contracts},
        }
        atomic_json(staging / "summary.json", summary)
        atomic_json(staging / "sha256_manifest.json", recursive_manifest(staging))
        os.replace(staging, output)
    except BaseException:
        if staging.exists():
            # The output is still unpromoted; preserve nothing that could be mistaken for a release.
            shutil.rmtree(staging)
        raise
    print(canonical_json(summary).decode("utf-8"))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--output", required=True)
    return ap


def main() -> int:
    try:
        build(parser().parse_args())
    except (SplitError, OSError, UnicodeError, csv.Error, json.JSONDecodeError) as exc:
        print(f"E1_SPLIT_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
