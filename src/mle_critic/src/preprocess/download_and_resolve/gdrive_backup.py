#!/usr/bin/env python3
"""Back up prepared MLEBench data to Google Drive through rclone."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
from pathlib import Path


REMOTE_ROOT = "gdrive:mle/mlebench"


def check_rclone() -> None:
    """Fail early when rclone or the configured Google Drive remote is absent."""
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone is not available on PATH")
    result = subprocess.run(
        ["rclone", "config", "show", "gdrive"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "no such remote"
        raise RuntimeError(f"rclone remote 'gdrive' is not configured: {detail}")


def run_rclone(*args: str) -> None:
    subprocess.run(["rclone", *args], check=True)


def remote_file_exists(path: str) -> bool:
    result = subprocess.run(
        ["rclone", "lsf", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def remote_dir_exists(path: str) -> bool:
    result = subprocess.run(
        ["rclone", "lsd", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def make_tarball(source: Path, archive: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Missing source directory: {source}")
    with tarfile.open(archive, "w") as tar:
        for child in source.iterdir():
            tar.add(child, arcname=child.name)


def backup_task(task_dir: Path) -> None:
    task_name = task_dir.name
    prepared_dir = task_dir / "prepared"
    remote_dir = f"{REMOTE_ROOT}/{task_name}/prepared"
    remote_exists = remote_dir_exists(remote_dir)
    if not remote_exists:
        run_rclone("mkdir", remote_dir)

    temporary_archives: list[Path] = []
    try:
        for split in ("public", "private"):
            archive = prepared_dir / f"{split}.tar"
            remote_archive = f"{remote_dir}/{archive.name}"

            # Existing local archives are reusable.  Otherwise create one.
            if not archive.exists():
                make_tarball(prepared_dir / split, archive)
                temporary_archives.append(archive)

            # Upload when the remote archive is absent, or when the prepared
            # directory was just created (the latter makes the intent explicit).
            if not remote_exists or not remote_file_exists(remote_archive):
                run_rclone("copyto", str(archive), remote_archive)
    finally:
        # Archives are staging files only; remove both newly-created and
        # pre-existing local archives after all uploads have been attempted.
        for split in ("public", "private"):
            archive = prepared_dir / f"{split}.tar"
            if archive.exists():
                archive.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=Path, nargs="?", default=Path("data/mlebench"))
    args = parser.parse_args()
    check_rclone()
    if not args.data_dir.is_dir():
        raise SystemExit(f"Data directory does not exist: {args.data_dir}")
    for task_dir in sorted(p for p in args.data_dir.iterdir() if p.is_dir()):
        backup_task(task_dir)


if __name__ == "__main__":
    main()
