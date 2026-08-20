#!/usr/bin/env python3
"""Deterministic candidate-code graph features for a frozen WL baseline.

This module parses code but never imports or executes it.  Raw identifiers are
hashed before feature names leave the extractor; callers should emit aggregate
diagnostics only.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import io
import json
import keyword
import math
import token
import tokenize
from dataclasses import asdict, dataclass
from typing import Iterable


PROTOCOL = "wl-code-graph-features-v1"
WL_ITERATIONS = 2
MAXIMUM_NODES = 8192
HASHED_DIMENSIONS = 65536


@dataclass(frozen=True)
class GraphDiagnostics:
    mode: str
    nodes: int
    edges_undirected: int
    truncated: bool
    features: int
    feature_mass: int

    def to_dict(self) -> dict[str, int | str | bool]:
        return asdict(self)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()


def _bounded_name(value: object) -> str:
    text = str(value or "").strip().lower()
    return text[:128] if text else "<EMPTY>"


def _ast_label(node: ast.AST) -> str:
    base = type(node).__name__
    if isinstance(node, ast.Name):
        return f"{base}:{_bounded_name(node.id)}"
    if isinstance(node, ast.Attribute):
        return f"{base}:{_bounded_name(node.attr)}"
    if isinstance(node, ast.alias):
        return f"{base}:{_bounded_name(node.name)}:{_bounded_name(node.asname)}"
    if isinstance(node, ast.arg):
        return f"{base}:{_bounded_name(node.arg)}"
    if isinstance(node, ast.keyword):
        return f"{base}:{_bounded_name(node.arg)}"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return f"{base}:{_bounded_name(node.name)}"
    if isinstance(node, ast.Constant):
        value = node.value
        marker = (
            "none"
            if value is None
            else "ellipsis"
            if value is Ellipsis
            else "bool"
            if isinstance(value, bool)
            else "string"
            if isinstance(value, str)
            else "bytes"
            if isinstance(value, bytes)
            else "number"
            if isinstance(value, (int, float, complex))
            else type(value).__name__.lower()
        )
        return f"{base}:{marker}"
    return base


def _append_node(labels: list[str], adjacency: list[list[tuple[str, int]]], label: str) -> int:
    labels.append(_digest(label))
    adjacency.append([])
    return len(labels) - 1


def _ast_graph(code: str, maximum_nodes: int) -> tuple[list[str], list[list[tuple[str, int]]], bool]:
    root = ast.parse(code)
    labels: list[str] = []
    adjacency: list[list[tuple[str, int]]] = []
    truncated = False

    def visit(node: ast.AST) -> int | None:
        nonlocal truncated
        if len(labels) >= maximum_nodes:
            truncated = True
            return None
        current = _append_node(labels, adjacency, _ast_label(node))
        for field, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            for child in children:
                if not isinstance(child, ast.AST):
                    continue
                child_index = visit(child)
                if child_index is None:
                    continue
                adjacency[current].append((f"out:{field}", child_index))
                adjacency[child_index].append((f"in:{field}", current))
        return current

    visit(root)
    return labels, adjacency, truncated


def _token_label(item: tokenize.TokenInfo) -> str:
    if item.type == token.NAME:
        value = item.string.lower()
        return f"NAME:{value}" if keyword.iskeyword(value) else f"NAME:{_bounded_name(value)}"
    if item.type == token.NUMBER:
        return "NUMBER"
    if item.type == token.STRING:
        return "STRING"
    if item.type == token.OP:
        return f"OP:{item.string}"
    return tokenize.tok_name.get(item.type, str(item.type))


def _sequence_graph(labels_raw: Iterable[str], maximum_nodes: int) -> tuple[list[str], list[list[tuple[str, int]]], bool]:
    labels: list[str] = []
    adjacency: list[list[tuple[str, int]]] = []
    truncated = False
    for raw in labels_raw:
        if len(labels) >= maximum_nodes:
            truncated = True
            break
        _append_node(labels, adjacency, raw)
    for index in range(len(labels) - 1):
        adjacency[index].append(("next", index + 1))
        adjacency[index + 1].append(("prev", index))
    return labels, adjacency, truncated


def _token_graph(code: str, maximum_nodes: int) -> tuple[list[str], list[list[tuple[str, int]]], bool]:
    ignored = {tokenize.ENCODING, tokenize.ENDMARKER, tokenize.COMMENT}
    items = tokenize.generate_tokens(io.StringIO(code).readline)
    return _sequence_graph((_token_label(item) for item in items if item.type not in ignored), maximum_nodes)


def _raw_line_label(line: str) -> str:
    spaces = len(line) - len(line.lstrip(" \t"))
    stripped = line.strip()
    categories = collections.Counter(
        "alpha" if char.isalpha() else "digit" if char.isdigit() else "space" if char.isspace() else "punct"
        for char in stripped
    )
    signature = json.dumps(dict(sorted(categories.items())), separators=(",", ":"))
    return f"LINE:{min(spaces, 64)}:{signature}:{_digest(stripped[:256])}"


def _raw_line_graph(code: str, maximum_nodes: int) -> tuple[list[str], list[list[tuple[str, int]]], bool]:
    lines = code.splitlines() or [code]
    return _sequence_graph((_raw_line_label(line) for line in lines), maximum_nodes)


def _extract_graph(code: str, maximum_nodes: int) -> tuple[str, list[str], list[list[tuple[str, int]]], bool]:
    try:
        labels, adjacency, truncated = _ast_graph(code, maximum_nodes)
        mode = "python_ast"
    except (IndentationError, SyntaxError, ValueError, TypeError, MemoryError):
        try:
            labels, adjacency, truncated = _token_graph(code, maximum_nodes)
            mode = "python_token_sequence_graph"
        except (IndentationError, SyntaxError, tokenize.TokenError, UnicodeError, ValueError):
            labels, adjacency, truncated = _raw_line_graph(code, maximum_nodes)
            mode = "raw_line_sequence_graph"
    if not labels:
        labels, adjacency, truncated = _raw_line_graph(code, maximum_nodes)
        mode = "raw_line_sequence_graph"
    return mode, labels, adjacency, truncated


def wl_feature_dict(
    code: str,
    *,
    iterations: int = WL_ITERATIONS,
    maximum_nodes: int = MAXIMUM_NODES,
) -> tuple[dict[str, float], GraphDiagnostics]:
    if not isinstance(code, str) or not code:
        raise ValueError("code must be a non-empty string")
    if iterations < 0 or maximum_nodes < 1:
        raise ValueError("invalid graph configuration")
    mode, labels, adjacency, truncated = _extract_graph(code, maximum_nodes)
    features: collections.Counter[str] = collections.Counter()
    current = list(labels)
    for value in current:
        features[f"h0:{value}"] += 1
    for height in range(1, iterations + 1):
        updated: list[str] = []
        for index, label in enumerate(current):
            neighbours = sorted(f"{edge}:{current[target]}" for edge, target in adjacency[index])
            updated.append(_digest(label + "|" + "|".join(neighbours)))
        current = updated
        for value in current:
            features[f"h{height}:{value}"] += 1
    edge_count = sum(len(items) for items in adjacency) // 2
    diagnostics = GraphDiagnostics(
        mode=mode,
        nodes=len(labels),
        edges_undirected=edge_count,
        truncated=truncated,
        features=len(features),
        feature_mass=int(sum(features.values())),
    )
    return dict(features), diagnostics


def hashed_l2_matrix(
    feature_rows: Iterable[dict[str, float]],
    *,
    n_features: int = HASHED_DIMENSIONS,
):
    from sklearn.feature_extraction import FeatureHasher
    from sklearn.preprocessing import normalize

    if n_features < 2:
        raise ValueError("n_features must be at least two")
    hasher = FeatureHasher(
        n_features=n_features,
        input_type="dict",
        dtype=float,
        alternate_sign=True,
    )
    matrix = hasher.transform(feature_rows).tocsr()
    matrix = normalize(matrix, norm="l2", axis=1, copy=False)
    if matrix.shape[0] and (not math.isfinite(float(matrix.data.sum())) or not all(math.isfinite(float(x)) for x in matrix.data)):
        raise ValueError("non-finite graph matrix")
    return matrix


def aggregate_diagnostics(rows: Iterable[GraphDiagnostics]) -> dict[str, object]:
    values = list(rows)
    if not values:
        raise ValueError("empty graph diagnostics")
    mode_counts = collections.Counter(row.mode for row in values)
    nodes = sorted(row.nodes for row in values)
    return {
        "endpoints": len(values),
        "mode_counts": dict(sorted(mode_counts.items())),
        "truncated_endpoints": sum(row.truncated for row in values),
        "minimum_nodes": nodes[0],
        "median_nodes": nodes[(len(nodes) - 1) // 2],
        "maximum_nodes": nodes[-1],
        "total_feature_mass": sum(row.feature_mass for row in values),
    }
