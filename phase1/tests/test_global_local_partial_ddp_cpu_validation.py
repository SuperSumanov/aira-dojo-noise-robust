from dataclasses import replace
from fractions import Fraction

import pytest

pytest.importorskip("torch")

from phase1 import global_local_partial_ddp_cpu_validation as validation
from phase1.global_local_batch_adapter import observe_batch, pack_batch


@pytest.mark.parametrize("world,expected_per_rank_events", [(2, 25), (4, 13)])
@pytest.mark.parametrize("arm", ["G_to_L", "Ghash_to_L"])
def test_fixture_matches_real_terminal_remainders_and_balanced_rank_layout(
    world, expected_per_rank_events, arm
):
    value, pools, encoded, truth = validation.fixture(world, arm)
    assert value.steps == 4
    assert [segment.pair_visits for segment in value.segments] == [176, 209]
    assert [value.segments[0].pair_visits % 128, value.segments[1].pair_visits % 128] == [48, 81]
    assert len(value.batches) // world == expected_per_rank_events
    for step in range(value.steps):
        batches = [batch for batch in value.batches if batch.optimizer_step == step]
        assert {(batch.micro_step, batch.rank) for batch in batches} == {
            (micro, rank)
            for micro in range(max(batch.micro_step for batch in batches) + 1)
            for rank in range(world)
        }
        assert sum(
            Fraction(batch.loss_mean_scale_numerator, batch.loss_mean_scale_denominator)
            for batch in batches
        ) / world == 1
    if arm == "Ghash_to_L":
        global_keys = {row.key for row in pools[0]}
        def target(key):
            assert key not in global_keys
            return truth[key]
    else:
        target = truth.__getitem__
    receipts = []
    for batch in value.batches:
        packed = pack_batch(value, batch, lambda context, card: encoded[(context, card)], target, pad_id=0)
        receipts.append(observe_batch(value, batch, packed, target, pad_id=0))
    validation.verify_consumption_prefix(value, receipts, 4)


def test_runtime_receipt_verifier_rejects_corruption():
    value, _, encoded, truth = validation.fixture(2, "G_to_L")
    receipts = []
    for batch in value.batches:
        packed = pack_batch(value, batch, lambda context, card: encoded[(context, card)], truth.__getitem__, pad_id=0)
        receipts.append(observe_batch(value, batch, packed, truth.__getitem__, pad_id=0))
    broken = [replace(receipts[0], valid_tokens=receipts[0].valid_tokens + 1), *receipts[1:]]
    with pytest.raises(ValueError, match="consumption_receipt_mismatch"):
        validation.verify_consumption_prefix(value, broken, 4)


def test_module_is_explicitly_synthetic_and_has_no_research_launcher():
    source = open(validation.__file__, encoding="utf-8").read()
    assert "synthetic:" in source
    assert "sbatch" not in source
    assert "AutoModel" not in source
    assert "real_HF_Trainer_DeepSpeed_bf16_verified" in source
