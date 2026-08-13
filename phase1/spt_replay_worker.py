#!/usr/bin/env python3
"""Replay one frozen original/replicate/tapped candidate for the SPT pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from phase1.schema_probe_contract_worker import atomic_write_json, monitor_contract
from phase1.scoreable_prediction_tap import instrument
from phase1.trajectory_fidelity_worker import (
    DEFAULT_CACHE,
    DEFAULT_DATA,
    SIF,
    build_command,
    file_sha256,
    grade_snapshot,
)


ARMS = frozenset({"original_a", "original_b", "tap"})


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_manifest(path: Path, runtime_sha256: str) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    required = {
        "index",
        "group_index",
        "group_id",
        "sibling_index",
        "card_id",
        "competition",
        "metric",
        "higher_is_better",
        "run_id",
        "parent_id",
        "arm",
        "seed",
        "code",
        "code_sha256",
        "base_code_sha256",
        "tap_runtime_sha256",
        "tap_site_count",
        "source_export_sha256",
        "split_sha256",
    }
    if len(rows) != 18 or any(not isinstance(row, dict) or required - set(row) for row in rows):
        raise RuntimeError("malformed SPT pilot manifest")
    if [row["index"] for row in rows] != list(range(len(rows))):
        raise RuntimeError("manifest index order mismatch")
    by_card: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["arm"] not in ARMS:
            raise RuntimeError(f"unknown arm: {row['arm']}")
        if sha256_text(row["code"]) != row["code_sha256"]:
            raise RuntimeError(f"executed code hash mismatch: {row['index']}")
        if row["arm"] == "tap":
            if row["tap_runtime_sha256"] != runtime_sha256:
                raise RuntimeError(f"runtime hash mismatch: {row['index']}")
            if "from scoreable_prediction_tap_runtime import capture as __spt_capture__" not in row["code"]:
                raise RuntimeError(f"tap import missing: {row['index']}")
        else:
            if row["tap_runtime_sha256"] is not None:
                raise RuntimeError(f"original has tap runtime: {row['index']}")
            if sha256_text(row["code"]) != row["base_code_sha256"]:
                raise RuntimeError(f"original differs from base code: {row['index']}")
        by_card[row["card_id"]].append(row)
    if len(by_card) != 6:
        raise RuntimeError("pilot must have six unique cards")
    for card_id, card_rows in by_card.items():
        if {row["arm"] for row in card_rows} != ARMS:
            raise RuntimeError(f"incomplete arm triplet: {card_id}")
        shared = {
            (
                row["competition"],
                row["metric"],
                row["higher_is_better"],
                row["run_id"],
                row["parent_id"],
                row["base_code_sha256"],
                row["source_export_sha256"],
                row["split_sha256"],
            )
            for row in card_rows
        }
        if len(shared) != 1:
            raise RuntimeError(f"non-arm card drift: {card_id}")
        by_arm = {row["arm"]: row for row in card_rows}
        if by_arm["original_a"]["code"] != by_arm["original_b"]["code"]:
            raise RuntimeError(f"original replicate code mismatch: {card_id}")
        rebuilt_tap, tap_audit = instrument(by_arm["original_a"]["code"])
        if rebuilt_tap != by_arm["tap"]["code"]:
            raise RuntimeError(f"tap is not the deterministic base-code transform: {card_id}")
        if int(tap_audit["site_count"]) != int(by_arm["tap"]["tap_site_count"]):
            raise RuntimeError(f"tap site-count mismatch: {card_id}")
    return rows


def add_spt_grades(payload: dict, competition: str, data_dir: Path, staging: Path) -> None:
    probe = payload.get("probe")
    if isinstance(probe, dict) and probe.get("snapshot_relpath"):
        probe["grade"] = grade_snapshot(staging / probe["snapshot_relpath"], competition, data_dir)
    for row in payload["submission_events"]:
        relpath = row.get("snapshot_relpath")
        row["grade"] = (
            grade_snapshot(staging / relpath, competition, data_dir)
            if relpath
            else {
                "sub_score": None,
                "grade_rc": None,
                "grade_wall_s": None,
                "grade_output_sha256": None,
                "grade_skipped_reason": "no_stable_snapshot",
            }
        )
    for row in payload["checkpoints"]:
        row["grade"] = {
            "sub_score": None,
            "grade_rc": None,
            "grade_wall_s": None,
            "grade_output_sha256": None,
            "grade_skipped_reason": "not_graded_spt_pilot",
        }


def run_one(args: argparse.Namespace) -> None:
    runtime_sha = file_sha256(args.runtime_source)
    if file_sha256(SIF) != args.container_sha256:
        raise RuntimeError("container image SHA mismatch")
    rows = load_manifest(args.manifest, runtime_sha)
    if args.index < 0 or args.index >= len(rows):
        raise RuntimeError(f"index out of range: {args.index}/{len(rows)}")
    row = rows[args.index]
    destination = args.out / f"index_{args.index}"
    if destination.exists():
        raise RuntimeError(f"refusing existing result: {destination}")
    args.out.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".index-{args.index}-", dir=args.out))

    safe_id = hashlib.sha256(
        f"{row['card_id']}\0{row['arm']}".encode("utf-8")
    ).hexdigest()[:20]
    workdir = args.workbase / f"index_{args.index}_{safe_id}"
    if workdir.exists():
        raise RuntimeError(f"refusing existing workdir: {workdir}")
    workdir.mkdir(parents=True)
    (workdir / "solution.py").write_text(row["code"], encoding="utf-8", newline="")
    if row["arm"] == "tap":
        shutil.copyfile(args.runtime_source, workdir / "scoreable_prediction_tap_runtime.py")
        if file_sha256(workdir / "scoreable_prediction_tap_runtime.py") != runtime_sha:
            raise RuntimeError("staged tap runtime hash mismatch")

    stdout_path = workdir / "stdout.log"
    stderr_path = workdir / "stderr.log"
    public_data = args.data_dir / row["competition"] / "prepared" / "public"
    if not public_data.is_dir():
        raise RuntimeError(f"public data missing: {public_data}")
    nvfix = args.workbase / f"nvfix_{args.index}"
    source_nvvm = Path("/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4")
    source_icd = Path("/etc/OpenCL/vendors/nvidia.icd")
    if not source_nvvm.is_file() or not source_icd.is_file():
        raise RuntimeError("required NVIDIA/OpenCL host fix unavailable")
    nvfix.mkdir(parents=True)
    shutil.copy(source_nvvm, nvfix / "libnvidia-nvvm.so.4")
    command = build_command(workdir, public_data, args.hf_cache, args.online, nvfix)

    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        started_wall_ns = time.time_ns()
        started = time.monotonic()
        process = subprocess.Popen(
            command,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
        payload = monitor_contract(
            process,
            workdir,
            stdout_path,
            stderr_path,
            args.checkpoints,
            staging,
            args.poll_s,
            started,
        )
    add_spt_grades(payload, row["competition"], args.data_dir, staging)
    result = {
        "schema_version": 1,
        "index": args.index,
        "group_index": row["group_index"],
        "group_id": row["group_id"],
        "sibling_index": row["sibling_index"],
        "card_id": row["card_id"],
        "competition": row["competition"],
        "metric": row["metric"],
        "higher_is_better": row["higher_is_better"],
        "run_id": row["run_id"],
        "parent_id": row["parent_id"],
        "arm": row["arm"],
        "seed": row["seed"],
        "manifest": str(args.manifest),
        "manifest_sha256": file_sha256(args.manifest),
        "code_sha256": row["code_sha256"],
        "base_code_sha256": row["base_code_sha256"],
        "tap_runtime_sha256": row["tap_runtime_sha256"],
        "tap_site_count": row["tap_site_count"],
        "source_export_sha256": row["source_export_sha256"],
        "split_sha256": row["split_sha256"],
        "container_image": str(SIF),
        "container_sha256": args.container_sha256,
        "started_wall_ns": started_wall_ns,
        "workdir": str(workdir),
        "checkpoints_s": args.checkpoints,
        **payload,
    }
    atomic_write_json(staging / "result.json", result)
    os.replace(staging, destination)
    print(
        "SPT_REPLAY_WORKER_DONE "
        f"index={args.index} arm={row['arm']} task={row['competition']} "
        f"probe={int(result['probe'] is not None)} events={len(result['submission_events'])} "
        f"rc={result['final_rc']}",
        flush=True,
    )


def self_test(runtime_source: Path) -> None:
    runtime_sha = file_sha256(runtime_source)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rows = []
        for card_number in range(6):
            base = f"prediction_{card_number} = model.predict(X_test)\n"
            tapped, tap_audit = instrument(base)
            for arm in ("original_a", "original_b", "tap"):
                code = tapped if arm == "tap" else base
                rows.append(
                    {
                        "index": len(rows),
                        "group_index": card_number // 2,
                        "group_id": f"group-{card_number // 2}",
                        "sibling_index": card_number % 2,
                        "card_id": f"card-{card_number}",
                        "competition": f"task-{card_number // 2}",
                        "metric": "toy",
                        "higher_is_better": True,
                        "run_id": f"run-{card_number // 2}",
                        "parent_id": f"parent-{card_number // 2}",
                        "arm": arm,
                        "seed": 20260813,
                        "code": code,
                        "code_sha256": sha256_text(code),
                        "base_code_sha256": sha256_text(base),
                        "tap_runtime_sha256": runtime_sha if arm == "tap" else None,
                        "tap_site_count": tap_audit["site_count"],
                        "source_export_sha256": "a" * 64,
                        "split_sha256": "b" * 64,
                    }
                )
        manifest = root / "manifest.jsonl"
        manifest.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        loaded = load_manifest(manifest, runtime_sha)
        assert len(loaded) == 18
        print("SPT_REPLAY_WORKER_SELF_TEST_PASS", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--index", type=int)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--checkpoints", default="30,60,120,240,360,600")
    parser.add_argument("--poll-s", type=float, default=0.10)
    parser.add_argument("--workbase", type=Path)
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--hf-cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--container-sha256")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(args.runtime_source)
        return
    if None in (args.manifest, args.index, args.out, args.workbase, args.container_sha256):
        parser.error("--manifest --index --out --workbase --container-sha256 are required")
    args.checkpoints = sorted({float(value) for value in args.checkpoints.split(",")})
    if not args.checkpoints or args.checkpoints[0] <= 0 or args.poll_s <= 0:
        raise RuntimeError("positive checkpoints and poll interval required")
    args.workbase.mkdir(parents=True, exist_ok=True)
    args.hf_cache.mkdir(parents=True, exist_ok=True)
    run_one(args)


if __name__ == "__main__":
    main()
