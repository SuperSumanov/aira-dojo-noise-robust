#!/usr/bin/env python3
"""Deterministically wrap test-facing prediction calls without rewriting their body."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


METHODS = frozenset({"predict", "predict_proba", "decision_function"})
IMPORT_LINE = "from scoreable_prediction_tap_runtime import capture as __spt_capture__\n"
RESERVED_NAME = "__spt_capture__"


@dataclass(frozen=True)
class Site:
    method: str
    callsite: str
    argument: str
    start_byte: int
    end_byte: int


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def byte_line_offsets(source: bytes) -> list[int]:
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def absolute_byte(offsets: list[int], line: int, column: int) -> int:
    if line < 1 or line >= len(offsets):
        raise RuntimeError(f"invalid source line: {line}")
    return offsets[line - 1] + column


def identifiers(node: ast.AST) -> set[str]:
    values: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            values.add(child.id.lower())
        elif isinstance(child, ast.Attribute):
            values.add(child.attr.lower())
    return values


def test_facing(node: ast.AST) -> bool:
    # Precision-first frozen rule.  It intentionally abstains from opaque aliases such as X2.
    return any("test" in value or "infer" in value for value in identifiers(node))


def import_insertion_line(tree: ast.Module) -> int:
    line = 0
    body = tree.body
    index = 0
    if body and isinstance(body[0], ast.Expr):
        value = body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            line = int(body[0].end_lineno or body[0].lineno)
            index = 1
    while index < len(body):
        node = body[index]
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            line = int(node.end_lineno or node.lineno)
            index += 1
        else:
            break
    return line


def discover(source_text: str) -> tuple[ast.Module, list[Site]]:
    if "candidate_probe.csv" in source_text:
        raise RuntimeError("reserved probe artifact name already present")
    tree = ast.parse(source_text)
    if RESERVED_NAME.lower() in identifiers(tree):
        raise RuntimeError(f"reserved instrumentation name already present: {RESERVED_NAME}")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "scoreable_prediction_tap_runtime":
            raise RuntimeError("scoreable prediction tap runtime already imported")
    source = source_text.encode("utf-8")
    offsets = byte_line_offsets(source)
    sites: list[Site] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in METHODS or not node.args or not test_facing(node.args[0]):
            continue
        if None in (node.end_lineno, node.end_col_offset):
            raise RuntimeError("AST lacks end positions")
        start = absolute_byte(offsets, node.lineno, node.col_offset)
        end = absolute_byte(offsets, int(node.end_lineno), int(node.end_col_offset))
        argument = ast.get_source_segment(source_text, node.args[0]) or ast.unparse(node.args[0])
        sites.append(
            Site(
                method=node.func.attr,
                callsite=f"L{node.lineno}C{node.col_offset}",
                argument=argument,
                start_byte=start,
                end_byte=end,
            )
        )
    sites.sort(key=lambda item: (item.start_byte, item.end_byte))
    for left, right in zip(sites, sites[1:]):
        if left.end_byte > right.start_byte:
            raise RuntimeError(f"overlapping prediction sites: {left.callsite}, {right.callsite}")
    return tree, sites


def instrument(source_text: str) -> tuple[str, dict]:
    tree, sites = discover(source_text)
    if not sites:
        raise RuntimeError("no precision-qualified test-facing prediction call")
    source = source_text.encode("utf-8")
    edits: list[tuple[int, bytes]] = []
    for site in sites:
        prefix = b"__spt_capture__(("
        suffix = (
            b"), "
            + json.dumps(site.method).encode("utf-8")
            + b", "
            + json.dumps(site.callsite).encode("utf-8")
            + b", "
            + json.dumps(site.argument).encode("utf-8")
            + b")"
        )
        edits.append((site.start_byte, prefix))
        edits.append((site.end_byte, suffix))
    for offset, value in sorted(edits, key=lambda item: item[0], reverse=True):
        source = source[:offset] + value + source[offset:]

    # Insert after a module docstring and all legal __future__ imports.
    line = import_insertion_line(tree)
    offsets = byte_line_offsets(source_text.encode("utf-8"))
    insertion = offsets[line] if line else 0
    source = source[:insertion] + IMPORT_LINE.encode("utf-8") + source[insertion:]
    output = source.decode("utf-8")
    ast.parse(output)
    audit = {
        "schema_version": 1,
        "source_sha256": sha256_bytes(source_text.encode("utf-8")),
        "instrumented_sha256": sha256_bytes(source),
        "import_line": line + 1,
        "site_count": len(sites),
        "sites": [asdict(site) for site in sites],
        "claim_boundary": (
            "Text outside one import and call-expression wrappers is byte-preserved; runtime "
            "purity and final output equality still require execution checks."
        ),
    }
    return output, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.audit.exists():
        raise RuntimeError("refusing existing output/audit")
    source = args.input.read_text(encoding="utf-8")
    output, audit = instrument(source)
    args.output.write_text(output, encoding="utf-8", newline="")
    args.audit.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )
    print(f"SCOREABLE_PREDICTION_TAP_INSTRUMENTED sites={audit['site_count']}")


if __name__ == "__main__":
    main()
