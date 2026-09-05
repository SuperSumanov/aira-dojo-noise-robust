"""Actual pinned DS converter on generated checkpoint FORMAT, not DS engine."""
from collections import OrderedDict
import copy
import hashlib
import json

import pytest
torch = pytest.importorskip('torch')
pytest.importorskip('deepspeed')
from torch import nn

from phase1.critic_zero3_final_state import load_final_into_cpu
from phase1.global_local_zero3_session import TAG, STATE_KEYS, expected_files
from phase1.global_local_execution_plan import PlanError


def put(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True))


def fixture(root, *, step=4, nonfinite=False):
    root.mkdir()
    (root/TAG).mkdir()
    torch.manual_seed(6)
    model = nn.Sequential(nn.Linear(3, 5, dtype=torch.bfloat16), nn.Linear(5, 1, dtype=torch.bfloat16)).eval()
    model.register_buffer('calibration_constant', torch.tensor([1.25], dtype=torch.float32))
    expected = copy.deepcopy(model)
    shapes = OrderedDict((n, p.shape) for n, p in model.named_parameters())
    parts = [[], []]
    with torch.no_grad():
        for index, (name, p) in enumerate(expected.named_parameters()):
            full = (torch.arange(p.numel(), dtype=torch.float32).reshape(p.shape)+index+1)/71
            p.copy_(full.to(p.dtype))
            width = (p.numel()+1)//2
            padded = torch.nn.functional.pad(full.flatten(), (0, 2*width-p.numel()))
            for rank in (0, 1): parts[rank].append(padded[rank*width:(rank+1)*width].clone())
    if nonfinite: parts[1][0][0] = float('nan')
    binding = {'world': 2, 'total_steps': 4, 'fixture_only_no_source_qualification': True}
    for rank in (0, 1):
        torch.save({'module': {'calibration_constant': expected.calibration_constant},
            'buffer_names': ['calibration_constant'], 'param_shapes': [shapes], 'shared_params': {},
            'ds_version': '0.19.3'}, root/TAG/f'zero_pp_rank_{rank}_mp_rank_00_model_states.pt')
        torch.save({'optimizer_state_dict': {'zero_stage': 3, 'partition_count': 2,
            'fp32_flat_groups': [torch.cat(parts[rank])], 'optimizer_state_dict': {}}},
            root/TAG/f'bf16_zero_pp_rank_{rank}_mp_rank_00_optim_states.pt')
        torch.save({}, root/f'random_states_{rank}.pkl')
        put(root/f'observed_{rank}.json', {'rank': rank, 'binding': binding, 'completed_steps': step,
            'cumulative_valid_tokens': step*20, 'state': {k: 'a'*64 for k in STATE_KEYS},
            'counters': {'global_steps': step, 'global_samples': step*128, 'skipped_steps': 0,
                'micro_steps': step, 'micro_step_id': 0, 'step_applied': True}})
    # This must never be executed even though it is in the authenticated bundle.
    (root/'zero_to_fp32.py').write_text("raise RuntimeError('CHECKPOINT_SCRIPT_MUST_NOT_EXECUTE')\n")
    files = {name: {'bytes': (root/name).stat().st_size, 'sha256': hashlib.sha256((root/name).read_bytes()).hexdigest()}
             for name in expected_files()}
    put(root/'manifest.json', {'protocol': 'critic-zero3-checkpoint-v1', 'binding': binding,
        'completed_steps': step, 'cumulative_valid_tokens': step*20, 'files': files})
    sha = hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()
    return model, expected, binding, sha


def test_actual_converter_odd_partitions_and_bf16_inference(tmp_path):
    model, expected, binding, sha = fixture(tmp_path/'cp')
    result = load_final_into_cpu(model, tmp_path/'cp', binding=binding, manifest_sha256=sha, expected_tokens=80)
    assert all(torch.equal(model.state_dict()[k], v) for k, v in expected.state_dict().items())
    with torch.inference_mode():
        x = torch.tensor([[1., 2., 3.], [-1., .5, 2.]], dtype=torch.bfloat16)
        assert torch.equal(model(x), expected(x))
    assert result['state_elements'] == 27 and result['state_tensor_count'] == 5
    assert result['inference_only_optimizer_and_rng_not_restored']
    assert result['copied_checkpoint_script_executed'] is False
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('change,reason', [
    ('partial', 'final_readout_incomplete_checkpoint'),
    ('tokens', 'final_readout_incomplete_checkpoint'),
    ('manifest', 'zero3_manifest_hash'),
    ('training', 'final_readout_eval_required'),
    ('extra', 'zero3_file_set'),
    ('shape', 'final_readout_parameter_set'),
    ('nonfinite', 'final_readout_nonfinite_master'),
])
def test_rejects_incomplete_or_incompatible_state(tmp_path, change, reason):
    model, expected, binding, sha = fixture(tmp_path/'cp', step=2 if change == 'partial' else 4,
        nonfinite=change == 'nonfinite')
    if change == 'manifest': sha = 'f'*64
    if change == 'training': model.train()
    if change == 'extra': (tmp_path/'cp'/'latest').write_text(TAG)
    if change == 'shape': model = nn.Linear(3, 2).eval()
    with pytest.raises(PlanError, match=reason):
        load_final_into_cpu(model, tmp_path/'cp', binding=binding, manifest_sha256=sha,
            expected_tokens=81 if change == 'tokens' else 80)


def test_rejects_checkpoint_change_during_conversion(tmp_path, monkeypatch):
    from deepspeed.utils import zero_to_fp32
    model, expected, binding, sha = fixture(tmp_path/'cp')
    before = copy.deepcopy(model.state_dict())
    original = zero_to_fp32.get_fp32_state_dict_from_zero_checkpoint
    def changing(*args, **kwargs):
        out = original(*args, **kwargs)
        (tmp_path/'cp'/'random_states_0.pkl').write_bytes(b'changed')
        return out
    monkeypatch.setattr(zero_to_fp32, 'get_fp32_state_dict_from_zero_checkpoint', changing)
    with pytest.raises(PlanError, match='zero3_member_hash'):
        load_final_into_cpu(model, tmp_path/'cp', binding=binding, manifest_sha256=sha, expected_tokens=80)
    assert all(torch.equal(model.state_dict()[k], v) for k, v in before.items())
