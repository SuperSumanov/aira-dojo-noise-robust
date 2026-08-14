"""Audit whether historical MCTS and sequential batches form a fair policy comparison.

The command streams only ``dojo_config.json`` and ``checkpoint/journal.jsonl`` from immutable
senior tar drops.  Every allowlisted payload is scanned for credential shapes before JSON
parsing.  It never reads environment files, source code workspaces, submissions, or grades.

This is deliberately a contract-first audit.  Structural allocation statistics are descriptive
when any non-policy contract field differs across arms; they must not be interpreted causally.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import math
import os
import platform
import random
import re
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PROTOCOL = "search_policy_contract_audit_v1"
BOOTSTRAP_SEED = 20260814
BOOTSTRAP_REPLICATES = 10_000
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)
CONTRACT_PATHS = (
    "metadata.git_commit_id",
    "interpreter.timeout",
    "solver.execution_timeout",
    "solver.max_debug_depth",
    "solver.max_debug_time",
    "solver.num_children",
    "solver.step_limit",
    "solver.time_limit_secs",
    "solver.uct_c",
    "solver.use_complexity",
    "solver.use_test_score",
    "solver.memory.memory_processor",
    "solver.memory.memory_op_kwargs.include_buggy_nodes",
    "solver.memory.memory_op_kwargs.only_plans",
    "task.benchmark",
)
OPERATORS = ("analyze", "draft", "debug", "improve")
PROMPT_FIELDS = (
    "init_user_message_prompt_template",
    "system_message_prompt_template",
    "user_message_prompt_template",
)
RUN_COLUMNS = (
    "arm",
    "batch",
    "archive",
    "archive_sha256",
    "journal_sha256",
    "task",
    "seed",
    "contract_sha256",
    "nodes",
    "nonroot_nodes",
    "max_depth",
    "root_branches",
    "structure_eligible",
    "max_branch_share",
    "hhi",
    "normalized_hhi",
    "normalized_entropy",
    "effective_branch_ratio",
    "gini",
)


class AuditError(RuntimeError):
    pass


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def parse_batch(value: str) -> tuple[str, str, Path]:
    if "=" not in value or ":" not in value.split("=", 1)[0]:
        raise argparse.ArgumentTypeError("batch must be ARM:BATCH=DIR")
    identity, raw_path = value.split("=", 1)
    name, batch = identity.split(":", 1)
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name):
        raise argparse.ArgumentTypeError("arm name must be a lowercase identifier")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", batch):
        raise argparse.ArgumentTypeError("batch name must be a lowercase identifier")
    path = Path(raw_path).resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"batch directory not found: {raw_path}")
    return name, batch, path


def safe_member_path(member: tarfile.TarInfo) -> PurePosixPath:
    if "\\" in member.name or "\x00" in member.name:
        raise AuditError("unsafe tar member spelling")
    pure = PurePosixPath(member.name)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise AuditError("unsafe tar member path")
    if member.issym() or member.islnk() or member.isdev() or member.isfifo():
        raise AuditError("unsafe tar member type")
    return pure


def member_role(pure: PurePosixPath) -> tuple[str, str] | None:
    if pure.name == "dojo_config.json" and len(pure.parts) >= 2:
        return "/".join(pure.parts[:-1]), "config"
    if pure.parts[-2:] == ("checkpoint", "journal.jsonl") and len(pure.parts) >= 3:
        return "/".join(pure.parts[:-2]), "checkpoint"
    return None


def read_checked_member(
    handle: tarfile.TarFile, member: tarfile.TarInfo, max_member_bytes: int
) -> bytes:
    if member.size < 0 or member.size > max_member_bytes:
        raise AuditError("allowlisted tar member outside byte cap")
    stream = handle.extractfile(member)
    if stream is None:
        raise AuditError("allowlisted tar member unreadable")
    blob = stream.read(max_member_bytes + 1)
    if len(blob) != member.size or len(blob) > max_member_bytes:
        raise AuditError("allowlisted tar member size mismatch")
    if CREDENTIAL.search(blob):
        raise AuditError("credential-shaped allowlisted member refused before JSON parsing")
    return blob


def read_archive(
    archive: Path,
    max_member_bytes: int,
    max_members: int,
    max_declared_bytes: int,
) -> tuple[dict[str, dict[str, bytes]], dict[str, int]]:
    roots: dict[str, dict[str, bytes]] = collections.defaultdict(dict)
    member_count = 0
    declared_bytes = 0
    with tarfile.open(archive, "r|gz") as handle:
        for member in handle:
            member_count += 1
            declared_bytes += max(0, member.size)
            if member_count > max_members:
                raise AuditError("archive exceeds member-count cap")
            if declared_bytes > max_declared_bytes:
                raise AuditError("archive exceeds declared-byte cap")
            pure = safe_member_path(member)
            role = member_role(pure)
            if role is None or not member.isfile():
                continue
            root, kind = role
            if kind in roots[root]:
                raise AuditError(f"duplicate {kind} for one run root")
            roots[root][kind] = read_checked_member(handle, member, max_member_bytes)
    if not roots:
        raise AuditError("archive contains no allowlisted run roots")
    return dict(roots), {
        "members": member_count,
        "declared_member_bytes": declared_bytes,
        "discovered_run_roots": len(roots),
        "complete_run_roots": sum(set(value) == {"config", "checkpoint"} for value in roots.values()),
        "incomplete_run_roots": sum(set(value) != {"config", "checkpoint"} for value in roots.values()),
    }


def nested(value: object, path: str) -> object:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise AuditError(f"required config field missing: {path}")
        current = current[part]
    return current


def canonical_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    )


def config_contract(blob: bytes) -> tuple[dict[str, Any], str, int]:
    try:
        value = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditError("invalid config JSON") from error
    if not isinstance(value, dict):
        raise AuditError("config must be an object")
    selected = {path: nested(value, path) for path in CONTRACT_PATHS}
    seed = nested(value, "metadata.seed")
    task = nested(value, "task.name")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise AuditError("metadata.seed must be an integer")
    if not isinstance(task, str) or not task:
        raise AuditError("task.name must be a nonempty string")
    operators: dict[str, Any] = {}
    for operator in OPERATORS:
        prefix = f"solver.operators.{operator}"
        prompts = {
            field: nested(value, f"{prefix}.{field}.template") for field in PROMPT_FIELDS
        }
        operators[operator] = {
            "model_id": nested(value, f"{prefix}.llm.client.model_id"),
            "provider": nested(value, f"{prefix}.llm.client.provider"),
            "generation_kwargs": nested(value, f"{prefix}.llm.generation_kwargs"),
            "prompt_sha256": canonical_hash(prompts),
        }
    contract = {"selected": selected, "operators": operators}
    return contract, task, seed


def parse_journal(blob: bytes, expected_task: str) -> tuple[list[dict[str, Any]], str]:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AuditError("journal is not UTF-8") from error
    nodes: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise AuditError(f"invalid journal JSON at line {line_number}") from error
        if not isinstance(value, dict):
            raise AuditError("journal row must be an object")
        nodes.append(value)
    if not nodes:
        raise AuditError("journal is empty")
    steps = [node.get("step") for node in nodes]
    if any(isinstance(step, bool) or not isinstance(step, int) for step in steps):
        raise AuditError("journal steps must be integers")
    if len(set(steps)) != len(steps):
        raise AuditError("journal steps are not unique")
    by_step = {int(node["step"]): node for node in nodes}
    roots = [node for node in nodes if node["step"] == 0 and not (node.get("parents") or [])]
    if len(roots) != 1:
        raise AuditError("journal must contain exactly one step-0 root")
    root_time = roots[0].get("creation_time")
    if isinstance(root_time, bool) or not isinstance(root_time, (int, float)):
        raise AuditError("root creation_time must be numeric")
    if not math.isfinite(float(root_time)):
        raise AuditError("root creation_time must be finite")
    inferred_tasks = set()
    for node in nodes:
        parents = node.get("parents") or []
        if not isinstance(parents, list) or any(
            isinstance(parent, bool) or not isinstance(parent, int) for parent in parents
        ):
            raise AuditError("parents must be an integer list")
        step = int(node["step"])
        if step == 0:
            if parents:
                raise AuditError("step-0 root has parents")
        elif len(parents) != 1 or parents[0] not in by_step or parents[0] >= step:
            raise AuditError("non-root parent contract violated")
        creation = node.get("creation_time")
        if isinstance(creation, bool) or not isinstance(creation, (int, float)):
            raise AuditError("node creation_time must be numeric")
        if not math.isfinite(float(creation)) or float(creation) + 1e-6 < float(root_time):
            raise AuditError("node creation_time precedes root or is non-finite")
        competition = (node.get("metric_info") or {}).get("competition_id")
        if competition:
            inferred_tasks.add(str(competition))
    if inferred_tasks and inferred_tasks != {expected_task}:
        raise AuditError("journal task does not match config task")
    expected_children: dict[int, list[int]] = collections.defaultdict(list)
    for node in nodes:
        for parent in node.get("parents") or []:
            expected_children[int(parent)].append(int(node["step"]))
    for node in nodes:
        declared = node.get("children") or []
        if not isinstance(declared, list) or any(
            isinstance(child, bool) or not isinstance(child, int) for child in declared
        ):
            raise AuditError("children must be an integer list")
        if sorted(declared) != sorted(expected_children[int(node["step"])]):
            raise AuditError("declared children do not match parent graph")
    return nodes, sha256_bytes(blob)


def gini(values: list[int]) -> float:
    if not values or sum(values) <= 0:
        raise AuditError("Gini requires positive branch sizes")
    ordered = sorted(values)
    n = len(ordered)
    return (2.0 * sum((index + 1) * value for index, value in enumerate(ordered))) / (
        n * sum(ordered)
    ) - (n + 1.0) / n


def structure_metrics(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    parent: dict[int, int | None] = {}
    for node in nodes:
        step = int(node["step"])
        parents = node.get("parents") or []
        parent[step] = int(parents[0]) if parents else None
    depths: dict[int, int] = {0: 0}
    first_branch: dict[int, int] = {}
    for step in sorted(parent):
        if step == 0:
            continue
        ancestor = parent[step]
        if ancestor is None or ancestor not in depths:
            raise AuditError("journal is not topologically ordered by step")
        depths[step] = depths[ancestor] + 1
        first_branch[step] = step if ancestor == 0 else first_branch[ancestor]
    branch_sizes = collections.Counter(first_branch.values())
    sizes = list(branch_sizes.values())
    branches = len(sizes)
    nonroot = len(nodes) - 1
    eligible = branches >= 2 and nonroot >= 4
    output: dict[str, Any] = {
        "nodes": len(nodes),
        "nonroot_nodes": nonroot,
        "max_depth": max(depths.values()),
        "root_branches": branches,
        "structure_eligible": eligible,
        "max_branch_share": None,
        "hhi": None,
        "normalized_hhi": None,
        "normalized_entropy": None,
        "effective_branch_ratio": None,
        "gini": None,
    }
    if not eligible:
        return output
    probabilities = [size / nonroot for size in sizes]
    hhi = sum(probability * probability for probability in probabilities)
    normalized_hhi = (hhi - 1.0 / branches) / (1.0 - 1.0 / branches)
    entropy = -sum(probability * math.log(probability) for probability in probabilities)
    output.update(
        {
            "max_branch_share": max(probabilities),
            "hhi": hhi,
            "normalized_hhi": normalized_hhi,
            "normalized_entropy": entropy / math.log(branches),
            "effective_branch_ratio": (1.0 / hhi) / branches,
            "gini": gini(sizes),
        }
    )
    return output


def quantile(values: list[float], probability: float) -> float:
    if not values:
        raise AuditError("quantile requires values")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def median(values: Iterable[float]) -> float:
    items = list(values)
    return quantile(items, 0.5)


def task_summary(rows: list[dict[str, Any]], arm_names: tuple[str, str]) -> dict[str, Any]:
    by_task_arm: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        if row["structure_eligible"]:
            by_task_arm[(str(row["task"]), str(row["arm"]))].append(row)
    common = sorted(
        task
        for task in {str(row["task"]) for row in rows}
        if all(by_task_arm[(task, arm)] for arm in arm_names)
    )
    metrics = (
        "max_branch_share",
        "hhi",
        "normalized_hhi",
        "normalized_entropy",
        "effective_branch_ratio",
        "gini",
    )
    per_task: dict[str, Any] = {}
    for task in common:
        item: dict[str, Any] = {"arms": {}}
        for arm in arm_names:
            arm_rows = by_task_arm[(task, arm)]
            item["arms"][arm] = {
                "runs": len(arm_rows),
                **{
                    f"median_{metric}": median(float(row[metric]) for row in arm_rows)
                    for metric in metrics
                },
            }
        item["sequential_minus_mcts_normalized_hhi"] = (
            item["arms"][arm_names[1]]["median_normalized_hhi"]
            - item["arms"][arm_names[0]]["median_normalized_hhi"]
        )
        per_task[task] = item
    supported = [
        task
        for task in common
        if all(len(by_task_arm[(task, arm)]) >= 4 for arm in arm_names)
    ]
    macro = None
    ci = None
    if supported:
        differences = [
            per_task[task]["sequential_minus_mcts_normalized_hhi"] for task in supported
        ]
        macro = sum(differences) / len(differences)
        rng = random.Random(BOOTSTRAP_SEED)
        bootstrap: list[float] = []
        for _ in range(BOOTSTRAP_REPLICATES):
            task_differences = []
            for task in supported:
                arm_medians = []
                for arm in arm_names:
                    values = [
                        float(row["normalized_hhi"]) for row in by_task_arm[(task, arm)]
                    ]
                    sampled = [values[rng.randrange(len(values))] for _ in values]
                    arm_medians.append(median(sampled))
                task_differences.append(arm_medians[1] - arm_medians[0])
            bootstrap.append(sum(task_differences) / len(task_differences))
        ci = [quantile(bootstrap, 0.025), quantile(bootstrap, 0.975)]
    return {
        "common_tasks": common,
        "supported_tasks_min_four_runs_per_arm": supported,
        "per_task": per_task,
        "task_macro_sequential_minus_mcts_normalized_hhi": macro,
        "descriptive_run_bootstrap_ci95": ci,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RUN_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in RUN_COLUMNS})


def inventory_arms(
    batches: list[tuple[str, str, Path]], max_archives: int, max_archive_bytes: int
) -> list[dict[str, Any]]:
    records = []
    seen_paths = set()
    seen_batches = set()
    for arm, batch, directory in batches:
        if (arm, batch) in seen_batches:
            raise AuditError("duplicate arm/batch identity")
        seen_batches.add((arm, batch))
        archives = sorted(directory.glob("*.tar.gz"), key=lambda path: path.name)
        if not archives or len(archives) > max_archives:
            raise AuditError(f"arm {arm} archive count outside cap")
        for archive in archives:
            resolved = archive.resolve()
            if resolved in seen_paths or archive.is_symlink() or archive.parent.resolve() != directory:
                raise AuditError("archive inventory is not flat and unique")
            seen_paths.add(resolved)
            size = archive.stat().st_size
            if size <= 0 or size > max_archive_bytes:
                raise AuditError("archive byte size outside cap")
            records.append(
                {
                    "arm": arm,
                    "batch": batch,
                    "archive": archive.name,
                    "path": archive,
                    "bytes": size,
                    "sha256": sha256(archive),
                }
            )
    archive_hashes = [str(record["sha256"]) for record in records]
    if len(archive_hashes) != len(set(archive_hashes)):
        raise AuditError("duplicate archive bytes require explicit curation")
    return records


def contract_comparison(rows: list[dict[str, Any]], arm_names: tuple[str, str]) -> dict[str, Any]:
    by_task_arm: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for row in rows:
        by_task_arm[(str(row["task"]), str(row["arm"]))].add(str(row["contract_sha256"]))
    common_tasks = sorted(
        task
        for task in {str(row["task"]) for row in rows}
        if all(by_task_arm[(task, arm)] for arm in arm_names)
    )
    per_task = {}
    for task in common_tasks:
        left = sorted(by_task_arm[(task, arm_names[0])])
        right = sorted(by_task_arm[(task, arm_names[1])])
        per_task[task] = {
            arm_names[0]: left,
            arm_names[1]: right,
            "exact_contract_match": left == right and len(left) == 1,
        }
    return {
        "common_tasks": common_tasks,
        "per_task": per_task,
        "all_common_tasks_exact_contract_match": bool(common_tasks)
        and all(item["exact_contract_match"] for item in per_task.values()),
    }


def build(args: argparse.Namespace) -> int:
    batches = list(args.batch)
    if {name for name, _, _ in batches} != {"mcts", "sequential"}:
        raise AuditError("v1 requires mcts and sequential batches")
    arm_names = ("mcts", "sequential")
    out_dir = args.out_dir.resolve()
    temporary = out_dir.with_name(out_dir.name + ".tmp")
    if out_dir.exists() or temporary.exists():
        raise FileExistsError("refusing to overwrite audit output")
    records = inventory_arms(batches, args.max_archives_per_batch, args.max_archive_bytes)
    temporary.mkdir(parents=True)
    with (temporary / "input_manifest.tsv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("arm", "batch", "archive", "bytes", "sha256"))
        for record in records:
            writer.writerow(
                (
                    record["arm"], record["batch"], record["archive"],
                    record["bytes"], record["sha256"]
                )
            )
    rows: list[dict[str, Any]] = []
    archive_audits = []
    seen_journals: set[str] = set()
    for record in records:
        archive = Path(record["path"])
        if sha256(archive) != record["sha256"]:
            raise AuditError("archive changed after inventory freeze")
        roots, archive_audit = read_archive(
            archive,
            args.max_member_bytes,
            args.max_members_per_archive,
            args.max_declared_bytes_per_archive,
        )
        for payload in roots.values():
            if set(payload) != {"config", "checkpoint"}:
                continue
            contract, task, seed = config_contract(payload["config"])
            nodes, journal_sha = parse_journal(payload["checkpoint"], task)
            if journal_sha in seen_journals:
                raise AuditError("duplicate physical journal across input archives")
            seen_journals.add(journal_sha)
            metrics = structure_metrics(nodes)
            rows.append(
                {
                    "arm": record["arm"],
                    "batch": record["batch"],
                    "archive": record["archive"],
                    "archive_sha256": record["sha256"],
                    "journal_sha256": journal_sha,
                    "task": task,
                    "seed": seed,
                    "contract": contract,
                    "contract_sha256": canonical_hash(contract),
                    **metrics,
                }
            )
        archive_audits.append(
            {
                "arm": record["arm"],
                "batch": record["batch"],
                "archive": record["archive"],
                "archive_sha256": record["sha256"],
                **archive_audit,
            }
        )
    rows.sort(key=lambda row: (
        str(row["arm"]), str(row["batch"]), str(row["task"]),
        int(row["seed"]), str(row["journal_sha256"])
    ))
    write_csv(temporary / "run_structure.csv", rows)
    contract = contract_comparison(rows, arm_names)
    structure = task_summary(rows, arm_names)
    contract_catalog = {
        str(row["contract_sha256"]): row["contract"] for row in rows
    }
    per_arm = {}
    for arm in arm_names:
        selected = [row for row in rows if row["arm"] == arm]
        audits = [item for item in archive_audits if item["arm"] == arm]
        discovered = sum(int(item["discovered_run_roots"]) for item in audits)
        complete = sum(int(item["complete_run_roots"]) for item in audits)
        per_arm[arm] = {
            "archives": sum(record["arm"] == arm for record in records),
            "physical_runs": len(selected),
            "tasks": len({str(row["task"]) for row in selected}),
            "structure_eligible_runs": sum(bool(row["structure_eligible"]) for row in selected),
            "journal_coverage": complete / discovered if discovered else 0.0,
            "contract_signatures": len({str(row["contract_sha256"]) for row in selected}),
        }
    support_checks = {
        "at_least_twenty_physical_runs_per_arm": all(
            per_arm[arm]["physical_runs"] >= 20 for arm in arm_names
        ),
        "journal_coverage_at_least_0_8_per_arm": all(
            per_arm[arm]["journal_coverage"] >= 0.8 for arm in arm_names
        ),
        "at_least_two_common_tasks": len(structure["common_tasks"]) >= 2,
        "at_least_one_common_task_with_four_runs_per_arm": bool(
            structure["supported_tasks_min_four_runs_per_arm"]
        ),
    }
    support_pass = all(support_checks.values())
    contract_pass = bool(contract["all_common_tasks_exact_contract_match"])
    if contract_pass and support_pass:
        status = "HISTORICAL_POLICY_NATURAL_EXPERIMENT_ELIGIBLE"
    elif support_pass:
        status = "CONTRACT_KILLED_DESCRIPTIVE_COMPLETE"
    else:
        status = "CONTRACT_KILLED_DESCRIPTIVE_SUPPORT_INSUFFICIENT"
    summary = {
        "status": status,
        "protocol": PROTOCOL,
        "outcome_blind_discovery": False,
        "known_before_full_audit": [
            "The old fragment audit had already shown a two-task exploratory direction.",
            "One nomad config from each arm had already shown model, timeout, children, and commit differences.",
        ],
        "inventory": {"archives": len(records), "physical_runs": len(rows), "per_arm": per_arm},
        "contract": contract,
        "structure": structure,
        "support_checks": support_checks,
        "integrity": {
            "credential_shaped_allowlisted_members": 0,
            "duplicate_archive_bytes": 0,
            "duplicate_physical_journals": 0,
            "environment_files_read": 0,
            "grades_read": 0,
            "code_or_term_output_written": 0,
        },
        "limitations": [
            "The collection policy was not randomized.",
            "Any contract mismatch makes structural differences descriptive rather than causal.",
            "No grade was read, so this audit does not estimate label bias or critic utility.",
        ],
    }
    atomic_json(temporary / "archive_audits.json", archive_audits)
    atomic_json(temporary / "contract_catalog.json", contract_catalog)
    atomic_json(temporary / "summary.json", summary)
    metadata = {
        "protocol": PROTOCOL,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_commit": git_commit(args.repo_root.resolve()),
        "python": sys.version,
        "platform": platform.platform(),
        "command": sys.argv,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    }
    atomic_json(temporary / "run_metadata.json", metadata)
    with (temporary / "artifact_manifest.sha256").open("x", encoding="utf-8", newline="") as handle:
        for path in sorted(temporary.iterdir(), key=lambda item: item.name):
            if path.name == "artifact_manifest.sha256":
                continue
            handle.write(f"{sha256(path)}  {path.name}\n")
    os.replace(temporary, out_dir)
    print(
        status,
        f"archives={len(records)}",
        f"physical_runs={len(rows)}",
        f"common_tasks={len(structure['common_tasks'])}",
        f"supported_tasks={len(structure['supported_tasks_min_four_runs_per_arm'])}",
        f"contract_pass={contract_pass}",
        f"support_pass={support_pass}",
        f"summary_sha256={sha256(out_dir / 'summary.json')}",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="append", required=True, type=parse_batch)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--max-archives-per-batch", type=int, default=128)
    parser.add_argument("--max-archive-bytes", type=int, default=64 * 1024 * 1024 * 1024)
    parser.add_argument("--max-member-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--max-members-per-archive", type=int, default=1_000_000)
    parser.add_argument(
        "--max-declared-bytes-per-archive", type=int, default=256 * 1024 * 1024 * 1024
    )
    args = parser.parse_args()
    caps = (
        args.max_archives_per_batch,
        args.max_archive_bytes,
        args.max_member_bytes,
        args.max_members_per_archive,
        args.max_declared_bytes_per_archive,
    )
    if any(value <= 0 for value in caps):
        raise AuditError("resource caps must be positive")
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
