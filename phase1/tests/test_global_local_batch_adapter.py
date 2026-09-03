from dataclasses import replace
import pytest

from phase1.global_local_execution_plan import PlanError
from phase1.global_local_batch_adapter import PackedBatch, encoding_digest, observe_batch, pack_batch, synthetic_fixture
from phase1.verify_global_local_execution_trace import verify_prefix


@pytest.mark.parametrize("arm", ["L1", "Lbudget", "Gbudget", "G_to_L", "Ghash_to_L"])
@pytest.mark.parametrize("seed", [6, 7, 8])
def test_actual_packed_arrays_independently_observed(arm, seed):
    plan, pools, enc, truth = synthetic_fixture(arm, seed)
    forbidden = {r.key for r in pools[0]} if arm == "Ghash_to_L" else set()
    def target(key):
        assert key not in forbidden
        return truth[key]
    events = []
    for batch in plan.batches:
        packed = pack_batch(plan, batch, lambda c, n: enc[(c, n)], target, pad_id=0)
        events.append(observe_batch(plan, batch, packed, target, pad_id=0))
    assert verify_prefix(plan, events, completed_steps=plan.steps).plan_sha256 == plan.sha256


def test_real_and_hash_only_change_sign_not_model_inputs():
    packed = []
    for arm in ("G_to_L", "Ghash_to_L"):
        plan, _, enc, truth = synthetic_fixture(arm)
        packed.append([pack_batch(plan, b, lambda c, n: enc[(c, n)], truth.__getitem__, pad_id=0) for b in plan.batches])
    assert all(x.input_ids == y.input_ids and x.attention_mask == y.attention_mask for x, y in zip(*packed))
    assert any(x.signs != y.signs for x, y in zip(*packed))
    assert all(x.signs == y.signs for x, y in zip(packed[0][4:], packed[1][4:]))


@pytest.mark.parametrize("mutation", ["input_value", "mask_order", "pad_value", "pad_width", "sign", "sign_bool", "row_order", "dtype", "empty_mask", "missing_row"])
def test_corrupt_observed_tensors_rejected(mutation):
    plan, _, enc, truth = synthetic_fixture()
    batch = plan.batches[0]
    value = pack_batch(plan, batch, lambda c, n: enc[(c, n)], truth.__getitem__, pad_id=0)
    ids, mask, signs = [list(x) for x in value.input_ids], [list(x) for x in value.attention_mask], list(value.signs)
    if mutation == "input_value": ids[0][0] += 1
    if mutation == "mask_order": mask[0] = [1, 0, 1, 1, 0]
    if mutation == "pad_value": ids[0][-1] = 3
    if mutation == "pad_width": ids = [x + [0] for x in ids]; mask = [x + [0] for x in mask]
    if mutation == "sign": signs[0] *= -1
    if mutation == "sign_bool": signs[0] = True
    if mutation == "row_order": ids[0], ids[1] = ids[1], ids[0]
    if mutation == "dtype": ids[0][0] = float(ids[0][0])
    if mutation == "empty_mask": mask[0] = [0] * len(mask[0])
    if mutation == "missing_row": ids.pop()
    broken = PackedBatch(tuple(tuple(x) for x in ids), tuple(tuple(x) for x in mask), tuple(signs))
    with pytest.raises(PlanError):
        observe_batch(plan, batch, broken, truth.__getitem__, pad_id=0)


@pytest.mark.parametrize("ids", [[], [True], [-1], [1.0], "12", None])
def test_invalid_encoding(ids):
    with pytest.raises(PlanError, match="invalid_encoded_ids"):
        encoding_digest(ids)


def test_provider_mismatch_is_not_silently_reencoded():
    plan, _, enc, truth = synthetic_fixture()
    with pytest.raises(PlanError, match="provider_encoding_mismatch"):
        pack_batch(plan, plan.batches[0], lambda c, n: enc[(c, n)] + (99,), truth.__getitem__, pad_id=0)


def test_model_input_digest_changes_when_actual_content_changes():
    assert encoding_digest((1, 2, 3)) != encoding_digest((1, 2, 4))
    assert encoding_digest((1, 2, 3)) == encoding_digest([1, 2, 3])


@pytest.mark.parametrize("pad_id", [-1, True, 0.0])
def test_invalid_pad_id(pad_id):
    plan, _, enc, truth = synthetic_fixture()
    with pytest.raises(PlanError, match="invalid_pad_id"):
        pack_batch(plan, plan.batches[0], lambda c, n: enc[(c, n)], truth.__getitem__, pad_id=pad_id)
