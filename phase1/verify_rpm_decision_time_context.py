#!/usr/bin/env python3
"""Independent verifier for the RPM decision-time context payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any


PROTOCOL = "decision-corpus-rpm-decision-time-context-v1"
OUTPUT_SCHEMA = "decision-corpus-rpm-context-output-v1"
HEX = re.compile(r"^[0-9a-f]{64}$")
SECRET = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:or-v1-|ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
EMPTY = '[{"context_status":"NO_PRIOR_EXECUTED_SCORED_NODE"}]'
SOURCE_KEYS = {"protocol", "run_id_sha256", "task", "candidates", "nodes"}
CANDIDATE_KEYS = {"candidate_id_sha256", "step"}
NODE_KEYS = {
    "node_id_sha256",
    "run_id_sha256",
    "task",
    "step",
    "operator",
    "code",
    "self_reported_validation",
    "higher_is_better",
}


class RPMContextVerificationError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RPMContextVerificationError(message)


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def valid_hash(value: Any, label: str) -> str:
    need(isinstance(value, str) and HEX.fullmatch(value) is not None, f"invalid hash: {label}")
    return value


def scan(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            current = overlap + chunk
            need(SECRET.search(current) is None, f"credential-shaped bytes: {path.name}")
            overlap = current[-256:]


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RPMContextVerificationError(f"invalid JSON: {label}") from exc
    need(isinstance(value, dict), f"object required: {label}")
    return value


def integer_step(value: Any, label: str) -> int:
    need(not isinstance(value, bool) and isinstance(value, int) and value >= 0, f"invalid step: {label}")
    return value


def text(value: Any, label: str) -> str:
    need(isinstance(value, str) and bool(value.strip()), f"invalid text: {label}")
    return value


def compact(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def reconstruct(source: dict[str, Any]) -> dict[str, Any]:
    need(set(source) == SOURCE_KEYS and source.get("protocol") == PROTOCOL, "source schema")
    run_id = valid_hash(source.get("run_id_sha256"), "decision run")
    task = text(source.get("task"), "decision task")
    need(SECRET.search(task.encode("utf-8")) is None, "credential-shaped task")
    raw_candidates = source.get("candidates")
    raw_nodes = source.get("nodes")
    need(isinstance(raw_candidates, list) and len(raw_candidates) >= 2, "candidate array")
    need(isinstance(raw_nodes, list), "node array")

    candidate_ids: set[str] = set()
    candidate_steps: list[int] = []
    for number, candidate in enumerate(raw_candidates):
        need(isinstance(candidate, dict) and set(candidate) == CANDIDATE_KEYS, "candidate schema")
        identity = valid_hash(candidate.get("candidate_id_sha256"), f"candidate {number}")
        need(identity not in candidate_ids, "duplicate candidate")
        candidate_ids.add(identity)
        candidate_steps.append(integer_step(candidate.get("step"), f"candidate {number}"))
    cutoff = min(candidate_steps)

    normalized: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for number, node in enumerate(raw_nodes):
        need(isinstance(node, dict) and set(node) == NODE_KEYS, "history node schema")
        identity = valid_hash(node.get("node_id_sha256"), f"node {number}")
        need(identity not in node_ids and identity not in candidate_ids, "history identity closure")
        node_ids.add(identity)
        need(valid_hash(node.get("run_id_sha256"), f"node {number} run") == run_id, "cross-run node")
        need(text(node.get("task"), f"node {number} task") == task, "cross-task node")
        step = integer_step(node.get("step"), f"node {number}")
        need(step < cutoff, "same-step or post-decision node")
        operator = text(node.get("operator"), f"node {number} operator")
        code = text(node.get("code"), f"node {number} code")
        need(SECRET.search(operator.encode("utf-8")) is None, "credential-shaped operator")
        need(SECRET.search(code.encode("utf-8")) is None, "credential-shaped code")
        score = node.get("self_reported_validation")
        need(
            not isinstance(score, bool)
            and isinstance(score, (int, float))
            and math.isfinite(float(score)),
            "invalid self-reported validation",
        )
        higher = node.get("higher_is_better")
        need(isinstance(higher, bool), "invalid optimization direction")
        normalized.append(
            {
                "identity": identity,
                "step": step,
                "operator": operator,
                "code": code,
                "score": float(score),
                "higher": higher,
            }
        )
    normalized.sort(key=lambda item: (-item["step"], item["identity"]))
    lines = []
    for rank, node in enumerate(normalized, 1):
        lines.append(
            compact(
                {
                    "code": node["code"],
                    "context_rank": rank,
                    "journal_step": node["step"],
                    "operator": node["operator"],
                    "optimization_direction": (
                        "higher_is_better" if node["higher"] else "lower_is_better"
                    ),
                    "score_type": "self_reported_validation",
                    "self_reported_validation": node["score"],
                }
            )
        )
    context = "\n".join(lines) if lines else EMPTY
    return {
        "schema_version": OUTPUT_SCHEMA,
        "protocol": PROTOCOL,
        "cutoff_step": cutoff,
        "node_count": len(normalized),
        "ordering": "journal_step_desc_then_node_sha256_asc",
        "score_source": "self_reported_validation",
        "identity_fields_emitted": False,
        "context_text": context,
        "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
        "token_packing_applied": False,
        "live_call_authorized": False,
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RPMContextVerificationError("verification output already exists")
    payload = json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--expected-candidate-sha256", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    source_path = Path(arguments.source).resolve()
    candidate_path = Path(arguments.candidate).resolve()
    need(source_path.is_file() and candidate_path.is_file(), "input file absent")
    need(
        file_digest(source_path) == valid_hash(arguments.expected_source_sha256, "expected source"),
        "source hash mismatch",
    )
    need(
        file_digest(candidate_path)
        == valid_hash(arguments.expected_candidate_sha256, "expected candidate"),
        "candidate hash mismatch",
    )
    scan(source_path)
    scan(candidate_path)
    source = read_object(source_path, "source")
    candidate = read_object(candidate_path, "candidate")
    expected = reconstruct(source)
    need(candidate == expected, "candidate context differs from independent reconstruction")
    verification = {
        "status": "RPM_CONTEXT_INDEPENDENT_VERIFICATION_PASS",
        "protocol": PROTOCOL,
        "source_sha256": file_digest(source_path),
        "candidate_sha256": file_digest(candidate_path),
        "context_sha256": expected["context_sha256"],
        "node_count": expected["node_count"],
        "identity_fields_emitted": False,
        "external_grade_used": False,
        "candidate_outcome_used": False,
        "live_call_authorized": False,
    }
    atomic_json(Path(arguments.output).resolve(), verification)
    print("status=RPM_CONTEXT_INDEPENDENT_VERIFICATION_PASS")


if __name__ == "__main__":
    main()
