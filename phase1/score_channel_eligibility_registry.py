"""Build an outcome-blind run gate for the prospective score-channel replay.

The registry consumes only credential-screened intake summaries and their safe
source-provenance sidecars.  It never opens label vaults, blind code views, raw
journals, score registries, or replay outcomes.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-run-eligibility-registry-v1"


class RegistryError(RuntimeError):
    """Fail-closed integrity error."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise RegistryError(f"invalid timestamp: {value!r}") from error
    if parsed.tzinfo is None:
        raise RegistryError(f"timestamp has no timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def canonical_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def mechanism_cutoff(repo: Path, commit: str) -> tuple[str, str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", "-s", "--format=%H%n%cI", commit],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = result.stdout.strip().splitlines()
    if result.returncode != 0 or len(lines) != 2:
        raise RegistryError(f"cannot resolve mechanism commit: {commit}")
    resolved, timestamp = lines
    return resolved, canonical_utc(parse_utc(timestamp))


def repository_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or len(value) != 40:
        raise RegistryError("cannot resolve registry source commit")
    return value


def verify_intake_summary(summary: dict[str, Any], intake_name: str) -> None:
    if summary.get("protocol") != "prospective_drop_intake_v1":
        raise RegistryError(f"{intake_name}: unexpected intake protocol")
    security = summary.get("security") or {}
    expected_security = {
        "credential_shaped_journals": 0,
        "env_members_extracted": False,
        "env_members_read": False,
        "journal_scanned_before_json": True,
        "live_event_journal_members_read": False,
        "precutoff_code_sha256_overlap": 0,
        "precutoff_endpoint_id_overlap": 0,
        "raw_journals_written": False,
    }
    for key, expected in expected_security.items():
        if security.get(key) != expected:
            raise RegistryError(f"{intake_name}: unsafe intake flag {key}")
    blindness = summary.get("blindness") or {}
    expected_blindness = {
        "label_values_printed": False,
        "labels_used_for_endpoint_selection": False,
        "labels_used_for_run_selection": False,
        "metrics_computed": [],
    }
    for key, expected in expected_blindness.items():
        if blindness.get(key) != expected:
            raise RegistryError(f"{intake_name}: blindness flag failed: {key}")


def load_registry_rows(
    intake_root: Path, cutoff: datetime
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, Any]]]:
    provenance_paths = sorted(intake_root.glob("*/source_provenance.json"))
    if not provenance_paths:
        raise RegistryError("no source_provenance.json files found")
    all_rows: list[dict[str, str]] = []
    eligible_rows: list[dict[str, str]] = []
    manifests: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    seen_journals: set[str] = set()
    for provenance_path in provenance_paths:
        intake_name = provenance_path.parent.name
        summary_path = provenance_path.parent / "summary.json"
        if not summary_path.is_file():
            raise RegistryError(f"{intake_name}: summary.json is missing")
        summary = read_json(summary_path)
        if not isinstance(summary, dict):
            raise RegistryError(f"{intake_name}: summary is not an object")
        verify_intake_summary(summary, intake_name)
        expected_sha = (summary.get("outputs") or {}).get("source_provenance_sha256")
        actual_sha = sha256(provenance_path)
        if expected_sha != actual_sha:
            raise RegistryError(f"{intake_name}: source provenance SHA mismatch")
        rows = read_json(provenance_path)
        if not isinstance(rows, list) or not rows:
            raise RegistryError(f"{intake_name}: provenance must be a non-empty list")
        manifests.append(
            {
                "intake": intake_name,
                "runs": len(rows),
                "source_provenance_sha256": actual_sha,
                "summary_sha256": sha256(summary_path),
            }
        )
        for raw in rows:
            if not isinstance(raw, dict):
                raise RegistryError(f"{intake_name}: provenance row is not an object")
            required = (
                "archive_name", "archive_sha256", "run_id", "journal_sha256",
                "task", "generation_started_at_utc",
            )
            if any(not isinstance(raw.get(key), str) or not raw[key] for key in required):
                raise RegistryError(f"{intake_name}: malformed safe provenance row")
            run_id = raw["run_id"]
            journal_sha = raw["journal_sha256"].lower()
            if len(journal_sha) != 64 or any(c not in "0123456789abcdef" for c in journal_sha):
                raise RegistryError(f"{intake_name}: invalid journal SHA")
            if run_id != f"journal:{journal_sha}":
                raise RegistryError(f"{intake_name}: run ID does not bind journal SHA")
            if run_id in seen_runs or journal_sha in seen_journals:
                raise RegistryError(f"{intake_name}: duplicate physical journal")
            seen_runs.add(run_id)
            seen_journals.add(journal_sha)
            started = parse_utc(raw["generation_started_at_utc"])
            safe = {
                "archive_name": raw["archive_name"],
                "archive_sha256": raw["archive_sha256"],
                "generation_started_at_utc": canonical_utc(started),
                "journal_sha256": journal_sha,
                "run_id": run_id,
                "task": raw["task"],
            }
            all_rows.append(safe)
            if started > cutoff:
                eligible_rows.append(safe)
    sort_key = lambda row: (row["generation_started_at_utc"], row["journal_sha256"])
    return sorted(all_rows, key=sort_key), sorted(eligible_rows, key=sort_key), manifests


