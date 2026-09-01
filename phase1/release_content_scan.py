"""Scan historical release text fields for verbatim prepared competition data.

The public summary is aggregate-only. Raw candidate patterns, source matches, and
card identifiers stay inside a mode-0700 work directory; the private manifest
contains only hashes of identifiers and matched spans. Prospective resources are
not accepted by this tool.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import subprocess
import tokenize
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


TEXT_SUFFIXES = {".csv", ".json", ".jsonl", ".txt", ".tsv", ".yaml", ".yml"}


class ScanError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_json(path: Path, payload: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def safe_name(task: str) -> str:
    if not task or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in task):
        raise ScanError(f"unsafe task identifier: {task!r}")
    return task


def is_datalike(pattern: bytes, minimum_distinct: int, minimum_nonspace: int) -> bool:
    if len(set(pattern)) < minimum_distinct:
        return False
    if sum(byte not in b" \t" for byte in pattern) < minimum_nonspace:
        return False
    if any(byte < 32 and byte != 9 for byte in pattern):
        return False
    return any(
        48 <= byte <= 57 or 65 <= byte <= 90 or 97 <= byte <= 122 or byte >= 128
        for byte in pattern
    )


def windows(
    value: str | bytes,
    width: int,
    minimum_distinct: int,
    minimum_nonspace: int,
) -> Iterable[bytes]:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    for line in raw.splitlines():
        if len(line) < width:
            continue
        for offset in range(len(line) - width + 1):
            pattern = line[offset : offset + width]
            if is_datalike(pattern, minimum_distinct, minimum_nonspace):
                yield pattern


def literal_fragments(code: str) -> tuple[list[str | bytes], list[str], bool]:
    """Return decoded literals, comments, and whether both parsers succeeded."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(code)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    fragments: list[str | bytes] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            fragments.append(node.value)
            continue
        if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)) and not isinstance(
            parents.get(node), (ast.List, ast.Tuple, ast.Set, ast.Dict)
        ):
            try:
                ast.literal_eval(node)
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                continue
            segment = ast.get_source_segment(code, node)
            if segment:
                fragments.append(segment)

    comments: list[str] = []
    token_ok = True
    try:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type == tokenize.COMMENT:
                comments.append(token.string[1:])
    except (tokenize.TokenError, IndentationError):
        token_ok = False
    return fragments, comments, token_ok


def card_patterns(
    card: dict[str, Any],
    width: int,
    minimum_distinct: int,
    minimum_nonspace: int,
) -> tuple[dict[str, set[bytes]], bool]:
    output: dict[str, set[bytes]] = {"stdout_tail": set(), "code_literal_or_comment": set()}
    tail = str((card.get("obs") or {}).get("stdout_tail") or "")
    output["stdout_tail"].update(windows(tail, width, minimum_distinct, minimum_nonspace))
    code = str(card.get("code") or "")
    parser_ok = True
    try:
        literals, comments, token_ok = literal_fragments(code)
    except SyntaxError:
        literals, comments, token_ok = [], [], False
        parser_ok = False
    for fragment in literals:
        output["code_literal_or_comment"].update(
            windows(fragment, width, minimum_distinct, minimum_nonspace)
        )
    for comment in comments:
        output["code_literal_or_comment"].update(
            windows(comment, width, minimum_distinct, minimum_nonspace)
        )
    return output, parser_ok and token_ok


def source_files(data_root: Path, task: str) -> list[Path]:
    prepared = data_root / task / "prepared"
    if not prepared.is_dir():
        return []
    return sorted(
        path
        for path in prepared.rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
    )


