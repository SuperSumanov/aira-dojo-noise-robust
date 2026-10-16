"""CPU-only frozen-entry bypass reproduction and repaired dispatch regression.

Loads the old CLOSED root read-only; the new entry file is in a separate stage.
Fresh subprocesses prevent patched classes leaking between cases. No Slurm,
kernel, model request, checkpoint, or original experiment file is modified.
"""
import argparse
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v1')
PIN = 'f08b3052fcecf467f500b5b9aa6638087c602321ca3a81bf22ef8b65a55b41f9'
CASES = ('success','queue','admit','cancel','release')


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def exercise(variant, index, case):
    assert sha(ROOT/'plan.json') == PIN and (ROOT/'closed.json').is_file()
    sys.path.insert(0,str(ROOT))
    name='generation_quota_trial_20261017'
    if variant=='repaired':
        path=Path(__file__).with_name(name+'.py')
        assert path.parent != ROOT
        spec=importlib.util.spec_from_file_location(name,path)
        trial=importlib.util.module_from_spec(spec);sys.modules[name]=trial;spec.loader.exec_module(trial)
    else:
        trial=__import__(name)
    import colocation_production_gate_20261016 as gate
    source=inspect.getsource(gate.exercise)
    source=source.replace('import colocation_trial_20261016 as trial','import generation_quota_trial_20261017 as trial')
    needle='            trial.install_hooks(row,ep,deadline)'
    replacement='''            actual=trial.host()
            assert actual.install_hooks is trial.common.original.install_hooks,'native host bypasses quota hook'
            assert actual.worker.__globals__['install_hooks'] is actual.install_hooks,'worker binding differs'
            import live_runtime_hooks as hooks
            with patch.object(hooks,'wait_for_ready',lambda *a,**kw:False):
                actual.install_hooks(row,ep,deadline)
            import feedback_parent_policy_20261012 as parent
            assert parent.select_request.quota_mode==row['quota_mode']
            fixture_state=dict(active=[dict(task='fixture'),dict(task='fixture')],
                waiting=[dict(key='third',task='fixture',role='analyze',requested=0,run=0)])
            selected,_=parent.select_request(fixture_state,'fixture','greedy')
            assert selected==('third' if row['quota_mode']=='pooled' else None)
            from clock_pairing_20261016 import InfrastructureReadinessError
            try:JupyterKernelClient.wait_for_ready(None)
            except InfrastructureReadinessError:pass
            else:raise AssertionError('readiness failure did not propagate')'''
    assert source.count(needle)==1;source=source.replace(needle,replacement)
    exec(compile(source,'native-dispatch-regression','exec'),gate.__dict__)
    try:
        result=gate.exercise(ROOT,index,case)
    except AssertionError as e:
        if variant!='frozen' or str(e)!='native host bypasses quota hook': raise
        return dict(variant=variant,index=index,case=case,expected_bypass_detected=True,model_calls=0,gpu_calls=0)
    assert variant=='repaired'
    # Deliberately restore the frozen deeper binding to show the new per-worker
    # guard detects this exact regression, before executing any worker action.
    current=trial.common.original.base.c.trial.install_hooks
    trial.common.original.base.c.trial.install_hooks=lambda *a,**k:None
    try:
        try: trial.runtime_hook_guard()
        except AssertionError: pass
        else: raise AssertionError('new guard missed decoupled dispatch')
    finally: trial.common.original.base.c.trial.install_hooks=current
    return dict(variant=variant,actual_host_hook=True,guard_negative_control=True,**result)


def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',choices=('frozen','repaired'))
    p.add_argument('--index',type=int);p.add_argument('--case',choices=CASES);a=p.parse_args()
    if a.variant:
        print(json.dumps(exercise(a.variant,a.index,a.case),sort_keys=True));return
    results=[]
    matrix=[('frozen',i,'success') for i in (0,8)]+[('repaired',i,c) for i in (0,8) for c in CASES]
    for variant,index,case in matrix:
        cp=subprocess.run([sys.executable,'-B',__file__,'--variant',variant,'--index',str(index),'--case',case],
            text=True,capture_output=True,timeout=60)
        if cp.returncode:
            # No raw source/environment output; preserve private failure evidence.
            name=Path(__file__).with_name(f'quota-cpu-failure-{variant}-{index}-{case}.private.log')
            with name.open('x') as f:f.write(cp.stdout+cp.stderr)
            raise RuntimeError(f'CPU regression failed: {variant}/{index}/{case}')
        results.append(json.loads(cp.stdout.splitlines()[-1]))
    out=dict(passed=True,frozen_bypass_reproductions=2,repaired_cases=10,model_calls=0,gpu_calls=0,
        old_plan_sha256=PIN,reader_sha256=sha(__file__),
        repaired_entry_sha256=sha(Path(__file__).with_name('generation_quota_trial_20261017.py')),
        rows=results,limitations=['CPU dispatch/selector/signal regression only; no live treatment validation.',
        'Sealed19004 remains invalid for quota comparison and is never reopened.'])
    destination=Path(__file__).with_name('quota-hook-regression-20261017.safe.json')
    with destination.open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
    print(json.dumps(out,sort_keys=True))


if __name__=='__main__':main()
