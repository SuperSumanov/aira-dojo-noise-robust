from __future__ import annotations

import ast
from pathlib import Path


def test_capability_probe_never_opens_private_or_test_paths() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "balanced_continuation_capability_probe.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    lowered = "\n".join(string_literals).lower()
    assert "/workspace/data" in lowered
    assert "dsearch" not in lowered
    assert "dval" not in lowered
    assert "answer.csv" not in lowered
    assert "test.csv" not in lowered
