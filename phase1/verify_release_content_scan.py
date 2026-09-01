"""Independent aggregate verifier for release-content-scan-v1."""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import tokenize
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SUFFIXES = {".csv", ".json", ".jsonl", ".txt", ".tsv", ".yaml", ".yml"}


class VerifyError(RuntimeError):
    pass


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def byte_hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def qualifies(value: bytes, distinct: int, nonspace: int) -> bool:
    return (
        len(set(value)) >= distinct
        and sum(character not in (32, 9) for character in value) >= nonspace
        and not any(character < 32 and character != 9 for character in value)
        and any(
            48 <= character <= 57
            or 65 <= character <= 90
            or 97 <= character <= 122
            or character >= 128
            for character in value
        )
    )


def slices(value: str | bytes, width: int, distinct: int, nonspace: int) -> Iterable[bytes]:
    encoded = value.encode("utf-8") if isinstance(value, str) else value
    for line in encoded.splitlines():
        for start in range(max(0, len(line) - width + 1)):
            piece = line[start : start + width]
            if qualifies(piece, distinct, nonspace):
                yield piece


def independent_fragments(code: str) -> tuple[list[str | bytes], list[str], bool]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(code)
    parent_of = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    literals: list[str | bytes] = []
    for node in ast.walk(tree):
        if type(node) is ast.Constant and isinstance(node.value, (str, bytes)):
            literals.append(node.value)
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)) and not isinstance(
            parent_of.get(node), (ast.List, ast.Tuple, ast.Set, ast.Dict)
        ):
            try:
                ast.literal_eval(node)
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                continue
            segment = ast.get_source_segment(code, node)
            if segment:
                literals.append(segment)
    comments = []
    token_ok = True
    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        comments.extend(token.string[1:] for token in tokens if token.type == tokenize.COMMENT)
    except (tokenize.TokenError, IndentationError):
        token_ok = False
    return literals, comments, token_ok


def independent_card_patterns(
    card: dict[str, Any], width: int, distinct: int, nonspace: int
) -> tuple[dict[str, set[bytes]], bool]:
    output = {"stdout_tail": set(), "code_literal_or_comment": set()}
    tail = str((card.get("obs") or {}).get("stdout_tail") or "")
    output["stdout_tail"].update(slices(tail, width, distinct, nonspace))
    parser_ok = True
    try:
        literals, comments, token_ok = independent_fragments(str(card.get("code") or ""))
    except SyntaxError:
        literals, comments, token_ok, parser_ok = [], [], False, False
    for value in literals:
        output["code_literal_or_comment"].update(slices(value, width, distinct, nonspace))
    for value in comments:
        output["code_literal_or_comment"].update(slices(value, width, distinct, nonspace))
    return output, parser_ok and token_ok


def read_patterns(path: Path, width: int) -> set[bytes]:
    values = set()
    with path.open("rb") as handle:
        for number, line in enumerate(handle, 1):
            value = line[:-1] if line.endswith(b"\n") else line
            if len(value) != width:
                raise VerifyError(f"bad fixed-width record at {path}:{number}")
            values.add(value)
    return values


def text_sources(root: Path, task: str) -> list[Path]:
    prepared = root / task / "prepared"
    if not prepared.is_dir():
        return []
    return sorted(
        path for path in prepared.rglob("*") if path.is_file() and path.suffix.lower() in SUFFIXES
    )


def manifest(files: list[Path], prepared: Path) -> tuple[list[dict[str, Any]], str]:
    records = [
        {
            "relative_path": path.relative_to(prepared).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": file_hash(path),
        }
        for path in files
    ]
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return records, byte_hash(encoded)


def verify_source_matches(matches: set[bytes], files: list[Path], width: int) -> None:
    if len(matches) > 10_000:
        raise VerifyError("too many source matches for bounded independent verification")
    remaining = set(matches)
    overlap = width - 1
    for path in files:
        carry = b""
        with path.open("rb") as handle:
            while remaining:
                block = handle.read(32 * 1024 * 1024)
                if not block:
                    break
                data = carry + block
                for pattern in tuple(remaining):
                    if pattern in data:
                        remaining.remove(pattern)
                carry = data[-overlap:] if overlap else b""
        if not remaining:
            return
    if remaining:
        raise VerifyError(f"{len(remaining)} matched patterns not independently found in sources")


