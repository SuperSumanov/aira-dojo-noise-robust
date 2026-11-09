"""Response parsing, cache version, and atomic JSON output for hindsight generation."""

import ast
import json
from pathlib import Path
import re
import tempfile

VERSION = 9


def atomic_json(path: Path, value: object) -> None:
    """Write JSON to a sibling temporary file, then replace the destination to preserve complete cache entries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def parts(text: str) -> tuple[str, str, re.Match]:
    """Return thinking, answer text, and the sole Python block after checking the plan and Python syntax."""
    thinking, delimiter, answer = text.partition("</think>")
    if not delimiter or not thinking.removeprefix("<think>").strip():
        raise ValueError("Full response requires native thinking and a closing think delimiter")
    blocks = list(re.finditer(r"^```(?:python|py)\s*\n(?P<code>.*?)^```[ \t]*$", answer, re.M | re.S))
    if len(blocks) != 1 or len(re.findall(r"^```", answer, re.M)) != 2:
        raise ValueError("Full response requires exactly one fenced Python program")
    block = blocks[0]
    if not answer[: block.start()].strip():
        raise ValueError("Full response requires a plan before the Python program")
    ast.parse(block.group("code"))
    return thinking, answer, block
