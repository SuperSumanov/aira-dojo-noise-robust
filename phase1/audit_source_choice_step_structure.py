#!/usr/bin/env python3
"""Post-result, label-unused structural audit for source-choice step semantics."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any


GROUP_FIELDS = {
    "schema_version",
    "group_id",
    "task",
    "source_size",
    "candidates",
    "winner_candidate_sha256",
}
CANDIDATE_FIELDS = {
    "candidate_id_sha256",
    "code",
    "code_sha256",
    "depth",
    "operator",
    "step",
}


class StepStructureError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_integer(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StepStructureError(f"{name} must be an integer")
    return value


def audit(
    path: Path,
    *,
    expected_sha256: str,
    expected_groups: int,
    expected_candidates: int,
) -> dict[str, Any]:
    digest = sha256_file(path)
    if digest != expected_sha256:
        raise StepStructureError(f"input SHA mismatch: {digest}")

    groups = 0
    candidates = 0
    unique_steps = 0
    contiguous_steps = 0
    same_depth = 0
    same_operator = 0
    source_sizes: collections.Counter[int] = collections.Counter()
    step_spans: collections.Counter[int] = collections.Counter()
    operator_sets: collections.Counter[str] = collections.Counter()

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise StepStructureError(f"invalid JSON at line {line_number}") from error
            if not isinstance(row, dict) or set(row) != GROUP_FIELDS:
                raise StepStructureError(f"unexpected group schema at line {line_number}")
            items = row["candidates"]
            source_size = exact_integer(row["source_size"], "source_size")
            if not isinstance(items, list) or len(items) != source_size or source_size < 2:
                raise StepStructureError(f"candidate/source-size mismatch at line {line_number}")
            if any(not isinstance(item, dict) or set(item) != CANDIDATE_FIELDS for item in items):
                raise StepStructureError(f"unexpected candidate schema at line {line_number}")

            # The winner field is necessarily parsed with the JSON object, but is never
            # indexed, validated, copied, compared, or used in any statistic below.
            steps = [exact_integer(item["step"], "step") for item in items]
            depths = [exact_integer(item["depth"], "depth") for item in items]
            operators = [item["operator"] for item in items]
            if any(not isinstance(operator, str) or not operator for operator in operators):
                raise StepStructureError(f"invalid operator at line {line_number}")

            groups += 1
            candidates += source_size
            source_sizes[source_size] += 1
            unique_steps += len(set(steps)) == source_size
            contiguous_steps += sorted(steps) == list(range(min(steps), max(steps) + 1))
            same_depth += len(set(depths)) == 1
            same_operator += len(set(operators)) == 1
            step_spans[max(steps) - min(steps)] += 1
            operator_sets["|".join(sorted(set(operators)))] += 1

    if groups != expected_groups or candidates != expected_candidates:
        raise StepStructureError(
            f"frozen census mismatch: groups={groups}, candidates={candidates}"
        )

    return {
        "protocol": "exploratory-source-choice-step-structure-audit-v1",
        "status": "STRUCTURE_ONLY_POST_RESULT_AUDIT_COMPLETE",
        "input_sha256": digest,
        "winner_field_used_in_statistics": False,
        "groups": groups,
        "candidates": candidates,
        "groups_all_candidate_steps_unique": unique_steps,
        "groups_candidate_steps_contiguous": contiguous_steps,
        "groups_candidate_steps_noncontiguous": groups - contiguous_steps,
        "groups_all_candidates_same_depth": same_depth,
        "groups_all_candidates_same_operator": same_operator,
        "source_size_counts": dict(sorted(source_sizes.items())),
        "step_span_counts": dict(sorted(step_spans.items())),
        "operator_set_counts": dict(sorted(operator_sets.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-groups", type=int, required=True)
    parser.add_argument("--expected-candidates", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    result = audit(
        arguments.input,
        expected_sha256=arguments.expected_sha256,
        expected_groups=arguments.expected_groups,
        expected_candidates=arguments.expected_candidates,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
