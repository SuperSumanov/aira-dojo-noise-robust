"""Independent verifier for the E2-A six-task support audit.

This module intentionally does not import the producer.  It independently reconstructs
the task data summaries, eligible exact-two pool, distinct-run selection, and all overlap
checks from the hash-locked sources.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import re
import tempfile
from collections import Counter, defaultdict
from typing import Any


PROTOCOL = "balanced-continuation-e2a-support-audit-v1"
SEED = 20260819
CARD_ROWS = 16012
INPUT_HASHES = {
    "cards": "6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75",
    "hold": "b31bd70a4483ac1ca207eae47ae39d7b00ced1b02c81583d0b0447fdd3d8489b",
    "decision_train_b0": "bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca",
    "frozen_b0": "2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8",
    "frozen_b1": "a56f6c7bd6aad141fdaa45f3f30f944062e8dea922eefc03e75bc8b415e7bc90",
    "frozen_b2": "79d4694d4cea5a81a04c9d463b5c6599a559bbf867f34205fa5715b054f10bc7",
}
SPECS = {
    "spaceship-titanic": (
        "PassengerId", ("Transported",), "exact_target",
        "d852203bbc5e603b92a7cfc0b46e23277c43d7a910b1db8b0ad58b7c6e3f2baa",
        "ee35380587404b263ef8b38d9a2fff4196563abb2e12bc086b02c9808b7f37cb",
    ),
    "tabular-playground-series-may-2022": (
        "id", ("target",), "exact_target",
        "f0940d6a4c3536752bdc3ba99251fc3020662ea43b28dfad520d810b3cde5514",
        "a64340a1c829f6e2c3ee8411cfa3089a4418571fee7186c91b5be2ef241bfcff",
    ),
    "spooky-author-identification": (
        "id", ("author",), "exact_target",
        "87a02befe9c415b976486e4a59b96da0cc907b8645efbb7052256307715ecdbf",
        "35d7de46d74377f997bdc7f5859e36ca3311fb4ae2e37ab63491a9d7c72661bd",
    ),
    "us-patent-phrase-to-phrase-matching": (
        "id", ("score",), "exact_target",
        "f5ba9a9b1b7fa3e025c65ece3fa2b92867c7436919c56d11e346d5344bcca205",
        "c2cc3682177d64f12e3c4d651389d7d6ef50852eaf97ccbcee55f62ebe957f53",
    ),
    "nomad2018-predict-transparent-conductors": (
        "id", ("formation_energy_ev_natom", "bandgap_energy_ev"), "formation_energy_rank_decile",
        "6a85d60056f8737c6575c8a7c0575fee6501916cf1dbd6199b0113849352546c",
        "d70aa4ad5bd3c2d460b750ae26b7f3572271dcab50499f4c8de66f7d6c45e1ad",
    ),
    "learning-agency-lab-automated-essay-scoring-2": (
        "essay_id", ("score",), "exact_target",
        "ce6b0bd2c7d790a64ad3d2a8e15e3563d90e881c787638caa93504445caa65d0",
        "c11986179a042c909be5ab23275650f66160d7916ad229e133ca3f2af493cbed",
    ),
}
TASKS = tuple(SPECS)
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerifyError(RuntimeError):
    pass


def canon(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: pathlib.Path) -> Any:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    return json.loads(raw)


def require_hash(path: pathlib.Path, expected: str) -> None:
    if not path.is_file() or path.is_symlink() or sha(path) != expected:
        raise VerifyError(f"source hash/path differs: {path}")


def rank_key(task: str, run: str, parent: str) -> str:
    raw = f"{PROTOCOL}|{SEED}|{task}|{run}|{parent}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def frozen_ids(paths: list[pathlib.Path]) -> set[str]:
    result: set[str] = set()
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle, 1):
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise VerifyError(f"non-object frozen row: {path.name}:{index}")
                for field in ("better", "worse"):
                    endpoint = row.get(field)
                    if not isinstance(endpoint, str) or not endpoint:
                        raise VerifyError("invalid frozen endpoint")
                    result.add(endpoint)
    return result


def decision_pool(path: pathlib.Path) -> dict[str, set[tuple[str, str]]]:
    pool = {task: set() for task in TASKS}
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, 1):
            row = json.loads(line)
            if not isinstance(row, dict):
                raise VerifyError(f"non-object decision row: {index}")
            task = row.get("task")
            if task not in pool:
                continue
            if row.get("budget") == 0 and row.get("intask_split") == "train" and row.get("set_size") == 2:
                run, parent = row.get("run_id"), row.get("parent")
                if not isinstance(run, str) or not run or not isinstance(parent, str) or not parent:
                    raise VerifyError("invalid decision identity")
                pool[task].add((run, parent))
    return pool


def prior_runs(paths: list[pathlib.Path]) -> tuple[set[str], list[dict[str, str]]]:
    runs: set[str] = set()
    receipts = []
    for path in paths:
        rows = load_json(path)
        if not isinstance(rows, list) or not rows:
            raise VerifyError("invalid prior-selection receipt")
        for row in rows:
            run = row.get("source_run_id") if isinstance(row, dict) else None
            if not isinstance(run, str) or not run:
                raise VerifyError("invalid prior-selection run")
            runs.add(run)
        receipts.append({"rows": str(len(rows)), "sha256": sha(path)})
    return runs, receipts


def reconstruct_cards(
    path: pathlib.Path, frozen: set[str]
) -> tuple[dict[str, dict[str, str | None]], dict[str, list[str]], dict[str, str]]:
    target: dict[str, dict[str, str | None]] = {}
    children: dict[str, list[str]] = defaultdict(list)
    frozen_run: dict[str, str] = {}
    seen: set[str] = set()
    row_count = 0
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, 1):
            row_count += 1
            row = json.loads(line)
            card_id = row.get("id") if isinstance(row, dict) else None
            task_obj = row.get("task") if isinstance(row, dict) else None
            run = row.get("run_id") if isinstance(row, dict) else None
            if (
                not isinstance(card_id, str) or not card_id or card_id in seen
                or not isinstance(task_obj, dict) or not isinstance(task_obj.get("name"), str)
                or not isinstance(run, str) or not run
            ):
                raise VerifyError(f"card schema/identity differs: {index}")
            seen.add(card_id)
            if card_id in frozen:
                frozen_run[card_id] = run
            task = task_obj["name"]
            if task not in SPECS:
                continue
            lineage = row.get("lineage") or {}
            parent = lineage.get("parent_id") if isinstance(lineage, dict) else None
            code = row.get("code")
            if not isinstance(code, str) or not code or CREDENTIAL.search(code.encode("utf-8")):
                raise VerifyError(f"invalid target card code: {index}")
            target[card_id] = {
                "task": task, "run": run,
                "parent": parent if isinstance(parent, str) and parent else None,
                "code_sha": hashlib.sha256(code.encode("utf-8")).hexdigest(),
            }
            if isinstance(parent, str) and parent:
                children[parent].append(card_id)
    if row_count != CARD_ROWS or set(frozen_run) != frozen:
        raise VerifyError("card count or frozen endpoint resolution differs")
    return target, children, frozen_run


def reconstruct_selection(
    cards: dict[str, dict[str, str | None]],
    children: dict[str, list[str]],
    pool: dict[str, set[tuple[str, str]]],
    hold: set[str],
    frozen_runs_set: set[str],
    old_runs: set[str],
    frozen: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    support: dict[str, Any] = {}
    selected: list[dict[str, Any]] = []
    for task in TASKS:
        candidates = []
        rejected = Counter()
        for run, parent in pool[task]:
            child_ids = children.get(parent, [])
            if len(child_ids) != 2:
                rejected["not_exactly_two_structural_children"] += 1
                continue
            rows = [cards.get(card_id) for card_id in child_ids]
            if any(row is None for row in rows):
                rejected["child_outside_fixed_tasks"] += 1
                continue
            if {row["task"] for row in rows if row} != {task} or {row["run"] for row in rows if row} != {run}:
                rejected["task_or_run_mismatch"] += 1
                continue
            if run in hold or run in frozen_runs_set:
                rejected["held_or_frozen_run"] += 1
                continue
            if run in old_runs:
                rejected["prior_intervention_run"] += 1
                continue
            hashes = {str(row["code_sha"]) for row in rows if row}
            if len(hashes) != 2:
                rejected["duplicate_sibling_code"] += 1
                continue
            if set(child_ids) & frozen:
                rejected["frozen_endpoint"] += 1
                continue
            candidates.append((run, parent, sorted(child_ids)))
        candidates.sort(key=lambda item: (rank_key(task, item[0], item[1]), item[0], item[1]))
        one_per_run: dict[str, tuple[str, str, list[str]]] = {}
        for item in candidates:
            one_per_run.setdefault(item[0], item)
        ranked = sorted(
            one_per_run.values(),
            key=lambda item: (rank_key(task, item[0], item[1]), item[0], item[1]),
        )
        if len(ranked) < 4:
            raise VerifyError(f"insufficient distinct-run support for {task}")
        chosen = ranked[:4]
        support[task] = {
            "decision_whitelist_parents": len(pool[task]),
            "eligible_parents": len(candidates),
            "eligible_physical_runs": len(one_per_run),
            "selected_parents": 4,
            "selected_physical_runs": len({item[0] for item in chosen}),
            "rejection_counts": dict(sorted(rejected.items())),
        }
        for run, parent, child_ids in chosen:
            selected.append({
                "task": task,
                "physical_run_id": run,
                "parent_id": parent,
                "sibling_ids": child_ids,
                "sibling_code_sha256": [str(cards[item]["code_sha"]) for item in child_ids],
                "selection_key": rank_key(task, run, parent),
            })
    return support, selected


def data_summary(root: pathlib.Path, task: str, recorded: dict[str, Any]) -> None:
    ident, targets, stratification, train_sha, description_sha = SPECS[task]
    public = root / task / "prepared" / "public"
    train, description = public / "train.csv", public / "description.md"
    require_hash(train, train_sha)
    require_hash(description, description_sha)
    counts: Counter[str] = Counter()
    rows = 0
    with train.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        if len(header) != len(set(header)) or ident not in header or not set(targets) <= set(header):
            raise VerifyError(f"source header differs: {task}")
        for row in reader:
            values = [row[column] for column in targets]
            if not row[ident] or any(value == "" for value in values):
                raise VerifyError(f"empty source identity/target: {task}:{rows}")
            counts["\x1f".join(values)] += 1
            rows += 1
    expected_subset = {
        "source_rows": rows,
        "source_columns": header,
        "target_strata": len(counts),
        "smallest_target_stratum": min(counts.values()),
        "split_stratification": stratification,
        "train_sha256": train_sha,
        "description_sha256": description_sha,
        "authorized_files_opened": ["train.csv", "description.md"],
        "official_test_opened": False,
        "official_sample_submission_opened": False,
        "private_answer_opened": False,
        "id_uniqueness_checked": False,
    }
    if recorded != expected_subset:
        raise VerifyError(f"recorded public-train summary differs: {task}")


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise VerifyError("verification receipt must not pre-exist")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canon(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "cards": pathlib.Path(args.cards).resolve(),
        "hold": pathlib.Path(args.hold).resolve(),
        "decision_train_b0": pathlib.Path(args.decision_train_b0).resolve(),
        "frozen_b0": pathlib.Path(args.frozen_b0).resolve(),
        "frozen_b1": pathlib.Path(args.frozen_b1).resolve(),
        "frozen_b2": pathlib.Path(args.frozen_b2).resolve(),
    }
    for role, path in paths.items():
        require_hash(path, INPUT_HASHES[role])
    result_path = pathlib.Path(args.result).resolve()
    result = load_json(result_path)
    if (
        not isinstance(result, dict)
        or result.get("schema_version") != PROTOCOL
        or result.get("status") != "E2A_SIX_TASK_STRUCTURAL_AND_PUBLIC_TRAIN_SUPPORT_PASS"
        or result.get("scientific_outcomes_read") is not False
        or result.get("official_test_opened") is not False
        or result.get("official_sample_submission_opened") is not False
        or result.get("private_answers_opened") is not False
        or result.get("paid_rollouts_authorized") is not False
        or result.get("tasks") != list(TASKS)
    ):
        raise VerifyError("support result top-level contract differs")
    source_root = pathlib.Path(args.source_root).resolve()
    for task in TASKS:
        data_summary(source_root, task, result["data_support"][task])
    hold_value = load_json(paths["hold"])
    hold = set(hold_value["hold"])
    frozen_paths = [paths["frozen_b0"], paths["frozen_b1"], paths["frozen_b2"]]
    frozen = frozen_ids(frozen_paths)
    old_runs, old_receipts = prior_runs(
        [pathlib.Path(value).resolve() for value in args.prior_selection]
    )
    cards, children, frozen_run = reconstruct_cards(paths["cards"], frozen)
    support, selected = reconstruct_selection(
        cards, children, decision_pool(paths["decision_train_b0"]), hold,
        set(frozen_run.values()), old_runs, frozen,
    )
    if result.get("structural_support") != support or result.get("selected_anchors") != selected:
        raise VerifyError("independently reconstructed support/selection differs")
    if (
        result.get("input_sha256") != INPUT_HASHES
        or result.get("prior_selection_receipts") != old_receipts
        or result.get("prior_run_count") != len(old_runs)
        or result.get("frozen_endpoint_count") != len(frozen)
        or result.get("frozen_physical_run_count") != len(set(frozen_run.values()))
        or result.get("task_count") != 6
        or result.get("anchors_per_task") != 4
        or result.get("selected_anchor_count") != 24
        or result.get("selected_sibling_count") != 48
        or result.get("selected_physical_run_count") != 24
    ):
        raise VerifyError("support aggregate differs")
    selected_ids = [item for row in selected for item in row["sibling_ids"]]
    selected_hashes = [item for row in selected for item in row["sibling_code_sha256"]]
    if len(set(selected_ids)) != 48 or len(set(selected_hashes)) != 48:
        raise VerifyError("selected sibling identity/code hashes are not unique")
    receipt = {
        "schema_version": "balanced-continuation-e2a-support-verification-v1",
        "status": "VERIFIED_E2A_SIX_TASK_DISTINCT_RUN_SUPPORT",
        "producer_imported": False,
        "result_sha256": sha(result_path),
        "tasks": list(TASKS),
        "selected_anchors": 24,
        "selected_siblings": 48,
        "selected_physical_runs": 24,
        "frozen_endpoint_overlap": 0,
        "frozen_physical_run_overlap": 0,
        "prior_physical_run_overlap": 0,
        "scientific_outcomes_read": False,
        "official_test_opened": False,
        "official_sample_submission_opened": False,
        "private_answers_opened": False,
    }
    atomic_json(pathlib.Path(args.receipt).resolve(), receipt)
    print(canon(receipt).decode("utf-8"))
    return receipt


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--result", required=True)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--hold", required=True)
    ap.add_argument("--decision-train-b0", required=True)
    ap.add_argument("--frozen-b0", required=True)
    ap.add_argument("--frozen-b1", required=True)
    ap.add_argument("--frozen-b2", required=True)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--prior-selection", action="append", default=[])
    ap.add_argument("--receipt", required=True)
    return ap


def main() -> int:
    try:
        verify(parser().parse_args())
    except (VerifyError, OSError, UnicodeError, csv.Error, json.JSONDecodeError, KeyError) as exc:
        print(f"E2A_SUPPORT_VERIFY_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