def reject_absolute_strings(value: Any) -> None:
    if isinstance(value, str):
        if value.startswith(("/", "\\")) or (len(value) >= 3 and value[1:3] in (":\\", ":/")):
            raise VerifyError("public summary contains an absolute path")
    elif isinstance(value, list):
        for item in value:
            reject_absolute_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            reject_absolute_strings(item)


def verify(args: argparse.Namespace) -> dict[str, Any]:
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    private = json.loads(args.private_manifest.read_text(encoding="utf-8"))
    if summary.get("protocol") != "release-content-scan-v1":
        raise VerifyError("unexpected public protocol")
    if private.get("protocol") != "release-content-scan-private-manifest-v1":
        raise VerifyError("unexpected private protocol")
    reject_absolute_strings(summary)
    expected_sha = summary["input"]["cards_sha256"]
    if file_hash(args.cards) != expected_sha or private.get("cards_sha256") != expected_sha:
        raise VerifyError("cards hash mismatch")
    config = summary["configuration"]
    width = int(config["window_bytes"])
    distinct = int(config["minimum_distinct_bytes"])
    nonspace = int(config["minimum_nonspace_bytes"])

    recomputed_patterns: dict[str, set[bytes]] = defaultdict(set)
    cards_by_task: Counter[str] = Counter()
    parser_failures: Counter[str] = Counter()
    rows = 0
    with args.cards.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            task = str(row["task"]["name"])
            rows += 1
            cards_by_task[task] += 1
            fields, ok = independent_card_patterns(row, width, distinct, nonspace)
            if not ok:
                parser_failures[task] += 1
            recomputed_patterns[task].update(fields["stdout_tail"])
            recomputed_patterns[task].update(fields["code_literal_or_comment"])
    if rows != summary["input"]["cards_rows"]:
        raise VerifyError("card row count mismatch")

    matches_by_task: dict[str, set[bytes]] = {}
    for task in sorted(cards_by_task):
        public_task = summary["tasks"].get(task)
        if public_task is None or public_task["cards"] != cards_by_task[task]:
            raise VerifyError(f"task/card accounting mismatch for {task}")
        if public_task["parser_failures"] != parser_failures[task]:
            raise VerifyError(f"parser accounting mismatch for {task}")
        pattern_path = args.work_dir / "patterns" / f"{task}.patterns"
        recorded_patterns = read_patterns(pattern_path, width)
        if recorded_patterns != recomputed_patterns[task]:
            raise VerifyError(f"candidate pattern set mismatch for {task}")
        if (
            len(recorded_patterns) != public_task["candidate_patterns"]
            or file_hash(pattern_path) != public_task["candidate_pattern_file_sha256"]
        ):
            raise VerifyError(f"candidate pattern receipt mismatch for {task}")

        files = text_sources(args.data_root, task)
        if not files:
            if public_task["prepared_text_available"] or public_task["status"] != "UNSCANNED_NO_PREPARED_TEXT":
                raise VerifyError(f"missing-source status mismatch for {task}")
            continue
        if not public_task["prepared_text_available"]:
            raise VerifyError(f"prepared source omitted for {task}")
        source_records, source_sha = manifest(files, args.data_root / task / "prepared")
        if private["source_manifests"].get(task) != source_records:
            raise VerifyError(f"private source manifest mismatch for {task}")
        if (
            source_sha != public_task["source_manifest_sha256"]
            or len(files) != public_task["source_files"]
            or sum(record["bytes"] for record in source_records) != public_task["source_bytes"]
        ):
            raise VerifyError(f"public source receipt mismatch for {task}")

        match_path = args.work_dir / "matches" / f"{task}.unique"
        matches = read_patterns(match_path, width)
        if not matches.issubset(recorded_patterns):
            raise VerifyError(f"source match not in candidate set for {task}")
        if (
            len(matches) != public_task["matched_patterns"]
            or file_hash(match_path) != public_task["matched_pattern_file_sha256"]
        ):
            raise VerifyError(f"match receipt mismatch for {task}")
        verify_source_matches(matches, files, width)
        receipt_path = args.work_dir / "task_receipts" / f"{task}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            receipt.get("protocol") != "release-content-scan-task-receipt-v1"
            or receipt.get("matched_patterns") != len(matches)
            or receipt.get("unique_match_sha256") != file_hash(match_path)
            or file_hash(receipt_path) != public_task["task_receipt_sha256"]
            or receipt.get("matcher_rc") != public_task["matcher_rc"]
        ):
            raise VerifyError(f"task receipt mismatch for {task}")
        matches_by_task[task] = matches

    affected: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"stdout_tail": set(), "code_literal_or_comment": set()}
    )
    private_hits: dict[str, dict[str, Any]] = {}
    with args.cards.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            task = str(row["task"]["name"])
            matches = matches_by_task.get(task)
            if not matches:
                continue
            fields, _ = independent_card_patterns(row, width, distinct, nonspace)
            card_hash = byte_hash(str(row["id"]).encode("utf-8"))
            for field, candidates in fields.items():
                hits = candidates & matches
                if not hits:
                    continue
                affected[task][field].add(card_hash)
                key = f"{task}:{card_hash}:{field}"
                private_hits[key] = {
                    "task": task,
                    "card_id_sha256": card_hash,
                    "field": field,
                    "matched_span_sha256": sorted(byte_hash(hit) for hit in hits),
                }

    for task, public_task in summary["tasks"].items():
        if not public_task["prepared_text_available"]:
            continue
        fields = affected[task]
        expected_cards = len(set().union(*fields.values()))
        expected_fields = {field: len(values) for field, values in sorted(fields.items())}
        if expected_cards != public_task["affected_cards"] or expected_fields != public_task["affected_card_fields"]:
            raise VerifyError(f"affected-card aggregate mismatch for {task}")
    expected_private_hits = [private_hits[key] for key in sorted(private_hits)]
    if private.get("hits") != expected_private_hits:
        raise VerifyError("private hashed hit manifest mismatch")

    scanned = sum(row["prepared_text_available"] for row in summary["tasks"].values())
    total_patterns = sum(row["candidate_patterns"] for row in summary["tasks"].values())
    total_matches = sum(int(row["matched_patterns"] or 0) for row in summary["tasks"].values())
    total_affected = sum(int(row["affected_cards"] or 0) for row in summary["tasks"].values())
    if summary["coverage"] != {
        "tasks_total": len(cards_by_task),
        "tasks_scanned": scanned,
        "tasks_unscanned": len(cards_by_task) - scanned,
        "unscanned_tasks": sorted(
            task for task, row in summary["tasks"].items() if not row["prepared_text_available"]
        ),
    }:
        raise VerifyError("coverage totals mismatch")
    if summary["totals"] != {
        "candidate_patterns": total_patterns,
        "matched_patterns": total_matches,
        "affected_card_sum_across_tasks": total_affected,
        "parser_failures": sum(parser_failures.values()),
    }:
        raise VerifyError("scan totals mismatch")

    receipt = {
        "protocol": "release-content-scan-independent-verification-v1",
        "status": "PASS",
        "summary_sha256": file_hash(args.summary),
        "private_manifest_sha256": file_hash(args.private_manifest),
        "cards_sha256": expected_sha,
        "cards_rows": rows,
        "tasks_total": len(cards_by_task),
        "tasks_scanned": scanned,
        "candidate_patterns": total_patterns,
        "matched_patterns": total_matches,
        "affected_card_sum_across_tasks": total_affected,
        "source_values_emitted": False,
        "candidate_identities_emitted": False,
        "prospective_resources_read": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(args.output, 0o600)
    print(
        "RELEASE_CONTENT_SCAN_VERIFIER=PASS "
        f"tasks={scanned}/{len(cards_by_task)} patterns={total_patterns} "
        f"matches={total_matches} affected={total_affected} raw_values_emitted=false"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--private-manifest", type=Path, required=True)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
