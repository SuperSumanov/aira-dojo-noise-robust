# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Separate a response envelope from Python without scanning inside valid code.

This function does not repair, execute, rank or otherwise edit a program. It
only identifies source candidates. Callers retain their syntax validation and
formatting policy. Inline backticks in Python strings are not Markdown fences.
"""
import re

_OPEN = re.compile(r"^[ ]{0,3}(`{3,})([^`]*)$")


def python_code_blocks(text: str) -> list[str]:
    """Return complete Python/unlabelled fenced blocks, or unchanged raw Python.

    A fence must occupy its own line (at most three leading spaces). A closing
    fence has at least the opening width and no non-whitespace suffix. Unknown
    language blocks are skipped as complete blocks, not searched recursively.
    Unclosed fences fail closed, including after an earlier complete block.
    The returned source bytes, including line endings, are unchanged.
    """
    if not isinstance(text, str):
        raise TypeError("Expected response text")
    if not text.strip():
        return []
    if text.strip():
        try:
            compile(text, "<response>", "exec")
        except (SyntaxError, ValueError):
            pass
        else:
            return [text]

    blocks: list[str] = []
    width = 0
    language = ""
    body: list[str] = []
    saw_fence = False
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if not width:
            match = _OPEN.fullmatch(content)
            if match:
                saw_fence = True
                width = len(match[1])
                language = match[2].strip().lower()
                body = []
        elif re.fullmatch(r"[ ]{0,3}`{" + str(width) + r",}[ \t]*", content):
            source = "".join(body)
            if language in ("", "python") and source.strip():
                blocks.append(source)
            width = 0
            body = []
        else:
            body.append(line)
    if width:
        return []
    if not saw_fence:
        return [text]
    return blocks
