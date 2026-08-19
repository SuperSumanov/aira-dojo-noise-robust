"""Outcome-blind exact clone audit for the prospective first-960 prefix.

The audit reads code-only eligible manifests and identity-only run records.  It
never opens labels, grades, outcomes, scorer predictions, or frozen test data.
Normalized fingerprints are exact clone detectors, not semantic equivalence
proofs; the aggressive AST skeleton is reported only as a diagnostic upper bound.
"""

from __future__ import annotations

import argparse
import ast
import collections
import copy
import hashlib
import io
import json
import platform
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "prospective_code_clone_audit_v1"
FROZEN_COHORT_RUN_TARGET = 960
MIN_NORMALIZATION_COVERAGE = 0.99
MAX_CROSS_RUN_ENDPOINT_FRACTION = 0.01
MAX_CROSS_TASK_ENDPOINT_FRACTION = 0.005
MAX_LARGE_MULTITASK_GROUPS = 0
BLIND_KEYS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "generation_started_at_utc",
    "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
    "run_id",
    "task",
    "drop_id",
    "flow_status",
    "endpoints",
    "generation_started_at_utc",
    "source_sha256",
}


class CloneAuditError(RuntimeError):
    """Raised when an outcome-blind input or reproducibility invariant fails."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CloneAuditError(f"expected JSON object: {path.name}")
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise CloneAuditError(
                    f"invalid JSONL in {path.name} at line {line_number}"
                ) from error
            if not isinstance(value, dict):
                raise CloneAuditError(
                    f"non-object JSONL in {path.name} at line {line_number}"
                )
            yield value


def require_sha(path: Path, expected: Any) -> None:
    if not isinstance(expected, str) or sha256_file(path) != expected:
        raise CloneAuditError(f"SHA mismatch: {path.name}")


class _AstNormalizer(ast.NodeTransformer):
    def __init__(self, normalize_names: bool) -> None:
        self.normalize_names = normalize_names

    def visit_Constant(self, node: ast.Constant) -> ast.AST:  # noqa: N802
        value = node.value
        if value is None:
            marker = "<NONE>"
        elif value is Ellipsis:
            marker = "<ELLIPSIS>"
        elif isinstance(value, bool):
            marker = "<BOOL>"
        elif isinstance(value, str):
            marker = "<STR>"
        elif isinstance(value, bytes):
            marker = "<BYTES>"
        elif isinstance(value, (int, float, complex)):
            marker = "<NUMBER>"
        else:
            marker = f"<{type(value).__name__.upper()}>"
        return ast.copy_location(ast.Constant(value=marker), node)

    def visit_Name(self, node: ast.Name) -> ast.AST:  # noqa: N802
        if self.normalize_names:
            node.id = "<ID>"
        return self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> ast.AST:
        if self.normalize_names:
            node.arg = "<ARG>"
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802
        if self.normalize_names:
            node.name = "<FUNCTION>"
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:  # noqa: N802
        if self.normalize_names:
            node.name = "<ASYNC_FUNCTION>"
        return self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:  # noqa: N802
        if self.normalize_names:
            node.name = "<CLASS>"
        return self.generic_visit(node)

    def visit_alias(self, node: ast.alias) -> ast.AST:
        if self.normalize_names and node.asname is not None:
            node.asname = "<ALIAS>"
        return self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> ast.AST:  # noqa: N802
        if self.normalize_names:
            node.names = ["<GLOBAL>" for _ in node.names]
        return self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.AST:  # noqa: N802
        if self.normalize_names:
            node.names = ["<NONLOCAL>" for _ in node.names]
        return self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:  # noqa: N802
        if self.normalize_names and node.name is not None:
            node.name = "<EXCEPTION>"
        return self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> ast.AST:  # noqa: N802
        if self.normalize_names and node.name is not None:
            node.name = "<MATCH>"
        return self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> ast.AST:  # noqa: N802
        if self.normalize_names and node.name is not None:
            node.name = "<MATCH_STAR>"
        return self.generic_visit(node)


def token_literal_fingerprint(code: str) -> str:
    normalized: list[tuple[int, str]] = []
    ignored = {
        tokenize.ENCODING,
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.ENDMARKER,
    }
    for token in tokenize.generate_tokens(io.StringIO(code).readline):
        if token.type in ignored:
            continue
        value = token.string
        if token.type == tokenize.NUMBER:
            value = "<NUMBER>"
        elif token.type == tokenize.STRING:
            value = "<STRING>"
        normalized.append((token.type, value))
    payload = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
    return sha256_text(payload)


def ast_fingerprint(code: str, normalize_names: bool) -> str:
    tree = ast.parse(code)
    normalized = _AstNormalizer(normalize_names=normalize_names).visit(copy.deepcopy(tree))
    ast.fix_missing_locations(normalized)
    payload = ast.dump(normalized, annotate_fields=True, include_attributes=False)
    return sha256_text(payload)


def fingerprints(code: str) -> dict[str, str | None]:
    values: dict[str, str | None] = {"raw_exact": sha256_text(code)}
    try:
        values["token_literal_norm"] = token_literal_fingerprint(code)
    except (IndentationError, SyntaxError, tokenize.TokenError):
        values["token_literal_norm"] = None
    try:
        values["ast_literal_norm"] = ast_fingerprint(code, normalize_names=False)
        values["ast_skeleton"] = ast_fingerprint(code, normalize_names=True)
    except (IndentationError, SyntaxError, ValueError, TypeError, MemoryError):
        values["ast_literal_norm"] = None
        values["ast_skeleton"] = None
    return values


def summarize_fingerprint(
    records: list[dict[str, str]], fingerprint_name: str
) -> dict[str, int | float | None]:
    groups: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    failures = 0
    for record in records:
        value = record.get(fingerprint_name)
        if not value:
            failures += 1
            continue
        groups[value].append(record)
    fingerprinted = len(records) - failures
    duplicate_groups = [group for group in groups.values() if len(group) > 1]
    cross_run_groups = [
        group for group in duplicate_groups if len({record["run_id"] for record in group}) > 1
    ]
    cross_task_groups = [
        group for group in duplicate_groups if len({record["task"] for record in group}) > 1
    ]
    large_multitask_groups = [
        group
        for group in duplicate_groups
        if len(group) >= 10 and len({record["task"] for record in group}) >= 3
    ]
    same_parent_groups = [
        group
        for group in duplicate_groups
        if len({(record["run_id"], record["parent"]) for record in group}) == 1
    ]
    cross_run_endpoints = sum(len(group) for group in cross_run_groups)
    cross_task_endpoints = sum(len(group) for group in cross_task_groups)
    return {
        "input_endpoints": len(records),
        "fingerprinted_endpoints": fingerprinted,
        "normalization_failures": failures,
        "coverage": fingerprinted / len(records) if records else None,
        "unique_fingerprints": len(groups),
        "unique_fraction": len(groups) / fingerprinted if fingerprinted else None,
        "duplicate_groups": len(duplicate_groups),
        "duplicate_endpoints_beyond_first": sum(len(group) - 1 for group in duplicate_groups),
        "largest_group_size": max((len(group) for group in groups.values()), default=0),
        "same_parent_duplicate_groups": len(same_parent_groups),
        "cross_run_duplicate_groups": len(cross_run_groups),
        "cross_run_duplicate_endpoints": cross_run_endpoints,
        "cross_run_duplicate_endpoint_fraction": cross_run_endpoints / fingerprinted
        if fingerprinted
        else None,
        "cross_task_duplicate_groups": len(cross_task_groups),
        "cross_task_duplicate_endpoints": cross_task_endpoints,
        "cross_task_duplicate_endpoint_fraction": cross_task_endpoints / fingerprinted
        if fingerprinted
        else None,
        "large_multitask_duplicate_groups": len(large_multitask_groups),
    }


def audit(
    state_root: Path,
    snapshot_root: Path,
    cohort_run_target: int,
    source_commit: str,
) -> dict[str, Any]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    if snapshot_root.parent != state_root / "snapshots":
        raise CloneAuditError("snapshot is outside state root")
    if len(snapshot_root.name) != 64 or any(c not in "0123456789abcdef" for c in snapshot_root.name):
        raise CloneAuditError("snapshot basename is not a lowercase SHA-256")
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise CloneAuditError("source commit is not a lowercase full Git SHA")

    registry_path = snapshot_root / "intake_registry.jsonl"
    accumulator_dir = snapshot_root / "accumulator"
    runs_path = accumulator_dir / "provisional_runs.jsonl"
    accumulator_summary_path = accumulator_dir / "summary.json"
    registry = list(read_jsonl(registry_path))
    cards: dict[str, dict[str, str]] = {}
    drop_for_run: dict[str, str] = {}
    intake_summary_shas: dict[str, str] = {}
    seen_drops: set[str] = set()

    for entry in registry:
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise CloneAuditError("registry schema mismatch")
        drop_id = entry["drop_id"]
        if not isinstance(drop_id, str) or drop_id in seen_drops:
            raise CloneAuditError("duplicate or invalid drop ID")
        seen_drops.add(drop_id)
        intake_dir = Path(entry["intake_dir"]).resolve()
        if intake_dir.parent != state_root / "intakes" or intake_dir.name != drop_id:
            raise CloneAuditError("intake path binding mismatch")
        summary_path = intake_dir / "summary.json"
        require_sha(summary_path, entry["summary_sha256"])
        summary = read_json(summary_path)
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if not isinstance(outputs, dict) or not isinstance(security, dict) or not isinstance(
            blindness, dict
        ):
            raise CloneAuditError("intake metadata missing")
        if (
            security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or security.get("journal_scanned_before_json") is not True
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
        ):
            raise CloneAuditError("intake blindness gate mismatch")
        intake_summary_shas[drop_id] = entry["summary_sha256"]
        manifest_path = intake_dir / "eligible_blind_manifest.jsonl"
        require_sha(manifest_path, outputs.get("eligible_blind_manifest_sha256"))
        for row in read_jsonl(manifest_path):
            if set(row) != BLIND_KEYS or not isinstance(row.get("lineage"), dict):
                raise CloneAuditError("blind manifest schema mismatch")
            if set(row["lineage"]) != LINEAGE_KEYS:
                raise CloneAuditError("blind lineage schema mismatch")
            card_id = row["card_id"]
            run_id = row["run_id"]
            task = row["task"]
            code = row["code"]
            parent = row["lineage"]["parent"]
            generation_started_at_utc = row["generation_started_at_utc"]
            source_sha256 = row["source_sha256"]
            if not all(
                isinstance(value, str)
                for value in (
                    card_id,
                    run_id,
                    task,
                    code,
                    parent,
                    generation_started_at_utc,
                    source_sha256,
                )
            ):
                raise CloneAuditError("blind manifest identity type mismatch")
            if len(source_sha256) != 64 or any(
                character not in "0123456789abcdef" for character in source_sha256
            ):
                raise CloneAuditError("blind manifest source SHA mismatch")
            if card_id in cards or sha256_text(code) != row["code_sha256"]:
                raise CloneAuditError("duplicate card or exact-code SHA mismatch")
            owner = drop_for_run.setdefault(run_id, drop_id)
            if owner != drop_id:
                raise CloneAuditError("run appears in multiple drops")
            cards[card_id] = {
                "run_id": run_id,
                "task": task,
                "parent": parent,
                "code": code,
                "generation_started_at_utc": generation_started_at_utc,
                "source_sha256": source_sha256,
            }

    runs = list(read_jsonl(runs_path))
    run_rows: dict[str, dict[str, Any]] = {}
    for row in runs:
        if set(row) != RUN_KEYS:
            raise CloneAuditError("provisional run schema mismatch")
        run_id = row["run_id"]
        if not isinstance(run_id, str) or run_id in run_rows:
            raise CloneAuditError("duplicate or invalid run ID")
        if (
            not isinstance(row["task"], str)
            or not isinstance(row["generation_started_at_utc"], str)
            or not isinstance(row["source_sha256"], str)
            or not isinstance(row["endpoints"], int)
            or row["flow_status"] != "scoreable"
            or row["drop_id"] != drop_for_run.get(run_id)
        ):
            raise CloneAuditError("run flow or drop binding mismatch")
        run_rows[run_id] = row
    card_run_ids = {record["run_id"] for record in cards.values()}
    if card_run_ids != set(run_rows):
        raise CloneAuditError("card and run support differ")
    endpoint_counts = collections.Counter(record["run_id"] for record in cards.values())
    if any(row["endpoints"] != endpoint_counts[run_id] for run_id, row in run_rows.items()):
        raise CloneAuditError("run endpoint accounting mismatch")
    if any(
        record["task"] != run_rows[record["run_id"]]["task"]
        or record["generation_started_at_utc"]
        != run_rows[record["run_id"]]["generation_started_at_utc"]
        or record["source_sha256"] != run_rows[record["run_id"]]["source_sha256"]
        for record in cards.values()
    ):
        raise CloneAuditError("card and run ordering identity differ")

    ordered_runs = sorted(
        runs,
        key=lambda row: (
            str(row["generation_started_at_utc"]),
            str(row["source_sha256"]),
            str(row["run_id"]),
        ),
    )
    cohort_rows = ordered_runs[:cohort_run_target]
    cohort_run_ids = {str(row["run_id"]) for row in cohort_rows}
    cohort_cards = [
        (card_id, record)
        for card_id, record in sorted(cards.items())
        if record["run_id"] in cohort_run_ids
    ]
    records: list[dict[str, str]] = []
    for _card_id, record in cohort_cards:
        result = fingerprints(record["code"])
        records.append(
            {
                "run_id": record["run_id"],
                "task": record["task"],
                "parent": record["parent"],
                **{name: value or "" for name, value in result.items()},
            }
        )

    summaries = {
        name: summarize_fingerprint(records, name)
        for name in ("raw_exact", "token_literal_norm", "ast_literal_norm", "ast_skeleton")
    }
    primary_names = ("token_literal_norm", "ast_literal_norm")
    primary_checks = {
        name: {
            "coverage": summaries[name]["coverage"] is not None
            and summaries[name]["coverage"] >= MIN_NORMALIZATION_COVERAGE,
            "cross_run_endpoint_fraction": summaries[name][
                "cross_run_duplicate_endpoint_fraction"
            ]
            is not None
            and summaries[name]["cross_run_duplicate_endpoint_fraction"]
            <= MAX_CROSS_RUN_ENDPOINT_FRACTION,
            "cross_task_endpoint_fraction": summaries[name][
                "cross_task_duplicate_endpoint_fraction"
            ]
            is not None
            and summaries[name]["cross_task_duplicate_endpoint_fraction"]
            <= MAX_CROSS_TASK_ENDPOINT_FRACTION,
            "large_multitask_groups": summaries[name]["large_multitask_duplicate_groups"]
            <= MAX_LARGE_MULTITASK_GROUPS,
        }
        for name in primary_names
    }
    raw_cross_run_zero = summaries["raw_exact"]["cross_run_duplicate_groups"] == 0
    strong_support = raw_cross_run_zero and all(
        all(checks.values()) for checks in primary_checks.values()
    )

    accumulator_summary = read_json(accumulator_summary_path)
    inventory = accumulator_summary.get("inventory")
    if not isinstance(inventory, dict):
        raise CloneAuditError("accumulator inventory missing")
    cross_checks = {
        "transactions": inventory.get("drops") == len(registry),
        "all_eligible_runs": inventory.get("eligible_runs") == len(runs),
        "all_eligible_endpoints": inventory.get("eligible_endpoints") == len(cards),
        "provisional_first960_runs": inventory.get("provisional_first960_runs")
        == len(cohort_rows),
        "provisional_first960_endpoints": inventory.get("provisional_first960_endpoints")
        == len(cohort_cards),
    }
    if not all(cross_checks.values()):
        raise CloneAuditError("clone audit differs from accumulator inventory")

    return {
        "status": "PROVISIONAL_CODE_CLONE_AUDIT_COMPLETE",
        "protocol": PROTOCOL,
        "source_commit": source_commit,
        "source_sha256": sha256_file(Path(__file__)),
        "snapshot_sha256": snapshot_root.name,
        "scope": {
            "name": "provisional_first960_prefix",
            "target_runs": cohort_run_target,
            "observed_runs": len(cohort_rows),
            "observed_endpoints": len(cohort_cards),
            "confirmatory_outcomes_opened": False,
        },
        "inputs": {
            "intake_registry_sha256": sha256_file(registry_path),
            "provisional_runs_sha256": sha256_file(runs_path),
            "accumulator_summary_sha256": sha256_file(accumulator_summary_path),
            "intake_summary_sha256": dict(sorted(intake_summary_shas.items())),
        },
        "normalizations": summaries,
        "pre_registered_gate": {
            "thresholds": {
                "minimum_normalization_coverage": MIN_NORMALIZATION_COVERAGE,
                "maximum_cross_run_duplicate_endpoint_fraction": MAX_CROSS_RUN_ENDPOINT_FRACTION,
                "maximum_cross_task_duplicate_endpoint_fraction": MAX_CROSS_TASK_ENDPOINT_FRACTION,
                "maximum_large_multitask_duplicate_groups": MAX_LARGE_MULTITASK_GROUPS,
            },
            "raw_exact_cross_run_zero": raw_cross_run_zero,
            "primary_checks": primary_checks,
            "strong_low_normalized_clone_support": strong_support,
            "ast_skeleton_is_diagnostic_only": True,
            "semantic_equivalence_or_fuzzy_clone_absence_proven": False,
        },
        "cross_checks_against_accumulator": cross_checks,
        "reproducibility": {
            "python_version": platform.python_version(),
            "python_executable": str(Path(sys.executable).resolve()),
            "randomness_used": False,
        },
        "security": {
            "allowed_basenames_read": [
                "eligible_blind_manifest.jsonl",
                "intake_registry.jsonl",
                "provisional_runs.jsonl",
                "summary.json",
            ],
            "code_values_emitted": False,
            "task_or_card_values_emitted": False,
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--cohort-run-target", required=True, type=int)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output}")
    if args.cohort_run_target != FROZEN_COHORT_RUN_TARGET:
        raise CloneAuditError("cohort target differs from the frozen confirmatory protocol")
    repo_root = Path(__file__).resolve().parent.parent
    actual_commit = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    source_relative = Path(__file__).resolve().relative_to(repo_root).as_posix()
    committed_blob = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", f"{actual_commit}:{source_relative}"],
        text=True,
    ).strip()
    worktree_blob = subprocess.check_output(
        ["git", "-C", str(repo_root), "hash-object", str(Path(__file__).resolve())],
        text=True,
    ).strip()
    if actual_commit != args.source_commit or committed_blob != worktree_blob:
        raise CloneAuditError("source commit or Git blob binding failed")
    receipt = audit(
        args.state_root,
        args.snapshot_root,
        args.cohort_run_target,
        args.source_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PROSPECTIVE_CODE_CLONE_AUDIT_COMPLETE",
        f"runs={receipt['scope']['observed_runs']}",
        f"endpoints={receipt['scope']['observed_endpoints']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
