#!/usr/bin/env python3
"""Frozen matrix and helpers for the probe-contract safety A/B."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


ARMS = ("original", "contract")


@dataclass(frozen=True)
class ExperimentSpec:
    version: str
    schema_version: int
    experiment: str
    seed: int
    matrix: tuple[dict, ...]
    orientation: Mapping[str, int]
    sample_submission: Mapping[str, tuple[str, str | None]]
    issue_by_arm: Mapping[str, str]
    compliance_min: int
    coverage_min: int
    coverage_gain_min: int
    quality_pairs_min: int

    @property
    def tasks(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(row["task"] for row in self.matrix))

# Order is frozen before any candidate generation or API POST.  Each adjacent
# pair is launched simultaneously.  Arm order alternates to avoid a systematic
# command-order bias even though paired steps are concurrent.
V1_MATRIX = (
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

# Public competition metrics, frozen from task descriptions.  +1 means larger
# raw pristine score is better, -1 means smaller is better.
V1_ORIENTATION = {
    "chaii-hindi-and-tamil-question-answering": 1,
    "leaf-classification": -1,
    "nomad2018-predict-transparent-conductors": -1,
    "plant-pathology-2020-fgvc7": 1,
    "google-quest-challenge": 1,
    "tabular-playground-series-dec-2021": 1,
}

V2_MATRIX = (
    {"index": 0, "task": "aerial-cactus-identification", "arm": "original"},
    {"index": 1, "task": "aerial-cactus-identification", "arm": "contract"},
    {"index": 2, "task": "AI4Code", "arm": "contract"},
    {"index": 3, "task": "AI4Code", "arm": "original"},
    {"index": 4, "task": "denoising-dirty-documents", "arm": "original"},
    {"index": 5, "task": "denoising-dirty-documents", "arm": "contract"},
    {"index": 6, "task": "kuzushiji-recognition", "arm": "contract"},
    {"index": 7, "task": "kuzushiji-recognition", "arm": "original"},
    {
        "index": 8,
        "task": "learning-agency-lab-automated-essay-scoring-2",
        "arm": "original",
    },
    {
        "index": 9,
        "task": "learning-agency-lab-automated-essay-scoring-2",
        "arm": "contract",
    },
    {"index": 10, "task": "text-normalization-challenge-english-language", "arm": "contract"},
    {"index": 11, "task": "text-normalization-challenge-english-language", "arm": "original"},
    {"index": 12, "task": "mlsp-2013-birds", "arm": "original"},
    {"index": 13, "task": "mlsp-2013-birds", "arm": "contract"},
    {"index": 14, "task": "whale-categorization-playground", "arm": "contract"},
    {"index": 15, "task": "whale-categorization-playground", "arm": "original"},
)

# Public competition metric direction, frozen from each public description.
# +1 means larger pristine score is better; -1 means smaller is better.
V2_ORIENTATION = {
    "aerial-cactus-identification": 1,
    "AI4Code": 1,
    "denoising-dirty-documents": -1,
    "kuzushiji-recognition": 1,
    "learning-agency-lab-automated-essay-scoring-2": 1,
    "text-normalization-challenge-english-language": 1,
    "mlsp-2013-birds": 1,
    "whale-categorization-playground": 1,
}

# (path relative to prepared/public, optional member for a zip archive).
V2_SAMPLE_SUBMISSION = {
    "aerial-cactus-identification": ("sample_submission.csv", None),
    "AI4Code": ("sample_submission.csv", None),
    "denoising-dirty-documents": ("sampleSubmission.csv", None),
    "kuzushiji-recognition": ("sample_submission.csv", None),
    "learning-agency-lab-automated-essay-scoring-2": ("sample_submission.csv", None),
    "text-normalization-challenge-english-language": (
        "en_sample_submission_2.csv.zip",
        "en_sample_submission_2.csv",
    ),
    "mlsp-2013-birds": ("sample_submission.csv", None),
    "whale-categorization-playground": ("sample_submission.csv", None),
}


def _sample_map(tasks: tuple[str, ...]) -> Mapping[str, tuple[str, str | None]]:
    return MappingProxyType({task: ("sample_submission.csv", None) for task in tasks})


V1_TASKS = tuple(dict.fromkeys(row["task"] for row in V1_MATRIX))
V1_SPEC = ExperimentSpec(
    version="v1",
    schema_version=1,
    experiment="probe_contract_ab_safety_v1",
    seed=873,
    matrix=V1_MATRIX,
    orientation=MappingProxyType(V1_ORIENTATION),
    sample_submission=_sample_map(V1_TASKS),
    issue_by_arm=MappingProxyType(
        {
            "original": "probe_contract_ab_safety_v1_original",
            "contract": "probe_contract_ab_safety_v1_contract",
        }
    ),
    compliance_min=4,
    coverage_min=4,
    coverage_gain_min=2,
    quality_pairs_min=3,
)
V2_SPEC = ExperimentSpec(
    version="v2",
    schema_version=2,
    experiment="probe_contract_ab_safety_v2",
    seed=887,
    matrix=V2_MATRIX,
    orientation=MappingProxyType(V2_ORIENTATION),
    sample_submission=MappingProxyType(V2_SAMPLE_SUBMISSION),
    issue_by_arm=MappingProxyType(
        {
            "original": "probe_contract_ab_safety_v2_original",
            "contract": "probe_contract_ab_safety_v2_contract",
        }
    ),
    compliance_min=6,
    coverage_min=6,
    coverage_gain_min=3,
    quality_pairs_min=4,
)


def spec_for_version(version: str) -> ExperimentSpec:
    specs = {"v1": V1_SPEC, "v2": V2_SPEC}
    try:
        return specs[version]
    except KeyError as exc:
        raise RuntimeError(f"unknown probe-contract A/B version: {version}") from exc


# Backward-compatible V1 aliases used by frozen V1 fixtures and reports.
SEED = V1_SPEC.seed
SCHEMA_VERSION = V1_SPEC.schema_version
MATRIX = V1_SPEC.matrix
TASKS = V1_SPEC.tasks
ORIENTATION = V1_SPEC.orientation
ISSUE_BY_ARM = V1_SPEC.issue_by_arm


def row_for_index(index: int, version: str = "v1") -> dict:
    spec = spec_for_version(version)
    if index < 0 or index >= len(spec.matrix) or spec.matrix[index]["index"] != index:
        raise RuntimeError(f"index outside frozen A/B matrix: {index}")
    row = dict(spec.matrix[index])
    row["seed"] = spec.seed
    row["issue"] = spec.issue_by_arm[row["arm"]]
    return row


def validate_matrix(spec: ExperimentSpec) -> None:
    if tuple(row["index"] for row in spec.matrix) != tuple(range(len(spec.matrix))):
        raise RuntimeError("A/B indices are not contiguous")
    if len(spec.tasks) * len(ARMS) != len(spec.matrix):
        raise RuntimeError("A/B matrix is not exactly two arms per task")
    if set(spec.orientation) != set(spec.tasks) or set(spec.sample_submission) != set(spec.tasks):
        raise RuntimeError("A/B task/orientation set mismatch")
    if set(spec.issue_by_arm) != set(ARMS):
        raise RuntimeError("A/B issue/arm set mismatch")
    for task in spec.tasks:
        rows = [row for row in spec.matrix if row["task"] == task]
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


validate_matrix(V1_SPEC)
validate_matrix(V2_SPEC)
