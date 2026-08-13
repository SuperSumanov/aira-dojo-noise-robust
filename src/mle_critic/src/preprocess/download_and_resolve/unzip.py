"""Recursively extract all ``.tar.gz`` archives below a directory."""

from __future__ import annotations

import argparse
from pathlib import Path
import tarfile
from typing import Sequence


def find_archives(root_dir: Path) -> list[Path]:
    """Return all ``.tar.gz`` files below ``root_dir`` in stable order."""
    root_dir = root_dir.expanduser().resolve()
    if not root_dir.is_dir():
        raise NotADirectoryError(f"Input directory does not exist or is not a directory: {root_dir}")
    return sorted(path for path in root_dir.rglob("*.tar.gz") if path.is_file())


def extract_archive(archive: Path) -> None:
    """Extract one archive beside itself using tarfile's safe data filter."""
    with tarfile.open(archive, mode="r:gz") as tar:
        # The data filter rejects absolute paths, path traversal, device files,
        # and links that escape the destination directory.
        tar.extractall(path=archive.parent, filter="data")


def extract_archives(root_dir: Path, *, quiet: bool = False) -> list[Path]:
    """Extract every ``.tar.gz`` below ``root_dir`` into its archive directory.

    Args:
        root_dir: Directory to search recursively.
        quiet: Suppress per-archive progress messages.

    Returns:
        Archives extracted successfully.

    Raises:
        NotADirectoryError: If ``root_dir`` is not a directory.
        RuntimeError: If one or more archives cannot be extracted. Other valid
            archives are still processed before the error is raised.
    """
    archives = find_archives(root_dir)
    extracted: list[Path] = []
    failures: list[tuple[Path, Exception]] = []

    for index, archive in enumerate(archives, start=1):
        if not quiet:
            print(f"[{index}/{len(archives)}] extracting {archive}")
        try:
            extract_archive(archive)
            extracted.append(archive)
        except (OSError, tarfile.TarError) as error:
            failures.append((archive, error))
            print(f"[{index}/{len(archives)}] FAILED {archive}: {error}")

    if failures:
        details = "\n".join(f"  - {archive}: {error}" for archive, error in failures)
        raise RuntimeError(f"Failed to extract {len(failures)} of {len(archives)} archives:\n{details}")

    return extracted


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Recursively extract every .tar.gz archive beside itself."
    )
    parser.add_argument("directory", type=Path, help="Root directory to search recursively.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-archive progress output.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the archive extraction CLI."""
    args = parse_args(argv)
    archives = extract_archives(args.directory, quiet=args.quiet)
    if not args.quiet:
        print(f"Extraction complete: {len(archives)} archives extracted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
