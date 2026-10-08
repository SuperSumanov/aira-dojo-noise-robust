"""Passive Adam-step accounting; no parameter/optimizer/seed changes."""
INSTRUMENT='''import torch as _r14_torch, time as _r14_time, functools as _r14_functools
_r14_steps=[]
_r14_adam_step=_r14_torch.optim.Adam.step
@_r14_functools.wraps(_r14_adam_step)
def _r14_step(self,*args,**kwargs):
    _before=_r14_time.time()
    _grads=[p for g in self.param_groups for p in g['params'] if p.grad is not None]
    _devices=sorted({str(p.device) for p in _grads})
    _result=_r14_adam_step(self,*args,**kwargs)
    _r14_steps.append(dict(start=_before,end=_r14_time.time(),devices=_devices,gradient_parameters=len(_grads)))
    return _result
_r14_torch.optim.Adam.step=_r14_step
'''

RECEIPT='''import json as _r14_json
from pathlib import Path as _r14_Path
assert _r14_steps and all(r['devices']==['cuda:0'] and r['gradient_parameters']>0 for r in _r14_steps)
_r14_torch.cuda.synchronize()
_r14_Path('gpu_training.json').write_text(_r14_json.dumps(dict(backend='torch.Adam',device='cuda:0',steps=len(_r14_steps),
    first_step_start=_r14_steps[0]['start'],last_step_end=_r14_steps[-1]['end'],host_step_intervals=_r14_steps,
    timings_are_host_calls_not_kernel_durations=True),sort_keys=True))
'''
