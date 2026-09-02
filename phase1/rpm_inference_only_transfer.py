#!/usr/bin/env python3
"""Source-bound, network-free helpers for the RPM prompt-transfer baseline.

This module only renders the published optimized prompt and parses two deterministic
orientations.  It intentionally contains no provider transport, credential loading,
panel selection, outcome access, or model invocation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Mapping


PROMPT_PATH = (
    Path(__file__).resolve().parent
    / "baselines"
    / "rpm_inference_only_optimized_v2.txt"
)
PROMPT_BYTES = 1950
PROMPT_SHA256 = "d64763172087a4243ddfa3ff364fad071c552af0783e5786a301a37bc338ff96"
PLACEHOLDER_COUNTS = {
    "{task_desc}": 1,
    "{context_text}": 2,
    "{plan_A}": 1,
    "{code_A}": 1,
    "{plan_B}": 1,
    "{code_B}": 1,
}
BOXED_CHOICE = re.compile(r"\\boxed\s*\{\s*([AB])\s*\}", re.IGNORECASE)
TRAILING_PUNCTUATION = re.compile(r"^[\s.!]*$")


class RPMTransferError(RuntimeError):
    """Raised when the frozen transfer representation drifts or is ambiguous."""


@dataclass(frozen=True)
class CandidateText:
    """Decision-time text for one candidate, excluding its execution outcome."""

    plan: str
    code: str


@dataclass(frozen=True)
class ParsedChoice:
    """One strict orientation readout."""

    choice: str | None
    status: str


@dataclass(frozen=True)
class ReconciledChoice:
    """Orientation-consistent winner in canonical candidate order."""

    winner_index: int | None
    status: str


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RPMTransferError(message)


def _required_text(value: object, label: str) -> str:
    require(isinstance(value, str), f"{label} must be text")
    require(bool(value.strip()), f"{label} must be nonempty")
    require("\x00" not in value, f"{label} contains NUL")
    return value


def load_frozen_prompt(path: Path = PROMPT_PATH) -> str:
    """Load the exact prompt extracted from the arXiv v2 TeX source."""

    require(path.is_file() and not path.is_symlink(), "unsafe or absent prompt file")
    raw = path.read_bytes()
    require(len(raw) == PROMPT_BYTES, "RPM prompt byte-length drift")
    require(hashlib.sha256(raw).hexdigest() == PROMPT_SHA256, "RPM prompt SHA-256 drift")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RPMTransferError("RPM prompt is not UTF-8") from error
    for placeholder, expected in PLACEHOLDER_COUNTS.items():
        require(text.count(placeholder) == expected, f"RPM placeholder drift: {placeholder}")
    return text


def render_prompt(
    *,
    task_desc: str,
    context_text: str,
    candidate_a: CandidateText,
    candidate_b: CandidateText,
    template: str | None = None,
) -> str:
    """Render one displayed orientation without truncating or inferring missing fields."""

    source = load_frozen_prompt() if template is None else template
    for placeholder, expected in PLACEHOLDER_COUNTS.items():
        require(source.count(placeholder) == expected, f"template placeholder drift: {placeholder}")
    replacements: Mapping[str, str] = {
        "{task_desc}": _required_text(task_desc, "task_desc"),
        "{context_text}": _required_text(context_text, "context_text"),
        "{plan_A}": _required_text(candidate_a.plan, "candidate_a.plan"),
        "{code_A}": _required_text(candidate_a.code, "candidate_a.code"),
        "{plan_B}": _required_text(candidate_b.plan, "candidate_b.plan"),
        "{code_B}": _required_text(candidate_b.code, "candidate_b.code"),
    }
    rendered = source
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def render_orientations(
    *,
    task_desc: str,
    context_text: str,
    first: CandidateText,
    second: CandidateText,
) -> dict[str, str]:
    """Render canonical AB and swapped BA requests from identical information."""

    return {
        "AB": render_prompt(
            task_desc=task_desc,
            context_text=context_text,
            candidate_a=first,
            candidate_b=second,
        ),
        "BA": render_prompt(
            task_desc=task_desc,
            context_text=context_text,
            candidate_a=second,
            candidate_b=first,
        ),
    }


def parse_boxed_choice(content: object) -> ParsedChoice:
    """Accept exactly one terminal boxed A/B; never salvage hidden reasoning."""

    if not isinstance(content, str) or not content.strip():
        return ParsedChoice(None, "missing_final_content")
    matches = list(BOXED_CHOICE.finditer(content))
    if len(matches) != 1:
        return ParsedChoice(None, "not_exactly_one_boxed_choice")
    match = matches[0]
    if TRAILING_PUNCTUATION.fullmatch(content[match.end() :]) is None:
        return ParsedChoice(None, "boxed_choice_not_terminal")
    return ParsedChoice(match.group(1).upper(), "parsed")


def reconcile_orientations(ab_content: object, ba_content: object) -> ReconciledChoice:
    """Map displayed choices back to canonical order and abstain on disagreement."""

    ab = parse_boxed_choice(ab_content)
    ba = parse_boxed_choice(ba_content)
    if ab.choice is None or ba.choice is None:
        return ReconciledChoice(None, f"incomplete:{ab.status}:{ba.status}")
    ab_index = 0 if ab.choice == "A" else 1
    ba_index = 1 if ba.choice == "A" else 0
    if ab_index != ba_index:
        return ReconciledChoice(None, "position_disagreement")
    return ReconciledChoice(ab_index, "orientation_consistent")
