#!/usr/bin/env python3
"""Independent raw-artifact verifier for probe-contract A/B.

This file intentionally imports no project worker, builder, extractor, validator,
or helper.  It reconstructs topology, provenance, scoreability, regrades every
unique artifact with the pristine grader, and recomputes the frozen K0--K3 verdict.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import itertools
import json
import math
import re
import shutil
import statistics
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


SEED = 887
CHECKPOINTS = [30.0, 60.0, 120.0, 240.0, 360.0, 600.0]
MATRIX = (
    (0, "aerial-cactus-identification", "original"),
    (1, "aerial-cactus-identification", "contract"),
    (2, "AI4Code", "contract"),
    (3, "AI4Code", "original"),
    (4, "denoising-dirty-documents", "original"),
    (5, "denoising-dirty-documents", "contract"),
    (6, "kuzushiji-recognition", "contract"),
    (7, "kuzushiji-recognition", "original"),
    (8, "learning-agency-lab-automated-essay-scoring-2", "original"),
    (9, "learning-agency-lab-automated-essay-scoring-2", "contract"),
    (10, "text-normalization-challenge-english-language", "contract"),
    (11, "text-normalization-challenge-english-language", "original"),
    (12, "mlsp-2013-birds", "original"),
    (13, "mlsp-2013-birds", "contract"),
    (14, "whale-categorization-playground", "contract"),
    (15, "whale-categorization-playground", "original"),
)
ORIENTATION = {
    "aerial-cactus-identification": 1,
    "AI4Code": 1,
    "denoising-dirty-documents": -1,
    "kuzushiji-recognition": 1,
    "learning-agency-lab-automated-essay-scoring-2": 1,
    "text-normalization-challenge-english-language": 1,
    "mlsp-2013-birds": 1,
    "whale-categorization-playground": 1,
}
ISSUE = {
    "original": "probe_contract_ab_safety_v2_original",
    "contract": "probe_contract_ab_safety_v2_contract",
}
SAMPLE_SUBMISSION = {
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
CONTRACT_PREFIXES = (
    "- CRITICAL ANYTIME ARTIFACT CONTRACT:",
    "- Preserve the probe as immutable `candidate_probe.csv`.",
    "- Continue IN THE SAME PYTHON PROCESS from that probe into the full candidate method.",
    "- The host evaluates artifact creation time independently.",
)
PROBE_MARKER = re.compile(
    r"(?m)^CANDIDATE_PROBE_READY elapsed_s=([0-9]+(?:\.[0-9]+)?) "
    r"sha256=([0-9a-f]{64})\s*$"
)
FULL_MARKER = re.compile(
    r"(?m)^FULL_CANDIDATE_READY elapsed_s=([0-9]+(?:\.[0-9]+)?) "
    r"sha256=([0-9a-f]{64})\s*$"
)
FALLBACK_MARKER = re.compile(r"(?m)^COMMON_FALLBACK_READY(?:\s|$)")
SCORE_RE = re.compile(r'"score"\s*:\s*(-?[0-9]+(?:\.[0-9]+)?)')


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    check(all(isinstance(row, dict) for row in rows), f"non-object JSONL row: {path}")
    return rows


def safe_snapshot(index_dir: Path, row: dict[str, Any]) -> Path:
    rel = row.get("snapshot_relpath")
    check(isinstance(rel, str), "snapshot_relpath missing")
    relpath = Path(rel)
    check(not relpath.is_absolute() and ".." not in relpath.parts, f"unsafe snapshot path: {rel}")
    path = index_dir / relpath
    check(path.is_file(), f"snapshot missing: {path}")
    check(path.stat().st_size == row.get("sub_size"), f"snapshot size mismatch: {path}")
    check(sha256_file(path) == row.get("sub_sha256"), f"snapshot hash mismatch: {path}")
    return path


def compare_sample(candidate: Path, sample: Path) -> dict[str, Any]:
    try:
        candidate_handle = candidate.open(encoding="utf-8-sig", newline="")
        sample_handle = sample.open(encoding="utf-8-sig", newline="")
    except (AssertionError, csv.Error, UnicodeError) as error:
        return {
            "same_header": False,
            "same_row_count": False,
            "ids_match": False,
            "prediction_diff_rows": None,
            "prediction_nonconstant": False,
            "candidate_specific": False,
            "parse_error": type(error).__name__,
        }
    with candidate_handle, sample_handle:
        candidate_reader = csv.reader(candidate_handle)
        sample_reader = csv.reader(sample_handle)
        candidate_header = next(candidate_reader, None)
        sample_header = next(sample_reader, None)
        if not candidate_header or candidate_header != sample_header or len(candidate_header) < 2:
            return {
                "same_header": candidate_header == sample_header,
                "same_row_count": False,
                "ids_match": False,
                "prediction_diff_rows": 0,
                "prediction_nonconstant": False,
                "candidate_specific": False,
            }
        unique_predictions: set[tuple[str, ...]] = set()
        same_count = True
        ids_match = True
        diff_rows = 0
        row_count = 0
        for candidate_row, sample_row in itertools.zip_longest(candidate_reader, sample_reader):
            if candidate_row is None or sample_row is None:
                same_count = False
                continue
            row_count += 1
            if len(candidate_row) != len(candidate_header) or len(sample_row) != len(sample_header):
                same_count = False
                continue
            ids_match = ids_match and candidate_row[0] == sample_row[0]
            diff_rows += int(candidate_row[1:] != sample_row[1:])
            if len(unique_predictions) < 2:
                unique_predictions.add(tuple(candidate_row[1:]))
        nonconstant = len(unique_predictions) > 1
        return {
            "same_header": True,
            "same_row_count": same_count,
            "ids_match": ids_match,
            "rows": row_count,
            "prediction_diff_rows": diff_rows,
            "prediction_nonconstant": nonconstant,
            "candidate_specific": bool(
                same_count and ids_match and row_count > 0 and nonconstant and diff_rows > 0
            ),
        }


def materialize_samples(data_dir: Path, cache_dir: Path) -> dict[str, Path]:
    samples: dict[str, Path] = {}
    for task, (relative, member) in SAMPLE_SUBMISSION.items():
        source = data_dir / task / "prepared" / "public" / relative
        check(source.is_file(), f"sample source missing: {source}")
        if member is None:
            samples[task] = source
            continue
        check(source.suffix.lower() == ".zip", f"unsupported sample archive: {source}")
        destination = cache_dir / f"{task}.sample.csv"
        with zipfile.ZipFile(source) as archive:
            check(archive.namelist().count(member) == 1, f"sample member mismatch: {source}")
            with archive.open(member) as reader, destination.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
        check(destination.stat().st_size > 0, f"empty sample member: {source}/{member}")
        samples[task] = destination
    return samples


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def grade_matches_stored(regrade: dict[str, Any], stored: dict[str, Any]) -> bool:
    if regrade["rc"] != stored.get("grade_rc"):
        return False
    if regrade["rc"] == 0 and finite_number(regrade.get("score")):
        return finite_number(stored.get("sub_score")) and same_scalar(
            regrade["score"], stored["sub_score"]
        )
    return not finite_number(stored.get("sub_score"))


def run_grader(grader: Path, artifact: Path, task: str, data_dir: Path) -> dict[str, Any]:
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


def regrade_cached(
    grader: Path,
    artifact: Path,
    task: str,
    data_dir: Path,
    cache: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    key = (task, sha256_file(artifact))
    if key not in cache:
        cache[key] = run_grader(grader, artifact, task, data_dir)
    return cache[key]


def operator_set(node: dict[str, Any]) -> set[str]:
    value = node.get("operators_used")
    check(isinstance(value, list) and all(isinstance(item, str) for item in value), "bad operators")
    return set(value)


def raw_topology(source_export: Path, experiment_dir: Path) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    export = load_json(source_export)
    journal = experiment_dir / "checkpoint" / "journal.jsonl"
    state_path = experiment_dir / "checkpoint" / "state.json"
    check(journal.is_file() and state_path.is_file(), "missing raw checkpoint files")
    journal_lines = sum(bool(line.strip()) for line in journal.read_text(encoding="utf-8").splitlines())
    state = load_json(state_path)
    current_step = int(state.get("current_step", -1))
    nodes = export.get("nodes")
    check(isinstance(nodes, list) and current_step in (2, 3), "invalid node/state count")
    check(len(nodes) == journal_lines == current_step, "journal/export/state mismatch")
    check(all(isinstance(node, dict) for node in nodes), "non-object node")
    check([node.get("step") for node in nodes] == list(range(current_step)), "noncontiguous nodes")
    root, draft = nodes[0], nodes[1]
    check(not str(root.get("code", "")).strip(), "root contains code")
    check(root.get("parents") == [] and root.get("children") == [1], "bad root topology")
    check(not operator_set(root), "root operator present")
    check(str(draft.get("code", "")).strip() != "" and draft.get("parents") == [0], "bad draft")
    draft_ops = operator_set(draft)
    check("draft" in draft_ops and "debug" not in draft_ops and "improve" not in draft_ops, "bad draft ops")
    if current_step == 2:
        check(draft.get("is_buggy") is False and draft.get("children") == [], "draft not valid leaf")
        return "draft_valid", [draft], draft
    debug = nodes[2]
    check(draft.get("is_buggy") is True and draft.get("children") == [2], "draft/debug edge")
    check(
        str(debug.get("code", "")).strip() != ""
        and debug.get("parents") == [1]
        and debug.get("children") == [],
        "bad debug node",
    )
    debug_ops = operator_set(debug)
    check("debug" in debug_ops and "draft" not in debug_ops and "improve" not in debug_ops, "bad debug ops")
    mode = "debug_valid" if debug.get("is_buggy") is False else "debug_exhausted"
    return mode, [draft, debug], debug


def strip_contract(prompt: str) -> tuple[str, list[str]]:
    kept: list[str] = []
    removed: list[str] = []
    for line in prompt.splitlines():
        normalized = line.strip()
        if any(normalized.startswith(prefix) for prefix in CONTRACT_PREFIXES):
            removed.append(normalized)
        else:
            kept.append(line)
    return "\n".join(kept), removed


def nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        check(isinstance(current, dict) and key in current, f"missing config path: {keys}")
        current = current[key]
    return current


def verify_config(
    generation_row: dict[str, Any], task: str, arm: str, data_dir: Path
) -> tuple[str, dict[str, Any]]:
    experiment_dir = Path(generation_row["experiment_dir"])
    config_path = experiment_dir / "dojo_config.json"
    check(config_path.is_file(), "dojo config missing")
    check(sha256_file(config_path) == generation_row["dojo_config_sha256"], "config hash mismatch")
    config = load_json(config_path)
    check(str(nested(config, "task", "name")) == task, "config task mismatch")
    check(Path(nested(config, "task", "data_dir")) == data_dir / task / "prepared" / "public", "private data path")
    check(Path(nested(config, "logger", "output_dir")) == experiment_dir, "logger output mismatch")
    check(int(nested(config, "metadata", "seed")) == SEED, "config seed mismatch")
    check(str(nested(config, "metadata", "git_issue_id")) == ISSUE[arm], "config issue mismatch")
    solver = nested(config, "solver")
    exact = {
        "step_limit": 3,
        "num_children": 1,
        "max_debug_depth": 1,
        "execution_timeout": 600,
        "time_limit_secs": 1200,
    }
    check(all(int(solver.get(key, -1)) == value for key, value in exact.items()), "solver budget mismatch")
    check(solver.get("stop_after_first_valid") is True, "stop_after_first_valid mismatch")
    check(solver.get("exp_name") == experiment_dir.name, "solver exp_name mismatch")
    check(Path(solver.get("checkpoint_path", "")) == experiment_dir / "checkpoint", "checkpoint path mismatch")
    operators = solver.get("operators")
    check(isinstance(operators, dict), "operators malformed")
    for name in ("analyze", "debug", "draft", "improve"):
        check(nested(operators, name, "llm", "client", "model_id") == "deepseek-v4-flash", "model mismatch")
    prompt = str(nested(operators, "draft", "system_message_prompt_template", "template"))
    normalized = json.loads(json.dumps(solver))
    normalized.pop("checkpoint_path", None)
    normalized.pop("exp_name", None)
    normalized["operators"]["draft"]["system_message_prompt_template"]["template"] = "<ARM_PROMPT>"
    return prompt, normalized


def classify(summary: dict[str, Any]) -> tuple[str, dict[str, bool]]:
    k0 = summary["contract_probe_valid"] >= 6
    k1 = summary["contract_coverage_120"] >= 6 and summary["coverage_gain"] >= 3
    k2 = summary["contract_full_valid"] >= summary["original_full_valid"] - 1
    enough = summary["paired_full_scores"] >= 4
    k3 = bool(
        enough
        and summary["median_relative_oriented_full_delta"] is not None
        and summary["median_relative_oriented_full_delta"] >= -0.05
        and summary["catastrophic_harm_count"] <= 1
    )
    gates = {
        "K0_contract_compliance_at_least_6_of_8": k0,
        "K1_coverage_at_least_6_and_gain_at_least_3": k1,
        "K2_full_validity_not_worse_by_more_than_1": k2,
        "K3_quality_safety": k3,
        "quality_pairs_at_least_4": enough,
    }
    if all((k0, k1, k2, k3)):
        return "PROMISING", gates
    if not enough:
        return "INCONCLUSIVE", gates
    if not k2 or not k3:
        return "QUALITY_KILL", gates
    if not k0 or not k1:
        return "NO_COVERAGE_GAIN", gates
    return "INCONCLUSIVE", gates


def same_scalar(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        if left is None or right is None:
            return left is right
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)
    return left == right


def verify_one(
    index: int,
    manifest_row: dict[str, Any],
    generation_row: dict[str, Any],
    extraction_row: dict[str, Any],
    replay_dir: Path,
    data_dir: Path,
    samples: dict[str, Path],
    grader: Path,
    manifest_hash: str,
    grade_cache: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    expected_index, task, arm = MATRIX[index]
    check(expected_index == index, "matrix index drift")
    expected = {"index": index, "task": task, "arm": arm, "seed": SEED}
    check(all(manifest_row.get(key) == value for key, value in expected.items()), "manifest matrix mismatch")
    check(manifest_row.get("competition") == task, "competition mismatch")
    check(all(generation_row.get(key) == value for key, value in expected.items()), "generation matrix mismatch")
    check(all(extraction_row.get(key) == value for key, value in expected.items()), "extraction matrix mismatch")
    code = manifest_row.get("code")
    check(isinstance(code, str) and sha256_text(code) == manifest_row.get("code_sha256"), "code hash mismatch")
    try:
        ast.parse(code)
        python_ast_parse = True
    except SyntaxError:
        python_ast_parse = False

    source_export = Path(manifest_row["source_export"])
    experiment_dir = Path(generation_row["experiment_dir"])
    check(sha256_file(source_export) == manifest_row["source_export_sha256"], "source export hash mismatch")
    check(manifest_row["source_export_sha256"] == generation_row["source_export_sha256"], "source chain mismatch")
    check(str(source_export) == generation_row["source_export"], "source export path mismatch")
    mode, code_nodes, selected = raw_topology(source_export, experiment_dir)
    check(mode == manifest_row["generation_topology_mode"] == generation_row["topology_mode"], "topology mode mismatch")
    check(len(code_nodes) == generation_row["code_nodes"], "code-node count mismatch")
    check(str(selected.get("id")) == generation_row["selected_node_id"], "selected id mismatch")
    check(
        selected.get("is_buggy")
        == generation_row.get("selected_node_is_buggy")
        == manifest_row.get("generation_node_is_buggy")
        == extraction_row.get("selected_node_is_buggy"),
        "selected buggy-state mismatch",
    )
    check(str(selected.get("code")) == code, "selected code drift")
    check(python_ast_parse == extraction_row.get("python_ast_parse"), "AST audit mismatch")
    journal = experiment_dir / "checkpoint" / "journal.jsonl"
    state = experiment_dir / "checkpoint" / "state.json"
    check(sha256_file(journal) == generation_row["journal_sha256"], "journal hash mismatch")
    check(sha256_file(state) == generation_row["state_sha256"], "state hash mismatch")
    status_path = replay_dir.parent / "status" / f"index_{index:02d}.json"
    check(status_path.is_file(), "generation status missing")
    check(sha256_file(status_path) == generation_row["status_sha256"], "status hash mismatch")
    status = load_json(status_path)
    status_command = status.get("command")
    check(
        isinstance(status_command, list)
        and all(isinstance(item, str) for item in status_command)
        and hashlib.sha256("\0".join(status_command).encode("utf-8")).hexdigest()
        == status.get("command_sha256")
        == generation_row.get("command_sha256"),
        "generation command hash mismatch",
    )
    check(
        status.get("index") == index
        and status.get("task") == task
        and status.get("arm") == arm
        and status.get("seed") == SEED
        and status.get("schema_version") == 2
        and status.get("experiment") == "probe_contract_ab_safety_v2"
        and status.get("version") == "v2"
        and status.get("return_code") == 0,
        "generation status identity/rc mismatch",
    )

    prompt, normalized_solver = verify_config(generation_row, task, arm, data_dir)
    index_dir = replay_dir / f"index_{index}"
    result = load_json(index_dir / "result.json")
    check(
        result.get("index") == index
        and result.get("card_id") == manifest_row.get("card_id")
        and result.get("competition") == task
        and result.get("seed") == SEED,
        "result identity mismatch",
    )
    check(result.get("manifest_sha256") == manifest_hash, "result manifest hash mismatch")
    check(result.get("code_sha256") == manifest_row["code_sha256"], "result code hash mismatch")
    check(result.get("source_export_sha256") == manifest_row["source_export_sha256"], "result source hash")
    check(result.get("continuous_execution") is True, "not continuous execution")
    checkpoints = result.get("checkpoints", [])
    check([float(row["cap_s"]) for row in checkpoints] == CHECKPOINTS, "checkpoint grid")
    for checkpoint in checkpoints:
        if checkpoint.get("sub_copied"):
            safe_snapshot(index_dir, checkpoint)
    check(result.get("fallback_marker_count") == 0, "fallback marker present")
    workdir = Path(result["workdir"])
    check(sha256_file(workdir / "solution.py") == manifest_row["code_sha256"], "workdir code hash")
    stdout = (workdir / "stdout.log").read_text(encoding="utf-8", errors="replace")
    stderr = (workdir / "stderr.log").read_text(encoding="utf-8", errors="replace")
    combined = stdout + "\n" + stderr
    probe_markers = [
        {"elapsed_s": float(match.group(1)), "sha256": match.group(2)}
        for match in PROBE_MARKER.finditer(combined)
    ]
    full_markers = [
        {"elapsed_s": float(match.group(1)), "sha256": match.group(2)}
        for match in FULL_MARKER.finditer(combined)
    ]
    check(len(FALLBACK_MARKER.findall(combined)) == 0, "raw fallback marker present")
    check(probe_markers == result.get("probe_markers"), "probe marker parser mismatch")
    check(full_markers == result.get("full_markers"), "full marker parser mismatch")

    sample = samples[task]
    events: list[dict[str, Any]] = []
    raw_events = result.get("submission_events")
    check(isinstance(raw_events, list), "events malformed")
    for position, raw_event in enumerate(raw_events):
        check(raw_event.get("event_index") == position, "noncontiguous events")
        path = safe_snapshot(index_dir, raw_event)
        comparison = compare_sample(path, sample)
        grade = regrade_cached(grader, path, task, data_dir, grade_cache)
        stored = raw_event.get("grade") or {}
        check(
            grade_matches_stored(grade, stored),
            f"event regrade mismatch index={index} event={position}",
        )
        finite_grade = grade["rc"] == 0 and finite_number(grade.get("score"))
        events.append(
            {
                "event_index": position,
                "first_seen_elapsed_s": float(raw_event["first_seen_elapsed_s"]),
                "captured_elapsed_s": float(raw_event["captured_elapsed_s"]),
                "sha256": raw_event["sub_sha256"],
                "score": float(grade["score"]) if finite_grade else None,
                "candidate_specific": comparison["candidate_specific"],
                "scoreable": bool(finite_grade and comparison["candidate_specific"]),
                "sample_comparison": comparison,
                "regrade": grade,
            }
        )

    scoreable = [event for event in events if event["scoreable"]]
    by_120 = [event for event in scoreable if event["first_seen_elapsed_s"] <= 120.0]
    endpoint = scoreable[-1] if scoreable else None
    at_120 = by_120[-1] if by_120 else None

    probe_valid = False
    probe_audit = None
    raw_probe = result.get("probe")
    if isinstance(raw_probe, dict):
        probe_path = safe_snapshot(index_dir, raw_probe)
        probe_comparison = compare_sample(probe_path, sample)
        probe_grade = regrade_cached(grader, probe_path, task, data_dir, grade_cache)
        stored = raw_probe.get("grade") or {}
        check(
            grade_matches_stored(probe_grade, stored),
            f"probe regrade mismatch index={index}",
        )
        probe_valid = bool(
            probe_comparison["candidate_specific"]
            and probe_grade["rc"] == 0
            and finite_number(probe_grade.get("score"))
            and float(raw_probe.get("captured_elapsed_s", math.inf)) <= 120.0
            and result.get("probe_mutated_after_capture") is False
            and len(probe_markers) == 1
            and probe_markers[0]["sha256"] == raw_probe.get("sub_sha256")
            and events
            and events[0]["sha256"] == raw_probe.get("sub_sha256")
        )
        probe_audit = {
            "valid": probe_valid,
            "comparison": probe_comparison,
            "regrade": probe_grade,
            "captured_elapsed_s": raw_probe.get("captured_elapsed_s"),
        }

    full_event = None
    if len(full_markers) == 1:
        for event in events[1:]:
            if event["sha256"] == full_markers[0]["sha256"] and event["scoreable"]:
                full_event = event
                break
    if arm == "contract":
        full_like = bool(
            result.get("final_rc") == 0
            and full_event is not None
            and full_event["first_seen_elapsed_s"] <= 600.0
        )
        full_score = full_event["score"] if full_like else None
    else:
        full_like = bool(result.get("final_rc") == 0 and endpoint is not None)
        full_score = endpoint["score"] if full_like else None

    row = {
        "index": index,
        "task": task,
        "arm": arm,
        "topology_mode": mode,
        "final_rc": result.get("final_rc"),
        "wall_s": result.get("wall_s"),
        "event_count": len(events),
        "events": events,
        "coverage_120": at_120 is not None,
        "first_scoreable_s": scoreable[0]["first_seen_elapsed_s"] if scoreable else None,
        "score_at_120": at_120["score"] if at_120 else None,
        "endpoint_score": endpoint["score"] if endpoint else None,
        "probe_valid": probe_valid,
        "probe": probe_audit,
        "full_like_valid": full_like,
        "full_score": full_score,
    }
    return row, prompt, normalized_solver


def self_test() -> None:
    verdict, gates = classify(
        {
            "contract_probe_valid": 6,
            "contract_coverage_120": 6,
            "coverage_gain": 3,
            "contract_full_valid": 7,
            "original_full_valid": 8,
            "paired_full_scores": 4,
            "median_relative_oriented_full_delta": -0.01,
            "catastrophic_harm_count": 1,
        }
    )
    check(verdict == "PROMISING" and all(gates.values()), "positive gate self-test")
    killed, _ = classify(
        {
            "contract_probe_valid": 6,
            "contract_coverage_120": 6,
            "coverage_gain": 3,
            "contract_full_valid": 6,
            "original_full_valid": 8,
            "paired_full_scores": 4,
            "median_relative_oriented_full_delta": -0.11,
            "catastrophic_harm_count": 2,
        }
    )
    check(killed == "QUALITY_KILL", "negative gate self-test")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        sample = root / "sample.csv"
        candidate = root / "candidate.csv"
        sample.write_text("id,pred\n1,0.5\n2,0.5\n", encoding="utf-8")
        candidate.write_text("id,pred\n1,0.2\n2,0.8\n", encoding="utf-8")
        check(compare_sample(candidate, sample)["candidate_specific"], "candidate CSV self-test")
        experiment = root / "experiment"
        checkpoint = experiment / "checkpoint"
        checkpoint.mkdir(parents=True)
        nodes = [
            {
                "step": 0,
                "code": "",
                "parents": [],
                "children": [1],
                "operators_used": [],
            },
            {
                "id": "leaf",
                "step": 1,
                "code": "print('ok')",
                "parents": [0],
                "children": [],
                "operators_used": ["draft"],
                "is_buggy": False,
            },
        ]
        export = experiment / "search.json"
        export.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
        (checkpoint / "journal.jsonl").write_text("{}\n{}\n", encoding="utf-8")
        (checkpoint / "state.json").write_text('{"current_step": 2}\n', encoding="utf-8")
        mode, code_nodes, selected = raw_topology(export, experiment)
        check(mode == "draft_valid" and len(code_nodes) == 1 and selected["id"] == "leaf", "topology self-test")
        check(
            grade_matches_stored(
                {"rc": 0, "score": 0.25}, {"grade_rc": 0, "sub_score": 0.25}
            ),
            "grade-match self-test",
        )
    print("INDEPENDENT_PROBE_CONTRACT_AB_SELF_TEST_PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--grader", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if None in (args.root, args.data_dir, args.grader, args.output):
        parser.error("--root --data-dir --grader --output are required")
    check(args.grader.is_file(), f"grader missing: {args.grader}")
    check(not args.output.exists(), f"refusing existing output: {args.output}")

    manifest_path = args.root / "replay_manifest.jsonl"
    generation_path = args.root / "generation_manifest.json"
    extraction_path = args.root / "replay_manifest.audit.json"
    primary_path = args.root / "probe_contract_ab_result.json"
    manifest_hash = sha256_file(manifest_path)
    generation_hash = sha256_file(generation_path)
    manifest = load_jsonl(manifest_path)
    generation = load_json(generation_path)
    extraction = load_json(extraction_path)
    primary = load_json(primary_path)
    check(len(manifest) == len(MATRIX), "replay grid size")
    check(len({row.get("card_id") for row in manifest}) == len(MATRIX), "duplicate replay card id")
    check(generation.get("experiment") == "probe_contract_ab_safety_v2", "generation identity")
    check(generation.get("schema_version") == 2, "generation schema")
    check(generation.get("seed") == SEED, "generation seed")
    check(extraction.get("experiment") == "probe_contract_ab_safety_v2", "extraction identity")
    check(extraction.get("schema_version") == 2, "extraction schema")
    check(extraction.get("seed") == SEED, "extraction seed")
    check(primary.get("experiment") == "probe_contract_ab_safety_v2", "primary identity")
    check(primary.get("schema_version") == 2, "primary schema")
    check(primary.get("seed") == SEED, "primary seed")
    check(extraction.get("replay_manifest_sha256") == manifest_hash, "extraction hash")
    check(
        extraction.get("source_generation_manifest_sha256") == generation_hash,
        "extraction generation hash",
    )
    check(
        all(row.get("source_generation_manifest_sha256") == generation_hash for row in manifest),
        "replay-row generation hash",
    )
    check(primary.get("manifest_sha256") == manifest_hash, "primary hash")
    generation_by_index = {int(row["index"]): row for row in generation["rows"]}
    extraction_by_index = {int(row["index"]): row for row in extraction["rows"]}
    check(set(generation_by_index) == set(range(len(MATRIX))), "generation index grid")
    check(set(extraction_by_index) == set(range(len(MATRIX))), "extraction index grid")

    grade_cache: dict[tuple[str, str], dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    prompts: dict[tuple[str, str], str] = {}
    normalized_solvers: dict[tuple[str, str], dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="independent-probe-ab-samples-") as sample_temp:
        samples = materialize_samples(args.data_dir, Path(sample_temp))
        for index, manifest_row in enumerate(manifest):
            row, prompt, normalized_solver = verify_one(
                index,
                manifest_row,
                generation_by_index[index],
                extraction_by_index[index],
                args.root / "replay",
                args.data_dir,
                samples,
                args.grader,
                manifest_hash,
                grade_cache,
            )
            rows.append(row)
            prompts[(row["task"], row["arm"])] = prompt
            normalized_solvers[(row["task"], row["arm"])] = normalized_solver

    for task in ORIENTATION:
        stripped, removed = strip_contract(prompts[(task, "contract")])
        check(stripped == prompts[(task, "original")], f"prompt diff mismatch: {task}")
        check(len(removed) == len(CONTRACT_PREFIXES), f"contract-line count mismatch: {task}")
        check(
            normalized_solvers[(task, "original")] == normalized_solvers[(task, "contract")],
            f"non-prompt solver difference: {task}",
        )

    pairs: list[dict[str, Any]] = []
    for task, orientation in ORIENTATION.items():
        arms = {row["arm"]: row for row in rows if row["task"] == task}
        check(set(arms) == {"original", "contract"}, f"incomplete pair: {task}")
        original, contract = arms["original"], arms["contract"]
        pair = {
            "task": task,
            "coverage_delta": int(contract["coverage_120"]) - int(original["coverage_120"]),
            "full_valid_delta": int(contract["full_like_valid"]) - int(original["full_like_valid"]),
            "relative_oriented_full_delta": None,
        }
        if original["full_score"] is not None and contract["full_score"] is not None:
            pair["relative_oriented_full_delta"] = (
                orientation * (float(contract["full_score"]) - float(original["full_score"]))
                / max(abs(float(original["full_score"])), 1e-8)
            )
        pairs.append(pair)

    relative = [
        pair["relative_oriented_full_delta"]
        for pair in pairs
        if pair["relative_oriented_full_delta"] is not None
    ]
    summary = {
        "blocks": len(ORIENTATION),
        "original_coverage_120": sum(row["coverage_120"] for row in rows if row["arm"] == "original"),
        "contract_coverage_120": sum(row["coverage_120"] for row in rows if row["arm"] == "contract"),
        "coverage_gain": sum(pair["coverage_delta"] for pair in pairs),
        "contract_probe_valid": sum(row["probe_valid"] for row in rows if row["arm"] == "contract"),
        "original_full_valid": sum(row["full_like_valid"] for row in rows if row["arm"] == "original"),
        "contract_full_valid": sum(row["full_like_valid"] for row in rows if row["arm"] == "contract"),
        "paired_full_scores": len(relative),
        "median_relative_oriented_full_delta": statistics.median(relative) if relative else None,
        "catastrophic_harm_count": sum(value < -0.10 for value in relative),
    }
    verdict, gates = classify(summary)
    check(verdict == primary.get("verdict"), "primary/independent verdict mismatch")
    check(gates == primary.get("gates"), "primary/independent gates mismatch")
    for key, value in summary.items():
        check(same_scalar(value, primary["summary"].get(key)), f"summary mismatch: {key}")

    payload = {
        "schema_version": 2,
        "experiment": "probe_contract_ab_safety_v2",
        "verdict": verdict,
        "gates": gates,
        "independent_of_project_validator": True,
        "independent_pristine_regrades": len(grade_cache),
        "manifest_sha256": manifest_hash,
        "summary": summary,
        "pairs": pairs,
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
        "INDEPENDENT_PROBE_CONTRACT_AB_VERDICT "
        f"verdict={verdict} coverage={summary['original_coverage_120']}->"
        f"{summary['contract_coverage_120']} probe={summary['contract_probe_valid']}/8 "
        f"full={summary['original_full_valid']}->{summary['contract_full_valid']} "
        f"quality_pairs={summary['paired_full_scores']} regrades={len(grade_cache)}"
    )


if __name__ == "__main__":
    main()
