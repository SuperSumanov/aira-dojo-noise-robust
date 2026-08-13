#!/usr/bin/env python3
"""Replay one generated candidate once while observing an anytime artifact contract.

The candidate sees only MLE-bench public data.  A host-side watcher captures immutable
candidate_probe.csv and every stable submission.csv transition with monotonic timestamps.
Copied artifacts are graded only after the candidate process has stopped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from trajectory_fidelity_worker import (
    DEFAULT_CACHE,
    DEFAULT_DATA,
    SIF,
    build_command,
    copy_submission,
    file_sha256,
    grade_snapshot,
    kill_process_group,
    read_text_snapshot,
)


PROBE_MARKER = re.compile(
    r"(?m)^CANDIDATE_PROBE_READY elapsed_s=([0-9]+(?:\.[0-9]+)?) sha256=([0-9a-f]{64})\s*$"
)
FULL_MARKER = re.compile(
    r"(?m)^FULL_CANDIDATE_READY elapsed_s=([0-9]+(?:\.[0-9]+)?) sha256=([0-9a-f]{64})\s*$"
)
FALLBACK_MARKER = re.compile(r"(?m)^COMMON_FALLBACK_READY(?:\s|$)")


def safe_stat(path: Path) -> tuple[int, int, int, int] | None:
    try:
        value = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(value.st_mode):
        raise RuntimeError(f"artifact is not a regular file: {path}")
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def relative_copy_record(record: dict, root: Path) -> dict:
    public = dict(record)
    raw = public.pop("snapshot_path", None)
    public["snapshot_relpath"] = str(Path(raw).relative_to(root)) if raw else None
    return public


def capture_log_metadata(stdout_path: Path, stderr_path: Path) -> dict:
    stdout, stdout_bytes, stdout_sha, stdout_changed = read_text_snapshot(stdout_path)
    stderr, stderr_bytes, stderr_sha, stderr_changed = read_text_snapshot(stderr_path)
    return {
        "stdout_bytes": stdout_bytes,
        "stderr_bytes": stderr_bytes,
        "stdout_sha256": stdout_sha,
        "stderr_sha256": stderr_sha,
        "stdout_changed_during_read": stdout_changed,
        "stderr_changed_during_read": stderr_changed,
        "probe_marker_count": len(PROBE_MARKER.findall(stdout + "\n" + stderr)),
        "full_marker_count": len(FULL_MARKER.findall(stdout + "\n" + stderr)),
        "fallback_marker_count": len(FALLBACK_MARKER.findall(stdout + "\n" + stderr)),
    }


def monitor_contract(
    proc: subprocess.Popen,
    workdir: Path,
    stdout_path: Path,
    stderr_path: Path,
    checkpoints: list[float],
    staging: Path,
    poll_s: float,
    started: float,
) -> dict:
    stable_s = max(0.20, 2.0 * poll_s)
    probe_source = workdir / "candidate_probe.csv"
    submission_source = workdir / "submission.csv"
    probe_pending: tuple[int, int, int, int] | None = None
    probe_pending_since: float | None = None
    probe_captured_signature: tuple[int, int, int, int] | None = None
    probe_record: dict | None = None
    probe_first_seen_s: float | None = None
    probe_mutated_after_capture = False
    sub_pending: tuple[int, int, int, int] | None = None
    sub_pending_since: float | None = None
    sub_captured_signature: tuple[int, int, int, int] | None = None
    events: list[dict] = []
    fixed: list[dict] = []
    next_checkpoint = 0
    process_exit_elapsed_s: float | None = None

    def observe(elapsed: float) -> None:
        nonlocal probe_pending, probe_pending_since, probe_captured_signature
        nonlocal probe_record, probe_first_seen_s, probe_mutated_after_capture
        nonlocal sub_pending, sub_pending_since, sub_captured_signature

        probe_signature = safe_stat(probe_source)
        if probe_signature is not None and probe_first_seen_s is None:
            probe_first_seen_s = elapsed
        if probe_record is not None and probe_signature != probe_captured_signature:
            probe_mutated_after_capture = True
        if probe_record is None:
            if probe_signature is None:
                probe_pending = None
                probe_pending_since = None
            elif probe_signature != probe_pending:
                probe_pending = probe_signature
                probe_pending_since = elapsed
            elif probe_pending_since is not None and elapsed - probe_pending_since >= stable_s:
                raw = copy_submission(probe_source, staging / "probe" / "candidate_probe.csv")
                if raw["sub_copied"] and not raw["sub_source_changed_during_copy"]:
                    probe_captured_signature = probe_signature
                    probe_record = {
                        "first_seen_elapsed_s": round(probe_first_seen_s or elapsed, 6),
                        "captured_elapsed_s": round(elapsed, 6),
                        "source_signature": list(probe_signature),
                        **relative_copy_record(raw, staging),
                    }

        sub_signature = safe_stat(submission_source)
        if sub_signature is None:
            sub_pending = None
            sub_pending_since = None
        elif sub_signature == sub_captured_signature:
            sub_pending = None
            sub_pending_since = None
        elif sub_signature != sub_pending:
            sub_pending = sub_signature
            sub_pending_since = elapsed
        elif sub_pending_since is not None and elapsed - sub_pending_since >= stable_s:
            if len(events) >= 16:
                raise RuntimeError("more than 16 stable submission transitions")
            event_index = len(events)
            raw = copy_submission(
                submission_source,
                staging / "events" / f"submission_event_{event_index:02d}.csv",
            )
            if raw["sub_copied"] and not raw["sub_source_changed_during_copy"]:
                sub_captured_signature = sub_signature
                events.append(
                    {
                        "event_index": event_index,
                        "first_seen_elapsed_s": round(sub_pending_since, 6),
                        "captured_elapsed_s": round(elapsed, 6),
                        "source_signature": list(sub_signature),
                        **relative_copy_record(raw, staging),
                    }
                )
                sub_pending = None
                sub_pending_since = None

    def capture_checkpoint(cap: float, elapsed: float) -> None:
        raw = copy_submission(
            submission_source,
            staging / "checkpoints" / f"submission_t{str(cap).replace('.', 'p')}.csv",
        )
        fixed.append(
            {
                "cap_s": cap,
                "capture_elapsed_s": round(elapsed, 6),
                "process_alive": proc.poll() is None,
                "process_rc_at_capture": proc.poll(),
                **relative_copy_record(raw, staging),
                **capture_log_metadata(stdout_path, stderr_path),
            }
        )

    max_cap = checkpoints[-1]
    while True:
        now = time.monotonic()
        elapsed = now - started
        observe(elapsed)
        while next_checkpoint < len(checkpoints) and elapsed >= checkpoints[next_checkpoint]:
            capture_checkpoint(checkpoints[next_checkpoint], elapsed)
            next_checkpoint += 1

        rc = proc.poll()
        if rc is not None and process_exit_elapsed_s is None:
            process_exit_elapsed_s = elapsed
        if rc is not None:
            # Give the final atomic rename enough time to become a stable host event.
            settle_until = time.monotonic() + stable_s + poll_s
            while time.monotonic() < settle_until:
                observe(time.monotonic() - started)
                time.sleep(poll_s)
            elapsed = time.monotonic() - started
            while next_checkpoint < len(checkpoints):
                capture_checkpoint(checkpoints[next_checkpoint], elapsed)
                next_checkpoint += 1
            break
        if elapsed >= max_cap:
            break
        time.sleep(min(poll_s, max_cap - elapsed))

    if proc.poll() is None:
        kill_process_group(proc)
        settle_until = time.monotonic() + stable_s + poll_s
        while time.monotonic() < settle_until:
            observe(time.monotonic() - started)
            time.sleep(poll_s)
    final_rc = int(proc.returncode)
    final_elapsed = time.monotonic() - started
    observe(final_elapsed)
    while next_checkpoint < len(checkpoints):
        capture_checkpoint(checkpoints[next_checkpoint], final_elapsed)
        next_checkpoint += 1

    final_probe_signature = safe_stat(probe_source)
    final_submission_signature = safe_stat(submission_source)
    logs = capture_log_metadata(stdout_path, stderr_path)
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
    combined = stdout_text + "\n" + stderr_text
    probe_markers = [
        {"elapsed_s": float(match.group(1)), "sha256": match.group(2)}
        for match in PROBE_MARKER.finditer(combined)
    ]
    full_markers = [
        {"elapsed_s": float(match.group(1)), "sha256": match.group(2)}
        for match in FULL_MARKER.finditer(combined)
    ]
    return {
        "continuous_execution": True,
        "poll_s": poll_s,
        "stable_window_s": stable_s,
        "wall_s": round(final_elapsed, 6),
        "process_exit_elapsed_s": None if process_exit_elapsed_s is None else round(process_exit_elapsed_s, 6),
        "final_rc": final_rc,
        "probe": probe_record,
        "probe_mutated_after_capture": probe_mutated_after_capture,
        "probe_final_signature": list(final_probe_signature) if final_probe_signature else None,
        "submission_final_signature": list(final_submission_signature) if final_submission_signature else None,
        "submission_events": events,
        "checkpoints": fixed,
        "probe_markers": probe_markers,
        "full_markers": full_markers,
        "fallback_marker_count": len(FALLBACK_MARKER.findall(combined)),
        "final_logs": logs,
    }


def add_grades(payload: dict, competition: str, data_dir: Path, staging: Path) -> None:
    probe = payload.get("probe")
    if isinstance(probe, dict) and probe.get("snapshot_relpath"):
        probe["grade"] = grade_snapshot(staging / probe["snapshot_relpath"], competition, data_dir)
    for collection in (payload["submission_events"], payload["checkpoints"]):
        for row in collection:
            relpath = row.get("snapshot_relpath")
            row["grade"] = grade_snapshot(staging / relpath, competition, data_dir) if relpath else {
                "sub_score": None,
                "grade_rc": None,
                "grade_wall_s": None,
                "grade_output_sha256": None,
                "grade_skipped_reason": "no_stable_snapshot",
            }


def load_manifest(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    required = {"card_id", "competition", "seed", "code", "code_sha256", "source_export_sha256"}
    if not rows or any(not isinstance(row, dict) or required - set(row) for row in rows):
        raise RuntimeError("malformed replay manifest")
    if len({row["card_id"] for row in rows}) != len(rows):
        raise RuntimeError("duplicate replay card_id")
    for row in rows:
        if hashlib.sha256(row["code"].encode("utf-8")).hexdigest() != row["code_sha256"]:
            raise RuntimeError(f"code hash mismatch: {row['card_id']}")
    return rows


def atomic_write_json(path: Path, payload: object) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_one(args: argparse.Namespace) -> None:
    if file_sha256(SIF) != args.container_sha256:
        raise RuntimeError("container image SHA mismatch")
    rows = load_manifest(args.manifest)
    if args.index < 0 or args.index >= len(rows):
        raise RuntimeError(f"index out of range: {args.index}/{len(rows)}")
    row = rows[args.index]
    manifest_sha = file_sha256(args.manifest)
    destination = args.out / f"index_{args.index}"
    if destination.exists():
        raise RuntimeError(f"refusing existing result: {destination}")
    args.out.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".index-{args.index}-", dir=args.out))

    safe_id = hashlib.sha256(row["card_id"].encode("utf-8")).hexdigest()[:20]
    workdir = args.workbase / f"index_{args.index}_{safe_id}"
    if workdir.exists():
        raise RuntimeError(f"refusing existing workdir: {workdir}")
    workdir.mkdir(parents=True)
    (workdir / "solution.py").write_text(row["code"], encoding="utf-8")
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
        proc = subprocess.Popen(
            command,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
        payload = monitor_contract(
            proc,
            workdir,
            stdout_path,
            stderr_path,
            args.checkpoints,
            staging,
            args.poll_s,
            started,
        )
    add_grades(payload, row["competition"], args.data_dir, staging)
    result = {
        "schema_version": 1,
        "index": args.index,
        "card_id": row["card_id"],
        "competition": row["competition"],
        "seed": row["seed"],
        "manifest": str(args.manifest),
        "manifest_sha256": manifest_sha,
        "code_sha256": row["code_sha256"],
        "source_export_sha256": row["source_export_sha256"],
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
        "SCHEMA_PROBE_WORKER_DONE "
        f"index={args.index} task={row['competition']} probe={int(result['probe'] is not None)} "
        f"events={len(result['submission_events'])} rc={result['final_rc']}",
        flush=True,
    )


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        script = root / "toy.py"
        script.write_text(
            "import hashlib,os,pathlib,time\n"
            "start=time.monotonic()\n"
            "def atom(name,text):\n"
            " p=pathlib.Path(name); t=p.with_name('.'+p.name+'.tmp'); "
            "f=t.open('w'); f.write(text); f.flush(); os.fsync(f.fileno()); f.close(); os.replace(t,p)\n"
            "atom('candidate_probe.csv','id,pred\\n1,0.4\\n2,0.6\\n')\n"
            "atom('submission.csv',pathlib.Path('candidate_probe.csv').read_text())\n"
            "h=hashlib.sha256(pathlib.Path('candidate_probe.csv').read_bytes()).hexdigest()\n"
            "print(f'CANDIDATE_PROBE_READY elapsed_s={time.monotonic()-start:.3f} sha256={h}',flush=True)\n"
            # Keep the probe unchanged for comfortably more than the 0.20 s
            # stable window; 0.30 s was scheduler-jitter-sensitive on gpu nodes.
            "time.sleep(0.60)\n"
            "atom('submission.csv','id,pred\\n1,0.3\\n2,0.7\\n')\n"
            "h=hashlib.sha256(pathlib.Path('submission.csv').read_bytes()).hexdigest()\n"
            "print(f'FULL_CANDIDATE_READY elapsed_s={time.monotonic()-start:.3f} sha256={h}',flush=True)\n"
            "time.sleep(1)\n",
            encoding="utf-8",
        )
        stdout_path, stderr_path = root / "stdout", root / "stderr"
        staging = root / "staging"
        staging.mkdir()
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            started = time.monotonic()
            proc = subprocess.Popen(
                [sys.executable, str(script)], cwd=root, stdout=out, stderr=err, start_new_session=True
            )
            payload = monitor_contract(
                proc, root, stdout_path, stderr_path, [0.2, 0.5, 2.0], staging, 0.02, started
            )
        if payload["probe"] is None:
            raise AssertionError(
                f"probe not captured payload={payload} stdout={stdout_path.read_text(errors='replace')} "
                f"stderr={stderr_path.read_text(errors='replace')}"
            )
        assert payload["probe_mutated_after_capture"] is False
        assert len(payload["submission_events"]) == 2
        assert payload["submission_events"][0]["sub_sha256"] == payload["probe"]["sub_sha256"]
        assert len(payload["probe_markers"]) == 1 and len(payload["full_markers"]) == 1
        assert payload["final_rc"] == 0
        print("SCHEMA_PROBE_WORKER_SELF_TEST_PASS", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--index", type=int)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--checkpoints", default="30,60,120,240,360,600")
    parser.add_argument("--poll-s", type=float, default=0.10)
    parser.add_argument("--workbase", type=Path)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--hf-cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--container-sha256")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
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
