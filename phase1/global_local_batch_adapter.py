"""Pure CPU batch-boundary checks. No file readers, tokenizer, or model.

Encoding digests cover the exact unpadded input IDs and their all-one mask.
The encoder/protocol hashes remain separate bindings; this is NOT attestation
that tokenization of any real code was correct or permitted.
"""
from __future__ import annotations

from dataclasses import dataclass

from phase1.global_local_execution_plan import PlanError, digest_records, targets
from phase1.verify_global_local_execution_trace import BatchReceipt


def encoding_digest(ids):
    if not isinstance(ids, (tuple, list)) or not ids or any(type(x) is not int or x < 0 for x in ids):
        raise PlanError("invalid_encoded_ids")
    return digest_records([{"input_ids": list(ids), "attention_mask": [1] * len(ids)}])


@dataclass(frozen=True)
class PackedBatch:
    input_ids: tuple[tuple[int, ...], ...]
    attention_mask: tuple[tuple[int, ...], ...]
    signs: tuple[int, ...]


def pack_batch(plan, batch, encoding_provider, true_sign, *, pad_id):
    if type(pad_id) is not int or pad_id < 0:
        raise PlanError("invalid_pad_id")
    ids = []
    # Matches the actual RM's A-half/B-half layout without winner-first swapping.
    for side in ("a", "b"):
        for row in batch.rows:
            endpoint = getattr(row, side)
            value = tuple(encoding_provider(row.context_sha256, endpoint.card_id))
            if (encoding_digest(value) != endpoint.encoded_sha256
                    or len(value) != endpoint.valid_tokens or len(value) > plan.encoder.max_len):
                raise PlanError("provider_encoding_mismatch")
            ids.append(value)
    width = max(map(len, ids))
    packed = PackedBatch(tuple(x + (pad_id,) * (width - len(x)) for x in ids),
                         tuple((1,) * len(x) + (0,) * (width - len(x)) for x in ids),
                         targets(plan.arm, batch, true_sign))
    return packed


def observe_batch(plan, batch, packed, true_sign, *, pad_id):
    """Re-hash observed arrays, never manufacture observations from descriptors."""
    if type(pad_id) is not int or pad_id < 0:
        raise PlanError("invalid_pad_id")
    count = len(batch.rows)
    ids, masks = packed.input_ids, packed.attention_mask
    if (not count or len(ids) != 2 * count or len(masks) != len(ids)
            or packed.signs != targets(plan.arm, batch, true_sign)
            or any(type(s) is not int for s in packed.signs)):
        raise PlanError("observed_shape_or_sign_mismatch")
    expected_width = max(e.valid_tokens for r in batch.rows for e in (r.a, r.b))
    digests, valid = [], 0
    for index, (values, mask) in enumerate(zip(ids, masks)):
        if len(values) != expected_width or len(mask) != expected_width:
            raise PlanError("observed_padding_width_mismatch")
        if (any(type(x) is not int or x < 0 for x in values)
                or any(type(x) is not int or x not in (0, 1) for x in mask)):
            raise PlanError("observed_invalid_values")
        n = sum(mask)
        if not n or tuple(mask) != (1,) * n + (0,) * (expected_width - n):
            raise PlanError("observed_nonprefix_mask")
        if tuple(values[n:]) != (pad_id,) * (expected_width - n):
            raise PlanError("observed_padding_value_mismatch")
        side = "a" if index < count else "b"
        endpoint = getattr(batch.rows[index % count], side)
        observed_hash = encoding_digest(values[:n])
        if n != endpoint.valid_tokens or observed_hash != endpoint.encoded_sha256:
            raise PlanError("observed_encoding_mismatch")
        digests.append(observed_hash)
        valid += n
    return BatchReceipt(plan.sha256, batch.optimizer_step, batch.micro_step, batch.rank,
                        tuple(r.key for r in batch.rows),
                        tuple(zip(digests[:count], digests[count:])), valid, len(ids) * expected_width)


def synthetic_fixture(arm="G_to_L", seed=6, *, accumulation=2, pairs_per_rank=2):
    """Small deterministic synthetic IDs, not a real tokenizer or data source."""
    import hashlib
    from phase1.global_local_execution_plan import BatchShape, EncoderBinding, Endpoint, Pair, build_plan
    h = lambda x: hashlib.sha256(x.encode()).hexdigest()
    context = h("synthetic:consumer-context-v1")
    encoded, truth, pools = {}, {}, []
    for source in ("G", "L"):
        rows = []
        for i in range(8):
            endpoints = []
            for j, length in enumerate((3, 5)):
                name = f"synthetic:{source}:{i}:{j}"
                values = tuple(1 + ((i * 7 + j * 3 + k + (source == 'L')) % 19) for k in range(length))
                encoded[(context, name)] = values
                endpoints.append(Endpoint(name, length, encoding_digest(values)))
            row = Pair.canonical(source, *endpoints, context)
            truth[row.key] = 1 if i % 2 else -1
            rows.append(row)
        pools.append(tuple(rows))
    plan = build_plan(arm, *pools, seed=seed,
                      shape=BatchShape(1, pairs_per_rank, accumulation),
                      encoder=EncoderBinding(h("synthetic:integer-encoder"), h("synthetic:serializer"), 8),
                      protocol_sha256=h("synthetic:consumer-unit-test-not-frozen-v2"))
    return plan, pools, encoded, truth
