"""Parse in-memory responses and write explicitly requested JSON artifacts.

parts reads response text and returns thinking, answer, and a Python block.
write_json writes its value to the given file, creating its parent directory.
"""

import ast
import json
from pathlib import Path
import re


def write_json(path: Path, value: object) -> None:
    """Write a readable JSON file at the supplied destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
