"""Build a deterministic metadata-only manifest for released FOREAGENT alignments.

This script queries file listings at a pinned Hugging Face dataset revision.  It
does not download or parse any alignment outcome.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPO_ID = "zjunlp/PredictBeforeExecute"
DEFAULT_REVISION = "6b322cb88bdbcb2b2d3897ec7d0ded94a5bb2d06"
MODEL_FAMILY = {
    "deepseek-reasoner": "deepseek",
    "gpt-5_1": "gpt",
}
ALIGNMENT_RE = re.compile(
    r"^solutions_subset_50/(?P<task>[^/]+)/report/alignment_"
    r"(?P=task)_n2_data-both_(?P<model_token>deepseek-reasoner|gpt-5_1)_"
    r"(?P<temperature>[0-9]+p[0-9]+)_pboost_cot_(?P<timestamp>[0-9]{8}_[0-9]{6})\.json$"
)
HEADLINE_REPORT_RE = re.compile(
    r"^solutions_subset_50/report/grade_report_alltasks_from_reports_n0_"
    r"(?P<model_token>deepseek-reasoner|gpt-5_1)_[0-9]+p[0-9]+_pboost_cot_[0-9]{8}_[0-9]{6}\.txt$"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_tree(revision: str, path: str) -> list[dict[str, Any]]:
    quoted_revision = urllib.parse.quote(revision, safe="")
    quoted_path = urllib.parse.quote(path.strip("/"), safe="/")
    url = (
        f"https://huggingface.co/api/datasets/{REPO_ID}/tree/"
        f"{quoted_revision}/{quoted_path}?limit=1000&expand=false"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "aira-dojo-external-audit/1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        rows = json.load(response)
    if not isinstance(rows, list):
        raise RuntimeError(f"unexpected tree response for {path}: {type(rows).__name__}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--csv-out", type=Path, required=True)
    args = parser.parse_args()

    root_rows = read_tree(args.revision, "solutions_subset_50")
    root_prefix = "solutions_subset_50/"
    tasks = sorted(
        row["path"][len(root_prefix) :]
        for row in root_rows
        if row.get("type") == "directory"
        and str(row.get("path", "")).startswith(root_prefix)
        and "/" not in str(row["path"])[len(root_prefix) :]
        and row["path"] != "solutions_subset_50/report"
        and row["path"] != "solutions_subset_50/per_task_results"
    )
    if len(tasks) != 26:
        raise RuntimeError(f"expected 26 task directories, found {len(tasks)}: {tasks}")

    headline_rows = read_tree(args.revision, "solutions_subset_50/report")
    headline_reports = sorted(
        (
            {"path": row["path"], "size": row["size"], "oid": row["oid"]}
            for row in headline_rows
            if row.get("type") == "file" and HEADLINE_REPORT_RE.fullmatch(str(row.get("path", "")))
        ),
        key=lambda row: row["path"],
    )
    headline_counts: dict[str, int] = {"deepseek-reasoner": 0, "gpt-5_1": 0}
    for row in headline_reports:
        match = HEADLINE_REPORT_RE.fullmatch(row["path"])
        assert match is not None
        headline_counts[match.group("model_token")] += 1
    if headline_counts != {"deepseek-reasoner": 3, "gpt-5_1": 3}:
        raise RuntimeError(f"unexpected all-task headline reports: {headline_counts}")

    files: list[dict[str, Any]] = []
    excluded_alignment_files: list[dict[str, Any]] = []
    for task in tasks:
        report_path = f"solutions_subset_50/{task}/report"
        rows = read_tree(args.revision, report_path)
        selected: list[dict[str, Any]] = []
        for row in rows:
            if row.get("type") != "file":
                continue
            path = str(row.get("path", ""))
            match = ALIGNMENT_RE.fullmatch(path)
            if match is None:
                if Path(path).name.startswith("alignment_") and path.endswith(".json"):
                    excluded_alignment_files.append(
                        {
                            "task": task,
                            "path": path,
                            "size": row.get("size"),
                            "oid": row.get("oid"),
                            "reason": "not_in_complete_3x26_headline_model_grid",
                        }
                    )
                continue
            if match.group("task") != task:
                raise RuntimeError(f"task mismatch in {path}")
            size = row.get("size")
            oid = row.get("oid")
            if not isinstance(size, int) or size <= 0 or not isinstance(oid, str) or not oid:
                raise RuntimeError(f"missing immutable metadata for {path}")
            model_token = match.group("model_token")
            selected.append(
                {
                    "task": task,
                    "model_family": MODEL_FAMILY[model_token],
                    "model_token": model_token,
                    "temperature_token": match.group("temperature"),
                    "timestamp": match.group("timestamp"),
                    "path": path,
                    "size": size,
                    "oid": oid,
                }
            )
        by_family: dict[str, list[dict[str, Any]]] = {"deepseek": [], "gpt": []}
        for row in selected:
            by_family[row["model_family"]].append(row)
        if {key: len(value) for key, value in by_family.items()} != {"deepseek": 3, "gpt": 3}:
            raise RuntimeError(
                f"expected exactly 3 releases per model family for {task}, got "
                f"{ {key: len(value) for key, value in by_family.items()} }; "
                f"matched={[row['path'] for row in selected]}"
            )
        for family in ("deepseek", "gpt"):
            family_rows = sorted(by_family[family], key=lambda row: (row["timestamp"], row["path"]))
            for release_run, row in enumerate(family_rows, start=1):
                row["release_run"] = release_run
                files.append(row)

    files.sort(key=lambda row: (row["task"], row["model_family"], row["release_run"]))
    if len(files) != 156:
        raise RuntimeError(f"expected 156 alignment files, found {len(files)}")
    if len({row["path"] for row in files}) != len(files):
        raise RuntimeError("duplicate paths in manifest")

    manifest = {
        "schema_version": 1,
        "source": {
            "repo_id": REPO_ID,
            "revision": args.revision,
            "root": "solutions_subset_50",
        },
        "selection_contract": {
            "task_count": 26,
            "model_families": ["deepseek", "gpt"],
            "files_per_model_task": 3,
            "filename_contract": ALIGNMENT_RE.pattern,
            "selection_basis": "six pinned all-task report filenames (3 deepseek-reasoner, 3 gpt-5_1)",
        },
        "task_count": len(tasks),
        "file_count": len(files),
        "total_bytes": sum(row["size"] for row in files),
        "tasks": tasks,
        "headline_reports": headline_reports,
        "excluded_alignment_files": sorted(excluded_alignment_files, key=lambda row: row["path"]),
        "files": files,
    }
    json_raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_bytes(json_raw)

    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task",
                "model_family",
                "release_run",
                "model_token",
                "temperature_token",
                "timestamp",
                "size",
                "oid",
                "path",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(files)

    print(
        "FOREAGENT_ALIGNMENT_MANIFEST_PASS",
        f"revision={args.revision}",
        f"tasks={len(tasks)}",
        f"files={len(files)}",
        f"bytes={manifest['total_bytes']}",
        f"sha256={sha256_bytes(json_raw)}",
    )


if __name__ == "__main__":
    main()
