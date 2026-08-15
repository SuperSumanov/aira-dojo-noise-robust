"""Materialize the frozen score-channel replay manifest without opening labels.

The trusted parent selector emits only identities.  This separate process joins those
identities to credential-screened blind code views, assigns every physical run to one
of four deterministic shards, and keeps replay authorization false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-replay-manifest-v1"
ROW_SCHEMA = "score-channel-replay-candidate-v1"
SELECTION_PROTOCOL = "score-channel-parent-selection-v1"
SELECTION_ROW_SCHEMA = "score-channel-parent-selection-row-v1"
CAP_SECONDS = 120
SHARDS = 4
SELECTION_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"parent", "depth", "step", "n_siblings", "op"}
REPLAY_KEYS = {
    "schema_version", "card_id", "competition", "task", "run_id", "parent",
    "code", "code_sha256", "source_intake", "selection_rank_in_run",
    "shard_id", "cap_seconds",
}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)


class ManifestError(RuntimeError):
    """Fail-closed replay-manifest error."""


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
        raise ManifestError(f"invalid {label}")
    return value.lower()


def object_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise ManifestError(f"{label} is not an object")
    return value


def rows_file(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ManifestError(f"cannot read {label}") from error
    if not lines or any(not line for line in lines):
        raise ManifestError(f"{label} is empty or contains a blank line")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
            canonical(value)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise ManifestError(f"invalid {label} line {number}") from error
        if not isinstance(value, dict):
            raise ManifestError(f"non-object {label} line {number}")
        rows.append(value)
    return rows


def load_selection(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_path, rows_path = root / "summary.json", root / "selected_parents.jsonl"
    summary = object_file(summary_path, "parent-selection summary")
    if summary.get("protocol") != SELECTION_PROTOCOL or summary.get("status") != "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING":
        raise ManifestError("parent selection has not passed")
    if summary.get("gates") != {
        "run_gate_pass": True,
        "task_balance_pass": True,
        "parent_gate_pass": True,
        "replay_manifest_pending": True,
        "replay_submission_authorized": False,
    }:
        raise ManifestError("parent-selection gate contract mismatch")
    expected_sha = valid_sha((summary.get("outputs") or {}).get("selected_parents_sha256"), "selected-parent SHA")
    if digest(rows_path) != expected_sha:
        raise ManifestError("selected-parent SHA mismatch")
    rows = rows_file(rows_path, "selected parents")
    seen_parents: set[tuple[str, str]] = set()
    seen_cards: set[str] = set()
    for row in rows:
        if set(row) != SELECTION_KEYS or row.get("schema_version") != SELECTION_ROW_SCHEMA:
            raise ManifestError("selected-parent row schema mismatch")
        task, run_id, parent, intake = (
            row.get("task"), row.get("run_id"), row.get("parent_id"), row.get("source_intake")
        )
        if any(not isinstance(value, str) or not value for value in (task, run_id, parent, intake)) or Path(intake).name != intake:
            raise ManifestError("invalid selected-parent identity")
        key = (run_id, parent)
        if key in seen_parents:
            raise ManifestError("duplicate selected parent")
        seen_parents.add(key)
        cards = row.get("candidate_card_ids")
        if not isinstance(cards, list) or cards != sorted(set(cards)) or len(cards) < 2 or row.get("candidate_count") != len(cards):
            raise ManifestError("invalid selected candidate set")
        if text_digest(canonical(cards)) != valid_sha(row.get("candidate_identity_sha256"), "candidate identity SHA"):
            raise ManifestError("candidate identity SHA mismatch")
        if any(not isinstance(card, str) or not card or card in seen_cards for card in cards):
            raise ManifestError("invalid or duplicate selected candidate")
        seen_cards.update(cards)
    counts = summary.get("counts") or {}
    if counts.get("selected_parents") != len(rows) or counts.get("selected_candidates") != len(seen_cards):
        raise ManifestError("parent-selection count mismatch")
    return rows, summary


def load_selected_code(
    intake_root: Path,
    selected: list[dict[str, Any]],
    selection_summary: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    wanted: dict[str, dict[str, str]] = {}
    per_intake: dict[str, set[str]] = {}
    for row in selected:
        intake = row["source_intake"]
        per_intake.setdefault(intake, set()).update(row["candidate_card_ids"])
        for card in row["candidate_card_ids"]:
            wanted[card] = {
                "task": row["task"], "run_id": row["run_id"], "parent": row["parent_id"],
                "source_intake": intake,
            }
    declared_shas = (selection_summary.get("inputs") or {}).get("intake_summary_sha256")
    if not isinstance(declared_shas, dict):
        raise ManifestError("selection does not bind intake summaries")
    found: dict[str, dict[str, Any]] = {}
    for intake, card_ids in sorted(per_intake.items()):
        if intake not in declared_shas:
            raise ManifestError("selected intake is absent from selection input binding")
        root = intake_root / intake
        summary_path = root / "summary.json"
        if digest(summary_path) != valid_sha(declared_shas[intake], "intake summary SHA"):
            raise ManifestError("intake summary changed after parent selection")
        summary = object_file(summary_path, "intake summary")
        if summary.get("protocol") != "prospective_drop_intake_v1" or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE":
            raise ManifestError("intake completion contract mismatch")
        blind_path = root / "eligible_blind_manifest.jsonl"
        expected_sha = valid_sha((summary.get("outputs") or {}).get("eligible_blind_manifest_sha256"), "blind-manifest SHA")
        if digest(blind_path) != expected_sha:
            raise ManifestError("eligible blind manifest SHA mismatch")
        for row in rows_file(blind_path, "eligible blind manifest"):
            card = row.get("card_id")
            if card not in card_ids:
                continue
            if set(row) != BLIND_KEYS or not isinstance(row.get("lineage"), dict) or set(row["lineage"]) != LINEAGE_KEYS:
                raise ManifestError("blind code-view schema mismatch")
            identity = wanted[card]
            if (
                row.get("task") != identity["task"]
                or row.get("run_id") != identity["run_id"]
                or row["lineage"].get("parent") != identity["parent"]
                or card in found
            ):
                raise ManifestError("blind code identity mismatch or duplicate")
            code = row.get("code")
            if not isinstance(code, str) or not code:
                raise ManifestError("selected candidate code is empty")
            code_sha = valid_sha(row.get("code_sha256"), "code SHA")
            if text_digest(code) != code_sha:
                raise ManifestError("selected candidate code SHA mismatch")
            if CREDENTIAL.search(code.encode("utf-8")):
                raise ManifestError("credential-shaped bytes in selected candidate code")
            found[card] = row
    if set(found) != set(wanted):
        raise ManifestError("not every selected candidate has one blind code view")
    return found


def shard(run_id: str) -> int:
    value = text_digest(f"score-channel-shard-v1|{run_id}")
    return int(value, 16) % SHARDS


def repository_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    value = result.stdout.strip()
    if result.returncode or len(value) != 40:
        raise ManifestError("cannot resolve source commit")
    return value


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            if set(row) != REPLAY_KEYS:
                raise ManifestError("internal replay row schema mismatch")
            handle.write(canonical(row) + "\n")


def produce(selection_dir: Path, intake_root: Path, repo: Path, out_dir: Path) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite replay manifest: {out_dir}")
    selected, selection_summary = load_selection(selection_dir)
    code_views = load_selected_code(intake_root, selected, selection_summary)
    rows: list[dict[str, Any]] = []
    for parent in selected:
        shard_id = shard(parent["run_id"])
        for card in parent["candidate_card_ids"]:
            view = code_views[card]
            rows.append({
                "schema_version": ROW_SCHEMA,
                "card_id": card,
                "competition": parent["task"],
                "task": parent["task"],
                "run_id": parent["run_id"],
                "parent": parent["parent_id"],
                "code": view["code"],
                "code_sha256": view["code_sha256"],
                "source_intake": parent["source_intake"],
                "selection_rank_in_run": parent["selection_rank_in_run"],
                "shard_id": shard_id,
                "cap_seconds": CAP_SECONDS,
            })
    rows.sort(key=lambda row: (
        row["shard_id"], row["run_id"], row["selection_rank_in_run"], row["parent"], row["card_id"]
    ))
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp.", dir=out_dir.parent))
    try:
        manifest_path = temporary / "replay_manifest.jsonl"
        write_rows(manifest_path, rows)
        shard_hashes: dict[str, str] = {}
        shard_counts: dict[str, int] = {}
        for shard_id in range(SHARDS):
            shard_rows = [row for row in rows if row["shard_id"] == shard_id]
            shard_path = temporary / f"shard_{shard_id}.jsonl"
            write_rows(shard_path, shard_rows)
            shard_hashes[str(shard_id)] = digest(shard_path)
            shard_counts[str(shard_id)] = len(shard_rows)
        run_shards: dict[str, set[int]] = {}
        for row in rows:
            run_shards.setdefault(row["run_id"], set()).add(row["shard_id"])
        if any(len(values) != 1 for values in run_shards.values()):
            raise ManifestError("one physical run spans multiple shards")
        summary = {
            "protocol": PROTOCOL,
            "status": "REPLAY_MANIFEST_FROZEN_APPROVAL_PENDING",
            "matrix": {
                "cap_seconds": CAP_SECONDS,
                "caps_swept": False,
                "fresh_workspace_per_candidate": True,
                "candidate_code_modified": False,
                "online_hf": True,
                "pristine_external_grader": True,
                "shards": SHARDS,
                "gpus_per_shard": 1,
                "physical_run_single_shard": True,
                "resume_key": ["card_id", "cap_seconds"],
            },
            "counts": {
                "physical_runs": len(run_shards),
                "selected_parents": len(selected),
                "planned_candidate_replays": len(rows),
                "shard_candidate_replays": shard_counts,
            },
            "budget": {
                "cap_upper_bound_gpu_hours": len(rows) * CAP_SECONDS / 3600.0,
                "llm_api_calls": 0,
                "gpu_jobs_submitted": 0,
            },
            "inputs": {
                "parent_selection_summary_sha256": digest(selection_dir / "summary.json"),
                "selected_parents_sha256": digest(selection_dir / "selected_parents.jsonl"),
            },
            "outputs": {
                "replay_manifest_sha256": digest(manifest_path),
                "shard_sha256": shard_hashes,
            },
            "gates": {
                "parent_gate_pass": True,
                "manifest_frozen": True,
                "user_matrix_and_budget_approval_recorded": False,
                "replay_submission_authorized": False,
            },
            "blindness": {
                "label_vault_opened": False,
                "label_values_or_order_read": False,
                "code_opened": True,
                "replay_outcomes_opened": False,
                "outcome_metrics_computed": [],
            },
            "implementation": {
                "source_commit": repository_head(repo),
                "script_sha256": digest(Path(__file__)),
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
    parser.add_argument("--selection-dir", required=True, type=Path)
    parser.add_argument("--intake-root", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        summary = produce(args.selection_dir, args.intake_root, args.repo, args.out_dir)
    except (ManifestError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_REPLAY_MANIFEST_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical({
        "status": summary["status"],
        "planned_candidate_replays": summary["counts"]["planned_candidate_replays"],
        "cap_upper_bound_gpu_hours": summary["budget"]["cap_upper_bound_gpu_hours"],
        "gpu_jobs_submitted": 0,
        "replay_submission_authorized": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