def source_manifest(files: list[Path], prepared: Path) -> tuple[list[dict[str, Any]], str]:
    records = []
    for path in files:
        records.append(
            {
                "relative_path": path.relative_to(prepared).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return records, digest_bytes(canonical)


def write_patterns(path: Path, patterns: set[bytes]) -> None:
    with path.open("wb") as handle:
        for pattern in sorted(patterns):
            if b"\n" in pattern or b"\r" in pattern:
                raise ScanError("line break reached fixed-width pattern writer")
            handle.write(pattern + b"\n")
    os.chmod(path, 0o600)


def load_fixed_lines(path: Path, width: int) -> set[bytes]:
    output = set()
    with path.open("rb") as handle:
        for line_number, line in enumerate(handle, 1):
            value = line[:-1] if line.endswith(b"\n") else line
            if len(value) != width:
                raise ScanError(f"unexpected pattern width at {path}:{line_number}")
            output.add(value)
    return output


def grep_match(pattern_path: Path, files: list[Path], raw_output: Path, timeout_s: int) -> tuple[int, str]:
    command = ["grep", "-a", "-h", "-o", "-F", "-f", str(pattern_path), "--"]
    command.extend(str(path) for path in files)
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    with raw_output.open("wb") as output:
        try:
            completed = subprocess.run(
                command,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ScanError(f"grep matcher timed out after {timeout_s}s") from exc
    os.chmod(raw_output, 0o600)
    if completed.returncode not in (0, 1):
        raise ScanError(
            f"grep matcher failed rc={completed.returncode}, stderr_sha256="
            f"{digest_bytes(completed.stderr)}"
        )
    return completed.returncode, digest_bytes(completed.stderr)


def python_match(patterns: set[bytes], files: list[Path]) -> set[bytes]:
    """Tiny-fixture fallback used by tests, not the full release run."""

    matched: set[bytes] = set()
    for path in files:
        source = path.read_bytes()
        matched.update(pattern for pattern in patterns if pattern in source)
    return matched


def scan(args: argparse.Namespace) -> dict[str, Any]:
    cards_path = args.cards.resolve()
    if sha256(cards_path) != args.expected_cards_sha256:
        raise ScanError("cards SHA-256 differs from the frozen release")
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(work_dir, 0o700)
    pattern_dir = work_dir / "patterns"
    match_dir = work_dir / "matches"
    receipt_dir = work_dir / "task_receipts"
    for directory in (pattern_dir, match_dir, receipt_dir):
        directory.mkdir(exist_ok=True)
        os.chmod(directory, 0o700)

    minimum_nonspace = int(args.width * args.minimum_nonspace_fraction + 0.999999)
    patterns_by_task: dict[str, set[bytes]] = defaultdict(set)
    cards_by_task: Counter[str] = Counter()
    parser_failures: Counter[str] = Counter()
    rows = 0
    with cards_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            card = json.loads(line)
            task = safe_name(str((card.get("task") or {}).get("name") or ""))
            if not task:
                raise ScanError(f"missing task at cards row {line_number}")
            rows += 1
            cards_by_task[task] += 1
            fields, parser_ok = card_patterns(
                card, args.width, args.minimum_distinct, minimum_nonspace
            )
            if not parser_ok:
                parser_failures[task] += 1
            patterns_by_task[task].update(fields["stdout_tail"])
            patterns_by_task[task].update(fields["code_literal_or_comment"])

    task_scan: dict[str, Any] = {}
    matched_by_task: dict[str, set[bytes]] = {}
    private_sources: dict[str, Any] = {}
    for task in sorted(cards_by_task):
        patterns = patterns_by_task[task]
        pattern_path = pattern_dir / f"{task}.patterns"
        write_patterns(pattern_path, patterns)
        pattern_sha = sha256(pattern_path)
        files = source_files(args.data_root, task)
        if not files:
            task_scan[task] = {
                "cards": cards_by_task[task],
                "candidate_patterns": len(patterns),
                "candidate_pattern_file_sha256": pattern_sha,
                "parser_failures": parser_failures[task],
                "prepared_text_available": False,
                "source_files": 0,
                "source_bytes": 0,
                "source_manifest_sha256": None,
                "matched_patterns": None,
                "matched_pattern_file_sha256": None,
                "matcher_rc": None,
                "task_receipt_sha256": None,
                "affected_cards": None,
                "affected_card_fields": None,
                "status": "UNSCANNED_NO_PREPARED_TEXT",
            }
            continue

        prepared = args.data_root / task / "prepared"
        source_records, source_manifest_sha = source_manifest(files, prepared)
        private_sources[task] = source_records
        raw_match = match_dir / f"{task}.raw"
        unique_match = match_dir / f"{task}.unique"
        receipt_path = receipt_dir / f"{task}.json"
        resume_key = {
            "cards_sha256": args.expected_cards_sha256,
            "pattern_sha256": pattern_sha,
            "source_manifest_sha256": source_manifest_sha,
            "width": args.width,
            "minimum_distinct": args.minimum_distinct,
            "minimum_nonspace": minimum_nonspace,
            "matcher": args.matcher,
        }
        reused = False
        if args.resume and receipt_path.is_file() and unique_match.is_file():
            previous = json.loads(receipt_path.read_text(encoding="utf-8"))
            if previous.get("resume_key") == resume_key and previous.get("unique_match_sha256") == sha256(unique_match):
                reused = True

        if reused:
            matched = load_fixed_lines(unique_match, args.width)
            matcher_rc = int(previous["matcher_rc"])
            stderr_sha = str(previous["matcher_stderr_sha256"])
        elif args.matcher == "python":
            matched = python_match(patterns, files)
            write_patterns(unique_match, matched)
            matcher_rc = 0 if matched else 1
            stderr_sha = digest_bytes(b"")
        else:
            matcher_rc, stderr_sha = grep_match(
                pattern_path, files, raw_match, args.task_timeout_s
            )
            matched = load_fixed_lines(raw_match, args.width) if raw_match.stat().st_size else set()
            write_patterns(unique_match, matched)
        if not matched.issubset(patterns):
            raise ScanError(f"matcher emitted a non-candidate pattern for {task}")
        if not reused:
            atomic_json(
                receipt_path,
                {
                    "protocol": "release-content-scan-task-receipt-v1",
                    "task": task,
                    "resume_key": resume_key,
                    "matcher_rc": matcher_rc,
                    "matcher_stderr_sha256": stderr_sha,
                    "matched_patterns": len(matched),
                    "unique_match_sha256": sha256(unique_match),
                },
            )
        receipt_sha = sha256(receipt_path)
        matched_by_task[task] = matched
        task_scan[task] = {
            "cards": cards_by_task[task],
            "candidate_patterns": len(patterns),
            "candidate_pattern_file_sha256": pattern_sha,
            "parser_failures": parser_failures[task],
            "prepared_text_available": True,
            "source_files": len(files),
            "source_bytes": sum(record["bytes"] for record in source_records),
            "source_manifest_sha256": source_manifest_sha,
            "matched_patterns": len(matched),
            "matched_pattern_file_sha256": sha256(unique_match),
            "matcher_rc": matcher_rc,
            "task_receipt_sha256": receipt_sha,
            "affected_cards": 0,
            "affected_card_fields": {"stdout_tail": 0, "code_literal_or_comment": 0},
            "status": "SCANNED",
        }

    affected: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"stdout_tail": set(), "code_literal_or_comment": set()}
    )
    private_hits: dict[str, dict[str, Any]] = {}
    with cards_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            card = json.loads(line)
            task = str(card["task"]["name"])
            matched = matched_by_task.get(task)
            if not matched:
                continue
            fields, _ = card_patterns(card, args.width, args.minimum_distinct, minimum_nonspace)
            card_hash = digest_bytes(str(card["id"]).encode("utf-8"))
            for field, field_patterns in fields.items():
                hits = field_patterns & matched
                if not hits:
                    continue
                affected[task][field].add(card_hash)
                key = f"{task}:{card_hash}:{field}"
                private_hits[key] = {
                    "task": task,
                    "card_id_sha256": card_hash,
                    "field": field,
                    "matched_span_sha256": sorted(digest_bytes(hit) for hit in hits),
                }

    for task, fields in affected.items():
        union = set().union(*fields.values())
        task_scan[task]["affected_cards"] = len(union)
        task_scan[task]["affected_card_fields"] = {
            field: len(card_hashes) for field, card_hashes in sorted(fields.items())
        }

    prepared_tasks = sum(bool(row["prepared_text_available"]) for row in task_scan.values())
    total_matches = sum(
        int(row["matched_patterns"] or 0) for row in task_scan.values()
    )
    total_affected = sum(
        int(row["affected_cards"] or 0) for row in task_scan.values()
    )
    status = "PARTIAL_COVERAGE"
    if prepared_tasks == len(task_scan):
        status = "FULL_COVERAGE_MATCHES_REQUIRE_REVIEW" if total_matches else "FULL_COVERAGE_NO_MATCHES"
    elif total_matches:
        status = "PARTIAL_COVERAGE_MATCHES_REQUIRE_REVIEW"

    public = {
        "protocol": "release-content-scan-v1",
        "status": status,
        "input": {
            "cards_path": args.cards.name,
            "cards_sha256": args.expected_cards_sha256,
            "cards_rows": rows,
        },
        "configuration": {
            "window_bytes": args.width,
            "minimum_distinct_bytes": args.minimum_distinct,
            "minimum_nonspace_bytes": minimum_nonspace,
            "fields": ["stdout_tail", "code_literal_or_comment"],
            "source_suffixes": sorted(TEXT_SUFFIXES),
            "matcher": args.matcher,
        },
        "coverage": {
            "tasks_total": len(task_scan),
            "tasks_scanned": prepared_tasks,
            "tasks_unscanned": len(task_scan) - prepared_tasks,
            "unscanned_tasks": sorted(
                task for task, row in task_scan.items() if not row["prepared_text_available"]
            ),
        },
        "totals": {
            "candidate_patterns": sum(row["candidate_patterns"] for row in task_scan.values()),
            "matched_patterns": total_matches,
            "affected_card_sum_across_tasks": total_affected,
            "parser_failures": sum(row["parser_failures"] for row in task_scan.values()),
        },
        "tasks": task_scan,
        "scope": {
            "source_values_emitted": False,
            "candidate_identities_emitted": False,
            "matched_spans_emitted": False,
            "absolute_source_paths_emitted": False,
            "prospective_resources_read": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
            "code_coverage": "decoded string/bytes literals, literal containers, and comments",
            "stdout_coverage": "all fixed-width windows within lines",
        },
    }
    private = {
        "protocol": "release-content-scan-private-manifest-v1",
        "cards_sha256": args.expected_cards_sha256,
        "source_manifests": private_sources,
        "hits": [private_hits[key] for key in sorted(private_hits)],
    }
    atomic_json(args.summary, public)
    atomic_json(args.private_manifest, private)
    print(
        "RELEASE_CONTENT_SCAN=PASS "
        f"status={status} tasks={prepared_tasks}/{len(task_scan)} "
        f"patterns={public['totals']['candidate_patterns']} matches={total_matches} "
        f"affected={total_affected} raw_values_emitted=false"
    )
    return public


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--expected-cards-sha256", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--private-manifest", type=Path, required=True)
    parser.add_argument("--width", type=int, default=40)
    parser.add_argument("--minimum-distinct", type=int, default=12)
    parser.add_argument("--minimum-nonspace-fraction", type=float, default=0.6)
    parser.add_argument("--task-timeout-s", type=int, default=3600)
    parser.add_argument("--matcher", choices=("grep", "python"), default="grep")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.width < 16 or args.minimum_distinct < 2:
        raise ScanError("unsafe scan threshold")
    if not 0.0 < args.minimum_nonspace_fraction <= 1.0:
        raise ScanError("invalid nonspace fraction")
    scan(args)


if __name__ == "__main__":
    main()