def summarize(
    all_rows: list[dict[str, str]],
    eligible_rows: list[dict[str, str]],
    manifests: list[dict[str, Any]],
    mechanism_commit: str,
    cutoff_utc: str,
    min_runs: int,
    max_dominant_share: float,
) -> dict[str, Any]:
    per_task = collections.Counter(row["task"] for row in eligible_rows)
    dominant_task, dominant_runs = (per_task.most_common(1)[0] if per_task else (None, 0))
    eligible_count = len(eligible_rows)
    dominant_share = dominant_runs / eligible_count if eligible_count else None
    enough_runs = eligible_count >= min_runs
    task_balance = dominant_share is not None and dominant_share <= max_dominant_share
    run_gate_pass = enough_runs and task_balance
    return {
        "protocol": PROTOCOL,
        "status": (
            "RUN_GATE_PASS_PARENT_GATE_PENDING" if run_gate_pass else "RUN_GATE_WAIT"
        ),
        "mechanism_commit": mechanism_commit,
        "mechanism_cutoff_utc": cutoff_utc,
        "thresholds": {
            "min_runs": min_runs,
            "max_dominant_task_share": max_dominant_share,
        },
        "counts": {
            "intakes": len(manifests),
            "observed_runs": len(all_rows),
            "eligible_post_mechanism_runs": eligible_count,
            "excluded_pre_or_equal_cutoff_runs": len(all_rows) - eligible_count,
            "tasks": len(per_task),
            "remaining_to_min_runs": max(0, min_runs - eligible_count),
        },
        "task_balance": {
            "dominant_task": dominant_task,
            "dominant_runs": dominant_runs,
            "dominant_share": dominant_share,
            "per_task": dict(sorted(per_task.items())),
        },
        "gates": {
            "enough_runs": enough_runs,
            "task_balance": task_balance,
            "run_gate_pass": run_gate_pass,
            "parent_gate_pending": True,
            "replay_submission_authorized": False,
        },
        "blindness": {
            "label_vault_opened": False,
            "raw_journal_opened": False,
            "code_opened": False,
            "score_or_outcome_opened": False,
            "labels_used_for_run_selection": False,
        },
        "input_manifest": manifests,
    }


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def produce(
    intake_root: Path,
    repo: Path,
    mechanism_commit: str,
    min_runs: int,
    max_dominant_share: float,
    out_dir: Path,
) -> dict[str, Any]:
    if min_runs <= 0 or not 0 < max_dominant_share <= 1:
        raise RegistryError("invalid run-gate thresholds")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RegistryError(f"refusing to overwrite non-empty output: {out_dir}")
    resolved_commit, cutoff_utc = mechanism_cutoff(repo, mechanism_commit)
    cutoff = parse_utc(cutoff_utc)
    all_rows, eligible_rows, manifests = load_registry_rows(intake_root, cutoff)
    summary = summarize(
        all_rows, eligible_rows, manifests, resolved_commit, cutoff_utc,
        min_runs, max_dominant_share,
    )
    summary["implementation"] = {
        "python": platform.python_version(),
        "registry_source_commit": repository_head(repo),
        "script_sha256": sha256(Path(__file__)),
    }
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    try:
        eligible_path = temporary / "eligible_runs.jsonl"
        write_jsonl(eligible_path, eligible_rows)
        summary["outputs"] = {
            "eligible_runs_sha256": sha256(eligible_path),
        }
        (temporary / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        if out_dir.exists():
            out_dir.rmdir()
        os.replace(temporary, out_dir)
    except Exception:
        for child in temporary.iterdir():
            child.unlink()
        temporary.rmdir()
        raise
    return summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake-root", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--mechanism-commit", required=True)
    parser.add_argument("--min-runs", type=int, default=150)
    parser.add_argument("--max-dominant-share", type=float, default=0.25)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    summary = produce(
        args.intake_root,
        args.repo,
        args.mechanism_commit,
        args.min_runs,
        args.max_dominant_share,
        args.out_dir,
    )
    print(json.dumps({
        "status": summary["status"],
        "eligible_runs": summary["counts"]["eligible_post_mechanism_runs"],
        "remaining": summary["counts"]["remaining_to_min_runs"],
        "dominant_share": summary["task_balance"]["dominant_share"],
        "out_dir": str(args.out_dir),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
