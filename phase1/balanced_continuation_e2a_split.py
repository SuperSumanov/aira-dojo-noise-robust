"""Build the six-task public-train-only 80/10/10 dataset for E2-A."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import pathlib
import shutil
import stat
import tempfile
from collections import defaultdict
from typing import Any


SCHEMA = "balanced-continuation-e2a-split-v1"
SPLIT_SEED = 20260819
TASK_SPECS: dict[str, dict[str, Any]] = {
    "spaceship-titanic": {
        "id_column": "PassengerId", "target_columns": ["Transported"],
        "submission_columns": ["Transported"], "sample_defaults": ["False"],
        "metric": "accuracy", "orientation": 1, "split": "exact_target",
        "allowed": {"False", "True"}, "source_rows": 7823,
        "train_sha256": "d852203bbc5e603b92a7cfc0b46e23277c43d7a910b1db8b0ad58b7c6e3f2baa",
        "description_sha256": "ee35380587404b263ef8b38d9a2fff4196563abb2e12bc086b02c9808b7f37cb",
    },
    "tabular-playground-series-may-2022": {
        "id_column": "id", "target_columns": ["target"],
        "submission_columns": ["target"], "sample_defaults": ["0.5"],
        "metric": "roc_auc", "orientation": 1, "split": "exact_target",
        "allowed": {"0", "1"}, "source_rows": 800000,
        "train_sha256": "f0940d6a4c3536752bdc3ba99251fc3020662ea43b28dfad520d810b3cde5514",
        "description_sha256": "a64340a1c829f6e2c3ee8411cfa3089a4418571fee7186c91b5be2ef241bfcff",
    },
    "spooky-author-identification": {
        "id_column": "id", "target_columns": ["author"],
        "submission_columns": ["EAP", "HPL", "MWS"],
        "sample_defaults": ["0.3333333333333333"] * 3,
        "metric": "multiclass_log_loss", "orientation": -1, "split": "exact_target",
        "allowed": {"EAP", "HPL", "MWS"}, "source_rows": 17621,
        "train_sha256": "87a02befe9c415b976486e4a59b96da0cc907b8645efbb7052256307715ecdbf",
        "description_sha256": "35d7de46d74377f997bdc7f5859e36ca3311fb4ae2e37ab63491a9d7c72661bd",
    },
    "us-patent-phrase-to-phrase-matching": {
        "id_column": "id", "target_columns": ["score"],
        "submission_columns": ["score"], "sample_defaults": ["0.5"],
        "metric": "pearson", "orientation": 1, "split": "exact_target",
        "allowed_numeric": {0.0, 0.25, 0.5, 0.75, 1.0}, "source_rows": 32825,
        "train_sha256": "f5ba9a9b1b7fa3e025c65ece3fa2b92867c7436919c56d11e346d5344bcca205",
        "description_sha256": "c2cc3682177d64f12e3c4d651389d7d6ef50852eaf97ccbcee55f62ebe957f53",
    },
    "nomad2018-predict-transparent-conductors": {
        "id_column": "id",
        "target_columns": ["formation_energy_ev_natom", "bandgap_energy_ev"],
        "submission_columns": ["formation_energy_ev_natom", "bandgap_energy_ev"],
        "sample_defaults": ["0.1779", "1.8892"],
        "metric": "mean_columnwise_rmsle", "orientation": -1,
        "split": "formation_energy_rank_decile", "source_rows": 2160,
        "train_sha256": "6a85d60056f8737c6575c8a7c0575fee6501916cf1dbd6199b0113849352546c",
        "description_sha256": "d70aa4ad5bd3c2d460b750ae26b7f3572271dcab50499f4c8de66f7d6c45e1ad",
    },
    "learning-agency-lab-automated-essay-scoring-2": {
        "id_column": "essay_id", "target_columns": ["score"],
        "submission_columns": ["score"], "sample_defaults": ["3"],
        "metric": "quadratic_weighted_kappa", "orientation": 1,
        "split": "exact_target", "allowed": {"1", "2", "3", "4", "5", "6"},
        "source_rows": 15576,
        "train_sha256": "ce6b0bd2c7d790a64ad3d2a8e15e3563d90e881c787638caa93504445caa65d0",
        "description_sha256": "c11986179a042c909be5ab23275650f66160d7916ad229e133ca3f2af493cbed",
    },
}
TASK_ORDER = tuple(TASK_SPECS)


class SplitError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
    raw = f"{SCHEMA}|{SPLIT_SEED}|{task}|{row_id}|{source_index}".encode("utf-8")
    return hashlib.sha256(raw).digest()


def source_paths(source_root: pathlib.Path, task: str) -> tuple[pathlib.Path, pathlib.Path]:
    # These are the only authorized source paths; original test/sample/private files are unnamed.
    public = source_root / task / "prepared" / "public"
    return public / "train.csv", public / "description.md"


def validate_source(source_root: pathlib.Path, task: str) -> tuple[pathlib.Path, pathlib.Path]:
    train, description = source_paths(source_root, task)
    spec = TASK_SPECS[task]
    for path, key in ((train, "train_sha256"), (description, "description_sha256")):
        if not path.is_file() or path.is_symlink():
            raise SplitError(f"authorized source is missing or symlinked: {path}")
        actual = file_sha256(path)
        if actual != spec[key]:
            raise SplitError(f"{task} {path.name} SHA differs: {actual}")
    return train, description


def exact_stratum(task: str, row: dict[str, str]) -> str:
    spec = TASK_SPECS[task]
    values = [row[column] for column in spec["target_columns"]]
    if "allowed" in spec:
        if len(values) != 1 or values[0] not in spec["allowed"]:
            raise SplitError(f"{task} target value is outside the frozen domain")
        return values[0]
    if "allowed_numeric" in spec:
        try:
            value = float(values[0])
        except ValueError as exc:
            raise SplitError(f"{task} target value is not numeric") from exc
        if not math.isfinite(value) or value not in spec["allowed_numeric"]:
            raise SplitError(f"{task} target value is outside the frozen numeric domain")
        return format(value, ".2f")
    raise SplitError(f"{task} lacks an exact-target domain")


def scan_source(train: pathlib.Path, task: str) -> tuple[list[str], list[str], list[float | None]]:
    spec = TASK_SPECS[task]
    ids: list[str] = []
    strata: list[str] = []
    primary_values: list[float | None] = []
    seen: set[str] = set()
    with train.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        if len(header) != len(set(header)) or spec["id_column"] not in header:
            raise SplitError(f"{task} source header differs")
        if not set(spec["target_columns"]) <= set(header):
            raise SplitError(f"{task} target columns are absent")
        for source_index, row in enumerate(reader):
            if None in row or set(row) != set(header):
                raise SplitError(f"{task} malformed row {source_index}")
            row_id = row[spec["id_column"]]
            if not row_id or row_id in seen:
                raise SplitError(f"{task} empty/duplicate id at row {source_index}")
            seen.add(row_id)
            ids.append(row_id)
            if spec["split"] == "exact_target":
                strata.append(exact_stratum(task, row))
                primary_values.append(None)
            elif spec["split"] == "formation_energy_rank_decile":
                try:
                    values = [float(row[column]) for column in spec["target_columns"]]
                except ValueError as exc:
                    raise SplitError(f"{task} non-numeric regression target") from exc
                if any(not math.isfinite(value) or value < 0 for value in values):
                    raise SplitError(f"{task} negative/non-finite regression target")
                strata.append("")
                primary_values.append(values[0])
            else:
                raise SplitError(f"{task} split policy differs")
    if len(ids) != spec["source_rows"]:
        raise SplitError(f"{task} source row count differs: {len(ids)}")
    if spec["split"] == "formation_energy_rank_decile":
        order = sorted(
            range(len(ids)),
            key=lambda index: (
                primary_values[index], deterministic_key(task, ids[index], index), index
            ),
        )
        for rank, source_index in enumerate(order):
            strata[source_index] = str(min(9, rank * 10 // len(ids)))
    return header, strata, primary_values


def allocate_roles(
    train: pathlib.Path, task: str
) -> tuple[bytearray, dict[str, Any], list[str]]:
    header, row_strata, _ = scan_source(train, task)
    strata: dict[str, list[tuple[bytes, int]]] = defaultdict(list)
    # Re-open only the authorized train file to recover IDs; no other source path is touched.
    spec = TASK_SPECS[task]
    with train.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for source_index, row in enumerate(reader):
            strata[row_strata[source_index]].append(
                (deterministic_key(task, row[spec["id_column"]], source_index), source_index)
            )
    roles = bytearray(len(row_strata))
    class_counts: dict[str, dict[str, int]] = {}
    for label in sorted(strata):
        ranked = sorted(strata[label])
        if len(ranked) < 20:
            raise SplitError(f"{task} stratum {label} is smaller than 20")
        n_search = len(ranked) // 10
        n_val = len(ranked) // 10
        for _, source_index in ranked[:n_search]:
            roles[source_index] = 1
        for _, source_index in ranked[n_search:n_search + n_val]:
            roles[source_index] = 2
        class_counts[label] = {
            "source": len(ranked), "train": len(ranked) - n_search - n_val,
            "dsearch": n_search, "dval": n_val,
        }
    counts = {
        "source": len(roles), "train": roles.count(0), "dsearch": roles.count(1),
        "dval": roles.count(2), "strata": class_counts,
    }
    if counts["train"] + counts["dsearch"] + counts["dval"] != len(roles):
        raise SplitError("split roles do not cover source")
    return roles, counts, header


def write_task(staging: pathlib.Path, source_root: pathlib.Path, task: str) -> dict[str, Any]:
    train_source, description_source = validate_source(source_root, task)
    roles, counts, header = allocate_roles(train_source, task)
    spec = TASK_SPECS[task]
    ident = spec["id_column"]
    targets = list(spec["target_columns"])
    feature_header = [column for column in header if column not in targets]
    submission_header = [ident, *spec["submission_columns"]]
    private_header = [ident, *targets]
    public = staging / "public" / task
    public.mkdir(parents=True)
    (staging / "private" / "dsearch").mkdir(parents=True, exist_ok=True)
    (staging / "private" / "dval").mkdir(parents=True, exist_ok=True)
    paths = {
        "train": public / "train.csv", "test": public / "test.csv",
        "sample": public / "sample_submission.csv",
        "dsearch": staging / "private" / "dsearch" / f"{task}.csv",
        "dval": staging / "private" / "dval" / f"{task}.csv",
    }
    membership = hashlib.sha256()
    observed = [0, 0, 0]
    with (
        train_source.open("r", encoding="utf-8-sig", newline="") as source_handle,
        paths["train"].open("x", encoding="utf-8", newline="") as train_handle,
        paths["test"].open("x", encoding="utf-8", newline="") as test_handle,
        paths["sample"].open("x", encoding="utf-8", newline="") as sample_handle,
        paths["dsearch"].open("x", encoding="utf-8", newline="") as dsearch_handle,
        paths["dval"].open("x", encoding="utf-8", newline="") as dval_handle,
    ):
        reader = csv.DictReader(source_handle)
        writers = {
            "train": csv.DictWriter(train_handle, fieldnames=header, lineterminator="\n"),
            "test": csv.DictWriter(test_handle, fieldnames=feature_header, lineterminator="\n"),
            "sample": csv.DictWriter(sample_handle, fieldnames=submission_header, lineterminator="\n"),
            "dsearch": csv.DictWriter(dsearch_handle, fieldnames=private_header, lineterminator="\n"),
            "dval": csv.DictWriter(dval_handle, fieldnames=private_header, lineterminator="\n"),
        }
        for writer in writers.values():
            writer.writeheader()
        defaults = dict(zip(spec["submission_columns"], spec["sample_defaults"]))
        for source_index, row in enumerate(reader):
            role = int(roles[source_index])
            observed[role] += 1
            role_name = ("train", "dsearch", "dval")[role]
            membership.update(canonical_json({
                "id": row[ident], "role": role_name, "source_index": source_index,
            }) + b"\n")
            if role == 0:
                writers["train"].writerow(row)
                continue
            writers["test"].writerow({column: row[column] for column in feature_header})
            writers["sample"].writerow({ident: row[ident], **defaults})
            writers[role_name].writerow({ident: row[ident], **{column: row[column] for column in targets}})
        for handle in (train_handle, test_handle, sample_handle, dsearch_handle, dval_handle):
            handle.flush(); os.fsync(handle.fileno())
    if observed != [counts["train"], counts["dsearch"], counts["dval"]]:
        raise SplitError(f"{task} emitted role counts differ")
    description = public / "description.md"
    shutil.copyfile(description_source, description)
    for path in (paths["train"], paths["test"], paths["sample"], description):
        os.chmod(path, 0o444)
    for path in (paths["dsearch"], paths["dval"]):
        os.chmod(path, 0o600)
    os.chmod(public, 0o555)
    return {
        "task": task, "id_column": ident, "target_columns": targets,
        "submission_columns": list(spec["submission_columns"]),
        "metric": spec["metric"], "orientation": spec["orientation"],
        "split_stratification": spec["split"], "split_seed": SPLIT_SEED,
        "source_train_sha256": spec["train_sha256"],
        "source_description_sha256": spec["description_sha256"],
        "source_inputs_opened": ["train.csv", "description.md"],
        "official_test_opened": False, "official_sample_submission_opened": False,
        "private_answers_opened": False, "counts": counts,
        "membership_sha256": membership.hexdigest(),
        "public_file_sha256": {
            "train.csv": file_sha256(paths["train"]), "test.csv": file_sha256(paths["test"]),
            "sample_submission.csv": file_sha256(paths["sample"]),
            "description.md": file_sha256(description),
        },
        "private_label_sha256": {
            "dsearch": file_sha256(paths["dsearch"]), "dval": file_sha256(paths["dval"]),
        },
    }


def recursive_manifest(root: pathlib.Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "sha256_manifest.json":
            result[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size, "mode": stat.S_IMODE(path.stat().st_mode),
                "sha256": file_sha256(path),
            }
    return result


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_root = pathlib.Path(args.source_root).resolve()
    output = pathlib.Path(args.output)
    if not source_root.is_dir() or not output.is_absolute():
        raise SplitError("source root/output path differs")
    if output.exists() or output.is_symlink():
        raise SplitError("output must not pre-exist")
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if staging.exists() or staging.is_symlink():
        raise SplitError("staging path already exists")
    staging.mkdir(parents=True)
    try:
        (staging / "private").mkdir(); os.chmod(staging / "private", 0o700)
        contracts = [write_task(staging, source_root, task) for task in TASK_ORDER]
        public_contract = {
            "schema_version": "balanced-continuation-e2a-public-dataset-contract-v1",
            "split_schema_version": SCHEMA, "split_seed": SPLIT_SEED,
            "tasks": [{key: contract[key] for key in (
                "task", "id_column", "target_columns", "submission_columns", "metric",
                "orientation", "split_stratification", "counts", "membership_sha256",
                "public_file_sha256", "source_train_sha256", "source_description_sha256",
            )} for contract in contracts],
            "candidate_visible_roles": ["D_train", "unlabeled_D_search_plus_D_val"],
            "official_test_materialized": False, "official_sample_submission_read": False,
            "private_labels_under_public_root": False,
        }
        atomic_json(staging / "public_dataset_contract.json", public_contract)
        public_sha = file_sha256(staging / "public_dataset_contract.json")
        split_manifest = {
            "schema_version": SCHEMA, "split_seed": SPLIT_SEED,
            "policy": "80/10/10_exact_or_frozen_rank_decile",
            "tasks": contracts, "public_dataset_contract_sha256": public_sha,
            "dtest_rows_read": 0, "official_test_materialized": False,
            "official_sample_submission_read": False, "private_answers_read": False,
        }
        atomic_json(staging / "split_manifest_opaque.json", split_manifest, mode=0o600)
        split_sha = file_sha256(staging / "split_manifest_opaque.json")
        summary = {
            "schema_version": SCHEMA, "status": "VERIFIED_E2A_80_10_10_SPLIT_BUILT",
            "split_seed": SPLIT_SEED, "task_count": len(TASK_ORDER), "tasks": list(TASK_ORDER),
            "public_dataset_contract_sha256": public_sha,
            "split_manifest_sha256_opaque": split_sha,
            "dtest_rows_read": 0, "official_sample_submission_read": False,
            "private_answers_read": False, "source_inputs_per_task": ["train.csv", "description.md"],
            "counts": {contract["task"]: contract["counts"] for contract in contracts},
        }
        atomic_json(staging / "summary.json", summary)
        atomic_json(staging / "sha256_manifest.json", recursive_manifest(staging))
        os.replace(staging, output)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(canonical_json(summary).decode("utf-8"))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", required=True); ap.add_argument("--output", required=True)
    return ap


def main() -> int:
    try:
        build(parser().parse_args())
    except (SplitError, OSError, UnicodeError, csv.Error, json.JSONDecodeError) as exc:
        print(f"E2A_SPLIT_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
