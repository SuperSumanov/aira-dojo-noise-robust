"""Actual three-mode production hooks,15cross-thread signal scenarios, CPUonly."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import colocation_production_gate_20261016 as gate


def configure():
    source=inspect.getsource(gate.exercise)
    for old,new in (
        ('import colocation_trial_20261016 as trial','import diverse_trial_20261017 as trial'),
        ('from colocation_readout_20261016 import verify_queue','from diverse_pool_20261017 import independent_audit as verify_queue')):
        assert source.count(old)==1;source=source.replace(old,new)
    needle='            trial.install_hooks(row,ep,deadline)'
    replacement='''            JupyterKernelClient.wait_for_ready=lambda self,*a,**kw:False
            trial.install_hooks(row,ep,deadline)
            from clock_pairing_20261016 import InfrastructureReadinessError
            try:JupyterKernelClient.wait_for_ready(None)
            except InfrastructureReadinessError:pass
            else:raise AssertionError('production readiness failure not propagated')'''
    assert source.count(needle)==1;source=source.replace(needle,replacement)
    exec(compile(source,'actual-diverse-production-gate','exec'),gate.__dict__)


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--index',type=int);p.add_argument('--case',choices=gate.CASES)
    a=p.parse_args();configure()
    if a.case:
        print(json.dumps(gate.exercise(a.root,a.index,a.case),sort_keys=True));return
    rows=[]
    for index in (0,8,16):
        for case in gate.CASES:
            cp=subprocess.run([sys.executable,'-B',__file__,str(a.root),'--index',str(index),'--case',case],capture_output=True,text=True,timeout=60)
            if cp.returncode:
                with (a.root/f'production-gate-{index}-{case}.private.log').open('x') as f:f.write(cp.stdout+cp.stderr)
                raise RuntimeError(f'production gate failed index={index},case={case}')
            r=json.loads(cp.stdout.splitlines()[-1]);assert r['passed'];rows.append(r)
    result=dict(passed=True,cases=rows,production_source_sha256=hashlib.sha256((a.root/'diverse_trial_20261017.py').read_bytes()).hexdigest(),
        interpretation='Actual CPU production installation/readiness/transaction boundaries only, not a GPU acceptance or quality result.')
    with (a.root/'production-guard.safe.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps(dict(passed=True,production_cases=len(rows),gpu_calls=0,model_calls=0)))


if __name__=='__main__':main()
