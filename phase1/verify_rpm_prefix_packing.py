#!/usr/bin/env python3
"""Independent reconstruction of the RPM transfer prefix-packing receipt.

This verifier deliberately does not import either RPM packing or prompt-rendering
producer module.  It loads only a hash-bound local tokenizer snapshot and never
loads model weights or contacts a network service.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import struct
from typing import Any, Mapping, Sequence


PROTOCOL = "decision-corpus-rpm-token-packing-v1"
INPUT_PROTOCOL = "decision-corpus-rpm-token-packing-input-v1"
OUTPUT_SCHEMA = "decision-corpus-rpm-token-packing-output-v1"
CONTEXT_PROTOCOL = "decision-corpus-rpm-decision-time-context-v1"
CONTEXT_SCHEMA = "decision-corpus-rpm-context-output-v1"
MODEL_ID = "Qwen/Qwen3.6-27B"
MODEL_REVISION = "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
CONTEXT_WINDOW = 262_144
OUTPUT_RESERVE = 32_768
PROMPT_LIMIT = CONTEXT_WINDOW - OUTPUT_RESERVE
PROMPT_PATH = Path(__file__).resolve().parent / "baselines" / "rpm_inference_only_optimized_v2.txt"
PROMPT_BYTES = 1_950
PROMPT_SHA256 = "d64763172087a4243ddfa3ff364fad071c552af0783e5786a301a37bc338ff96"
CHAT_TEMPLATE_BYTES = 7_764
CHAT_TEMPLATE_SHA256 = "e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259"
MISSING_PLAN = "[PLAN_NOT_RECORDED_BY_DECISION_CORPUS]"
NO_PRIOR = '[{"context_status":"NO_PRIOR_EXECUTED_SCORED_NODE"}]'
NO_FIT = '[{"context_status":"NO_COMPLETE_PRIOR_NODE_FITS_TOKEN_BUDGET"}]'
PLACEHOLDERS = {
    "{task_desc}": 1,
    "{context_text}": 2,
    "{plan_A}": 1,
    "{code_A}": 1,
    "{plan_B}": 1,
    "{code_B}": 1,
}
VERSIONS = {
    "transformers": "4.57.1",
    "tokenizers": "0.22.1",
    "huggingface-hub": "0.36.0",
}
ARTIFACTS: dict[str, tuple[int, str]] = {
    "config.json": (4_308, "69db4eb7196bc8190813231b3018ca05d8c2e3abc7b1af19d55c157af44a9d9c"),
    "generation_config.json": (202, "e70c136c1b78ddc1fb0905bac8e733a4dc448d4f852a5dd75143fffc70be550e"),
    "tokenizer_config.json": (16_718, "5186f0defcd7f232382c7f0aebcd2252d073bb921ab240e407b7ae8745d2b29b"),
    "tokenizer.json": (12_807_982, "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    "README.md": (62_593, "bb936d6da51014f1edc9aa4cf9abf28d98695b7616ad56adfeeebfa752051d3d"),
}
HEX = re.compile(r"^[0-9a-f]{64}$")
SECRET = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:or-v1-|ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
WEIGHT = re.compile(r"(?:\.safetensors|\.bin|\.pt|\.pth|\.gguf)$", re.IGNORECASE)
INPUT_KEYS = {"protocol", "task_desc", "context", "candidate_first", "candidate_second"}
CANDIDATE_KEYS = {"plan", "code"}
CONTEXT_KEYS = {
    "schema_version", "protocol", "cutoff_step", "node_count", "ordering",
    "score_source", "identity_fields_emitted", "context_text", "context_sha256",
    "token_packing_applied", "live_call_authorized",
}
LINE_KEYS = {
    "code", "context_rank", "journal_step", "operator", "optimization_direction",
    "score_type", "self_reported_validation",
}


class RPMTokenPackingVerificationError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RPMTokenPackingVerificationError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def scan(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            need(SECRET.search(payload) is None, f"credential-shaped bytes: {path.name}")
            overlap = payload[-256:]


def valid_hash(value: Any, label: str) -> str:
    need(isinstance(value, str) and HEX.fullmatch(value) is not None, f"invalid hash: {label}")
    return value


def text(value: Any, label: str) -> str:
    need(isinstance(value, str) and bool(value.strip()) and "\x00" not in value, f"invalid text: {label}")
    need(SECRET.search(value.encode("utf-8")) is None, f"credential-shaped text: {label}")
    return value


def integer(value: Any, label: str) -> int:
    need(not isinstance(value, bool) and isinstance(value, int) and value >= 0, f"invalid integer: {label}")
    return value


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RPMTokenPackingVerificationError(f"invalid JSON: {label}") from error
    need(isinstance(value, dict), f"object required: {label}")
    return value


def validate_snapshot(root: Path) -> dict[str, Any]:
    need(root.is_dir() and not root.is_symlink(), "tokenizer directory absent or symlinked")
    for path in root.rglob("*"):
        if path.is_file():
            need(WEIGHT.search(path.name) is None, f"model weight file refused: {path.name}")
    records: dict[str, dict[str, Any]] = {}
    for name, (size, sha256) in ARTIFACTS.items():
        path = root / name
        need(path.is_file() and not path.is_symlink(), f"artifact absent or symlinked: {name}")
        need(path.stat().st_size == size, f"artifact size drift: {name}")
        need(digest(path) == sha256, f"artifact hash drift: {name}")
        scan(path)
        records[name] = {"bytes": size, "sha256": sha256}
    config = read_json(root / "tokenizer_config.json", "tokenizer config")
    template = config.get("chat_template")
    need(isinstance(template, str), "chat template absent")
    encoded = template.encode("utf-8")
    need(len(encoded) == CHAT_TEMPLATE_BYTES, "chat template size drift")
    need(hashlib.sha256(encoded).hexdigest() == CHAT_TEMPLATE_SHA256, "chat template hash drift")
    need(config.get("tokenizer_class") == "Qwen2Tokenizer", "tokenizer class drift")
    need(config.get("model_max_length") == CONTEXT_WINDOW, "model max length drift")
    need(config.get("bos_token") is None, "BOS token drift")
    need(config.get("eos_token") == "<|im_end|>", "EOS token drift")
    need(config.get("pad_token") == "<|endoftext|>", "PAD token drift")
    return {
        "artifacts": records,
        "chat_template_bytes": len(encoded),
        "chat_template_sha256": hashlib.sha256(encoded).hexdigest(),
        "tokenizer_class_in_config": config["tokenizer_class"],
        "model_max_length": config["model_max_length"],
        "bos_token": None,
        "eos_token": config["eos_token"],
        "pad_token": config["pad_token"],
    }


def load_tokenizer(root: Path) -> tuple[Any, dict[str, str]]:
    observed: dict[str, str] = {}
    for package, expected in VERSIONS.items():
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as error:
            raise RPMTokenPackingVerificationError(f"package unavailable: {package}") from error
        need(version == expected, f"runtime version drift: {package}")
        observed[package] = version
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RPMTokenPackingVerificationError("transformers unavailable") from error
    tokenizer = AutoTokenizer.from_pretrained(
        str(root), local_files_only=True, trust_remote_code=False, use_fast=True
    )
    need(getattr(tokenizer, "model_max_length", None) == CONTEXT_WINDOW, "loaded max length drift")
    need(getattr(tokenizer, "bos_token", None) is None, "loaded BOS drift")
    need(getattr(tokenizer, "eos_token", None) == "<|im_end|>", "loaded EOS drift")
    need(getattr(tokenizer, "pad_token", None) == "<|endoftext|>", "loaded PAD drift")
    loaded_template = getattr(tokenizer, "chat_template", None)
    need(isinstance(loaded_template, str), "loaded chat template absent")
    need(hashlib.sha256(loaded_template.encode("utf-8")).hexdigest() == CHAT_TEMPLATE_SHA256, "loaded chat template drift")
    return tokenizer, observed


def load_prompt() -> str:
    need(PROMPT_PATH.is_file() and not PROMPT_PATH.is_symlink(), "prompt file absent or symlinked")
    raw = PROMPT_PATH.read_bytes()
    need(len(raw) == PROMPT_BYTES, "prompt byte-length drift")
    need(hashlib.sha256(raw).hexdigest() == PROMPT_SHA256, "prompt hash drift")
    try:
        prompt = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RPMTokenPackingVerificationError("prompt is not UTF-8") from error
    for placeholder, expected in PLACEHOLDERS.items():
        need(prompt.count(placeholder) == expected, f"prompt placeholder drift: {placeholder}")
    return prompt


def validate_context(value: Any) -> tuple[list[str], bool, str]:
    need(isinstance(value, dict) and set(value) == CONTEXT_KEYS, "context schema")
    need(value.get("schema_version") == CONTEXT_SCHEMA, "context output schema")
    need(value.get("protocol") == CONTEXT_PROTOCOL, "context protocol")
    integer(value.get("cutoff_step"), "cutoff")
    count = integer(value.get("node_count"), "node count")
    need(value.get("ordering") == "journal_step_desc_then_node_sha256_asc", "context ordering")
    need(value.get("score_source") == "self_reported_validation", "context score source")
    need(value.get("identity_fields_emitted") is False, "context identity fields")
    need(value.get("token_packing_applied") is False, "context already packed")
    need(value.get("live_call_authorized") is False, "context live-call flag")
    context_text = text(value.get("context_text"), "context text")
    need(hashlib.sha256(context_text.encode("utf-8")).hexdigest() == valid_hash(value.get("context_sha256"), "context"), "context hash")
    if count == 0:
        need(context_text == NO_PRIOR, "empty-context literal")
        return [], True, context_text
    lines = context_text.splitlines()
    need(len(lines) == count, "context line count")
    for rank, line in enumerate(lines, 1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            raise RPMTokenPackingVerificationError(f"context line JSON: {rank}") from error
        need(isinstance(item, dict) and set(item) == LINE_KEYS, f"context line schema: {rank}")
        need(item.get("context_rank") == rank, f"context rank: {rank}")
        integer(item.get("journal_step"), f"journal step: {rank}")
        text(item.get("operator"), f"operator: {rank}")
        text(item.get("code"), f"code: {rank}")
        need(item.get("optimization_direction") in {"higher_is_better", "lower_is_better"}, f"direction: {rank}")
        need(item.get("score_type") == "self_reported_validation", f"score type: {rank}")
        score = item.get("self_reported_validation")
        need(not isinstance(score, bool) and isinstance(score, (int, float)) and math.isfinite(float(score)), f"score: {rank}")
        need(compact(item) == line, f"noncanonical context line: {rank}")
    return lines, False, context_text


def validate_source(value: Any) -> dict[str, Any]:
    need(isinstance(value, dict) and set(value) == INPUT_KEYS, "source schema")
    need(value.get("protocol") == INPUT_PROTOCOL, "source protocol")
    task_desc = text(value.get("task_desc"), "task description")
    candidates = []
    for label in ("candidate_first", "candidate_second"):
        candidate = value.get(label)
        need(isinstance(candidate, dict) and set(candidate) == CANDIDATE_KEYS, f"candidate schema: {label}")
        need(candidate.get("plan") == MISSING_PLAN, f"candidate plan marker: {label}")
        candidates.append({"plan": MISSING_PLAN, "code": text(candidate.get("code"), f"candidate code: {label}")})
    lines, empty, original = validate_context(value.get("context"))
    return {
        "task_desc": task_desc,
        "first": candidates[0],
        "second": candidates[1],
        "lines": lines,
        "empty": empty,
        "original": original,
        "context_sha256": value["context"]["context_sha256"],
    }


def render_prompt(template: str, task: str, context: str, first: Mapping[str, str], second: Mapping[str, str]) -> str:
    replacements = {
        "{task_desc}": task,
        "{context_text}": context,
        "{plan_A}": first["plan"],
        "{code_A}": first["code"],
        "{plan_B}": second["plan"],
        "{code_B}": second["code"],
    }
    result = template
    for placeholder, replacement in replacements.items():
        result = result.replace(placeholder, replacement)
    return result


def ids_hash(values: Sequence[int]) -> str:
    value = hashlib.sha256()
    value.update(len(values).to_bytes(8, "big"))
    for token_id in values:
        need(not isinstance(token_id, bool) and isinstance(token_id, int) and 0 <= token_id < 2**32, "invalid token id")
        value.update(struct.pack(">I", token_id))
    return value.hexdigest()


def measure(tokenizer: Any, prompt: str) -> dict[str, Any]:
    messages = [{"role": "user", "content": prompt}]
    rendered = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=True
    )
    token_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, enable_thinking=True
    )
    need(isinstance(rendered, str) and isinstance(token_ids, list), "tokenizer return type")
    return {
        "prompt_token_count": len(token_ids),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "rendered_chat_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "token_ids_sha256": ids_hash(token_ids),
    }


def measure_both(tokenizer: Any, template: str, source: Mapping[str, Any], context: str) -> dict[str, dict[str, Any]]:
    return {
        "AB": measure(tokenizer, render_prompt(template, source["task_desc"], context, source["first"], source["second"])),
        "BA": measure(tokenizer, render_prompt(template, source["task_desc"], context, source["second"], source["first"])),
    }


def reconstruct(
    raw_source: Any,
    *,
    tokenizer: Any,
    snapshot: Mapping[str, Any],
    versions: Mapping[str, str],
    source_sha256: str,
) -> dict[str, Any]:
    source = validate_source(raw_source)
    need(dict(versions) == VERSIONS, "runtime binding")
    template = load_prompt()
    if source["empty"]:
        packed = NO_PRIOR
        selected = 0
        overflow = None
        reason = "NO_ELIGIBLE_CONTEXT_NODES"
        measurements = measure_both(tokenizer, template, source, packed)
        need(all(item["prompt_token_count"] <= PROMPT_LIMIT for item in measurements.values()), "empty prompt overflow")
    else:
        packed = NO_FIT
        selected = 0
        overflow = None
        measurements = measure_both(tokenizer, template, source, packed)
        need(all(item["prompt_token_count"] <= PROMPT_LIMIT for item in measurements.values()), "base prompt overflow")
        for rank in range(1, len(source["lines"]) + 1):
            candidate_context = "\n".join(source["lines"][:rank])
            candidate_measurements = measure_both(tokenizer, template, source, candidate_context)
            if any(item["prompt_token_count"] > PROMPT_LIMIT for item in candidate_measurements.values()):
                overflow = rank
                break
            selected = rank
            packed = candidate_context
            measurements = candidate_measurements
        reason = "ALL_ELIGIBLE_CONTEXT_NODES_FIT" if overflow is None else "FIRST_OVERFLOW_STOPS_PREFIX"
    result = {
        "schema_version": OUTPUT_SCHEMA,
        "protocol": PROTOCOL,
        "model": {
            "model_id": MODEL_ID,
            "public_repository_revision": MODEL_REVISION,
            "checkpoint_status": "PUBLIC_TRANSFER_REVISION_NOT_RPM_PRIVATE_CHECKPOINT",
            "model_weights_downloaded_or_loaded": False,
        },
        "tokenizer": {
            **dict(snapshot),
            "runtime_versions": dict(versions),
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
            "context_window_tokens": CONTEXT_WINDOW,
            "output_reserve_tokens": OUTPUT_RESERVE,
            "prompt_token_limit": PROMPT_LIMIT,
            "eligible_node_count": len(source["lines"]),
            "included_node_count": selected,
            "dropped_node_count": len(source["lines"]) - selected,
            "stop_reason": reason,
            "overflow_at_node_rank": overflow,
            "input_context_sha256": source["context_sha256"],
            "packed_context_text": packed,
            "packed_context_sha256": hashlib.sha256(packed.encode("utf-8")).hexdigest(),
            "whole_nodes_only": True,
            "partial_node_truncation": False,
            "first_overflow_stops": True,
            "both_orientations_must_fit": True,
        },
        "orientations": measurements,
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
        "source_sha256": source_sha256,
    }
    return result


def atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RPMTokenPackingVerificationError("verification output exists")
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
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
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--expected-candidate-sha256", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    source_path = Path(arguments.source).resolve()
    candidate_path = Path(arguments.candidate).resolve()
    output_path = Path(arguments.output).resolve()
    tokenizer_root = Path(arguments.tokenizer_dir).resolve()
    need(source_path.is_file() and candidate_path.is_file(), "input absent")
    source_sha = digest(source_path)
    candidate_sha = digest(candidate_path)
    need(source_sha == valid_hash(arguments.expected_source_sha256, "expected source"), "source hash mismatch")
    need(candidate_sha == valid_hash(arguments.expected_candidate_sha256, "expected candidate"), "candidate hash mismatch")
    scan(source_path)
    scan(candidate_path)
    raw_source = read_json(source_path, "source")
    candidate = read_json(candidate_path, "candidate")
    snapshot = validate_snapshot(tokenizer_root)
    tokenizer, versions = load_tokenizer(tokenizer_root)
    expected = reconstruct(
        raw_source,
        tokenizer=tokenizer,
        snapshot=snapshot,
        versions=versions,
        source_sha256=source_sha,
    )
    need(candidate == expected, "candidate differs from independent reconstruction")
    receipt = {
        "status": "RPM_TOKEN_PACKING_INDEPENDENT_VERIFICATION_PASS",
        "protocol": PROTOCOL,
        "source_sha256": source_sha,
        "candidate_sha256": candidate_sha,
        "model_revision": MODEL_REVISION,
        "eligible_node_count": expected["packing"]["eligible_node_count"],
        "included_node_count": expected["packing"]["included_node_count"],
        "packed_context_sha256": expected["packing"]["packed_context_sha256"],
        "ab_prompt_token_count": expected["orientations"]["AB"]["prompt_token_count"],
        "ba_prompt_token_count": expected["orientations"]["BA"]["prompt_token_count"],
        "model_weights_downloaded_or_loaded": False,
        "live_call_authorized": False,
    }
    atomic_write(output_path, receipt)
    print("status=RPM_TOKEN_PACKING_INDEPENDENT_VERIFICATION_PASS")


if __name__ == "__main__":
    main()
