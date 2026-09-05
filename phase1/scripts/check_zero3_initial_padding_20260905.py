"""Actual pinned DS partition method on CPU tensors, NOT a DS engine test."""
import json
import os
from types import SimpleNamespace as NS
from unittest.mock import patch

import torch

assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
from deepspeed.runtime.zero import partition_parameters as pp
from phase1.global_local_zero3_padding import initialized_partition_padding
from phase1.global_local_execution_plan import PlanError


def parameter(size, nan=False):
    p = torch.nn.Parameter(torch.arange(size, dtype=torch.bfloat16) + 1)
    if nan:
        p.data[0] = float('nan')
    p.ds_shape = p.shape
    p.ds_numel = p.numel()
    p.ds_tensor = None
    p.ds_status = pp.ZeroParamStatus.AVAILABLE
    p.ds_id = 0
    p.ds_persist = False
    p.ds_active_sub_modules = set()
    return p


def owner(rank):
    return NS(_aligned_size=lambda p: ((p.ds_numel + 1) // 2) * 2,
              _partition_world_size=lambda p: 2, _partition_rank=lambda p: rank,
              remote_device=pp.OffloadDeviceEnum.cpu, local_device='cpu',
              pin_memory=False, quantized_nontrainable_weights=False)


def main():
    torch.set_num_threads(1)
    torch.manual_seed(6)
    torch.use_deterministic_algorithms(True)
    torch.utils.deterministic.fill_uninitialized_memory = True
    original = pp.Init._partition_param
    cases = []
    # Even, odd, and entirely padded scalar rank; original method untouched.
    for size in (1, 3, 4, 7):
        for rank in (0, 1):
            width = (size + 1) // 2
            valid = max(0, min(width, size - rank * width))
            raw = parameter(size)
            expected = raw.detach().flatten()[rank * width:rank * width + valid].clone()
            original(owner(rank), raw)
            assert torch.equal(raw.ds_tensor[:valid], expected)
            assert int((~torch.isfinite(raw.ds_tensor)).sum()) == width - valid
            fixed = parameter(size)
            with initialized_partition_padding() as receipt:
                pp.Init._partition_param(owner(rank), fixed)
            assert pp.Init._partition_param is original
            assert torch.equal(fixed.ds_tensor[:valid], expected)
            assert bool(torch.isfinite(fixed.ds_tensor).all())
            assert not bool(fixed.ds_tensor[valid:].count_nonzero())
            assert receipt['padding_elements_initialized'] == width - valid
            assert receipt['nonfinite_padding_before_initialization'] == width - valid
            # A second (non-initial) partition must not sanitize corruption.
            if width > valid:
                fixed.ds_tensor[-1] = float('nan')
                with initialized_partition_padding() as repeat:
                    pp.Init._partition_param(owner(rank), fixed)
                assert repeat['new_partitions'] == 0 and bool(torch.isnan(fixed.ds_tensor[-1]))
            cases.append({'size':size,'rank':rank,'valid':valid,'padding':width-valid,'passed':True})
    for rank in (0, 1):
        p = parameter(3, nan=True)
        try:
            with initialized_partition_padding():
                pp.Init._partition_param(owner(rank), p)
        except PlanError as exc:
            assert str(exc) == 'zero3_initial_real_parameter_nonfinite'
        else:
            raise AssertionError('real_nan_not_rejected')
        assert p.ds_tensor is None and pp.Init._partition_param is original
    try:
        with initialized_partition_padding():
            with initialized_partition_padding():
                pass
    except PlanError as exc:
        assert str(exc) == 'zero3_padding_hook_nested'
    else:
        raise AssertionError('nested_hook_not_rejected')
    assert pp.Init._partition_param is original and not torch.cuda.is_initialized()
    print(json.dumps({'classification':'PINNED_DS_INITIAL_PARTITION_CPU_REPRO_NOT_GPU',
                      'cases':cases,'real_nan_negative_controls':2,'nested_hook_rejected':True,
                      'gpu_initialized':False,'payload_reads':0},sort_keys=True))


if __name__ == '__main__':
    # Logging alone asks for initialized distributed rank. The real partition
    # computation uses the explicit CPU receiver rank above, not this logger.
    with patch.object(pp, 'print_rank_0', lambda *args, **kwargs: None):
        main()
