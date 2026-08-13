"""Checkpointed downloader and reasoning-free extractor for FOREAGENT alignments."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "aira-dojo-external-audit/1"})
    with urllib.request.urlopen(request, timeout=300) as source, temporary.open("wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, destination)


def compact_one(source: Path, destination: Path, source_index: int, row: dict[str, Any]) -> tuple[int, str]:
    root = json.loads(source.read_text(encoding="utf-8"))
    results = root.get("results") if isinstance(root, dict) else None
    if not isinstance(results, list):
        raise RuntimeError(f"missing results list in {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for ordinal, result in enumerate(results):
            if not isinstance(result, dict):
                raise RuntimeError(f"non-dict result {ordinal} in {source}")
            solutions = result.get("solutions")
            groundtruth = result.get("groundtruth")
            prediction = result.get("prediction")
            if not isinstance(solutions, list) or len(solutions) != 2:
                raise RuntimeError(f"bad solutions at {ordinal} in {source}")
            if not isinstance(groundtruth, dict) or not isinstance(prediction, dict):
                raise RuntimeError(f"bad groundtruth/prediction at {ordinal} in {source}")
            compact = {
                "source_index": source_index,
                "task": row["task"],
                "model_family": row["model_family"],
                "release_run": row["release_run"],
                "ordinal": ordinal,
                "log_index": result.get("log_index"),
                "solution_paths": [solutions[0].get("path"), solutions[1].get("path")],
                "scores": [solutions[0].get("score"), solutions[1].get("score")],
                "is_lower_better": groundtruth.get("is_lower_better"),
                "groundtruth_best_index": groundtruth.get("best_index"),
                "prediction_best_index": prediction.get("best_index"),
                "confidence": prediction.get("confidence"),
                "release_correct": result.get("correct"),
            }
            handle.write(json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)
    return len(results), sha256_file(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--compact-dir", type=Path, required=True)
    parser.add_argument("--download-log", type=Path, required=True)
    parser.add_argument("--master-out", type=Path, required=True)
    args = parser.parse_args()

    manifest_raw = args.manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    revision = manifest["source"]["revision"]
    repo_id = manifest["source"]["repo_id"]
    files = manifest["files"]
    if manifest.get("file_count") != 156 or len(files) != 156:
        raise RuntimeError("manifest file count is not frozen 156")

    if args.download_log.exists():
        state = json.loads(args.download_log.read_text(encoding="utf-8"))
        if state.get("manifest_sha256") != hashlib.sha256(manifest_raw).hexdigest():
            raise RuntimeError("download log belongs to a different manifest")
    else:
        state = {
            "schema_version": 1,
            "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "repo_id": repo_id,
            "revision": revision,
            "completed": {},
        }

    for source_index, row in enumerate(files):
        source_path = str(row["path"])
        expected_size = int(row["size"])
        raw_path = args.cache_dir / source_path
        compact_path = (
            args.compact_dir
            / row["task"]
            / row["model_family"]
            / f"release_run_{int(row['release_run'])}.jsonl"
        )
        meta_path = compact_path.with_suffix(".meta.json")

        prior = state["completed"].get(source_path)
        reusable = False
        if prior and compact_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            reusable = (
                meta.get("source_path") == source_path
                and meta.get("source_index") == source_index
                and meta.get("compact_sha256") == sha256_file(compact_path)
                and prior.get("compact_sha256") == meta.get("compact_sha256")
            )
        if reusable:
            print(
                "FOREAGENT_FETCH_REUSE",
                f"index={source_index + 1}/156",
                f"task={row['task']}",
                f"model={row['model_family']}",
                f"run={row['release_run']}",
            )
            continue

        if not raw_path.exists() or raw_path.stat().st_size != expected_size:
            quoted_revision = urllib.parse.quote(revision, safe="")
            quoted_path = urllib.parse.quote(source_path, safe="/")
            url = f"https://huggingface.co/datasets/{repo_id}/resolve/{quoted_revision}/{quoted_path}"
            download(url, raw_path)
        if raw_path.stat().st_size != expected_size:
            raise RuntimeError(f"size mismatch for {source_path}")
        raw_sha256 = sha256_file(raw_path)
        rows, compact_sha256 = compact_one(raw_path, compact_path, source_index, row)
        meta = {
            "source_index": source_index,
            "source_path": source_path,
            "source_bytes": expected_size,
            "source_sha256": raw_sha256,
            "compact_path": str(compact_path),
            "compact_rows": rows,
            "compact_sha256": compact_sha256,
        }
        atomic_json(meta_path, meta)
        state["completed"][source_path] = meta
        atomic_json(args.download_log, state)
        print(
            "FOREAGENT_FETCH_DONE",
            f"index={source_index + 1}/156",
            f"task={row['task']}",
            f"model={row['model_family']}",
            f"run={row['release_run']}",
            f"rows={rows}",
            f"bytes={expected_size}",
            f"sha256={raw_sha256}",
        )

    if len(state["completed"]) != 156:
        raise RuntimeError(f"only {len(state['completed'])}/156 files completed")

    args.master_out.parent.mkdir(parents=True, exist_ok=True)
    master_tmp = args.master_out.with_name(args.master_out.name + ".tmp")
    total_rows = 0
    with master_tmp.open("wb") as target:
        for row in files:
            compact_path = (
                args.compact_dir
                / row["task"]
                / row["model_family"]
                / f"release_run_{int(row['release_run'])}.jsonl"
            )
            meta_path = compact_path.with_suffix(".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta["compact_sha256"] != sha256_file(compact_path):
                raise RuntimeError(f"compact hash mismatch for {compact_path}")
            total_rows += int(meta["compact_rows"])
            with compact_path.open("rb") as source:
                shutil.copyfileobj(source, target, length=1024 * 1024)
        target.flush()
        os.fsync(target.fileno())
    os.replace(master_tmp, args.master_out)
    state["master"] = {
        "path": str(args.master_out),
        "rows": total_rows,
        "bytes": args.master_out.stat().st_size,
        "sha256": sha256_file(args.master_out),
    }
    atomic_json(args.download_log, state)
    print(
        "FOREAGENT_FETCH_ALL_PASS",
        "files=156",
        f"rows={total_rows}",
        f"bytes={args.master_out.stat().st_size}",
        f"sha256={state['master']['sha256']}",
    )


if __name__ == "__main__":
    main()
