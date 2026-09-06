"""Pinned native CPUAdam restart experiment, synthetic vectors, no CUDA context.

Four cases fixed before results: (end,cut)=(4,2),(4,3),(9,7),(33,31).
Compare uninterrupted vs ordinary restore vs native-cache priming using empty
tensors. Priming is a diagnostic candidate, not yet admitted into the consumer.
"""
import copy,hashlib,json,os,re,time
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/cpu-adam-native-resume-20260906')
DS=Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/lib/python3.11/site-packages/deepspeed')
EXPECTED={'ops/adam/cpu_adam.py':'8a65f2a4b90df3e25cc0d21f81c53e10c3f5fffffa5178c2a7bd91c065641cac',
    'ops/csrc/includes/cpu_adam.h':'860efc966eb408c56b277606346b85b7c2f2889db9740090178b70831e5f9584',
    'ops/csrc/adam/cpu_adam_impl.cpp':'27bf2f662fc119c53902011b4cc59ba4e7527b9ade56a13c8b4f1ba1f5f038ee'}


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and os.environ.get('HF_HUB_OFFLINE')=='1'
    assert re.fullmatch('[0-9a-f]{40}',os.environ.get('DIAG_CODE_COMMIT',''))
    assert ROOT.is_dir() and not (ROOT/'result.json').exists()
    assert all(digest(DS/p)==h for p,h in EXPECTED.items())
    import torch
    from deepspeed.ops.adam import DeepSpeedCPUAdam
    assert torch.__version__=='2.11.0+cu128' and not torch.cuda.is_initialized()
    torch.set_num_threads(1);torch.manual_seed(6)
    start=time.monotonic()
    values=torch.linspace(-.12,.34,16384,dtype=torch.float32)
    fixed=torch.arange(values.numel(),dtype=torch.float32).remainder(17).sub_(8).div_(100)
    def make(data=None):
        p=torch.nn.Parameter(values.clone() if data is None else data.detach().clone())
        o=DeepSpeedCPUAdam([p],lr=1e-5,weight_decay=.01,betas=(.9,.999),eps=1e-8,adamw_mode=True)
        return p,o
    def advance(p,o,first,last):
        for step in range(first,last+1):
            p.grad=fixed.mul(step)
            o.step();p.grad=None
    def prime(o,cut):
        empty=torch.empty(0,dtype=torch.float32);g=o.param_groups[0]
        before=copy.deepcopy(o.state_dict());states=tuple(o.state)
        params=[p.detach().clone() for p in states]
        for step in range(1,cut+1):
            rc=o.ds_opt_adam.adam_update(o.opt_id,step,g['lr'],*g['betas'],g['eps'],g['weight_decay'],
                g['bias_correction'],empty,empty,empty,empty)
            assert rc==0
        assert before['param_groups']==o.state_dict()['param_groups']
        for key,state in before['state'].items():
            for k,v in state.items():
                actual=o.state_dict()['state'][key][k]
                assert torch.equal(v,actual) if isinstance(v,torch.Tensor) else v==actual
        assert all(torch.equal(p,q) for p,q in zip(states,params))
    rows=[];native=None
    for end,cut in [(4,2),(4,3),(9,7),(33,31)]:
        full,fo=make();advance(full,fo,1,end)
        prefix,po=make();advance(prefix,po,1,cut);saved=copy.deepcopy(po.state_dict())
        ordinary,oo=make(prefix);oo.load_state_dict(copy.deepcopy(saved));advance(ordinary,oo,cut+1,end)
        primed,co=make(prefix);co.load_state_dict(copy.deepcopy(saved));prime(co,cut);advance(primed,co,cut+1,end)
        def compare(p,o):
            return {'different_master_elements':int(torch.count_nonzero(p.detach()!=full.detach())),
                'max_absolute_master_difference':float((p.detach()-full.detach()).abs().max()),
                'momentum_equal':torch.equal(o.state[p]['exp_avg'],fo.state[full]['exp_avg']),
                'variance_equal':torch.equal(o.state[p]['exp_avg_sq'],fo.state[full]['exp_avg_sq']),
                'step_equal':o.state[p]['step']==fo.state[full]['step']==end}
        rows.append({'end':end,'cut':cut,'ordinary_restore':compare(ordinary,oo),'empty_tensor_primed_restore':compare(primed,co)})
        native=Path(fo.ds_opt_adam.__file__)
    assert not torch.cuda.is_initialized()
    result={'classification':'ACTUAL_NATIVE_CPUADAM_RESTART_DIAGNOSTIC_NOT_MODEL_EFFECT',
        'code_commit':os.environ['DIAG_CODE_COMMIT'],'source_sha256':digest(Path(__file__)),
        'runtime_sources':EXPECTED,'native_extension_sha256':digest(native),
        'torch_version':torch.__version__,'seed':6,'vector_elements':16384,'rows':rows,
        'elapsed_seconds':time.monotonic()-start,'gpu_initialized':False,'corpus_reads':0,
        'priming_changes_no_parameter_or_serialized_optimizer_state':True}
    with (ROOT/'result.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
