#!/usr/bin/env python3
"""Outcome-free audit of the 12 resolved Hydra configs and public inputs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import yaml

from phase1.build_probe_contract_ab_manifest import CONTRACT_PREFIXES, strip_contract
from phase1.probe_contract_ab_common import MATRIX, SEED, TASKS, atomic_json, row_for_index, sha256_file


V1_V2_TASKS = {
    "spooky-author-identification",
    "tabular-playground-series-may-2022",
    "spaceship-titanic",
    "tweet-sentiment-extraction",
}


def nested(value: dict, *keys: str):
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise RuntimeError(f"missing config field: {'/'.join(keys)}")
        value = value[key]
    return value


def normalize_solver(solver: dict) -> dict:
    value = copy.deepcopy(solver)
    value["operators"]["draft"]["system_message_prompt_template"]["template"] = "<ARM_PROMPT>"
    return value


def metadata_tree(public: Path) -> dict:
    digest = hashlib.sha256()
    count = 0
    total_bytes = 0
    for path in sorted(item for item in public.rglob("*") if item.is_file()):
        relative = path.relative_to(public).as_posix()
        size = path.stat().st_size
        digest.update(relative.encode("utf-8") + b"\0" + str(size).encode("ascii") + b"\n")
        count += 1
        total_bytes += size
    return {
        "file_count": count,
        "total_bytes": total_bytes,
        "path_size_tree_sha256": digest.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing existing Hydra audit: {args.output}")
    if set(TASKS) & V1_V2_TASKS:
        raise RuntimeError("A/B task overlaps V1/V2")

    rows = []
    prompts: dict[tuple[str, str], str] = {}
    normalized: dict[tuple[str, str], dict] = {}
    for frozen in MATRIX:
        expected = row_for_index(frozen["index"])
        path = args.config_dir / f"index_{expected['index']:02d}_{expected['arm']}_{expected['task']}.yaml"
        if not path.is_file():
            raise RuntimeError(f"resolved config missing: {path}")
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        if nested(config, "task", "name") != expected["task"]:
            raise RuntimeError(f"task mismatch: {path}")
        if nested(config, "metadata", "seed") != SEED:
            raise RuntimeError(f"seed mismatch: {path}")
        if nested(config, "metadata", "git_issue_id") != expected["issue"]:
            raise RuntimeError(f"issue mismatch: {path}")
        solver = nested(config, "solver")
        for name, value in {
            "step_limit": 3,
            "num_children": 1,
            "max_debug_depth": 1,
            "execution_timeout": 600,
            "time_limit_secs": 1200,
        }.items():
            if int(solver.get(name, -1)) != value:
                raise RuntimeError(f"budget mismatch {name}: {path}")
        if solver.get("stop_after_first_valid") is not True:
            raise RuntimeError(f"first-valid mismatch: {path}")
        operators = solver["operators"]
        for name in ("analyze", "debug", "draft", "improve"):
            if nested(operators, name, "llm", "client", "model_id") != "deepseek-v4-flash":
                raise RuntimeError(f"model mismatch: {path}/{name}")
        prompt = nested(operators, "draft", "system_message_prompt_template", "template")
        has_contract = "CRITICAL ANYTIME ARTIFACT CONTRACT" in prompt and "candidate_probe.csv" in prompt
        if has_contract != (expected["arm"] == "contract"):
            raise RuntimeError(f"prompt/arm mismatch: {path}")
        key = (expected["task"], expected["arm"])
        prompts[key] = prompt
        normalized[key] = normalize_solver(solver)
        rows.append(
            {
                **expected,
                "resolved_config": str(path),
                "resolved_config_sha256": sha256_file(path),
                "draft_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            }
        )

    prompt_pairs = []
    for task in TASKS:
        stripped, removed = strip_contract(prompts[(task, "contract")])
        if stripped != prompts[(task, "original")] or len(removed) != len(CONTRACT_PREFIXES):
            raise RuntimeError(f"non-contract prompt difference: {task}")
        if normalized[(task, "original")] != normalized[(task, "contract")]:
            raise RuntimeError(f"non-prompt solver difference: {task}")
        prompt_pairs.append(
            {
                "task": task,
                "normalized_solver_equal": True,
                "removed_contract_lines": removed,
            }
        )

    data_rows = []
    for task in TASKS:
        public = args.data_dir / task / "prepared" / "public"
        if not public.is_dir():
            raise RuntimeError(f"public task data missing: {task}")
        samples = sorted(public.rglob("sample_submission.csv"))
        if len(samples) != 1 or samples[0].stat().st_size <= 0:
            raise RuntimeError(f"lowercase sample submission gate failed: {task}")
        description = public / "description.md"
        if not description.is_file() or description.stat().st_size <= 0:
            raise RuntimeError(f"description gate failed: {task}")
        key_files = []
        for name in ("description.md", "sample_submission.csv", "train.csv", "test.csv"):
            path = public / name
            if path.is_file():
                key_files.append(
                    {"name": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                )
        if not any(row["name"] == "train.csv" for row in key_files) or not any(
            row["name"] == "test.csv" for row in key_files
        ):
            raise RuntimeError(f"standard train/test files missing: {task}")
        data_rows.append(
            {
                "task": task,
                "public_dir": str(public),
                "key_files": key_files,
                **metadata_tree(public),
            }
        )

    payload = {
        "schema_version": 1,
        "experiment": "probe_contract_ab_safety_v1",
        "seed": SEED,
        "rows": rows,
        "prompt_pairs": prompt_pairs,
        "public_data": data_rows,
    }
    atomic_json(args.output, payload)
    print(
        f"PROBE_CONTRACT_AB_HYDRA_PASS configs={len(rows)} pairs={len(prompt_pairs)} tasks={len(data_rows)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
