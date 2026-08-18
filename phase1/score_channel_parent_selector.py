"""Freeze prospective score-channel parents after the outcome-blind run gate passes.

This is a trusted-boundary tool: it opens label vaults only after the fixed 150-run
and task-balance gates pass.  Labels are used solely to decide whether ``graded`` is
finite.  The output contains identities and hashes, never label values, gaps, ranks,
or winners.  Candidate code is not opened here.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-parent-selection-v1"
ROW_SCHEMA = "score-channel-parent-selection-row-v1"
RUN_PROTOCOL = "score-channel-run-eligibility-registry-v1"
INTAKE_PROTOCOL = "prospective_drop_intake_v1"
MECHANISM_COMMIT = "4c964f8691b00af2f5ecb98f7a60dcd272bfb8cc"
SELECTION_SEED = 20260813
MIN_RUNS = 150
MAX_DOMINANT_SHARE = 0.25
MAX_PARENTS_PER_RUN = 2

RUN_KEYS = {
    "archive_name", "archive_sha256", "generation_started_at_utc",
    "journal_sha256", "run_id", "task",
}
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}
VAULT_KEYS = {
    "card_id", "task", "run_id", "graded", "y_norm", "eligible_by_start_time",
}
ROW_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}


class SelectionError(RuntimeError):
    """Fail-closed selection or integrity error."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_hash(value: Any, label: str, length: int = 64) -> str:
    if not isinstance(value, str) or len(value) != length or any(
        char not in "0123456789abcdef" for char in value.lower()
    ):
        raise SelectionError(f"invalid {label}")
    return value.lower()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SelectionError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise SelectionError(f"{label} must be an object")
    return value


