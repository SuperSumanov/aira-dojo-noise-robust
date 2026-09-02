#!/usr/bin/env python3
"""Deterministic, local-only prefix packing for the RPM prompt transfer.

This module binds a public Qwen3.6-27B repository revision and its tokenizer
artifacts, then packs only complete nodes from the already-frozen Decision Corpus
context order.  It contains no network download, provider transport, credential
loader, panel selection, outcome join, or model invocation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import struct
from typing import Any, Mapping, Sequence

from phase1 import rpm_inference_only_transfer as transfer


PROTOCOL = "decision-corpus-rpm-token-packing-v1"
INPUT_PROTOCOL = "decision-corpus-rpm-token-packing-input-v1"
OUTPUT_SCHEMA = "decision-corpus-rpm-token-packing-output-v1"
CONTEXT_PROTOCOL = "decision-corpus-rpm-decision-time-context-v1"
CONTEXT_SCHEMA = "decision-corpus-rpm-context-output-v1"
MODEL_ID = "Qwen/Qwen3.6-27B"
MODEL_REVISION = "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
CONTEXT_WINDOW_TOKENS = 262_144
OUTPUT_RESERVE_TOKENS = 32_768
PROMPT_TOKEN_LIMIT = CONTEXT_WINDOW_TOKENS - OUTPUT_RESERVE_TOKENS
CHAT_TEMPLATE_BYTES = 7_764
CHAT_TEMPLATE_SHA256 = "e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259"
MISSING_PLAN = "[PLAN_NOT_RECORDED_BY_DECISION_CORPUS]"
NO_PRIOR_CONTEXT = '[{"context_status":"NO_PRIOR_EXECUTED_SCORED_NODE"}]'
NO_FIT_CONTEXT = '[{"context_status":"NO_COMPLETE_PRIOR_NODE_FITS_TOKEN_BUDGET"}]'
EXPECTED_RUNTIME = {
    "transformers": "4.57.1",
    "tokenizers": "0.22.1",
    "huggingface-hub": "0.36.0",
}
REQUIRED_ARTIFACTS: dict[str, tuple[int, str]] = {
    "config.json": (
        4_308,
        "69db4eb7196bc8190813231b3018ca05d8c2e3abc7b1af19d55c157af44a9d9c",
    ),
    "generation_config.json": (
        202,
        "e70c136c1b78ddc1fb0905bac8e733a4dc448d4f852a5dd75143fffc70be550e",
    ),
    "tokenizer_config.json": (
        16_718,
        "5186f0defcd7f232382c7f0aebcd2252d073bb921ab240e407b7ae8745d2b29b",
    ),
    "tokenizer.json": (
        12_807_982,
        "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42",
    ),
    "README.md": (
        62_593,
        "bb936d6da51014f1edc9aa4cf9abf28d98695b7616ad56adfeeebfa752051d3d",
    ),
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:or-v1-|ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
WEIGHT_FILE = re.compile(r"(?:\.safetensors|\.bin|\.pt|\.pth|\.gguf)$", re.IGNORECASE)
INPUT_KEYS = {"protocol", "task_desc", "context", "candidate_first", "candidate_second"}
CANDIDATE_KEYS = {"plan", "code"}
CONTEXT_KEYS = {
    "schema_version",
    "protocol",
    "cutoff_step",
    "node_count",
    "ordering",
    "score_source",
    "identity_fields_emitted",
    "context_text",
    "context_sha256",
    "token_packing_applied",
    "live_call_authorized",
}
CONTEXT_LINE_KEYS = {
    "code",
    "context_rank",
    "journal_step",
    "operator",
    "optimization_direction",
    "score_type",
    "self_reported_validation",
}


class RPMTokenPackingError(RuntimeError):
    """Raised when a frozen artifact, input, tokenizer, or token budget drifts."""


@dataclass(frozen=True)
class PromptMeasure:
    prompt_token_count: int
    prompt_sha256: str
    rendered_chat_sha256: str
    token_ids_sha256: str

    def to_json(self) -> dict[str, Any]:
        return {
            "prompt_token_count": self.prompt_token_count,
            "prompt_sha256": self.prompt_sha256,
            "rendered_chat_sha256": self.rendered_chat_sha256,
            "token_ids_sha256": self.token_ids_sha256,
        }


@dataclass(frozen=True)
class PrefixSelection:
    eligible_node_count: int
    included_node_count: int
    packed_context_text: str
    stop_reason: str
    overflow_at_node_rank: int | None
    orientations: Mapping[str, PromptMeasure]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RPMTokenPackingError(message)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            require(CREDENTIAL.search(payload) is None, f"credential-shaped bytes: {path.name}")
            overlap = payload[-256:]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _hash(value: Any, label: str) -> str:
    require(isinstance(value, str) and SHA256.fullmatch(value) is not None, f"invalid hash: {label}")
    return value


def _text(value: Any, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"nonempty text required: {label}")
    require("\x00" not in value, f"NUL refused: {label}")
    require(CREDENTIAL.search(value.encode("utf-8")) is None, f"credential-shaped text: {label}")
    return value


def _integer(value: Any, label: str) -> int:
    require(not isinstance(value, bool) and isinstance(value, int) and value >= 0, f"invalid integer: {label}")
    return value


def validate_artifact_manifest(
    root: Path, expected: Mapping[str, tuple[int, str]]
) -> dict[str, dict[str, Any]]:
    """Validate a local immutable artifact set without resolving anything online."""

    require(root.is_dir() and not root.is_symlink(), "tokenizer directory absent or symlinked")
    for path in root.rglob("*"):
        if path.is_file() and WEIGHT_FILE.search(path.name):
            raise RPMTokenPackingError(f"model weight file refused: {path.name}")
    observed: dict[str, dict[str, Any]] = {}
    for name, (expected_bytes, expected_sha256) in expected.items():
        path = root / name
        require(path.is_file() and not path.is_symlink(), f"artifact absent or symlinked: {name}")
        actual_bytes = path.stat().st_size
        actual_sha256 = file_sha256(path)
        require(actual_bytes == expected_bytes, f"artifact byte-length drift: {name}")
        require(actual_sha256 == expected_sha256, f"artifact SHA-256 drift: {name}")
        scan_file(path)
        observed[name] = {"bytes": actual_bytes, "sha256": actual_sha256}
    return observed


def validate_tokenizer_snapshot(root: Path) -> dict[str, Any]:
    artifacts = validate_artifact_manifest(root, REQUIRED_ARTIFACTS)
    try:
        config = json.loads((root / "tokenizer_config.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RPMTokenPackingError("invalid tokenizer_config.json") from error
    require(isinstance(config, dict), "tokenizer config must be an object")
    template = config.get("chat_template")
    require(isinstance(template, str), "chat template must be text")
    template_bytes = template.encode("utf-8")
    require(len(template_bytes) == CHAT_TEMPLATE_BYTES, "chat template byte-length drift")
    require(hashlib.sha256(template_bytes).hexdigest() == CHAT_TEMPLATE_SHA256, "chat template SHA-256 drift")
    require(config.get("tokenizer_class") == "Qwen2Tokenizer", "tokenizer class drift")
    require(config.get("model_max_length") == CONTEXT_WINDOW_TOKENS, "model_max_length drift")
    require(config.get("bos_token") is None, "BOS token drift")
    require(config.get("eos_token") == "<|im_end|>", "EOS token drift")
    require(config.get("pad_token") == "<|endoftext|>", "PAD token drift")
    return {
        "artifacts": artifacts,
        "chat_template_bytes": len(template_bytes),
        "chat_template_sha256": hashlib.sha256(template_bytes).hexdigest(),
        "tokenizer_class_in_config": config["tokenizer_class"],
        "model_max_length": config["model_max_length"],
        "bos_token": None,
        "eos_token": config["eos_token"],
        "pad_token": config["pad_token"],
    }


def load_local_tokenizer(root: Path) -> tuple[Any, dict[str, str]]:
    versions: dict[str, str] = {}
    for package, expected in EXPECTED_RUNTIME.items():
        try:
            observed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as error:
            raise RPMTokenPackingError(f"required package unavailable: {package}") from error
        require(observed == expected, f"runtime version drift: {package}")
        versions[package] = observed
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RPMTokenPackingError("transformers unavailable") from error
    tokenizer = AutoTokenizer.from_pretrained(
        str(root),
        local_files_only=True,
        trust_remote_code=False,
        use_fast=True,
    )
    require(getattr(tokenizer, "model_max_length", None) == CONTEXT_WINDOW_TOKENS, "loaded model_max_length drift")
    require(getattr(tokenizer, "bos_token", None) is None, "loaded BOS token drift")
    require(getattr(tokenizer, "eos_token", None) == "<|im_end|>", "loaded EOS token drift")
    require(getattr(tokenizer, "pad_token", None) == "<|endoftext|>", "loaded PAD token drift")
    loaded_template = getattr(tokenizer, "chat_template", None)
    require(isinstance(loaded_template, str), "loaded chat template absent")
    require(
        hashlib.sha256(loaded_template.encode("utf-8")).hexdigest() == CHAT_TEMPLATE_SHA256,
        "loaded chat template drift",
    )
    return tokenizer, versions


def _validate_context(value: Any) -> tuple[list[str], bool, str]:
    require(isinstance(value, dict) and set(value) == CONTEXT_KEYS, "context schema mismatch")
    require(value.get("schema_version") == CONTEXT_SCHEMA, "context output schema drift")
    require(value.get("protocol") == CONTEXT_PROTOCOL, "context protocol drift")
    _integer(value.get("cutoff_step"), "context cutoff")
    count = _integer(value.get("node_count"), "context node_count")
    require(value.get("ordering") == "journal_step_desc_then_node_sha256_asc", "context ordering drift")
    require(value.get("score_source") == "self_reported_validation", "context score source drift")
    require(value.get("identity_fields_emitted") is False, "context identity fields emitted")
    require(value.get("token_packing_applied") is False, "context was already token packed")
    require(value.get("live_call_authorized") is False, "context unexpectedly authorizes live calls")
    text = _text(value.get("context_text"), "context_text")
    require(hashlib.sha256(text.encode("utf-8")).hexdigest() == _hash(value.get("context_sha256"), "context"), "context hash drift")
    if count == 0:
        require(text == NO_PRIOR_CONTEXT, "empty-context literal drift")
        return [], True, text
    lines = text.splitlines()
    require(len(lines) == count, "context line count drift")
    for rank, line in enumerate(lines, 1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise RPMTokenPackingError(f"invalid context node JSON: {rank}") from error
        require(isinstance(payload, dict) and set(payload) == CONTEXT_LINE_KEYS, f"context node schema drift: {rank}")
        require(payload.get("context_rank") == rank, f"context rank drift: {rank}")
        _integer(payload.get("journal_step"), f"context journal step: {rank}")
        _text(payload.get("operator"), f"context operator: {rank}")
        _text(payload.get("code"), f"context code: {rank}")
        require(
            payload.get("optimization_direction") in {"higher_is_better", "lower_is_better"},
            f"context optimization direction drift: {rank}",
        )
        require(payload.get("score_type") == "self_reported_validation", f"context score type drift: {rank}")
        score = payload.get("self_reported_validation")
        require(
            not isinstance(score, bool)
            and isinstance(score, (int, float))
            and math.isfinite(float(score)),
            f"context score invalid: {rank}",
        )
        require(canonical_json(payload) == line, f"context node is not canonical JSON: {rank}")
    return lines, False, text


def validate_source(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == INPUT_KEYS, "packing input schema mismatch")
    require(value.get("protocol") == INPUT_PROTOCOL, "packing input protocol mismatch")
    task_desc = _text(value.get("task_desc"), "task_desc")
    candidates = []
    for label in ("candidate_first", "candidate_second"):
        candidate = value.get(label)
        require(isinstance(candidate, dict) and set(candidate) == CANDIDATE_KEYS, f"candidate schema mismatch: {label}")
        require(candidate.get("plan") == MISSING_PLAN, f"candidate plan marker drift: {label}")
        candidates.append(transfer.CandidateText(MISSING_PLAN, _text(candidate.get("code"), f"{label}.code")))
    lines, source_empty, original_context = _validate_context(value.get("context"))
    return {
        "task_desc": task_desc,
        "first": candidates[0],
        "second": candidates[1],
        "context_lines": lines,
        "source_context_empty": source_empty,
        "original_context_text": original_context,
        "input_context_sha256": value["context"]["context_sha256"],
    }


def token_ids_sha256(token_ids: Sequence[int]) -> str:
    digest = hashlib.sha256()
    digest.update(len(token_ids).to_bytes(8, "big"))
    for token_id in token_ids:
        require(not isinstance(token_id, bool) and isinstance(token_id, int) and 0 <= token_id < 2**32, "invalid token id")
        digest.update(struct.pack(">I", token_id))
    return digest.hexdigest()


def measure_prompt(tokenizer: Any, prompt: str) -> PromptMeasure:
    messages = [{"role": "user", "content": prompt}]
    rendered_chat = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
    )
    token_ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=True,
    )
    require(isinstance(rendered_chat, str), "rendered chat must be text")
    require(isinstance(token_ids, list), "tokenizer must return a token-id list")
    return PromptMeasure(
        prompt_token_count=len(token_ids),
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        rendered_chat_sha256=hashlib.sha256(rendered_chat.encode("utf-8")).hexdigest(),
        token_ids_sha256=token_ids_sha256(token_ids),
    )


def measure_orientations(
    *,
    tokenizer: Any,
    task_desc: str,
    context_text: str,
    first: transfer.CandidateText,
    second: transfer.CandidateText,
) -> dict[str, PromptMeasure]:
    rendered = transfer.render_orientations(
        task_desc=task_desc,
        context_text=context_text,
        first=first,
        second=second,
    )
    return {orientation: measure_prompt(tokenizer, prompt) for orientation, prompt in rendered.items()}


def select_prefix(
    *,
    tokenizer: Any,
    task_desc: str,
    context_lines: Sequence[str],
    source_context_empty: bool,
    first: transfer.CandidateText,
    second: transfer.CandidateText,
    prompt_token_limit: int,
) -> PrefixSelection:
    require(prompt_token_limit > 0, "prompt token limit must be positive")
    if source_context_empty:
        require(not context_lines, "empty source context has node lines")
        measures = measure_orientations(
            tokenizer=tokenizer,
            task_desc=task_desc,
            context_text=NO_PRIOR_CONTEXT,
            first=first,
            second=second,
        )
        require(
            all(item.prompt_token_count <= prompt_token_limit for item in measures.values()),
            "prompt without eligible context exceeds token budget",
        )
        return PrefixSelection(0, 0, NO_PRIOR_CONTEXT, "NO_ELIGIBLE_CONTEXT_NODES", None, measures)

    baseline = measure_orientations(
        tokenizer=tokenizer,
        task_desc=task_desc,
        context_text=NO_FIT_CONTEXT,
        first=first,
        second=second,
    )
    require(
        all(item.prompt_token_count <= prompt_token_limit for item in baseline.values()),
        "base prompt exceeds token budget",
    )
    accepted_count = 0
    accepted_text = NO_FIT_CONTEXT
    accepted_measures = baseline
    overflow_rank: int | None = None
    for rank in range(1, len(context_lines) + 1):
        candidate_text = "\n".join(context_lines[:rank])
        candidate_measures = measure_orientations(
            tokenizer=tokenizer,
            task_desc=task_desc,
            context_text=candidate_text,
            first=first,
            second=second,
        )
        if any(item.prompt_token_count > prompt_token_limit for item in candidate_measures.values()):
            overflow_rank = rank
            break
        accepted_count = rank
        accepted_text = candidate_text
        accepted_measures = candidate_measures
    stop_reason = (
        "ALL_ELIGIBLE_CONTEXT_NODES_FIT"
        if overflow_rank is None
        else "FIRST_OVERFLOW_STOPS_PREFIX"
    )
    return PrefixSelection(
        len(context_lines),
        accepted_count,
        accepted_text,
        stop_reason,
        overflow_rank,
        accepted_measures,
    )


def build_packing(
    source: Any,
    *,
    tokenizer: Any,
    snapshot_binding: Mapping[str, Any],
    runtime_versions: Mapping[str, str],
) -> dict[str, Any]:
    validated = validate_source(source)
    require(dict(runtime_versions) == EXPECTED_RUNTIME, "runtime binding drift")
    selection = select_prefix(
        tokenizer=tokenizer,
        task_desc=validated["task_desc"],
        context_lines=validated["context_lines"],
        source_context_empty=validated["source_context_empty"],
        first=validated["first"],
        second=validated["second"],
        prompt_token_limit=PROMPT_TOKEN_LIMIT,
    )
    require(
        all(item.prompt_token_count <= PROMPT_TOKEN_LIMIT for item in selection.orientations.values()),
        "accepted prompt exceeds token budget",
    )
    packed_sha256 = hashlib.sha256(selection.packed_context_text.encode("utf-8")).hexdigest()
    return {
        "schema_version": OUTPUT_SCHEMA,
        "protocol": PROTOCOL,
        "model": {
            "model_id": MODEL_ID,
            "public_repository_revision": MODEL_REVISION,
            "checkpoint_status": "PUBLIC_TRANSFER_REVISION_NOT_RPM_PRIVATE_CHECKPOINT",
            "model_weights_downloaded_or_loaded": False,
        },
        "tokenizer": {
            **dict(snapshot_binding),
            "runtime_versions": dict(runtime_versions),
            "local_files_only": True,
            "trust_remote_code": False,
        },
        "wrapper": {
            "messages": [{"role": "user"}],
            "add_generation_prompt": True,
            "enable_thinking": True,
            "system_message": None,
        },
        "packing": {
            "context_window_tokens": CONTEXT_WINDOW_TOKENS,
            "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
            "prompt_token_limit": PROMPT_TOKEN_LIMIT,
            "eligible_node_count": selection.eligible_node_count,
            "included_node_count": selection.included_node_count,
            "dropped_node_count": selection.eligible_node_count - selection.included_node_count,
            "stop_reason": selection.stop_reason,
            "overflow_at_node_rank": selection.overflow_at_node_rank,
            "input_context_sha256": validated["input_context_sha256"],
            "packed_context_text": selection.packed_context_text,
            "packed_context_sha256": packed_sha256,
            "whole_nodes_only": True,
            "partial_node_truncation": False,
            "first_overflow_stops": True,
            "both_orientations_must_fit": True,
        },
        "orientations": {
            key: value.to_json() for key, value in selection.orientations.items()
        },
        "paper_alignment": {
            "result_name": "RPM-style inference-only prompt transfer",
            "paper_aligned_parent_bfs_context_selection": False,
            "paper_aligned_non_buggy_predicate_reconstructed": False,
            "may_be_called_exact_reproduction": False,
        },
        "security": {
            "prospective_label_outcome_prediction_accuracy_utility_read": False,
            "prospective_candidate_identity_or_private_profile_read": False,
            "network_download_implemented": False,
            "model_call_implemented": False,
            "live_call_authorized": False,
        },
    }


def read_source(path: Path) -> dict[str, Any]:
    scan_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RPMTokenPackingError("invalid packing source JSON") from error
    require(isinstance(value, dict), "packing source must be an object")
    return value


def atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RPMTokenPackingError("output already exists")
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
    parser.add_argument("--tokenizer-dir", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    source_path = Path(arguments.source).resolve()
    tokenizer_root = Path(arguments.tokenizer_dir).resolve()
    output_path = Path(arguments.output).resolve()
    require(source_path.is_file(), "packing source absent")
    require(
        file_sha256(source_path) == _hash(arguments.expected_source_sha256, "expected source"),
        "packing source hash mismatch",
    )
    source = read_source(source_path)
    snapshot = validate_tokenizer_snapshot(tokenizer_root)
    tokenizer, versions = load_local_tokenizer(tokenizer_root)
    result = build_packing(
        source,
        tokenizer=tokenizer,
        snapshot_binding=snapshot,
        runtime_versions=versions,
    )
    result["source_sha256"] = file_sha256(source_path)
    atomic_write(output_path, result)
    print(
        "status=RPM_TOKEN_PACKING_PASS "
        f"included={result['packing']['included_node_count']} "
        f"eligible={result['packing']['eligible_node_count']}"
    )


if __name__ == "__main__":
    main()
