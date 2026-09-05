"""Scoped, source-pinned initialization of *new* ZeRO-3 partition padding.

No finite-value exception: real elements are checked before and after partition,
and the session still checks every element of every saved state. No hook remains
installed during training or restore. This is not a data/production eligibility gate.
"""
from contextlib import contextmanager
from functools import wraps
import inspect
import math
from pathlib import Path

import torch

from phase1.global_local_critic_session import file_sha
from phase1.global_local_execution_plan import PlanError

PARTITION_FILE_SHA = '8b3c65d20fada0fc85c3685615b0da65247f4e8739313ca1de01b1a3102f2500'


def require(ok, reason):
    if not ok:
        raise PlanError(reason)


def finite(tensor):
    for chunk in tensor.detach().reshape(-1).split(1 << 20):
        require(bool(torch.isfinite(chunk).all()), 'zero3_initial_real_parameter_nonfinite')


@contextmanager
def initialized_partition_padding():
    """Only wrap Accelerator.prepare, before FP32 masters are constructed."""
    from deepspeed.runtime.zero import partition_parameters as pp
    require(file_sha(Path(inspect.getsourcefile(pp.Init))) == PARTITION_FILE_SHA,
            'zero3_partition_runtime_drift')
    original = pp.Init._partition_param
    require(not getattr(original, '_critic_padding_hook', False), 'zero3_padding_hook_nested')
    receipt = {'partition_source_sha256': PARTITION_FILE_SHA,
               'new_partitions': 0, 'padding_elements_initialized': 0,
               'nonfinite_padding_before_initialization': 0}

    @wraps(original)
    def partition(owner, param, buffer=None, has_been_updated=False, free_data=True):
        fresh = param.ds_status == pp.ZeroParamStatus.AVAILABLE and param.ds_tensor is None
        if fresh:
            require(buffer is None and not has_been_updated and param.requires_grad
                    and param.dtype == torch.bfloat16 and not param.ds_persist
                    and owner.remote_device != pp.OffloadDeviceEnum.nvme
                    and not owner.quantized_nontrainable_weights, 'zero3_initial_partition_mode')
            world, rank = owner._partition_world_size(param), owner._partition_rank(param)
            total = param.ds_numel
            require(type(world) is int and world == 2 and type(rank) is int and rank in (0, 1)
                    and type(total) is int and total > 0
                    and total == param.numel() == math.prod(param.ds_shape), 'zero3_partition_geometry')
            width = (total + world - 1) // world
            valid = max(0, min(width, total - rank * width))
            finite(param)
        result = original(owner, param, buffer, has_been_updated, free_data)
        if fresh:
            shard = param.ds_tensor
            require(shard is not None and shard.ndim == 1 and shard.is_contiguous()
                    and shard.numel() == shard.ds_numel == width
                    and shard.dtype == torch.bfloat16 and not shard.requires_grad
                    and shard.final_location is None, 'zero3_partition_result_geometry')
            finite(shard[:valid])
            # This interval contains no model coefficient. In particular a scalar
            # on rank 1 has valid=0, width=1. Never touch a valid prefix.
            with torch.no_grad():
                padding = shard[valid:]
                receipt['nonfinite_padding_before_initialization'] += int((~torch.isfinite(padding)).sum().item())
                padding.zero_()
            finite(shard)
            receipt['new_partitions'] += 1
            receipt['padding_elements_initialized'] += width - valid
        return result

    partition._critic_padding_hook = True
    pp.Init._partition_param = partition
    try:
        yield receipt
    finally:
        unchanged = pp.Init._partition_param is partition
        pp.Init._partition_param = original
        require(unchanged, 'zero3_partition_hook_changed')
