#!/usr/bin/env python3
"""Frozen matrix and helpers for the probe-contract safety A/B."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


SEED = 873
SCHEMA_VERSION = 1
ARMS = ("original", "contract")
ISSUE_BY_ARM = {
    "original": "probe_contract_ab_safety_v1_original",
    "contract": "probe_contract_ab_safety_v1_contract",
}

# Order is frozen before any candidate generation or API POST.  Each adjacent
# pair is launched simultaneously.  Arm order alternates to avoid a systematic
# command-order bias even though paired steps are concurrent.
MATRIX = (
    {"index": 0, "task": "chaii-hindi-and-tamil-question-answering", "arm": "original"},
    {"index": 1, "task": "chaii-hindi-and-tamil-question-answering", "arm": "contract"},
    {"index": 2, "task": "leaf-classification", "arm": "contract"},
    {"index": 3, "task": "leaf-classification", "arm": "original"},
    {"index": 4, "task": "nomad2018-predict-transparent-conductors", "arm": "original"},
    {"index": 5, "task": "nomad2018-predict-transparent-conductors", "arm": "contract"},
    {"index": 6, "task": "plant-pathology-2020-fgvc7", "arm": "contract"},
    {"index": 7, "task": "plant-pathology-2020-fgvc7", "arm": "original"},
    {"index": 8, "task": "google-quest-challenge", "arm": "original"},
    {"index": 9, "task": "google-quest-challenge", "arm": "contract"},
    {"index": 10, "task": "tabular-playground-series-dec-2021", "arm": "contract"},
    {"index": 11, "task": "tabular-playground-series-dec-2021", "arm": "original"},
)
TASKS = tuple(dict.fromkeys(row["task"] for row in MATRIX))

# Public competition metrics, frozen from task descriptions.  +1 means larger
# raw pristine score is better, -1 means smaller is better.
ORIENTATION = {
    "chaii-hindi-and-tamil-question-answering": 1,
    "leaf-classification": -1,
    "nomad2018-predict-transparent-conductors": -1,
    "plant-pathology-2020-fgvc7": 1,
    "google-quest-challenge": 1,
    "tabular-playground-series-dec-2021": 1,
}


def row_for_index(index: int) -> dict:
    if index < 0 or index >= len(MATRIX) or MATRIX[index]["index"] != index:
        raise RuntimeError(f"index outside frozen A/B matrix: {index}")
    row = dict(MATRIX[index])
    row["seed"] = SEED
    row["issue"] = ISSUE_BY_ARM[row["arm"]]
    return row


def validate_matrix() -> None:
    if tuple(row["index"] for row in MATRIX) != tuple(range(12)):
        raise RuntimeError("A/B indices are not contiguous")
    if len(TASKS) != 6 or set(ORIENTATION) != set(TASKS):
        raise RuntimeError("A/B task/orientation set mismatch")
    for task in TASKS:
        rows = [row for row in MATRIX if row["task"] == task]
        if len(rows) != 2 or {row["arm"] for row in rows} != set(ARMS):
            raise RuntimeError(f"A/B pairing mismatch: {task}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


validate_matrix()
