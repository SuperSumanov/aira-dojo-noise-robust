#!/usr/bin/env python3
"""Independent verifier for the frozen schema/probe V2 gate.

This deliberately imports no project validator or worker code.  It consumes the
archived manifests/results/artifacts and, when requested, invokes the pristine
MLE-bench grader again.  The output is a deterministic JSON audit.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path


PROBE_MARKER = re.compile(
    r"^CANDIDATE_PROBE_READY elapsed_s=([0-9]+(?:\.[0-9]+)?) "
    r"sha256=([0-9a-f]{64})$",
    re.MULTILINE,
)
FULL_MARKER = re.compile(
    r"^FULL_CANDIDATE_READY elapsed_s=([0-9]+(?:\.[0-9]+)?) "
    r"sha256=([0-9a-f]{64})$",
    re.MULTILINE,
)
SCORE_RE = re.compile(r'"score"\s*:\s*(-?[0-9]+(?:\.[0-9]+)?)')


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def csv_profile(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise AssertionError(f"empty CSV: {path}")
    width = len(rows[0])
    if width < 2 or any(len(row) != width for row in rows):
        raise AssertionError(f"ragged or prediction-free CSV: {path}")
    return rows[0], rows[1:]


def compare_sample(candidate: Path, sample: Path) -> dict:
    cand_header, cand_rows = csv_profile(candidate)
    sample_header, sample_rows = csv_profile(sample)
    same_header = cand_header == sample_header
    same_rows = len(cand_rows) == len(sample_rows)
    ids_match = same_rows and all(a[0] == b[0] for a, b in zip(cand_rows, sample_rows))
    predictions = [tuple(row[1:]) for row in cand_rows]
    nonconstant = len(set(predictions)) > 1
    diff_rows = (
        sum(tuple(a[1:]) != tuple(b[1:]) for a, b in zip(cand_rows, sample_rows))
        if same_rows
        else None
    )
    return {
        "same_header": same_header,
        "same_row_count": same_rows,
        "ids_match": ids_match,
        "prediction_nonconstant": nonconstant,
        "prediction_diff_rows": diff_rows,
        "candidate_specific": bool(
            same_header and same_rows and ids_match and nonconstant and diff_rows and diff_rows > 0
        ),
    }


def run_grader(grader: Path, artifact: Path, task: str, data_dir: Path) -> dict:
    completed = subprocess.run(
        [str(grader), "grade-sample", str(artifact), task, "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    match = SCORE_RE.search(output)
    score = float(match.group(1)) if match else None
    return {
        "rc": completed.returncode,
        "score": score,
        "output_sha256": sha256_text(output),
    }


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def verify_one(
    index: int,
    manifest_row: dict,
    root: Path,
    generation_row: dict,
    data_dir: Path,
    grader: Path | None,
    manifest_hash: str,
) -> dict:
    task = manifest_row["competition"]
    result = load_json(root / "replay" / f"index_{index}" / "result.json")
    probe_path = root / "replay" / f"index_{index}" / "candidate_probe.csv"
    full_path = root / "replay" / f"index_{index}" / "full_candidate.csv"
    sample_paths = sorted((data_dir / task / "prepared" / "public").rglob("sample_submission.csv"))
    check(len(sample_paths) == 1, f"{task}: expected one lowercase sample submission")

    code = manifest_row["code"]
    ast.parse(code)
    checks = {
        "identity": result["index"] == index
        and result["competition"] == task
        and result["seed"] == manifest_row["seed"]
        and result["card_id"] == manifest_row["card_id"],
        "manifest_hash": result["manifest_sha256"] == manifest_hash,
        "source_hash": result["source_export_sha256"] == manifest_row["source_export_sha256"],
        "code_hash": sha256_text(code) == manifest_row["code_sha256"] == result["code_sha256"],
        "topology": generation_row["task"] == task
        and generation_row["seed"] == manifest_row["seed"]
        and generation_row["topology_mode"] == "draft_valid"
        and generation_row["code_nodes"] == 1
        and generation_row["selected_node_step"] == 1
        and generation_row["selected_node_is_buggy"] is False,
        "continuous_and_clean_exit": result["continuous_execution"] is True and result["final_rc"] == 0,
        "probe_hash": sha256_file(probe_path) == result["probe"]["sub_sha256"],
        "probe_deadline": float(result["probe"]["captured_elapsed_s"]) <= 120.0,
        "probe_grade": result["probe"]["grade"]["grade_rc"] == 0
        and math.isfinite(float(result["probe"]["grade"]["sub_score"])),
        "probe_immutable": result["probe_mutated_after_capture"] is False,
        "full_hash": sha256_file(full_path) == result["submission_events"][1]["sub_sha256"],
        "full_deadline": float(result["submission_events"][1]["first_seen_elapsed_s"]) <= 600.0,
        "full_grade": result["submission_events"][1]["grade"]["grade_rc"] == 0
        and math.isfinite(float(result["submission_events"][1]["grade"]["sub_score"])),
        "ordered_distinct_events": len(result["submission_events"]) == 2
        and result["submission_events"][0]["sub_sha256"] == result["probe"]["sub_sha256"]
        and result["submission_events"][0]["first_seen_elapsed_s"]
        < result["submission_events"][1]["first_seen_elapsed_s"]
        and result["submission_events"][0]["sub_sha256"]
        != result["submission_events"][1]["sub_sha256"],
    }

    workdir = Path(result["workdir"])
    stdout = (workdir / "stdout.log").read_text(encoding="utf-8", errors="replace")
    stderr = (workdir / "stderr.log").read_text(encoding="utf-8", errors="replace")
    markers_text = stdout + "\n" + stderr
    probe_markers = PROBE_MARKER.findall(markers_text)
    full_markers = FULL_MARKER.findall(markers_text)
    checks["markers"] = (
        len(probe_markers) == 1
        and probe_markers[0][1] == sha256_file(probe_path)
        and len(full_markers) == 1
        and full_markers[0][1] == sha256_file(full_path)
    )
    checks["workdir_solution"] = sha256_file(workdir / "solution.py") == manifest_row["code_sha256"]

    sample_comparison = compare_sample(probe_path, sample_paths[0])
    checks["candidate_specific_csv"] = sample_comparison["candidate_specific"]

    # This is intentionally only a provenance sanity check, not a proof of model fidelity.
    # The outcome report records the separate manual semantic code audit.
    checks["training_data_and_probe_symbols"] = all(
        token in code
        for token in ("train.csv", "test.csv", "candidate_probe.csv", "CANDIDATE_PROBE_READY")
    ) and any(token in code for token in (".fit(", "lgb.train(", "run_training("))

    regrades = None
    if grader is not None:
        probe_regrade = run_grader(grader, probe_path, task, data_dir)
        full_regrade = run_grader(grader, full_path, task, data_dir)
        checks["independent_regrade"] = (
            probe_regrade["rc"] == 0
            and full_regrade["rc"] == 0
            and math.isclose(
                float(probe_regrade["score"]),
                float(result["probe"]["grade"]["sub_score"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(full_regrade["score"]),
                float(result["submission_events"][1]["grade"]["sub_score"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        )
        regrades = {"probe": probe_regrade, "full": full_regrade}

    for label, passed in checks.items():
        check(passed is True, f"{task}: failed independent check {label}")

    return {
        "index": index,
        "task": task,
        "seed": manifest_row["seed"],
        "checks": checks,
        "probe_host_capture_s": result["probe"]["captured_elapsed_s"],
        "probe_score": result["probe"]["grade"]["sub_score"],
        "full_first_seen_s": result["submission_events"][1]["first_seen_elapsed_s"],
        "full_score": result["submission_events"][1]["grade"]["sub_score"],
        "sample_comparison": sample_comparison,
        "regrades": regrades,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--grader", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = args.root / "replay_manifest.jsonl"
    manifest_hash = sha256_file(manifest_path)
    manifest = load_jsonl(manifest_path)
    extraction = load_json(args.root / "replay_manifest.audit.json")
    generation = load_json(args.root / "generation_manifest.audit.json")
    primary = load_json(args.root / "schema_probe_validation.json")

    check(len(manifest) == 2, "expected exactly two replay rows")
    check(len({row["competition"] for row in manifest}) == 2, "tasks are not distinct")
    check(extraction["replay_manifest_sha256"] == manifest_hash, "extraction manifest hash")
    check(primary["manifest_sha256"] == manifest_hash, "primary validator manifest hash")
    check(primary["decision"] == "PASS", "primary decision is not PASS")
    generation_by_task = {row["task"]: row for row in generation["rows"]}

    rows = [
        verify_one(
            index,
            row,
            args.root,
            generation_by_task[row["competition"]],
            args.data_dir,
            args.grader,
            manifest_hash,
        )
        for index, row in enumerate(manifest)
    ]
    payload = {
        "schema_version": 1,
        "verdict": "PASS",
        "independent_of_project_validator": True,
        "manifest_sha256": manifest_hash,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=args.output.parent, delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(args.output)
    print(
        "INDEPENDENT_SCHEMA_V2_PASS "
        + " ".join(
            f"{row['task']}:{row['probe_host_capture_s']:.6f}s:"
            f"{row['probe_score']:.5f}->{row['full_score']:.5f}"
            for row in rows
        )
    )


if __name__ == "__main__":
    main()
