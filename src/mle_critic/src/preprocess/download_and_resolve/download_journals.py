"""Incrementally download the shared journal folder from Google Drive.

Files are written under ``data/augmented_mle_critic/raw_journal`` while
preserving the directory structure in Google Drive.  Existing files are
skipped, and interrupted ``.part`` downloads are resumed on the next run.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import time
from typing import Sequence

import gdown
import requests


DEFAULT_FOLDER_URL = (
    "https://drive.google.com/drive/folders/"
    "1yKoLdcEpouFsG8RpsWH0XPFPEVWi9BNz?usp=drive_link"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "data" / "augmented_mle_critic" / "raw_journal"


def download_journals(
    folder_url: str = DEFAULT_FOLDER_URL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    quiet: bool = False,
) -> list[Path]:
    """Download missing journal files and return their local paths.

    gdown is used to recursively enumerate the public folder.  Files are then
    downloaded individually through Drive's user-content endpoint.  The latter
    avoids a gdown failure mode where large public files show a virus-scan
    confirmation page that gdown cannot parse.

    Args:
        folder_url: Public Google Drive folder URL.
        output_dir: Directory that should contain the shared folder's contents.
        quiet: Suppress gdown's progress output.

    Returns:
        Local paths for all files in the shared folder, including files that
        were already present and therefore skipped.

    Raises:
        RuntimeError: If the folder cannot be listed or any file still fails
            after retries.
    """
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = gdown.download_folder(
        url=folder_url,
        output=str(output_dir),
        quiet=quiet,
        skip_download=True,
    )
    if entries is None:
        raise RuntimeError(f"Failed to list Google Drive folder: {folder_url}")

    local_paths: list[Path] = []
    failures: list[tuple[str, Path, Exception]] = []
    session = requests.Session()
    for index, entry in enumerate(entries, start=1):
        relative_path = Path(entry.path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise RuntimeError(f"Unsafe path returned by Google Drive: {entry.path!r}")

        destination = output_dir / relative_path
        local_paths.append(destination)
        if destination.is_file():
            if not quiet:
                print(f"[{index}/{len(entries)}] skip {relative_path}")
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        if not quiet:
            print(f"[{index}/{len(entries)}] download {relative_path}")
        try:
            _download_drive_file(session, entry.id, destination, quiet=quiet)
        except Exception as error:  # Continue so one bad permission does not block the folder.
            failures.append((entry.id, relative_path, error))
            print(f"[{index}/{len(entries)}] FAILED {relative_path}: {error}")

    if failures:
        details = "\n".join(
            f"  - {path} (https://drive.google.com/file/d/{file_id}/view): {error}"
            for file_id, path, error in failures
        )
        raise RuntimeError(f"Failed to download {len(failures)} of {len(entries)} files:\n{details}")

    return local_paths


def _download_drive_file(
    session: requests.Session,
    file_id: str,
    destination: Path,
    *,
    quiet: bool,
    attempts: int = 4,
) -> None:
    """Download one public Drive file, resuming an existing .part file."""
    url = "https://drive.usercontent.google.com/download"
    part_path = destination.with_name(destination.name + ".part")

    for attempt in range(1, attempts + 1):
        offset = part_path.stat().st_size if part_path.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with session.get(
                url,
                params={"id": file_id, "export": "download", "confirm": "t"},
                headers=headers,
                stream=True,
                timeout=(30, 30),
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" in content_type:
                    preview = response.content[:300].decode("utf-8", errors="replace")
                    raise RuntimeError(f"Drive returned HTML instead of file data: {preview!r}")

                append = offset > 0 and response.status_code == requests.codes.partial_content
                mode = "ab" if append else "wb"
                downloaded = offset if append else 0
                total = _response_total_size(response, downloaded)
                with part_path.open(mode) as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        output.write(chunk)
                        downloaded += len(chunk)
                        if not quiet and total:
                            print(
                                f"  {downloaded / 2**20:.1f}/{total / 2**20:.1f} MiB",
                                end="\r",
                                flush=True,
                            )

            if total is not None and part_path.stat().st_size != total:
                raise RuntimeError(
                    f"size mismatch: got {part_path.stat().st_size} bytes, expected {total}"
                )
            os.replace(part_path, destination)
            if not quiet:
                print(" " * 60, end="\r", flush=True)
            return
        except (requests.RequestException, OSError, RuntimeError):
            if attempt == attempts:
                raise
            time.sleep(2 ** (attempt - 1))


def _response_total_size(response: requests.Response, offset: int) -> int | None:
    """Return the complete file size described by a Drive response."""
    content_range = response.headers.get("Content-Range")
    if content_range and "/" in content_range:
        total = content_range.rsplit("/", 1)[1]
        if total.isdigit():
            return int(total)
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit():
        return offset + int(content_length)
    return None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Incrementally download shared MLE journal data from Google Drive."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_FOLDER_URL,
        help="Google Drive shared-folder URL (default: the augmented journal folder).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Destination directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress download progress output.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the journal downloader CLI."""
    args = parse_args(argv)
    files = download_journals(args.url, args.output_dir, quiet=args.quiet)
    if not args.quiet:
        print(f"Journal sync complete: {len(files)} files present in {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
