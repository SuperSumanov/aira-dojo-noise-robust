"""Atomically package independently verified E2-A inputs and splits for execution."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

from phase1.balanced_continuation_e2a_scoring import (
    CREDENTIAL, canonical_json, checked_json, file_sha256,
)


class GateError(RuntimeError):
    pass


GIT_NO_LFS = [
    "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=",
    "-c", "filter.lfs.required=false",
]


def exact_source_commit() -> str:
    root = pathlib.Path(__file__).resolve().parents[1]
    commit = subprocess.run(
        ["git", *GIT_NO_LFS, "rev-parse", "HEAD"], cwd=root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.decode("ascii").strip()
    dirty = subprocess.run(
        ["git", *GIT_NO_LFS, "status", "--porcelain"], cwd=root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    if dirty or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise GateError("E2-A data gate requires an exact clean source commit")
    return commit


def build(args: argparse.Namespace) -> dict:
    inputs = pathlib.Path(args.inputs).resolve()
    split = pathlib.Path(args.split).resolve()
    input_receipt_path = pathlib.Path(args.input_receipt).resolve()
    split_receipt_path = pathlib.Path(args.split_receipt).resolve()
    output = pathlib.Path(args.output).resolve()
    if output.exists() or output.is_symlink():
        raise GateError("data-gate output must be new")
    for path, label in ((inputs, "inputs"), (split, "split")):
        if not path.is_dir() or path.is_symlink():
            raise GateError(f"verified {label} root differs")
    for path, label in (
        (input_receipt_path, "input receipt"), (split_receipt_path, "split receipt")
    ):
        if not path.is_file() or path.is_symlink():
            raise GateError(f"{label} differs")
    input_receipt = checked_json(input_receipt_path)
    split_receipt = checked_json(split_receipt_path)
    if (
        input_receipt.get("status")
        != "VERIFIED_E2A_INPUTS_OUTCOME_BLIND_DISTINCT_RUNS"
        or input_receipt.get("producer_imported") is not False
        or input_receipt.get("result_manifest_sha256")
        != file_sha256(inputs / "sha256_manifest.json")
    ):
        raise GateError("input independent-verification binding differs")
    if (
        split_receipt.get("status")
        != "VERIFIED_E2A_SPLIT_RECONSTRUCTION_NO_DTEST_READ"
        or split_receipt.get("producer_imported") is not False
        or split_receipt.get("result_manifest_sha256")
        != file_sha256(split / "sha256_manifest.json")
        or split_receipt.get("dtest_rows_read") != 0
    ):
        raise GateError("split independent-verification binding differs")
    commit = exact_source_commit()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if staging.exists() or staging.is_symlink():
        raise GateError("data-gate staging root exists")
    staging.mkdir(mode=0o700)
    try:
        shutil.copytree(inputs, staging / "e2a_inputs", copy_function=shutil.copy2)
        shutil.copytree(split, staging / "e2a_split", copy_function=shutil.copy2)
        shutil.copy2(input_receipt_path, staging / "e2a_inputs.verify.json")
        shutil.copy2(split_receipt_path, staging / "e2a_split.verify.json")
        (staging / "source_commit.txt").write_text(commit + "\n", encoding="ascii", newline="\n")
        summary = {
            "schema_version": "balanced-continuation-e2a-data-gate-v1",
            "status": "VERIFIED_E2A_DATA_GATE_PACKAGED",
            "source_commit": commit,
            "tasks": input_receipt["tasks"],
            "anchors": input_receipt["anchors"],
            "physical_runs": input_receipt["physical_runs"],
            "siblings": input_receipt["siblings"],
            "calibration_anchors": input_receipt["calibration_anchors"],
            "input_verification_receipt_sha256": file_sha256(
                staging / "e2a_inputs.verify.json"
            ),
            "split_verification_receipt_sha256": file_sha256(
                staging / "e2a_split.verify.json"
            ),
            "contains_outcomes": False,
            "dtest_rows_read": 0,
        }
        (staging / "summary.json").write_bytes(canonical_json(summary) + b"\n")
        files = [path for path in sorted(staging.rglob("*")) if path.is_file()]
        top = "".join(
            f"{file_sha256(path)}  {path.relative_to(staging).as_posix()}\n"
            for path in files
        )
        (staging / "top_manifest.sha256").write_text(top, encoding="ascii", newline="\n")
        if CREDENTIAL.search(b"".join(path.read_bytes() for path in staging.rglob("*") if path.is_file())):
            raise GateError("credential-shaped bytes in packaged data gate")
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(canonical_json(summary).decode("utf-8"))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--input-receipt", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--split-receipt", required=True)
    parser.add_argument("--output", required=True)
    try:
        build(parser.parse_args())
    except (
        GateError, OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"E2A_DATA_GATE_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
