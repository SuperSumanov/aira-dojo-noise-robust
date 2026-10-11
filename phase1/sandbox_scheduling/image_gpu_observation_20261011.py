"""Passive optimizer observation, never a validity gate or CUDA-time estimate."""
INSTRUMENT='''import torch as _r14_torch,time as _r14_time,functools as _r14_functools
_r14_steps=[]
def _r14_wrap(_class,_name):
    _original=_class.step
    @_r14_functools.wraps(_original)
    def _wrapped(self,*args,**kwargs):
        _begin=_r14_time.time()
        _value=_original(self,*args,**kwargs)
        _grads=[p for g in self.param_groups for p in g['params'] if p.grad is not None]
        _r14_steps.append(dict(start=_begin,end=_r14_time.time(),optimizer=_name,
                              devices=sorted({str(p.device) for p in _grads}),gradient_parameters=len(_grads)))
        return _value
    _class.step=_wrapped
for _r14_name in ('Adam','AdamW','SGD','RMSprop','Adagrad','Adadelta','Rprop','ASGD','Adamax','NAdam','RAdam','SparseAdam'):
    _r14_class=getattr(_r14_torch.optim,_r14_name,None)
    if _r14_class is not None and 'step' in _r14_class.__dict__:_r14_wrap(_r14_class,_r14_name)
'''
RECEIPT='''import json as _r14_json
from pathlib import Path as _r14_Path
_r14_Path('gpu_training.json').write_text(_r14_json.dumps(dict(steps=len(_r14_steps),
    cuda_gradient_steps=sum(any(d.startswith('cuda:') for d in r['devices']) and r['gradient_parameters']>0 for r in _r14_steps),
    host_step_intervals=_r14_steps,timings_are_host_calls_not_kernel_durations=True),sort_keys=True))
'''
