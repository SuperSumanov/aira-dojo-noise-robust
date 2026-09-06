"""Exercise the production cache-restoration helper against real native CPUAdam."""
import copy,hashlib,json,os,time
from pathlib import Path
import torch
from deepspeed.ops.adam import DeepSpeedCPUAdam
from phase1.global_local_cpu_adam_resume import restore_native_cache
from phase1.global_local_execution_plan import PlanError


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not torch.cuda.is_initialized()
    torch.set_num_threads(1);torch.manual_seed(6)
    start=time.monotonic();rows=[]
    values=torch.linspace(-.12,.34,16384,dtype=torch.float32)
    fixed=torch.arange(values.numel(),dtype=torch.float32).remainder(17).sub_(8).div_(100)
    def make(data=None):
        p=torch.nn.Parameter(values.clone() if data is None else data.detach().clone())
        return p,DeepSpeedCPUAdam([p],lr=1e-5,weight_decay=.01,betas=(.9,.999),eps=1e-8,adamw_mode=True)
    def advance(p,o,first,last):
        for step in range(first,last+1):p.grad=fixed.mul(step);o.step();p.grad=None
    for repeat in ('A','B'):
        for end,cut in ((4,2),(4,3),(9,7),(33,31)):
            full,fo=make();advance(full,fo,1,end)
            prefix,po=make();advance(prefix,po,1,cut)
            resumed,ro=make(prefix);ro.load_state_dict(copy.deepcopy(po.state_dict()))
            before=resumed.detach().clone();state=copy.deepcopy(ro.state[resumed]);rng=torch.get_rng_state().clone()
            ro.param_groups[0]['params']=[]
            receipt=restore_native_cache(ro,cut)
            assert receipt['empty_native_calls']==cut and receipt['parameter_elements_passed']==receipt['python_optimizer_step_calls']==0
            assert torch.equal(resumed,before) and torch.equal(torch.get_rng_state(),rng)
            for k,v in state.items():assert torch.equal(v,ro.state[resumed][k]) if isinstance(v,torch.Tensor) else v==ro.state[resumed][k]
            try:restore_native_cache(ro,cut)
            except PlanError as e:assert str(e)=='native_cache_already_attempted'
            else:raise AssertionError('duplicate restore was accepted')
            ro.param_groups[0]['params']=[resumed];advance(resumed,ro,cut+1,end)
            assert torch.equal(full,resumed)
            assert ro.state[resumed]['step']==fo.state[full]['step']==end
            for k in ('exp_avg','exp_avg_sq'):assert torch.equal(ro.state[resumed][k],fo.state[full][k])
            rows.append({'repeat':repeat,'end':end,'cut':cut,'all_final_bits_equal':True,
                'priming_preserved_parameters_moments_and_rng':True,'duplicate_restore_rejected':True,'cache_receipt':receipt})
    assert not torch.cuda.is_initialized()
    result={'classification':'REAL_NATIVE_CPUADAM_HELPER_AB_VALIDATION_NOT_GPU_OR_EFFECT','rows':rows,
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'code_commit':os.environ['DIAG_CODE_COMMIT'],
        'elapsed_seconds':time.monotonic()-start,'gpu_initialized':False,'corpus_reads':0}
    output=Path(os.environ['NATIVE_CACHE_VALIDATION_OUTPUT'])
    with output.open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps({'status':result['classification'],'cases':len(rows),'receipt_sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
