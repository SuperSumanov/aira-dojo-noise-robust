"""Independent artifact verifier for ``search_policy_contract_audit_v1``.

This verifier does not import the producer.  It rehashes immutable input archives, checks the
artifact manifest and strict schemas, and independently recomputes inventory, contract, support,
and descriptive task summaries from the emitted run-level CSV.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import random
import re
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "search_policy_contract_audit_v1"
BOOTSTRAP_SEED = 20260814
BOOTSTRAP_REPLICATES = 10_000
ARMS = ("mcts", "sequential")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)
RUN_COLUMNS = (
    "arm",
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
EXPECTED_ARTIFACTS = {
    "archive_audits.json",
    "contract_catalog.json",
    "input_manifest.tsv",
    "run_metadata.json",
    "run_structure.csv",
    "summary.json",
}
CONTRACT_PATHS = {
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
}
OPERATORS = {"analyze", "draft", "debug", "improve"}


class VerifyError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_arm(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("arm must be NAME=DIR")
    name, raw_path = value.split("=", 1)
    path = Path(raw_path).resolve()
    if name not in ARMS or not path.is_dir():
        raise argparse.ArgumentTypeError("invalid arm name or directory")
    return name, path


def quantile(values: list[float], probability: float) -> float:
    if not values:
        raise VerifyError("empty quantile")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def median(values: Iterable[float]) -> float:
    return quantile(list(values), 0.5)


def close(left: object, right: object, tolerance: float = 1e-12) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return all(close(a, b, tolerance) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict) and set(left) == set(right):
        return all(close(left[key], right[key], tolerance) for key in left)
    return left == right


def verify_artifact_manifest(result: Path) -> None:
    manifest = result / "artifact_manifest.sha256"
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line]
    names = set()
    for line in lines:
        if "  " not in line:
            raise VerifyError("malformed artifact manifest")
        expected, name = line.split("  ", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or Path(name).name != name:
            raise VerifyError("unsafe artifact manifest entry")
        if name in names or not (result / name).is_file() or sha256(result / name) != expected:
            raise VerifyError("artifact manifest hash or uniqueness failure")
        names.add(name)
    if names != EXPECTED_ARTIFACTS:
        raise VerifyError("artifact manifest coverage mismatch")


def verify_input_manifest(result: Path, arm_roots: dict[str, Path]) -> list[dict[str, Any]]:
    with (result / "input_manifest.tsv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != ("arm", "archive", "bytes", "sha256"):
            raise VerifyError("input manifest schema mismatch")
        rows = list(reader)
    identities = set()
    hashes = set()
    for row in rows:
        arm = row["arm"]
        archive = row["archive"]
        if arm not in arm_roots or Path(archive).name != archive:
            raise VerifyError("input manifest arm/path mismatch")
        path = arm_roots[arm] / archive
        identity = (arm, archive)
        if identity in identities or row["sha256"] in hashes:
            raise VerifyError("duplicate input archive identity or bytes")
        identities.add(identity)
        hashes.add(row["sha256"])
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != int(row["bytes"])
            or sha256(path) != row["sha256"]
        ):
            raise VerifyError("immutable input archive no longer matches manifest")
    if not rows:
        raise VerifyError("empty input manifest")
    return rows


def load_runs(result: Path) -> list[dict[str, Any]]:
    with (result / "run_structure.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != RUN_COLUMNS:
            raise VerifyError("run CSV schema mismatch")
        raw = list(reader)
    output = []
    seen_journals = set()
    for row in raw:
        if row["arm"] not in ARMS or not row["task"]:
            raise VerifyError("invalid run arm/task")
        if not re.fullmatch(r"[0-9a-f]{64}", row["journal_sha256"]):
            raise VerifyError("invalid journal SHA")
        if row["journal_sha256"] in seen_journals:
            raise VerifyError("duplicate physical journal in run CSV")
        seen_journals.add(row["journal_sha256"])
        eligible = row["structure_eligible"] == "True"
        if row["structure_eligible"] not in {"True", "False"}:
            raise VerifyError("invalid structure eligible flag")
        parsed: dict[str, Any] = dict(row)
        parsed["seed"] = int(row["seed"])
        for key in ("nodes", "nonroot_nodes", "max_depth", "root_branches"):
            parsed[key] = int(row[key])
        parsed["structure_eligible"] = eligible
        for key in (
            "max_branch_share",
            "hhi",
            "normalized_hhi",
            "normalized_entropy",
            "effective_branch_ratio",
            "gini",
        ):
            parsed[key] = float(row[key]) if row[key] else None
            if parsed[key] is not None and not math.isfinite(parsed[key]):
                raise VerifyError("non-finite structure metric")
        if parsed["nodes"] != parsed["nonroot_nodes"] + 1:
            raise VerifyError("node inventory mismatch")
        if eligible != (parsed["root_branches"] >= 2 and parsed["nonroot_nodes"] >= 4):
            raise VerifyError("structure eligibility mismatch")
        if eligible and any(parsed[key] is None for key in (
            "max_branch_share", "hhi", "normalized_hhi", "normalized_entropy",
            "effective_branch_ratio", "gini"
        )):
            raise VerifyError("eligible run is missing a structure metric")
        if not eligible and any(parsed[key] is not None for key in (
            "max_branch_share", "hhi", "normalized_hhi", "normalized_entropy",
            "effective_branch_ratio", "gini"
        )):
            raise VerifyError("ineligible run unexpectedly has structure metrics")
        output.append(parsed)
    if not output:
        raise VerifyError("empty run CSV")
    return output


def verify_contract_catalog(result: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    catalog = json.loads((result / "contract_catalog.json").read_text(encoding="utf-8"))
    if set(catalog) != {row["contract_sha256"] for row in rows}:
        raise VerifyError("contract catalog coverage mismatch")
    for signature, value in catalog.items():
        if not re.fullmatch(r"[0-9a-f]{64}", signature) or set(value) != {"operators", "selected"}:
            raise VerifyError("contract catalog top-level schema mismatch")
        if set(value["selected"]) != CONTRACT_PATHS or set(value["operators"]) != OPERATORS:
            raise VerifyError("contract catalog field coverage mismatch")
        for operator in value["operators"].values():
            if set(operator) != {"model_id", "provider", "generation_kwargs", "prompt_sha256"}:
                raise VerifyError("operator contract schema mismatch")
            if not re.fullmatch(r"[0-9a-f]{64}", operator["prompt_sha256"]):
                raise VerifyError("operator prompt SHA malformed")
    return catalog


def recompute_contract(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by = collections.defaultdict(set)
    for row in rows:
        by[(row["task"], row["arm"])].add(row["contract_sha256"])
    common = sorted(
        task for task in {row["task"] for row in rows} if all(by[(task, arm)] for arm in ARMS)
    )
    per_task = {}
    for task in common:
        left, right = sorted(by[(task, ARMS[0])]), sorted(by[(task, ARMS[1])])
        per_task[task] = {
            ARMS[0]: left,
            ARMS[1]: right,
            "exact_contract_match": left == right and len(left) == 1,
        }
    return {
        "common_tasks": common,
        "per_task": per_task,
        "all_common_tasks_exact_contract_match": bool(common)
        and all(item["exact_contract_match"] for item in per_task.values()),
    }


def recompute_structure(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by = collections.defaultdict(list)
    for row in rows:
        if row["structure_eligible"]:
            by[(row["task"], row["arm"])].append(row)
    common = sorted(
        task for task in {row["task"] for row in rows} if all(by[(task, arm)] for arm in ARMS)
    )
    metric_names = (
        "max_branch_share", "hhi", "normalized_hhi", "normalized_entropy",
        "effective_branch_ratio", "gini"
    )
    per_task = {}
    for task in common:
        item: dict[str, Any] = {"arms": {}}
        for arm in ARMS:
            selected = by[(task, arm)]
            item["arms"][arm] = {
                "runs": len(selected),
                **{
                    f"median_{metric}": median(float(row[metric]) for row in selected)
                    for metric in metric_names
                },
            }
        item["sequential_minus_mcts_normalized_hhi"] = (
            item["arms"]["sequential"]["median_normalized_hhi"]
            - item["arms"]["mcts"]["median_normalized_hhi"]
        )
        per_task[task] = item
    supported = [task for task in common if all(len(by[(task, arm)]) >= 4 for arm in ARMS)]
    macro = None
    ci = None
    if supported:
        macro = sum(per_task[task]["sequential_minus_mcts_normalized_hhi"] for task in supported) / len(supported)
        rng = random.Random(BOOTSTRAP_SEED)
        replicates = []
        for _ in range(BOOTSTRAP_REPLICATES):
            differences = []
            for task in supported:
                arm_medians = []
                for arm in ARMS:
                    values = [float(row["normalized_hhi"]) for row in by[(task, arm)]]
                    sampled = [values[rng.randrange(len(values))] for _ in values]
                    arm_medians.append(median(sampled))
                differences.append(arm_medians[1] - arm_medians[0])
            replicates.append(sum(differences) / len(differences))
        ci = [quantile(replicates, 0.025), quantile(replicates, 0.975)]
    return {
        "common_tasks": common,
        "supported_tasks_min_four_runs_per_arm": supported,
        "per_task": per_task,
        "task_macro_sequential_minus_mcts_normalized_hhi": macro,
        "descriptive_run_bootstrap_ci95": ci,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    }


def verify(args: argparse.Namespace) -> int:
    result = args.result_dir.resolve()
    if not result.is_dir():
        raise VerifyError("result directory missing")
    arms = dict(args.arm)
    if set(arms) != set(ARMS) or len(args.arm) != 2:
        raise VerifyError("exact mcts and sequential arm roots required")
    verify_artifact_manifest(result)
    for path in result.iterdir():
        if path.is_file() and CREDENTIAL.search(path.read_bytes()):
            raise VerifyError("credential shape found in result artifact")
    input_rows = verify_input_manifest(result, arms)
    rows = load_runs(result)
    catalog = verify_contract_catalog(result, rows)
    del catalog
    archive_identity = {(row["arm"], row["archive"]): row for row in input_rows}
    for row in rows:
        key = (row["arm"], row["archive"])
        if key not in archive_identity or row["archive_sha256"] != archive_identity[key]["sha256"]:
            raise VerifyError("run row archive identity mismatch")
    archive_audits = json.loads((result / "archive_audits.json").read_text(encoding="utf-8"))
    if len(archive_audits) != len(input_rows):
        raise VerifyError("archive audit count mismatch")
    contract = recompute_contract(rows)
    structure = recompute_structure(rows)
    per_arm = {}
    for arm in ARMS:
        selected = [row for row in rows if row["arm"] == arm]
        audits = [row for row in archive_audits if row["arm"] == arm]
        discovered = sum(int(row["discovered_run_roots"]) for row in audits)
        complete = sum(int(row["complete_run_roots"]) for row in audits)
        per_arm[arm] = {
            "archives": sum(row["arm"] == arm for row in input_rows),
            "physical_runs": len(selected),
            "tasks": len({row["task"] for row in selected}),
            "structure_eligible_runs": sum(bool(row["structure_eligible"]) for row in selected),
            "journal_coverage": complete / discovered if discovered else 0.0,
            "contract_signatures": len({row["contract_sha256"] for row in selected}),
        }
    support_checks = {
        "at_least_twenty_physical_runs_per_arm": all(per_arm[arm]["physical_runs"] >= 20 for arm in ARMS),
        "journal_coverage_at_least_0_8_per_arm": all(per_arm[arm]["journal_coverage"] >= 0.8 for arm in ARMS),
        "at_least_two_common_tasks": len(structure["common_tasks"]) >= 2,
        "at_least_one_common_task_with_four_runs_per_arm": bool(structure["supported_tasks_min_four_runs_per_arm"]),
    }
    support_pass = all(support_checks.values())
    contract_pass = contract["all_common_tasks_exact_contract_match"]
    expected_status = (
        "HISTORICAL_POLICY_NATURAL_EXPERIMENT_ELIGIBLE"
        if contract_pass and support_pass
        else "CONTRACT_KILLED_DESCRIPTIVE_COMPLETE"
        if support_pass
        else "CONTRACT_KILLED_DESCRIPTIVE_SUPPORT_INSUFFICIENT"
    )
    summary = json.loads((result / "summary.json").read_text(encoding="utf-8"))
    expected = {
        "status": expected_status,
        "protocol": PROTOCOL,
        "inventory": {"archives": len(input_rows), "physical_runs": len(rows), "per_arm": per_arm},
        "contract": contract,
        "structure": structure,
        "support_checks": support_checks,
    }
    for key, value in expected.items():
        if key not in summary or not close(summary[key], value):
            raise VerifyError(f"summary mismatch at {key}")
    integrity = summary.get("integrity") or {}
    if not integrity or any(value != 0 for value in integrity.values()):
        raise VerifyError("summary integrity counters are not all zero")
    metadata = json.loads((result / "run_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("protocol") != PROTOCOL or metadata.get("bootstrap_seed") != BOOTSTRAP_SEED:
        raise VerifyError("run metadata protocol/seed mismatch")
    print(
        "SEARCH_POLICY_CONTRACT_AUDIT_VERIFIED",
        f"status={expected_status}",
        f"archives={len(input_rows)}",
        f"physical_runs={len(rows)}",
        f"summary_sha256={sha256(result / 'summary.json')}",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--arm", action="append", required=True, type=parse_arm)
    return verify(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
