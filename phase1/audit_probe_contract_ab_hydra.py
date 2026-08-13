#!/usr/bin/env python3
"""Outcome-free audit of the 12 resolved Hydra configs and public inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import yaml

from phase1.build_probe_contract_ab_manifest import (
    CONTRACT_PREFIXES,
    normalize_solver,
    strip_contract,
)
from phase1.probe_contract_ab_common import atomic_json, row_for_index, sha256_file, spec_for_version


PRIOR_INTERVENTION_TASKS = {
    "spooky-author-identification",
    "tabular-playground-series-may-2022",
    "spaceship-titanic",
    "tweet-sentiment-extraction",
    "chaii-hindi-and-tamil-question-answering",
    "leaf-classification",
    "nomad2018-predict-transparent-conductors",
    "plant-pathology-2020-fgvc7",
    "google-quest-challenge",
    "tabular-playground-series-dec-2021",
    "random-acts-of-pizza",
    "us-patent-phrase-to-phrase-matching",
    "petfinder-pawpularity-score",
}


def nested(value: dict, *keys: str):
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise RuntimeError(f"missing config field: {'/'.join(keys)}")
        value = value[key]
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


def audit_sample(public: Path, relative: str, member: str | None) -> dict:
    source = public / relative
    if not source.is_file() or source.stat().st_size <= 0:
        raise RuntimeError(f"sample submission source missing: {source}")
    payload = {
        "relative_path": relative,
        "archive_member": member,
        "source_bytes": source.stat().st_size,
        "source_sha256": sha256_file(source),
    }
    if member is None:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            header = handle.readline().rstrip("\r\n")
        payload["member_bytes"] = source.stat().st_size
        payload["member_sha256"] = payload["source_sha256"]
    else:
        if source.suffix.lower() != ".zip":
            raise RuntimeError(f"unsupported sample archive: {source}")
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if names.count(member) != 1:
                raise RuntimeError(f"sample archive member mismatch: {source}/{member}")
            info = archive.getinfo(member)
            digest = hashlib.sha256()
            with archive.open(member) as raw:
                first = raw.readline()
                digest.update(first)
                for chunk in iter(lambda: raw.read(1 << 20), b""):
                    digest.update(chunk)
            header = first.decode("utf-8-sig").rstrip("\r\n")
            payload["member_bytes"] = info.file_size
            payload["member_sha256"] = digest.hexdigest()
    if not header or "," not in header:
        raise RuntimeError(f"sample submission header malformed: {source}/{member or ''}")
    payload["header"] = header
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = spec_for_version(args.version)
    if args.output.exists():
        raise RuntimeError(f"refusing existing Hydra audit: {args.output}")
    if args.version == "v2" and set(spec.tasks) & PRIOR_INTERVENTION_TASKS:
        raise RuntimeError("V2 task overlaps a prior related intervention outcome")

    rows = []
    prompts: dict[tuple[str, str], str] = {}
    normalized: dict[tuple[str, str], dict] = {}
    for frozen in spec.matrix:
        expected = row_for_index(frozen["index"], args.version)
        path = args.config_dir / f"index_{expected['index']:02d}_{expected['arm']}_{expected['task']}.yaml"
        if not path.is_file():
            raise RuntimeError(f"resolved config missing: {path}")
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        if nested(config, "task", "name") != expected["task"]:
            raise RuntimeError(f"task mismatch: {path}")
        if nested(config, "metadata", "seed") != spec.seed:
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
    for task in spec.tasks:
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
    for task in spec.tasks:
        public = args.data_dir / task / "prepared" / "public"
        if not public.is_dir():
            raise RuntimeError(f"public task data missing: {task}")
        description = public / "description.md"
        if not description.is_file() or description.stat().st_size <= 0:
            raise RuntimeError(f"description gate failed: {task}")
        sample = audit_sample(public, *spec.sample_submission[task])
        key_files = []
        for name in sorted({"description.md", spec.sample_submission[task][0], "train.csv", "test.csv"}):
            path = public / name
            if path.is_file():
                key_files.append(
                    {"name": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                )
        visible_inputs = [path for path in public.iterdir() if path.name not in {"description.md", spec.sample_submission[task][0]}]
        if not visible_inputs:
            raise RuntimeError(f"no public train/test inputs visible: {task}")
        data_rows.append(
            {
                "task": task,
                "public_dir": str(public),
                "orientation": spec.orientation[task],
                "description_sha256": sha256_file(description),
                "sample_submission": sample,
                "key_files": key_files,
                **metadata_tree(public),
            }
        )

    payload = {
        "schema_version": spec.schema_version,
        "experiment": spec.experiment,
        "version": spec.version,
        "seed": spec.seed,
        "rows": rows,
        "prompt_pairs": prompt_pairs,
        "public_data": data_rows,
    }
    atomic_json(args.output, payload)
    print(
        f"PROBE_CONTRACT_AB_HYDRA_PASS version={spec.version} configs={len(rows)} "
        f"pairs={len(prompt_pairs)} tasks={len(data_rows)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
