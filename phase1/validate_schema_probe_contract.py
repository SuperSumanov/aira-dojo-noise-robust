#!/usr/bin/env python3
"""Independent, fail-closed validation for the two-task schema/probe smoke."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import re
import tempfile
from pathlib import Path


PROBE_MARKER = re.compile(
    r"(?m)^CANDIDATE_PROBE_READY elapsed_s=([0-9]+(?:\.[0-9]+)?) sha256=([0-9a-f]{64})\s*$"
)
FULL_MARKER = re.compile(
    r"(?m)^FULL_CANDIDATE_READY elapsed_s=([0-9]+(?:\.[0-9]+)?) sha256=([0-9a-f]{64})\s*$"
)
FALLBACK_MARKER = re.compile(r"(?m)^COMMON_FALLBACK_READY(?:\s|$)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or len({row.get("card_id") for row in rows}) != len(rows):
        raise RuntimeError("malformed or duplicate replay manifest")
    return rows


def resolve_snapshot(index_dir: Path, row: dict) -> Path:
    rel = row.get("snapshot_relpath")
    if not isinstance(rel, str):
        raise RuntimeError("snapshot relative path missing")
    relpath = Path(rel)
    if relpath.is_absolute() or ".." in relpath.parts:
        raise RuntimeError(f"unsafe snapshot path: {rel}")
    path = index_dir / relpath
    if not path.is_file():
        raise RuntimeError(f"snapshot missing: {path}")
    if path.stat().st_size != row.get("sub_size") or sha256_file(path) != row.get("sub_sha256"):
        raise RuntimeError(f"snapshot provenance mismatch: {path}")
    return path


def finite_grade(row: dict) -> bool:
    grade = row.get("grade")
    if not isinstance(grade, dict) or grade.get("grade_rc") != 0:
        return False
    value = grade.get("sub_score")
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def compare_to_sample(probe_path: Path, sample_path: Path) -> dict:
    with probe_path.open(encoding="utf-8-sig", newline="") as probe_file, sample_path.open(
        encoding="utf-8-sig", newline=""
    ) as sample_file:
        probe_reader = csv.reader(probe_file)
        sample_reader = csv.reader(sample_file)
        probe_header = next(probe_reader, None)
        sample_header = next(sample_reader, None)
        if not probe_header or probe_header != sample_header or len(probe_header) < 2:
            return {
                "same_header": probe_header == sample_header,
                "same_row_count": False,
                "prediction_diff_rows": 0,
                "any_prediction_nonconstant": False,
                "candidate_specific": False,
            }
        unique_values = [set() for _ in probe_header[1:]]
        diff_rows = 0
        row_count = 0
        same_count = True
        for probe_row, sample_row in itertools.zip_longest(probe_reader, sample_reader):
            if probe_row is None or sample_row is None:
                same_count = False
                continue
            row_count += 1
            if len(probe_row) != len(probe_header) or len(sample_row) != len(sample_header):
                same_count = False
                continue
            if probe_row[1:] != sample_row[1:]:
                diff_rows += 1
            for values, item in zip(unique_values, probe_row[1:]):
                if len(values) < 2:
                    values.add(item)
        nonconstant = any(len(values) > 1 for values in unique_values)
        return {
            "same_header": True,
            "same_row_count": same_count,
            "rows": row_count,
            "prediction_diff_rows": diff_rows,
            "any_prediction_nonconstant": nonconstant,
            "candidate_specific": same_count and row_count > 0 and diff_rows > 0 and nonconstant,
        }


def validate_one(
    index: int,
    manifest_row: dict,
    out_dir: Path,
    data_dir: Path,
    manifest_sha: str,
) -> dict:
    index_dir = out_dir / f"index_{index}"
    result_path = index_dir / "result.json"
    if not result_path.is_file():
        raise RuntimeError(f"result missing: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    checks["identity"] = (
        result.get("index") == index
        and result.get("card_id") == manifest_row.get("card_id")
        and result.get("competition") == manifest_row.get("competition")
        and result.get("seed") == manifest_row.get("seed")
    )
    checks["manifest_hash"] = result.get("manifest_sha256") == manifest_sha
    checks["code_hash"] = result.get("code_sha256") == manifest_row.get("code_sha256")
    checks["source_export_hash"] = result.get("source_export_sha256") == manifest_row.get(
        "source_export_sha256"
    )
    checks["continuous_execution"] = result.get("continuous_execution") is True
    checks["checkpoint_grid"] = [float(row["cap_s"]) for row in result.get("checkpoints", [])] == [
        30.0,
        60.0,
        120.0,
        240.0,
        360.0,
        600.0,
    ]

    workdir = Path(result.get("workdir", ""))
    solution_path = workdir / "solution.py"
    checks["workdir_solution_hash"] = solution_path.is_file() and sha256_file(solution_path) == result.get(
        "code_sha256"
    )
    stdout_path, stderr_path = workdir / "stdout.log", workdir / "stderr.log"
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    combined = stdout + "\n" + stderr
    probe_markers = [
        {"elapsed_s": float(match.group(1)), "sha256": match.group(2)}
        for match in PROBE_MARKER.finditer(combined)
    ]
    full_markers = [
        {"elapsed_s": float(match.group(1)), "sha256": match.group(2)}
        for match in FULL_MARKER.finditer(combined)
    ]
    checks["one_probe_marker"] = len(probe_markers) == 1
    checks["at_most_one_full_marker"] = len(full_markers) <= 1
    checks["no_common_fallback"] = len(FALLBACK_MARKER.findall(combined)) == 0

    probe = result.get("probe")
    probe_path: Path | None = None
    sample_comparison: dict = {}
    if isinstance(probe, dict):
        probe_path = resolve_snapshot(index_dir, probe)
        checks["probe_finite_grade"] = finite_grade(probe)
        checks["probe_host_by_120"] = float(probe.get("captured_elapsed_s", math.inf)) <= 120.0
        checks["probe_unmutated"] = result.get("probe_mutated_after_capture") is False
        final_probe = workdir / "candidate_probe.csv"
        checks["probe_persists"] = final_probe.is_file() and sha256_file(final_probe) == probe.get("sub_sha256")
        samples = sorted((data_dir / manifest_row["competition"] / "prepared" / "public").rglob("sample_submission.csv"))
        if len(samples) != 1:
            raise RuntimeError(f"sample submission count={len(samples)} for {manifest_row['competition']}")
        sample_comparison = compare_to_sample(probe_path, samples[0])
        sample_comparison["byte_hash_differs"] = sha256_file(probe_path) != sha256_file(samples[0])
        checks["probe_candidate_specific"] = bool(
            sample_comparison.get("candidate_specific") and sample_comparison["byte_hash_differs"]
        )
        checks["probe_marker_hash"] = (
            len(probe_markers) == 1 and probe_markers[0]["sha256"] == probe.get("sub_sha256")
        )
    else:
        for name in (
            "probe_finite_grade",
            "probe_host_by_120",
            "probe_unmutated",
            "probe_persists",
            "probe_candidate_specific",
            "probe_marker_hash",
        ):
            checks[name] = False

    events = result.get("submission_events", [])
    for event in events:
        if event.get("sub_copied"):
            resolve_snapshot(index_dir, event)
    checks["first_submission_is_probe"] = bool(
        probe is not None and events and events[0].get("sub_sha256") == probe.get("sub_sha256")
    )
    checks["first_submission_by_120"] = bool(
        events and float(events[0].get("captured_elapsed_s", math.inf)) <= 120.0
    )

    full_transition = False
    full_event_index = None
    if len(full_markers) == 1:
        marker = full_markers[0]
        for event in events[1:]:
            if (
                event.get("sub_sha256") == marker["sha256"]
                and float(event.get("first_seen_elapsed_s", math.inf)) <= 600.0
                and finite_grade(event)
            ):
                full_transition = True
                full_event_index = event.get("event_index")
                break
    checks["valid_full_transition_if_marked"] = len(full_markers) == 0 or full_transition

    probe_required = (
        "identity",
        "manifest_hash",
        "code_hash",
        "source_export_hash",
        "continuous_execution",
        "checkpoint_grid",
        "workdir_solution_hash",
        "one_probe_marker",
        "at_most_one_full_marker",
        "no_common_fallback",
        "probe_finite_grade",
        "probe_host_by_120",
        "probe_unmutated",
        "probe_persists",
        "probe_candidate_specific",
        "probe_marker_hash",
        "first_submission_is_probe",
        "first_submission_by_120",
        "valid_full_transition_if_marked",
    )
    probe_pass = all(checks.get(name) is True for name in probe_required)
    return {
        "index": index,
        "card_id": manifest_row["card_id"],
        "competition": manifest_row["competition"],
        "seed": manifest_row["seed"],
        "checks": checks,
        "probe_pass": probe_pass,
        "probe_host_capture_s": probe.get("captured_elapsed_s") if isinstance(probe, dict) else None,
        "probe_score": probe.get("grade", {}).get("sub_score") if isinstance(probe, dict) else None,
        "submission_event_count": len(events),
        "probe_markers": probe_markers,
        "full_markers": full_markers,
        "valid_full_transition": full_transition,
        "full_event_index": full_event_index,
        "sample_comparison": sample_comparison,
        "final_rc": result.get("final_rc"),
        "wall_s": result.get("wall_s"),
    }


def atomic_json(path: Path, payload: object) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def self_test() -> None:
    marker = "CANDIDATE_PROBE_READY elapsed_s=1.25 sha256=" + "a" * 64
    assert PROBE_MARKER.findall(marker) == [("1.25", "a" * 64)]
    assert not PROBE_MARKER.findall("print('CANDIDATE_PROBE_READY')")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sample = root / "sample.csv"
        probe = root / "probe.csv"
        sample.write_text("id,pred\n1,0.5\n2,0.5\n", encoding="utf-8")
        probe.write_text("id,pred\n1,0.2\n2,0.8\n", encoding="utf-8")
        comparison = compare_to_sample(probe, sample)
        assert comparison["candidate_specific"] is True
        probe.write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")
        assert compare_to_sample(probe, sample)["candidate_specific"] is False
    print("SCHEMA_PROBE_VALIDATOR_SELF_TEST_PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("/research/d7/spc/yzyang4/mle-bench-data"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.manifest or not args.audit or not args.out_dir:
        parser.error("--manifest --audit --out-dir are required")

    manifest_rows = load_manifest(args.manifest)
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    manifest_sha = sha256_file(args.manifest)
    if audit.get("replay_manifest_sha256") != manifest_sha:
        raise RuntimeError("extraction audit/replay manifest hash mismatch")
    if len(manifest_rows) != 2 or len({row["competition"] for row in manifest_rows}) != 2:
        raise RuntimeError("smoke matrix must contain exactly two distinct tasks")
    rows = [
        validate_one(index, row, args.out_dir, args.data_dir, manifest_sha)
        for index, row in enumerate(manifest_rows)
    ]
    probe_pass_count = sum(row["probe_pass"] for row in rows)
    full_transition_count = sum(row["valid_full_transition"] for row in rows)
    if probe_pass_count < 2:
        decision = "FAIL"
    elif full_transition_count >= 1:
        decision = "PASS"
    else:
        decision = "PARTIAL"
    payload = {
        "schema_version": 1,
        "decision": decision,
        "gate": {
            "pass": "both candidate-specific probes pass by host 120s and at least one valid full transition by 600s",
            "partial": "both probes pass by 120s but no valid full transition by 600s",
            "fail": "either probe fails validity, provenance, candidate-specificity, immutability, or 120s deadline",
        },
        "manifest_sha256": manifest_sha,
        "probe_pass_count": probe_pass_count,
        "full_transition_count": full_transition_count,
        "rows": rows,
    }
    output_path = args.out_dir / "schema_probe_validation.json"
    if output_path.exists():
        raise RuntimeError(f"refusing existing validation output: {output_path}")
    atomic_json(output_path, payload)
    print(
        "SCHEMA_PROBE_VALIDATION "
        f"decision={decision} probes={probe_pass_count}/2 full_transitions={full_transition_count}/2"
    )
    if decision == "FAIL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
