"""Label-blind, in-memory endpoint inference; no readers/loaders/launch authority.

Caller must separately authorize inputs, bind tokenizer/checkpoints and enforce
process-level access isolation. v1 is task-conditioned and budget-independent.
Models stay caller-owned: no loading, training, mode changes or auto GPU use.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any


class EndpointInferenceError(ValueError):
    """Fixed reason codes only; do not expose identifiers or supplied values."""


CARD_KEYS = {"endpoint_id", "code", "task_name"}
ARMS = ("L1", "Lbudget", "G-reuse-budget", "G-reuse-to-L-full", "Ghash-reuse-to-L-full")
SCORE_KEYS = {f"{arm}|{seed}" for arm in ARMS for seed in (6, 7, 8)} | {"tfidf"}
ENCODER_REFERENCE_SHA256 = "3e1969499405199a187c12106d9f4d4a5542b4a1ecf094e0bd9f7c71514b4643"


def require(condition, reason):
    if not condition:
        raise EndpointInferenceError(reason)


def identity(value):
    return (type(value) is str and 0 < len(value.encode("utf-8")) <= 512
            and all(ord(c) >= 32 for c in value))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def token_sequence(ids):
    return (type(ids) in (list, tuple) and bool(ids)
            and all(type(i) is int and 0 <= i < 2**63 for i in ids))


@dataclass(frozen=True)
class EncodedEndpoint:
    endpoint_id: str
    input_ids: tuple[int, ...]

    @property
    def sha256(self):
        return digest({"input_ids": list(self.input_ids), "attention_mask": [1] * len(self.input_ids)})


def encode_endpoints(cards: list[dict[str, Any]], tokenizer, *, max_len: int) -> tuple[EncodedEndpoint, ...]:
    """Match the pinned CardEncoder at head_frac=.25, task=true, budget=false.

    max_len is never inferred from the tokenizer. Input projection must happen
    in a separately authorized caller; passing a raw labelled Card is rejected.
    """
    require(type(max_len) is int and 1 <= max_len <= 16384, "invalid_context_limit")
    require(type(cards) is list and bool(cards), "empty_or_invalid_cards")
    seen = set()
    for row in cards:
        require(type(row) is dict and set(row) == CARD_KEYS, "blinded_card_schema")
        name = row["endpoint_id"]
        require(identity(name) and name not in seen, "invalid_or_duplicate_endpoint")
        require(type(row["code"]) is str, "invalid_code")
        require(type(row["task_name"]) is str and bool(row["task_name"])
                and all(ord(c) >= 32 for c in row["task_name"]), "invalid_task_name")
        seen.add(name)
    encoded = []
    for row in sorted(cards, key=lambda r: r["endpoint_id"]):
        text = f"# MLE-bench task: {row['task_name']}\n" + row["code"]
        value = tokenizer(text, add_special_tokens=False)
        require(isinstance(value, dict) or hasattr(value, "keys"), "invalid_tokenizer_output")
        require("input_ids" in value, "missing_input_ids")
        ids = value["input_ids"]
        require(token_sequence(ids), "invalid_token_sequence")
        if len(ids) > max_len:
            head = int(max_len * 0.25)
            ids = ids[:head] + ids[-(max_len - head):]
        encoded.append(EncodedEndpoint(row["endpoint_id"], tuple(ids)))
    return tuple(encoded)


def score_endpoints(model, endpoints, *, pad_id: int, batch_size: int, device: str):
    """Run each unique endpoint once; return private scalars and public counts.

    Uses inference_mode but deliberately rejects training-mode models instead
    of mutating mode. Existing gradients are not evidence of a new backward;
    no backward/optimizer exists here. Device must be supplied explicitly.
    """
    import torch

    require(type(pad_id) is int and 0 <= pad_id < 2**63, "invalid_pad_id")
    require(type(batch_size) is int and 1 <= batch_size <= 1024, "invalid_batch_size")
    require(type(device) is str and (device == "cpu" or
            (device.startswith("cuda:") and device[5:].isdigit())), "explicit_device_required")
    require(type(endpoints) in (tuple, list) and bool(endpoints), "empty_or_invalid_endpoints")
    seen = set()
    for row in endpoints:
        require(type(row) is EncodedEndpoint, "encoded_endpoint_schema")
        require(identity(row.endpoint_id) and row.endpoint_id not in seen, "invalid_or_duplicate_endpoint")
        require(type(row.input_ids) is tuple and token_sequence(row.input_ids)
                and len(row.input_ids) <= 16384, "invalid_encoded_tokens")
        seen.add(row.endpoint_id)
    require(isinstance(model, torch.nn.Module) and all(not m.training for m in model.modules()), "model_must_be_eval")
    selected_device = torch.device(device)
    require(all(t.device == selected_device for t in list(model.parameters()) + list(model.buffers())), "model_device_mismatch")
    ordered = sorted(endpoints, key=lambda r: r.endpoint_id)
    scores, padded, calls = {}, 0, 0
    with torch.inference_mode():
        for start in range(0, len(ordered), batch_size):
            batch = ordered[start:start + batch_size]
            width = max(len(r.input_ids) for r in batch)
            ids = torch.tensor([r.input_ids + (pad_id,) * (width - len(r.input_ids)) for r in batch],
                               dtype=torch.long, device=selected_device)
            mask = torch.tensor([(1,) * len(r.input_ids) + (0,) * (width - len(r.input_ids)) for r in batch],
                                dtype=torch.long, device=selected_device)
            output = model(input_ids=ids, attention_mask=mask)
            require(isinstance(output, dict) and "logits" in output, "missing_scalar_logits")
            logits = output["logits"]
            require(isinstance(logits, torch.Tensor) and tuple(logits.shape) == (len(batch),)
                    and logits.is_floating_point(), "invalid_scalar_logits")
            require(bool(torch.isfinite(logits).all()), "nonfinite_scalar_logits")
            values = logits.detach().float().cpu().tolist()
            require(all(math.isfinite(v) for v in values), "nonfinite_cast_logits")
            scores.update((row.endpoint_id, value) for row, value in zip(batch, values))
            padded += len(batch) * width
            calls += 1
    receipt = {
        "classification": "ENDPOINT_FORWARD_ONLY_NOT_AUTHORIZED_ESCROW",
        "endpoints": len(ordered), "forward_calls": calls,
        "valid_tokens": sum(len(r.input_ids) for r in ordered), "padded_slots": padded,
        "batch_size": batch_size, "device": device,
        "encoded_support_sha256": digest([(r.endpoint_id, r.sha256) for r in ordered]),
        "checkpoint_and_input_authorization_checked": False,
        "os_access_isolation_checked": False,
    }
    return scores, receipt


def assemble_score_matrix(expected_endpoints, by_model):
    """Join private endpoint scores into the existing margin-materializer schema.

    Schema and coverage checking does NOT authenticate model provenance, training
    seeds, or checkpoint hashes; the frozen escrow gate must do that separately.
    """
    require(type(expected_endpoints) in (list, tuple) and bool(expected_endpoints), "empty_or_invalid_support")
    require(all(identity(x) for x in expected_endpoints), "invalid_endpoint")
    require(len(set(expected_endpoints)) == len(expected_endpoints), "duplicate_support")
    support = set(expected_endpoints)
    require(type(by_model) is dict and set(by_model) == SCORE_KEYS, "incomplete_model_matrix")
    for values in by_model.values():
        require(type(values) is dict and set(values) == support, "model_endpoint_support_mismatch")
        require(all(type(v) in (float, int) and math.isfinite(float(v)) for v in values.values()), "invalid_model_score")
    return [{"endpoint_id": name, "scores": {key: float(by_model[key][name]) for key in sorted(SCORE_KEYS)}}
            for name in sorted(support)]
