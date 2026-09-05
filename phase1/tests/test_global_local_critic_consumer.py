from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
import torch

import phase1.global_local_critic_consumer as consumer
from phase1.global_local_batch_adapter import pack_batch, synthetic_fixture
from phase1.global_local_execution_plan import PlanError
from phase1.global_local_token_budget_plan import build_plan


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor([0.3, -0.1]))
        self.calls = 0

    def forward(self, input_ids, attention_mask):
        self.calls += 1
        values = input_ids.float() * attention_mask
        features = torch.stack((values.sum(1) / 100, values.square().sum(1) / 1000), 1)
        return {'logits': features @ self.weight}


class FakeAccelerator:
    """Unit double only; real Accelerate+Qwen parity is a separate executable."""
    def __init__(self, optimizer, gas):
        self.process_index, self.num_processes = 0, 1
        self.gradient_accumulation_steps = gas
        self.device, self.distributed_type = torch.device('cpu'), 'NO'
        self._optimizers, self._schedulers = [optimizer], []
        self.sync_gradients, self.optimizer_step_was_skipped = True, False
        self.gradient_state = SimpleNamespace(_set_sync_gradients=self.set_sync)

    def set_sync(self, value):
        self.sync_gradients = value

    def no_sync(self, model):
        return nullcontext()

    def autocast(self):
        return nullcontext()

    def backward(self, loss):
        (loss / self.gradient_accumulation_steps).backward()

    def clip_grad_norm_(self, parameters, norm):
        return torch.nn.utils.clip_grad_norm_(parameters, norm)

    def reduce(self, value, reduction):
        assert reduction == 'sum'
        return value


def make_consumer(monkeypatch, arm='G_to_L'):
    monkeypatch.setattr(consumer, 'runtime_binding', lambda: {'unit_double': True})
    old, pools, encoded, truth = synthetic_fixture()
    plan = build_plan(arm, *pools, seed=6, shape=replace(old.shape, accumulation=3), encoder=old.encoder,
                      protocol_sha256=old.protocol_sha256)
    model = Model()
    optimizer = torch.optim.SGD(model.parameters(), lr=1e-5)
    accelerator = FakeAccelerator(optimizer, plan.shape.accumulation)
    global_keys = {r.key for r in pools[0]}
    def target(key):
        if arm == 'Ghash_to_L' and key in global_keys:
            raise AssertionError('true_global_label_access')
        return truth[key]
    obj = consumer.PlannedCriticConsumer(plan=plan, pools=pools, accelerator=accelerator,
        model=model, optimizer=optimizer, encoding_provider=lambda ctx, card: encoded[(ctx, card)],
        true_sign=target, pad_id=0)
    return obj, encoded, target


@pytest.mark.parametrize('arm', ['L1', 'Lbudget', 'Gbudget', 'G_to_L', 'Ghash_to_L'])
def test_all_arms_equal_whole_update_reference(monkeypatch, arm):
    obj, encoded, target = make_consumer(monkeypatch, arm)
    reference = deepcopy(obj.model)
    opt = torch.optim.SGD(reference.parameters(), lr=1e-5)
    events = []
    for step in range(obj.plan.steps):
        batches = [b for b in obj.plan.batches if b.optimizer_step == step]
        holder = SimpleNamespace(rows=tuple(r for b in batches for r in b.rows))
        packed = pack_batch(obj.plan, holder, lambda ctx, card: encoded[(ctx, card)], target, pad_id=0)
        scores = reference(input_ids=torch.tensor(packed.input_ids), attention_mask=torch.tensor(packed.attention_mask))['logits']
        n = len(packed.signs)
        loss = -torch.nn.functional.logsigmoid(torch.tensor(packed.signs) * (scores[:n] - scores[n:])).mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(reference.parameters(), 1.0)
        opt.param_groups[0]['lr'] = float(obj.plan.peak_lr_decimal) * batches[0].lr_scale_numerator / batches[0].lr_scale_denominator
        opt.step()
        event = obj.run_next_update()
        events.append(event)
        assert event.completed_steps == step + 1
        assert event.cumulative_global_valid_tokens == batches[0].cumulative_valid_tokens_after_update
        torch.testing.assert_close(obj.model.weight, reference.weight, atol=1e-7, rtol=1e-6)
    assert sum(e.local_valid_tokens for e in events) == obj.plan.planned_valid_tokens
    assert sum(e.local_pair_visits for e in events) == obj.plan.planned_pair_visits
    before = obj.model.weight.detach().clone()
    with pytest.raises(PlanError, match='plan_already_complete'):
        obj.run_next_update()
    assert torch.equal(before, obj.model.weight)


def test_encoding_drift_rejected_before_model_and_poisoned(monkeypatch):
    obj, encoded, _ = make_consumer(monkeypatch)
    for key in encoded:
        encoded[key] = (99,)
    with pytest.raises(PlanError, match='provider_encoding_mismatch'):
        obj.run_next_update()
    assert obj.model.calls == obj.completed_steps == 0
    with pytest.raises(PlanError, match='consumer_failed'):
        obj.run_next_update()


def test_skip_never_commits_cursor(monkeypatch):
    obj, _, _ = make_consumer(monkeypatch)
    obj.accelerator.optimizer_step_was_skipped = True
    with pytest.raises(PlanError, match='optimizer_update_skipped_cursor_not_committed'):
        obj.run_next_update()
    assert obj.completed_steps == 0 and obj.poisoned


@pytest.mark.parametrize('drift', ['mode', 'gas', 'rank', 'world', 'scheduler'])
def test_drift_rejected_before_forward(monkeypatch, drift):
    obj, _, _ = make_consumer(monkeypatch)
    if drift == 'mode':
        obj.model.eval()
    elif drift == 'gas':
        obj.accelerator.gradient_accumulation_steps += 1
    elif drift == 'rank':
        obj.accelerator.process_index = 1
    elif drift == 'world':
        obj.accelerator.num_processes = 2
    else:
        obj.accelerator._schedulers.append(object())
    with pytest.raises(PlanError, match='configuration_drift'):
        obj.run_next_update()
    assert obj.model.calls == obj.completed_steps == 0


@pytest.mark.parametrize('kind', ['nan', 'detached', 'shape', 'dtype', 'missing'])
def test_bad_forward_output_rejected(monkeypatch, kind):
    obj, _, _ = make_consumer(monkeypatch)
    old = obj.model.forward
    def broken(**kwargs):
        logits = old(**kwargs)['logits']
        if kind == 'nan': logits = logits * float('nan')
        if kind == 'detached': logits = logits.detach()
        if kind == 'shape': logits = logits[:, None]
        if kind == 'dtype': logits = logits.double()
        return {'x' if kind == 'missing' else 'logits': logits}
    obj.model.forward = broken
    with pytest.raises(PlanError, match='critic_scalar_logits'):
        obj.run_next_update()
    assert obj.completed_steps == 0 and obj.poisoned


def test_changing_truth_rejected_before_forward(monkeypatch):
    obj, _, target = make_consumer(monkeypatch)
    counts = {}
    def inconsistent(key):
        counts[key] = counts.get(key, 0) + 1
        return target(key) if counts[key] == 1 else -target(key)
    obj.true_sign = inconsistent
    with pytest.raises(PlanError, match='observed_shape_or_sign_mismatch'):
        obj.run_next_update()
    assert obj.model.calls == obj.completed_steps == 0
