#!/usr/bin/env python3
"""Build a result-blind historical context for the RPM prompt-transfer baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


PROTOCOL = "decision-corpus-rpm-decision-time-context-v1"
OUTPUT_SCHEMA = "decision-corpus-rpm-context-output-v1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:or-v1-|ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
EMPTY_CONTEXT = '[{"context_status":"NO_PRIOR_EXECUTED_SCORED_NODE"}]'
SOURCE_FIELDS = {"protocol", "run_id_sha256", "task", "candidates", "nodes"}
CANDIDATE_FIELDS = {"candidate_id_sha256", "step"}
NODE_FIELDS = {
    "node_id_sha256",
    "run_id_sha256",
    "task",
    "step",
    "operator",
    "code",
    "self_reported_validation",
    "higher_is_better",
}


class RPMContextError(RuntimeError):
    pass


@dataclass(frozen=True)
class CandidateRef:
    candidate_id_sha256: str
    step: int


@dataclass(frozen=True)
class ExecutedNode:
    node_id_sha256: str
    run_id_sha256: str
    task: str
    step: int
    operator: str
    code: str
    self_reported_validation: float
    higher_is_better: bool


@dataclass(frozen=True)
class ContextBuild:
    cutoff_step: int
    node_count: int
    context_text: str
    context_sha256: str

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": OUTPUT_SCHEMA,
            "protocol": PROTOCOL,
            "cutoff_step": self.cutoff_step,
            "node_count": self.node_count,
            "ordering": "journal_step_desc_then_node_sha256_asc",
            "score_source": "self_reported_validation",
            "identity_fields_emitted": False,
            "context_text": self.context_text,
            "context_sha256": self.context_sha256,
            "token_packing_applied": False,
            "live_call_authorized": False,
        }


def _sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise RPMContextError(f"invalid SHA-256: {where}")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RPMContextError(f"nonempty text required: {where}")
    return value


def _step(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RPMContextError(f"nonnegative integer step required: {where}")
    return value


def _finite(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RPMContextError(f"finite numeric value required: {where}")
    result = float(value)
    if not math.isfinite(result):
        raise RPMContextError(f"finite numeric value required: {where}")
    return result


def reject_credential_shape(text: str, where: str) -> None:
    if CREDENTIAL.search(text.encode("utf-8")):
        raise RPMContextError(f"credential-shaped content refused: {where}")


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise RPMContextError(f"credential-shaped source refused: {path.name}")
            overlap = payload[-256:]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _validated_candidates(values: Sequence[CandidateRef]) -> tuple[set[str], int]:
    if len(values) < 2:
        raise RPMContextError("complete sibling candidate set must contain at least two candidates")
    identities: set[str] = set()
    steps: list[int] = []
    for index, value in enumerate(values):
        identity = _sha(value.candidate_id_sha256, f"candidate {index}")
        if identity in identities:
            raise RPMContextError("duplicate candidate identity")
        identities.add(identity)
        steps.append(_step(value.step, f"candidate {index}"))
    return identities, min(steps)


def select_context_nodes(
    *,
    run_id_sha256: str,
    task: str,
    candidates: Sequence[CandidateRef],
    nodes: Iterable[ExecutedNode],
) -> tuple[int, list[ExecutedNode]]:
    run_id_sha256 = _sha(run_id_sha256, "decision run")
    task = _text(task, "decision task")
    candidate_ids, cutoff = _validated_candidates(candidates)
    selected: list[ExecutedNode] = []
    seen: set[str] = set()
    for index, node in enumerate(nodes):
        identity = _sha(node.node_id_sha256, f"history node {index}")
        if identity in seen:
            raise RPMContextError("duplicate history node identity")
        seen.add(identity)
        if identity in candidate_ids:
            raise RPMContextError("candidate record present in history input")
        node_run = _sha(node.run_id_sha256, f"history node {index} run")
        node_task = _text(node.task, f"history node {index} task")
        node_step = _step(node.step, f"history node {index}")
        if node_run != run_id_sha256:
            raise RPMContextError("cross-run history node present")
        if node_task != task:
            raise RPMContextError("cross-task history node present")
        if node_step >= cutoff:
            raise RPMContextError("same-step or post-decision history node present")
        operator = _text(node.operator, f"history node {index} operator")
        code = _text(node.code, f"history node {index} code")
        reject_credential_shape(operator, f"history node {index} operator")
        reject_credential_shape(code, f"history node {index} code")
        score = _finite(node.self_reported_validation, f"history node {index} score")
        if not isinstance(node.higher_is_better, bool):
            raise RPMContextError(f"boolean optimization direction required: history node {index}")
        selected.append(
            ExecutedNode(
                node_id_sha256=identity,
                run_id_sha256=node_run,
                task=node_task,
                step=node_step,
                operator=operator,
                code=code,
                self_reported_validation=score,
                higher_is_better=node.higher_is_better,
            )
        )
    selected.sort(key=lambda node: (-node.step, node.node_id_sha256))
    return cutoff, selected


def serialize_context_node(node: ExecutedNode, rank: int) -> str:
    payload = {
        "code": node.code,
        "context_rank": rank,
        "journal_step": node.step,
        "operator": node.operator,
        "optimization_direction": (
            "higher_is_better" if node.higher_is_better else "lower_is_better"
        ),
        "score_type": "self_reported_validation",
        "self_reported_validation": node.self_reported_validation,
    }
    return canonical_json(payload).decode("utf-8")


def build_context(
    *,
    run_id_sha256: str,
    task: str,
    candidates: Sequence[CandidateRef],
    nodes: Iterable[ExecutedNode],
) -> ContextBuild:
    reject_credential_shape(task, "decision task")
    cutoff, selected = select_context_nodes(
        run_id_sha256=run_id_sha256,
        task=task,
        candidates=candidates,
        nodes=nodes,
    )
    context = (
        "\n".join(serialize_context_node(node, rank) for rank, node in enumerate(selected, 1))
        if selected
        else EMPTY_CONTEXT
    )
    return ContextBuild(
        cutoff_step=cutoff,
        node_count=len(selected),
        context_text=context,
        context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
    )


def load_source(path: Path) -> tuple[str, str, list[CandidateRef], list[ExecutedNode]]:
    scan_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RPMContextError("invalid source JSON") from exc
    if not isinstance(value, dict) or set(value) != SOURCE_FIELDS:
        raise RPMContextError("source schema mismatch")
    if value.get("protocol") != PROTOCOL:
        raise RPMContextError("source protocol mismatch")
    raw_candidates = value.get("candidates")
    raw_nodes = value.get("nodes")
    if not isinstance(raw_candidates, list) or not isinstance(raw_nodes, list):
        raise RPMContextError("source candidates/nodes must be arrays")
    candidates: list[CandidateRef] = []
    for index, raw in enumerate(raw_candidates):
        if not isinstance(raw, dict) or set(raw) != CANDIDATE_FIELDS:
            raise RPMContextError(f"candidate source schema mismatch: {index}")
        candidates.append(CandidateRef(raw["candidate_id_sha256"], raw["step"]))
    nodes: list[ExecutedNode] = []
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict) or set(raw) != NODE_FIELDS:
            raise RPMContextError(f"history source schema mismatch: {index}")
        nodes.append(ExecutedNode(**raw))
    return value["run_id_sha256"], value["task"], candidates, nodes


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RPMContextError("output already exists")
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
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    source = Path(arguments.source).resolve()
    output = Path(arguments.output).resolve()
    if not source.is_file() or file_sha256(source) != _sha(
        arguments.expected_source_sha256, "expected source"
    ):
        raise RPMContextError("source hash mismatch")
    run_id, task, candidates, nodes = load_source(source)
    result = build_context(
        run_id_sha256=run_id, task=task, candidates=candidates, nodes=nodes
    )
    atomic_write(output, result.to_json())
    print(f"status=RPM_CONTEXT_BUILD_PASS node_count={result.node_count}")


if __name__ == "__main__":
    main()
