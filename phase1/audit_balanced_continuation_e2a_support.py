"""Outcome-blind structural/data qualification for balanced-continuation E2-A.

The audit deliberately has no argument for scores, grades, gaps, winner orientation,
official test data, or private competition answers.  It qualifies six public-train-only
tasks and deterministically freezes four exact-two parents from distinct physical runs
per task.  It does not build an evaluator or authorize a paid rollout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import pathlib
import re
import tempfile
from collections import Counter, defaultdict
from typing import Any


SCHEMA = "balanced-continuation-e2a-support-audit-v1"
SELECTION_SEED = 20260819
EXPECTED_CARD_ROWS = 16012
EXPECTED_SHA256 = {
    "cards": "6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75",
    "hold": "b31bd70a4483ac1ca207eae47ae39d7b00ced1b02c81583d0b0447fdd3d8489b",
    "decision_train_b0": "bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca",
    "frozen_b0": "2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8",
    "frozen_b1": "a56f6c7bd6aad141fdaa45f3f30f944062e8dea922eefc03e75bc8b415e7bc90",
    "frozen_b2": "79d4694d4cea5a81a04c9d463b5c6599a559bbf867f34205fa5715b054f10bc7",
}
TASK_SPECS: dict[str, dict[str, Any]] = {
    "spaceship-titanic": {
        "id_column": "PassengerId",
        "target_column": "Transported",
        "target_columns": ["Transported"],
        "submission_columns": ["Transported"],
        "metric": "accuracy",
        "split_stratification": "exact_target",
        "train_sha256": "d852203bbc5e603b92a7cfc0b46e23277c43d7a910b1db8b0ad58b7c6e3f2baa",
        "description_sha256": "ee35380587404b263ef8b38d9a2fff4196563abb2e12bc086b02c9808b7f37cb",
    },
    "tabular-playground-series-may-2022": {
        "id_column": "id",
        "target_column": "target",
        "target_columns": ["target"],
        "submission_columns": ["target"],
        "metric": "roc_auc",
        "split_stratification": "exact_target",
        "train_sha256": "f0940d6a4c3536752bdc3ba99251fc3020662ea43b28dfad520d810b3cde5514",
        "description_sha256": "a64340a1c829f6e2c3ee8411cfa3089a4418571fee7186c91b5be2ef241bfcff",
    },
    "spooky-author-identification": {
        "id_column": "id",
        "target_column": "author",
        "target_columns": ["author"],
        "submission_columns": ["EAP", "HPL", "MWS"],
        "metric": "multiclass_log_loss",
        "split_stratification": "exact_target",
        "train_sha256": "87a02befe9c415b976486e4a59b96da0cc907b8645efbb7052256307715ecdbf",
        "description_sha256": "35d7de46d74377f997bdc7f5859e36ca3311fb4ae2e37ab63491a9d7c72661bd",
    },
    "us-patent-phrase-to-phrase-matching": {
        "id_column": "id",
        "target_column": "score",
        "target_columns": ["score"],
        "submission_columns": ["score"],
        "metric": "pearson",
        "split_stratification": "exact_target",
        "train_sha256": "f5ba9a9b1b7fa3e025c65ece3fa2b92867c7436919c56d11e346d5344bcca205",
        "description_sha256": "c2cc3682177d64f12e3c4d651389d7d6ef50852eaf97ccbcee55f62ebe957f53",
    },
    "nomad2018-predict-transparent-conductors": {
        "id_column": "id",
        "target_column": "formation_energy_ev_natom",
        "target_columns": ["formation_energy_ev_natom", "bandgap_energy_ev"],
        "submission_columns": ["formation_energy_ev_natom", "bandgap_energy_ev"],
        "metric": "mean_columnwise_rmsle",
        "split_stratification": "formation_energy_rank_decile",
        "train_sha256": "6a85d60056f8737c6575c8a7c0575fee6501916cf1dbd6199b0113849352546c",
        "description_sha256": "d70aa4ad5bd3c2d460b750ae26b7f3572271dcab50499f4c8de66f7d6c45e1ad",
    },
    "learning-agency-lab-automated-essay-scoring-2": {
        "id_column": "essay_id",
        "target_column": "score",
        "target_columns": ["score"],
        "submission_columns": ["score"],
        "metric": "quadratic_weighted_kappa",
        "split_stratification": "exact_target",
        "train_sha256": "ce6b0bd2c7d790a64ad3d2a8e15e3563d90e881c787638caa93504445caa65d0",
        "description_sha256": "c11986179a042c909be5ab23275650f66160d7916ad229e133ca3f2af493cbed",
    },
}
TASK_ORDER = tuple(TASK_SPECS)
FORBIDDEN_KEYS = {
    "grade", "grades", "gap", "gap_raw", "label", "labels", "metric_value",
    "prediction", "predictions", "reward", "rewards", "score", "scores",
    "self_report", "stdout", "winner", "winners",
}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class AuditError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: pathlib.Path, expected: str, role: str) -> str:
    if not path.is_file() or path.is_symlink():
        raise AuditError(f"missing or symlinked {role}: {path}")
    actual = file_sha256(path)
    if actual != expected:
        raise AuditError(f"{role} SHA differs: expected={expected} actual={actual}")
    return actual


def checked_json(path: pathlib.Path) -> Any:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise AuditError(f"credential-shaped bytes in {path.name}")
    return json.loads(raw)


def load_hold(path: pathlib.Path) -> set[str]:
    value = checked_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("hold"), list):
        raise AuditError("hold manifest schema differs")
    hold = value["hold"]
    if len(hold) != len(set(hold)) or not all(isinstance(item, str) and item for item in hold):
        raise AuditError("hold run identities are invalid")
    return set(hold)


def load_frozen_endpoints(paths: list[pathlib.Path]) -> set[str]:
    endpoints: set[str] = set()
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise AuditError(f"frozen row is not an object: {path.name}:{line_number}")
                for key in ("better", "worse"):
                    value = row.get(key)
                    if not isinstance(value, str) or not value:
                        raise AuditError(f"invalid frozen endpoint: {path.name}:{line_number}")
                    endpoints.add(value)
    return endpoints


def load_prior_runs(paths: list[pathlib.Path]) -> tuple[set[str], list[dict[str, str]]]:
    runs: set[str] = set()
    receipts: list[dict[str, str]] = []
    for path in paths:
        rows = checked_json(path)
        if not isinstance(rows, list) or not rows:
            raise AuditError(f"prior selection is not a non-empty list: {path}")
        file_runs: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise AuditError("prior selection row is not an object")
            if set(row) & FORBIDDEN_KEYS:
                raise AuditError("prior selection unexpectedly contains an outcome-bearing key")
            run_id = row.get("source_run_id")
            if not isinstance(run_id, str) or not run_id:
                raise AuditError("prior selection run identity is invalid")
            file_runs.add(run_id)
            runs.add(run_id)
        receipts.append({"sha256": file_sha256(path), "rows": str(len(rows))})
    return runs, receipts


def load_whitelist(path: pathlib.Path) -> dict[str, set[tuple[str, str]]]:
    result = {task: set() for task in TASK_ORDER}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            if not isinstance(row, dict):
                raise AuditError(f"decision row is not an object: {line_number}")
            task = row.get("task")
            if task not in result:
                continue
            # Outcome-bearing fields exist in this released file but are never retained or compared.
            if row.get("budget") != 0 or row.get("intask_split") != "train" or row.get("set_size") != 2:
                continue
            run_id, parent = row.get("run_id"), row.get("parent")
            if not isinstance(run_id, str) or not run_id or not isinstance(parent, str) or not parent:
                raise AuditError(f"invalid decision identity: {line_number}")
            result[task].add((run_id, parent))
    if any(not result[task] for task in TASK_ORDER):
        raise AuditError("at least one fixed task has no b0 train exact-two parent")
    return result


def load_cards(
    path: pathlib.Path, frozen_endpoints: set[str]
) -> tuple[dict[str, dict[str, str | None]], dict[str, list[str]], dict[str, str]]:
    cards: dict[str, dict[str, str | None]] = {}
    children: dict[str, list[str]] = defaultdict(list)
    frozen_endpoint_runs: dict[str, str] = {}
    rows = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            rows += 1
            row = json.loads(line)
            if not isinstance(row, dict):
                raise AuditError(f"card row is not an object: {line_number}")
            card_id = row.get("id")
            task_obj = row.get("task")
            run_id = row.get("run_id")
            if (
                not isinstance(card_id, str) or not card_id or card_id in cards
                or not isinstance(task_obj, dict) or not isinstance(task_obj.get("name"), str)
                or not isinstance(run_id, str) or not run_id
            ):
                raise AuditError(f"card identity/schema differs: {line_number}")
            if card_id in frozen_endpoints:
                frozen_endpoint_runs[card_id] = run_id
            task = task_obj["name"]
            if task not in TASK_SPECS:
                continue
            lineage = row.get("lineage") or {}
            parent = lineage.get("parent_id") if isinstance(lineage, dict) else None
            code = row.get("code")
            if not isinstance(code, str) or not code:
                raise AuditError(f"target-task card lacks code: {line_number}")
            raw_code = code.encode("utf-8")
            if CREDENTIAL.search(raw_code):
                raise AuditError(f"credential-shaped bytes in target-task code: {line_number}")
            cards[card_id] = {
                "task": task,
                "run_id": run_id,
                "parent": parent if isinstance(parent, str) and parent else None,
                "code_sha256": hashlib.sha256(raw_code).hexdigest(),
            }
            if isinstance(parent, str) and parent:
                children[parent].append(card_id)
    if rows != EXPECTED_CARD_ROWS:
        raise AuditError(f"card row count differs: {rows}")
    if set(frozen_endpoints) != set(frozen_endpoint_runs):
        raise AuditError("not all frozen endpoints resolve to a physical run")
    return cards, children, frozen_endpoint_runs


def audit_public_train(source_root: pathlib.Path, task: str) -> dict[str, Any]:
    spec = TASK_SPECS[task]
    public = source_root / task / "prepared" / "public"
    train = public / "train.csv"
    description = public / "description.md"
    require_hash(train, spec["train_sha256"], f"{task} train.csv")
    require_hash(description, spec["description_sha256"], f"{task} description.md")
    rows = 0
    target_counts: Counter[str] = Counter()
    with train.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        if len(header) != len(set(header)):
            raise AuditError(f"{task} has a duplicated CSV column")
        target_columns = list(spec["target_columns"])
        if spec["id_column"] not in header or not set(target_columns) <= set(header):
            raise AuditError(f"{task} id/target column is absent")
        for row in reader:
            if None in row or set(row) != set(header):
                raise AuditError(f"{task} malformed CSV row at index {rows}")
            row_id = row[spec["id_column"]]
            targets = [row[column] for column in target_columns]
            if not row_id or any(target == "" for target in targets):
                raise AuditError(f"{task} empty id/target at index {rows}")
            target_counts["\x1f".join(targets)] += 1
            rows += 1
    if rows < 1000 or len(target_counts) < 2:
        raise AuditError(f"{task} lacks enough rows/target strata for 80/10/10")
    if spec["split_stratification"] == "exact_target" and min(target_counts.values()) < 20:
        raise AuditError(f"{task} has an exact target stratum smaller than 20")
    return {
        "train_sha256": spec["train_sha256"],
        "description_sha256": spec["description_sha256"],
        "source_rows": rows,
        "source_columns": header,
        "target_strata": len(target_counts),
        "smallest_target_stratum": min(target_counts.values()),
        "split_stratification": spec["split_stratification"],
        "id_uniqueness_checked": False,
        "authorized_files_opened": ["train.csv", "description.md"],
        "official_test_opened": False,
        "official_sample_submission_opened": False,
        "private_answer_opened": False,
    }


def selection_key(task: str, run_id: str, parent: str) -> str:
    return hashlib.sha256(
        f"{SCHEMA}|{SELECTION_SEED}|{task}|{run_id}|{parent}".encode("utf-8")
    ).hexdigest()


def choose_anchors(
    cards: dict[str, dict[str, str | None]],
    children: dict[str, list[str]],
    whitelist: dict[str, set[tuple[str, str]]],
    held_runs: set[str],
    frozen_runs: set[str],
    prior_runs: set[str],
    frozen_endpoints: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    support: dict[str, Any] = {}
    selected: list[dict[str, Any]] = []
    selected_siblings: set[str] = set()
    selected_hashes: set[str] = set()
    for task in TASK_ORDER:
        eligible: list[tuple[str, str, list[str]]] = []
        rejection = Counter()
        for run_id, parent in whitelist[task]:
            child_ids = children.get(parent, [])
            if len(child_ids) != 2:
                rejection["not_exactly_two_structural_children"] += 1
                continue
            child_rows = [cards.get(card_id) for card_id in child_ids]
            if any(row is None for row in child_rows):
                rejection["child_outside_fixed_tasks"] += 1
                continue
            if {row["task"] for row in child_rows if row} != {task} or {
                row["run_id"] for row in child_rows if row
            } != {run_id}:
                rejection["task_or_run_mismatch"] += 1
                continue
            if run_id in held_runs or run_id in frozen_runs:
                rejection["held_or_frozen_run"] += 1
                continue
            if run_id in prior_runs:
                rejection["prior_intervention_run"] += 1
                continue
            code_hashes = {str(row["code_sha256"]) for row in child_rows if row}
            if len(code_hashes) != 2:
                rejection["duplicate_sibling_code"] += 1
                continue
            if set(child_ids) & frozen_endpoints:
                rejection["frozen_endpoint"] += 1
                continue
            eligible.append((run_id, parent, sorted(child_ids)))
        eligible.sort(key=lambda item: (selection_key(task, item[0], item[1]), item[0], item[1]))
        by_run: dict[str, tuple[str, str, list[str]]] = {}
        for item in eligible:
            by_run.setdefault(item[0], item)
        distinct_run_pool = sorted(
            by_run.values(), key=lambda item: (selection_key(task, item[0], item[1]), item[0], item[1])
        )
        if len(distinct_run_pool) < 4:
            raise AuditError(f"{task} has fewer than four eligible distinct physical runs")
        chosen = distinct_run_pool[:4]
        support[task] = {
            "decision_whitelist_parents": len(whitelist[task]),
            "eligible_parents": len(eligible),
            "eligible_physical_runs": len(by_run),
            "selected_parents": len(chosen),
            "selected_physical_runs": len({item[0] for item in chosen}),
            "rejection_counts": dict(sorted(rejection.items())),
        }
        for run_id, parent, child_ids in chosen:
            sibling_hashes = [str(cards[card_id]["code_sha256"]) for card_id in child_ids]
            selected_siblings.update(child_ids)
            selected_hashes.update(sibling_hashes)
            selected.append(
                {
                    "task": task,
                    "physical_run_id": run_id,
                    "parent_id": parent,
                    "sibling_ids": child_ids,
                    "sibling_code_sha256": sibling_hashes,
                    "selection_key": selection_key(task, run_id, parent),
                }
            )
    if len(selected) != 24 or len(selected_siblings) != 48 or len(selected_hashes) != 48:
        raise AuditError("selected E2-A anchors/siblings/code hashes are not globally unique")
    return support, selected


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise AuditError("output must not pre-exist")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def run(args: argparse.Namespace) -> dict[str, Any]:
    inputs = {
        "cards": pathlib.Path(args.cards).resolve(),
        "hold": pathlib.Path(args.hold).resolve(),
        "decision_train_b0": pathlib.Path(args.decision_train_b0).resolve(),
        "frozen_b0": pathlib.Path(args.frozen_b0).resolve(),
        "frozen_b1": pathlib.Path(args.frozen_b1).resolve(),
        "frozen_b2": pathlib.Path(args.frozen_b2).resolve(),
    }
    input_hashes = {
        role: require_hash(path, EXPECTED_SHA256[role], role) for role, path in inputs.items()
    }
    source_root = pathlib.Path(args.source_root).resolve()
    if not source_root.is_dir():
        raise AuditError("source root is absent")
    prior_paths = [pathlib.Path(value).resolve() for value in args.prior_selection]
    prior_runs, prior_receipts = load_prior_runs(prior_paths)
    held_runs = load_hold(inputs["hold"])
    frozen_paths = [inputs["frozen_b0"], inputs["frozen_b1"], inputs["frozen_b2"]]
    frozen_endpoints = load_frozen_endpoints(frozen_paths)
    whitelist = load_whitelist(inputs["decision_train_b0"])
    cards, children, frozen_endpoint_runs = load_cards(inputs["cards"], frozen_endpoints)
    frozen_runs = set(frozen_endpoint_runs.values())
    data_support = {task: audit_public_train(source_root, task) for task in TASK_ORDER}
    structural_support, selected = choose_anchors(
        cards, children, whitelist, held_runs, frozen_runs, prior_runs, frozen_endpoints
    )
    result = {
        "schema_version": SCHEMA,
        "status": "E2A_SIX_TASK_STRUCTURAL_AND_PUBLIC_TRAIN_SUPPORT_PASS",
        "scientific_outcomes_read": False,
        "official_test_opened": False,
        "official_sample_submission_opened": False,
        "private_answers_opened": False,
        "paid_rollouts_authorized": False,
        "selection_seed": SELECTION_SEED,
        "selection_rule": "sha256-rank-one-parent-per-distinct-run-v1",
        "tasks": list(TASK_ORDER),
        "task_count": len(TASK_ORDER),
        "anchors_per_task": 4,
        "selected_anchor_count": len(selected),
        "selected_sibling_count": sum(len(row["sibling_ids"]) for row in selected),
        "selected_physical_run_count": len({row["physical_run_id"] for row in selected}),
        "input_sha256": input_hashes,
        "prior_selection_receipts": prior_receipts,
        "prior_run_count": len(prior_runs),
        "frozen_endpoint_count": len(frozen_endpoints),
        "frozen_physical_run_count": len(frozen_runs),
        "data_support": data_support,
        "structural_support": structural_support,
        "selected_anchors": selected,
        "limitations": {
            "id_uniqueness_deferred_to_split_builder": True,
            "metric_implementation_not_yet_qualified": True,
            "worker_not_yet_qualified": True,
            "this_is_not_an_effect_result": True,
        },
    }
    if not math.isfinite(float(result["selected_anchor_count"])):
        raise AuditError("non-finite summary count")
    atomic_json(pathlib.Path(args.output).resolve(), result)
    print(canonical_json({key: result[key] for key in (
        "status", "task_count", "selected_anchor_count", "selected_sibling_count",
        "selected_physical_run_count", "prior_run_count",
    )}).decode("utf-8"))
    return result


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--hold", required=True)
    ap.add_argument("--decision-train-b0", required=True)
    ap.add_argument("--frozen-b0", required=True)
    ap.add_argument("--frozen-b1", required=True)
    ap.add_argument("--frozen-b2", required=True)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--prior-selection", action="append", default=[])
    ap.add_argument("--output", required=True)
    return ap


def main() -> int:
    try:
        run(parser().parse_args())
    except (AuditError, OSError, UnicodeError, csv.Error, json.JSONDecodeError) as exc:
        print(f"E2A_SUPPORT_AUDIT_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
