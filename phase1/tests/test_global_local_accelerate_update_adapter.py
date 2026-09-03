from dataclasses import replace
from decimal import Decimal

import pytest

from phase1.global_local_accelerate_update_adapter import (
    RUNTIME_FILE_SHA256,
    RUNTIME_METHOD_SHA256,
    RUNTIME_VERSIONS,
    rank_update_batches,
    update_learning_rate,
)
from phase1.global_local_execution_plan import PlanError
from phase1.global_local_execution_plan import BatchShape, EncoderBinding, Endpoint, Pair
from phase1.global_local_token_budget_plan import build_plan


def _sha(value):
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()


def fixture(world, arm):
    pools = []
    for source, count in (("G", 176), ("L", 209)):
        rows = []
        for index in range(count):
            a = Endpoint(f"synthetic:{source}:{index}:a", 3, _sha(f"a:{source}:{index}"))
            b = Endpoint(f"synthetic:{source}:{index}:b", 5, _sha(f"b:{source}:{index}"))
            rows.append(Pair.canonical(source, a, b, _sha("context")))
        pools.append(tuple(rows))
    value = build_plan(
        arm,
        *pools,
        seed=6,
        shape=BatchShape(world, 8, 8 if world == 2 else 4),
        encoder=EncoderBinding(_sha("encoder"), _sha("serializer"), 8),
        protocol_sha256=_sha("protocol"),
    )
    return value, pools, {}, {}


@pytest.mark.parametrize("world", [2, 4])
@pytest.mark.parametrize("arm", ["G_to_L", "Ghash_to_L"])
def test_rank_updates_preserve_all_boundaries(world, arm):
    value, _, _, _ = fixture(world, arm)
    for step in range(value.steps):
        per_rank = [rank_update_batches(value, rank, step) for rank in range(world)]
        assert len({len(rows) for rows in per_rank}) == 1
        assert sum(len(batch.rows) for rows in per_rank for batch in rows) == per_rank[0][0].update_real_pairs
        assert {batch.source for rows in per_rank for batch in rows} == {per_rank[0][0].source}
        assert update_learning_rate(value, per_rank[0], value.peak_lr_decimal) == float(
            Decimal(value.peak_lr_decimal)
            * Decimal(per_rank[0][0].lr_scale_numerator)
            / Decimal(per_rank[0][0].lr_scale_denominator)
        )


def test_rank_update_and_learning_rate_fail_closed_on_drift():
    value, _, _, _ = fixture(2, "G_to_L")
    with pytest.raises(PlanError, match="invalid_plan_rank"):
        rank_update_batches(value, 2, 0)
    batches = rank_update_batches(value, 0, 0)
    broken = (replace(batches[0], lr_scale_numerator=0), *batches[1:])
    with pytest.raises(PlanError, match="mixed_learning_rate_within_update"):
        update_learning_rate(value, broken, value.peak_lr_decimal)
    with pytest.raises(PlanError, match="peak_learning_rate_mismatch"):
        update_learning_rate(value, batches, "0.00002")


def test_adapter_binds_exact_runtime_and_has_no_launcher():
    assert RUNTIME_VERSIONS == {
        "torch": "2.11.0+cu128",
        "transformers": "5.12.1",
        "accelerate": "1.14.0",
        "deepspeed": "0.19.3",
    }
    assert set(RUNTIME_FILE_SHA256) == {
        "transformers.trainer", "accelerate.accelerator", "accelerate.state",
        "accelerate.utils.deepspeed", "deepspeed.runtime.engine",
    }
    assert "Trainer._run_epoch" in RUNTIME_METHOD_SHA256
    assert "DeepSpeedEngine.set_gradient_accumulation_boundary" in RUNTIME_METHOD_SHA256
    source = open(__import__(
        "phase1.global_local_accelerate_update_adapter", fromlist=["x"]
    ).__file__, encoding="utf-8").read()
    for forbidden in ("sbatch", "AutoModel", "from_pretrained", "requests.", "subprocess"):
        assert forbidden not in source
