"""Actual pinned ZeRO-3 partition save/load methods, CPU test receiver only.

No real DS engine or GPU; Torch AdamW substitutes for CPUAdam here. This proves
the partition-state observer sees real tensors, not hardware qualification.
"""
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import random
from types import SimpleNamespace as NS

import numpy as np
import torch

assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
from deepspeed.runtime.engine import DeepSpeedEngine as Engine
from deepspeed.runtime.zero.stage3 import DeepSpeedZeroOptimizer_Stage3 as Zero
from deepspeed.runtime.fp16.loss_scaler import LossScaler
from phase1.global_local_zero3_session import current_state, file_sha, runtime_binding, expected_files, TAG


class Receiver:
    _rigid_state_dict=Zero._rigid_state_dict
    _rigid_load_state_dict=Zero._rigid_load_state_dict
    _set_fp32_optimizer_param_groups=Zero._set_fp32_optimizer_param_groups
    _clear_fp32_optimizer_param_groups=Zero._clear_fp32_optimizer_param_groups
    _zero3_partition_group_metadata=lambda self:None
    unflatten=staticmethod(torch._utils._unflatten_dense_tensors)
    @property
    def loss_scale(self):return self.loss_scaler.cur_scale
    def __init__(self,rank,offset):
        self.model=torch.nn.Linear(4,2,bias=False).bfloat16()
        self.master=torch.nn.Parameter(torch.arange(4,dtype=torch.float32)/20+rank+offset)
        self.model.weight.ds_tensor=self.master.detach().bfloat16().clone()
        self.fp16_groups=[[self.model.weight]]
        self.fp32_partitioned_groups_flat=[self.master]
        self.fp16_partitioned_groups_flat=[self.model.weight.ds_tensor]
        self.fp16_partitioned_groups=[[self.model.weight.ds_tensor]]
        self.sub_group_to_group_id=[0]
        self.optimizer=torch.optim.AdamW([self.master],lr=0.01,weight_decay=0.1)
        self.optimizer.param_groups[0]['params']=[]
        self.dynamic_loss_scale=False;self.overflow=False;self.loss_scaler=LossScaler(1.0)
        self.partition_count=2;self.swap_optimizer=False;self.elastic_checkpoint=False
    def advance(self):
        self._set_fp32_optimizer_param_groups()
        self.master.grad=torch.arange(4,dtype=torch.float32)+0.1
        self.optimizer.step();self.master.grad=None
        self._clear_fp32_optimizer_param_groups()
        self.fp16_partitioned_groups_flat[0].copy_(self.master.detach())
    def consumer(self):
        engine=NS(module=self.model,optimizer=self)
        optimizer=NS(optimizer=self)
        accelerator=NS(distributed_type='DEEPSPEED',deepspeed_engine_wrapped=NS(engine=engine),
                       _optimizers=[optimizer],device=torch.device('cpu'))
        return NS(model=engine,optimizer=optimizer,accelerator=accelerator)


def main():
    runtime=runtime_binding()
    root=Path(os.environ['ZERO3_CPU_OUTPUT'])
    assert root.is_absolute() and root.is_relative_to(Path('/tmp')) and not root.exists()
    root.mkdir(mode=0o700)
    torch.set_num_threads(1);torch.manual_seed(6);random.seed(6);np.random.seed(6)
    rows=[]
    for rank in (0,1):
        first=Receiver(rank,0);first.advance();first.advance()
        rng=(random.getstate(),np.random.get_state(),torch.get_rng_state())
        before=current_state(first.consumer())
        path=root/f'synthetic_optimizer_rank_{rank}.pt'
        torch.save(first._rigid_state_dict(),path)
        digest=file_sha(path)
        second=Receiver(rank,10)
        assert file_sha(path)==digest
        data=torch.load(path,map_location='cpu',weights_only=False)
        second._rigid_load_state_dict(data,load_optimizer_states=True)
        random.setstate(rng[0]);np.random.set_state(rng[1]);torch.set_rng_state(rng[2])
        assert current_state(second.consumer())==before
        # The methods can restore masters while deliberately skipping AdamW.
        # Our full-state observer must reject precisely that incomplete restore.
        third=Receiver(rank,10)
        third._rigid_load_state_dict(deepcopy(data),load_optimizer_states=False)
        random.setstate(rng[0]);np.random.set_state(rng[1]);torch.set_rng_state(rng[2])
        bad=current_state(third.consumer())
        assert bad['master_shards']==before['master_shards'] and bad['adamw']!=before['adamw']
        # Continued updates also match, not only the immediate restore value.
        first.advance();second.advance()
        assert current_state(first.consumer())==current_state(second.consumer())
        naming=NS(_get_zero_ckpt_prefix=lambda dp_rank,bf16_mode:Engine._get_zero_ckpt_prefix(
            NS(),dp_rank,bf16_mode=bf16_mode))
        name=Engine._get_rank_zero_ckpt_name(naming,'/synthetic',TAG,0,rank,True)
        assert Path(name).relative_to('/synthetic').as_posix() in expected_files()
        rows.append({'synthetic_rank':rank,'checkpoint_sha256':digest,'full_restore_equal':True,
                     'missing_optimizer_rejected_by_observer':True,'continued_update_equal':True})
    result={'classification':'ACTUAL_ZERO3_PARTITION_METHODS_CPU_RECEIVER_NOT_GPU',
            'code_commit':os.environ['ZERO3_CODE_COMMIT'],'seed':6,'cases':rows,'runtime_binding':runtime,
            'real_ds_engine':False,'optimizer':'TorchAdamW_CPU_control_not_DeepSpeedCPUAdam',
            'gpu_initialized':torch.cuda.is_initialized(),'corpus_files_opened':0,
            'session_source_sha256':file_sha(Path(__file__).parents[1]/'global_local_zero3_session.py'),
            'driver_source_sha256':file_sha(Path(__file__))}
    assert result['gpu_initialized'] is False
    (root/'summary.json').write_text(json.dumps(result,sort_keys=True,indent=2))
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
