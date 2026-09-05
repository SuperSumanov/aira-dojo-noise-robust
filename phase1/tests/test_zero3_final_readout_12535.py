"""Local gate tests, not real checkpoint or GPU acceptance."""
import copy

import pytest

from phase1.scripts.verify_zero3_final_readout_12535_20260906 import acceptance_gate


def accepted_fixture():
    return {'classification': 'INDEPENDENT_TINY_ZERO3_RESUME_ACCEPTANCE_NOT_EFFECT',
        'job_id': '12535', 'code_commit': '09911b15ca065442386120707dccf036e262dadd',
        'gpu_initialized': False,
        'actual_checkpoint_payload_comparisons': [
            {'rank': rank, 'case': case, 'file': name, 'all_payload_bits_equal': True}
            for rank in (0, 1) for case in ('resume2', 'resume3')
            for name in (f'pytorch_model/zero_pp_rank_{rank}_mp_rank_00_model_states.pt',
                         f'pytorch_model/bf16_zero_pp_rank_{rank}_mp_rank_00_optim_states.pt',
                         f'random_states_{rank}.pkl')]}


def test_payload_gate_accepts_complete_fixture():
    acceptance_gate(accepted_fixture())


@pytest.mark.parametrize('field,value', [
    ('classification', 'CPU_FORMAT_FIXTURE'), ('job_id', '12570'),
    ('code_commit', '0'*40), ('gpu_initialized', 0), ('gpu_initialized', True),
])
def test_payload_gate_rejects_wrong_source(field, value):
    obj = accepted_fixture()
    obj[field] = value
    with pytest.raises(ValueError):
        acceptance_gate(obj)


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'false', 'bool_rank', 'other_file', 'extra'])
def test_payload_gate_rejects_partial_or_ambiguous_comparison(mutation):
    obj = accepted_fixture()
    rows = obj['actual_checkpoint_payload_comparisons']
    if mutation == 'missing': rows.pop()
    elif mutation == 'duplicate': rows[-1] = copy.deepcopy(rows[0])
    elif mutation == 'false': rows[0]['all_payload_bits_equal'] = False
    elif mutation == 'bool_rank': rows[0]['rank'] = False
    elif mutation == 'other_file': rows[0]['file'] = 'not-the-fixed-checkpoint'
    elif mutation == 'extra': rows[0]['assumed'] = True
    with pytest.raises(ValueError):
        acceptance_gate(obj)


def make_models():
    torch = pytest.importorskip('torch')
    from torch import nn
    class ScalarFixture(nn.Module):
        def __init__(self):
            super().__init__()
            self.scale = nn.Parameter(torch.tensor([0.25], dtype=torch.bfloat16))
            self.offset = 0
            self.mutate = False
        def forward(self, input_ids, attention_mask):
            if self.mutate:
                self.scale.add_(1)
            return {'logits': (input_ids*attention_mask).sum(1).to(torch.bfloat16)*self.scale+self.offset}
    return [ScalarFixture().eval() for _ in range(3)]


def test_actual_cpu_bf16_forward_helper():
    from phase1.scripts.verify_zero3_final_readout_12535_20260906 import compare_models
    out = compare_models(make_models())
    assert out['final_models'] == out['synthetic_input_rows'] == 3
    assert out['bitwise_final_weights_equal'] and out['bitwise_synthetic_outputs_equal']


@pytest.mark.parametrize('mutation', ['weights', 'mode', 'dtype', 'forward', 'mutating', 'nan'])
def test_actual_cpu_forward_rejects_bad_inputs(mutation):
    from phase1.scripts.verify_zero3_final_readout_12535_20260906 import compare_models
    models = make_models()
    import torch
    if mutation == 'weights':
        with torch.no_grad(): models[1].scale.add_(1)
    elif mutation == 'mode': models[1].train()
    elif mutation == 'dtype': models[1].float()
    elif mutation == 'forward': models[1].offset = 1
    elif mutation == 'mutating':
        for model in models: model.mutate = True
    elif mutation == 'nan':
        for model in models: model.offset = float('nan')
    with pytest.raises(ValueError):
        compare_models(models)
