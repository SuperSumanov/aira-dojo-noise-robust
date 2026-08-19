"""Independent reconstruction verifier for the E2-A six-task 80/10/10 split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import pathlib
import stat
import tempfile
from collections import defaultdict
from typing import Any, Iterator


SCHEMA = "balanced-continuation-e2a-split-v1"
SEED = 20260819
SPECS: dict[str, dict[str, Any]] = {
    "spaceship-titanic": {
        "id": "PassengerId", "targets": ["Transported"], "outputs": ["Transported"],
        "defaults": ["False"], "metric": "accuracy", "orientation": 1,
        "split": "exact_target", "allowed": {"False", "True"}, "rows": 7823,
        "train_sha": "d852203bbc5e603b92a7cfc0b46e23277c43d7a910b1db8b0ad58b7c6e3f2baa",
        "description_sha": "ee35380587404b263ef8b38d9a2fff4196563abb2e12bc086b02c9808b7f37cb",
    },
    "tabular-playground-series-may-2022": {
        "id": "id", "targets": ["target"], "outputs": ["target"], "defaults": ["0.5"],
        "metric": "roc_auc", "orientation": 1, "split": "exact_target",
        "allowed": {"0", "1"}, "rows": 800000,
        "train_sha": "f0940d6a4c3536752bdc3ba99251fc3020662ea43b28dfad520d810b3cde5514",
        "description_sha": "a64340a1c829f6e2c3ee8411cfa3089a4418571fee7186c91b5be2ef241bfcff",
    },
    "spooky-author-identification": {
        "id": "id", "targets": ["author"], "outputs": ["EAP", "HPL", "MWS"],
        "defaults": ["0.3333333333333333"] * 3, "metric": "multiclass_log_loss",
        "orientation": -1, "split": "exact_target", "allowed": {"EAP", "HPL", "MWS"},
        "rows": 17621,
        "train_sha": "87a02befe9c415b976486e4a59b96da0cc907b8645efbb7052256307715ecdbf",
        "description_sha": "35d7de46d74377f997bdc7f5859e36ca3311fb4ae2e37ab63491a9d7c72661bd",
    },
    "us-patent-phrase-to-phrase-matching": {
        "id": "id", "targets": ["score"], "outputs": ["score"], "defaults": ["0.5"],
        "metric": "pearson", "orientation": 1, "split": "exact_target",
        "allowed_numeric": {0.0, 0.25, 0.5, 0.75, 1.0}, "rows": 32825,
        "train_sha": "f5ba9a9b1b7fa3e025c65ece3fa2b92867c7436919c56d11e346d5344bcca205",
        "description_sha": "c2cc3682177d64f12e3c4d651389d7d6ef50852eaf97ccbcee55f62ebe957f53",
    },
    "nomad2018-predict-transparent-conductors": {
        "id": "id", "targets": ["formation_energy_ev_natom", "bandgap_energy_ev"],
        "outputs": ["formation_energy_ev_natom", "bandgap_energy_ev"],
        "defaults": ["0.1779", "1.8892"], "metric": "mean_columnwise_rmsle",
        "orientation": -1, "split": "formation_energy_rank_decile", "rows": 2160,
        "train_sha": "6a85d60056f8737c6575c8a7c0575fee6501916cf1dbd6199b0113849352546c",
        "description_sha": "d70aa4ad5bd3c2d460b750ae26b7f3572271dcab50499f4c8de66f7d6c45e1ad",
    },
    "learning-agency-lab-automated-essay-scoring-2": {
        "id": "essay_id", "targets": ["score"], "outputs": ["score"], "defaults": ["3"],
        "metric": "quadratic_weighted_kappa", "orientation": 1, "split": "exact_target",
        "allowed": {"1", "2", "3", "4", "5", "6"}, "rows": 15576,
        "train_sha": "ce6b0bd2c7d790a64ad3d2a8e15e3563d90e881c787638caa93504445caa65d0",
        "description_sha": "c11986179a042c909be5ab23275650f66160d7916ad229e133ca3f2af493cbed",
    },
}
TASKS = tuple(SPECS)


class VerifyError(RuntimeError):
    pass


def canon(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def row_key(task: str, row_id: str, source_index: int) -> bytes:
    return hashlib.sha256(
        f"{SCHEMA}|{SEED}|{task}|{row_id}|{source_index}".encode("utf-8")
    ).digest()


def source_files(root: pathlib.Path, task: str) -> tuple[pathlib.Path, pathlib.Path]:
    public = root / task / "prepared" / "public"
    return public / "train.csv", public / "description.md"


def exact_label(task: str, row: dict[str, str]) -> str:
    spec = SPECS[task]
    value = row[spec["targets"][0]]
    if "allowed" in spec:
        if value not in spec["allowed"]:
            raise VerifyError(f"target domain differs: {task}")
        return value
    try:
        number = float(value)
    except ValueError as exc:
        raise VerifyError(f"numeric target differs: {task}") from exc
    if not math.isfinite(number) or number not in spec["allowed_numeric"]:
        raise VerifyError(f"numeric target domain differs: {task}")
    return format(number, ".2f")


def allocate(path: pathlib.Path, task: str) -> tuple[bytearray, dict[str, Any], list[str]]:
    spec = SPECS[task]
    ids: list[str] = []
    strata: list[str] = []
    primary: list[float | None] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        if len(header) != len(set(header)) or spec["id"] not in header or not set(spec["targets"]) <= set(header):
            raise VerifyError(f"source header differs: {task}")
        for index, row in enumerate(reader):
            row_id = row[spec["id"]]
            if not row_id or row_id in seen or None in row or set(row) != set(header):
                raise VerifyError(f"source identity/schema differs: {task}:{index}")
            seen.add(row_id); ids.append(row_id)
            if spec["split"] == "exact_target":
                strata.append(exact_label(task, row)); primary.append(None)
            else:
                try:
                    values = [float(row[column]) for column in spec["targets"]]
                except ValueError as exc:
                    raise VerifyError(f"regression target differs: {task}") from exc
                if any(not math.isfinite(value) or value < 0 for value in values):
                    raise VerifyError(f"regression target range differs: {task}")
                strata.append(""); primary.append(values[0])
    if len(ids) != spec["rows"]:
        raise VerifyError(f"source row count differs: {task}")
    if spec["split"] == "formation_energy_rank_decile":
        order = sorted(
            range(len(ids)), key=lambda index: (primary[index], row_key(task, ids[index], index), index)
        )
        for rank, index in enumerate(order):
            strata[index] = str(min(9, rank * 10 // len(ids)))
    groups: dict[str, list[tuple[bytes, int]]] = defaultdict(list)
    for index, (row_id, label) in enumerate(zip(ids, strata)):
        groups[label].append((row_key(task, row_id, index), index))
    roles = bytearray(len(ids))
    stratum_counts = {}
    for label in sorted(groups):
        ranked = sorted(groups[label])
        if len(ranked) < 20:
            raise VerifyError(f"source stratum is too small: {task}/{label}")
        search = len(ranked) // 10; val = len(ranked) // 10
        for _, index in ranked[:search]: roles[index] = 1
        for _, index in ranked[search:search + val]: roles[index] = 2
        stratum_counts[label] = {
            "source": len(ranked), "train": len(ranked) - search - val,
            "dsearch": search, "dval": val,
        }
    return roles, {
        "source": len(ids), "train": roles.count(0), "dsearch": roles.count(1),
        "dval": roles.count(2), "strata": stratum_counts,
    }, header


def next_row(reader: Iterator[dict[str, str]], label: str) -> dict[str, str]:
    try:
        return next(reader)
    except StopIteration as exc:
        raise VerifyError(f"generated {label} ended early") from exc


def verify_task(result: pathlib.Path, source_root: pathlib.Path, task: str) -> dict[str, Any]:
    spec = SPECS[task]
    source_train, source_description = source_files(source_root, task)
    if sha(source_train) != spec["train_sha"] or sha(source_description) != spec["description_sha"]:
        raise VerifyError(f"source hash differs: {task}")
    roles, counts, header = allocate(source_train, task)
    feature_header = [column for column in header if column not in spec["targets"]]
    sample_header = [spec["id"], *spec["outputs"]]
    private_header = [spec["id"], *spec["targets"]]
    public = result / "public" / task
    paths = {
        "train": public / "train.csv", "test": public / "test.csv",
        "sample": public / "sample_submission.csv", "description": public / "description.md",
        "dsearch": result / "private" / "dsearch" / f"{task}.csv",
        "dval": result / "private" / "dval" / f"{task}.csv",
    }
    if any(not path.is_file() or path.is_symlink() for path in paths.values()):
        raise VerifyError(f"generated task path differs: {task}")
    if paths["description"].read_bytes() != source_description.read_bytes():
        raise VerifyError(f"generated description differs: {task}")
    if os.name == "posix":
        for role in ("train", "test", "sample", "description"):
            if stat.S_IMODE(paths[role].stat().st_mode) != 0o444:
                raise VerifyError(f"public mode differs: {task}/{role}")
        for role in ("dsearch", "dval"):
            if stat.S_IMODE(paths[role].stat().st_mode) != 0o600:
                raise VerifyError(f"private mode differs: {task}/{role}")
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
            "train": csv.DictReader(train_handle), "test": csv.DictReader(test_handle),
            "sample": csv.DictReader(sample_handle), "dsearch": csv.DictReader(dsearch_handle),
            "dval": csv.DictReader(dval_handle),
        }
        if list(source_reader.fieldnames or []) != header:
            raise VerifyError(f"source header changed: {task}")
        expected_headers = {
            "train": header, "test": feature_header, "sample": sample_header,
            "dsearch": private_header, "dval": private_header,
        }
        for role, expected in expected_headers.items():
            if list(generated[role].fieldnames or []) != expected:
                raise VerifyError(f"generated header differs: {task}/{role}")
        defaults = dict(zip(spec["outputs"], spec["defaults"]))
        for index, source_row in enumerate(source_reader):
            role = int(roles[index]); role_name = ("train", "dsearch", "dval")[role]
            membership.update(canon({
                "id": source_row[spec["id"]], "role": role_name, "source_index": index,
            }) + b"\n")
            if role == 0:
                if next_row(generated["train"], f"{task}/train") != source_row:
                    raise VerifyError(f"generated train row differs: {task}:{index}")
                continue
            expected_test = {column: source_row[column] for column in feature_header}
            expected_sample = {spec["id"]: source_row[spec["id"]], **defaults}
            expected_private = {
                spec["id"]: source_row[spec["id"]],
                **{column: source_row[column] for column in spec["targets"]},
            }
            if next_row(generated["test"], f"{task}/test") != expected_test:
                raise VerifyError(f"generated test row differs: {task}:{index}")
            if next_row(generated["sample"], f"{task}/sample") != expected_sample:
                raise VerifyError(f"generated sample row differs: {task}:{index}")
            if next_row(generated[role_name], f"{task}/{role_name}") != expected_private:
                raise VerifyError(f"generated private row differs: {task}:{index}")
        for role, reader in generated.items():
            try:
                next(reader)
            except StopIteration:
                continue
            raise VerifyError(f"generated file has extra rows: {task}/{role}")
    return {
        "task": task, "id_column": spec["id"], "target_columns": spec["targets"],
        "submission_columns": spec["outputs"], "metric": spec["metric"],
        "orientation": spec["orientation"], "split_stratification": spec["split"],
        "split_seed": SEED, "source_train_sha256": spec["train_sha"],
        "source_description_sha256": spec["description_sha"],
        "source_inputs_opened": ["train.csv", "description.md"],
        "official_test_opened": False, "official_sample_submission_opened": False,
        "private_answers_opened": False, "counts": counts,
        "membership_sha256": membership.hexdigest(),
        "public_file_sha256": {
            "train.csv": sha(paths["train"]), "test.csv": sha(paths["test"]),
            "sample_submission.csv": sha(paths["sample"]), "description.md": sha(paths["description"]),
        },
        "private_label_sha256": {"dsearch": sha(paths["dsearch"]), "dval": sha(paths["dval"])},
    }


def manifest(root: pathlib.Path) -> dict[str, dict[str, Any]]:
    output = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "sha256_manifest.json":
            output[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size, "mode": stat.S_IMODE(path.stat().st_mode),
                "sha256": sha(path),
            }
    return output


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
    root = pathlib.Path(args.result).resolve(); source_root = pathlib.Path(args.source_root).resolve()
    if not root.is_dir() or root.is_symlink() or not source_root.is_dir():
        raise VerifyError("result/source root differs")
    contracts = [verify_task(root, source_root, task) for task in TASKS]
    public_contract = {
        "schema_version": "balanced-continuation-e2a-public-dataset-contract-v1",
        "split_schema_version": SCHEMA, "split_seed": SEED,
        "tasks": [{key: contract[key] for key in (
            "task", "id_column", "target_columns", "submission_columns", "metric",
            "orientation", "split_stratification", "counts", "membership_sha256",
            "public_file_sha256", "source_train_sha256", "source_description_sha256",
        )} for contract in contracts],
        "candidate_visible_roles": ["D_train", "unlabeled_D_search_plus_D_val"],
        "official_test_materialized": False, "official_sample_submission_read": False,
        "private_labels_under_public_root": False,
    }
    public_path = root / "public_dataset_contract.json"
    if json.loads(public_path.read_bytes()) != public_contract:
        raise VerifyError("public dataset contract differs")
    public_sha = sha(public_path)
    split_manifest = {
        "schema_version": SCHEMA, "split_seed": SEED,
        "policy": "80/10/10_exact_or_frozen_rank_decile", "tasks": contracts,
        "public_dataset_contract_sha256": public_sha, "dtest_rows_read": 0,
        "official_test_materialized": False, "official_sample_submission_read": False,
        "private_answers_read": False,
    }
    opaque = root / "split_manifest_opaque.json"
    if json.loads(opaque.read_bytes()) != split_manifest:
        raise VerifyError("opaque split manifest differs")
    if os.name == "posix" and stat.S_IMODE(opaque.stat().st_mode) != 0o600:
        raise VerifyError("opaque split manifest mode differs")
    opaque_sha = sha(opaque)
    expected_summary = {
        "schema_version": SCHEMA, "status": "VERIFIED_E2A_80_10_10_SPLIT_BUILT",
        "split_seed": SEED, "task_count": 6, "tasks": list(TASKS),
        "public_dataset_contract_sha256": public_sha,
        "split_manifest_sha256_opaque": opaque_sha, "dtest_rows_read": 0,
        "official_sample_submission_read": False, "private_answers_read": False,
        "source_inputs_per_task": ["train.csv", "description.md"],
        "counts": {contract["task"]: contract["counts"] for contract in contracts},
    }
    if json.loads((root / "summary.json").read_bytes()) != expected_summary:
        raise VerifyError("split summary differs")
    if json.loads((root / "sha256_manifest.json").read_bytes()) != manifest(root):
        raise VerifyError("recursive manifest differs")
    receipt = {
        "schema_version": "balanced-continuation-e2a-split-verification-v1",
        "status": "VERIFIED_E2A_SPLIT_RECONSTRUCTION_NO_DTEST_READ",
        "producer_imported": False, "tasks": list(TASKS), "counts": expected_summary["counts"],
        "public_dataset_contract_sha256": public_sha,
        "split_manifest_sha256_opaque": opaque_sha, "dtest_rows_read": 0,
        "official_sample_submission_read": False, "private_answers_read": False,
        "result_manifest_sha256": sha(root / "sha256_manifest.json"),
    }
    atomic_json(pathlib.Path(args.receipt).resolve(), receipt)
    print(canon(receipt).decode("utf-8"))
    return receipt


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", required=True); ap.add_argument("--result", required=True)
    ap.add_argument("--receipt", required=True)
    return ap


def main() -> int:
    try:
        verify(parser().parse_args())
    except (VerifyError, OSError, UnicodeError, csv.Error, json.JSONDecodeError, KeyError) as exc:
        print(f"E2A_SPLIT_VERIFY_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
