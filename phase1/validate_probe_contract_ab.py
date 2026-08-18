#!/usr/bin/env python3
"""Evaluate the frozen six-block original-vs-contract safety A/B."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import tempfile
import zipfile
from pathlib import Path

from phase1.probe_contract_ab_common import atomic_json, sha256_file, spec_for_version
from phase1.validate_schema_probe_contract import (
    compare_to_sample,
    finite_grade,
    resolve_snapshot,
)


CHECKPOINTS = [30.0, 60.0, 120.0, 240.0, 360.0, 600.0]


def materialize_sample(task: str, data_dir: Path, cache_dir: Path, version: str) -> Path:
    spec = spec_for_version(version)
    relative, member = spec.sample_submission[task]
    source = data_dir / task / "prepared" / "public" / relative
    if not source.is_file():
        raise RuntimeError(f"sample submission source missing: {source}")
    if member is None:
        return source
    if source.suffix.lower() != ".zip":
        raise RuntimeError(f"unsupported sample archive: {source}")
    destination = cache_dir / f"{task}.sample.csv"
    with zipfile.ZipFile(source) as archive:
        if archive.namelist().count(member) != 1:
            raise RuntimeError(f"sample archive member mismatch: {source}/{member}")
        with archive.open(member) as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
    if destination.stat().st_size <= 0:
        raise RuntimeError(f"empty sample archive member: {source}/{member}")
    return destination


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def event_record(index_dir: Path, event: dict, sample: Path) -> dict:
    path = resolve_snapshot(index_dir, event)
    comparison = compare_to_sample(path, sample)
    return {
        "event_index": event["event_index"],
        "first_seen_elapsed_s": float(event["first_seen_elapsed_s"]),
        "captured_elapsed_s": float(event["captured_elapsed_s"]),
        "sha256": event["sub_sha256"],
        "score": event.get("grade", {}).get("sub_score"),
        "finite_grade": finite_grade(event),
        "candidate_specific": comparison.get("candidate_specific") is True,
        "scoreable": finite_grade(event) and comparison.get("candidate_specific") is True,
        "sample_comparison": comparison,
    }


def marker_match(markers: list[dict], events: list[dict], *, after_first: bool) -> dict | None:
    if len(markers) != 1:
        return None
    marker = markers[0]
    candidates = events[1:] if after_first else events
    for event in candidates:
        if event["sha256"] == marker.get("sha256") and event["scoreable"]:
            return event
    return None


def summarize_one(
    index: int,
    manifest_row: dict,
    extraction_row: dict,
    replay_dir: Path,
    sample: Path,
    manifest_sha: str,
    version: str,
) -> dict:
    spec = spec_for_version(version)
    expected = spec.matrix[index]
    if (
        manifest_row.get("index") != index
        or manifest_row.get("task") != expected["task"]
        or manifest_row.get("arm") != expected["arm"]
        or manifest_row.get("seed") != spec.seed
        or manifest_row.get("competition") != expected["task"]
    ):
        raise RuntimeError(f"manifest row differs from frozen matrix: {index}")
    index_dir = replay_dir / f"index_{index}"
    result_path = index_dir / "result.json"
    if not result_path.is_file():
        raise RuntimeError(f"missing replay result: {index}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    integrity = {
        "identity": result.get("index") == index
        and result.get("card_id") == manifest_row.get("card_id")
        and result.get("competition") == expected["task"]
        and result.get("seed") == spec.seed,
        "manifest_hash": result.get("manifest_sha256") == manifest_sha,
        "code_hash": result.get("code_sha256") == manifest_row.get("code_sha256"),
        "source_hash": result.get("source_export_sha256") == manifest_row.get("source_export_sha256"),
        "continuous_execution": result.get("continuous_execution") is True,
        "checkpoint_grid": [float(row["cap_s"]) for row in result.get("checkpoints", [])]
        == CHECKPOINTS,
        "workdir_code_hash": sha256_file(Path(result["workdir"]) / "solution.py")
        == manifest_row.get("code_sha256"),
        "fallback_absent": result.get("fallback_marker_count") == 0,
    }
    failed_integrity = [name for name, passed in integrity.items() if passed is not True]
    if failed_integrity:
        raise RuntimeError(f"integrity failure index={index}: {failed_integrity}")

    events = [event_record(index_dir, event, sample) for event in result["submission_events"]]
    if any(event["event_index"] != position for position, event in enumerate(events)):
        raise RuntimeError(f"non-contiguous event order: {index}")
    scoreable = [event for event in events if event["scoreable"]]
    by_120 = [event for event in scoreable if event["first_seen_elapsed_s"] <= 120.0]
    endpoint = scoreable[-1] if scoreable else None
    at_120 = by_120[-1] if by_120 else None

    probe_valid = False
    probe = result.get("probe")
    if isinstance(probe, dict):
        probe_path = resolve_snapshot(index_dir, probe)
        probe_comparison = compare_to_sample(probe_path, sample)
        probe_valid = bool(
            finite_grade(probe)
            and probe_comparison.get("candidate_specific") is True
            and float(probe.get("captured_elapsed_s", math.inf)) <= 120.0
            and result.get("probe_mutated_after_capture") is False
            and len(result.get("probe_markers", [])) == 1
            and result["probe_markers"][0].get("sha256") == probe.get("sub_sha256")
            and events
            and events[0]["sha256"] == probe.get("sub_sha256")
        )

    full_event = marker_match(result.get("full_markers", []), events, after_first=True)
    if expected["arm"] == "contract":
        full_like = bool(
            result.get("final_rc") == 0
            and full_event is not None
            and full_event["first_seen_elapsed_s"] <= 600.0
        )
        full_score = full_event["score"] if full_like else None
        contract_static = extraction_row.get("static_contract", {}).get("required_pass") is True
    else:
        full_like = bool(result.get("final_rc") == 0 and endpoint is not None)
        full_score = endpoint["score"] if full_like else None
        contract_static = None

    return {
        "index": index,
        "task": expected["task"],
        "arm": expected["arm"],
        "seed": spec.seed,
        "integrity": integrity,
        "topology_mode": manifest_row.get("generation_topology_mode"),
        "generation_node_is_buggy": manifest_row.get("generation_node_is_buggy"),
        "python_ast_parse": extraction_row.get("python_ast_parse"),
        "contract_static_pass": contract_static,
        "final_rc": result.get("final_rc"),
        "wall_s": result.get("wall_s"),
        "event_count": len(events),
        "events": events,
        "coverage_120": at_120 is not None,
        "first_scoreable_s": scoreable[0]["first_seen_elapsed_s"] if scoreable else None,
        "score_at_120": at_120["score"] if at_120 else None,
        "endpoint_score": endpoint["score"] if endpoint else None,
        "probe_valid": probe_valid,
        "full_like_valid": full_like,
        "full_score": full_score,
    }


def classify(summary: dict, version: str = "v1") -> tuple[str, dict]:
    spec = spec_for_version(version)
    k0 = summary["contract_probe_valid"] >= spec.compliance_min
    k1 = (
        summary["contract_coverage_120"] >= spec.coverage_min
        and summary["coverage_gain"] >= spec.coverage_gain_min
    )
    k2 = summary["contract_full_valid"] >= summary["original_full_valid"] - 1
    enough_quality = summary["paired_full_scores"] >= spec.quality_pairs_min
    k3 = bool(
        enough_quality
        and summary["median_relative_oriented_full_delta"] is not None
        and summary["median_relative_oriented_full_delta"] >= -0.05
        and summary["catastrophic_harm_count"] <= 1
    )
    gates = {
        (
            f"K0_contract_compliance_at_least_{spec.compliance_min}_of_{len(spec.tasks)}"
        ): k0,
        (
            f"K1_coverage_at_least_{spec.coverage_min}_and_gain_at_least_"
            f"{spec.coverage_gain_min}"
        ): k1,
        "K2_full_validity_not_worse_by_more_than_1": k2,
        "K3_quality_safety": k3,
        f"quality_pairs_at_least_{spec.quality_pairs_min}": enough_quality,
    }
    if all((k0, k1, k2, k3)):
        verdict = "PROMISING"
    elif not enough_quality:
        verdict = "INCONCLUSIVE"
    elif not k2 or not k3:
        verdict = "QUALITY_KILL"
    elif not k0 or not k1:
        verdict = "NO_COVERAGE_GAIN"
    else:
        verdict = "INCONCLUSIVE"
    return verdict, gates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--extraction-audit", type=Path)
    parser.add_argument("--generation-manifest", type=Path)
    parser.add_argument("--replay-dir", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    spec = spec_for_version(args.version)
    if args.self_test:
        promising, gates = classify(
            {
                "contract_probe_valid": 6,
                "contract_coverage_120": 6,
                "coverage_gain": 3,
                "contract_full_valid": 5,
                "original_full_valid": 6,
                "paired_full_scores": 5,
                "median_relative_oriented_full_delta": -0.01,
                "catastrophic_harm_count": 1,
            }
        )
        assert promising == "PROMISING" and all(gates.values())
        killed, _ = classify(
            {
                "contract_probe_valid": 6,
                "contract_coverage_120": 6,
                "coverage_gain": 3,
                "contract_full_valid": 4,
                "original_full_valid": 6,
                "paired_full_scores": 4,
                "median_relative_oriented_full_delta": -0.20,
                "catastrophic_harm_count": 2,
            }
        )
        assert killed == "QUALITY_KILL"
        promising_v2, gates_v2 = classify(
            {
                "contract_probe_valid": 6,
                "contract_coverage_120": 6,
                "coverage_gain": 3,
                "contract_full_valid": 7,
                "original_full_valid": 8,
                "paired_full_scores": 4,
                "median_relative_oriented_full_delta": -0.01,
                "catastrophic_harm_count": 1,
            },
            "v2",
        )
        assert promising_v2 == "PROMISING" and all(gates_v2.values())
        print("PROBE_CONTRACT_AB_VALIDATOR_SELF_TEST_PASS")
        return
    if None in (
        args.manifest,
        args.extraction_audit,
        args.generation_manifest,
        args.replay_dir,
        args.data_dir,
        args.output,
    ):
        parser.error(
            "--manifest --extraction-audit --generation-manifest --replay-dir "
            "--data-dir --output are required"
        )
    if args.output.exists():
        raise RuntimeError(f"refusing existing A/B output: {args.output}")

    manifest_hash = sha256_file(args.manifest)
    manifest = load_jsonl(args.manifest)
    extraction = json.loads(args.extraction_audit.read_text(encoding="utf-8"))
    generation = json.loads(args.generation_manifest.read_text(encoding="utf-8"))
    if (
        len(manifest) != len(spec.matrix)
        or extraction.get("replay_manifest_sha256") != manifest_hash
        or extraction.get("experiment") != spec.experiment
        or extraction.get("seed") != spec.seed
        or generation.get("experiment") != spec.experiment
        or generation.get("seed") != spec.seed
    ):
        raise RuntimeError("A/B manifest/audit identity mismatch")
    extraction_by_index = {row["index"]: row for row in extraction["rows"]}
    if set(extraction_by_index) != set(range(len(spec.matrix))):
        raise RuntimeError("A/B extraction index grid mismatch")
    with tempfile.TemporaryDirectory(prefix="probe-ab-samples-") as sample_temp:
        sample_cache = Path(sample_temp)
        samples = {
            task: materialize_sample(task, args.data_dir, sample_cache, args.version)
            for task in spec.tasks
        }
        rows = [
            summarize_one(
                index,
                manifest[index],
                extraction_by_index[index],
                args.replay_dir,
                samples[spec.matrix[index]["task"]],
                manifest_hash,
                args.version,
            )
            for index in range(len(spec.matrix))
        ]

    pairs = []
    for task in spec.tasks:
        arms = {row["arm"]: row for row in rows if row["task"] == task}
        if set(arms) != {"original", "contract"}:
            raise RuntimeError(f"incomplete paired block: {task}")
        original, contract = arms["original"], arms["contract"]
        pair = {
            "task": task,
            "orientation": spec.orientation[task],
            "original_index": original["index"],
            "contract_index": contract["index"],
            "coverage_delta": int(contract["coverage_120"]) - int(original["coverage_120"]),
            "full_valid_delta": int(contract["full_like_valid"]) - int(original["full_like_valid"]),
            "first_scoreable_delta_s": (
                contract["first_scoreable_s"] - original["first_scoreable_s"]
                if contract["first_scoreable_s"] is not None
                and original["first_scoreable_s"] is not None
                else None
            ),
            "raw_full_delta": None,
            "oriented_full_delta": None,
            "relative_oriented_full_delta": None,
        }
        if original["full_score"] is not None and contract["full_score"] is not None:
            raw = float(contract["full_score"]) - float(original["full_score"])
            oriented = spec.orientation[task] * raw
            pair["raw_full_delta"] = raw
            pair["oriented_full_delta"] = oriented
            pair["relative_oriented_full_delta"] = oriented / max(abs(float(original["full_score"])), 1e-8)
        pairs.append(pair)

    relative_deltas = [
        pair["relative_oriented_full_delta"]
        for pair in pairs
        if pair["relative_oriented_full_delta"] is not None
    ]
    summary = {
        "blocks": len(spec.tasks),
        "original_coverage_120": sum(row["coverage_120"] for row in rows if row["arm"] == "original"),
        "contract_coverage_120": sum(row["coverage_120"] for row in rows if row["arm"] == "contract"),
        "coverage_gain": sum(pair["coverage_delta"] for pair in pairs),
        "contract_probe_valid": sum(row["probe_valid"] for row in rows if row["arm"] == "contract"),
        "original_full_valid": sum(row["full_like_valid"] for row in rows if row["arm"] == "original"),
        "contract_full_valid": sum(row["full_like_valid"] for row in rows if row["arm"] == "contract"),
        "paired_full_scores": len(relative_deltas),
        "median_relative_oriented_full_delta": statistics.median(relative_deltas)
        if relative_deltas
        else None,
        "catastrophic_harm_count": sum(value < -0.10 for value in relative_deltas),
        "contract_better_full_count": sum(value > 0 for value in relative_deltas),
        "contract_worse_full_count": sum(value < 0 for value in relative_deltas),
        "total_replay_wall_s": sum(float(row["wall_s"]) for row in rows),
    }

    usage_by_arm = {}
    for arm in ("original", "contract"):
        arm_rows = [row for row in generation["rows"] if row["arm"] == arm]
        usage_by_arm[arm] = {
            "generation_wall_s_sum": sum(float(row["generation_wall_s"]) for row in arm_rows),
            "llm_records": sum(row["llm_usage"]["records"] for row in arm_rows),
            "prompt_tokens": sum(row["llm_usage"]["prompt_tokens"] for row in arm_rows),
            "completion_tokens": sum(row["llm_usage"]["completion_tokens"] for row in arm_rows),
            "reasoning_tokens": sum(row["llm_usage"]["reasoning_tokens"] for row in arm_rows),
            "total_tokens": sum(row["llm_usage"]["total_tokens"] for row in arm_rows),
            "llm_latency_s_sum": sum(float(row["llm_usage"]["latency_s"]) for row in arm_rows),
        }
    verdict, gates = classify(summary, args.version)
    payload = {
        "schema_version": spec.schema_version,
        "experiment": spec.experiment,
        "version": spec.version,
        "seed": spec.seed,
        "verdict": verdict,
        "gates": gates,
        "gate_scope": "safety/discovery only; no significance or venue-level effect claim",
        "manifest_sha256": manifest_hash,
        "summary": summary,
        "usage_by_arm": usage_by_arm,
        "pairs": pairs,
        "rows": rows,
    }
    atomic_json(args.output, payload)
    print(
        "PROBE_CONTRACT_AB_VERDICT "
        f"verdict={verdict} coverage={summary['original_coverage_120']}->"
        f"{summary['contract_coverage_120']} gain={summary['coverage_gain']} "
        f"probe={summary['contract_probe_valid']}/{len(spec.tasks)} full="
        f"{summary['original_full_valid']}->{summary['contract_full_valid']} "
        f"quality_pairs={summary['paired_full_scores']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