def read_jsonl(path: Path, label: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SelectionError(f"cannot read {label}") from error
    if not lines and not allow_empty:
        raise SelectionError(f"{label} is empty")
    for line_number, line in enumerate(lines, 1):
        if not line:
            raise SelectionError(f"blank line in {label}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise SelectionError(f"invalid JSON in {label} line {line_number}") from error
        if not isinstance(row, dict):
            raise SelectionError(f"non-object in {label} line {line_number}")
        try:
            canonical(row)
        except (TypeError, ValueError) as error:
            raise SelectionError(f"non-finite or unsupported value in {label}") from error
        rows.append(row)
    return rows


def verify_run_registry(registry_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_path = registry_dir / "summary.json"
    runs_path = registry_dir / "eligible_runs.jsonl"
    summary = read_json(summary_path, "run registry summary")
    if summary.get("protocol") != RUN_PROTOCOL:
        raise SelectionError("unexpected run registry protocol")
    if summary.get("mechanism_commit") != MECHANISM_COMMIT:
        raise SelectionError("mechanism commit mismatch")
    thresholds = summary.get("thresholds") or {}
    if thresholds != {
        "min_runs": MIN_RUNS,
        "max_dominant_task_share": MAX_DOMINANT_SHARE,
    }:
        raise SelectionError("run registry thresholds differ from preregistration")
    gates = summary.get("gates") or {}
    if not (
        summary.get("status") == "RUN_GATE_PASS_PARENT_GATE_PENDING"
        and gates.get("enough_runs") is True
        and gates.get("task_balance") is True
        and gates.get("run_gate_pass") is True
        and gates.get("parent_gate_pending") is True
        and gates.get("replay_submission_authorized") is False
    ):
        raise SelectionError("run gate has not passed or replay was already authorized")
    expected_sha = require_hash(
        (summary.get("outputs") or {}).get("eligible_runs_sha256"),
        "eligible run registry SHA",
    )
    if sha256(runs_path) != expected_sha:
        raise SelectionError("eligible run registry SHA mismatch")
    rows = read_jsonl(runs_path, "eligible run registry")
    seen: set[str] = set()
    counts: collections.Counter[str] = collections.Counter()
    for row in rows:
        if set(row) != RUN_KEYS:
            raise SelectionError("eligible run row schema mismatch")
        run_id = row.get("run_id")
        task = row.get("task")
        journal = require_hash(row.get("journal_sha256"), "journal SHA")
        if not isinstance(run_id, str) or run_id != f"journal:{journal}":
            raise SelectionError("run ID does not bind journal SHA")
        if not isinstance(task, str) or not task or run_id in seen:
            raise SelectionError("duplicate run or invalid task")
        seen.add(run_id)
        counts[task] += 1
    declared = (summary.get("counts") or {}).get("eligible_post_mechanism_runs")
    if len(rows) != declared or len(rows) < MIN_RUNS:
        raise SelectionError("eligible run count does not satisfy the fixed gate")
    dominant = max(counts.values()) / len(rows)
    if dominant > MAX_DOMINANT_SHARE + 1e-15:
        raise SelectionError("recomputed task-balance gate failed")
    return rows, summary


def verify_intake_summary(path: Path, expected_sha: str, name: str) -> dict[str, Any]:
    if sha256(path) != require_hash(expected_sha, f"{name} summary SHA"):
        raise SelectionError(f"{name}: intake summary SHA mismatch")
    summary = read_json(path, f"{name} intake summary")
    if summary.get("protocol") != INTAKE_PROTOCOL or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE":
        raise SelectionError(f"{name}: intake is not complete")
    blindness = summary.get("blindness") or {}
    if blindness != {
        "labels_used_for_run_selection": False,
        "labels_used_for_endpoint_selection": False,
        "label_values_printed": False,
        "metrics_computed": [],
    }:
        raise SelectionError(f"{name}: intake blindness contract mismatch")
    security = summary.get("security") or {}
    for key, expected in {
        "env_members_read": False,
        "env_members_extracted": False,
        "live_event_journal_members_read": False,
        "journal_scanned_before_json": True,
        "credential_shaped_journals": 0,
        "raw_journals_written": False,
        "precutoff_endpoint_id_overlap": 0,
        "precutoff_code_sha256_overlap": 0,
    }.items():
        if security.get(key) != expected:
            raise SelectionError(f"{name}: unsafe intake flag {key}")
    return summary


def load_selection_inputs(
    intake_root: Path,
    run_rows: list[dict[str, Any]],
    registry_summary: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str]]:
    allowed_runs = {row["run_id"]: row["task"] for row in run_rows}
    run_intake: dict[str, str] = {}
    vault: dict[str, dict[str, Any]] = {}
    seen_vault_cards: set[str] = set()
    sibling_sets: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    pair_edges: dict[tuple[str, str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    intake_summary_shas: dict[str, str] = {}
    manifests = registry_summary.get("input_manifest")
    if not isinstance(manifests, list) or not manifests:
        raise SelectionError("run registry input manifest is empty")
    seen_intakes: set[str] = set()
    for item in manifests:
        if not isinstance(item, dict):
            raise SelectionError("run registry input manifest row is invalid")
        name = item.get("intake")
        if not isinstance(name, str) or not name or name in seen_intakes or Path(name).name != name:
            raise SelectionError("invalid or duplicate intake name")
        seen_intakes.add(name)
        intake_dir = intake_root / name
        summary_path = intake_dir / "summary.json"
        summary_sha = require_hash(item.get("summary_sha256"), f"{name} summary SHA")
        summary = verify_intake_summary(summary_path, summary_sha, name)
        intake_summary_shas[name] = summary_sha
        outputs = summary.get("outputs") or {}

        provenance_path = intake_dir / "source_provenance.json"
        if sha256(provenance_path) != require_hash(outputs.get("source_provenance_sha256"), f"{name} provenance SHA"):
            raise SelectionError(f"{name}: provenance SHA mismatch")
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SelectionError(f"{name}: invalid provenance") from error
        if not isinstance(provenance, list):
            raise SelectionError(f"{name}: provenance must be a list")
        for row in provenance:
            if not isinstance(row, dict):
                raise SelectionError(f"{name}: invalid provenance row")
            run_id = row.get("run_id")
            if run_id in allowed_runs:
                if row.get("task") != allowed_runs[run_id] or run_id in run_intake:
                    raise SelectionError("eligible run provenance mismatch or duplicate")
                run_intake[run_id] = name

        pairs_path = intake_dir / "eligible_structural_pairs.jsonl"
        if sha256(pairs_path) != require_hash(outputs.get("eligible_structural_pairs_sha256"), f"{name} pair SHA"):
            raise SelectionError(f"{name}: structural-pair SHA mismatch")
        for row in read_jsonl(pairs_path, f"{name} structural pairs", allow_empty=True):
            if set(row) != PAIR_KEYS:
                raise SelectionError(f"{name}: structural-pair schema mismatch")
            run_id, task, parent = row.get("run_id"), row.get("task"), row.get("parent")
            left, right = row.get("left"), row.get("right")
            if run_id not in allowed_runs:
                continue
            if task != allowed_runs[run_id] or any(not isinstance(value, str) or not value for value in (parent, left, right)):
                raise SelectionError(f"{name}: invalid structural pair identity")
            if not left < right or parent in {left, right}:
                raise SelectionError(f"{name}: noncanonical structural pair")
            key = (task, run_id, parent)
            edge = (left, right)
            if edge in pair_edges[key]:
                raise SelectionError(f"{name}: duplicate structural pair")
            pair_edges[key].add(edge)
            sibling_sets[key].update(edge)

        vault_path = intake_dir / "label_vault.jsonl"
        if sha256(vault_path) != require_hash(outputs.get("label_vault_sha256"), f"{name} vault SHA"):
            raise SelectionError(f"{name}: label-vault SHA mismatch")
        for row in read_jsonl(vault_path, f"{name} label vault", allow_empty=True):
            if set(row) != VAULT_KEYS:
                raise SelectionError(f"{name}: label-vault schema mismatch")
            run_id, task, card_id = row.get("run_id"), row.get("task"), row.get("card_id")
            if run_id not in allowed_runs:
                continue
            if task != allowed_runs[run_id] or not isinstance(card_id, str) or not card_id:
                raise SelectionError(f"{name}: invalid label-vault identity")
            eligible = row.get("eligible_by_start_time")
            if not isinstance(eligible, bool):
                raise SelectionError("label-vault eligibility flag is not boolean")
            if card_id in seen_vault_cards:
                raise SelectionError("duplicate card in label vault")
            seen_vault_cards.add(card_id)
            if not eligible:
                continue
            for label_key in ("graded", "y_norm"):
                value = row.get(label_key)
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
                ):
                    raise SelectionError(f"non-finite {label_key} in label vault")
            vault[card_id] = row

    if set(run_intake) != set(allowed_runs):
        raise SelectionError("not every eligible run maps to exactly one intake")
    for key, children in sibling_sets.items():
        expected = {(left, right) for index, left in enumerate(sorted(children)) for right in sorted(children)[index + 1:]}
        if pair_edges[key] != expected:
            raise SelectionError("structural pair set is not a complete sibling clique")
        task, run_id, _ = key
        for card_id in children:
            row = vault.get(card_id)
            if row is None or row["task"] != task or row["run_id"] != run_id:
                raise SelectionError("structural child is missing from the matching vault")
    return {
        "vault": vault,
        "sibling_sets": sibling_sets,
    }, run_intake, intake_summary_shas


def selection_key(run_id: str, parent_id: str) -> str:
    return sha256_text(f"{SELECTION_SEED}|{run_id}|{parent_id}")


def choose_rows(
    run_rows: list[dict[str, Any]],
    state: dict[str, Any],
    run_intake: dict[str, str],
) -> tuple[list[dict[str, Any]], int, int]:
    vault = state["vault"]
    sibling_sets = state["sibling_sets"]
    per_run: dict[str, list[tuple[str, str, list[str]]]] = collections.defaultdict(list)
    eligible_parent_count = 0
    for (task, run_id, parent_id), children in sibling_sets.items():
        finite_children = sorted(
            card_id
            for card_id in children
            if vault[card_id]["graded"] is not None
        )
        if len(finite_children) < 2:
            continue
        eligible_parent_count += 1
        per_run[run_id].append((selection_key(run_id, parent_id), parent_id, finite_children))

    selected: list[dict[str, Any]] = []
    runs_with_parents = 0
    for run in run_rows:
        run_id, task = run["run_id"], run["task"]
        candidates = sorted(per_run.get(run_id, []), key=lambda item: (item[0], item[1]))
        if candidates:
            runs_with_parents += 1
        for rank, (key_hash, parent_id, child_ids) in enumerate(candidates[:MAX_PARENTS_PER_RUN], 1):
            identity_hash = sha256_text(canonical(child_ids))
            selected.append({
                "schema_version": ROW_SCHEMA,
                "task": task,
                "run_id": run_id,
                "parent_id": parent_id,
                "source_intake": run_intake[run_id],
                "selection_rank_in_run": rank,
                "selection_key_sha256": key_hash,
                "candidate_card_ids": child_ids,
                "candidate_count": len(child_ids),
                "candidate_identity_sha256": identity_hash,
            })
    return selected, eligible_parent_count, runs_with_parents


def repository_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    value = result.stdout.strip()
    if result.returncode or len(value) != 40:
        raise SelectionError("cannot resolve source commit")
    return value


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            if set(row) != ROW_KEYS:
                raise SelectionError("internal selected-parent schema mismatch")
            handle.write(canonical(row) + "\n")


def produce(registry_dir: Path, intake_root: Path, repo: Path, out_dir: Path) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite parent selection output: {out_dir}")
    run_rows, registry_summary = verify_run_registry(registry_dir)
    state, run_intake, intake_summary_shas = load_selection_inputs(
        intake_root, run_rows, registry_summary
    )
    selected, eligible_parent_count, runs_with_parents = choose_rows(
        run_rows, state, run_intake
    )
    if not selected:
        raise SelectionError("no eligible finite-grade parent exists after the run gate")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp.", dir=out_dir.parent))
    try:
        rows_path = temporary / "selected_parents.jsonl"
        write_jsonl(rows_path, selected)
        registry_summary_path = registry_dir / "summary.json"
        registry_runs_path = registry_dir / "eligible_runs.jsonl"
        summary = {
            "protocol": PROTOCOL,
            "status": "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING",
            "selection": {
                "seed": SELECTION_SEED,
                "ordering": "sha256(seed|run_id|parent_id)",
                "max_parents_per_run": MAX_PARENTS_PER_RUN,
                "parent_eligibility": "at_least_two_finite_graded_structural_siblings",
                "ties_allowed": True,
            },
            "inputs": {
                "run_registry_summary_sha256": sha256(registry_summary_path),
                "eligible_runs_sha256": sha256(registry_runs_path),
                "intake_summary_sha256": dict(sorted(intake_summary_shas.items())),
            },
            "counts": {
                "eligible_runs": len(run_rows),
                "runs_with_eligible_parents": runs_with_parents,
                "runs_without_eligible_parents": len(run_rows) - runs_with_parents,
                "eligible_parents": eligible_parent_count,
                "selected_parents": len(selected),
                "selected_candidates": sum(row["candidate_count"] for row in selected),
                "tasks": len({row["task"] for row in run_rows}),
            },
            "gates": {
                "run_gate_pass": True,
                "task_balance_pass": True,
                "parent_gate_pass": True,
                "replay_manifest_pending": True,
                "replay_submission_authorized": False,
            },
            "blindness": {
                "trusted_label_vault_opened": True,
                "label_values_used_beyond_finiteness": False,
                "label_values_or_order_printed": False,
                "code_opened": False,
                "replay_outcomes_opened": False,
                "metrics_computed": [],
            },
            "outputs": {"selected_parents_sha256": sha256(rows_path)},
            "implementation": {
                "source_commit": repository_head(repo),
                "script_sha256": sha256(Path(__file__)),
                "python": platform.python_version(),
            },
        }
        (temporary / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        os.replace(temporary, out_dir)
    except Exception:
        for child in temporary.iterdir():
            child.unlink()
        temporary.rmdir()
        raise
    return summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-registry", required=True, type=Path)
    parser.add_argument("--intake-root", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        summary = produce(args.run_registry, args.intake_root, args.repo, args.out_dir)
    except (SelectionError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_PARENT_SELECTION_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical({
        "status": summary["status"],
        "eligible_runs": summary["counts"]["eligible_runs"],
        "selected_parents": summary["counts"]["selected_parents"],
        "selected_candidates": summary["counts"]["selected_candidates"],
        "replay_submission_authorized": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
