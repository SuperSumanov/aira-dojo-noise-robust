"""Independently rebuild and verify score-channel parent selection.

This verifier deliberately does not import ``score_channel_parent_selector``.  It
opens the trusted label vault, uses only grade finiteness, independently reconstructs
the SHA-256 lottery, and emits a label-free receipt.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


RUN_PROTOCOL = "score-channel-run-eligibility-registry-v1"
SELECTION_PROTOCOL = "score-channel-parent-selection-v1"
ROW_SCHEMA = "score-channel-parent-selection-row-v1"
MECHANISM_COMMIT = "4c964f8691b00af2f5ecb98f7a60dcd272bfb8cc"
SEED = 20260813
MIN_RUNS = 150
MAX_SHARE = 0.25
MAX_PARENTS = 2
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}
VAULT_KEYS = {"card_id", "task", "run_id", "graded", "y_norm", "eligible_by_start_time"}
ROW_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}


class VerificationError(RuntimeError):
    """Fail-closed independent verification error."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_sha(value: Any, label: str, length: int = 64) -> str:
    if not isinstance(value, str) or len(value) != length or any(
        character not in "0123456789abcdef" for character in value.lower()
    ):
        raise VerificationError(f"invalid {label}")
    return value.lower()


def object_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def lines_file(path: Path, label: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise VerificationError(f"cannot read {label}") from error
    if (not lines and not allow_empty) or any(not line for line in lines):
        raise VerificationError(f"{label} is empty or contains a blank line")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            canonical(row)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise VerificationError(f"invalid {label} line {number}") from error
        if not isinstance(row, dict):
            raise VerificationError(f"non-object {label} line {number}")
        rows.append(row)
    return rows


def registry_state(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_path, rows_path = root / "summary.json", root / "eligible_runs.jsonl"
    summary = object_file(summary_path, "run registry summary")
    gates = summary.get("gates") or {}
    if (
        summary.get("protocol") != RUN_PROTOCOL
        or summary.get("status") != "RUN_GATE_PASS_PARENT_GATE_PENDING"
        or summary.get("mechanism_commit") != MECHANISM_COMMIT
        or summary.get("thresholds") != {"min_runs": MIN_RUNS, "max_dominant_task_share": MAX_SHARE}
        or gates != {
            "enough_runs": True,
            "task_balance": True,
            "run_gate_pass": True,
            "parent_gate_pending": True,
            "replay_submission_authorized": False,
        }
    ):
        raise VerificationError("run registry gate contract mismatch")
    expected = valid_sha((summary.get("outputs") or {}).get("eligible_runs_sha256"), "run registry SHA")
    if digest(rows_path) != expected:
        raise VerificationError("run registry SHA mismatch")
    rows = lines_file(rows_path, "eligible run registry")
    ids: set[str] = set()
    tasks: collections.Counter[str] = collections.Counter()
    for row in rows:
        run_id, task, journal = row.get("run_id"), row.get("task"), row.get("journal_sha256")
        journal = valid_sha(journal, "journal SHA")
        if run_id != f"journal:{journal}" or not isinstance(task, str) or not task or run_id in ids:
            raise VerificationError("invalid or duplicate run row")
        ids.add(run_id)
        tasks[task] += 1
    if len(rows) < MIN_RUNS or len(rows) != (summary.get("counts") or {}).get("eligible_post_mechanism_runs"):
        raise VerificationError("run count gate mismatch")
    if max(tasks.values()) / len(rows) > MAX_SHARE + 1e-15:
        raise VerificationError("task balance fails independent reconstruction")
    return rows, summary


def independent_expected_rows(
    intake_root: Path,
    runs: list[dict[str, Any]],
    registry_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str], int, int]:
    run_task = {row["run_id"]: row["task"] for row in runs}
    run_intake: dict[str, str] = {}
    summary_shas: dict[str, str] = {}
    labels: dict[str, dict[str, Any]] = {}
    seen_vault_cards: set[str] = set()
    children: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    edges: dict[tuple[str, str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    manifests = registry_summary.get("input_manifest")
    if not isinstance(manifests, list) or not manifests:
        raise VerificationError("input manifest is empty")
    seen_names: set[str] = set()
    for manifest in manifests:
        if not isinstance(manifest, dict):
            raise VerificationError("invalid input manifest row")
        name = manifest.get("intake")
        if not isinstance(name, str) or not name or Path(name).name != name or name in seen_names:
            raise VerificationError("invalid or duplicate intake name")
        seen_names.add(name)
        root = intake_root / name
        summary_path = root / "summary.json"
        expected_summary_sha = valid_sha(manifest.get("summary_sha256"), "intake summary SHA")
        if digest(summary_path) != expected_summary_sha:
            raise VerificationError("intake summary SHA mismatch")
        summary_shas[name] = expected_summary_sha
        summary = object_file(summary_path, "intake summary")
        if summary.get("protocol") != "prospective_drop_intake_v1" or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE":
            raise VerificationError("intake completion contract mismatch")
        if summary.get("blindness") != {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
            "label_values_printed": False,
            "metrics_computed": [],
        }:
            raise VerificationError("intake blindness mismatch")
        outputs = summary.get("outputs") or {}

        provenance_path = root / "source_provenance.json"
        if digest(provenance_path) != valid_sha(outputs.get("source_provenance_sha256"), "provenance SHA"):
            raise VerificationError("provenance SHA mismatch")
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise VerificationError("invalid provenance") from error
        if not isinstance(provenance, list):
            raise VerificationError("provenance is not a list")
        for row in provenance:
            if not isinstance(row, dict):
                raise VerificationError("invalid provenance row")
            run_id = row.get("run_id")
            if run_id in run_task:
                if row.get("task") != run_task[run_id] or run_id in run_intake:
                    raise VerificationError("eligible-run provenance collision")
                run_intake[run_id] = name

        pair_path = root / "eligible_structural_pairs.jsonl"
        if digest(pair_path) != valid_sha(outputs.get("eligible_structural_pairs_sha256"), "pair SHA"):
            raise VerificationError("structural-pair SHA mismatch")
        for row in lines_file(pair_path, "structural pairs", allow_empty=True):
            if set(row) != PAIR_KEYS:
                raise VerificationError("structural-pair schema mismatch")
            task, run_id, parent, left, right = (
                row.get("task"), row.get("run_id"), row.get("parent"), row.get("left"), row.get("right")
            )
            if run_id not in run_task:
                continue
            if task != run_task[run_id] or any(not isinstance(value, str) or not value for value in (parent, left, right)):
                raise VerificationError("invalid structural-pair identity")
            if not left < right or parent in {left, right}:
                raise VerificationError("noncanonical structural pair")
            key, edge = (task, run_id, parent), (left, right)
            if edge in edges[key]:
                raise VerificationError("duplicate structural pair")
            edges[key].add(edge)
            children[key].update(edge)

        vault_path = root / "label_vault.jsonl"
        if digest(vault_path) != valid_sha(outputs.get("label_vault_sha256"), "vault SHA"):
            raise VerificationError("label-vault SHA mismatch")
        for row in lines_file(vault_path, "label vault", allow_empty=True):
            if set(row) != VAULT_KEYS:
                raise VerificationError("label-vault schema mismatch")
            run_id, task, card = row.get("run_id"), row.get("task"), row.get("card_id")
            if run_id not in run_task:
                continue
            if task != run_task[run_id] or not isinstance(card, str) or not card:
                raise VerificationError("invalid vault identity")
            eligible = row.get("eligible_by_start_time")
            if not isinstance(eligible, bool):
                raise VerificationError("vault eligibility flag is not boolean")
            if card in seen_vault_cards:
                raise VerificationError("duplicate card in label vault")
            seen_vault_cards.add(card)
            if not eligible:
                continue
            for key in ("graded", "y_norm"):
                value = row.get(key)
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
                ):
                    raise VerificationError(f"non-finite {key}")
            labels[card] = row

    if set(run_intake) != set(run_task):
        raise VerificationError("not all eligible runs have unique intake provenance")
    eligible: dict[str, list[tuple[str, str, list[str]]]] = collections.defaultdict(list)
    eligible_count = 0
    for (task, run_id, parent), members in children.items():
        ordered = sorted(members)
        complete = {(left, right) for index, left in enumerate(ordered) for right in ordered[index + 1:]}
        if edges[(task, run_id, parent)] != complete:
            raise VerificationError("sibling pairs are not a complete clique")
        for card in ordered:
            if card not in labels or labels[card]["task"] != task or labels[card]["run_id"] != run_id:
                raise VerificationError("sibling/vault identity mismatch")
        finite = [card for card in ordered if labels[card]["graded"] is not None]
        if len(finite) >= 2:
            eligible_count += 1
            key = text_digest(f"{SEED}|{run_id}|{parent}")
            eligible[run_id].append((key, parent, finite))

    expected_rows: list[dict[str, Any]] = []
    runs_with = 0
    for run in runs:
        run_id, task = run["run_id"], run["task"]
        options = sorted(eligible.get(run_id, []), key=lambda item: (item[0], item[1]))
        runs_with += bool(options)
        for rank, (key, parent, finite) in enumerate(options[:MAX_PARENTS], 1):
            expected_rows.append({
                "schema_version": ROW_SCHEMA,
                "task": task,
                "run_id": run_id,
                "parent_id": parent,
                "source_intake": run_intake[run_id],
                "selection_rank_in_run": rank,
                "selection_key_sha256": key,
                "candidate_card_ids": finite,
                "candidate_count": len(finite),
                "candidate_identity_sha256": text_digest(canonical(finite)),
            })
    return expected_rows, summary_shas, eligible_count, runs_with


def verify(
    registry_dir: Path,
    intake_root: Path,
    selection_dir: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite verifier receipt: {receipt_path}")
    runs, registry_summary = registry_state(registry_dir)
    expected, intake_shas, eligible_count, runs_with = independent_expected_rows(
        intake_root, runs, registry_summary
    )
    summary_path = selection_dir / "summary.json"
    rows_path = selection_dir / "selected_parents.jsonl"
    summary = object_file(summary_path, "selection summary")
    if summary.get("protocol") != SELECTION_PROTOCOL or summary.get("status") != "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING":
        raise VerificationError("selection status mismatch")
    if summary.get("selection") != {
        "seed": SEED,
        "ordering": "sha256(seed|run_id|parent_id)",
        "max_parents_per_run": MAX_PARENTS,
        "parent_eligibility": "at_least_two_finite_graded_structural_siblings",
        "ties_allowed": True,
    }:
        raise VerificationError("selection policy mismatch")
    expected_inputs = {
        "run_registry_summary_sha256": digest(registry_dir / "summary.json"),
        "eligible_runs_sha256": digest(registry_dir / "eligible_runs.jsonl"),
        "intake_summary_sha256": dict(sorted(intake_shas.items())),
    }
    if summary.get("inputs") != expected_inputs:
        raise VerificationError("selection input binding mismatch")
    if digest(rows_path) != valid_sha((summary.get("outputs") or {}).get("selected_parents_sha256"), "selected rows SHA"):
        raise VerificationError("selected-parent SHA mismatch")
    actual = lines_file(rows_path, "selected parents")
    for row in actual:
        if set(row) != ROW_KEYS:
            raise VerificationError("selected-parent schema mismatch")
        lowered = {key.lower() for key in row}
        if any(fragment in key for key in lowered for fragment in ("graded", "y_norm", "gap", "winner", "stdout", "sub_score", "code")):
            raise VerificationError("selected-parent row contains outcome-bearing key")
    if actual != expected:
        raise VerificationError("selected-parent rows differ from independent reconstruction")
    expected_counts = {
        "eligible_runs": len(runs),
        "runs_with_eligible_parents": runs_with,
        "runs_without_eligible_parents": len(runs) - runs_with,
        "eligible_parents": eligible_count,
        "selected_parents": len(expected),
        "selected_candidates": sum(row["candidate_count"] for row in expected),
        "tasks": len({row["task"] for row in runs}),
    }
    if summary.get("counts") != expected_counts:
        raise VerificationError("selection counts differ from reconstruction")
    if summary.get("gates") != {
        "run_gate_pass": True,
        "task_balance_pass": True,
        "parent_gate_pass": True,
        "replay_manifest_pending": True,
        "replay_submission_authorized": False,
    }:
        raise VerificationError("selection gate flags mismatch")
    receipt = {
        "protocol": "score-channel-parent-selection-independent-verifier-v1",
        "status": "PASS_PARENT_SELECTION_REPLAY_APPROVAL_PENDING",
        "implementation_independent_of_producer": True,
        "producer_module_imported": False,
        "run_gate_reconstructed": True,
        "task_balance_reconstructed": True,
        "finite_sibling_eligibility_reconstructed": True,
        "sha256_lottery_reconstructed": True,
        "selected_parent_rows_exact": True,
        "eligible_runs": len(runs),
        "eligible_parents": eligible_count,
        "selected_parents": len(expected),
        "selected_candidates": sum(row["candidate_count"] for row in expected),
        "trusted_label_vault_opened": True,
        "label_values_printed": False,
        "label_values_used_beyond_finiteness": False,
        "code_opened": False,
        "replay_outcomes_opened": False,
        "selection_summary_sha256": digest(summary_path),
        "selected_parents_sha256": digest(rows_path),
        "replay_submission_authorized": False,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_name(receipt_path.name + f".tmp-{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"temporary verifier receipt exists: {temporary}")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    os.replace(temporary, receipt_path)
    return receipt


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-registry", required=True, type=Path)
    parser.add_argument("--intake-root", required=True, type=Path)
    parser.add_argument("--selection-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        receipt = verify(args.run_registry, args.intake_root, args.selection_dir, args.receipt)
    except (VerificationError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_PARENT_VERIFY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
