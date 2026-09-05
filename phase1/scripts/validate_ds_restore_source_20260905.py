"""Exercise actual pinned DS load_checkpoint control flow with a CPU test double.

No engine initialization, tensors, model, checkpoint files or GPU. This checks
the adapter's interception point; it cannot certify real optimizer restoration.
"""
import hashlib
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace as NS

assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
from deepspeed.runtime.engine import DeepSpeedEngine
from phase1.global_local_ds_completion import observe_deepspeed_restore
from phase1.global_local_execution_plan import PlanError

SOURCE_SHA='5728d3dfa42a3d6c44836873002f5ccfb9e72091c98029b3843b30ec5651161f'
assert hashlib.sha256(inspect.getsource(DeepSpeedEngine.load_checkpoint).encode()).hexdigest()==SOURCE_SHA


class Receiver:
    load_checkpoint=DeepSpeedEngine.load_checkpoint
    def __init__(self, succeeds):
        self.succeeds=succeeds;self.global_steps=0;self.skipped_steps=0;self.lr_scheduler=None
        self.has_moe_layers=False;self.fallback_used=False
        self.optimizer=NS(_restore_from_bit16_weights=self.fallback)
    def fallback(self):self.fallback_used=True
    def _optimizer_has_ckpt_event_prologue(self):return False
    def _optimizer_has_ckpt_event_epilogue(self):return False
    def zero_optimization(self):return True
    def zero_nvme_offload_optimizer(self):return False
    def zero_optimization_partition_weights(self):return True
    def load_universal_checkpoint(self):return False
    def _load_checkpoint(self,*args,**kwargs):
        self.global_steps=3
        return '/synthetic/verified/pytorch_model/model.pt',{'critic_session':{'contract':'fixed'}}
    def _load_zero_checkpoint(self,*args,**kwargs):return self.succeeds


baseline=Receiver(False)
baseline.load_checkpoint('/synthetic/verified','pytorch_model')
assert baseline.fallback_used,'actual_source_negative_control_did_not_exercise_fallback'
cases=[]
for succeeds in (False,True):
    e=Receiver(succeeds);o=NS(optimizer=e.optimizer)
    a=NS(distributed_type='DEEPSPEED',deepspeed_engine_wrapped=NS(engine=e),_optimizers=[o])
    stopped=False
    try:
        with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}) as observed:
            e.load_checkpoint('/synthetic/verified','pytorch_model')
    except PlanError as exc:
        assert not succeeds and str(exc)=='zero_optimizer_restore_failed_no_weight_only_fallback'
        stopped=True
    assert not e.fallback_used
    assert stopped is (not succeeds)
    cases.append({'mock_partition_restore_succeeds':succeeds,'stopped_before_fallback':stopped,
                  'real_ds_control_flow_used':True,'pass':True})
result={'classification':'PINNED_DS_SOURCE_OBSERVER_CHECK_NOT_HARDWARE_RESTORE',
        'load_checkpoint_sha256':SOURCE_SHA,'unguarded_failure_invoked_fallback':True,
        'cases':cases,'gpu_used':False,'real_engine_initialized':False,'checkpoint_files_read':0,
        'code_commit':os.environ['DS_RESTORE_CODE_COMMIT']}
output=Path(os.environ['DS_RESTORE_OUTPUT'])
with output.open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True))
