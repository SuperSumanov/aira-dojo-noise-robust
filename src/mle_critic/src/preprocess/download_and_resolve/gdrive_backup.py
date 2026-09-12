#!/usr/bin/env python3
"""Back up prepared MLEBench data to Google Drive through rclone.

For every task directory, ``prepared/public`` and ``prepared/private`` are
packed into a tar archive and uploaded to
``gdrive:mle/mlebench/<task>/prepared/<split>.tar``.  The archive is only
built when the remote copy is missing, so re-running after an interrupted
backup does not re-pack hundreds of gigabytes.  Use --force to re-upload
everything regardless of what is already on the remote.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
from pathlib import Path


REMOTE_ROOT = "gdrive:mle/mlebench"
SPLITS = ("public", "private")

# rclone exit codes: 3 = directory not found, 4 = file not found.
# See https://rclone.org/docs/#exit-code
RCLONE_NOT_FOUND = (3, 4)


def run_rclone(*args: str) -> None:
    """Run rclone with stdout/stderr attached, so long transfers show progress."""
    subprocess.run(["rclone", *args], check=True)


def capture_rclone(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["rclone", *args], capture_output=True, text=True)


def check_rclone() -> None:
    """Fail early when rclone or the configured Google Drive remote is absent."""
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone is not available on PATH")
    result = capture_rclone("config", "show", "gdrive")
    if result.returncode != 0:
        detail = result.stderr.strip() or "no such remote"
        raise RuntimeError(f"rclone remote 'gdrive' is not configured: {detail}")


def remote_file_size(remote_path: str) -> int | None:
    """Size of a single remote file in bytes, or None when it does not exist."""
    result = capture_rclone("lsf", "--format", "sp", remote_path)
    if result.returncode in RCLONE_NOT_FOUND:
        return None
    if result.returncode != 0:
        # Anything else (network trouble, expired token, rate limit) must not be
        # mistaken for "missing", which would trigger a full re-pack and upload.
        raise RuntimeError(f"rclone lsf {remote_path} failed: {result.stderr.strip()}")
    entries = [line for line in result.stdout.splitlines() if line.strip()]
    if len(entries) != 1:
        raise RuntimeError(f"rclone lsf {remote_path} matched {len(entries)} entries: {entries}")
    return int(entries[0].split(";", 1)[0])


def make_tarball(source: Path, archive: Path) -> None:
    """Pack ``source`` into ``archive`` without ever leaving a short archive behind."""
    if not source.is_dir():
        raise FileNotFoundError(f"Missing source directory: {source}")
    partial = archive.with_name(archive.name + ".partial")
    partial.unlink(missing_ok=True)
    with tarfile.open(partial, "w") as tar:
        for child in source.iterdir():
            tar.add(child, arcname=child.name)
    # Rename only once the archive is complete, so a killed run cannot leave a
    # truncated public.tar that later runs would happily upload.
    partial.replace(archive)


def backup_split(task_name: str, prepared_dir: Path, split: str, force: bool) -> None:
    source = prepared_dir / split
    archive = prepared_dir / f"{split}.tar"
    remote_archive = f"{REMOTE_ROOT}/{task_name}/prepared/{archive.name}"

    if not source.is_dir():
        print(f"[skip] {task_name}/{split}: no local directory {source}")
        return

    if not force and (remote_size := remote_file_size(remote_archive)):
        print(f"[keep] {task_name}/{split}: {remote_archive} already exists ({remote_size} bytes)")
        return

    if archive.exists():
        # A previous upload failed and kept its archive; that file is complete
        # because make_tarball renames into place.
        print(f"[pack] {task_name}/{split}: reusing local {archive.name}")
    else:
        print(f"[pack] {task_name}/{split}: packing {source}")
        make_tarball(source, archive)

    size = archive.stat().st_size
    run_rclone("copyto", str(archive), remote_archive)
    uploaded_size = remote_file_size(remote_archive)
    if uploaded_size != size:
        raise RuntimeError(
            f"{remote_archive} is {uploaded_size} bytes after upload, expected {size}"
        )
    archive.unlink()
    print(f"[done] {task_name}/{split}: uploaded {size} bytes")


def backup_task(task_dir: Path, force: bool) -> None:
    prepared_dir = task_dir / "prepared"
    if not prepared_dir.is_dir():
        print(f"[skip] {task_dir.name}: no local directory {prepared_dir}")
        return
    for split in SPLITS:
        backup_split(task_dir.name, prepared_dir, split, force)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path, nargs="?", default=Path("data/mlebench"))
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-pack and re-upload even when the remote archive already exists",
    )
    args = parser.parse_args()
    check_rclone()
    if not args.data_dir.is_dir():
        raise SystemExit(f"Data directory does not exist: {args.data_dir}")

    task_dirs = sorted(p for p in args.data_dir.iterdir() if p.is_dir())
    failed: list[str] = []
    for task_dir in task_dirs:
        try:
            backup_task(task_dir, args.force)
        except Exception as exc:
            # One unreadable task should not abort the remaining backup.
            print(f"[fail] {task_dir.name}: {exc}")
            failed.append(task_dir.name)
    if failed:
        raise SystemExit(f"{len(failed)} of {len(task_dirs)} tasks failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
